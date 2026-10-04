# Space Radiation Measurement Reliability

## Question

What do sampling, repeated timestamps, and missing observations allow us to conclude from public space-radiation time series?

The first task is to make those data properties visible and reproducible before interpreting an integrated result.

## Work so far

Abhi Singh initiated the project and built a four-case DosTel1/DosTel2 pilot, followed by the fixed 18-case diagnostic report in this release. The package includes a reusable annotation-interval checker and synthetic examples. Repeated timestamps are preserved; affected series receive diagnostics without numerical integration.

## First deliverable

A reproducible report for DosTel1 and DosTel2 on March 1 and April 1–8, 2022, with source snapshots, hashes, repeated-reading details, spacing summaries, and numerical masking sensitivity where the structural checks allow it.

## Collaborators welcome

- **Instrument interpretation:** review timestamp, direction/channel, cadence, interval, and quality-flag conventions.
- **Data checks:** challenge the diagnostics with small documented cases and improve useful reporting.
- **Independent reproduction:** run the release from a clean checkout and report the environment, results, and disagreements.

Abhi will coordinate the initial scope, integrate contributions, and keep the evidence and open questions current. On September 28, Hitaeshi Sehgal [offered to help](https://awg.osdr.space/t/space-radiation-measurement-reliability-project-proposal-and-collaborators/4682/2) with independent reproduction and repeated-timestamp checks. Her October 2 neighboring-sample calculations were independently verified against the public snapshots. The [follow-up report and original implementation](reports/neighbor-review/README.md) make that comparison reproducible; they do not establish which reading is physically correct. The [review table](reports/timestamp-review/README.md) retains the original source rows.

## Relationship to existing work

This proposed work concerns measurement reliability and reporting. The existing [LEO Dosimetry SAA/GCR subgroup](https://awg.osdr.space/t/leo-dosimetry-saa-gcr-separation-using-ml-new-subgroup/3665) studies separation and labeling. The scope and overlap should be discussed with that team and the AI/ML AWG leads. An accepted task within an existing group may be more useful than a separate subgroup.

Formal AWG subgroup recognition is pending. The next milestone is instrument-expert review of the unresolved timestamp and channel conventions, followed by an agreed team scope. Verification of the neighboring-sample calculations does not establish clean-checkout reproduction of the full release, instrument validation, adoption, or a leadership appointment.
