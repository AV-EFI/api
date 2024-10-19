from fastapi import APIRouter, HTTPException
from app.core.elasticsearch import es_client
from app.schemas.search import SearchRequest,SearchResponse
from app.core.config import settings

router = APIRouter()

@router.post("/search/similar_works", response_model=SearchResponse)
async def find_similar_works(request: SearchRequest):
    """
    Search for similar works based on title, date, and/or director.
    Returns matching works and similarity indicators.
    """
    try:
        # Build the query
        must_clauses = []
        
        if request.title:
            must_clauses.append({
                "match": {
                    "has_record.has_primary_title.has_name": request.title
                }
            })
        
        if request.date:
            must_clauses.append({
                "term": {
                    "has_record.has_event.has_date.keyword": request.date
                }
            })
            
        if request.director:
            must_clauses.append({
                "nested": {
                    "path": "has_record.has_event",
                    "query": {
                        "nested": {
                            "path": "has_record.has_event.has_activity",
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "term": {
                                                "has_record.has_event.has_activity.category.keyword": "avefi:DirectingActivity"
                                            }
                                        },
                                        {
                                            "nested": {
                                                "path": "has_record.has_event.has_activity.has_agent",
                                                "query": {
                                                    "match": {
                                                        "has_record.has_event.has_activity.has_agent.has_name": request.director
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            })

        # Execute search
        query = {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            }
        }

        response = es_client.search(
            index=settings.ES_INDEX,
            body=query,
            size=10  # Limit results
        )

        # Process results
        hits = response['hits']['hits']
        
        # print(hits)
        total_matches = response['hits']['total']['value']
        print(total_matches)
        
        # Extract relevant information from matches
        similar_works = []
        for hit in hits:
            source = hit['_source']
            work = {
                'handle': source['handle'],
                'title': source['has_record']['has_primary_title']['has_name'],
                'score': hit['_score']
            }
            
            # Extract date if available
            if 'has_event' in source['has_record'] and source['has_record']['has_event']:
                work['date'] = source['has_record']['has_event'][0].get('has_date')

            similar_works.append(work)

        # Create matching criteria indicators
        matching_criteria = {
            "title_match": any(hit['_score'] > 1.0 for hit in hits) if request.title else None,
            "date_match": any(
                hit['_source']['has_record']['has_event'][0].get('has_date') == request.date 
                for hit in hits
            ) if request.date else None,
            "director_match": any(
                any(
                    activity.get('category') == 'avefi:DirectingActivity' 
                    for activity in event.get('has_activity', [])
                )
                for hit in hits
                for event in hit['_source']['has_record'].get('has_event', [])
            ) if request.director else None
        }

        return SearchResponse(
            matches_found=total_matches,
            similar_works=similar_works,
            matching_criteria=matching_criteria
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

