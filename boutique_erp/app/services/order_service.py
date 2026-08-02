"""
Order business logic service: create, confirm payment, ship, cancel.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories import order_repo, product_repo
from app.database.models import Order
from app.core.constants import OrderStatus
from app.core.config import settings
from app.bot.handlers.order.renderers import format_payment_message

logger = logging.getLogger(__name__)


async def create_new_order(
    session: AsyncSession,
    user_id: int,
    items: list[dict],
    shipping_cost: int = 0,
    discount: int = 0,
) -> Optional[Order]:
    """
    Create a new order with inventory reservation.

    items = [{"product_id": 1, "quantity": 1, "sold_price": 350000}]

    Steps:
    1. Validate stock availability for all items
    2. Reserve stock for each item (reserved_quantity += quantity)
    3. Create order with status PENDING_PAYMENT
    4. Create order_items
    5. Return order
    """
    # Step 1: Validate stock
    for item in items:
        product = await product_repo.get_product_by_id(session, item["product_id"])
        if not product:
            logger.error(f"Product {item['product_id']} not found")
            return None
        available = product.stock_quantity - product.reserved_quantity
        if available < item["quantity"]:
            logger.warning(
                f"Insufficient stock for product {product.sku}: "
                f"available={available}, requested={item['quantity']}"
            )
            return None

    # Step 2: Reserve stock
    for item in items:
        success = await product_repo.reserve_stock(session, item["product_id"], item["quantity"])
        if not success:
            # Rollback already reserved items
            logger.error(f"Failed to reserve stock for product {item['product_id']}")
            return None

    # Step 3 & 4: Create order and order_items
    order = await order_repo.create_order(
        session=session,
        user_id=user_id,
        items=items,
        shipping_cost=shipping_cost,
        discount_amount=discount,
    )

    logger.info(f"Order {order.id} created for user {user_id}")
    return order


async def confirm_payment(
    session: AsyncSession,
    order_id: int,
    receipt_file_id: Optional[str] = None,
    card_last4: Optional[str] = None,
) -> Optional[Order]:
    """
    Confirm payment for an order.

    Steps:
    1. Set status = PAID
    2. Decrease stock_quantity (actual sell)
    3. Release reserved_quantity
    4. Save receipt info
    """
    order = await order_repo.get_order_by_id(session, order_id)
    if not order:
        return None

    # Update status and payment info
    kwargs = {}
    if receipt_file_id:
        kwargs["payment_receipt_file_id"] = receipt_file_id
    if card_last4:
        kwargs["payment_card_last4"] = card_last4

    was_pending = order.status == OrderStatus.PENDING_PAYMENT.value
    order = await order_repo.update_order_status(session, order_id, OrderStatus.PAID.value, **kwargs)

    # Update actual stock for each item only if it was pending
    if was_pending:
        for item in order.items:
            await product_repo.update_stock(session, item.product_id, -item.quantity)  # Decrease stock
            await product_repo.release_stock(session, item.product_id, item.quantity)   # Release reservation

    logger.info(f"Order {order_id} payment confirmed")
    return order


async def ship_order(session: AsyncSession, order_id: int, tracking_code: str) -> Optional[Order]:
    """Set order status to SHIPPED and save tracking code."""
    order = await order_repo.update_order_status(
        session,
        order_id,
        OrderStatus.SHIPPED.value,
        tracking_code=tracking_code
    )
    if order:
        logger.info(f"Order {order_id} shipped with tracking code {tracking_code}")
    return order


async def cancel_order(session: AsyncSession, order_id: int) -> Optional[Order]:
    """
    Cancel an order and release reserved stock.

    Steps:
    1. Set status = CANCELLED
    2. Release reserved stock back
    """
    order = await order_repo.get_order_by_id(session, order_id)
    if not order:
        return None

    # Only release stock if order was pending (not yet paid/shipped)
    if order.status == OrderStatus.PENDING_PAYMENT.value:
        for item in order.items:
            await product_repo.release_stock(session, item.product_id, item.quantity)

    order = await order_repo.update_order_status(session, order_id, OrderStatus.CANCELLED.value)
    logger.info(f"Order {order_id} cancelled")
    return order


async def get_payment_message(order: Order) -> str:
    """
    Generate payment instruction text with card number.

    🔮 FUTURE: When BALE_PAYMENT_PROVIDER_TOKEN is set in .env,
    use bot.send_invoice() with LabeledPrice instead of this manual card info.
    See: https://docs.python-bale-bot.ir/en/stable/bale.payments.html
    """
    return format_payment_message(
        order=order,
        card_number=settings.payment_card_number,
        card_holder=settings.payment_card_holder,
    )
