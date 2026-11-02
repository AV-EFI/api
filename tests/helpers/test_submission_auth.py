from unittest.mock import MagicMock, patch

from elasticsearch.exceptions import ConnectionError as ESConnectionError
from httpx2 import HTTPStatusError, Request, Response
import pytest

from app.helpers.submission_auth import (
    ISIL_CATEGORY,
    ISSUER_CATEGORY_FIELD,
    ISSUER_ID_FIELD,
    ISSUER_NAME_FIELD,
    ISSUER_SAME_AS_FIELD,
    InvalidSubmissionCredentials,
    SubmissionAuthUnavailable,
    lookup_submission_identity,
    resolve_submission_identity,
)


def _hit(**source):
    return {"_source": source}


def _source():
    return {
        "handle": "21.11155/SDK",
        ISSUER_NAME_FIELD: (
            "Stiftung Deutsche Kinemathek - Museum für Film und Fernsehen"
        ),
        ISSUER_SAME_AS_FIELD: {
            ISSUER_CATEGORY_FIELD: ISIL_CATEGORY,
            ISSUER_ID_FIELD: "DE-MUS-407010",
        },
    }


def test_lookup_uses_primary_index_exact_query_and_restricted_fields():
    client = MagicMock()
    client.search.return_value = {"hits": {"hits": [_hit(**_source())]}}

    provider_handle, source = lookup_submission_identity("SDK", client=client)

    assert provider_handle == "21.11155/SDK"
    assert source == _source()
    client.search.assert_called_once_with(
        index="21.11155",
        body={
            "size": 2,
            "_source": ["handle", ISSUER_NAME_FIELD, ISSUER_SAME_AS_FIELD],
            "query": {"term": {"handle.keyword": "SDK"}},
        },
    )


def test_lookup_rejects_unknown_username_as_invalid_credentials():
    client = MagicMock()
    client.search.return_value = {"hits": {"hits": []}}

    with pytest.raises(InvalidSubmissionCredentials):
        lookup_submission_identity("unknown", client=client)


def test_lookup_rejects_duplicate_username_as_unavailable():
    client = MagicMock()
    client.search.return_value = {
        "hits": {"hits": [_hit(**_source()), _hit(**_source())]}
    }

    with pytest.raises(SubmissionAuthUnavailable):
        lookup_submission_identity("SDK", client=client)


def test_lookup_rejects_missing_required_same_as():
    client = MagicMock()
    source = _source()
    del source[ISSUER_SAME_AS_FIELD]
    client.search.return_value = {"hits": {"hits": [_hit(**source)]}}

    with pytest.raises(SubmissionAuthUnavailable):
        lookup_submission_identity("SDK", client=client)


def test_lookup_rejects_missing_issuer_category():
    client = MagicMock()
    source = _source()
    del source[ISSUER_SAME_AS_FIELD][ISSUER_CATEGORY_FIELD]
    client.search.return_value = {"hits": {"hits": [_hit(**source)]}}

    with pytest.raises(SubmissionAuthUnavailable):
        lookup_submission_identity("SDK", client=client)


def test_lookup_rejects_unsupported_issuer_category():
    client = MagicMock()
    source = _source()
    source[ISSUER_SAME_AS_FIELD][ISSUER_CATEGORY_FIELD] = "other:Resource"
    client.search.return_value = {"hits": {"hits": [_hit(**source)]}}

    with pytest.raises(SubmissionAuthUnavailable):
        lookup_submission_identity("SDK", client=client)


def test_lookup_maps_elasticsearch_failure_to_unavailable():
    client = MagicMock()
    client.search.side_effect = ESConnectionError("connection failed")

    with pytest.raises(SubmissionAuthUnavailable):
        lookup_submission_identity("SDK", client=client)


def test_resolve_authenticates_derived_handle_and_returns_profile():
    elasticsearch_client = MagicMock()
    elasticsearch_client.search.return_value = {
        "hits": {"hits": [_hit(**_source())]}
    }
    api = MagicMock()

    with (
        patch(
            "app.helpers.submission_auth.create_user_client", return_value=api
        ) as create_client,
        patch(
            "app.helpers.submission_auth.get_handle_base_url",
            return_value="https://handles.example/",
        ),
    ):
        identity = resolve_submission_identity(
            "SDK",
            "client-password",
            elasticsearch_client=elasticsearch_client,
        )

    create_client.assert_called_once_with(
        profile={
            "has_issuer_name": (
                "Stiftung Deutsche Kinemathek - Museum für Film und Fernsehen"
            ),
            "has_issuer_id": "https://w3id.org/isil/DE-MUS-407010",
        },
        prefix="21.11155",
        username="SDK",
        password="client-password",
        base_url="https://handles.example/",
    )
    api.get.assert_called_once_with("21.11155/SDK")
    api.close.assert_called_once_with()
    assert identity.submitter_principal == "SDK"
    assert identity.authentication_method == "basic"
    assert identity.provider_handle == "21.11155/SDK"
    assert identity.prefix == "21.11155"


@pytest.mark.parametrize("status_code", [401, 403])
def test_resolve_maps_handle_auth_failure_to_invalid_credentials(status_code):
    elasticsearch_client = MagicMock()
    elasticsearch_client.search.return_value = {
        "hits": {"hits": [_hit(**_source())]}
    }
    api = MagicMock()
    request = Request("GET", "https://handles.example/21.11155/SDK")
    api.get.side_effect = HTTPStatusError(
        "authentication failed",
        request=request,
        response=Response(status_code, request=request),
    )

    with (
        patch(
            "app.helpers.submission_auth.create_user_client", return_value=api
        ),
        patch(
            "app.helpers.submission_auth.get_handle_base_url",
            return_value="https://handles.example/",
        ),
        pytest.raises(InvalidSubmissionCredentials),
    ):
        resolve_submission_identity(
            "SDK",
            "wrong-password",
            elasticsearch_client=elasticsearch_client,
        )

    api.close.assert_called_once_with()


def test_resolve_maps_handle_server_failure_to_unavailable():
    elasticsearch_client = MagicMock()
    elasticsearch_client.search.return_value = {
        "hits": {"hits": [_hit(**_source())]}
    }
    api = MagicMock()
    request = Request("GET", "https://handles.example/21.11155/SDK")
    api.get.side_effect = HTTPStatusError(
        "server failed",
        request=request,
        response=Response(503, request=request),
    )

    with (
        patch(
            "app.helpers.submission_auth.create_user_client", return_value=api
        ),
        patch(
            "app.helpers.submission_auth.get_handle_base_url",
            return_value="https://handles.example/",
        ),
        pytest.raises(SubmissionAuthUnavailable),
    ):
        resolve_submission_identity(
            "SDK",
            "client-password",
            elasticsearch_client=elasticsearch_client,
        )

    api.close.assert_called_once_with()
