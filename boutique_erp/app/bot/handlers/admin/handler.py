import logging
from bale import Message, CallbackQuery, InlineKeyboardButton
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.core.config import settings
from app.core.constants import AdminRole
from app.database.repositories import admin_repo
from app.bot.handlers.admin.keyboards import (
    main_menu_keyboard, settings_keyboard, back_to_main_keyboard, build_kb
)

logger = logging.getLogger(__name__)

class AdminHandler(BaseHandler):
    HANDLER_NAME = "admin"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        message_router.register_command("/start", self.cmd_start)
        router.register_exact("menu:main", self.callback_main_menu)
        router.register_exact("menu:settings", self.callback_settings)
        router.register_exact("admin:list", self.callback_admin_list)
        router.register_exact("admin:add", self.callback_admin_add)
        router.register_exact("admin:remove", self.callback_admin_remove)

    async def cmd_start(self, message: Message, ctx) -> None:
        """Handle /start command. Auto-register SUPER_ADMIN on first run."""
        chat_id = message.chat.id
        full_name = message.chat.first_name or "ادمین"

        async with self.session_factory() as session:
            if chat_id == settings.super_admin_chat_id:
                admin = await admin_repo.get_admin_by_chat_id(session, chat_id)
                if not admin:
                    await admin_repo.create_admin(
                        session=session,
                        chat_id=chat_id,
                        full_name=full_name,
                        role=AdminRole.SUPER_ADMIN.value
                    )
                    logger.info(f"SUPER_ADMIN {chat_id} auto-registered.")
                admin = await admin_repo.get_admin_by_chat_id(session, chat_id)
            else:
                admin = await admin_repo.get_admin_by_chat_id(session, chat_id)

            if not admin or not admin.is_active:
                return

        try:
            await message.reply(
                f"👋 سلام {full_name} عزیز!\n\n"
                "🎛 به پنل مدیریت بوتیک خوش آمدید.\n"
                "از منوی زیر انتخاب کنید:",
                components=main_menu_keyboard(admin.role == AdminRole.SUPER_ADMIN.value)
            )
        except Exception as e:
            logger.error(f"Error in reply: {e}", exc_info=True)

    async def callback_main_menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        admin = await self.require_admin(chat_id)
        if not admin: return

        await callback.message.edit(
            "🎛 پنل مدیریت بوتیک\nاز منوی زیر انتخاب کنید:",
            components=main_menu_keyboard(admin.role == AdminRole.SUPER_ADMIN.value)
        )

    async def callback_settings(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        admin = await self.require_admin(chat_id)
        if not admin: return

        is_super = admin.role == AdminRole.SUPER_ADMIN.value
        await callback.message.edit(
            "⚙️ تنظیمات\nمدیریت ادمین‌های ربات:",
            components=settings_keyboard(is_super_admin=is_super)
        )

    async def callback_admin_list(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        admin = await self.require_admin(chat_id)
        if not admin: return

        async with self.session_factory() as session:
            admins = await admin_repo.get_all_admins(session)
        text = "👤 لیست ادمین‌ها:\n\n"
        for a in admins:
            status = "✅" if a.is_active else "❌"
            role_text = "👑 سوپر ادمین" if a.role == AdminRole.SUPER_ADMIN.value else "🔑 ادمین"
            text += f"{status} {role_text}: {a.full_name}\n📌 Chat ID: `{a.chat_id}`\n\n"

        if not admins:
            text = "هیچ ادمینی ثبت نشده است."

        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:settings")]])
        await callback.message.edit(text, components=back_kb)

    async def callback_admin_add(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_super_admin(chat_id):
            await callback.message.reply("⛔ فقط سوپر ادمین می‌تواند ادمین اضافه کند.")
            return

        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_admin_chat_id")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:settings")]])
        await callback.message.edit(
            "➕ افزودن ادمین جدید\n\n"
            "لطفاً Chat ID ادمین جدید را ارسال کنید:\n"
            "(عدد بدون @ مثلاً: 123456789)",
            components=cancel_kb
        )

    async def callback_admin_remove(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_super_admin(chat_id):
            await callback.message.reply("⛔ فقط سوپر ادمین می‌تواند ادمین حذف کند.")
            return

        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_remove_admin_id")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:settings")]])
        await callback.message.edit(
            "🗑 حذف ادمین\n\n"
            "Chat ID ادمینی که می‌خواهید حذف کنید را ارسال کنید:",
            components=cancel_kb
        )

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        if state.step == "awaiting_admin_chat_id":
            try:
                new_chat_id = int(message.content.strip())
            except ValueError:
                await message.reply("⚠️ Chat ID باید یک عدد باشد. دوباره ارسال کنید:")
                return True

            async with self.session_factory() as session:
                existing = await admin_repo.get_admin_by_chat_id(session, new_chat_id)
                if existing:
                    await message.reply(f"⚠️ این کاربر قبلاً ادمین است ({existing.full_name}).")
                    self.conversations.end(chat_id, self.HANDLER_NAME)
                    return True

                if new_chat_id == settings.super_admin_chat_id:
                    await message.reply("⚠️ سوپر ادمین از قبل ثبت است.")
                    self.conversations.end(chat_id, self.HANDLER_NAME)
                    return True

                new_admin = await admin_repo.create_admin(
                    session=session,
                    chat_id=new_chat_id,
                    full_name=f"ادمین {new_chat_id}",
                    role=AdminRole.ADMIN.value
                )
            self.conversations.end(chat_id, self.HANDLER_NAME)
            await message.reply(
                f"✅ ادمین جدید با Chat ID `{new_chat_id}` اضافه شد.\n"
                "برای استفاده از ربات باید /start بفرستد.",
                components=back_to_main_keyboard()
            )
            return True

        elif state.step == "awaiting_remove_admin_id":
            try:
                remove_chat_id = int(message.content.strip())
            except ValueError:
                await message.reply("⚠️ Chat ID باید یک عدد باشد. دوباره ارسال کنید:")
                return True

            if remove_chat_id == settings.super_admin_chat_id:
                await message.reply("⛔ نمی‌توان سوپر ادمین را حذف کرد.")
                self.conversations.end(chat_id, self.HANDLER_NAME)
                return True

            async with self.session_factory() as session:
                success = await admin_repo.deactivate_admin(session, remove_chat_id)
            self.conversations.end(chat_id, self.HANDLER_NAME)
            if success:
                await message.reply(
                    f"✅ ادمین با Chat ID `{remove_chat_id}` غیرفعال شد.",
                    components=back_to_main_keyboard()
                )
            else:
                await message.reply(
                    "⚠️ ادمینی با این Chat ID پیدا نشد.",
                    components=back_to_main_keyboard()
                )
            return True

        return False
