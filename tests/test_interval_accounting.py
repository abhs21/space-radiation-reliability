import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from interval_accounting import ROOT, RATE_UNIT, account, build_demo, interval, regroup, shifted


class IntervalAccountingTests(unittest.TestCase):
    def test_analytic_complete_intervals_and_regrouping(self):
        demo = build_demo()
        self.assertEqual([case['name'] for case in demo['fixtures']],
                         ['constant', 'linear', 'adaptive_pulse', 'narrow_peak_boundary',
                          'missing_conflicting', 'gain_clocks'])
        for case, expected in zip(demo['fixtures'][:3],
                                  [Fraction(5, 9), Fraction(5, 9), Fraction(19, 36)]):
            self.assertEqual(case['correct_dose_microgray'], expected)
            self.assertEqual(case['regrouped_dose_microgray'], expected)
            self.assertEqual(case['accounting']['covered_seconds'], 1000)
            self.assertEqual(case['accounting']['unobserved_seconds'], 0)
            self.assertEqual(case['accounting']['covered_support_dose_bounds_microgray'],
                             [expected, expected])
        adaptive = demo['fixtures'][2]
        self.assertEqual(adaptive['incorrect_unweighted_dose_microgray'], Fraction(295, 252))
        self.assertAlmostEqual(float(adaptive['incorrect_unweighted_relative_error_percent']),
                               121.80451127819549, places=10)
        self.assertEqual(demo['fixtures'][0]['incorrect_unweighted_relative_error_percent'], 0)
        self.assertNotEqual(demo['fixtures'][1]['incorrect_unweighted_dose_microgray'], Fraction(5, 9))

    def test_fractional_endpoints_are_exact_and_no_duration_is_inferred(self):
        result = account([interval('0.000000001', '0.000000003', '3600')], RATE_UNIT,
                         ['0', '0.000000010'])
        self.assertEqual(result['complete_interval_dose_microgray'], Fraction(2, 10**9))
        self.assertEqual(result['covered_seconds'], Fraction(2, 10**9))
        self.assertEqual(result['unobserved_seconds'], Fraction(8, 10**9))
        self.assertEqual(len(result['gaps']), 2)
        with self.assertRaisesRegex(ValueError, 'requires start_seconds'):
            account([{'timestamp': 0, 'mean_rate': 3600}], RATE_UNIT)

    def test_partial_bins_separate_allocation_assumption_and_bounds(self):
        cases = build_demo()['fixtures'][3]['cases']
        self.assertEqual(cases[0]['analytic_partial_dose_microgray'], Fraction(1, 12))
        self.assertEqual(cases[0]['accounting']['constant_allocation_estimate_microgray'], Fraction(2, 15))
        self.assertEqual(cases[0]['accounting']['covered_support_dose_bounds_microgray'],
                         [0, Fraction(5, 36)])
        self.assertEqual(cases[1]['analytic_partial_dose_microgray'], Fraction(7, 36))
        self.assertEqual(cases[1]['accounting']['covered_support_dose_bounds_microgray'],
                         [Fraction(5, 36), Fraction(5, 18)])
        self.assertEqual(cases[2]['accounting']['constant_allocation_estimate_microgray'], Fraction(7, 45))
        for case in cases:
            result = case['accounting']
            self.assertEqual(case['full_bin_dose_microgray'], Fraction(5, 18))
            self.assertEqual(result['partial_bin_allocation'], 'piecewise-constant assumption')
            self.assertNotEqual(result['constant_allocation_estimate_microgray'],
                                case['analytic_partial_dose_microgray'])
            lower, upper = result['requested_window_dose_bounds_microgray']
            self.assertLessEqual(lower, case['analytic_partial_dose_microgray'])
            self.assertGreaterEqual(upper, case['analytic_partial_dose_microgray'])

    def test_missing_exposure_has_no_finite_upper_bound_and_conflicts_are_rejected(self):
        case = build_demo()['fixtures'][4]
        result = case['accounting']
        self.assertEqual(result['covered_seconds'], 880)
        self.assertEqual(result['unobserved_seconds'], 120)
        self.assertEqual(result['complete_interval_dose_microgray'], Fraction(4, 9))
        self.assertEqual([(g['start_seconds'], g['end_seconds']) for g in result['gaps']],
                         [(400, 500), (940, 960)])
        self.assertEqual(result['requested_window_dose_bounds_microgray'], [Fraction(4, 9), None])
        totals = [item['full_window_dose_microgray'] for item in case['compatible_gap_completions']]
        self.assertEqual(totals, [Fraction(4, 9), Fraction(34, 9)])
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            account(case['conflicting_input'], RATE_UNIT)
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            regroup([interval(0, 1, 2), interval(2, 3, 2)])
        empty = account([], RATE_UNIT, [0, 10])
        self.assertEqual(empty['requested_window_dose_bounds_microgray'], [0, None])
        self.assertEqual(empty['unobserved_seconds'], 10)

    def test_independent_gain_and_known_clock_shift_keep_coverage_visible(self):
        case = build_demo()['fixtures'][5]
        self.assertEqual(case['frozen_gain_factor'], 2)
        self.assertEqual(case['held_out_scaled_dose_microgray'], Fraction(19, 18))
        self.assertEqual(case['gain_corrected_complete_span_dose_microgray'], Fraction(19, 36))
        restored = case['known_clock_corrected_accounting']
        self.assertEqual(restored['complete_interval_dose_microgray'], Fraction(19, 36))
        self.assertEqual(restored['covered_seconds'], 1000)
        scenarios = {item['applied_shift_seconds']: item['accounting'] for item in case['clock_scenarios']}
        self.assertEqual(scenarios[0]['covered_seconds'], 940)
        self.assertEqual(scenarios[0]['complete_interval_dose_microgray'], Fraction(13, 36))
        self.assertEqual(scenarios[-30]['constant_allocation_estimate_microgray'], Fraction(4, 9))
        self.assertEqual(scenarios[60]['covered_seconds'], 880)
        self.assertEqual(scenarios[60]['constant_allocation_estimate_microgray'], Fraction(11, 45))
        self.assertEqual(case['missing_exposure_after_gain_correction'], 120)
        for offset in [-60, 0, 60]:
            full = account(shifted([interval(0, 100, 2)], offset), RATE_UNIT)
            self.assertEqual(full['complete_interval_dose_microgray'], Fraction(1, 18))

    def test_invalid_rates_endpoints_units_overlap_and_order_are_rejected(self):
        for field in ['start_seconds', 'end_seconds', 'mean_rate']:
            for value in ['NaN', 'Infinity', '-Infinity', 'invalid', True]:
                row = interval(0, 1, 2)
                row[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    account([row], RATE_UNIT)
        for rows, message in [([interval(0, 1, -1)], 'negative rate'),
                              ([interval(1, 1, 2)], 'nonpositive duration'),
                              ([interval(2, 1, 2)], 'nonpositive duration'),
                              ([interval(0, 2, 1), interval(1, 3, 1)], 'Overlapping'),
                              ([interval(0, 2, 1), interval(0, 2, 1)], 'duplicate'),
                              ([interval(2, 3, 1), interval(0, 1, 1)], 'ordered')]:
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, message):
                account(rows, RATE_UNIT)
        for unit in ['microgray/second', 'microsievert/hour', '', None]:
            with self.subTest(unit=unit), self.assertRaisesRegex(ValueError, 'unit'):
                account([interval(0, 1, 2)], unit)
        for window in [[1, 0], [0, 'NaN'], [0], [0, 1, 2], '01']:
            with self.subTest(window=window), self.assertRaises(ValueError):
                account([interval(0, 1, 2)], RATE_UNIT, window)

    def test_cli_deterministic_regeneration_and_invalid_input_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for name in ['first', 'second']:
                subprocess.run([sys.executable, str(ROOT / 'interval_accounting.py'),
                                '--output-dir', str(folder / name)], check=True, capture_output=True, timeout=10)
            for name in ['results.json', 'REPORT.md']:
                self.assertEqual((folder / 'first' / name).read_bytes(),
                                 (folder / 'second' / name).read_bytes())
                self.assertEqual((folder / 'first' / name).read_bytes(),
                                 (ROOT / 'reports/interval-accounting' / name).read_bytes())
            source = folder / 'input.json'
            source.write_text(json.dumps({'rate_unit': RATE_UNIT, 'intervals':
                                         [interval(0, 10, 2), interval(5, 15, 3)]}))
            original = source.read_bytes()
            failed = subprocess.run([sys.executable, str(ROOT / 'interval_accounting.py'),
                                     '--input', str(source), '--output-dir', str(folder / 'invalid')],
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('Overlapping', failed.stderr)
            self.assertFalse((folder / 'invalid').exists())
            self.assertEqual(source.read_bytes(), original)
            source.write_text(json.dumps({'rate_unit': RATE_UNIT, 'intervals': [interval(0, 100, 36)],
                                         'window_seconds': [0, 50]}))
            original = source.read_bytes()
            subprocess.run([sys.executable, str(ROOT / 'interval_accounting.py'),
                            '--input', str(source), '--output-dir', str(folder / 'valid')],
                           check=True, capture_output=True, timeout=10)
            output = json.loads((folder / 'valid/results.json').read_text())
            self.assertEqual(output['constant_allocation_estimate_microgray'], '0.5')
            self.assertEqual(output['covered_support_dose_bounds_microgray'], ['0', '1'])
            self.assertEqual(output['partial_bin_allocation'], 'piecewise-constant assumption')
            self.assertEqual(source.read_bytes(), original)
            overwrite = folder / 'first/results.json'
            original = overwrite.read_bytes()
            failed = subprocess.run([sys.executable, str(ROOT / 'interval_accounting.py'),
                                     '--input', str(overwrite), '--output-dir', str(overwrite.parent)],
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('must not overwrite', failed.stderr)
            self.assertEqual(overwrite.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
