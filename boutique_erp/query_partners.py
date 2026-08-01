import asyncio
from app.database.base import async_session
from app.database.models import Partner
from sqlalchemy import select

async def main():
    async with async_session() as session:
        result = await session.execute(select(Partner))
        partners = result.scalars().all()
        for p in partners:
            print(f"ID: {p.id}, Name: {p.name}")

if __name__ == "__main__":
    asyncio.run(main())
