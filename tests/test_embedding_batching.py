"""Unit tests for embedding batching and transient-failure retry."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from openai import APIError

from server.engine import embedding as embedding_module
from server.engine.embedding import OpenAIEmbeddingProvider
from server.env_config import ProviderConfig


class _FakeAPIError(APIError):
    def __init__(self, message: str = "LM Link connection closed.") -> None:
        self.message = message


@dataclass
class _Item:
    embedding: list[float]


@dataclass
class _Response:
    data: list[_Item]


class _FakeClient:
    """Records batch sizes and can fail the first N calls with a transient error."""

    def __init__(self, dimensions: int, fail_first: int = 0) -> None:
        self.dimensions = dimensions
        self.fail_first = fail_first
        self.calls = 0
        self.batch_sizes: list[int] = []
        self.embeddings = self

    def create(self, *, input: list[str], model: str, dimensions: int) -> _Response:
        self.calls += 1
        if self.calls <= self.fail_first:
            raise _FakeAPIError()
        self.batch_sizes.append(len(input))
        return _Response(data=[_Item([0.0] * self.dimensions) for _ in input])


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedding_module.time, "sleep", lambda _seconds: None)


def _provider(monkeypatch: pytest.MonkeyPatch, dimensions: int = 4) -> OpenAIEmbeddingProvider:
    monkeypatch.setenv("GRIM_EMBEDDING_DIMENSIONS", str(dimensions))
    provider = OpenAIEmbeddingProvider(ProviderConfig(base_url="http://x", token="t", model="m"))
    return provider


def test_embed_splits_into_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(monkeypatch)
    fake = _FakeClient(provider.dimensions)
    provider.client = fake

    total = embedding_module.EMBEDDING_BATCH_SIZE * 2 + 3
    vectors = provider.embed(["text"] * total)

    assert len(vectors) == total
    assert fake.batch_sizes == [
        embedding_module.EMBEDDING_BATCH_SIZE,
        embedding_module.EMBEDDING_BATCH_SIZE,
        3,
    ]


def test_embed_retries_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(monkeypatch)
    fake = _FakeClient(provider.dimensions, fail_first=2)
    provider.client = fake

    vectors = provider.embed(["a", "b"])

    assert len(vectors) == 2
    assert fake.calls == 3  # two failures then success


def test_embed_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(monkeypatch)
    fake = _FakeClient(provider.dimensions, fail_first=embedding_module.EMBEDDING_MAX_ATTEMPTS)
    provider.client = fake

    with pytest.raises(APIError):
        provider.embed(["a"])
    assert fake.calls == embedding_module.EMBEDDING_MAX_ATTEMPTS


def test_embed_empty_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider(monkeypatch)
    provider.client = _FakeClient(provider.dimensions)
    assert provider.embed([]) == []
