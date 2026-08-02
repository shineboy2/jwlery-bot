from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Category

async def get_all_categories(session: AsyncSession, active_only: bool = True) -> list[Category]:
    query = select(Category).order_by(Category.name)
    if active_only:
        query = query.where(Category.is_active == True)
    result = await session.execute(query)
    return list(result.scalars().all())

async def get_category_by_id(session: AsyncSession, category_id: int) -> Optional[Category]:
    result = await session.execute(
        select(Category).where(Category.id == category_id)
    )
    return result.scalar_one_or_none()

async def get_category_by_prefix(session: AsyncSession, prefix: str) -> Optional[Category]:
    result = await session.execute(
        select(Category).where(Category.prefix == prefix.upper())
    )
    return result.scalar_one_or_none()

async def create_category(session: AsyncSession, name: str, prefix: str, attributes: list = None) -> Category:
    category = Category(name=name, prefix=prefix.upper(), attributes=attributes or [])
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category

async def update_category(session: AsyncSession, category_id: int, **kwargs) -> Optional[Category]:
    result = await session.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        return None
    for key, value in kwargs.items():
        setattr(category, key, value)
    await session.commit()
    await session.refresh(category)
    return category

async def deactivate_category(session: AsyncSession, category_id: int) -> bool:
    result = await session.execute(
        update(Category)
        .where(Category.id == category_id)
        .values(is_active=False)
    )
    await session.commit()
    return result.rowcount > 0

async def toggle_category(session: AsyncSession, category_id: int) -> Optional[Category]:
    result = await session.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        return None
    category.is_active = not category.is_active
    await session.commit()
    await session.refresh(category)
    return category
