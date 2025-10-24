from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from ...core.config import settings
from ...core.elasticsearch import collect_children, collect_parents, es_client
from ...schemas.view import DetailView


router = APIRouter()


@router.get("/view/{prefix}/{id}", response_model=DetailView)
async def get_detail(
        prefix: Annotated[str, Path(pattern="^21\\.\\d+$")],
        id: Annotated[str, Path(pattern="^[!-~]+$")]) -> dict:
    """
    Get record by EFI.
    """
    handle = f"{prefix}/{id}"
    query = {"query": {"bool": {"filter": [{"bool": {"should": [
        {"term": {"handle.keyword": handle}},
        {"nested": {
            "path": "manifestations",
            "query": {"bool": {"should": [
                {"term": {"manifestations.handle.keyword": handle}},
                {"nested": {
                    "path": "manifestations.items",
                    "query": {"term": {
                        "manifestations.items.handle.keyword": handle
                    }}
                }}
            ]}}
        }}
    ]}}]}}}
    response = es_client.search(index=settings.ES_INDEX, body=query)
    total = response['hits']['total']['value']
    if total == 1:
        return {
            'handle': handle,
            'compound_record': response['hits']['hits'][0],
        }
    response = es_client.get(index=settings.ES_LOOKUP_INDEX, id=id)
    result = response['_source']
    category = result.get('has_record', {}).get('category')
    if category == 'avefi:Item':
        manifestation_id = result['has_record']['is_item_of']['id']
        prefix, id = manifestation_id.split('/', maxsplit=1)
        response = es_client.get(
            index=settings.ES_LOOKUP_INDEX, id=id)
        result = response['_source']
        category = result.get('has_record', {}).get('category')
    if category == 'avefi:Manifestation':
        work_variants = collect_parents(
            settings.ES_LOOKUP_INDEX, result, ['is_manifestation_of'])
        if len(work_variants) < 2:
            raise HTTPException(
                status_code=500,
                detail=f"Works for manifestation {handle} not properly"
                f" indexed yet, try again later.")
        result['work_variants'] = work_variants
        items = collect_children(
            settings.ES_LOOKUP_INDEX, f"{prefix}/{id}", 'is_item_of')
        if items:
            result['items'] = items
    elif category == 'avefi:WorkVariant':
        parents = collect_parents(
            settings.ES_LOOKUP_INDEX, result, ['is_part_of', 'is_variant_of'],
            recursive=True)
        if parents:
            result['parents'] = parents
        parts = collect_children(
            settings.ES_LOOKUP_INDEX, f"{prefix}/{id}", 'is_part_of')
        if parts:
            result['parts'] = parts
        variants = collect_children(
            settings.ES_LOOKUP_INDEX, f"{prefix}/{id}", 'is_variant_of')
        if variants:
            result['variants'] = variants
    else:
        raise RuntimeError(
            f"Unexpected category: {category} while resolving handle:"
            f" {prefix}/{id}")
    return {
        'handle': handle,
        'compound_record': {
            '_source': result,
        },
    }
