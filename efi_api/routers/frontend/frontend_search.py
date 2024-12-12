from http.client import HTTPException
import os
from fastapi import APIRouter, Depends
import httpx 
from pydantic import BaseModel
from typing import List

from efi_api.core.elasticsearch import get_elasticsearch_client
from efi_api.core.config import settings


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
            index="21.11155-dev-runtime",
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
            nbHits=total_hits
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))