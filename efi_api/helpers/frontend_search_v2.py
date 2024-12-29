from http.client import HTTPException
from typing import List, Dict
import logging

from efi_api.core.elasticsearch import get_elasticsearch_client
from efi_api.schemas.frontend_search_v2 import SearchRequest

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

es_client = get_elasticsearch_client()

def build_es_query(search_request: SearchRequest) -> Dict:
    query_parts = []

    if search_request.query:
        query_parts.append({
            "bool": {
                "should": [
                    {"match": {"has_record.has_primary_title.has_name": {
                        "query": search_request.query,
                        "boost": 2}}},
                    {"match": {"_all": {
                        "query": search_request.query,
                        "fuzziness": "AUTO"}}}
                ]
            }
        })

    if search_request.facetFilters:
        for filter_group in search_request.facetFilters:
            filter_conditions = [{"match": {f.split(":")[0]: f.split(":")[1]}} for f in filter_group]
            query_parts.append({
                "bool": {
                    "should": filter_conditions,
                    "minimum_should_match": 1
                }
            })

    return {
        "query": {"bool": {"must": query_parts}},
        "size": search_request.hitsPerPage,
        "from": search_request.page * search_request.hitsPerPage,
        "aggs": {facet: {"terms": {"field": f"{facet}.keyword", "size": search_request.maxValuesPerFacet}}
                 for facet in ["castmembers", "categories", "category_clean",
                               "countries", "directors", "producers",
                               "productionyears", "subjects"]},
        "highlight": {
            "pre_tags": [search_request.highlightPreTag],
            "post_tags": [search_request.highlightPostTag],
            "fields": {
                "has_record.has_primary_title.has_name": {},
                "subjects": {}
            }
        }
    }

def execute_search(es_query: Dict) -> Dict:
    try:
        return es_client.search(index="21.11155-dev-runtime", body=es_query)
    except Exception as e:
        logger.error(f"Elasticsearch query failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to execute search query")

def transform_hits(hits: List[Dict]) -> List[Dict]:
    transformed_hits = []
    for hit in hits:
        hit_data = {
            "objectID": hit["_id"],
            "_index": hit["_index"],
            "_score": hit["_score"],
            "handle": hit["_source"].get("handle", ""),
            "has_record": hit["_source"].get("has_record", {}),
            "castmembers": hit["_source"].get("castmembers", []),
            "directors": hit["_source"].get("directors", []),
            "subjects": hit["_source"].get("subjects", []),
            "countries": hit["_source"].get("countries", []),
            "productionyears": hit["_source"].get("productionyears", [])
        }
        if "highlight" in hit:
            hit_data["_highlightResult"] = {
                "has_record": {
                    "has_primary_title": {
                        "has_name": {
                            "value": next(iter(hit["highlight"].values()))[0]
                        }
                    }
                }
            }
        transformed_hits.append(hit_data)
    return transformed_hits

def transform_facets(aggregations: Dict) -> Dict:
    return {
        facet_name: {bucket["key"]: bucket["doc_count"]
                     for bucket in facet_data["buckets"]}
        for facet_name, facet_data in aggregations.items()
    }