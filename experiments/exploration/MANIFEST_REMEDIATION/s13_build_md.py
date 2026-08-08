# -*- coding: utf-8 -*-
import json, os, collections

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")
P = json.load(open(os.path.join(OUT, "REMEDIATION_PLAN.json"), encoding="utf-8"))
A = P["artifacts"]
L = []
w = L.append

w("# Manifest remediation plan - the 68 unmanifested shared artifacts")
w("")
w("**No manifest was written by this analysis.** This is a plan. Writing a manifest asserts a")
w("provenance claim about someone else's artifact, and a wrong one is worse than a missing one")
w("because it converts *unverifiable* into *falsely verified*.")
w("")
w("Input: `experiments/exploration/AUDIT_baseline_provenance/MISSING_MANIFESTS.json`.")
w("Classification method: producers located by scanning 762 `.py` files, then the build code was")
w("**read** and the construction line quoted. Regex only ever located candidates; no text match")
w("stands as a finding. Lineage was traced through inputs, so inherited granularity is captured.")
w("")

w("## The headline")
w("")
c = P["counts"]
w("| | count |")
w("|---|---|")
w("| Artifacts in scope | %d |" % c["total"])
w("| **Live contamination** (artifact-granular AND embeds 2025/2026 AND live) | **%d** |" %
  c["by_group"]["LIVE CONTAMINATION - needs a re-run or a scope decision, not just paperwork"])
w("| **Safe / honestly bounded - needs only a manifest** | **%d** |" %
  c["by_group"]["SAFE / HONESTLY-BOUNDED - needs only a manifest"])
w("| **Undetermined - needs a human decision** | **%d** |" %
  c["by_group"]["UNDETERMINED - needs a human decision"])
w("| **Dead / unused - ignorable** | **%d** |" %
  c["by_group"]["DEAD or UNUSED - ignorable"])
w("")
w("Proposed granularity: **%d ROW**, **%d ARTIFACT**, **%d UNDETERMINED**." %
  (c["by_granularity"].get("ROW", 0), c["by_granularity"].get("ARTIFACT", 0),
   c["by_granularity"].get("UNDETERMINED", 0)))
w("Confidence: %d HIGH, %d MEDIUM, %d NONE. %d of the 68 are consumed by a PASSED graph node." %
  (c["by_confidence"].get("HIGH", 0), c["by_confidence"].get("MEDIUM", 0),
   c["by_confidence"].get("NONE", 0), c["consumed_by_a_passed_node"]))
w("")

w("### The single most useful distinction in this document")
w("")
w("Thirty of the 68 are artifact-granular, but they are **not all contaminated**. They split three ways:")
w("")
w("- **%d embed holdout data** (`SPANS_HOLDOUT`). All six inherit from `cbs_v15_player_oof_v5`" %
  c["by_holdout_risk"].get("SPANS_HOLDOUT", 0))
w("  prediction files whose own manifests already declare `asof_granularity: \"artifact\"`. This is")
w("  the real-contamination set.")
w("- **%d pool across rows but only inside 2021-2024** (`PARTITION_ONLY_LOOKAHEAD`). Every one of" %
  c["by_holdout_risk"].get("PARTITION_ONLY_LOOKAHEAD", 0))
w("  these is an exploration frame whose build script hard-filters to the partition on **column**")
w("  **values** before it pools anything. A 2021 row in these files cannot contain 2026 information.")
w("  They are still not `row`-granular and must not be manifested as such - but they need no re-run.")
w("- **%d are capture logs, static dimensions or realised-outcome targets** with no pooling at all." %
  c["by_holdout_risk"].get("NONE", 0))
w("")
w("**In short: the sweep found no new holdout contamination.** The six `SPANS_HOLDOUT` artifacts all")
w("trace to one already-known and already-declared source. The rest of the artifact-granular set is")
w("a paperwork problem, and a good deal of the paperwork can say `row` honestly.")
w("")

w("## Priority ranking (consumers x liveness)")
w("")
w("Liveness resolved two ways: from `PROGRAM_GRAPH.json` + `GRAPH_STATE.json` node status (86 PASSED")
w("of 104 nodes), and - for the exploration lane, which no graph node names - from")
w("`experiments/idea_log.jsonl` lead verdicts. Live leads: **I0004, I0009, I0011, I0014**.")
w("Dead leads: **I0008, I0010, I0012, I0013**.")
w("")
w("| # | consumers | liveness | granularity | conf | group | artifact |")
w("|---|---|---|---|---|---|---|")
for x in A[:20]:
    live = x["consumer_liveness"].split(":")[0]
    w("| %d | %d | %s | %s | %s | %d | `%s` |" % (x["priority_rank"], x["consumer_count"], live,
      x["proposed_asof_granularity"], x["confidence"], x["group"], x["artifact"].replace("\\", "/")))
w("")
w("Note on the top of the table: the four 11-consumer `frame.parquet` files are only **three**")
w("distinct artifacts. `E1_I0004_rim_finishing/_validate_sandbox/frame.parquet` is byte-identical")
w("(sha256 `311BFDA2...`) to `E1_I0011_split_alpha/frame.parquet`; the same holds for the two")
w("`grid_metrics.parquet` copies (`D6580165...`). 68 paths, 66 distinct contents.")
w("")

GROUPS = P["groups"]
for g in ["1", "2", "3", "4"]:
    gi = int(g)
    sub = [x for x in A if x["group"] == gi]
    w("## Group %s. %s" % (g, GROUPS[g]))
    w("")
    w("%d artifacts." % len(sub))
    w("")
    if gi == 1:
        w("These are artifact-granular **and** embed 2025/2026 inputs **and** are consumed by")
        w("something in the live player-program lineage. They are the ones where a manifest alone is")
        w("not the whole answer.")
        w("")
        w("All six share one root cause, which is the useful part: `build_projected_exposure.py`")
        w("globs **every** season of `experiments/cbs_v15_player_oof_v5/attempt_001/` -")
        w("`predictions__p_active__*.parquet` and `predictions__e_minutes_given_active__*.parquet`,")
        w("2021 through 2026 - and those files' own manifests already say")
        w("`\"asof_granularity\": \"artifact\"`. Everything downstream inherits it.")
        w("")
        w("**The mitigating fact, which must not be lost when this is fixed:** each per-season")
        w("prediction file was fit only on *strictly prior* seasons. The 2024 file's manifest reads")
        w("`fit_seasons: [2021, 2022, 2023]`. So a 2021 row did **not** see 2026 - the chain is")
        w("walk-forward, not pooled. The binary `row`/`artifact` vocabulary simply cannot express")
        w("\"bounded by the start of its own season\", which is what these actually are. That is a")
        w("convention decision for a human (see group 3), and it determines whether these need a")
        w("re-run at all or just an honest manifest plus a note.")
        w("")
    if gi == 2:
        w("Nothing here needs to be rebuilt. Each needs a sibling `<artifact>.manifest.json` stating")
        w("the granularity below. Note that **a good number of these are `ARTIFACT`** - that is the")
        w("correct, honest declaration, not a failure. An `ARTIFACT` label with")
        w("`holdout_risk: PARTITION_ONLY_LOOKAHEAD` tells a future screen exactly what it needs to know.")
        w("")
    if gi == 3:
        w("Do not guess these. Two different kinds of unknown are mixed here and they need different")
        w("things from a human:")
        w("")
        w("**(a) A vocabulary decision, affecting several artifacts at once.** GRAPH_POLICY defines")
        w("`row` as *bounded by the row's own date*. Several artifacts are bounded by the row's own")
        w("**season** instead - `team_season_coverage_v1.csv` (one row per team-season), and the")
        w("whole walk-forward prediction chain (bounded by the start of its own season). For all of")
        w("them, filtering by season **is** sufficient, so the policy's actual purpose is met - but")
        w("`row` would be literally false and `artifact` is needlessly disqualifying. One ruling on")
        w("whether a season-bounded row counts as `row`, or whether a third value is needed, settles")
        w("a large fraction of this backlog at once. **This is the highest-leverage decision in the")
        w("document.**")
        w("")
        w("**(b) Genuinely not traced.** 13 legacy game-and-betting-program outputs whose producers")
        w("were located but whose build code was not read. No granularity is proposed for them")
        w("because none was established. The prior leans ARTIFACT - the H1 hazard already lists two")
        w("siblings of this family as contaminated - but a prior is not evidence, and this program")
        w("has already paid once for confident guesses.")
        w("")
    if gi == 4:
        w("Housekeeping only. No player-program graph node and no live exploration lead reads these.")
        w("")
    w("| artifact | cons | granularity | conf | holdout risk | remedy | cost |")
    w("|---|---|---|---|---|---|---|")
    for x in sorted(sub, key=lambda y: -y["consumer_count"]):
        w("| `%s` | %d | %s | %s | %s | %s | %s |" % (x["artifact"].replace("\\", "/"),
          x["consumer_count"], x["proposed_asof_granularity"], x["confidence"],
          x["holdout_risk"], x["remedy"], x["estimated_cost"]))
    w("")

w("## Evidence, per artifact")
w("")
w("Every classification below is backed by a line that was read. A classification without a quoted")
w("line is not evidence, so entries with no quote are reported as UNDETERMINED.")
w("")
for x in A:
    w("### %d. `%s`" % (x["priority_rank"], x["artifact"].replace("\\", "/")))
    w("")
    w("- **Proposed `asof_granularity`: %s** (confidence %s, holdout risk %s)" %
      (x["proposed_asof_granularity"], x["confidence"], x["holdout_risk"]))
    w("- Consumers: %d. %s" % (x["consumer_count"], x["consumer_liveness"]))
    w("- Remedy: **%s**, estimated cost %s. Group %d." % (x["remedy"], x["estimated_cost"], x["group"]))
    w("")
    w("%s" % x["note"])
    w("")
    ev = [e for e in x["evidence"] if e.get("quote") and e["file"] != "(not reached)"]
    if ev:
        w("Evidence:")
        w("")
        for e in ev:
            loc = "%s:%d" % (e["file"], e["line"]) if e["line"] else e["file"]
            w("- `%s`" % loc)
            w("  ```")
            w("  %s" % e["quote"])
            w("  ```")
        w("")

w("## What this sweep did NOT cover")
w("")
w("Stated plainly so this does not read as complete when it is not:")
w("")
w("- **13 legacy game-and-betting artifacts were not code-traced** (group 3b). Producers are")
w("  recorded in `producer_candidates.json`; the build code was not read.")
w("- The **24 screen-local intermediates** and **21 unresolved references** in the audit's other")
w("  buckets were out of scope and were not classified.")
w("- `experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/translation_rows.parquet` was")
w("  classified but deliberately **not pursued**: a concurrent agent (`MEASURE_F1_m13_fitpool`) is")
w("  measuring that exact fit pool, and D075 records the M13 finding as HALT-AND-RAISED and")
w("  USER_REQUIRED because it touches PASSED nodes.")
w("- Three directories were excluded from every scan as required:")
w("  `E1_I0004_fga_forecast`, `MEASURE_F1_m13_fitpool`, `_screen_kit`.")
w("- Of the seven directories the audit flagged as having zero manifests, six were reached")
w("  (`turnover_p1_v1`, `turnover_p2_v1`, `turnover_targets_v1`, `projected_exposure_v1`,")
w("  `fits_v1`, plus the possession stores). **`possession_features_v1` and `validation_v1` have")
w("  no artifact in the 68-item list**, so nothing in them was classified.")
w("")
w("## Partition compliance")
w("")
w("One numerical probe was run (`s11_bios_probe.py`, on `player_bios.csv`). It filters to")
w("`season in [2021,2022,2023,2024]` on column values immediately after load and before any")
w("comparison. No 2025/2026 data was loaded into any analysis. Source code referencing later")
w("seasons was read, which the brief permits.")

open(os.path.join(OUT, "REMEDIATION_PLAN.md"), "w", encoding="utf-8").write("\n".join(L))
print("wrote REMEDIATION_PLAN.md  (%d lines)" % len(L))
