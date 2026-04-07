from __future__ import annotations

import asyncio
from pathlib import Path

import httpx


def test_api_bootstrap_and_site_crud(tmp_path: Path):
    asyncio.run(_run_api_bootstrap_and_site_crud(tmp_path))


def test_model_group_candidates_include_credential_dimension(tmp_path: Path):
    asyncio.run(_run_model_group_candidates_include_credential_dimension(tmp_path))


def test_model_group_detail_and_stats_api(tmp_path: Path):
    asyncio.run(_run_model_group_detail_and_stats_api(tmp_path))


def test_model_price_api(tmp_path: Path):
    asyncio.run(_run_model_price_api(tmp_path))


def test_openai_requests_require_matching_group_protocol(tmp_path: Path):
    asyncio.run(_run_openai_requests_require_matching_group_protocol(tmp_path))


def test_openai_responses_proxy_standard_request(tmp_path: Path):
    asyncio.run(_run_openai_responses_proxy_standard_request(tmp_path))


async def _run_api_bootstrap_and_site_crud(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-crud.db')

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/auth/login', json={'username': config.admin_default_username, 'password': config.admin_default_password})
            assert login.status_code == 200
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            sites_before = await client.get('/api/sites', headers=headers)
            assert sites_before.status_code == 200
            before_count = len(sites_before.json())

            created = await client.post(
                '/api/sites',
                headers=headers,
                json={
                    'name': 'Test Site',
                    'base_url': 'https://api.openai.com',
                    'credentials': [
                        {'name': 'Key A', 'api_key': 'key-a', 'enabled': True},
                    ],
                    'protocols': [
                        {
                            'protocol': 'openai_chat',
                            'enabled': True,
                            'headers': {},
                            'channel_proxy': '',
                            'param_override': '',
                            'match_regex': '',
                            'bindings': [],
                            'models': [],
                        }
                    ],
                },
            )
            assert created.status_code == 201
            payload = created.json()
            assert payload['name'] == 'Test Site'
            assert len(payload['credentials']) == 1
            assert len(payload['protocols']) == 1
            site_id = payload['id']

            sites_after_create = await client.get('/api/sites', headers=headers)
            assert sites_after_create.status_code == 200
            assert len(sites_after_create.json()) == before_count + 1

            deleted = await client.delete(f'/api/sites/{site_id}', headers=headers)
            assert deleted.status_code == 204

            sites_after_delete = await client.get('/api/sites', headers=headers)
            assert sites_after_delete.status_code == 200
            assert len(sites_after_delete.json()) == before_count
    finally:
        await service_module._close_app_state(service_module.app_state)


async def _run_model_group_candidates_include_credential_dimension(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-candidates.db')

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/auth/login', json={'username': config.admin_default_username, 'password': config.admin_default_password})
            assert login.status_code == 200
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            created = await client.post(
                '/api/sites',
                headers=headers,
                json={
                    'name': 'Candidate Site',
                    'base_url': 'https://api.openai.com',
                    'credentials': [
                        {'name': 'Alpha', 'api_key': 'alpha-key', 'enabled': True},
                        {'name': 'Beta', 'api_key': 'beta-key', 'enabled': True},
                    ],
                    'protocols': [
                        {
                            'protocol': 'openai_chat',
                            'enabled': True,
                            'headers': {},
                            'channel_proxy': '',
                            'param_override': '',
                            'match_regex': '',
                            'bindings': [],
                            'models': [],
                        }
                    ],
                },
            )
            assert created.status_code == 201
            site = created.json()
            protocol = site['protocols'][0]
            alpha = next(item for item in site['credentials'] if item['name'] == 'Alpha')
            beta = next(item for item in site['credentials'] if item['name'] == 'Beta')

            updated = await client.put(
                f"/api/sites/{site['id']}",
                headers=headers,
                json={
                    'name': site['name'],
                    'base_url': site['base_url'],
                    'credentials': [
                        {'id': alpha['id'], 'name': alpha['name'], 'api_key': alpha['api_key'], 'enabled': True},
                        {'id': beta['id'], 'name': beta['name'], 'api_key': beta['api_key'], 'enabled': True},
                    ],
                    'protocols': [
                        {
                            'id': protocol['id'],
                            'protocol': protocol['protocol'],
                            'enabled': True,
                            'headers': {},
                            'channel_proxy': '',
                            'param_override': '',
                            'match_regex': '',
                            'bindings': [
                                {'credential_id': alpha['id'], 'enabled': True},
                                {'credential_id': beta['id'], 'enabled': True},
                            ],
                            'models': [
                                {'credential_id': alpha['id'], 'model_name': 'gpt-4.1', 'enabled': True},
                                {'credential_id': beta['id'], 'model_name': 'gpt-4.1', 'enabled': True},
                                {'credential_id': beta['id'], 'model_name': 'gpt-4.1-mini', 'enabled': True},
                            ],
                        }
                    ],
                },
            )
            assert updated.status_code == 200

            candidates = await client.post(
                '/api/model-groups/candidates',
                headers=headers,
                json={
                    'protocol': 'openai_chat',
                    'exclude_items': [],
                },
            )
            assert candidates.status_code == 200
            payload = candidates.json()
            keys = {(item['channel_id'], item['credential_id'], item['model_name']) for item in payload['candidates']}
            assert (protocol['id'], alpha['id'], 'gpt-4.1') in keys
            assert (protocol['id'], beta['id'], 'gpt-4.1') in keys
            assert (protocol['id'], beta['id'], 'gpt-4.1-mini') in keys
            assert all(item['channel_name'] == 'Candidate Site' for item in payload['candidates'])

    finally:
        await service_module._close_app_state(service_module.app_state)


async def _run_model_group_detail_and_stats_api(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-group-detail.db')

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/auth/login', json={'username': config.admin_default_username, 'password': config.admin_default_password})
            assert login.status_code == 200
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            created_site = await client.post(
                '/api/sites',
                headers=headers,
                json={
                    'name': 'Stats Site',
                    'base_url': 'https://api.openai.com',
                    'credentials': [{'name': 'Key A', 'api_key': 'key-a', 'enabled': True}],
                    'protocols': [{
                        'protocol': 'openai_chat',
                        'enabled': True,
                        'headers': {},
                        'channel_proxy': '',
                        'param_override': '',
                        'match_regex': '',
                        'bindings': [],
                        'models': [],
                    }],
                },
            )
            assert created_site.status_code == 201
            site = created_site.json()
            protocol = site['protocols'][0]
            credential = site['credentials'][0]

            updated_site = await client.put(
                f"/api/sites/{site['id']}",
                headers=headers,
                json={
                    'name': site['name'],
                    'base_url': site['base_url'],
                    'credentials': [{'id': credential['id'], 'name': credential['name'], 'api_key': credential['api_key'], 'enabled': True}],
                    'protocols': [{
                        'id': protocol['id'],
                        'protocol': protocol['protocol'],
                        'enabled': True,
                        'headers': {},
                        'channel_proxy': '',
                        'param_override': '',
                        'match_regex': '',
                        'bindings': [{'credential_id': credential['id'], 'enabled': True}],
                        'models': [{'credential_id': credential['id'], 'model_name': 'gpt-4.1', 'enabled': True}],
                    }],
                },
            )
            assert updated_site.status_code == 200

            created_group = await client.post(
                '/api/model-groups',
                headers=headers,
                json={
                    'name': 'gpt-4.1',
                    'protocol': 'openai_chat',
                    'strategy': 'failover',
                    'items': [{
                        'channel_id': protocol['id'],
                        'credential_id': credential['id'],
                        'model_name': 'gpt-4.1',
                        'enabled': True,
                    }],
                },
            )
            assert created_group.status_code == 201
            group = created_group.json()

            group_detail = await client.get(f"/api/model-groups/{group['id']}", headers=headers)
            assert group_detail.status_code == 200
            detail_payload = group_detail.json()
            assert detail_payload['id'] == group['id']
            assert detail_payload['items'][0]['channel_id'] == protocol['id']

            missing_group = await client.get('/api/model-groups/missing-group-id', headers=headers)
            assert missing_group.status_code == 404

            await service_module.app_state.domain_store.create_request_log(
                protocol='openai_chat',
                requested_model='gpt-4.1',
                matched_group_name='gpt-4.1',
                channel_id=protocol['id'],
                gateway_key_id='gw-test',
                status_code=200,
                success=True,
                latency_ms=123,
                resolved_model='gpt-4.1',
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                input_cost_usd=0.001,
                output_cost_usd=0.002,
                total_cost_usd=0.003,
                error_message=None,
            )

            stats = await client.get('/api/model-groups/stats', headers=headers)
            assert stats.status_code == 200
            stats_payload = stats.json()
            target = next(item for item in stats_payload if item['name'] == 'gpt-4.1')
            assert target['request_count'] == 1
            assert target['success_count'] == 1
            assert target['failed_count'] == 0
            assert target['last_resolved_model'] == 'gpt-4.1'
    finally:
        await service_module._close_app_state(service_module.app_state)


async def _run_model_price_api(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-model-price.db')

    async def fake_sync(state, overwrite_existing: bool = False):
        await state.domain_store.sync_model_prices([
            {
                'model_key': 'gpt-5.4',
                'display_name': 'gpt-5.4',
                'input_price_per_million': 1.0,
                'output_price_per_million': 8.0,
                'cache_read_price_per_million': 0.5,
                'cache_write_price_per_million': 1.5,
            }
        ], overwrite_existing=overwrite_existing, allowed_keys=['gpt-5.4'])
        await state.domain_store.set_model_price_sync_time('2026-04-05T00:00:00+00:00')

    service_module._sync_group_prices = fake_sync

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/auth/login', json={'username': config.admin_default_username, 'password': config.admin_default_password})
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            created_group = await client.post(
                '/api/model-groups',
                headers=headers,
                json={
                    'name': 'gpt-5.4',
                    'protocol': 'openai_chat',
                    'strategy': 'round_robin',
                    'items': [],
                },
            )
            assert created_group.status_code == 201

            prices = await client.get('/api/model-prices', headers=headers)
            assert prices.status_code == 200
            assert prices.json()['items'][0]['model_key'] == 'gpt-5.4'
            assert prices.json()['items'][0]['cache_read_price_per_million'] == 0.5
            assert prices.json()['items'][0]['cache_write_price_per_million'] == 1.5

            updated = await client.put(
                '/api/model-prices/gpt-5.4',
                headers=headers,
                json={
                    'model_key': 'ignored-by-path',
                    'display_name': 'gpt-5.4',
                    'input_price_per_million': 2.5,
                    'output_price_per_million': 10.5,
                    'cache_read_price_per_million': 0.8,
                    'cache_write_price_per_million': 1.8,
                },
            )
            assert updated.status_code == 200
            assert updated.json()['input_price_per_million'] == 2.5
            assert updated.json()['cache_read_price_per_million'] == 0.8

            missing = await client.put(
                '/api/model-prices/not-a-group',
                headers=headers,
                json={
                    'model_key': 'ignored-by-path',
                    'display_name': 'not-a-group',
                    'input_price_per_million': 1,
                    'output_price_per_million': 1,
                    'cache_read_price_per_million': 0,
                    'cache_write_price_per_million': 0,
                },
            )
            assert missing.status_code == 400

            synced = await client.post('/api/model-prices/sync', headers=headers)
            assert synced.status_code == 200
            assert synced.json()['last_synced_at'] == '2026-04-05T00:00:00+00:00'
    finally:
        await service_module._close_app_state(service_module.app_state)


async def _run_openai_requests_require_matching_group_protocol(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-routing-protocol.db')

    async def fake_request(*args, **kwargs):
        raise AssertionError('upstream should not be called when protocol-specific group is missing')

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    original_request = service_module.app_state.http.request
    service_module.app_state.http.request = fake_request
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/auth/login', json={'username': config.admin_default_username, 'password': config.admin_default_password})
            assert login.status_code == 200
            token = login.json()['access_token']
            admin_headers = {'authorization': f'Bearer {token}'}
            updated_settings = await client.put(
                '/api/settings',
                headers=admin_headers,
                json={'items': [{'key': 'gateway_api_keys', 'value': 'test-gateway-key'}]},
            )
            assert updated_settings.status_code == 200

            created_site = await client.post(
                '/api/sites',
                headers=admin_headers,
                json={
                    'name': 'Mixed OpenAI Site',
                    'base_url': 'https://api.openai.com',
                    'credentials': [{'name': 'Key A', 'api_key': 'key-a', 'enabled': True}],
                    'protocols': [
                        {
                            'protocol': 'openai_chat',
                            'enabled': True,
                            'headers': {},
                            'channel_proxy': '',
                            'param_override': '',
                            'match_regex': '',
                            'bindings': [],
                            'models': [],
                        },
                        {
                            'protocol': 'openai_responses',
                            'enabled': True,
                            'headers': {},
                            'channel_proxy': '',
                            'param_override': '',
                            'match_regex': '',
                            'bindings': [],
                            'models': [],
                        },
                    ],
                },
            )
            assert created_site.status_code == 201
            site = created_site.json()
            credential = site['credentials'][0]
            chat_protocol = next(item for item in site['protocols'] if item['protocol'] == 'openai_chat')
            responses_protocol = next(item for item in site['protocols'] if item['protocol'] == 'openai_responses')

            updated_site = await client.put(
                f"/api/sites/{site['id']}",
                headers=admin_headers,
                json={
                    'name': site['name'],
                    'base_url': site['base_url'],
                    'credentials': [{'id': credential['id'], 'name': credential['name'], 'api_key': credential['api_key'], 'enabled': True}],
                    'protocols': [
                        {
                            'id': chat_protocol['id'],
                            'protocol': 'openai_chat',
                            'enabled': True,
                            'headers': {},
                            'channel_proxy': '',
                            'param_override': '',
                            'match_regex': '',
                            'bindings': [{'credential_id': credential['id'], 'enabled': True}],
                            'models': [],
                        },
                        {
                            'id': responses_protocol['id'],
                            'protocol': 'openai_responses',
                            'enabled': True,
                            'headers': {},
                            'channel_proxy': '',
                            'param_override': '',
                            'match_regex': '',
                            'bindings': [{'credential_id': credential['id'], 'enabled': True}],
                            'models': [{'credential_id': credential['id'], 'model_name': 'gpt-5.4', 'enabled': True}],
                        },
                    ],
                },
            )
            assert updated_site.status_code == 200

            created_group = await client.post(
                '/api/model-groups',
                headers=admin_headers,
                json={
                    'name': 'gpt-5.4',
                    'protocol': 'openai_responses',
                    'strategy': 'round_robin',
                    'items': [{
                        'channel_id': responses_protocol['id'],
                        'credential_id': credential['id'],
                        'model_name': 'gpt-5.4',
                        'enabled': True,
                    }],
                },
            )
            assert created_group.status_code == 201

            gateway_response = await client.post(
                '/v1/chat/completions',
                headers={'authorization': 'Bearer test-gateway-key'},
                json={
                    'model': 'gpt-5.4',
                    'messages': [{'role': 'user', 'content': 'hello'}],
                },
            )
            assert gateway_response.status_code == 503
            payload = gateway_response.json()
            assert payload['error']['type'] == 'routing_error'
            assert payload['error']['message'] == 'No model group matched protocol=openai_chat model=gpt-5.4'
    finally:
        service_module.app_state.http.request = original_request
        await service_module._close_app_state(service_module.app_state)


async def _run_openai_responses_proxy_standard_request(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-openai-responses.db')

    upstream_calls: list[dict[str, object]] = []

    async def fake_request(method, url, headers=None, json=None, **kwargs):
        upstream_calls.append({'method': method, 'url': url, 'headers': headers, 'json': json})
        request = httpx.Request(method, url, headers=headers, json=json)
        if method == 'GET' and url == 'https://models.dev/api.json':
            return httpx.Response(200, request=request, json={})
        return httpx.Response(
            200,
            request=request,
            headers={'content-type': 'application/json', 'x-request-id': 'req_test'},
            json={
                'id': 'resp_123',
                'object': 'response',
                'model': 'gpt-5.4',
                'output': [
                    {
                        'id': 'msg_123',
                        'type': 'message',
                        'role': 'assistant',
                        'content': [{'type': 'output_text', 'text': 'hello'}],
                    }
                ],
                'usage': {
                    'input_tokens': 10,
                    'output_tokens': 20,
                    'total_tokens': 30,
                },
            },
        )

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    original_request = service_module.app_state.http.request
    service_module.app_state.http.request = fake_request
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/auth/login', json={'username': config.admin_default_username, 'password': config.admin_default_password})
            assert login.status_code == 200
            token = login.json()['access_token']
            admin_headers = {'authorization': f'Bearer {token}'}
            updated_settings = await client.put(
                '/api/settings',
                headers=admin_headers,
                json={'items': [{'key': 'gateway_api_keys', 'value': 'test-gateway-key'}]},
            )
            assert updated_settings.status_code == 200

            created_site = await client.post(
                '/api/sites',
                headers=admin_headers,
                json={
                    'name': 'Responses Site',
                    'base_url': 'https://api.openai.com',
                    'credentials': [{'name': 'Key A', 'api_key': 'key-a', 'enabled': True}],
                    'protocols': [{
                        'protocol': 'openai_responses',
                        'enabled': True,
                        'headers': {},
                        'channel_proxy': '',
                        'param_override': '',
                        'match_regex': '',
                        'bindings': [],
                        'models': [],
                    }],
                },
            )
            assert created_site.status_code == 201
            site = created_site.json()
            credential = site['credentials'][0]
            protocol = site['protocols'][0]

            updated_site = await client.put(
                f"/api/sites/{site['id']}",
                headers=admin_headers,
                json={
                    'name': site['name'],
                    'base_url': site['base_url'],
                    'credentials': [{'id': credential['id'], 'name': credential['name'], 'api_key': credential['api_key'], 'enabled': True}],
                    'protocols': [{
                        'id': protocol['id'],
                        'protocol': 'openai_responses',
                        'enabled': True,
                        'headers': {},
                        'channel_proxy': '',
                        'param_override': '',
                        'match_regex': '',
                        'bindings': [{'credential_id': credential['id'], 'enabled': True}],
                        'models': [{'credential_id': credential['id'], 'model_name': 'gpt-5.4', 'enabled': True}],
                    }],
                },
            )
            assert updated_site.status_code == 200

            created_group = await client.post(
                '/api/model-groups',
                headers=admin_headers,
                json={
                    'name': 'gpt-5.4',
                    'protocol': 'openai_responses',
                    'strategy': 'round_robin',
                    'items': [{
                        'channel_id': protocol['id'],
                        'credential_id': credential['id'],
                        'model_name': 'gpt-5.4',
                        'enabled': True,
                    }],
                },
            )
            assert created_group.status_code == 201

            gateway_response = await client.post(
                '/v1/responses',
                headers={'authorization': 'Bearer test-gateway-key'},
                json={'model': 'gpt-5.4', 'input': 'hello'},
            )
            assert gateway_response.status_code == 200
            payload = gateway_response.json()
            assert payload['model'] == 'gpt-5.4'
            assert payload['output'][0]['content'][0]['text'] == 'hello'

            post_call = next(item for item in upstream_calls if item['method'] == 'POST')
            assert post_call['url'] == 'https://api.openai.com/v1/responses'
            assert post_call['json'] == {'model': 'gpt-5.4', 'input': 'hello'}
    finally:
        service_module.app_state.http.request = original_request
        await service_module._close_app_state(service_module.app_state)


async def _build_test_app(database_path: Path):
    from lens.core.db import Base
    from lens.core.config import Settings
    from lens.gateway import service as service_module

    config = Settings(
        database_url=f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}",
        admin_default_username='admin',
        admin_default_password='admin',
        auth_secret_key='lens-test-secret-key-with-32-bytes!!',
    )
    service_module.settings = config
    service_module.app_state = service_module.AppState()
    async with service_module.app_state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return service_module, service_module.app, config

