import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

from review_neighbors import ROOT, parse_timestamp, review, write_outputs


@contextmanager
def source_case(rows, content=None):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'case.csv'
        if content is None:
            buffer = io.StringIO(newline='')
            writer = csv.writer(buffer)
            writer.writerow(['timestamp', 'instrument_id', 'absorbed_dose_rate'])
            writer.writerows(rows)
            content = buffer.getvalue()
        path.write_text(content, encoding='utf-8')
        source = {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'instrument_id': 'DosTel1', 'day': '2022-04-01', 'source_url': 'synthetic'}
        yield Path(folder), {'sources': [source]}, path


def reading(seconds, rate):
    return ['2022-04-01T00:00:' + seconds, 'DosTel1', rate]


class NeighborReviewTests(unittest.TestCase):
    def test_irregular_interpolation_preserves_source_values(self):
        rows = [reading('00', '1'), reading('10', '2.000'),
                reading('10', '4.5'), reading('30', '7')]
        with source_case(rows) as (folder, manifest, path):
            original = path.read_bytes()
            groups, summary = review(folder, manifest)
            group = groups[0]
            self.assertEqual(group['source_rows'], [3, 4])
            self.assertEqual(group['rates_microgray_per_hour'], ['2.000', '4.5'])
            self.assertEqual(group['expected_from_trend_microgray_per_hour'], '3')
            self.assertEqual(group['absolute_differences_microgray_per_hour'], ['1', '1.5'])
            self.assertEqual(group['closest_source_rows'], [3])
            self.assertEqual(group['pre_gap_seconds'], '10')
            self.assertEqual(group['post_gap_seconds'], '20')
            self.assertEqual(group['typical_gap_seconds_this_file'], '15')
            self.assertEqual(summary['closest_source_position_counts'], {'1': 1})
            self.assertEqual(group['timezone_convention'], 'not_supplied')
            self.assertEqual(group['sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(path.read_bytes(), original)

    def test_ties_and_more_than_two_readings(self):
        for rates, positions, status in [(['1', '3', '3.0'], [1, 2, 3], 'tied'),
                                         (['10', '3', '2'], [3], 'compared')]:
            with self.subTest(rates=rates), source_case(
                    [reading('00', '0')] + [reading('10', r) for r in rates] + [reading('20', '4')]) as (folder, manifest, _):
                groups, summary = review(folder, manifest)
                self.assertEqual(groups[0]['closest_source_positions'], positions)
                self.assertEqual(groups[0]['comparison_status'], status)
                self.assertEqual(summary['tied_groups'], int(status == 'tied'))
                self.assertEqual(summary['readings_in_differing_rate_groups'], 3)

    def test_missing_and_conflicting_neighbors_remain_unavailable(self):
        examples = [
            ([reading('10', '1'), reading('10', '3'), reading('20', '2')], ['missing_before']),
            ([reading('00', '2'), reading('10', '1'), reading('10', '3')], ['missing_after']),
            ([reading('10', '1'), reading('10', '3')], ['missing_before', 'missing_after']),
            ([reading('00', '1'), reading('00', '3'), reading('10', '2'),
              reading('10', '4'), reading('20', '5')], ['conflicting_before']),
            ([reading('00', '0'), reading('10', '1'), reading('10', '3'),
              reading('20', '2'), reading('20', '4')], ['conflicting_after']),
        ]
        for rows, blockers in examples:
            with self.subTest(blockers=blockers), source_case(rows) as (folder, manifest, _):
                groups, _ = review(folder, manifest)
                group = next(g for g in groups if g['timestamps_as_recorded'][0].endswith('10'))
                self.assertEqual(group['comparison_blockers'], blockers)
                self.assertEqual(group['comparison_status'], 'unavailable')
                self.assertIsNone(group['expected_from_trend_microgray_per_hour'])
                self.assertEqual(group['closest_source_rows'], [])

    def test_identical_neighbor_rates_are_unambiguous_and_retained(self):
        with source_case([reading('00', '1.0'), reading('00', '1'), reading('10', '2'),
                          reading('10', '9'), reading('20', '3')]) as (folder, manifest, _):
            groups, summary = review(folder, manifest)
            self.assertEqual(groups[0]['before']['source_rows'], [2, 3])
            self.assertEqual(groups[0]['before']['rates_microgray_per_hour'], ['1.0', '1'])
            self.assertEqual(groups[0]['comparison_status'], 'compared')
            self.assertEqual(groups[0]['expected_from_trend_microgray_per_hour'], '2')
            self.assertEqual(summary['source_rows'], 5)

    def test_fractional_timestamps_offsets_and_source_order(self):
        left, aware = parse_timestamp('2022-04-01T00:00:00.000000001Z')
        right, _ = parse_timestamp('2022-04-01T00:00:00.000000002+00:00')
        self.assertTrue(aware)
        self.assertEqual(right - left, Fraction(1, 10 ** 9))
        rows = [
            ['2022-04-01T00:00:20Z', 'DosTel1', '4'],
            ['2022-04-01T01:00:10+01:00', 'DosTel1', '2.00'],
            ['2022-04-01T00:00:00Z', 'DosTel1', '0'],
            ['2022-04-01T00:00:10Z', 'DosTel1', '9'],
        ]
        with source_case(rows) as (folder, manifest, _):
            groups, summary = review(folder, manifest)
            self.assertEqual(groups[0]['source_rows'], [3, 5])
            self.assertEqual(groups[0]['timestamps_as_recorded'], [rows[1][0], rows[3][0]])
            self.assertEqual(groups[0]['pre_gap_seconds'], '10')
            self.assertEqual(groups[0]['expected_from_trend_microgray_per_hour'], '2')
            self.assertEqual(summary['cases'][0]['out_of_order_transitions'], 2)
        rows[0][0] = '2022-04-01T00:00:20'
        with source_case(rows) as (folder, manifest, _):
            with self.assertRaisesRegex(ValueError, 'Mixed timezone'):
                review(folder, manifest)

    def test_invalid_inputs_hashes_and_duplicate_manifest_entries(self):
        for rate in ['NaN', 'Infinity', '-1', 'invalid']:
            with self.subTest(rate=rate), source_case([reading('00', rate)]) as (folder, manifest, _):
                with self.assertRaisesRegex(ValueError, 'Invalid rate'):
                    review(folder, manifest)
        for stamp in ['2022-04-01T00:00', '2022-04-01T00:00:60', '2022-04-01T00:00:00+00:60']:
            with self.subTest(stamp=stamp), source_case([[stamp, 'DosTel1', '1']]) as (folder, manifest, _):
                with self.assertRaises(ValueError):
                    review(folder, manifest)
        for row in [['2022-04-01T00:00:00', 'other', '1'], ['2022-04-02T00:00:00', 'DosTel1', '1']]:
            with self.subTest(row=row), source_case([row]) as (folder, manifest, _):
                with self.assertRaisesRegex(ValueError, 'mismatch'):
                    review(folder, manifest)
        for content, message in [('timestamp,instrument_id,absorbed_dose_rate\n2022-04-01T00:00:00,DosTel1\n', 'Malformed'),
                                 ('timestamp,rate\n', 'schema')]:
            with self.subTest(content=content), source_case([], content=content) as (folder, manifest, _):
                with self.assertRaisesRegex(ValueError, message):
                    review(folder, manifest)
        with source_case([reading('00', '1')]) as (folder, manifest, path):
            with self.assertRaisesRegex(ValueError, 'Duplicate source'):
                review(folder, {'sources': manifest['sources'] * 2})
            path.write_bytes(path.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'Source hash changed'):
                review(folder, manifest)

    def test_empty_sources_and_deterministic_json_csv_exports(self):
        with source_case([]) as (folder, manifest, _):
            groups, summary = review(folder, manifest)
            self.assertEqual(groups, [])
            self.assertIsNone(summary['median_pre_gap_vs_typical'])
            write_outputs(folder / 'out', groups, summary)
            self.assertEqual(json.loads((folder / 'out/neighboring_sample_groups.json').read_text()), [])
        with source_case([reading('00', '0'), reading('10', '2.00'), reading('10', '9'),
                          reading('20', '4')]) as (folder, manifest, _):
            groups, summary = review(folder, manifest)
            for output in ['first', 'second']:
                write_outputs(folder / output, groups, summary)
            for path in (folder / 'first').iterdir():
                self.assertEqual(path.read_bytes(), (folder / 'second' / path.name).read_bytes())
            self.assertEqual(json.loads((folder / 'first/neighboring_sample_groups.json').read_text()), groups)
            with (folder / 'first/neighboring_sample_groups.csv').open(newline='') as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(json.loads(row['source_rows']), [3, 4])
            self.assertEqual(json.loads(row['rates_microgray_per_hour']), ['2.00', '9'])
            self.assertEqual(json.loads(row['before']), groups[0]['before'])

    def test_fixed_snapshot_results_and_manifest_order_independence(self):
        manifest = json.loads((ROOT / 'reports/source_manifest.json').read_text())
        groups, summary = review(ROOT / 'data/radlab', manifest)
        self.assertEqual(summary['source_cases'], 18)
        self.assertEqual(summary['source_rows'], 21500)
        self.assertEqual(summary['differing_rate_groups'], 58)
        self.assertEqual(summary['readings_in_differing_rate_groups'], 116)
        self.assertEqual(summary['comparable_groups'], 58)
        self.assertEqual(summary['unavailable_groups'], 0)
        self.assertEqual(summary['tied_groups'], 0)
        self.assertEqual(summary['closest_source_position_counts'], {'1': 53, '2': 5})
        self.assertEqual(summary['instrument_days_with_differing_rates'], 16)
        self.assertEqual(summary['calendar_days_with_differing_rates'], 9)
        self.assertAlmostEqual(float(summary['median_pre_gap_vs_typical']), 1.14, places=2)
        self.assertAlmostEqual(float(summary['median_post_gap_vs_typical']), 1.14, places=2)
        reversed_manifest = {'sources': list(reversed(manifest['sources']))}
        self.assertEqual(review(ROOT / 'data/radlab', reversed_manifest), (groups, summary))

    def test_cli_refuses_to_overwrite_manifest(self):
        with source_case([reading('00', '1')]) as (folder, manifest, _):
            path = folder / 'neighboring_sample_summary.json'
            path.write_text(json.dumps(manifest))
            original = path.read_bytes()
            result = subprocess.run([sys.executable, str(ROOT / 'review_neighbors.py'),
                                     '--data-dir', str(folder), '--manifest', str(path),
                                     '--output-dir', str(folder)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Outputs must not overwrite inputs', result.stderr)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse((folder / 'neighboring_sample_groups.csv').exists())


if __name__ == '__main__':
    unittest.main()
