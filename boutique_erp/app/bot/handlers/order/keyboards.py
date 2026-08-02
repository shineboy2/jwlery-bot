from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

def orders_menu_keyboard() -> InlineKeyboardMarkup:
    """Orders management menu."""
    return build_kb([
        [
            InlineKeyboardButton("➕ سفارش جدید", callback_data="ord:new"),
        ],
        [
            InlineKeyboardButton("🔄 در انتظار پرداخت", callback_data="ord:filter:PENDING_PAYMENT"),
            InlineKeyboardButton("✅ پرداخت شده", callback_data="ord:filter:PAID"),
        ],
        [
            InlineKeyboardButton("📦 دپو شده", callback_data="ord:filter:PAID_HELD"),
            InlineKeyboardButton("🚚 ارسال شده", callback_data="ord:filter:SHIPPED"),
        ],
        [
            InlineKeyboardButton("📋 همه سفارشات", callback_data="ord:filter:ALL"),
        ],
        [
            InlineKeyboardButton("📥 خروجی سفارشات", callback_data="ord:export"),
            InlineKeyboardButton("🚚 ثبت گروهی بارکد", callback_data="ord:bulk_track"),
        ],
        [
            InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main"),
        ]
    ])

def order_detail_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    """Order management buttons based on current status."""
    buttons = []
    if status == "PENDING_PAYMENT":
        buttons.extend([
            [InlineKeyboardButton("✅ تأیید پرداخت (ارسال)", callback_data=f"ord:status:{order_id}:PAID")],
            [InlineKeyboardButton("📥 تأیید پرداخت (دپو)", callback_data=f"ord:status:{order_id}:PAID_HELD")],
            [InlineKeyboardButton("❌ لغو سفارش", callback_data=f"ord:status:{order_id}:CANCELLED")],
        ])
    elif status == "PAID":
        buttons.extend([
            [InlineKeyboardButton("🚚 ثبت کد رهگیری", callback_data=f"ord:track:{order_id}")],
            [InlineKeyboardButton("❌ لغو", callback_data=f"ord:status:{order_id}:CANCELLED")],
        ])
    elif status == "PAID_HELD":
        buttons.extend([
            [InlineKeyboardButton("📤 خروج از دپو (آماده ارسال)", callback_data=f"ord:status:{order_id}:PAID")],
            [InlineKeyboardButton("❌ لغو", callback_data=f"ord:status:{order_id}:CANCELLED")],
        ])
    elif status == "SHIPPED":
        buttons.append([
            InlineKeyboardButton("📦 تحویل داده شد", callback_data=f"ord:status:{order_id}:DELIVERED")
        ])

    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:orders")])
    return build_kb(buttons)

def order_product_select_keyboard(products: list) -> InlineKeyboardMarkup:
    """Select products for a new order."""
    buttons = []
    for prod in products:
        price_k = prod.base_sell_price // 10000  # to thousands of tomans
        buttons.append([
            InlineKeyboardButton(
                f"[{prod.sku}] {prod.description[:25]} | {price_k}K | 📦{prod.stock_quantity}",
                callback_data=f"ord:prod:{prod.id}"
            )
        ])
    buttons.append([
        InlineKeyboardButton("✅ اتمام انتخاب محصولات", callback_data="ord:items_done"),
    ])
    buttons.append([
        InlineKeyboardButton("❌ لغو", callback_data="menu:orders"),
    ])
    return build_kb(buttons)
