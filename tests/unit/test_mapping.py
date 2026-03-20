from __future__ import annotations

from autoelastic.schema.mapping import (
    build_index_body,
)


class TestBuildIndexBody:
    def test_default_body_has_settings_and_mappings(self):
        body = build_index_body()
        assert "settings" in body
        assert "mappings" in body

    def test_default_shards_and_replicas(self):
        body = build_index_body()
        assert body["settings"]["number_of_shards"] == 3
        assert body["settings"]["number_of_replicas"] == 1

    def test_custom_shards(self):
        body = build_index_body(shards=5, replicas=2)
        assert body["settings"]["number_of_shards"] == 5
        assert body["settings"]["number_of_replicas"] == 2

    def test_name_field_has_edge_ngram(self):
        body = build_index_body()
        name = body["mappings"]["properties"]["name"]
        assert name["type"] == "text"
        assert "edge_ngram" in name["fields"]
        assert name["fields"]["edge_ngram"]["analyzer"] == "edge_ngram_analyzer"

    def test_name_field_has_keyword(self):
        body = build_index_body()
        name = body["mappings"]["properties"]["name"]
        assert name["fields"]["keyword"]["type"] == "keyword"

    def test_analyzers_present(self):
        body = build_index_body()
        analyzers = body["settings"]["analysis"]["analyzer"]
        assert "edge_ngram_analyzer" in analyzers
        assert "name_search_analyzer" in analyzers

    def test_edge_ngram_tokenizer_config(self):
        body = build_index_body()
        tokenizer = body["settings"]["analysis"]["tokenizer"]["edge_ngram_tokenizer"]
        assert tokenizer["type"] == "edge_ngram"
        assert tokenizer["min_gram"] == 2
        assert tokenizer["max_gram"] == 15

    def test_settings_overrides(self):
        body = build_index_body(settings_overrides={"refresh_interval": "5s"})
        assert body["settings"]["refresh_interval"] == "5s"

    def test_mapping_overrides_add_field(self):
        body = build_index_body(mapping_overrides={"properties": {"phone": {"type": "keyword"}}})
        assert "phone" in body["mappings"]["properties"]
        assert body["mappings"]["properties"]["phone"]["type"] == "keyword"
        assert "name" in body["mappings"]["properties"]

    def test_all_expected_fields_present(self):
        body = build_index_body()
        props = body["mappings"]["properties"]
        for field in ["name", "address", "city", "postal", "region", "country"]:
            assert field in props, f"Missing field: {field}"

    def test_postal_is_keyword_only(self):
        body = build_index_body()
        assert body["mappings"]["properties"]["postal"]["type"] == "keyword"

    def test_address_has_keyword_subfield(self):
        body = build_index_body()
        address = body["mappings"]["properties"]["address"]
        assert address["type"] == "text"
        assert address["fields"]["keyword"]["type"] == "keyword"
