from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from elasticsearch import Elasticsearch

from autoelastic.config import (
    AutoElasticConfig,
    IngestConfig,
)
from autoelastic.ingest.engine import IngestEngine, IngestResult
from autoelastic.ingest.sources.parquet import count_rows, detect_schema, stream_parquet
from autoelastic.schema.mapping import build_index_body

logger = logging.getLogger(__name__)


class AutoElastic:
    def __init__(
        self,
        hosts: str | list[str] | None = None,
        *,
        cloud_id: str | None = None,
        api_key: str | tuple[str, str] | None = None,
        basic_auth: tuple[str, str] | None = None,
        ca_certs: str | None = None,
        verify_certs: bool = True,
        request_timeout: int = 30,
        max_retries: int = 3,
        config: AutoElasticConfig | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "request_timeout": request_timeout,
            "max_retries": max_retries,
        }
        if hosts:
            kwargs["hosts"] = hosts if isinstance(hosts, list) else [hosts]
        if cloud_id:
            kwargs["cloud_id"] = cloud_id
        if api_key:
            kwargs["api_key"] = api_key
        if basic_auth:
            kwargs["basic_auth"] = basic_auth
        if ca_certs:
            kwargs["ca_certs"] = ca_certs
            kwargs["verify_certs"] = verify_certs

        self._client = Elasticsearch(**kwargs)
        self._config = config or AutoElasticConfig()

    @property
    def client(self) -> Elasticsearch:
        return self._client

    @property
    def config(self) -> AutoElasticConfig:
        return self._config

    def ping(self) -> bool:
        return self._client.ping()

    def ingest_parquet(
        self,
        index: str,
        path: str,
        *,
        id_field: str | None = None,
        columns: list[str] | None = None,
        batch_size: int = 10_000,
        mapping: dict[str, Any] | None = None,
        shards: int = 3,
        ingest_config: IngestConfig | None = None,
    ) -> IngestResult:
        cfg = ingest_config or self._config.ingest

        if mapping is None:
            mapping = build_index_body(shards=shards)

        total_rows = count_rows(path)
        logger.info("Parquet file %s has %d rows", path, total_rows)

        actions = stream_parquet(
            path,
            index,
            batch_size=batch_size,
            id_field=id_field,
            columns=columns,
        )

        engine = IngestEngine(self._client, cfg)
        return engine.ingest(index, actions, mapping=mapping)

    def ingest_dicts(
        self,
        index: str,
        docs: list[dict[str, Any]] | Any,
        *,
        id_field: str | None = None,
        mapping: dict[str, Any] | None = None,
        shards: int = 3,
        ingest_config: IngestConfig | None = None,
    ) -> IngestResult:
        cfg = ingest_config or self._config.ingest

        if mapping is None:
            mapping = build_index_body(shards=shards)

        def _actions() -> Iterator[dict[str, Any]]:
            for doc in docs:
                action: dict[str, Any] = {"_index": index, "_source": doc}
                if id_field and id_field in doc:
                    action["_id"] = doc[id_field]
                yield action

        engine = IngestEngine(self._client, cfg)
        return engine.ingest(index, _actions(), mapping=mapping)

    def search_name(
        self, index: str, name: str, *, filters: dict[str, str] | None = None, **overrides: Any
    ) -> list[dict[str, Any]]:
        from autoelastic.search.query import NameSearch

        searcher = NameSearch(self._client, self._config.name_search)
        return searcher.search(index, name, filters=filters, **overrides)

    def search_names_bulk(
        self, index: str, names: list[str], *, filters: dict[str, str] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        from autoelastic.search.query import NameSearch

        searcher = NameSearch(self._client, self._config.name_search)
        return searcher.search_bulk(index, names, filters=filters)

    def scan(
        self, index: str, query: dict[str, Any] | None = None, **kwargs: Any
    ) -> Iterator[dict[str, Any]]:
        from autoelastic.search.bulk import BulkSearch

        searcher = BulkSearch(self._client, self._config.search)
        return searcher.scan(index, query=query, **kwargs)

    def parquet_schema(self, path: str) -> dict[str, str]:
        return detect_schema(path)

    def parquet_row_count(self, path: str) -> int:
        return count_rows(path)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AutoElastic:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
