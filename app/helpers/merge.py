# ruff: noqa
import logging
import re

from ..schemas.efi_schema import efi

logger = logging.getLogger(__name__)


class MergeError(ValueError):
    pass


def merge(work1: efi.WorkVariant, work2: efi.WorkVariant) -> efi.WorkVariant:
    """Return a record created by merging ``work2`` into ``work1``."""
    if work1.type != work2.type or work1.variant_type != work2.variant_type:
        raise MergeError()
    result = work1.model_copy(deep=True)
    process_titles(result, work2)
    for event in work2.has_event:
        incorporate_event(result.has_event, event)
    # other_fields_set = work2.model_fields_set
    return result


def process_titles(work1: efi.WorkVariant, work2: efi.WorkVariant):
    def _merge_alternative_title(titles, other_title):
        if other_title.type == "PreferredTitle":
            other_title.type = efi.TitleTypeEnum("AlternativeTitle")
        last_same_type = None
        for i, title in enumerate(titles):
            if title.type != other_title.type:
                continue
            last_same_type = i
            pick = compare_and_pick(title.has_name, other_title.has_name)
            if pick < 0:
                return
            elif pick > 0:
                title.has_name = other_title.has_name
                title.has_ordering_name = other_title.has_ordering_name
                return
        if last_same_type is not None:
            titles.insert(last_same_type + 1, other_title)
        else:
            titles.append(other_title)

    # Handle primary title first
    pick = compare_and_pick(
        work1.has_primary_title.has_name, work2.has_primary_title.has_name
    )
    if pick:
        if pick > 1:
            work1.has_primary_title.has_name = work2.has_primary_title.has_name
            work1.has_primary_title.has_ordering_name = (
                work2.has_primary_title.has_ordering_name
            )
        if (
            work1.has_primary_title.type != "PreferredTitle"
            and work2.has_primary_title.type == "PreferredTitle"
        ):
            work1.has_primary_title.type = work2.has_primary_title.type
    else:
        if (
            work1.has_primary_title.type == "PreferredTitle"
            or work2.has_primary_title.type != "PreferredTitle"
        ):
            _merge_alternative_title(
                work1.has_alternative_title, work2.has_primary_title
            )
        else:
            _merge_alternative_title(
                work1.has_alternative_title, work1.has_primary_title
            )
            work1.has_primary_title = work2.has_primary_title

    # Handle alternative titles
    for title in work2.has_alternative_title:
        _merge_alternative_title(work1.has_alternative_title, title)


def compare_and_pick(a: str, b: str) -> int:
    """Decide whether one of two strings can replace the other.

    Compare two strings and if their casefolded versions coincide,
    indicate whether ``a`` should replace ``b`` or the other way
    around. The algorithm is designed to favour ``a`` over ``b``
    except when ``b`` is a mixed case string and ``a`` is not.

    Returns
    -------
    int
        -1 for ``a``, 1 for ``b``, and 0 if none should replace the
        other.

    """
    if a == b:
        return -1
    if a.casefold() == b.casefold():
        if b.isupper() or b.islower():
            return -1
        elif a.isupper() or a.islower():
            return 1
        else:
            return -1
    return 0


def incorporate_event(events: list[efi.Event], other_event: efi.Event):
    same_type = same_category = None
    for i, event in enumerate(events):
        if event.category != other_event.category:
            continue
        same_category = i
        if event.type != other_event.type:
            continue
        same_type = i
        if events_merge(event, other_event):
            return
    if same_type is not None:
        ref_idx = same_type
    elif same_category is not None:
        ref_idx = same_category
    else:
        events.append(other_event)
        return
    events.insert(ref_idx + 1, other_event)


def events_merge(event: efi.Event, other_event: efi.Event) -> bool:
    """Check whether events can be merged and, if so, do it.

    Check whether ``event`` and ``other_event`` really should be
    merged and, if so, transform ``event`` accordingly.

    Assumptions: Both events are assumed to be of the same category
    and type (not checked again).

    Currently, only production events are actually merged.

    Returns
    -------
    bool
        True if merged, False otherwise.

    """
    if event == other_event:
        return True
    if event.category == "avefi:ProductionEvent":
        merged_date = merge_dates(event.has_date, other_event.has_date)
        event.has_date = merged_date


def merge_dates(date: str, other_date: str) -> str:
    if date == other_date:
        return date
    year_gte, year_gte_certainty, _, year_lte, year_lte_certainty = re.search(
        r"^([0-9]{4,})?([?~])?[-~?0-9]*(/([0-9]{4,})?([?~])?)?", date
    ).groups()
    if year_gte is None:
        raise ValueError(f"Cannot handle date string: {date}")
    (
        other_year_gte,
        other_year_gte_certainty,
        _,
        other_year_lte,
        other_year_lte_certainty,
    ) = re.search(
        r"^([0-9]{4,})?([?~])?[-~?0-9]*(/([0-9]{4,})?([?~])?)?", other_date
    ).groups()
    if other_year_gte is None:
        raise ValueError(f"Cannot handle date string: {other_date}")
    year_gte_int = int(year_gte)
