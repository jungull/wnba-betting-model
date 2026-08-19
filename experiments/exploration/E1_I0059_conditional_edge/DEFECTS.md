# DEFECTS — E1_I0059_conditional_edge

Everything wrong with this screen, including what does not change the answer.

---

## D1 — the preregistered permutation null is ill-defined for four of five conditioners

**Severity: B. Found during implementation. Not repaired — the prereg is hash-frozen.**

PREREG §5.2 states the subgroup label is reassigned *"at the game level (whole games move
together)"*. **That is not implementable for `C1`–`C4`**, because `n_prior_games`, `min_hat`, `M1`
and `line_sd` vary **between players inside the same game** — there is no single label for a game
to carry. Only `C5` (`is_fallback`) is close to game-level, and even that varies within a game.

**What was done instead, and why it is disclosed rather than chosen quietly.** Two nulls were
computed and the **more conservative (larger) p-value** is reported as the headline for every
conditioner:

* `PERM_WITHIN_GAME` — labels permuted inside each game. Every game keeps its own label
  composition; no `d` value moves. This is the closest faithful reading of *"preserving `d`'s
  within-game structure"*.
* `PERM_WITHIN_PLAYER` — labels permuted inside each player, preserving player-level structure.
  This matters because the strongest conditioner (`C1`) is a player property, and a game-only null
  would leave player effects free to drive the result.

Neither is anticonservative in the way a plain row-level shuffle would be — the defect
`D093`/`D115`/`D117` spent four decisions repairing.

**The two nulls disagree sharply, which is exactly why both are reported:**

| conditioner | p (within game) | p (within player) | headline |
|---|---|---|---|
| C1 `n_prior_games` | 0.8022 | **0.0002** | 0.8022 |
| C2 `min_hat` | 0.8756 | 0.4953 | 0.8756 |
| C3 `M1` | **0.0002** | 0.3915 | 0.3915 |
| C4 `line_sd` | 0.0042 | 0.0398 | 0.0398 |
| C5 `is_fallback` | 0.0010 | 0.0002 | **0.0010** |

A three-order-of-magnitude disagreement on `C1` and `C3` means **the choice of permutation unit
dominates the p-value** for those conditioners. Any reader taking a single p from this table
without the other is being misled, which is why the headline is the maximum.

**Does it change the conclusion? No, and the reason is structural.** The §4 edge criteria do not
use the permutation p at all — they use the sign of `mean(d)`, the cluster-bootstrap interval, and
the materiality floor. The permutation is supporting evidence for *differences between* subgroups,
not for the edge test itself. Every subgroup is negative with an interval excluding zero under
both cluster levels, so `P1` is unaffected by anything in this table.

**Lesson:** specify a permutation unit that the conditioner actually lives at. "Game level" was
written by analogy to the clustering, without checking that each conditioner is constant within a
game. Four of five are not.

---

## D2 — the screen is underpowered by its own preregistered standard (P3 FAILS)

**Severity: A for what it forbids, none for what was found.**

PREREG §5.3: *"If the MDE for a subgroup exceeds the 0.10 materiality floor, that subgroup's null
is reported as UNINFORMATIVE."* **Zero of five conditioners have MDE < 0.10 in both halves.**
MDEs run from 0.099 (not cold start) to 1.484 (cold start).

**What this genuinely forbids:** claiming this screen rules out a *small* edge. It does not. In
the cold-start subgroup it could not have detected an edge below ~1.5 points; in the thin-history
half, below ~0.32.

**What it does not touch:** the finding actually made. Low power limits the detection of *small*
effects, not confidence in a *large* one already detected. Every one of the ten intervals excludes
zero on the negative side at 99%. **`P1` passes because every subgroup is negative, not because a
test failed to reject** — and that distinction is the whole difference between an informative
result and an uninformative one.

Recorded as a defect anyway, because a reader who sees "P3 FAIL" and stops has been served badly,
and one who sees "P1 PASS" without D2 has been served worse.

---

## D3 — ten subgroups from five median splits is a weak instrument, chosen deliberately

**Severity: C. Design limitation, declared in advance.**

Median splits throw away within-half structure; a continuous interaction would be strictly more
powerful. PREREG §8 registered this in advance and chose the weaker instrument on purpose, to hold
down researcher degrees of freedom in a family already carrying a Bonferroni correction.

**Consequence to hold onto:** a genuine edge concentrated in, say, the top decile of some
conditioner could be diluted to invisibility by a median split. This screen therefore rules out
edges that are *broadly distributed across half the population*, and is weak against edges that
are *sharply concentrated in a small tail*. The one sharply-concentrated effect it did find
(cold start, 7.4% of rows) was found only because `is_fallback` is a natural binary, not a split.

---

## D4 — the deficit decomposition in NOTES §3 is POST-HOC

**Severity: C, labelling.**

The three-bucket decomposition and the abstention table in `NOTES.md` §§3–4 are **not
preregistered**. They were computed after the frozen analysis returned, to characterise a
preregistered *failure* (`P4`, spread < 0.40, observed 2.99). They are descriptive arithmetic on
an already-established result rather than new hypothesis tests, and no p-value or interval is
attached to any of them.

They are labelled POST-HOC in `NOTES.md` at every occurrence. **The abstention numbers must not be
quoted as a validated improvement** — they describe what the 2024 data would have done, not what a
policy would do prospectively. A real abstention rule needs its own preregistration.

---

## D5 — one season, and the frame is inherited rather than rebuilt

**Severity: C, scope.**

n = 1,972 rows, 78 players, 262 games, season 2024 only, 40.2% selection. The frame is `D141`'s,
re-verified by hash at run time (`8605a559…47b7c8`) rather than rebuilt — so every construction
choice in `E1_I0058`, including its own recorded defects, is inherited here. That is deliberate:
rebuilding it would have produced a second, subtly different population and made the two screens
non-comparable.
