from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

def cms_categories_list_keyboard(categories) -> InlineKeyboardMarkup:
    buttons = []
    buttons.append([InlineKeyboardButton("➕ ایجاد دسته‌بندی محتوا", callback_data="cms:cat:add")])
    
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(f"🏷 {cat.name} ({cat.code})", callback_data=f"cms:cat:view:{cat.id}")
        ])
        
    buttons.append([InlineKeyboardButton("🔙 بازگشت به منوی محتوا", callback_data="menu:cms")])
    return build_kb(buttons)

def cms_category_detail_keyboard(cat_id: int) -> InlineKeyboardMarkup:
    return build_kb([
        [
            InlineKeyboardButton("✏️ ویرایش نام", callback_data=f"cms:cat:edit_name:{cat_id}"),
            InlineKeyboardButton("✏️ ویرایش کد", callback_data=f"cms:cat:edit_code:{cat_id}")
        ],
        [
            InlineKeyboardButton("🤖 تنظیم پرامپت هوش مصنوعی", callback_data=f"cms:cat:edit_prompt:{cat_id}")
        ],
        [
            InlineKeyboardButton("📜 تاریخچه پست‌های این دسته", callback_data=f"cms:cat:hist:{cat_id}:1")
        ],
        [
            InlineKeyboardButton("🗑 حذف دسته‌بندی", callback_data=f"cms:cat:delete:{cat_id}")
        ],
        [InlineKeyboardButton("🔙 لیست دسته‌بندی‌ها", callback_data="cms:cat:manage")]
    ])
