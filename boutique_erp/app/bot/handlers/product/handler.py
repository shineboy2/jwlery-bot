import logging
import math
from bale import Message, CallbackQuery, InlineKeyboardButton, InputFile
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import category_repo, product_repo, config_repo
from app.services.product_service import register_product, search_products
from app.services.ai_service import generate_product_description
from app.services.channel_service import publish_to_channel, update_channel_post, remove_channel_post
from app.database.models import ScheduledPost
from app.bot.handlers.product.keyboards import (
    products_menu_keyboard, product_list_keyboard, product_detail_keyboard,
    category_select_keyboard, done_uploading_keyboard, confirm_product_keyboard,
    publish_after_register_keyboard, product_edit_keyboard, ai_generate_keyboard,
    preview_ai_keyboard, build_kb
)
from app.utils.formatters import format_price, to_persian_digits

logger = logging.getLogger(__name__)

PER_PAGE = 5
_EDIT_FIELD_LABELS = {
    "description": "توضیحات/کپشن",
    "buy_price": "قیمت خرید (تومان)",
    "sell_price": "قیمت فروش (تومان)",
    "supplier": "نام تأمین‌کننده",
}

class ProductHandler(BaseHandler):
    HANDLER_NAME = "product"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_exact("menu:products", self.menu)
        router.register_exact("prod:add", self.add)
        router.register_pattern(r"^prod:cat_select:(\d+)$", self.category_select)
        router.register_exact("prod:images_done", self.images_done)
        router.register_exact("prod:cancel", self.cancel)
        router.register_exact("prod:confirm", self.confirm)
        
        router.register_exact("prod:ai_gen", self.ai_gen)
        router.register_exact("prod:ai_edit", self.ai_edit)
        router.register_exact("prod:ai_regen", self.ai_regen)
        router.register_exact("prod:ai_queue", self.ai_queue)
        router.register_exact("prod:ai_publish", self.ai_publish)
        router.register_exact("prod:ai_manual", self.ai_manual)
        router.register_exact("prod:ai_skip", self.ai_skip)
        
        router.register_pattern(r"^prod:list:page:(\d+)$", self.list_products)
        router.register_pattern(r"^prod:view:(\d+)$", self.view)
        router.register_pattern(r"^prod:toggle:(\d+)$", self.toggle)
        router.register_pattern(r"^prod:stock:(\d+)$", self.stock)
        router.register_exact("prod:search", self.search)
        
        router.register_pattern(r"^prod:edit:(\d+)$", self.edit_menu)
        router.register_pattern(r"^prod:edit:([a-z_]+):(\d+)$", self.edit_field)
        
        # Channel Routes
        router.register_pattern(r"^ch:publish:(\d+)$", self.channel_publish)
        router.register_pattern(r"^ch:pub_direct:(\d+)$", self.channel_publish_direct)
        router.register_pattern(r"^ch:pub_type:(\d+):([a-zA-Z_]+)$", self.channel_publish_type)
        router.register_pattern(r"^ch:update:(\d+)$", self.channel_update)
        router.register_pattern(r"^ch:remove:(\d+)$", self.channel_remove)

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        step = state.step
        text = message.content.strip() if message.content else ""

        if step == "awaiting_sku":
            if not text or len(text) < 2:
                await message.reply("⚠️ کد محصول حداقل باید ۲ کاراکتر باشد.")
                return True
                
            self.conversations.advance(chat_id, self.HANDLER_NAME, "uploading_images", sku=text.upper(), images=[])
            
            await message.reply(
                "✅ کد محصول ثبت شد.\n\n"
                "مرحله ۳/۹: عکس‌های محصول را ارسال کنید.\n"
                "می‌توانید چند عکس ارسال کنید.\n"
                "بعد از آخرین عکس دکمه ✅ را بزنید:",
                components=done_uploading_keyboard()
            )
            return True

        if step == "uploading_images" and message.photos:
            photo = message.photos[-1]
            images = state.data.get("images", [])
            images.append(photo.file_id)
            self.conversations.advance(chat_id, self.HANDLER_NAME, "uploading_images", images=images)
            count = len(images)
            await message.reply(
                f"✅ عکس {to_persian_digits(str(count))} دریافت شد. "
                "بیشتر ارسال کنید یا دکمه ✅ را بزنید.",
                components=done_uploading_keyboard()
            )
            return True

        if step == "awaiting_description":
            if len(text) < 5:
                await message.reply("⚠️ توضیحات باید حداقل ۵ کاراکتر باشد.")
                return True
            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_buy_price", description=text)

            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
            await message.reply(
                "✅ توضیحات ثبت شد.\n\n"
                "مرحله ۴/۸: قیمت خرید محصول را به تومان وارد کنید:\n"
                "مثال: 250000",
                components=cancel_kb
            )
            return True

        if step == "awaiting_buy_price":
            try:
                price = int(text.replace(",", "").replace("،", ""))
                if price <= 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ قیمت باید یک عدد مثبت باشد. مثال: 250000")
                return True

            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_sell_price", buy_price=price * 10)

            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
            await message.reply(
                f"✅ قیمت خرید: {format_price(price * 10)}\n\n"
                "مرحله ۵/۸: قیمت فروش محصول را به تومان وارد کنید:",
                components=cancel_kb
            )
            return True

        if step == "awaiting_sell_price":
            try:
                price = int(text.replace(",", "").replace("،", ""))
                if price <= 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ قیمت باید یک عدد مثبت باشد.")
                return True

            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_stock", base_sell_price=price * 10)

            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
            await message.reply(
                f"✅ قیمت فروش: {format_price(price * 10)}\n\n"
                "مرحله ۶/۸: تعداد موجودی اولیه را وارد کنید:",
                components=cancel_kb
            )
            return True

        if step == "awaiting_stock":
            try:
                quantity = int(text)
                if quantity < 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ موجودی باید یک عدد صحیح غیر منفی باشد.")
                return True

            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_supplier", stock_quantity=quantity)

            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
            await message.reply(
                f"✅ موجودی: {to_persian_digits(str(quantity))} عدد\n\n"
                "مرحله ۷/۸: نام تأمین‌کننده را وارد کنید:\n"
                "(اختیاری — برای عبور 'رد' بنویسید)",
                components=cancel_kb
            )
            return True

        if step == "awaiting_supplier":
            supplier = None if text.lower() in ("رد", "skip", "-", "") else text
            
            async with ctx.session_factory() as session:
                category = await category_repo.get_category_by_id(session, state.data["category_id"])
            attributes = category.attributes if category and category.attributes else []
            
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
            
            if not attributes:
                self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_ai_generation", supplier_name=supplier)
                await message.reply(
                    "✅ نام تأمین‌کننده ثبت شد.\n\n"
                    "آیا می‌خواهید توضیحات محصول را با استفاده از هوش مصنوعی (Gemini) جذاب‌تر کنید؟",
                    components=ai_generate_keyboard()
                )
                return True
            else:
                pending_attributes = list(attributes)
                first_attr = pending_attributes[0]
                self.conversations.advance(
                    chat_id, self.HANDLER_NAME, "awaiting_dynamic_attribute", 
                    supplier_name=supplier, pending_attributes=pending_attributes, dynamic_attributes={}
                )
                await message.reply(
                    f"✅ نام تأمین‌کننده ثبت شد.\n\n"
                    f"مرحله ۸: لطفاً مقدار ویژگی '{first_attr}' را وارد کنید:\n"
                    "(اختیاری — برای عبور 'رد' بنویسید)",
                    components=cancel_kb
                )
                return True

        if step == "awaiting_dynamic_attribute":
            pending = state.data["pending_attributes"]
            current_attr = pending[0]
            dynamic_attributes = state.data["dynamic_attributes"]
            
            if text.lower() not in ("رد", "skip", "-", ""):
                dynamic_attributes[current_attr] = text.strip()
                
            pending.pop(0)
            
            if pending:
                self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_dynamic_attribute", pending_attributes=pending, dynamic_attributes=dynamic_attributes)
                cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
                next_attr = pending[0]
                await message.reply(
                    f"✅ ثبت شد.\nلطفاً مقدار ویژگی '{next_attr}' را وارد کنید:\n"
                    "(اختیاری — برای عبور 'رد' بنویسید)",
                    components=cancel_kb
                )
                return True
            else:
                self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_ai_generation", pending_attributes=[], dynamic_attributes=dynamic_attributes)
                await message.reply(
                    "✅ ویژگی‌ها ثبت شدند.\n\n"
                    "آیا می‌خواهید توضیحات محصول را با استفاده از هوش مصنوعی (Gemini) جذاب‌تر کنید؟",
                    components=ai_generate_keyboard()
                )
                return True

        if step == "awaiting_description_confirmation":
            desc = text.strip()
            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_description_confirmation", description=desc)
            await message.reply("✅ توضیحات ویرایش شده ذخیره شد.")
            
            images = state.data.get("images", [])
            try:
                if not images:
                    await message.reply(desc)
                elif len(images) == 1:
                    await self.bot.send_photo(chat_id=chat_id, photo=InputFile(images[0]), caption=desc)
                else:
                    await self.bot.send_photo(chat_id=chat_id, photo=InputFile(images[0]), caption=desc)
                    for file_id in images[1:]:
                        try:
                            await self.bot.send_photo(chat_id=chat_id, photo=InputFile(file_id))
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error sending preview: {e}")
                await message.reply(f"متن پیش‌نمایش:\n{desc}")

            await message.reply(
                "انتخاب کنید:",
                components=preview_ai_keyboard()
            )
            return True

        if step == "update_stock":
            try:
                quantity = int(text)
                if quantity < 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ موجودی باید یک عدد صحیح غیر منفی باشد.")
                return True

            product_id = state.data["product_id"]
            async with ctx.session_factory() as session:
                await product_repo.update_product(session, product_id, stock_quantity=quantity)
            self.conversations.end(chat_id, self.HANDLER_NAME)

            back_kb = build_kb([[
                InlineKeyboardButton("🔙 بازگشت به محصول", callback_data=f"prod:view:{product_id}")
            ]])
            await message.reply(
                f"✅ موجودی به {to_persian_digits(str(quantity))} عدد بروزرسانی شد.",
                components=back_kb
            )
            return True

        if step == "searching":
            if len(text) < 2:
                await message.reply("⚠️ عبارت جستجو باید حداقل ۲ کاراکتر باشد.")
                return True

            self.conversations.end(chat_id, self.HANDLER_NAME)
            products = await search_products(text)

            if not products:
                back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:products")]])
                await message.reply(f"🔍 نتیجه‌ای برای '{text}' یافت نشد.", components=back_kb)
                return True

            result_text = f"🔍 نتایج جستجو برای '{text}':\n\n"
            for prod in products[:10]:
                status = "✅" if prod.status == "ACTIVE" else "❌"
                result_text += f"{status} [{prod.sku}] {prod.description[:40]}\n"
                result_text += f"   💰 {format_price(prod.base_sell_price)} | 📦 {to_persian_digits(str(prod.stock_quantity))}\n\n"

            back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu:products")]])
            await message.reply(result_text, components=back_kb)
            return True

        if step.startswith("edit_"):
            return await self._handle_product_edit_message(message, state, chat_id)

        return False

    async def _handle_product_edit_message(self, message: Message, state, chat_id: int) -> bool:
        step = state.step
        text = message.content.strip() if message.content else ""
        product_id = state.data["product_id"]

        if step == "edit_description":
            if len(text) < 3:
                await message.reply("⚠️ توضیحات باید حداقل ۳ کاراکتر باشد.")
                return True
            async with ctx.session_factory() as session:
                await product_repo.update_product(session, product_id, description=text)
            self.conversations.end(chat_id, self.HANDLER_NAME)
            await message.reply(f"✅ توضیحات بروزرسانی شد.", components=product_edit_keyboard(product_id))
            return True

        if step == "edit_buy_price":
            try:
                price = int(text.replace(",", "").replace("،", ""))
                if price <= 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ قیمت باید یک عدد مثبت باشد.")
                return True
            async with ctx.session_factory() as session:
                await product_repo.update_product(session, product_id, buy_price=price * 10)
            self.conversations.end(chat_id, self.HANDLER_NAME)
            await message.reply(f"✅ قیمت خرید به {format_price(price * 10)} بروزرسانی شد.", components=product_edit_keyboard(product_id))
            return True

        if step == "edit_sell_price":
            try:
                price = int(text.replace(",", "").replace("،", ""))
                if price <= 0: raise ValueError
            except ValueError:
                await message.reply("⚠️ قیمت باید یک عدد مثبت باشد.")
                return True
            async with ctx.session_factory() as session:
                await product_repo.update_product(session, product_id, base_sell_price=price * 10)
            self.conversations.end(chat_id, self.HANDLER_NAME)
            await message.reply(f"✅ قیمت فروش به {format_price(price * 10)} بروزرسانی شد.", components=product_edit_keyboard(product_id))
            return True

        if step == "edit_supplier":
            supplier = None if text.lower() in ("رد", "skip", "-", "") else text
            async with ctx.session_factory() as session:
                await product_repo.update_product(session, product_id, supplier_name=supplier)
            self.conversations.end(chat_id, self.HANDLER_NAME)
            display = supplier or "(حذف شد)"
            await message.reply(f"✅ تأمین‌کننده به '{display}' بروزرسانی شد.", components=product_edit_keyboard(product_id))
            return True
            
        return False

    async def menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        
        self.conversations.end(chat_id, self.HANDLER_NAME)

        await callback.message.edit(
            "📦 مدیریت محصولات\nاز منوی زیر انتخاب کنید:",
            components=products_menu_keyboard()
        )

    async def add(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        async with ctx.session_factory() as session:
            categories = await category_repo.get_all_categories(session, active_only=True)
        if not categories:
            await callback.message.reply("⚠️ ابتدا باید دسته‌بندی ایجاد کنید.")
            return

        self.conversations.start(chat_id, self.HANDLER_NAME, "select_category", {"images": []})
        await callback.message.edit(
            "📦 ثبت محصول جدید\n\nمرحله ۱/۸: دسته‌بندی محصول را انتخاب کنید:",
            components=category_select_keyboard(categories)
        )

    async def category_select(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        cat_id = int(match.group(1))
        
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "select_category": return

        self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_sku", category_id=cat_id)
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
        await callback.message.edit(
            "📦 ثبت محصول جدید\n\n"
            "مرحله ۲/۹: لطفاً کد محصول (SKU) مورد نظر خود را وارد کنید:\n"
            "(به عنوان مثال: NK-101)",
            components=cancel_kb
        )

    async def images_done(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "uploading_images": return

        if not state.data.get("images"):
            await callback.message.reply("⚠️ حداقل یک عکس ارسال کنید.")
            return

        self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_description")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
        await callback.message.edit(
            f"✅ {to_persian_digits(str(len(state.data['images'])))} عکس دریافت شد.\n\n"
            "مرحله ۳/۸: توضیحات محصول را وارد کنید:\n"
            "مثال: گردنبند زنجیر طلایی ظریف با آویز قلب",
            components=cancel_kb
        )

    async def cancel(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        self.conversations.end(chat_id, self.HANDLER_NAME)
        await callback.message.edit("❌ ثبت محصول لغو شد.", components=products_menu_keyboard())

    async def send_product_confirmation(self, message: Message, state):
        data = state.data
        summary = (
            "📋 خلاصه محصول — مرحله نهایی\n"
            "━━━━━━━━━━━━━━━\n"
            f"📸 عکس‌ها: {to_persian_digits(str(len(data.get('images', []))))} عدد\n"
            f"📝 توضیحات: {data.get('description', '')}\n"
            f"💸 قیمت خرید: {format_price(data.get('buy_price', 0))}\n"
            f"💰 قیمت فروش: {format_price(data.get('base_sell_price', 0))}\n"
            f"📦 موجودی: {to_persian_digits(str(data.get('stock_quantity', 0)))} عدد\n"
        )
        if data.get("supplier_name"):
            summary += f"🏭 تأمین‌کننده: {data['supplier_name']}\n"
        
        attributes = data.get("dynamic_attributes")
        if attributes:
            attrs_str = " | ".join([f"{k}: {v}" for k, v in attributes.items()])
            summary += f"✨ ویژگی‌ها: {attrs_str}\n"

        summary += "\n✅ آیا تأیید می‌کنید؟"
        await message.reply(summary, components=confirm_product_keyboard())

    async def confirm(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "confirming": return

        data = state.data
        try:
            product = await register_product(
                sku=data["sku"],
                category_id=data["category_id"],
                description=data["description"],
                buy_price=data["buy_price"],
                base_sell_price=data["base_sell_price"],
                stock_quantity=data["stock_quantity"],
                image_file_ids=data.get("images", []),
                supplier_name=data.get("supplier_name"),
                dynamic_attributes=data.get("dynamic_attributes", {}),
            )
            self.conversations.end(chat_id, self.HANDLER_NAME)
            await callback.message.edit(
                f"✅ محصول با موفقیت ثبت شد!\n\n"
                f"🏷 کد: {product.sku}\n"
                f"📝 توضیحات: {product.description}\n"
                f"💰 قیمت فروش: {format_price(product.base_sell_price)}\n"
                f"📦 موجودی: {to_persian_digits(str(product.stock_quantity))} عدد\n\n"
                "آیا می‌خواهید این محصول را در کانال منتشر کنید؟",
                components=publish_after_register_keyboard(product.id)
            )
        except Exception as e:
            logger.error(f"Product registration failed: {e}")
            self.conversations.end(chat_id, self.HANDLER_NAME)
            await callback.message.edit(f"❌ خطا در ثبت محصول: {str(e)}", components=products_menu_keyboard())

    async def _register_product_from_state(self, chat_id: int, state):
        data = state.data
        try:
            product = await register_product(
                sku=data["sku"],
                category_id=data["category_id"],
                description=data["description"],
                buy_price=data["buy_price"],
                base_sell_price=data["base_sell_price"],
                stock_quantity=data["stock_quantity"],
                image_file_ids=data.get("images", []),
                supplier_name=data.get("supplier_name"),
                dynamic_attributes=data.get("dynamic_attributes", {}),
            )
            return product
        except Exception as e:
            logger.error(f"Product registration failed: {e}")
            return None

    async def ai_gen(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_ai_generation": return

        await callback.message.edit("در حال ارتباط با هوش مصنوعی... ⏳")
        data = state.data
        
        async with ctx.session_factory() as session:
            category = await category_repo.get_category_by_id(session, data["category_id"])
            cat_name = category.name if category else "نامشخص"
            prompt_template = await config_repo.get_ai_prompt_by_name(session, "product_description")
        
        ai_desc = await generate_product_description(
            title=data.get("description", data.get("sku", "")), 
            category=cat_name, 
            attributes=data.get("dynamic_attributes", {}),
            base_sell_price=data.get("base_sell_price"),
            stock_quantity=data.get("stock_quantity"),
            prompt_template=prompt_template
        )
        
        if ai_desc:
            self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_description_confirmation", description=ai_desc)
            
            images = data.get("images", [])
            try:
                if not images:
                    await callback.message.reply(ai_desc)
                elif len(images) == 1:
                    await self.bot.send_photo(chat_id=chat_id, photo=InputFile(images[0]), caption=ai_desc)
                else:
                    await self.bot.send_photo(chat_id=chat_id, photo=InputFile(images[0]), caption=ai_desc)
                    for file_id in images[1:]:
                        try:
                            await self.bot.send_photo(chat_id=chat_id, photo=InputFile(file_id))
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error sending preview: {e}")
                await callback.message.reply(f"متن پیش‌نمایش:\n{ai_desc}")

            await callback.message.reply(
                "انتخاب کنید:",
                components=preview_ai_keyboard()
            )
        else:
            await callback.message.reply("❌ خطا در تولید متن هوش مصنوعی. از همان توضیحات قبلی استفاده می‌شود.")
            self.conversations.advance(chat_id, self.HANDLER_NAME, "confirming")
            await self.send_product_confirmation(callback.message, self.conversations.get_active(chat_id))

    async def ai_edit(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_description_confirmation": return
        await callback.message.reply("✏️ لطفاً متن جدید و ویرایش‌شده را ارسال کنید:\n(متن ارسالی شما کاملاً جایگزین متن هوش مصنوعی خواهد شد)")

    async def ai_regen(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_description_confirmation": return
        self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_ai_generation")
        await self.ai_gen(callback, ctx)

    async def ai_queue(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_description_confirmation": return
        
        await callback.message.edit("در حال ثبت محصول و افزودن به صف... ⏳")
        product = await self._register_product_from_state(chat_id, state)
        if product:
            self.conversations.end(chat_id, self.HANDLER_NAME)
            
            async with ctx.session_factory() as session:
                images = state.data.get("images", [])
                images_str = ",".join(images) if images else None
                post = ScheduledPost(
                    product_id=product.id,
                    post_type="MEDIA_GROUP" if images_str and "," in images_str else "IMAGE" if images_str else "TEXT",
                    category=None,
                    content_text=product.description,
                    file_id=images_str,
                    status="QUEUED"
                )
                session.add(post)
                await session.commit()
                
            await callback.message.reply(
                f"✅ محصول با موفقیت ثبت شد و به صف انتشار اضافه گردید!",
                components=product_detail_keyboard(product.id, True, False)
            )
        else:
            await callback.message.reply("❌ خطا در ثبت محصول.")

    async def ai_publish(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_description_confirmation": return
        
        await callback.message.edit("در حال ثبت محصول و انتشار آنی... ⏳")
        product = await self._register_product_from_state(chat_id, state)
        if product:
            self.conversations.end(chat_id, self.HANDLER_NAME)
            message_id = await publish_to_channel(self.bot, product.id)
            
            if message_id:
                await callback.message.reply(
                    f"✅ محصول با موفقیت ثبت و بلافاصله در کانال منتشر شد!",
                    components=product_detail_keyboard(product.id, True, True)
                )
            else:
                await callback.message.reply(
                    f"✅ محصول ثبت شد اما انتشار در کانال با خطا مواجه شد.",
                    components=product_detail_keyboard(product.id, True, False)
                )
        else:
            await callback.message.reply("❌ خطا در ثبت محصول.")

    async def ai_manual(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_ai_generation": return
        self.conversations.advance(chat_id, self.HANDLER_NAME, "awaiting_description_confirmation")
        await callback.message.reply("✏️ لطفاً کپشن دستی خود را برای این محصول ارسال کنید:")

    async def ai_skip(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.step != "awaiting_ai_generation": return
        self.conversations.advance(chat_id, self.HANDLER_NAME, "confirming")
        await self.send_product_confirmation(callback.message, self.conversations.get_active(chat_id))

    async def list_products(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        page = int(match.group(1))

        async with ctx.session_factory() as session:
            total = await product_repo.count_products(session, active_only=False)
            total_pages = max(1, math.ceil(total / PER_PAGE))
            page = max(1, min(page, total_pages))

            products = await product_repo.get_all_products(session, active_only=False, page=page, per_page=PER_PAGE)

        if not products:
            await callback.message.edit("📦 هیچ محصولی یافت نشد.", components=products_menu_keyboard())
            return

        await callback.message.edit(
            f"📦 لیست محصولات ({to_persian_digits(str(total))} محصول):",
            components=product_list_keyboard(products, page, total_pages)
        )

    async def view(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))

        async with ctx.session_factory() as session:
            product = await product_repo.get_product_by_id(session, product_id)
        if not product:
            await callback.message.reply("محصول یافت نشد.")
            return

        status = "✅ فعال" if product.status == "ACTIVE" else "❌ غیرفعال"
        has_channel_post = product.channel_message_id is not None

        text = (
            f"📦 جزئیات محصول\n"
            "━━━━━━━━━━━━━━━\n"
            f"🏷 کد: {product.sku}\n"
            f"🗂 دسته‌بندی: {product.category.name}\n"
            f"📝 توضیحات: {product.description}\n"
            f"💸 قیمت خرید: {format_price(product.buy_price)}\n"
            f"💰 قیمت فروش: {format_price(product.base_sell_price)}\n"
            f"📦 موجودی: {to_persian_digits(str(product.stock_quantity))} عدد\n"
            f"🔒 رزرو شده: {to_persian_digits(str(product.reserved_quantity))} عدد\n"
            f"📊 وضعیت: {status}\n"
        )
        if product.supplier_name: text += f"🏭 تأمین‌کننده: {product.supplier_name}\n"
        if has_channel_post: text += "📢 پست کانال: ✅ منتشر شده\n"

        await callback.message.edit(text, components=product_detail_keyboard(product.id, product.status == "ACTIVE", has_channel_post))

    async def toggle(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))

        async with ctx.session_factory() as session:
            product = await product_repo.get_product_by_id(session, product_id)
        if not product:
            await callback.message.reply("محصول یافت نشد.")
            return

        new_status = "INACTIVE" if product.status == "ACTIVE" else "ACTIVE"
        async with ctx.session_factory() as session:
            await product_repo.update_product(session, product_id, status=new_status)
        await self.view(callback, ctx, match)

    async def stock(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))

        self.conversations.start(chat_id, self.HANDLER_NAME, "update_stock", {"product_id": product_id})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"prod:view:{product_id}")]])
        async with ctx.session_factory() as session:
            product = await product_repo.get_product_by_id(session, product_id)
        await callback.message.edit(
            f"📦 بروزرسانی موجودی\n\n"
            f"محصول: {product.sku} — {product.description[:30]}\n"
            f"موجودی فعلی: {to_persian_digits(str(product.stock_quantity))} عدد\n\n"
            "تعداد جدید موجودی را وارد کنید (عدد مثبت):",
            components=cancel_kb
        )

    async def search(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        self.conversations.start(chat_id, self.HANDLER_NAME, "searching")
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:products")]])
        await callback.message.edit(
            "🔍 جستجوی محصول\n\n"
            "کد محصول (SKU) یا بخشی از توضیحات را وارد کنید:",
            components=cancel_kb
        )

    async def edit_menu(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))

        async with ctx.session_factory() as session:
            product = await product_repo.get_product_by_id(session, product_id)
        if not product:
            await callback.message.reply("❌ محصول یافت نشد.")
            return

        text = (
            f"✏️ ویرایش محصول: [{product.sku}]\n"
            f"📝 توضیحات: {product.description[:50]}...\n"
            f"💰 قیمت فروش: {format_price(product.base_sell_price)}\n\n"
            "کدام فیلد را می‌خواهید ویرایش کنید؟"
        )
        await callback.message.edit(text, components=product_edit_keyboard(product_id))

    async def edit_field(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        field = match.group(1)
        product_id = int(match.group(2))

        async with ctx.session_factory() as session:
            product = await product_repo.get_product_by_id(session, product_id)
        if not product:
            await callback.message.reply("❌ محصول یافت نشد.")
            return

        current_values = {
            "description": product.description,
            "buy_price": format_price(product.buy_price),
            "sell_price": format_price(product.base_sell_price),
            "supplier": product.supplier_name or "—",
        }
        current = current_values.get(field, "—")
        label = _EDIT_FIELD_LABELS.get(field, field)

        self.conversations.start(chat_id, self.HANDLER_NAME, f"edit_{field}", {"product_id": product_id})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"prod:edit:{product_id}")]])
        await callback.message.edit(
            f"✏️ ویرایش {label}\n\n"
            f"مقدار فعلی:\n{current}\n\n"
            f"مقدار جدید را ارسال کنید:",
            components=cancel_kb
        )


