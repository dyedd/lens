from __future__ import annotations

from dataclasses import dataclass, field

from .....models.site_import import SiteImportItem


@dataclass
class ParsedForeignSites:
    """Outcome of converting one foreign backup file into Lens site imports."""

    sites: list[SiteImportItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def skip(self, name: str, reason: str) -> None:
        self.skipped.append(f"{name}: {reason}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
