from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def stream_parquet(
    path: str | Path,
    index: str,
    *,
    batch_size: int = 10_000,
    id_field: str | None = None,
    columns: list[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream rows from a Parquet file as Elasticsearch action dicts."""
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=columns):
        col_arrays = batch.to_pydict()
        num_rows = batch.num_rows
        keys = list(col_arrays.keys())
        for i in range(num_rows):
            row: dict[str, Any] = {k: col_arrays[k][i] for k in keys}
            action: dict[str, Any] = {"_index": index, "_source": row}
            if id_field is not None:
                action["_id"] = row[id_field]
            yield action


def count_rows(path: str | Path) -> int:
    """Return the total row count of a Parquet file without reading its data."""
    return pq.ParquetFile(path).metadata.num_rows


def detect_schema(path: str | Path) -> dict[str, str]:
    """Return a mapping of column name to Arrow type string for a Parquet file."""
    schema = pq.ParquetFile(path).schema_arrow
    return {schema.field(i).name: str(schema.field(i).type) for i in range(len(schema))}
