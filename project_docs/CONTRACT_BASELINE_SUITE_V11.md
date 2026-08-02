# `contract_baseline_suite_v11` + `prediction_contract_v4`

**Evidence label — definition, correction and executability only. No real MODEL fit, prediction,
score, accuracy result, coverage result, profitability result, or model output exists.** Real
artifacts are read and written and real frames are built and identity-bound; nothing is handed to
an estimator. Throughout this document **"coverage" means obligation completeness** — did every
required row receive a forecast slot — and never predictive accuracy.

Authorised by the Codex supervisory reply `20260802T025455738Z`, corrections 1–7.

---

## 1. Why this arm exists

v10 shipped a **green Layer-A gate (20/20, 1,266 assertions) over a real player path that could
not execute at all.**

```
MergeError: Merge keys are not unique in left dataset; not a one-to-one merge
```

`cbs_real_frames_v2.build_player_frame(season, require_attested=True)` raises this for **every
season 2021–2026**, not merely for 2024. `prediction_contract_v3` deliberately restored dual-team
obligations but kept the team-blind `row_uid = pg_uid(player_id, game_id)`, and the adapter joins
the master box on `(game_id, player_id)` with `validate="1:1"`. 28 obligations share 14 legacy ids.

The gate was green because **every v10 suite that touched the player path was synthetic at
precisely the boundary that had changed.** That is the lesson this arm encodes, and it is why
correction 6 — a real no-fit integration check in the standing gate — matters more than any
individual key fix. A green gate must mean the real path executes.

The v10 registration's contrary claim is corrected by
`contract_baseline_suite_v10__erratum_20260802` (registry line 90). The registry is append-only;
v10's own record is byte-identical.

---

## 2. The canonical key (`cbs_obligation_key/1`)

| name | rule | unique? | purpose |
|---|---|---|---|
| `row_uid` | `sha256(player_id, game_id, team_id)`[:16], `ob_` prefix | **yes** | the canonical prediction obligation key |
| `player_game_uid` | `sha256(player_id, game_id)`[:16], `pg_` prefix | no | legacy linkage, byte-identical to v2's `pg_uid` |
| `obligation_uid` | alias of `row_uid` | yes | naming continuity with v3's `ob_uid` |

Measured over the real universe: **35,627 obligations, 35,627 distinct canonical keys, 35,613
distinct legacy keys, 28 rows sharing 14 ids.**

**A design tension recorded rather than hidden.** The v1 contract chose a team-blind id *on
purpose* — its docstring says the id must not move when a team is restated. That reasoning is not
refuted: a retroactive trade correction **will** move a v4 `row_uid`. The cost is accepted because
a key that cannot uniquely name the thing being predicted cannot support a merge, a coverage count
or a scoring join, and v10 shows what that costs in practice. Stability of a name is worth less
than uniqueness of a referent.

**The row set is unchanged.** v3 → v4 is 35,627 → 35,627, 0 in and 0 out. Only the key changed;
any row-set change would have been a defect, and the receipt asserts its absence.

---

## 3. The seven corrections

### 1 — one unique team-bearing key end to end
Propagated through contract, frame, universe, manifest, runner, prediction, exclusion, coverage
and provenance receipts. `assert_unique_canonical_keys()` **raises rather than de-duplicating**:
silently dropping a duplicate is exactly how v2 deleted 14 obligations without a receipt.

### 2 — team-aware obligation joins
`cbs_real_frames/3` joins master on `(game_id, team_id, player_id)` and keys appearance evidence
on `(team_id, game_id)`.

Two measured findings that extend the supervisor's review:

- **The master-join corruption is 13 rows, not 11 of the 28.** Eleven are dual-team obligations;
  **two are single obligations registered to the club the player did not play for** — a case the
  dual-team framing does not cover. Of the 13, two imported a `DNP - Coach's Decision` and two
  imported `starter_flag=1` from another club.
- **The appearance index was the far larger defect, and it was silent.** `appeared_by_game` was
  keyed on `game_id`, which names a contest containing *two* clubs: **167 cross-club triples,
  1,347 corrupted lookups, 860 obligations affected across all six seasons** (worst 2025, 369).
  Roughly thirty times the merge defect, and it raised no error — it simply produced wrong
  team-history features.

**Trade fixture.** The old club's obligation carries `master_row_present=False`,
`starter_flag_observed=<NA>`, `dnp_class=NaN`, `played_last_team_game=0` — no starter, no DNP, no
appearance evidence from the new club — while the player's own minutes history correctly carries
across the trade. Absence is never coerced into a signal; the `if NaN:` trap that bit the v9 cycle
is asserted shut.

### 3 — candidate membership stated accurately
The implementation pools every prior **admitted** master box row **including DNP rows**; it does
not require actual appearance. The behaviour is **kept** — it is the more defensible recency-roster
proxy and preserves 35,627 obligations — but it is now registered as *"prior admitted team-game box
membership, including DNP rows"*, not *"appeared in a prior game"*. An appeared-only universe would
hold **32,438 rows, 3,189 fewer** — reproducing the supervisor's figure exactly.

### 4 — roster provenance bound to the candidacy records
`src_asof_roster` and `n_roster_games_consumed` now derive from the contract's
`admitted_window_bound` and `lookback_games_used`, plus a digest of the exact ordered window that a
timestamp cannot carry, enforced as a hard precondition in `cbs_provenance/4`.

**Proof the old coincidence was not a binding:** on the 2024 fold the bound is identical on
**22,659/22,659** rows while the **count differs on 19,830** — the contract uses a fixed five-game
candidacy window, the adapter a union read-window of usually ten. Agreement of the maxima was a
consequence of availability being monotone in `game_date`.

### 5 — cutoff identity strengthened
Eight fields compared and failing closed individually: `cutoff`, `policy`, `exact_cutoff_ok`,
scheduled tip, tip source, `observed_at`, quality, revision count. Result: **1,495 games, 0
mismatches.** (The supervisor named cutoff and policy "plus six more"; all eight are compared.)

The v3 tip-source guard is retained: `data/odds_capture/` is gitignored, so a naive run resolves
**2** exact tips instead of **407** and flips 1,086 games to the date-only policy. v4 refuses to
emit unless every game's cutoff and policy match the frozen source exactly.

### 6 — a real no-fit integration gate
`tests/test_cbs_real_integration_v11.py`, a **named standing check** in
`verify_all.REPOSITORY_CHECKS`. It builds both real player and team folds for **every season
2021–2026**, asserts unique canonical keys and exact universe coverage by `row_uid` set equality,
builds and binds the snapshot manifest, flows the duplicate-obligation fixture through the
**actual** validator, and asserts zero fits/predictions/scores.

### 7 — accounting labels closed
- **Candidate count per team-game** (2,990 team-games): min 0, max 17, mean 11.9154, median 12.
  The 76 zero-candidate team-games are all `season_opener_no_prior_in_season_game`. The contract's
  own distribution was keyed per *game*, not per *team-game*.
- **The three absent team ids are real franchise history, not data gaps:** Golden State Valkyries
  (first season 2025), Portland Fire (2026), Toronto Tempo (2026). All three absences are
  *leading*; no id has a gap after its first season, which is what a data gap would look like.
- **Franchise transition exception:** Phoenix Mercury, `team_id` 1611661317, abbreviation
  **PHO → PHX** in 2025 on a **stable id**, with identical city/arena/lat/lon/timezone — measured
  *not* a relocation. Consequence: `team_abbreviation` is not a safe cross-season join key. Zero
  relocations 2021–2026.
- **Explicitly undetermined:** whether any of those ids had a pre-2021 incarnation is not decidable
  from this repository — no artifact covers a season before 2021. An authoritative league franchise
  register would settle it.
- **The A15 receipt digest** is corrected in the erratum; see §5.

---

## 4. `cbs_snapshot_manifest/5` — a fan-in reconciliation

The branch that wrote `cbs_provenance_v4` reused `cbs_v10.SNAPSHOT_MANIFEST_SCHEMA`
(`cbs_snapshot_manifest/4`) while **also** adding three required fields to the manifest body:
`obligation_key_id`, `membership_rule_id`, `roster_binding_id`. No genuine v10-era `/4` manifest
carries them, so a checker enforcing them while still calling itself `/4` would be a second
contract wearing an existing name — the "two policies wearing one name" defect this codebase keeps
correcting.

The coordinator therefore introduced **`/5`**, and `/1`–`/4` are **refused, not superseded**,
following the discipline `cbs_v10` applied to `/1`–`/3`. `/4` is refused for a *different* reason
than `/1`–`/3` were: `/4`'s frame digests are sound, but a `/4` manifest does not name the
obligation key, so it cannot show that the digested rows were uniquely keyed. **A digest over a row
set that silently collapsed two obligations into one is a faithful digest of the wrong thing.**
v10's manifests remain valid `/4` documents; they are simply not `/5` documents.

---

## 5. Errata carried in this cycle

`contract_baseline_suite_v10__erratum_20260802` records four corrections:

1. **The false executability claim.** v10 stated the adapter builds and hashes real player folds.
   It builds none, for any season. The real *team* path does build for all six.
2. **The A15 receipt digest.** Recorded as `9ba369cc0186fdfd…`; the authoritative value is the raw
   SHA-256 of the bytes on disk, **`697595497db7eb97fe50ba4b1e5b92b043306b25ea7d9de6f64d4060af7de5a7`**.
   The quoted value is the digest of the file's **LF-normalized** content — all 205 of its line
   endings are CRLF — so it identifies a *transformation* of the file rather than the file, and can
   never be reproduced by hashing what is stored. It was additionally truncated to 16 of 64 hex
   characters. The bad digest had propagated into four documents.
3. **Candidate membership prose** — "appeared in a prior game" corrected to box membership
   including DNP rows.
4. **Sections 4 and 6 of the v10 spec doc were measured on the wrong universe.** Every number —
   185→0, 1,060→0, 23→0, 881, 25,498, 107 (57/42/7/1), 368/424/146 — **reproduces exactly**, but on
   the **v2** universe of 35,615 obligations, not v3's 35,627. They could not have been measured on
   v3, because `build_player_frame` cannot run on v3 at all. The arithmetic was right and the label
   was wrong. They are now receipted with the universe they were measured on, in
   `experiments/cbs_accounting_v11/`, and are **not** re-asserted for v3 or v4.

---

## 6. Execution shape

The supervisor proposed three parallel branches. The coordinator ran **A** (contract
key/provenance) and **C1** (accounting/errata) in parallel because they are genuinely independent,
then **B** (team-aware adapter) and **C2** (real integration gate), which depend on A's artifacts.
Presenting B and C2 as simultaneous would have been a false claim of parallelism.

The coordinator wrote the shared key contract (`cbs_obligation_key.py`) **before** fan-out so every
branch built against one definition rather than three guesses, verified each branch's output
independently rather than accepting its report, reconciled the `/4`→`/5` overlap at fan-in, and ran
one unified gate.

---

## 7. What is still not done

- **No real fit, prediction, score, accuracy/coverage result or profitability evaluation.** Not
  authorised, not performed.
- **Layer B (operational certification) is not claimed.** The coordinator did inadvertently execute
  it once via a bare `verify_all.py` and recorded the result honestly — `FAIL (1 fail, 2 warn, 7
  pass/skip)` on `odds capture freshness` — but `verify_all` itself states the operational layer
  must run on the capture machine, which a clean checkout is not. It is **not** evidence of an
  operational defect and is **not** a Layer-B certification. The latest genuine Layer-B result
  remains **B5**.
- The Layer-B aggregate input hash will change again: the `prediction_contract_v4` and
  `cbs_accounting_v11` artifacts and sidecars enter the glob set.
- **No PR** — `gh` is not installed on this machine.
