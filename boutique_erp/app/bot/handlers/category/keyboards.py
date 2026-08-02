from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

def categories_menu_keyboard(categories: list, is_super_admin: bool = False) -> InlineKeyboardMarkup:
    """Show categories list with toggle buttons."""
    buttons = []
    for cat in categories:
        status_icon = "✅" if cat.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                f"{status_icon} {cat.name} ({cat.prefix})",
                callback_data=f"cat:view:{cat.id}"
            )
        ])
    buttons.append([
        InlineKeyboardButton("➕ افزودن دسته‌بندی جدید", callback_data="cat:add")
    ])
    buttons.append([
        InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main")
    ])
    return build_kb(buttons)

def category_detail_keyboard(category_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Buttons for viewing a category."""
    toggle_text = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    buttons = [
        [
            InlineKeyboardButton("✏️ ویرایش", callback_data=f"cat:edit:{category_id}"),
            InlineKeyboardButton(toggle_text, callback_data=f"cat:toggle:{category_id}"),
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="menu:categories")
        ]
    ]
    return build_kb(buttons)

def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Single back button to main menu."""
    return build_kb([
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")],
    ])
