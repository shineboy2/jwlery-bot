"""
Product business logic service layer.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories import product_repo
from app.database.models import Product


async def register_product(
    session: AsyncSession,
    sku: str,
    category_id: int,
    description: str,
    buy_price: int,
    base_sell_price: int,
    stock_quantity: int,
    image_file_ids: list[str],
    supplier_name: Optional[str] = None,
    dynamic_attributes: dict = None,
) -> Product:
    """
    Full product registration flow:
    1. Create product via CRUD using provided SKU
    2. Save images (first image = primary)
    3. Return complete product with images

    Prices are expected in RIALS.
    """
    # Step 1: Create product
    product = await product_repo.create_product(
        session=session,
        sku=sku,
        category_id=category_id,
        description=description,
        buy_price=buy_price,
        base_sell_price=base_sell_price,
        stock_quantity=stock_quantity,
        supplier_name=supplier_name,
        dynamic_attributes=dynamic_attributes,
        status="DRAFT",
    )

    # Step 3: Save images
    for i, file_id in enumerate(image_file_ids):
        is_primary = (i == 0)  # First image is primary
        await product_repo.add_product_image(
            session=session,
            product_id=product.id,
            file_id=file_id,
            is_primary=is_primary,
            sort_order=i,
        )

    # Step 4: Return complete product
    return await product_repo.get_product_by_id(session, product.id)


async def get_product_card(session: AsyncSession, product_id: int) -> Optional[dict]:
    """
    Return product with images + category info for display.
    """
    product = await product_repo.get_product_by_id(session, product_id)
    if not product:
        return None

    images = await product_repo.get_product_images(session, product_id)
    primary_image = next((img for img in images if img.is_primary), images[0] if images else None)

    return {
        "product": product,
        "category": product.category,
        "images": images,
        "primary_image": primary_image,
    }


async def search_products(session: AsyncSession, query: str) -> list[Product]:
    """Search products by SKU or description."""
    return await product_repo.search_products(session, query)
