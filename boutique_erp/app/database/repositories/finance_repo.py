from typing import Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import ExpenseCategory, Expense, Partner, PartnerTransaction

async def get_expense_categories(session: AsyncSession, active_only: bool = True) -> list[ExpenseCategory]:
    query = select(ExpenseCategory).order_by(ExpenseCategory.name)
    if active_only:
        query = query.where(ExpenseCategory.is_active == True)
    result = await session.execute(query)
    return list(result.scalars().all())

async def get_expense_category_by_id(session: AsyncSession, cat_id: int) -> Optional[ExpenseCategory]:
    result = await session.execute(
        select(ExpenseCategory).where(ExpenseCategory.id == cat_id)
    )
    return result.scalar_one_or_none()

async def create_expense(session: AsyncSession, category_id: int, amount: int, description: str = None) -> Expense:
    expense = Expense(category_id=category_id, amount=amount, description=description)
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense

async def get_all_partners(session: AsyncSession, active_only: bool = True) -> list[Partner]:
    query = select(Partner).order_by(Partner.id)
    if active_only:
        query = query.where(Partner.is_active == True)
    result = await session.execute(query)
    return list(result.scalars().all())

async def get_partner_by_id(session: AsyncSession, partner_id: int) -> Optional[Partner]:
    result = await session.execute(
        select(Partner).where(Partner.id == partner_id)
    )
    return result.scalar_one_or_none()

async def create_partner_transaction(session: AsyncSession, partner_id: int, amount: int, type: str = "DRAWING", description: str = None) -> PartnerTransaction:
    pt = PartnerTransaction(partner_id=partner_id, amount=amount, type=type, description=description)
    session.add(pt)
    await session.commit()
    await session.refresh(pt)
    return pt

async def get_expenses_between(session: AsyncSession, start_date: datetime = None, end_date: datetime = None) -> list[Expense]:
    query = select(Expense).options(selectinload(Expense.category))
    if start_date:
        query = query.where(Expense.expense_date >= start_date)
    if end_date:
        query = query.where(Expense.expense_date <= end_date)
    result = await session.execute(query.order_by(Expense.expense_date.desc()))
    return list(result.scalars().all())

async def get_partner_transactions_between(session: AsyncSession, start_date: datetime = None, end_date: datetime = None) -> list[PartnerTransaction]:
    query = select(PartnerTransaction).options(selectinload(PartnerTransaction.partner))
    if start_date:
        query = query.where(PartnerTransaction.transaction_date >= start_date)
    if end_date:
        query = query.where(PartnerTransaction.transaction_date <= end_date)
    result = await session.execute(query.order_by(PartnerTransaction.transaction_date.desc()))
    return list(result.scalars().all())
