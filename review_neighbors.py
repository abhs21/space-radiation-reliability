import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from statistics import median

from timestamp_utils import decimal_text, parse_timestamp

ROOT = Path(__file__).resolve().parent
FIELDS = [
    'instrument_id', 'day', 'source_file', 'source_url', 'sha256',
    'timezone_convention', 'timestamps_as_recorded', 'source_rows',
    'rates_microgray_per_hour', 'before', 'after', 'pre_gap_seconds',
    'post_gap_seconds', 'typical_gap_seconds_this_file', 'pre_gap_vs_typical',
    'post_gap_vs_typical', 'comparison_status', 'comparison_blockers',
    'expected_from_trend_microgray_per_hour', 'absolute_differences_microgray_per_hour',
    'closest_source_positions', 'closest_source_rows',
]


def load_source(data_dir, source):
    root = Path(data_dir).resolve()
    path = (root / source['file']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Source file must be inside data directory')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != source['sha256']:
        raise ValueError('Source hash changed: ' + source['file'])
    rows, conventions = [], set()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''))
    if reader.fieldnames != ['timestamp', 'instrument_id', 'absorbed_dose_rate']:
        raise ValueError('Unexpected schema: ' + source['file'])
    for number, raw in enumerate(reader, 2):
        if None in raw or any(value is None for value in raw.values()):
            raise ValueError('Malformed CSV row: ' + source['file'])
        if raw['instrument_id'] != source['instrument_id'] or raw['timestamp'][:10] != source['day']:
            raise ValueError('Source instrument or recorded date mismatch')
        moment, aware = parse_timestamp(raw['timestamp'])
        try:
            rate = Decimal(raw['absorbed_dose_rate'])
        except InvalidOperation as exc:
            raise ValueError('Invalid rate') from exc
        if not rate.is_finite() or rate < 0:
            raise ValueError('Invalid rate')
        conventions.add(aware)
        rows.append({'timestamp': raw['timestamp'], 'time': moment, 'row': number,
                     'rate_text': raw['absorbed_dose_rate'], 'rate': Fraction(rate)})
    if len(conventions) > 1:
        raise ValueError('Mixed timezone conventions: ' + source['file'])
    convention = ('explicit_offsets_used_for_elapsed_time' if conventions == {True}
                  else 'not_supplied' if rows else 'no_timestamps')
    return rows, convention


def original_readings(rows):
    if rows is None:
        return None
    return {'timestamps_as_recorded': [r['timestamp'] for r in rows],
            'source_rows': [r['row'] for r in rows],
            'rates_microgray_per_hour': [r['rate_text'] for r in rows]}


def review(data_dir, manifest):
    groups, cases = [], []
    pre_ratios, post_ratios = [], []
    position_counts = Counter()
    files = [s['file'] for s in manifest['sources']]
    if len(files) != len(set(files)):
        raise ValueError('Duplicate source file in manifest')
    sources = sorted(manifest['sources'], key=lambda s: (s['instrument_id'], s['day'], s['file']))
    for source in sources:
        rows, convention = load_source(data_dir, source)
        by_time = defaultdict(list)
        for row in rows:
            by_time[row['time']].append(row)
        times = sorted(by_time)
        gaps = [b - a for a, b in zip(times, times[1:])]
        typical = median(gaps) if gaps else None
        count, compared = 0, 0
        for index, moment in enumerate(times):
            readings = by_time[moment]
            if len({r['rate'] for r in readings}) < 2:
                continue
            count += 1
            before = by_time[times[index - 1]] if index else None
            after = by_time[times[index + 1]] if index + 1 < len(times) else None
            pre = moment - times[index - 1] if before else None
            post = times[index + 1] - moment if after else None
            blockers = []
            for label, neighbor in [('before', before), ('after', after)]:
                if neighbor is None:
                    blockers.append('missing_' + label)
                elif len({r['rate'] for r in neighbor}) > 1:
                    blockers.append('conflicting_' + label)
            group = {k: source[k] for k in ['instrument_id', 'day', 'source_url', 'sha256']}
            group.update({
                'source_file': source['file'], 'timezone_convention': convention,
                **original_readings(readings), 'before': original_readings(before),
                'after': original_readings(after), 'pre_gap_seconds': decimal_text(pre),
                'post_gap_seconds': decimal_text(post),
                'typical_gap_seconds_this_file': decimal_text(typical),
                'pre_gap_vs_typical': decimal_text(pre / typical) if pre is not None else None,
                'post_gap_vs_typical': decimal_text(post / typical) if post is not None else None,
                'comparison_status': 'unavailable', 'comparison_blockers': blockers,
                'expected_from_trend_microgray_per_hour': None,
                'absolute_differences_microgray_per_hour': None,
                'closest_source_positions': [], 'closest_source_rows': [],
            })
            if not blockers:
                expected = (before[0]['rate'] * post + after[0]['rate'] * pre) / (pre + post)
                errors = [abs(r['rate'] - expected) for r in readings]
                minimum_error = min(errors)
                closest = [i + 1 for i, error in enumerate(errors) if error == minimum_error]
                group.update({
                    'comparison_status': 'compared' if len(closest) == 1 else 'tied',
                    'expected_from_trend_microgray_per_hour': decimal_text(expected),
                    'absolute_differences_microgray_per_hour': [decimal_text(e) for e in errors],
                    'closest_source_positions': closest,
                    'closest_source_rows': [readings[i - 1]['row'] for i in closest],
                })
                if len(closest) == 1:
                    position_counts[closest[0]] += 1
                pre_ratios.append(pre / typical)
                post_ratios.append(post / typical)
                compared += 1
            groups.append({field: group[field] for field in FIELDS})
        cases.append({
            'instrument_id': source['instrument_id'], 'day': source['day'],
            'source_file': source['file'], 'sha256': source['sha256'],
            'timezone_convention': convention, 'source_rows': len(rows),
            'unique_timestamp_instants': len(times), 'differing_rate_groups': count,
            'comparable_groups': compared, 'typical_gap_seconds': decimal_text(typical),
            'out_of_order_transitions': sum(a['time'] > b['time'] for a, b in zip(rows, rows[1:])),
        })
    summary = {
        'source_cases': len(cases), 'source_rows': sum(c['source_rows'] for c in cases),
        'differing_rate_groups': len(groups),
        'readings_in_differing_rate_groups': sum(len(g['source_rows']) for g in groups),
        'comparable_groups': len(pre_ratios),
        'unavailable_groups': sum(g['comparison_status'] == 'unavailable' for g in groups),
        'tied_groups': sum(g['comparison_status'] == 'tied' for g in groups),
        'closest_source_position_counts': {str(p): position_counts[p] for p in sorted(position_counts)},
        'instrument_days_with_differing_rates': len({(g['instrument_id'], g['day']) for g in groups}),
        'calendar_days_with_differing_rates': len({g['day'] for g in groups}),
        'median_pre_gap_vs_typical': decimal_text(median(pre_ratios)) if pre_ratios else None,
        'median_post_gap_vs_typical': decimal_text(median(post_ratios)) if post_ratios else None,
        'calculation': 'Linear interpolation between the nearest distinct timestamp groups with unambiguous rates',
        'numeric_export': 'Computed values are decimal strings rounded to 50 significant digits; comparisons use exact fractions',
        'interpretation': 'Descriptive local-trend comparison only; source order is not acquisition order or evidence of physical correctness',
        'cases': cases,
    }
    return groups, summary


def write_outputs(output_dir, groups, summary):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / 'neighboring_sample_groups.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        for group in groups:
            writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in group.items()})
    serialized = ',\n'.join(json.dumps(g, ensure_ascii=False, allow_nan=False) for g in groups)
    (output_dir / 'neighboring_sample_groups.json').write_text('[\n' + serialized + '\n]\n', encoding='utf-8')
    (output_dir / 'neighboring_sample_summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Compare conflicting readings with neighboring samples without selecting or changing them.')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/radlab')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'reports/source_manifest.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/neighbor-review')
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        inputs = {args.manifest.resolve()} | {(args.data_dir / s['file']).resolve() for s in manifest['sources']}
        outputs = {(args.output_dir / name).resolve() for name in
                   ['neighboring_sample_groups.csv', 'neighboring_sample_groups.json', 'neighboring_sample_summary.json']}
        if inputs & outputs:
            raise ValueError('Outputs must not overwrite inputs')
        groups, summary = review(args.data_dir, manifest)
        write_outputs(args.output_dir, groups, summary)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
