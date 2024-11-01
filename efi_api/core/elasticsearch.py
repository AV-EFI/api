from elasticsearch import Elasticsearch
from .config import settings

def get_elasticsearch_client() -> Elasticsearch:
    """
    Create and return Elasticsearch client instance
    """
    return Elasticsearch([{
        'host': settings.ES_HOST,
        'port': settings.ES_PORT,
        'scheme': settings.ES_SCHEME
    }])

# Initialize Elasticsearch client
es_client = get_elasticsearch_client()
