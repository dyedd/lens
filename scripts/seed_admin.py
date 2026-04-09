from __future__ import annotations

import argparse
import asyncio

from lens_api.core.config import settings
from lens_api.core.db import create_engine, create_session_factory
from lens_api.persistence.admin_store import AdminStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed an admin user into the configured database.")
    parser.add_argument("--username", required=True, help="Admin username to create or update.")
    parser.add_argument("--password", required=True, help="Admin password to set.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    store = AdminStore(session_factory)
    await store.ensure_default_admin(args.username, args.password)
    await engine.dispose()
    print(f"seeded admin: {args.username}")


if __name__ == "__main__":
    asyncio.run(main())
