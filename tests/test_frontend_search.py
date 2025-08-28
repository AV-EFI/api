import pytest
from unittest.mock import patch

from efi_api.core.config import settings
from efi_api.helpers.frontend_search import (
    process_search_request, SearchAdapter,
)
from efi_api.schemas.frontend_search import SearchParams, SearchRequest

def test_build_es_query_basic_search():
    request = SearchRequest(
        indexName=settings.ES_INDEX,
        params={
            'query': "test query",
            'hitsPerPage': 20,
            'page': 0,
            'maxValuesPerFacet': 10,
        },
    )

    query = process_search_request.build_es_query(request)

    assert query["query"]["bool"]["must"] == [
        {"combined_fields": {
            "query": "test query",
            "fields": process_search_request.query_fields,
            "zero_terms_query": "all",
        }},
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
                ]
            ]
        ))
    
    query = process_search_request.build_es_query(request)
    
    assert len(query["query"]["bool"]["must"]) == 1
    assert list(query["query"]["bool"]["must"][0].keys()) == [
        "combined_fields"]
    assert len(query["query"]["bool"]["filter"]) == 2
    assert query["query"]["bool"]["filter"][0] == {
        "terms": {"directors_or_editors.keyword": ["Director 1"]},
    }
    assert len(query["query"]["bool"]["filter"]) == 2
    assert query["query"]["bool"]["filter"][1]["nested"]["query"][
        "nested"]["query"]["terms"][
            "manifestations.items.has_record.has_format.type.keyword"] == [
                "16mmFilm", "35mmFilm"]

def test_transform_hits():
    mock_hits = [{
        "_id": "123",
        "_index": "test-index",
        "_score": 1.0,
        "_source": {
            "handle": "test-handle",
            "has_record": {"has_primary_title": {
                "has_name": "Test Title",
                "type": "PreferredTitle"
            }},
            "castmembers": ["Actor 1"],
            "directors_or_editors": ["Director 1"],
            "subjects": ["Subject 1"],
            "production": ["Country 1"],
            "years": ["2023"]
        },
        "highlight": {
            "has_record.has_primary_title.has_name": [
                "<em>Test</em> Title"
            ]
        }
    }]
    params = SearchParams(
        query="test query",
        hitsPerPage=20,
        page=0,
        maxValuesPerFacet=10,
    )

    transformed = process_search_request.transform_hits(mock_hits, params)
    
    assert transformed[0]["objectID"] == "123"
    assert transformed[0]["handle"] == "test-handle"
    assert transformed[0]["_highlightResult"]["has_record"][
        "has_primary_title"]["has_name"][0]["value"] == "<em>Test</em> Title"

def test_transform_facets():
    mock_aggregations = {
        "production.keyword": {
            "buckets": [
                {"key": "Germany", "doc_count": 10},
                {"key": "France", "doc_count": 5}
            ]
        }
    }
    
    transformed = process_search_request.transform_facets(mock_aggregations)
    
    assert transformed["production"] == {
        "Germany": 10,
        "France": 5
    }


@pytest.fixture
def mock_es_client():
    with patch('efi_api.helpers.frontend_search.es_client') as mock:
        yield mock

@pytest.fixture
def example_request():
    return SearchRequest(
        indexName=settings.ES_INDEX,
        params=SearchParams.model_validate({
            "query": "DIE HEIMAT DES DON QUIJOTE",
            "numeric-refinements": {
                "production_in_year": {
                    ">=": 1953,
                    "<=": 1953
                }
            },
            "facetFilters": [
                ["directors_or_editors:Hinke, Gisbert"]
            ],
            "facets": [
                "castmembers", "production", "directors_or_editors",
                "has_format_type", "subjects",
            ],
            "highlightPreTag": "__ais-highlight__",
            "highlightPostTag": "__/ais-highlight__",
            "hitsPerPage": 20,
            "maxValuesPerFacet": 10,
            "page": 0,
        }))

@pytest.fixture
def mock_es_response():
    return {
        "took": 10,
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "max_score": 45.886757,
            "hits": [{
                "_index": "21.11155-denormalised-work",
                "_id": "123",
                "_score": 45.886757,
                "_source": {
                    "handle": "test/123",
                    "has_record": {
                        "has_primary_title": {
                            "has_name": "DIE HEIMAT DES DON QUIJOTE"
                        }
                    },
                    "castmembers": ["Actor 1"],
                    "directors_or_editors": ["Gasquet, Nicole"],
                    "subjects": ["Literature"],
                    "production": ["Spain"],
                    "production_in_year": [
                        {
                            "gte": 1953,
                            "lte": 1953
                        }
                    ],
                },
                "highlight": {
                    "directors_or_editors.keyword": [
                        "__ais-highlight__Hinke, "
                        "Gisbert__/ais-highlight__"
                    ],
                    "has_record.has_primary_title.has_name": [
                        "__ais-highlight__DIE__/ais-highlight__ "
                        "__ais-highlight__HEIMAT__/ais-highlight__ "
                        "__ais-highlight__DES__/ais-highlight__ "
                        "__ais-highlight__DON__/ais-highlight__ "
                        "__ais-highlight__QUIJOTE__/ais-highlight__"
                    ]
                }
            }]
        },
        "aggregations": {
            "production.keyword": {
                "buckets": [
                    {"key": "Spain", "doc_count": 1}
                ]
            },
            "directors_or_editors.keyword": {
                "buckets": [
                    {"key": "Gasquet, Nicole", "doc_count": 1}
                ]
            },
            'manifestations': {
                'doc_count': 1,
                'items': {
                    'doc_count': 6,
                    'has_record.has_format.type.keyword': {
                        'buckets': [
                            {'doc_count': 5, 'key': '35mmFilm'},
                            {'doc_count': 1, 'key': '17.5mmFilm'}
                        ],
                        'doc_count_error_upper_bound': 0,
                        'sum_other_doc_count': 0
                    }
                }
            }
        }
    }

def test_full_search_flow(mock_es_client, example_request, mock_es_response):
    # Setup mock ES response
    mock_es_client.search.return_value = mock_es_response
    
    response = process_search_request(example_request)
    
    # Verify ES client was called correctly
    mock_es_client.search.assert_called_once_with(
        index=settings.ES_INDEX,
        body=process_search_request.build_es_query(example_request),
    )

    # Transform results
    hits = response["hits"]
    facets = response["facets"]

    # Verify transformed hits
    assert len(hits) == 1
    assert hits[0]["objectID"] == "123"
    assert hits[0]["directors_or_editors"] == ["Gasquet, Nicole"]
    assert hits[0]["production_in_year"][0]["gte"] == 1953

    # Verify transformed facets
    assert facets["production"]["Spain"] == 1
    assert facets["directors_or_editors"]["Gasquet, Nicole"] == 1
    assert facets["has_format_type"] == {'35mmFilm': 5, '17.5mmFilm': 1}

def test_empty_response_handling(mock_es_client):
    # Setup mock with empty response
    mock_es_client.search.return_value = {
        "took": 1,
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "hits": []
        },
        "aggregations": {}
    }
    
    query = SearchRequest(
        indexName=settings.ES_INDEX,
        params=SearchParams(query="nonexistent"))
    response = process_search_request(query)
    
    hits = response["hits"]
    facets = response["facets"]
    
    assert len(hits) == 0
    assert facets == {}
