"""Server endpoint tests — stubs until Phase 1."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.skip(reason="Phase 1: implement orchestrator-backed endpoints")
def test_search_returns_hits(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/search",
        json={"query": "example"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "hits" in response.json()


def test_health_unauthenticated(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True


def test_search_requires_bearer(client: TestClient) -> None:
    response = client.post("/search", json={"query": "example"})
    assert response.status_code == 401


def test_search_not_implemented(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/search",
        json={"query": "example"},
        headers=auth_headers,
    )
    assert response.status_code == 501
