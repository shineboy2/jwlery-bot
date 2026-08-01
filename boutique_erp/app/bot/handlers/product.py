"""
Product management handlers: FSM registration, list, view, edit, stock management.
"""
import logging
import math

from bale import Message, CallbackQuery

from app.database.crud import (
    get_admin_by_chat_id, get_all_categories, get_product_by_id,
    update_product, toggle_category, count_products, get_all_products
)
from app.services.product_service import register_product, search_products
from app.bot.keyboards.inline import (
    products_menu_keyboard, product_list_keyboard, product_detail_keyboard,
    category_select_keyboard, done_uploading_keyboard, confirm_product_keyboard,
    publish_after_register_keyboard, back_to_main_keyboard
)
from app.utils.formatters import format_price, to_persian_digits

logger = logging.getLogger(__name__)

PER_PAGE = 5

# FSM states for product registration
# {chat_id: {"step": "...", "data": {...}}}
_product_states = {}


async def callback_products_menu(callback: CallbackQuery):
    """Show products menu."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    await callback.message.edit(
        "📦 مدیریت محصولات\nاز منوی زیر انتخاب کنید:",
        components=products_menu_keyboard()
    )


async def callback_product_add(callback: CallbackQuery):
    """Start product registration FSM - Step 1: Select category."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    categories = await get_all_categories(active_only=True)
    if not categories:
        await callback.message.reply("⚠️ ابتدا باید دسته‌بندی ایجاد کنید.")
        return

    _product_states[chat_id] = {"step": "select_category", "data": {"images": []}}

    await callback.message.edit(
        "📦 ثبت محصول جدید\n\n"
        "مرحله ۱/۸: دسته‌بندی محصول را انتخاب کنید:",
        components=category_select_keyboard(categories)
    )


async def callback_product_category_select(callback: CallbackQuery, category_id: int):
    """Step 1: Category selected → Step 2: Upload images."""
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "select_category":
        return

    state["data"]["category_id"] = category_id
    state["step"] = "awaiting_sku"
    _product_states[chat_id] = state

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")
    ]])
    await callback.message.edit(
        "📦 ثبت محصول جدید\n\n"
        "مرحله ۲/۹: لطفاً کد محصول (SKU) مورد نظر خود را وارد کنید:\n"
        "(به عنوان مثال: NK-101)",
        components=cancel_kb
    )


async def callback_images_done(callback: CallbackQuery):
    """Step 2 done: Images uploaded → Step 3: Description."""
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "uploading_images":
        return

    if not state["data"].get("images"):
        await callback.message.reply("⚠️ حداقل یک عکس ارسال کنید.")
        return

    state["step"] = "awaiting_description"
    _product_states[chat_id] = state

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")
    ]])
    await callback.message.edit(
        f"✅ {to_persian_digits(str(len(state['data']['images'])))} عکس دریافت شد.\n\n"
        "مرحله ۳/۸: توضیحات محصول را وارد کنید:\n"
        "مثال: گردنبند زنجیر طلایی ظریف با آویز قلب",
        components=cancel_kb
    )


async def callback_product_cancel(callback: CallbackQuery):
    """Cancel product registration."""
    chat_id = callback.message.chat.id
    _product_states.pop(chat_id, None)
    await callback.message.edit(
        "❌ ثبت محصول لغو شد.",
        components=products_menu_keyboard()
    )


async def callback_product_confirm(callback: CallbackQuery):
    """Step 8: Final confirmation → Register product."""
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "confirming":
        return

    data = state["data"]
    try:
        product = await register_product(
            sku=data["sku"],
            category_id=data["category_id"],
            description=data["description"],
            buy_price=data["buy_price"],
            base_sell_price=data["base_sell_price"],
            stock_quantity=data["stock_quantity"],
            image_file_ids=data["images"],
            supplier_name=data.get("supplier_name"),
            dynamic_attributes=data.get("dynamic_attributes", {}),
        )
        del _product_states[chat_id]

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
        del _product_states[chat_id]
        await callback.message.edit(
            f"❌ خطا در ثبت محصول: {str(e)}",
            components=products_menu_keyboard()
        )


async def callback_ai_gen(callback):
    """Handle AI Generation request."""
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "awaiting_ai_generation":
        return

    await callback.message.edit("در حال ارتباط با هوش مصنوعی... ⏳")
    
    data = state["data"]
    from app.services.ai_service import generate_product_description
    from app.database.crud import get_category_by_id, get_ai_prompt_by_name
    
    category = await get_category_by_id(data["category_id"])
    cat_name = category.name if category else "نامشخص"
    
    prompt_template = await get_ai_prompt_by_name("product_description")
    
    ai_desc = await generate_product_description(
        title=data.get("description", data.get("sku", "")), 
        category=cat_name, 
        attributes=data.get("dynamic_attributes", {}),
        base_sell_price=data.get("base_sell_price"),
        stock_quantity=data.get("stock_quantity"),
        prompt_template=prompt_template
    )
    
    if ai_desc:
        data["description"] = ai_desc
        state["data"] = data
        state["step"] = "awaiting_description_confirmation"
        _product_states[chat_id] = state
        
        from app.bot.keyboards.inline import preview_ai_keyboard
        from app.bot.loader import bot
        from bale import InputFile
        
        images = data.get("images", [])
        try:
            if not images:
                await callback.message.reply(ai_desc)
            elif len(images) == 1:
                await bot.send_photo(chat_id=chat_id, photo=InputFile(images[0]), caption=ai_desc)
            else:
                # Bale has no send_media_group - send first with caption, rest without
                await bot.send_photo(chat_id=chat_id, photo=InputFile(images[0]), caption=ai_desc)
                for file_id in images[1:]:
                    try:
                        await bot.send_photo(chat_id=chat_id, photo=InputFile(file_id))
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
        state["step"] = "confirming"
        _product_states[chat_id] = state
        await send_product_confirmation(callback.message, state)

async def callback_ai_edit(callback):
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "awaiting_description_confirmation":
        return
    await callback.message.reply("✏️ لطفاً متن جدید و ویرایش‌شده را ارسال کنید:\n(متن ارسالی شما کاملاً جایگزین متن هوش مصنوعی خواهد شد)")

async def callback_ai_regen(callback):
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "awaiting_description_confirmation":
        return
    
    state["step"] = "awaiting_ai_generation"
    _product_states[chat_id] = state
    await callback_ai_gen(callback)

async def _register_product_from_state(chat_id: int, state: dict):
    from app.database.crud import register_product
    data = state["data"]
    try:
        product = await register_product(
            sku=data["sku"],
            category_id=data["category_id"],
            description=data["description"],
            buy_price=data["buy_price"],
            base_sell_price=data["base_sell_price"],
            stock_quantity=data["stock_quantity"],
            image_file_ids=data["images"],
            supplier_name=data.get("supplier_name"),
            dynamic_attributes=data.get("dynamic_attributes", {}),
        )
        return product
    except Exception as e:
        logger.error(f"Product registration failed: {e}")
        return None

async def callback_ai_queue(callback):
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "awaiting_description_confirmation":
        return
        
    await callback.message.edit("در حال ثبت محصول و افزودن به صف... ⏳")
    product = await _register_product_from_state(chat_id, state)
    if product:
        del _product_states[chat_id]
        
        # Add to ScheduledPost
        from app.database.crud import async_session
        from app.database.models import ScheduledPost
        async with async_session() as session:
            images = state["data"].get("images", [])
            images_str = ",".join(images) if images else None
            post = ScheduledPost(
                product_id=product.id,
                post_type="MEDIA_GROUP" if images_str and "," in images_str else "IMAGE" if images_str else "TEXT",
                category=None, # Will be picked up by the next available slot or scheduled time
                content_text=product.description,
                file_id=images_str,
                status="QUEUED"
            )
            session.add(post)
            await session.commit()
            
        from app.bot.keyboards.inline import product_detail_keyboard
        await callback.message.reply(
            f"✅ محصول با موفقیت ثبت شد و به صف انتشار اضافه گردید!",
            components=product_detail_keyboard(product.id, True, False)
        )
    else:
        await callback.message.reply("❌ خطا در ثبت محصول.")

async def callback_ai_publish(callback):
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "awaiting_description_confirmation":
        return
        
    await callback.message.edit("در حال ثبت محصول و انتشار آنی... ⏳")
    product = await _register_product_from_state(chat_id, state)
    if product:
        del _product_states[chat_id]
        from app.services.channel_service import publish_to_channel
        from app.bot.loader import bot
        message_id = await publish_to_channel(bot, product.id)
        
        from app.bot.keyboards.inline import product_detail_keyboard
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


async def callback_ai_manual(callback):
    """Switch to manual description entry mode."""
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "awaiting_ai_generation":
        return
        
    state["step"] = "awaiting_description_confirmation"
    _product_states[chat_id] = state
    await callback.message.reply("✏️ لطفاً کپشن دستی خود را برای این محصول ارسال کنید:")

async def callback_ai_skip(callback):
    """Skip AI Generation request."""
    chat_id = callback.message.chat.id
    state = _product_states.get(chat_id)
    if not state or state["step"] != "awaiting_ai_generation":
        return
        
    state["step"] = "confirming"
    _product_states[chat_id] = state
    
    await send_product_confirmation(callback.message, state)


async def callback_product_list(callback: CallbackQuery, page: int = 1):
    """Show paginated product list."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    total = await count_products(active_only=False)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    page = max(1, min(page, total_pages))

    products = await get_all_products(active_only=False, page=page, per_page=PER_PAGE)

    if not products:
        await callback.message.edit(
            "📦 هیچ محصولی یافت نشد.",
            components=products_menu_keyboard()
        )
        return

    await callback.message.edit(
        f"📦 لیست محصولات ({to_persian_digits(str(total))} محصول):",
        components=product_list_keyboard(products, page, total_pages)
    )


async def callback_product_view(callback: CallbackQuery, product_id: int):
    """Show product details."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    product = await get_product_by_id(product_id)
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

    if product.supplier_name:
        text += f"🏭 تأمین‌کننده: {product.supplier_name}\n"

    if has_channel_post:
        text += "📢 پست کانال: ✅ منتشر شده\n"

    await callback.message.edit(
        text,
        components=product_detail_keyboard(
            product.id,
            product.status == "ACTIVE",
            has_channel_post
        )
    )


async def callback_product_toggle(callback: CallbackQuery, product_id: int):
    """Toggle product active status."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    product = await get_product_by_id(product_id)
    if not product:
        await callback.message.reply("محصول یافت نشد.")
        return

    new_status = "INACTIVE" if product.status == "ACTIVE" else "ACTIVE"
    await update_product(product_id, status=new_status)
    # loading: f"وضعیت به {'فعال' if new_status == 'ACTIVE' else 'غیرفعال'} تغییر یافت."
    await callback_product_view(callback, product_id)


async def callback_product_stock(callback: CallbackQuery, product_id: int):
    """Start stock update flow."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _product_states[chat_id] = {
        "step": "update_stock",
        "data": {"product_id": product_id}
    }

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data=f"prod:view:{product_id}")
    ]])
    product = await get_product_by_id(product_id)
    await callback.message.edit(
        f"📦 بروزرسانی موجودی\n\n"
        f"محصول: {product.sku} — {product.description[:30]}\n"
        f"موجودی فعلی: {to_persian_digits(str(product.stock_quantity))} عدد\n\n"
        "تعداد جدید موجودی را وارد کنید (عدد مثبت):",
        components=cancel_kb
    )


async def callback_product_search(callback: CallbackQuery):
    """Start product search."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _product_states[chat_id] = {"step": "searching", "data": {}}

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="menu:products")
    ]])
    await callback.message.edit(
        "🔍 جستجوی محصول\n\n"
        "کد محصول (SKU) یا بخشی از توضیحات را وارد کنید:",
        components=cancel_kb
    )


async def handle_product_message(message: Message) -> bool:
    """
    Handle text/photo messages for product FSM.
    Returns True if message was consumed by this handler.
    """
    chat_id = message.chat.id
    state = _product_states.get(chat_id)
    if not state:
        return False

    step = state["step"]
    text = message.content.strip() if message.content else ""

    # Handle manual SKU entry
    if step == "awaiting_sku":
        if not text or len(text) < 2:
            await message.reply("⚠️ کد محصول حداقل باید ۲ کاراکتر باشد.")
            return True
            
        # TODO: Add check for duplicate SKU if needed
        
        state["data"]["sku"] = text.upper()
        state["step"] = "uploading_images"
        state["data"]["images"] = []
        _product_states[chat_id] = state
        
        from app.bot.keyboards.inline import done_uploading_keyboard
        await message.reply(
            "✅ کد محصول ثبت شد.\n\n"
            "مرحله ۳/۹: عکس‌های محصول را ارسال کنید.\n"
            "می‌توانید چند عکس ارسال کنید.\n"
            "بعد از آخرین عکس دکمه ✅ را بزنید:",
            components=done_uploading_keyboard()
        )
        return True

    # Handle photo uploads
    if step == "uploading_images" and message.photos:
        # Get the largest photo
        photo = message.photos[-1]
        state["data"]["images"].append(photo.file_id)
        _product_states[chat_id] = state
        count = len(state["data"]["images"])
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
        state["data"]["description"] = text
        state["step"] = "awaiting_buy_price"
        _product_states[chat_id] = state

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
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
            if price <= 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ قیمت باید یک عدد مثبت باشد. مثال: 250000")
            return True

        state["data"]["buy_price"] = price * 10  # Convert to Rials
        state["step"] = "awaiting_sell_price"
        _product_states[chat_id] = state

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
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
            if price <= 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ قیمت باید یک عدد مثبت باشد.")
            return True

        state["data"]["base_sell_price"] = price * 10  # Convert to Rials
        state["step"] = "awaiting_stock"
        _product_states[chat_id] = state

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
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
            if quantity < 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ موجودی باید یک عدد صحیح غیر منفی باشد.")
            return True

        state["data"]["stock_quantity"] = quantity
        state["step"] = "awaiting_supplier"
        _product_states[chat_id] = state

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
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
        state["data"]["supplier_name"] = supplier
        
        from app.database.crud import get_category_by_id
        category = await get_category_by_id(state["data"]["category_id"])
        attributes = category.attributes if category and category.attributes else []
        
        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
        
        if not attributes:
            state["step"] = "awaiting_ai_generation"
            _product_states[chat_id] = state
            from app.bot.keyboards.inline import ai_generate_keyboard
            await message.reply(
                "✅ نام تأمین‌کننده ثبت شد.\n\n"
                "آیا می‌خواهید توضیحات محصول را با استفاده از هوش مصنوعی (Gemini) جذاب‌تر کنید؟",
                components=ai_generate_keyboard()
            )
            return True
        else:
            state["data"]["pending_attributes"] = list(attributes)
            state["data"]["dynamic_attributes"] = {}
            state["step"] = "awaiting_dynamic_attribute"
            _product_states[chat_id] = state
            
            first_attr = state["data"]["pending_attributes"][0]
            await message.reply(
                f"✅ نام تأمین‌کننده ثبت شد.\n\n"
                f"مرحله ۸: لطفاً مقدار ویژگی '{first_attr}' را وارد کنید:\n"
                "(اختیاری — برای عبور 'رد' بنویسید)",
                components=cancel_kb
            )
            return True

    if step == "awaiting_dynamic_attribute":
        pending = state["data"]["pending_attributes"]
        current_attr = pending[0]
        
        if text.lower() not in ("رد", "skip", "-", ""):
            state["data"]["dynamic_attributes"][current_attr] = text.strip()
            
        pending.pop(0)
        
        if pending:
            state["data"]["pending_attributes"] = pending
            _product_states[chat_id] = state
            from bale import InlineKeyboardButton
            from app.bot.keyboards.inline import build_kb
            cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="prod:cancel")]])
            
            next_attr = pending[0]
            await message.reply(
                f"✅ ثبت شد.\nلطفاً مقدار ویژگی '{next_attr}' را وارد کنید:\n"
                "(اختیاری — برای عبور 'رد' بنویسید)",
                components=cancel_kb
            )
            return True
        else:
            state["step"] = "awaiting_ai_generation"
            _product_states[chat_id] = state
            from app.bot.keyboards.inline import ai_generate_keyboard
            await message.reply(
                "✅ ویژگی‌ها ثبت شدند.\n\n"
                "آیا می‌خواهید توضیحات محصول را با استفاده از هوش مصنوعی (Gemini) جذاب‌تر کنید؟",
                components=ai_generate_keyboard()
            )
            return True

    if step == "awaiting_description_confirmation":
        state["data"]["description"] = text.strip()
        _product_states[chat_id] = state
        await message.reply("✅ توضیحات ویرایش شده ذخیره شد.")
        
        # Resend preview
        from app.bot.keyboards.inline import preview_ai_keyboard
        from app.bot.loader import bot
        from bale import InputFile
        
        images = state["data"].get("images", [])
        desc = state["data"]["description"]
        try:
            if not images:
                await message.reply(desc)
            elif len(images) == 1:
                await bot.send_photo(chat_id=chat_id, photo=InputFile(images[0]), caption=desc)
            else:
                # Bale has no send_media_group - send first with caption, rest without
                await bot.send_photo(chat_id=chat_id, photo=InputFile(images[0]), caption=desc)
                for file_id in images[1:]:
                    try:
                        await bot.send_photo(chat_id=chat_id, photo=InputFile(file_id))
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
            if quantity < 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ موجودی باید یک عدد صحیح غیر منفی باشد.")
            return True

        product_id = state["data"]["product_id"]
        await update_product(product_id, stock_quantity=quantity)
        del _product_states[chat_id]

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
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

        del _product_states[chat_id]
        products = await search_products(text)

        if not products:
            from bale import InlineKeyboardButton
            from app.bot.keyboards.inline import build_kb
            back_kb = build_kb([[
                InlineKeyboardButton("🔙 بازگشت", callback_data="menu:products")
            ]])
            await message.reply(f"🔍 نتیجه‌ای برای '{text}' یافت نشد.", components=back_kb)
            return True

        result_text = f"🔍 نتایج جستجو برای '{text}':\n\n"
        for prod in products[:10]:
            status = "✅" if prod.status == "ACTIVE" else "❌"
            result_text += f"{status} [{prod.sku}] {prod.description[:40]}\n"
            result_text += f"   💰 {format_price(prod.base_sell_price)} | 📦 {to_persian_digits(str(prod.stock_quantity))}\n\n"

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        back_kb = build_kb([[
            InlineKeyboardButton("🔙 بازگشت", callback_data="menu:products")
        ]])
        await message.reply(result_text, components=back_kb)
        return True

    # Handle product field editing
    if step.startswith("edit_"):
        return await _handle_product_edit_message(message, state, chat_id)

    return False


async def send_product_confirmation(message, state):
    data = state["data"]
    summary = (
        "📋 خلاصه محصول — مرحله نهایی\n"
        "━━━━━━━━━━━━━━━\n"
        f"📸 عکس‌ها: {to_persian_digits(str(len(data['images'])))} عدد\n"
        f"📝 توضیحات: {data['description']}\n"
        f"💸 قیمت خرید: {format_price(data['buy_price'])}\n"
        f"💰 قیمت فروش: {format_price(data['base_sell_price'])}\n"
        f"📦 موجودی: {to_persian_digits(str(data['stock_quantity']))} عدد\n"
    )
    if data.get("supplier_name"):
        summary += f"🏭 تأمین‌کننده: {data['supplier_name']}\n"
    
    attributes = data.get("dynamic_attributes")
    if attributes:
        attrs_str = " | ".join([f"{k}: {v}" for k, v in attributes.items()])
        summary += f"✨ ویژگی‌ها: {attrs_str}\n"

    summary += "\n✅ آیا تأیید می‌کنید؟"

    from app.bot.keyboards.inline import confirm_product_keyboard
    await message.reply(summary, components=confirm_product_keyboard())


def get_product_state(chat_id: int) -> dict | None:
    return _product_states.get(chat_id)


def clear_product_state(chat_id: int):
    _product_states.pop(chat_id, None)

# ─────────────────────────────────────────
# Product Edit Handlers
# ─────────────────────────────────────────
_EDIT_FIELD_LABELS = {
    "description": "توضیحات/کپشن",
    "buy_price": "قیمت خرید (تومان)",
    "sell_price": "قیمت فروش (تومان)",
    "supplier": "نام تأمین‌کننده",
}

async def callback_product_edit(callback: CallbackQuery, product_id: int):
    """Show edit menu for a product."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    product = await get_product_by_id(product_id)
    if not product:
        await callback.message.reply("❌ محصول یافت نشد.")
        return

    from app.bot.keyboards.inline import product_edit_keyboard
    text = (
        f"✏️ ویرایش محصول: [{product.sku}]\n"
        f"📝 توضیحات: {product.description[:50]}...\n"
        f"💰 قیمت فروش: {format_price(product.base_sell_price)}\n\n"
        "کدام فیلد را می‌خواهید ویرایش کنید؟"
    )
    await callback.message.edit(text, components=product_edit_keyboard(product_id))


async def callback_product_edit_field(callback: CallbackQuery, field: str, product_id: int):
    """Start edit FSM for a specific field."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    product = await get_product_by_id(product_id)
    if not product:
        await callback.message.reply("❌ محصول یافت نشد.")
        return

    # Show current value
    current_values = {
        "description": product.description,
        "buy_price": format_price(product.buy_price),
        "sell_price": format_price(product.base_sell_price),
        "supplier": product.supplier_name or "—",
    }
    current = current_values.get(field, "—")
    label = _EDIT_FIELD_LABELS.get(field, field)

    _product_states[chat_id] = {
        "step": f"edit_{field}",
        "data": {"product_id": product_id}
    }

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"prod:edit:{product_id}")]])
    await callback.message.edit(
        f"✏️ ویرایش {label}\n\n"
        f"مقدار فعلی:\n{current}\n\n"
        f"مقدار جدید را ارسال کنید:",
        components=cancel_kb
    )


async def _handle_product_edit_message(message, state: dict, chat_id: int) -> bool:
    """Handle text input during product field editing. Returns True if consumed."""
    step = state["step"]
    text = message.content.strip() if message.content else ""
    product_id = state["data"]["product_id"]

    if step == "edit_description":
        if len(text) < 3:
            await message.reply("⚠️ توضیحات باید حداقل ۳ کاراکتر باشد.")
            return True
        await update_product(product_id, description=text)
        del _product_states[chat_id]
        from app.bot.keyboards.inline import product_edit_keyboard
        await message.reply(f"✅ توضیحات بروزرسانی شد.", components=product_edit_keyboard(product_id))
        return True

    if step == "edit_buy_price":
        try:
            price = int(text.replace(",", "").replace("،", ""))
            if price <= 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ قیمت باید یک عدد مثبت باشد.")
            return True
        await update_product(product_id, buy_price=price * 10)
        del _product_states[chat_id]
        from app.bot.keyboards.inline import product_edit_keyboard
        await message.reply(f"✅ قیمت خرید به {format_price(price * 10)} بروزرسانی شد.", components=product_edit_keyboard(product_id))
        return True

    if step == "edit_sell_price":
        try:
            price = int(text.replace(",", "").replace("،", ""))
            if price <= 0:
                raise ValueError
        except ValueError:
            await message.reply("⚠️ قیمت باید یک عدد مثبت باشد.")
            return True
        await update_product(product_id, base_sell_price=price * 10)
        del _product_states[chat_id]
        from app.bot.keyboards.inline import product_edit_keyboard
        await message.reply(f"✅ قیمت فروش به {format_price(price * 10)} بروزرسانی شد.", components=product_edit_keyboard(product_id))
        return True

    if step == "edit_supplier":
        supplier = None if text.lower() in ("رد", "skip", "-", "") else text
        await update_product(product_id, supplier_name=supplier)
        del _product_states[chat_id]
        from app.bot.keyboards.inline import product_edit_keyboard
        display = supplier or "(حذف شد)"
        await message.reply(f"✅ تأمین‌کننده به '{display}' بروزرسانی شد.", components=product_edit_keyboard(product_id))
        return True

    return False
