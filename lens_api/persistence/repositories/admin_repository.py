from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from ...core.auth import PBKDF2_ITERATIONS, hash_password, verify_password
from ..entities import AdminUserEntity

_DUMMY_PASSWORD_HASH = (
    f"pbkdf2_sha256${PBKDF2_ITERATIONS}$lens-admin-login-dummy${'0' * 64}"
)


class AdminRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_default_admin(
        self,
        username: str,
        password: str,
        *,
        publish_initial_password: Callable[[], None] | None = None,
    ) -> bool:
        """Create the initial administrator when no account exists."""
        async with self._session_factory() as session:
            result = await session.execute(select(AdminUserEntity.id).limit(1))
            existing = result.scalar_one_or_none()
            if existing is not None:
                return False

            session.add(
                AdminUserEntity(
                    username=username,
                    password_hash=await run_in_threadpool(hash_password, password),
                    is_active=1,
                )
            )
            try:
                await session.flush()
                if publish_initial_password is not None:
                    publish_initial_password()
                await session.commit()
            except IntegrityError:
                await session.rollback()
                result = await session.execute(select(AdminUserEntity.id).limit(1))
                if result.scalar_one_or_none() is not None:
                    return False
                raise
            except Exception:
                await session.rollback()
                raise
            return True

    async def authenticate(
        self, username: str, password: str
    ) -> AdminUserEntity | None:
        """Authenticate an active administrator by username and password."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AdminUserEntity)
                .where(AdminUserEntity.username == username)
                .limit(1)
            )
            user = result.scalar_one_or_none()
            is_active = user is not None and user.is_active == 1
            password_hash = user.password_hash if is_active else _DUMMY_PASSWORD_HASH
            password_matches = await run_in_threadpool(
                verify_password, password, password_hash
            )
            if not is_active or not password_matches:
                return None
            assert user is not None
            return user

    async def find_by_username(self, username: str) -> AdminUserEntity | None:
        """Return an administrator by username when present."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AdminUserEntity)
                .where(AdminUserEntity.username == username)
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def update_password(
        self, username: str, current_password: str, new_password: str
    ) -> None:
        """Change an administrator password after verifying the current one."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(AdminUserEntity)
                .where(AdminUserEntity.username == username)
                .limit(1)
            )
            user = result.scalar_one_or_none()
            if user is None or user.is_active != 1:
                raise KeyError(username)
            original_password_hash = user.password_hash
            original_token_version = user.auth_token_version
            if not await run_in_threadpool(
                verify_password, current_password, original_password_hash
            ):
                raise ValueError("Current password is incorrect")
            next_password_hash = await run_in_threadpool(hash_password, new_password)
            update_result = await session.execute(
                update(AdminUserEntity)
                .where(
                    AdminUserEntity.id == user.id,
                    AdminUserEntity.username == username,
                    AdminUserEntity.password_hash == original_password_hash,
                    AdminUserEntity.auth_token_version == original_token_version,
                    AdminUserEntity.is_active == 1,
                )
                .values(
                    password_hash=next_password_hash,
                    auth_token_version=AdminUserEntity.auth_token_version + 1,
                )
                .execution_options(synchronize_session=False)
            )
            if update_result.rowcount != 1:
                await session.rollback()
                raise ValueError("Administrator account changed; retry")
            await session.commit()

    async def update_profile(
        self,
        current_username: str,
        next_username: str,
        current_password: str,
        new_password: str,
    ) -> AdminUserEntity:
        """Update an administrator username and optional password."""
        normalized_username = next_username.strip()

        async with self._session_factory() as session:
            result = await session.execute(
                select(AdminUserEntity)
                .where(AdminUserEntity.username == current_username)
                .limit(1)
            )
            user = result.scalar_one_or_none()
            if user is None or user.is_active != 1:
                raise KeyError(current_username)

            original_username = user.username
            original_password_hash = user.password_hash
            original_token_version = user.auth_token_version
            username_changed = normalized_username != original_username
            if username_changed:
                duplicate = await session.execute(
                    select(AdminUserEntity.id)
                    .where(
                        AdminUserEntity.username == normalized_username,
                        AdminUserEntity.id != user.id,
                    )
                    .limit(1)
                )
                if duplicate.scalar_one_or_none() is not None:
                    raise ValueError("Username already exists")

            password_changed = bool(new_password)
            next_password_hash = original_password_hash
            if password_changed:
                if not current_password:
                    raise ValueError("Current password is required")
                if not await run_in_threadpool(
                    verify_password, current_password, original_password_hash
                ):
                    raise ValueError("Current password is incorrect")
                next_password_hash = await run_in_threadpool(
                    hash_password, new_password
                )

            if not username_changed and not password_changed:
                return user

            try:
                update_result = await session.execute(
                    update(AdminUserEntity)
                    .where(
                        AdminUserEntity.id == user.id,
                        AdminUserEntity.username == original_username,
                        AdminUserEntity.password_hash == original_password_hash,
                        AdminUserEntity.auth_token_version == original_token_version,
                        AdminUserEntity.is_active == 1,
                    )
                    .values(
                        username=normalized_username,
                        password_hash=next_password_hash,
                        auth_token_version=AdminUserEntity.auth_token_version + 1,
                    )
                    .execution_options(synchronize_session=False)
                )
                if update_result.rowcount != 1:
                    await session.rollback()
                    raise ValueError("Administrator account changed; retry")
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                if username_changed:
                    raise ValueError("Username already exists") from exc
                raise
            await session.refresh(user)
            return user
