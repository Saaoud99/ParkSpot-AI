from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def create(db: AsyncSession, user: User) -> User:
    db.add(user)
    await db.flush()
    return user


async def list_users(db: AsyncSession, limit: int, offset: int) -> tuple[list[User], int]:
    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    rows = (await db.execute(select(User).order_by(User.id).limit(limit).offset(offset))).scalars().all()
    return list(rows), total


async def count_all(db: AsyncSession) -> int:
    return (await db.execute(select(func.count(User.id)))).scalar_one()
