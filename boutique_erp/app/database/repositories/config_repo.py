from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import PublishSchedule, AIPrompt, ContentCategory, SystemConfig

async def get_all_publish_schedules(session: AsyncSession) -> list[PublishSchedule]:
    result = await session.execute(
        select(PublishSchedule).order_by(PublishSchedule.time)
    )
    return list(result.scalars().all())

async def create_publish_schedule(session: AsyncSession, slot_type: str, time: str, count: int = 1, post_category: str = None) -> PublishSchedule:
    schedule = PublishSchedule(
        slot_type=slot_type,
        time=time,
        count=count,
        post_category=post_category
    )
    session.add(schedule)
    await session.commit()
    await session.refresh(schedule)
    return schedule

async def delete_publish_schedule(session: AsyncSession, schedule_id: int) -> bool:
    result = await session.execute(
        select(PublishSchedule).where(PublishSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        return False
    await session.delete(schedule)
    await session.commit()
    return True

async def get_ai_prompt_by_name(session: AsyncSession, name: str) -> Optional[str]:
    result = await session.execute(
        select(AIPrompt).where(AIPrompt.name == name)
    )
    prompt = result.scalar_one_or_none()
    return prompt.content if prompt else None

async def set_ai_prompt(session: AsyncSession, name: str, content: str) -> None:
    result = await session.execute(
        select(AIPrompt).where(AIPrompt.name == name)
    )
    prompt = result.scalar_one_or_none()
    if prompt:
        prompt.content = content
    else:
        prompt = AIPrompt(name=name, content=content)
        session.add(prompt)
    await session.commit()

async def get_all_content_categories(session: AsyncSession) -> list[ContentCategory]:
    result = await session.execute(
        select(ContentCategory).order_by(ContentCategory.id.asc())
    )
    return list(result.scalars().all())

async def get_content_category(session: AsyncSession, category_id: int) -> Optional[ContentCategory]:
    result = await session.execute(
        select(ContentCategory).where(ContentCategory.id == category_id)
    )
    return result.scalar_one_or_none()

async def get_content_category_by_code(session: AsyncSession, code: str) -> Optional[ContentCategory]:
    result = await session.execute(
        select(ContentCategory).where(ContentCategory.code == code)
    )
    return result.scalar_one_or_none()

async def create_content_category(session: AsyncSession, name: str, code: str, prompt_template: str = None) -> ContentCategory:
    cat = ContentCategory(name=name, code=code, prompt_template=prompt_template)
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    return cat

async def update_content_category(session: AsyncSession, category_id: int, **kwargs) -> Optional[ContentCategory]:
    result = await session.execute(
        select(ContentCategory).where(ContentCategory.id == category_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        return None

    for key, value in kwargs.items():
        if hasattr(cat, key):
            setattr(cat, key, value)

    await session.commit()
    await session.refresh(cat)
    return cat

async def delete_content_category(session: AsyncSession, category_id: int) -> bool:
    result = await session.execute(
        select(ContentCategory).where(ContentCategory.id == category_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        return False
    await session.delete(cat)
    await session.commit()
    return True

async def get_system_config(session: AsyncSession, key: str) -> Optional[str]:
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()
    return config.value if config else None

async def set_system_config(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()
    if config:
        config.value = value
    else:
        config = SystemConfig(key=key, value=value)
        session.add(config)
    await session.commit()
