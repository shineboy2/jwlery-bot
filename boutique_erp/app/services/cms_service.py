"""
CMS publishing service — publishes a ScheduledPost to the Bale channel.
Single image + caption only (Bale has no send_media_group support).
"""
import logging
from datetime import datetime
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


async def publish_post_to_channel(bot, post) -> bool:
    """
    Publish a ScheduledPost to the channel.
    - Uses image_file_id (single image) if available
    - Falls back to text-only if no image
    - Updates post status to 'published' and sets published_at on success
    """
    from bale import InputFile
    channel_id = str(settings.channel_id) if settings.channel_id else settings.channel_username

    try:
        if post.image_file_id:
            await bot.send_photo(
                chat_id=channel_id,
                photo=InputFile(post.image_file_id),
                caption=post.content_text,
            )
        else:
            await bot.send_message(
                chat_id=channel_id,
                text=post.content_text,
            )

        # Mark as published
        from app.database.base import async_session
        from app.database.models import ScheduledPost
        async with async_session() as session:
            db_post = await session.get(ScheduledPost, post.id)
            if db_post:
                db_post.status = "published"
                db_post.published_at = datetime.now()
                await session.commit()

        logger.info(f"Published ScheduledPost {post.id} (category={post.category}) to channel")
        return True

    except Exception as e:
        logger.error(f"Failed to publish ScheduledPost {post.id}: {e}", exc_info=True)
        return False


async def publish_scheduled_post(bot, post) -> bool:
    """Legacy alias — kept for backward compatibility with old CMS code."""
    return await publish_post_to_channel(bot, post)
