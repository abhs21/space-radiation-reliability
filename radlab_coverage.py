"""Audit one RadLab dose-rate series and run a bounded masking demonstration.

This computes a numerical integral of *reported rates*. It does not infer
unobserved radiation dose or validate an instrument's interval semantics.
"""

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import median
from timestamp_utils import format_timestamp, parse_timestamp


SOURCE_URL = (
    "https://visualization.osdr.nasa.gov/radlab/api/"
    "?instrument_id=DosTel2&timestamp%3E=2022-04-01T00%3A00"
    "&timestamp%3C2022-04-02T00%3A00&absorbed_dose_rate&format=csv"
)


def quantile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile requires at least one value")
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def load_series(path, expected_id, with_timezone=False):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "instrument_id", "absorbed_dose_rate"}
        if (not reader.fieldnames or not required.issubset(reader.fieldnames)
                or len(reader.fieldnames) != len(set(reader.fieldnames))):
            raise ValueError(f"CSV must contain {sorted(required)}")
        rows = []
        conventions = set()
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"line {line_number}: malformed row")
            if row["instrument_id"] != expected_id:
                raise ValueError(f"line {line_number}: unexpected instrument ID")
            try:
                timestamp, aware = parse_timestamp(row["timestamp"], allow_minutes=True)
                rate = float(row["absorbed_dose_rate"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {line_number}: invalid timestamp or rate") from exc
            conventions.add(aware)
            if len(conventions) > 1:
                raise ValueError("mixed timezone conventions")
            if not math.isfinite(rate) or rate < 0:
                raise ValueError(f"line {line_number}: rate must be finite and nonnegative")
            rows.append((timestamp, rate))
    rows.sort()
    if len(rows) < 3:
        raise ValueError("at least three readings are required")
    duplicate_count = sum(a[0] == b[0] for a, b in zip(rows, rows[1:]))
    if duplicate_count:
        raise ValueError(
            f"{duplicate_count} duplicate timestamps; resolve before integrating"
        )
    return (rows, conventions == {True}) if with_timezone else rows


def trapezoid_area(rows):
    """Integrate μGy/hour rates over reported timestamps, yielding μGy."""
    return math.fsum(
        elapsed_seconds(left[0], right[0])
        / 3600
        * (left[1] + right[1])
        / 2
        for left, right in zip(rows, rows[1:])
    )


def error_percent(reference, estimate):
    return 100 * (estimate / reference - 1)


def summarize_cases(cases):
    if not cases:
        return {"cases": 0, "median_absolute_error_percent": None,
                "p95_absolute_error_percent": None,
                "max_absolute_error_percent": None, "worst_case": None}
    errors = [abs(case["error_percent"]) for case in cases]
    worst = max(cases, key=lambda case: abs(case["error_percent"]))
    return {
        "cases": len(cases),
        "median_absolute_error_percent": quantile(errors, 0.5),
        "p95_absolute_error_percent": quantile(errors, 0.95),
        "max_absolute_error_percent": max(errors),
        "worst_case": worst,
    }


def elapsed_seconds(left, right):
    difference = right - left
    return difference.total_seconds() if isinstance(left, datetime) else float(difference)


def block_cases(rows, minutes, phase=0, aware=False):
    cases = []
    start = rows[0][0] + (30 + phase) * 60
    latest_start = rows[-1][0] - (minutes + 30) * 60
    reference = trapezoid_area(rows)
    while start <= latest_start:
        end = start + minutes * 60
        retained = [row for row in rows if row[0] < start or row[0] >= end]
        removed = len(rows) - len(retained)
        cases.append({
            'start': format_timestamp(start, aware),
            'removed_readings': removed,
            'error_percent': error_percent(reference, trapezoid_area(retained)),
        })
        start += 30 * 60
    return cases


def audit(rows, instrument_id, aware=False, phase_offsets=None):
    if rows and isinstance(rows[0][0], datetime):
        conventions = {stamp.utcoffset() is not None for stamp, _ in rows}
        if len(conventions) > 1:
            raise ValueError('mixed timezone conventions')
        aware = conventions == {True}
        rows = [(parse_timestamp(stamp.isoformat())[0], rate) for stamp, rate in rows]
    if len(rows) < 3:
        raise ValueError('at least three readings are required')
    if any(right[0] <= left[0] for left, right in zip(rows, rows[1:])):
        raise ValueError('timestamps must be strictly increasing')
    if any(not math.isfinite(rate) or rate < 0 for _, rate in rows):
        raise ValueError('rates must be finite and nonnegative')
    timestamps = [timestamp for timestamp, _ in rows]
    rates = [rate for _, rate in rows]
    intervals = [
        float(right - left)
        for left, right in zip(timestamps, timestamps[1:])
    ]
    reference = trapezoid_area(rows)
    if reference <= 0:
        raise ValueError("a positive reference area is required")

    thinning = {}
    for stride in (2, 5, 10):
        retained = [
            row for index, row in enumerate(rows)
            if index % stride == 0 or index == len(rows) - 1
        ]
        thinning[str(stride)] = {
            "retained_readings": len(retained),
            "error_percent": error_percent(reference, trapezoid_area(retained)),
        }

    blocks = {}
    for minutes in (5, 15, 30):
        cases = [case for case in block_cases(rows, minutes, aware=aware) if case['removed_readings']]
        blocks[str(minutes)] = summarize_cases(cases)

    result = {
        "instrument_id": instrument_id,
        "rate_unit": "microgray/hour",
        "timestamp_timezone": "explicit_offsets_normalized_to_utc" if aware else "not supplied by API output",
        "reading_count": len(rows),
        "first_timestamp": format_timestamp(timestamps[0], aware),
        "last_timestamp": format_timestamp(timestamps[-1], aware),
        "inter_record_seconds": {
            "min": min(intervals),
            "median": median(intervals),
            "p95": quantile(intervals, 0.95),
            "max": max(intervals),
        },
        "rate_microgray_per_hour": {
            "min": min(rates),
            "median": median(rates),
            "p95": quantile(rates, 0.95),
            "max": max(rates),
        },
        "reported_series_trapezoid_microgray": reference,
        "stride_masking": thinning,
        "block_masking_minutes": blocks,
    }
    if phase_offsets is not None:
        result['phase_masking'] = {}
        for phase in phase_offsets:
            if isinstance(phase, bool) or not isinstance(phase, int) or not 0 <= phase < 30:
                raise ValueError('phase offsets must be integer minutes from 0 to 29')
            result['phase_masking'][str(phase)] = {}
            for minutes in (5, 15, 30):
                cases = block_cases(rows, minutes, phase, aware)
                tested = [case for case in cases if case['removed_readings']]
                result['phase_masking'][str(phase)][str(minutes)] = {
                    'summary': summarize_cases(tested),
                    'empty_blocks': len(cases) - len(tested),
                    'all_cases': cases,
                }
    return result
