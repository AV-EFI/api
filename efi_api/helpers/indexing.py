from efi_api.core.elasticsearch import es_client
from elasticsearch import helpers

PRIMARY_INDEX = '21.11155'
NESTED_INDEX = '21.11155-nested'
DENORMALISED_INDEX = '21.11155-denormalised-work'
NESTED_MAPPINGS = {
    "properties": {
        "has_record": {
            "properties": {
                "has_event": {
                    "type": "nested",
                    "properties": {
                        "has_activity": {
                            "type": "nested"
                        }
                    }
                }
            }
        }
    }
}
DENORMALISED_MAPPINGS = {
    "properties": {
        **NESTED_MAPPINGS["properties"],
        "manifestations": {
            "type": "nested",
            "properties": {
                **NESTED_MAPPINGS["properties"],
                "items": {
                    "type": "nested",
                    "properties": {
                        **NESTED_MAPPINGS["properties"]
                    }
                }
            }
        },
        "parents": {
            "type": "nested",
            "properties": {
                **NESTED_MAPPINGS["properties"]
            }
        }
    }
}
AVEFI_PIPELINE = 'avefi-pipeline'
INGEST_PROCESSORS = [
    {
        "script": {
            "description": "Extract directors, cast, countries … from events",
            "if": "ctx?.has_record?.has_event != null",
            "lang": "painless",
            "source": """
              List castmembers = new ArrayList();
              List countries = new ArrayList();
              List directors_or_editors = new ArrayList();
              List production = new ArrayList();
              List years = new ArrayList();
              for (event in ctx.has_record.has_event) {
                if (event?.has_activity != null) {
                  for (activity in event.has_activity) {
                    if (!activity?.has_agent.empty) {
                      if (activity?.type == 'Director' || activity?.type == 'Editor') {
                        for (agent in activity.has_agent) {
                          directors_or_editors.add(agent.has_name)
                        }
                      }
                      if (activity?.type == 'CastMember') {
                        for (agent in activity.has_agent) {
                          castmembers.add(agent.has_name)
                        }
                      }
                      if (activity?.type == 'Producer' || activity?.type == 'ProductionCompany') {
                        for (agent in activity.has_agent) {
                          production.add(agent.has_name)
                        }
                      }
                    }
                  }
                }
                if (event?.has_date != null) {
                  years.add(event.has_date)
                }
              }
              if (!castmembers.empty) {
                ctx.castmembers = castmembers
              }
              if (!countries.empty) {
                ctx.countries = countries
              }
              if (!directors_or_editors.empty) {
                ctx.directors_or_editors = directors_or_editors
              }
              if (!production.empty) {
                ctx.production = production
              }
              if (!years.empty) {
                ctx.years = years
              }
            """
        }
    },
    {
        "script": {
            "description": "Extract subjects",
            "if": "ctx?.has_record?.has_subject != null",
            "lang": "painless",
            "source": """
              List subjects = new ArrayList();
              for (subject in ctx.has_record.has_subject) {
                subjects.add(subject.has_name)
              }
              ctx.subjects = subjects;
            """
        }
    }
]


def rebuild_nested_index():
    es_client.indices.delete(index=NESTED_INDEX, ignore_unavailable=True)
    if AVEFI_PIPELINE in es_client.ingest.get_pipeline():
        es_client.ingest.delete_pipeline(id=AVEFI_PIPELINE)
    es_client.ingest.put_pipeline(
        id=AVEFI_PIPELINE, processors=INGEST_PROCESSORS)
    es_client.indices.create(
        index=NESTED_INDEX, mappings=NESTED_MAPPINGS, settings={
            'index.default_pipeline': AVEFI_PIPELINE
        })
    es_client.reindex(
        dest={
            "index": NESTED_INDEX
        },
        source={
            "index": PRIMARY_INDEX
        },
        refresh=True)


def es_iter(index=None, query=None, scroll='2m'):
    return helpers.scan(
        client=es_client, index=index, scroll=scroll, query=query)


def filter_by_pids(pids):
    return {
        "terms": {
            "handle.keyword": pids
        }
    }


def filter_by_category(category):
    return {
        "term": {
            "has_record.category.keyword": category
        }
    }


def collect_children(index, parent_ref, child_category, reference_key):
    query = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "term": {
                            reference_key: parent_ref
                        }
                    }
                ]
            }
        }
    }
    return [child['_source'] for child in es_iter(index, query)]


def collect_parents(index, doc, parents=None):
    if parents is None:
        parents = []
    references = doc.get('is_part_of', []) or doc.get('is_variant_of', [])
    if not references:
        return parents
    if not isinstance(references):
        references = [references]
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
    for parent_doc in [
            parent['_source'] for parent in es_iter(index, query)]:
        parents.append(parent_doc)
        collect_parents(index, parent_doc, parents)
    return parents


def denormalise_work(index, doc):
    """Add associated manifestations, items and parents to the document.

    Add manifestations associated via their is_manifestation_of key as
    nested documents under the manifestations key. Moreover, for each
    added manifestation collect the items associated via their
    is_item_of key and add them as nested documents under the items
    key of the manifestation.

    If there are no manifestations associated with the work to begin
    with, leave the document unchanged and return False. Otherwise,
    check wether the passed document is linked to other WorkVariant
    documents via is_part_of or is_variant_of and those documents
    under the parents key, recursively.

    Args:
        doc: dict representing document with category=avefi:WorkVariant.

    Returns:
        bool: True if associated manifestations have been found,
        meaning that the passed dict has been modified in place, False
        otherwise.

    """
    manifestations = []
    for manifestation in collect_children(
            index, doc['handle'], 'avefi:Manifestation',
            'has_record.is_manifestation_of.id.keyword'):
        items = collect_children(
            index, manifestation['handle'], 'avefi:Item',
            'has_record.is_item_of.id.keyword')
        if not items:
            continue
        manifestation['items'] = items
        manifestations.append(manifestation)
    if not manifestations:
        return False
    doc['manifestations'] = manifestations
    parents = collect_parents(index, doc)
    if parents:
        doc['parents'] = parents
    return True


def full_reindex(source_idx, target_idx):
    """Populate target index with denormalised work documents.

    Cycle through all documents with category=avefi:WorkVariant in
    ``source_idx`` and add associated manifestations and their
    associated items as nested documents. Also, add parents if
    applicable (e.g. serial works). Index the generated composite work
    documents in ``target_idx``.

    Deliberately do not reindex work documents that have no
    manifestations directly associated to them. Hence, aggregating and
    serial works will only be present in ``target_idx`` as nested
    documents under the parents key of some other work document.

    Args:
        source_idx: Name of source index.
        target_idx: Name of target index.

    """
    query = {
        "query": {
            "bool": {
                "filter": [filter_by_category('avefi:WorkVariant')]
            }
        }
    }
    # Increase scroll value for full index
    for doc in es_iter(index=source_idx, query=query, scroll='10m'):
        source_doc = doc["_source"]
        if denormalise_work(source_idx, source_doc):
            es_client.index(
                index=target_idx, document=source_doc, id=doc['_id'])


def rebuild_denormalised_index():
    es_client.indices.delete(
        index=DENORMALISED_INDEX, ignore_unavailable=True)
    es_client.indices.create(
        index=DENORMALISED_INDEX, mappings=DENORMALISED_MAPPINGS)
    full_reindex(NESTED_INDEX, DENORMALISED_INDEX)


def rebuild_search_index():
    """Entry point for rebuilding search index from scratch.

    """
    rebuild_nested_index()
    rebuild_denormalised_index()
