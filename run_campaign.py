"""Reproduce the fixed 18 instrument-day audit from versioned public CSV snapshots."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from radlab_diagnostics import diagnose

ROOT = Path(__file__).resolve().parent
BASE_DAYS = ('2022-03-01', '2022-04-01')
EXTENSION_DAYS = tuple(f'2022-04-{n:02d}' for n in range(2, 9))
CASES = [(instrument, day) for day in BASE_DAYS + EXTENSION_DAYS for instrument in ('DosTel1', 'DosTel2')]


def source_url(instrument, day):
    end = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    return ('https://visualization.osdr.nasa.gov/radlab/api/'
            f'?instrument_id={quote(instrument)}&timestamp%3E={quote(day+"T00:00", safe="")}'
            f'&timestamp%3C{quote(end+"T00:00", safe="")}&absorbed_dose_rate&format=csv')


def download_one(case, folder):
    instrument, day = case
    path = folder / f'{instrument.lower()}-{day}.csv'
    if path.exists():
        return
    errors = []
    for _ in range(2):
        try:
            req = Request(source_url(instrument, day), headers={'User-Agent': 'SpaceRadiationReliability/0.1'})
            with urlopen(req, timeout=45) as response:
                data = response.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024 or not data.startswith(b'timestamp,instrument_id,absorbed_dose_rate'):
                raise ValueError('Unexpected response or response larger than 1 MiB')
            path.write_bytes(data)
            return
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError(f'{instrument} {day}: {errors}')


def report(cases):
    conflicts = sum(c['conflicting_timestamp_count'] for c in cases)
    excluded = sum(c['status'] == 'diagnostics_only' for c in cases)
    rows = sum(c['source_rows'] for c in cases)
    lines = ['# RadLab diagnostic report', '',
             'Release 0.1.0 — fixed audit of 18 instrument-day CSV snapshots.', '',
             f'The batch contains **{rows:,} readings**, **{conflicts} timestamps with differing rates**, and **{excluded} series excluded from numerical integration**.', '',
             '## Selection and method', '',
             'The four original cases use DosTel1 and DosTel2 on March 1 and April 1, 2022. The extension uses both instruments on April 2–8, 2022. These dates were fixed before running the extension. They are a convenience sample, not a representative instrument survey.', '',
             'Each API query requests one instrument and absorbed dose rate over a half-open calendar-day window. The CSV does not supply a timezone or interval definition. Day boundaries here follow the literal API timestamps; they are not asserted to be UTC. Source URLs and exact byte hashes are in [source_manifest.json](source_manifest.json).', '',
             'Duplicate groups retain their source rows and every rate. No readings are averaged or removed. Spacing is calculated from sorted unique parsed timestamps, so duplicate groups do not introduce artificial zero-second gaps. A repeated timestamp can have a valid instrument explanation; these findings do not establish corrupted data.', '',
             '| Instrument | Day | Rows | Repeated timestamps | Differing-rate timestamps | Median unique spacing (s) | Worst 30-minute masking change (%) |',
             '|---|---|---:|---:|---:|---:|---:|']
    for c in cases:
        spacing = c['spacing_seconds']['median'] if c['spacing_seconds'] else None
        num = c['numerical_masking']
        worst = num['block_masking_minutes']['30']['max_absolute_error_percent'] if num else None
        fmt = lambda x: '—' if x is None else f'{x:.4f}'
        lines.append(f"| {c['instrument_id']} | {c['day']} | {c['source_rows']} | {c['duplicate_timestamp_count']} | {c['conflicting_timestamp_count']} | {fmt(spacing)} | {fmt(worst)} |")
    lines.extend(['', '## Interpretation', '',
                  'The numerical analysis integrates the reported rate values with the trapezoidal rule over the observed timestamp span. Synthetic 5-, 15-, and 30-minute blocks are removed at half-hour start positions, with a 30-minute boundary margin. The retained series is integrated across each artificial gap. The comparison is against the full reported series, not physical ground truth; it does not detect naturally missing telemetry or estimate unobserved dose. Outputs include every prescribed mask summary and stride 2/5/10 sensitivity.', '',
                  'Series with duplicate timestamps, malformed/value findings, mixed timestamp conventions, fewer than three readings, or nonpositive reference area receive diagnostics without integration. Passing these software checks does not resolve instrument semantics or establish physical validity.', '',
                  'The published DosTel2 knowledgebase lists a 300-second cadence. Observed record spacing is reported above without assuming the two quantities should match. Direction/channel interpretation, interval averaging, quality flags, and timezone remain domain questions.', '',
                  '## Reproduce', '',
                  'Run `python3 run_campaign.py --output-dir outputs/reproduced`. This uses the committed public-data snapshots and checks their SHA-256 hashes against the release manifest. It does not access private volunteer annotations. To query current public data separately, use an empty data directory and `--download-missing`; changed source bytes stop reproduction rather than silently replacing the release snapshot.', '',
                  '## Sources', '',
                  '- [RadLab API documentation](https://visualization.osdr.nasa.gov/radlab/gui/data-api/)',
                  '- [DosTel2 knowledgebase](https://visualization.osdr.nasa.gov/radlab/gui/knowledgebase/dostel2)',
                  '- [RadLab overview](https://visualization.osdr.nasa.gov/radlab/gui/overview/)', '',
                  'These are exploratory software diagnostics. Formal AWG subgroup recognition, instrument-level validation, and external adoption are not established by this report.', ''])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/radlab')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/campaign')
    parser.add_argument('--download-missing', action='store_true', help='At most two attempts per missing file, three concurrent requests')
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    if args.download_missing:
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda case: download_one(case, args.data_dir), CASES))
    manifest_path = ROOT / 'reports/source_manifest.json'
    prior = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    known = {c['file']: c for c in prior['sources']} if prior else {}
    cases, sources = [], []
    for instrument, day in CASES:
        path = args.data_dir / f'{instrument.lower()}-{day}.csv'
        if not path.exists():
            parser.error(f'Missing {path.name}; provide snapshots or use --download-missing')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.name in known and known[path.name]['sha256'] != digest:
            parser.error(f'Source hash changed: {path.name}; preserve and investigate separately')
        result = diagnose(path, instrument, day, source_url(instrument, day))
        cases.append(result)
        sources.append(known.get(path.name, {
            'file': path.name, 'instrument_id': instrument, 'day': day,
            'source_url': source_url(instrument, day), 'sha256': digest,
            'bytes': path.stat().st_size,
            'source_acquired_date': '2026-09-22' if day in BASE_DAYS else datetime.now(timezone.utc).date().isoformat(),
            'selection': 'original_four_case_panel' if day in BASE_DAYS else 'prespecified_seven_day_extension',
        }))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {'version': '0.1.0', 'case_count': len(cases), 'cases': cases}
    (args.output_dir / 'diagnostics.json').write_text(json.dumps(payload, indent=2) + '\n')
    (args.output_dir / 'source_manifest.json').write_text(json.dumps({'sources': sources}, indent=2) + '\n')
    (args.output_dir / 'REPORT.md').write_text(report(cases))
    print(json.dumps({'cases': len(cases), 'rows': sum(c['source_rows'] for c in cases),
                      'excluded': sum(c['status'] == 'diagnostics_only' for c in cases),
                      'conflicting_timestamps': sum(c['conflicting_timestamp_count'] for c in cases)}))


if __name__ == '__main__':
    main()
