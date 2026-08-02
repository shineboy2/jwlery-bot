from typing import Optional
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Product, ProductImage

async def create_product(
    session: AsyncSession,
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

async def get_product_by_id(session: AsyncSession, product_id: int) -> Optional[Product]:
    result = await session.execute(
        select(Product)
        .options(selectinload(Product.images), selectinload(Product.category))
        .where(Product.id == product_id)
    )
    return result.scalar_one_or_none()

async def get_product_by_sku(session: AsyncSession, sku: str) -> Optional[Product]:
    result = await session.execute(
        select(Product)
        .options(selectinload(Product.images), selectinload(Product.category))
        .where(Product.sku == sku)
    )
    return result.scalar_one_or_none()

async def get_products_by_category(session: AsyncSession, category_id: int) -> list[Product]:
    result = await session.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.category_id == category_id)
        .order_by(Product.sku)
    )
    return list(result.scalars().all())

async def get_all_products(session: AsyncSession, active_only: bool = True, page: int = 1, per_page: int = 10) -> list[Product]:
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

async def count_products(session: AsyncSession, active_only: bool = True) -> int:
    query = select(func.count(Product.id))
    if active_only:
        query = query.where(Product.status == "ACTIVE")
    result = await session.execute(query)
    return result.scalar_one()

async def update_product(session: AsyncSession, product_id: int, **kwargs) -> Optional[Product]:
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

async def update_stock(session: AsyncSession, product_id: int, quantity_change: int) -> Optional[Product]:
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

async def reserve_stock(session: AsyncSession, product_id: int, quantity: int) -> bool:
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product or product.stock_quantity < quantity:
        return False
    product.reserved_quantity += quantity
    await session.commit()
    return True

async def release_stock(session: AsyncSession, product_id: int, quantity: int) -> bool:
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return False
    product.reserved_quantity = max(0, product.reserved_quantity - quantity)
    await session.commit()
    return True

async def count_products_in_category(session: AsyncSession, category_id: int) -> int:
    result = await session.execute(
        select(func.count(Product.id)).where(Product.category_id == category_id)
    )
    return result.scalar_one()

async def search_products(session: AsyncSession, query_str: str) -> list[Product]:
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

async def add_product_image(session: AsyncSession, product_id: int, file_id: str, is_primary: bool = False, sort_order: int = 0) -> ProductImage:
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

async def get_product_images(session: AsyncSession, product_id: int) -> list[ProductImage]:
    result = await session.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order)
    )
    return list(result.scalars().all())

async def set_primary_image(session: AsyncSession, image_id: int) -> bool:
    result = await session.execute(
        select(ProductImage).where(ProductImage.id == image_id)
    )
    image = result.scalar_one_or_none()
    if not image:
        return False

    await session.execute(
        update(ProductImage)
        .where(ProductImage.product_id == image.product_id)
        .values(is_primary=False)
    )
    image.is_primary = True
    await session.commit()
    return True
