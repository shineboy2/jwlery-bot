from bale import InlineKeyboardMarkup, InlineKeyboardButton

def build_kb(buttons_list: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for row_idx, row in enumerate(buttons_list, start=1):
        for btn in row:
            kb.add(btn, row=row_idx)
    return kb

def finance_menu_keyboard(is_super_admin: bool = False) -> InlineKeyboardMarkup:
    """Finance main menu."""
    buttons = [
        [
            InlineKeyboardButton("💸 ثبت هزینه جدید", callback_data="fin:exp:new"),
        ],
        [
            InlineKeyboardButton("🤝 تراکنش شرکا (برداشت/واریز)", callback_data="fin:part:new"),
        ],
    ]
    
    if is_super_admin:
        buttons.extend([
            [
                InlineKeyboardButton("📊 گزارش سود و زیان ماه جاری", callback_data="fin:rep:month"),
            ],
            [
                InlineKeyboardButton("📈 گزارش سود و زیان کل زمان‌ها", callback_data="fin:rep:all"),
            ]
        ])
        
    buttons.append([InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="menu:main")])
    return build_kb(buttons)

def expense_categories_keyboard(categories: list) -> InlineKeyboardMarkup:
    """Select expense category."""
    buttons = []
    for cat in categories:
        buttons.append([
            InlineKeyboardButton(f"📁 {cat.name}", callback_data=f"fin:exp:cat:{cat.id}")
        ])
    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:finance")])
    return build_kb(buttons)

def partners_keyboard(partners: list) -> InlineKeyboardMarkup:
    """Select partner."""
    buttons = []
    for p in partners:
        buttons.append([
            InlineKeyboardButton(f"👤 {p.name}", callback_data=f"fin:part:id:{p.id}")
        ])
    buttons.append([InlineKeyboardButton("❌ لغو", callback_data="menu:finance")])
    return build_kb(buttons)

def partner_transaction_type_keyboard(partner_id: int) -> InlineKeyboardMarkup:
    """Select type of partner transaction."""
    return build_kb([
        [
            InlineKeyboardButton("📉 برداشت شخصی (Drawing)", callback_data=f"fin:part:type:DRAWING:{partner_id}"),
        ],
        [
            InlineKeyboardButton("📈 تزریق سرمایه (Injection)", callback_data=f"fin:part:type:INJECTION:{partner_id}"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="menu:finance")]
    ])
