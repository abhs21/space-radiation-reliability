"""Run the fixed sampling study without replacing the original release snapshots."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from radlab_coverage import audit, load_series, trapezoid_area
from radlab_diagnostics import diagnose
from run_campaign import download_one, source_url

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'experiments/sampling-stress.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2) + '\n')


def acquire(case, folder, known, download):
    instrument, day = case
    path = folder / f'{instrument.lower()}-{day}.csv'
    record = {'file': path.name, 'instrument_id': instrument, 'day': day,
              'source_url': source_url(instrument, day)}
    prior = known.get(path.name)
    if path.exists():
        if not prior or prior.get('status') != 'downloaded':
            raise ValueError(f'Untracked snapshot: {path.name}; preserve and investigate separately')
        if digest(path) != prior['sha256']:
            raise ValueError(f'Source hash changed: {path.name}')
        return prior
    if prior and prior.get('status') == 'downloaded':
        raise ValueError(f'Missing frozen snapshot: {path.name}; restore exact bytes')
    if prior and prior.get('status') == 'unavailable':
        return prior
    if not download:
        return dict(record, status='not_downloaded', reason='No local snapshot; download not requested')
    record['attempted_at_utc'] = datetime.now(timezone.utc).isoformat()
    try:
        download_one(case, folder)
    except RuntimeError as exc:
        return dict(record, status='unavailable', reason=str(exc))
    return dict(record, status='downloaded', sha256=digest(path), bytes=path.stat().st_size)


def study_case(source, folder, panel, phases):
    record = dict(source, panel=panel)
    if source.get('status', 'downloaded') != 'downloaded':
        record['analysis_status'] = 'unavailable'
        record['phase_analysis'] = None
        return record
    path = folder / source['file']
    if digest(path) != source['sha256']:
        raise ValueError(f'Source hash changed: {path.name}')
    diagnostic = diagnose(path, source['instrument_id'], source['day'], source['source_url'])
    record['diagnostics'] = diagnostic
    record['analysis_status'] = 'empty_response' if diagnostic['source_rows'] == 0 and not diagnostic['issues'] else diagnostic['status']
    record['phase_analysis'] = None
    if diagnostic['numerical_masking'] is not None:
        rows, aware = load_series(path, source['instrument_id'], with_timezone=True)
        record['phase_analysis'] = audit(rows, source['instrument_id'], aware=aware, phase_offsets=phases)
    return record


def controls(phases):
    signals = {
        'constant': [(Fraction(n * 60), 2) for n in range(241)],
        'linear': [(Fraction(n * 60), 2 + n / 60) for n in range(241)],
        'peak': [(Fraction(n * 60), 100 if n == 65 else 1) for n in range(241)],
        'adaptive_constant': [(Fraction(n), 2) for n in (0, 100, 200, 220, 240, 340, 440)],
    }
    results = {name: audit(rows, 'synthetic-' + name, phase_offsets=phases)
               for name, rows in signals.items()}
    results['unobserved_peak'] = {
        'retained_observations': [[0, 1], [3600, 1]],
        'retained_trapezoid_microgray': 1,
        'possible_hidden_midpoint_peaks': [
            {'midpoint_rate': height,
             'possible_trapezoid_microgray': trapezoid_area([(Fraction(0), 1),
                 (Fraction(1800), height), (Fraction(3600), 1)])}
            for height in (10, 1000, 10**9)],
        'interpretation': 'All examples have identical retained observations. Without a bound on the missing signal, the observations alone provide no finite upper dose bound.',
    }
    return results


def report(payload):
    cases = payload['cases']
    lines = ['# Sampling stress test', '',
             'This is a reported-data processing study, not an instrument calibration or physical-dose uncertainty estimate.', '',
             '## Fixed design', '',
             'Both DosTel instruments on May 1–7 and June 1–7, 2022: 28 instrument-days fixed before download. This extends a convenience sample; it is not a representative survey. Unavailable dates are retained without replacements. The original 18 snapshots remain separate and unchanged.', '',
             f"Protocol SHA-256: `{payload['protocol_sha256']}`. Exact source hashes, URLs and acquisition outcomes are in `data/stress-test/source_manifest.json`.", '',
             'For integration-eligible series, remove 5-, 15- and 30-minute blocks at 30-minute spacing, offset 0/10/20 minutes from the original first-timestamp-plus-30-minute start. Retain the endpoints and a 30-minute boundary margin; bridge each gap with trapezoids. Strides 2/5/10 use the same endpoint policy. `results.json` includes every prescribed block, including blocks removing no observations, each exclusion, and each stride result. Summary percent changes use the complete reported-series integral as reference.', '',
             '## Results by panel', '']
    for panel in ('original18', 'extension28'):
        subset = [case for case in cases if case['panel'] == panel]
        downloaded = [case for case in subset if 'diagnostics' in case]
        available = [case for case in downloaded if case['diagnostics']['source_rows'] > 0]
        empty = [case for case in downloaded if case['analysis_status'] == 'empty_response']
        eligible = [case for case in subset if case['phase_analysis'] is not None]
        lines += [f"- {panel}: {len(subset)} planned, {len(downloaded)} CSV responses, {len(available)} with readings, {len(empty)} empty, {len(subset)-len(downloaded)} unavailable responses; {len(eligible)} integration-eligible and {len(available)-len(eligible)} nonempty series excluded. {sum(c['diagnostics']['source_rows'] for c in available):,} readings and {sum(c['diagnostics']['conflicting_timestamp_count'] for c in available)} differing-rate timestamp groups."]
    lines += ['', '| Panel | Instrument | Day | Rows | Integration / reason | Worst 30-minute change by offset 0 / 10 / 20 (%) |',
              '|---|---|---|---:|---|---|']
    for case in cases:
        diagnostic = case.get('diagnostics')
        rows = diagnostic['source_rows'] if diagnostic else '—'
        reason = ('empty CSV response; no readings' if case['analysis_status'] == 'empty_response' else
                  'eligible' if case['phase_analysis'] else
                  ', '.join(diagnostic['integration_exclusion_reasons']) if diagnostic else case.get('reason', 'unavailable'))
        changes = []
        if case['phase_analysis']:
            for phase in payload['protocol']['phase_offsets_minutes']:
                value = case['phase_analysis']['phase_masking'][str(phase)]['30']['summary']['max_absolute_error_percent']
                changes.append('no tested blocks' if value is None else f'{value:.4f}')
        lines.append(f"| {case['panel']} | {case['instrument_id']} | {case['day']} | {rows} | {reason.replace('|', '/')} | {' / '.join(changes) or '—'} |")
    extension = [case for case in cases if case['panel'] == 'extension28']
    empty_count = sum(case['analysis_status'] == 'empty_response' for case in extension)
    lines += ['', f'{empty_count} of {len(extension)} planned new queries have frozen header-only responses. Empty and unavailable cases add no measurement evidence. No dates were substituted.']
    control = payload.get('api_control')
    if control:
        lines += ['', f"A separately recorded control request on {control['retrieval_date_utc']} for {control['instrument_id']} on {control['day']} returned {control['source_rows']:,} readings matching the original snapshot SHA-256. This is an API check, not a replacement study case. It shows that the API returned readings for that known populated date; it does not establish why other queries are empty."]
    lines += ['', '## Controls and interpretation', '',
              'Constant and linear signals retain their analytic integrals within floating-point roundoff across all prescribed masks. The peaked signal demonstrates dependence on mask placement. A valid 100/20-second changing-cadence constant signal remains eligible. The hidden-peak examples keep identical retained observations while the possible full-signal integral grows without bound; masking sensitivity is not a missing-dose bound.', '',
              'The original roughly 21% examples came from only two eligible instrument-days. Neither these nor this extension establish instrument-wide error rates. Report results per day and instrument; overlapping masks and days are not independent statistical samples. Repeated timestamps remain unresolved observations, not discarded errors.', '',
              'All 58 repeated groups in the original panel occur on five-minute boundaries. Native interval storage (20/100 seconds in the cited DOSTEL paper) and the RadLab DosTel2 knowledgebase cadence (300 seconds) may describe different processing stages. Timestamp, channel, binning, averaging, timezone and quality-flag semantics require an instrument contact before physical interpretation.', '',
              '## Reproduce', '',
              '`python3 run_stress_test.py --output-dir outputs/stress-reproduced` uses frozen snapshots and checks hashes. Compare `results.json` using `verify_reproduction.py`. Acquisition used `--download-missing`, at most two attempts per missing file and three simultaneous requests; recorded failures are not retried on reproduction.', '',
              'The original `reports/diagnostics.json` and its 18 source files are unchanged. Default diagnostics retain the original report schema and phase-zero masking method; the additional phase cases live only in this separate study.', '',
              '## Sources', '',
              '- [DOSTEL instrument paper](https://arxiv.org/pdf/2107.01672)',
              '- [RadLab DosTel2 entry](https://visualization.osdr.nasa.gov/radlab/gui/knowledgebase/dostel2)',
              '- [RadLab API](https://visualization.osdr.nasa.gov/radlab/gui/data-api/)', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/stress-test')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/stress-test')
    parser.add_argument('--download-missing', action='store_true')
    args = parser.parse_args()
    protocol = json.loads(CONFIG.read_text())
    protocol_hash = digest(CONFIG)
    cases = [(instrument, day) for day in protocol['days'] for instrument in protocol['instruments']]
    args.data_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.data_dir / 'source_manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if previous and previous['protocol_sha256'] != protocol_hash:
        parser.error('Protocol changed since acquisition; use a separately named study')
    known = {source['file']: source for source in previous['sources']} if previous else {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        sources = []
        for source in pool.map(lambda case: acquire(case, args.data_dir, known, args.download_missing), cases):
            sources.append(source)
            if args.download_missing:
                records = {item['file']: item for item in sources}
                remaining = [known[name] for name in known if name not in records]
                temporary = manifest_path.with_suffix('.tmp')
                save_json(temporary, {'protocol_sha256': protocol_hash, 'sources': sources + remaining})
                temporary.replace(manifest_path)
    original = json.loads((ROOT / 'reports/source_manifest.json').read_text())['sources']
    phases = protocol['phase_offsets_minutes']
    results = [study_case(source, ROOT / 'data/radlab', 'original18', phases) for source in original]
    results += [study_case(source, args.data_dir, 'extension28', phases) for source in sources]
    payload = {'protocol_sha256': protocol_hash, 'protocol': protocol,
               'cases': results, 'synthetic_controls': controls(phases)}
    control_path = ROOT / 'reports/stress-test/api-control.json'
    if control_path.exists():
        control = json.loads(control_path.read_text())
        matches = [source for source in original if source['instrument_id'] == control['instrument_id'] and source['day'] == control['day']]
        if (len(matches) != 1 or matches[0]['sha256'] != control['sha256']
                or results[original.index(matches[0])]['diagnostics']['source_rows'] != control['source_rows']):
            parser.error('Recorded API control does not match the frozen baseline')
        payload['api_control'] = control
    args.output_dir.mkdir(parents=True, exist_ok=True)
    save_json(args.output_dir / 'results.json', payload)
    (args.output_dir / 'REPORT.md').write_text(report(payload))
    print(json.dumps({'planned_new_cases': len(cases),
                      'downloaded': sum(s['status'] == 'downloaded' for s in sources),
                      'new_eligible': sum(c['phase_analysis'] is not None for c in results if c['panel'] == 'extension28')}))


if __name__ == '__main__':
    main()
