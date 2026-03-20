"""Integration tests for BulkSearch.scan() — PIT and search_after pagination."""

from __future__ import annotations

from autoelastic.config import SearchConfig
from autoelastic.search.bulk import BulkSearch


class TestScan:
    """Test BulkSearch.scan() — paginated retrieval via PIT and search_after."""

    def test_scan_returns_all_docs(self, ae_client, seeded_index):
        """Test that scan() returns all documents from the index."""
        docs = list(ae_client.scan(seeded_index))
        assert len(docs) == 12

    def test_scan_returns_source_dicts(self, ae_client, seeded_index):
        """Test that scan() yields _source dicts with no metadata (_id, _score)."""
        docs = list(ae_client.scan(seeded_index))
        assert len(docs) > 0
        doc = docs[0]
        assert isinstance(doc, dict)
        assert "name" in doc
        assert "city" in doc
        assert "address" in doc
        assert "_id" not in doc
        assert "_score" not in doc

    def test_scan_with_query_filter(self, ae_client, seeded_index):
        """Test that scan() respects query filters (e.g., term query on city.keyword)."""
        docs = list(
            ae_client.scan(seeded_index, query={"term": {"city.keyword": "Cupertino"}})
        )
        assert len(docs) == 1
        assert any("Apple" in n for n in docs[0]["name"])

    def test_scan_empty_result(self, ae_client, seeded_index):
        """Test that scan() returns empty iterator when query matches no docs."""
        docs = list(
            ae_client.scan(
                seeded_index, query={"term": {"city.keyword": "Nonexistent City"}}
            )
        )
        assert len(docs) == 0

    def test_scan_with_small_page_size(self, ae_client, seeded_index):
        """Test that scan() works across multiple pages with small page_size."""
        config = SearchConfig(page_size=3)
        searcher = BulkSearch(ae_client.client, config)
        docs = list(searcher.scan(seeded_index))
        assert len(docs) == 12
