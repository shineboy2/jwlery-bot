"""
Bot instance creation and handler registration.
All callbacks are routed here via regex-based callback_data parsing.
"""
import re
import logging

from bale import Bot
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create bot instance
bot = Bot(token=settings.bale_bot_token)


def register_handlers():
    """Register all handlers for the bot."""

    # ─────────────────────────────────────────
    # Import handlers
    # ─────────────────────────────────────────
    from app.bot.handlers import admin as admin_h
    from app.bot.handlers import category as cat_h
    from app.bot.handlers import product as prod_h
    from app.bot.handlers import channel as ch_h
    from app.bot.handlers import order as ord_h
    from app.bot.handlers import customer as cust_h
    from app.bot.handlers import report as rep_h
    from app.bot.handlers import cms as cms_h
    from app.bot.handlers import cms_category as cms_cat_h
    from app.bot.handlers import cms_create as cms_create_h
    from app.bot.handlers import queue_handler as queue_h
    from app.bot.handlers import buffer_handler as buffer_h
    from app.bot.handlers import finance as finance_h

    # ─────────────────────────────────────────
    # /start command
    # ─────────────────────────────────────────
    @bot.event
    async def on_message(message):
        """Route all incoming messages."""
        # Only process text messages (content)
        if not message:
            return

        text = message.content or ""
        chat_id = message.chat.id
        logger.info(f"Incoming message from chat_id: {chat_id} - text: {text}")

        # Handle /start
        if text.strip() == "/start":
            clear_all_states(chat_id)
            await admin_h.cmd_start(message)
            return

        # Route to FSM handlers in priority order
        # Each handler returns True if it consumed the message
        if await prod_h.handle_product_message(message):
            return
        if await cat_h.handle_category_message(message):
            return
        if await ord_h.handle_order_message(message):
            return
        if await cust_h.handle_customer_message(message):
            return
        # CMS create FSM (new content creation)
        if await cms_create_h.handle_cms_create_message(message):
            return
        # Queue/buffer edit FSMs
        if await queue_h.handle_queue_edit_message(message):
            return
        if await buffer_h.handle_buffer_edit_message(message):
            return
        if await finance_h.handle_finance_message(message):
            return
        # Legacy CMS FSM
        if await cms_h.handle_cms_message(message):
            return
        if await cms_cat_h.handle_cms_cat_message(message):
            return

        # Admin flow (add/remove admin)
        await admin_h.handle_message(message)

    # ─────────────────────────────────────────
    # Helper to clear all FSM states
    # ─────────────────────────────────────────
    def clear_all_states(chat_id: int):
        prod_h._product_states.pop(chat_id, None)
        ord_h._order_states.pop(chat_id, None)
        cust_h._customer_states.pop(chat_id, None)
        cat_h._cat_states.pop(chat_id, None)
        cms_h._cms_states.pop(chat_id, None)
        cms_cat_h._cms_cat_states.pop(chat_id, None)
        cms_create_h._cms_create_states.pop(chat_id, None)
        queue_h._queue_edit_states.pop(chat_id, None)
        buffer_h._buffer_edit_states.pop(chat_id, None)
        finance_h._finance_states.pop(chat_id, None)

    # ─────────────────────────────────────────
    # Callback query routing
    # ─────────────────────────────────────────
    @bot.event
    async def on_callback(callback):
        """Route all incoming callback queries."""
        data = callback.data
        chat_id = callback.message.chat.id
        logger.info(f"Callback query: {data}")

        if data.startswith("menu:"):
            clear_all_states(chat_id)

        # ── Main Menu ───────────────────────────
        if data == "menu:main":
            await admin_h.callback_main_menu(callback)

        elif data == "menu:settings":
            await admin_h.callback_settings(callback)

        elif data == "menu:categories":
            await cat_h.callback_categories_menu(callback)

        elif data == "menu:products":
            await prod_h.callback_products_menu(callback)

        elif data == "menu:orders":
            await ord_h.callback_orders_menu(callback)

        elif data == "menu:customers":
            await cust_h.callback_customers_menu(callback)

        elif data == "menu:reports":
            await rep_h.callback_reports_menu(callback)

        elif data == "menu:cms":
            await cms_h.callback_cms_menu(callback)

        elif data == "menu:finance":
            await finance_h.callback_finance_menu(callback)

        # ── Admin Management ────────────────────
        elif data == "admin:list":
            await admin_h.callback_admin_list(callback)

        elif data == "admin:add":
            await admin_h.callback_admin_add(callback)

        elif data == "admin:remove":
            await admin_h.callback_admin_remove(callback)

        # ── Category ────────────────────────────
        elif data == "cat:add":
            await cat_h.callback_category_add(callback)

        elif m := re.match(r"^cat:view:(\d+)$", data):
            await cat_h.callback_category_view(callback, int(m.group(1)))

        elif m := re.match(r"^cat:toggle:(\d+)$", data):
            await cat_h.callback_category_toggle(callback, int(m.group(1)))

        elif m := re.match(r"^cat:edit:(\d+)$", data):
            await cat_h.callback_category_edit(callback, int(m.group(1)))

        # ── Product ─────────────────────────────
        elif data == "prod:add":
            await prod_h.callback_product_add(callback)

        elif data == "prod:images_done":
            await prod_h.callback_images_done(callback)

        elif data == "prod:ai_gen":
            await prod_h.callback_ai_gen(callback)

        elif data == "prod:ai_manual":
            await prod_h.callback_ai_manual(callback)

        elif data == "prod:ai_skip":
            await prod_h.callback_ai_skip(callback)

        elif data == "prod:ai_edit":
            await prod_h.callback_ai_edit(callback)

        elif data == "prod:ai_regen":
            await prod_h.callback_ai_regen(callback)

        elif data == "prod:ai_queue":
            await prod_h.callback_ai_queue(callback)

        elif data == "prod:ai_publish":
            await prod_h.callback_ai_publish(callback)

        elif data == "prod:confirm":
            await prod_h.callback_product_confirm(callback)

        elif data == "prod:cancel":
            await prod_h.callback_product_cancel(callback)

        elif data == "prod:search":
            await prod_h.callback_product_search(callback)

        elif m := re.match(r"^prod:cat:(\d+)$", data):
            await prod_h.callback_product_category_select(callback, int(m.group(1)))

        elif m := re.match(r"^prod:list:page:(\d+)$", data):
            await prod_h.callback_product_list(callback, int(m.group(1)))

        elif m := re.match(r"^prod:view:(\d+)$", data):
            await prod_h.callback_product_view(callback, int(m.group(1)))

        elif m := re.match(r"^prod:edit:(\d+)$", data):
            await prod_h.callback_product_edit(callback, int(m.group(1)))

        elif m := re.match(r"^prod:edit:(\w+):(\d+)$", data):
            await prod_h.callback_product_edit_field(callback, m.group(1), int(m.group(2)))

        elif m := re.match(r"^prod:toggle:(\d+)$", data):
            await prod_h.callback_product_toggle(callback, int(m.group(1)))

        elif m := re.match(r"^prod:stock:(\d+)$", data):
            await prod_h.callback_product_stock(callback, int(m.group(1)))

        # ── Channel (legacy, kept for reference) ─
        # Direct product publishing removed — use CMS instead

        # ── Orders ──────────────────────────────
        elif data == "ord:export":
            await ord_h.callback_order_export(callback)

        elif data == "ord:bulk_track":
            await ord_h.callback_order_bulk_track(callback)

        elif data == "ord:new":
            await ord_h.callback_new_order(callback)

        elif data == "ord:confirm":
            await ord_h.callback_order_confirm(callback)
            
        elif data == "ord:edit":
            await ord_h.callback_order_edit(callback)

        elif data == "ord:items_done":
            await ord_h.callback_order_items_done(callback)

        elif m := re.match(r"^ord:view:(\d+)$", data):
            await ord_h.callback_order_view(callback, int(m.group(1)))

        elif m := re.match(r"^ord:filter:(.+)$", data):
            await ord_h.callback_orders_filter(callback, m.group(1))

        elif m := re.match(r"^ord:status:(\d+):(.+)$", data):
            await ord_h.callback_order_status(callback, int(m.group(1)), m.group(2))

        elif m := re.match(r"^ord:track:(\d+)$", data):
            await ord_h.callback_order_tracking(callback, int(m.group(1)))

        elif m := re.match(r"^ord:ship_cost:skip:(\d+)$", data):
            await ord_h.callback_order_ship_cost_skip(callback, int(m.group(1)))

        elif m := re.match(r"^ord:prod:(\d+)$", data):
            await ord_h.callback_order_product_select(callback, int(m.group(1)))

        # ── Customers ───────────────────────────
        elif data == "cust:search":
            await cust_h.callback_customer_search(callback)

        elif data == "cust:add":
            await cust_h.callback_add_customer(callback)

        elif m := re.match(r"^cust:view:(\d+)$", data):
            await cust_h.callback_customer_view(callback, int(m.group(1)))

        elif m := re.match(r"^cust:orders:(\d+)$", data):
            await cust_h.callback_customer_orders(callback, int(m.group(1)))

        elif m := re.match(r"^cust:edit:(\d+)$", data):
            await cust_h.callback_customer_edit(callback, int(m.group(1)))

        elif m := re.match(r"^cust:edit:(\w+):(\d+)$", data):
            await cust_h.callback_customer_edit_field(callback, m.group(1), int(m.group(2)))

        # ── Reports ─────────────────────────────
        elif data == "rep:profit":
            await rep_h.callback_report_profit(callback, "all")

        elif data == "rep:profit:month":
            await rep_h.callback_report_profit(callback, "month")

        elif data == "rep:profit:all":
            await rep_h.callback_report_profit(callback, "all")

        elif data == "rep:inventory":
            await rep_h.callback_report_inventory(callback)

        elif data == "rep:sales:week":
            await rep_h.callback_report_sales(callback, "week")

        elif data == "rep:sales:month":
            await rep_h.callback_report_sales(callback, "month")

        elif data == "rep:sales":
            await rep_h.callback_report_sales(callback, "month")

        # ── Noop (for display-only buttons) ─────
        elif data == "noop":
            pass

        elif data == "cms:new":
            await cms_h.callback_cms_new(callback)

        elif data == "cms:list":
            await cms_h.callback_cms_list(callback)

        elif data == "cms:config":
            await cms_h.callback_cms_config(callback)

        elif data == "cms:history":
            await cms_h.callback_cms_history(callback)

        elif m := re.match(r"^cms:hist:page:(\d+)$", data):
            await cms_h.callback_cms_history(callback, int(m.group(1)))

        elif m := re.match(r"^cms:hist:view:(\d+)$", data):
            await cms_h.callback_cms_history_view(callback, int(m.group(1)))

        elif m := re.match(r"^cms:hist:resend:(\d+)$", data):
            await cms_h.callback_cms_history_resend(callback, int(m.group(1)))

        # ── CMS Create Content ─────────────────────────────────
        elif data == "cms:create":
            await cms_create_h.callback_cms_create_mode(callback)

        elif data == "cms:create:wizard":
            await cms_create_h.callback_cms_create(callback)
            
        elif data == "cms:create:forward":
            await cms_create_h.callback_cms_create_forward(callback)

        elif m := re.match(r"^cms:create:cat:(.+)$", data):
            await cms_create_h.callback_cms_select_category(callback, m.group(1))

        elif data == "cms:create:skip_img":
            await cms_create_h.callback_cms_skip_image(callback)

        elif data == "cms:create:queue":
            await cms_create_h.callback_cms_create_queue(callback)

        elif data == "cms:create:buffer":
            await cms_create_h.callback_cms_create_buffer(callback)

        elif data == "cms:create:publish_now":
            await cms_create_h.callback_cms_create_publish_now(callback)

        elif data == "cms:create:edit_cap":
            await cms_create_h.callback_cms_create_edit_cap(callback)

        elif data == "cms:create:edit_img":
            await cms_create_h.callback_cms_create_edit_img(callback)

        # ── CMS Queue Management ─────────────────────────────
        elif data == "cms:queue":
            await queue_h.callback_cms_queue_menu(callback)

        elif m := re.match(r"^cms:queue:cat:(.+)$", data):
            await queue_h.callback_cms_queue_category(callback, m.group(1))

        elif m := re.match(r"^cms:queue:post:(\d+)$", data):
            await queue_h.callback_cms_queue_post_detail(callback, int(m.group(1)))

        elif m := re.match(r"^cms:queue:top:(\d+)$", data):
            await queue_h.callback_cms_queue_move_top(callback, int(m.group(1)))

        elif m := re.match(r"^cms:queue:up:(\d+)$", data):
            await queue_h.callback_cms_queue_move_up(callback, int(m.group(1)))

        elif m := re.match(r"^cms:queue:to_buf:(\d+)$", data):
            await queue_h.callback_cms_queue_to_buffer(callback, int(m.group(1)))

        elif m := re.match(r"^cms:queue:del:(\d+)$", data):
            await queue_h.callback_cms_queue_delete(callback, int(m.group(1)))

        elif m := re.match(r"^cms:queue:publish_now:(\d+)$", data):
            await queue_h.callback_cms_queue_publish_now(callback, int(m.group(1)))

        elif m := re.match(r"^cms:queue:edit_cap:(\d+)$", data):
            await queue_h.callback_cms_queue_edit_cap(callback, int(m.group(1)))

        elif m := re.match(r"^cms:queue:edit_img:(\d+)$", data):
            await queue_h.callback_cms_queue_edit_img(callback, int(m.group(1)))

        # ── CMS Buffer Management ─────────────────────────────
        elif data == "cms:buf":
            await buffer_h.callback_cms_buffer_menu(callback)

        elif m := re.match(r"^cms:buf:cat:(.+)$", data):
            await buffer_h.callback_cms_buffer_category(callback, m.group(1))

        elif m := re.match(r"^cms:buf:post:(\d+)$", data):
            await buffer_h.callback_cms_buffer_post_detail(callback, int(m.group(1)))

        elif m := re.match(r"^cms:buf:to_queue:(\d+)$", data):
            await buffer_h.callback_cms_buffer_to_queue(callback, int(m.group(1)))

        elif m := re.match(r"^cms:buf:del:(\d+)$", data):
            await buffer_h.callback_cms_buffer_delete(callback, int(m.group(1)))

        elif m := re.match(r"^cms:buf:publish_now:(\d+)$", data):
            await buffer_h.callback_cms_buffer_publish_now(callback, int(m.group(1)))

        elif m := re.match(r"^cms:buf:edit_cap:(\d+)$", data):
            await buffer_h.callback_cms_buffer_edit_cap(callback, int(m.group(1)))

        elif m := re.match(r"^cms:buf:edit_img:(\d+)$", data):
            await buffer_h.callback_cms_buffer_edit_img(callback, int(m.group(1)))

        # ── Finance Management ──────────────────────────────
        elif data == "fin:exp:new":
            await finance_h.callback_expense_new(callback)
            
        elif m := re.match(r"^fin:exp:cat:(\d+)$", data):
            await finance_h.callback_expense_category(callback, int(m.group(1)))
            
        elif data == "fin:exp:skip_desc":
            await finance_h.callback_expense_skip_desc(callback)
            
        elif data == "fin:part:new":
            await finance_h.callback_partner_new(callback)
            
        elif m := re.match(r"^fin:part:id:(\d+)$", data):
            await finance_h.callback_partner_select(callback, int(m.group(1)))
            
        elif m := re.match(r"^fin:part:type:(DRAWING|INJECTION):(\d+)$", data):
            await finance_h.callback_partner_type(callback, m.group(1), int(m.group(2)))
            
        elif data == "fin:part:skip_desc":
            await finance_h.callback_partner_skip_desc(callback)
            
        elif m := re.match(r"^fin:rep:(.+)$", data):
            await finance_h.callback_report_pl(callback, m.group(1))

        # ── Legacy queue delete (old CMS) ──────────────────────

        elif data == "cms:ai_prompt":
            await cms_h.callback_cms_ai_prompt(callback)
            
        elif m := re.match(r"^cms:ai_cat:(\d+)$", data):
            await cms_h.callback_cms_ai_cat(callback, int(m.group(1)))
            
        elif data == "cms:manual_post":
            await cms_h.callback_cms_manual_post(callback)

        elif data == "cms:ai_ok":
            await cms_h.callback_cms_ai_ok(callback)

        elif m := re.match(r"^cms:schedule:(\w+)$", data):
            await cms_h.callback_cms_schedule(callback, m.group(1))

        elif m := re.match(r"^cms:cat:(\w+)$", data):
            if data == "cms:cat:manage":
                await cms_cat_h.callback_cms_cat_manage(callback)
            elif data == "cms:cat:add":
                await cms_cat_h.callback_cms_cat_add(callback)
            else:
                await cms_h.callback_cms_category(callback, m.group(1))
                
        elif m := re.match(r"^cms:cat:view:(\d+)$", data):
            await cms_cat_h.callback_cms_cat_view(callback, int(m.group(1)))
            
        elif m := re.match(r"^cms:cat:delete:(\d+)$", data):
            await cms_cat_h.callback_cms_cat_delete(callback, int(m.group(1)))
            
        elif m := re.match(r"^cms:cat:hist:(\d+):(\d+)$", data):
            await cms_cat_h.callback_cms_cat_history(callback, int(m.group(1)), int(m.group(2)))

        elif m := re.match(r"^cms:cat:hist_view:(\d+):(\d+)$", data):
            await cms_cat_h.callback_cms_cat_history_view(callback, int(m.group(1)), int(m.group(2)))
            
        elif m := re.match(r"^cms:cat:edit_(\w+):(\d+)$", data):
            await cms_cat_h.callback_cms_cat_edit_field(callback, m.group(1), int(m.group(2)))

        elif data == "cms:prompts":
            await cms_h.callback_cms_prompts(callback)

        elif m := re.match(r"^cms:prompt:edit:(.+)$", data):
            await cms_h.callback_cms_prompt_edit(callback, m.group(1))

        # ── CMS Scheduler ───────────────────────
        elif data == "cms:schedules":
            await cms_h.callback_cms_schedules(callback)

        elif data == "cms:sch:add":
            await cms_h.callback_cms_schedule_add(callback)

        elif m := re.match(r"^cms:sch:del:(\d+)$", data):
            await cms_h.callback_cms_schedule_del(callback, int(m.group(1)))

        elif m := re.match(r"^cms:sch:type:(.+)$", data):
            await cms_h.callback_cms_schedule_type(callback, m.group(1))

        elif m := re.match(r"^cms:sch:cat:([^:]+):(.+)$", data):
            await cms_h.callback_cms_schedule_cat(callback, m.group(1), m.group(2))

        # ── Unknown ─────────────────────────────
        else:
            await callback.message.reply("دستور نامشخص.")
            logger.warning(f"Unhandled callback: {data}")
