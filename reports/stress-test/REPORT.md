# Sampling stress test

This is a reported-data processing study, not an instrument calibration or physical-dose uncertainty estimate.

## Fixed design

Both DosTel instruments on May 1–7 and June 1–7, 2022: 28 instrument-days fixed before download. This extends a convenience sample; it is not a representative survey. Unavailable dates are retained without replacements. The original 18 snapshots remain separate and unchanged.

Protocol SHA-256: `0024b4d014ca5ece2e593737908f9f239581570b7b1ed5bbd8b9137747fac3e9`. Exact source hashes, URLs and acquisition outcomes are in `data/stress-test/source_manifest.json`.

For integration-eligible series, remove 5-, 15- and 30-minute blocks at 30-minute spacing, offset 0/10/20 minutes from the original first-timestamp-plus-30-minute start. Retain the endpoints and a 30-minute boundary margin; bridge each gap with trapezoids. Strides 2/5/10 use the same endpoint policy. `results.json` includes every prescribed block, including blocks removing no observations, each exclusion, and each stride result. Summary percent changes use the complete reported-series integral as reference.

## Results by panel

- original18: 18 planned, 18 CSV responses, 18 with readings, 0 empty, 0 unavailable responses; 2 integration-eligible and 16 nonempty series excluded. 21,500 readings and 58 differing-rate timestamp groups.
- extension28: 28 planned, 28 CSV responses, 0 with readings, 28 empty, 0 unavailable responses; 0 integration-eligible and 0 nonempty series excluded. 0 readings and 0 differing-rate timestamp groups.

| Panel | Instrument | Day | Rows | Integration / reason | Worst 30-minute change by offset 0 / 10 / 20 (%) |
|---|---|---|---:|---|---|
| original18 | DosTel1 | 2022-03-01 | 1202 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-03-01 | 1187 | eligible | 21.6888 / 18.5680 / 19.1965 |
| original18 | DosTel1 | 2022-04-01 | 1192 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-04-01 | 1197 | eligible | 21.2489 / 21.1410 / 22.6394 |
| original18 | DosTel1 | 2022-04-02 | 1193 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-04-02 | 1192 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel1 | 2022-04-03 | 1196 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-04-03 | 1192 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel1 | 2022-04-04 | 1199 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-04-04 | 1166 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel1 | 2022-04-05 | 1201 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-04-05 | 1190 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel1 | 2022-04-06 | 1202 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-04-06 | 1193 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel1 | 2022-04-07 | 1196 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-04-07 | 1190 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel1 | 2022-04-08 | 1212 | duplicate_timestamps_require_domain_interpretation | — |
| original18 | DosTel2 | 2022-04-08 | 1200 | duplicate_timestamps_require_domain_interpretation | — |
| extension28 | DosTel1 | 2022-05-01 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-05-01 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-05-02 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-05-02 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-05-03 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-05-03 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-05-04 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-05-04 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-05-05 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-05-05 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-05-06 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-05-06 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-05-07 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-05-07 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-06-01 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-06-01 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-06-02 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-06-02 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-06-03 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-06-03 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-06-04 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-06-04 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-06-05 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-06-05 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-06-06 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-06-06 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel1 | 2022-06-07 | 0 | empty CSV response; no readings | — |
| extension28 | DosTel2 | 2022-06-07 | 0 | empty CSV response; no readings | — |

28 of 28 planned new queries have frozen header-only responses. Empty and unavailable cases add no measurement evidence. No dates were substituted.

A separately recorded control request on 2026-10-08 for DosTel2 on 2022-04-01 returned 1,197 readings matching the original snapshot SHA-256. This is an API check, not a replacement study case. It shows that the API returned readings for that known populated date; it does not establish why other queries are empty.

## Controls and interpretation

Constant and linear signals retain their analytic integrals within floating-point roundoff across all prescribed masks. The peaked signal demonstrates dependence on mask placement. A valid 100/20-second changing-cadence constant signal remains eligible. The hidden-peak examples keep identical retained observations while the possible full-signal integral grows without bound; masking sensitivity is not a missing-dose bound.

The original roughly 21% examples came from only two eligible instrument-days. Neither these nor this extension establish instrument-wide error rates. Report results per day and instrument; overlapping masks and days are not independent statistical samples. Repeated timestamps remain unresolved observations, not discarded errors.

All 58 repeated groups in the original panel occur on five-minute boundaries. Native interval storage (20/100 seconds in the cited DOSTEL paper) and the RadLab DosTel2 knowledgebase cadence (300 seconds) may describe different processing stages. Timestamp, channel, binning, averaging, timezone and quality-flag semantics require an instrument contact before physical interpretation.

## Reproduce

`python3 run_stress_test.py --output-dir outputs/stress-reproduced` uses frozen snapshots and checks hashes. Compare `results.json` using `verify_reproduction.py`. Acquisition used `--download-missing`, at most two attempts per missing file and three simultaneous requests; recorded failures are not retried on reproduction.

The original `reports/diagnostics.json` and its 18 source files are unchanged. Default diagnostics retain the original report schema and phase-zero masking method; the additional phase cases live only in this separate study.

## Sources

- [DOSTEL instrument paper](https://arxiv.org/pdf/2107.01672)
- [RadLab DosTel2 entry](https://visualization.osdr.nasa.gov/radlab/gui/knowledgebase/dostel2)
- [RadLab API](https://visualization.osdr.nasa.gov/radlab/gui/data-api/)
