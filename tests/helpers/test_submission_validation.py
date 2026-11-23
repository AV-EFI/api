"""Intake validation with the packaged AVefi validator."""

from unittest.mock import patch

from app.core.config import settings
from app.helpers.submission_payload import decode_payload
from app.helpers.submission_validation import (
    check_records,
    decode_envelope,
    invalid_envelope,
    validation_fingerprint,
)


def _local(identifier):
    return {"category": "avefi:LocalResource", "id": identifier}


def _hierarchy():
    return [
        {
            "category": "avefi:WorkVariant",
            "type": "Monographic",
            "has_primary_title": {
                "type": "PreferredTitle",
                "has_name": "Test",
            },
            "has_identifier": [_local("w1")],
        },
        {
            "category": "avefi:Manifestation",
            "has_primary_title": {
                "type": "TitleProper",
                "has_name": "Test",
            },
            "has_identifier": [_local("m1")],
            "is_manifestation_of": [_local("w1")],
        },
        {
            "category": "avefi:Item",
            "has_primary_title": {
                "type": "TitleProper",
                "has_name": "Test",
            },
            "has_identifier": [_local("i1")],
            "is_item_of": _local("m1"),
        },
    ]


def _cycle():
    return [
        {
            "category": "avefi:WorkVariant",
            "type": "Analytic",
            "has_primary_title": {
                "type": "PreferredTitle",
                "has_name": "One",
            },
            "has_identifier": [_local("w1")],
            "is_part_of": [_local("w2")],
        },
        {
            "category": "avefi:WorkVariant",
            "type": "Analytic",
            "has_primary_title": {
                "type": "PreferredTitle",
                "has_name": "Two",
            },
            "has_identifier": [_local("w2")],
            "is_part_of": [_local("w1")],
        },
    ]


def test_fingerprint_names_the_validator_and_schema():
    fingerprint = validation_fingerprint()

    assert fingerprint["package"] == "0.5.0"
    assert fingerprint["version"] == "2.0"
    assert fingerprint["report_contract"] == "1.1"
    assert len(fingerprint["sha256"]) == 64
    assert validation_fingerprint() is fingerprint


def test_a_complete_hierarchy_passes():
    assert check_records(decode_payload(_hierarchy())).passed


def test_a_reference_cycle_is_reported():
    result = check_records(decode_payload(_cycle()))

    assert not result.passed
    assert result.invalid == 2
    assert {str(diagnostic.code) for diagnostic in result.diagnostics} == {
        "reference.cycle"
    }


def test_invalid_envelope_carries_the_counts_and_fingerprint():
    envelope = invalid_envelope(check_records(decode_payload(_cycle())))

    assert envelope["detail"] == ("Submission contains invalid AVefi records")
    assert envelope["invalid"] == 2
    assert envelope["dependants"] == 0
    assert envelope["truncated"] is False
    assert envelope["validator"] == validation_fingerprint()
    assert len(envelope["diagnostics"]) == 2


def test_invalid_envelope_truncates_diagnostics():
    result = check_records(decode_payload(_cycle()))
    with patch.object(settings, "SUBMISSION_VALIDATION_MAX_DIAGNOSTICS", 1):
        envelope = invalid_envelope(result)

    assert envelope["truncated"] is True
    assert len(envelope["diagnostics"]) == 1


def test_decode_envelope_has_no_diagnostics():
    envelope = decode_envelope()

    assert envelope["detail"] == "Invalid AVefi records"
    assert envelope["invalid"] == 0
    assert envelope["dependants"] == 0
    assert envelope["truncated"] is False
    assert envelope["diagnostics"] == []
