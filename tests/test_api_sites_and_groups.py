from __future__ import annotations

import asyncio
from pathlib import Path

import httpx


def test_api_bootstrap_and_site_crud(tmp_path: Path):
    asyncio.run(_run_api_bootstrap_and_site_crud(tmp_path))


def test_model_group_candidates_include_credential_dimension(tmp_path: Path):
    asyncio.run(_run_model_group_candidates_include_credential_dimension(tmp_path))


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
                            'proxy': False,
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
                            'proxy': False,
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
                            'proxy': False,
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
                    'name': 'gpt-4.1',
                    'match_regex': '',
                    'exclude_items': [],
                },
            )
            assert candidates.status_code == 200
            payload = candidates.json()
            keys = {(item['provider_id'], item['credential_id'], item['model_name']) for item in payload['candidates']}
            assert (protocol['id'], alpha['id'], 'gpt-4.1') in keys
            assert (protocol['id'], beta['id'], 'gpt-4.1') in keys
            assert (protocol['id'], beta['id'], 'gpt-4.1-mini') in keys
            assert all(item['provider_name'] == 'Candidate Site' for item in payload['candidates'])

            matched = {(item['credential_id'], item['model_name']) for item in payload['matched_items']}
            assert (alpha['id'], 'gpt-4.1') in matched
            assert (beta['id'], 'gpt-4.1') in matched
            assert (beta['id'], 'gpt-4.1-mini') not in matched
    finally:
        await service_module._close_app_state(service_module.app_state)


async def _build_test_app(database_path: Path):
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
    return service_module, service_module.app, config
