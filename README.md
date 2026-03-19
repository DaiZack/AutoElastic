# autoelastic

Bulk-load any data into Elasticsearch and search at scale.

## Installation

```bash
pip install autoelastic
```

Requires Python >=3.10.

| Dependency | Version |
| --- | --- |
| `elasticsearch[async]` | >=8.13, <9 |
| `pyarrow` | >=15.0 |
| `pydantic` | >=2.0 |
| `pydantic-settings` | >=2.0 |

## Quick Start

All methods are synchronous.

```python
from autoelastic import AutoElastic

# Connect using a context manager for automatic cleanup
with AutoElastic("http://localhost:9200") as ae:
    # Sample data
    docs = [
        {
            "name": ["Apple", "Apple Inc"],
            "address": "One Apple Park Way",
            "city": "Cupertino",
            "postal": "95014",
            "region": "California",
            "country": "US",
        },
        {
            "name": ["Google", "Alphabet Inc"],
            "address": "1600 Amphitheatre Pkwy",
            "city": "Mountain View",
            "postal": "94043",
            "region": "California",
            "country": "US",
        },
    ]
    
    # Ingest documents
    ae.ingest_dicts("businesses", docs)
    
    # Search for a name
    results = ae.search_name("businesses", "apple")
    for hit in results:
        print(f"Found: {hit['_source']['name']} in {hit['_source']['city']}")
```

## Ingestion

### ingest_dicts
`ingest_dicts(index, docs, *, id_field=None, mapping=None, shards=3, ingest_config=None)`

Bulk-index a list of dictionaries.

```python
from autoelastic import AutoElastic

with AutoElastic("http://localhost:9200") as ae:
    result = ae.ingest_dicts(
        index="my-index",
        docs=[{"id": "1", "name": ["Test"]}],
        id_field="id"
    )
    print(f"Succeeded: {result.succeeded}")
```

### ingest_parquet
`ingest_parquet(index, path, *, id_field=None, columns=None, batch_size=10000, mapping=None, shards=3, ingest_config=None)`

Efficiently stream and index data from a Parquet file.

```python
from autoelastic import AutoElastic

with AutoElastic("http://localhost:9200") as ae:
    result = ae.ingest_parquet(
        index="large-index",
        path="data.parquet",
        columns=["name", "address", "city"]
    )
```

**IngestResult**
Both methods return an `IngestResult` object with the following fields:
- `total`: Total documents processed.
- `succeeded`: Number of successful indexing operations.
- `failed`: Number of failed operations.
- `errors`: List of error details for failed documents.
- `elapsed_seconds`: Time taken for the operation.

## Search

### search_name
`search_name(index, name, **overrides)`

Search for a specific name with fuzzy matching and highlighting.

```python
results = ae.search_name("businesses", "apple", size=5, fuzziness="1")
# Result shape:
# {
#     "_id": str,
#     "_score": float,
#     "_source": dict,
#     "highlight": dict | None
# }
```

### search_names_bulk
`search_names_bulk(index, names)`

Perform multiple name searches in a single bulk request.

```python
results = ae.search_names_bulk("businesses", ["apple", "google"])
# Returns: dict[str, list[dict]] (name -> list of hits)
```

## Scanning

### scan
`scan(index, query=None, **kwargs)`

A generator that yields all documents matching a query. Note: yields `_source` dicts only (no `_id`, no `_score`).

```python
# Filtered scan example
query = {"term": {"city": "Cupertino"}}
for doc in ae.scan("businesses", query=query):
    print(doc["name"])
```

## Configuration

`AutoElasticConfig` is the top-level container for all settings.

```python
from autoelastic import AutoElasticConfig, IngestConfig

config = AutoElasticConfig(
    ingest=IngestConfig(thread_count=8)
)
ae = AutoElastic("http://localhost:9200", config=config)
```

### IngestConfig
| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `chunk_size` | `int` | `2000` | Number of documents per bulk request. |
| `max_chunk_bytes` | `int` | `15728640` | Maximum size in bytes per bulk request (15 MB). |
| `thread_count` | `int` | `4` | Number of parallel threads for parallel_bulk. |
| `queue_size` | `int` | `4` | Queue size between producer and consumer threads. |
| `max_retries` | `int` | `3` | Maximum retries per failed document. |
| `request_timeout` | `int` | `120` | Request timeout in seconds per bulk call. |
| `raise_on_error` | `bool` | `False` | If False, collect errors instead of raising. |
| `optimize_for_bulk` | `bool` | `True` | If True, disable refresh and replicas during ingest, restore after. |
| `refresh_interval_during` | `str` | `"-1"` | Refresh interval during bulk load ('-1' = disabled). |
| `replicas_during` | `int` | `0` | Number of replicas during bulk load (0 = none). |
| `refresh_interval_after` | `str` | `"1s"` | Refresh interval to restore after bulk load. |
| `replicas_after` | `int` | `1` | Number of replicas to restore after bulk load. |
| `force_merge_after` | `bool` | `True` | Force merge index segments after bulk load for search performance. |
| `max_num_segments` | `int` | `1` | Target segment count for force merge. |

### SearchConfig
| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `page_size` | `int` | `10000` | Documents per search page (PIT + search_after). |
| `pit_keep_alive` | `str` | `"5m"` | Point-in-time keep-alive duration. |
| `request_timeout` | `int` | `60` | Request timeout in seconds per search call. |
| `max_concurrent` | `int` | `5` | Maximum concurrent msearch requests. |
| `track_total_hits` | `bool` | `False` | Track total hits count (False = faster for large scans). |

### NameSearchConfig
| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `fuzziness` | `str` | `"AUTO"` | Fuzziness level for fuzzy matching (AUTO, 0, 1, 2). |
| `prefix_length` | `int` | `1` | Minimum prefix before fuzziness applies. |
| `min_score` | `float \| None` | `None` | Minimum relevance score threshold (None = no threshold). |
| `size` | `int` | `20` | Default number of results to return. |
| `highlight` | `bool` | `True` | Include match highlights in results. |

## Connection Options

### Basic Authentication
```python
ae = AutoElastic("http://localhost:9200", basic_auth=("user", "pass"))
```

### API Key
```python
ae = AutoElastic(api_key="your-api-key")
```

### Elastic Cloud
```python
ae = AutoElastic(cloud_id="your-cloud-id", api_key="your-api-key")
```

### Context Manager
```python
with AutoElastic("http://localhost:9200") as ae:
    # Use ae here
    pass
# Closes automatically
```

### Other Methods
- `ping()`: Returns `True` if the cluster is reachable.
- `close()`: Closes the underlying Elasticsearch client.

## Data Format

Documents are expected to be dictionaries. The `name` field is special: it should be a `list[str]`. Each element in the list is indexed separately, allowing for multiple aliases or variations of a name.

```python
{
    "name": ["Apple", "Apple Inc"],
    "address": "One Apple Park Way",
    "city": "Cupertino",
    "postal": "95014",
    "region": "California",
    "country": "US",
}
```

## Examples

Refer to the following scripts for real-world usage patterns:

- `examples/ingest_parquet.py`: Bulk-load data from Parquet files.
  ```bash
  python examples/ingest_parquet.py --path data.parquet --index businesses
  ```
- `examples/search_names.py`: Search for business names.
  ```bash
  python examples/search_names.py --index businesses --name "apple"
  python examples/search_names.py --index businesses --names "apple" "google" "microsoft"
  ```

## License

MIT
