from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

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
        title = getattr(p, 'post_type', getattr(p, 'content_type', 'POST'))
        cat = getattr(p, 'category', None) or getattr(p, 'post_category', None)
        if cat:
            title += f" | {cat}"
        if getattr(p, 'product_id', None):
            title += f" | محصول:{p.product_id}"
            
        buttons.append([
            InlineKeyboardButton(f"✅ {title}", callback_data=f"cms:hist:view:{p.id}")
        ])
    
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
