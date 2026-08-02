from app.utils.formatters import format_price
from app.core.config import settings

def format_channel_post(product, category, images) -> str:
    """Generate formatted Persian channel post text."""
    stock_text = "✅ موجود" if product.stock_quantity > 0 else "❌ ناموجود"

    return (
        f"💎 {category.name} | {product.description}\n"
        "━━━━━━━━━━━━━━━\n"
        f"🏷 کد: {product.sku}\n"
        f"💰 قیمت: {format_price(product.base_sell_price)}\n"
        f"📦 موجودی: {stock_text}\n"
        "\n"
        f"🛒 برای سفارش: {settings.channel_username}"
    )
