import json

from fastapi.testclient import TestClient
import pytest

from app.main import EFI_PATH, app
from app.schemas.efi_schema import efi

pytest.skip(allow_module_level=True)

client = TestClient(app)

@pytest.fixture
def valid_input_data():
    return {
        "category": "avefi:WorkVariant",
        "has_primary_title": {
            "has_name": "DIE HEIMAT DES DON QUIJOTE",
            "type": "PreferredTitle",
            "has_ordering_name": "HEIMAT DES DON QUIJOTE, DIE"
        },
        "has_event": [
            {
                "category": "avefi:ProductionEvent",
                "has_activity": [
                    {
                        "category": "avefi:DirectingActivity",
                        "has_agent": [
                            {
                                "category": "avefi:Agent",
                                "has_name": "Hinke, Gisbert",
                                "type": "Person"
                            }
                        ],
                        "type": "Director"
                    }
                ],
                "has_date": "1953",
                "located_in": [
                    {
                        "category": "avefi:GeographicName",
                        "has_name": "Deutschland"
                    }
                ]
            }
        ],
        "type": "Monographic"
    }

@pytest.fixture
def expected_output():
    return [
        {
            "type": "KIP",
            "parsed_data": "http://typeapi.lab.pidconsortium.net/v1/types/schema/21.T11969/873d5c9f6ebbffecf1df",
            "idx": 1
        },
        {
            "type": "has_record",
            "parsed_data": efi.WorkVariant.model_validate({
                "category": "avefi:WorkVariant",
                "has_primary_title": {
                    "has_name": "DIE HEIMAT DES DON QUIJOTE",
                    "type": "PreferredTitle",
                    "has_ordering_name": "HEIMAT DES DON QUIJOTE, DIE"
                },
                "described_by": [
                    {
                        "has_issuer_id": "https://w3id.org/isil/DE-MUS-432511",
                        "has_issuer_name":
                        "Filmmuseum der Landeshauptstadt Düsseldorf"
                    }
                ],
                "has_event": [
                    {
                        "category": "avefi:ProductionEvent",
                        "has_activity": [
                            {
                                "category": "avefi:DirectingActivity",
                                "has_agent": [
                                    {
                                        "category": "avefi:Agent",
                                        "has_name": "Hinke, Gisbert",
                                        "type": "Person"
                                    }
                                ],
                                "type": "Director"
                            }
                        ],
                        "has_date": "1953",
                        "located_in": [
                            {
                                "category": "avefi:GeographicName",
                                "has_name": "Deutschland"
                            }
                        ]
                    }
                ],
                "type": "Monographic"
            }).model_dump_json(exclude_unset=True),
            "idx": 2
        }
    ]

def test_successful_transformation(valid_input_data, expected_output):
    """Test successful transformation of valid input data."""
    response = client.post(f"{EFI_PATH}/transform", json=valid_input_data)
    assert response.status_code == 200, response.json()
    assert response.json() == expected_output

def test_missing_required_field():
    """Test handling of missing required fields."""
    invalid_data = {
        "category": "avefi:WorkVariant",
        # missing has_primary_title
        "has_event": [],
        "type": "Monographic"
    }
    response = client.post(f"{EFI_PATH}/transform", json=invalid_data)
    assert response.status_code == 422  # Validation error

def test_invalid_data_type():
    """Test handling of invalid data types."""
    invalid_data = {
        "category": "avefi:WorkVariant",
        "has_primary_title": {
            "has_name": 123,  # should be string
            "type": "PreferredTitle",
            "has_ordering_name": "HEIMAT DES DON QUIJOTE, DIE"
        },
        "has_event": [],
        "type": "Monographic"
    }
    response = client.post(f"{EFI_PATH}/transform", json=invalid_data)
    assert response.status_code == 422

def test_empty_input():
    """Test handling of empty input."""
    response = client.post(f"{EFI_PATH}/transform", json={})
    assert response.status_code == 422

def test_output_structure(valid_input_data):
    """Test the structure of the output."""
    response = client.post(f"{EFI_PATH}/transform", json=valid_input_data)
    data = response.json()

    # Check if output is a list with exactly 2 items
    assert isinstance(data, list)
    assert len(data) == 2

    # Check first item (KIP record)
    assert data[0]["type"] == "KIP"
    assert isinstance(data[0]["parsed_data"], str)
    assert data[0]["idx"] == 1

    # Check second item (has_record)
    assert data[1]["type"] == "has_record"
    assert isinstance(data[1]["parsed_data"], str)
    assert data[1]["idx"] == 2

    # Check if described_by was added
    assert "described_by" in data[1]["parsed_data"]

def test_described_by_content(valid_input_data):
    """Test if described_by field is correctly added."""
    response = client.post(f"{EFI_PATH}/transform", json=valid_input_data)
    payload = json.loads(response.json()[1]["parsed_data"])
    described_by = payload["described_by"]

    assert described_by[0]["has_issuer_id"] == "https://w3id.org/isil/DE-MUS-432511"
    assert described_by[0][
        "has_issuer_name"] == "Filmmuseum der Landeshauptstadt Düsseldorf"

def test_invalid_json():
    """Test handling of invalid JSON."""
    response = client.post(f"{EFI_PATH}/transform", content="invalid json")
    assert response.status_code == 422
