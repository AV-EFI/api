import pytest
from fastapi.testclient import TestClient
from efi_api.main import app, ROOT_PATH

client = TestClient(app)

@pytest.fixture
def efi_data():
    return {
        "category": "avefi:WorkVariant",
        "has_primary_title": {
            "has_name": "Menschen am Sonntag – Das Dokument der Gegenwart",
            "type": "PreferredTitle"
        },
        "described_by": {
            "has_issuer_id": "https://w3id.org/isil/DE-MUS-407010",
            "has_issuer_name": "Deutsche Kinemathek - Museum für Film und Fernsehen"
        },
        "has_event": [
            {
                "category": "avefi:ProductionEvent",
                "has_activity": [
                    {
                        "category": "avefi:CastActivity",
                        "has_agent": [
                            {
                                "category": "avefi:Agent",
                                "has_name": "Borchert, Brigitte",
                                "type": "Person",
                                "same_as": [
                                    {
                                        "category": "avefi:GNDResource",
                                        "id": "173787681"
                                    }
                                ]
                            },
                            {
                                "category": "avefi:Agent",
                                "has_name": "Splettstößer, Erwin",
                                "type": "Person",
                                "same_as": [
                                    {
                                        "category": "avefi:GNDResource",
                                        "id": "1061393046"
                                    }
                                ]
                            }
                        ],
                        "type": "CastMember"
                    },
                    {
                        "category": "avefi:WritingActivity",
                        "has_agent": [
                            {
                                "category": "avefi:Agent",
                                "has_name": "Wilder, Billy",
                                "type": "Person",
                                "same_as": [
                                    {
                                        "category": "avefi:GNDResource",
                                        "id": "118632795"
                                    }
                                ]
                            }
                        ],
                        "type": "Writer"
                    }
                ],
                "has_date": "1929/1930",
                "located_in": [
                    {
                        "category": "avefi:GeographicName",
                        "has_name": "Germany (German Reich)",
                        "same_as": [
                            {
                                "category": "avefi:GNDResource",
                                "id": "2008993-4"
                            }
                        ]
                    }
                ]
            }
        ],
        "has_identifier": [
            {
                "category": "avefi:LocalResource",
                "id": "150003397"
            }
        ],
        "type": "Monographic",
        "has_genre": [
            {
                "has_name": "Fiction"
            }
        ],
        "same_as": [
            {
                "category": "avefi:FilmportalResource",
                "id": "f570e1abdad841dc8d5b25b0f7737065"
            }
        ]
    }

def test_process_efi_endpoint(efi_data):
    response = client.post(f"{ROOT_PATH}/efi", json=efi_data)
    assert response.status_code == 201, response.json()
    assert response.json()["message"] == "EFI data processed successfully"
    assert response.json()["data"] == efi_data

def test_process_efi_endpoint_invalid_data():
    invalid_data = {"invalid": "data"}
    response = client.post(f"{ROOT_PATH}/efi", json=invalid_data)
    assert response.status_code == 422, response.json() # Unprocessable Entity

def test_process_efi_endpoint_missing_required_field(efi_data):
    del efi_data["has_primary_title"]
    response = client.post(f"{ROOT_PATH}/efi", json=efi_data)
    assert response.status_code == 422, response.json() # Unprocessable Entity

def test_process_efi_endpoint_additional_field(efi_data):
    # efi_data["additional_field"] = "This should be ignored"
    efi_data["additional_field"] = "This should be rejected"
    response = client.post(f"{ROOT_PATH}/efi", json=efi_data)
    assert response.status_code == 422, response.json()
    #assert "additional_field" not in response.json()["data"]

def test_process_efi_endpoint_empty_payload():
    response = client.post(f"{ROOT_PATH}/efi", json={})
    assert response.status_code == 422, response.json() # Unprocessable Entity
