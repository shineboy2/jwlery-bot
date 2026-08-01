"""
Auto SKU generation based on category prefix and sequence number.
"""
from app.database.crud import get_category_by_id, count_products_in_category


async def generate_sku(category_id: int) -> str:
    """
    Generate next SKU for given category.
    Example: NK-001, NK-002, BR-001, ER-001

    Args:
        category_id: The category to generate SKU for.

    Returns:
        SKU string like "NK-006"
    """
    category = await get_category_by_id(category_id)
    if not category:
        raise ValueError(f"Category {category_id} not found")

    # Count all products (including inactive) in this category
    count = await count_products_in_category(category_id)
    next_number = count + 1

    return f"{category.prefix}-{next_number:03d}"
