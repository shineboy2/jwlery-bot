"""
Channel publishing service for sending/updating/removing product posts.
"""
import logging
from typing import Optional

from app.core.config import settings
from app.database.crud import get_product_by_id, update_product, get_product_images
from app.utils.formatters import format_channel_post

logger = logging.getLogger(__name__)


async def publish_to_channel(bot, product_id: int) -> Optional[int]:
    """
    Publish product to channel.

    1. Get product + images + category from DB
    2. Format post text
    3. If single image: bot.send_photo(channel_id, photo=file_id, caption=text)
    4. If multiple images: bot.send_media_group(channel_id, media=[...])
    5. Save channel_message_id to product
    6. Return message_id

    Returns: message_id if successful, None otherwise.
    """
    product = await get_product_by_id(product_id)
    if not product:
        logger.error(f"Product {product_id} not found for channel publish")
        return None

    category = product.category
    images = await get_product_images(product_id)
    caption = format_channel_post(product, category, images)
    # Use channel_username as it's more reliable for public channels in Bale
    channel_id = settings.channel_username or str(settings.channel_id)

    from bale import InputFile

    try:
        if not images:
            # No images - send text only
            msg = await bot.send_message(channel_id, caption)
            message_id = msg.message_id

        elif len(images) == 1:
            # Single image - must use InputFile
            msg = await bot.send_photo(
                chat_id=channel_id,
                photo=InputFile(images[0].file_id),
                caption=caption,
            )
            message_id = msg.message_id

        else:
            # Multiple images: Bale has no send_media_group
            # Send first image with caption, rest without caption
            msg = await bot.send_photo(
                chat_id=channel_id,
                photo=InputFile(images[0].file_id),
                caption=caption,
            )
            message_id = msg.message_id
            # Send the rest without caption
            for img in images[1:]:
                try:
                    await bot.send_photo(
                        chat_id=channel_id,
                        photo=InputFile(img.file_id),
                    )
                except Exception as img_err:
                    logger.warning(f"Could not send extra image for product {product_id}: {img_err}")

        if message_id:
            # Save channel_message_id to product
            await update_product(product_id, channel_message_id=message_id)
            logger.info(f"Product {product_id} published to channel, message_id={message_id}")

        return message_id

    except Exception as e:
        logger.error(f"Failed to publish product {product_id} to channel: {e}", exc_info=True)
        return None


async def update_channel_post(bot, product_id: int) -> bool:
    """
    Update existing channel post when product is edited (price/stock change).
    Uses bot.edit_message_caption if message_id exists.
    """
    product = await get_product_by_id(product_id)
    if not product or not product.channel_message_id:
        return False

    category = product.category
    images = await get_product_images(product_id)
    caption = format_channel_post(product, category, images)

    try:
        await bot.edit_message_caption(
            chat_id=settings.channel_id,
            message_id=product.channel_message_id,
            caption=caption,
        )
        logger.info(f"Channel post for product {product_id} updated")
        return True
    except Exception as e:
        logger.error(f"Failed to update channel post for product {product_id}: {e}")
        return False


async def remove_channel_post(bot, product_id: int) -> bool:
    """
    Delete channel post when product is deactivated.
    """
    product = await get_product_by_id(product_id)
    if not product or not product.channel_message_id:
        return False

    try:
        await bot.delete_message(
            chat_id=settings.channel_id,
            message_id=product.channel_message_id,
        )
        # Clear channel_message_id in DB
        await update_product(product_id, channel_message_id=None)
        logger.info(f"Channel post for product {product_id} removed")
        return True
    except Exception as e:
        logger.error(f"Failed to remove channel post for product {product_id}: {e}")
        return False
