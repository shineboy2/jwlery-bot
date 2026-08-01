"""
Persian text formatting utilities for channel posts and reports.
"""
from app.core.config import settings


def to_persian_digits(text: str) -> str:
    """Convert English digits to Persian digits."""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    return "".join(persian_digits[int(c)] if c.isdigit() else c for c in str(text))


def format_price(amount_rials: int) -> str:
    """
    Convert rials to formatted Persian toman string.
    Example: 10000000 → '۱,۰۰۰,۰۰۰ تومان'
    """
    tomans = amount_rials // 10
    formatted = f"{tomans:,}"
    return to_persian_digits(formatted) + " تومان"


def format_number(number: int) -> str:
    """Format number with Persian digits and comma separators."""
    return to_persian_digits(f"{number:,}")


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


def format_order_summary(order, user, items_info: list[dict]) -> str:
    """Format a complete order summary."""
    items_text = ""
    for item in items_info:
        items_text += (
            f"  • [{item['sku']}] {item['name']} × {to_persian_digits(str(item['quantity']))} "
            f"= {format_price(item['quantity'] * item['sold_price'])}\n"
        )

    return (
        f"🛒 جزئیات سفارش #{to_persian_digits(str(order.id))}\n"
        "━━━━━━━━━━━━━━━\n"
        f"👤 مشتری: {user.full_name}\n"
        f"📱 Chat ID: {to_persian_digits(str(user.chat_id))}\n"
        "\n"
        f"📦 اقلام:\n{items_text}"
        "━━━━━━━━━━━━━━━\n"
        f"🚚 هزینه ارسال: {format_price(order.shipping_cost)}\n"
        f"🎁 تخفیف: {format_price(order.discount_amount)}\n"
        f"💰 مبلغ کل: {format_price(order.total_amount)}\n"
        f"📊 وضعیت: {format_order_status(order.status)}"
    )


def format_order_status(status: str) -> str:
    """Format order status in Persian."""
    status_map = {
        "PENDING_PAYMENT": "🕐 در انتظار پرداخت",
        "PAID": "✅ پرداخت شده",
        "SHIPPED": "🚚 ارسال شده",
        "DELIVERED": "📦 تحویل داده شده",
        "CANCELLED": "❌ لغو شده",
    }
    return status_map.get(status, status)


def format_payment_message(order, card_number: str, card_holder: str) -> str:
    """
    Generate manual card-to-card payment instruction message.

    🔮 FUTURE: When BALE_PAYMENT_PROVIDER_TOKEN is set in .env,
    use bot.send_invoice() with LabeledPrice instead of this manual card info.
    See: https://docs.python-bale-bot.ir/en/stable/bale.payments.html
    """
    return (
        f"🛒 سفارش شما ثبت شد!\n"
        "━━━━━━━━━━━━━━━\n"
        f"شماره سفارش: #ORD-{to_persian_digits(str(order.id).zfill(4))}\n"
        f"مبلغ قابل پرداخت: {format_price(order.total_amount)}\n"
        "\n"
        f"💳 شماره کارت:\n"
        f"`{card_number}`\n"
        f"به نام: {card_holder}\n"
        "\n"
        "📸 لطفاً رسید پرداخت را ارسال کنید."
    )


def format_profit_report(data: dict, period: str = "کل") -> str:
    """Format profit report for display."""
    return (
        f"📊 گزارش سود خالص — {period}\n"
        "━━━━━━━━━━━━━━━\n"
        f"💰 درآمد فروش: {format_price(data['total_revenue'])}\n"
        f"🏷 هزینه خرید: {format_price(data['total_cost'])}\n"
        f"🚚 هزینه ارسال: {format_price(data['total_shipping'])}\n"
        f"🎁 تخفیفات: {format_price(data['total_discount'])}\n"
        "━━━━━━━━━━━━━━━\n"
        f"✅ سود خالص: {format_price(data['net_profit'])}\n"
        "\n"
        f"📦 تعداد سفارشات: {format_number(data['order_count'])}"
    )


def format_inventory_report(data: dict) -> str:
    """Format inventory report for display."""
    low_stock = "\n".join(
        f"  ⚠️ [{p['sku']}] {p['name']} — {to_persian_digits(str(p['stock']))} عدد"
        for p in data.get("low_stock_products", [])
    ) or "  ✅ همه محصولات موجودی کافی دارند"

    out_of_stock = "\n".join(
        f"  ❌ [{p['sku']}] {p['name']}"
        for p in data.get("out_of_stock_products", [])
    ) or "  ✅ هیچ محصولی ناموجود نیست"

    return (
        f"📦 گزارش موجودی انبار\n"
        "━━━━━━━━━━━━━━━\n"
        f"📊 کل محصولات: {format_number(data['total_products'])}\n"
        f"📥 کل موجودی: {format_number(data['total_stock'])} عدد\n"
        f"🔒 رزرو شده: {format_number(data['total_reserved'])} عدد\n"
        f"💰 ارزش انبار (خرید): {format_price(data['inventory_value_buy'])}\n"
        f"💎 ارزش انبار (فروش): {format_price(data['inventory_value_sell'])}\n"
        "━━━━━━━━━━━━━━━\n"
        f"⚠️ موجودی کم:\n{low_stock}\n"
        "━━━━━━━━━━━━━━━\n"
        f"❌ ناموجود:\n{out_of_stock}"
    )
