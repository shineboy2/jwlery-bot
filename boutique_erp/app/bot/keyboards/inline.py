"""
All InlineKeyboardMarkup builders for the bot.
"""
from bale import InlineKeyboardMarkup, InlineKeyboardButton


def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    """Helper to build InlineKeyboardMarkup from a list of rows."""
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb


# ─────────────────────────────────────────
# Main Menu
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Settings Menu (Admin Management)
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Category Keyboards
# ─────────────────────────────────────────

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
        InlineKeyboardButton("➕ افزودن دسته‌بندی", callback_data="cat:add"),
        InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main"),
    ])
    return build_kb(buttons)


def category_detail_keyboard(category_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Single category management keyboard."""
    toggle_text = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    return build_kb([
        [
            InlineKeyboardButton(toggle_text, callback_data=f"cat:toggle:{category_id}"),
            InlineKeyboardButton("✏️ ویرایش", callback_data=f"cat:edit:{category_id}"),
        ],
        [
            InlineKeyboardButton("🔙 بازگشت", callback_data="menu:categories"),
        ]
    ])


def category_select_keyboard(categories: list) -> InlineKeyboardMarkup:
    """Select category for product registration."""
    buttons = []
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(f"{cat.name} ({cat.prefix})", callback_data=f"prod:cat:{cat.id}")
        ])
    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:products")])
    return build_kb(buttons)


# ─────────────────────────────────────────
# Product Keyboards
# ─────────────────────────────────────────

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

    # Pagination row
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


# ─────────────────────────────────────────
# Order Keyboards
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Customer Keyboards
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Reports Keyboards
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# CMS Menu
# ─────────────────────────────────────────

def cms_menu_keyboard() -> InlineKeyboardMarkup:
    """Redesigned CMS main menu."""
    return build_kb([
        [
            InlineKeyboardButton("✍️ تولید محتوای جدید", callback_data="cms:create"),
        ],
        [
            InlineKeyboardButton("📋 مدیریت صف‌ها", callback_data="cms:queue"),
            InlineKeyboardButton("🗂 مدیریت بافرها", callback_data="cms:buf"),
        ],
        [
            InlineKeyboardButton("📜 تاریخچه انتشار", callback_data="cms:history"),
            InlineKeyboardButton("🏷 دسته‌بندی‌ها", callback_data="cms:cat:manage"),
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات زمان‌بندی", callback_data="cms:schedules"),
            InlineKeyboardButton("🤖 پرامپت‌ها", callback_data="cms:prompts"),
        ],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")],
    ])


# ─────────────────────────────────────────
# CMS Create Content Keyboards
# ─────────────────────────────────────────

def cms_creation_mode_keyboard() -> InlineKeyboardMarkup:
    """Choose creation mode: Wizard or Forward."""
    return build_kb([
        [InlineKeyboardButton("✨ ساخت مرحله به مرحله (ویزارد)", callback_data="cms:create:wizard")],
        [InlineKeyboardButton("📥 ارسال یکجای پست (فوروارد)", callback_data="cms:create:forward")],
        [InlineKeyboardButton("❌ لغو", callback_data="menu:cms")],
    ])

def cms_create_category_keyboard(custom_cats: list, for_forward: bool = False) -> InlineKeyboardMarkup:
    """Category selection for new content creation."""
    buttons = [
        [InlineKeyboardButton("📦 معرفی محصول جدید", callback_data=f"cms:create:cat:product_launch{':fwd' if for_forward else ''}")],
    ]
    if custom_cats:
        buttons.append([InlineKeyboardButton("─── دسته‌های سفارشی ───", callback_data="noop")])
        for cat in custom_cats:
            buttons.append([InlineKeyboardButton(f"🏷 {cat.name}", callback_data=f"cms:create:cat:{cat.code}{':fwd' if for_forward else ''}")])
    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:cms")])
    return build_kb(buttons)


def cms_create_skip_image_keyboard() -> InlineKeyboardMarkup:
    """Option to skip image upload."""
    return build_kb([
        [InlineKeyboardButton("⏭ بدون عکس ادامه بده", callback_data="cms:create:skip_img")],
        [InlineKeyboardButton("❌ لغو", callback_data="menu:cms")],
    ])


def cms_create_preview_keyboard() -> InlineKeyboardMarkup:
    """Preview actions: add to queue, buffer, or publish now."""
    return build_kb([
        [
            InlineKeyboardButton("➕ افزودن به صف", callback_data="cms:create:queue"),
            InlineKeyboardButton("🗂 ذخیره در بافر", callback_data="cms:create:buffer"),
        ],
        [
            InlineKeyboardButton("🚀 انتشار همین الان", callback_data="cms:create:publish_now"),
        ],
        [
            InlineKeyboardButton("✏️ ویرایش کپشن", callback_data="cms:create:edit_cap"),
            InlineKeyboardButton("🖼 تغییر عکس", callback_data="cms:create:edit_img"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="menu:cms")],
    ])


# ─────────────────────────────────────────
# CMS Queue Keyboards
# ─────────────────────────────────────────

def cms_queue_menu_keyboard(counts: dict, custom_cats: list) -> InlineKeyboardMarkup:
    """Queue overview — show count per category."""
    pl = counts.get("product_launch", 0)
    ia = counts.get("interactive", 0)
    buttons = [
        [InlineKeyboardButton(f"📦 معرفی محصول ({pl})", callback_data="cms:queue:cat:product_launch")],
    ]
    for cat in custom_cats:
        cnt = counts.get(cat.code, 0)
        buttons.append([
            InlineKeyboardButton(f"🏷 {cat.name} ({cnt})", callback_data=f"cms:queue:cat:{cat.code}")
        ])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:cms")])
    return build_kb(buttons)


def cms_queue_list_keyboard(posts: list, cat_code: str) -> InlineKeyboardMarkup:
    """List posts in a queue with numbered buttons."""
    buttons = []
    row = []
    for i, p in enumerate(posts, start=1):
        row.append(InlineKeyboardButton(str(i), callback_data=f"cms:queue:post:{p.id}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 بازگشت به صف‌ها", callback_data="cms:queue")])
    return build_kb(buttons)


def cms_queue_post_keyboard(post_id: int, cat_code: str, is_first: bool = False) -> InlineKeyboardMarkup:
    """Actions for a single queued post."""
    buttons = []
    if not is_first:
        buttons.append([
            InlineKeyboardButton("🔝 انتقال به اول صف", callback_data=f"cms:queue:top:{post_id}"),
            InlineKeyboardButton("⬆️ یک پله بالاتر", callback_data=f"cms:queue:up:{post_id}"),
        ])
    buttons.extend([
        [
            InlineKeyboardButton("✏️ ویرایش کپشن", callback_data=f"cms:queue:edit_cap:{post_id}"),
            InlineKeyboardButton("🖼 تغییر عکس", callback_data=f"cms:queue:edit_img:{post_id}"),
        ],
        [
            InlineKeyboardButton("🚀 انتشار همین الان", callback_data=f"cms:queue:publish_now:{post_id}"),
        ],
        [
            InlineKeyboardButton("🗂 انتقال به بافر", callback_data=f"cms:queue:to_buf:{post_id}"),
            InlineKeyboardButton("🗑 حذف کامل", callback_data=f"cms:queue:del:{post_id}"),
        ],
        [InlineKeyboardButton("🔙 بازگشت به صف", callback_data=f"cms:queue:cat:{cat_code}")],
    ])
    return build_kb(buttons)


# ─────────────────────────────────────────
# CMS Buffer Keyboards
# ─────────────────────────────────────────

def cms_buffer_menu_keyboard(counts: dict, custom_cats: list) -> InlineKeyboardMarkup:
    """Buffer overview — show count per category."""
    pl = counts.get("product_launch", 0)
    ia = counts.get("interactive", 0)
    buttons = [
        [InlineKeyboardButton(f"📦 معرفی محصول ({pl})", callback_data="cms:buf:cat:product_launch")],
    ]
    for cat in custom_cats:
        cnt = counts.get(cat.code, 0)
        buttons.append([
            InlineKeyboardButton(f"🏷 {cat.name} ({cnt})", callback_data=f"cms:buf:cat:{cat.code}")
        ])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:cms")])
    return build_kb(buttons)


def cms_buffer_list_keyboard(posts: list, cat_code: str) -> InlineKeyboardMarkup:
    """List posts in a buffer."""
    buttons = []
    for i, p in enumerate(posts, start=1):
        label = p.content_text[:30].replace("\n", " ")
        if p.product_id:
            label = f"[محصول] {label}"
        buttons.append([InlineKeyboardButton(f"{i}. {label}...", callback_data=f"cms:buf:post:{p.id}")])
    buttons.append([InlineKeyboardButton("🔙 بازگشت به بافرها", callback_data="cms:buf")])
    return build_kb(buttons)


def cms_buffer_post_keyboard(post_id: int, cat_code: str) -> InlineKeyboardMarkup:
    """Actions for a single buffered post."""
    return build_kb([
        [
            InlineKeyboardButton("✏️ ویرایش کپشن", callback_data=f"cms:buf:edit_cap:{post_id}"),
            InlineKeyboardButton("🖼 تغییر عکس", callback_data=f"cms:buf:edit_img:{post_id}"),
        ],
        [
            InlineKeyboardButton("🚀 انتشار همین الان", callback_data=f"cms:buf:publish_now:{post_id}"),
        ],
        [
            InlineKeyboardButton("➕ انتقال به انتهای صف", callback_data=f"cms:buf:to_queue:{post_id}"),
        ],
        [
            InlineKeyboardButton("🗑 حذف کامل", callback_data=f"cms:buf:del:{post_id}"),
        ],
        [InlineKeyboardButton("🔙 بازگشت به بافر", callback_data=f"cms:buf:cat:{cat_code}")],
    ])


def cms_new_post_keyboard() -> InlineKeyboardMarkup:
    return build_kb([
        [
            InlineKeyboardButton("✨ تولید با هوش مصنوعی", callback_data="cms:ai_gen"),
            InlineKeyboardButton("لغو", callback_data="cms:cancel"),
        ]
    ])

def cms_schedules_list_keyboard(schedules: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in schedules:
        label = f"{s.time} | {s.slot_type}"
        if s.post_category:
            label += f" | {s.post_category}"
        buttons.append([
            InlineKeyboardButton(f"🗑 حذف: {label}", callback_data=f"cms:sch:del:{s.id}")
        ])
    buttons.append([
        InlineKeyboardButton("➕ افزودن زمان‌بندی جدید", callback_data="cms:sch:add"),
    ])
    buttons.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data="menu:cms"),
    ])
    return build_kb(buttons)

def cms_schedule_type_keyboard() -> InlineKeyboardMarkup:
    return build_kb([
        [
            InlineKeyboardButton("📦 محصول (Category)", callback_data="cms:sch:type:PRODUCT"),
            InlineKeyboardButton("📝 پست (Category)", callback_data="cms:sch:type:POST"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="cms:schedules")]
    ])

def category_select_for_schedule_keyboard(categories: list, slot_type: str) -> InlineKeyboardMarkup:
    buttons = []
    
    if slot_type == "PRODUCT":
        buttons.append([InlineKeyboardButton("📦 همه محصولات (بدون دسته‌بندی خاص)", callback_data=f"cms:sch:cat:{slot_type}:ALL")])
        
    for cat in categories:
        # Product Category has name, ContentCategory has name and code
        label = cat.name
        code = getattr(cat, "code", cat.name)
        buttons.append([
            InlineKeyboardButton(f"🏷 {label}", callback_data=f"cms:sch:cat:{slot_type}:{code}")
        ])
    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="cms:schedules")])
    return build_kb(buttons)

def cms_post_history_keyboard(posts: list, page: int = 1, total_pages: int = 1) -> InlineKeyboardMarkup:
    """List of PUBLISHED scheduled posts."""
    buttons = []
    if not posts:
        buttons.append([InlineKeyboardButton("📦 پستی یافت نشد", callback_data="noop")])
    for p in posts:
        # p is ScheduledPost
        title = getattr(p, 'post_type', getattr(p, 'content_type', 'POST'))
        cat = getattr(p, 'category', None) or getattr(p, 'post_category', None)
        if cat:
            title += f" | {cat}"
        if getattr(p, 'product_id', None):
            title += f" | محصول:{p.product_id}"
            
        buttons.append([
            InlineKeyboardButton(f"✅ {title}", callback_data=f"cms:hist:view:{p.id}")
        ])
    
    # Pagination row
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"cms:hist:page:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"cms:hist:page:{page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton("🔙 بازگشت به مدیریت محتوا", callback_data="menu:cms")])
    return build_kb(buttons)

def cms_history_view_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """View a single history post with option to resend."""
    return build_kb([
        [InlineKeyboardButton("🔄 ارسال مجدد (انتقال به صف)", callback_data=f"cms:hist:resend:{post_id}")],
        [InlineKeyboardButton("🔙 بازگشت به تاریخچه", callback_data="cms:history")]
    ])


# ─────────────────────────────────────────
# Finance Keyboards
# ─────────────────────────────────────────

def finance_menu_keyboard(is_super_admin: bool = False) -> InlineKeyboardMarkup:
    """Finance main menu."""
    buttons = [
        [
            InlineKeyboardButton("💸 ثبت هزینه جدید", callback_data="fin:exp:new"),
        ],
        [
            InlineKeyboardButton("🤝 تراکنش شرکا (برداشت/واریز)", callback_data="fin:part:new"),
        ],
    ]
    
    if is_super_admin:
        buttons.extend([
            [
                InlineKeyboardButton("📊 گزارش سود و زیان ماه جاری", callback_data="fin:rep:month"),
            ],
            [
                InlineKeyboardButton("📈 گزارش سود و زیان کل زمان‌ها", callback_data="fin:rep:all"),
            ]
        ])
        
    buttons.append([InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")])
    return build_kb(buttons)

def expense_categories_keyboard(categories: list) -> InlineKeyboardMarkup:
    """Select expense category."""
    buttons = []
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(f"📁 {cat.name}", callback_data=f"fin:exp:cat:{cat.id}")
        ])
    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:finance")])
    return build_kb(buttons)

def partners_keyboard(partners: list) -> InlineKeyboardMarkup:
    """Select partner."""
    buttons = []
    for p in partners:
        buttons.append([
            InlineKeyboardButton(f"👤 {p.name}", callback_data=f"fin:part:id:{p.id}")
        ])
    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:finance")])
    return build_kb(buttons)

def partner_transaction_type_keyboard(partner_id: int) -> InlineKeyboardMarkup:
    """Select type of partner transaction."""
    return build_kb([
        [
            InlineKeyboardButton("📉 برداشت شخصی (Drawing)", callback_data=f"fin:part:type:DRAWING:{partner_id}"),
        ],
        [
            InlineKeyboardButton("📈 تزریق سرمایه (Injection)", callback_data=f"fin:part:type:INJECTION:{partner_id}"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="menu:finance")]
    ])
