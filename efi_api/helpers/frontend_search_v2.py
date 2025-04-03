from http.client import HTTPException
from typing import List, Dict
import logging

from efi_api.core.elasticsearch import get_elasticsearch_client
from efi_api.schemas.frontend_search import SearchRequest
from efi_api.core.config import settings

logger = logging.getLogger(__name__)

es_client = get_elasticsearch_client()

def build_es_query(search_request: SearchRequest) -> Dict:
    query_parts = {
        "must": [],
        "filter": []
    }

    if search_request.query:
        query_parts["must"].append({
            "bool": {
                "should": [
                    {"match": {"has_record.has_primary_title.has_name": {
                        "query": search_request.query,
                        "boost": 3,
                        "fuzziness": 1}}},
                    {"match": {"production": {
                        "query": search_request.query,
                        "boost": 1,
                        "fuzziness": 1}}},
                    {"match": {"directors_or_editors": {
                        "query": search_request.query,
                        "boost": 1,
                        "fuzziness": 1}}},
                    {"match": {"castmembers": {
                        "query": search_request.query,
                        "boost": 1,
                        "fuzziness": 1}}},
                    {"match": {"subjects": {
                        "query": search_request.query,
                        "boost": 1,
                        "fuzziness": 1}}},
                    {"match": {"_all": {
                        "query": search_request.query,
                        "fuzziness": 1}}}
                ]
            }
        })

    if search_request.facetFilters:
        for filter_group in search_request.facetFilters:
            if len(filter_group) == 1:
                # Single filter in the group - add directly to filter clause
                field, value = filter_group[0].split(":")
                query_parts["filter"].append({"term": {f"{field}.keyword": value}})
            else:
                # Multiple filters in the group - these should be OR'd together
                filter_conditions = []
                for f in filter_group:
                    field, value = f.split(":")
                    filter_conditions.append({"term": {f"{field}.keyword": value}})
                
                query_parts["filter"].append({
                    "bool": {
                        "should": filter_conditions,
                        "minimum_should_match": 1
                    }
                })

    aggs = {
        "directors_or_editors": {"terms": {"field": "directors_or_editors.keyword", "size": search_request.maxValuesPerFacet}},
        "years": {"terms": {"field": "years.keyword", "size": search_request.maxValuesPerFacet}},
        "subjects": {"terms": {"field": "subjects.keyword", "size": search_request.maxValuesPerFacet}},
        "has_genre_has_name": {"terms": {"field": "has_record.has_genre.has_name.keyword", "size": search_request.maxValuesPerFacet}},
        "production": {"terms": {"field": "production.keyword", "size": search_request.maxValuesPerFacet}},
        "castmembers": {"terms": {"field": "castmembers.keyword", "size": search_request.maxValuesPerFacet}},
    }

    nested_aggs = {
        "manifestations": {
            "path": "manifestations",
            "fields": {
                "has_sound_type": "has_record.has_sound_type",
                "in_language_code": "has_record.in_language.code",
                "has_duration_has_value": "has_record.has_duration.has_value",
                "has_issuer_name": "has_record.described_by.has_issuer_name",
                "has_colour_type": "has_record.has_colour_type"
            }
        },
        "has_record.has_event": {
            "path": "has_record.has_event",
            "fields": {
                "located_in_has_name": "located_in.has_name"
            }
        },
        "manifestations.items": {
            "path": "manifestations.items",
            "fields": {
                "has_format_type": "has_record.has_format.type"
            }
        }
    }

    # Add nested aggregations to the main aggs dictionary
    for path_info in nested_aggs.values():
        for agg_name, field in path_info["fields"].items():
            aggs[agg_name] = {
                "nested": {"path": path_info["path"]},
                "aggs": {
                    agg_name: {
                        "terms": {
                            "field": f"{path_info['path']}.{field}.keyword",
                            "size": search_request.maxValuesPerFacet
                        }
                    }
                }
            }

    return {
        "query": {"bool": query_parts},
        "size": search_request.hitsPerPage,
        "from": search_request.page * search_request.hitsPerPage,
        "aggs": aggs,
        "highlight": {
            "pre_tags": [search_request.highlightPreTag],
            "post_tags": [search_request.highlightPostTag],
            "fields": {
                "has_record.has_primary_title.has_name": {},
                "production": {},
                "directors_or_editors": {},
                "castmembers": {},
                "subjects": {}
            }
        }
    }

def execute_search(es_query: Dict) -> Dict:
    try:
        return es_client.search(index=settings.ES_INDEX, body=es_query)
    except Exception as e:
        logger.error(f"Elasticsearch query failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to execute search query")

def transform_hits(hits: List[Dict], query: str) -> List[Dict]:
    transformed_hits = []
    for hit in hits:
        hit_data = {
            "objectID": hit["_id"],
            "_index": hit["_index"],
            "_score": hit["_score"],
            "handle": hit["_source"].get("handle", ""),
            "has_record": hit["_source"].get("has_record", {}),
            "directors_or_editors": hit["_source"].get("directors_or_editors", []),
            "years": hit["_source"].get("years", []),
            "manifestations": hit["_source"].get("manifestations", [])
        }
        
        highlight_data = {
            "directors_or_editors": [
                {
                    "matchLevel": "none",
                    "matchedWords": [],
                    "value": director
                }
                for director in hit["_source"].get("directors_or_editors", [])
            ]
        }
        
        if "highlight" in hit:
            title_highlight = None
            for field, highlights in hit["highlight"].items():
                if "has_primary_title.has_name" in field and highlights:
                    title_highlight = highlights[0]
                    break
                    
            if title_highlight:
                highlight_data["has_record"] = {
                    "has_primary_title": {
                        "has_name": {
                            "fullyHighlighted": False,
                            "matchLevel": "full",
                            "matchedWords": [query],  # You might want to extract this from the highlight
                            "value": title_highlight
                        }
                    }
                }
        
        hit_data["_highlightResult"] = highlight_data
        transformed_hits.append(hit_data)
    return transformed_hits

def transform_facets(aggregations: Dict) -> Dict:
    if not aggregations:
        return {}
        
    transformed_facets = {}
    for facet_name, facet_data in aggregations.items():
        if "buckets" in facet_data:
            transformed_facets[facet_name] = {
                bucket["key"]: bucket["doc_count"]
                for bucket in facet_data["buckets"]
            }
        elif facet_name in facet_data:
            nested_buckets = facet_data[facet_name]["buckets"]
            transformed_facets[facet_name] = {
                bucket["key"]: bucket["doc_count"]
                for bucket in nested_buckets
            }

    return transformed_facets
