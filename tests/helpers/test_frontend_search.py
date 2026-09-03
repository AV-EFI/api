from app.core.config import settings
from app.helpers.frontend_search import process_search_request
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
            "combined_fields": {
                "query": "test query",
                "fields": process_search_request.query_fields,
                "zero_terms_query": "all",
                "boost": 2,
                "operator": "and",
            }
        },
        {
            "multi_match": {
                "query": "test query",
                "fields": process_search_request.query_fields,
                "zero_terms_query": "all",
                "fuzziness": "AUTO",
                "minimum_should_match": "90%",
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
                ["creators:Director 1"],
                [
                    "has_format_type:16mmFilm",
                    "has_format_type:35mmFilm",
                ],
            ],
        ),
    )

    query = process_search_request.build_es_query(request)

    assert len(query["query"]["bool"]["should"]) == 2
    assert list(query["query"]["bool"]["should"][0].keys()) == [
        "combined_fields",
    ]
    assert len(query["query"]["bool"]["filter"]) == 2
    assert query["query"]["bool"]["filter"][0] == {
        "terms": {"creators.keyword": ["Director 1"]},
    }
    assert len(query["query"]["bool"]["filter"]) == 2

    # Special checks related to filtering nested documents
    nested_filter_clause = query["query"]["bool"]["filter"][1]["nested"]
    assert "*" in nested_filter_clause["inner_hits"]["highlight"]["fields"]
    nested_filter_clause = nested_filter_clause["query"]["bool"]["filter"][0][
        "nested"
    ]
    assert nested_filter_clause["query"]["bool"]["filter"][0]["terms"][
        "manifestations.items.has_record.has_format.type.keyword"
    ] == ["16mmFilm", "35mmFilm"]

    # Check that nested filters are applied to implicit aggregations
    assert list(query["aggs"]) == ["categories", "manifestations"]
    assert (
        query["aggs"]["manifestations"]["nested"]["path"] == "manifestations"
    )
    assert list(query["aggs"]["manifestations"]["aggs"]) == [
        "filtered_manifestations"
    ]
    filtered_agg = query["aggs"]["manifestations"]["aggs"][
        "filtered_manifestations"
    ]
    agg_nested_filter = filtered_agg["filter"]["bool"]["filter"][0]["nested"]
    assert set(agg_nested_filter["query"]["bool"]["filter"][0]) == set(
        ["terms"]
    )
    assert "inner_hits" not in agg_nested_filter
    assert set(filtered_agg["aggs"]) == set(["handle_count", "items"])


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
                "creators": ["Director 1"],
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
