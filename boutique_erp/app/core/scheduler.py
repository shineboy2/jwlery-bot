import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone

from app.database.base import async_session
from app.services.order_service import cancel_order
from sqlalchemy import select, or_
from app.database.models import ScheduledPost, Order, PublishSchedule, Product, SystemConfig
from app.bot.loader import bot
from app.services.cms_service import publish_scheduled_post
from app.services.channel_service import publish_to_channel

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def cancel_expired_orders():
    """Cancel PENDING_PAYMENT orders older than 2 hours."""
    try:
        async with async_session() as session:
            expire_threshold = datetime.now() - timedelta(hours=2)
            result = await session.execute(
                select(Order)
                .where(Order.status == "PENDING_PAYMENT")
                .where(Order.created_at < expire_threshold)
            )
            orders = result.scalars().all()
            for order in orders:
                await cancel_order(order.id)
                logger.info(f"Auto-cancelled expired order {order.id}")
    except Exception as e:
        logger.error(f"Error in cancel_expired_orders job: {e}")

async def publish_pending_posts():
    """Publish ScheduledPosts that have a specific publish_time that is due."""
    try:
        async with async_session() as session:
            now = datetime.now()
            result = await session.execute(
                select(ScheduledPost)
                .where(ScheduledPost.status == "QUEUED")
                .where(ScheduledPost.publish_time != None)
                .where(ScheduledPost.publish_time <= now)
            )
            posts = result.scalars().all()
            for post in posts:
                success = await publish_scheduled_post(bot, post)
                if success:
                    post.status = "PUBLISHED"
                    logger.info(f"Auto-published scheduled post {post.id}")
                else:
                    post.status = "FAILED"
                    logger.warning(f"Failed to publish scheduled post {post.id}, marked as FAILED")
                await session.commit()
    except Exception as e:
        logger.error(f"Error in publish_pending_posts job: {e}")

async def publish_dynamic_slots():
    """Check PublishSchedule and publish products or queued category posts."""
    try:
        async with async_session() as session:
            current_time = datetime.now().strftime("%H:%M")
            
            # Find matching active schedules
            schedules_result = await session.execute(
                select(PublishSchedule)
                .where(PublishSchedule.is_active == True)
                .where(PublishSchedule.time == current_time)
            )
            schedules = schedules_result.scalars().all()
            
            if not schedules:
                return
                
            # Get cooldown config
            config_result = await session.execute(select(SystemConfig).where(SystemConfig.key == "product_cooldown_days"))
            config = config_result.scalar_one_or_none()
            cooldown_days = int(config.value) if config else 4
            cooldown_threshold = datetime.now().date() - timedelta(days=cooldown_days)
            
            for schedule in schedules:
                if schedule.slot_type == "PRODUCT":
                    # Publish products
                    query = (
                        select(Product)
                        .where(Product.status == "ACTIVE")
                        .where(Product.stock_quantity > 0)
                        .where(
                            or_(
                                Product.last_published_at == None,
                                Product.last_published_at < cooldown_threshold
                            )
                        )
                    )
                    
                    if schedule.post_category and schedule.post_category != "ALL":
                        from app.database.models import ProductCategory
                        query = query.join(ProductCategory).where(ProductCategory.name == schedule.post_category)
                        
                    products_result = await session.execute(
                        query.order_by(Product.last_published_at.asc().nullsfirst()).limit(schedule.count)
                    )
                    products = products_result.scalars().all()
                    for p in products:
                        msg_id = await publish_to_channel(bot, p.id)
                        if msg_id:
                            p.last_published_at = datetime.now().date()
                            await session.commit()
                            logger.info(f"Auto-published product {p.id} via dynamic schedule.")
                            
                elif schedule.slot_type == "POST" and schedule.post_category:
                    # Publish from queue
                    posts_result = await session.execute(
                        select(ScheduledPost)
                        .where(ScheduledPost.status == "QUEUED")
                        .where(ScheduledPost.category == schedule.post_category)
                        .where(ScheduledPost.publish_time == None)
                        .order_by(ScheduledPost.created_at.asc())
                        .limit(schedule.count)
                    )
                    posts = posts_result.scalars().all()
                    for post in posts:
                        success = await publish_scheduled_post(bot, post)
                        if success:
                            post.status = "PUBLISHED"
                            logger.info(f"Auto-published queued post {post.id} (Category: {schedule.post_category})")
                        else:
                            post.status = "FAILED"
                            logger.warning(f"Failed to publish queued post {post.id}, marked as FAILED")
                        await session.commit()
                            
    except Exception as e:
        logger.error(f"Error in publish_dynamic_slots job: {e}")

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(cancel_expired_orders, 'interval', minutes=30)
        scheduler.add_job(publish_pending_posts, 'interval', minutes=1)
        scheduler.add_job(publish_dynamic_slots, 'interval', minutes=1)
        scheduler.start()
        logger.info("Scheduler started.")
