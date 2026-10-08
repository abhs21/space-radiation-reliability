import argparse
import hashlib
import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from review_neighbors import ROOT, review
from timestamp_utils import decimal_text

OUTPUT_NAMES = ['review_packet.json', 'review_packet.html', 'REVIEW.md']


def build_packet(data_dir, manifest):
    groups, summary = review(data_dir, manifest)
    sources = sorted([{'file': s['file'], 'sha256': s['sha256']} for s in manifest['sources']],
                     key=lambda s: s['file'])
    source_set = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    ranked = []
    for group in groups:
        rates = [Fraction(Decimal(rate)) for rate in group['rates_microgray_per_hour']]
        spread = max(rates) - min(rates)
        identity = group['source_file'] + '/' + group['sha256'] + '/' + ','.join(map(str, group['source_rows']))
        ranked.append((spread, dict(group, group_key=identity,
                                   rate_range_microgray_per_hour=decimal_text(spread))))
    ranked.sort(key=lambda item: (-item[0], item[1]['instrument_id'], item[1]['day'],
                                  item[1]['timestamps_as_recorded'][0], item[1]['source_rows']))
    return {
        'title': 'RadLab reading review', 'source_set_sha256': source_set,
        'sort_basis': 'Descending absolute difference between the largest and smallest rate in a group; not scientific severity',
        'summary': summary, 'groups': [group for _, group in ranked],
    }


def render_html(packet):
    template = (ROOT / 'templates/review_packet.html').read_text(encoding='utf-8')
    if template.count('__PACKET_JSON__') != 1:
        raise ValueError('Review template must contain one data placeholder')
    encoded = json.dumps(packet, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    for character, replacement in [('<', r'\u003c'), ('>', r'\u003e'), ('&', r'\u0026')]:
        encoded = encoded.replace(character, replacement)
    return template.replace('__PACKET_JSON__', encoded)


def markdown_cell(value):
    return str(value).replace('\n', ' ').replace('|', r'\|').replace('<', '&lt;').replace('>', '&gt;')


def render_markdown(packet):
    summary = packet['summary']
    lines = ['# RadLab reading review', '',
             'A reproducible packet for instrument and data reviewers. Open review_packet.html for filters, surrounding readings, source evidence, and notes; review_packet.json retains the complete data.', '',
             f"This packet contains {summary['source_cases']} source files, {summary['source_rows']:,} readings, and {summary['differing_rate_groups']} differing-rate timestamp groups.",
             f"Comparisons: {summary['comparable_groups']} available, {summary['tied_groups']} tied, {summary['unavailable_groups']} unavailable.",
             'The list is sorted by the absolute range of the recorded rates. That order does not measure scientific severity or determine a correct reading.', '',
             '## Largest recorded rate differences', '',
             '| Instrument | Day | Recorded timestamp | CSV rows | Rate range (microgray/hour) | Local comparison |',
             '|---|---|---|---|---:|---|']
    for group in packet['groups'][:10]:
        closest = ', '.join(map(str, group['closest_source_rows'])) or 'unavailable'
        comparison = 'CSV row(s) ' + closest if closest != 'unavailable' else closest
        values = [group['instrument_id'], group['day'], group['timestamps_as_recorded'][0],
                  ', '.join(map(str, group['source_rows'])), group['rate_range_microgray_per_hour'], comparison]
        lines.append('| ' + ' | '.join(map(markdown_cell, values)) + ' |')
    lines.extend(['', '## Instrument-day coverage', '',
                  '| Instrument | Day | Readings | Differing-rate groups | Available comparisons |',
                  '|---|---|---:|---:|---:|'])
    for case in summary['cases']:
        values = [case['instrument_id'], case['day'], case['source_rows'],
                  case['differing_rate_groups'], case['comparable_groups']]
        lines.append('| ' + ' | '.join(map(markdown_cell, values)) + ' |')
    lines.extend(['', '## Questions for instrument review', '',
                  '1. What does the recorded timestamp represent: an acquisition instant, interval boundary, average, or processing time?',
                  '2. Do the differing readings represent distinct detector channels or directions, and can those identities be recovered from the source?',
                  '3. Does instrument documentation explain the repeated timestamps on five-minute boundaries in this fixed batch?',
                  '4. Which interval and quality-flag conventions should be applied before any physical-dose interpretation?', '',
                  'Source order does not establish acquisition order. Neither closeness to a local trend nor rate range identifies a physically correct reading. Every original reading is retained.', '',
                  '## Review notes and provenance', '',
                  'The page saves notes in this browser on this device, under a key tied to the source snapshots. Export notes explicitly to keep or share them. Notes do not modify the source CSVs or the published calculations.',
                  '`review_packet.json` includes original timestamp/rate strings, CSV rows, neighboring readings, source URLs, and SHA-256 hashes. Exported notes identify the source snapshots and rows alongside each note. Files with no differing-rate groups remain in the coverage table.', '',
                  'Source-set SHA-256: ' + packet['source_set_sha256'], ''])
    return '\n'.join(lines)


def write_packet(output_dir, packet):
    output_dir = Path(output_dir)
    rendered = {'review_packet.json': json.dumps(packet, indent=2, allow_nan=False) + '\n',
                'review_packet.html': render_html(packet), 'REVIEW.md': render_markdown(packet)}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in rendered.items():
        (output_dir / name).write_text(content, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Build an offline, source-traceable review page for differing readings.')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/radlab')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'reports/source_manifest.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'outputs/review-packet')
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        inputs = {args.manifest.resolve()} | {(args.data_dir / s['file']).resolve() for s in manifest['sources']}
        if inputs & {(args.output_dir / name).resolve() for name in OUTPUT_NAMES}:
            raise ValueError('Outputs must not overwrite inputs')
        packet = build_packet(args.data_dir, manifest)
        write_packet(args.output_dir, packet)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'groups': len(packet['groups']), 'source_files': packet['summary']['source_cases'],
                      'source_set_sha256': packet['source_set_sha256']}))


if __name__ == '__main__':
    main()
