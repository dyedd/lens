from functools import lru_cache


@lru_cache(maxsize=1)
def read_system_version() -> str:
    """Read the running system version."""
    from app import __version__

    return __version__
