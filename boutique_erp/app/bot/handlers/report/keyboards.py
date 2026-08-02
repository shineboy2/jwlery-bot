from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

def reports_menu_keyboard() -> InlineKeyboardMarkup:
    """Reports menu."""
    return build_kb([
        [
            InlineKeyboardButton("💰 گزارش سود", callback_data="rep:profit"),
            InlineKeyboardButton("📦 موجودی انبار", callback_data="rep:inventory"),
        ],
        [
            InlineKeyboardButton("📈 فروش هفته", callback_data="rep:sales:week"),
            InlineKeyboardButton("📈 فروش ماه", callback_data="rep:sales:month"),
        ],
        [
            InlineKeyboardButton("📊 سود ماه جاری", callback_data="rep:profit:month"),
            InlineKeyboardButton("📊 سود کل", callback_data="rep:profit:all"),
        ],
        [
            InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main"),
        ]
    ])
