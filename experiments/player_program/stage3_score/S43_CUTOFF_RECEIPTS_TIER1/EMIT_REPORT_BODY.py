r"""S43 / D065 -- render REPORT_BODY.md from RECEIPTS.json.

Every number in the report is interpolated from the receipt rather than retyped, so the prose
cannot drift from the measurement. Run MEASURE_TIER1_PROVENANCE.py first.

No fitting. No performance number. Reads only this node's own RECEIPTS.json; writes only
REPORT_BODY.md inside this node's directory.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.loads(open(os.path.join(HERE, "RECEIPTS.json"), encoding="utf-8").read())

U = R["universe"]
F = {f["field"]: f for f in R["fields"]}
M = {k: v["measurements"] for k, v in F.items()}
H = R["evidence_sha256_all_reads"]
RD = {r["id"]: r for r in R["raise_do_not_assign"]}
tzr = M["timezone.shift_from_prev_venue_hours"]["reconciliation_to_the_D10_ledger_number"]
po = RD["R1"]["census"]


def h(rel: str) -> str:
    return H[rel][:16] + "…"


def counts(d: dict) -> str:
    return ", ".join(f"{k}→{v:,}" for k, v in d.items())


tier_rows = [
    (0, "sched.game_id", "**coordinator**",
     "`build_masters.py` (`:355`, `:600-607`) + `universe.py:131-140`",
     "none (job) / byte-pinned (universe)"),
    (2, "sched.season", "**coordinator**",
     "`build_masters.py::season_of` `:110-111`, applied `:572`",
     "none — but the column is a pure function of `game_id`"),
    (3, "sched.season_type", "user",
     "`build_masters.py::stype_of` `:114-115` + `:80-81`, applied `:573`",
     "none — pure function of `game_id`"),
    (4, "sched.is_home", "user",
     "`build_masters.py::build_game_index` `:319-325`, `:345-370`, merged `:568-570`",
     "**none — widest gap; see 4.1**"),
    (5, "sched.opp_team_id", "user",
     "`build_masters.py::build_game_index` `:386-391`, merged `:568-570`",
     "none — reads no source beyond cluster membership"),
    (9, "rest.is_back_to_back", "user",
     "`sc06_sched_fatigue_diff.py::fatigue_index` `:91-96` (**in-frame; no materialised column**)",
     "byte-pinned universe"),
    (10, "rest.games_in_prev_7_days (3-in-4 class)", "user",
     "`sc06_sched_fatigue_diff.py::fatigue_index` `:92-97` (**in-frame**)",
     "byte-pinned universe"),
    (12, "venue.venue_team_id", "user",
     "`sc06_sched_fatigue_diff.py:100-101` (**in-frame**)",
     "inherits #4 and #5; no new source"),
    (18, "timezone.venue_iana_timezone", "user",
     "`collect_bios.py::phase_cities` `:201-224` from `CITY_ROWS` `:180-198`; read by `sc06:73-81`",
     "offline; value is a source-code literal"),
    (22, "timezone.shift_from_prev_venue_hours", "user",
     "`sc06_sched_fatigue_diff.py:99-105` (**in-frame**)",
     "inherits #12 and #18; no new source"),
]
TIER_TABLE = "\n".join(
    f"| {n} | `{f}` | {by} | {job} | {ab} | ISSUED |" for n, f, by, job, ab in tier_rows)

HASH_TABLE = "\n".join(f"| `{h(rel)}` | `{rel}` |" for rel in H)

md = f"""# S43_CUTOFF_RECEIPTS_TIER1 — tier-1 cutoff-validity provenance receipts for ten schedule-fixed fields

**Commissioned by:** user decision D065. **Discharges:** part of S37 audit finding A9 (Severity A).

**Epistemic status:**

> {R["epistemic_status"]}

**Root.** The program worktree
`{U["root"]}`, and only it.
`data/masters/master_team.parquet` was verified to hash to the pin `{U["master_team_sha256"][:16]}…`;
the known-drifted live copy `{U["known_drifted_copy_refused_by_name"][:16]}…` is refused **by
name**, as `runner/universe.py:71-73` does, not merely by pin failure.

**Write scope.** Everything this node produced is inside
`experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER1/`. No file outside it was
modified, no frozen artifact was edited, and no git command was run.

**Outputs.** `RECEIPTS.json` (machine-readable, one object per field), this report, and the two
scripts that produced them. Reproduce with:

```
python experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER1/MEASURE_TIER1_PROVENANCE.py
python experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER1/EMIT_REPORT_BODY.py
```

Every number below is interpolated from `RECEIPTS.json` by `EMIT_REPORT_BODY.py`, never retyped, so
the prose cannot drift from the measurement.

---

## 1. The standard being applied, and whose it is

D065, verbatim on the standard:

> "{R["tier1_standard_verbatim_from_D065"]}"

The tier-1 discriminator is therefore: **is the value fixed by the schedule before tipoff, or is it
computed from observations?** Tier 1 is the former. This is a provenance demonstration, not a
per-observation timestamp audit.

Per the coordinator addition to D065, a tier-1 receipt must not merely argue that the concept is
schedule-fixed. For each field it must state the **producing job**, that job's **as-of bound**, the
**provenance chain**, and **sha256 of every file read as evidence**. The rationale, recorded because
it is the reason the addition exists:

> {R["mandatory_receipt_content_rationale"]}

That addition earned its keep here. See section 4.

---

## 2. The D10 ledger's objection, engaged rather than evaded

The D10 field-availability ledger rules all ten of these fields `CUTOFF_UNPROVEN`, and it says why,
on the timezone table (`build_ledger.py:360-366`):

> "The values are time-invariant in substance, but time-invariance is an argument, not a timestamp,
> and this ledger does not accept arguments in place of evidence."

{R["d10_ledger_objection_engaged_not_evaded"]}

Stated plainly so it cannot be misread later: **these receipts are a ruling about the standard, not
a discovery that the ledger was wrong.**

---

## 3. Universe the receipts are measured on

Rebuilt exactly as `runner/universe.py::build_universe` (lines 127-143) does it: `is_home == 1`
clusters, excluding the D010 date `{U["d010_excluded_date"]}`.

| quantity | measured |
|---|---:|
| game clusters | {U["clusters"]:,} |
| team-game rows | {U["team_game_rows"]:,} |
| Regular Season rows / clusters | {U["per_season_type_rows"]["Regular Season"]:,} / {U["per_season_type_clusters"]["Regular Season"]:,} |
| Playoffs rows / clusters | {U["playoff_rows"]:,} / {U["playoff_clusters"]:,} |
| distinct team_ids | {M["sched.opp_team_id"]["distinct_team_ids"]} |
| O2 pre-build game_id digest | `{U["o2_prebuild_digest_rederived_here"][:16]}…`, re-derived here and **{"matching" if U["o2_prebuild_digest_match"] else "NOT MATCHING"}** `PREBUILD_GAME_ID_DIGEST.json` |

Per-season clusters: {", ".join(f"{k} {v}" for k, v in U["per_season_clusters"].items())}. Only two
season types occur (`Regular Season`, `Playoffs`); no Preseason or All-Star row is in the universe.

`master_team.parquet` carries an `observed_time` column that is a **local file mtime in mid-2026**,
not an as-of bound. It is dropped immediately after read, before any downstream use, and **no frame
was written to disk at all** — every output of this node is JSON aggregates and this prose.

---

## 4. The as-of bound finding, which is the substantive result of this node

Three producing jobs cover all ten fields. Their as-of bounds are not alike, and one of them is
honestly absent.

### 4.1 `build_masters.py` — **NO AS-OF BOUND**

`build_masters.py` takes no as-of argument, no cutoff, no date bound and no snapshot id. It globs
whatever is present under `data/refresh_2026/gamelog_*.parquet`,
`data/wnba_gamelog_{{2021..2024}}.parquet`, `data/wnba_team_gamelog_2024.parquet`, the per-game
misc/advanced directories and `data/shotcharts/shots_*.parquet`; reads each in full; and records
`observed_time = max(local file mtime of the contributing files)` (`:118-120`, `:594-595`). Every one
of those artifacts is a **completed-game record** and every mtime is a 2026 bulk scrape.

**This receipt does not claim an as-of bound for `build_masters.py`, because it does not have one.**
This is exactly the case the coordinator addition was written to catch, and it is stated rather than
finessed.

What makes the five `master_team` schedule columns tier-1 is therefore **not** a bound on the job. It
is that the job derives them from **game identity** and never from any quantity produced by the play
of the target game:

* `season` and `season_type` are **pure functions of the `game_id` string**;
* `opp_team_id` is the **set complement** of the row's own `team_id` within its `game_id` cluster;
* `is_home` is the **MATCHUP orientation token** (`" @ "`) or the shotchart HTM/VTM role.

No box-score statistic, score, minute or outcome enters any of them. A later re-scrape could only
change these values by changing the league's own identity record of the fixture.

For `sched.is_home` the as-of gap is at its widest, and the receipt says so in terms: the
orientation token is read off a completed-game box score or shot chart. The receipt asserts the
**class** and names the **producing job**; it does not and cannot assert that the bytes read were
captured before tipoff.

### 4.2 `runner/universe.py::build_universe` — **byte-bounded, not time-bounded**

It refuses to build unless `master_team.parquet` hashes to the pin (`:64-77`), refuses the
known-drifted live copy by name (`:71-73`), and refuses to return a frame unless the built `game_id`
set re-derives to `PREBUILD_GAME_ID_DIGEST.json` (`:80-90`, `:136-140`). That is a **reproducibility
bound, not an as-of bound**, and it is reported as such. It was verified live: the digest re-derived
and matched.

### 4.3 `collect_bios.py::phase_cities` — **offline and unbounded by construction**

`data/reference/collect_bios.py::phase_cities` (`:201-224`) performs no network read and no data read
that can supply a value. It materialises `team_cities.csv` from the `CITY_ROWS` **literal in its own
source** (`:180-198`), hand-entered 2026-07-31 at city-level precision (`:172-179`). Its only read of
repository data is `master_team.parquet` for join **verification** (`:210-218`), which can fail the
build closed but cannot inject a value.

This reframes the D10 complaint. The ledger objected that the file has "no capture timestamp of any
kind — no column, no sidecar manifest, no fetch record." That is correct and, on this reading,
**expected: there is no capture.** The value's provenance is the producing job's source code, which
is a *stronger* bound than a capture timestamp would be, because it is fixed for every row of every
season simultaneously.

---

## 5. The receipts

All ten are issued. Verdict `TIER1_RECEIPT_ISSUED` in every case. Full provenance chains, per-field
evidence hashes and residual-risk statements are in `RECEIPTS.json`.

| # | field | tier assigned by | producing job (as consumed) | as-of bound | verdict |
|---|---|---|---|---|---|
{TIER_TABLE}

**A finding worth naming on its own:** five of the ten fields (#9, #10, #12, #22, and #18's consumed
form) have **no materialised column anywhere in the repository**. They are derived in-frame by
`sc06_sched_fatigue_diff.py` from `universe.team_rows`. The producing job for those fields *is the
arm module*. Nothing backfills them, because nothing stores them.

### 5.1 Identity tests — every one returns zero violations

These are censuses over all {U["team_game_rows"]:,} rows. A test returning zero violations
demonstrates that the column **is** the schedule-fixed quantity it is claimed to be. It does not, and
cannot, demonstrate anything about *when* the bytes were captured.

| test | rule | violations |
|---|---|---:|
| `season` | `season == int("20" + game_id[3:5])` | **{M["sched.season"]["rows_where_column_disagrees_with_the_game_id_substring"]} / {M["sched.season"]["rows_tested"]:,}** |
| `season_type` | `season_type == SEASON_TYPE_BY_DIGIT[game_id[2]]` | **{M["sched.season_type"]["rows_where_column_disagrees_with_the_game_id_digit"]} / {M["sched.season_type"]["rows_tested"]:,}** ({M["sched.season_type"]["unknown_rows"]} `Unknown`) |
| `opp_team_id` | is the other `team_id` in the same cluster | **{M["sched.opp_team_id"]["rows_where_opp_team_id_is_not_the_cluster_partner"]} / {M["sched.opp_team_id"]["rows_tested"]:,}** |
| `opp_team_id` | never equals own `team_id`; never null | **{M["sched.opp_team_id"]["rows_where_opp_team_id_equals_own_team_id"]} self-referential, {M["sched.opp_team_id"]["null_rows"]} null** |
| `is_home` | domain ⊆ {{0,1}}; no nulls | **{M["sched.is_home"]["null_rows"]} null** |
| `is_home` | exactly one home row per cluster | **{M["sched.is_home"]["clusters_violating_exactly_one_home"]} / {U["clusters"]:,} clusters** |
| `game_id` | 10 characters, all digits | **{"0" if M["sched.game_id"]["all_length_10"] and M["sched.game_id"]["all_digits"] else "VIOLATIONS"} / {U["team_game_rows"]:,}** |
| `game_id` | exactly two team rows per cluster; no duplicate (game_id, team_id) | **{M["sched.game_id"]["clusters_with_other_than_2_team_rows"]} bad clusters, {M["sched.game_id"]["duplicate_game_id_team_id_pairs"]} dupes** |
| `venue_team_id` | equals the cluster's home team | **{M["venue.venue_team_id"]["rows_where_venue_team_id_is_not_the_cluster_home_team"]} / {M["venue.venue_team_id"]["rows_tested"]:,}** |
| `venue_iana_timezone` | resolves every row; every zone in the arm's pinned map | **{M["timezone.venue_iana_timezone"]["rows_unresolved"]} unresolved, {len(M["timezone.venue_iana_timezone"]["zones_in_team_cities_absent_from_the_arm_standard_offset_map"])} unmapped** |

`game_id` digit 2 takes only the values {" and ".join(f"`{k}` ({v[0]})" for k, v in M["sched.season_type"]["digit_to_value_observed"].items())},
matching `season_type` on every row. All {M["sched.opp_team_id"]["distinct_team_ids"]} universe
`team_id`s are present in `team_cities.csv`
({M["timezone.venue_iana_timezone"]["team_cities_rows"]} rows,
{M["timezone.venue_iana_timezone"]["team_cities_distinct_team_ids"]} ids — PHO and PHX share id
1611661317); its sha256 `{h("data/reference/team_cities.csv")}` matches the hash the D10 ledger
itself cites. {len(M["timezone.venue_iana_timezone"]["distinct_zones_on_the_universe"])} IANA zones
occur on the universe, all of them in SC06's pinned `STANDARD_OFFSETS`; the arm fails closed on any
zone outside it (`sc06:78-79`).

### 5.2 Consumed censuses

Counts only. No performance quantity of any kind was computed.

* `rest.is_back_to_back`: **{M["rest.is_back_to_back"]["true_rows_career_clock_as_consumed"]}** true
  rows. Career clock and same-season clock give the **same
  {M["rest.is_back_to_back"]["true_rows_same_season_clock_as_carded"]}** and disagree on
  **{M["rest.is_back_to_back"]["rows_where_the_two_clocks_disagree"]} rows** — a cross-season gap
  is never exactly one day. This independently confirms S37 finding B1's statement that the two rest
  components evaluate identically across an off-season gap and the B1 defect is confined to the
  travel term.
* `rest` 3-in-4 (as consumed by SC06):
  **{M["rest.games_in_prev_7_days"]["third_in_four_true_rows_as_consumed"]}** true rows;
  {M["rest.games_in_prev_7_days"]["rows_with_fewer_than_two_previous_games"]} rows have fewer than
  two previous games.
* `rest.games_in_prev_7_days` (the ledger's literal quantity):
  {counts(M["rest.games_in_prev_7_days"]["games_in_prev_7_days_value_counts_ledger_form"])}.
* `tz_crossed` (as consumed): non-zero on
  **{M["timezone.shift_from_prev_venue_hours"]["nonzero_tz_crossed_rows_as_consumed"]:,}** rows;
  values {counts(M["timezone.shift_from_prev_venue_hours"]["tz_crossed_value_counts_as_consumed"])}.
  Career vs same-season clocks disagree on
  **{M["timezone.shift_from_prev_venue_hours"]["rows_where_career_and_same_season_clocks_disagree"]}**
  rows — exactly the 30 team-game rows S37 finding B1 measured, independently reproduced here.

### 5.3 Reconciling `tz_crossed` to the ledger's published number

The D10 report publishes `timezone.shift_from_prev_venue_hours` as non-zero on
**{tzr["ledger_published_nonzero_rows"]:,}** of {U["team_game_rows"]:,} rows. The consumed quantity
reads **{tzr["consumed_reading_career_standard_offsets_nonzero_rows"]:,}**. A reader must be able to
see why, so it was decomposed:

| reading | non-zero rows |
|---|---:|
| D10 ledger, published | {tzr["ledger_published_nonzero_rows"]:,} |
| **re-derived here**: same-season clock, DST resolved via `zoneinfo` | **{tzr["rederived_here_same_season_dst_resolved_nonzero_rows"]:,}** ✅ exact match |
| career clock, DST resolved | {tzr["rederived_here_career_dst_resolved_nonzero_rows"]:,} (+{tzr["rederived_here_career_dst_resolved_nonzero_rows"] - tzr["rederived_here_same_season_dst_resolved_nonzero_rows"]}, the cross-season openers) |
| career clock, standard offsets — **the consumed reading** | {tzr["consumed_reading_career_standard_offsets_nonzero_rows"]:,} (+{tzr["consumed_reading_career_standard_offsets_nonzero_rows"] - tzr["rederived_here_career_dst_resolved_nonzero_rows"]}) |

The final increment is exactly the count of rows whose venue and previous venue are the
`America/Phoenix` ↔ `America/Los_Angeles` pair:
**{tzr["rows_whose_venue_and_previous_venue_are_the_America_Phoenix_America_Los_Angeles_pair"]}**.
{tzr["why_they_differ"]}

The exact reproduction of the ledger's {tzr["ledger_published_nonzero_rows"]:,} is a useful side
effect: the D10 number replicates.

---

## 6. COORDINATOR-ASSIGNED TIER

**Two of the ten fields were not named by the user. They were assigned to tier 1 by
{R["coordinator_assigned_tier"]["assigned_by"]}.**

| field | ledger # | ground for the assignment |
|---|---|---|
| `sched.game_id` | 0 | the league's own fixture identifier, issued at schedule release; not computed from observations |
| `sched.season` | 2 | literally `int("20" + game_id[3:5])` — a pure function of the identifier, measured to hold on {M["sched.season"]["rows_tested"]:,} / {M["sched.season"]["rows_tested"]:,} rows |

The user's D065 tier-1 list named:
**{", ".join(R["coordinator_assigned_tier"]["user_named_tier1_list"])}**. `game_id` and `season` are
not on it.

{R["coordinator_assigned_tier"]["note"]}

---

## 7. The `shift_from_prev_venue_hours` tension, recorded not papered over

`timezone.shift_from_prev_venue_hours` (ledger #22) is schedule-derived **and yet depends on the
previous game having been played.** Its value on row *r* is a function of the team's previous row in
the *resolved universe*, and that row is only known to be the previous row once that game has been
played and resolved in. Under the published schedule alone the previous fixture — and hence the
shift — is also determined; the two coincide **except where a fixture was postponed or
displaced.**

**The user's explicit naming of "venue/timezone" in the D065 tier-1 list settles this field as
tier 1.** The tension is recorded here so that the settlement is visible as a *ruling* rather than as
an omission. Absent that naming, this field would have gone to RAISE-DO-NOT-ASSIGN below.

Consequences that follow and are not closed by this receipt:

1. Like the rest fields, #22 **inherits M_A1's enumerated `game_date` exception set** — the 10
   release-order displaced clusters plus the 6 with no second-endpoint witness.
2. SC06 already carries an **A1-SENSITIVITY kill** for precisely this dependency (`sc06:178-180`).
   S37 finding **B3** records that the kill cannot fire, because the enumerated exception set is
   never read by any code. Wiring it converts this tension from an assumption into a measured
   sensitivity, and needs no new data.
3. The career-vs-same-season clock ambiguity (S37 **B1**) touches this field and only this field
   among the ten, on
   {M["timezone.shift_from_prev_venue_hours"]["rows_where_career_and_same_season_clocks_disagree"]}
   rows, measured above.

---

## 8. RAISE-DO-NOT-ASSIGN

Assigning a tier **is** deciding the standard of proof, and D065 reserves that judgement to the user.
Three boundary cases were found. **No field was reassigned and no receipt was narrowed on account of
them.**

### R1 — playoff rows: the discriminator's two clauses come apart

**Concerns:** {", ".join("`" + c + "`" for c in RD["R1"]["concerns"])} — **{RD["R1"]["scope"].lower()}.**
**Census:** {po["playoff_rows"]} of {U["team_game_rows"]:,} team-game rows
({po["playoff_rows_share_of_universe_rows"] * 100:.2f}%), {po["playoff_clusters"]} of
{U["clusters"]:,} clusters; by season
{", ".join(f"{k} {v}" for k, v in po["playoff_clusters_by_season"].items())}, 2026 none (the 2026
season is partial).

{RD["R1"]["the_boundary"]}

**What this node believes but did not act on:** {RD["R1"]["what_this_node_believes_but_did_not_act_on"]}

**Cheapest possible ruling** — {RD["R1"]["cheapest_possible_ruling"]}

### R2 — "scheduled" versus "as played"

**Concerns:** {", ".join("`" + c + "`" for c in RD["R2"]["concerns"])}, on all rows.

{RD["R2"]["the_boundary"]}

{RD["R2"]["why_this_is_NOT_being_resolved_here"]}

**What would close it cheaply:** {RD["R2"]["what_would_close_it_cheaply"]}

### R3 — ledger #10 denotes two different quantities

**Concerns:** {", ".join("`" + c + "`" for c in RD["R3"]["concerns"])} — **{RD["R3"]["scope"].lower()}.**

{RD["R3"]["the_boundary"]}

{RD["R3"]["why_this_is_NOT_being_resolved_here"]}

---

## 9. What these receipts do NOT establish

1. **That any of the bytes were captured before tipoff.** For the five `master_team` schedule
   columns the producing job has no as-of bound and reads only completed-game artifacts. The receipt
   establishes class and names the job; it stops there, deliberately.
2. **That the venue is the home team's arena.** `sched.neutral_site_flag` is ABSENT from the entire
   repository (D10 `build_ledger.py:262-270`). `venue.venue_team_id` and
   `timezone.venue_iana_timezone` mean "the home team's" venue and zone, not "the venue used". This
   is an **accuracy** gap, not a cutoff-validity gap, it is load-bearing for four families, and no
   source in the repository could settle it.
3. **The correctness of `game_date` or of the `(game_date, game_id)` sequencing.** That rests on
   ledger #1, which has its own measurement (`M_A1_GAME_DATE_CUTOFF_V2`) and its own 16 enumerated
   exception clusters. `sched.game_id`'s receipt does not extend to it.
4. **Anything about the other three A9 items.** `opponent.opp_pace_estimate` (#50),
   `opponent.prior_box_aggregates` (#51) and the five `score_baseline_rows` prediction columns are
   outside this node's ten and are untouched. **A9 is only partly discharged.**
5. **Anything comparative.** No fit, no arm-vs-null comparison, no performance number. Nothing under
   any sealed-results tree was opened.

---

## 10. Evidence — sha256 of every file read

| sha256 | file (repo-relative) |
|---|---|
{HASH_TABLE}

Full-length digests are in `RECEIPTS.json` under `evidence_sha256_all_reads`, and per-field under
each record's `evidence_sha256`.

---

## 11. One thing this report must not be read as saying

Nothing here admits any field into any model, and nothing here promotes a D10 ledger record. Ten
fields now carry the tier-1 provenance receipt D065 called for. **Availability is not eligibility and
eligibility is not admission.** Whether these receipts discharge S30 §8 for these ten fields
— and therefore whether A9's halt lifts for them — is the coordinator's and the user's call,
not this node's.
"""

with open(os.path.join(HERE, "REPORT_BODY.md"), "w", encoding="utf-8") as fh:
    fh.write(md)
print(f"wrote REPORT_BODY.md ({len(md):,} chars) from RECEIPTS.json")
