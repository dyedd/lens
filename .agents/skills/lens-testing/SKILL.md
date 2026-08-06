---
name: lens-testing
description: Apply Lens's test policy when adding or changing backend or frontend tests, fixing a reproducible bug, or updating CI validation. Keep behavior coverage in the repository and run the complete suite in CI while local development uses only focused, fast checks.
---

# Lens Testing

Keep tests for externally observable behavior, not implementation details. A new route or reproducible bug needs a regression test; a refactor, formatting change, or type-only edit does not justify a new test file.

## Workflow

1. Trace the affected request or UI flow and reuse the nearest existing fixture/helper.
2. Add the smallest behavior test that fails before the fix and passes after it.
3. Keep backend tests under `tests/` and frontend tests under `ui/tests/`.
4. Do not run the full suite as a local gate. Locally run only the relevant static checks or one focused test while debugging.
5. Let CI run the full backend suite with pytest-xdist and the frontend's `node:test` files, type check, lint, and build.

## Commands

- Backend focused check: `uv run --no-sync python -m pytest tests/api/test_<area>.py -q --confcutdir=tests`
- Backend CI suite: `uv run --no-sync python -m pytest tests -q --confcutdir=tests -n auto --dist worksteal`
- Frontend focused check: `cd ui && pnpm test`
- Frontend CI checks: `pnpm test`, `pnpm lint`, `pnpm exec tsc --noEmit`, and `pnpm build`

Do not add a second test runner or a custom parallel harness. `pytest-xdist` is the backend parallel runner; Node's built-in `node:test` is sufficient for the current frontend utility tests. Add broader frontend coverage only when a user-facing regression or a reusable pure utility warrants it.
