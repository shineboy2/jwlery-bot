import asyncio
from app.database.crud import create_content_category, get_content_category_by_code
from app.database.engine import init_db

async def seed():
    await init_db()
    cats = [
        ("صبح بخیر", "MORNING"),
        ("آموزشی", "EDU"),
        ("فروش ویژه", "PROMO"),
        ("کالکشن جدید", "NEW_ARRIVAL"),
        ("شارژ مجدد", "RESTOCK")
    ]
    for name, code in cats:
        existing = await get_content_category_by_code(code)
        if not existing:
            await create_content_category(name=name, code=code)
            print(f"Created category {name} ({code})")

if __name__ == "__main__":
    asyncio.run(seed())
