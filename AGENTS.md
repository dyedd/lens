# Lens Repository Guide

## Project Overview

Lens is a multi-provider LLM gateway for authentication, model-group routing, protocol conversion, upstream requests, failover, and request and usage logging. The backend uses Python 3.14+ in a uv workspace. The frontend and documentation site use pnpm.

See the [development setup](docs/development/setup.md), [quick start](docs/guide/quick-start.md), and [configuration reference](docs/reference/configuration.md) for local setup and operation.

## Build and Test Commands

Run backend commands from the repository root with `uv run --no-sync`.

Install the locked backend dependencies with `uv sync --locked`.

When updating `uv.lock`, set the official package index explicitly:

```powershell
$env:UV_DEFAULT_INDEX = "https://pypi.org/simple"
uv lock
```

Check that wheel and source archive URLs in `uv.lock` use `pypi.org` or `files.pythonhosted.org`.

Check backend syntax:

```bash
uv run --no-sync python -m compileall -q backend/app backend/tests scripts
```

Lint and build the frontend from `frontend/`:

```bash
pnpm lint
pnpm build
```

Build the documentation site from `docs/`:

```bash
pnpm build
```

## Code Style Guidelines

Follow the [backend coding style](.agents/BACKEND-CODING-STYLE.md) for Python and the [frontend coding style](.agents/FRONTEND-CODING-STYLE.md) for TypeScript and React. Follow [DESIGN.md](.agents/DESIGN.md) for frontend visual decisions.

Format and lint only the changed backend files:

```bash
uv run --no-sync ruff format <paths>
uv run --no-sync ruff check --fix <paths>
```

Format and lint changed frontend files from `frontend/`:

```bash
pnpm exec biome check --write <paths>
```

## Testing Instructions

Add tests only when requested, required by repository guidance, or needed to verify specific behavior that existing tests do not cover. Run relevant existing tests and checks, and verify that the requested behavior works as intended.

Follow the [lens-testing skill](.agents/skills/lens-testing/SKILL.md) for backend HTTP test conventions. Choose the applicable commands below according to the changed component.

For documentation-only changes, verify local links.

Run the backend API suite from the repository root:

```bash
uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal
```

Run one API test module during focused debugging:

```bash
uv run --no-sync python -m pytest backend/tests/api/test_<area>_api.py -q --confcutdir=backend/tests
```

For database migration changes, set `LENS_DATABASE_URL` to an isolated test database before running migration checks:

```bash
uv run --no-sync lens db upgrade
cd backend
uv run --no-sync python -m alembic check
```

Before finishing, review the full diff against this guide and the applicable coding style guide. Apply its comment rules to every added comment.

Report the checks that ran, any skipped or failed checks and why, and relevant assumptions or unresolved limitations.

Before finishing, run `git diff --check` and `git status --short`.

## Security Considerations

- Never expose `.env` contents or real credentials in source code, logs, responses, or tests.
- Keep existing Alembic migration files unchanged. Add a new revision for schema changes.
- Use an isolated test database for migration checks and tests that modify persistent data.
- Preserve repository history. Commit, push, or rewrite history only when the user explicitly requests it.
