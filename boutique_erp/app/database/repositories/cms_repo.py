from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import ScheduledPost

SYSTEM_CATEGORIES = {
    "product_launch": {"label": "معرفی محصول جدید", "icon": "📦", "requires_sku": True},
    "interactive":    {"label": "صبح‌بخیر / تعاملی",  "icon": "☕️", "requires_sku": False},
}

def is_product_category(category: str) -> bool:
    return SYSTEM_CATEGORIES.get(category, {}).get("requires_sku", False)

async def create_content_post(
    session: AsyncSession,
    category: str,
    caption: str,
    image_file_id=None,
    product_id=None,
    status: str = "buffered",
) -> ScheduledPost:
    post_type = "IMAGE" if image_file_id else "TEXT"
    post = ScheduledPost(
        category=category,
        content_text=caption,
        image_file_id=image_file_id,
        product_id=product_id,
        post_type=post_type,
        status=status,
    )
    if status == "queued":
        result = await session.execute(
            select(func.max(ScheduledPost.queue_order)).where(
                ScheduledPost.category == category,
                ScheduledPost.status == "queued",
            )
        )
        max_order = result.scalar_one_or_none() or 0
        post.queue_order = max_order + 1
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post

async def get_queue_by_category(session: AsyncSession, category: str) -> list:
    result = await session.execute(
        select(ScheduledPost)
        .where(
            ScheduledPost.category == category,
            ScheduledPost.status == "queued",
        )
        .order_by(ScheduledPost.queue_order.asc().nullslast())
    )
    return list(result.scalars().all())

async def get_buffer_by_category(session: AsyncSession, category: str) -> list:
    result = await session.execute(
        select(ScheduledPost)
        .where(
            ScheduledPost.category == category,
            ScheduledPost.status == "buffered",
        )
        .order_by(ScheduledPost.created_at.asc())
    )
    return list(result.scalars().all())

async def get_post_by_id(session: AsyncSession, post_id: int):
    result = await session.execute(
        select(ScheduledPost).where(ScheduledPost.id == post_id)
    )
    return result.scalar_one_or_none()

async def move_post_to_queue(session: AsyncSession, post_id: int):
    post = await session.get(ScheduledPost, post_id)
    if not post:
        return None
    result = await session.execute(
        select(func.max(ScheduledPost.queue_order)).where(
            ScheduledPost.category == post.category,
            ScheduledPost.status == "queued",
        )
    )
    max_order = result.scalar_one_or_none() or 0
    post.status = "queued"
    post.queue_order = max_order + 1
    await session.commit()
    await session.refresh(post)
    return post

async def move_post_to_buffer(session: AsyncSession, post_id: int):
    post = await session.get(ScheduledPost, post_id)
    if not post:
        return None
    old_category = post.category
    old_order = post.queue_order
    post.status = "buffered"
    post.queue_order = None
    await session.commit()
    if old_order is not None:
        await _compact_queue_in_session(session, old_category, old_order)
    await session.refresh(post)
    return post

async def _compact_queue_in_session(session: AsyncSession, category: str, removed_order: int):
    result = await session.execute(
        select(ScheduledPost).where(
            ScheduledPost.category == category,
            ScheduledPost.status == "queued",
            ScheduledPost.queue_order > removed_order,
        ).order_by(ScheduledPost.queue_order.asc())
    )
    posts = result.scalars().all()
    for p in posts:
        p.queue_order -= 1
    await session.commit()

async def move_post_to_top(session: AsyncSession, post_id: int) -> bool:
    post = await session.get(ScheduledPost, post_id)
    if not post or post.status != "queued":
        return False
    result = await session.execute(
        select(ScheduledPost).where(
            ScheduledPost.category == post.category,
            ScheduledPost.status == "queued",
            ScheduledPost.queue_order < post.queue_order,
        )
    )
    others = result.scalars().all()
    for p in others:
        p.queue_order += 1
    post.queue_order = 1
    await session.commit()
    return True

async def move_post_order_up(session: AsyncSession, post_id: int) -> bool:
    post = await session.get(ScheduledPost, post_id)
    if not post or post.status != "queued" or (post.queue_order or 0) <= 1:
        return False
    result = await session.execute(
        select(ScheduledPost).where(
            ScheduledPost.category == post.category,
            ScheduledPost.status == "queued",
            ScheduledPost.queue_order == post.queue_order - 1,
        )
    )
    above = result.scalar_one_or_none()
    if above:
        above.queue_order, post.queue_order = post.queue_order, above.queue_order
    await session.commit()
    return True

async def update_post_content(session: AsyncSession, post_id: int, caption=None, image_file_id=None):
    post = await session.get(ScheduledPost, post_id)
    if not post:
        return None
    if caption is not None:
        post.content_text = caption
    if image_file_id is not None:
        post.image_file_id = image_file_id
        post.post_type = "IMAGE"
    await session.commit()
    await session.refresh(post)
    return post

async def delete_content_post(session: AsyncSession, post_id: int) -> bool:
    post = await session.get(ScheduledPost, post_id)
    if not post:
        return False
    old_category = post.category
    old_order = post.queue_order
    await session.delete(post)
    await session.commit()
    if old_order is not None:
        await _compact_queue_in_session(session, old_category, old_order)
    return True

async def count_queued_by_category(session: AsyncSession, category: str) -> int:
    result = await session.execute(
        select(func.count(ScheduledPost.id)).where(
            ScheduledPost.category == category,
            ScheduledPost.status == "queued",
        )
    )
    return result.scalar_one()

async def count_buffered_by_category(session: AsyncSession, category: str) -> int:
    result = await session.execute(
        select(func.count(ScheduledPost.id)).where(
            ScheduledPost.category == category,
            ScheduledPost.status == "buffered",
        )
    )
    return result.scalar_one()

async def create_scheduled_post(session: AsyncSession, content_text: str, file_id: str = None, publish_time=None) -> ScheduledPost:
    post = ScheduledPost(
        content_text=content_text,
        file_id=file_id,
        publish_time=publish_time,
        status="queued",
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post

async def update_scheduled_post_status(session: AsyncSession, post_id: int, status: str) -> bool:
    post = await session.get(ScheduledPost, post_id)
    if post:
        post.status = status
        await session.commit()
        return True
    return False

async def count_published_by_category(session: AsyncSession, category: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(ScheduledPost).where(
            ScheduledPost.status == "PUBLISHED",
            ScheduledPost.category == category
        )
    )
    return result.scalar() or 0

async def get_published_by_category(session: AsyncSession, category: str, limit: int, offset: int) -> list[ScheduledPost]:
    result = await session.execute(
        select(ScheduledPost).where(
            ScheduledPost.status == "PUBLISHED",
            ScheduledPost.category == category
        ).order_by(ScheduledPost.id.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())

async def count_published(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count()).select_from(ScheduledPost).where(
            ScheduledPost.status == "published"
        )
    )
    return result.scalar() or 0

async def get_published(session: AsyncSession, limit: int, offset: int) -> list[ScheduledPost]:
    result = await session.execute(
        select(ScheduledPost).where(
            ScheduledPost.status == "published"
        ).order_by(ScheduledPost.id.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())
