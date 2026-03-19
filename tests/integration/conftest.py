"""Shared fixtures for autoelastic integration tests."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from elasticsearch import Elasticsearch

from autoelastic.client import AutoElastic
from autoelastic.config import IngestConfig
from autoelastic.schema.mapping import build_index_body

# ---------------------------------------------------------------------------
# .env loading — no python-dotenv dependency
# ---------------------------------------------------------------------------

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"

_env_vars: dict[str, str] = {}
if _ENV_PATH.exists():
    with open(_ENV_PATH) as _fh:
        for _line in _fh:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _env_vars[_k.strip()] = _v.strip()

_ES_PASS = _env_vars.get("es_pass") or os.environ.get("ES_PASS", "elastic")

ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://10.120.1.102:9200")
ES_BASIC_AUTH: tuple[str, str] = ("elastic", _ES_PASS)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_BUSINESSES = [
    {
        "name": ["Apple", "Apple Inc"],
        "address": "One Apple Park Way",
        "city": "Cupertino",
        "postal": "95014",
        "region": "California",
        "country": "US",
    },
    {
        "name": ["Google", "Google LLC", "Alphabet Inc"],
        "address": "1600 Amphitheatre Pkwy",
        "city": "Mountain View",
        "postal": "94043",
        "region": "California",
        "country": "US",
    },
    {
        "name": ["Microsoft", "Microsoft Corporation"],
        "address": "One Microsoft Way",
        "city": "Redmond",
        "postal": "98052",
        "region": "Washington",
        "country": "US",
    },
    {
        "name": ["Amazon", "Amazon.com Inc"],
        "address": "410 Terry Ave N",
        "city": "Seattle",
        "postal": "98109",
        "region": "Washington",
        "country": "US",
    },
    {
        "name": ["Meta", "Meta Platforms Inc", "Facebook"],
        "address": "1 Hacker Way",
        "city": "Menlo Park",
        "postal": "94025",
        "region": "California",
        "country": "US",
    },
    {
        "name": ["Netflix", "Netflix Inc"],
        "address": "100 Winchester Circle",
        "city": "Los Gatos",
        "postal": "95032",
        "region": "California",
        "country": "US",
    },
    {
        "name": ["Tesla", "Tesla Inc"],
        "address": "3500 Deer Creek Rd",
        "city": "Palo Alto",
        "postal": "94304",
        "region": "California",
        "country": "US",
    },
    {
        "name": ["Nvidia", "Nvidia Corporation"],
        "address": "2788 San Tomas Expy",
        "city": "Santa Clara",
        "postal": "95051",
        "region": "California",
        "country": "US",
    },
    {
        "name": ["Apple Leisure Group"],
        "address": "2 Manhattanville Rd",
        "city": "Purchase",
        "postal": "10577",
        "region": "New York",
        "country": "US",
    },
    {
        "name": ["Applebee's", "Applebee's International Inc"],
        "address": "8140 Ward Pkwy",
        "city": "Kansas City",
        "postal": "64114",
        "region": "Missouri",
        "country": "US",
    },
]

# ---------------------------------------------------------------------------
# Elasticsearch / AutoElastic session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def es_client():
    """Raw Elasticsearch client — session-scoped."""
    client = Elasticsearch(
        hosts=[ES_URL],
        basic_auth=ES_BASIC_AUTH,
    )
    if not client.ping():
        client.close()
        pytest.skip(f"Elasticsearch not reachable at {ES_URL}")
    yield client
    client.close()


@pytest.fixture(scope="session")
def ae_client():
    """AutoElastic client — session-scoped."""
    client = AutoElastic(hosts=ES_URL, basic_auth=ES_BASIC_AUTH)
    if not client.ping():
        client.close()
        pytest.skip(f"Elasticsearch not reachable at {ES_URL}")
    yield client
    client.close()


# ---------------------------------------------------------------------------
# Per-test index management fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def index_name() -> str:
    """Return a unique test index name."""
    return f"test-autoelastic-{uuid4().hex[:12]}"


@pytest.fixture
def cleanup_index(ae_client):
    """Factory fixture — call _register(name) to track indices for teardown."""
    registered: list[str] = []

    def _register(name: str) -> None:
        registered.append(name)

    yield _register

    for idx in registered:
        try:
            ae_client.client.indices.delete(index=idx, ignore_unavailable=True)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Parquet fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_parquet(tmp_path) -> str:
    """Write SAMPLE_BUSINESSES to a Parquet file and return its path as str."""
    names = pa.array(
        [biz["name"] for biz in SAMPLE_BUSINESSES],
        type=pa.list_(pa.string()),
    )
    addresses = pa.array([biz["address"] for biz in SAMPLE_BUSINESSES])
    cities = pa.array([biz["city"] for biz in SAMPLE_BUSINESSES])
    postals = pa.array([biz["postal"] for biz in SAMPLE_BUSINESSES])
    regions = pa.array([biz["region"] for biz in SAMPLE_BUSINESSES])
    countries = pa.array([biz["country"] for biz in SAMPLE_BUSINESSES])

    table = pa.table(
        {
            "name": names,
            "address": addresses,
            "city": cities,
            "postal": postals,
            "region": regions,
            "country": countries,
        }
    )
    path = tmp_path / "sample_businesses.parquet"
    pq.write_table(table, path)
    return str(path)


# ---------------------------------------------------------------------------
# IngestConfig fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def fast_ingest_config() -> IngestConfig:
    """Lightweight IngestConfig for integration tests."""
    return IngestConfig(
        chunk_size=100,
        thread_count=1,
        queue_size=1,
        max_retries=1,
        request_timeout=30,
        optimize_for_bulk=True,
        force_merge_after=False,
        replicas_after=0,
    )


# ---------------------------------------------------------------------------
# Seeded index fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_index(ae_client, fast_ingest_config):
    """Create a unique index pre-loaded with SAMPLE_BUSINESSES, yield its name."""
    idx = f"test-autoelastic-{uuid4().hex[:12]}"
    mapping = build_index_body(shards=1, replicas=0)
    ae_client.ingest_dicts(
        idx,
        SAMPLE_BUSINESSES,
        mapping=mapping,
        ingest_config=fast_ingest_config,
    )
    ae_client.client.indices.refresh(index=idx)
    yield idx
    try:
        ae_client.client.indices.delete(index=idx, ignore_unavailable=True)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# pytest hook — auto-mark integration tests
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(items):
    """Auto-add pytest.mark.integration to every test in an integration/ path."""
    integration_mark = pytest.mark.integration
    for item in items:
        if "integration" in str(item.nodeid):
            item.add_marker(integration_mark)
