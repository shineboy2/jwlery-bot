from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

def customer_detail_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Customer management keyboard."""
    return build_kb([
        [
            InlineKeyboardButton("✏️ ویرایش اطلاعات", callback_data=f"cust:edit:{user_id}"),
            InlineKeyboardButton("📋 سفارشات", callback_data=f"cust:orders:{user_id}"),
        ],
        [
            InlineKeyboardButton("🔙 بازگشت", callback_data="menu:customers"),
        ]
    ])
