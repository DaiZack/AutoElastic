import logging
from collections.abc import Iterator

from elasticsearch import Elasticsearch

from autoelastic.config import SearchConfig

logger = logging.getLogger(__name__)

_DEFAULT_SORT = [{"_shard_doc": "asc"}]


class BulkSearch:
    """Bulk search utilities: full-index scan via PIT+search_after and batched _msearch."""

    def __init__(self, client: Elasticsearch, config: SearchConfig) -> None:
        self.client = client
        self.config = config

    def scan(
        self,
        index: str,
        query: dict | None = None,
        sort: list | None = None,
    ) -> Iterator[dict]:
        """Paginate through all hits using a PIT and search_after, yielding each hit's _source."""
        if query is None:
            query = {"match_all": {}}
        if sort is None:
            sort = _DEFAULT_SORT

        pit_resp = self.client.open_point_in_time(
            index=index, keep_alive=self.config.pit_keep_alive
        )
        pit_id: str = pit_resp["id"]

        try:
            search_after = None
            page = 0

            while True:
                body: dict = {
                    "query": query,
                    "sort": sort,
                    "size": self.config.page_size,
                    "pit": {"id": pit_id, "keep_alive": self.config.pit_keep_alive},
                    "track_total_hits": self.config.track_total_hits,
                }
                if search_after is not None:
                    body["search_after"] = search_after

                resp = self.client.search(body=body)

                hits = resp["hits"]["hits"]
                if not hits:
                    break

                pit_id = resp["pit_id"]
                body["pit"]["id"] = pit_id

                page += 1
                if page % 10 == 0:
                    logger.info("scan page %d, hits so far: %d", page, page * self.config.page_size)

                for hit in hits:
                    yield hit["_source"]

                search_after = hits[-1]["sort"]

                if len(hits) < self.config.page_size:
                    break

        finally:
            try:
                self.client.close_point_in_time(id=pit_id)
            except Exception:
                logger.warning("Failed to close PIT %s", pit_id, exc_info=True)

    def msearch(self, index: str, queries: list[dict]) -> list[dict]:
        """Batch multiple query bodies into _msearch calls, returning all responses in order."""
        results: list[dict] = []
        batch_size = self.config.max_concurrent

        for i in range(0, len(queries), batch_size):
            batch = queries[i : i + batch_size]
            request_body: list = []
            for q in batch:
                request_body.append({"index": index})
                request_body.append(q)

            resp = self.client.msearch(body=request_body)
            for r in resp["responses"]:
                results.append(r)

        return results
