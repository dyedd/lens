from __future__ import annotations

from .shared import (
    AsyncSession,
    async_sessionmaker,
)
from .export_import import BackupExportImportMixin
from .loaders import BackupLoadersMixin
from .replacers import BackupReplacersMixin


class BackupStore(
    BackupExportImportMixin,
    BackupReplacersMixin,
    BackupLoadersMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
