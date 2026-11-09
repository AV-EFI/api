from avefi_schema import model_pydantic_v2 as efi
from pydantic import ValidationError
import pytest

from app.helpers.submission_payload import decode_payload, record_count


def _work_variant() -> dict:
    return {
        "category": "avefi:WorkVariant",
        "has_primary_title": {
            "has_name": "Test",
            "type": "PreferredTitle",
        },
        "type": "Monographic",
    }


def test_single_object_is_decoded_as_one_record():
    records = decode_payload(_work_variant())

    assert len(records) == 1
    assert isinstance(records[0], efi.WorkVariant)
    assert record_count(_work_variant()) == 1


def test_array_is_decoded_as_records():
    records = decode_payload([_work_variant(), _work_variant()])

    assert len(records) == 2
    assert all(isinstance(record, efi.WorkVariant) for record in records)
    assert record_count([_work_variant()]) == 1


def test_invalid_payload_raises_validation_error():
    with pytest.raises(ValidationError):
        decode_payload({"category": "avefi:WorkVariant"})
