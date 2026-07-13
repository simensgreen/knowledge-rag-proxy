"""SurrealDB connection and schema bootstrap."""

from __future__ import annotations

import logging
import threading
from typing import Any

from surrealdb import Surreal

from server.engine.store_schema import (
    build_schema_statements,
    parse_fulltext_languages,
    schema_statement_fallbacks,
)
from server.env_config import (
    get_embedding_dimensions,
    get_fulltext_languages_raw,
    get_surreal_database,
    get_surreal_namespace,
    get_surreal_url,
)

logger = logging.getLogger(__name__)


class SurrealStore:
    def __init__(self, url: str, namespace: str, database: str) -> None:
        self.url = url
        self.namespace = namespace
        self.database = database
        self.lock = threading.Lock()
        self.connection = Surreal(url)

    def connect(self) -> None:
        self.connection.connect()
        self.connection.use(self.namespace, self.database)

    def close(self) -> None:
        self.connection.close()

    def query(self, sql: str, variables: dict[str, Any] | None = None) -> Any:
        with self.lock:
            if variables is None:
                return self.connection.query(sql)
            return self.connection.query(sql, variables)

    def ensure_schema(
        self,
        fulltext_languages: list[str],
        embedding_dimensions: int,
        defer_indexes: bool = True,
    ) -> None:
        statements = build_schema_statements(
            fulltext_languages=fulltext_languages,
            embedding_dimensions=embedding_dimensions,
            defer_indexes=defer_indexes,
        )
        for statement in statements:
            self.run_schema_statement(statement)

    def run_schema_statement(self, statement: str) -> None:
        last_error: Exception | None = None
        for candidate in schema_statement_fallbacks(statement):
            try:
                self.query(candidate)
                if candidate != statement:
                    logger.debug("Schema statement applied via fallback: %s", candidate[:100])
                return
            except Exception as error:
                if "already exists" in str(error).lower():
                    return
                last_error = error
        if last_error is not None:
            raise last_error


def open_store() -> SurrealStore:
    return SurrealStore(
        url=get_surreal_url(),
        namespace=get_surreal_namespace(),
        database=get_surreal_database(),
    )


def ensure_store_schema(store: SurrealStore | None = None) -> SurrealStore:
    embedding_dimensions = get_embedding_dimensions()
    fulltext_languages = parse_fulltext_languages(get_fulltext_languages_raw())
    owned_store = store is None
    active_store = store or open_store()

    try:
        if owned_store:
            active_store.connect()
        logger.info(
            "Applying SurrealDB schema (languages=%s, embedding_dimensions=%d)",
            ", ".join(fulltext_languages),
            embedding_dimensions,
        )
        active_store.ensure_schema(
            fulltext_languages=fulltext_languages,
            embedding_dimensions=embedding_dimensions,
        )
        logger.info("SurrealDB schema is ready")
        return active_store
    except Exception:
        if owned_store:
            active_store.close()
        raise
