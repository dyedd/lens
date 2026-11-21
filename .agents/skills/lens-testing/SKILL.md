---
name: lens-testing
description: Guidance for writing and maintaining Lens backend HTTP tests, including request entry points, shared fixtures, and upstream mocks.
---

# Lens Backend HTTP Testing

Follow [AGENTS.md](../../../AGENTS.md) for test-addition and verification requirements. This skill defines Lens backend HTTP test conventions.

## Conventions

- **HTTP entry point:** Put tests in `backend/tests/api/test_<area>_api.py` and send requests through the `client` fixture so they exercise the actual routes and middleware.
- **Core flows:** Prioritize successful workflows through core endpoints. An admin CRUD test may cover listing, creation, retrieval, update, and deletion. Test gateway requests and responses through the corresponding public protocol endpoints.
- **State setup:** Prepare state through public endpoints or the [shared fixtures](../../../backend/tests/conftest.py). Reuse `admin_headers`, `create_site`, `create_model_group`, `create_gateway_key`, and `create_site_group_and_key`.
- **Database and lifecycle:** Use the temporary SQLite database provided by the `app_state` fixture. The default fixture skips application startup. For startup and shutdown behavior, follow the [lifecycle tests](../../../backend/tests/api/test_lifecycle_api.py) and enable the real `lifespan`.
- **Upstream mocks:** Proxy tests may replace `app.gateway.service.proxy.proxy_upstream._send_upstream` with a mock that returns an HTTP response or stream. This keeps authentication, routing, protocol conversion, and request logging in the tested flow. To test protocol endpoint dispatch alone, replace `app.gateway.service.proxy_routes.proxy_protocol`.
