from typing import Annotated

from fastapi import APIRouter, Path

from ...core.config import settings
from ...core.elasticsearch import collect_children, collect_parents, es_client
from ...schemas.view import DetailView

router = APIRouter()


@router.get("/view/{prefix}/{id_}", response_model=DetailView)
async def get_detail(
        prefix: Annotated[str, Path(pattern="^21\\.\\d+$")],
        id_: Annotated[str, Path(pattern="^[!-~]+$")]) -> dict:
    """Get record by EFI."""
    handle = f"{prefix}/{id_}"
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
    response = es_client.get(index=settings.ES_LOOKUP_INDEX, id=id_)
    result = response['_source']
    category = result.get('has_record', {}).get('category')
    removed_item = None
    if category == 'avefi:Item':
        if result.get('has_record', {}).get('has_access_status') == 'Removed':
            removed_item = result
        manifestation_id = result['has_record']['is_item_of']['id']
        prefix, id_ = manifestation_id.split('/', maxsplit=1)
        response = es_client.get(
            index=settings.ES_LOOKUP_INDEX, id=id_)
        result = response['_source']
        category = result.get('has_record', {}).get('category')
    if category == 'avefi:Manifestation':
        items = collect_children(
            settings.ES_LOOKUP_INDEX, f"{prefix}/{id_}", 'is_item_of')
        if removed_item:
            items.append(removed_item)
        if items:
            result['items'] = items
        work_variants = collect_parents(
            settings.ES_LOOKUP_INDEX, result, ['is_manifestation_of'])
        if len(work_variants) == 1:
            manifestations = collect_children(
                settings.ES_LOOKUP_INDEX,
                work_variants[0]['handle'],
                'is_manifestation_of')
            if removed_item:
                for i, manifestation in enumerate(manifestations):
                    if manifestation.get('handle') == result['handle']:
                        manifestations[i] = result
                        break
                else:
                    manifestations.append(result)
            result = work_variants[0]
            category = result.get('has_record', {}).get('category')
            if manifestations:
                result['manifestations'] = manifestations
        else:
            result['work_variants'] = work_variants
    if category == 'avefi:WorkVariant':
        parents = collect_parents(
            settings.ES_LOOKUP_INDEX, result, ['is_part_of', 'is_variant_of'],
            recursive=True)
        if parents:
            result['parents'] = parents
        parts = collect_children(
            settings.ES_LOOKUP_INDEX, f"{prefix}/{id_}", 'is_part_of')
        if parts:
            result['parts'] = parts
        variants = collect_children(
            settings.ES_LOOKUP_INDEX, f"{prefix}/{id_}", 'is_variant_of')
        if variants:
            result['variants'] = variants
    return {
        'handle': handle,
        'compound_record': {
            '_source': result,
        },
    }
