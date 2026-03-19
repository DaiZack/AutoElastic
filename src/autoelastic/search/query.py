from elasticsearch import Elasticsearch

from autoelastic.config import NameSearchConfig

VALID_FILTER_FIELDS = {"address", "city", "postal", "region", "country"}
KEYWORD_ONLY_FIELDS = {"postal"}
PHRASE_MATCH_FIELDS = {"address"}


class NameSearch:
    """Business name search with fuzzy, prefix, and exact-match boosting."""

    def __init__(self, client: Elasticsearch, config: NameSearchConfig) -> None:
        self.client = client
        self.config = config

    def _build_query_body(self, name: str, fuzziness: str) -> dict:
        """Build the query dict with fuzzy, prefix, and boosted exact matching."""
        return {
            "bool": {
                "should": [
                    {
                        "match": {
                            "name": {
                                "query": name,
                                "fuzziness": fuzziness,
                                "prefix_length": self.config.prefix_length,
                            }
                        }
                    },
                    {"match": {"name.edge_ngram": {"query": name, "boost": 0.5}}},
                    {"match_phrase_prefix": {"name": {"query": name}}},
                    {"match": {"name.keyword": {"query": name, "boost": 2.0}}},
                ],
                "minimum_should_match": 1,
            }
        }

    def _build_filter_clauses(self, filters: dict[str, str]) -> list[dict]:
        """Build ES bool.filter clauses from a filters dict."""
        if not filters:
            return []
        clauses = []
        for key, val in filters.items():
            if key not in VALID_FILTER_FIELDS:
                raise ValueError(f"Invalid filter field: {key!r}. Valid fields: {sorted(VALID_FILTER_FIELDS)}")
            if val == "":
                raise ValueError(f"Empty value for filter field: {key!r}")
            if key in PHRASE_MATCH_FIELDS:
                clauses.append({"match_phrase": {key: val}})
            elif key in KEYWORD_ONLY_FIELDS:
                clauses.append({"term": {key: {"value": val, "case_insensitive": True}}})
            else:
                clauses.append({"term": {f"{key}.keyword": {"value": val, "case_insensitive": True}}})
        return clauses

    def _compute_matched_fields(self, hit: dict, name: str, filters: dict[str, str] | None) -> list[str]:
        """Compute which fields had exact matches for a given hit."""
        if not filters:
            return []
        matched = []
        source = hit["_source"]
        if any(n.lower() == name.lower() for n in source.get("name", [])):
            matched.append("name")
        for field in filters:
            matched.append(field)
        return sorted(matched)

    def search(self, index: str, name: str, *, filters: dict[str, str] | None = None, **overrides) -> list[dict]:
        """Search for businesses by name using fuzzy, prefix, and boosted exact matching."""
        fuzziness = overrides.pop("fuzziness", self.config.fuzziness)
        size = overrides.pop("size", self.config.size)

        query = self._build_query_body(name, fuzziness)

        if filters:
            query["bool"]["filter"] = self._build_filter_clauses(filters)

        body: dict = {"query": query, "size": size}
        body.update(overrides)

        if self.config.min_score is not None:
            body["min_score"] = self.config.min_score

        if self.config.highlight:
            body["highlight"] = {"fields": {"name": {}}}

        resp = self.client.search(index=index, body=body)

        return [
            {
                "_id": hit["_id"],
                "_score": hit["_score"],
                "_source": hit["_source"],
                "highlight": hit.get("highlight"),
                "matched_fields": self._compute_matched_fields(hit, name, filters),
            }
            for hit in resp["hits"]["hits"]
        ]

    def search_bulk(self, index: str, names: list[str], *, filters: dict[str, str] | None = None) -> dict[str, list[dict]]:
        """Search multiple names at once via _msearch, returning a mapping of name → results."""
        filter_clauses = self._build_filter_clauses(filters) if filters else []

        request_body: list = []
        for name in names:
            fuzziness = self.config.fuzziness
            size = self.config.size

            query = self._build_query_body(name, fuzziness)

            if filter_clauses:
                query["bool"]["filter"] = filter_clauses

            body: dict = {"query": query, "size": size}

            if self.config.min_score is not None:
                body["min_score"] = self.config.min_score

            if self.config.highlight:
                body["highlight"] = {"fields": {"name": {}}}

            request_body.append({"index": index})
            request_body.append(body)

        resp = self.client.msearch(body=request_body)

        return {
            name: [
                {
                    "_id": hit["_id"],
                    "_score": hit["_score"],
                    "_source": hit["_source"],
                    "highlight": hit.get("highlight"),
                    "matched_fields": self._compute_matched_fields(hit, name, filters),
                }
                for hit in r["hits"]["hits"]
            ]
            for name, r in zip(names, resp["responses"])
        }
