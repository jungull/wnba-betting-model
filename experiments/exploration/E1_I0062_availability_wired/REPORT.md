# E1_I0062 — the good availability model, wired in and measured

**Prereg** `bfbd792b5180f1245efc732bf87ecb67682bcd0bcc96bc7745534a182c57f195`, frozen after the
join's shape and before any score. Exploration only: 14,299 rows, 222 players, seasons
2022–2024, appeared rate 0.8575, zero fallback rows.

**Identical minutes point forecast and identical played-branch distribution in every arm.**
Only the availability term varies, so every difference below is that term and nothing else.

---

## The answer

**All five predictions passed, and the recommendation E1_I0061 made without testing is
confirmed and larger than its own floor: 17.8% against the 11.5% obtained with the crude
instrument.**

| Brier on P(minutes > t) | t>15 | t>20 | t>25 | t>30 | t>35 |
|---|---|---|---|---|---|
| `N_NONE` — no availability branch | 0.12751 | 0.11889 | 0.11344 | 0.10600 | 0.05980 |
| `W_CRUDE` — prior appearance rate | 0.11309 | 0.10981 | 0.10803 | 0.10332 | 0.05935 |
| **`G_GOOD` — shipped `p_active`** | **0.10487** | **0.10405** | **0.10463** | **0.10164** | **0.05907** |
| improvement, crude | +11.3% | +7.6% | +4.8% | +2.5% | +0.8% |
| **improvement, good** | **+17.8%** | **+12.5%** | **+7.8%** | **+4.1%** | **+1.2%** |

Both increments are separated from zero on a cluster bootstrap by player-season:

| at t = 15 | gain | 95% interval |
|---|---|---|
| having a branch at all (`W` over `N`) | **+0.01442** | [+0.00852, +0.02143] |
| upgrading the branch (`G` over `W`) | **+0.00822** | [+0.00591, +0.01067] |

And over the whole dressed distribution, CRPS **4.33012 → 3.75864 → 3.54549** — an 18.1%
improvement end to end, with non-overlapping intervals between `N` and `G`.

## P2: where the value actually sits

The sceptical prediction held. **Having any availability branch is worth more than having a
good one** — +0.0144 against +0.0082. But the upgrade is not a rounding error either: it adds
**57% on top** of what the crude instrument delivered, and its interval is tighter and further
from zero than the crude gain's.

The practical ordering is: *not modelling availability at all* is the large error, and *using
a bad availability model* is a second error about half as large again.

## The wrinkle: the better model is worse calibrated, and that is fine

| instrument, against `appeared` | Brier | AUC | calibration MAD | mean prediction |
|---|---|---|---|---|
| `W_CRUDE` prior appearance rate | 0.08588 | 0.8599 | **0.01819** | 0.8709 |
| `G_GOOD` shipped `p_active` | **0.07902** | **0.8977** | 0.05053 | 0.8141 |

*(actual appearance rate 0.8575)*

`p_active` **under-predicts availability by 4.3 points** on this row set and is nearly three
times worse on calibration deviation — yet it wins decisively on Brier and AUC. It is the
better *ranker* and the worse *calibrator*, and ranking is what the mixture needs.

### The obvious next step, tested post-hoc, does not work

Recalibrating `p_active` walk-forward (logistic on the logit, fitted only on strictly earlier
seasons) does exactly what it should to the instrument — Brier 0.07884 → 0.07770, mean
prediction 0.8114 → 0.8582 against an actual 0.8540.

**And it makes the minutes forecast worse.** t>15 Brier 0.10438 → 0.10515; CRPS 3.52561 →
3.53438, on the 9,908 rows where a recalibration is available.

So the headroom that the miscalibration appeared to leave is not there. Something in the
played branch is absorbing the bias — most plausibly that the played-branch distribution is
fitted on players who did play, and so runs high for the marginal ones that `p_active`'s
downward bias happens to offset. **This is recorded to close the step, not because it is
understood.** It is post-hoc and not preregistered.

## What this settles

- **Wire `p_active` into the minutes forecast.** It is already built, already validated for
  point-in-time provenance by E0_I0019, costs nothing to consume, and is worth 17.8% on the
  prop-shaped question at the threshold where availability dominates.
- **Do not recalibrate it first.** That improves the instrument and degrades the forecast.
- **The gradient across thresholds reproduces exactly** (P4), which is the strongest internal
  evidence that this is a real mechanism and not a fitting artefact: availability matters most
  at low lines, where not dressing is the dominant way to miss, and fades to +1.2% by t>35
  where the question becomes rotation size.

## What this does NOT establish

- **Provenance is inherited, not re-derived.** `v15 p_active` is an out-of-fold production
  artifact. E0_I0019 verified its point-in-time discipline with four leak probes, three of
  which it withdrew and rebuilt. If that verdict ever falls, every number here falls with it.
- **No wager-shaped claim.** S42 stands. Threshold Brier is prop-shaped; that is not
  permission to price a prop.
- **`appeared` is conditional on being in the frame.** A player who never dresses does not
  appear at all, so every arm answers "given this player is a candidate, will they play?" and
  none answers "will this named player produce minutes tonight".
- **2021 is absent** — degenerate in both availability arms — so this is three seasons.
