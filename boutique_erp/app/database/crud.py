"""
CRUD operations for all models.
All functions use async_session context manager.
"""
from typing import Optional
from datetime import datetime

from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload

from app.database.base import async_session
from app.database.models import Admin, Category, Product, ProductImage, User, Order, OrderItem


# ─────────────────────────────────────────
# Admin CRUD
# ─────────────────────────────────────────

async def get_admin_by_chat_id(chat_id: int) -> Optional[Admin]:
    async with async_session() as session:
        result = await session.execute(
            select(Admin).where(Admin.chat_id == chat_id)
        )
        return result.scalar_one_or_none()


async def create_admin(chat_id: int, full_name: str, role: str = "ADMIN") -> Admin:
    async with async_session() as session:
        admin = Admin(chat_id=chat_id, full_name=full_name, role=role)
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


async def get_all_admins() -> list[Admin]:
    async with async_session() as session:
        result = await session.execute(
            select(Admin).order_by(Admin.created_at)
        )
        return list(result.scalars().all())


async def deactivate_admin(chat_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            update(Admin)
            .where(Admin.chat_id == chat_id)
            .values(is_active=False)
        )
        await session.commit()
        return result.rowcount > 0


async def activate_admin(chat_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            update(Admin)
            .where(Admin.chat_id == chat_id)
            .values(is_active=True)
        )
        await session.commit()
        return result.rowcount > 0


# ─────────────────────────────────────────
# Category CRUD
# ─────────────────────────────────────────

async def get_all_categories(active_only: bool = True) -> list[Category]:
    async with async_session() as session:
        query = select(Category).order_by(Category.name)
        if active_only:
            query = query.where(Category.is_active == True)
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_category_by_id(category_id: int) -> Optional[Category]:
    async with async_session() as session:
        result = await session.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()


async def get_category_by_prefix(prefix: str) -> Optional[Category]:
    async with async_session() as session:
        result = await session.execute(
            select(Category).where(Category.prefix == prefix.upper())
        )
        return result.scalar_one_or_none()


async def create_category(name: str, prefix: str, attributes: list = None) -> Category:
    async with async_session() as session:
        category = Category(name=name, prefix=prefix.upper(), attributes=attributes or [])
        session.add(category)
        await session.commit()
        await session.refresh(category)
        return category


async def update_category(category_id: int, **kwargs) -> Optional[Category]:
    async with async_session() as session:
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


async def deactivate_category(category_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            update(Category)
            .where(Category.id == category_id)
            .values(is_active=False)
        )
        await session.commit()
        return result.rowcount > 0


async def toggle_category(category_id: int) -> Optional[Category]:
    async with async_session() as session:
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


# ─────────────────────────────────────────
# Product CRUD
# ─────────────────────────────────────────

async def create_product(
    sku: str,
    category_id: int,
    description: str,
    buy_price: int,
    base_sell_price: int,
    stock_quantity: int,
    supplier_name: Optional[str] = None,
    dynamic_attributes: dict = None,
    status: str = "DRAFT",
) -> Product:
    async with async_session() as session:
        product = Product(
            sku=sku,
            category_id=category_id,
            description=description,
            buy_price=buy_price,
            base_sell_price=base_sell_price,
            stock_quantity=stock_quantity,
            supplier_name=supplier_name,
            dynamic_attributes=dynamic_attributes or {},
            status=status,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product


async def get_product_by_id(product_id: int) -> Optional[Product]:
    async with async_session() as session:
        result = await session.execute(
            select(Product)
            .options(selectinload(Product.images), selectinload(Product.category))
            .where(Product.id == product_id)
        )
        return result.scalar_one_or_none()


async def get_product_by_sku(sku: str) -> Optional[Product]:
    async with async_session() as session:
        result = await session.execute(
            select(Product)
            .options(selectinload(Product.images), selectinload(Product.category))
            .where(Product.sku == sku)
        )
        return result.scalar_one_or_none()


async def get_products_by_category(category_id: int) -> list[Product]:
    async with async_session() as session:
        result = await session.execute(
            select(Product)
            .options(selectinload(Product.images))
            .where(Product.category_id == category_id)
            .order_by(Product.sku)
        )
        return list(result.scalars().all())


async def get_all_products(active_only: bool = True, page: int = 1, per_page: int = 10) -> list[Product]:
    async with async_session() as session:
        query = (
            select(Product)
            .options(selectinload(Product.images), selectinload(Product.category))
            .order_by(Product.sku)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        if active_only:
            query = query.where(Product.status == "ACTIVE")
        result = await session.execute(query)
        return list(result.scalars().all())


async def count_products(active_only: bool = True) -> int:
    async with async_session() as session:
        query = select(func.count(Product.id))
        if active_only:
            query = query.where(Product.status == "ACTIVE")
        result = await session.execute(query)
        return result.scalar_one()


async def update_product(product_id: int, **kwargs) -> Optional[Product]:
    async with async_session() as session:
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            return None
        for key, value in kwargs.items():
            setattr(product, key, value)
        await session.commit()
        await session.refresh(product)
        return product


async def update_stock(product_id: int, quantity_change: int) -> Optional[Product]:
    """Add or subtract from stock. Use positive for increase, negative for decrease."""
    async with async_session() as session:
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            return None
        product.stock_quantity += quantity_change
        await session.commit()
        await session.refresh(product)
        return product


async def reserve_stock(product_id: int, quantity: int) -> bool:
    """Reserve stock for pending orders."""
    async with async_session() as session:
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product or product.stock_quantity < quantity:
            return False
        product.reserved_quantity += quantity
        await session.commit()
        return True


async def release_stock(product_id: int, quantity: int) -> bool:
    """Release previously reserved stock."""
    async with async_session() as session:
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            return False
        product.reserved_quantity = max(0, product.reserved_quantity - quantity)
        await session.commit()
        return True


async def count_products_in_category(category_id: int) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(Product.id)).where(Product.category_id == category_id)
        )
        return result.scalar_one()


async def search_products(query_str: str) -> list[Product]:
    """Search products by SKU or description."""
    async with async_session() as session:
        result = await session.execute(
            select(Product)
            .options(selectinload(Product.images), selectinload(Product.category))
            .where(
                (Product.sku.ilike(f"%{query_str}%")) |
                (Product.description.ilike(f"%{query_str}%"))
            )
            .order_by(Product.sku)
        )
        return list(result.scalars().all())


# ─────────────────────────────────────────
# Product Images CRUD
# ─────────────────────────────────────────

async def add_product_image(product_id: int, file_id: str, is_primary: bool = False, sort_order: int = 0) -> ProductImage:
    async with async_session() as session:
        image = ProductImage(
            product_id=product_id,
            file_id=file_id,
            is_primary=is_primary,
            sort_order=sort_order,
        )
        session.add(image)
        await session.commit()
        await session.refresh(image)
        return image


async def get_product_images(product_id: int) -> list[ProductImage]:
    async with async_session() as session:
        result = await session.execute(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.sort_order)
        )
        return list(result.scalars().all())


async def set_primary_image(image_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(ProductImage).where(ProductImage.id == image_id)
        )
        image = result.scalar_one_or_none()
        if not image:
            return False

        # Unset all primary for this product
        await session.execute(
            update(ProductImage)
            .where(ProductImage.product_id == image.product_id)
            .values(is_primary=False)
        )

        # Set this one as primary
        image.is_primary = True
        await session.commit()
        return True


# ─────────────────────────────────────────
# User CRUD
# ─────────────────────────────────────────

async def get_user_by_chat_id(chat_id: int) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.chat_id == chat_id)
        )
        return result.scalar_one_or_none()


async def get_user_by_id(user_id: int) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()


async def get_or_create_user(chat_id: int, full_name: str) -> User:
    async with async_session() as session:
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


async def update_user(user_id: int, **kwargs) -> Optional[User]:
    async with async_session() as session:
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


async def search_users(query_str: str) -> list[User]:
    """Search users by name or phone number."""
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .where(
                (User.full_name.ilike(f"%{query_str}%")) |
                (User.phone_number.ilike(f"%{query_str}%"))
            )
            .order_by(User.full_name)
        )
        return list(result.scalars().all())


async def get_all_users(page: int = 1, per_page: int = 10) -> list[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all())


async def get_user_orders(user_id: int) -> list[Order]:
    async with async_session() as session:
        result = await session.execute(
            select(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())


# ─────────────────────────────────────────
# Order CRUD
# ─────────────────────────────────────────

async def create_order(
    user_id: int,
    items: list[dict],
    shipping_cost: int = 0,
    discount_amount: int = 0,
) -> Order:
    """
    items = [{"product_id": 1, "quantity": 1, "sold_price": 350000}]
    """
    async with async_session() as session:
        total = sum(i["quantity"] * i["sold_price"] for i in items)
        order = Order(
            user_id=user_id,
            total_amount=total + shipping_cost - discount_amount,
            shipping_cost=shipping_cost,
            discount_amount=discount_amount,
            status="PENDING_PAYMENT",
        )
        session.add(order)
        await session.flush()  # Get order.id

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


async def get_order_by_id(order_id: int) -> Optional[Order]:
    async with async_session() as session:
        result = await session.execute(
            select(Order)
            .options(
                selectinload(Order.user),
                selectinload(Order.items).selectinload(OrderItem.product)
            )
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()


async def update_order_status(order_id: int, status: str, **kwargs) -> Optional[Order]:
    async with async_session() as session:
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


async def get_orders_by_status(status: str) -> list[Order]:
    async with async_session() as session:
        result = await session.execute(
            select(Order)
            .options(selectinload(Order.user))
            .where(Order.status == status)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())


async def get_recent_orders(limit: int = 20) -> list[Order]:
    async with async_session() as session:
        result = await session.execute(
            select(Order)
            .options(selectinload(Order.user))
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

# ==========================================
# ScheduledPost CRUD (Content Management)
# ==========================================
from app.database.models import ScheduledPost

# دسته‌های سیستمی ثابت
SYSTEM_CATEGORIES = {
    "product_launch": {"label": "معرفی محصول جدید", "icon": "📦", "requires_sku": True},
    "interactive":    {"label": "صبح‌بخیر / تعاملی",  "icon": "☕️", "requires_sku": False},
}


def is_product_category(category: str) -> bool:
    """Return True if this category requires a product SKU link."""
    return SYSTEM_CATEGORIES.get(category, {}).get("requires_sku", False)


async def create_content_post(
    category: str,
    caption: str,
    image_file_id=None,
    product_id=None,
    status: str = "buffered",
) -> ScheduledPost:
    """Create a new content post (buffered or queued)."""
    async with async_session() as session:
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


async def get_queue_by_category(category: str) -> list:
    """Get all queued posts for a category, ordered by queue_order."""
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledPost)
            .where(
                ScheduledPost.category == category,
                ScheduledPost.status == "queued",
            )
            .order_by(ScheduledPost.queue_order.asc().nullslast())
        )
        return list(result.scalars().all())


async def get_buffer_by_category(category: str) -> list:
    """Get all buffered posts for a category, ordered by creation time."""
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledPost)
            .where(
                ScheduledPost.category == category,
                ScheduledPost.status == "buffered",
            )
            .order_by(ScheduledPost.created_at.asc())
        )
        return list(result.scalars().all())


async def get_post_by_id(post_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledPost).where(ScheduledPost.id == post_id)
        )
        return result.scalar_one_or_none()


async def move_post_to_queue(post_id: int):
    """Move a post to the end of its category's queue."""
    async with async_session() as session:
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


async def move_post_to_buffer(post_id: int):
    """Move a post from queue to buffer."""
    async with async_session() as session:
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


async def _compact_queue_in_session(session, category: str, removed_order: int):
    """Shift queue_order down for posts after the removed position."""
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


async def move_post_to_top(post_id: int) -> bool:
    """Move a post to position 1 in the queue, shifting others down."""
    async with async_session() as session:
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


async def move_post_order_up(post_id: int) -> bool:
    """Swap a post with the one immediately above it in the queue."""
    async with async_session() as session:
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


async def update_post_content(post_id: int, caption=None, image_file_id=None):
    async with async_session() as session:
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


async def delete_content_post(post_id: int) -> bool:
    async with async_session() as session:
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


async def count_queued_by_category(category: str) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(ScheduledPost.id)).where(
                ScheduledPost.category == category,
                ScheduledPost.status == "queued",
            )
        )
        return result.scalar_one()


async def count_buffered_by_category(category: str) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(func.count(ScheduledPost.id)).where(
                ScheduledPost.category == category,
                ScheduledPost.status == "buffered",
            )
        )
        return result.scalar_one()


# Legacy helpers (backward compatibility)
async def create_scheduled_post(content_text: str, file_id: str = None, publish_time=None) -> ScheduledPost:
    async with async_session() as session:
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


async def update_scheduled_post_status(post_id: int, status: str) -> bool:
    async with async_session() as session:
        post = await session.get(ScheduledPost, post_id)
        if post:
            post.status = status
            await session.commit()
            return True
        return False

# ==========================================
# PublishSchedule CRUD
# ==========================================
from app.database.models import PublishSchedule

async def get_all_publish_schedules() -> list[PublishSchedule]:
    async with async_session() as session:
        result = await session.execute(
            select(PublishSchedule).order_by(PublishSchedule.time)
        )
        return list(result.scalars().all())

async def create_publish_schedule(slot_type: str, time: str, count: int = 1, post_category: str = None) -> PublishSchedule:
    async with async_session() as session:
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

async def delete_publish_schedule(schedule_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(PublishSchedule).where(PublishSchedule.id == schedule_id)
        )
        schedule = result.scalar_one_or_none()
        if not schedule:
            return False
        await session.delete(schedule)
        await session.commit()
        return True

# ==========================================
# AIPrompt CRUD
# ==========================================
from app.database.models import AIPrompt

async def get_ai_prompt_by_name(name: str) -> Optional[str]:
    async with async_session() as session:
        result = await session.execute(
            select(AIPrompt).where(AIPrompt.name == name)
        )
        prompt = result.scalar_one_or_none()
        return prompt.content if prompt else None

async def set_ai_prompt(name: str, content: str) -> None:
    async with async_session() as session:
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

# ==========================================
# ContentCategory CRUD
# ==========================================
from app.database.models import ContentCategory

async def get_all_content_categories() -> list[ContentCategory]:
    async with async_session() as session:
        result = await session.execute(
            select(ContentCategory).order_by(ContentCategory.id.asc())
        )
        return list(result.scalars().all())

async def get_content_category(category_id: int) -> Optional[ContentCategory]:
    async with async_session() as session:
        result = await session.execute(
            select(ContentCategory).where(ContentCategory.id == category_id)
        )
        return result.scalar_one_or_none()

async def get_content_category_by_code(code: str) -> Optional[ContentCategory]:
    async with async_session() as session:
        result = await session.execute(
            select(ContentCategory).where(ContentCategory.code == code)
        )
        return result.scalar_one_or_none()

async def create_content_category(name: str, code: str, prompt_template: str = None) -> ContentCategory:
    async with async_session() as session:
        cat = ContentCategory(name=name, code=code, prompt_template=prompt_template)
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return cat

async def update_content_category(category_id: int, **kwargs) -> Optional[ContentCategory]:
    async with async_session() as session:
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

async def delete_content_category(category_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(ContentCategory).where(ContentCategory.id == category_id)
        )
        cat = result.scalar_one_or_none()
        if not cat:
            return False
        await session.delete(cat)
        await session.commit()
        return True


# ==========================================
# Finance & ERP CRUD
# ==========================================
from app.database.models import ExpenseCategory, Expense, Partner, PartnerTransaction

async def get_expense_categories(active_only: bool = True) -> list[ExpenseCategory]:
    async with async_session() as session:
        query = select(ExpenseCategory).order_by(ExpenseCategory.name)
        if active_only:
            query = query.where(ExpenseCategory.is_active == True)
        result = await session.execute(query)
        return list(result.scalars().all())

async def get_expense_category_by_id(cat_id: int) -> Optional[ExpenseCategory]:
    async with async_session() as session:
        result = await session.execute(
            select(ExpenseCategory).where(ExpenseCategory.id == cat_id)
        )
        return result.scalar_one_or_none()

async def create_expense(category_id: int, amount: int, description: str = None) -> Expense:
    async with async_session() as session:
        expense = Expense(category_id=category_id, amount=amount, description=description)
        session.add(expense)
        await session.commit()
        await session.refresh(expense)
        return expense

async def get_all_partners(active_only: bool = True) -> list[Partner]:
    async with async_session() as session:
        query = select(Partner).order_by(Partner.id)
        if active_only:
            query = query.where(Partner.is_active == True)
        result = await session.execute(query)
        return list(result.scalars().all())

async def get_partner_by_id(partner_id: int) -> Optional[Partner]:
    async with async_session() as session:
        result = await session.execute(
            select(Partner).where(Partner.id == partner_id)
        )
        return result.scalar_one_or_none()

async def create_partner_transaction(partner_id: int, amount: int, type: str = "DRAWING", description: str = None) -> PartnerTransaction:
    async with async_session() as session:
        pt = PartnerTransaction(partner_id=partner_id, amount=amount, type=type, description=description)
        session.add(pt)
        await session.commit()
        await session.refresh(pt)
        return pt

async def get_expenses_between(start_date: datetime = None, end_date: datetime = None) -> list[Expense]:
    async with async_session() as session:
        query = select(Expense).options(selectinload(Expense.category))
        if start_date:
            query = query.where(Expense.expense_date >= start_date)
        if end_date:
            query = query.where(Expense.expense_date <= end_date)
        result = await session.execute(query.order_by(Expense.expense_date.desc()))
        return list(result.scalars().all())

async def get_partner_transactions_between(start_date: datetime = None, end_date: datetime = None) -> list[PartnerTransaction]:
    async with async_session() as session:
        query = select(PartnerTransaction).options(selectinload(PartnerTransaction.partner))
        if start_date:
            query = query.where(PartnerTransaction.transaction_date >= start_date)
        if end_date:
            query = query.where(PartnerTransaction.transaction_date <= end_date)
        result = await session.execute(query.order_by(PartnerTransaction.transaction_date.desc()))
        return list(result.scalars().all())

async def get_paid_orders_between(start_date: datetime = None, end_date: datetime = None) -> list[Order]:
    async with async_session() as session:
        query = select(Order).options(selectinload(Order.items).selectinload(OrderItem.product))
        # Statuses that imply successful sale
        query = query.where(Order.status.in_(["PAID", "PAID_HELD", "SHIPPED", "DELIVERED"]))
        if start_date:
            query = query.where(Order.created_at >= start_date)
        if end_date:
            query = query.where(Order.created_at <= end_date)
        result = await session.execute(query)
        return list(result.scalars().all())
