# 💎 Smart Boutique ERP Bot

یک ربات **ERP / CRM** جامع برای مدیریت کسب‌وکار بوتیک جواهرات و اکسسوری بر بستر پیام‌رسان **بله (Bale)**
ساخته‌شده با کتابخانه `python-bale-bot` و معماری لایه‌ای قابل توسعه.

---

## ✨ ویژگی‌ها

### 📦 مدیریت محصولات
- ثبت محصول با چند تصویر (Media-First) و تولید خودکار کد **SKU** بر اساس پیشوند دسته‌بندی
- فرایند ثبت چندمرحله‌ای (**FSM**): انتخاب دسته‌بندی → ارسال تصاویر → قیمت خرید/فروش → موجودی → توضیحات → ویژگی‌های داینامیک
- ویرایش محصولات، تغییر وضعیت (Draft/Active/Inactive)، مدیریت موجودی
- جستجوی محصول بر اساس نام یا SKU
- صفحه‌بندی لیست محصولات

### 🗂 دسته‌بندی داینامیک
- افزودن/ویرایش/غیرفعال‌سازی دسته‌بندی با پیشوند SKU اختصاصی
- تعریف **ویژگی‌های داینامیک** (JSONB) برای هر دسته (مثلاً: جنس، رنگ، سایز)
- محصولات هر دسته ویژگی‌های متفاوتی دریافت می‌کنند

### 📢 مدیریت محتوا و انتشار در کانال (CMS)
- **تولید محتوا با هوش مصنوعی:** یکپارچه‌سازی با Google Gemini برای نوشتن کپشن حرفه‌ای محصولات و پست‌های کانال
- **سیستم دسته‌بندی محتوا:** تعریف دسته‌بندی‌های سفارشی برای پست‌ها (معرفی محصول، صبح‌بخیر، ...) با قالب پرامپت اختصاصی
- **صف انتشار (Queue):** مدیریت صف پست‌ها به ترتیب اولویت، جابجایی، ویرایش کپشن و تصویر
- **بافر (Buffer):** نگهداری پیش‌نویس‌ها قبل از انتقال به صف
- **زمان‌بندی خودکار:** تعریف اسلات‌های زمانی (ساعت و تعداد) برای انتشار خودکار محصولات و پست‌ها با `APScheduler`
- **Cooldown هوشمند:** جلوگیری از انتشار مجدد محصول قبل از سپری شدن دوره Cooldown (قابل تنظیم)
- **انتشار فوری و انتشار زمان‌بندی‌شده:** هر پست می‌تواند فوری یا در زمان مشخص منتشر شود

### 🛒 مدیریت سفارشات
- ثبت سفارش جدید: انتخاب مشتری → افزودن محصولات → تعیین قیمت فروش → تخفیف → هزینه ارسال → تأیید
- **رزرو موجودی خودکار** هنگام ثبت سفارش و آزادسازی در صورت لغو
- **چرخه وضعیت سفارش:** `PENDING_PAYMENT` → `PAID` / `PAID_HELD` → `SHIPPED` → `DELIVERED` / `CANCELLED`
- ثبت **رسید پرداخت** (تصویر) و شماره کارت مبدأ
- **ورود دسته‌ای کد رهگیری پستی** (Bulk Tracking)
- **خروجی CSV** سفارشات پرداخت‌شده برای لجستیک
- **لغو خودکار** سفارشات منتظر پرداخت پس از ۲ ساعت (Scheduler)
- کانال فروش: آنلاین / حضوری

### 👥 CRM مشتریان
- ثبت مشتری جدید / جستجو بر اساس نام، شماره تلفن، یا Chat ID
- پروفایل مشتری: نام، تلفن، آدرس، کدپستی، تاریخ تولد، یادداشت
- مشاهده تاریخچه سفارشات هر مشتری
- محاسبه **ارزش عمر مشتری (LTV)** به صورت خودکار
- ویرایش فیلدهای مشتری

### 💰 حسابداری و مالی
- **صورت سود و زیان (P&L):** محاسبه درآمد، بهای تمام شده کالا (COGS)، هزینه ارسال، تخفیفات، سود ناخالص، هزینه‌های عملیاتی (OPEX) و سود خالص
- **دسته‌بندی هزینه‌ها:** ثبت هزینه‌ها به تفکیک دسته (بسته‌بندی، پست، تبلیغات، ...) با نوع ثابت/متغیر
- **مدیریت شرکا:** تعریف سهامداران، درصد سهم، سرمایه اولیه
- **تراکنش‌های شرکا:** ثبت برداشت (Drawing)، تزریق سرمایه (Injection)
- **گزارش سهم شرکا:** محاسبه خودکار سهم سود، کسر برداشت‌ها، محاسبه مبلغ قابل پرداخت
- فیلتر گزارش: ماهانه / کل دوره

### 📊 گزارش‌ها
- گزارش سود خالص (ماهانه / کل)
- گزارش موجودی انبار با اعداد فارسی
- آمار فروش هفتگی و ماهانه

### 🔐 سیستم نقش‌ها و احراز هویت
| نقش | دسترسی‌ها |
|-----|-----------|
| `SUPER_ADMIN` | همه دسترسی‌ها + افزودن/حذف ادمین |
| `ADMIN` | مدیریت محصول، سفارش، مشتری، CMS، مالی، گزارش |

- احراز هویت از طریق **Decorator** (`admin_required` / `super_admin_required`) روی هندلرها
- Super Admin اولیه از طریق `SUPER_ADMIN_CHAT_ID` در متغیرهای محیطی تعریف می‌شود

---

## 🛠 پشته فناوری

| ابزار | نسخه | توضیح |
|-------|-------|-------|
| **Python** | 3.11+ | زبان اصلی |
| `python-bale-bot` | 2.5.0 | SDK ربات بله |
| `SQLAlchemy[asyncio]` | 2.0.36 | ORM غیرهمزمان |
| `asyncpg` | 0.29.0 | درایور PostgreSQL |
| `alembic` | 1.13.3 | مایگریشن دیتابیس |
| `pydantic-settings` | 2.5.0 | مدیریت تنظیمات از `.env` |
| `google-generativeai` | 0.8.3 | یکپارچه‌سازی Gemini AI |
| `APScheduler` | — | زمان‌بندی وظایف (Cancel Expired Orders, Auto-Publish) |
| **PostgreSQL** | 15+ (Docker) | پایگاه داده اصلی |
| **Docker & Docker Compose** | — | استقرار و ایزوله‌سازی |

---

## 📁 ساختار پروژه

```text
boutique_erp/
├── app/
│   ├── main.py                          # نقطه ورود: لاگینگ + اجرای بات
│   ├── core/
│   │   ├── config.py                    # Pydantic Settings (خواندن .env)
│   │   ├── constants.py                 # Enums: AdminRole, ProductStatus, OrderStatus
│   │   └── scheduler.py                 # APScheduler: لغو خودکار سفارش، انتشار زمان‌بندی‌شده
│   ├── database/
│   │   ├── base.py                      # Async SQLAlchemy Engine + Session Factory
│   │   ├── models.py                    # ۱۳ مدل ORM (جدول زیر)
│   │   └── crud.py                      # توابع CRUD (DAO)
│   ├── bot/
│   │   ├── loader.py                    # ساخت Bot instance + ثبت هندلرها + مسیریابی Callback
│   │   ├── handlers/
│   │   │   ├── admin.py                 # /start، منوی اصلی، مدیریت ادمین‌ها
│   │   │   ├── category.py              # CRUD دسته‌بندی محصولات
│   │   │   ├── product.py               # ثبت/ویرایش/جستجوی محصول (FSM)
│   │   │   ├── channel.py               # انتشار مستقیم محصول به کانال
│   │   │   ├── order.py                 # چرخه سفارشات (FSM)
│   │   │   ├── customer.py              # CRM مشتریان (FSM)
│   │   │   ├── report.py                # گزارشات سود، موجودی، فروش
│   │   │   ├── cms.py                   # منوی CMS، پرامپت AI، تنظیمات
│   │   │   ├── cms_category.py          # مدیریت دسته‌بندی‌های محتوا
│   │   │   ├── cms_create.py            # ایجاد محتوای جدید (ویزارد/فوروارد)
│   │   │   ├── queue_handler.py         # مدیریت صف انتشار
│   │   │   ├── buffer_handler.py        # مدیریت بافر (پیش‌نویس‌ها)
│   │   │   └── finance.py               # ثبت هزینه، شرکا، گزارش P&L
│   │   ├── keyboards/
│   │   │   └── inline.py                # سازنده‌های InlineKeyboardMarkup
│   │   └── middlewares/
│   │       └── auth.py                  # دکوراتورهای admin_required / super_admin_required
│   ├── services/
│   │   ├── ai_service.py                # یکپارچه‌سازی Google Gemini
│   │   ├── channel_service.py           # فرمت‌دهی و ارسال پست محصول به کانال
│   │   ├── cms_service.py               # انتشار ScheduledPost به کانال
│   │   ├── finance_service.py           # محاسبه P&L و سهم شرکا
│   │   ├── logistics_service.py         # خروجی CSV و ورود دسته‌ای کد رهگیری
│   │   ├── order_service.py             # منطق رزرو موجودی و تغییر وضعیت سفارش
│   │   ├── product_service.py           # منطق کسب‌وکار محصولات
│   │   └── report_service.py            # محاسبات گزارش‌ها (سود، موجودی، فروش)
│   └── utils/
│       ├── sku_generator.py             # تولید خودکار SKU (پیشوند دسته + شماره ترتیبی)
│       └── formatters.py                # تبدیل اعداد به فارسی، فرمت قیمت، قالب پست کانال
├── alembic/
│   ├── env.py                           # تنظیمات Alembic
│   ├── script.py.mako                   # قالب مایگریشن
│   └── versions/                        # فایل‌های مایگریشن
├── alembic.ini                          # تنظیمات Alembic
├── docker-compose.yml                   # PostgreSQL + Bot
├── Dockerfile                           # Image اپلیکیشن
├── requirements.txt                     # وابستگی‌های Python
├── start.sh                             # اسکریپت راه‌اندازی (DB + Migration + Bot)
├── seed.py / seed_categories.py / seed_finance.py  # اسکریپت‌های Seed دیتابیس
├── .env.example                         # نمونه متغیرهای محیطی
└── .gitignore
```

---

## 🗄 مدل‌های دیتابیس (۱۳ جدول)

| # | جدول | توضیح |
|---|-------|-------|
| 1 | `admins` | ادمین‌های ربات (chat_id, role, is_active) |
| 2 | `categories` | دسته‌بندی محصولات (name, prefix, attributes JSONB) |
| 3 | `products` | محصولات (sku, price, stock, status, dynamic_attributes JSONB, channel_message_id) |
| 4 | `product_images` | تصاویر محصول (file_id, is_primary, sort_order) |
| 5 | `users` | مشتریان / کاربران (chat_id, phone, address, birth_date, ltv) |
| 6 | `orders` | سفارشات (status, sales_channel, payment_receipt, tracking_code) |
| 7 | `order_items` | اقلام سفارش (quantity, sold_price, buy_price) |
| 8 | `scheduled_posts` | پست‌های CMS (post_type, category, content_text, image_file_id, status, queue_order) |
| 9 | `ai_prompts` | قالب‌های پرامپت AI (name, content) |
| 10 | `expense_categories` | دسته‌بندی هزینه‌ها (name, type: FIXED/VARIABLE) |
| 11 | `expenses` | ثبت هزینه‌ها (amount, description, receipt_file_id) |
| 12 | `partners` | شرکا (name, equity_share%, initial_capital) |
| 13 | `partner_transactions` | تراکنش شرکا (type: DRAWING/INJECTION, amount) |
| 14 | `content_categories` | دسته‌بندی محتوای CMS (name, code, prompt_template) |
| 15 | `publish_schedules` | اسلات‌های زمان‌بندی انتشار (slot_type, time, count, post_category) |
| 16 | `system_configs` | تنظیمات سیستمی key-value (مثل product_cooldown_days) |

---

## 🚀 راه‌اندازی سریع

### پیش‌نیازها
- Python 3.11+
- Docker & Docker Compose
- توکن ربات بله ([ساخت ربات](https://ble.ir/botfather))

### ۱. ساخت فایل `.env`

```bash
cp .env.example .env
# ویرایش با مقادیر واقعی
```

```env
BALE_BOT_TOKEN=your_bot_token_here
SUPER_ADMIN_CHAT_ID=123456789
DATABASE_URL=postgresql+asyncpg://botuser:botpassword@localhost:5432/boutique_erp
CHANNEL_ID=-1001234567890
CHANNEL_USERNAME=@your_channel
PAYMENT_CARD_NUMBER=6037-XXXX-XXXX-XXXX
PAYMENT_CARD_HOLDER=نام صاحب کارت
# اختیاری: GEMINI_API_KEY=your_gemini_api_key
```

### ۲. راه‌اندازی با اسکریپت (پیشنهادی)

```bash
chmod +x start.sh
./start.sh
```

این اسکریپت به ترتیب:
1. دیتابیس PostgreSQL را با Docker بالا می‌آورد
2. مایگریشن‌های Alembic را اعمال می‌کند
3. ربات را اجرا می‌کند

### ۳. راه‌اندازی دستی

```bash
# بالا آوردن دیتابیس
docker compose up -d db

# نصب وابستگی‌ها
pip install -r requirements.txt

# اعمال مایگریشن‌ها
alembic upgrade head

# اجرای ربات
python3 -m app.main
```

---

## 🐳 اجرا با Docker (Production)

```bash
docker compose up --build -d
```

---

## ⏰ وظایف زمان‌بندی‌شده (Scheduler)

سه وظیفه توسط `APScheduler` به صورت خودکار اجرا می‌شوند:

| وظیفه | بازه | توضیح |
|-------|------|-------|
| `cancel_expired_orders` | هر ۳۰ دقیقه | لغو سفارشات `PENDING_PAYMENT` بیشتر از ۲ ساعت |
| `publish_pending_posts` | هر ۱ دقیقه | انتشار پست‌های زمان‌بندی‌شده که زمانشان رسیده |
| `publish_dynamic_slots` | هر ۱ دقیقه | انتشار خودکار محصولات/پست‌ها مطابق اسلات‌های تعریف‌شده |

---

## 🔮 ویژگی‌های آینده

- **پرداخت آنلاین بله:** `bot.send_invoice()` با `LabeledPrice` ([مستندات](https://docs.python-bale-bot.ir/en/stable/bale.payments.html))
- سیستم کد تخفیف
- اعلان تولد مشتری
- جستجوی inline محصولات
- مهاجرت FSM از حافظه به Redis برای مقیاس‌پذیری افقی

---

## 📄 لایسنس

این پروژه خصوصی است و تحت مالکیت توسعه‌دهنده اصلی قرار دارد.
