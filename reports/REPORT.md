# RadLab diagnostic report

Release 0.1.0 — fixed audit of 18 instrument-day CSV snapshots.

The batch contains **21,500 readings**, **58 timestamps with differing rates**, and **16 series excluded from numerical integration**.

## Selection and method

The four original cases use DosTel1 and DosTel2 on March 1 and April 1, 2022. The extension uses both instruments on April 2–8, 2022. These dates were fixed before running the extension. They are a convenience sample, not a representative instrument survey.

Each API query requests one instrument and absorbed dose rate over a half-open calendar-day window. The CSV does not supply a timezone or interval definition. Day boundaries here follow the literal API timestamps; they are not asserted to be UTC. Source URLs and exact byte hashes are in [source_manifest.json](source_manifest.json).

Duplicate groups retain their source rows and every rate. No readings are averaged or removed. Spacing is calculated from sorted unique parsed timestamps, so duplicate groups do not introduce artificial zero-second gaps. A repeated timestamp can have a valid instrument explanation; these findings do not establish corrupted data.

| Instrument | Day | Rows | Repeated timestamps | Differing-rate timestamps | Median unique spacing (s) | Worst 30-minute masking change (%) |
|---|---|---:|---:|---:|---:|---:|
| DosTel1 | 2022-03-01 | 1202 | 4 | 4 | 89.0000 | — |
| DosTel2 | 2022-03-01 | 1187 | 0 | 0 | 92.5000 | 21.6888 |
| DosTel1 | 2022-04-01 | 1192 | 3 | 3 | 90.0000 | — |
| DosTel2 | 2022-04-01 | 1197 | 0 | 0 | 92.0000 | 21.2489 |
| DosTel1 | 2022-04-02 | 1193 | 4 | 4 | 88.0000 | — |
| DosTel2 | 2022-04-02 | 1192 | 1 | 1 | 93.0000 | — |
| DosTel1 | 2022-04-03 | 1196 | 6 | 6 | 87.0000 | — |
| DosTel2 | 2022-04-03 | 1192 | 4 | 4 | 92.0000 | — |
| DosTel1 | 2022-04-04 | 1199 | 5 | 5 | 89.0000 | — |
| DosTel2 | 2022-04-04 | 1166 | 5 | 5 | 93.0000 | — |
| DosTel1 | 2022-04-05 | 1201 | 2 | 2 | 85.0000 | — |
| DosTel2 | 2022-04-05 | 1190 | 2 | 2 | 88.0000 | — |
| DosTel1 | 2022-04-06 | 1202 | 2 | 2 | 87.0000 | — |
| DosTel2 | 2022-04-06 | 1193 | 4 | 4 | 88.0000 | — |
| DosTel1 | 2022-04-07 | 1196 | 4 | 4 | 88.0000 | — |
| DosTel2 | 2022-04-07 | 1190 | 6 | 6 | 89.0000 | — |
| DosTel1 | 2022-04-08 | 1212 | 4 | 4 | 86.0000 | — |
| DosTel2 | 2022-04-08 | 1200 | 2 | 2 | 88.0000 | — |

## Interpretation

The numerical analysis integrates the reported rate values with the trapezoidal rule over the observed timestamp span. Synthetic 5-, 15-, and 30-minute blocks are removed at half-hour start positions, with a 30-minute boundary margin. The retained series is integrated across each artificial gap. The comparison is against the full reported series, not physical ground truth; it does not detect naturally missing telemetry or estimate unobserved dose. Outputs include every prescribed mask summary and stride 2/5/10 sensitivity.

Series with duplicate timestamps, malformed/value findings, mixed timestamp conventions, fewer than three readings, or nonpositive reference area receive diagnostics without integration. Passing these software checks does not resolve instrument semantics or establish physical validity.

The published DosTel2 knowledgebase lists a 300-second cadence. Observed record spacing is reported above without assuming the two quantities should match. Direction/channel interpretation, interval averaging, quality flags, and timezone remain domain questions.

## Reproduce

Run `python3 run_campaign.py --output-dir outputs/reproduced`. This uses the committed public-data snapshots and checks their SHA-256 hashes against the release manifest. It does not access private volunteer annotations. To query current public data separately, use an empty data directory and `--download-missing`; changed source bytes stop reproduction rather than silently replacing the release snapshot.

## Sources

- [RadLab API documentation](https://visualization.osdr.nasa.gov/radlab/gui/data-api/)
- [DosTel2 knowledgebase](https://visualization.osdr.nasa.gov/radlab/gui/knowledgebase/dostel2)
- [RadLab overview](https://visualization.osdr.nasa.gov/radlab/gui/overview/)

These are exploratory software diagnostics. Formal AWG subgroup recognition, instrument-level validation, and external adoption are not established by this report.
