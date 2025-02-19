from http.client import HTTPException
import os
from fastapi import APIRouter, Depends
import httpx 
from pydantic import BaseModel
from typing import List

from efi_api.core.elasticsearch import get_elasticsearch_client
from efi_api.core.config import Settings

settings = Settings()


router = APIRouter()
url = settings.PID_SERVICE_URL
es_client = get_elasticsearch_client()

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    hits: List[dict]
    facets: dict
    page: int
    nbPages: int
    nbHits: int
    appliedRules: List[str]
    exhaustiveNbHits: bool
    exhaustiveFacetsCount: bool
    exhaustiveTypo: bool
    exhaustive: dict
    hitsPerPage: int
    processingTimeMS: int
    query: str
    renderingContent: dict

@router.post("/frontend/search", summary="Elastic Search", tags=["Frontend"])
async def multi_search(search_request: SearchRequest):
    try:
        # Construct the Elasticsearch query
        es_query = {
            "query": {
                "multi_match": {
                    "query": search_request.query,
                    "fields": ["*"]  # Search across all fields
                }
            },
            "size": 20,  # hitsPerPage from your original request
            "from": 0,   # page * hitsPerPage
            "aggs": {
                "castmembers": {
                    "terms": {
                        "field": "castmembers.keyword",
                        "size": 10
                    }
                },
                "categories": {
                    "terms": {
                        "field": "categories.keyword",
                        "size": 10
                    }
                },
                "countries": {
                    "terms": {
                        "field": "countries.keyword",
                        "size": 10
                    }
                },
                "directors": {
                    "terms": {
                        "field": "directors.keyword",
                        "size": 10
                    }
                },
                "has_record.has_subject.has_name": {
                    "terms": {
                        "field": "has_record.has_subject.has_name.keyword",
                        "size": 10
                    }
                },
                "producers": {
                    "terms": {
                        "field": "producers.keyword",
                        "size": 10
                    }
                },
                "productionyears": {
                    "terms": {
                        "field": "productionyears.keyword",
                        "size": 10
                    }
                }
            },
            "highlight": {
                "pre_tags": ["__ais-highlight__"],
                "post_tags": ["__/ais-highlight__"],
                "fields": {
                    "*": {}  # Enable highlighting for all fields
                }
            }
        }

        # Execute the search
        response = es_client.search(
            index=settings.ES_INDEX,
            body=es_query
        )

        # Transform Elasticsearch response to match your frontend expectations
        hits = response["hits"]["hits"]
        total_hits = response["hits"]["total"]["value"]
        aggregations = response["aggregations"]

        # Convert aggregations to facets format
        facets = {}
        for facet_name, facet_data in aggregations.items():
            facets[facet_name] = {
                "data": [
                    {"value": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in facet_data["buckets"]
                ]
            }

        return SearchResponse(
            hits=[{
                "_id": hit["_id"],
                "_source": hit["_source"],
                "highlight": hit.get("highlight", {})
            } for hit in hits],
            facets=facets,
            page=0,
            nbPages=(total_hits + 19) // 20,  # Calculate total pages
            nbHits=total_hits,
            appliedRules=[],
            exhaustiveNbHits=True,
            exhaustiveFacetsCount=True,
            exhaustiveTypo=True,
            exhaustive={
                "facetsCount": True,
                "nbHits": True,
                "typo": True
            },
            hitsPerPage=20,
            processingTimeMS=18,  # You might want to actually measure this
            query=search_request.query,
            renderingContent={
                "facetOrdering": {
                    "facets": {
                        "order": [
                            "has_sound_type",
                            "in_language_code",
                            "has_genre_has_name",
                            "subjects",
                            "directors_or_editors",
                            "castmembers",
                            "production",
                            "years",
                            "located_in_has_name",
                            "has_duration_has_value",
                            "has_issuer_name",
                            "has_format_type",
                            "manifestation_event_type",
                            "has_colour_type",
                            "item_element_type"
                        ]
                    },
                    "values": {
                        "has_sound_type": {"sortRemainingBy": "count"},
                        "in_language_code": {"sortRemainingBy": "count"},
                        "has_genre_has_name": {"sortRemainingBy": "count"},
                        "subjects": {"sortRemainingBy": "count"},
                        "directors_or_editors": {"sortRemainingBy": "count"},
                        "castmembers": {"sortRemainingBy": "count"},
                        "production": {"sortRemainingBy": "count"},
                        "years": {"sortRemainingBy": "count"},
                        "located_in_has_name": {"sortRemainingBy": "count"},
                        "has_duration_has_value": {"sortRemainingBy": "count"},
                        "has_issuer_name": {"sortRemainingBy": "count"},
                        "has_format_type": {"sortRemainingBy": "count"},
                        "manifestation_event_type": {"sortRemainingBy": "count"},
                        "has_colour_type": {"sortRemainingBy": "count"},
                        "item_element_type": {"sortRemainingBy": "count"}
                    }
                }
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))