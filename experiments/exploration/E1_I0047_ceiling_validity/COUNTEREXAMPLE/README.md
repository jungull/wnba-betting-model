# COUNTEREXAMPLE

Contents produced by `scripts/s02_bound_or_not.py`. All statistics signed and unstandardised.

- `minimal_counterexample.npz` — the n=3 case. `y = (-1,0,1)`, base = intercept only,
  candidate `x = (-1,0,1)` (exactly orthogonal to the base), shift `d = 0.5x` applied at
  **half** its optimal coefficient. `(d·d)/SST = 0.250000`, realised `ΔR² = 0.750000`. The
  bound is exceeded by 3.00×. Complementary case `d = 2x` in the same file: the bound holds.
- `collinearity_probe.csv` — 1,000 draws sweeping the candidate's correlation with the base
  from 0 to 0.99 with `d` always the OLS fitted contribution. `c*` is 1 to 6.8e-15 in every
  draw; the bound never fails; the raw-sd form's slack rises with collinearity.
- `live_counterexamples.csv` — the counterexamples that already exist in the programme's own
  recorded artifacts, including **D098's own headline cell**, where the realised statistic
  exceeds the published ceiling by 46%.

**The failing assumption is SCALE, not orthogonality.** `(d·d)/SST ≥ ΔR²` iff `c* ≤ 1`.
