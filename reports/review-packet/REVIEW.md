# RadLab reading review

A reproducible packet for instrument and data reviewers. Open review_packet.html for filters, surrounding readings, source evidence, and notes; review_packet.json retains the complete data.

This packet contains 18 source files, 21,500 readings, and 58 differing-rate timestamp groups.
Comparisons: 58 available, 0 tied, 0 unavailable.
The list is sorted by the absolute range of the recorded rates. That order does not measure scientific severity or determine a correct reading.

## Largest recorded rate differences

| Instrument | Day | Recorded timestamp | CSV rows | Rate range (microgray/hour) | Local comparison |
|---|---|---|---|---:|---|
| DosTel1 | 2022-04-03 | 2022-04-03T02:30:00 | 131, 132 | 33.475253185304 | CSV row(s) 132 |
| DosTel2 | 2022-04-02 | 2022-04-02T13:05:00 | 675, 676 | 26.77553 | CSV row(s) 676 |
| DosTel1 | 2022-04-02 | 2022-04-02T11:30:00 | 599, 600 | 12.8403091707317 | CSV row(s) 600 |
| DosTel1 | 2022-04-08 | 2022-04-08T08:20:00 | 445, 446 | 6.8861881214058 | CSV row(s) 445 |
| DosTel1 | 2022-04-02 | 2022-04-02T01:45:00 | 87, 88 | 6.1198931477273 | CSV row(s) 88 |
| DosTel2 | 2022-04-04 | 2022-04-04T09:55:00 | 500, 501 | 5.601991 | CSV row(s) 500 |
| DosTel1 | 2022-04-08 | 2022-04-08T08:15:00 | 441, 442 | 2.632125 | CSV row(s) 441 |
| DosTel2 | 2022-04-07 | 2022-04-07T00:30:00 | 25, 26 | 1.81687287539936 | CSV row(s) 25 |
| DosTel1 | 2022-04-06 | 2022-04-06T11:20:00 | 597, 598 | 1.61010727795527 | CSV row(s) 597 |
| DosTel2 | 2022-04-04 | 2022-04-04T09:50:00 | 496, 497 | 1.510279341853 | CSV row(s) 496 |

## Instrument-day coverage

| Instrument | Day | Readings | Differing-rate groups | Available comparisons |
|---|---|---:|---:|---:|
| DosTel1 | 2022-03-01 | 1202 | 4 | 4 |
| DosTel1 | 2022-04-01 | 1192 | 3 | 3 |
| DosTel1 | 2022-04-02 | 1193 | 4 | 4 |
| DosTel1 | 2022-04-03 | 1196 | 6 | 6 |
| DosTel1 | 2022-04-04 | 1199 | 5 | 5 |
| DosTel1 | 2022-04-05 | 1201 | 2 | 2 |
| DosTel1 | 2022-04-06 | 1202 | 2 | 2 |
| DosTel1 | 2022-04-07 | 1196 | 4 | 4 |
| DosTel1 | 2022-04-08 | 1212 | 4 | 4 |
| DosTel2 | 2022-03-01 | 1187 | 0 | 0 |
| DosTel2 | 2022-04-01 | 1197 | 0 | 0 |
| DosTel2 | 2022-04-02 | 1192 | 1 | 1 |
| DosTel2 | 2022-04-03 | 1192 | 4 | 4 |
| DosTel2 | 2022-04-04 | 1166 | 5 | 5 |
| DosTel2 | 2022-04-05 | 1190 | 2 | 2 |
| DosTel2 | 2022-04-06 | 1193 | 4 | 4 |
| DosTel2 | 2022-04-07 | 1190 | 6 | 6 |
| DosTel2 | 2022-04-08 | 1200 | 2 | 2 |

## Questions for instrument review

1. What does the recorded timestamp represent: an acquisition instant, interval boundary, average, or processing time?
2. Do the differing readings represent distinct detector channels or directions, and can those identities be recovered from the source?
3. Does instrument documentation explain the repeated timestamps on five-minute boundaries in this fixed batch?
4. Which interval and quality-flag conventions should be applied before any physical-dose interpretation?

Source order does not establish acquisition order. Neither closeness to a local trend nor rate range identifies a physically correct reading. Every original reading is retained.

## Review notes and provenance

The page saves notes in this browser on this device, under a key tied to the source snapshots. Export notes explicitly to keep or share them. Notes do not modify the source CSVs or the published calculations.
`review_packet.json` includes original timestamp/rate strings, CSV rows, neighboring readings, source URLs, and SHA-256 hashes. Exported notes identify the source snapshots and rows alongside each note. Files with no differing-rate groups remain in the coverage table.

Source-set SHA-256: c82cce694786e649b650aef1f28d0a9b66fa462c6d0c367ec72d413701fe63c3
