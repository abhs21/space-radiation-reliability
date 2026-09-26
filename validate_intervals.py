"""Read-only audit of daily SAA CSVs; never merges or edits annotations."""
import argparse
import math
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent


def audit(paths, window_seconds=600):
    if not math.isfinite(window_seconds) or window_seconds < 0:
        raise ValueError('window_seconds must be nonnegative')
    rows, issues, manifest = [], [], []
    for path in sorted(paths):
        data = path.read_bytes()
        manifest.append({'file': path.name, 'sha256_local_copy': hashlib.sha256(data).hexdigest()})
        with path.open(newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != ['annotator', 'date', 'start', 'end', 'label']:
                issues.append({'file': path.name, 'row': 1, 'kind': 'unexpected_schema'})
                continue
            for number, raw in enumerate(reader, 2):
                ref = {'file': path.name, 'row': number}
                if None in raw or any(value is None for value in raw.values()):
                    issues.append(dict(ref, kind='malformed_row'))
                    continue
                try:
                    start, end = (datetime.fromisoformat(raw[k]) for k in ('start', 'end'))
                    day = datetime.strptime(raw['date'], '%Y-%m-%d').date()
                    if start.utcoffset() is None or end.utcoffset() is None:
                        raise ValueError('timezone required')
                    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
                except (TypeError, ValueError):
                    issues.append(dict(ref, kind='invalid_date_or_timezone'))
                    continue
                if start >= end:
                    issues.append(dict(ref, kind='nonpositive_duration'))
                    continue
                if start.date() != day or end.date() != day:
                    issues.append(dict(ref, kind='outside_declared_utc_day'))
                if path.name[:10] != raw['date']:
                    issues.append(dict(ref, kind='filename_date_mismatch'))
                if not raw['annotator'].strip() or raw['label'] != 'SAA':
                    issues.append(dict(ref, kind='unexpected_annotator_or_label'))
                rows.append(dict(ref, **raw, start_dt=start, end_dt=end, day=day))
    groups = defaultdict(list)
    previous = {}
    for row in rows:
        groups[(row['annotator'], row['label'])].append(row)
        key = (row['file'], row['annotator'], row['label'])
        if key in previous and row['start_dt'] < previous[key]:
            issues.append({'file': row['file'], 'row': row['row'], 'kind': 'out_of_order_start'})
        previous[key] = row['start_dt']
    candidates = []
    for group in groups.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if (a['start_dt'], a['end_dt']) == (b['start_dt'], b['end_dt']):
                    issues.append({'file': b['file'], 'row': b['row'], 'kind': 'duplicate_interval', 'other_file': a['file'], 'other_row': a['row']})
                elif max(a['start_dt'], b['start_dt']) < min(a['end_dt'], b['end_dt']):
                    issues.append({'file': b['file'], 'row': b['row'], 'kind': 'overlapping_interval', 'other_file': a['file'], 'other_row': a['row']})
        ordered = sorted((r for r in group if r['start_dt'].date() == r['day'] == r['end_dt'].date()), key=lambda r: r['start_dt'])
        for a, b in zip(ordered, ordered[1:]):
            midnight = datetime.combine(b['day'], datetime.min.time(), timezone.utc)
            before = (midnight - a['end_dt']).total_seconds()
            after = (b['start_dt'] - midnight).total_seconds()
            if b['day'] == a['day'] + timedelta(days=1) and 0 <= before <= window_seconds and 0 <= after <= window_seconds:
                candidates.append({'annotator': a['annotator'], 'left_file': a['file'], 'left_row': a['row'], 'left_start': a['start'], 'left_end': a['end'], 'right_file': b['file'], 'right_row': b['row'], 'right_start': b['start'], 'right_end': b['end'], 'gap_seconds': (b['start_dt'] - a['end_dt']).total_seconds(), 'status': 'review_candidate_not_merge'})
    return {'files': len(manifest), 'valid_parsed_intervals': len(rows), 'window_seconds_each_side': window_seconds, 'issues': issues, 'candidates': candidates, 'manifest': manifest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='CSV file or directory of daily CSVs')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--window-seconds', type=float, default=600, help='Review window on EACH side of midnight')
    args = parser.parse_args()
    paths = sorted(args.input.glob('*.csv')) if args.input.is_dir() else [args.input]
    if not paths or any(not p.is_file() for p in paths):
        parser.error('No source CSV files')
    output_files = [args.output_dir / name for name in ('audit_results.json', 'flagged_intervals.csv')]
    if any(out.resolve() in {p.resolve() for p in paths} for out in output_files):
        parser.error('An output would overwrite a source file')
    result = audit(paths, args.window_seconds)
    result['sensitivity'] = {str(n): len(audit(paths, n)['candidates']) for n in (60, 120, 300, 600)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_files[0].write_text(json.dumps(result, indent=2) + '\n')
    fields = ['annotator', 'left_file', 'left_row', 'left_start', 'left_end', 'right_file', 'right_row', 'right_start', 'right_end', 'gap_seconds', 'status']
    with output_files[1].open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result['candidates'])
    print(f"{result['files']} files; {result['valid_parsed_intervals']} parsed intervals; {len(result['issues'])} structural findings; {len(result['candidates'])} midnight review candidates")


if __name__ == '__main__':
    main()
