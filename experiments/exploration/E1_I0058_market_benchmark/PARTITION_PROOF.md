# PARTITION_PROOF -- E1_I0058_market_benchmark

**Generated from `out/leak_proof.json`, which was written by `s01_frame.py` at frame-build time.**
Nothing here is asserted by hand.

PREREG sha256 recorded in the leak proof: `6ea05be00509ab80d8fa7220bc24b07ad87c8159b52c05962f8838b13596ca9b`
Analysis frame sha256 recorded in the leak proof: `8605a559fc66076990055a35c3b932c9f242d665656d795e018ce2b9a547b7c8`

## The boundary is the repository's own

Taken from `experiments/exploration/_screen_kit/screenkit.py`, not assumed:

```
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
HOLDOUT_SEASONS     = (2025, 2026)      # FORBIDDEN
```

## What the props file contains, and what was admitted

| commence year | rows | admitted? |
|---|---|---|
| 2024 | 11,237 | **YES -- exploration** |
| 2025 | 15,053 | NO -- holdout |
| 2026 | 10,656 | NO -- holdout |
| **total** | **36,946** | |

Rows admitted: **11,237**.
Rows excluded as holdout-or-later: **25,709**.
Admitted commence years: **[2024]**.

The holdout filter is applied **before any other operation**.

## The analysis frame that resulted

| quantity | value |
|---|---|
| rows | 1,972 |
| seasons present | [2024] |
| distinct players | 78 |
| distinct games | 262 |
| earliest game date | 2024-05-14 |
| latest game date | 2024-10-20 |
| **rows from holdout seasons** | **0** |
| **rows dated after the partition** | **0** |

Both leakage counters are **zero**.

## The sigma(.) calibration is separately clean

`sigma(x) = a + b*sqrt(max(x,0))`, fitted **only** on seasons [2021, 2022, 2023] --
exploration seasons that the props file does not even reach, so no market price and no 2024
outcome can enter it. Frozen coefficients: **a = 0.5985187874**, **b = 1.5305680503**.

## The outcome

`pts` enters this screen **only as the response**, never as a regressor, at any stage. s00
established -- before the PREREG was frozen -- that `feature_asof < forecast_cutoff` on 100% of
rows, that `forecast_cutoff` precedes tip on 100% of rows, and that the market snapshot precedes
`commence_time` on 100% of rows (median lead 1.156 h).

## Re-derivation

`scripts/verify.py` recomputes both file hashes from the bytes on disk and re-asserts every
counter in this document. It exits non-zero if any of them moves.
