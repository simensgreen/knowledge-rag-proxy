"""Pytest fixtures for server tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("GRIM_DOCUMENTS_DIR", str(_REPO_ROOT / "documents"))

from server.app import app  # noqa: E402
from server.deps import get_engine_dep, get_parser_dep  # noqa: E402
from server.engine.stub_engine import StubEngine  # noqa: E402
from server.engine.stub_parser import StubParser  # noqa: E402


@pytest.fixture
def temp_dirs(tmp_path: Path) -> dict[str, Path]:
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    return {"documents_dir": documents_dir}


@pytest.fixture
def stub_engine(temp_dirs: dict[str, Path]) -> StubEngine:
    del temp_dirs
    return StubEngine()


@pytest.fixture
def stub_parser() -> StubParser:
    return StubParser()


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "test-token-for-pytest"
    monkeypatch.setenv("GRIM_BEARER", token)
    return token


@pytest.fixture
def client(
    api_key: str,
    stub_engine: StubEngine,
    stub_parser: StubParser,
    temp_dirs: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    del api_key
    monkeypatch.setenv("GRIM_WATCH_DISABLED", "1")
    monkeypatch.setenv("GRIM_DOCUMENTS_DIR", str(temp_dirs["documents_dir"]))

    app.dependency_overrides[get_engine_dep] = lambda: stub_engine
    app.dependency_overrides[get_parser_dep] = lambda: stub_parser
    monkeypatch.setattr("server.env_config.get_allowed_roots", lambda: [temp_dirs["documents_dir"]])
    monkeypatch.setattr("server.paths.documents_root", lambda: temp_dirs["documents_dir"])
    monkeypatch.setattr("server.app.probe_documents_dir", lambda: None)
    monkeypatch.setattr("server.app.start_watchers", lambda: None)
    monkeypatch.setattr("server.app.stop_watchers", lambda: None)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
