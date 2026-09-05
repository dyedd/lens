---
name: lens-testing
description: Use when a Lens change needs backend HTTP contract coverage. Keep tests risk-based, drive them through the API fixtures, and use the repository's uv-managed checks.
---

# Lens Testing

## Scope

Cover only critical, high-risk backend HTTP contracts: authentication and authorization, data persistence or loss, gateway protocol compatibility, and routing or failover behavior. A new route or reproducible bug alone does not justify a test; the affected HTTP contract must warrant the coverage.

Do not automatically add frontend tests or direct tests of units, services, helpers, converters, or repositories. Follow explicit user instructions when they change the scope.

Delete a test once the behavior it guarded is covered elsewhere, or once the field or option it pinned has been removed or derived.

## Workflow

1. Trace the affected HTTP path and decide whether it is a contract worth protecting.
2. Reuse the nearest area file under `backend/tests/api/`, plus fixtures and helpers in `backend/tests/conftest.py`.
3. If coverage is justified, add the smallest request-and-response behavior test.
4. Format touched files and run the smallest relevant check. For backend contract changes, run the API suite in parallel; narrow to one file only while debugging.
5. Run frontend lint, type check, or build only when frontend files or the requested verification require them; CI remains the full repository check.

## Conventions

One file per area, named `backend/tests/api/test_<area>_api.py`. Name each test after the behavior it asserts, and separate arrange, act, and assert with blank lines.

- Drive every test through the `client` fixture. A test that bypasses HTTP, by calling a service function directly or by hand-building a `Request`, is testing an implementation detail.
- Build state through the admin API with the shared fixtures `admin_headers`, `create_site`, `create_model_group`, `create_gateway_key`, and `create_site_group_and_key`. Import helpers with `from conftest import ...`: `valid_site_payload`, `gateway_headers`, `openai_chat_channel_id`, `seed_request_log`, `assert_error`, and `json_response`.
- Stub only at the network edge, by monkeypatching `proxy_upstream._send_upstream` or by injecting an `httpx.MockTransport` client, so the gateway path under test still runs end to end. Never monkeypatch the function under test and then assert on its own return value.
- Assert one invariant per test, and express variants with `pytest.mark.parametrize` and `pytest.param(..., id=...)` rather than copied test bodies. For schema rejection cases, parametrize a mutator that edits an otherwise valid payload.
- Assert only what the HTTP contract promises. Response item order is not a contract unless the endpoint documents it; compare sorted values or sets instead.
- For protocol and streaming coverage, keep the upstream frames literal in the test, then assert both the converted client-visible body and the persisted request log.
- Do not restate what the framework already guarantees. Request and backup models inherit `StrictBaseModel(extra="forbid")`, so one representative case per schema family covers rejected extra fields and missing required fields; do not add a case per field.
- Do not write per-endpoint 401 tests. `test_every_admin_route_rejects_missing_token` walks `app.routes` and covers the whole admin surface; when a new admin route is intentionally public, add it to `_UNAUTHENTICATED_ADMIN_ROUTES` in the same change.

## Commands

Call every backend tool through `uv run --no-sync` from the repository root, so it comes from the `dev` dependency group instead of a global install.

- Format and lint touched files: `uv run --no-sync ruff format <paths>` then `uv run --no-sync ruff check --fix <paths>`
- Backend suite: `uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal`
- One file, while debugging: `uv run --no-sync python -m pytest backend/tests/api/test_<area>_api.py -q --confcutdir=backend/tests`
- Frontend checks, from `frontend/`: `pnpm lint`, `pnpm exec tsc --noEmit`, and `pnpm build`

`pytest-xdist` and `ruff` ship in the `dev` dependency group; install them with `uv sync --locked`. With a package index mirror configured, `--locked` misreports lockfile drift, so use `uv sync --frozen`.

Do not add another test runner or a custom parallel harness.
