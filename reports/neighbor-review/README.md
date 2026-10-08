# Neighboring-sample comparison

October 3, 2026. Uses the unchanged 18 public RadLab snapshots from release v0.1.1: 21,500 readings across DosTel1 and DosTel2 on March 1 and April 1–8, 2022.

Hitaeshi Sehgal suggested and supplied a comparison of the conflicting readings with neighboring samples. Those calculations were independently checked on October 2. This original implementation reproduces the descriptive result using the committed public data. The outputs contain source data and computed checks.

The 58 differing-rate timestamp groups cover 16 instrument-days on nine calendar dates. All have two readings and unambiguous neighboring rates in this batch. The first-listed source row is closer to the interpolated local trend in 53 groups; the second-listed row is closer in five. There are no ties or unavailable comparisons. Median gaps before and after a conflicting timestamp are each about 1.14 times that file's median positive gap.

“First-listed” refers to CSV source order. Equal timestamps do not establish acquisition order. Closeness to a local trend does not prove that a reading is correct, that the other is noise, or that a specific processing mechanism caused the difference. These are descriptive results from a fixed convenience sample, with unresolved instrument conventions. No readings are deleted, averaged, corrected, or used to restore integration of affected series.

## Calculation and provenance

For each differing-rate timestamp group, take the nearest distinct timestamp before and after it. If either neighbor is missing or itself contains differing rates, retain the group and report the comparison as unavailable. Repeated numerically equal neighbor rates are unambiguous; every original row is still recorded. Groups with more than two conflicting readings are supported, and all equally close rows are reported as a tie.

Let `pre` and `post` be the elapsed gaps to those neighbors. The comparison value is:

```text
expected = (before_rate * post + after_rate * pre) / (pre + post)
```

Compare the absolute difference of each conflicting rate from that value. The typical gap is the median gap between sorted distinct timestamp instants within the same file. Report `pre / typical` and `post / typical` without rounding before aggregation. This gap definition excludes zero gaps from repeated timestamps.

Timestamp strings and rate strings are preserved. Naive timestamps use their recorded clock; no timezone is invented. Explicit offsets determine elapsed time and grouping of equivalent instants, while original strings remain visible. Mixed naive/offset conventions stop the run. Fractional seconds are retained exactly, including differences smaller than a microsecond. File dates are checked as recorded, consistent with the original timestamp review.

Every source hash must match [the manifest](../source_manifest.json). Invalid schemas, malformed rows, invalid timestamps, wrong instrument/date values, and nonfinite or negative rates stop the run before export. Rows are sorted only for the calculation; source row positions remain unchanged. Source row numbers count the header as row 1.

Calculations and tie comparisons use exact rational arithmetic. Computed quantities are exported as decimal strings with 50 significant digits; original rate strings are untouched. This precision is a representation choice, not measurement uncertainty or instrument precision.

## Inspect and reproduce

- [All 58 comparisons as CSV](neighboring_sample_groups.csv)
- [The same comparisons as JSON](neighboring_sample_groups.json)
- [Summary, file counts, and source hashes](neighboring_sample_summary.json)

Parallel arrays `timestamps_as_recorded`, `source_rows`, and `rates_microgray_per_hour` describe the same readings. `before` and `after` retain the neighboring groups in that format. `closest_source_positions` uses positions starting at 1 within the conflicting group; `closest_source_rows` points to the corresponding original CSV records. These fields report the comparison and do not choose a replacement reading. Nested CSV fields are JSON; empty optional fields are null in the JSON export.

From the repository root, using Python 3.9 or newer:

```sh
python3 -m unittest discover -s tests -v
python3 review_neighbors.py --output-dir outputs/neighbor-review
python3 verify_reproduction.py reports/neighbor-review/neighboring_sample_groups.json outputs/neighbor-review/neighboring_sample_groups.json
python3 verify_reproduction.py reports/neighbor-review/neighboring_sample_summary.json outputs/neighbor-review/neighboring_sample_summary.json
```

No network access or third-party packages are needed. CI runs these checks on Python 3.9 and 3.12 alongside reproduction of the original report. The new comparison does not change the original diagnostics or their integration exclusions.

The next useful review is whether instrument documentation or a domain expert explains the timestamp/channel relationship. A broader date sample should be specified before inspecting its results.
