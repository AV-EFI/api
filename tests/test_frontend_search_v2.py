import pytest
from unittest.mock import patch

from efi_api.schemas.frontend_search_v2 import SearchRequest
from efi_api.helpers.frontend_search_v2 import build_es_query, execute_search, transform_hits, transform_facets


def test_build_es_query_basic_search():
    request = SearchRequest(
        query="test query",
        hitsPerPage=20,
        page=0,
        maxValuesPerFacet=10
    )
    
    query = build_es_query(request)
    
    assert query["query"]["bool"]["must"][0]["bool"]["should"] == [
        {"match": {"has_record.has_primary_title.has_name": {"query": "test query", "boost": 2}}},
        {"match": {"_all": {"query": "test query", "fuzziness": "AUTO"}}}
    ]
    assert query["size"] == 20
    assert query["from"] == 0

def test_build_es_query_with_facet_filters():
    request = SearchRequest(
        query="test",
        facetFilters=[
            ["category_clean:avefi_WorkVariant", "category_clean:avefi_Item"],
            ["productionyears:1975"]
        ]
    )
    
    query = build_es_query(request)
    
    assert len(query["query"]["bool"]["must"]) == 3  # query + 2 filter groups
    filter_group1 = query["query"]["bool"]["must"][1]["bool"]
    filter_group2 = query["query"]["bool"]["must"][2]["bool"]
    
    assert filter_group1["minimum_should_match"] == 1
    assert len(filter_group1["should"]) == 2
    assert filter_group2["minimum_should_match"] == 1
    assert len(filter_group2["should"]) == 1

def test_transform_hits():
    mock_hits = [{
        "_id": "123",
        "_index": "test-index",
        "_score": 1.0,
        "_source": {
            "handle": "test-handle",
            "has_record": {"title": "Test Title"},
            "castmembers": ["Actor 1"],
            "directors": ["Director 1"],
            "subjects": ["Subject 1"],
            "countries": ["Country 1"],
            "productionyears": ["2023"]
        },
        "highlight": {
            "has_record.has_primary_title.has_name": ["<em>Test</em> Title"]
        }
    }]
    
    transformed = transform_hits(mock_hits)
    
    assert transformed[0]["objectID"] == "123"
    assert transformed[0]["handle"] == "test-handle"
    assert transformed[0]["_highlightResult"]["has_record"]["has_primary_title"]["has_name"]["value"] == "<em>Test</em> Title"

def test_transform_facets():
    mock_aggregations = {
        "countries": {
            "buckets": [
                {"key": "Germany", "doc_count": 10},
                {"key": "France", "doc_count": 5}
            ]
        }
    }
    
    transformed = transform_facets(mock_aggregations)
    
    assert transformed["countries"] == {
        "Germany": 10,
        "France": 5
    }


@pytest.fixture
def mock_es_client():
    with patch('efi_api.helpers.frontend_search_v2.es_client') as mock:
        yield mock

@pytest.fixture
def example_request():
    return SearchRequest(
        query="DIE HEIMAT DES DON QUIJOTE",
        facetFilters=[
            ["category_clean:avefi_WorkVariant", "category_clean:avefi_Item"],
            ["productionyears:1975"],
            ["directors:Gasquet, Nicole"]
        ],
        facets=["castmembers", "categories", "category_clean", "countries", 
                "directors", "producers", "productionyears", "subjects"],
        highlightPreTag="__ais-highlight__",
        highlightPostTag="__/ais-highlight__",
        hitsPerPage=20,
        maxValuesPerFacet=10,
        page=0
    )

@pytest.fixture
def mock_es_response():
    return {
        "took": 5,
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "max_score": 1.0,
            "hits": [{
                "_index": "test-index",
                "_id": "123",
                "_score": 1.0,
                "_source": {
                    "handle": "test/123",
                    "has_record": {
                        "has_primary_title": {
                            "has_name": "DIE HEIMAT DES DON QUIJOTE"
                        }
                    },
                    "castmembers": ["Actor 1"],
                    "directors": ["Gasquet, Nicole"],
                    "subjects": ["Literature"],
                    "countries": ["Spain"],
                    "productionyears": ["1975"],
                    "category_clean": ["avefi_WorkVariant"]
                },
                "highlight": {
                    "has_record.has_primary_title.has_name": [
                        "__ais-highlight__DIE HEIMAT__/ais-highlight__ DES DON QUIJOTE"
                    ]
                }
            }]
        },
        "aggregations": {
            "countries": {
                "buckets": [
                    {"key": "Spain", "doc_count": 1}
                ]
            },
            "directors": {
                "buckets": [
                    {"key": "Gasquet, Nicole", "doc_count": 1}
                ]
            },
            "productionyears": {
                "buckets": [
                    {"key": "1975", "doc_count": 1}
                ]
            }
        }
    }

def test_full_search_flow(mock_es_client, example_request, mock_es_response):
    # Setup mock ES response
    mock_es_client.search.return_value = mock_es_response
    
    # Build query
    query = build_es_query(example_request)
    
    # Verify query structure
    assert len(query["query"]["bool"]["must"]) == 4  # query + 3 filter groups
    assert query["highlight"]["pre_tags"] == ["__ais-highlight__"]
    assert query["highlight"]["post_tags"] == ["__/ais-highlight__"]
    
    # Execute search
    response = execute_search(query)
    
    # Verify ES client was called correctly
    mock_es_client.search.assert_called_once_with(
        index="21.11155-dev-runtime",
        body=query
    )
    
    # Transform results
    hits = transform_hits(response["hits"]["hits"])
    facets = transform_facets(response["aggregations"])
    
    # Verify transformed hits
    assert len(hits) == 1
    assert hits[0]["objectID"] == "123"
    assert hits[0]["directors"] == ["Gasquet, Nicole"]
    assert hits[0]["productionyears"] == ["1975"]
    
    # Verify transformed facets
    assert facets["countries"]["Spain"] == 1
    assert facets["directors"]["Gasquet, Nicole"] == 1
    assert facets["productionyears"]["1975"] == 1

def test_empty_response_handling(mock_es_client):
    # Setup mock with empty response
    mock_es_client.search.return_value = {
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "hits": []
        },
        "aggregations": {}
    }
    
    query = build_es_query(SearchRequest(query="nonexistent"))
    response = execute_search(query)
    
    hits = transform_hits(response["hits"]["hits"])
    facets = transform_facets(response["aggregations"])
    
    assert len(hits) == 0
    assert facets == {}