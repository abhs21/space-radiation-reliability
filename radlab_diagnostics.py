"""Report RadLab CSV structure and timing without interpreting detector semantics."""
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import median

from radlab_coverage import audit as masking_audit
from timestamp_utils import format_timestamp, parse_timestamp, utc_day


def diagnose(path, instrument_id, day=None, source_url=None):
    path = Path(path)
    expected_day = date.fromisoformat(day) if day else None
    issues, readings, by_time = [], [], defaultdict(list)
    result = {
        'instrument_id': instrument_id, 'day': day, 'file': path.name,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_url': source_url, 'rate_unit': 'microgray/hour',
        'timestamp_semantics': 'Instrument interval semantics remain unresolved',
        'source_rows': 0, 'issues': issues,
    }
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        required = {'timestamp', 'instrument_id', 'absorbed_dose_rate'}
        if (not reader.fieldnames or not required.issubset(reader.fieldnames)
                or len(reader.fieldnames) != len(set(reader.fieldnames))):
            issues.append({'row': 1, 'kind': 'unexpected_schema'})
        else:
            for number, raw in enumerate(reader, 2):
                result['source_rows'] += 1
                if None in raw or any(v is None for v in raw.values()):
                    issues.append({'row': number, 'kind': 'malformed_row'})
                    continue
                if raw['instrument_id'] != instrument_id:
                    issues.append({'row': number, 'kind': 'unexpected_instrument'})
                    continue
                try:
                    normalized, aware = parse_timestamp(raw['timestamp'], allow_minutes=True)
                    rate = float(raw['absorbed_dose_rate'])
                    if not math.isfinite(rate) or rate < 0:
                        raise ValueError('invalid rate')
                except (ValueError, TypeError):
                    issues.append({'row': number, 'kind': 'invalid_timestamp_or_rate'})
                    continue
                if expected_day and utc_day(normalized) != expected_day:
                    issues.append({'row': number, 'kind': 'outside_requested_day'})
                readings.append((normalized, rate, number, aware))
                by_time[(aware, normalized)].append({'row': number, 'rate': rate})
    result['parsed_rows'] = len(readings)
    duplicate_groups = [
        {'timestamp': format_timestamp(stamp, aware), 'rows': rows,
         'distinct_rates': sorted({row['rate'] for row in rows}),
         'conflicting': len({row['rate'] for row in rows}) > 1}
        for (aware, stamp), rows in by_time.items() if len(rows) > 1
    ]
    result['duplicate_groups'] = duplicate_groups
    result['duplicate_timestamp_count'] = len(duplicate_groups)
    result['conflicting_timestamp_count'] = sum(g['conflicting'] for g in duplicate_groups)
    conventions = {r[3] for r in readings}
    result['timezone_convention'] = ('mixed' if len(conventions) > 1 else
                                     'explicit_offsets_normalized_to_utc' if conventions == {True} else
                                     'not_supplied' if conventions == {False} else 'no_valid_timestamps')
    result['spacing_seconds'] = None
    if len(conventions) > 1:
        issues.append({'kind': 'mixed_timezone_conventions'})
    elif readings:
        result['out_of_order_transitions'] = sum(a[0] > b[0] for a, b in zip(readings, readings[1:]))
        unique = sorted({r[0] for r in readings})
        gaps = [float(b-a) for a, b in zip(unique, unique[1:])]
        if gaps:
            result['spacing_seconds'] = {'basis': 'sorted_unique_timestamps', 'min': min(gaps),
                                         'median': median(gaps), 'max': max(gaps)}
        result['first_timestamp'] = format_timestamp(unique[0], readings[0][3])
        result['last_timestamp'] = format_timestamp(unique[-1], readings[0][3])
    reasons = []
    if issues:
        reasons.append('structural_or_value_findings')
    if duplicate_groups:
        reasons.append('duplicate_timestamps_require_domain_interpretation')
    if len(readings) < 3:
        reasons.append('fewer_than_three_readings')
    result['integration_exclusion_reasons'] = reasons
    result['numerical_masking'] = None
    if not reasons:
        rows = sorted((r[0], r[1]) for r in readings)
        try:
            numerical = masking_audit(rows, instrument_id, aware=readings[0][3])
            numerical['timestamp_timezone'] = result['timezone_convention']
            result['numerical_masking'] = numerical
        except ValueError as exc:
            reasons.append(str(exc))
    result['status'] = 'diagnostics_only' if reasons else 'numerical_reported_series_only'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--instrument-id', required=True)
    parser.add_argument('--day')
    parser.add_argument('--source-url')
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Output must not overwrite input')
    result = diagnose(args.input, args.instrument_id, args.day, args.source_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f"{result['source_rows']} rows; {result['duplicate_timestamp_count']} repeated timestamps; {result['status']}")


if __name__ == '__main__':
    main()
