import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any

from app.database.crud import (
    get_paid_orders_between,
    get_expenses_between,
    get_partner_transactions_between,
    get_all_partners
)
from app.utils.formatters import format_price, to_persian_digits

logger = logging.getLogger(__name__)

async def calculate_pl_report(start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
    """
    Calculate Profit & Loss (P&L) and partner equity.
    """
    orders = await get_paid_orders_between(start_date, end_date)
    expenses = await get_expenses_between(start_date, end_date)
    partner_txs = await get_partner_transactions_between(start_date, end_date)
    partners = await get_all_partners()

    # 1. Revenue & COGS
    total_revenue = 0
    total_cogs = 0
    total_shipping_paid_by_us = 0
    total_discounts = 0

    for order in orders:
        # total_amount includes what customer paid (after discount, including shipping if they paid it)
        total_revenue += order.total_amount
        total_shipping_paid_by_us += order.shipping_cost
        total_discounts += order.discount_amount

        for item in order.items:
            # If buy_price was not set properly for older items, fallback to current product buy_price
            bp = item.buy_price if item.buy_price > 0 else (item.product.buy_price or 0)
            total_cogs += (bp * item.quantity)

    # 2. OPEX (Operating Expenses)
    total_opex = sum(e.amount for e in expenses)

    # 3. Gross & Net Profit
    # Revenue is what entered the bank account.
    # But for gross profit, we just want: Sales Revenue - COGS - Actual Shipping - Discounts
    gross_profit = total_revenue - total_cogs - total_shipping_paid_by_us
    net_profit = gross_profit - total_opex

    # 4. Partner Equities
    partner_data = []
    for p in partners:
        share_percentage = p.equity_share / 100.0
        profit_share = net_profit * share_percentage
        
        # Calculate drawings (withdrawals) or injections
        drawings = sum(t.amount for t in partner_txs if t.partner_id == p.id and t.type == "DRAWING")
        injections = sum(t.amount for t in partner_txs if t.partner_id == p.id and t.type == "INJECTION")
        
        net_payable = profit_share - drawings + injections
        
        partner_data.append({
            "name": p.name,
            "share_percent": p.equity_share,
            "profit_share": profit_share,
            "drawings": drawings,
            "injections": injections,
            "net_payable": net_payable
        })

    return {
        "orders_count": len(orders),
        "total_revenue": total_revenue,
        "total_cogs": total_cogs,
        "total_shipping": total_shipping_paid_by_us,
        "total_discounts": total_discounts,
        "gross_profit": gross_profit,
        "total_opex": total_opex,
        "net_profit": net_profit,
        "partners": partner_data
    }

def format_pl_report(data: Dict[str, Any], title: str = "گزارش مالی") -> str:
    """Format the P&L dict into a nice readable string."""
    text = f"📊 {title}\n━━━━━━━━━━━━━━━\n"
    text += f"📦 تعداد سفارشات موفق: {to_persian_digits(str(data['orders_count']))}\n"
    text += f"💳 مجموع پرداختی مشتریان: {format_price(data['total_revenue'])}\n"
    text += f"🏷 مجموع تخفیف‌ها: {format_price(data['total_discounts'])}\n"
    text += f"🚚 هزینه ارسال (به پست): {format_price(data['total_shipping'])}\n"
    text += f"🛒 بهای تمام شده کالا (COGS): {format_price(data['total_cogs'])}\n"
    text += "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
    text += f"💰 سود ناخالص: {format_price(data['gross_profit'])}\n"
    text += f"💸 هزینه‌های جاری (OPEX): {format_price(data['total_opex'])}\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    # Net profit icon
    icon = "📈" if data['net_profit'] >= 0 else "📉"
    text += f"{icon} سود خالص: {format_price(data['net_profit'])}\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    if data['partners']:
        text += "👥 سهم شرکا:\n"
        for p in data['partners']:
            text += f"🔹 {p['name']} ({to_persian_digits(str(p['share_percent']))}٪):\n"
            text += f"   سود: {format_price(p['profit_share'])}\n"
            text += f"   برداشت: {format_price(p['drawings'])}\n"
            if p['injections'] > 0:
                text += f"   آورده جدید: {format_price(p['injections'])}\n"
            text += f"   👈 قابل پرداخت: {format_price(p['net_payable'])}\n"

    return text
