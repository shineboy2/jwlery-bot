"""
Product business logic service layer.
"""
from typing import Optional

from app.database.crud import (
    create_product, add_product_image, get_product_by_id,
    get_product_images, search_products as db_search_products
)
from app.database.models import Product
from app.utils.sku_generator import generate_sku


async def register_product(
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
    product = await create_product(
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
        await add_product_image(
            product_id=product.id,
            file_id=file_id,
            is_primary=is_primary,
            sort_order=i,
        )

    # Step 4: Return complete product
    return await get_product_by_id(product.id)


async def get_product_card(product_id: int) -> Optional[dict]:
    """
    Return product with images + category info for display.
    """
    product = await get_product_by_id(product_id)
    if not product:
        return None

    images = await get_product_images(product_id)
    primary_image = next((img for img in images if img.is_primary), images[0] if images else None)

    return {
        "product": product,
        "category": product.category,
        "images": images,
        "primary_image": primary_image,
    }


async def search_products(query: str) -> list[Product]:
    """Search products by SKU or description."""
    return await db_search_products(query)
