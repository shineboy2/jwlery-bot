"""
Finance management handlers: Expenses, Partner transactions, P&L Reports.
"""
import logging
from datetime import datetime, timedelta
import calendar

from bale import Message, CallbackQuery

from app.database.crud import (
    get_admin_by_chat_id, get_expense_categories, create_expense,
    get_all_partners, create_partner_transaction
)
from app.services.finance_service import calculate_pl_report, format_pl_report
from app.bot.keyboards.inline import (
    finance_menu_keyboard, expense_categories_keyboard,
    partners_keyboard, partner_transaction_type_keyboard, build_kb
)
from bale import InlineKeyboardButton
from app.utils.formatters import to_persian_digits, format_price

logger = logging.getLogger(__name__)

# FSM state
_finance_states = {}  # {chat_id: {"step": "...", "data": {...}}}


async def callback_finance_menu(callback: CallbackQuery):
    """Show main finance menu."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _finance_states.pop(chat_id, None)

    from app.database.models import AdminRole
    await callback.message.edit(
        "💰 مدیریت مالی\nلطفاً یک گزینه را انتخاب کنید:",
        components=finance_menu_keyboard(admin.role == AdminRole.SUPER_ADMIN.value)
    )


# ─────────────────────────────────────────
# Expense Handlers
# ─────────────────────────────────────────
async def callback_expense_new(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _finance_states[chat_id] = {"step": "awaiting_expense_amount", "data": {}}

    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:finance")]])
    await callback.message.edit(
        "💸 ثبت هزینه جدید\n\n"
        "مبلغ هزینه را به تومان وارد کنید:",
        components=cancel_kb
    )


async def callback_expense_category(callback: CallbackQuery, cat_id: int):
    chat_id = callback.message.chat.id
    state = _finance_states.get(chat_id)
    if not state or state["step"] != "awaiting_expense_category":
        return

    state["data"]["category_id"] = cat_id
    state["step"] = "awaiting_expense_desc"
    _finance_states[chat_id] = state

    cancel_kb = build_kb([[
        InlineKeyboardButton("⏭ ثبت بدون توضیحات", callback_data="fin:exp:skip_desc"),
        InlineKeyboardButton("❌ لغو", callback_data="menu:finance")
    ]])
    await callback.message.edit(
        "📝 توضیحات هزینه را وارد کنید:\n"
        "(یا ثبت بدون توضیحات را بزنید)",
        components=cancel_kb
    )


async def callback_expense_skip_desc(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    await finalize_expense(chat_id, callback.message, None)


async def finalize_expense(chat_id: int, message_or_callback_msg, description: str = None):
    state = _finance_states.get(chat_id)
    if not state or state["step"] != "awaiting_expense_desc":
        return

    data = state["data"]
    amount = data["amount"]
    category_id = data["category_id"]

    try:
        await create_expense(category_id=category_id, amount=amount, description=description)
        msg = f"✅ هزینه {format_price(amount)} با موفقیت ثبت شد."
    except Exception as e:
        logger.error(f"Error creating expense: {e}")
        msg = "❌ خطا در ثبت هزینه."

    _finance_states.pop(chat_id, None)
    
    back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به مدیریت مالی", callback_data="menu:finance")]])
    if isinstance(message_or_callback_msg, Message):
        await message_or_callback_msg.reply(msg, components=back_kb)
    else:
        await message_or_callback_msg.edit(msg, components=back_kb)


# ─────────────────────────────────────────
# Partner Handlers
# ─────────────────────────────────────────
async def callback_partner_new(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    partners = await get_all_partners()
    if not partners:
        await callback.message.reply("هیچ شریکی در سیستم ثبت نشده است.")
        return

    _finance_states[chat_id] = {"step": "awaiting_partner_selection", "data": {}}
    
    await callback.message.edit(
        "🤝 ثبت تراکنش شرکا\n\n"
        "ابتدا شریک مورد نظر را انتخاب کنید:",
        components=partners_keyboard(partners)
    )

async def callback_partner_select(callback: CallbackQuery, partner_id: int):
    chat_id = callback.message.chat.id
    state = _finance_states.get(chat_id)
    if not state or state["step"] != "awaiting_partner_selection":
        return
        
    state["data"]["partner_id"] = partner_id
    state["step"] = "awaiting_partner_type"
    _finance_states[chat_id] = state
    
    await callback.message.edit(
        "نوع تراکنش را انتخاب کنید:",
        components=partner_transaction_type_keyboard(partner_id)
    )


async def callback_partner_type(callback: CallbackQuery, tx_type: str, partner_id: int):
    chat_id = callback.message.chat.id
    state = _finance_states.get(chat_id)
    if not state or state["step"] != "awaiting_partner_type":
        return
        
    state["data"]["type"] = tx_type
    state["step"] = "awaiting_partner_amount"
    _finance_states[chat_id] = state
    
    type_fa = "برداشت شخصی" if tx_type == "DRAWING" else "تزریق سرمایه"
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:finance")]])
    
    await callback.message.edit(
        f"مبلغ {type_fa} را به تومان وارد کنید:",
        components=cancel_kb
    )


async def callback_partner_skip_desc(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    await finalize_partner_tx(chat_id, callback.message, None)


async def finalize_partner_tx(chat_id: int, message_or_callback_msg, description: str = None):
    state = _finance_states.get(chat_id)
    if not state or state["step"] != "awaiting_partner_desc":
        return

    data = state["data"]
    partner_id = data["partner_id"]
    tx_type = data["type"]
    amount = data["amount"]

    try:
        await create_partner_transaction(partner_id=partner_id, amount=amount, type=tx_type, description=description)
        type_fa = "برداشت" if tx_type == "DRAWING" else "تزریق سرمایه"
        msg = f"✅ {type_fa} مبلغ {format_price(amount)} با موفقیت ثبت شد."
    except Exception as e:
        logger.error(f"Error creating partner tx: {e}")
        msg = "❌ خطا در ثبت تراکنش."

    _finance_states.pop(chat_id, None)
    
    back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به مدیریت مالی", callback_data="menu:finance")]])
    if isinstance(message_or_callback_msg, Message):
        await message_or_callback_msg.reply(msg, components=back_kb)
    else:
        await message_or_callback_msg.edit(msg, components=back_kb)


# ─────────────────────────────────────────
# Reports Handlers
# ─────────────────────────────────────────
async def callback_report_pl(callback: CallbackQuery, period: str):
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    await callback.message.edit("در حال محاسبه سود و زیان... ⏳")

    now = datetime.now()
    if period == "month":
        # First day of current Jalali month is hard to compute without jdatetime
        # We will just use the last 30 days for simplicity if jdatetime is not used, 
        # or use standard month. Let's use last 30 days for "month".
        start_date = now - timedelta(days=30)
        end_date = now
        title = "گزارش سود و زیان (۳۰ روز اخیر)"
    else:
        start_date = None
        end_date = None
        title = "گزارش سود و زیان (کل زمان‌ها)"

    data = await calculate_pl_report(start_date, end_date)
    text = format_pl_report(data, title)

    back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به مدیریت مالی", callback_data="menu:finance")]])
    await callback.message.edit(text, components=back_kb)


# ─────────────────────────────────────────
# Main Message Handler for FSM
# ─────────────────────────────────────────
async def handle_finance_message(message: Message) -> bool:
    """Handle messages for finance FSM. Returns True if consumed."""
    chat_id = message.chat.id
    state = _finance_states.get(chat_id)
    if not state:
        return False

    step = state["step"]
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

        state["data"]["amount"] = amount * 10  # Rials
        state["step"] = "awaiting_expense_category"
        _finance_states[chat_id] = state

        categories = await get_expense_categories()
        await message.reply(
            f"✅ مبلغ {format_price(amount*10)}\n\n"
            "اکنون دسته‌بندی هزینه را انتخاب کنید:",
            components=expense_categories_keyboard(categories)
        )
        return True

    if step == "awaiting_expense_desc":
        await finalize_expense(chat_id, message, text)
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

        state["data"]["amount"] = amount * 10  # Rials
        state["step"] = "awaiting_partner_desc"
        _finance_states[chat_id] = state

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
        await finalize_partner_tx(chat_id, message, text)
        return True

    return False
