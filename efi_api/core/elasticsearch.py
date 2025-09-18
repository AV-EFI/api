from typing import Optional

from elasticsearch import Elasticsearch, helpers

from .config import settings


def get_elasticsearch_client() -> Elasticsearch:
    """
    Create and return Elasticsearch client instance
    """
    return Elasticsearch(
        [{
            'host': settings.ES_HOST,
            'port': settings.ES_PORT,
            'scheme': settings.ES_SCHEME
        }],
        request_timeout=30,
        max_retries=4,
        retry_on_timeout=True,
    )


# Initialize Elasticsearch client
es_client = get_elasticsearch_client()


def es_iter(index=None, query=None, scroll='2m'):
    return helpers.scan(
        client=es_client, index=index, scroll=scroll, query=query)


def filter_by_pids(pids: list[str]) -> dict:
    return {
        "terms": {
            "handle.keyword": pids
        }
    }


def filter_by_category(category: str) -> dict:
    return {
        "term": {
            "has_record.category.keyword": category
        }
    }


def collect_parents(
        index: str, doc: dict, reference_keys: list[str], recursive=False,
        parents: Optional[dict | None] = None):
    """Get list of WorkVariants evaluating is_part_of, is_variant_of.

    Resolve the handles in has_record.is_part_of or
    has_record.is_variant_of, recursively, and return one list in
    ascending order.

    - `index`: Index to be queried.
    - `doc`: '_source' part of an ES document.
    - `reference_keys`: List of keys und `has_record` to be used for parent lookup.
    - `recursive`: Recursively lookup parents if true.
    - `parents`: For internal use during rescursiosn.

    """
    if parents is None:
        parents = []
    record = doc.get('has_record', {})
    references = []
    for ref_key in reference_keys:
        refs = record.get(ref_key, [])
        if not refs:
            continue
        if isinstance(refs, list):
            references.extend(refs)
        else:
            references.append(refs)
    if not references:
        return parents
    parent_ids = [
        parent.get('id') for parent in references if parent.get('id')]
    query = {
        "query": {
            "bool": {
                "filter": [
                    filter_by_pids(parent_ids)
                ]
            }
        }
    }
    for parent in es_iter(index, query):
        parent_doc = parent['_source']
        parents.append(parent_doc)
        if recursive:
            collect_parents(
                index, parent_doc, reference_keys, recursive, parents)
    return parents


def collect_children(index: str, parent_ref: str, reference_key: str):
    """Gather children linked to current document.

    Collect child documents referencing current document, e.g. items
    linked to a manifestation.

    - `index`: Index to be used for lookup.
    - `parent_ref`: Handle identifying the parent doc.
    - `reference_key`: Key und `has_record` in the child docs referencing the parent.

    """
    query = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            f"has_record.{reference_key}.id.keyword": parent_ref
                        }
                    }
                ]
            }
        }
    }
    return [child['_source'] for child in es_iter(index, query)]
