# Defects found in THIS screen's own construction

Written incrementally, at the moment of discovery, per the brief. A previous agent died holding a
warning it had not yet written down.

---

## SD1 — my CHECK I (cumulative-signature test) convicted constants. MY BUG, NOT THE KIT'S.

**Found:** S00 first run.

CHECK I tested "is this column non-decreasing within player-season by date?" as the signature of a
cumulative/expanding column. It flagged three columns at >0.9:

| column | frac non-decreasing | why it is NOT a cumulative |
|---|---|---|
| `PLAYER_ID` | 1.0000 | constant within player-season **by definition of the group** |
| `SHOT_ATTEMPTED_FLAG` | 1.0000 | globally constant, single value `1` across all 132,558 rows |
| `TEAM_ID` | 0.9633 | constant within player-season except for in-season trades |

**A constant sequence is non-decreasing.** The test as written cannot distinguish "never changes"
from "only ever goes up". The verdict `UNDETERMINED` produced by the first run was therefore an
artifact of my test, not a property of the data.

**Fix:** require *strict* increase somewhere — a column is a cumulative suspect only if it is
non-decreasing within the group **and** takes more than one distinct value inside that group.
Re-run under `s00_provenance.py` CHECK I v2.

**Generalisable lesson (not specific to shotcharts):** any monotonicity-based leakage probe needs a
non-degeneracy clause. This is the same shape as the kit's own K0 — a test whose *positive* branch
fires on a case it was never meant to cover.

---

## SD2 — I read `check_manifest(...)["verdict"]`; the field is `["status"]`. MY BUG.

**Found:** S00 first run. Every file printed `verdict=None`, which reads as "no verdict available"
when the kit had in fact returned `status="UNVERIFIABLE"` correctly and loudly.

`check_manifest` returns `status`, `usable_at_e0_e1`, `filtering_helps`, `note` — no `verdict` key.
`dict.get` returning `None` for a misspelled key is a silent failure mode, and in a provenance gate
a silent `None` could be misread as "clean". Fixed to read `status` and `usable_at_e0_e1`, and the
full returned dict is now dumped to `_s00.json` verbatim so no single key can hide the verdict.

**This is worth a kit note** (see NOTES.md kit feedback): the field a caller most wants is the one
whose absence is least visible.

---

## SD3 — `s02` first draft used the realised-game shot frame to define the player's own prior.

**Found:** while writing `s01_build_frame.py`; caught before any statistic was computed.

The natural join is shot-row -> player-game, then aggregate. The trap is that the aggregation
`groupby(player, game).mean()` gives the **realised** shot quality of the game being predicted,
which is measured from the outcome game and is forbidden. Every shot-quality column is therefore
built as `.shift(1).expanding()` **inside (player, season) ordered by date**, exactly as
`ep_base.prior_*` does, and the realised per-game value is retained ONLY as an intermediate that is
never used as a feature. `s01` asserts this by construction check: for every feature column, the
value on a player's first appearance of a season is NaN.

---

## SD4 — the entity-season decomposition that killed D085's 47 cells is NOT used here.

Not a defect found, a defect **declined**. `E0_I0016/ep_base.decompose()` splits a feature into an
entity-season mean plus remainder purely so the kit's `scheme="between"` becomes applicable. That
mean reads the whole season, so a game-5 row's value contains games 6-40. It is a
retrospective baseline that entered through the *inference machinery*.

This screen uses `screenkit.entity_swap_null` / `SCHEME_ENTITY_SWAP` instead, which is the kit's
own answer to the same problem and requires no decomposition of the feature at all. The
TIME-WINDOW TABLE in NOTES.md covers inference steps as well as features for exactly this reason.
