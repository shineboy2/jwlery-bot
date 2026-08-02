import logging
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func
from bale import Message, CallbackQuery, InlineKeyboardButton, InputFile
import jdatetime

from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import config_repo, cms_repo, product_repo
from app.database.repositories.cms_repo import SYSTEM_CATEGORIES
from app.database.repositories import config_repo, cms_repo
from app.database.models import ScheduledPost, AIPrompt, SystemConfig
from app.services.ai_service import generate_cms_post
from app.services.cms_service import publish_post_to_channel
from app.bot.handlers.cms.keyboards import (
    cms_menu_keyboard, build_kb, cms_schedules_list_keyboard,
    cms_schedule_type_keyboard, category_select_for_schedule_keyboard,
    cms_post_history_keyboard, cms_history_view_keyboard,
    cms_creation_mode_keyboard, cms_create_category_keyboard,
    cms_create_skip_image_keyboard, cms_create_preview_keyboard
)

logger = logging.getLogger(__name__)

class CmsHandler(BaseHandler):
    HANDLER_NAME = "cms"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_exact("menu:cms", self.menu)
        
        # New Create Content (merged from cms_create.py)
        router.register_exact("cms:create", self.create_mode)
        router.register_exact("cms:create:wizard", self.create_wizard)
        router.register_exact("cms:create:forward", self.create_forward)
        router.register_pattern(r"^cms:create:cat:(.+)$", self.select_category)
        router.register_exact("cms:create:skip_img", self.skip_image)
        
        # Preview actions
        router.register_exact("cms:create:queue", self.create_queue)
        router.register_exact("cms:create:buffer", self.create_buffer)
        router.register_exact("cms:create:publish_now", self.create_publish_now)
        router.register_exact("cms:create:edit_cap", self.create_edit_cap)
        router.register_exact("cms:create:edit_img", self.create_edit_img)
        
        # Schedules
        router.register_exact("cms:schedules", self.schedules)
        router.register_exact("cms:sch:add", self.schedule_add)
        router.register_pattern(r"^cms:sch:del:(\d+)$", self.schedule_del)
        router.register_pattern(r"^cms:sch:type:(PRODUCT|POST)$", self.schedule_type)
        router.register_pattern(r"^cms:sch:cat:(PRODUCT|POST):(.+)$", self.schedule_cat)
        
        # Prompts
        router.register_exact("cms:prompts", self.prompts)
        router.register_pattern(r"^cms:prompt:edit:(.+)$", self.prompt_edit)
        
        # Config
        router.register_exact("cms:config", self.config_menu)
        
        # History
        router.register_exact("cms:history", self.history_first_page)
        router.register_pattern(r"^cms:hist:page:(\d+)$", self.history_page)
        router.register_pattern(r"^cms:hist:view:(\d+)$", self.history_view)
        router.register_pattern(r"^cms:hist:resend:(\d+)$", self.history_resend)

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        step = state.step
        text = message.content.strip() if message.content else ""

        # --- Old CMS Prompts/Config FSM ---
        if step == "awaiting_prompt_text":
            prompt_name = state.data["prompt_name"]
            try:
                async with self.session_factory() as session:
                    await config_repo.set_ai_prompt(session, prompt_name, text)
                await message.reply(f"✅ پرامپت '{prompt_name}' با موفقیت بروزرسانی شد.", components=cms_menu_keyboard())
            except Exception as e:
                logger.error(f"Error saving prompt: {e}")
                await message.reply("❌ خطا در ذخیره پرامپت.", components=cms_menu_keyboard())
            self.conversations.end(chat_id, self.HANDLER_NAME)
            return True

        if step == "sch_awaiting_time":
            time_str = text
            if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', time_str):
                cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:schedules")]])
                await message.reply("❌ فرمت زمان نادرست است. لطفاً دقیقاً مانند 14:30 وارد کنید:", components=cancel_kb)
                return True
            self.conversations.advance(chat_id, self.HANDLER_NAME, "sch_awaiting_type", time=time_str)
            await message.reply(
                f"✅ زمان {time_str} ثبت شد.\nاکنون نوع محتوایی که باید در این ساعت منتشر شود را انتخاب کنید:",
                components=cms_schedule_type_keyboard()
            )
            return True

        if step == "awaiting_cooldown":
            try:
                days = int(text)
                if days < 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ لطفاً یک عدد صحیح و مثبت وارد کنید.")
                return True
            async with self.session_factory() as session:
                await config_repo.set_system_config(session, "product_cooldown_days", str(days))
            self.conversations.end(chat_id, self.HANDLER_NAME)
            await message.reply(f"✅ تنظیمات ذخیره شد. فاصله انتشار مجدد به {days} روز تغییر یافت.", components=cms_menu_keyboard())
            return True

        # --- New CMS Create FSM ---
        if step == "awaiting_forward":
            forward_text = message.caption or message.text or ""
            photo_id = None
            if getattr(message, 'photo', None):
                photo_id = message.photo[-1].file_id if isinstance(message.photo, list) else message.photo.file_id
            
            if not forward_text and not photo_id:
                await message.reply("⚠️ محتوای قابل قبولی یافت نشد. لطفاً عکس یا متن ارسال کنید.")
                return True
                
            self.conversations.advance(chat_id, self.HANDLER_NAME, "select_category_forward", image_file_id=photo_id, caption=forward_text)
            async with self.session_factory() as session:
                custom_cats = await config_repo.get_all_content_categories(session)
            await message.reply(
                "✅ محتوا دریافت شد.\n\nلطفاً دسته‌بندی این پست را انتخاب کنید:",
                components=cms_create_category_keyboard(custom_cats, for_forward=True)
            )
            return True

        if step == "sku_input":
            sku = text.upper()
            if not sku: return True
            async with self.session_factory() as session:
                product = await product_repo.get_product_by_sku(session, sku)
            if not product:
                cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
                await message.reply(f"❌ محصولی با کد «{sku}» یافت نشد.\nدوباره وارد کنید:", components=cancel_kb)
                return True
            self.conversations.advance(
                chat_id, self.HANDLER_NAME, "upload_image",
                category=state.data["category"],
                product_id=product.id, product_sku=product.sku, product_name=product.description[:40]
            )
            await message.reply(
                f"✅ محصول یافت شد: **{product.description[:40]}** | کد: {product.sku}\n\n"
                "🖼 لطفاً عکس پست را ارسال کنید:",
                components=cms_create_skip_image_keyboard()
            )
            return True

        if step == "upload_image":
            file_id = None
            if getattr(message, 'photo', None):
                file_id = message.photo[-1].file_id if isinstance(message.photo, list) else message.photo.file_id
            elif getattr(message, 'document', None):
                file_id = message.document.file_id
            if not file_id:
                cancel_kb = build_kb([
                    [InlineKeyboardButton("⏭ بدون عکس ادامه بده", callback_data="cms:create:skip_img")],
                    [InlineKeyboardButton("❌ لغو", callback_data="menu:cms")],
                ])
                await message.reply("⚠️ لطفاً یک عکس ارسال کنید یا «بدون عکس» را انتخاب کنید:", components=cancel_kb)
                return True
            
            data = state.data
            data["image_file_id"] = file_id
            self.conversations.advance(chat_id, self.HANDLER_NAME, "write_caption", **data)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
            await message.reply("✅ عکس دریافت شد.\n\n✏️ کپشن پست را بنویسید:", components=cancel_kb)
            return True

        if step == "write_caption":
            caption = (message.content or message.caption or "").strip()
            if not caption:
                await message.reply("⚠️ کپشن نمی‌تواند خالی باشد. لطفاً متن بنویسید:")
                return True
            data = state.data
            data["caption"] = caption
            self.conversations.advance(chat_id, self.HANDLER_NAME, "preview", **data)
            state = self.conversations.get_active(chat_id)
            await self._show_preview(message, state)
            return True

        if step == "edit_caption":
            caption = (message.content or message.caption or "").strip()
            if not caption:
                await message.reply("⚠️ کپشن نمی‌تواند خالی باشد:")
                return True
            data = state.data
            data["caption"] = caption
            self.conversations.advance(chat_id, self.HANDLER_NAME, "preview", **data)
            state = self.conversations.get_active(chat_id)
            await self._show_preview(message, state)
            return True

        if step == "edit_image":
            file_id = None
            if getattr(message, 'photo', None):
                file_id = message.photo[-1].file_id if isinstance(message.photo, list) else message.photo.file_id
            if not file_id:
                await message.reply("⚠️ لطفاً یک عکس ارسال کنید:")
                return True
            data = state.data
            data["image_file_id"] = file_id
            self.conversations.advance(chat_id, self.HANDLER_NAME, "preview", **data)
            state = self.conversations.get_active(chat_id)
            await self._show_preview(message, state)
            return True

        return False

    async def _show_preview(self, message: Message, state):
        data = state.data
        caption = data.get("caption", "")
        image_file_id = data.get("image_file_id")
        category = data.get("category", "")
        product_sku = data.get("product_sku", "")

        cat_label = SYSTEM_CATEGORIES.get(category, {}).get("label", category)
        header = f"📋 پیش‌نمایش پست | دسته: {cat_label}"
        if product_sku: header += f" | کد: {product_sku}"

        kb = cms_create_preview_keyboard()
        try:
            if image_file_id:
                await message.reply_photo(photo=InputFile(image_file_id), caption=f"{header}\n\n{caption}", components=kb)
            else:
                await message.reply(f"{header}\n\n📝 کپشن:\n{caption}", components=kb)
        except Exception as e:
            logger.error(f"Error showing preview: {e}")
            await message.reply(f"{header}\n\n📝 کپشن:\n{caption}\n\n⚠️ نمایش عکس ممکن نبود.", components=kb)

    async def menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        self.conversations.end(chat_id, self.HANDLER_NAME)
        await callback.message.edit("📢 سیستم مدیریت محتوا (CMS)\n\nانتخاب کنید:", components=cms_menu_keyboard())

    # --- Creation Routes ---
    async def create_mode(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        await callback.message.edit("✍️ **تولید محتوای جدید**\n\nنحوه ارسال محتوا را انتخاب کنید:", components=cms_creation_mode_keyboard())

    async def create_forward(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_forward")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
        await callback.message.edit("📥 **ارسال یکجا**\n\nلطفاً پست مورد نظر خود (عکس با کپشن، یا فقط متن) را به اینجا فوروارد کنید یا بفرستید:", components=cancel_kb)

    async def create_wizard(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        self.conversations.start(chat_id, self.HANDLER_NAME, "select_category")
        async with ctx.session_factory() as session:
            custom_cats = await config_repo.get_all_content_categories(session)
        await callback.message.edit("✨ **ساخت مرحله به مرحله**\n\nلطفاً دسته‌بندی محتوا را انتخاب کنید:", components=cms_create_category_keyboard(custom_cats))

    async def select_category(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        cat_code = match.group(1)
        is_forward = cat_code.endswith(":fwd")
        if is_forward: cat_code = cat_code.replace(":fwd", "")
            
        state = self.conversations.get_active(chat_id)
        if not state or state.step not in ("select_category", "select_category_forward"): return
            
        data = state.data
        data["category"] = cat_code
        
        if is_forward:
            self.conversations.advance(chat_id, self.HANDLER_NAME, "preview", **data)
            state = self.conversations.get_active(chat_id)
            await self._show_preview(callback.message, state)
            return

        if cms_repo.is_product_category(cat_code):
            self.conversations.advance(chat_id, self.HANDLER_NAME, "sku_input", **data)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
            await callback.message.edit("🔍 لطفاً کد محصول (SKU) را وارد کنید:\n(مثال: NEC-1045)", components=cancel_kb)
        else:
            self.conversations.advance(chat_id, self.HANDLER_NAME, "upload_image", **data)
            await callback.message.edit("🖼 لطفاً عکس پست را ارسال کنید:", components=cms_create_skip_image_keyboard())

    async def skip_image(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state: return
        data = state.data
        data["image_file_id"] = None
        self.conversations.advance(chat_id, self.HANDLER_NAME, "write_caption", **data)
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
        await callback.message.edit("✏️ کپشن پست را بنویسید:", components=cancel_kb)

    # --- Preview Actions ---
    async def create_queue(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state: return
        data = state.data
        async with self.session_factory() as session:
            post = await cms_repo.create_content_post(
                session, category=data["category"], caption=data["caption"],
                image_file_id=data.get("image_file_id"), product_id=data.get("product_id"), status="queued"
            )
        self.conversations.end(chat_id, self.HANDLER_NAME)
        await callback.message.edit(f"✅ پست با موفقیت به صف اضافه شد. (شماره {post.queue_order})", components=cms_menu_keyboard())

    async def create_buffer(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state: return
        data = state.data
        async with self.session_factory() as session:
            await cms_repo.create_content_post(
                session, category=data["category"], caption=data["caption"],
                image_file_id=data.get("image_file_id"), product_id=data.get("product_id"), status="buffered"
            )
        self.conversations.end(chat_id, self.HANDLER_NAME)
        await callback.message.edit("✅ پست در بافر ذخیره شد.", components=cms_menu_keyboard())

    async def create_publish_now(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state: return
        data = state.data
        await callback.message.edit("⏳ در حال انتشار در کانال...")
        async with self.session_factory() as session:
            post = await cms_repo.create_content_post(
                session, category=data["category"], caption=data["caption"],
                image_file_id=data.get("image_file_id"), product_id=data.get("product_id"), status="buffered"
            )
            success = await publish_post_to_channel(session, self.bot, post)
        self.conversations.end(chat_id, self.HANDLER_NAME)
        if success: await callback.message.edit("✅ پست با موفقیت در کانال منتشر شد!", components=cms_menu_keyboard())
        else: await callback.message.edit("❌ خطا در انتشار. پست در بافر ذخیره شد.", components=cms_menu_keyboard())

    async def create_edit_cap(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state: return
        data = state.data
        self.conversations.advance(chat_id, self.HANDLER_NAME, "edit_caption", **data)
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
        await callback.message.reply("✏️ کپشن جدید را بفرستید:", components=cancel_kb)

    async def create_edit_img(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state: return
        data = state.data
        self.conversations.advance(chat_id, self.HANDLER_NAME, "edit_image", **data)
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
        await callback.message.reply("🖼 عکس جدید را بفرستید:", components=cancel_kb)

    # --- Config & Schedules & History (unchanged) ---
    async def config_menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        async with self.session_factory() as session:
            cooldown_val = await config_repo.get_system_config(session, "product_cooldown_days")
            cooldown = int(cooldown_val) if cooldown_val else 14
        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_cooldown")
        await callback.message.edit(
            f"🛠 تنظیمات سیستم\n\nفاصله مجاز انتشار مجدد محصول (Cooldown): {cooldown} روز\n\nبرای تغییر این مقدار، عدد جدید (تعداد روز) را ارسال کنید:",
            components=build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:cms")]])
        )

    async def schedules(self, callback: CallbackQuery, ctx) -> None:
        async with ctx.session_factory() as session:
            schedules = await config_repo.get_all_publish_schedules(session)
        await callback.message.edit(
            "⚙️ تنظیمات زمان‌بندی (تقویم انتشار):\n\nلیست زمان‌های تنظیم شده برای انتشار خودکار:",
            components=cms_schedules_list_keyboard(schedules)
        )

    async def schedule_del(self, callback: CallbackQuery, ctx, match) -> None:
        schedule_id = int(match.group(1))
        async with ctx.session_factory() as session:
            await config_repo.delete_publish_schedule(session, schedule_id)
            schedules = await config_repo.get_all_publish_schedules(session)
        await callback.message.edit(
            "✅ زمان‌بندی با موفقیت حذف شد.\n\nلیست زمان‌های تنظیم شده:",
            components=cms_schedules_list_keyboard(schedules)
        )

    async def schedule_add(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        self.conversations.start(chat_id, self.HANDLER_NAME, "sch_awaiting_time")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:schedules")]])
        await callback.message.edit("⏰ لطفاً زمان انتشار را وارد کنید (فرمت 24 ساعته، مثلاً 10:30 یا 18:00):", components=cancel_kb)

    async def schedule_type(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        slot_type = match.group(1)
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "sch_awaiting_type": return
        self.conversations.advance(chat_id, self.HANDLER_NAME, "sch_awaiting_cat", slot_type=slot_type, time=state.data["time"])
        if slot_type == "PRODUCT":
            from app.database.repositories import category_repo
            async with ctx.session_factory() as session:
                categories = await category_repo.get_all_categories(session, active_only=True)
            await callback.message.edit("🗂 لطفاً دسته‌بندی محصولات را برای این زمان‌بندی انتخاب کنید:", components=category_select_for_schedule_keyboard(categories, slot_type))
        else:
            async with ctx.session_factory() as session:
                post_queues = await config_repo.get_all_content_categories(session)
            await callback.message.edit("🗂 لطفاً دسته‌بندی محتوا را انتخاب کنید:", components=category_select_for_schedule_keyboard(post_queues, slot_type))

    async def schedule_cat(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        slot_type = match.group(1)
        category_name = match.group(2)
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "sch_awaiting_cat": return
        time_str = state.data["time"]
        async with ctx.session_factory() as session:
            await config_repo.create_publish_schedule(session, slot_type=slot_type, time=time_str, count=1, post_category=category_name)
        self.conversations.end(chat_id, self.HANDLER_NAME)
        async with ctx.session_factory() as session:
            schedules = await config_repo.get_all_publish_schedules(session)
        await callback.message.edit(
            f"✅ زمان‌بندی جدید ({time_str} برای {category_name}) با موفقیت ایجاد شد.\n\nلیست:",
            components=cms_schedules_list_keyboard(schedules)
        )

    async def prompts(self, callback: CallbackQuery, ctx) -> None:
        prompts_kb = build_kb([
            [InlineKeyboardButton("پرامپت توضیحات محصول", callback_data="cms:prompt:edit:product_description")],
            [InlineKeyboardButton("بازگشت", callback_data="menu:cms")]
        ])
        await callback.message.edit("🤖 مدیریت پرامپت‌های هوش مصنوعی\n\nبرای ویرایش دستورالعمل هوش مصنوعی، یکی از گزینه‌ها را انتخاب کنید:", components=prompts_kb)

    async def prompt_edit(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        prompt_name = match.group(1)
        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_prompt_text", {"prompt_name": prompt_name})
        async with ctx.session_factory() as session:
            current_prompt = await config_repo.get_ai_prompt_by_name(session, prompt_name)
        current_text = current_prompt or "تنظیم نشده (از پیش‌فرض استفاده می‌شود)"
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:prompts")]])
        await callback.message.edit(
            f"مقدار فعلی:\n{current_text}\n\nلطفاً متن جدید را برای پرامپت '{prompt_name}' وارد کنید:\n(متن شما جایگزین متن پیش‌فرض هوش مصنوعی می‌شود)",
            components=cancel_kb
        )

    async def history_first_page(self, callback: CallbackQuery, ctx) -> None:
        await self.history_page_with_num(callback, 1)
        
    async def history_page(self, callback: CallbackQuery, ctx, match) -> None:
        await self.history_page_with_num(callback, int(match.group(1)))
        
    async def history_page_with_num(self, callback: CallbackQuery, page: int) -> None:
        PER_PAGE = 10
        
        async with self.session_factory() as session:
            total_count = await cms_repo.count_published(session)
            total_pages = (total_count + PER_PAGE - 1) // PER_PAGE if total_count > 0 else 1
            posts = await cms_repo.get_published(session, limit=PER_PAGE, offset=(page - 1) * PER_PAGE)
        text = "📜 تاریخچه پست‌های منتشر شده:\n\nبرای مشاهده هر پست روی آن کلیک کنید."
        kb = cms_post_history_keyboard(posts, page, total_pages)
        try: await callback.message.edit(text, components=kb)
        except Exception:
            await callback.message.delete()
            await callback.message.reply(text, components=kb)

    async def history_view(self, callback: CallbackQuery, ctx, match) -> None:
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
        if not post:
            await callback.message.reply("❌ پست یافت نشد.")
            return
        cat = post.category or '--'
        pub_date = post.published_at or post.scheduled_time
        if pub_date:
            jdate = jdatetime.datetime.fromgregorian(datetime=pub_date)
            pub_str = jdate.strftime("%Y/%m/%d %H:%M")
            days = (datetime.now() - pub_date).days
            ago_str = "امروز" if days == 0 else "دیروز" if days == 1 else f"{days} روز پیش"
            date_text = f"زمان انتشار: {pub_str} ({ago_str})"
        else:
            date_text = "زمان انتشار: نامشخص"
        text = f"📅 پست شماره: {post.id}\n🏷 دسته‌بندی: {cat}\n📦 نوع: {post.post_type}\n🕒 {date_text}\n\n📝 متن:\n{post.content_text}"
        file_id = getattr(post, 'image_file_id', None) or getattr(post, 'file_id', None)
        if file_id:
            try:
                await callback.message.delete()
                await callback.message.reply(text, photo=InputFile(file_id), components=cms_history_view_keyboard(post.id))
            except Exception: await callback.message.edit(text, components=cms_history_view_keyboard(post.id))
        else:
            await callback.message.edit(text, components=cms_history_view_keyboard(post.id))

    async def history_resend(self, callback: CallbackQuery, ctx, match) -> None:
        async with ctx.session_factory() as session:
            await cms_repo.move_post_to_queue(session, int(match.group(1)))
        text = "✅ پست با موفقیت به صف انتشار بازگردانده شد."
        try: await callback.message.edit(text, components=cms_menu_keyboard())
        except Exception:
            await callback.message.delete()
            await callback.message.reply(text, components=cms_menu_keyboard())
