"""
Order management handlers: create, view, status changes.
"""
import logging

from bale import Message, CallbackQuery

from app.database.crud import (
    get_admin_by_chat_id, get_order_by_id, get_orders_by_status,
    get_recent_orders, get_or_create_user, search_users, get_all_products
)
from app.services.order_service import (
    create_new_order, confirm_payment, ship_order, cancel_order, get_payment_message
)
from app.bot.keyboards.inline import (
    orders_menu_keyboard, order_detail_keyboard, order_product_select_keyboard, back_to_main_keyboard
)
from app.utils.formatters import format_order_summary, format_order_status, to_persian_digits, format_price

logger = logging.getLogger(__name__)

# FSM states for order creation
_order_states = {}  # {chat_id: {"step": "...", "data": {...}}}


async def callback_orders_menu(callback: CallbackQuery):
    """Show orders menu."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    await callback.message.edit(
        "🛒 مدیریت سفارشات\nاز منوی زیر انتخاب کنید:",
        components=orders_menu_keyboard()
    )


async def callback_orders_filter(callback: CallbackQuery, status: str):
    """Show filtered orders by status."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    if status == "ALL":
        orders = await get_recent_orders(limit=20)
        title = "📋 آخرین سفارشات"
    else:
        orders = await get_orders_by_status(status)
        title = f"🛒 سفارشات — {format_order_status(status)}"

    if not orders:
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        back_kb = build_kb([[
            InlineKeyboardButton("🔙 بازگشت", callback_data="menu:orders")
        ]])
        await callback.message.edit(f"هیچ سفارشی یافت نشد.", components=back_kb)
        return

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    buttons = []
    for order in orders:
        buttons.append([
            InlineKeyboardButton(
                f"#{to_persian_digits(str(order.id).zfill(4))} — {order.user.full_name} — {format_order_status(order.status)}",
                callback_data=f"ord:view:{order.id}"
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:orders")])

    await callback.message.edit(
        f"{title} ({to_persian_digits(str(len(orders)))} مورد):",
        components=build_kb(buttons)
    )


async def callback_order_view(callback: CallbackQuery, order_id: int):
    """Show order details."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    order = await get_order_by_id(order_id)
    if not order:
        await callback.message.reply("سفارش یافت نشد.")
        return

    items_info = [
        {
            "sku": item.product.sku,
            "name": item.product.description[:30],
            "quantity": item.quantity,
            "sold_price": item.sold_price,
        }
        for item in order.items
    ]

    text = format_order_summary(order, order.user, items_info)
    if order.tracking_code:
        text += f"\n🚚 کد رهگیری: {order.tracking_code}"

    await callback.message.edit(
        text,
        components=order_detail_keyboard(order.id, order.status)
    )


async def callback_order_status(callback: CallbackQuery, order_id: int, new_status: str):
    """Handle order status changes."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    if new_status == "PAID":
        order = await confirm_payment(order_id)
        msg = "✅ پرداخت تأیید شد. سفارش در لیست ارسال قرار گرفت."
    elif new_status == "PAID_HELD":
        # If order is already PAID_HELD, and they press PAID, it just changes status.
        # Wait, if we use confirm_payment it decreases stock.
        order = await get_order_by_id(order_id)
        if order.status == "PENDING_PAYMENT":
            order = await confirm_payment(order_id)
        from app.database.crud import update_order_status
        order = await update_order_status(order_id, "PAID_HELD")
        msg = "📥 پرداخت تأیید شد و محصول دپو شد."
    elif new_status == "CANCELLED":
        order = await cancel_order(order_id)
        msg = "❌ سفارش لغو شد. موجودی آزاد شد."
    elif new_status == "DELIVERED":
        from app.database.crud import update_order_status
        order = await update_order_status(order_id, new_status)
        msg = "📦 سفارش تحویل داده شد."
    else:
        return

    if order:
        await callback.message.reply(msg)
        await callback_order_view(callback, order_id)
    else:
        await callback.message.reply("❌ خطا در تغییر وضعیت.")


async def callback_order_tracking(callback: CallbackQuery, order_id: int):
    """Start tracking code entry flow."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _order_states[chat_id] = {"step": "awaiting_tracking", "data": {"order_id": order_id}}

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data=f"ord:view:{order_id}")
    ]])
    await callback.message.edit(
        "🚚 ثبت کد رهگیری\n\n"
        "کد رهگیری پستی را وارد کنید:",
        components=cancel_kb
    )


async def callback_new_order(callback: CallbackQuery):
    """Start new order creation flow."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _order_states[chat_id] = {
        "step": "searching_customer",
        "data": {"items": [], "selected_products": {}}
    }

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="menu:orders")
    ]])
    await callback.message.edit(
        "🛒 سفارش جدید\n\n"
        "مرحله ۱: نام یا شماره مشتری را جستجو کنید:\n"
        "(یا Chat ID مستقیم وارد کنید)",
        components=cancel_kb
    )


async def callback_order_product_select(callback: CallbackQuery, product_id: int):
    """Add product to order."""
    chat_id = callback.message.chat.id
    state = _order_states.get(chat_id)
    if not state or state["step"] != "selecting_products":
        return

    # Add product to selected list
    selected = state["data"].get("selected_products", {})
    if str(product_id) in selected:
        selected[str(product_id)]["quantity"] += 1
    else:
        from app.database.crud import get_product_by_id
        product = await get_product_by_id(product_id)
        if product:
            selected[str(product_id)] = {
                "product_id": product_id,
                "sku": product.sku,
                "name": product.description[:30],
                "quantity": 1,
                "sold_price": product.base_sell_price,  # Default sell price
                "buy_price": product.buy_price,  # Save COGS
            }

    state["data"]["selected_products"] = selected
    _order_states[chat_id] = state

    count = sum(v["quantity"] for v in selected.values())
    
    from app.database.crud import get_all_products
    from app.bot.keyboards.inline import order_product_select_keyboard
    products = await get_all_products(active_only=True, per_page=50)
    
    user_name = state["data"].get("user_name", "مشتری")
    await callback.message.edit(
        f"✅ مشتری: {user_name}\n\n"
        "مرحله ۲: محصولات را انتخاب کنید:\n"
        f"🛒 در سبد خرید: {to_persian_digits(str(count))} محصول",
        components=order_product_select_keyboard(products)
    )


async def callback_order_items_done(callback: CallbackQuery):
    """Finish product selection, move to pricing."""
    chat_id = callback.message.chat.id
    state = _order_states.get(chat_id)
    if not state or state["step"] != "selecting_products":
        return

    selected = state["data"].get("selected_products", {})
    if not selected:
        await callback.message.reply("⚠️ حداقل یک محصول انتخاب کنید.")
        return

    state["step"] = "awaiting_shipping"
    _order_states[chat_id] = state

    items_text = "\n".join(
        f"• [{v['sku']}] ×{to_persian_digits(str(v['quantity']))} — {format_price(v['sold_price'])}"
        for v in selected.values()
    )

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="menu:orders")
    ]])
    await callback.message.edit(
        f"✅ محصولات انتخاب شدند:\n{items_text}\n\n"
        "هزینه ارسال را به تومان وارد کنید:\n(برای بدون هزینه: 0)",
        components=cancel_kb
    )


async def handle_order_message(message: Message) -> bool:
    """Handle messages for order FSM. Returns True if consumed."""
    chat_id = message.chat.id
    state = _order_states.get(chat_id)
    if not state:
        return False

    step = state["step"]
    text = message.content.strip() if message.content else ""

    if step == "searching_customer":
        # Try as chat_id first, then search by name
        try:
            customer_chat_id = int(text)
            user = await get_or_create_user(customer_chat_id, f"مشتری {customer_chat_id}")
        except ValueError:
            users = await search_users(text)
            if not users:
                await message.reply("⚠️ مشتری‌ای با این مشخصات یافت نشد. Chat ID یا نام وارد کنید:")
                return True
            if len(users) == 1:
                user = users[0]
            else:
                # Show selection
                from bale import InlineKeyboardButton
                from app.bot.keyboards.inline import build_kb
                buttons = [[
                    InlineKeyboardButton(f"{u.full_name} — {u.chat_id}", callback_data=f"ord:cust:{u.id}")
                ] for u in users[:5]]
                buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:orders")])
                await message.reply(
                    "چند مشتری یافت شد. انتخاب کنید:",
                    components=build_kb(buttons)
                )
                return True

        state["data"]["user_id"] = user.id
        state["data"]["user_name"] = user.full_name
        state["step"] = "selecting_products"
        _order_states[chat_id] = state

        # Show product search prompt
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        products = await get_all_products(active_only=True, per_page=20)
        kb = order_product_select_keyboard(products)
        await message.reply(
            f"✅ مشتری: {user.full_name}\n\n"
            "مرحله ۲: محصول را جستجو یا انتخاب کنید:\n"
            "💡 برای جستجو، کد یا نام محصول را تایپ کنید",
            components=kb
        )
        return True

    if step == "selecting_products" and text:
        # User typed something — treat as product search
        from app.services.product_service import search_products
        results = await search_products(text)
        if not results:
            from app.bot.keyboards.inline import build_kb
            from bale import InlineKeyboardButton
            cancel_kb = build_kb([[InlineKeyboardButton("❌ انصراف", callback_data="menu:orders")]])
            await message.reply(f"❌ محصولی با '{text}' یافت نشد. جستجوی دیگری امتحان کنید:", components=cancel_kb)
            return True
        await message.reply(
            f"🔍 نتایج جستجو برای '{text}':",
            components=order_product_select_keyboard(results[:15])
        )
        return True

    if step == "awaiting_shipping":
        try:
            shipping = int(text.replace(",", "").replace("،", ""))
            if shipping < 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ هزینه ارسال باید عدد غیر منفی باشد.")
            return True

        state["data"]["shipping_cost"] = shipping * 10  # To rials
        state["step"] = "awaiting_discount"
        _order_states[chat_id] = state

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:orders")]])
        await message.reply(
            f"✅ هزینه ارسال: {format_price(shipping * 10)}\n\n"
            "تخفیف را به تومان وارد کنید:\n(برای بدون تخفیف: 0)",
            components=cancel_kb
        )
        return True

    if step == "awaiting_discount":
        try:
            discount = int(text.replace(",", "").replace("،", ""))
            if discount < 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ تخفیف باید عدد غیر منفی باشد.")
            return True

        state["data"]["discount"] = discount * 10  # To rials
        state["step"] = "confirming_order"
        _order_states[chat_id] = state

        # Build summary
        selected = state["data"]["selected_products"]
        items = list(selected.values())
        total_items = sum(i["quantity"] * i["sold_price"] for i in items)
        total = total_items + state["data"]["shipping_cost"] - state["data"]["discount"]

        items_text = "\n".join(
            f"• [{i['sku']}] ×{to_persian_digits(str(i['quantity']))} — {format_price(i['quantity'] * i['sold_price'])}"
            for i in items
        )

        summary = (
            f"📋 خلاصه سفارش\n"
            "━━━━━━━━━━━━━━━\n"
            f"👤 مشتری: {state['data']['user_name']}\n\n"
            f"📦 اقلام:\n{items_text}\n\n"
            f"🚚 هزینه ارسال: {format_price(state['data']['shipping_cost'])}\n"
            f"🎁 تخفیف: {format_price(state['data']['discount'])}\n"
            "━━━━━━━━━━━━━━━\n"
            f"💰 مبلغ کل: {format_price(total)}\n\n"
            "✅ آیا سفارش را ثبت می‌کنید؟"
        )

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        confirm_kb = build_kb([
            [InlineKeyboardButton("✅ ثبت نهایی سفارش", callback_data="ord:confirm")],
            [
                InlineKeyboardButton("✏️ ویرایش", callback_data="ord:edit"),
                InlineKeyboardButton("❌ لغو", callback_data="menu:orders"),
            ]
        ])
        await message.reply(summary, components=confirm_kb)
        return True

    if step == "awaiting_tracking":
        order_id = state["data"]["order_id"]
        order = await ship_order(order_id, text)

        if order:
            state["step"] = "awaiting_actual_shipping_cost"
            _order_states[chat_id] = state
            
            from bale import InlineKeyboardButton
            from app.bot.keyboards.inline import build_kb
            skip_kb = build_kb([[
                InlineKeyboardButton("⏭ ثبت بدون هزینه (0)", callback_data=f"ord:ship_cost:skip:{order_id}")
            ]])
            
            await message.reply(
                f"✅ کد رهگیری `{text}` ثبت شد.\n"
                f"وضعیت سفارش به ارسال شده تغییر یافت.\n\n"
                f"لطفاً مبلغی که در اداره پست برای ارسال این سفارش پرداخت کردید را به تومان وارد کنید:",
                components=skip_kb
            )
        else:
            del _order_states[chat_id]
            await message.reply("❌ خطا در ثبت کد رهگیری.")
        return True

    if step == "awaiting_actual_shipping_cost":
        order_id = state["data"]["order_id"]
        try:
            cost = int(text.replace(",", "").replace("،", ""))
            if cost < 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ مبلغ باید یک عدد معتبر باشد.")
            return True
            
        from app.database.crud import update_order_status
        await update_order_status(order_id, "SHIPPED", shipping_cost=cost * 10)  # Convert to Rials
        del _order_states[chat_id]
        
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        back_kb = build_kb([[
            InlineKeyboardButton("🔙 مشاهده سفارش", callback_data=f"ord:view:{order_id}")
        ]])
        await message.reply(
            f"✅ هزینه پست واقعی {format_price(cost * 10)} برای سفارش ثبت شد.",
            components=back_kb
        )
        return True

    if step == "awaiting_bulk_track":
        from app.services.logistics_service import process_bulk_tracking_codes
        
        await message.reply("در حال پردازش... ⏳")
        result = await process_bulk_tracking_codes(text)
        
        del _order_states[chat_id]
        
        msg = (
            f"✅ با موفقیت: {result['success']}\n"
            f"❌ ناموفق: {result['failed']}\n"
        )
        if result['errors']:
            msg += "\nخطاها:\n" + "\n".join(result['errors'][:10])
            
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به سفارشات", callback_data="menu:orders")]])
        
        await message.reply(msg, components=back_kb)
        return True

    return False


async def callback_order_confirm(callback: CallbackQuery):
    """Confirm order creation."""
    chat_id = callback.message.chat.id
    state = _order_states.get(chat_id)
    if not state or state["step"] != "confirming_order":
        return

    data = state["data"]
    items = [
        {
            "product_id": v["product_id"],
            "quantity": v["quantity"],
            "sold_price": v["sold_price"],
            "buy_price": v.get("buy_price", 0),
        }
        for v in data["selected_products"].values()
    ]

    order = await create_new_order(
        user_id=data["user_id"],
        items=items,
        shipping_cost=data["shipping_cost"],
        discount=data["discount"],
    )

    del _order_states[chat_id]

    if not order:
        await callback.message.edit(
            "❌ خطا در ثبت سفارش. موجودی کافی نیست یا خطای دیگری رخ داده.",
            components=orders_menu_keyboard()
        )
        return

    # Generate payment message for the customer
    payment_msg = await get_payment_message(order)

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    view_kb = build_kb([[
        InlineKeyboardButton("🔍 مشاهده سفارش", callback_data=f"ord:view:{order.id}")
    ]])

    await callback.message.edit(
        f"✅ سفارش #{to_persian_digits(str(order.id).zfill(4))} ثبت شد!\n\n"
        f"پیام زیر برای مشتری ارسال می‌شود:\n\n{payment_msg}",
        components=view_kb
    )


async def callback_order_edit(callback: CallbackQuery):
    """Handle editing an order before confirmation (goes back to product selection)."""
    chat_id = callback.message.chat.id
    state = _order_states.get(chat_id)
    if not state or state["step"] != "confirming_order":
        return

    # Keep user selection, just clear shipping and discount and go back to product selection
    state["data"].pop("shipping_cost", None)
    state["data"].pop("discount", None)
    state["step"] = "selecting_products"
    
    from app.database.crud import get_all_products
    from app.bot.keyboards.inline import order_product_select_keyboard
    products = await get_all_products(active_only=True, per_page=20)
    
    selected_count = sum(v["quantity"] for v in state["data"].get("selected_products", {}).values())
    
    await callback.message.edit(
        f"✏️ ویرایش سفارش\nمشتری: {state['data']['user_name']}\n\n"
        f"🛒 در سبد خرید: {to_persian_digits(str(selected_count))} محصول\n"
        "محصول را جستجو یا انتخاب کنید:",
        components=order_product_select_keyboard(products)
    )


async def callback_order_ship_cost_skip(callback: CallbackQuery, order_id: int):
    """Skip actual shipping cost."""
    chat_id = callback.message.chat.id
    state = _order_states.get(chat_id)
    if not state or state["step"] != "awaiting_actual_shipping_cost":
        return
        
    from app.database.crud import update_order_status
    await update_order_status(order_id, "SHIPPED", shipping_cost=0)
    del _order_states[chat_id]
    
    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    back_kb = build_kb([[
        InlineKeyboardButton("🔙 مشاهده سفارش", callback_data=f"ord:view:{order_id}")
    ]])
    await callback.message.edit(
        f"✅ هزینه پست واقعی 0 برای سفارش ثبت شد.",
        components=back_kb
    )


def get_order_state(chat_id: int) -> dict | None:
    return _order_states.get(chat_id)


def clear_order_state(chat_id: int):
    _order_states.pop(chat_id, None)

async def callback_order_export(callback: CallbackQuery):
    """Export orders to CSV."""
    chat_id = callback.message.chat.id
    from app.services.logistics_service import export_paid_orders_csv
    from bale import InputFile
    
    await callback.message.edit("در حال تهیه خروجی... ⏳")
    
    csv_bytes = await export_paid_orders_csv()
    if not csv_bytes:
        await callback.message.reply("هیچ سفارشی یافت نشد.")
        return
        
    file = InputFile(csv_bytes, file_name="orders_export.csv")
    await callback.message.reply(
        "📥 خروجی سفارشات (پرداخت شده و دپو):",
        file=file
    )
    
async def callback_order_bulk_track(callback: CallbackQuery):
    """Start bulk tracking code registration."""
    chat_id = callback.message.chat.id
    _order_states[chat_id] = {"step": "awaiting_bulk_track", "data": {}}
    
    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:orders")]])
    
    await callback.message.edit(
        "🚚 ثبت گروهی بارکد پستی\n\n"
        "لیست سفارشات و بارکدها را در هر خط به فرمت زیر وارد کنید:\n"
        "آیدی سفارش : بارکد\n\n"
        "مثال:\n"
        "12 : 12345678901234567890\n"
        "15 : 09876543210987654321",
        components=cancel_kb
    )
