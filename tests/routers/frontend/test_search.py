import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.main import EFI_PATH
from app.main import app as main_app

client = TestClient(main_app)


@pytest.fixture
def mock_es_client():
    with patch('app.helpers.frontend_search.es_client') as mock:
        yield mock


@pytest.fixture
def example_request(runtime_path_of):
    with runtime_path_of(
            'search_by_date_director_format_with_facets_request.json').open() as f:
        return json.load(f)


def test_full_search_flow(mock_es_client, example_request, runtime_path_of):
    # Setup mock ES response
    with runtime_path_of(
            'search_by_date_director_format_with_facets_response.json').open() as f:
        mock_es_client.search.return_value = json.load(f)
    response = client.post(f"{EFI_PATH}/frontend/search", json=example_request)
    assert response.status_code == 200, response.json()
    mock_es_client.search.assert_called_once()

    # Transform results
    result = response.json()['results'][0]
    hits = result['hits']
    facets = result["facets"]

    # Verify top-level numbers
    assert result['nbHits'] == 2
    assert result['nbManifestations'] == 2
    assert result['nbItems'] == 2

    # Verify transformed hits
    assert len(hits) == 2
    assert hits[0]["objectID"] == "6BF2032D-3640-4BF8-A5DF-0590526F875F"
    assert hits[0]["directors_or_editors"] == ["Hinke, Gisbert"]
    assert hits[0]["production_in_year"][0]["gte"] == 1953

    # Verify transformed facets
    assert facets.get('has_colour_type') == {'BlackAndWhite': 2}
    assert facets["has_format_type"] == {'16mmFilm': 2}
    assert facets["in_language_code"]["ger"] == 2
    assert facets["production_in_year"]['1953'] == 2


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

    query = dict(
        indexName="test_index",
        params=dict(query="nonexistent"))
    response = client.post(f"{EFI_PATH}/frontend/search", json=[query])
    assert response.status_code == 200, response.json()
    mock_es_client.search.assert_called_once()
    result = response.json()['results'][0]
    hits = result["hits"]
    facets = result["facets"]

    assert len(hits) == 0
    assert facets == {}
