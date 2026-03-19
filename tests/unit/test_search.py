from __future__ import annotations

from unittest.mock import MagicMock

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
