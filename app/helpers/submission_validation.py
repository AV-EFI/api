"""Validate submitted records with the packaged AVefi validator."""

from functools import lru_cache
import logging

from avefi_schema import model_pydantic_v2 as efi
from avefi_validate import (
    REPORT_CONTRACT_VERSION,
    CheckResult,
    get_schema_validator,
    pass_checks,
    schema_fingerprint,
)

from app.core.config import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _validator():
    """Return the packaged schema validator, built once per process."""
    return get_schema_validator()


@lru_cache(maxsize=1)
def validation_fingerprint() -> dict:
    """Return the validator and schema identity recorded on jobs."""
    return {
        **schema_fingerprint(),
        "report_contract": REPORT_CONTRACT_VERSION,
    }


def check_records(
    records: list[efi.MovingImageRecord],
) -> CheckResult:
    """Run the full submission rules against already-parsed records."""
    return pass_checks(
        records,
        _validator(),
        placeholder_issuer_id=settings.SUBMISSION_PLACEHOLDER_ISSUER_ID,
    )


def invalid_envelope(result: CheckResult) -> dict:
    """Return the 422 body for records the validator rejected."""
    limit = settings.SUBMISSION_VALIDATION_MAX_DIAGNOSTICS
    diagnostics = [diagnostic.to_dict() for diagnostic in result.diagnostics]
    return {
        "detail": "Submission contains invalid AVefi records",
        "invalid": result.invalid,
        "dependants": result.dependants,
        "truncated": len(diagnostics) > limit,
        "validator": validation_fingerprint(),
        "diagnostics": diagnostics[:limit],
    }


def decode_envelope() -> dict:
    """Return the 422 body for a payload that is not AVefi JSON."""
    return {
        "detail": "Invalid AVefi records",
        "invalid": 0,
        "dependants": 0,
        "truncated": False,
        "validator": validation_fingerprint(),
        "diagnostics": [],
    }
