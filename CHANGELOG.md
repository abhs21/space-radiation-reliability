# Changelog

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
