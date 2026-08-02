import logging
from bale import Message, CallbackQuery, InlineKeyboardButton
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.services.report_service import get_profit_report, get_inventory_report, get_sales_report
from app.bot.handlers.report.keyboards import reports_menu_keyboard, build_kb
from app.bot.handlers.report.renderers import format_profit_report, format_inventory_report
from app.utils.formatters import to_persian_digits, format_price

logger = logging.getLogger(__name__)

class ReportHandler(BaseHandler):
    HANDLER_NAME = "report"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_exact("menu:reports", self.menu)
        router.register_exact("rep:profit", self.profit_all)
        router.register_exact("rep:profit:all", self.profit_all)
        router.register_exact("rep:profit:month", self.profit_month)
        router.register_exact("rep:inventory", self.inventory)
        router.register_exact("rep:sales:week", self.sales_week)
        router.register_exact("rep:sales:month", self.sales_month)

    async def handle_message(self, message: Message) -> bool:
        return False

    async def menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_super_admin(chat_id):
            return

        await callback.message.edit(
            "📊 گزارش‌ها و حسابداری\nاز منوی زیر انتخاب کنید:",
            components=reports_menu_keyboard()
        )

    async def profit_all(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_super_admin(chat_id):
            return

        data = await get_profit_report()
        text = format_profit_report(data, "کل")
        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:reports")]])
        await callback.message.edit(text, components=back_kb)

    async def profit_month(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_super_admin(chat_id):
            return

        from datetime import datetime
        now = datetime.utcnow()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data = await get_profit_report(start_date=start)
        
        text = format_profit_report(data, "ماه جاری")
        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:reports")]])
        await callback.message.edit(text, components=back_kb)

    async def inventory(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_super_admin(chat_id):
            return

        data = await get_inventory_report()
        text = format_inventory_report(data)
        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:reports")]])
        await callback.message.edit(text, components=back_kb)

    async def _sales_report(self, callback: CallbackQuery, period: str) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_super_admin(chat_id):
            return

        data = await get_sales_report(period)

        top_text = "\n".join(
            f"  {i + 1}. [{p['sku']}] {p['name']} — {to_persian_digits(str(p['sold']))} فروخته شده"
            for i, p in enumerate(data["top_products"])
        ) or "  داده‌ای موجود نیست"

        text = (
            f"📈 گزارش فروش — {data['period']}\n"
            "━━━━━━━━━━━━━━━\n"
            f"📦 تعداد سفارشات: {to_persian_digits(str(data['orders_count']))}\n"
            f"🛍 اقلام فروخته شده: {to_persian_digits(str(data['items_sold']))}\n"
            f"💰 درآمد: {format_price(data['revenue'])}\n"
            "━━━━━━━━━━━━━━━\n"
            f"🏆 پرفروش‌ترین محصولات:\n{top_text}"
        )

        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:reports")]])
        await callback.message.edit(text, components=back_kb)

    async def sales_week(self, callback: CallbackQuery, ctx) -> None:
        await self._sales_report(callback, "week")

    async def sales_month(self, callback: CallbackQuery, ctx) -> None:
        await self._sales_report(callback, "month")
