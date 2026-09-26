import csv
import tempfile
import unittest
from pathlib import Path
from validate_intervals import audit


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



if __name__ == '__main__':
    unittest.main()
