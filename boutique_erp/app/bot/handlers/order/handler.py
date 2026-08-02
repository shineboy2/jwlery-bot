import logging
from bale import Message, CallbackQuery, InlineKeyboardButton, InputFile
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import order_repo, user_repo, product_repo
from app.services.order_service import (
    create_new_order, confirm_payment, ship_order, cancel_order, get_payment_message
)
from app.services.product_service import search_products
from app.services.logistics_service import process_bulk_tracking_codes, export_paid_orders_csv
from app.bot.handlers.order.keyboards import (
    orders_menu_keyboard, order_detail_keyboard, order_product_select_keyboard, build_kb
)
from app.utils.formatters import to_persian_digits, format_price
from app.bot.handlers.order.renderers import format_order_summary, format_order_status

logger = logging.getLogger(__name__)

class OrderHandler(BaseHandler):
    HANDLER_NAME = "order"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_exact("menu:orders", self.menu)
        router.register_exact("ord:new", self.new_order)
        router.register_exact("ord:export", self.export)
        router.register_exact("ord:bulk_track", self.bulk_track)
        router.register_pattern(r"^ord:filter:(ALL|PENDING_PAYMENT|PAID|PAID_HELD|SHIPPED|DELIVERED)$", self.filter_orders)
        router.register_pattern(r"^ord:view:(\d+)$", self.view)
        router.register_pattern(r"^ord:status:(\d+):(PAID|PAID_HELD|CANCELLED|DELIVERED)$", self.status_change)
        router.register_pattern(r"^ord:track:(\d+)$", self.track)
        router.register_pattern(r"^ord:ship_cost:skip:(\d+)$", self.ship_cost_skip)
        
        router.register_pattern(r"^ord:cust:(\d+)$", self.select_customer)
        router.register_pattern(r"^ord:prod:(\d+)$", self.product_select)
        router.register_exact("ord:items_done", self.items_done)
        router.register_exact("ord:confirm", self.confirm)
        router.register_exact("ord:edit", self.edit_order)

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        step = state.step
        text = message.content.strip() if message.content else ""

        if step == "searching_customer":
            try:
                customer_chat_id = int(text)
                async with self.session_factory() as session:
                    user = await user_repo.get_or_create_user(session, customer_chat_id, f"مشتری {customer_chat_id}")
            except ValueError:
                async with self.session_factory() as session:
                    users = await user_repo.search_users(session, text)
                if not users:
                    await message.reply("⚠️ مشتری‌ای با این مشخصات یافت نشد. Chat ID یا نام وارد کنید:")
                    return True
                if len(users) == 1:
                    user = users[0]
                else:
                    buttons = [[
                        InlineKeyboardButton(f"{u.full_name} — {u.chat_id}", callback_data=f"ord:cust:{u.id}")
                    ] for u in users[:5]]
                    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:orders")])
                    await message.reply(
                        "چند مشتری یافت شد. انتخاب کنید:",
                        components=build_kb(buttons)
                    )
                    return True

            self.conversations.advance(
                chat_id, self.HANDLER_NAME, "selecting_products",
                user_id=user.id, user_name=user.full_name, items=[], selected_products={}
            )

            async with self.session_factory() as session:
                products = await product_repo.get_all_products(session, active_only=True, per_page=20)
            await message.reply(
                f"✅ مشتری: {user.full_name}\n\n"
                "مرحله ۲: محصول را جستجو یا انتخاب کنید:\n"
                "💡 برای جستجو، کد یا نام محصول را تایپ کنید",
                components=order_product_select_keyboard(products)
            )
            return True

        if step == "selecting_products" and text:
            async with self.session_factory() as session:
                results = await search_products(session, text)
            if not results:
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
                if shipping < 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ هزینه ارسال باید عدد غیر منفی باشد.")
                return True

            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_discount", shipping_cost=shipping * 10)

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
                if discount < 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ تخفیف باید عدد غیر منفی باشد.")
                return True

            self.conversations.advance(chat_id, self.HANDLER_NAME, "confirming_order", discount=discount * 10)
            
            state = self.conversations.get_active(chat_id)
            selected = state.data["selected_products"]
            items = list(selected.values())
            total_items = sum(i["quantity"] * i["sold_price"] for i in items)
            total = total_items + state.data["shipping_cost"] - state.data["discount"]

            items_text = "\n".join(
                f"• [{i['sku']}] ×{to_persian_digits(str(i['quantity']))} — {format_price(i['quantity'] * i['sold_price'])}"
                for i in items
            )

            summary = (
                f"📋 خلاصه سفارش\n"
                "━━━━━━━━━━━━━━━\n"
                f"👤 مشتری: {state.data['user_name']}\n\n"
                f"📦 اقلام:\n{items_text}\n\n"
                f"🚚 هزینه ارسال: {format_price(state.data['shipping_cost'])}\n"
                f"🎁 تخفیف: {format_price(state.data['discount'])}\n"
                "━━━━━━━━━━━━━━━\n"
                f"💰 مبلغ کل: {format_price(total)}\n\n"
                "✅ آیا سفارش را ثبت می‌کنید؟"
            )

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
            order_id = state.data["order_id"]
            async with self.session_factory() as session:
                order = await ship_order(session, order_id, text)

            if order:
                self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_actual_shipping_cost")
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
                self.conversations.end(chat_id, self.HANDLER_NAME)
                await message.reply("❌ خطا در ثبت کد رهگیری.")
            return True

        if step == "awaiting_actual_shipping_cost":
            order_id = state.data["order_id"]
            try:
                cost = int(text.replace(",", "").replace("،", ""))
                if cost < 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ مبلغ باید یک عدد معتبر باشد.")
                return True
                
            async with self.session_factory() as session:
                await order_repo.update_order_status(session, order_id, "SHIPPED", shipping_cost=cost * 10)
            self.conversations.end(chat_id, self.HANDLER_NAME)
            
            back_kb = build_kb([[
                InlineKeyboardButton("🔙 مشاهده سفارش", callback_data=f"ord:view:{order_id}")
            ]])
            await message.reply(
                f"✅ هزینه پست واقعی {format_price(cost * 10)} برای سفارش ثبت شد.",
                components=back_kb
            )
            return True

        if step == "awaiting_bulk_track":
            await message.reply("در حال پردازش... ⏳")
            async with self.session_factory() as session:
                result = await process_bulk_tracking_codes(session, text)
            
            self.conversations.end(chat_id, self.HANDLER_NAME)
            
            msg = (
                f"✅ با موفقیت: {result['success']}\n"
                f"❌ ناموفق: {result['failed']}\n"
            )
            if result['errors']:
                msg += "\nخطاها:\n" + "\n".join(result['errors'][:10])
                
            back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت به سفارشات", callback_data="menu:orders")]])
            
            await message.reply(msg, components=back_kb)
            return True

        return False

    async def menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        
        self.conversations.end(chat_id, self.HANDLER_NAME)

        await callback.message.edit(
            "🛒 مدیریت سفارشات\nاز منوی زیر انتخاب کنید:",
            components=orders_menu_keyboard()
        )

    async def filter_orders(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        status = match.group(1)

        async with ctx.session_factory() as session:
            if status == "ALL":
                orders = await order_repo.get_recent_orders(session, limit=20)
                title = "📋 آخرین سفارشات"
            else:
                orders = await order_repo.get_orders_by_status(session, status)
                title = f"🛒 سفارشات — {format_order_status(status)}"

        if not orders:
            back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:orders")]])
            await callback.message.edit(f"هیچ سفارشی یافت نشد.", components=back_kb)
            return

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

    async def view(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        order_id = int(match.group(1))

        async with ctx.session_factory() as session:
            order = await order_repo.get_order_by_id(session, order_id)
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

        await callback.message.edit(text, components=order_detail_keyboard(order.id, order.status))

    async def status_change(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        order_id = int(match.group(1))
        new_status = match.group(2)

        async with ctx.session_factory() as session:
            if new_status == "PAID":
                order = await confirm_payment(session, order_id)
                msg = "✅ پرداخت تأیید شد. سفارش در لیست ارسال قرار گرفت."
            elif new_status == "PAID_HELD":
                order = await order_repo.get_order_by_id(session, order_id)
                if order and order.status == "PENDING_PAYMENT":
                    order = await confirm_payment(session, order_id)
                order = await order_repo.update_order_status(session, order_id, "PAID_HELD")
                msg = "📥 پرداخت تأیید شد و محصول دپو شد."
            elif new_status == "CANCELLED":
                order = await cancel_order(session, order_id)
                msg = "❌ سفارش لغو شد. موجودی آزاد شد."
            elif new_status == "DELIVERED":
                order = await order_repo.update_order_status(session, order_id, new_status)
                msg = "📦 سفارش تحویل داده شد."
            else:
                return

        if order:
            await callback.message.reply(msg)
            await self.view(callback, ctx, match)
        else:
            await callback.message.reply("❌ خطا در تغییر وضعیت.")

    async def track(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        order_id = int(match.group(1))

        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_tracking", {"order_id": order_id})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"ord:view:{order_id}")]])
        await callback.message.edit(
            "🚚 ثبت کد رهگیری\n\nکد رهگیری پستی را وارد کنید:",
            components=cancel_kb
        )

    async def new_order(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        self.conversations.start(chat_id, self.HANDLER_NAME, "searching_customer", {"items": [], "selected_products": {}})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:orders")]])
        await callback.message.edit(
            "🛒 سفارش جدید\n\n"
            "مرحله ۱: نام یا شماره مشتری را جستجو کنید:\n"
            "(یا Chat ID مستقیم وارد کنید)",
            components=cancel_kb
        )

    async def select_customer(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        user_id = int(match.group(1))
        
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "searching_customer": return

        async with ctx.session_factory() as session:
            user = await user_repo.get_user_by_id(session, user_id)
        if not user: return

        self.conversations.advance(
            chat_id, self.HANDLER_NAME, "selecting_products",
            user_id=user.id, user_name=user.full_name, items=[], selected_products={}
        )

        async with ctx.session_factory() as session:
            products = await product_repo.get_all_products(session, active_only=True, per_page=20)
        await callback.message.edit(
            f"✅ مشتری: {user.full_name}\n\n"
            "مرحله ۲: محصول را جستجو یا انتخاب کنید:\n"
            "💡 برای جستجو، کد یا نام محصول را تایپ کنید",
            components=order_product_select_keyboard(products)
        )

    async def product_select(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        product_id = int(match.group(1))
        
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "selecting_products": return

        selected = state.data.get("selected_products", {})
        if str(product_id) in selected:
            selected[str(product_id)]["quantity"] += 1
        else:
            async with ctx.session_factory() as session:
                product = await product_repo.get_product_by_id(session, product_id)
            if product:
                selected[str(product_id)] = {
                    "product_id": product_id,
                    "sku": product.sku,
                    "name": product.description[:30],
                    "quantity": 1,
                    "sold_price": product.base_sell_price,
                    "buy_price": product.buy_price,
                }

        self.conversations.advance(chat_id, self.HANDLER_NAME, "selecting_products", selected_products=selected)
        count = sum(v["quantity"] for v in selected.values())
        async with ctx.session_factory() as session:
            products = await product_repo.get_all_products(session, active_only=True, per_page=50)
        user_name = state.data.get("user_name", "مشتری")
        
        await callback.message.edit(
            f"✅ مشتری: {user_name}\n\n"
            "مرحله ۲: محصولات را انتخاب کنید:\n"
            f"🛒 در سبد خرید: {to_persian_digits(str(count))} محصول",
            components=order_product_select_keyboard(products)
        )

    async def items_done(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "selecting_products": return

        selected = state.data.get("selected_products", {})
        if not selected:
            await callback.message.reply("⚠️ حداقل یک محصول انتخاب کنید.")
            return

        self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_shipping")
        items_text = "\n".join(
            f"• [{v['sku']}] ×{to_persian_digits(str(v['quantity']))} — {format_price(v['sold_price'])}"
            for v in selected.values()
        )

        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:orders")]])
        await callback.message.edit(
            f"✅ محصولات انتخاب شدند:\n{items_text}\n\n"
            "هزینه ارسال را به تومان وارد کنید:\n(برای بدون هزینه: 0)",
            components=cancel_kb
        )

    async def confirm(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "confirming_order": return

        data = state.data
        items = [
            {
                "product_id": v["product_id"],
                "quantity": v["quantity"],
                "sold_price": v["sold_price"],
                "buy_price": v.get("buy_price", 0),
            }
            for v in data["selected_products"].values()
        ]

        async with ctx.session_factory() as session:
            order = await create_new_order(
                session=session,
                user_id=data["user_id"],
                items=items,
                shipping_cost=data["shipping_cost"],
                discount=data["discount"],
            )

        self.conversations.end(chat_id, self.HANDLER_NAME)

        if not order:
            await callback.message.edit(
                "❌ خطا در ثبت سفارش. موجودی کافی نیست یا خطای دیگری رخ داده.",
                components=orders_menu_keyboard()
            )
            return

        payment_msg = await get_payment_message(order)
        view_kb = build_kb([[InlineKeyboardButton("🔍 مشاهده سفارش", callback_data=f"ord:view:{order.id}")]])

        await callback.message.edit(
            f"✅ سفارش #{to_persian_digits(str(order.id).zfill(4))} ثبت شد!\n\n"
            f"پیام زیر برای مشتری ارسال می‌شود:\n\n{payment_msg}",
            components=view_kb
        )

    async def edit_order(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "confirming_order": return

        data = state.data
        data.pop("shipping_cost", None)
        data.pop("discount", None)
        self.conversations.advance(chat_id, self.HANDLER_NAME, "selecting_products", **data)
        
        async with ctx.session_factory() as session:
            products = await product_repo.get_all_products(session, active_only=True, per_page=20)
        selected_count = sum(v["quantity"] for v in data.get("selected_products", {}).values())
        
        await callback.message.edit(
            f"✏️ ویرایش سفارش\nمشتری: {data['user_name']}\n\n"
            f"🛒 در سبد خرید: {to_persian_digits(str(selected_count))} محصول\n"
            "محصول را جستجو یا انتخاب کنید:",
            components=order_product_select_keyboard(products)
        )

    async def ship_cost_skip(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        order_id = int(match.group(1))
        
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_actual_shipping_cost": return
            
        async with ctx.session_factory() as session:
            await order_repo.update_order_status(session, order_id, "SHIPPED", shipping_cost=0)
        self.conversations.end(chat_id, self.HANDLER_NAME)
        
        back_kb = build_kb([[InlineKeyboardButton("🔙 مشاهده سفارش", callback_data=f"ord:view:{order_id}")]])
        await callback.message.edit(
            f"✅ هزینه پست واقعی 0 برای سفارش ثبت شد.",
            components=back_kb
        )

    async def export(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        
        await callback.message.edit("در حال تهیه خروجی... ⏳")
        async with ctx.session_factory() as session:
            csv_bytes = await export_paid_orders_csv(session)
        
        if not csv_bytes:
            await callback.message.reply("هیچ سفارشی یافت نشد.")
            return
            
        file = InputFile(csv_bytes, file_name="orders_export.csv")
        await callback.message.reply("📥 خروجی سفارشات (پرداخت شده و دپو):", file=file)

    async def bulk_track(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        
        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_bulk_track")
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
