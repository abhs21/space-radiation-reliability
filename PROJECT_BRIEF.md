# Space Radiation Measurement Reliability

## Proposed subgroup

We build reproducible checks that show how timestamps, sampling gaps and processing choices affect radiation-data summaries, preserving every original reading for expert review.

The intended users are researchers preparing public RadLab time series for analysis or machine learning. The deliverable is a tested checker, a source-linked offline review tool and a documented case study. Abhi Singh initiated and coordinates the project; formal AI/ML AWG subgroup recognition and a project-lead appointment are requested, not yet confirmed.

## Evidence and limits

The original fixed panel contains 18 instrument-days and 21,500 readings. It preserves 58 differing-rate repeated timestamp groups; all 58 occur on five-minute clock boundaries. Sixteen series are excluded from numerical integration, leaving only two exploratory masking examples. These findings do not establish corrupted data or identify the physically correct reading.

The [October 8 stress test](reports/stress-test/REPORT.md) fixes a separate 28 instrument-day sample before download and preserves all outcomes. All 28 queries returned empty CSVs; no dates were substituted. A control query reproduced an original populated snapshot exactly. The expanded mask-placement checks therefore still cover only the two original eligible series. Synthetic controls and timestamp regression tests assess software behavior, not instrument accuracy.

The checker now preserves fractional timestamps exactly across supported Python versions, including nanoseconds. Every mask case, exclusion, source query and byte hash is available for review. Numerical masking measures changes in the integral of the reported series; it does not estimate hidden radiation peaks or bound missing dose.

## Instrument questions

We need an instrument or RadLab contact to explain the repeated five-minute timestamps, channel/direction identity, rate averaging, timezone and quality flags. The [DOSTEL paper](https://arxiv.org/pdf/2107.01672) describes 20/100-second storage intervals; the [RadLab DosTel2 entry](https://visualization.osdr.nasa.gov/radlab/gui/knowledgebase/dostel2) lists 300-second cadence. These may describe different stages of processing. We also need to establish available date coverage before designing any later measurement sample.

## Relationship to existing work

This proposed subgroup focuses on source-data checks before downstream modeling. The existing [telemetry/anomaly project](https://awg.osdr.space/t/sharing-project-report-data-mining-for-space-habitats/3397) studies environmental and biological associations, and the [LEO Dosimetry SAA/GCR subgroup](https://awg.osdr.space/t/leo-dosimetry-saa-gcr-separation-using-ml-new-subgroup/3665) studies separation and labeling. Scope agreement with these teams and the AI/ML leads is part of the proposal. The annotation-interval checker supports the separate LEO collaboration; it is not the core claim of this subgroup.

## Team and next step

Abhi coordinates scope, software integration and written updates. Hitaeshi Sehgal [offered to help](https://awg.osdr.space/t/space-radiation-measurement-reliability-project-proposal-and-collaborators/4682/2) with reproduction and repeated-reading checks; her October 2 neighboring-sample calculations were independently verified. That does not establish full-release independent reproduction or instrument validation.

The request to the leads is recognition of a separate subgroup with Abhi as project lead, an instrument contact, and the remaining requirements for recognition and recruiting contributors. Coordination is through written review and updates. A named workstream in an existing project is a fallback if the leads consider that a better fit.

Open contribution roles, subject to agreement: instrument interpretation, data/software checks, and independent reproduction. No additional members or adviser are confirmed. The next scientific milestone is documented instrument interpretation and a scope agreed with the leads; recognition depends on their explicit decision.
