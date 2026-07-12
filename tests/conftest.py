"""Pytest fixtures for server tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from server.app import app


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    token = "test-token-for-pytest"
    monkeypatch.setenv("KB_PROXY_API_KEY", token)
    return token


@pytest.fixture
def client(api_key: str) -> TestClient:
    del api_key
    return TestClient(app)


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}
