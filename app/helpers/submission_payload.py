from avefi_schema import model_pydantic_v2 as efi


def decode_payload(data) -> list[efi.MovingImageRecord]:
    """Validate submitted JSON and return the contained records."""
    if isinstance(data, list):
        return list(efi.MovingImageRecords.model_validate(data).root)
    return [efi.MovingImageRecordTypeAdapter.validate_python(data)]


def record_count(data) -> int:
    """Validate submitted JSON and return the number of records."""
    return len(decode_payload(data))
