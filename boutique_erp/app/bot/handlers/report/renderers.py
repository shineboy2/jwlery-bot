from app.utils.formatters import format_price, to_persian_digits, format_number

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
