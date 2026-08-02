import logging
from datetime import datetime, timedelta
from bale import Message, CallbackQuery, InlineKeyboardButton
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import finance_repo
from app.services.finance_service import calculate_pl_report, format_pl_report
from app.bot.handlers.finance.keyboards import (
    finance_menu_keyboard, expense_categories_keyboard,
    partners_keyboard, partner_transaction_type_keyboard, build_kb
)
from app.utils.formatters import format_price
from app.core.constants import AdminRole

logger = logging.getLogger(__name__)

class FinanceHandler(BaseHandler):
    HANDLER_NAME = "finance"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_exact("menu:finance", self.menu)
        router.register_exact("fin:exp:new", self.expense_new)
        router.register_pattern(r"^fin:exp:cat:(\d+)$", self.expense_category)
        router.register_exact("fin:exp:skip_desc", self.expense_skip_desc)
        router.register_exact("fin:part:new", self.partner_new)
        router.register_pattern(r"^fin:part:id:(\d+)$", self.partner_select)
        router.register_pattern(r"^fin:part:type:(DRAWING|INJECTION):(\d+)$", self.partner_type)
        router.register_exact("fin:part:skip_desc", self.partner_skip_desc)
        router.register_pattern(r"^fin:rep:(month|all)$", self.report_pl)

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        step = state.step
        text = message.content.strip() if message.content else ""

        # Expense Flow
        if step == "awaiting_expense_amount":
            try:
                amount = int(text.replace(",", "").replace("،", ""))
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await message.reply("⚠️ مبلغ باید یک عدد معتبر باشد.")
                return True

            amount_rials = amount * 10
            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_expense_category", amount=amount_rials)

            async with self.session_factory() as session:
                categories = await finance_repo.get_expense_categories(session)
            await message.reply(
                f"✅ مبلغ {format_price(amount_rials)}\n\n"
                "اکنون دسته‌بندی هزینه را انتخاب کنید:",
                components=expense_categories_keyboard(categories)
            )
            return True

        if step == "awaiting_expense_desc":
            await self.finalize_expense(chat_id, message, text)
            return True

        # Partner Tx Flow
        if step == "awaiting_partner_amount":
            try:
                amount = int(text.replace(",", "").replace("،", ""))
                if amount <= 0:
                    raise ValueError
            except ValueError:
                await message.reply("⚠️ مبلغ باید یک عدد معتبر باشد.")
                return True

            amount_rials = amount * 10
            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_partner_desc", amount=amount_rials)

            cancel_kb = build_kb([[
                InlineKeyboardButton("⏭ ثبت بدون توضیحات", callback_data="fin:part:skip_desc"),
                InlineKeyboardButton("❌ لغو", callback_data="menu:finance")
            ]])
            await message.reply(
                "📝 توضیحات تراکنش را وارد کنید:\n"
                "(مثلاً: خرید ملزومات شخصی از کارت شرکت)",
                components=cancel_kb
            )
            return True

        if step == "awaiting_partner_desc":
            await self.finalize_partner_tx(chat_id, message, text)
            return True

        return False

    async def finalize_expense(self, chat_id: int, message_or_callback_msg, description: str = None):
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_expense_desc":
            return

        amount = state.data["amount"]
        category_id = state.data["category_id"]

        try:
            async with self.session_factory() as session:
                await finance_repo.create_expense(session, category_id=category_id, amount=amount, description=description)
            msg = f"✅ هزینه {format_price(amount)} با موفقیت ثبت شد."
        except Exception as e:
            logger.error(f"Error creating expense: {e}")
            msg = "❌ خطا در ثبت هزینه."

        self.conversations.end(chat_id, self.HANDLER_NAME)
        
        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به مدیریت مالی", callback_data="menu:finance")]])
        if isinstance(message_or_callback_msg, Message):
            await message_or_callback_msg.reply(msg, components=back_kb)
        else:
            await message_or_callback_msg.edit(msg, components=back_kb)

    async def finalize_partner_tx(self, chat_id: int, message_or_callback_msg, description: str = None):
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_partner_desc":
            return

        partner_id = state.data["partner_id"]
        tx_type = state.data["type"]
        amount = state.data["amount"]

        try:
            async with self.session_factory() as session:
                await finance_repo.create_partner_transaction(session, partner_id=partner_id, amount=amount, type=tx_type, description=description)
            type_fa = "برداشت" if tx_type == "DRAWING" else "تزریق سرمایه"
            msg = f"✅ {type_fa} مبلغ {format_price(amount)} با موفقیت ثبت شد."
        except Exception as e:
            logger.error(f"Error creating partner tx: {e}")
            msg = "❌ خطا در ثبت تراکنش."

        self.conversations.end(chat_id, self.HANDLER_NAME)
        
        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به مدیریت مالی", callback_data="menu:finance")]])
        if isinstance(message_or_callback_msg, Message):
            await message_or_callback_msg.reply(msg, components=back_kb)
        else:
            await message_or_callback_msg.edit(msg, components=back_kb)


    async def menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        admin = await self.require_admin(chat_id)
        if not admin: return

        self.conversations.end(chat_id, self.HANDLER_NAME)

        await callback.message.edit(
            "💰 مدیریت مالی\nلطفاً یک گزینه را انتخاب کنید:",
            components=finance_menu_keyboard(admin.role == AdminRole.SUPER_ADMIN.value)
        )

    async def expense_new(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_expense_amount")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:finance")]])
        await callback.message.edit(
            "💸 ثبت هزینه جدید\n\n"
            "مبلغ هزینه را به تومان وارد کنید:",
            components=cancel_kb
        )

    async def expense_category(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        cat_id = int(match.group(1))
        
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_expense_category":
            return

        self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_expense_desc", category_id=cat_id)
        cancel_kb = build_kb([[
            InlineKeyboardButton("⏭ ثبت بدون توضیحات", callback_data="fin:exp:skip_desc"),
            InlineKeyboardButton("❌ لغو", callback_data="menu:finance")
        ]])
        await callback.message.edit(
            "📝 توضیحات هزینه را وارد کنید:\n"
            "(یا ثبت بدون توضیحات را بزنید)",
            components=cancel_kb
        )

    async def expense_skip_desc(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        await self.finalize_expense(chat_id, callback.message, None)

    async def partner_new(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        async with ctx.session_factory() as session:
            partners = await finance_repo.get_all_partners(session)
        if not partners:
            await callback.message.reply("هیچ شریکی در سیستم ثبت نشده است.")
            return

        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_partner_selection")
        await callback.message.edit(
            "🤝 ثبت تراکنش شرکا\n\n"
            "ابتدا شریک مورد نظر را انتخاب کنید:",
            components=partners_keyboard(partners)
        )

    async def partner_select(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        partner_id = int(match.group(1))
        
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_partner_selection":
            return
            
        self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_partner_type", partner_id=partner_id)
        await callback.message.edit(
            "نوع تراکنش را انتخاب کنید:",
            components=partner_transaction_type_keyboard(partner_id)
        )

    async def partner_type(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        tx_type = match.group(1)
        partner_id = int(match.group(2))
        
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_partner_type":
            return
            
        self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_partner_amount", type=tx_type)
        
        type_fa = "برداشت شخصی" if tx_type == "DRAWING" else "تزریق سرمایه"
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:finance")]])
        
        await callback.message.edit(
            f"مبلغ {type_fa} را به تومان وارد کنید:",
            components=cancel_kb
        )

    async def partner_skip_desc(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        await self.finalize_partner_tx(chat_id, callback.message, None)

    async def report_pl(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_super_admin(chat_id): return
        period = match.group(1)

        await callback.message.edit("در حال محاسبه سود و زیان... ⏳")

        now = datetime.now()
        if period == "month":
            start_date = now - timedelta(days=30)
            end_date = now
            title = "گزارش سود و زیان (۳۰ روز اخیر)"
        else:
            start_date = None
            end_date = None
            title = "گزارش سود و زیان (کل زمان‌ها)"

        async with ctx.session_factory() as session:
            data = await calculate_pl_report(session, start_date, end_date)
        text = format_pl_report(data, title)

        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به مدیریت مالی", callback_data="menu:finance")]])
        await callback.message.edit(text, components=back_kb)
