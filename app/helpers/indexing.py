from elasticsearch import helpers

from ..core.config import settings
from ..core.elasticsearch import (
    collect_children,
    collect_parents,
    es_client,
    es_iter,
    filter_by_category,
)

PRIMARY_INDEX = settings.ES_PRIMARY_INDEX
NESTED_INDEX = settings.ES_LOOKUP_INDEX
DENORMALISED_INDEX = settings.ES_INDEX
NESTED_MAPPINGS = {
    "properties": {
        "has_record": {
            "properties": {
                "has_event": {
                    "type": "nested",
                    "properties": {
                        "has_activity": {
                            "type": "nested"
                        },
                        "has_date": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        }
                    }
                },
                "has_extent": {
                    "properties": {
                        "has_value": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        }
                    }
                }
            }
        },
        "duration_in_minutes": {
            "type": "integer"
        },
        "production_in_year": {
            "type": "integer_range"
        },
        "years": {
            "type": "text",
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": 256
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
              def extractYear(def datePart) {
                def yearComponent = /^(\\d+)([?~]?)/.matcher(datePart);
                if (yearComponent.matches() && yearComponent.group(1) != '') {
                  Map result = new HashMap();
                  result['year'] = Integer.parseInt(yearComponent.group(1));
                  if (yearComponent.group(2) == '?') {
                    result['uncertainty'] = 5;
                  } else if (yearComponent.group(2) == '~') {
                    result['uncertainty'] = 1;
                  } else {
                    result['uncertainty'] = 0;
                  }
                  return result;
                }
                return null;
              }
              Map yearOfEvent(def event) {
                def date = event?.has_date;
                if (date != null) {
                  def parts = date.splitOnToken('/');
                  Map part0 = extractYear(parts[0]);
                  if (part0 != null) {
                    Map dateRange;
                    if (parts.length == 1) {
                      dateRange = [
                        "gte": part0['year'] - part0['uncertainty'],
                        "lte": part0['year'] + part0['uncertainty']
                      ];
                    } else {
                      Map part1 = extractYear(parts[1]);
                      if (part1 == null) {
                        part1 = part0;
                      }
                      dateRange = [
                        "gte": part0['year'] - part0['uncertainty'],
                        "lte": part1['year'] + part1['uncertainty']
                      ];
                    }
                    return dateRange;
                  }
                }
                return null;
              }
              List castmembers = new ArrayList();
              List countries = new ArrayList();
              List directors_or_editors = new ArrayList();
              List production = new ArrayList();
              List years = new ArrayList();
              List event_in_year = new ArrayList();
              Map year;
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
                if (event?.has_date != null
                    && event?.category == 'avefi:ProductionEvent') {
                  years.add(event.has_date);
                  year = yearOfEvent(event);
                  if (year != null) {
                    event_in_year.add(year)
                  }
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
              if (!event_in_year.empty) {
                ctx.production_in_year = event_in_year;
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
    },
    {
        "script": {
            "description": "Store duration in number of seconds",
            "if": "ctx?.has_record?.has_duration?.has_value != null",
            "lang": "painless",
            "source": """
              int result = 0;
              def durationComponent = /^PT(\\d+)H(\\d+)M([0-5][0-9])S$/.matcher(ctx.has_record.has_duration.has_value);
              if (durationComponent.matches() && durationComponent.group(1) != '') {
                result = Integer.parseInt(durationComponent.group(1)) * 60;
                result = Integer.parseInt(durationComponent.group(2)) + result;
                ctx.duration_in_minutes = result;
              }
            """
        }
    }
]


def rebuild_nested_index():
    es_client.ingest.put_pipeline(
        id=AVEFI_PIPELINE, processors=INGEST_PROCESSORS)
    es_client.indices.delete(index=NESTED_INDEX, ignore_unavailable=True)
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
    documents via is_part_of or is_variant_of and add those documents
    under the parents key, recursively.

    Args:
        doc: dict representing document with category=avefi:WorkVariant.

    Returns
    -------
    bool
        True if associated manifestations have been found,
        meaning that the passed dict has been modified in place, False
        otherwise.

    """
    manifestations = []
    for manifestation in collect_children(
            index, doc['handle'], 'is_manifestation_of'):
        items = collect_children(index, manifestation['handle'], 'is_item_of')
        if not items:
            continue
        manifestation['items'] = items
        manifestations.append(manifestation)
    if not manifestations:
        return False
    doc['manifestations'] = manifestations
    parents = collect_parents(
        index, doc, ['is_part_of', 'is_variant_of'], recursive=True)
    if parents:
        doc['parents'] = parents
    return True


BULK_SIZE = 40


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
    request_stack = []
    # Increase scroll value for full index
    for doc in es_iter(index=source_idx, query=query, scroll='10m'):
        doc_source = doc["_source"]
        if denormalise_work(source_idx, doc_source):
            request = {
                '_op_type': 'index',
                '_index': target_idx,
                '_id': doc['_id'],
                '_source': doc_source,
            }
            request_stack.append(request)
            if len(request_stack) > BULK_SIZE:
                res = helpers.bulk(
                    es_client, request_stack, raise_on_error=False)
                if res[1]:
                    raise RuntimeError(f"Bulk indexing failed: {res}")
                del request_stack[:]
    if request_stack:
        res = helpers.bulk(es_client, request_stack, raise_on_error=False)
        if res[1]:
            raise RuntimeError(f"Bulk indexing failed: {res}")
        del request_stack[:]


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
