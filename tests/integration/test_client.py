"""Integration tests for AutoElastic client lifecycle and Parquet utilities."""

from __future__ import annotations

from autoelastic.client import AutoElastic
from tests.integration.conftest import ES_BASIC_AUTH, ES_URL


class TestClientLifecycle:
    """Test AutoElastic client connection and lifecycle methods."""

    def test_ping(self, ae_client):
        """Test that ping() returns True when connected."""
        result = ae_client.ping()
        assert result is True

    def test_context_manager(self, es_client):  # noqa: ARG002  # ensures skip if ES unreachable
        """Test that AutoElastic works as a context manager."""
        with AutoElastic(hosts=ES_URL, basic_auth=ES_BASIC_AUTH) as ae:
            assert ae.ping() is True

    def test_client_property(self, ae_client):
        """Test that client property returns Elasticsearch instance with info()."""
        info = ae_client.client.info()
        assert "version" in info


class TestParquetUtilities:
    """Test AutoElastic Parquet schema and row count methods."""

    def test_parquet_schema(self, ae_client, sample_parquet):
        """Test that parquet_schema returns expected columns."""
        schema = ae_client.parquet_schema(sample_parquet)
        assert isinstance(schema, dict)
        expected_columns = {"name", "address", "city", "postal", "region", "country"}
        assert set(schema.keys()) == expected_columns

    def test_parquet_row_count(self, ae_client, sample_parquet):
        """Test that parquet_row_count returns correct count."""
        count = ae_client.parquet_row_count(sample_parquet)
        assert count == 12
