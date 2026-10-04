# Changelog

## Unreleased

- Add a source-traceable neighboring-sample comparison for the 58 differing-rate timestamp groups, preserving all readings and exposing missing neighbors and ties.
- Preserve fractional-second annotation timestamps exactly across Python 3.9 and 3.12, including `Z` offsets, interval ordering, overlaps, and midnight thresholds. Export the exact candidate gap alongside its numeric value.
- Prevent invalid annotation labels, blank annotators, wrong dates, or wrong filenames from generating midnight candidates while retaining structural findings.

## 0.1.1 — 2026-09-26

- Replace byte-for-byte report comparison with exact structural checks and a `1e-12` relative/absolute floating-point tolerance. Hosted Python 3.12 checks exposed last-digit differences while all scientific tests passed.
- Add two regression tests for roundoff and material/structural changes (19 tests total).
- Source snapshots, scientific calculations, and published diagnostic findings are unchanged.

## 0.1.0 — 2026-09-26

- Fixed 18-case public RadLab diagnostic report: 21,500 readings, 58 timestamps with differing rates, 16 series excluded from numerical integration.
- Exact source snapshots, queries, and SHA-256 provenance.
- Reusable command-line annotation checker with synthetic examples.
- 17 automated tests; offline reproduction and original-case regression checks.

Formal subgroup recognition, confirmed collaborators, domain validation, and external adoption remain pending.
