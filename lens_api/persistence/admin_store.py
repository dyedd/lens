from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..core.auth import hash_password, verify_password
from .entities import AdminUserEntity


class AdminStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_default_admin(self, username: str, password: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(select(AdminUserEntity.id).limit(1))
            existing = result.scalar_one_or_none()
            if existing is not None:
                return False

            session.add(
                AdminUserEntity(
                    username=username,
                    password_hash=hash_password(password),
                    is_active=1,
                )
            )
            await session.commit()
            return True

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

    async def update_password(self, username: str, current_password: str, new_password: str) -> None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AdminUserEntity).where(AdminUserEntity.username == username).limit(1)
            )
            user = result.scalar_one_or_none()
            if user is None or user.is_active != 1:
                raise KeyError(username)
            if not verify_password(current_password, user.password_hash):
                raise ValueError("Current password is incorrect")
            user.password_hash = hash_password(new_password)
            await session.commit()

    async def update_profile(
        self,
        current_username: str,
        next_username: str,
        current_password: str,
        new_password: str,
    ) -> AdminUserEntity:
        normalized_username = next_username.strip()
        normalized_new_password = new_password.strip()

        async with self._session_factory() as session:
            result = await session.execute(
                select(AdminUserEntity).where(AdminUserEntity.username == current_username).limit(1)
            )
            user = result.scalar_one_or_none()
            if user is None or user.is_active != 1:
                raise KeyError(current_username)

            if normalized_username != user.username:
                duplicate = await session.execute(
                    select(AdminUserEntity.id)
                    .where(AdminUserEntity.username == normalized_username, AdminUserEntity.id != user.id)
                    .limit(1)
                )
                if duplicate.scalar_one_or_none() is not None:
                    raise ValueError("Username already exists")
                user.username = normalized_username

            if normalized_new_password:
                if not current_password:
                    raise ValueError("Current password is required")
                if not verify_password(current_password, user.password_hash):
                    raise ValueError("Current password is incorrect")
                user.password_hash = hash_password(normalized_new_password)

            await session.commit()
            await session.refresh(user)
            return user
