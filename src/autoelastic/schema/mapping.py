from __future__ import annotations

BUSINESS_ENTITY_SETTINGS = {
    "analysis": {
        "analyzer": {
            "edge_ngram_analyzer": {
                "type": "custom",
                "tokenizer": "edge_ngram_tokenizer",
                "filter": ["lowercase", "asciifolding"],
            },
            "name_search_analyzer": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "asciifolding"],
            },
        },
        "tokenizer": {
            "edge_ngram_tokenizer": {
                "type": "edge_ngram",
                "min_gram": 2,
                "max_gram": 15,
                "token_chars": ["letter", "digit"],
            },
        },
    },
}

BUSINESS_ENTITY_MAPPINGS = {
    "properties": {
        "name": {
            "type": "text",
            "analyzer": "name_search_analyzer",
            "fields": {
                "keyword": {"type": "keyword", "ignore_above": 512},
                "edge_ngram": {
                    "type": "text",
                    "analyzer": "edge_ngram_analyzer",
                    "search_analyzer": "name_search_analyzer",
                },
            },
        },
        "address": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
        },
        "city": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
        },
        "postal": {"type": "keyword"},
        "region": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
        },
        "country": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
        },
    },
}


def build_index_body(
    *,
    settings_overrides: dict | None = None,
    mapping_overrides: dict | None = None,
    shards: int = 3,
    replicas: int = 1,
) -> dict:
    settings = {
        **BUSINESS_ENTITY_SETTINGS,
        "number_of_shards": shards,
        "number_of_replicas": replicas,
    }
    if settings_overrides:
        settings.update(settings_overrides)

    mappings = dict(BUSINESS_ENTITY_MAPPINGS)
    if mapping_overrides:
        mappings["properties"] = {
            **mappings["properties"],
            **mapping_overrides.get("properties", {}),
        }

    return {"settings": settings, "mappings": mappings}
