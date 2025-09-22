import logging
import re

from pydantic import BaseModel

from ..core.config import settings
from ..core.elasticsearch import es_client, es_iter
from ..schemas.efi_schema import efi


logger = logging.getLogger(__name__)


def find_matches(index: str) -> dict:
    """Iterate over WorkVariants and find matches by AVefi criteria.

    Do a full index scan for merge candidates according to the AVefi
    criteria title, country, date and director.

    Return a dict containing merge candidates in a dict and a list of
    errors that may have occurred along the way.

    """
    matches = {}
    errors = []
    work_variant_query = {"query": {"bool": {"filter": [{
        "term": {"has_record.category.keyword": {"value": "avefi:WorkVariant"}}
    }]}}}
    for doc in es_iter(index=index, query=work_variant_query, scroll='10m'):
        _make_described_by_list(doc['_source'])
        try:
            work = efi.WorkVariant.model_validate(doc['_source']['has_record'])
        except Exception as e:
            errors.append({'error': e, '_source': doc['_source']})
            continue
        hits = get_works_matching(work)
        if hits['total']['value'] > 1:
            for hit in hits['hits']:
                _make_described_by_list(hit['_source'])
            matches[doc['_source']['handle']] = hits['hits']
    return {'matches': matches, 'errors': errors}


def _make_described_by_list(doc_source: dict):
    """Helper function fixing old style described_by in WorkVariants.

    """
    if isinstance(doc_source.get('has_record', {}).get('described_by'), dict):
        doc_source['has_record']['described_by'] = [
            doc_source['has_record']['described_by']]


def get_works_matching(work: efi.WorkVariant) -> dict:
    """Return Elasticsearch hits matching `work` by AVefi criteria.

    See doc-string of `build_match_query()` for details about matching
    criteria.

    Returns:
    

    """
    query = build_match_query(work)
    if query:
        response = es_client.search(index=settings.ES_LOOKUP_INDEX, body=query)
        return response['hits']
    return {'hits': [], 'total': {'value': 0, 'relation': 'eq'}}


def build_match_query(work: efi.WorkVariant) -> dict | None:
    """Build query according to AVefi match criteria.

    Build query matching against title, place of production, year of
    production and director, respectively, editor to account for
    non-fiction works.

    """
    date_ranges = []
    location_clauses = []
    activity_clauses = []
    for event in work.has_event or []:
        # Only match on production events
        if not isinstance(event, efi.ProductionEvent):
            continue

        # Match against production year
        date_string = event.has_date
        if date_string:
            date_range = year_range_from_dtf(date_string)
            if date_range['lte'] - date_range['gte'] < 2:
                date_range['gte'] -= 1
                date_range['lte'] += 1
            date_ranges.append({"range": {"production_in_year": date_range}})

        # Country of production (or possibly city in case of amateur movies)
        for loc in event.located_in or []:
            location_clauses.extend(
                names_clause(loc, "has_record.has_event.located_in"))
            location_clauses.extend(
                same_as_clause(loc, "has_record.has_event.located_in"))

        # Director or editor
        for activity in event.has_activity or []:
            if activity.type not in ('Director', 'Editor'):
                continue
            agent_clauses = []
            for agent in activity.has_agent or []:
                agent_clauses.extend(names_clause(
                    agent, "has_record.has_event.has_activity.has_agent"))
                agent_clauses.extend(same_as_clause(
                    agent, "has_record.has_event.has_activity.has_agent"))
            if agent_clauses:
                activity_clauses.append({
                    "nested": {
                        "path": "has_record.has_event.has_activity",
                        "query": {"bool": {
                            "filter": [{"term": {
                                "has_record.has_event"
                                ".has_activity.type.keyword": activity.type,
                            }}],
                            "should": agent_clauses,
                            "minimum_should_match": 1,
                        }},
                    },
                })

    if all([date_ranges, location_clauses, activity_clauses]):
        title_clauses = []
        title_strings = [work.has_primary_title.has_name]
        # title_strings.extend(
        #     title.has_name for title in work.has_alternative_title or [])
        for title_str in title_strings:
            title_clauses.extend([
                {"match_phrase": {
                    "has_record.has_primary_title.has_name": title_str,
                }},
                {"match_phrase": {
                    "has_record.has_alternative_title.has_name": title_str,
                }},
            ])
        top_filters = date_ranges.copy()
        top_filters.append(
            {"term": {"has_record.category.keyword": work.category}}
        )
        query = {"query": {"bool": {
            "filter": top_filters,
            "must": [
                {"bool": {
                    "should": title_clauses,
                    "minimum_should_match": 1,
                }},
                _in_production_event({
                    "should": activity_clauses,
                    "minimum_should_match": 1,
                }),
                _in_production_event({
                    "should": location_clauses,
                    "minimum_should_match": 1,
                }),
            ],
        }}}
        logger.debug(f"Match query: {query}")
        return query
    else:
        return None


def _in_production_event(clause: dict) -> dict:
    nested_clause = clause.copy()
    nested_clause.setdefault("filter", []).append(
        {"term": {
            "has_record.has_event.category.keyword": "avefi:ProductionEvent",
        }}
    )
    return {"nested": {
        "path": "has_record.has_event",
        "query": {"bool": nested_clause},
    }}


def year_range_from_dtf(date_string: str) -> dict:
    """
    Convert ISO 8601 / DTF compliant string into a year range query.
    """
    components = date_string.split('/')
    start, start_margin = year_and_margin_from_dtf(components[0])
    len_components = len(components)
    if len_components == 1:
        end, end_margin = start, start_margin
    elif len_components == 2:
        end, end_margin = year_and_margin_from_dtf(components[1])
    else:
        raise ValueError(f"Cannot parse date or period: {date_string}")
    if start > end:
        raise ValueError(
            f"Period seems to start after it has ended: {date_string}")
    return {
        'gte': start - start_margin,
        'lte': end + end_margin,
    }


def year_and_margin_from_dtf(date_string: str) -> tuple:
    """
    Convert ISO 8601 / DTF compliant string into a (year, margin) tuple.
    """
    match = re.match(r'^(-?\d+)([?~]?)', date_string)
    if not match:
        raise ValueError(f"Cannot parse date: {date_string}")
    year_str, uncertainty = match.groups()
    year = int(year_str)
    if not uncertainty:
        margin = 0
    elif uncertainty == '~':
        margin = 1
    elif uncertainty == '?':
        margin = 5
    return (year, margin)


def names_clause(elem: BaseModel, path: str) -> list[dict]:
    names = [getattr(elem, 'has_name')]
    names.extend(getattr(elem, 'has_alternate_name') or [])
    query = []
    for name in names:
        query.extend([
            {"match_phrase": {f"{path}.has_name": name}},
            {"match_phrase": {f"{path}.has_alternate_name": name}},
        ])
    return query


def same_as_clause(elem: BaseModel, path: str) -> list[dict]:
    query = []
    for ref in elem.same_as or []:
        query.append({"bool": {"filter": [
            {"term": {f"{path}.same_as.id.keyword": ref.id}},
            {"term": {f"{path}.same_as.category.keyword": ref.category}},
        ]}})
    return query
