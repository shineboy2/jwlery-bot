# System Architecture Document: Smart Boutique ERP Bot

---

## 1. Overview

**Smart Boutique ERP Bot** یک سیستم ERP/CRM جامع است که به عنوان ربات پیام‌رسان **بله (Bale)** اجرا می‌شود. این سیستم برای مدیریت یکپارچه فروشگاه آنلاین جواهرات و اکسسوری طراحی شده و شامل مدیریت محصولات، سفارشات، مشتریان، محتوای کانال، حسابداری و گزارش‌دهی است.

---

## 2. High-Level Architecture

سیستم از یک معماری **لایه‌ای (Layered Architecture)** تبعیت می‌کند:

```
┌─────────────────────────────────────────────────────────────┐
│                    Bale Messenger Client                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ Webhook / Long Polling
┌──────────────────────────▼──────────────────────────────────┐
│              Presentation Layer (Bot Interface)              │
│  loader.py → on_message() / on_callback()                   │
│  handlers/ → admin, product, order, customer, cms, finance  │
│  keyboards/ → inline.py (InlineKeyboardMarkup builders)     │
│  middlewares/ → auth.py (admin_required decorators)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              Business Logic Layer (Services)                 │
│  ai_service.py        → Google Gemini integration           │
│  channel_service.py   → Product publishing to channel       │
│  cms_service.py       → ScheduledPost publishing            │
│  order_service.py     → Reservation, status transitions     │
│  product_service.py   → Product lifecycle                   │
│  finance_service.py   → P&L calculation, partner equity     │
│  logistics_service.py → CSV export, bulk tracking           │
│  report_service.py    → Sales, inventory, profit reports    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              Data Access Layer (CRUD / DAO)                   │
│  crud.py → SQLAlchemy async queries                         │
│  models.py → 16 ORM models                                  │
│  base.py → AsyncEngine + SessionFactory                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              Storage Layer                                    │
│  PostgreSQL 15+ (Docker)                                     │
│  Alembic (schema migrations)                                 │
└─────────────────────────────────────────────────────────────┘
```

### لایه‌ها

| لایه | مسئولیت | فایل‌های کلیدی |
|------|---------|----------------|
| **Presentation** | تعامل با کاربر از طریق بله، مسیریابی پیام و Callback، کیبوردهای Inline، کنترل دسترسی | `loader.py`, `handlers/*`, `keyboards/inline.py`, `middlewares/auth.py` |
| **Business Logic** | قوانین کسب‌وکار، محاسبات مالی، فرمت‌دهی محتوا، یکپارچه‌سازی AI | `services/*` |
| **Data Access** | عملیات CRUD غیرهمزمان با SQLAlchemy | `crud.py`, `models.py`, `base.py` |
| **Storage** | ذخیره‌سازی دائمی داده‌ها، مدیریت schema | PostgreSQL, Alembic |

---

## 3. Bot Framework: `python-bale-bot`

### چرا `python-bale-bot`؟
برخلاف طراحی اولیه (که با Aiogram بود)، سیستم نهایی از **SDK رسمی بله** (`python-bale-bot 2.5.0`) استفاده می‌کند. این SDK مستقیماً با API بله ارتباط دارد و نیازی به تغییر Base URL ندارد.

### Event-Based Routing
بات از سیستم رویدادی `python-bale-bot` استفاده می‌کند:

```python
# loader.py
bot = Bot(token=settings.bale_bot_token)

@bot.event
async def on_message(message):   # همه پیام‌های متنی
    ...

@bot.event
async def on_callback(callback): # همه Callback Queries
    ...

@bot.event
async def on_ready():            # بات آماده شد
    start_scheduler()
```

### مسیریابی پیام‌ها (Message Routing)
`loader.py` به عنوان **Central Router** عمل می‌کند:

1. **پیام‌ها (`on_message`):** ابتدا `/start` بررسی می‌شود. سپس پیام به ترتیب اولویت به هندلرهای FSM ارسال می‌شود. هر هندلر اگر پیام متعلق به state فعالش باشد، `True` برمی‌گرداند و زنجیره متوقف می‌شود:
   ```
   product → category → order → customer → cms_create → queue → buffer → finance → cms → cms_cat → admin
   ```

2. **Callbackها (`on_callback`):** با الگوی `callback.data` و regex pattern matching مسیریابی می‌شود:
   ```
   menu:*    → منوهای اصلی
   cat:*     → دسته‌بندی
   prod:*    → محصول
   ord:*     → سفارش
   cust:*    → مشتری
   rep:*     → گزارش
   cms:*     → مدیریت محتوا
   fin:*     → مالی
   ```

---

## 4. FSM (Finite State Machine) — مدیریت وضعیت

### طراحی In-Memory
از آنجا که `python-bale-bot` (**برخلاف Aiogram**) سیستم FSM داخلی ندارد، مدیریت State به صورت **In-Memory** با دیکشنری‌های Python پیاده‌سازی شده:

```python
# مثال از product.py
_product_states: dict[int, dict] = {}  # key = chat_id

# ست کردن state
_product_states[chat_id] = {"step": "WAITING_IMAGES", "data": {...}}

# بررسی state
async def handle_product_message(message):
    state = _product_states.get(chat_id)
    if not state:
        return False  # این هندلر مسئول نیست
    # پردازش بر اساس state["step"]
    return True
```

### هندلرهای FSM‌دار

| هندلر | State Dictionary | مراحل اصلی |
|--------|-----------------|-------------|
| `product.py` | `_product_states` | انتخاب دسته → تصاویر → قیمت خرید → قیمت فروش → موجودی → توضیحات → ویژگی‌ها → AI کپشن → تأیید |
| `order.py` | `_order_states` | انتخاب مشتری → انتخاب محصول → تعداد → قیمت → تکرار/تمام → تخفیف → هزینه ارسال → تأیید |
| `customer.py` | `_customer_states` | نام → تلفن → آدرس → ... |
| `category.py` | `_cat_states` | نام → پیشوند → ویژگی‌ها |
| `cms.py` | `_cms_states` | موضوع → تولید AI → ویرایش → ذخیره |
| `cms_create.py` | `_cms_create_states` | انتخاب دسته → متن/تصویر → بافر/صف/انتشار |
| `queue_handler.py` | `_queue_edit_states` | ویرایش کپشن/تصویر پست صف |
| `buffer_handler.py` | `_buffer_edit_states` | ویرایش کپشن/تصویر پست بافر |
| `finance.py` | `_finance_states` | ثبت هزینه / ثبت شریک / تراکنش |
| `cms_category.py` | `_cms_cat_states` | مدیریت دسته‌بندی محتوا |

### پاک‌سازی State
هنگام فشردن `/start` یا بازگشت به منوی اصلی (`menu:*`)، تمام Stateها پاک می‌شوند:

```python
def clear_all_states(chat_id: int):
    prod_h._product_states.pop(chat_id, None)
    ord_h._order_states.pop(chat_id, None)
    cust_h._customer_states.pop(chat_id, None)
    # ... سایر هندلرها
```

---

## 5. Database Schema

### Engine & Session
```python
# base.py
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

### Naming Convention (Alembic-Compatible)
```python
convention = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

### Entity Relationship Diagram

```
┌──────────┐      ┌──────────────┐      ┌────────────┐
│  admins  │      │  categories  │──1:N─│  products   │
└──────────┘      └──────────────┘      └─────┬──────┘
                                              │ 1:N
                                    ┌─────────┴──────────┐
                                    │                    │
                              ┌─────▼──────┐     ┌──────▼────────┐
                              │product_images│    │scheduled_posts│
                              └────────────┘     └───────────────┘

┌─────────┐──1:N──┌──────────┐──1:N──┌─────────────┐
│  users  │       │  orders  │       │ order_items  │──N:1──products
└─────────┘       └──────────┘       └─────────────┘

┌───────────────────┐      ┌────────────┐──1:N──┌──────────┐
│ expense_categories│──1:N─│  expenses  │       │          │
└───────────────────┘      └────────────┘       │          │
                                                │          │
┌──────────┐──1:N──┌──────────────────────┐     │          │
│ partners │       │ partner_transactions │     │          │
└──────────┘       └──────────────────────┘     │          │

┌────────────────────┐  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
│ content_categories │  │ publish_schedules│  │system_configs│  │  ai_prompts  │
└────────────────────┘  └──────────────────┘  └──────────────┘  └──────────────┘
```

### جداول به تفصیل

#### Domain Core
| جدول | ستون‌های کلیدی | روابط |
|------|----------------|-------|
| `admins` | `chat_id` (unique), `role` (SUPER_ADMIN/ADMIN), `is_active` | — |
| `categories` | `name`, `prefix` (unique, 5 char), `attributes` (JSONB) | → products |
| `products` | `sku` (unique), `buy_price`, `base_sell_price`, `stock_quantity`, `reserved_quantity`, `status` (DRAFT/ACTIVE/INACTIVE), `dynamic_attributes` (JSONB), `channel_message_id`, `last_published_at` | → category, → images, → order_items, → scheduled_posts |
| `product_images` | `file_id`, `is_primary`, `sort_order` | → product |
| `users` | `chat_id` (unique), `phone_number`, `full_name`, `address`, `postal_code`, `birth_date`, `notes`, `ltv` | → orders |
| `orders` | `total_amount`, `discount_amount`, `shipping_cost`, `status` (PENDING_PAYMENT/PAID/PAID_HELD/SHIPPED/DELIVERED/CANCELLED), `sales_channel` (ONLINE/IN_PERSON), `tracking_code`, `payment_receipt_file_id`, `payment_card_last4` | → user, → items |
| `order_items` | `quantity`, `sold_price`, `buy_price` | → order, → product |

#### CMS (Content Management System)
| جدول | ستون‌های کلیدی | توضیح |
|------|----------------|-------|
| `scheduled_posts` | `post_type` (TEXT/IMAGE), `category`, `content_text`, `image_file_id`, `queue_order`, `publish_time`, `status` (draft/buffered/queued/published/cancelled/failed) | ذخیره تمام پست‌های CMS |
| `content_categories` | `name`, `code` (unique), `prompt_template` | دسته‌بندی محتوا با قالب AI |
| `publish_schedules` | `slot_type` (PRODUCT/POST), `time` (HH:MM), `count`, `post_category`, `is_active` | برنامه زمان‌بندی انتشار |
| `ai_prompts` | `name` (unique), `content` | قالب‌های پرامپت AI |
| `system_configs` | `key` (unique), `value` | تنظیمات عمومی (مثل product_cooldown_days) |

#### Finance (حسابداری)
| جدول | ستون‌های کلیدی | توضیح |
|------|----------------|-------|
| `expense_categories` | `name`, `type` (FIXED/VARIABLE), `is_active` | دسته‌بندی هزینه‌های عملیاتی |
| `expenses` | `amount`, `description`, `expense_date`, `receipt_file_id` | ثبت هزینه |
| `partners` | `name`, `equity_share` (%), `initial_capital`, `is_active` | شرکا/سهامداران |
| `partner_transactions` | `amount`, `type` (DRAWING/SALARY/INJECTION), `description` | برداشت و تزریق سرمایه |

---

## 6. Services Layer

### 6.1 AI Service (`ai_service.py`)
- **Google Gemini API** (`google-generativeai`) برای تولید محتوا
- دو تابع اصلی:
  - `generate_product_description()`: کپشن محصول با داده‌های DB به عنوان **تنها منبع حقیقت**
  - `generate_cms_post()`: تولید پست CMS بر اساس موضوع و قالب پرامپت
- **قانون کلیدی:** AI فقط **کپی‌رایتر** است و هرگز داده جدید (قیمت، موجودی) اختراع نمی‌کند

### 6.2 Channel Service (`channel_service.py`)
- فرمت‌دهی و ارسال پست محصول به کانال بله
- استفاده از `file_id` ذخیره‌شده برای ارسال سریع بدون آپلود مجدد
- بروزرسانی `channel_message_id` و `last_published_at` محصول پس از انتشار

### 6.3 CMS Service (`cms_service.py`)
- انتشار `ScheduledPost` به کانال (تصویر + کپشن یا فقط متن)
- بروزرسانی وضعیت پست به `published` و ثبت زمان انتشار

### 6.4 Order Service (`order_service.py`)
- **رزرو موجودی:** هنگام ثبت سفارش، `reserved_quantity` محصول افزایش می‌یابد
- **آزادسازی رزرو:** هنگام لغو سفارش، موجودی آزاد می‌شود
- **تغییر وضعیت:** بررسی انتقال‌های مجاز بین وضعیت‌ها
- **تأیید پرداخت:** کاهش `stock_quantity` و صفر شدن `reserved_quantity`

### 6.5 Finance Service (`finance_service.py`)
- **محاسبه P&L:** درآمد − COGS − ارسال = سود ناخالص; سود ناخالص − OPEX = سود خالص
- **محاسبه سهم شرکا:** سود خالص × درصد سهم − برداشت‌ها + آورده‌های جدید = مبلغ قابل پرداخت
- **فرمت‌دهی گزارش:** خروجی فارسی با اعداد فارسی و نمادهای بصری

### 6.6 Logistics Service (`logistics_service.py`)
- **خروجی CSV:** تولید فایل CSV از سفارشات `PAID`/`PAID_HELD` برای ارسال به پست
- **Bulk Tracking:** پردازش کدهای رهگیری دسته‌ای (فرمت: `order_id: tracking_code`)

### 6.7 Report Service (`report_service.py`)
- گزارش سود خالص (ماهانه / کل)
- گزارش موجودی انبار (موجود vs رزرو)
- آمار فروش (هفتگی / ماهانه)

---

## 7. Scheduler (وظایف زمان‌بندی‌شده)

### فناوری: `APScheduler` (AsyncIOScheduler)

```python
# scheduler.py
scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(cancel_expired_orders, 'interval', minutes=30)
    scheduler.add_job(publish_pending_posts, 'interval', minutes=1)
    scheduler.add_job(publish_dynamic_slots, 'interval', minutes=1)
    scheduler.start()
```

### وظایف

| وظیفه | بازه | عملکرد |
|-------|------|--------|
| `cancel_expired_orders` | ۳۰ دقیقه | لغو سفارشات `PENDING_PAYMENT` بیشتر از ۲ ساعت + آزادسازی رزرو |
| `publish_pending_posts` | ۱ دقیقه | انتشار `ScheduledPost`هایی که `publish_time` مشخص دارند و زمانشان رسیده |
| `publish_dynamic_slots` | ۱ دقیقه | بررسی `PublishSchedule` فعال → انتشار خودکار محصولات (با Cooldown) یا پست‌های صف |

### Dynamic Slots Logic
```
PublishSchedule { slot_type, time, count, post_category }

اگر slot_type == PRODUCT:
  → محصولات ACTIVE با موجودی > 0 که Cooldown سپری شده
  → مرتب‌سازی: last_published_at ASC (NULLs FIRST)
  → فیلتر اختیاری بر اساس دسته‌بندی

اگر slot_type == POST:
  → پست‌های QUEUED در دسته‌بندی مشخص بدون publish_time
  → مرتب‌سازی: created_at ASC
```

---

## 8. Authentication & Authorization

### Decorator-Based
```python
# middlewares/auth.py

@admin_required        # فقط ادمین‌های فعال
async def some_handler(update, admin=None): ...

@super_admin_required  # فقط SUPER_ADMIN
async def admin_management(update, admin=None): ...
```

### جریان احراز هویت
1. دکوراتور `chat_id` را از `message` یا `callback` استخراج می‌کند
2. در جدول `admins` جستجو می‌کند
3. اگر ادمین فعال نباشد → پیام **بی‌صدا** نادیده گرفته می‌شود
4. در صورت موفقیت، شیء `admin` به هندلر تزریق می‌شود

### ثبت اولین Super Admin
- هنگام اولین `/start`، اگر `chat_id` برابر با `SUPER_ADMIN_CHAT_ID` (از `.env`) باشد، به عنوان `SUPER_ADMIN` در دیتابیس ثبت می‌شود

---

## 9. Configuration Management

### Pydantic Settings
```python
# config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    
    bale_bot_token: str
    super_admin_chat_id: int
    database_url: str
    channel_id: int
    channel_username: str
    payment_card_number: str
    payment_card_holder: str
    gemini_api_key: str | None = None
```

### Runtime Configuration (`system_configs`)
تنظیمات قابل تغییر در زمان اجرا (بدون ریستارت):
- `product_cooldown_days`: حداقل فاصله بین انتشارهای مجدد یک محصول (پیش‌فرض: ۴ روز)

---

## 10. Deployment Architecture

```
┌────────────────────────────────┐
│         Ubuntu Server          │
│                                │
│  ┌──────────────────────────┐  │
│  │  Docker Compose          │  │
│  │                          │  │
│  │  ┌────────┐  ┌────────┐  │  │
│  │  │  Bot   │  │  PG 15 │  │  │
│  │  │ Python │→ │ Alpine │  │  │
│  │  │  3.11  │  │        │  │  │
│  │  └────────┘  └────────┘  │  │
│  │      depends_on:         │  │
│  │      condition:          │  │
│  │      service_healthy     │  │
│  └──────────────────────────┘  │
│                                │
│  Volume: pgdata (persistent)   │
└────────────────────────────────┘
```

### Startup Scripts
- **`start.sh`**: ساده — Docker DB up → Alembic migrate → Run bot
- **`start_bot.sh`**: Auto-start — Docker start → Kill old process → nohup bot → PID log
- **Health Check:** PostgreSQL با `pg_isready` هر ۱۰ ثانیه بررسی می‌شود

---

## 11. Data Flow Examples

### ثبت محصول جدید
```
Admin /start → 📦 مدیریت محصولات → ➕ ثبت محصول جدید
  → انتخاب دسته‌بندی (Inline Keyboard)
  → ارسال تصاویر (چندگانه) → "تمام"
  → قیمت خرید → قیمت فروش → موجودی → توضیحات
  → ویژگی‌های داینامیک دسته (JSONB)
  → [اختیاری] تولید کپشن AI (Gemini)
  → تأیید نهایی
  → ذخیره در DB (status: DRAFT|ACTIVE)
  → [اختیاری] انتشار فوری یا صف‌بندی در CMS
```

### چرخه سفارش
```
ثبت سفارش → PENDING_PAYMENT
  → reserved_quantity += quantity
  ┌── [پرداخت تأیید شد] → PAID → stock_quantity -= quantity
  │     → [ارسال شد] → SHIPPED (+ tracking_code)
  │         → [تحویل داده شد] → DELIVERED
  └── [لغو / Timeout 2h] → CANCELLED
        → reserved_quantity -= quantity (آزادسازی)
```

---

## 12. Key Design Decisions

| تصمیم | دلیل |
|-------|------|
| `python-bale-bot` به جای Aiogram | SDK رسمی بله، بدون نیاز به هک Base URL |
| FSM In-Memory (dict) | سادگی؛ بله FSM داخلی ندارد؛ Single-Instance فعلاً کافی است |
| JSONB برای `dynamic_attributes` | هر دسته‌بندی ویژگی‌های متفاوتی دارد؛ schema انعطاف‌پذیر |
| `file_id` به جای ذخیره فایل | استفاده از Storage سرور بله؛ بدون نیاز به Object Storage |
| `buy_price` در `order_items` | ثبت بهای تمام شده در لحظه فروش (نه قیمت فعلی) برای محاسبه دقیق سود |
| Decorator برای Auth | جداسازی منطق احراز هویت از هندلرها |
| APScheduler | اجرای وظایف دوره‌ای بدون نیاز به Celery/Redis |

---

## 13. Scalability Considerations

### محدودیت‌های فعلی
- **FSM In-Memory:** در صورت ریستارت بات، Stateهای فعال از دست می‌روند
- **Single Instance:** فقط یک Instance از بات در هر لحظه قابل اجراست
- **عدم Worker Queue:** پردازش AI و ارسال به کانال Synchronous (در Context هندلر) است

### مسیر مقیاس‌پذیری آینده
1. **مهاجرت FSM به Redis:** حفظ State بین ریستارت‌ها و امکان Multi-Instance
2. **صف وظایف (Task Queue):** Celery/RQ برای عملیات سنگین (AI, ارسال به کانال)
3. **پرداخت آنلاین بله:** `bot.send_invoice()` + `successful_payment` event listener
4. **Horizontal Scaling:** با Redis FSM و Task Queue، چند Instance قابل اجراست

---

## 14. Security

- **No Direct SQL:** تمام کوئری‌ها از طریق SQLAlchemy ORM (محافظت در برابر SQL Injection)
- **Admin-Only Access:** تمام هندلرها با دکوراتور محافظت می‌شوند
- **Silent Rejection:** کاربران غیرمجاز هیچ پاسخی دریافت نمی‌کنند
- **Environment Variables:** اطلاعات حساس (توکن، DB URL، API Key) در `.env` نگهداری می‌شوند
- **`.gitignore`:** فایل `.env` از Git حذف شده است
