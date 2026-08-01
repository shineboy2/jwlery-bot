import asyncio
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.future import select
from app.database.base import async_session
from app.database.models import ExpenseCategory, Partner

async def seed_finance():
    async with async_session() as session:
        # Seed Expense Categories
        expense_cats = [
            {"name": "بسته‌بندی و ملزومات ارسال", "type": "VARIABLE"},
            {"name": "هزینه پست و پیک", "type": "VARIABLE"},
            {"name": "تبلیغات اینستاگرام/تلگرام", "type": "VARIABLE"},
            {"name": "هزینه سرور و دامنه", "type": "FIXED"},
            {"name": "اشتراک هوش مصنوعی", "type": "FIXED"},
            {"name": "متفرقه", "type": "VARIABLE"},
        ]
        
        print("Seeding Expense Categories...")
        for cat in expense_cats:
            stmt = select(ExpenseCategory).where(ExpenseCategory.name == cat["name"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                new_cat = ExpenseCategory(name=cat["name"], type=cat["type"])
                session.add(new_cat)
                print(f"Created Expense Category: {cat['name']}")

        # Seed Partners
        partners = [
            {"name": "شهاب", "equity_share": 50},
            {"name": "شریک دوم", "equity_share": 50},
        ]
        
        print("Seeding Partners...")
        for p in partners:
            stmt = select(Partner).where(Partner.name == p["name"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                new_partner = Partner(name=p["name"], equity_share=p["equity_share"])
                session.add(new_partner)
                print(f"Created Partner: {p['name']}")
                
        await session.commit()
        print("Finance seed completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_finance())
