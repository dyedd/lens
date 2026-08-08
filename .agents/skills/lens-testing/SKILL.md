---
name: lens-testing
description: Apply Lens's policy for critical backend HTTP API tests and CI validation. Keep only high-risk API boundary coverage, and validate the frontend with static checks instead of frontend tests.
---

# Lens Testing

Keep tests only for critical, high-risk backend HTTP contracts: authentication and authorization, data persistence or loss, gateway protocol compatibility, and routing or failover behavior. A new route or reproducible bug does not automatically require a test; add or update one only when the affected HTTP contract warrants the maintenance cost.

Do not add frontend tests or direct tests of units, services, helpers, converters, repositories, or other implementation details.

## Workflow

1. Trace the affected HTTP path and decide whether it is a high-risk contract.
2. Reuse the nearest file and fixture under `tests/api/`.
3. If coverage is justified, add the smallest request-and-response behavior test.
4. Locally run static checks and, only when debugging, one focused API test.
5. Let CI run the backend API suite with pytest-xdist and the frontend lint, type check, and build.

## Commands

- Backend focused check: `uv run --no-sync python -m pytest tests/api/test_<area>.py -q --confcutdir=tests`
- Backend CI suite: `uv run --no-sync python -m pytest tests/api -q --confcutdir=tests -n auto --dist worksteal`
- Frontend checks: `pnpm lint`, `pnpm exec tsc --noEmit`, and `pnpm build`

Do not add another test runner or a custom parallel harness. `pytest-xdist` is the backend parallel runner.
