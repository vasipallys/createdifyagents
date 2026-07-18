"""Release-blocker regression tests for safe configuration and persistence."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

import story_pointer.api as api_module
import story_pointer.dsl_api as dsl_module
from story_pointer.config import JiraInstance, Settings


def test_production_rejects_wildcard_cors_and_missing_dsl_key():
    settings = Settings(environment="production", cors_origins="*")
    try:
        settings.validate_production_ready()
    except RuntimeError as exc:
        assert "CORS_ORIGINS" in str(exc)
    else:  # pragma: no cover - documents the required failure
        raise AssertionError("unsafe production settings were accepted")

    settings = Settings(
        environment="production",
        cors_origins="https://story-pointer.example",
        dsl_write_api_key="",
    )
    try:
        settings.validate_production_ready()
    except RuntimeError as exc:
        assert "DSL_WRITE_API_KEY" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("production without a DSL key was accepted")


def test_jira_instances_endpoint_never_returns_credentials(monkeypatch):
    instance = JiraInstance(
        name="banking-test",
        base_url="https://jira.example",
        email="person@example.com",
        token="top-secret-token",
        username="admin",
        password="top-secret-password",
    )
    monkeypatch.setattr(
        api_module,
        "get_settings",
        lambda: SimpleNamespace(jira_config=lambda: [instance]),
    )

    with TestClient(api_module.app) as client:
        response = client.get("/jira/instances")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "instances": [{"name": "banking-test", "version": "v3", "auth_type": "pat"}]
    }
    serialized = response.text.lower()
    assert "top-secret" not in serialized
    assert "password" not in serialized
    assert "token" not in serialized


def test_upload_limit_is_enforced_before_spreadsheet_parsing(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "get_settings",
        lambda: SimpleNamespace(max_upload_bytes=4),
    )

    with TestClient(api_module.app) as client:
        response = client.post(
            "/upload",
            files={"file": ("stories.csv", b"12345", "text/csv")},
        )

    assert response.status_code == 413
    assert "4 bytes" in response.json()["detail"]


def test_batch_limit_is_enforced_before_streaming(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "get_settings",
        lambda: SimpleNamespace(max_batch_size=1),
    )

    with TestClient(api_module.app) as client:
        response = client.post(
            "/estimate/batch",
            json={"stories": [{"title": "One"}, {"title": "Two"}]},
        )

    assert response.status_code == 413
    assert "1 stories" in response.json()["detail"]


def test_dsl_save_requires_key_is_atomic_and_uses_revision(monkeypatch):
    source = (Path(__file__).parents[1] / "dsl" / "graph_http.yml").read_text(encoding="utf-8")
    test_dir = Path(__file__).parent / f".dsl-test-{uuid4().hex}"
    test_dir.mkdir()
    monkeypatch.setattr(dsl_module, "DSL_DIR", test_dir)
    monkeypatch.setattr(
        dsl_module,
        "get_settings",
        lambda: SimpleNamespace(max_dsl_bytes=1024 * 1024, dsl_write_api_key="write-secret"),
    )
    monkeypatch.setattr(
        dsl_module,
        "_inspect_dsl",
        lambda _dsl: {"loadable": True, "dependencies": [], "error": ""},
    )

    try:
        with TestClient(api_module.app) as client:
            denied = client.post("/dsl/save", json={"name": "copy.yml", "dsl": source})
            created = client.post(
                "/dsl/save",
                headers={"X-DSL-API-Key": "write-secret"},
                json={"name": "copy.yml", "dsl": source},
            )
            conflict = client.post(
                "/dsl/save",
                headers={"X-DSL-API-Key": "write-secret"},
                json={"name": "copy.yml", "dsl": source},
            )
            updated = client.post(
                "/dsl/save",
                headers={"X-DSL-API-Key": "write-secret"},
                json={"name": "copy.yml", "dsl": source, "revision": created.json()["revision"]},
            )

        assert denied.status_code == 401
        assert created.status_code == 200
        assert conflict.status_code == 409
        assert updated.status_code == 200
        assert (test_dir / "copy.yml").read_text(encoding="utf-8") == source
        assert not list(test_dir.glob(".dsl-*.tmp"))
    finally:
        for child in test_dir.iterdir():
            child.unlink()
        test_dir.rmdir()
