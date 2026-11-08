from __future__ import annotations

import argparse
import re
from pathlib import Path


def parse_version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value)
    if match is None:
        raise argparse.ArgumentTypeError(f"Expected major.minor.patch, got {value!r}")
    return int(match[1]), int(match[2]), int(match[3])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update the application and documentation versions together."
    )
    parser.add_argument(
        "--base-version", type=parse_version, help="Latest published version for CI"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source_path = root / "backend/app/__init__.py"
    feed_path = root / "docs/public/version.txt"
    source = source_path.read_text(encoding="utf-8")
    match = re.search(r"""__version__\s*=\s*["']([^"']+)["']""", source)
    if match is None:
        parser.error("Could not find __version__ in backend/app/__init__.py")
    current = parse_version(match[1])
    base = args.base_version or current
    if current < base:
        parser.error(
            f"Source version {match[1]} is behind the latest published version"
        )
    major, minor, patch = base
    next_version = match[1] if current > base else f"{major}.{minor}.{patch + 1}"

    if not args.dry_run:
        updated = source[: match.start(1)] + next_version + source[match.end(1) :]
        source_path.write_text(updated, encoding="utf-8")
        feed_path.write_text(next_version + "\n", encoding="utf-8")
    print(next_version)


if __name__ == "__main__":
    main()
