import logging
from bale import Message, CallbackQuery, InlineKeyboardButton
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import category_repo
from app.core.constants import AdminRole
from app.bot.handlers.category.keyboards import (
    categories_menu_keyboard, category_detail_keyboard,
    back_to_main_keyboard, build_kb
)

logger = logging.getLogger(__name__)

class CategoryHandler(BaseHandler):
    HANDLER_NAME = "category"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_exact("menu:categories", self.menu)
        router.register_exact("cat:add", self.add)
        router.register_pattern(r"^cat:view:(\d+)$", self.view)
        router.register_pattern(r"^cat:toggle:(\d+)$", self.toggle)
        router.register_pattern(r"^cat:edit:(\d+)$", self.edit)

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        step = state.step
        text = message.content.strip() if message.content else ""

        if step == "awaiting_name":
            if len(text) < 2:
                await message.reply("⚠️ نام باید حداقل ۲ کاراکتر باشد.")
                return True

            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_prefix", name=text)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:categories")]])
            await message.reply(
                f"✅ نام: {text}\n\n"
                "مرحله ۲/۲: پیشوند (prefix) برای کد محصول را وارد کنید:\n"
                "مثال: NK (گردنبند)، BR (دستبند)، RN (انگشتر)\n"
                "⚠️ فقط ۲-۴ حرف انگلیسی بزرگ",
                components=cancel_kb
            )
            return True

        elif step == "awaiting_prefix":
            prefix = text.upper().strip()
            if not prefix.isalpha() or not (2 <= len(prefix) <= 4):
                await message.reply("⚠️ پیشوند باید ۲ تا ۴ حرف انگلیسی باشد. مثال: NK")
                return True

            async with self.session_factory() as session:
                existing = await category_repo.get_category_by_prefix(session, prefix)
            if existing:
                await message.reply(f"⚠️ پیشوند '{prefix}' قبلاً استفاده شده است. پیشوند دیگری وارد کنید:")
                return True

            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_attributes", prefix=prefix)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:categories")]])
            await message.reply(
                f"✅ پیشوند: {prefix}\n\n"
                "مرحله ۳/۳: ویژگی‌های این دسته‌بندی را با کاما (,) جدا کرده و وارد کنید:\n"
                "مثال: وزن، عیار، سایز\n"
                "(اگر ویژگی خاصی ندارد، کلمه 'ندارد' را ارسال کنید)",
                components=cancel_kb
            )
            return True

        elif step == "awaiting_attributes":
            attributes = []
            if text.strip() and text.strip() != "ندارد":
                attributes = [attr.strip() for attr in text.split(",") if attr.strip()]
            
            name = state.data["name"]
            prefix = state.data["prefix"]
            try:
                async with self.session_factory() as session:
                    category = await category_repo.create_category(session, name=name, prefix=prefix, attributes=attributes)
            except Exception as e:
                logger.error(f"Error creating category: {e}")
                await message.reply(f"❌ خطا در ایجاد دسته‌بندی: {str(e)}")
                self.conversations.end(chat_id, self.HANDLER_NAME)
                return True

            self.conversations.end(chat_id, self.HANDLER_NAME)
            
            attr_str = "، ".join(attributes) if attributes else "ندارد"
            await message.reply(
                f"✅ دسته‌بندی ایجاد شد!\n\n"
                f"📌 نام: {category.name}\n"
                f"🔤 پیشوند: {category.prefix}\n"
                f"🏷 ویژگی‌ها: {attr_str}\n"
                f"کد اولین محصول: {category.prefix}-001",
                components=back_to_main_keyboard()
            )
            return True

        elif step == "edit_name":
            category_id = state.data["category_id"]
            async with self.session_factory() as session:
                category = await category_repo.get_category_by_id(session, category_id)

            if text.strip() == "-":
                new_name = category.name
            else:
                if len(text) < 2:
                    await message.reply("⚠️ نام باید حداقل ۲ کاراکتر باشد.")
                    return True
                new_name = text

            self.conversations.advance(chat_id, self.HANDLER_NAME, "edit_attributes", name=new_name)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cat:view:{category_id}")]])
            
            old_attrs = "، ".join(category.attributes) if category.attributes else "ندارد"
            await message.reply(
                f"✅ نام: {new_name}\n\n"
                f"ویژگی‌های فعلی: {old_attrs}\n\n"
                "ویژگی‌های جدید را با کاما (,) جدا کرده و وارد کنید:\n"
                "(برای تغییر ندادن، علامت - را بفرستید. برای حذف همه ویژگی‌ها کلمه 'ندارد' را بفرستید)",
                components=cancel_kb
            )
            return True

        elif step == "edit_attributes":
            category_id = state.data["category_id"]
            async with self.session_factory() as session:
                category = await category_repo.get_category_by_id(session, category_id)
            
            if text.strip() == "-":
                attributes = category.attributes
            else:
                attributes = []
                if text.strip() and text.strip() != "ندارد":
                    attributes = [attr.strip() for attr in text.split(",") if attr.strip()]
                
            name = state.data["name"]
            async with self.session_factory() as session:
                await category_repo.update_category(session, category_id, name=name, attributes=attributes)
            self.conversations.end(chat_id, self.HANDLER_NAME)

            back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:view:{category_id}")]])
            
            attr_str = "، ".join(attributes) if attributes else "ندارد"
            await message.reply(
                f"✅ دسته‌بندی با موفقیت ویرایش شد.\n\n"
                f"نام: {name}\n"
                f"ویژگی‌ها: {attr_str}",
                components=back_kb
            )
            return True

        return False

    async def menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        admin = await self.require_admin(chat_id)
        if not admin: return

        async with ctx.session_factory() as session:
            categories = await category_repo.get_all_categories(session, active_only=False)
        is_super = admin.role == AdminRole.SUPER_ADMIN.value

        if not categories:
            text = "🗂 دسته‌بندی‌ها\n\nهنوز دسته‌بندی ایجاد نشده است."
        else:
            text = f"🗂 دسته‌بندی‌ها ({len(categories)} مورد):\n\nروی هر دسته‌بندی کلیک کنید:"

        await callback.message.edit(
            text,
            components=categories_menu_keyboard(categories, is_super_admin=is_super)
        )

    async def add(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_name")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:categories")]])
        await callback.message.edit(
            "➕ افزودن دسته‌بندی جدید\n\n"
            "مرحله ۱/۲: نام دسته‌بندی را وارد کنید:\n"
            "مثال: گردنبند، دستبند، انگشتر",
            components=cancel_kb
        )

    async def view(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        category_id = int(match.group(1))

        async with ctx.session_factory() as session:
            category = await category_repo.get_category_by_id(session, category_id)
        if not category:
            await callback.message.reply("دسته‌بندی یافت نشد.")
            return

        status = "✅ فعال" if category.is_active else "❌ غیرفعال"
        text = (
            f"🗂 دسته‌بندی: {category.name}\n"
            f"🔤 پیشوند SKU: {category.prefix}\n"
            f"📊 وضعیت: {status}"
        )
        await callback.message.edit(
            text,
            components=category_detail_keyboard(category.id, category.is_active)
        )

    async def toggle(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        category_id = int(match.group(1))

        async with ctx.session_factory() as session:
            category = await category_repo.toggle_category(session, category_id)
        if not category:
            await callback.message.reply("دسته‌بندی یافت نشد.")
            return
        
        await self.view(callback, ctx, match)

    async def edit(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        category_id = int(match.group(1))

        self.conversations.start(chat_id, self.HANDLER_NAME, "edit_name", {"category_id": category_id})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cat:view:{category_id}")]])
        
        async with ctx.session_factory() as session:
            category = await category_repo.get_category_by_id(session, category_id)
        await callback.message.edit(
            f"✏️ ویرایش دسته‌بندی ({category.name})\n\n"
            "نام جدید دسته‌بندی را وارد کنید:\n"
            "(برای تغییر ندادن نام، علامت - را بفرستید)",
            components=cancel_kb
        )
