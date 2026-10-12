"""Read-only audit of daily SAA CSVs; never merges or edits annotations."""
import argparse
import math
import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path

from timestamp_utils import midnight_seconds, parse_timestamp, utc_day

BASE = Path(__file__).resolve().parent


def audit(paths, window_seconds=600):
    if not math.isfinite(window_seconds) or window_seconds < 0:
        raise ValueError('window_seconds must be nonnegative')
    exact_window = Fraction(str(window_seconds))
    rows, issues, manifest = [], [], []
    for path in sorted(paths):
        data = path.read_bytes()
        manifest.append({'file': path.name, 'sha256_local_copy': hashlib.sha256(data).hexdigest()})
        with io.StringIO(data.decode('utf-8-sig'), newline='') as handle:
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
                    (start, start_aware), (end, end_aware) = (parse_timestamp(raw[k], allow_minutes=True) for k in ('start', 'end'))
                    day = datetime.strptime(raw['date'], '%Y-%m-%d').date()
                    if not start_aware or not end_aware:
                        raise ValueError('timezone required')
                    start_day, end_day = utc_day(start), utc_day(end)
                except (TypeError, ValueError, OverflowError):
                    issues.append(dict(ref, kind='invalid_date_or_timezone'))
                    continue
                if start >= end:
                    issues.append(dict(ref, kind='nonpositive_duration'))
                    continue
                matching_day = start_day == day == end_day
                matching_filename = path.name[:10] == raw['date']
                matching_identity = bool(raw['annotator'].strip()) and raw['label'] == 'SAA'
                if not matching_day:
                    issues.append(dict(ref, kind='outside_declared_utc_day'))
                if not matching_filename:
                    issues.append(dict(ref, kind='filename_date_mismatch'))
                if not matching_identity:
                    issues.append(dict(ref, kind='unexpected_annotator_or_label'))
                rows.append(dict(ref, **raw, start_time=start, end_time=end, day=day,
                                 candidate_eligible=matching_day and matching_filename and matching_identity))
    groups = defaultdict(list)
    previous = {}
    for row in rows:
        groups[(row['annotator'], row['label'])].append(row)
        key = (row['file'], row['annotator'], row['label'])
        if key in previous and row['start_time'] < previous[key]:
            issues.append({'file': row['file'], 'row': row['row'], 'kind': 'out_of_order_start'})
        previous[key] = row['start_time']
    candidates = []
    for group in groups.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if (a['start_time'], a['end_time']) == (b['start_time'], b['end_time']):
                    issues.append({'file': b['file'], 'row': b['row'], 'kind': 'duplicate_interval', 'other_file': a['file'], 'other_row': a['row']})
                elif max(a['start_time'], b['start_time']) < min(a['end_time'], b['end_time']):
                    issues.append({'file': b['file'], 'row': b['row'], 'kind': 'overlapping_interval', 'other_file': a['file'], 'other_row': a['row']})
        ordered = sorted((r for r in group if r['candidate_eligible']), key=lambda r: r['start_time'])
        for a, b in zip(ordered, ordered[1:]):
            midnight = midnight_seconds(b['day'])
            before = midnight - a['end_time']
            after = b['start_time'] - midnight
            if b['day'] == a['day'] + timedelta(days=1) and 0 <= before <= exact_window and 0 <= after <= exact_window:
                gap = b['start_time'] - a['end_time']
                candidates.append({'annotator': a['annotator'], 'left_file': a['file'], 'left_row': a['row'], 'left_start': a['start'], 'left_end': a['end'], 'right_file': b['file'], 'right_row': b['row'], 'right_start': b['start'], 'right_end': b['end'], 'gap_seconds': float(gap), 'gap_seconds_exact': str(gap), 'status': 'review_candidate_not_merge'})
    return {'files': len(manifest), 'valid_parsed_intervals': len(rows), 'candidate_eligible_intervals': sum(r['candidate_eligible'] for r in rows), 'window_seconds_each_side': window_seconds, 'issues': issues, 'candidates': candidates, 'manifest': manifest}


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
    fields = ['annotator', 'left_file', 'left_row', 'left_start', 'left_end', 'right_file', 'right_row', 'right_start', 'right_end', 'gap_seconds', 'gap_seconds_exact', 'status']
    with output_files[1].open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result['candidates'])
    print(f"{result['files']} files; {result['valid_parsed_intervals']} parsed intervals; {len(result['issues'])} structural findings; {len(result['candidates'])} midnight review candidates")


if __name__ == '__main__':
    main()
