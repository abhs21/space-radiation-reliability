import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from review_timestamps import ROOT, on_five_minute_boundary, review


class TimestampReviewTests(unittest.TestCase):
    def test_boundary_and_fractional_seconds(self):
        for stamp in ('2022-04-01T09:10:00', '2022-04-01T00:00:00.000000', '2022-04-01T09:10:00+00:01'):
            self.assertTrue(on_five_minute_boundary(stamp))
        for stamp in ('2022-04-01T09:11:00', '2022-04-01T09:10:01', '2022-04-01T09:10:00.0000001', '2022-04-01T23:59:59.999999'):
            self.assertFalse(on_five_minute_boundary(stamp))
        with self.assertRaises(ValueError):
            on_five_minute_boundary('2022-04-01T09:10')

    def test_quoted_csv_preserves_rows_rates_and_hash_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'case.csv'
            path.write_text('timestamp,instrument_id,absorbed_dose_rate\n"2022-04-01T09:10:00","DosTel1",1.000\n"2022-04-01T09:10:00","DosTel1",2.500\n"2022-04-01T09:11:00","DosTel1",3\n"2022-04-01T09:11:00","DosTel1",3.0\n')
            source = {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'instrument_id': 'DosTel1', 'day': '2022-04-01', 'source_url': 'synthetic'}
            groups, summary = review(folder, {'sources': [source]})
            self.assertEqual(len(groups), 1)
            self.assertEqual(json.loads(groups[0]['source_rows_json']), [2, 3])
            self.assertEqual(json.loads(groups[0]['rates_microgray_per_hour_json']), ['1.000', '2.500'])
            self.assertEqual(summary['unique_recorded_timestamps'], 2)
            self.assertEqual(summary['five_minute_aligned_unique_timestamps'], 1)
            path.write_text(path.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'Source hash changed'):
                review(folder, {'sources': [source]})

    def test_fixed_snapshot_counts_and_every_group_against_source(self):
        manifest = json.loads((ROOT / 'reports/source_manifest.json').read_text())
        groups, summary = review(ROOT / 'data/radlab', manifest)
        self.assertEqual([summary[k] for k in ('source_cases', 'source_rows', 'differing_rate_groups', 'readings_in_differing_rate_groups', 'five_minute_aligned_differing_rate_groups', 'unique_recorded_timestamps', 'five_minute_aligned_unique_timestamps')], [18, 21500, 58, 116, 58, 21442, 5176])
        for group in groups:
            with (ROOT / 'data/radlab' / group['source_file']).open(newline='') as f:
                rows = list(csv.DictReader(f))
            for number, value in zip(json.loads(group['source_rows_json']), json.loads(group['rates_microgray_per_hour_json'])):
                self.assertEqual(rows[number - 2]['timestamp'], group['timestamp_as_recorded'])
                self.assertEqual(rows[number - 2]['absorbed_dose_rate'], value)


if __name__ == '__main__':
    unittest.main()
