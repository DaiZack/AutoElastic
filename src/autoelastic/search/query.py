from elasticsearch import Elasticsearch

from autoelastic.config import NameSearchConfig


class NameSearch:
    """Business name search with fuzzy, prefix, and exact-match boosting."""

    def __init__(self, client: Elasticsearch, config: NameSearchConfig) -> None:
        self.client = client
        self.config = config

    def search(self, index: str, name: str, **overrides) -> list[dict]:
        """Search for businesses by name using fuzzy, prefix, and boosted exact matching."""
        fuzziness = overrides.pop("fuzziness", self.config.fuzziness)
        size = overrides.pop("size", self.config.size)

        query = {
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
            }
            for hit in resp["hits"]["hits"]
        ]

    def search_bulk(self, index: str, names: list[str]) -> dict[str, list[dict]]:
        """Search multiple names at once via _msearch, returning a mapping of name → results."""
        request_body: list = []
        for name in names:
            fuzziness = self.config.fuzziness
            size = self.config.size

            query = {
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
                }
                for hit in r["hits"]["hits"]
            ]
            for name, r in zip(names, resp["responses"])
        }
