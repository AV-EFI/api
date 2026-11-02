from dataclasses import dataclass
import logging
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ApiError
from elasticsearch.exceptions import ConnectionError as ESConnectionError
from httpx2 import HTTPStatusError

from ..core.config import settings
from ..core.elasticsearch import es_client
from .epic_client import create_user_client

log = logging.getLogger(__name__)

ISSUER_NAME_FIELD = "21.11155/attributedefhasname"
ISSUER_SAME_AS_FIELD = "21.11155/attributedefsameas"
ISSUER_CATEGORY_FIELD = "21.11155/AttributeDefCategory"
ISSUER_ID_FIELD = "21.11155/AttributeDefId"
ISIL_CATEGORY = "avefi:ISILResource"


class SubmissionAuthError(Exception):
    """Base class for expected submission authentication failures."""


class InvalidSubmissionCredentials(SubmissionAuthError):
    """The supplied credentials do not identify or authenticate a user."""


class SubmissionAuthUnavailable(SubmissionAuthError):
    """An authorization dependency or its data is currently unavailable."""


@dataclass(frozen=True)
class SubmissionIdentity:
    """Authorized identity and immutable issuer data for one submission."""

    submitter_principal: str
    authentication_method: str
    provider_handle: str
    prefix: str
    profile: dict[str, str]


def lookup_submission_identity(
    username: str,
    *,
    client: Elasticsearch = es_client,
) -> tuple[str, dict[str, Any]]:
    """Look up the unique issuer Handle associated with ``username``."""
    query = {
        "size": 2,
        "_source": ["handle", ISSUER_NAME_FIELD, ISSUER_SAME_AS_FIELD],
        "query": {"term": {"handle.keyword": username}},
    }
    try:
        response = client.search(index=settings.ES_PRIMARY_INDEX, body=query)
    except (ESConnectionError, ApiError) as exc:
        log.warning("Submission identity lookup unavailable: %s", exc)
        raise SubmissionAuthUnavailable from exc
    except Exception as exc:
        log.exception("Unexpected submission identity lookup failure")
        raise SubmissionAuthUnavailable from exc

    hits = response.get("hits", {}).get("hits", [])
    if not hits:
        raise InvalidSubmissionCredentials
    if len(hits) != 1:
        log.error(
            "Expected one submission identity for username, got %s", len(hits)
        )
        raise SubmissionAuthUnavailable

    source = hits[0].get("_source", {})
    required_fields = ("handle", ISSUER_NAME_FIELD, ISSUER_SAME_AS_FIELD)
    if any(not source.get(field) for field in required_fields):
        log.error("Submission identity is missing required issuer fields")
        raise SubmissionAuthUnavailable
    same_as = source[ISSUER_SAME_AS_FIELD]
    if not isinstance(same_as, dict):
        log.error("Submission identity has invalid same-as data")
        raise SubmissionAuthUnavailable
    category = same_as.get(ISSUER_CATEGORY_FIELD)
    id_ = same_as.get(ISSUER_ID_FIELD)
    if category != ISIL_CATEGORY or not id_:
        log.error("Submission identity has unsupported issuer category")
        raise SubmissionAuthUnavailable
    return source["handle"], source


def resolve_submission_identity(
    username: str,
    password: str,
    *,
    elasticsearch_client: Elasticsearch = es_client,
    handle_base_url: str,
) -> SubmissionIdentity:
    """Resolve and authenticate a submission user.

    The supplied password is used only to construct the short-lived Handle
    client. It is not returned in the identity or persisted by this helper.
    """
    provider_handle, source = lookup_submission_identity(
        username, client=elasticsearch_client
    )
    prefix = provider_handle.split("/", maxsplit=1)[0]
    profile = {
        "has_issuer_name": source[ISSUER_NAME_FIELD],
        "has_issuer_id": (
            f"https://w3id.org/isil/"
            f"{source[ISSUER_SAME_AS_FIELD][ISSUER_ID_FIELD]}"
        ),
    }
    api = create_user_client(
        profile=profile,
        prefix=prefix,
        username=username,
        password=password,
        base_url=handle_base_url,
    )
    try:
        api.get(provider_handle)
    except HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code in (401, 403):
            raise InvalidSubmissionCredentials from exc
        log.warning("Handle authentication failed with HTTP %s", status_code)
        raise SubmissionAuthUnavailable from exc
    except Exception as exc:
        log.warning("Handle authentication unavailable: %s", exc)
        raise SubmissionAuthUnavailable from exc
    finally:
        api.close()

    return SubmissionIdentity(
        submitter_principal=username,
        authentication_method="basic",
        provider_handle=provider_handle,
        prefix=prefix,
        profile=profile,
    )
