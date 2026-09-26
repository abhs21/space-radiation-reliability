# Space Radiation Measurement Reliability

Small, reproducible tools for checking radiation time series and SAA annotation intervals.

**Project initiator: Abhi Singh.** This is a proposed community project; formal OSDR AWG subgroup recognition and collaborator participation are pending.

## Start here

- [Diagnostic report: 18 instrument-day cases](reports/REPORT.md)
- [Exact source queries and snapshot hashes](reports/source_manifest.json)
- [Project brief and ways to contribute](PROJECT_BRIEF.md)
- [Machine-readable diagnostic results](reports/diagnostics.json)

The tools preserve repeated readings and identify questions for instrument experts. Numerical masking compares integrals of reported rates; it is not a validated physical-dose estimate.

## Run locally

Python 3.9 or newer; no third-party packages are required.

```sh
git clone https://github.com/abhs21/space-radiation-reliability.git
cd space-radiation-reliability
python3 -m unittest discover -s tests -v
python3 run_campaign.py --output-dir outputs/reproduced
python3 validate_intervals.py --input examples/annotations --output-dir outputs/annotations
```

The campaign uses the committed public RadLab snapshots and checks their hashes. Sources were collected on September 22 and 26, 2026. Reproduction requires no network connection. Querying current data into a separate empty directory is supported with `--data-dir outputs/current-data --download-missing`; a source-hash mismatch stops the run so changed data cannot silently replace the release evidence.

Check another rate CSV:

```sh
python3 radlab_diagnostics.py --input your.csv --instrument-id DosTel1 --day 2022-04-01 --output outputs/your-diagnostics.json
```

Required rate columns: `timestamp,instrument_id,absorbed_dose_rate`. Additional columns are allowed. Rates must be finite and nonnegative. Naive timestamps are retained without inventing a timezone; explicit offsets are normalized to UTC. Mixed conventions block numerical integration. `--day` checks literal dates for naive timestamps and UTC dates for offset-aware timestamps.

## Annotation checker

Input is one CSV or a folder of daily CSVs, with this exact header:

```text
annotator,date,start,end,label
```

Filenames begin with the declared `YYYY-MM-DD`. Start/end timestamps need explicit offsets and are checked against that UTC day. Labels are `SAA`. Different annotators remain separate. Findings include malformed rows, date/order problems, duplicates, overlaps, and midnight review candidates. Outputs are `audit_results.json` and `flagged_intervals.csv`; source files are never edited.

`--window-seconds 600` sets a candidate window on **each side** of midnight, not a maximum total gap. The default was calibrated to previously reported examples; it is not an independently validated classifier. The output also reports counts for 60/120/300/600-second windows. Candidates are never merged automatically. Structural checks do not validate scientific labeling or find missing passages.

The examples are fictional and labeled synthetic. Volunteer annotations and private correspondence are not included. The separate local preparation audit covered 53 intervals in eight files and reproduced four midnight cases already reported by the annotator; those are not new discoveries. See [the original discussion](https://awg.osdr.space/t/leo-dosimetry-saa-gcr-separation-using-ml-new-subgroup/3665/117).

## Contribute

Open an issue with a small reproducible example, expected behavior, source provenance, and the question you want checked. We are looking for help with instrument interpretation, data checks, and independent reproduction. See [the project brief](PROJECT_BRIEF.md). Use synthetic examples when sharing annotations unless you have permission to publish the source data.

## Data and license

Original code and documentation are under the [MIT license](LICENSE). Public RadLab CSV snapshots are reproduced as source data with their original instrument identifiers and provenance; this project does not relicense NASA or third-party data. See [data provenance](data/README.md). No NASA endorsement or formal subgroup status is implied.
