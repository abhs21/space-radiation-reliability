# Synthetic interval-mean accounting

This demonstration uses analytic synthetic signals and explicit, nonoverlapping accumulation intervals. It makes no claim about a real instrument discrepancy. All inputs, interval/gap ledgers and scenario results are in `results.json`.

**Contract:** rates are wall-time interval means in microgray/hour over `[start_seconds,end_seconds)`, with a common time origin. Dose in microgray is `sum(mean_rate * duration_seconds / 3600)`. No duration is inferred from timestamp spacing. Live-time denominators, dose equivalent, material conversion and calibration changes require separate documented inputs; they are outside this contract. Unsupported units, nonfinite values or negative rates, unordered/nonpositive intervals, duplicates, conflicts and overlaps reject the entire input.

## Complete intervals conserve dose

| Synthetic signal | Exact dose (microgray) | Weighted dose (microgray) | Incorrect unweighted estimate (microgray) | Error |
|---|---:|---:|---:|---:|
| constant | 5/9 | 0.555555555556 | 0.555555555556 | +0.000000% |
| linear | 5/9 | 0.555555555556 | 0.465277777778 | -16.250000% |
| adaptive_pulse | 19/36 | 0.527777777778 | 1.170634920635 | +121.804511% |

The constant control is 2 microgray/hour for 1000 s, partitioned as 9×100 s + 5×20 s. The linear control is `1 + 0.002t` on `[0,1000)`, averaged over unequal intervals ending at 100, 250, 500 and 1000 s. The adaptive pulse is 1 microgray/hour for 900 s and 10 for 100 s with the same 100/20 s partition. Each weighted sum exactly equals its analytic integral and the dose after regrouping to one duration-weighted coarse interval. The deliberately incorrect estimate is the arithmetic mean of interval means times total exposure; extra samples in the high-rate region produce the pulse bias.

## Boundaries, missing exposure and clocks

**Narrow boundary:** a rectangular 100 microgray/hour peak on `[45,55)` is averaged into bins with edges `[0,50,100]` and `[0,20,70,100]`. Both complete-bin totals are exactly 5/18 microgray. On `[0,48)`, analytic dose is 1/12 microgray; constant allocation estimates are 2/15 and 7/45 microgray. The first estimate has nonnegative bounds `[0,5/36]`; the second `[0,5/18]`. Results also move the window end to 52 s. Cutting a bin requires an assumption: interval means alone permit any partial dose from zero to the entire cut-bin dose. Bounds sum exact complete-bin doses and these boundary limits; they do not recover peak timing.

**Missing/conflicting:** removing `[400,500)` and `[940,960)` from the adaptive pulse leaves 880 s of exposure and 4/9 microgray of complete-interval dose. Missing 120 s remains unobserved. Filling it with rates of 0 or 100 gives different totals with identical observations; nonnegative rates alone give no finite upper bound for the full window. A second record for `[900,920)` with rate 99 is rejected rather than selected, merged or counted twice.

**Gain/clocks:** separate constant calibration intervals `[-200,-100)` at rates 3 and 6 supply a frozen gain of 2. Dividing held-out scaled rates by that factor recovers the original dose. A known +60 s offset preserves the full shifted-span dose, but on the fixed `[0,1000)` window leaves 940 s coverage and 13/36 microgray. Correcting the known offset restores the original result. Applied shifts −60/−30/0/+30/+60 s are diagnostic scenarios, not uncertainty intervals or estimates of real clock accuracy. Gain scaling leaves the missing fixture’s 120 s gap unchanged; neither scaling nor shifting creates missing observations.

Exact rational checks pass for complete-interval truth and regrouping. Decimal output uses 50-digit precision; tests also check analytic boundary values, gap bounds, invalid-input rejection and deterministic regeneration. These are computational checks, not measurement accuracy. A real comparison requires documented accumulation/rebinning, rate denominator, material, clock correction and common support before interpreting its totals.
