"""
Report handlers: profit, inventory, sales statistics.
"""
import logging

from bale import CallbackQuery

from app.database.crud import get_admin_by_chat_id
from app.services.report_service import get_profit_report, get_inventory_report, get_sales_report
from app.bot.keyboards.inline import reports_menu_keyboard
from app.utils.formatters import (
    format_profit_report, format_inventory_report, to_persian_digits, format_price
)

logger = logging.getLogger(__name__)


async def callback_reports_menu(callback: CallbackQuery):
    """Show reports menu."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    await callback.message.edit(
        "📊 گزارش‌ها و حسابداری\nاز منوی زیر انتخاب کنید:",
        components=reports_menu_keyboard()
    )


async def callback_report_profit(callback: CallbackQuery, period: str = "all"):
    """Show profit report."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    # loading: "⏳ در حال محاسبه..."

    if period == "month":
        from datetime import datetime
        now = datetime.utcnow()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data = await get_profit_report(start_date=start)
        period_label = "ماه جاری"
    else:
        data = await get_profit_report()
        period_label = "کل"

    text = format_profit_report(data, period_label)

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    back_kb = build_kb([[
        InlineKeyboardButton("🔙 بازگشت", callback_data="menu:reports")
    ]])
    await callback.message.edit(text, components=back_kb)


async def callback_report_inventory(callback: CallbackQuery):
    """Show inventory status report."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    # loading: "⏳ در حال بارگذاری..."

    data = await get_inventory_report()
    text = format_inventory_report(data)

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    back_kb = build_kb([[
        InlineKeyboardButton("🔙 بازگشت", callback_data="menu:reports")
    ]])
    await callback.message.edit(text, components=back_kb)


async def callback_report_sales(callback: CallbackQuery, period: str = "month"):
    """Show sales report."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    # loading: "⏳ در حال محاسبه..."

    data = await get_sales_report(period)

    top_text = "\n".join(
        f"  {i + 1}. [{p['sku']}] {p['name']} — {to_persian_digits(str(p['sold']))} فروخته شده"
        for i, p in enumerate(data["top_products"])
    ) or "  داده‌ای موجود نیست"

    text = (
        f"📈 گزارش فروش — {data['period']}\n"
        "━━━━━━━━━━━━━━━\n"
        f"📦 تعداد سفارشات: {to_persian_digits(str(data['orders_count']))}\n"
        f"🛍 اقلام فروخته شده: {to_persian_digits(str(data['items_sold']))}\n"
        f"💰 درآمد: {format_price(data['revenue'])}\n"
        "━━━━━━━━━━━━━━━\n"
        f"🏆 پرفروش‌ترین محصولات:\n{top_text}"
    )

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    back_kb = build_kb([[
        InlineKeyboardButton("🔙 بازگشت", callback_data="menu:reports")
    ]])
    await callback.message.edit(text, components=back_kb)
