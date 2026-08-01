import asyncio
from app.database.base import async_session
from app.database.models import Partner
from sqlalchemy import select, update

async def main():
    async with async_session() as session:
        # Find partner 2 and update name
        stmt = update(Partner).where(Partner.name == 'شریک دوم').values(name='امین')
        await session.execute(stmt)
        await session.commit()
        print("Partner updated to امین")

if __name__ == "__main__":
    asyncio.run(main())
