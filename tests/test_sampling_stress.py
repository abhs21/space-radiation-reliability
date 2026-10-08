import csv
import tempfile
import unittest
from unittest.mock import patch
from fractions import Fraction
from pathlib import Path

from radlab_coverage import audit, load_series, trapezoid_area
from radlab_diagnostics import diagnose
from timestamp_utils import format_timestamp, parse_timestamp
from run_stress_test import acquire, digest, report, study_case


class SamplingStressTests(unittest.TestCase):
    def inspect(self, timestamps, rates=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'series.csv'
            with path.open('w', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(['timestamp', 'instrument_id', 'absorbed_dose_rate'])
                writer.writerows((stamp, 'DosTel1', rate) for stamp, rate in
                                 zip(timestamps, rates or [2] * len(timestamps)))
            result = diagnose(path, 'DosTel1')
            rows = load_series(path, 'DosTel1') if not result['integration_exclusion_reasons'] else None
            return result, rows

    def test_nanoseconds_are_distinct_in_both_readers(self):
        result, rows = self.inspect(['2022-04-01T00:00:00.000000001',
                                     '2022-04-01T00:00:00.000000002',
                                     '2022-04-01T00:00:01'])
        self.assertEqual(result['parsed_rows'], 3)
        self.assertEqual(result['duplicate_timestamp_count'], 0)
        self.assertEqual(result['spacing_seconds']['min'], 1e-9)
        self.assertEqual(rows[1][0] - rows[0][0], Fraction(1, 10**9))
        self.assertEqual(result['first_timestamp'], '2022-04-01T00:00:00.000000001')
        self.assertAlmostEqual(trapezoid_area(rows), 2 * (1 - 1e-9) / 3600)

    def test_nanosecond_offset_equivalence_and_genuine_duplicate(self):
        result, _ = self.inspect(['2022-04-01T01:00:00.000000001+01:00',
                                  '2022-04-01T00:00:00.000000001Z',
                                  '2022-04-01T00:00:01Z'], [1, 2, 1])
        self.assertEqual(result['conflicting_timestamp_count'], 1)
        self.assertEqual(result['duplicate_groups'][0]['timestamp'],
                         '2022-04-01T00:00:00.000000001+00:00')
        self.assertEqual([row['row'] for row in result['duplicate_groups'][0]['rows']], [2, 3])
        self.assertIsNone(result['numerical_masking'])

    def test_offsets_integrate_on_one_common_timeline(self):
        result, rows = self.inspect(['2022-04-01T01:00:00+01:00',
                                     '2022-04-01T01:00:00Z',
                                     '2022-04-01T03:00:00+01:00'])
        self.assertEqual(result['numerical_masking']['reported_series_trapezoid_microgray'], 4)
        self.assertEqual(trapezoid_area(rows), 4)

    def test_mixed_conventions_excluded(self):
        result, _ = self.inspect(['2022-04-01T00:00:00Z',
                                  '2022-04-01T01:00:00', '2022-04-01T02:00:00'])
        self.assertEqual(result['timezone_convention'], 'mixed')
        self.assertIsNone(result['numerical_masking'])

    def test_exact_roundtrip_before_epoch_and_beyond_nanoseconds(self):
        for text in ('1969-12-31T23:59:59.999999999Z',
                     '2022-04-01T00:00:00.' + '0' * 65 + '1'):
            seconds, aware = parse_timestamp(text)
            self.assertEqual(parse_timestamp(format_timestamp(seconds, aware)), (seconds, aware))

    def test_adaptive_cadence_does_not_invalidate_constant_signal(self):
        offsets = [0, 100, 200, 220, 240, 340, 440]
        stamps = [format_timestamp(parse_timestamp('2022-04-01T00:00:00')[0] + n) for n in offsets]
        result, _ = self.inspect(stamps)
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['status'], 'numerical_reported_series_only')
        self.assertAlmostEqual(result['numerical_masking']['reported_series_trapezoid_microgray'], 2 * 440 / 3600)

    def test_constant_and_linear_signals_survive_all_prescribed_masks(self):
        for linear in (False, True):
            rows = [(Fraction(n * 60), 2 + n / 60 if linear else 2) for n in range(241)]
            result = audit(rows, 'synthetic', phase_offsets=(0, 10, 20))
            self.assertAlmostEqual(result['reported_series_trapezoid_microgray'], 16 if linear else 8)
            for lengths in result['phase_masking'].values():
                for item in lengths.values():
                    self.assertEqual(item['empty_blocks'], 0)
                    self.assertEqual(item['summary']['cases'], len(item['all_cases']))
                    self.assertLess(item['summary']['max_absolute_error_percent'], 1e-10)

    def test_empty_masks_are_recorded(self):
        rows = [(Fraction(n * 3600), 2) for n in range(5)]
        item = audit(rows, 'sparse', phase_offsets=(0,))['phase_masking']['0']['5']
        self.assertGreater(item['empty_blocks'], 0)
        self.assertEqual(len(item['all_cases']), item['empty_blocks'] + item['summary']['cases'])

    def test_peak_sensitivity_depends_on_mask_phase(self):
        rows = [(Fraction(n * 60), 100 if n == 65 else 1) for n in range(241)]
        result = audit(rows, 'peak', phase_offsets=(0, 10, 20))
        zero = result['phase_masking']['0']['15']['summary']['max_absolute_error_percent']
        ten = result['phase_masking']['10']['15']['summary']['max_absolute_error_percent']
        self.assertGreater(zero, 0)
        self.assertNotEqual(zero, ten)

    def test_unobserved_peak_has_no_bound_from_retained_readings(self):
        observed = [(Fraction(0), 1), (Fraction(3600), 1)]
        reference = trapezoid_area(observed)
        for height in (10, 1000, 10**9):
            possible = [observed[0], (Fraction(1800), height), observed[1]]
            self.assertGreater(trapezoid_area(possible), reference)
            self.assertEqual([possible[0], possible[-1]], observed)
            self.assertEqual(trapezoid_area(possible), (height + 1) / 2)

    def test_empty_response_is_preserved_and_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / 'empty.csv'
            path.write_text('timestamp,instrument_id,absorbed_dose_rate\n\n')
            source = {'file': path.name, 'instrument_id': 'DosTel1', 'day': '2022-05-01',
                      'source_url': 'https://example.invalid', 'sha256': digest(path)}
            result = study_case(source, folder, 'extension28', (0, 10, 20))
            self.assertEqual(result['analysis_status'], 'empty_response')
            self.assertEqual(result['diagnostics']['source_rows'], 0)
            self.assertIsNone(result['phase_analysis'])

    def test_unavailable_report_does_not_claim_empty_responses(self):
        case = {'file': 'missing.csv', 'instrument_id': 'DosTel1', 'day': '2022-05-01',
                'panel': 'extension28', 'analysis_status': 'unavailable',
                'phase_analysis': None, 'reason': 'request failed'}
        text = report({'cases': [case], 'protocol_sha256': 'test',
                       'protocol': {'phase_offsets_minutes': [0, 10, 20]}})
        self.assertIn('0 of 1 planned new queries have frozen header-only responses', text)
        self.assertNotIn('A separately recorded control request', text)

    def test_failed_acquisition_stays_in_panel_without_retry_on_reproduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('run_stress_test.download_one', side_effect=RuntimeError('two attempts failed')) as download:
                result = acquire(('DosTel1', '2022-05-01'), Path(tmp), {}, True)
                self.assertEqual(result['status'], 'unavailable')
                again = acquire(('DosTel1', '2022-05-01'), Path(tmp), {result['file']: result}, True)
                self.assertEqual(result, again)
                download.assert_called_once()

    def test_changed_snapshot_stops_instead_of_redownloading(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / 'dostel1-2022-05-01.csv'
            path.write_text('original')
            record = {'file': path.name, 'status': 'downloaded', 'sha256': digest(path)}
            path.write_text('changed')
            with patch('run_stress_test.download_one') as download:
                with self.assertRaisesRegex(ValueError, 'Source hash changed'):
                    acquire(('DosTel1', '2022-05-01'), folder, {path.name: record}, True)
                download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
