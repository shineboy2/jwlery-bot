from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Admin

async def get_admin_by_chat_id(session: AsyncSession, chat_id: int) -> Optional[Admin]:
    result = await session.execute(
        select(Admin).where(Admin.chat_id == chat_id)
    )
    return result.scalar_one_or_none()

async def create_admin(session: AsyncSession, chat_id: int, full_name: str, role: str = "ADMIN") -> Admin:
    admin = Admin(chat_id=chat_id, full_name=full_name, role=role)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin

async def get_all_admins(session: AsyncSession) -> list[Admin]:
    result = await session.execute(
        select(Admin).order_by(Admin.created_at)
    )
    return list(result.scalars().all())

async def deactivate_admin(session: AsyncSession, chat_id: int) -> bool:
    result = await session.execute(
        update(Admin)
        .where(Admin.chat_id == chat_id)
        .values(is_active=False)
    )
    await session.commit()
    return result.rowcount > 0

async def activate_admin(session: AsyncSession, chat_id: int) -> bool:
    result = await session.execute(
        update(Admin)
        .where(Admin.chat_id == chat_id)
        .values(is_active=True)
    )
    await session.commit()
    return result.rowcount > 0
