from __future__ import annotations

import asyncio

from lens.core.config import settings
from lens.core.db import create_engine, create_session_factory
from lens.persistence.admin_store import AdminStore


async def main() -> None:
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    store = AdminStore(session_factory)
    await store.ensure_default_admin(
        settings.admin_default_username,
        settings.admin_default_password,
    )
    await engine.dispose()
    print(f"seeded admin: {settings.admin_default_username}")


if __name__ == "__main__":
    asyncio.run(main())

