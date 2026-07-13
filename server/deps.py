"""FastAPI dependencies."""

from __future__ import annotations

from server.engine.protocols import Engine, Parser
from server.engine.stub_engine import StubEngine
from server.engine.stub_parser import StubParser

_engine: Engine | None = None
_parser: Parser | None = None


def get_engine_dep() -> Engine:
    global _engine
    if _engine is None:
        _engine = StubEngine()
    return _engine


def get_parser_dep() -> Parser:
    global _parser
    if _parser is None:
        _parser = StubParser()
    return _parser
