from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.gateway.service.app_state import AppState


@pytest.fixture
def client(app_state: AppState, tmp_path: Path) -> Iterator[TestClient]:
    static_dir = tmp_path / "ui"
    for relative_path, content in {
        "index.html": "<h1>Lens home</h1>",
        "reports/index.html": "<h1>Lens reports</h1>",
        "readme.txt": "Lens static resource",
        "_next/static/chunks/app.js": "console.log('Lens');",
        "api/private/index.html": "<h1>Reserved path must stay hidden</h1>",
    }.items():
        file_path = static_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
    (tmp_path / "outside.txt").write_text("Outside the UI root", encoding="utf-8")

    with TestClient(
        create_app(ui_static_dir=str(static_dir), state=app_state),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client


def test_custom_ui_serves_pages_and_cached_assets_within_its_root(
    client: TestClient,
) -> None:
    for path, content in (
        ("/", "<h1>Lens home</h1>"),
        ("/reports", "<h1>Lens reports</h1>"),
        ("/readme.txt", "Lens static resource"),
    ):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert response.text == content

    asset = client.get("/_next/static/chunks/app.js")
    assert asset.status_code == 200, asset.text
    assert asset.text == "console.log('Lens');"
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"

    cached_asset = client.get(
        "/_next/static/chunks/app.js", headers={"If-None-Match": asset.headers["etag"]}
    )
    assert cached_asset.status_code == 304
    assert cached_asset.headers["cache-control"] == asset.headers["cache-control"]

    for path in ("/api/private", "/%2e%2e%2foutside.txt", "/%2e%2e%5coutside.txt"):
        response = client.get(path)
        assert response.status_code == 404, response.text
