"""Tests for class block detection helper."""

from datetime import UTC, datetime, timedelta

from custom_components.wodify.coordinator import detect_class_blocks


def _class(start: datetime, duration_minutes: int = 60, **extra):
    end = start + timedelta(minutes=duration_minutes)
    base = {"start": start, "end": end}
    base.update(extra)
    return base


def test_adjacent_classes_grouped():
    """Classes back-to-back should be grouped into a single block."""

    start = datetime(2024, 1, 1, 9, 0, 0, tzinfo=UTC)
    classes = [
        _class(start, id=1),
        _class(start + timedelta(minutes=60), id=2),
        _class(start + timedelta(minutes=120 + 5), id=3),
    ]

    blocks = detect_class_blocks(classes)

    assert len(blocks) == 1
    assert [cls["id"] for cls in blocks[0]] == [1, 2, 3]


def test_gap_threshold_boundary():
    """Gaps under the threshold stay grouped; over the threshold split blocks."""

    start = datetime(2024, 1, 1, 6, 0, 0, tzinfo=UTC)
    under_gap = _class(start, id="under")
    under_gap_next = _class(start + timedelta(minutes=60 + 29), id="still")
    over_gap = _class(start + timedelta(minutes=60 + 31), id="split")

    blocks = detect_class_blocks([under_gap, under_gap_next, over_gap])

    assert len(blocks) == 2
    assert [cls["id"] for cls in blocks[0]] == ["under", "still"]
    assert [cls["id"] for cls in blocks[1]] == ["split"]


def test_empty_input_returns_empty_list():
    """Empty input should return an empty list of blocks."""

    assert detect_class_blocks([]) == []


def test_blocks_sorted_and_cancelled_removed():
    """Inputs are sorted and cancelled classes are excluded from blocks."""

    start = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)
    classes = [
        _class(start + timedelta(minutes=90), id="later", is_cancelled=False),
        _class(start, id="first", is_cancelled=False),
        _class(start + timedelta(minutes=45), id="cancelled", is_cancelled=True),
    ]

    blocks = detect_class_blocks(classes)

    assert len(blocks) == 1
    assert [cls["id"] for cls in blocks[0]] == ["first", "later"]


def _cls(start_min: int, end_min: int) -> dict:
    """Minimal class dict anchored to a fixed day."""
    base = datetime(2026, 8, 7, 6, 0)
    return {
        "start": base + timedelta(minutes=start_min),
        "end": base + timedelta(minutes=end_min),
        "is_cancelled": False,
    }


def test_gap_threshold_defaults_to_thirty_minutes():
    """A 30-minute gap merges, 31 splits — the documented boundary."""
    merged = detect_class_blocks([_cls(0, 60), _cls(90, 150)])
    assert len(merged) == 1

    split = detect_class_blocks([_cls(0, 60), _cls(91, 151)])
    assert len(split) == 2


def test_gap_threshold_is_configurable():
    """A gap that splits at the default must merge under a wider threshold."""
    classes = [_cls(0, 60), _cls(95, 155)]  # 35-minute gap

    assert len(detect_class_blocks(classes)) == 2
    assert len(detect_class_blocks(classes, 45)) == 1
    assert len(detect_class_blocks(classes, gap_threshold=45)) == 1


def test_gap_threshold_applies_to_overlaps_too():
    """The threshold is symmetric: large overlaps split as well."""
    # Sorted by start, so the gap is measured from the first class's end
    # (+60) to the second's start (+10) = -50 minutes of overlap.
    overlapping = [_cls(0, 60), _cls(10, 200)]
    assert len(detect_class_blocks(overlapping, 30)) == 2
    assert len(detect_class_blocks(overlapping, 60)) == 1
