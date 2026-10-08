import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path

from build_review_packet import ROOT, build_packet, render_html, write_packet


class EmbeddedPacketParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.script_ids = []
        self.in_data = False
        self.data = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            identity = dict(attrs).get('id')
            self.script_ids.append(identity)
            self.in_data = identity == 'packet-data'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_data = False

    def handle_data(self, data):
        if self.in_data:
            self.data += data


class ReviewPacketTests(unittest.TestCase):
    def source(self, folder):
        path = Path(folder) / 'case.csv'
        with path.open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['timestamp', 'instrument_id', 'absorbed_dose_rate'])
            for seconds, rate in [('00', '1'), ('10', '2.000'), ('10', '9'),
                                  ('20', '3'), ('30', '4'), ('30', '20'), ('40', '5')]:
                writer.writerow(['2022-04-01T00:00:' + seconds, 'DosTel1', rate])
        manifest = {'sources': [{'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                 'instrument_id': 'DosTel1', 'day': '2022-04-01', 'source_url': 'synthetic'}]}
        return path, manifest

    def test_rank_preserves_all_source_rows_rates_and_exact_spread(self):
        with tempfile.TemporaryDirectory() as folder:
            path, manifest = self.source(folder)
            original = path.read_bytes()
            packet = build_packet(folder, manifest)
            first, second = packet['groups']
            self.assertEqual(first['rate_range_microgray_per_hour'], '16')
            self.assertEqual(first['source_rows'], [6, 7])
            self.assertEqual(first['rates_microgray_per_hour'], ['4', '20'])
            self.assertEqual(second['rates_microgray_per_hour'], ['2.000', '9'])
            self.assertEqual(packet['summary']['source_rows'], 7)
            self.assertIn('/' + manifest['sources'][0]['sha256'] + '/6,7', first['group_key'])
            self.assertEqual(path.read_bytes(), original)

    def test_untrusted_text_cannot_escape_embedded_data(self):
        with tempfile.TemporaryDirectory() as folder:
            _, manifest = self.source(folder)
            packet = build_packet(folder, manifest)
            malicious = '</script><script>alert(1)</script>&'
            packet['groups'][0]['source_file'] = malicious
            packet['groups'][0]['source_url'] = 'javascript:alert(1)'
            output = render_html(packet)
            self.assertNotIn(malicious, output)
            parser = EmbeddedPacketParser()
            parser.feed(output)
            self.assertEqual(len(parser.script_ids), 2)
            self.assertEqual(json.loads(parser.data), packet)
            self.assertNotIn('src=', output)
            self.assertIn("['https:','http:']", output)

    def test_packet_exports_are_deterministic_and_preserve_empty_cases(self):
        with tempfile.TemporaryDirectory() as folder:
            _, manifest = self.source(folder)
            packet = build_packet(folder, manifest)
            for name in ['first', 'second']:
                write_packet(Path(folder) / name, packet)
            for path in (Path(folder) / 'first').iterdir():
                self.assertEqual(path.read_bytes(), (Path(folder) / 'second' / path.name).read_bytes())
            self.assertEqual(json.loads((Path(folder) / 'first/review_packet.json').read_text()), packet)
            self.assertIn('CSV row(s)', (Path(folder) / 'first/REVIEW.md').read_text())
            empty = build_packet(folder, {'sources': []})
            write_packet(Path(folder) / 'empty', empty)
            self.assertEqual(json.loads((Path(folder) / 'empty/review_packet.json').read_text())['groups'], [])

    def test_cli_hash_change_does_not_write_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            source, manifest = self.source(folder)
            manifest_path = Path(folder) / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest))
            source.write_bytes(source.read_bytes() + b'\n')
            output = Path(folder) / 'output'
            result = subprocess.run([sys.executable, str(ROOT / 'build_review_packet.py'),
                                     '--data-dir', folder, '--manifest', str(manifest_path),
                                     '--output-dir', str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Source hash changed', result.stderr)
            self.assertFalse(output.exists())

    def test_cli_refuses_manifest_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            _, manifest = self.source(folder)
            path = Path(folder) / 'review_packet.json'
            path.write_text(json.dumps(manifest))
            original = path.read_bytes()
            result = subprocess.run([sys.executable, str(ROOT / 'build_review_packet.py'),
                                     '--data-dir', folder, '--manifest', str(path),
                                     '--output-dir', folder], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Outputs must not overwrite inputs', result.stderr)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse((Path(folder) / 'review_packet.html').exists())

    def test_full_snapshot_coverage_source_evidence_and_stable_order(self):
        manifest = json.loads((ROOT / 'reports/source_manifest.json').read_text())
        packet = build_packet(ROOT / 'data/radlab', manifest)
        self.assertEqual(packet['summary']['source_cases'], 18)
        self.assertEqual(packet['summary']['source_rows'], 21500)
        self.assertEqual(len(packet['groups']), 58)
        self.assertEqual(sum(c['differing_rate_groups'] == 0 for c in packet['summary']['cases']), 2)
        self.assertEqual(packet, build_packet(ROOT / 'data/radlab', {'sources': list(reversed(manifest['sources']))}))
        source_rows = {}
        for source in manifest['sources']:
            with (ROOT / 'data/radlab' / source['file']).open(newline='') as handle:
                source_rows[source['file']] = list(csv.DictReader(handle))
        spreads = []
        for group in packet['groups']:
            values = [Fraction(Decimal(v)) for v in group['rates_microgray_per_hour']]
            spread = max(values) - min(values)
            self.assertEqual(Fraction(Decimal(group['rate_range_microgray_per_hour'])), spread)
            spreads.append(spread)
            for readings in [group, group['before'], group['after']]:
                for number, stamp, rate in zip(readings['source_rows'], readings['timestamps_as_recorded'],
                                               readings['rates_microgray_per_hour']):
                    raw = source_rows[group['source_file']][number - 2]
                    self.assertEqual((raw['timestamp'], raw['absorbed_dose_rate']), (stamp, rate))
        self.assertEqual(spreads, sorted(spreads, reverse=True))


if __name__ == '__main__':
    unittest.main()
