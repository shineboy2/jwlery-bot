"""
Financial and inventory reporting service.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.database.base import async_session
from app.database.models import Order, OrderItem, Product, ProductImage
from app.core.constants import OrderStatus


async def get_profit_report(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    Calculate profit report for a given period.

    Returns:
    {
        "total_revenue": sum of sold_price * quantity for PAID/SHIPPED/DELIVERED orders,
        "total_cost": sum of buy_price * quantity,
        "total_shipping": sum of shipping_cost,
        "total_discount": sum of discount_amount,
        "net_profit": revenue - cost,
        "order_count": count of non-cancelled orders,
    }
    """
    completed_statuses = [
        OrderStatus.PAID.value,
        OrderStatus.SHIPPED.value,
        OrderStatus.DELIVERED.value,
    ]

    async with async_session() as session:
        # Build query for orders
        order_query = (
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .where(Order.status.in_(completed_statuses))
        )

        if start_date:
            order_query = order_query.where(Order.created_at >= start_date)
        if end_date:
            order_query = order_query.where(Order.created_at <= end_date)

        result = await session.execute(order_query)
        orders = result.scalars().all()

    total_revenue = 0
    total_cost = 0
    total_shipping = 0
    total_discount = 0

    for order in orders:
        total_shipping += order.shipping_cost
        total_discount += order.discount_amount
        for item in order.items:
            total_revenue += item.sold_price * item.quantity
            total_cost += item.product.buy_price * item.quantity

    net_profit = total_revenue - total_cost

    return {
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_shipping": total_shipping,
        "total_discount": total_discount,
        "net_profit": net_profit,
        "order_count": len(orders),
    }


async def get_inventory_report() -> dict:
    """
    Current inventory status report.

    Returns:
    {
        "total_products": count,
        "total_stock": sum of stock_quantity,
        "total_reserved": sum of reserved_quantity,
        "low_stock_products": products where stock_quantity <= 2,
        "out_of_stock_products": products where stock_quantity == 0,
        "inventory_value_buy": sum of (buy_price * stock_quantity),
        "inventory_value_sell": sum of (base_sell_price * stock_quantity),
    }
    """
    async with async_session() as session:
        result = await session.execute(select(Product))
        products = result.scalars().all()

    total_products = len(products)
    
    active_products = [p for p in products if p.status == "ACTIVE"]
    total_active = len(active_products)
    total_inactive = total_products - total_active

    total_stock = sum(p.stock_quantity for p in products)
    total_reserved = sum(p.reserved_quantity for p in products)
    
    inventory_value_buy = sum(p.buy_price * p.stock_quantity for p in products)
    inventory_value_sell = sum(p.base_sell_price * p.stock_quantity for p in products)

    low_stock = [
        {"sku": p.sku, "name": p.description[:30], "stock": p.stock_quantity}
        for p in active_products if 0 < p.stock_quantity <= 2
    ]

    out_of_stock = [
        {"sku": p.sku, "name": p.description[:30]}
        for p in active_products if p.stock_quantity == 0
    ]

    return {
        "total_products": total_products,
        "total_active": total_active,
        "total_inactive": total_inactive,
        "total_stock": total_stock,
        "total_reserved": total_reserved,
        "low_stock_products": low_stock,
        "out_of_stock_products": out_of_stock,
        "inventory_value_buy": inventory_value_buy,
        "inventory_value_sell": inventory_value_sell,
    }


async def get_sales_report(period: str = "month") -> dict:
    """
    Sales statistics for a given period.

    period: "week" | "month" | "all"

    Returns:
    {
        "period": "...",
        "orders_count": ...,
        "items_sold": ...,
        "revenue": ...,
        "top_products": [{"sku": "NK-001", "sold": 5}, ...],  # top 5
    }
    """
    now = datetime.utcnow()
    if period == "week":
        start_date = now - timedelta(days=7)
        period_text = "هفته گذشته"
    elif period == "month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_text = "ماه جاری"
    else:
        start_date = None
        period_text = "کل"

    completed_statuses = [
        OrderStatus.PAID.value,
        OrderStatus.SHIPPED.value,
        OrderStatus.DELIVERED.value,
    ]

    async with async_session() as session:
        order_query = (
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .where(Order.status.in_(completed_statuses))
        )
        if start_date:
            order_query = order_query.where(Order.created_at >= start_date)

        result = await session.execute(order_query)
        orders = result.scalars().all()

    orders_count = len(orders)
    revenue = 0
    items_sold = 0
    product_sales = {}  # {sku: {"sku": ..., "name": ..., "sold": ...}}

    for order in orders:
        for item in order.items:
            revenue += item.sold_price * item.quantity
            items_sold += item.quantity
            sku = item.product.sku
            if sku not in product_sales:
                product_sales[sku] = {
                    "sku": sku,
                    "name": item.product.description[:30],
                    "sold": 0
                }
            product_sales[sku]["sold"] += item.quantity

    # Top 5 by quantity sold
    top_products = sorted(product_sales.values(), key=lambda x: x["sold"], reverse=True)[:5]

    return {
        "period": period_text,
        "orders_count": orders_count,
        "items_sold": items_sold,
        "revenue": revenue,
        "top_products": top_products,
    }
