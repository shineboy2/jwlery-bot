"""
Auto SKU generation based on category prefix and sequence number.
"""
from app.database.repositories import category_repo, product_repo
from sqlalchemy.ext.asyncio import AsyncSession


async def generate_sku(session: AsyncSession, category_id: int) -> str:
    """
    Generate next SKU for given category.
    Example: NK-001, NK-002, BR-001, ER-001

    Args:
        category_id: The category to generate SKU for.

    Returns:
        SKU string like "NK-006"
    """
    category = await category_repo.get_category_by_id(session, category_id)
    if not category:
        raise ValueError(f"Category {category_id} not found")

    # Count all products (including inactive) in this category
    count = await product_repo.count_products_in_category(session, category_id)
    next_number = count + 1

    return f"{category.prefix}-{next_number:03d}"
