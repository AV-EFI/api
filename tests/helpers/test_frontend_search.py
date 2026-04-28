from app.core.config import settings
from app.helpers.frontend_search import SearchAdapter, process_search_request
from app.schemas.frontend_search import SearchParams, SearchRequest


def test_build_es_query_basic_search():
    request = SearchRequest(
        indexName=settings.ES_INDEX,
        params={
            "query": "test query",
            "hitsPerPage": 20,
            "page": 0,
            "maxValuesPerFacet": 10,
        },
    )

    query = process_search_request.build_es_query(request)

    assert query["query"]["bool"]["should"] == [
        {
            "multi_match": {
                "query": "test query",
                "fields": process_search_request.query_fields,
                "zero_terms_query": "all",
                "boost": 2,
            }
        },
        {
            "multi_match": {
                "query": "test query",
                "fields": process_search_request.query_fields,
                "zero_terms_query": "all",
                "fuzziness": "AUTO",
                "tie_breaker": 0.667,
            }
        },
    ]
    assert query["size"] == 20
    assert query["from"] == 0


def test_build_es_query_with_facet_filters():
    request = SearchRequest(
        indexName=settings.ES_INDEX,
        params=SearchParams(
            query="test",
            facetFilters=[
                ["directors_or_editors:Director 1"],
                [
                    "has_format_type:16mmFilm",
                    "has_format_type:35mmFilm",
                ],
            ],
        ),
    )

    query = process_search_request.build_es_query(request)

    assert len(query["query"]["bool"]["should"]) == 2
    assert list(query["query"]["bool"]["should"][0].keys()) == ["multi_match"]
    assert len(query["query"]["bool"]["filter"]) == 2
    assert query["query"]["bool"]["filter"][0] == {
        "terms": {"directors_or_editors.keyword": ["Director 1"]},
    }
    assert len(query["query"]["bool"]["filter"]) == 2
    assert query["query"]["bool"]["filter"][1]["nested"]["query"]["bool"][
        "filter"
    ][0]["terms"][
        "manifestations.items.has_record.has_format.type.keyword"
    ] == ["16mmFilm", "35mmFilm"]


def test_transform_hits():
    mock_hits = [
        {
            "_id": "123",
            "_index": "test-index",
            "_score": 1.0,
            "_source": {
                "handle": "test-handle",
                "has_record": {
                    "has_primary_title": {
                        "has_name": "Test Title",
                        "type": "PreferredTitle",
                    }
                },
                "castmembers": ["Actor 1"],
                "directors_or_editors": ["Director 1"],
                "subjects": ["Subject 1"],
                "production": ["Country 1"],
                "years": ["2023"],
            },
            "highlight": {
                "has_record.has_primary_title.has_name": [
                    "<em>Test</em> Title"
                ]
            },
        }
    ]
    params = SearchParams(
        query="test query",
        hitsPerPage=20,
        page=0,
        maxValuesPerFacet=10,
    )

    transformed = process_search_request.transform_hits(mock_hits, params)

    assert transformed[0]["objectID"] == "123"
    assert transformed[0]["handle"] == "test-handle"
    assert (
        transformed[0]["_highlightResult"]["has_record"]["has_primary_title"][
            "has_name"
        ][0]["value"]
        == "<em>Test</em> Title"
    )


def test_transform_facets():
    mock_aggregations = {
        "production.keyword": {
            "buckets": [
                {"key": "Germany", "doc_count": 10},
                {"key": "France", "doc_count": 5},
            ]
        }
    }

    transformed = process_search_request.transform_facets(mock_aggregations)

    assert transformed["production"] == {"Germany": 10, "France": 5}


class TestNestedFilterGrouping:
    """Test suite for nested filter grouping functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = SearchAdapter()
        self.params = SearchParams(
            query="test query",
            hitsPerPage=20,
            page=0,
            maxValuesPerFacet=10,
        )

    def test_basic_grouping_and_wrapping(self):
        """Test basic grouping of filters with common prefix."""
        # Test case from user's example
        input_filters = [
            {
                "nested": {
                    "path": "manifestations.items",
                    "query": {"terms": {"field1": ["value1"]}},
                }
            },
            {
                "nested": {
                    "path": "manifestations.other",
                    "query": {"terms": {"field2": ["value2"]}},
                }
            },
            {
                "nested": {
                    "path": "manifestations",
                    "query": {"terms": {"field3": ["value3"]}},
                }
            },
            {
                "nested": {
                    "path": "different.path",
                    "query": {"terms": {"field4": ["value4"]}},
                }
            },
        ]

        result = self.adapter._group_nested_filters(input_filters, self.params)

        # Verify structure
        assert len(result) == 2
        # Order is not preserved as side effect of _group_nested_filters
        assert result[1]["nested"]["path"] == "manifestations"
        assert result[0]["nested"]["path"] == "different.path"

        # Verify wrapped structure
        manifestations_filter = result[1]
        assert "bool" in manifestations_filter["nested"]["query"]
        assert "filter" in manifestations_filter["nested"]["query"]["bool"]

        wrapped_filters = manifestations_filter["nested"]["query"]["bool"][
            "filter"
        ]
        assert len(wrapped_filters) == 3

        # Verify path stripping for exact match
        stripped_filter = wrapped_filters[0]
        assert stripped_filter == {"terms": {"field3": ["value3"]}}
        assert "nested" not in stripped_filter

    def test_no_common_prefix(self):
        """Test that filters with different prefixes remain separate."""
        input_filters = [
            {
                "nested": {
                    "path": "field1.sub",
                    "query": {"terms": {"a": ["1"]}},
                }
            },
            {
                "nested": {
                    "path": "field2.sub",
                    "query": {"terms": {"b": ["2"]}},
                }
            },
        ]

        result = self.adapter._group_nested_filters(input_filters, self.params)
        assert len(result) == 2
        assert result[0]["nested"]["path"] == "field1.sub"
        assert result[1]["nested"]["path"] == "field2.sub"

    def test_single_filter_no_grouping(self):
        """Test that single filters are not optimized."""
        input_filters = [
            {
                "nested": {
                    "path": "single.field",
                    "query": {"terms": {"a": ["1"]}},
                }
            }
        ]

        result = self.adapter._group_nested_filters(input_filters, self.params)
        assert len(result) == 1
        assert result[0]["nested"]["path"] == "single.field"

    def test_non_nested_filters_unchanged(self):
        """Test that non-nested filters are not affected."""
        input_filters = [
            {"terms": {"field1": ["value1"]}},
            {"range": {"field2": {"gte": 10}}},
        ]

        result = self.adapter._group_nested_filters(input_filters, self.params)
        assert len(result) == 2
        assert result[0] == {"terms": {"field1": ["value1"]}}
        assert result[1] == {"range": {"field2": {"gte": 10}}}

    def test_recursive_grouping(self):
        """Test recursive grouping for multi-level nesting."""
        input_filters = [
            {"nested": {"path": "a.b.c", "query": {"terms": {"f1": ["v1"]}}}},
            {"nested": {"path": "a.b", "query": {"terms": {"f2": ["v2"]}}}},
            {"nested": {"path": "a", "query": {"terms": {"f3": ["v3"]}}}},
        ]

        result = self.adapter._group_nested_filters(input_filters, self.params)
        assert len(result) == 1
        assert result[0]["nested"]["path"] == "a"

        # Verify structure can be safely processed without infinite recursion
        result_2 = self.adapter._group_nested_filters(result, self.params)
        assert len(result_2) == 1  # Should not create additional wrapping

    def test_grouping_logic(self):
        """Test the grouping logic directly."""
        nested_filters = [
            {
                "nested": {
                    "path": "group1.field1",
                    "query": {"terms": {"a": ["1"]}},
                }
            },
            {
                "nested": {
                    "path": "group1.field2",
                    "query": {"terms": {"b": ["2"]}},
                }
            },
            {
                "nested": {
                    "path": "group2.field1",
                    "query": {"terms": {"c": ["3"]}},
                }
            },
        ]

        groups = self.adapter._group_nested_filters_by_path_components(
            nested_filters
        )
        assert len(groups) == 3
        # There was no way of knowing that group1 is not an object
        assert ("group1",) not in groups

        double_nested_filters = [
            {
                "nested": {
                    "path": "group1",
                    "query": {"bool": {"filter": nested_filters[0:1]}},
                }
            },
            nested_filters[2],
        ]

        groups = self.adapter._group_nested_filters_by_path_components(
            double_nested_filters
        )
        assert len(groups) == 2
        assert ("group1",) in groups
        assert ("group2", "field1") in groups
        assert len(groups[("group1",)]) == 1
        assert len(groups[("group2", "field1")]) == 1

    def test_empty_filter_list(self):
        """Test handling of empty filter list."""
        result = self.adapter._group_nested_filters([], self.params)
        assert result == []

    def test_mixed_nested_and_non_nested(self):
        """Test handling of mixed nested and non-nested filters."""
        input_filters = [
            {"terms": {"field1": ["value1"]}},
            {
                "nested": {
                    "path": "nested.field1",
                    "query": {"terms": {"a": ["1"]}},
                }
            },
            {
                "nested": {
                    "path": "nested.field2",
                    "query": {"terms": {"b": ["2"]}},
                }
            },
            {"range": {"field2": {"gte": 10}}},
        ]

        result = self.adapter._group_nested_filters(input_filters, self.params)
        # Should have 3 entries: 2 non-nested, 1 wrapped nested
        assert len(result) == 4
        assert result[0] == {"terms": {"field1": ["value1"]}}
        assert result[1] == {"range": {"field2": {"gte": 10}}}
        assert result[2]["nested"]["path"] == "nested.field1"

    def test_recursion_with_complex_structure(self):
        """Test recursion with a more complex nested structure."""
        # Create a structure that would benefit from recursive grouping
        input_filters = [
            {
                "nested": {
                    "path": "level1.level2.level3",
                    "query": {"terms": {"f1": ["v1"]}},
                }
            },
            {
                "nested": {
                    "path": "level1.level2",
                    "query": {"terms": {"f2": ["v2"]}},
                }
            },
            {
                "nested": {
                    "path": "level1.level2.level3.sub",
                    "query": {"terms": {"f3": ["v3"]}},
                }
            },
            {"nested": {"path": "level1", "query": {"terms": {"f4": ["v4"]}}}},
        ]

        result = self.adapter._group_nested_filters(input_filters, self.params)
        assert len(result) == 1
        assert result[0]["nested"]["path"] == "level1"

        # The result should be safe to process again
        result_2 = self.adapter._group_nested_filters(result, self.params)
        assert len(result_2) == 1
