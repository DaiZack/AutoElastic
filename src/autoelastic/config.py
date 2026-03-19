"""Configuration for AutoElastic ingest and search operations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IngestConfig:
    """Tuning parameters for bulk ingestion.

    Defaults are optimized for large datasets (50M+ records).
    """

    chunk_size: int = 2000
    """Number of documents per bulk request."""

    max_chunk_bytes: int = 15 * 1024 * 1024
    """Maximum size in bytes per bulk request (15 MB)."""

    thread_count: int = 4
    """Number of parallel threads for parallel_bulk."""

    queue_size: int = 4
    """Queue size between producer and consumer threads."""

    max_retries: int = 3
    """Maximum retries per failed document."""

    request_timeout: int = 120
    """Request timeout in seconds per bulk call."""

    raise_on_error: bool = False
    """If False, collect errors instead of raising."""

    optimize_for_bulk: bool = True
    """If True, disable refresh and replicas during ingest, restore after."""

    refresh_interval_during: str = "-1"
    """Refresh interval during bulk load ('-1' = disabled)."""

    replicas_during: int = 0
    """Number of replicas during bulk load (0 = none)."""

    refresh_interval_after: str = "1s"
    """Refresh interval to restore after bulk load."""

    replicas_after: int = 1
    """Number of replicas to restore after bulk load."""

    force_merge_after: bool = True
    """Force merge index segments after bulk load for search performance."""

    max_num_segments: int = 1
    """Target segment count for force merge."""


@dataclass(frozen=True)
class SearchConfig:
    """Tuning parameters for bulk search operations."""

    page_size: int = 10_000
    """Documents per search page (PIT + search_after)."""

    pit_keep_alive: str = "5m"
    """Point-in-time keep-alive duration."""

    request_timeout: int = 60
    """Request timeout in seconds per search call."""

    max_concurrent: int = 5
    """Maximum concurrent msearch requests."""

    track_total_hits: bool = False
    """Track total hits count (False = faster for large scans)."""


@dataclass(frozen=True)
class NameSearchConfig:
    """Configuration for business name search behavior."""

    fuzziness: str = "AUTO"
    """Fuzziness level for fuzzy matching (AUTO, 0, 1, 2)."""

    prefix_length: int = 1
    """Minimum prefix before fuzziness applies."""

    min_score: float | None = None
    """Minimum relevance score threshold (None = no threshold)."""

    size: int = 20
    """Default number of results to return."""

    highlight: bool = True
    """Include match highlights in results."""


@dataclass
class AutoElasticConfig:
    """Top-level configuration container."""

    ingest: IngestConfig = field(default_factory=IngestConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    name_search: NameSearchConfig = field(default_factory=NameSearchConfig)
