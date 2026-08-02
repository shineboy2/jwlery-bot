from typing import Optional
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User, Order, OrderItem

async def get_user_by_chat_id(session: AsyncSession, chat_id: int) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.chat_id == chat_id)
    )
    return result.scalar_one_or_none()

async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()

async def create_user(session: AsyncSession, chat_id: int, full_name: str, phone_number: str = None, address: str = None, postal_code: str = None, notes: str = None, birth_date: date = None) -> User:
    user = User(
        chat_id=chat_id,
        full_name=full_name,
        phone_number=phone_number,
        address=address,
        postal_code=postal_code,
        notes=notes,
        birth_date=birth_date
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def get_or_create_user(session: AsyncSession, chat_id: int, full_name: str) -> User:
    result = await session.execute(
        select(User).where(User.chat_id == chat_id)
    )
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(chat_id=chat_id, full_name=full_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def update_user(session: AsyncSession, user_id: int, **kwargs) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    for key, value in kwargs.items():
        setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user

async def search_users(session: AsyncSession, query_str: str) -> list[User]:
    result = await session.execute(
        select(User)
        .where(
            (User.full_name.ilike(f"%{query_str}%")) |
            (User.phone_number.ilike(f"%{query_str}%"))
        )
        .order_by(User.full_name)
    )
    return list(result.scalars().all())

async def get_all_users(session: AsyncSession, page: int = 1, per_page: int = 10) -> list[User]:
    result = await session.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(result.scalars().all())

async def get_user_orders(session: AsyncSession, user_id: int) -> list[Order]:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())
