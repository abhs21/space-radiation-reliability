import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def on_five_minute_boundary(timestamp):
    match = re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:(\d{2}):(\d{2}(?:\.\d+)?)(?:Z|[+-]\d{2}:\d{2})?', timestamp)
    if not match:
        raise ValueError('Expected ISO timestamp with seconds')
    datetime.fromisoformat(re.sub(r'\.\d+', '', timestamp).replace('Z', '+00:00'))
    return int(match[1]) % 5 == 0 and Decimal(match[2]) == 0


def review(data_dir, manifest):
    groups, summaries = [], []
    for source in manifest['sources']:
        path = Path(data_dir) / source['file']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != source['sha256']:
            raise ValueError('Source hash changed: ' + source['file'])
        by_time = defaultdict(list)
        with path.open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != ['timestamp', 'instrument_id', 'absorbed_dose_rate']:
                raise ValueError('Unexpected schema: ' + source['file'])
            for number, row in enumerate(reader, 2):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError('Malformed CSV row')
                stamp = row['timestamp']
                on_five_minute_boundary(stamp)
                if row['instrument_id'] != source['instrument_id'] or stamp[:10] != source['day']:
                    raise ValueError('Source instrument or date mismatch')
                rate = Decimal(row['absorbed_dose_rate'])
                if not rate.is_finite() or rate < 0:
                    raise ValueError('Invalid rate')
                by_time[stamp].append((number, row['absorbed_dose_rate']))
        count = 0
        for stamp, values in sorted(by_time.items()):
            if len({Decimal(value) for _, value in values}) < 2:
                continue
            count += 1
            groups.append({
                'instrument_id': source['instrument_id'], 'day': source['day'],
                'timestamp_as_recorded': stamp,
                'timezone_convention': 'explicit_offset_preserved' if re.search(r'(Z|[+-]\d{2}:\d{2})$', stamp) else 'not_supplied',
                'on_five_minute_boundary_as_recorded': on_five_minute_boundary(stamp),
                'source_file': source['file'],
                'source_rows_json': json.dumps([n for n, _ in values]),
                'rates_microgray_per_hour_json': json.dumps([v for _, v in values]),
                'source_url': source['source_url'], 'sha256': digest,
            })
        summaries.append({
            'instrument_id': source['instrument_id'], 'day': source['day'],
            'source_rows': sum(map(len, by_time.values())),
            'unique_recorded_timestamps': len(by_time),
            'five_minute_aligned_unique_timestamps': sum(map(on_five_minute_boundary, by_time)),
            'differing_rate_groups': count,
        })
    summary = {
        'source_cases': len(summaries),
        'source_rows': sum(s['source_rows'] for s in summaries),
        'differing_rate_groups': len(groups),
        'readings_in_differing_rate_groups': sum(len(json.loads(g['source_rows_json'])) for g in groups),
        'five_minute_aligned_differing_rate_groups': sum(g['on_five_minute_boundary_as_recorded'] for g in groups),
        'unique_recorded_timestamps': sum(s['unique_recorded_timestamps'] for s in summaries),
        'five_minute_aligned_unique_timestamps': sum(s['five_minute_aligned_unique_timestamps'] for s in summaries),
        'cases': summaries,
    }
    return groups, summary


def main():
    parser = argparse.ArgumentParser(description='Export differing-rate timestamp groups from verified snapshots.')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/radlab')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'reports/source_manifest.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/timestamp-review')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    groups, summary = review(args.data_dir, manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fields = ['instrument_id', 'day', 'timestamp_as_recorded', 'timezone_convention', 'on_five_minute_boundary_as_recorded', 'source_file', 'source_rows_json', 'rates_microgray_per_hour_json', 'source_url', 'sha256']
    with (args.output_dir / 'repeated_timestamp_groups.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(groups)
    (args.output_dir / 'timestamp_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
