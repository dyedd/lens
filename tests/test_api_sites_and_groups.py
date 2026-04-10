from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx


TEST_ADMIN_USERNAME = 'admin'
TEST_ADMIN_PASSWORD = 'admin'


def _site_create_payload(name: str, credentials: list[dict], protocols: list[dict], base_url: str = 'https://api.openai.com') -> dict:
    return {
        'name': name,
        'base_urls': [
            {'url': base_url, 'name': '', 'enabled': True},
        ],
        'credentials': credentials,
        'protocols': protocols,
    }


def _site_update_payload(site: dict, credentials: list[dict], protocols: list[dict]) -> dict:
    return {
        'name': site['name'],
        'base_urls': [
            {
                'id': item['id'],
                'url': item['url'],
                'name': item['name'],
                'enabled': item['enabled'],
            }
            for item in site['base_urls']
        ],
        'credentials': credentials,
        'protocols': protocols,
    }


def test_api_bootstrap_and_site_crud(tmp_path: Path):
    asyncio.run(_run_api_bootstrap_and_site_crud(tmp_path))


def test_app_info_api(tmp_path: Path):
    asyncio.run(_run_app_info_api(tmp_path))


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


def test_openai_responses_stream_log_detail_distills_completed_response(tmp_path: Path):
    asyncio.run(_run_openai_responses_stream_log_detail_distills_completed_response(tmp_path))


def test_request_log_detail_api(tmp_path: Path):
    asyncio.run(_run_request_log_detail_api(tmp_path))


async def _run_api_bootstrap_and_site_crud(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-crud.db')

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            assert login.status_code == 200
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            sites_before = await client.get('/api/admin/sites', headers=headers)
            assert sites_before.status_code == 200
            before_count = len(sites_before.json())

            created = await client.post(
                '/api/admin/sites',
                headers=headers,
                json=_site_create_payload(
                    'Test Site',
                    credentials=[
                        {'name': 'Key A', 'api_key': 'key-a', 'enabled': True},
                    ],
                    protocols=[
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
                ),
            )
            assert created.status_code == 201
            payload = created.json()
            assert payload['name'] == 'Test Site'
            assert len(payload['credentials']) == 1
            assert len(payload['protocols']) == 1
            site_id = payload['id']

            sites_after_create = await client.get('/api/admin/sites', headers=headers)
            assert sites_after_create.status_code == 200
            assert len(sites_after_create.json()) == before_count + 1

            deleted = await client.delete(f'/api/admin/sites/{site_id}', headers=headers)
            assert deleted.status_code == 204

            sites_after_delete = await client.get('/api/admin/sites', headers=headers)
            assert sites_after_delete.status_code == 200
            assert len(sites_after_delete.json()) == before_count
    finally:
        await service_module._close_app_state(service_module.app_state)


async def _run_app_info_api(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-app-info.db')

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            assert login.status_code == 200
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            response = await client.get('/api/admin/app-info', headers=headers)
            assert response.status_code == 200
            payload = response.json()
            assert payload['backend_version'] == service_module.backend_version
            assert isinstance(payload['frontend_version'], str)
            assert payload['frontend_version']
            assert payload['app_env'] == config.app_env
            assert payload['site_name'] == 'Lens'
    finally:
        await service_module._close_app_state(service_module.app_state)


async def _run_model_group_candidates_include_credential_dimension(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-candidates.db')

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            assert login.status_code == 200
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            created = await client.post(
                '/api/admin/sites',
                headers=headers,
                json=_site_create_payload(
                    'Candidate Site',
                    credentials=[
                        {'name': 'Alpha', 'api_key': 'alpha-key', 'enabled': True},
                        {'name': 'Beta', 'api_key': 'beta-key', 'enabled': True},
                    ],
                    protocols=[
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
                ),
            )
            assert created.status_code == 201
            site = created.json()
            protocol = site['protocols'][0]
            alpha = next(item for item in site['credentials'] if item['name'] == 'Alpha')
            beta = next(item for item in site['credentials'] if item['name'] == 'Beta')

            updated = await client.put(
                f"/api/admin/sites/{site['id']}",
                headers=headers,
                json=_site_update_payload(
                    site,
                    credentials=[
                        {'id': alpha['id'], 'name': alpha['name'], 'api_key': alpha['api_key'], 'enabled': True},
                        {'id': beta['id'], 'name': beta['name'], 'api_key': beta['api_key'], 'enabled': True},
                    ],
                    protocols=[
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
                ),
            )
            assert updated.status_code == 200

            candidates = await client.post(
                '/api/admin/model-group-candidates',
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
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            assert login.status_code == 200
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            created_site = await client.post(
                '/api/admin/sites',
                headers=headers,
                json=_site_create_payload(
                    'Stats Site',
                    credentials=[{'name': 'Key A', 'api_key': 'key-a', 'enabled': True}],
                    protocols=[{
                        'protocol': 'openai_chat',
                        'enabled': True,
                        'headers': {},
                        'channel_proxy': '',
                        'param_override': '',
                        'match_regex': '',
                        'bindings': [],
                        'models': [],
                    }],
                ),
            )
            assert created_site.status_code == 201
            site = created_site.json()
            protocol = site['protocols'][0]
            credential = site['credentials'][0]

            updated_site = await client.put(
                f"/api/admin/sites/{site['id']}",
                headers=headers,
                json=_site_update_payload(
                    site,
                    credentials=[{'id': credential['id'], 'name': credential['name'], 'api_key': credential['api_key'], 'enabled': True}],
                    protocols=[{
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
                ),
            )
            assert updated_site.status_code == 200

            created_group = await client.post(
                '/api/admin/model-groups',
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

            group_detail = await client.get(f"/api/admin/model-groups/{group['id']}", headers=headers)
            assert group_detail.status_code == 200
            detail_payload = group_detail.json()
            assert detail_payload['id'] == group['id']
            assert detail_payload['items'][0]['channel_id'] == protocol['id']

            missing_group = await client.get('/api/admin/model-groups/missing-group-id', headers=headers)
            assert missing_group.status_code == 404

            await service_module.app_state.domain_store.create_request_log(
                protocol='openai_chat',
                requested_model='gpt-4.1',
                matched_group_name='gpt-4.1',
                channel_id=protocol['id'],
                channel_name=protocol['id'],
                gateway_key_id='gw-test',
                status_code=200,
                success=True,
                is_stream=False,
                first_token_latency_ms=0,
                latency_ms=123,
                resolved_model='gpt-4.1',
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                input_cost_usd=0.001,
                output_cost_usd=0.002,
                total_cost_usd=0.003,
                request_content='{"model":"gpt-4.1"}',
                response_content='{"model":"gpt-4.1"}',
                attempts=[],
                error_message=None,
            )

            stats = await client.get('/api/admin/model-group-stats', headers=headers)
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
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            created_group = await client.post(
                '/api/admin/model-groups',
                headers=headers,
                json={
                    'name': 'gpt-5.4',
                    'protocol': 'openai_chat',
                    'strategy': 'round_robin',
                    'items': [],
                },
            )
            assert created_group.status_code == 201

            prices = await client.get('/api/admin/model-prices', headers=headers)
            assert prices.status_code == 200
            assert prices.json()['items'][0]['model_key'] == 'gpt-5.4'
            assert prices.json()['items'][0]['cache_read_price_per_million'] == 0.5
            assert prices.json()['items'][0]['cache_write_price_per_million'] == 1.5

            updated = await client.put(
                '/api/admin/model-prices/gpt-5.4',
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
                '/api/admin/model-prices/not-a-group',
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

            synced = await client.post('/api/admin/model-price-sync-jobs', headers=headers)
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
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            assert login.status_code == 200
            token = login.json()['access_token']
            admin_headers = {'authorization': f'Bearer {token}'}
            updated_settings = await client.put(
                '/api/admin/settings',
                headers=admin_headers,
                json={'items': [{'key': 'gateway_api_keys', 'value': 'test-gateway-key'}]},
            )
            assert updated_settings.status_code == 200

            created_site = await client.post(
                '/api/admin/sites',
                headers=admin_headers,
                json=_site_create_payload(
                    'Mixed OpenAI Site',
                    credentials=[{'name': 'Key A', 'api_key': 'key-a', 'enabled': True}],
                    protocols=[
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
                ),
            )
            assert created_site.status_code == 201
            site = created_site.json()
            credential = site['credentials'][0]
            chat_protocol = next(item for item in site['protocols'] if item['protocol'] == 'openai_chat')
            responses_protocol = next(item for item in site['protocols'] if item['protocol'] == 'openai_responses')

            updated_site = await client.put(
                f"/api/admin/sites/{site['id']}",
                headers=admin_headers,
                json=_site_update_payload(
                    site,
                    credentials=[{'id': credential['id'], 'name': credential['name'], 'api_key': credential['api_key'], 'enabled': True}],
                    protocols=[
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
                ),
            )
            assert updated_site.status_code == 200

            created_group = await client.post(
                '/api/admin/model-groups',
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
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            assert login.status_code == 200
            token = login.json()['access_token']
            admin_headers = {'authorization': f'Bearer {token}'}
            updated_settings = await client.put(
                '/api/admin/settings',
                headers=admin_headers,
                json={'items': [{'key': 'gateway_api_keys', 'value': 'test-gateway-key'}]},
            )
            assert updated_settings.status_code == 200

            created_site = await client.post(
                '/api/admin/sites',
                headers=admin_headers,
                json=_site_create_payload(
                    'Responses Site',
                    credentials=[{'name': 'Key A', 'api_key': 'key-a', 'enabled': True}],
                    protocols=[{
                        'protocol': 'openai_responses',
                        'enabled': True,
                        'headers': {},
                        'channel_proxy': '',
                        'param_override': '',
                        'match_regex': '',
                        'bindings': [],
                        'models': [],
                    }],
                ),
            )
            assert created_site.status_code == 201
            site = created_site.json()
            credential = site['credentials'][0]
            protocol = site['protocols'][0]

            updated_site = await client.put(
                f"/api/admin/sites/{site['id']}",
                headers=admin_headers,
                json=_site_update_payload(
                    site,
                    credentials=[{'id': credential['id'], 'name': credential['name'], 'api_key': credential['api_key'], 'enabled': True}],
                    protocols=[{
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
                ),
            )
            assert updated_site.status_code == 200

            created_group = await client.post(
                '/api/admin/model-groups',
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
            assert post_call['json'] == {
                'model': 'gpt-5.4',
                'input': [
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'input_text', 'text': 'hello'},
                        ],
                    }
                ],
            }
    finally:
        service_module.app_state.http.request = original_request
        await service_module._close_app_state(service_module.app_state)


async def _run_request_log_detail_api(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-request-log-detail.db')

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            assert login.status_code == 200
            token = login.json()['access_token']
            headers = {'authorization': f'Bearer {token}'}

            created = await service_module.app_state.domain_store.create_request_log(
                protocol='openai_chat',
                requested_model='gpt-4.1',
                matched_group_name='gpt-4.1',
                channel_id='channel-a',
                channel_name='Channel A',
                gateway_key_id='gw-test',
                status_code=200,
                success=True,
                is_stream=False,
                first_token_latency_ms=0,
                latency_ms=321,
                resolved_model='gpt-4.1',
                input_tokens=12,
                output_tokens=34,
                total_tokens=46,
                input_cost_usd=0.0012,
                output_cost_usd=0.0034,
                total_cost_usd=0.0046,
                request_content='{"model":"gpt-4.1","messages":[{"role":"user","content":"hello"}]}',
                response_content='{"model":"gpt-4.1","choices":[{"message":{"role":"assistant","content":"world"}}]}',
                attempts=[{'channel_id': 'channel-a', 'channel_name': 'Channel A', 'model_name': 'gpt-4.1', 'status_code': 200, 'success': True, 'duration_ms': 321}],
                error_message=None,
            )

            summary = await client.get('/api/admin/request-logs', headers=headers)
            assert summary.status_code == 200
            summary_payload = summary.json()
            assert summary_payload[0]['id'] == created.id
            assert 'request_content' not in summary_payload[0]

            detail = await client.get(f'/api/admin/request-logs/{created.id}', headers=headers)
            assert detail.status_code == 200
            payload = detail.json()
            assert payload['id'] == created.id
            assert payload['channel_name'] == 'Channel A'
            assert payload['request_content'].startswith('{"model":"gpt-4.1"')
            assert 'world' in payload['response_content']
            assert payload['attempts'][0]['channel_name'] == 'Channel A'
            assert payload['first_token_latency_ms'] == 0

            missing = await client.get('/api/admin/request-logs/999999', headers=headers)
            assert missing.status_code == 404
    finally:
        await service_module._close_app_state(service_module.app_state)


async def _run_openai_responses_stream_log_detail_distills_completed_response(tmp_path: Path):
    service_module, app, config = await _build_test_app(tmp_path / 'api-openai-responses-stream-log.db')

    sse_body = (
        'event: response.created\n'
        'data: {"type":"response.created","response":{"id":"resp_123","model":"gpt-5.4","instructions":"very long hidden instructions"}}\n\n'
        'event: response.output_text.delta\n'
        'data: {"type":"response.output_text.delta","delta":"OK"}\n\n'
        'event: response.completed\n'
        'data: {"type":"response.completed","response":{"id":"resp_123","object":"response","model":"gpt-5.4","output":[{"id":"msg_123","type":"message","role":"assistant","content":[{"type":"output_text","text":"OK","annotations":[]}]}],"usage":{"input_tokens":10,"output_tokens":2,"total_tokens":12}}}\n\n'
        'data: [DONE]\n\n'
    ).encode()

    async def fake_send(request, **kwargs):
        if request.method == 'GET' and str(request.url) == 'https://models.dev/api.json':
            return httpx.Response(200, request=request, json={})
        return httpx.Response(
            200,
            request=request,
            headers={'content-type': 'text/event-stream', 'x-request-id': 'req_stream'},
            content=sse_body,
        )

    transport = httpx.ASGITransport(app=app)
    await service_module._startup_app_state(service_module.app_state)
    original_send = service_module.app_state.http.send
    service_module.app_state.http.send = fake_send
    try:
        async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
            login = await client.post('/api/admin/session', json={'username': TEST_ADMIN_USERNAME, 'password': TEST_ADMIN_PASSWORD})
            assert login.status_code == 200
            token = login.json()['access_token']
            admin_headers = {'authorization': f'Bearer {token}'}

            updated_settings = await client.put(
                '/api/admin/settings',
                headers=admin_headers,
                json={'items': [{'key': 'gateway_api_keys', 'value': 'test-gateway-key'}]},
            )
            assert updated_settings.status_code == 200

            created_site = await client.post(
                '/api/admin/sites',
                headers=admin_headers,
                json=_site_create_payload(
                    'Responses Stream Site',
                    credentials=[{'name': 'Key A', 'api_key': 'key-a', 'enabled': True}],
                    protocols=[{
                        'protocol': 'openai_responses',
                        'enabled': True,
                        'headers': {},
                        'channel_proxy': '',
                        'param_override': '',
                        'match_regex': '',
                        'bindings': [],
                        'models': [],
                    }],
                ),
            )
            assert created_site.status_code == 201
            site = created_site.json()
            credential = site['credentials'][0]
            protocol = site['protocols'][0]

            updated_site = await client.put(
                f"/api/admin/sites/{site['id']}",
                headers=admin_headers,
                json=_site_update_payload(
                    site,
                    credentials=[{'id': credential['id'], 'name': credential['name'], 'api_key': credential['api_key'], 'enabled': True}],
                    protocols=[{
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
                ),
            )
            assert updated_site.status_code == 200

            created_group = await client.post(
                '/api/admin/model-groups',
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
                json={'model': 'gpt-5.4', 'input': 'Reply with exactly OK.'},
            )
            assert gateway_response.status_code == 200
            assert 'OK' in gateway_response.text

            summary = await client.get('/api/admin/request-logs', headers=admin_headers)
            assert summary.status_code == 200
            latest_id = summary.json()[0]['id']

            detail = await client.get(f'/api/admin/request-logs/{latest_id}', headers=admin_headers)
            assert detail.status_code == 200
            payload = detail.json()
            assert payload['protocol'] == 'openai_responses'
            assert payload['is_stream'] is True
            assert payload['response_content']
            distilled = json.loads(payload['response_content'])
            assert distilled['model'] == 'gpt-5.4'
            assert distilled['usage']['total_tokens'] == 12
            assert distilled['output'][0]['content'][0]['text'] == 'OK'
            assert 'data:' not in payload['response_content']
            assert 'very long hidden instructions' not in payload['response_content']
    finally:
        service_module.app_state.http.send = original_send
        await service_module._close_app_state(service_module.app_state)


async def _build_test_app(database_path: Path):
    from lens_api.core.db import Base
    from lens_api.core.config import Settings
    from lens_api.gateway import service as service_module
    from lens_api.persistence.admin_store import AdminStore

    config = Settings(
        database_url=f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}",
        auth_secret_key='lens-test-secret-key-with-32-bytes!!',
    )
    service_module.settings = config
    service_module.app_state = service_module.AppState()
    async with service_module.app_state.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    admin_store = AdminStore(service_module.app_state.session_factory)
    await admin_store.ensure_default_admin(TEST_ADMIN_USERNAME, TEST_ADMIN_PASSWORD)
    return service_module, service_module.app, config

