from app.utils.formatters import to_persian_digits, format_price

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
