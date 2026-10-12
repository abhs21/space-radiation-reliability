"""Account for documented interval-mean rates; demonstrate with synthetic data."""
import argparse
import json
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

from timestamp_utils import decimal_text

ROOT = Path(__file__).resolve().parent
RATE_UNIT = 'microgray/hour'


def exact_number(value):
    if isinstance(value, Fraction):
        return value
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Expected a finite numeric value')
    if not number.is_finite():
        raise ValueError('Expected a finite numeric value')
    return Fraction(number)


def validate_intervals(intervals, rate_unit):
    if rate_unit != RATE_UNIT:
        raise ValueError('Rate unit must be microgray/hour; no implicit conversion')
    validated = []
    for index, raw in enumerate(intervals, 1):
        try:
            start, end, rate = [exact_number(raw[key]) for key in
                                ['start_seconds', 'end_seconds', 'mean_rate']]
        except (KeyError, TypeError):
            raise ValueError('Interval {} requires start_seconds, end_seconds and mean_rate'.format(index))
        if end <= start:
            raise ValueError('Interval {} has nonpositive duration'.format(index))
        if rate < 0:
            raise ValueError('Interval {} has a negative rate'.format(index))
        if validated:
            previous_start, previous_end, previous_rate = validated[-1]
            if start == previous_start and end == previous_end:
                kind = 'conflicting' if rate != previous_rate else 'duplicate'
                raise ValueError('{} interval at record {}; entire input rejected'.format(kind, index))
            if start < previous_start:
                raise ValueError('Intervals must be ordered by start time')
            if start < previous_end:
                raise ValueError('Overlapping interval at record {}; entire input rejected'.format(index))
        validated.append((start, end, rate))
    return validated


def account(intervals, rate_unit, window_seconds=None):
    rows = validate_intervals(intervals, rate_unit)
    if window_seconds is None:
        if not rows:
            raise ValueError('Empty input requires an explicit window')
        window_start, window_end = rows[0][0], rows[-1][1]
    else:
        if not isinstance(window_seconds, (list, tuple)) or len(window_seconds) != 2:
            raise ValueError('Window requires two endpoints')
        window_start, window_end = map(exact_number, window_seconds)
    if window_end <= window_start:
        raise ValueError('Window must have positive duration')
    complete_dose = Fraction(0)
    estimate = Fraction(0)
    upper = Fraction(0)
    covered = Fraction(0)
    cursor = window_start
    gaps, ledger = [], []
    for index, (start, end, rate) in enumerate(rows, 1):
        left, right = max(start, window_start), min(end, window_end)
        exposure = max(Fraction(0), right - left)
        full_dose = rate * (end - start) / 3600
        complete = exposure == end - start
        allocation = rate * exposure / 3600
        if exposure:
            if left > cursor:
                gaps.append({'start_seconds': cursor, 'end_seconds': left,
                             'duration_seconds': left - cursor})
            cursor = right
            covered += exposure
            estimate += allocation
            upper += full_dose
            if complete:
                complete_dose += full_dose
        ledger.append({'record': index, 'start_seconds': start, 'end_seconds': end,
                       'mean_rate': rate, 'duration_seconds': end - start,
                       'full_interval_dose_microgray': full_dose,
                       'covered_seconds_in_window': exposure,
                       'complete_interval_in_window': complete,
                       'constant_allocation_microgray': allocation})
    if cursor < window_end:
        gaps.append({'start_seconds': cursor, 'end_seconds': window_end,
                     'duration_seconds': window_end - cursor})
    partial = any(row['covered_seconds_in_window'] > 0 and
                  not row['complete_interval_in_window'] for row in ledger)
    return {'rate_unit': RATE_UNIT, 'dose_unit': 'microgray',
            'window_seconds': [window_start, window_end],
            'covered_seconds': covered, 'unobserved_seconds': window_end - window_start - covered,
            'gaps': gaps, 'ledger': ledger,
            'complete_interval_dose_microgray': complete_dose,
            'constant_allocation_estimate_microgray': estimate,
            'partial_bin_allocation': 'piecewise-constant assumption' if partial else 'none; complete intervals only',
            'covered_support_dose_bounds_microgray': [complete_dose, upper],
            'requested_window_dose_bounds_microgray': [complete_dose, None if gaps else upper]}


def interval(start, end, rate):
    return {'start_seconds': start, 'end_seconds': end, 'mean_rate': rate}


def regroup(intervals):
    rows = validate_intervals(intervals, RATE_UNIT)
    if not rows or any(a[1] != b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError('Regrouping requires contiguous complete intervals')
    dose_seconds = sum((rate * (end - start) for start, end, rate in rows), Fraction(0))
    return [interval(rows[0][0], rows[-1][1], dose_seconds / (rows[-1][1] - rows[0][0]))]


def shifted(intervals, seconds, gain=1):
    offset, scale = exact_number(seconds), exact_number(gain)
    return [interval(exact_number(row['start_seconds']) + offset,
                     exact_number(row['end_seconds']) + offset,
                     exact_number(row['mean_rate']) * scale) for row in intervals]


def comparison(name, intervals, truth):
    result = account(intervals, RATE_UNIT)
    coarse = account(regroup(intervals), RATE_UNIT)
    rows = validate_intervals(intervals, RATE_UNIT)
    wrong = sum((row[2] for row in rows), Fraction(0)) / len(rows) * result['covered_seconds'] / 3600
    correct = result['complete_interval_dose_microgray']
    if correct != truth or coarse['complete_interval_dose_microgray'] != truth:
        raise ValueError('Synthetic conservation check failed: ' + name)
    return {'name': name, 'intervals': intervals, 'expected_dose_microgray': truth,
            'correct_dose_microgray': correct, 'correct_dose_microgray_exact': str(correct),
            'regrouped_dose_microgray': coarse['complete_interval_dose_microgray'],
            'incorrect_unweighted_dose_microgray': wrong,
            'incorrect_unweighted_relative_error_percent': (wrong / truth - 1) * 100,
            'accounting': result}


def build_demo():
    constant = [interval(i * 100, (i + 1) * 100, 2) for i in range(9)]
    constant += [interval(900 + i * 20, 920 + i * 20, 2) for i in range(5)]
    linear = [interval(a, b, 1 + Fraction(a + b, 1000)) for a, b in
              [(0, 100), (100, 250), (250, 500), (500, 1000)]]
    pulse = [interval(i * 100, (i + 1) * 100, 1) for i in range(9)]
    pulse += [interval(900 + i * 20, 920 + i * 20, 10) for i in range(5)]
    fixtures = [comparison('constant', constant, Fraction(2000, 3600)),
                comparison('linear', linear, Fraction(2000, 3600)),
                comparison('adaptive_pulse', pulse, Fraction(1900, 3600))]
    boundary_cases = []
    for edges in [[0, 50, 100], [0, 20, 70, 100]]:
        bins = [interval(a, b, Fraction(max(0, min(b, 55) - max(a, 45)) * 100, b - a))
                for a, b in zip(edges, edges[1:])]
        full = account(bins, RATE_UNIT)
        if full['complete_interval_dose_microgray'] != Fraction(1000, 3600):
            raise ValueError('Boundary fixture full-bin conservation failed')
        for stop in [48, 52]:
            result = account(bins, RATE_UNIT, [0, stop])
            truth = Fraction((stop - 45) * 100, 3600)
            lower, upper = result['covered_support_dose_bounds_microgray']
            if not lower <= truth <= upper:
                raise ValueError('Boundary fixture bounds failed')
            boundary_cases.append({'bin_edges_seconds': edges, 'window_seconds': [0, stop],
                                   'analytic_partial_dose_microgray': truth,
                                   'full_bin_dose_microgray': full['complete_interval_dose_microgray'],
                                   'accounting': result})
    fixtures.append({'name': 'narrow_peak_boundary',
                     'signal': '100 microgray/hour on [45,55); zero elsewhere on [0,100)',
                     'cases': boundary_cases})
    missing = [row for row in pulse if row['start_seconds'] not in [400, 940]]
    incomplete = account(missing, RATE_UNIT, [0, 1000])
    conflicting = list(pulse[:10]) + [interval(900, 920, 99)] + pulse[10:]
    try:
        account(conflicting, RATE_UNIT)
    except ValueError as error:
        conflict_error = str(error)
    else:
        raise ValueError('Synthetic conflicting input was not rejected')
    observed = incomplete['complete_interval_dose_microgray']
    fixtures.append({'name': 'missing_conflicting', 'accounting': incomplete,
                     'conflicting_input': conflicting, 'conflicting_input_rejection': conflict_error,
                     'compatible_gap_completions': [
                         {'gap_rate_microgray_per_hour': 0, 'full_window_dose_microgray': observed},
                         {'gap_rate_microgray_per_hour': 100,
                          'full_window_dose_microgray': observed + 100 * incomplete['unobserved_seconds'] / 3600}],
                     'unobserved_gap_upper_bound_microgray': None})
    calibration_a, calibration_b = [interval(-200, -100, 3)], [interval(-200, -100, 6)]
    gain = (account(calibration_b, RATE_UNIT)['complete_interval_dose_microgray'] /
            account(calibration_a, RATE_UNIT)['complete_interval_dose_microgray'])
    gain_corrected = shifted(shifted(pulse, 0, gain), 0, 1 / gain)
    recorded = shifted(gain_corrected, 60)
    corrected = account(shifted(recorded, -60), RATE_UNIT, [0, 1000])
    if gain != 2 or corrected['complete_interval_dose_microgray'] != Fraction(1900, 3600):
        raise ValueError('Synthetic independent gain/known-clock correction failed')
    fixtures.append({'name': 'gain_clocks', 'independent_calibration_intervals':
                     {'series_a': calibration_a, 'series_b': calibration_b},
                     'frozen_gain_factor': gain, 'imposed_clock_offset_seconds': 60,
                     'held_out_scaled_dose_microgray':
                     account(shifted(pulse, 0, gain), RATE_UNIT)['complete_interval_dose_microgray'],
                     'gain_corrected_complete_span_dose_microgray':
                     account(recorded, RATE_UNIT)['complete_interval_dose_microgray'],
                     'known_clock_corrected_accounting': corrected,
                     'clock_scenarios': [{'applied_shift_seconds': shift,
                                          'accounting': account(shifted(recorded, shift), RATE_UNIT, [0, 1000])}
                                         for shift in [-60, -30, 0, 30, 60]],
                     'missing_exposure_after_gain_correction':
                     account(shifted(shifted(missing, 0, gain), 0, 1 / gain), RATE_UNIT, [0, 1000])['unobserved_seconds']})
    return {'title': 'Synthetic interval-mean accounting demonstration',
            'input_contract': 'Ordered, nonoverlapping [start_seconds,end_seconds) wall-time intervals with explicit mean_rate and microgray/hour units; one time origin per series.',
            'formula': 'D_microgray = sum(mean_rate * (end_seconds-start_seconds) / 3600)',
            'arithmetic': 'Exact rational arithmetic internally; decimal strings rendered to 50-digit precision.',
            'scope': 'Synthetic accounting only; no native durations or physical timing inferred from RadLab timestamps.',
            'fixtures': fixtures}


def json_values(value):
    if isinstance(value, Fraction):
        return decimal_text(value)
    if isinstance(value, dict):
        return {key: json_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_values(item) for item in value]
    return value


def render_report(demo):
    rows = []
    for case in demo['fixtures'][:3]:
        rows.append('| {} | {} | {} | {} | {:+.6f}% |'.format(
            case['name'], case['correct_dose_microgray_exact'],
            format(float(case['correct_dose_microgray']), '.12f'),
            format(float(case['incorrect_unweighted_dose_microgray']), '.12f'),
            float(case['incorrect_unweighted_relative_error_percent'])))
    return '\n'.join([
        '# Synthetic interval-mean accounting', '',
        'This demonstration uses analytic synthetic signals and explicit, nonoverlapping accumulation intervals. It makes no claim about a real instrument discrepancy. All inputs, interval/gap ledgers and scenario results are in `results.json`.', '',
        '**Contract:** rates are wall-time interval means in microgray/hour over `[start_seconds,end_seconds)`, with a common time origin. Dose in microgray is `sum(mean_rate * duration_seconds / 3600)`. No duration is inferred from timestamp spacing. Live-time denominators, dose equivalent, material conversion and calibration changes require separate documented inputs; they are outside this contract. Unsupported units, nonfinite values or negative rates, unordered/nonpositive intervals, duplicates, conflicts and overlaps reject the entire input.', '',
        '## Complete intervals conserve dose', '',
        '| Synthetic signal | Exact dose (microgray) | Weighted dose (microgray) | Incorrect unweighted estimate (microgray) | Error |',
        '|---|---:|---:|---:|---:|', *rows, '',
        'The constant control is 2 microgray/hour for 1000 s, partitioned as 9×100 s + 5×20 s. The linear control is `1 + 0.002t` on `[0,1000)`, averaged over unequal intervals ending at 100, 250, 500 and 1000 s. The adaptive pulse is 1 microgray/hour for 900 s and 10 for 100 s with the same 100/20 s partition. Each weighted sum exactly equals its analytic integral and the dose after regrouping to one duration-weighted coarse interval. The deliberately incorrect estimate is the arithmetic mean of interval means times total exposure; extra samples in the high-rate region produce the pulse bias.', '',
        '## Boundaries, missing exposure and clocks', '',
        '**Narrow boundary:** a rectangular 100 microgray/hour peak on `[45,55)` is averaged into bins with edges `[0,50,100]` and `[0,20,70,100]`. Both complete-bin totals are exactly 5/18 microgray. On `[0,48)`, analytic dose is 1/12 microgray; constant allocation estimates are 2/15 and 7/45 microgray. The first estimate has nonnegative bounds `[0,5/36]`; the second `[0,5/18]`. Results also move the window end to 52 s. Cutting a bin requires an assumption: interval means alone permit any partial dose from zero to the entire cut-bin dose. Bounds sum exact complete-bin doses and these boundary limits; they do not recover peak timing.', '',
        '**Missing/conflicting:** removing `[400,500)` and `[940,960)` from the adaptive pulse leaves 880 s of exposure and 4/9 microgray of complete-interval dose. Missing 120 s remains unobserved. Filling it with rates of 0 or 100 gives different totals with identical observations; nonnegative rates alone give no finite upper bound for the full window. A second record for `[900,920)` with rate 99 is rejected rather than selected, merged or counted twice.', '',
        '**Gain/clocks:** separate constant calibration intervals `[-200,-100)` at rates 3 and 6 supply a frozen gain of 2. Dividing held-out scaled rates by that factor recovers the original dose. A known +60 s offset preserves the full shifted-span dose, but on the fixed `[0,1000)` window leaves 940 s coverage and 13/36 microgray. Correcting the known offset restores the original result. Applied shifts −60/−30/0/+30/+60 s are diagnostic scenarios, not uncertainty intervals or estimates of real clock accuracy. Gain scaling leaves the missing fixture’s 120 s gap unchanged; neither scaling nor shifting creates missing observations.', '',
        'Exact rational checks pass for complete-interval truth and regrouping. Decimal output uses 50-digit precision; tests also check analytic boundary values, gap bounds, invalid-input rejection and deterministic regeneration. These are computational checks, not measurement accuracy. A real comparison requires documented accumulation/rebinning, rate denominator, material, clock correction and common support before interpreting its totals.', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Optional JSON with rate_unit, intervals and optional window_seconds')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/interval-accounting')
    args = parser.parse_args()
    targets = [args.output_dir / 'results.json', args.output_dir / 'REPORT.md']
    if args.input and args.input.resolve() in {path.resolve() for path in targets}:
        parser.error('Outputs must not overwrite input')
    try:
        if args.input:
            raw = json.loads(args.input.read_text(encoding='utf-8'))
            result = account(raw['intervals'], raw['rate_unit'], raw.get('window_seconds'))
            report = ('# Explicit interval accounting\n\n'
                      'Rates must be documented wall-time interval means in microgray/hour. '
                      'Dose is mean rate times explicit duration divided by 3600. '
                      'See results.json for the interval ledger, covered exposure, unobserved gaps, '
                      'complete-interval dose and separately labeled partial-bin constant-allocation estimates. '
                      'Nonnegative partial-bin bounds do not infer within-bin structure. '
                      'A null full-window upper bound means unobserved exposure has no finite upper bound.\n')
        else:
            result = build_demo()
            report = render_report(result)
        encoded = json.dumps(json_values(result), indent=2, allow_nan=False) + '\n'
        args.output_dir.mkdir(parents=True, exist_ok=True)
        targets[0].write_text(encoded, encoding='utf-8')
        targets[1].write_text(report, encoding='utf-8')
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print('Wrote interval accounting results to ' + str(args.output_dir))


if __name__ == '__main__':
    main()
