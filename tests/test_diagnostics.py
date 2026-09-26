import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from radlab_diagnostics import diagnose
from validate_intervals import audit

ROOT = Path(__file__).resolve().parents[1]


class DiagnosticTests(unittest.TestCase):
    def result(self, rows, header=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.csv'
            with path.open('w', newline='') as f:
                w = csv.writer(f)
                w.writerow(header or ['timestamp', 'instrument_id', 'absorbed_dose_rate'])
                w.writerows(rows)
            before = path.read_bytes()
            result = diagnose(path, 'DosTel1', '2022-04-01')
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(result['sha256'], hashlib.sha256(before).hexdigest())
            return result

    def rows(self):
        return [[f'2022-04-01T0{i}:00:00', 'DosTel1', 2] for i in range(3)]

    def test_constant_rate_exact_integral(self):
        result = self.result(self.rows())
        self.assertEqual(result['numerical_masking']['reported_series_trapezoid_microgray'], 4)
        self.assertEqual(result['numerical_masking']['block_masking_minutes']['30']['max_absolute_error_percent'], 0)

    def test_conflicting_duplicates_still_report_spacing(self):
        rows = self.rows() + [['2022-04-01T01:00:00', 'DosTel1', 3]]
        result = self.result(rows)
        self.assertEqual(result['conflicting_timestamp_count'], 1)
        self.assertEqual(result['duplicate_groups'][0]['rows'], [{'row': 3, 'rate': 2}, {'row': 5, 'rate': 3}])
        self.assertEqual(result['spacing_seconds']['median'], 3600)
        self.assertIsNone(result['numerical_masking'])

    def test_equal_duplicates_are_not_conflicting(self):
        result = self.result(self.rows() + [self.rows()[1]])
        self.assertEqual((result['duplicate_timestamp_count'], result['conflicting_timestamp_count']), (1, 0))
        self.assertIsNone(result['numerical_masking'])

    def test_bad_values_and_wrong_instrument_block_integration(self):
        for bad in ('NaN', 'inf', '-1', 'not-a-number'):
            with self.subTest(value=bad):
                result = self.result(self.rows() + [['2022-04-01T03:00:00', 'DosTel1', bad]])
                self.assertIsNone(result['numerical_masking'])
                self.assertIn('invalid_timestamp_or_rate', [i['kind'] for i in result['issues']])
        result = self.result(self.rows() + [['2022-04-01T03:00:00', 'DosTel2', 1]])
        self.assertIsNone(result['numerical_masking'])

    def test_bad_timestamp_row_and_schema(self):
        for row in (['bad-date', 'DosTel1', 2], ['2022-04-01T03:00:00', 'DosTel1'], ['2022-04-01T03:00:00', 'DosTel1', 2, 'extra']):
            self.assertIsNone(self.result(self.rows() + [row])['numerical_masking'])
        self.assertEqual(self.result([], ['wrong'])['issues'][0]['kind'], 'unexpected_schema')

    def test_mixed_timezone_blocks_integration(self):
        rows = self.rows()
        rows[0][0] += '+00:00'
        result = self.result(rows)
        self.assertEqual(result['timezone_convention'], 'mixed')
        self.assertIsNone(result['numerical_masking'])

    def test_equivalent_offsets_find_duplicate(self):
        rows = [['2022-04-01T01:00:00+01:00', 'DosTel1', 2],
                ['2022-04-01T00:00:00Z', 'DosTel1', 3],
                ['2022-04-01T02:00:00+00:00', 'DosTel1', 2]]
        self.assertEqual(self.result(rows)['conflicting_timestamp_count'], 1)

    def test_zero_short_outside_day(self):
        self.assertIsNone(self.result(self.rows()[:2])['numerical_masking'])
        self.assertIsNone(self.result([[r[0], r[1], 0] for r in self.rows()])['numerical_masking'])
        result = self.result(self.rows() + [['2022-04-02T00:00:00', 'DosTel1', 1]])
        self.assertIsNone(result['numerical_masking'])

    def test_source_order_retained_in_findings(self):
        result = self.result(list(reversed(self.rows())))
        self.assertEqual(result['out_of_order_transitions'], 2)
        self.assertEqual(result['numerical_masking']['reported_series_trapezoid_microgray'], 4)

    def test_cli_refuses_input_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'data.csv'
            p.write_text('timestamp,instrument_id,absorbed_dose_rate\n')
            before = p.read_bytes()
            run = subprocess.run([sys.executable, str(ROOT/'radlab_diagnostics.py'), '--input', str(p), '--output', str(p), '--instrument-id', 'DosTel1'], capture_output=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(p.read_bytes(), before)


class ReleaseTests(unittest.TestCase):
    def test_original_panel_reproduction(self):
        expected = [('DosTel1','2022-03-01',1202,4), ('DosTel2','2022-03-01',1187,0),
                    ('DosTel1','2022-04-01',1192,3), ('DosTel2','2022-04-01',1197,0)]
        for instrument, day, count, conflicts in expected:
            result = diagnose(ROOT/'data/radlab'/f'{instrument.lower()}-{day}.csv', instrument, day)
            self.assertEqual((result['source_rows'], result['conflicting_timestamp_count']), (count, conflicts))
        march = diagnose(ROOT/'data/radlab/dostel2-2022-03-01.csv', 'DosTel2')
        april = diagnose(ROOT/'data/radlab/dostel2-2022-04-01.csv', 'DosTel2')
        self.assertEqual(round(march['numerical_masking']['block_masking_minutes']['30']['max_absolute_error_percent'],2), 21.69)
        self.assertEqual(round(april['numerical_masking']['block_masking_minutes']['30']['max_absolute_error_percent'],2), 21.25)

    def test_midnight_synthetic_example_and_cli(self):
        inputs = sorted((ROOT/'examples/annotations').glob('*.csv'))
        before = {p: p.read_bytes() for p in inputs}
        result = audit(inputs)
        self.assertEqual(result['issues'], [])
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(result['candidates'][0]['gap_seconds'], 50)
        self.assertEqual(result['candidates'][0]['annotator'], 'example-A')
        self.assertEqual(len(audit(inputs, 10)['candidates']), 0)
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(ROOT/'validate_intervals.py'), '--input', str(ROOT/'examples/annotations'), '--output-dir', tmp], check=True, capture_output=True)
            actual = json.loads((Path(tmp)/'audit_results.json').read_text())
            self.assertEqual(actual['candidates'], result['candidates'])
        self.assertEqual(before, {p: p.read_bytes() for p in inputs})

    def test_bad_window_and_schema(self):
        for window in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                audit([], window)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.csv'
            p.write_text('wrong\nvalue\n')
            self.assertEqual(audit([p])['issues'][0]['kind'], 'unexpected_schema')
            p.write_text('annotator,date,start,end,label\nA,2022-04-01\n')
            self.assertEqual(audit([p])['issues'][0]['kind'], 'malformed_row')

    def test_source_hashes(self):
        manifest = json.loads((ROOT/'reports/source_manifest.json').read_text())
        self.assertEqual(len(manifest['sources']), 18)
        for source in manifest['sources']:
            self.assertEqual(hashlib.sha256((ROOT/'data/radlab'/source['file']).read_bytes()).hexdigest(), source['sha256'])


if __name__ == '__main__':
    unittest.main()
