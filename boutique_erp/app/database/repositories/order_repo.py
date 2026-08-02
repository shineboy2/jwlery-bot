from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Order, OrderItem

async def create_order(
    session: AsyncSession,
    user_id: int,
    items: list[dict],
    shipping_cost: int = 0,
    discount_amount: int = 0,
) -> Order:
    total = sum(i["quantity"] * i["sold_price"] for i in items)
    order = Order(
        user_id=user_id,
        total_amount=total + shipping_cost - discount_amount,
        shipping_cost=shipping_cost,
        discount_amount=discount_amount,
        status="PENDING_PAYMENT",
    )
    session.add(order)
    await session.flush()

    for item_data in items:
        item = OrderItem(
            order_id=order.id,
            product_id=item_data["product_id"],
            quantity=item_data["quantity"],
            sold_price=item_data["sold_price"],
            buy_price=item_data.get("buy_price", 0),
        )
        session.add(item)

    await session.commit()
    await session.refresh(order)
    return order

async def get_order_by_id(session: AsyncSession, order_id: int) -> Optional[Order]:
    result = await session.execute(
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.items).selectinload(OrderItem.product)
        )
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()

async def update_order_status(session: AsyncSession, order_id: int, status: str, **kwargs) -> Optional[Order]:
    result = await session.execute(
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.items).selectinload(OrderItem.product)
        )
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return None
    order.status = status
    for key, value in kwargs.items():
        setattr(order, key, value)
    await session.commit()
    await session.refresh(order)
    return order

async def get_orders_by_status(session: AsyncSession, status: str) -> list[Order]:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user))
        .where(Order.status == status)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())

async def get_recent_orders(session: AsyncSession, limit: int = 20) -> list[Order]:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user))
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

async def get_paid_orders_between(session: AsyncSession, start_date=None, end_date=None) -> list[Order]:
    query = select(Order).options(selectinload(Order.items).selectinload(OrderItem.product))
    query = query.where(Order.status.in_(["PAID", "PAID_HELD", "SHIPPED", "DELIVERED"]))
    if start_date:
        query = query.where(Order.created_at >= start_date)
    if end_date:
        query = query.where(Order.created_at <= end_date)
    result = await session.execute(query)
    return list(result.scalars().all())
