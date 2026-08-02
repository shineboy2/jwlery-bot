import logging
import time
from datetime import datetime
from bale import Message, CallbackQuery, InlineKeyboardButton
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import user_repo, order_repo
from app.database.repositories.user_repo import create_user
from app.bot.handlers.customer.keyboards import customer_detail_keyboard, build_kb
from app.utils.formatters import to_persian_digits, format_price
from app.bot.handlers.order.renderers import format_order_status

logger = logging.getLogger(__name__)

class CustomerHandler(BaseHandler):
    HANDLER_NAME = "customer"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_exact("menu:customers", self.menu)
        router.register_exact("cust:add", self.add_customer)
        router.register_exact("cust:search", self.search)
        router.register_pattern(r"^cust:view:(\d+)$", self.view)
        router.register_pattern(r"^cust:orders:(\d+)$", self.orders)
        router.register_pattern(r"^cust:edit:(\d+)$", self.edit)
        router.register_pattern(r"^cust:edit:([a-z_]+):(\d+)$", self.edit_field)

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        step = state.step
        text = message.content.strip() if message.content else ""

        if step == "add_full_name":
            self.conversations.advance(chat_id, self.HANDLER_NAME, "add_phone", full_name=text)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
            await message.reply("مرحله ۲/۶: لطفاً شماره موبایل مشتری را وارد کنید:", components=cancel_kb)
            return True

        if step == "add_phone":
            self.conversations.advance(chat_id, self.HANDLER_NAME, "add_id", phone_number=text)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
            await message.reply("مرحله ۳/۶: لطفاً آیدی مشتری در بله/تلگرام را وارد کنید (در صورت نداشتن آیدی بنویسید 'رد'):", components=cancel_kb)
            return True

        if step == "add_id":
            notes = f"ID: {text}" if text.lower() not in ("رد", "skip", "-") else ""
            self.conversations.advance(chat_id, self.HANDLER_NAME, "add_address", notes=notes)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
            await message.reply("مرحله ۴/۶: لطفاً آدرس دقیق پستی مشتری را وارد کنید (اجباری):", components=cancel_kb)
            return True

        if step == "add_address":
            if not text or text.lower() in ("رد", "skip", "-"):
                await message.reply("⚠️ آدرس پستی اجباری است. لطفاً آدرس را وارد کنید:")
                return True
                
            self.conversations.advance(chat_id, self.HANDLER_NAME, "add_postal_code", address=text)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
            await message.reply("مرحله ۵/۶: کد پستی را وارد کنید (اختیاری - برای رد شدن بنویسید 'رد'):", components=cancel_kb)
            return True

        if step == "add_postal_code":
            postal_code = text if text.lower() not in ("رد", "skip", "-") else None
            self.conversations.advance(chat_id, self.HANDLER_NAME, "add_birth_date", postal_code=postal_code)
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
            await message.reply("مرحله ۶/۶: تاریخ تولد مشتری را وارد کنید (فرمت: YYYY-MM-DD مانند 1370-05-12) (اختیاری - برای رد شدن بنویسید 'رد'):", components=cancel_kb)
            return True

        if step == "add_birth_date":
            birth_date = None
            if text.lower() not in ("رد", "skip", "-"):
                try:
                    birth_date = datetime.strptime(text.replace("/", "-"), "%Y-%m-%d").date()
                except ValueError:
                    await message.reply("⚠️ فرمت تاریخ تولد نامعتبر است. لطفاً دقیقاً با فرمت YYYY-MM-DD وارد کنید یا برای عبور کلمه 'رد' را ارسال کنید:")
                    return True

            try:
                import time
                dummy_chat_id = -int(time.time() * 1000)
                async with self.session_factory() as session:
                    new_user = await create_user(
                        session=session,
                        chat_id=dummy_chat_id,
                        full_name=state.data["full_name"],
                        phone_number=state.data["phone_number"],
                        address=state.data["address"],
                        postal_code=state.data["postal_code"],
                        notes=state.data.get("notes"),
                        birth_date=birth_date
                    )
                    
                self.conversations.end(chat_id, self.HANDLER_NAME)
                kb = build_kb([[InlineKeyboardButton("👀 مشاهده مشتری", callback_data=f"cust:view:{new_user.id}")]])
                await message.reply(f"✅ مشتری {new_user.full_name} با موفقیت ثبت شد.", components=kb)
            except Exception as e:
                logger.error(f"Error creating customer: {e}")
                await message.reply("❌ خطا در ثبت مشتری.")
                self.conversations.end(chat_id, self.HANDLER_NAME)
            return True

        if step == "searching":
            self.conversations.end(chat_id, self.HANDLER_NAME)
            async with self.session_factory() as session:
                users = await user_repo.search_users(session, text)

            if not users:
                back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:customers")]])
                await message.reply(f"⚠️ مشتری‌ای با '{text}' یافت نشد.", components=back_kb)
                return True

            buttons = [[
                InlineKeyboardButton(
                    f"👤 {u.full_name} — {u.chat_id}",
                    callback_data=f"cust:view:{u.id}"
                )
            ] for u in users[:10]]
            buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:customers")])
            await message.reply(
                f"🔍 نتایج جستجو ({to_persian_digits(str(len(users)))} نفر):",
                components=build_kb(buttons)
            )
            return True

        # Handle field edits
        field_map = {
            "edit_name": "full_name",
            "edit_phone": "phone_number",
            "edit_address": "address",
            "edit_postal": "postal_code",
            "edit_notes": "notes",
        }

        if step in field_map:
            user_id = state.data["user_id"]
            field_db = field_map[step]
            async with self.session_factory() as session:
                await user_repo.update_user(session, user_id, **{field_db: text})
            self.conversations.end(chat_id, self.HANDLER_NAME)

            back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به پروفایل", callback_data=f"cust:view:{user_id}")]])
            await message.reply("✅ اطلاعات مشتری بروزرسانی شد.", components=back_kb)
            return True

        return False

    async def menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        async with ctx.session_factory() as session:
            users = await user_repo.get_all_users(session, page=1, per_page=20)

        if not users:
            back_kb = build_kb([
                [InlineKeyboardButton("➕ ثبت مشتری جدید", callback_data="cust:add")],
                [InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main")]
            ])
            await callback.message.edit("👥 هنوز هیچ مشتری‌ای ثبت نشده. برای افزودن مشتری جدید دکمه زیر را فشار دهید:", components=back_kb)
            return

        buttons = []
        buttons.append([InlineKeyboardButton("➕ ثبت مشتری جدید", callback_data="cust:add")])

        for user in users:
            buttons.append([
                InlineKeyboardButton(f"👤 {user.full_name}", callback_data=f"cust:view:{user.id}")
            ])

        buttons.append([
            InlineKeyboardButton("🔍 جستجو", callback_data="cust:search"),
            InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main"),
        ])

        await callback.message.edit(
            f"👥 مشتریان ({to_persian_digits(str(len(users)))} نفر):",
            components=build_kb(buttons)
        )

    async def view(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        user_id = int(match.group(1))

        async with ctx.session_factory() as session:
            user = await user_repo.get_user_by_id(session, user_id)
        if not user:
            await callback.message.reply("مشتری یافت نشد.")
            return

        text = (
            f"👤 پروفایل مشتری\n"
            "━━━━━━━━━━━━━━━\n"
            f"📛 نام: {user.full_name}\n"
            f"📱 Chat ID: {to_persian_digits(str(user.chat_id))}\n"
        )
        if user.phone_number:
            text += f"📞 تلفن: {user.phone_number}\n"
        if user.address:
            text += f"🏠 آدرس: {user.address}\n"
        if user.postal_code:
            text += f"📮 کد پستی: {user.postal_code}\n"
        if user.birth_date:
            text += f"🎂 تولد: {user.birth_date}\n"
        if user.notes:
            text += f"\n📝 یادداشت:\n{user.notes}\n"

        await callback.message.edit(text, components=customer_detail_keyboard(user.id))

    async def orders(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        user_id = int(match.group(1))

        async with ctx.session_factory() as session:
            user = await user_repo.get_user_by_id(session, user_id)
            orders = await order_repo.get_user_orders(session, user_id)

        if not orders:
            back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"cust:view:{user_id}")]])
            await callback.message.edit(f"📋 {user.full_name} هنوز سفارشی ندارد.", components=back_kb)
            return

        buttons = []
        text = f"📋 سفارشات {user.full_name} ({to_persian_digits(str(len(orders)))} سفارش):\n\n"

        for order in orders:
            text += (
                f"#{to_persian_digits(str(order.id).zfill(4))} — "
                f"{format_order_status(order.status)} — "
                f"{format_price(order.total_amount)}\n"
            )
            buttons.append([
                InlineKeyboardButton(
                    f"#{to_persian_digits(str(order.id).zfill(4))} {format_order_status(order.status)}",
                    callback_data=f"ord:view:{order.id}"
                )
            ])

        buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"cust:view:{user_id}")])
        await callback.message.edit(text, components=build_kb(buttons))

    async def edit(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        user_id = int(match.group(1))

        edit_kb = build_kb([
            [
                InlineKeyboardButton("📛 نام", callback_data=f"cust:edit:name:{user_id}"),
                InlineKeyboardButton("📞 تلفن", callback_data=f"cust:edit:phone:{user_id}"),
            ],
            [
                InlineKeyboardButton("🏠 آدرس", callback_data=f"cust:edit:address:{user_id}"),
                InlineKeyboardButton("📮 کد پستی", callback_data=f"cust:edit:postal:{user_id}"),
            ],
            [
                InlineKeyboardButton("📝 یادداشت", callback_data=f"cust:edit:notes:{user_id}"),
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data=f"cust:view:{user_id}"),
            ]
        ])
        await callback.message.edit(
            "✏️ ویرایش اطلاعات مشتری\nکدام فیلد را ویرایش کنید؟",
            components=edit_kb
        )

    async def edit_field(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        field = match.group(1)
        user_id = int(match.group(2))

        field_names = {
            "name": "نام کامل",
            "phone": "شماره تلفن",
            "address": "آدرس کامل",
            "postal": "کد پستی",
            "notes": "یادداشت",
        }

        self.conversations.start(chat_id, self.HANDLER_NAME, f"edit_{field}", {"user_id": user_id})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cust:view:{user_id}")]])
        
        await callback.message.edit(
            f"✏️ ویرایش {field_names.get(field, field)}\n\n"
            f"مقدار جدید را وارد کنید:",
            components=cancel_kb
        )

    async def search(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        self.conversations.start(chat_id, self.HANDLER_NAME, "searching")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
        
        await callback.message.edit(
            "🔍 جستجوی مشتری\n\nنام یا شماره تلفن مشتری را وارد کنید:",
            components=cancel_kb
        )

    async def add_customer(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        self.conversations.start(chat_id, self.HANDLER_NAME, "add_full_name")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
        
        await callback.message.edit(
            "➕ ثبت مشتری جدید\n\nلطفاً نام و نام خانوادگی مشتری را وارد کنید:",
            components=cancel_kb
        )
