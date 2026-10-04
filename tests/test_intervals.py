import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from validate_intervals import BASE, audit


class AuditTests(unittest.TestCase):
    def run_rows(self, rows, window=600):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '2020-12-10_test.csv'
            with path.open('w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['annotator', 'date', 'start', 'end', 'label'])
                w.writerows(rows)
            return audit([path], window)

    def row(self, start, end, name='A'):
        return [name, '2020-12-10', '2020-12-10T' + start + '+00:00', '2020-12-10T' + end + '+00:00', 'SAA']

    def test_duplicates_nested_overlap_and_separate_annotators(self):
        rows = [self.row('01:00:00', '02:00:00'), self.row('01:00:00', '02:00:00'), self.row('01:10:00', '01:20:00'), self.row('01:00:00', '02:00:00', 'B')]
        result = self.run_rows(rows)
        kinds = [i['kind'] for i in result['issues']]
        self.assertEqual(kinds.count('duplicate_interval'), 1)
        self.assertEqual(kinds.count('overlapping_interval'), 2)

    def test_invalid_timezone_duration_and_touching(self):
        rows = [self.row('01:00:00', '02:00:00'), self.row('02:00:00', '03:00:00'), self.row('04:00:00', '04:00:00')]
        bad = self.row('05:00:00', '06:00:00')
        bad[2] = bad[2].replace('+00:00', '')
        result = self.run_rows(rows + [bad])
        self.assertEqual({i['kind'] for i in result['issues']}, {'nonpositive_duration', 'invalid_date_or_timezone'})

    def test_order_and_declared_day(self):
        rows = [self.row('02:00:00', '03:00:00'), self.row('00:00:00', '01:00:00')]
        rows[0][1] = '2020-12-09'
        kinds = {i['kind'] for i in self.run_rows(rows)['issues']}
        self.assertEqual(kinds, {'out_of_order_start', 'filename_date_mismatch', 'outside_declared_utc_day'})

    def test_nanosecond_duration_and_equivalent_zulu_offsets(self):
        rows = [self.row('00:00:00.000000001', '00:00:00.000000002')]
        offset = self.row('01:00:00.000000001', '01:00:00.000000002')
        offset[2] = offset[2].replace('+00:00', '+01:00')
        offset[3] = offset[3].replace('+00:00', '+01:00')
        rows.append(offset)
        rows[0][2] = rows[0][2].replace('+00:00', 'Z')
        rows[0][3] = rows[0][3].replace('+00:00', 'Z')
        result = self.run_rows(rows)
        self.assertEqual(result['valid_parsed_intervals'], 2)
        self.assertEqual(result['candidate_eligible_intervals'], 2)
        self.assertEqual([issue['kind'] for issue in result['issues']], ['duplicate_interval'])

    def test_existing_minute_space_comma_and_compact_offset_formats(self):
        for start, end in [('2020-12-10T01:00+00:00', '2020-12-10T01:01+00:00'),
                           ('2020-12-10 01:00:00+0000', '2020-12-10 01:01:00+00'),
                           ('2020-12-10T01:00:00,000000001Z', '2020-12-10T01:00:00,000000002Z')]:
            with self.subTest(start=start):
                result = self.run_rows([['A', '2020-12-10', start, end, 'SAA']])
                self.assertEqual(result['valid_parsed_intervals'], 1)
                self.assertEqual(result['candidate_eligible_intervals'], 1)
                self.assertEqual(result['issues'], [])

    def test_submicrosecond_overlap_touching_and_source_order(self):
        rows = [self.row('00:00:00.000000003', '00:00:00.000000005'),
                self.row('00:00:00.000000001', '00:00:00.000000002'),
                self.row('00:00:00.000000002', '00:00:00.000000004')]
        result = self.run_rows(rows)
        self.assertEqual(result['valid_parsed_intervals'], 3)
        kinds = [issue['kind'] for issue in result['issues']]
        self.assertEqual(kinds.count('out_of_order_start'), 1)
        self.assertEqual(kinds.count('overlapping_interval'), 1)
        self.assertNotIn('duplicate_interval', kinds)
        self.assertNotIn('nonpositive_duration', kinds)

    def test_fractional_offset_uses_declared_utc_day(self):
        row = ['A', '2020-12-10', '2020-12-09T23:59:59.999999999-00:01',
               '2020-12-10T00:00:00.000000001-00:01', 'SAA']
        result = self.run_rows([row])
        self.assertEqual(result['valid_parsed_intervals'], 1)
        self.assertEqual(result['candidate_eligible_intervals'], 1)
        self.assertEqual(result['issues'], [])

    def write_daily(self, folder, day, start, end, annotator='A', label='SAA', filename=None):
        path = Path(folder) / (filename or day + '_test.csv')
        with path.open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['annotator', 'date', 'start', 'end', 'label'])
            writer.writerow([annotator, day, day + 'T' + start + 'Z', day + 'T' + end + 'Z', label])
        return path

    def test_nanosecond_midnight_gap_and_exact_window(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write_daily(folder, '2020-12-10', '23:59:50', '23:59:59.999999999')
            right = self.write_daily(folder, '2020-12-11', '00:00:00.000000001', '00:00:10')
            original = {path: path.read_bytes() for path in (left, right)}
            result = audit([left, right], 1e-9)
            self.assertEqual(result['issues'], [])
            self.assertEqual(len(result['candidates']), 1)
            candidate = result['candidates'][0]
            self.assertEqual(candidate['gap_seconds'], 2e-9)
            self.assertEqual(candidate['gap_seconds_exact'], '1/500000000')
            self.assertTrue(candidate['left_end'].endswith('999999999Z'))
            self.assertEqual(len(audit([left, right], 0)['candidates']), 0)
            self.assertEqual(original, {path: path.read_bytes() for path in (left, right)})

    def test_one_nanosecond_beyond_midnight_window_is_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            left = self.write_daily(folder, '2020-12-10', '23:59:30', '23:59:59')
            right = self.write_daily(folder, '2020-12-11', '00:10:00.000000001', '00:11:00')
            self.assertEqual(len(audit([left, right], 600)['candidates']), 0)
            self.write_daily(folder, '2020-12-11', '00:10:00', '00:11:00')
            self.assertEqual(len(audit([left, right], 600)['candidates']), 1)

    def test_invalid_annotation_metadata_cannot_create_midnight_candidate(self):
        examples = [({'label': 'INVALID'}, 'unexpected_annotator_or_label'),
                    ({'annotator': ' '}, 'unexpected_annotator_or_label'),
                    ({'filename': 'wrong.csv'}, 'filename_date_mismatch')]
        for options, kind in examples:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                left_options, right_options = dict(options), dict(options)
                if 'filename' in options:
                    left_options['filename'] = 'wrong-left.csv'
                    right_options['filename'] = 'wrong-right.csv'
                left = self.write_daily(folder, '2020-12-10', '23:59:30', '23:59:50', **left_options)
                right = self.write_daily(folder, '2020-12-11', '00:00:10', '00:02:00', **right_options)
                result = audit([left, right])
                self.assertEqual(result['valid_parsed_intervals'], 2)
                self.assertEqual(result['candidate_eligible_intervals'], 0)
                self.assertEqual(result['candidates'], [])
                self.assertEqual([issue['kind'] for issue in result['issues']], [kind, kind])

    def test_nanosecond_cli_json_and_csv_agree(self):
        with tempfile.TemporaryDirectory() as folder:
            inputs = Path(folder) / 'inputs'
            inputs.mkdir()
            self.write_daily(inputs, '2020-12-10', '23:59:50', '23:59:59.999999999')
            self.write_daily(inputs, '2020-12-11', '00:00:00.000000001', '00:00:10')
            output = Path(folder) / 'output'
            subprocess.run([sys.executable, str(BASE / 'validate_intervals.py'), '--input', str(inputs),
                            '--output-dir', str(output), '--window-seconds', '0.000000001'],
                           check=True, capture_output=True, text=True)
            result = json.loads((output / 'audit_results.json').read_text())
            with (output / 'flagged_intervals.csv').open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(result['candidate_eligible_intervals'], 2)
            self.assertEqual(rows[0]['gap_seconds_exact'], '1/500000000')
            self.assertEqual(rows[0]['gap_seconds_exact'], result['candidates'][0]['gap_seconds_exact'])
            self.assertEqual(float(rows[0]['gap_seconds']), result['candidates'][0]['gap_seconds'])



if __name__ == '__main__':
    unittest.main()
