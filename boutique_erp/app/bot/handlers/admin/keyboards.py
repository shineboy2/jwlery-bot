from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

def main_menu_keyboard(is_super_admin: bool = False) -> InlineKeyboardMarkup:
    """Main admin panel with role-based buttons."""
    buttons = [
        [
            InlineKeyboardButton("📦 مدیریت محصولات", callback_data="menu:products"),
            InlineKeyboardButton("🗂 دسته‌بندی‌ها", callback_data="menu:categories"),
        ],
        [
            InlineKeyboardButton("🛒 سفارشات", callback_data="menu:orders"),
            InlineKeyboardButton("👥 مشتریان", callback_data="menu:customers"),
        ],
    ]
    
    if is_super_admin:
        buttons.append([
            InlineKeyboardButton("📊 گزارش‌ها", callback_data="menu:reports"),
            InlineKeyboardButton("📢 سیستم محتوا (CMS)", callback_data="menu:cms"),
        ])
        buttons.append([
            InlineKeyboardButton("💰 مدیریت مالی", callback_data="menu:finance"),
            InlineKeyboardButton("⚙️ تنظیمات", callback_data="menu:settings"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton("📢 سیستم محتوا (CMS)", callback_data="menu:cms"),
            InlineKeyboardButton("💰 مدیریت مالی", callback_data="menu:finance"),
        ])

    return build_kb(buttons)

def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Single back button to main menu."""
    return build_kb([
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")],
    ])

def settings_keyboard(is_super_admin: bool = False) -> InlineKeyboardMarkup:
    """Settings menu. Super admin sees admin management buttons."""
    buttons = []
    if is_super_admin:
        buttons.extend([
            [
                InlineKeyboardButton("👤 لیست ادمین‌ها", callback_data="admin:list"),
            ],
            [
                InlineKeyboardButton("➕ افزودن ادمین", callback_data="admin:add"),
                InlineKeyboardButton("🗑 حذف ادمین", callback_data="admin:remove"),
            ],
        ])
    else:
        buttons.append([
            InlineKeyboardButton("👤 لیست ادمین‌ها", callback_data="admin:list"),
        ])
    buttons.append([
        InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main")
    ])
    return build_kb(buttons)
