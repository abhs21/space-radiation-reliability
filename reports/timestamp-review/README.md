# Repeated-timestamp review

September 28, 2026. Based on the unchanged 18 public snapshots in release v0.1.1.

The [review table](repeated_timestamp_groups.csv) contains 58 timestamp groups with differing rates: 34 in DosTel1 and 24 in DosTel2. Each contains two readings, giving 116 source rows. All 58 timestamps fall exactly on five-minute boundaries in the recorded clock. The complete batch contains 21,500 readings and 21,442 unique instrument/file timestamps, of which 5,176 fall on those boundaries. The remaining 16,266 unique timestamps have no differing-rate groups in this batch.

This is a descriptive pattern in a convenience sample. It does not establish the cause, a detector direction, a processing defect, or physical-dose validity. Timezone and interval conventions remain unresolved. The timestamp strings are preserved without calling them UTC. No readings are averaged, deleted, or reassigned.

## Trace a group

Each row includes the original instrument, date, timestamp, source filename, source query, and SHA-256 hash. `source_rows_json` lists CSV row numbers with the header counted as row 1. `rates_microgray_per_hour_json` retains the corresponding rate strings in the same order. The two JSON arrays belong together. [Summary counts](timestamp_summary.json) include all 18 instrument-day cases, including cases with zero differing-rate groups.

## Reproduce

From the current checkout, run:

```sh
python3 review_timestamps.py --output-dir outputs/timestamp-review
python3 -m unittest discover -s tests -v
```

The script checks every snapshot against `reports/source_manifest.json` before exporting. It groups identical recorded timestamp strings within each file and compares rates as decimal values. Five-minute alignment means a minute divisible by five with exactly zero seconds, including the fractional part. Explicit offsets, when present, are preserved; alignment refers to the recorded clock rather than normalized UTC.

For an independent reproduction of the original scientific report, use the frozen v0.1.1 release and its README commands first. This added review table is a separate follow-up on the same snapshots. Return the release/commit, Python version, operating system, reproduction result, and any discrepancies before proposing source-data changes.

Useful next checks are whether the pattern persists beyond this fixed batch, whether nearby rows reveal a processing pattern, and whether instrument documentation explains the records. Current diagnostics alone cannot answer those questions. Broader sampling should be specified before inspecting additional dates.
