from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.helpers import parallel_bulk

from autoelastic.config import IngestConfig

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    total: int
    succeeded: int
    failed: int
    errors: list[dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class IngestEngine:
    """Orchestrates high-throughput bulk indexing into Elasticsearch.

    Uses parallel_bulk for parallelised ingestion with optional pre/post
    index optimisations (disable refresh and replicas during load, force
    merge after) to maximise indexing throughput.
    """

    def __init__(self, client: Elasticsearch, config: IngestConfig | None = None) -> None:
        self._client = client
        self._config = config or IngestConfig()

    def ingest(
        self,
        index: str,
        actions: Iterator[dict[str, Any]],
        *,
        create_index: bool = True,
        mapping: dict[str, Any] | None = None,
    ) -> IngestResult:
        """Bulk-index *actions* into *index* and return an IngestResult.

        Parameters
        ----------
        index:
            Target Elasticsearch index name.
        actions:
            Iterator of action dicts.  Each dict should contain ``_index``,
            optionally ``_id``, and ``_source``.
        create_index:
            When *True* (default), create the index if it does not yet exist.
        mapping:
            Optional mapping body passed verbatim to ``indices.create``.
            Ignored when the index already exists or *create_index* is False.
        """
        cfg = self._config
        client = self._client

        if create_index and not client.indices.exists(index=index):
            logger.info("Creating index %r", index)
            if mapping is not None:
                client.indices.create(index=index, body=mapping)
            else:
                client.indices.create(index=index)

        original_refresh_interval: str | None = None
        original_replicas: int | None = None

        if cfg.optimize_for_bulk:
            settings = client.indices.get_settings(index=index)
            idx_settings = settings[index]["settings"]["index"]
            original_refresh_interval = idx_settings.get("refresh_interval", "1s")
            original_replicas = int(idx_settings.get("number_of_replicas", 1))

            client.indices.put_settings(
                index=index,
                body={
                    "index": {
                        "refresh_interval": cfg.refresh_interval_during,
                        "number_of_replicas": cfg.replicas_during,
                    }
                },
            )
            logger.info(
                "Optimised index %r for bulk load (refresh_interval=%s, replicas=%d)",
                index,
                cfg.refresh_interval_during,
                cfg.replicas_during,
            )

        succeeded = 0
        failed = 0
        errors: list[dict[str, Any]] = []

        logger.info("Starting bulk ingest into index %r", index)
        start = time.perf_counter()

        try:
            # parallel_bulk yields (success: bool, info: dict) tuples for every
            # action — success=True means the document was indexed, False means
            # it failed and info contains the error details.
            for success, info in parallel_bulk(
                client,
                actions,
                chunk_size=cfg.chunk_size,
                max_chunk_bytes=cfg.max_chunk_bytes,
                thread_count=cfg.thread_count,
                queue_size=cfg.queue_size,
                raise_on_error=False,
            ):
                if success:
                    succeeded += 1
                else:
                    failed += 1
                    errors.append(info)

                total_so_far = succeeded + failed
                if total_so_far % 10_000 == 0:
                    logger.info(
                        "Ingest progress for %r: %d docs processed (%d succeeded, %d failed)",
                        index,
                        total_so_far,
                        succeeded,
                        failed,
                    )
        finally:
            if cfg.optimize_for_bulk:
                restore_interval = (
                    original_refresh_interval
                    if original_refresh_interval is not None
                    else cfg.refresh_interval_after
                )
                restore_replicas = (
                    original_replicas if original_replicas is not None else cfg.replicas_after
                )
                client.indices.put_settings(
                    index=index,
                    body={
                        "index": {
                            "refresh_interval": restore_interval,
                            "number_of_replicas": restore_replicas,
                        }
                    },
                )
                logger.info(
                    "Restored index %r settings (refresh_interval=%s, replicas=%d)",
                    index,
                    restore_interval,
                    restore_replicas,
                )

            if cfg.force_merge_after:
                logger.info("Force-merging index %r to %d segment(s)", index, cfg.max_num_segments)
                client.indices.forcemerge(index=index, max_num_segments=cfg.max_num_segments)

            client.indices.refresh(index=index)

        elapsed = time.perf_counter() - start
        total = succeeded + failed

        logger.info(
            "Ingest complete for %r: %d total, %d succeeded, %d failed in %.2fs",
            index,
            total,
            succeeded,
            failed,
            elapsed,
        )

        return IngestResult(
            total=total,
            succeeded=succeeded,
            failed=failed,
            errors=errors,
            elapsed_seconds=elapsed,
        )
