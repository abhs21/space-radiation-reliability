"""Audit one RadLab dose-rate series and run a bounded masking demonstration.

This computes a numerical integral of *reported rates*. It does not infer
unobserved radiation dose or validate an instrument's interval semantics.
"""

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median


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


def load_series(path, expected_id):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "instrument_id", "absorbed_dose_rate"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain {sorted(required)}")
        rows = []
        for line_number, row in enumerate(reader, start=2):
            if row["instrument_id"] != expected_id:
                raise ValueError(f"line {line_number}: unexpected instrument ID")
            try:
                timestamp = datetime.fromisoformat(row["timestamp"])
                rate = float(row["absorbed_dose_rate"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"line {line_number}: invalid timestamp or rate") from exc
            if timestamp.tzinfo is not None:
                raise ValueError("mixed or explicit time zones need a separate policy")
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
    return rows


def trapezoid_area(rows):
    """Integrate μGy/hour rates over reported timestamps, yielding μGy."""
    return sum(
        (right[0] - left[0]).total_seconds()
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


def audit(rows, instrument_id):
    timestamps = [timestamp for timestamp, _ in rows]
    rates = [rate for _, rate in rows]
    intervals = [
        (right - left).total_seconds()
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
        cases = []
        start = timestamps[0] + timedelta(minutes=30)
        latest_start = timestamps[-1] - timedelta(minutes=minutes + 30)
        while start <= latest_start:
            end = start + timedelta(minutes=minutes)
            retained = [
                row for row in rows
                if row[0] < start or row[0] >= end
            ]
            removed = len(rows) - len(retained)
            if removed:
                cases.append({
                    "start": start.isoformat(),
                    "removed_readings": removed,
                    "error_percent": error_percent(
                        reference, trapezoid_area(retained)
                    ),
                })
            start += timedelta(minutes=30)
        blocks[str(minutes)] = summarize_cases(cases)

    return {
        "instrument_id": instrument_id,
        "rate_unit": "microgray/hour",
        "timestamp_timezone": "not supplied by API output",
        "reading_count": len(rows),
        "first_timestamp": timestamps[0].isoformat(),
        "last_timestamp": timestamps[-1].isoformat(),
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
