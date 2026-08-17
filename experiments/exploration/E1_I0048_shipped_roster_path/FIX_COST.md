# Blast radius of a fix — reported, not paid

**Nothing in this document was enacted. No production file was modified.**

The brief asked for the cost of a hypothetical repair to the shipped roster path, on the reasoning
that "a cheap fix on the shipped side may be worth far more than an expensive one on the research
side". The answer changes the question:

**The shipped-side fix has already been designed, implemented, tested, adopted and wired into
production. It landed on 2026-08-06, one day after E1_I0045 identified the defect and one day
before this screen ran. There is no fix left to cost.**

What follows is therefore (§1) what the paid fix actually cost, as a reference price for the next
one; (§2) the small residue that remains; and (§3) the cost of the research-side repair E1_I0045
priced, restated so the comparison the brief wanted can still be made.

---

## 1. The fix that was already paid

| component | file | size |
|---|---|---:|
| production module | `entity_resolution.py` | 16,787 B |
| adoption tests | `ops_adoption_tests/O14/test_o14.py` | 23,170 B |
| baseline comparison | `ops_adoption_tests/O14/baseline_port.py` | 3,909 B |
| wiring specification | `ops_adoption_tests/O14/B_HANDOFF.md` | 7,133 B |
| alias table artifact | `data/entity_resolution/alias_table.json` | schema `ops_lane/O14/alias_table/1`, empty by design |
| capture-path adopters | `injury_capture_daily.py`, `props_capture_daily.py`, `migrate_o14_capture_player_id.py` | 3 files |
| forecast-path adopter | `daily_forecast.py` (`player_layer` reduced to a 10-line delegation) | 1 file |

**Seven production files touched; four new artifacts; one research node
(`experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION`, referenced as the design
source) that does not exist in this worktree.** The test file is larger than the module it tests,
which is the right ratio for a change to a scheduled critical path.

Notably, the fix **did not** require what E1_I0045 feared. It needed no entity-resolution step
bolted on to port a research rule, because it did not port a research rule — it replaced the
construction with one keyed on the id that was already present. Cost of the key change itself:
one line.

---

## 2. The residue, and what each item is worth

Four items remain. None is a model change; three are documentation or hygiene; **all four are the
user's to authorise, and none was enacted.**

### R-1 — The worktree copy still carries the defective code. *(Cost: zero. Do nothing.)*

`.claude/worktrees/player-model-program/daily_forecast.py` is still at the `735b63bc` shape
(1,300 lines vs production's 1,523). This is what E1_I0045 read. It is a research worktree, it is
on no scheduler, and worktrees are expected to lag. **The action item is not to change the file —
it is that a screen citing `daily_forecast.py:NNN` should record which worktree it read and the
git sha, because this screen has now seen a case where that distinction inverted a conclusion.**

### R-2 — `entity_resolution.py`'s docstring is stale. *(Cost: one comment. Not enacted.)*

Lines 31–34 state:

> `player_layer_resolved()` is the designed replacement for the roster/availability construction
> in `daily_forecast.player_layer` (`daily_forecast.py:640-760`). **`daily_forecast.py` is NOT
> modified here**; the exact wiring is specified in `ops_adoption_tests/O14/B_HANDOFF.md`.

`daily_forecast.py` **was** modified, four hours later, in `55d84f1e`. The docstring describes the
module's status at authoring time and is now false about production. It also cites
`daily_forecast.py:640-760`, line numbers that no longer point at the roster code. Anyone reading
the module to decide whether the fix is live gets the wrong answer. A two-line correction; it is
still a production file and therefore still the user's call.

### R-3 — Records 0–39 permanently carry pre-repair rosters. *(Cost: do not attempt a fix.)*

They are inside the regime-D hash chain. Correcting them would break `verify_chain`, which is the
entire point of the chain. Since nothing reads the fields (`CONSUMERS.md`) and the measured damage
is zero (`SHIPPED_DAMAGE.csv`), **the correct action is none.** Recorded here so that a later
reader who discovers the era split does not propose a migration.

### R-4 — The alias table is empty and depends on box-score-first appearances. *(Cost: an ops runbook line, not code.)*

Described in `NAME_KEY.md` §6. A player whose first appearance under a new name is on an injury
report now raises `BLOCK` — correct, fail-closed, and an operational event that needs an owner.

---

## 3. The comparison the brief wanted

E1_I0045 priced the research-side repair — a currency rule on the contract universe — at ~32
`player_program` files, the `cbs_v12`–`cbs_v15` estimator stack, ten exploration screens and the
contract test suite, *plus* invalidation of every cached frame and receipt keyed on the row set,
**for a benefit it could not distinguish from the cheaper calibration fix.**

| | contract-side currency rule (unpaid) | shipped-side identity fix (**paid**) |
|---|---|---|
| production files touched | 0 | 7 |
| research files invalidated | ~32 + cbs_v12–v15 + 10 screens + contract tests | 0 |
| cached frames / receipts invalidated | all, keyed on the row set | none |
| changes shipped output | **no** | **yes** — records 40+ |
| measured benefit | indistinguishable from the cheaper option | closes a live-path identity hazard before it fired |
| status | **still unenacted; still the user's decision** | **enacted 2026-08-06** |

The brief's intuition was right, and the ordering it predicted is what actually happened: the
cheap fix on the shipped side was worth more than the expensive one on the research side, and it
is the one that got done. **The expensive research-side change remains unenacted and this screen
recommends nothing about it** — that verdict belongs to E1_I0045 and to the user.

---

## 4. What this screen recommends

**Nothing that touches a production file.** The one substantive finding is that a defect logged
as live is not live, which is a correction to the record rather than a change to the system. If
any of R-1 through R-4 is to be actioned, it is a separate, authorised act.
