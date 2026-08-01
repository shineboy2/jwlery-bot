"""
CMS Handlers: Manage Scheduled Posts.
"""
import logging
from datetime import datetime, timedelta
from bale import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.database.crud import get_admin_by_chat_id
from app.bot.keyboards.inline import build_kb, cms_menu_keyboard
from app.database.base import async_session
from app.database.models import ScheduledPost

logger = logging.getLogger(__name__)

_cms_states = {}  # {chat_id: {"step": "...", "data": {...}}}


async def callback_cms_menu(callback: CallbackQuery):
    """Show CMS menu."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    await callback.message.edit(
        "📢 سیستم مدیریت محتوا (CMS)\n\nانتخاب کنید:",
        components=cms_menu_keyboard()
    )

async def callback_cms_new(callback: CallbackQuery):
    """Start creating a new CMS post."""
    chat_id = callback.message.chat.id
    _cms_states[chat_id] = {"step": "awaiting_content", "data": {}}
    
    cancel_kb = build_kb([
        [InlineKeyboardButton("📝 ساخت پست دستی", callback_data="cms:manual_post")],
        [InlineKeyboardButton("✨ تولید با هوش مصنوعی", callback_data="cms:ai_prompt")],
        [InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]
    ])
    await callback.message.edit(
        "📝 **ساخت پست جدید**\n\nآیا می‌خواهید پست را دستی بنویسید یا از هوش مصنوعی کمک بگیرید؟\n(همچنین می‌توانید مستقیماً متن، عکس، یا ویدئوی خود را همینجا ارسال کنید)",
        components=cancel_kb
    )

async def callback_cms_list(callback: CallbackQuery):
    """List queued posts."""
    try:
        async with async_session() as session:
            result = await session.execute(
                select(ScheduledPost)
                .where(ScheduledPost.status == "QUEUED")
                .order_by(ScheduledPost.created_at.desc())
                .limit(5)
            )
            posts = result.scalars().all()
            
        if not posts:
            await callback.message.edit("🗂 صف خالی است.", components=cms_menu_keyboard())
            return
            
        text = "🗂 پست‌های موجود در صف:\n\n"
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        
        buttons = []
        for p in posts:
            desc = p.content_text[:20].replace('\n', ' ')
            text += f"▪️ {p.id} | دسته: {p.category or 'بدون دسته'} | {desc}...\n"
            buttons.append([InlineKeyboardButton(f"🗑 حذف پست {p.id}", callback_data=f"cms:queue:del:{p.id}")])
            
        buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:cms")])
        await callback.message.edit(text, components=build_kb(buttons))
    except Exception as e:
        logger.error(f"Error listing cms: {e}")
        await callback.message.edit("❌ خطا در لیست پست‌ها", components=cms_menu_keyboard())

async def callback_cms_queue_del(callback: CallbackQuery, post_id: int):
    """Delete a queued post."""
    try:
        from app.database.crud import async_session
        async with async_session() as session:
            post = await session.get(ScheduledPost, post_id)
            if post:
                await session.delete(post)
                await session.commit()
                await callback.message.reply(f"✅ پست {post_id} از صف حذف شد.")
            else:
                await callback.message.reply("⚠️ پست یافت نشد.")
        await callback_cms_list(callback)
    except Exception as e:
        logger.error(f"Error deleting queued post: {e}")
        await callback.message.reply("❌ خطا در حذف پست.")


async def handle_cms_message(message: Message) -> bool:
    """Handle FSM for CMS."""
    chat_id = message.chat.id
    state = _cms_states.get(chat_id)
    if not state:
        return False

    step = state["step"]

    if step == "awaiting_ai_topic":
        topic = message.text or ""
        cat_id = state["data"].get("ai_cat_id")
        await message.reply("⏳ در حال تولید متن با هوش مصنوعی...")
        
        from app.database.crud import get_content_category
        cat = await get_content_category(cat_id) if cat_id else None
        
        from app.services.ai_service import generate_cms_post
        ai_desc = await generate_cms_post(
            topic=topic, 
            category_name=cat.name if cat else None, 
            prompt_template=cat.prompt_template if cat else None
        )
        
        if ai_desc:
            state["data"]["text"] = ai_desc
            state["data"]["file_id"] = None
            state["step"] = "confirming_ai"
            
            confirm_kb = build_kb([
                [InlineKeyboardButton("✅ تایید", callback_data="cms:ai_ok")],
                [InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]
            ])
            await message.reply(f"✨ متن تولید شده:\n\n{ai_desc}\n\nدر صورت تایید دکمه زیر را بزنید، یا متن دلخواه خود را جایگزین کنید:", components=confirm_kb)
        else:
            await message.reply("❌ خطا در تولید متن.", components=cms_menu_keyboard())
            del _cms_states[chat_id]
        return True

    if step == "awaiting_prompt_text":
        prompt_text = message.text
        prompt_name = state["data"]["prompt_name"]
        
        from app.database.models import AIPrompt
        try:
            async with async_session() as session:
                result = await session.execute(select(AIPrompt).where(AIPrompt.name == prompt_name))
                prompt = result.scalar_one_or_none()
                if prompt:
                    prompt.content = prompt_text
                else:
                    prompt = AIPrompt(name=prompt_name, content=prompt_text)
                    session.add(prompt)
                await session.commit()
            
            await message.reply(f"✅ پرامپت '{prompt_name}' با موفقیت بروزرسانی شد.", components=cms_menu_keyboard())
        except Exception as e:
            logger.error(f"Error saving prompt: {e}")
            await message.reply("❌ خطا در ذخیره پرامپت.", components=cms_menu_keyboard())
            
        del _cms_states[chat_id]
        return True

    if step == "confirming_ai":
        # User manually edited the AI text
        state["data"]["text"] = message.text or ""
        state["step"] = "awaiting_schedule"
        return await show_schedule_options(message, state)

    if step == "awaiting_content":
        content_text = message.text or message.caption or ""
        file_id = None
        
        if getattr(message, 'photo', None):
            file_id = message.photo[-1].file_id
        elif getattr(message, 'document', None):
            file_id = message.document.file_id
        elif getattr(message, 'video', None):
            file_id = message.video.file_id

        if not content_text and not file_id:
            await message.reply("⚠️ محتوای خالی مجاز نیست.")
            return True

        state["data"]["text"] = content_text
        state["data"]["file_id"] = file_id
        state["step"] = "awaiting_schedule"
        return await show_schedule_options(message, state)

    if step == "sch_awaiting_time":
        return await handle_cms_schedule_time(message, state)

    if step == "awaiting_cooldown":
        try:
            days = int(message.text.strip())
            if days < 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ لطفاً یک عدد صحیح و مثبت وارد کنید.")
            return True
            
        from app.database.crud import async_session
        from app.database.models import SystemConfig
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(select(SystemConfig).where(SystemConfig.key == "product_cooldown_days"))
            config = result.scalar_one_or_none()
            if config:
                config.value = str(days)
            else:
                config = SystemConfig(key="product_cooldown_days", value=str(days))
                session.add(config)
            await session.commit()
            
        del _cms_states[chat_id]
        await message.reply(f"✅ تنظیمات ذخیره شد. فاصله انتشار مجدد به {days} روز تغییر یافت.", components=cms_menu_keyboard())
        return True

    return False

async def show_schedule_options(message, state):
    chat_id = message.chat.id
    _cms_states[chat_id] = state
    sched_kb = build_kb([
        [InlineKeyboardButton("🚀 ارسال آنی", callback_data="cms:schedule:now")],
        [InlineKeyboardButton("⏳ زمان مشخص (۱ساعت)", callback_data="cms:schedule:1h")],
        [InlineKeyboardButton("📚 افزودن به صف پیام‌های روزانه", callback_data="cms:schedule:queue")],
        [InlineKeyboardButton("❌ لغو", callback_data="menu:cms")],
    ])
    
    await message.reply(
        "✅ محتوا دریافت شد.\nزمان ارسال را انتخاب کنید:",
        components=sched_kb
    )
    return True

async def callback_cms_manual_post(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id in _cms_states:
        _cms_states[chat_id]["step"] = "awaiting_content"
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
        await callback.message.edit("📝 لطفاً محتوای پست خود را (متن، عکس، یا ویدئو با کپشن) ارسال کنید:", components=cancel_kb)

async def callback_cms_ai_prompt(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id in _cms_states:
        _cms_states[chat_id]["step"] = "awaiting_ai_cat"
        from app.database.crud import get_all_content_categories
        categories = await get_all_content_categories()
        
        buttons = []
        for cat in categories:
            buttons.append([InlineKeyboardButton(f"🏷 {cat.name}", callback_data=f"cms:ai_cat:{cat.id}")])
        # Add a "General" option without a specific category
        buttons.append([InlineKeyboardButton("🌐 بدون دسته‌بندی خاص (عمومی)", callback_data="cms:ai_cat:0")])
        buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:cms")])
        
        await callback.message.edit("لطفاً مشخص کنید این پست برای کدام دسته‌بندی است (تا پرامپت مربوطه اعمال شود):", components=build_kb(buttons))

async def callback_cms_ai_cat(callback: CallbackQuery, cat_id: int):
    chat_id = callback.message.chat.id
    if chat_id in _cms_states:
        _cms_states[chat_id]["step"] = "awaiting_ai_topic"
        _cms_states[chat_id]["data"]["ai_cat_id"] = cat_id if cat_id > 0 else None
        await callback.message.edit("لطفا موضوع یا کلمات کلیدی پست را وارد کنید (مثلا: تبریک یلدا، معرفی فروشگاه):")

async def callback_cms_ai_ok(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    state = _cms_states.get(chat_id)
    if state and state["step"] == "confirming_ai":
        state["step"] = "awaiting_schedule"
        await show_schedule_options(callback.message, state)


async def callback_cms_schedule(callback: CallbackQuery, time_option: str):
    """Handle scheduling selection."""
    chat_id = callback.message.chat.id
    state = _cms_states.get(chat_id)
    if not state or state["step"] != "awaiting_schedule":
        return

    data = state["data"]
    
    if time_option == "now":
        publish_time = datetime.now()
        await save_post_to_db(callback, chat_id, data, publish_time, None)
    elif time_option == "1h":
        publish_time = datetime.now() + timedelta(hours=1)
        await save_post_to_db(callback, chat_id, data, publish_time, None)
    elif time_option == "queue":
        state["step"] = "awaiting_queue_category"
        from app.database.crud import get_all_content_categories
        categories = await get_all_content_categories()
        
        buttons = []
        for cat in categories:
            buttons.append([InlineKeyboardButton(f"🏷 {cat.name}", callback_data=f"cms:cat:{cat.code}")])
        buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:cms")])
        
        cat_kb = build_kb(buttons)
        await callback.message.edit("لطفاً صف مورد نظر را انتخاب کنید:", components=cat_kb)

async def callback_cms_category(callback: CallbackQuery, category: str):
    chat_id = callback.message.chat.id
    state = _cms_states.get(chat_id)
    if not state or state["step"] != "awaiting_queue_category":
        return
        
    await save_post_to_db(callback, chat_id, state["data"], None, category)

async def callback_cms_prompts(callback: CallbackQuery):
    """Show prompt management menu."""
    prompts_kb = build_kb([
        [InlineKeyboardButton("پرامپت توضیحات محصول", callback_data="cms:prompt:edit:product_description")],
        [InlineKeyboardButton("بازگشت", callback_data="menu:cms")]
    ])
    await callback.message.edit(
        "🤖 مدیریت پرامپت‌های هوش مصنوعی\n\nبرای ویرایش دستورالعمل هوش مصنوعی، یکی از گزینه‌ها را انتخاب کنید:",
        components=prompts_kb
    )

async def callback_cms_prompt_edit(callback: CallbackQuery, prompt_name: str):
    """Start editing a specific prompt."""
    chat_id = callback.message.chat.id
    _cms_states[chat_id] = {"step": "awaiting_prompt_text", "data": {"prompt_name": prompt_name}}
    
    from app.database.crud import get_ai_prompt_by_name
    current_prompt = await get_ai_prompt_by_name(prompt_name)
    current_text = current_prompt or "تنظیم نشده (از پیش‌فرض استفاده می‌شود)"
    
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:prompts")]])
    await callback.message.edit(
        f"مقدار فعلی:\n{current_text}\n\nلطفاً متن جدید را برای پرامپت '{prompt_name}' وارد کنید:\n(متن شما جایگزین متن پیش‌فرض هوش مصنوعی می‌شود)",
        components=cancel_kb
    )

async def save_post_to_db(callback, chat_id, data, publish_time, category):
    try:
        async with async_session() as session:
            post = ScheduledPost(
                content_text=data["text"],
                file_id=data.get("file_id"),
                publish_time=publish_time,
                category=category,
                post_type="IMAGE" if data.get("file_id") else "TEXT"
            )
            session.add(post)
            await session.commit()
    except Exception as e:
        logger.error(f"Error saving scheduled post: {e}")
        await callback.message.edit("❌ خطا در ثبت پست.", components=cms_menu_keyboard())
        return

    del _cms_states[chat_id]
    
    if publish_time is None:
        msg = f"✅ پست به صف '{category}' اضافه شد."
    elif publish_time <= datetime.now() + timedelta(minutes=5):
        msg = "✅ پست برای ارسال آنی در صف قرار گرفت."
    else:
        msg = f"✅ پست زمان‌بندی شد."

    await callback.message.edit(msg, components=cms_menu_keyboard())

# ─────────────────────────────────────────
# Scheduler Management (Publish Calendar)
# ─────────────────────────────────────────
from app.database.crud import get_all_publish_schedules, create_publish_schedule, delete_publish_schedule, get_all_categories
from app.bot.keyboards.inline import cms_schedules_list_keyboard, cms_schedule_type_keyboard, category_select_for_schedule_keyboard
import re

async def callback_cms_schedules(callback: CallbackQuery):
    """Show list of all publish schedules."""
    schedules = await get_all_publish_schedules()
    await callback.message.edit(
        "⚙️ تنظیمات زمان‌بندی (تقویم انتشار):\n\nلیست زمان‌های تنظیم شده برای انتشار خودکار:",
        components=cms_schedules_list_keyboard(schedules)
    )

async def callback_cms_schedule_del(callback: CallbackQuery, schedule_id: int):
    """Delete a publish schedule."""
    await delete_publish_schedule(schedule_id)
    schedules = await get_all_publish_schedules()
    await callback.message.edit(
        "✅ زمان‌بندی با موفقیت حذف شد.\n\nلیست زمان‌های تنظیم شده:",
        components=cms_schedules_list_keyboard(schedules)
    )

async def callback_cms_schedule_add(callback: CallbackQuery):
    """Start process to add a new schedule."""
    chat_id = callback.message.chat.id
    _cms_states[chat_id] = {"step": "sch_awaiting_time", "data": {}}
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:schedules")]])
    await callback.message.edit(
        "⏰ لطفاً زمان انتشار را وارد کنید (فرمت 24 ساعته، مثلاً 10:30 یا 18:00):",
        components=cancel_kb
    )

async def handle_cms_schedule_time(message: Message, state: dict) -> bool:
    """Handle time input for new schedule."""
    time_str = message.text.strip()
    if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:schedules")]])
        await message.reply("❌ فرمت زمان نادرست است. لطفاً دقیقاً مانند 14:30 وارد کنید:", components=cancel_kb)
        return True
    
    state["data"]["time"] = time_str
    state["step"] = "sch_awaiting_type"
    
    await message.reply(
        f"✅ زمان {time_str} ثبت شد.\nاکنون نوع محتوایی که باید در این ساعت منتشر شود را انتخاب کنید:",
        components=cms_schedule_type_keyboard()
    )
    return True

async def callback_cms_schedule_type(callback: CallbackQuery, slot_type: str):
    """Handle type selection (PRODUCT/POST) for schedule."""
    chat_id = callback.message.chat.id
    state = _cms_states.get(chat_id)
    if not state or state["step"] != "sch_awaiting_type":
        return
        
    state["data"]["slot_type"] = slot_type
    state["step"] = "sch_awaiting_cat"
    
    if slot_type == "PRODUCT":
        categories = await get_all_categories(active_only=True)
        await callback.message.edit(
            "🗂 لطفاً دسته‌بندی محصولات را برای این زمان‌بندی انتخاب کنید:",
            components=category_select_for_schedule_keyboard(categories, slot_type)
        )
    else:
        from app.database.crud import get_all_content_categories
        post_queues = await get_all_content_categories()
        await callback.message.edit(
            "🗂 لطفاً دسته‌بندی محتوا را انتخاب کنید:",
            components=category_select_for_schedule_keyboard(post_queues, slot_type)
        )

async def callback_cms_schedule_cat(callback: CallbackQuery, slot_type: str, category_name: str):
    """Handle category selection and create schedule."""
    chat_id = callback.message.chat.id
    state = _cms_states.get(chat_id)
    if not state or state["step"] != "sch_awaiting_cat":
        return
        
    time_str = state["data"]["time"]
    await create_publish_schedule(slot_type=slot_type, time=time_str, count=1, post_category=category_name)
    
    del _cms_states[chat_id]
    
    schedules = await get_all_publish_schedules()
    await callback.message.edit(
        f"✅ زمان‌بندی جدید ({time_str} برای {category_name}) با موفقیت ایجاد شد.\n\nلیست:",
        components=cms_schedules_list_keyboard(schedules)
    )

async def callback_cms_config(callback: CallbackQuery):
    """Show system configuration menu."""
    from app.database.crud import async_session
    from app.database.models import SystemConfig
    from sqlalchemy import select
    
    async with async_session() as session:
        result = await session.execute(select(SystemConfig).where(SystemConfig.key == "product_cooldown_days"))
        config = result.scalar_one_or_none()
        cooldown_days = config.value if config else "4"
        
    chat_id = callback.message.chat.id
    _cms_states[chat_id] = {"step": "awaiting_cooldown"}
    
    await callback.message.edit(
        f"🛠 تنظیمات سیستم\n\n"
        f"فاصله مجاز انتشار مجدد محصول (Cooldown): {cooldown_days} روز\n\n"
        f"برای تغییر این مقدار، عدد جدید (تعداد روز) را ارسال کنید:",
        components=build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:cms")]])
    )

async def callback_cms_history(callback: CallbackQuery, page: int = 1):
    from app.database.crud import async_session
    from app.database.models import ScheduledPost
    from sqlalchemy import select, func
    from app.bot.keyboards.inline import cms_post_history_keyboard
    
    PER_PAGE = 10
    
    async with async_session() as session:
        count_stmt = select(func.count()).select_from(ScheduledPost).where(ScheduledPost.status == "published")
        total_count = await session.scalar(count_stmt)
        total_pages = (total_count + PER_PAGE - 1) // PER_PAGE if total_count > 0 else 1
        
        stmt = select(ScheduledPost).where(ScheduledPost.status == "published").order_by(ScheduledPost.id.desc()).offset((page - 1) * PER_PAGE).limit(PER_PAGE)
        result = await session.execute(stmt)
        posts = result.scalars().all()
        
    text = "📜 تاریخچه پست‌های منتشر شده:\n\nبرای مشاهده هر پست روی آن کلیک کنید."
    kb = cms_post_history_keyboard(posts, page, total_pages)
    
    try:
        await callback.message.edit(text, components=kb)
    except Exception:
        # If the message is a photo, edit might fail. Delete and send new.
        await callback.message.delete()
        await callback.message.reply(text, components=kb)

async def callback_cms_history_view(callback: CallbackQuery, post_id: int):
    from app.database.crud import async_session
    from app.database.models import ScheduledPost
    from sqlalchemy import select
    from app.bot.keyboards.inline import cms_history_view_keyboard
    
    async with async_session() as session:
        result = await session.execute(select(ScheduledPost).where(ScheduledPost.id == post_id))
        post = result.scalar_one_or_none()
        
    if not post:
        await callback.message.reply("❌ پست یافت نشد.")
        return
        
    cat = post.category or '--'
    
    # Calculate publish date
    from datetime import datetime
    import jdatetime
    
    pub_date = post.published_at or post.scheduled_time
    if pub_date:
        jdate = jdatetime.datetime.fromgregorian(datetime=pub_date)
        pub_str = jdate.strftime("%Y/%m/%d %H:%M")
        
        diff = datetime.now() - pub_date
        days = diff.days
        if days == 0:
            ago_str = "امروز"
        elif days == 1:
            ago_str = "دیروز"
        else:
            ago_str = f"{days} روز پیش"
            
        date_text = f"زمان انتشار: {pub_str} ({ago_str})"
    else:
        date_text = "زمان انتشار: نامشخص"

    text = f"📅 پست شماره: {post.id}\n🏷 دسته‌بندی: {cat}\n📦 نوع: {post.post_type}\n🕒 {date_text}\n\n📝 متن:\n{post.content_text}"
    
    if post.image_file_id:
        from bale import InputFile
        await callback.message.delete()
        await callback.message.reply(
            text,
            photo=InputFile(post.image_file_id),
            components=cms_history_view_keyboard(post.id)
        )
    else:
        await callback.message.edit(text, components=cms_history_view_keyboard(post.id))

async def callback_cms_history_resend(callback: CallbackQuery, post_id: int):
    from app.database.crud import move_post_to_queue
    from app.bot.keyboards.inline import cms_menu_keyboard
    
    await move_post_to_queue(post_id)
            
    text = "✅ پست با موفقیت به صف انتشار بازگردانده شد."
    kb = cms_menu_keyboard()
    
    try:
        await callback.message.edit(text, components=kb)
    except Exception:
        await callback.message.delete()
        await callback.message.reply(text, components=kb)
