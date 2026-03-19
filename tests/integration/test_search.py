"""Integration tests for name search and bulk search functionality."""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestNameSearch:
    """Tests for AutoElastic.search_name()."""

    def test_exact_match(self, ae_client, seeded_index):
        results = ae_client.search_name(seeded_index, "Apple")
        assert len(results) > 0
        assert any("Apple" in n for n in results[0]["_source"]["name"])

    def test_exact_match_full_name(self, ae_client, seeded_index):
        results = ae_client.search_name(seeded_index, "Apple Inc")
        assert len(results) > 0
        assert any("Apple" in n for n in results[0]["_source"]["name"])

    def test_fuzzy_match_typo(self, ae_client, seeded_index):
        # "Appel" is a 1-char typo of "Apple" — fuzziness AUTO allows 1 edit for 5-char terms
        results = ae_client.search_name(seeded_index, "Appel")
        assert len(results) > 0
        assert any(any("Apple" in n for n in r["_source"]["name"]) for r in results)

    def test_partial_match_prefix(self, ae_client, seeded_index):
        # "App" (3 chars) should match via edge_ngram
        results = ae_client.search_name(seeded_index, "App")
        assert len(results) > 0
        assert any(
            any("Apple" in n or "Applebee" in n for n in r["_source"]["name"])
            for r in results
        )

    def test_case_insensitive(self, ae_client, seeded_index):
        results_lower = ae_client.search_name(seeded_index, "apple")
        results_upper = ae_client.search_name(seeded_index, "APPLE")
        assert len(results_lower) > 0
        assert len(results_upper) > 0
        assert results_lower[0]["_id"] == results_upper[0]["_id"]

    def test_no_results_for_garbage(self, ae_client, seeded_index):
        results = ae_client.search_name(seeded_index, "zzxxyy999nonexistent")
        assert len(results) == 0

    def test_search_returns_highlight(self, ae_client, seeded_index):
        results = ae_client.search_name(seeded_index, "Google")
        assert len(results) > 0
        assert results[0]["highlight"] is not None
        assert "name" in results[0]["highlight"]

    def test_search_with_size_limit(self, ae_client, seeded_index):
        results = ae_client.search_name(seeded_index, "Apple", size=1)
        assert len(results) == 1

    def test_search_multiple_hits_for_apple(self, ae_client, seeded_index):
        # Apple Inc, Apple Leisure Group, and Applebee's are all in the data
        results = ae_client.search_name(seeded_index, "Apple")
        assert len(results) >= 2

    def test_search_result_structure(self, ae_client, seeded_index):
        results = ae_client.search_name(seeded_index, "Microsoft")
        assert len(results) > 0
        r = results[0]
        assert "_id" in r
        assert "_score" in r
        assert isinstance(r["_score"], (int, float)) and r["_score"] > 0
        assert "_source" in r
        assert "name" in r["_source"]
        assert "highlight" in r


@pytest.mark.integration
class TestNameSearchBulk:
    """Tests for AutoElastic.search_names_bulk()."""

    def test_bulk_search_returns_all_names(self, ae_client, seeded_index):
        results = ae_client.search_names_bulk(seeded_index, ["Apple", "Google", "Tesla"])
        assert set(results.keys()) == {"Apple", "Google", "Tesla"}
        assert len(results["Apple"]) > 0
        assert len(results["Google"]) > 0
        assert len(results["Tesla"]) > 0

    def test_bulk_search_mixed_hits_and_misses(self, ae_client, seeded_index):
        results = ae_client.search_names_bulk(
            seeded_index, ["Microsoft", "zzxxyy_nonexistent"]
        )
        assert len(results["Microsoft"]) > 0
        assert len(results["zzxxyy_nonexistent"]) == 0

    def test_bulk_search_single_name(self, ae_client, seeded_index):
        results = ae_client.search_names_bulk(seeded_index, ["Netflix"])
        assert "Netflix" in results
        assert len(results["Netflix"]) > 0

    def test_bulk_search_result_quality(self, ae_client, seeded_index):
        results = ae_client.search_names_bulk(seeded_index, ["Amazon"])
        assert len(results["Amazon"]) > 0
        top = results["Amazon"][0]
        assert any("Amazon" in n for n in top["_source"]["name"])
