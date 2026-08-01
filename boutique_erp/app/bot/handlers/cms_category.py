import logging
from bale import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from app.bot.keyboards.inline import build_kb
from app.database.crud import (
    get_all_content_categories, get_content_category,
    create_content_category, update_content_category, delete_content_category,
    get_admin_by_chat_id
)

logger = logging.getLogger(__name__)
_cms_cat_states = {}  # {chat_id: {"step": "...", "data": {...}}}

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

async def callback_cms_cat_manage(callback: CallbackQuery):
    """List all content categories."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    categories = await get_all_content_categories()
    await callback.message.edit(
        "🏷 **مدیریت دسته‌بندی‌های محتوا**\n\nشما می‌توانید دسته‌بندی‌های مختلف (مانند آموزشی، صبح بخیر، و...) بسازید و برای هرکدام یک دستورالعمل (پرامپت) مجزا تنظیم کنید تا هوش مصنوعی بر اساس آن محتوا تولید کند.",
        components=cms_categories_list_keyboard(categories)
    )

async def callback_cms_cat_view(callback: CallbackQuery, cat_id: int):
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    cat = await get_content_category(cat_id)
    if not cat:
        await callback.message.reply("❌ دسته‌بندی یافت نشد.")
        return

    text = f"🏷 **دسته‌بندی محتوا:** {cat.name}\n"
    text += f"🔢 **کد سیستمی:** {cat.code}\n"
    text += f"🤖 **پرامپت اختصاصی:**\n{cat.prompt_template or 'تنظیم نشده (از پرامپت پیش‌فرض استفاده خواهد شد)'}"

    await callback.message.edit(text, components=cms_category_detail_keyboard(cat.id))

async def callback_cms_cat_add(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    _cms_cat_states[chat_id] = {"step": "add_name", "data": {}}
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:cat:manage")]])
    await callback.message.edit("لطفاً نام دسته‌بندی محتوا را وارد کنید (مثال: محتوای آموزشی):", components=cancel_kb)

async def handle_cms_cat_message(message: Message) -> bool:
    chat_id = message.chat.id
    state = _cms_cat_states.get(chat_id)
    if not state:
        return False
        
    text = message.content.text
    step = state["step"]
    
    if step == "add_name":
        state["data"]["name"] = text
        state["step"] = "add_code"
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:cat:manage")]])
        await message.reply("لطفاً یک کد انگلیسی برای این دسته‌بندی وارد کنید (مثال: EDU, MORNING):", components=cancel_kb)
        return True
        
    if step == "add_code":
        name = state["data"]["name"]
        code = text.upper().strip()
        try:
            await create_content_category(name, code)
            del _cms_cat_states[chat_id]
            
            categories = await get_all_content_categories()
            await message.reply(f"✅ دسته‌بندی '{name}' با کد '{code}' ایجاد شد.\nحالا می‌توانید پرامپت آن را تنظیم کنید.", components=cms_categories_list_keyboard(categories))
        except Exception as e:
            logger.error(f"Error creating content category: {e}")
            await message.reply("❌ خطا در ایجاد دسته‌بندی. ممکن است کد تکراری باشد.")
        return True
        
    if step in ["edit_name", "edit_code", "edit_prompt"]:
        cat_id = state["data"]["cat_id"]
        field_map = {
            "edit_name": "name",
            "edit_code": "code",
            "edit_prompt": "prompt_template"
        }
        field = field_map[step]
        
        try:
            await update_content_category(cat_id, **{field: text})
            del _cms_cat_states[chat_id]
            
            cat = await get_content_category(cat_id)
            msg_text = f"🏷 **دسته‌بندی محتوا:** {cat.name}\n"
            msg_text += f"🔢 **کد سیستمی:** {cat.code}\n"
            msg_text += f"🤖 **پرامپت اختصاصی:**\n{cat.prompt_template or 'تنظیم نشده'}"
            
            await message.reply(f"✅ با موفقیت ویرایش شد.\n\n{msg_text}", components=cms_category_detail_keyboard(cat.id))
        except Exception as e:
            logger.error(f"Error updating content category: {e}")
            await message.reply("❌ خطا در بروزرسانی.")
        return True

    return False

async def callback_cms_cat_edit_field(callback: CallbackQuery, field: str, cat_id: int):
    chat_id = callback.message.chat.id
    _cms_cat_states[chat_id] = {"step": f"edit_{field}", "data": {"cat_id": cat_id}}
    
    prompts = {
        "name": "نام جدید را وارد کنید:",
        "code": "کد انگلیسی جدید را وارد کنید:",
        "prompt": "پرامپت هوش مصنوعی را برای این دسته وارد کنید.\nنکته: در این پرامپت می‌توانید مشخص کنید هوش مصنوعی دقیقاً چه لحنی داشته باشد و چه متنی تولید کند.\n\nمثال: «یک متن صبح بخیر پرانرژی برای فروشگاه بدلیجات بنویس»"
    }
    
    cat = await get_content_category(cat_id)
    current_val = ""
    if cat:
        if field == "name": current_val = cat.name
        elif field == "code": current_val = cat.code
        elif field == "prompt": current_val = cat.prompt_template or "تنظیم نشده"
        
    msg = f"مقدار فعلی:\n{current_val}\n\n{prompts.get(field, 'مقدار جدید را وارد کنید:')}"
    
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cms:cat:view:{cat_id}")]])
    await callback.message.edit(msg, components=cancel_kb)

async def callback_cms_cat_history(callback: CallbackQuery, cat_id: int, page: int = 1):
    from app.database.crud import async_session
    from app.database.models import ScheduledPost
    from sqlalchemy import select, func
    from app.bot.keyboards.inline import build_kb, InlineKeyboardButton
    
    cat = await get_content_category(cat_id)
    if not cat:
        await callback.message.reply("❌ دسته‌بندی یافت نشد.")
        return
        
    PER_PAGE = 10
    
    async with async_session() as session:
        count_stmt = select(func.count()).select_from(ScheduledPost).where(
            ScheduledPost.status == "PUBLISHED",
            ScheduledPost.category == cat.name
        )
        total_count = await session.scalar(count_stmt)
        total_pages = (total_count + PER_PAGE - 1) // PER_PAGE if total_count > 0 else 1
        
        stmt = select(ScheduledPost).where(
            ScheduledPost.status == "PUBLISHED",
            ScheduledPost.category == cat.name
        ).order_by(ScheduledPost.id.desc()).offset((page - 1) * PER_PAGE).limit(PER_PAGE)
        result = await session.execute(stmt)
        posts = result.scalars().all()
        
    buttons = []
    if not posts:
        buttons.append([InlineKeyboardButton("📦 هیچ پستی برای این دسته یافت نشد", callback_data="noop")])
    for p in posts:
        title = p.post_type
        if p.product_id:
            title += f" | محصول:{p.product_id}"
            
        buttons.append([
            InlineKeyboardButton(f"✅ {title}", callback_data=f"cms:cat:hist_view:{cat.id}:{p.id}")
        ])
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"cms:cat:hist:{cat.id}:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"cms:cat:hist:{cat.id}:{page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton("🔙 بازگشت به دسته‌بندی", callback_data=f"cms:cat:view:{cat.id}")])
    kb = build_kb(buttons)
        
    await callback.message.edit(
        f"📜 تاریخچه پست‌های منتشر شده دسته {cat.name}:\n\nبرای مشاهده هر پست روی آن کلیک کنید.",
        components=kb
    )

async def callback_cms_cat_history_view(callback: CallbackQuery, cat_id: int, post_id: int):
    from app.database.crud import async_session
    from app.database.models import ScheduledPost
    from sqlalchemy import select
    from app.bot.keyboards.inline import build_kb, InlineKeyboardButton
    
    async with async_session() as session:
        result = await session.execute(select(ScheduledPost).where(ScheduledPost.id == post_id))
        post = result.scalar_one_or_none()
        
    if not post:
        await callback.message.reply("❌ پست یافت نشد.")
        return
        
    kb = build_kb([
        [InlineKeyboardButton("🔄 ارسال مجدد (انتقال به صف)", callback_data=f"cms:hist:resend:{post_id}")],
        [InlineKeyboardButton("🔙 بازگشت به تاریخچه", callback_data=f"cms:cat:hist:{cat_id}:1")]
    ])
        
    cat = post.category or '—'
    text = f"📅 پست شماره: {post.id}\n🏷 دسته‌بندی: {cat}\n📦 نوع: {post.post_type}\n\n📝 متن:\n{post.content_text}"
    await callback.message.edit(text, components=kb)


async def callback_cms_cat_delete(callback: CallbackQuery, cat_id: int):
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return
        
    await delete_content_category(cat_id)
    categories = await get_all_content_categories()
    await callback.message.edit("✅ دسته‌بندی با موفقیت حذف شد.", components=cms_categories_list_keyboard(categories))
