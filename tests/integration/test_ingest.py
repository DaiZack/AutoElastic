"""Integration tests for AutoElastic ingest — dicts and Parquet sources."""

from __future__ import annotations

import pytest

from autoelastic.schema.mapping import build_index_body
from tests.integration.conftest import SAMPLE_BUSINESSES


@pytest.mark.integration
class TestIngestDicts:
    """Integration tests for ingest_dicts()."""

    def test_ingest_creates_index_and_loads_docs(
        self,
        ae_client,
        index_name,
        cleanup_index,
        fast_ingest_config,
    ):
        """ingest_dicts() creates the index and returns correct result counts."""
        idx = index_name
        cleanup_index(idx)

        result = ae_client.ingest_dicts(
            idx,
            SAMPLE_BUSINESSES,
            mapping=build_index_body(shards=1, replicas=0),
            ingest_config=fast_ingest_config,
        )

        assert result.succeeded == 10
        assert result.failed == 0
        assert result.total == 10
        assert result.elapsed_seconds > 0

    def test_ingest_docs_are_searchable(self, ae_client, seeded_index):
        """Documents ingested via ingest_dicts() are searchable by count."""
        count = ae_client.client.count(index=seeded_index)["count"]
        assert count == 10

    def test_ingest_mapping_applied_correctly(self, ae_client, seeded_index):
        """ingest_dicts() applies the business-entity mapping to the index."""
        mapping = ae_client.client.indices.get_mapping(index=seeded_index)
        props = mapping[seeded_index]["mappings"]["properties"]

        # name is a multi-field text field
        assert props["name"]["type"] == "text"
        assert "edge_ngram" in props["name"]["fields"]
        assert "keyword" in props["name"]["fields"]

        # postal is a plain keyword — no sub-fields
        assert props["postal"]["type"] == "keyword"

    def test_ingest_with_id_field(
        self,
        ae_client,
        index_name,
        cleanup_index,
        fast_ingest_config,
    ):
        """ingest_dicts() assigns custom _id when id_field is specified."""
        idx = index_name
        cleanup_index(idx)

        docs = [
            {
                "name": [f"Biz {i}"],
                "address": f"Addr {i}",
                "city": "TestCity",
                "postal": f"0000{i}",
                "region": "CA",
                "country": "US",
                "my_id": f"biz-{i}",
            }
            for i in range(3)
        ]

        ae_client.ingest_dicts(
            idx,
            docs,
            id_field="my_id",
            mapping=build_index_body(shards=1, replicas=0),
            ingest_config=fast_ingest_config,
        )

        ae_client.client.indices.refresh(index=idx)

        for i in range(3):
            found = ae_client.client.get(index=idx, id=f"biz-{i}")["found"]
            assert found is True

    def test_ingest_optimization_restores_settings(
        self,
        ae_client,
        index_name,
        cleanup_index,
        fast_ingest_config,
    ):
        """After ingest with optimize_for_bulk=True, refresh_interval is restored (not -1)."""
        idx = index_name
        cleanup_index(idx)

        docs = SAMPLE_BUSINESSES[:2]
        ae_client.ingest_dicts(
            idx,
            docs,
            mapping=build_index_body(shards=1, replicas=0),
            ingest_config=fast_ingest_config,
        )

        settings = ae_client.client.indices.get_settings(index=idx)[idx]["settings"]["index"]
        # refresh_interval should be restored to the original value ("1s"), not left at "-1"
        assert settings.get("refresh_interval") != "-1"

    def test_ingest_empty_list(
        self,
        ae_client,
        index_name,
        cleanup_index,
        fast_ingest_config,
    ):
        """ingest_dicts() with an empty list returns zero counts."""
        idx = index_name
        cleanup_index(idx)

        result = ae_client.ingest_dicts(
            idx,
            [],
            mapping=build_index_body(shards=1, replicas=0),
            ingest_config=fast_ingest_config,
        )

        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0


@pytest.mark.integration
class TestIngestParquet:
    """Integration tests for ingest_parquet()."""

    def test_ingest_parquet_loads_all_rows(
        self,
        ae_client,
        sample_parquet,
        index_name,
        cleanup_index,
        fast_ingest_config,
    ):
        """ingest_parquet() loads all rows from a Parquet file."""
        idx = index_name
        cleanup_index(idx)

        result = ae_client.ingest_parquet(
            idx,
            sample_parquet,
            mapping=build_index_body(shards=1, replicas=0),
            ingest_config=fast_ingest_config,
        )

        assert result.succeeded == 10
        assert result.failed == 0

    def test_ingest_parquet_with_column_filter(
        self,
        ae_client,
        sample_parquet,
        index_name,
        cleanup_index,
        fast_ingest_config,
    ):
        """ingest_parquet() with columns= only indexes the specified columns."""
        idx = index_name
        cleanup_index(idx)

        ae_client.ingest_parquet(
            idx,
            sample_parquet,
            columns=["name", "city"],
            mapping=build_index_body(shards=1, replicas=0),
            ingest_config=fast_ingest_config,
        )

        ae_client.client.indices.refresh(index=idx)

        hits = ae_client.client.search(
            index=idx,
            body={"query": {"match_all": {}}, "size": 1},
        )["hits"]["hits"]

        assert len(hits) > 0
        source = hits[0]["_source"]
        assert "name" in source
        assert "city" in source
        assert "address" not in source
        assert "postal" not in source

    def test_ingest_parquet_schema_and_count(
        self,
        ae_client,
        sample_parquet,
    ):
        """parquet_schema() and parquet_row_count() return correct metadata."""
        schema = ae_client.parquet_schema(sample_parquet)
        assert set(schema.keys()) == {"name", "address", "city", "postal", "region", "country"}

        assert ae_client.parquet_row_count(sample_parquet) == 10
