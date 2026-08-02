from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

def products_menu_keyboard() -> InlineKeyboardMarkup:
    """Products management menu."""
    return build_kb([
        [
            InlineKeyboardButton("➕ ثبت محصول جدید", callback_data="prod:add"),
        ],
        [
            InlineKeyboardButton("📋 لیست محصولات", callback_data="prod:list:page:1"),
            InlineKeyboardButton("🔍 جستجو", callback_data="prod:search"),
        ],
        [
            InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main"),
        ]
    ])

def product_list_keyboard(products: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Product list with pagination."""
    buttons = []
    for prod in products:
        status = "✅" if prod.status == "ACTIVE" else "❌"
        buttons.append([
            InlineKeyboardButton(
                f"{status} [{prod.sku}] {prod.description[:25]}",
                callback_data=f"prod:view:{prod.id}"
            )
        ])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"prod:list:page:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"prod:list:page:{page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="menu:products"),
    ])
    return build_kb(buttons)

def product_detail_keyboard(product_id: int, is_active: bool, has_channel_post: bool = False) -> InlineKeyboardMarkup:
    """Single product management keyboard."""
    toggle_text = "❌ غیرفعال" if is_active else "✅ فعال کردن"
    buttons = [
        [
            InlineKeyboardButton("✏️ ویرایش", callback_data=f"prod:edit:{product_id}"),
            InlineKeyboardButton("📦 موجودی", callback_data=f"prod:stock:{product_id}"),
        ],
        [
            InlineKeyboardButton(toggle_text, callback_data=f"prod:toggle:{product_id}"),
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="prod:list:page:1")]
    ]
    return build_kb(buttons)

def product_edit_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Product edit field selection keyboard."""
    return build_kb([
        [
            InlineKeyboardButton("📝 توضیحات/کپشن", callback_data=f"prod:edit:description:{product_id}"),
        ],
        [
            InlineKeyboardButton("💸 قیمت خرید", callback_data=f"prod:edit:buy_price:{product_id}"),
            InlineKeyboardButton("💰 قیمت فروش", callback_data=f"prod:edit:sell_price:{product_id}"),
        ],
        [
            InlineKeyboardButton("🏥 نام تامین‌کننده", callback_data=f"prod:edit:supplier:{product_id}"),
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"prod:view:{product_id}")],
    ])

def done_uploading_keyboard() -> InlineKeyboardMarkup:
    """Button for confirming image upload completion."""
    return build_kb([
        [InlineKeyboardButton("✅ آپلود تمام شد", callback_data="prod:images_done")],
        [InlineKeyboardButton("❌ لغو", callback_data="menu:products")],
    ])

def preview_ai_keyboard() -> InlineKeyboardMarkup:
    """Preview options for generated AI draft."""
    return build_kb([
        [InlineKeyboardButton("✏️ ویرایش متن", callback_data="prod:ai_edit")],
        [InlineKeyboardButton("🔄 تولید مجدد", callback_data="prod:ai_regen")],
        [
            InlineKeyboardButton("📚 افزودن به صف", callback_data="prod:ai_queue"),
            InlineKeyboardButton("🚀 انتشار آنی", callback_data="prod:ai_publish"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]
    ])

def confirm_product_keyboard(product_id: int = None) -> InlineKeyboardMarkup:
    """Confirm or cancel product registration."""
    return build_kb([
        [
            InlineKeyboardButton("✅ تأیید و ثبت", callback_data="prod:confirm"),
            InlineKeyboardButton("❌ لغو", callback_data="prod:cancel"),
        ]
    ])

def publish_after_register_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """After product registered, ask about publishing."""
    return build_kb([
        [
            InlineKeyboardButton("📢 بله، منتشر کن", callback_data=f"ch:publish:{product_id}"),
            InlineKeyboardButton("⏭ بعداً", callback_data=f"prod:view:{product_id}"),
        ]
    ])

def ai_generate_keyboard() -> InlineKeyboardMarkup:
    """Ask whether to generate description using AI."""
    return build_kb([
        [InlineKeyboardButton("✨ تولید با هوش مصنوعی", callback_data="prod:ai_gen")],
        [InlineKeyboardButton("✍️ نوشتن دستی کپشن", callback_data="prod:ai_manual")],
        [InlineKeyboardButton("⏭ استفاده از توضیحات پیش‌فرض", callback_data="prod:ai_skip")],
    ])

def category_select_keyboard(categories: list) -> InlineKeyboardMarkup:
    """Category selection for new product."""
    buttons = []
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(f"📁 {cat.name}", callback_data=f"prod:cat_select:{cat.id}")
        ])
    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")])
    return build_kb(buttons)
