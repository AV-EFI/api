from collections import defaultdict
import json
import logging
import re
from typing import List, Dict
from urllib import parse

from fastapi import HTTPException

from ..core.config import settings
from ..core.elasticsearch import es_client
from ..schemas.frontend_search import SearchParams, SearchRequest


logger = logging.getLogger(__name__)


class SearchAdapter:
    """Handle search requests from instantsearch.js.

    Implement an endpoint according to the Algolia specification:
    https://www.algolia.com/doc/rest-api/search/#tag/Search/operation/search

    """
    search_attributes = [
        {
            "field": "has_record.has_primary_title.has_name",
            "weight": 2
        },{
            "field": "has_record.has_alternative_title.has_name",
            "weight": 2
        },{
            "field": "production",
            "weight": 1
        },{
            "field": "directors_or_editors",
            "weight": 1
        },{
            "field": "subjects",
            "weight": 1
        }
    ]

    result_attributes = [
        "@timestamp",
        "has_record.described_by",
        "has_record.has_primary_title.has_name",
        "has_record.has_alternative_title",
        "has_record.category",
        "has_record.has_form",
        "has_record.is_part_of",
        "subjects",
        "handle",
        "production",
        "directors_or_editors",
        "castmembers",
        "has_record.has_genre.has_name",
        "years",
        "has_record.has_event.located_in",
        "manifestations.handle",
        "manifestations.has_record.has_duration.has_value",
        "manifestations.has_record.described_by.has_issuer_name",
        "manifestations.items.has_record.has_format.type",
        "manifestations.has_record.has_colour_type",
        "manifestations.has_record.element_type",
        "manifestations.items.has_record.element_type",
        "manifestations.has_record.has_sound_type",
        "manifestations.has_record.in_language.code",
        "manifestations.has_record.is_manifestation_of",
        "manifestations.items",
        "production_in_year.lte",
        "production_in_year.gte"
    ]

    facet_attributes = [
        {
            "attribute": "production_in_year",
            "field": "production_in_year",
            "type": "numeric-refinement"
        },{
            "attribute": "has_sound_type",
            "field": "has_record.has_sound_type.keyword",
            "type": "string",
            "nested_paths": ["manifestations"]
        },{
            "attribute": "in_language_code",
            "field": "has_record.in_language.code.keyword",
            "type": "string",
            "nested_paths": ["manifestations"]
        },{
            "attribute": "has_genre_has_name",
            "field": "has_record.has_genre.has_name.keyword",
            "type": "string"
        },{
            "attribute": "subjects", 
            "field": "subjects.keyword",
            "type": "string"
        },{
            "attribute": "directors_or_editors",
            "field": "directors_or_editors.keyword",
            "type": "string"
        },{
            "attribute": "castmembers",
            "field": "castmembers.keyword",
            "type": "string"
        },{
            "attribute": "production",
            "field": "production.keyword",
            "type": "string"
        },{
            "attribute": "years",
            "field": "years.keyword",
            "type": "string"
        },{
            "attribute": "located_in_has_name",
            "field": "located_in.has_name.keyword",
            "type": "string",
            "nested_paths": ["has_record.has_event"]
        },{
            "attribute": "has_duration_has_value",
            "field": "has_record.has_duration.has_value.keyword",
            "type": "string",
            "nested_paths": ["manifestations"]
        },{
            "attribute": "has_issuer_name",
            "field": "has_record.described_by.has_issuer_name.keyword",
            "type": "string",
            "nested_paths": ["manifestations"]
        },{
            "attribute": "has_format_type",
            "field": "has_record.has_format.type.keyword",
            "type": "string",
            "nested_paths": ["manifestations", "items"]
        },{
            "attribute": "manifestation_event_type",
            "field": "type.keyword",
            "type": "string",
            "nested_paths": ["manifestations", "has_record.has_event"]
        },{
            "attribute": "has_colour_type", 
            "field": "has_record.has_colour_type.keyword",
            "type": "string",
            "nested_paths": ["manifestations"]
        },{
            "attribute": "item_element_type",
            "field": "has_record.element_type.keyword",
            "type": "string",
            "nested_paths": ["manifestations", "items"]
        },{
            "attribute": "has_form",
            "field": "has_record.has_form.keyword",
            "type": "string"
        }
    ]

    sorting = {
        "default": [
            {
                "field": "_score",
                "order": "desc"
            },{
                "field": "has_record.has_primary_title.has_name.keyword",
                "order": "asc"
            }
        ],
        "_title_asc": {
            "field": "has_record.has_primary_title.has_name",
            "order": "asc"
        },        
        "_title_desc": {
            "field": "has_record.has_primary_title.has_name",
            "order": "desc"
        },
        "_country_asc": {
            "field": "country",
            "order": "asc"
        },
        "_country_desc": {
            "field": "country",
            "order": "desc"
        },        
        "_year_asc": {
            "field": "year",
            "order": "asc"
        },        
        "_year_desc": {
            "field": "year",
            "order": "desc"
        },
        "_directors_asc": {
            "field": "directors_or_editors",
            "order": "asc"
        },
        "_directors_desc": {
            "field": "directors_or_editors",
            "order": "desc"
        },        
        "_production_asc": {
            "field": "production",
            "order": "asc"
        },
        "_production_desc": {
            "field": "production",
            "order": "desc"
        }
    }

    # Refer to: https://www.algolia.com/doc/guides/building-search-ui/ui-and-ux-patterns/facet-display/js/
    renderingContent = {
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
                    "located_in_has_name",
                    "has_duration_has_value",
                    "has_issuer_name",
                    "has_format_type",
                    "manifestation_event_type",
                    "has_colour_type",
                    "item_element_type",
                    "has_form"
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
                "located_in_has_name": {"sortRemainingBy": "count"},
                "has_duration_has_value": {"sortRemainingBy": "count"},
                "has_issuer_name": {"sortRemainingBy": "count"},
                "has_format_type": {"sortRemainingBy": "count"},
                "manifestation_event_type": {"sortRemainingBy": "count"},
                "has_colour_type": {"sortRemainingBy": "count"},
                "item_element_type": {"sortRemainingBy": "count"},
                "has_form": {"sortRemainingBy": "count"}
            }
        }
    }

    def __init__(self):
        self.query_fields = [
            f"{qf['field']}^{qf['weight']}" for qf in self.search_attributes
        ]
        self.facet_by_name = {}
        self.facet_by_path = {}
        for attr in self.facet_attributes:
            self.facet_by_name[attr['attribute']] = attr
            path_segments = attr.get('nested_paths', []).copy()
            path_segments.append(attr['field'])
            field_path = '.'.join(path_segments)
            self.facet_by_path[field_path] = attr

    def __call__(self, request: SearchRequest):
        es_query = self.build_es_query(request)
        try:
            response = es_client.search(index=settings.ES_INDEX, body=es_query)
        except Exception:
            logger.error(
                f"Elasticsearch query failed: {json.dumps(es_query)}")
            raise
        try:
            return self.transform_es_response(response, request)
        except Exception:
            logger.error(
                f"Error while parsing Elasticsearch response: {response}")
            raise

    def build_es_query(self, request: SearchRequest) -> dict:
        params = request.params
        query = {
            "query": {
                "bool": self.get_must_clause(params.query)
            },
            "size": params.hitsPerPage,
            "from": params.page * params.hitsPerPage,
            "highlight": {
                "fields": {
                    "*": {
                        "pre_tags": [params.highlightPreTag],
                        "post_tags": [params.highlightPostTag],
                    }
                }
            }
        }
        if params.facetFilters:
            query['query']['bool']['filter'] = self.get_filter_clause(params)
        if params.facets:
            query['aggs'] = self.get_aggs_clause(params)
        return query

    def get_filter_clause(self, params: SearchParams) -> dict:
        """Build filter clause.

        API references:
        https://www.algolia.com/doc/api-reference/api-parameters/facetFilters/
        https://www.algolia.com/doc/api-reference/api-parameters/numericFilters/
        https://www.algolia.com/doc/api-reference/api-parameters/filters/

        """
        filter_list = []
        for filter_group in params.facetFilters:
            if isinstance(filter_group, list):
                subfilter_dict = defaultdict(list)
                for subfilter in filter_group:
                    try:
                        key, term = subfilter.split(':', maxsplit=1)
                    except ValueError:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Cannot handle facet filter: {subfilter}")
                    subfilter_dict[key].append(term)
                subfilter_list = []
                for key, val in subfilter_dict.items():
                    subfilter_list.append(self._es_filter_from_facet(key, val))
                if len(subfilter_list) == 1:
                    entry = subfilter_list[0]
                elif len(subfilter_list) > 1:
                    entry = {"bool": {"should": subfilter_list}}
            else:
                try:
                    key, term = filter_group.split(':', maxsplit=1)
                except ValueError:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Cannot handle facet filter: {filter_group}")
                entry = self._es_filter_from_facet(key, term)
            filter_list.append(entry)
        if params.numericRefinements:
            for key, refinement in params.numericRefinements.items():
                range_dict = {
                    {
                        '<': 'lt',
                        '<=': 'lte',
                        '>=': 'gte',
                        '>': 'gt',
                    }[k]: v
                    for k, v in refinement.items()
                }
                entry = self._es_filter_from_facet(key, range_dict)
                filter_list.append(entry)
        return filter_list

    def _es_filter_from_facet(self, facet_name: str, value):
        try:
            facet_attr = self.facet_by_name[facet_name]
        except KeyError:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown facet filter: {facet_name}")
        path_segments = facet_attr.get("nested_paths", []).copy()
        path_segments.append(facet_attr["field"])
        if facet_attr['type'] == 'string':
            entry = {"terms": {'.'.join(path_segments): value}}
        elif facet_attr['type'] == 'numericRefinement':
            entry = {"range": {'.'.join(path_segments): value}}
        for i in range(len(path_segments)-1, 0, -1):
            entry = {
                "nested": {
                    "path": '.'.join(path_segments[:i]),
                    "query": entry,
                }
            }
        return entry

    def get_must_clause(self, query):
        return {"must": [
            {
                "combined_fields": {
                    "query": query,
                    "fields": self.query_fields,
                    "zero_terms_query": "all",
                }
            }
        ]}

    def get_aggs_clause(self, params: SearchParams) -> dict:
        # Copy facets and remove them one by one
        if params.facets:
            if isinstance(params.facets, list):
                facets = params.facets.copy()
            else:
                facets = [params.facets]
        else:
            facets = []
        if params.numericRefinements:
            refinements = list(params.numericRefinements.keys())
        else:
            refinements = []
        aggs_dict = defaultdict(dict)
        for facet_attr in self.facet_attributes:
            try:
                facet_type = facet_attr['type']
                if facet_type == 'numeric-refinement':
                    refinements.remove(facet_attr["attribute"])
                else:
                    facets.remove(facet_attr["attribute"])
            except ValueError:
                continue
            self.add_aggregation(aggs_dict, facet_attr, facet_type)

        if facets:
            raise HTTPException(
                status_code=422,
                detail=f"Request for undefined facet(s): {facets}")
        return aggs_dict

    def add_aggregation(
            self, aggs: dict, facet_attr: dict, facet_type: str):
        path_segments = facet_attr.get("nested_paths", []).copy()
        path_segments.append(facet_attr["field"])
        level = 0
        while level < len(path_segments) - 1:
            key = path_segments[level]
            if not key in aggs:
                aggs[key] = {
                    'nested': {'path': '.'.join(path_segments[:level+1])},
                    'aggs': defaultdict(dict),
                }
            elif not 'aggs' in aggs[key]:
                raise HTTPException(
                    status_code=422,
                    detail=f"Collision between nested aggregation at"
                    f" {'.'.join(path_segments)} and another at"
                    f" {'.'.join(path_segments[:level+1])}: {aggs[key]}")
            aggs = aggs[key]['aggs']
            level += 1

        agg_spec = {'field': '.'.join(path_segments)}
        if facet_type == 'numeric-refinement':
            agg_type = 'histogram'
            agg_spec.update({
                "interval": 1,
                "min_doc_count": 1,
                "order": {"_key": "desc"},
            })
        else:
            agg_type = "terms"
        aggs[path_segments[-1]] = {agg_type: agg_spec}

    def transform_es_response(
            self, response: dict, request: SearchRequest) -> dict:
        """Return Algolia like response

        https://www.algolia.com/doc/api-reference/api-methods/search/

        """
        params = request.params
        hits = self.transform_hits(response['hits']['hits'], params)
        total_hits = response['hits']['total']['value']
        facets = self.transform_facets(response['aggregations'])

        # Handle case where hitsPerPage is 0
        hits_per_page = max(1, params.hitsPerPage)
        nb_pages = (total_hits + hits_per_page - 1) // hits_per_page
        return {
            "index": request.indexName,
            "hits": hits,
            "facets": facets,
            "facets_stats": {},
            "page": params.page,
            "nbPages": nb_pages,
            "nbHits": total_hits,
            "appliedRules": [],
            # "exhaustiveNbHits": True,
            # "exhaustiveFacetsCount": True,
            # "exhaustiveTypo": True,
            "exhaustive": {
                "facetsCount": True,
                "nbHits": True,
                "typo": True
            },
            "hitsPerPage": params.hitsPerPage,
            "processingTimeMS": response['took'],
            "query": params.query,
            "params": parse.urlencode(params.model_dump()),
            "renderingContent": self.renderingContent,
        }

    def transform_hits(self, hits: list[dict], params: SearchParams) -> dict:
        """Make hits interpretable for instantsearch.

        See the following reference for API specifications with regard
        to highlighting:
        https://www.algolia.com/doc/api-reference/api-parameters/attributesToHighlight/

        """
        pre_pattern = re.escape(params.highlightPreTag)
        post_pattern = re.escape(params.highlightPostTag)
        nb_query_words = len(params.query.split())
        result = []
        for hit in hits:
            t_hit = {
                'objectID': hit['_id'],
                '_index': hit['_index'],
                '_score': hit['_score'],
            }
            t_hit.update(hit['_source'])
            if hit.get('highlight'):
                for field, values in hit['highlight'].items():
                    subdict = t_hit.setdefault('_highlightResult', {})
                    path = field.split('.')
                    for name in path[:-1]:
                        subdict = subdict.setdefault(name, {})
                    value_list = subdict[path[-1]] = []
                    for value in values:
                        matched_words = re.findall(
                            f"{pre_pattern}(.*?){post_pattern}", value)
                        if len(matched_words) == nb_query_words:
                            match_level = 'full'
                        elif not matched_words:
                            match_level = 'none'
                        else:
                            match_level = 'partial'
                        fully_highlighted = all([
                            w.startswith(params.highlightPreTag)
                            and w.endswith(params.highlightPostTag)
                            for w in value.split()])
                        value_list.append({
                            'value': value,
                            'matchedWords': matched_words,
                            'matchLevel': match_level,
                            'fullyHighlighted': fully_highlighted,
                        })
            result.append(t_hit)
        return result

    def transform_facets(self, es_aggregations: dict) -> dict:
        facets = {}
        nested_path = None
        return self._transform_facets(es_aggregations, facets, nested_path)

    def _transform_facets(self, es_aggregations, facets, nested_path):
        for name, agg in es_aggregations.items():
            if not isinstance(agg, dict):
                continue
            if nested_path:
                field = f"{nested_path}.{name}"
            else:
                field = name
            try:
                buckets = agg['buckets']
            except KeyError:
                self._transform_facets(
                    agg, facets, field)
            else:
                attr_name = self.facet_by_path[field]['attribute']
                if attr_name == 'production_in_year':
                    get_key = lambda x: int(x['key'])
                else:
                    get_key = lambda x: x['key']
                facets[attr_name] = {
                    get_key(b): b['doc_count'] for b in buckets}
        return facets


process_search_request = SearchAdapter()
