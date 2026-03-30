from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .auth import hash_password, verify_password
from .entities import AdminUserEntity


class AdminStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_default_admin(self, username: str, password: str) -> None:
        async with self._session_factory() as session:
            result = await session.execute(select(AdminUserEntity.id).limit(1))
            existing = result.scalar_one_or_none()
            if existing is not None:
                return

            session.add(
                AdminUserEntity(
                    username=username,
                    password_hash=hash_password(password),
                    is_active=1,
                )
            )
            await session.commit()

    async def authenticate(self, username: str, password: str) -> AdminUserEntity | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AdminUserEntity).where(AdminUserEntity.username == username).limit(1)
            )
            user = result.scalar_one_or_none()
            if user is None or user.is_active != 1:
                return None
            if not verify_password(password, user.password_hash):
                return None
            return user

    async def get_by_username(self, username: str) -> AdminUserEntity | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AdminUserEntity).where(AdminUserEntity.username == username).limit(1)
            )
            return result.scalar_one_or_none()
