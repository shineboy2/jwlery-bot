from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import (
    BigInteger, String, Boolean, Integer, Text,
    ForeignKey, Date, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="ADMIN")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return f"<Admin id={self.id} chat_id={self.chat_id} role={self.role}>"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    prefix: Mapped[str] = mapped_column(String(5), unique=True)
    attributes: Mapped[list] = mapped_column(JSONB, server_default='[]')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name} prefix={self.prefix}>"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    description: Mapped[str] = mapped_column(Text)
    buy_price: Mapped[int] = mapped_column(Integer)  # Rials
    base_sell_price: Mapped[int] = mapped_column(Integer)  # Rials
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    supplier_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT, ACTIVE, INACTIVE
    dynamic_attributes: Mapped[dict] = mapped_column(JSONB, server_default='{}')
    channel_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_published_at: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    images: Mapped[List["ProductImage"]] = relationship(
        "ProductImage", back_populates="product", order_by="ProductImage.sort_order", cascade="all, delete-orphan"
    )
    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="product")
    scheduled_posts: Mapped[List["ScheduledPost"]] = relationship("ScheduledPost", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku}>"


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    file_id: Mapped[str] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="images")

    def __repr__(self) -> str:
        return f"<ProductImage id={self.id} product_id={self.product_id} is_primary={self.is_primary}>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ltv: Mapped[int] = mapped_column(Integer, default=0)  # Lifetime Value in Rials
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} chat_id={self.chat_id} full_name={self.full_name}>"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    total_amount: Mapped[int] = mapped_column(Integer)  # Rials
    discount_amount: Mapped[int] = mapped_column(Integer, default=0)  # Rials
    shipping_cost: Mapped[int] = mapped_column(Integer, default=0)  # Rials
    status: Mapped[str] = mapped_column(String(30), default="PENDING_PAYMENT") # PENDING_PAYMENT, PAID, PAID_HELD, SHIPPED, CANCELLED
    sales_channel: Mapped[str] = mapped_column(String(20), default="ONLINE") # ONLINE, IN_PERSON
    tracking_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_receipt_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_card_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Order id={self.id} user_id={self.user_id} status={self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    sold_price: Mapped[int] = mapped_column(Integer)  # Rials - price at time of sale
    buy_price: Mapped[int] = mapped_column(Integer, default=0)  # Rials - cost of goods at time of sale

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")

    def __repr__(self) -> str:
        return f"<OrderItem id={self.id} order_id={self.order_id} product_id={self.product_id}>"


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id"), nullable=True)
    post_type: Mapped[str] = mapped_column(String(20), default="TEXT")  # TEXT, IMAGE
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # category values:
    #   System: "product_launch" (معرفی محصول), "interactive" (صبح‌بخیر)
    #   Custom: any ContentCategory.code
    content_text: Mapped[str] = mapped_column(Text)
    file_id: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)  # legacy, kept for compat
    image_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # single image file_id
    queue_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # per-category ordering
    publish_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="buffered")
    # status values: draft, buffered, queued, published, cancelled, failed
    published_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    product: Mapped[Optional["Product"]] = relationship("Product", foreign_keys=[product_id])


class AIPrompt(Base):
    __tablename__ = "ai_prompts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class ExpenseCategory(Base):
    """Categories for business expenses (e.g. Packaging, Post, Ads)"""
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[str] = mapped_column(String(20), default="VARIABLE") # FIXED, VARIABLE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="category")


class Expense(Base):
    """Records of business expenses"""
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_categories.id"))
    amount: Mapped[int] = mapped_column(Integer) # Rials
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expense_date: Mapped[datetime] = mapped_column(server_default=func.now())
    receipt_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    category: Mapped["ExpenseCategory"] = relationship("ExpenseCategory", back_populates="expenses")


class Partner(Base):
    """Business partners/owners"""
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    equity_share: Mapped[int] = mapped_column(Integer, default=50) # Percentage
    initial_capital: Mapped[int] = mapped_column(Integer, default=0) # Rials
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    transactions: Mapped[List["PartnerTransaction"]] = relationship("PartnerTransaction", back_populates="partner")


class PartnerTransaction(Base):
    """Partner withdrawals, salary, or capital injection"""
    __tablename__ = "partner_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id"))
    amount: Mapped[int] = mapped_column(Integer) # Rials
    type: Mapped[str] = mapped_column(String(20), default="DRAWING") # DRAWING, SALARY, INJECTION
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    partner: Mapped["Partner"] = relationship("Partner", back_populates="transactions")
class ContentCategory(Base):
    """Dynamically created content categories for CMS posts."""
    __tablename__ = "content_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    prompt_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return f"<ContentCategory id={self.id} code={self.code}>"


class PublishSchedule(Base):
    """Schedules for automated publishing (Products and Queued Posts)"""
    __tablename__ = "publish_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_type: Mapped[str] = mapped_column(String(20)) # PRODUCT, POST
    time: Mapped[str] = mapped_column(String(5)) # HH:MM format, e.g. "10:00"
    count: Mapped[int] = mapped_column(Integer, default=1) # How many items to publish (for products)
    post_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Category to pull from if slot_type is POST
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SystemConfig(Base):
    """Global system configuration (key-value)"""
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text) # JSON serialized value or string
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

