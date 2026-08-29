---
name: lens-testing
description: Apply Lens's scope policy and writing conventions for critical backend HTTP API tests, and run the backend suite in parallel through the uv-managed toolchain. Validate the frontend with static checks instead of frontend tests.
---

# Lens Testing

## Scope

Cover only critical, high-risk backend HTTP contracts: authentication and authorization, data persistence or loss, gateway protocol compatibility, and routing or failover behavior. A new route or a reproducible bug does not by itself justify a test; add one only when the affected HTTP contract warrants the maintenance cost.

Never add frontend tests, nor direct tests of units, services, helpers, converters, repositories, or other implementation details.

Delete a test once the behavior it guarded is covered elsewhere, or once the field or option it pinned has been removed or derived.

## Workflow

1. Trace the affected HTTP path and decide whether it is a high-risk contract.
2. Reuse the nearest area file under `backend/tests/api/`, and the fixtures and helpers in `backend/tests/conftest.py`.
3. If coverage is justified, add the smallest request-and-response behavior test.
4. Format the touched files, then run the backend suite in parallel; narrow to one file only to debug a single failure.
5. Let CI repeat the backend suite and run the frontend lint, type check, and build.

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

Call every backend tool through `uv run --no-sync`, so it comes from the `dev` dependency group instead of a global install. Run every command from the repository root, not from `backend/`.

- Format and lint touched files: `uv run --no-sync ruff format <paths>` then `uv run --no-sync ruff check --fix <paths>`
- Local pre-commit formatting: `uv run --no-sync prek install -f`, then `uv run --no-sync prek run --all-files`
- Backend suite: `uv run --no-sync python -m pytest backend/tests/api -q --confcutdir=backend/tests -n auto --dist worksteal`
- One file, while debugging: `uv run --no-sync python -m pytest backend/tests/api/test_<area>_api.py -q --confcutdir=backend/tests`
- Frontend checks: `pnpm format` for local fixes, then `pnpm lint`, `pnpm exec tsc --noEmit`, and `pnpm build`

`pytest-xdist` and `ruff` ship in the `dev` dependency group; install them with `uv sync --locked`. With a package index mirror configured, `--locked` misreports lockfile drift, so use `uv sync --frozen`.

Do not add another test runner or a custom parallel harness.
