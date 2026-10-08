# Space Radiation Measurement Reliability

Reproducible checks of how timestamps, sampling gaps and processing choices affect radiation-data summaries, preserving every original reading for expert review.

**Project initiator: Abhi Singh.** This is a proposed community project; formal OSDR AWG subgroup recognition remains pending. Hitaeshi Sehgal contributed a neighboring-sample comparison of the repeated readings. The calculations were independently checked against the public snapshots; the [reproducible follow-up](reports/neighbor-review/README.md) preserves the readings and describes the limits of that comparison.

## Start here

- [Diagnostic report: original 18 instrument-day cases](reports/REPORT.md)
- [Sampling stress test: fixed 28-query extension, empty responses and phase checks](reports/stress-test/REPORT.md)
- [Exact source queries and snapshot hashes](reports/source_manifest.json)
- [Project brief and ways to contribute](PROJECT_BRIEF.md)
- [Machine-readable diagnostic results](reports/diagnostics.json)
- [Repeated-timestamp review table and reproduction notes](reports/timestamp-review/README.md)
- [Neighboring-sample comparison and source-row evidence](reports/neighbor-review/README.md)
- [Instrument-review packet and coverage table](reports/review-packet/REVIEW.md)

The tools preserve repeated readings and identify questions for instrument experts. Numerical masking compares integrals of reported rates; it is not a validated physical-dose estimate.

## Run locally

Python 3.9 or newer; no third-party packages are required.

```sh
git clone https://github.com/abhs21/space-radiation-reliability.git
cd space-radiation-reliability
python3 -m unittest discover -s tests -v
python3 run_campaign.py --output-dir outputs/reproduced
python3 verify_reproduction.py reports/diagnostics.json outputs/reproduced/diagnostics.json
python3 run_stress_test.py --output-dir outputs/stress-reproduced
python3 verify_reproduction.py reports/stress-test/results.json outputs/stress-reproduced/results.json
python3 validate_intervals.py --input examples/annotations --output-dir outputs/annotations
python3 review_neighbors.py --output-dir outputs/neighbor-review
python3 verify_reproduction.py reports/neighbor-review/neighboring_sample_groups.json outputs/neighbor-review/neighboring_sample_groups.json
python3 verify_reproduction.py reports/neighbor-review/neighboring_sample_summary.json outputs/neighbor-review/neighboring_sample_summary.json
python3 build_review_packet.py --output-dir outputs/review-packet
python3 verify_reproduction.py reports/review-packet/review_packet.json outputs/review-packet/review_packet.json
```

The campaign uses the committed public RadLab snapshots and checks their hashes. Sources were collected on September 22 and 26, 2026. Reproduction requires no network connection. Querying current data into a separate empty directory is supported with `--data-dir outputs/current-data --download-missing`; a source-hash mismatch stops the run so changed data cannot silently replace the release evidence.

Check another rate CSV:

```sh
python3 radlab_diagnostics.py --input your.csv --instrument-id DosTel1 --day 2022-04-01 --output outputs/your-diagnostics.json
```

Required rate columns: `timestamp,instrument_id,absorbed_dose_rate`. Additional columns are allowed. Rates must be finite and nonnegative. Naive timestamps are retained without inventing a timezone; explicit offsets are normalized to UTC. Fractional seconds, including nanoseconds, are retained exactly for timestamp identity, sorting and interval subtraction; only elapsed differences are converted to floating point for numerical integration. Mixed conventions block numerical integration. `--day` checks literal dates for naive timestamps and UTC dates for offset-aware timestamps.

Cross-version verification checks structure, counts, strings, and hashes exactly; finite floating-point values use relative and absolute tolerances of `1e-12`. This accommodates the last-digit differences observed between Python 3.9 and 3.12. It is a numerical reproduction tolerance, not measurement uncertainty.

## Sampling stress test

The separate protocol was committed locally before downloading both instruments for May 1–7 and June 1–7, 2022. All 28 requests returned header-only CSVs; these exact responses and hashes are retained in `data/stress-test`, without replacement dates. A known populated control query matched its original snapshot. This extension adds no new measurement evidence.

The two original integration-eligible series were tested with 0/10/20-minute mask-start offsets, lengths 5/15/30 minutes and strides 2/5/10. Every mask case, empty block and excluded series is recorded. Synthetic constant, linear, peaked and changing-cadence controls test the implementation. Identical retained observations can conceal arbitrarily different peak integrals, so these sensitivity numbers are not missing-dose bounds. The original 18-file results remain unchanged.

## Offline reading review

Open `outputs/review-packet/review_packet.html` in a browser after running the generator above. It contains the verified snapshots' differing-rate groups, instrument/date/search filters, surrounding-sample plots, source rows and hashes, and review notes. It needs no server, network connection, or third-party packages. The accompanying `REVIEW.md` summarizes all 18 instrument-day cases, including the two without differing-rate groups; `review_packet.json` contains the full source evidence.

The list can be sorted by recorded rate range or by instrument/date. Rate range and closeness to a trend are descriptive comparisons, not scientific severity or proof of a correct reading. Notes stay in that browser on that device and are tied to the source snapshots. Use **Export review notes** to save them as JSON; notes do not change the source data or calculations.

## Annotation checker

Input is one CSV or a folder of daily CSVs, with this exact header:

```text
annotator,date,start,end,label
```

Filenames begin with the declared `YYYY-MM-DD`. Start/end timestamps need explicit offsets (including `Z`) and are checked against that UTC day. Whole-minute timestamps remain supported. Fractional seconds, including nanoseconds, are retained exactly for duration, ordering, overlap, and midnight-window checks on both supported Python versions. Labels are `SAA`. Different annotators remain separate. Findings include malformed rows, date/order problems, duplicates, overlaps, and midnight review candidates. Outputs are `audit_results.json` and `flagged_intervals.csv`; source files are never edited.

Rows with wrong dates, filenames, blank annotators, or unsupported labels keep their findings but cannot generate midnight candidates. `valid_parsed_intervals` counts positive intervals with parseable timestamps; `candidate_eligible_intervals` additionally requires those metadata checks to pass. Candidates retain the original timestamp strings, a numeric `gap_seconds`, and `gap_seconds_exact` as an exact rational string (for example, `1/500000000` seconds). The original source hashes refer to the bytes actually parsed.

`--window-seconds 600` sets a candidate window on **each side** of midnight, not a maximum total gap. The default was calibrated to previously reported examples; it is not an independently validated classifier. The output also reports counts for 60/120/300/600-second windows. Candidates are never merged automatically. Structural checks do not validate scientific labeling or find missing passages.

The examples are fictional and labeled synthetic. Volunteer annotations and private correspondence are not included. The separate local preparation audit covered 53 intervals in eight files and reproduced four midnight cases already reported by the annotator; those are not new discoveries. See [the original discussion](https://awg.osdr.space/t/leo-dosimetry-saa-gcr-separation-using-ml-new-subgroup/3665/117).

## Contribute

Open an issue with a small reproducible example, expected behavior, source provenance, and the question you want checked. We are looking for help with instrument interpretation, data checks, and independent reproduction. See [the project brief](PROJECT_BRIEF.md). Use synthetic examples when sharing annotations unless you have permission to publish the source data.

## Data and license

Original code and documentation are under the [MIT license](LICENSE). Public RadLab CSV snapshots are reproduced as source data with their original instrument identifiers and provenance; this project does not relicense NASA or third-party data. See [data provenance](data/README.md). No NASA endorsement or formal subgroup status is implied.
