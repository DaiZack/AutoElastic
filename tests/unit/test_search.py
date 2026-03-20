from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from autoelastic.config import NameSearchConfig
from autoelastic.search.query import NameSearch


def _make_search_response(hits: list[dict] | None = None) -> dict:
    if hits is None:
        hits = [
            {
                "_id": "1",
                "_score": 5.5,
                "_source": {"name": ["Apple", "Apple Inc"], "city": "Cupertino"},
                "highlight": {"name": ["<em>Apple</em>"]},
            }
        ]
    return {"hits": {"total": {"value": len(hits)}, "hits": hits}}


class TestNameSearch:
    def test_search_builds_correct_query_structure(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search("test-index", "apple")

        call_kwargs = client.search.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        query = body["query"]["bool"]
        assert "should" in query
        assert query["minimum_should_match"] == 1
        assert len(query["should"]) == 4

    def test_search_returns_formatted_results(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search("test-index", "apple")

        assert len(results) == 1
        assert results[0]["_id"] == "1"
        assert results[0]["_score"] == 5.5
        assert results[0]["_source"]["name"] == ["Apple", "Apple Inc"]
        assert results[0]["highlight"] == {"name": ["<em>Apple</em>"]}

    def test_search_with_size_override(self):
        client = MagicMock()
        client.search.return_value = _make_search_response([])
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search("test-index", "apple", size=5)

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        assert body["size"] == 5

    def test_search_with_fuzziness_override(self):
        client = MagicMock()
        client.search.return_value = _make_search_response([])
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search("test-index", "apple", fuzziness="2")

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        match_clause = body["query"]["bool"]["should"][0]["match"]["name"]
        assert match_clause["fuzziness"] == "2"

    def test_search_includes_highlight(self):
        client = MagicMock()
        client.search.return_value = _make_search_response([])
        searcher = NameSearch(client, NameSearchConfig(highlight=True))

        searcher.search("test-index", "apple")

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        assert "highlight" in body
        assert "name" in body["highlight"]["fields"]

    def test_search_no_highlight(self):
        client = MagicMock()
        client.search.return_value = _make_search_response([])
        searcher = NameSearch(client, NameSearchConfig(highlight=False))

        searcher.search("test-index", "apple")

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        assert "highlight" not in body

    def test_search_with_min_score(self):
        client = MagicMock()
        client.search.return_value = _make_search_response([])
        searcher = NameSearch(client, NameSearchConfig(min_score=2.0))

        searcher.search("test-index", "apple")

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        assert body["min_score"] == 2.0

    def test_search_bulk_returns_per_name_results(self):
        client = MagicMock()
        client.msearch.return_value = {
            "responses": [
                _make_search_response(),
                _make_search_response([]),
            ]
        }
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search_bulk("test-index", ["apple", "banana"])

        assert "apple" in results
        assert "banana" in results
        assert len(results["apple"]) == 1
        assert len(results["banana"]) == 0

    def test_search_bulk_msearch_body_structure(self):
        client = MagicMock()
        client.msearch.return_value = {"responses": [_make_search_response()]}
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search_bulk("test-index", ["apple"])

        call_kwargs = client.msearch.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        assert body[0] == {"index": "test-index"}
        assert "query" in body[1]


def _make_hit(id="1", score=5.0, source=None):
    return {
        "_id": id,
        "_score": score,
        "_source": source or {"name": ["Apple"], "city": "Cupertino"},
        "highlight": None,
    }


class TestNameSearchFilters:
    def test_filter_adds_bool_filter_clause(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search("idx", "Apple", filters={"city": "Cupertino"})

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        assert "filter" in body["query"]["bool"]
        filter_clauses = body["query"]["bool"]["filter"]
        assert any("term" in clause for clause in filter_clauses)
        term_clauses = [c["term"] for c in filter_clauses if "term" in c]
        assert any("city.keyword" in t for t in term_clauses)

    def test_filter_postal_uses_term_query(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search("idx", "Apple", filters={"postal": "95014"})

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        filter_clauses = body["query"]["bool"]["filter"]
        term_clauses = [c["term"] for c in filter_clauses if "term" in c]
        assert any("postal" in t for t in term_clauses)
        postal_term = next(t for t in term_clauses if "postal" in t)
        assert postal_term["postal"].get("case_insensitive") is True

    def test_filter_address_uses_match_phrase(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search("idx", "Apple", filters={"address": "Apple Park"})

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        filter_clauses = body["query"]["bool"]["filter"]
        assert any("match_phrase" in clause for clause in filter_clauses)
        mp_clauses = [c["match_phrase"] for c in filter_clauses if "match_phrase" in c]
        assert any("address" in mp for mp in mp_clauses)

    def test_multiple_filters_produce_multiple_clauses(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search("idx", "Apple", filters={"city": "Cupertino", "country": "US"})

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        assert len(body["query"]["bool"]["filter"]) == 2

    def test_invalid_filter_key_raises_valueerror(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        with pytest.raises(ValueError):
            searcher.search("idx", "Apple", filters={"invalid": "x"})

    def test_empty_string_filter_raises_valueerror(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        with pytest.raises(ValueError):
            searcher.search("idx", "Apple", filters={"city": ""})

    def test_empty_dict_filters_treated_as_none(self):
        client = MagicMock()
        client.search.return_value = _make_search_response()
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search("idx", "Apple", filters={})

        body = client.search.call_args.kwargs.get("body") or client.search.call_args[1]["body"]
        assert "filter" not in body["query"]["bool"]
        assert results[0]["matched_fields"] == []

    def test_matched_fields_present_in_results(self):
        client = MagicMock()
        client.search.return_value = _make_search_response(
            hits=[_make_hit(source={"name": ["Apple"]})]
        )
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search("idx", "Apple", filters={"city": "Cupertino"})

        assert "matched_fields" in results[0]
        assert isinstance(results[0]["matched_fields"], list)

    def test_matched_fields_includes_name_on_exact_match(self):
        client = MagicMock()
        client.search.return_value = _make_search_response(
            hits=[_make_hit(source={"name": ["Apple", "Apple Inc"]})]
        )
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search("idx", "Apple", filters={"city": "Cupertino"})

        assert "name" in results[0]["matched_fields"]

    def test_matched_fields_excludes_name_on_fuzzy_match(self):
        client = MagicMock()
        client.search.return_value = _make_search_response(
            hits=[_make_hit(source={"name": ["Apple"]})]
        )
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search("idx", "Appel", filters={"city": "Cupertino"})

        assert "name" not in results[0]["matched_fields"]

    def test_matched_fields_includes_filter_fields(self):
        client = MagicMock()
        client.search.return_value = _make_search_response(
            hits=[_make_hit(source={"name": ["Apple"], "city": "Cupertino"})]
        )
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search("idx", "Apple", filters={"city": "Cupertino"})

        assert "city" in results[0]["matched_fields"]

    def test_matched_fields_empty_when_no_filters(self):
        client = MagicMock()
        client.search.return_value = _make_search_response(
            hits=[_make_hit(source={"name": ["Apple"]})]
        )
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search("idx", "Apple")

        assert results[0]["matched_fields"] == []


class TestNameSearchBulkFilters:
    def test_bulk_filter_includes_filter_clauses_per_name(self):
        client = MagicMock()
        hit = _make_hit(source={"name": ["Apple"], "city": "Cupertino"})
        client.msearch.return_value = {
            "responses": [
                {"hits": {"hits": [hit]}},
                {"hits": {"hits": [hit]}},
            ]
        }
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search_bulk("idx", ["apple", "google"], filters={"city": "Cupertino"})

        body = client.msearch.call_args.kwargs.get("body") or client.msearch.call_args[1]["body"]
        assert "filter" in body[1]["query"]["bool"]
        assert "filter" in body[3]["query"]["bool"]

    def test_bulk_filter_applies_same_filters_to_all_names(self):
        client = MagicMock()
        hit = _make_hit(source={"name": ["Apple"], "city": "Cupertino"})
        client.msearch.return_value = {
            "responses": [
                {"hits": {"hits": [hit]}},
                {"hits": {"hits": [hit]}},
            ]
        }
        searcher = NameSearch(client, NameSearchConfig())

        searcher.search_bulk("idx", ["apple", "google"], filters={"city": "Cupertino"})

        body = client.msearch.call_args.kwargs.get("body") or client.msearch.call_args[1]["body"]
        assert body[1]["query"]["bool"]["filter"] == body[3]["query"]["bool"]["filter"]

    def test_bulk_matched_fields_present_in_results(self):
        client = MagicMock()
        hit_apple = _make_hit(id="1", source={"name": ["Apple"], "city": "Cupertino"})
        hit_banana = _make_hit(id="2", source={"name": ["Banana"], "city": "Cupertino"})
        client.msearch.return_value = {
            "responses": [
                {"hits": {"hits": [hit_apple]}},
                {"hits": {"hits": [hit_banana]}},
            ]
        }
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search_bulk("idx", ["apple", "banana"], filters={"city": "Cupertino"})

        assert "matched_fields" in results["apple"][0]
        assert "matched_fields" in results["banana"][0]

    def test_bulk_matched_fields_values_correct(self):
        client = MagicMock()
        hit = _make_hit(source={"name": ["Apple"], "city": "Cupertino"})
        client.msearch.return_value = {
            "responses": [
                {"hits": {"hits": [hit]}},
            ]
        }
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search_bulk("idx", ["apple"], filters={"city": "Cupertino"})

        assert "city" in results["apple"][0]["matched_fields"]
        assert "name" in results["apple"][0]["matched_fields"]

    def test_bulk_invalid_filter_raises_valueerror(self):
        client = MagicMock()
        client.msearch.return_value = {"responses": [{"hits": {"hits": []}}]}
        searcher = NameSearch(client, NameSearchConfig())

        with pytest.raises(ValueError):
            searcher.search_bulk("idx", ["apple"], filters={"invalid": "x"})

    def test_bulk_no_filters_no_filter_clause(self):
        client = MagicMock()
        hit = _make_hit(source={"name": ["Apple"], "city": "Cupertino"})
        client.msearch.return_value = {
            "responses": [
                {"hits": {"hits": [hit]}},
            ]
        }
        searcher = NameSearch(client, NameSearchConfig())

        results = searcher.search_bulk("idx", ["apple"])

        body = client.msearch.call_args.kwargs.get("body") or client.msearch.call_args[1]["body"]
        assert "filter" not in body[1]["query"]["bool"]
        assert "matched_fields" in results["apple"][0]
        assert results["apple"][0]["matched_fields"] == []
