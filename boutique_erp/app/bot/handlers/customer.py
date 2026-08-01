"""
Customer management handlers: list, view profile, edit info.
"""
import logging

from bale import Message, CallbackQuery

from app.database.crud import (
    get_admin_by_chat_id, get_all_users, get_user_by_id,
    get_user_orders, update_user, search_users
)
from app.bot.keyboards.inline import customer_detail_keyboard, orders_menu_keyboard
from app.utils.formatters import format_order_status, to_persian_digits, format_price

logger = logging.getLogger(__name__)

# FSM states for customer editing
_customer_states = {}  # {chat_id: {"step": "...", "data": {...}}}


async def callback_customers_menu(callback: CallbackQuery):
    """Show customer list."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    users = await get_all_users(page=1, per_page=20)

    if not users:
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        back_kb = build_kb([
            [InlineKeyboardButton("➕ ثبت مشتری جدید", callback_data="cust:add")],
            [InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main")]
        ])
        await callback.message.edit("👥 هنوز هیچ مشتری‌ای ثبت نشده. برای افزودن مشتری جدید دکمه زیر را فشار دهید:", components=back_kb)
        return

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    buttons = []
    
    # Add new customer button at the top
    buttons.append([
        InlineKeyboardButton("➕ ثبت مشتری جدید", callback_data="cust:add")
    ])

    for user in users:
        buttons.append([
            InlineKeyboardButton(
                f"👤 {user.full_name}",
                callback_data=f"cust:view:{user.id}"
            )
        ])

    # Search + back buttons
    buttons.append([
        InlineKeyboardButton("🔍 جستجو", callback_data="cust:search"),
        InlineKeyboardButton("🏠 بازگشت", callback_data="menu:main"),
    ])

    await callback.message.edit(
        f"👥 مشتریان ({to_persian_digits(str(len(users)))} نفر):",
        components=build_kb(buttons)
    )


async def callback_customer_view(callback: CallbackQuery, user_id: int):
    """Show customer profile."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    user = await get_user_by_id(user_id)
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

    await callback.message.edit(
        text,
        components=customer_detail_keyboard(user.id)
    )


async def callback_customer_orders(callback: CallbackQuery, user_id: int):
    """Show customer's order history."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    user = await get_user_by_id(user_id)
    orders = await get_user_orders(user_id)

    if not orders:
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        back_kb = build_kb([[
            InlineKeyboardButton("🔙 بازگشت", callback_data=f"cust:view:{user_id}")
        ]])
        await callback.message.edit(
            f"📋 {user.full_name} هنوز سفارشی ندارد.",
            components=back_kb
        )
        return

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
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


async def callback_customer_edit(callback: CallbackQuery, user_id: int):
    """Start customer edit flow."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
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


async def callback_customer_edit_field(callback: CallbackQuery, field: str, user_id: int):
    """Start editing a specific field."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    field_names = {
        "name": "نام کامل",
        "phone": "شماره تلفن",
        "address": "آدرس کامل",
        "postal": "کد پستی",
        "notes": "یادداشت",
    }

    _customer_states[chat_id] = {
        "step": f"edit_{field}",
        "data": {"user_id": user_id}
    }

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data=f"cust:view:{user_id}")
    ]])
    await callback.message.edit(
        f"✏️ ویرایش {field_names.get(field, field)}\n\n"
        f"مقدار جدید را وارد کنید:",
        components=cancel_kb
    )


async def callback_customer_search(callback: CallbackQuery):
    """Start customer search."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _customer_states[chat_id] = {"step": "searching", "data": {}}

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="menu:customers")
    ]])
    await callback.message.edit(
        "🔍 جستجوی مشتری\n\nنام یا شماره تلفن مشتری را وارد کنید:",
        components=cancel_kb
    )


async def callback_add_customer(callback: CallbackQuery):
    """Start FSM to add a new customer."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _customer_states[chat_id] = {"step": "add_full_name", "data": {}}

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="menu:customers")
    ]])
    await callback.message.edit(
        "➕ ثبت مشتری جدید\n\nلطفاً نام و نام خانوادگی مشتری را وارد کنید:",
        components=cancel_kb
    )

async def handle_customer_message(message: Message) -> bool:
    """Handle messages for customer FSM. Returns True if consumed."""
    chat_id = message.chat.id
    state = _customer_states.get(chat_id)
    if not state:
        return False

    step = state["step"]
    text = message.content.strip() if message.content else ""

    if step == "add_full_name":
        state["data"]["full_name"] = text
        state["step"] = "add_phone"
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
        await message.reply("مرحله ۲/۶: لطفاً شماره موبایل مشتری را وارد کنید:", components=cancel_kb)
        return True

    if step == "add_phone":
        state["data"]["phone_number"] = text
        state["step"] = "add_id"
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
        await message.reply("مرحله ۳/۶: لطفاً آیدی مشتری در بله/تلگرام را وارد کنید (در صورت نداشتن آیدی بنویسید 'رد'):", components=cancel_kb)
        return True

    if step == "add_id":
        state["data"]["notes"] = f"ID: {text}" if text.lower() not in ("رد", "skip", "-") else ""
        state["step"] = "add_address"
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
        await message.reply("مرحله ۴/۶: لطفاً آدرس دقیق پستی مشتری را وارد کنید (اجباری):", components=cancel_kb)
        return True

    if step == "add_address":
        if not text or text.lower() in ("رد", "skip", "-"):
            await message.reply("⚠️ آدرس پستی اجباری است. لطفاً آدرس را وارد کنید:")
            return True
            
        state["data"]["address"] = text
        state["step"] = "add_postal_code"
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
        await message.reply("مرحله ۵/۶: کد پستی را وارد کنید (اختیاری - برای رد شدن بنویسید 'رد'):", components=cancel_kb)
        return True

    if step == "add_postal_code":
        state["data"]["postal_code"] = text if text.lower() not in ("رد", "skip", "-") else None
        state["step"] = "add_birth_date"
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:customers")]])
        await message.reply("مرحله ۶/۶: تاریخ تولد مشتری را وارد کنید (فرمت: YYYY-MM-DD مانند 1370-05-12) (اختیاری - برای رد شدن بنویسید 'رد'):", components=cancel_kb)
        return True

    if step == "add_birth_date":
        birth_date = None
        if text.lower() not in ("رد", "skip", "-"):
            try:
                from datetime import datetime
                birth_date = datetime.strptime(text.replace("/", "-"), "%Y-%m-%d").date()
            except ValueError:
                await message.reply("⚠️ فرمت تاریخ تولد نامعتبر است. لطفاً دقیقاً با فرمت YYYY-MM-DD وارد کنید یا برای عبور کلمه 'رد' را ارسال کنید:")
                return True

        from app.database.crud import async_session
        from app.database.models import User
        import time
        try:
            async with async_session() as session:
                # Generate unique chat_id for manually added users who haven't started bot
                # Bale user IDs are positive ints, we use negative timestamp to avoid collision with real chat_ids
                dummy_chat_id = -int(time.time() * 1000)
                
                new_user = User(
                    chat_id=dummy_chat_id,
                    full_name=state["data"]["full_name"],
                    phone_number=state["data"]["phone_number"],
                    address=state["data"]["address"],
                    postal_code=state["data"]["postal_code"],
                    notes=state["data"].get("notes"),
                    birth_date=birth_date
                )
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                
            del _customer_states[chat_id]
            from bale import InlineKeyboardButton
            from app.bot.keyboards.inline import build_kb
            kb = build_kb([[InlineKeyboardButton("👀 مشاهده مشتری", callback_data=f"cust:view:{new_user.id}")]])
            await message.reply(f"✅ مشتری {new_user.full_name} با موفقیت ثبت شد.", components=kb)
        except Exception as e:
            logger.error(f"Error creating customer: {e}")
            await message.reply("❌ خطا در ثبت مشتری.")
            del _customer_states[chat_id]
        return True

    if step == "searching":
        del _customer_states[chat_id]
        users = await search_users(text)

        if not users:
            from bale import InlineKeyboardButton
            from app.bot.keyboards.inline import build_kb
            back_kb = build_kb([[
                InlineKeyboardButton("🔙 بازگشت", callback_data="menu:customers")
            ]])
            await message.reply(f"⚠️ مشتری‌ای با '{text}' یافت نشد.", components=back_kb)
            return True

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
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
        user_id = state["data"]["user_id"]
        field_db = field_map[step]
        await update_user(user_id, **{field_db: text})
        del _customer_states[chat_id]

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        back_kb = build_kb([[
            InlineKeyboardButton("🔙 بازگشت به پروفایل", callback_data=f"cust:view:{user_id}")
        ]])
        await message.reply("✅ اطلاعات مشتری بروزرسانی شد.", components=back_kb)
        return True

    return False
