from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from autoelastic.ingest.sources.parquet import count_rows, detect_schema, stream_parquet


def _write_test_parquet(path: Path, num_rows: int = 5) -> None:
    names = pa.array(
        [["Apple", "Apple Inc"], ["Google", "Alphabet"], ["Meta"], ["Amazon", "AWS"], ["Tesla"]],
        type=pa.list_(pa.string()),
    )
    addresses = pa.array(
        ["1 Apple Park", "1600 Amphitheatre", "1 Hacker Way", "410 Terry Ave", "3500 Deer Creek"],
    )
    cities = pa.array(["Cupertino", "Mountain View", "Menlo Park", "Seattle", "Palo Alto"])
    postals = pa.array(["95014", "94043", "94025", "98109", "94304"])
    regions = pa.array(["CA", "CA", "CA", "WA", "CA"])
    countries = pa.array(["US", "US", "US", "US", "US"])

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
    pq.write_table(table, path)


class TestStreamParquet:
    def test_yields_correct_number_of_actions(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)

        actions = list(stream_parquet(str(path), "test-index"))
        assert len(actions) == 5

    def test_action_has_correct_structure(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)

        action = next(iter(stream_parquet(str(path), "test-index")))
        assert action["_index"] == "test-index"
        assert "_source" in action
        assert "name" in action["_source"]

    def test_name_column_is_python_list(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)

        action = next(iter(stream_parquet(str(path), "test-index")))
        names = action["_source"]["name"]
        assert isinstance(names, list)
        assert names == ["Apple", "Apple Inc"]

    def test_id_field_extracts_id(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)

        action = next(iter(stream_parquet(str(path), "test-index", id_field="postal")))
        assert action["_id"] == "95014"

    def test_columns_filter(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)

        action = next(iter(stream_parquet(str(path), "test-index", columns=["name", "city"])))
        assert "name" in action["_source"]
        assert "city" in action["_source"]
        assert "address" not in action["_source"]

    def test_batch_size_doesnt_affect_total(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)

        actions_small = list(stream_parquet(str(path), "test-index", batch_size=2))
        actions_big = list(stream_parquet(str(path), "test-index", batch_size=100))
        assert len(actions_small) == len(actions_big) == 5


class TestCountRows:
    def test_returns_correct_count(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)
        assert count_rows(str(path)) == 5


class TestDetectSchema:
    def test_detects_all_columns(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)

        schema = detect_schema(str(path))
        assert set(schema.keys()) == {"name", "address", "city", "postal", "region", "country"}

    def test_name_is_list_type(self, tmp_path):
        path = tmp_path / "test.parquet"
        _write_test_parquet(path)

        schema = detect_schema(str(path))
        assert "list" in schema["name"]
        assert "string" in schema["name"]
