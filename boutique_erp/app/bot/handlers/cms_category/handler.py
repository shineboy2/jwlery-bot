import logging
from sqlalchemy import select, func
from bale import Message, CallbackQuery, InlineKeyboardButton
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import config_repo, cms_repo
from app.database.repositories.cms_repo import (
    count_published_by_category, get_published_by_category
)
from app.database.models import ScheduledPost
from app.bot.handlers.cms_category.keyboards import (
    cms_categories_list_keyboard, cms_category_detail_keyboard, build_kb
)

logger = logging.getLogger(__name__)

class CmsCategoryHandler(BaseHandler):
    HANDLER_NAME = "cms_category"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_exact("cms:cat:manage", self.manage)
        router.register_pattern(r"^cms:cat:view:(\d+)$", self.view)
        router.register_exact("cms:cat:add", self.add)
        router.register_pattern(r"^cms:cat:delete:(\d+)$", self.delete)
        router.register_pattern(r"^cms:cat:(edit_name|edit_code|edit_prompt):(\d+)$", self.edit_field)
        router.register_pattern(r"^cms:cat:hist:(\d+):(\d+)$", self.history)
        router.register_pattern(r"^cms:cat:hist_view:(\d+):(\d+)$", self.history_view)

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        step = state.step
        text = message.content.strip() if message.content else ""

        if step == "add_name":
            self.conversations.advance(chat_id, self.HANDLER_NAME, "add_code", name=text)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:cat:manage")]])
            await message.reply("لطفاً یک کد انگلیسی برای این دسته‌بندی وارد کنید (مثال: EDU, MORNING):", components=cancel_kb)
            return True

        if step == "add_code":
            name = state.data["name"]
            code = text.upper().strip()
            try:
                async with self.session_factory() as session:
                    await config_repo.create_content_category(session, name, code)
                self.conversations.end(chat_id, self.HANDLER_NAME)
                
                async with self.session_factory() as session:
                    categories = await config_repo.get_all_content_categories(session)
                await message.reply(
                    f"✅ دسته‌بندی '{name}' با کد '{code}' ایجاد شد.\nحالا می‌توانید پرامپت آن را تنظیم کنید.", 
                    components=cms_categories_list_keyboard(categories)
                )
            except Exception as e:
                logger.error(f"Error creating content category: {e}")
                await message.reply("❌ خطا در ایجاد دسته‌بندی. ممکن است کد تکراری باشد.")
            return True

        if step in ["edit_name", "edit_code", "edit_prompt"]:
            cat_id = state.data["cat_id"]
            field_map = {
                "edit_name": "name",
                "edit_code": "code",
                "edit_prompt": "prompt_template"
            }
            field = field_map[step]
            
            try:
                async with self.session_factory() as session:
                    await cms_repo.update_content_category(session, cat_id, **{field: text})
                self.conversations.end(chat_id, self.HANDLER_NAME)
                
                async with self.session_factory() as session:
                    cat = await cms_repo.get_content_category(session, cat_id)
                msg_text = f"🏷 **دسته‌بندی محتوا:** {cat.name}\n"
                msg_text += f"🔢 **کد سیستمی:** {cat.code}\n"
                msg_text += f"🤖 **پرامپت اختصاصی:**\n{cat.prompt_template or 'تنظیم نشده'}"
                
                await message.reply(f"✅ با موفقیت ویرایش شد.\n\n{msg_text}", components=cms_category_detail_keyboard(cat.id))
            except Exception as e:
                logger.error(f"Error updating content category: {e}")
                await message.reply("❌ خطا در بروزرسانی.")
            return True

        return False

    async def manage(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        async with ctx.session_factory() as session:
            categories = await config_repo.get_all_content_categories(session)
        await callback.message.edit(
            "🏷 **مدیریت دسته‌بندی‌های محتوا**\n\nشما می‌توانید دسته‌بندی‌های مختلف (مانند آموزشی، صبح بخیر، و...) بسازید و برای هرکدام یک دستورالعمل (پرامپت) مجزا تنظیم کنید تا هوش مصنوعی بر اساس آن محتوا تولید کند.",
            components=cms_categories_list_keyboard(categories)
        )

    async def view(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        cat_id = int(match.group(1))

        async with ctx.session_factory() as session:
            cat = await cms_repo.get_content_category(session, cat_id)
        if not cat:
            await callback.message.reply("❌ دسته‌بندی یافت نشد.")
            return

        text = f"🏷 **دسته‌بندی محتوا:** {cat.name}\n"
        text += f"🔢 **کد سیستمی:** {cat.code}\n"
        text += f"🤖 **پرامپت اختصاصی:**\n{cat.prompt_template or 'تنظیم نشده (از پرامپت پیش‌فرض استفاده خواهد شد)'}"

        await callback.message.edit(text, components=cms_category_detail_keyboard(cat.id))

    async def add(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        self.conversations.start(chat_id, self.HANDLER_NAME, "add_name")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="cms:cat:manage")]])
        await callback.message.edit("لطفاً نام دسته‌بندی محتوا را وارد کنید (مثال: محتوای آموزشی):", components=cancel_kb)

    async def edit_field(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        field = match.group(1)
        cat_id = int(match.group(2))

        self.conversations.start(chat_id, self.HANDLER_NAME, field, {"cat_id": cat_id})
        
        prompts = {
            "edit_name": "نام جدید را وارد کنید:",
            "edit_code": "کد انگلیسی جدید را وارد کنید:",
            "edit_prompt": "پرامپت هوش مصنوعی را برای این دسته وارد کنید.\nنکته: در این پرامپت می‌توانید مشخص کنید هوش مصنوعی دقیقاً چه لحنی داشته باشد و چه متنی تولید کند.\n\nمثال: «یک متن صبح بخیر پرانرژی برای فروشگاه بدلیجات بنویس»"
        }
        
        async with ctx.session_factory() as session:
            cat = await cms_repo.get_content_category(session, cat_id)
        current_val = ""
        if cat:
            if field == "edit_name": current_val = cat.name
            elif field == "edit_code": current_val = cat.code
            elif field == "edit_prompt": current_val = cat.prompt_template or "تنظیم نشده"
            
        msg = f"مقدار فعلی:\n{current_val}\n\n{prompts.get(field, 'مقدار جدید را وارد کنید:')}"
        
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cms:cat:view:{cat_id}")]])
        await callback.message.edit(msg, components=cancel_kb)

    async def delete(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        cat_id = int(match.group(1))
            
        async with ctx.session_factory() as session:
            await config_repo.delete_content_category(session, cat_id)
            categories = await config_repo.get_all_content_categories(session)
        await callback.message.edit("✅ دسته‌بندی با موفقیت حذف شد.", components=cms_categories_list_keyboard(categories))

    async def history(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        cat_id = int(match.group(1))
        page = int(match.group(2))
        
        async with ctx.session_factory() as session:
            cat = await cms_repo.get_content_category(session, cat_id)
        if not cat:
            await callback.message.reply("❌ دسته‌بندی یافت نشد.")
            return
            
        PER_PAGE = 10
        
        async with self.session_factory() as session:
            total_count = await count_published_by_category(session, cat.name)
            total_pages = (total_count + PER_PAGE - 1) // PER_PAGE if total_count > 0 else 1
            posts = await get_published_by_category(session, cat.name, limit=PER_PAGE, offset=(page - 1) * PER_PAGE)
            
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

    async def history_view(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        cat_id = int(match.group(1))
        post_id = int(match.group(2))
        
        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
            
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
