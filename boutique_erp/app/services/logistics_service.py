"""
Logistics Service: Export orders, process bulk tracking codes.
"""
import logging
import csv
import io
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories import order_repo

logger = logging.getLogger(__name__)

async def export_paid_orders_csv(session: AsyncSession) -> bytes:
    """Generate CSV file for PAID and PAID_HELD orders."""
    from app.database.models import Order
    from sqlalchemy import select

    result = await session.execute(
        select(Order).where(Order.status.in_(["PAID", "PAID_HELD"]))
    )
    orders = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order ID", "Customer Name", "Customer Chat ID", 
        "Status", "Total Price", "Shipping Cost", "Items"
    ])

    for order in orders:
        items_str = " | ".join([f"{item.product.sku} x {item.quantity}" for item in order.items])
        writer.writerow([
            order.id,
            order.user.full_name,
            order.user.chat_id,
            order.status,
            order.total_amount,
            order.shipping_cost,
            items_str
        ])

    return output.getvalue().encode('utf-8-sig')


async def process_bulk_tracking_codes(session: AsyncSession, text: str) -> dict:
    """
    Process multi-line text:
    Format:
    order_id: tracking_code
    12: 12345678901234567890
    
    Returns: {"success": int, "failed": int, "errors": list}
    """
    lines = text.strip().split('\n')
    success_count = 0
    failed_count = 0
    errors = []

    for line in lines:
        if not line.strip():
            continue
        parts = line.split(":")
        if len(parts) != 2:
            parts = line.split("-")
            if len(parts) != 2:
                failed_count += 1
                errors.append(f"فرمت نامعتبر: {line}")
                continue
                
        try:
            order_id = int(parts[0].strip())
            tracking_code = parts[1].strip()
            
            order = await order_repo.update_order_status(session, order_id, "SHIPPED", tracking_code=tracking_code)
            if order:
                success_count += 1
            else:
                failed_count += 1
                errors.append(f"سفارش {order_id} یافت نشد یا خطا در آپدیت.")
        except ValueError:
            failed_count += 1
            errors.append(f"آیدی نامعتبر: {line}")

    return {
        "success": success_count,
        "failed": failed_count,
        "errors": errors
    }
