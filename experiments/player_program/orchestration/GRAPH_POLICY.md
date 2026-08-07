# Graph policy — autonomous program graph for the WNBA player model

Version: `GRAPH_POLICY_V1`. Governs the orchestration layer only. It does **not** amend
`RESEARCH_CONTRACT_V1`, `GATE_INVOCATION_CONTRACT.md`, or any frozen scientific artifact — where
this policy and a scientific contract appear to disagree, the **scientific contract governs** and
the disagreement is recorded in `DECISION_LEDGER.jsonl` rather than silently reconciled.

---

## 1. Source-of-truth hierarchy

Applied in this order. A lower tier never overrides a higher one.

1. frozen artifact bytes and rederived hashes
2. committed receipts and manifests
3. `RESEARCH_CONTRACT_V1.md`
4. `PROGRAM_STATE.json`
5. accepted task cards and decision records
6. accepted scientific rulings recorded in Stage 1B and Stage 2A artifacts
7. project updates and prose handoffs
8. task-specific rulings recorded in `DECISION_LEDGER.jsonl`

**Where prose conflicts with frozen bytes, the bytes govern.** Never silently reconcile a
contradiction; append it to `DECISION_LEDGER.jsonl` with both readings preserved.

---

## 2. What the committed graph is

| file | role | mutability |
|---|---|---|
| `PROGRAM_GRAPH.json` | node definitions and dependency structure | append/amend, never delete a node id |
| `GRAPH_EVENTS.jsonl` | historical ledger of everything that happened | **append-only, never rewritten** |
| `GRAPH_STATE.json` | generated current snapshot | **derived, never hand-edited** |
| `DECISION_LEDGER.jsonl` | coordinator rulings and preserved contradictions | append-only |
| `ARTIFACT_LEDGER.jsonl` | path → sha256 → observed-at-event | append-only |
| `FILE_OWNERSHIP.json` | generated write-ownership map | derived |

`GRAPH_STATE.json` must be **deterministically reconstructable** from the graph definition, the
append-only events, repository state and artifact hashes. `graphctl.py state --check` rebuilds it
and fails on any divergence. Runtime scratch lives under `.claude/graph_runtime/` and is ignored;
nothing there is authority.

**Never rewrite history to make a failed attempt disappear.** A failed node keeps its FAILED
event; remediation is a *new* node that declares the failure as its parent finding.

---

## 3. Frozen paths — no graph node may write here

Enforced by `scripts/frozen_path_guard.py`, which is invoked by `integrate_node.py` before any
merge and fails closed.

* `experiments/player_program/possessions_v1/`, `possessions_v2/`, `projected_exposure_v1/`,
  `event_contract_v1/`, `turnover_targets_v1/`, `turnover_p1_v1/`, `turnover_p2_v1/`,
  `p3_downstream_v1/`, `fits_v1/`, `possession_features_v1/`, `validation_v1/`
* `experiments/player_program/arm_registry.jsonl`, `registry.jsonl` — **append-only**; existing
  records may never be edited. Appending requires a passed preregistration gate.
* `experiments/player_program/feature_gate.py`, `comparison_gate.py`, `gate_invocation.py`,
  `receipt_integrity.py` — shared contracts
* `experiments/player_program/discovery_wave_1/`
* `experiments/player_program/stage2a/EVIDENCE_PACKET.json`,
  `EVIDENCE_PACKET_V2.json`, `V2_HYPOTHESES_*.md`, `V2_GENERATION_ORDER.json`,
  `V2_STOP_CONDITION.json`, `GENERATION_ORDER.json`, `HYPOTHESES_*.md`, `SYNTHESIS.md`
* everything constituting **Arm D** (`D_ewma_shrunk`): source, configuration and outputs
* `PROGRAM_STATE.json` — derived; regenerate via `build_program_state.py`, never hand-edit

A task-specific wrapper is the correct way to add enforcement. **Do not modify a frozen shared
gate to add a check** — write the check at the call site.

---

## 4. Isolation

**Writable engineering nodes.** One worktree per node, branch `graph/<node_id>`, pinned base
commit, exclusive file ownership. Two live nodes may never own the same file. `dispatch_ready.py`
refuses to emit a dispatch set containing an ownership collision.

**Scientific ideation nodes.** Independence is *structural*, not promised. The node runs against
an isolated directory containing only the allowed frozen packet and its prompt. The repository is
not exposed. Other hypothesis files, syntheses and coordinator ideas are not exposed. Raw output is
frozen and hashed **before** any other source can read it.

**Audit nodes.** An audit node may not be the implementation node whose work it audits. Enforced
by `validate_graph.py`: an audit node listing implementation node `X` in `dependencies` must not
share `X`'s `agent_prompt_path` or `owned_files`.

**Retries and replacements.** A retry is labelled `RETRY` and is *not* a new independent source. A
replacement for a lost agent is labelled `REPLACEMENT`. Neither inflates evidence-source counts.

---

## 5. Automatic advancement

A node passes automatically only when **all** hold:

1. every declared output exists;
2. every input hash rederives to its frozen value;
3. every `validation_command` exits 0;
4. every `acceptance_criterion` is machine-verifiable and satisfied;
5. no Severity A issue remains open against it;
6. no forbidden path changed;
7. an **independent verifier context** agrees.

The coordinator may decide without asking the user when the governing contract resolves it, when
it is a deterministic consequence of an accepted ruling, when it narrows scope to avoid leakage or
unverified data, when it removes a redundant or unidentified candidate, when it rejects an arm for
failing predeclared integrity checks, or when it advances an experiment whose frozen
preregistration and implementation audits pass. Consequential coordinator gates use **at least two
independent reviewers**, and **disagreement is preserved**, never averaged away.

Severity B failures automatically spawn a remediation node, at most two cycles unless a new
mechanism is involved. Severity C is documented and scheduled without halting unrelated work.

---

## 6. `USER_REQUIRED` — the only stopping points

Stop, and ask exactly one concrete question with the evidence needed to answer it, when a decision
would:

* change the primary estimand or target;
* weaken a scientific gate after any relevant outcome was observed;
* modify a frozen canonical artifact;
* modify Arm D or replace the champion;
* accept known leakage or an unresolved Severity A risk;
* alter an existing registry record;
* make an external deployment, push or financial commitment;
* choose between scientifically equivalent alternatives on a business preference not documented in
  the repository.

Everything else proceeds. In particular the coordinator does **not** ask permission to create
worktrees, make task-scoped commits, run tests, perform read-only audits, remediate a confirmed
implementation defect, advance a fully satisfied gate, retry a failed agent, launch an unblocked
node, update graph metadata, freeze a preregistration whose reviews all passed, or execute an
already-frozen preregistered experiment.

---

## 7. Blinding

Candidate-performance results stay **sealed** until V3 is frozen, hypotheses are frozen, families
are deduplicated, multiplicity treatment is frozen, task cards are frozen, formulas are frozen,
feature lineages are frozen, `K0_MATCHED[arm]` is frozen for every arm, implementation code is
frozen, and all integrity audits pass.

Implementation nodes may run unit, synthetic, identity and schema tests, and dry runs that do not
reveal comparative historical performance. They may **not** inspect challenger performance. The
runner writes into a sealed result directory; a separate result-integrity node verifies commit,
data hashes, row universe, folds, `K0` pairing, seeds and output completeness; only then may a
separate adjudication node open results.

---

## 8. Git policy

**Allowed without asking:** local worktrees, local branches, task-scoped commits, merging a
validated task branch into `player-model-program`, appending graph and evidence records, appending
new registry records after the preregistration gate passes.

**Prohibited:** force push, force reset, history rewrite, deleting another actor's work, editing an
existing registry record, modifying frozen canonical bytes, modifying Arm D, pushing to a remote,
deploying, changing production credentials, spending money, modifying shared contracts or frozen
gates.

Integration requires: clean dependency base, changed-file scope check, test pass, artifact-hash
reconciliation, no unexpected file ownership, no forbidden-path change, and an explicit merge
event.

---

## 9. Model tiering — match the agent to the task

Dispatch cost is real. Every agent launch declares a model tier and a reasoning effort, chosen
by what the node *is*, not by what capacity happens to be free:

| tier | use for |
|---|---|
| **highest available** (inherit session model, high effort) | target and contract interpretation; K0 design; preregistration authoring and red-team review; adversarial verification on the possession critical path; final adjudication; graph mutation after a scientific blocker |
| **mid** (`sonnet`, medium effort) | documentation extraction with refusal discipline; target-contract drafts; citation-checking verification off the critical path; data cleaning with fixed rules; UI scaffolding |
| **fast** (`haiku`, low effort) | file inventory; mechanical reformatting; report assembly from existing structured data with no judgement calls |

Two rules that override the table:

1. **Verification of a Severity A node never runs below the tier of the work it verifies.**
   A cheap verifier signing off on expensive analysis is how a plausible-but-wrong finding
   survives.
2. **Do not launch redundant agents merely because capacity exists.** An additional agent must
   supply a distinct expertise lens, an independent audit, genuinely parallel implementation, or
   fault isolation.

## 10. Remote policy

The program branch `player-model-program` is pushed to `origin` after each integration cycle
(user authorization 2026-08-04, superseding this policy's original no-push rule — see decision
`D017`). Constraints that remain in force: never force-push, never push `main` or any branch not
owned by this graph, never rewrite published history. A push is a backup of committed work, not a
deployment.

**Pushes require a quiescent tree** (`D018`). The repository's pre-push hook runs `verify_all`
(~10 min, 35 checks), and `test_run_player_oof_v14` check 10 asserts the dirty-path count is
stable across its own runtime — a deliberate refusal to certify a tree that changed while being
measured. A push attempted while agents are writing fails that check *by design*. Therefore: a
push happens only after the running wave has completed, its outputs are committed, and no agent
holds a write scope in the worktree. Never bypass the hook (`--no-verify` is prohibited); if the
gate fails, the tree was not quiescent or something real broke — investigate, never override.

## 11. Severity and blocking

A blocker in one lane blocks **descendants in that lane**, not independent work elsewhere. Severity
A stops affected descendants. Severity B creates a remediation node. Severity C is scheduled.

Do not report "waiting" while unrelated nodes remain READY.

## 12. Continuous operation and succession (`D050`, user directive 2026-08-07)

The graph exists to keep the program moving without supervision. Three rules make that binding.

**12.1 Always be executing.** A coordinator never idles and never asks the user whether to
continue. When a node halts — for a failing gate, an exhausted agent, a blocked dependency, a
`USER_REQUIRED` decision — that lane parks and the coordinator **immediately moves to the next
READY node in any other lane** (`graphctl.py ready` is the worklist; §11 governs). Parking one
lane is not parking the program. Reporting "waiting" or "shall I continue?" while any node is
READY is a policy violation, not a courtesy. The only legitimate stopping states are: every node
is PASSED, SUPERSEDED, or blocked behind a `USER_REQUIRED` gate; or the user says stop.

**12.2 What halting actually means.** A halted node keeps its HALTED event and its honest reason,
is retry-eligible (a retry is labeled `RETRY` and is never a new independent source, §4), and
**blocks only its own descendants**. The coordinator records the halt, records what the next
coordinator must do to clear it, and goes to work elsewhere in the same turn. A gate that
requires an independent context is still never self-granted (§5, §6) — the correct response to
"the independent reviewer died" is *another independent reviewer later*, plus other lanes now.

**12.3 Retire by training a successor, never by stopping.** When a coordinator's context is
filling, it does not wind down the program; it **produces a successor packet and hands off mid-
stride**. The packet is written to `orchestration/reports/COORDINATOR_HANDOFF_<date>.md` and must
contain, at minimum: the live state (`graphctl.py ready` + `status` output at hand-off), every
in-flight or halted node with exactly what clears it, the current worklist **in execution order**,
the standing user directives and every `USER_REQUIRED` item the successor may never self-grant,
the disciplines learned this session (what broke, what the fix was), and an explicit statement of
§12.1 so the successor inherits the anti-stall rule. The outgoing coordinator commits the packet,
leaves the tree quiescent and pushed, and the incoming coordinator's **first action** is to read
it plus this policy. Succession is a normal operation of the graph, not an emergency.

**12.3.1 The succession trigger is CONTEXT, not the clock** (`D056`, user directive 2026-08-07).
The recurring scheduled run is only a **safety net**. The intended trigger for succession is the
coordinator's own context consumption, and because no harness mechanism fires on context
percentage, **the coordinator is the trigger**: it self-assesses continuously and acts on the
threshold itself.

At roughly **60% of context — erring EARLY, never late** — the coordinator begins retirement. A
coordinator that runs out mid-handoff hands over nothing, which is the failure this threshold
exists to prevent. The sequence is: (1) stop dispatching new nodes — winding down IS the remaining
work, and §12.1's rule against idling is suspended for this purpose only; (2) close in-flight
agents properly if they are nearly done, otherwise record each in the packet with its node id,
write scope, exactly what clears it, and an explicit **DO NOT RE-DISPATCH — check for its return
event first**; (3) write the §12.3 packet, carrying this subsection verbatim so the successor
inherits the trigger; (4) commit, then push **only once `git status` shows no agent still holds a
write scope**, because the pre-push gate correctly refuses a tree that changes while it is
measured; (5) append a **`coordinator_retired`** event naming the packet and any in-flight nodes,
as the LAST ledger write; (6) trigger the successor immediately with a **one-time** scheduled task
firing a few minutes out, rather than leaving the program dark until the next recurring run; (7)
stop — two live coordinators writing one branch is precisely the collision the staleness guard
exists to prevent.

**The staleness-guard override this requires.** An incoming coordinator stands down if the last
ledger event is under 30 minutes old, on the assumption that another instance is live. Under
self-triggered succession that assumption inverts: the freshest event is the predecessor's own
handoff write, minutes old by design. **Therefore: if the most recent event is `coordinator_retired`,
the successor does NOT stand down — it was deliberately summoned and proceeds immediately.**
Without this override the chain deadlocks and the program stalls until the safety-net run. This
failure was observed live on 2026-08-07, when a scheduled coordinator stood down against a
9-minute-old ledger while its predecessor was in fact retiring.

**12.4 Dispatch under resource failure.** An agent that dies on capacity/credit exhaustion is an
infrastructure event, not a scientific finding: nothing it produced partially may be used or
claimed. Retry it later at the same tier (never a cheaper tier for a Severity-A verification,
§9.1), and in the meantime execute work that does not depend on it.


---

## 13. Evidence levels E0-E3: rigor is sequenced, not uniform (`D057`, user directive 2026-08-07)

**The problem this fixes.** The graph applied approximately one burden of proof to two different
questions: *"is there anything interesting here?"* and *"should money depend on this?"* Measured on
this session's own ledger, **0.4% of agent time went to idea generation and 99.6% to validating
what little was generated** (4 minutes vs 948). That is not rigor; it is misallocation. Rigor
belongs **at the point where you start believing the result**, not at the point where you first
look.

| Level | Purpose | Standard | May it be cited? |
|---|---|---|---|
| **E0 Exploration** | find anything unusual | fast, permissive, time-boxed (~30-60 min), explicitly non-claiming | **NO** |
| **E1 Signal candidate** | does the effect persist? | basic season split / holdout **inside the exploration partition** | **NO** |
| **E2 Challenger** | does it improve forecasting? | preregistration + full clean walk-forward vs champion | yes |
| **E3 Production** | should money depend on it? | prospective + calibration + market + betting gates | yes, USER gate |

**13.1 E0/E1 are explicitly non-claiming.** No registry entry, no preregistration, no leaderboard
row, no REPORT.md, no bootstrap, no promotion threshold. Output is a **one-line kill/keep log
entry**. An E0/E1 finding is a **LEAD, never a RESULT**, and may never be cited as evidence for
anything. Most leads die; that is the point. Expect ~40 of 50 to die immediately.

**13.2 THE ONE GUARD THAT MAKES THE SANDBOX SAFE — the exploration partition.**
This is the enabling condition for going fast, not a tax on it. **E0 and E1 run ONLY on a
designated exploration partition. The E2 confirmation holdout is NEVER read, joined, plotted or
described during E0/E1.**

Why it is non-negotiable: if exploration touches the holdout, then screening 50 ideas and promoting
the 2 that "look legitimately strange and persistent" means those 2 were **selected using the very
data meant to confirm them**. Preregistering afterwards preregisters a hypothesis the data already
chose. That is selection leakage at program scale, and it is the same family as the failures this
program has already paid for -- the arm-G leak worth 16x its reported gain, and the apparent
breakthroughs that evaporated. With the partition in place, screening 50 ideas costs **nothing**
statistically, because confirmation happens on data the search never saw. Without it, the faster
process manufactures false confidence faster.

**13.3 Disclose the screen count.** An E2 preregistration states how many E0 leads were screened in
the campaign that produced it. Not to penalise the search -- to let a reader calibrate. A lead that
survived 1-of-50 and one that survived 1-of-2 are different objects.

**13.4 Promotion is a real decision, and downgrade is free.** E1 to E2 requires a written
preregistration *before* the holdout is touched. Killing a lead at E0/E1 needs no ceremony, no
report and no adjudication -- one log line. Cheap death is what makes cheap birth safe.

**13.5 Stop centring global MAE.** "Beat the market on every game" is an extraordinarily hard bar
and probably the wrong target. The operative question becomes: **where is our information advantage
strongest, what observable pre-game state predicts that advantage, and can we abstain everywhere
else?** A model mediocre in 80% of games and genuinely superior in 20% is valuable, and pooled
averaging is precisely what hides it. §12's D051 residual-characterisation directive is the
existing bridge to this; conditional-edge work and abstention are first-class targets, not
afterthoughts.

**13.6 Effort allocation, until further notice: ~70% signal discovery / ~20% validation of
survivors / ~10% infrastructure.** The constitution is good enough. **Do not spend further effort
making it more pure unless an actual flaw appears** -- and note the irony that this section is
itself constitutional work: it is authorised as the change that *ends* that phase, not as licence
to continue it. Priority target: the **player-level residual**, i.e. granular player x matchup x
availability interactions, which is the program's original thesis and the thing the infrastructure
was built to test.


**13.7 E2 uses ALL pseudo-futures, with fold provenance labelled honestly** (`D063`, user directive
2026-08-07). The WNBA record is small and there is not enough 2026 season left to wait for a large
prospective sample. So E2 does not consume one fresh test set — it runs the full walk-forward ladder:

| fold | trains through | predicts | provenance |
|---|---|---|---|
| F1 | 2021 | 2022 | **DEVELOPMENT_CONTAMINATED** |
| F2 | 2022 | 2023 | **DEVELOPMENT_CONTAMINATED** |
| F3 | 2023 | 2024 | **DEVELOPMENT_CONTAMINATED** |
| F4 | 2024 | **2025** | **CLEAN_CONFIRMATION** |
| F5 | 2025 | **2026** | **CLEAN_CONFIRMATION** |

Folds F1-F3 predict seasons E0/E1 were allowed to explore, so **they are not independent
confirmation and may never be reported as such** — they are *robustness evidence*, which is real and
must not be discarded merely because discovery touched those seasons. **F4 and F5 are the strongest
historical confirmation available** because exploration never saw 2025 or 2026. Every E2 report
states F4/F5 **separately and pooled**, and labels the pooled figure as mixed-provenance.

**13.8 The holdout degrades with use, and the accounting is mandatory.** Do NOT retune against
2025-2026 and present each rerun as fresh confirmation. Every E2 record carries two fields:

* `holdout_touch_count` — how many times this idea's lineage has evaluated against 2025/26;
* `adaptive_generation` — **0** for the first look, incremented whenever an E2 result *causes a
  redesign* that is then re-tested.

Any record with `adaptive_generation > 0` is **ADAPTIVE, not fresh confirmation**, and says so in its
headline. This is not bureaucracy: a confirmation holdout cannot be restored once informed, so the
counter is the only honest way to report how much of it has been spent. Two ideas showing the same
F4/F5 result at generation 0 and generation 3 are not equally believable.

**13.9 E2 evidence can carry a model to deployment; E3 modulates confidence, it does not gate first
use.** A model may be deployed on sufficiently strong E2 historical evidence rather than waiting for
hundreds of prospective games. The bar is all five of:

1. signal discovered on development data;
2. mechanics survive proper point-in-time historical walk-forward;
3. it **holds up independently on 2025 and 2026**;
4. it materially improves the relevant forecast / market / decision benchmark;
5. leakage, calibration, stability and coverage checks pass.

**E3 is live verification** — CLV, ROI, calibration and drift measured prospectively, which raises or
lowers the confidence and capital given to a model that has *already earned deployment at E2*. E3
must not be used to forbid the use of a model that clears the bar above.

**What this does NOT change:** the *authority* to deploy. GRAPH_POLICY §6 reserves external
deployment and financial commitment to the user, and D063 changes the **evidence standard**, not who
rules. E2 can now make the case; the user still makes the call.

**13.8.1 `adaptive_generation` follows the HYPOTHESIS FAMILY, not the experiment id** (`D064`, user
directive 2026-08-07). The counter attaches to the **campaign/lineage**, not to a name. If a 2025/26
result teaches something and a closely related variant is spun out of that information, **renaming it
does not reset it to fresh confirmation** — the variant inherits the family's `adaptive_generation`
and increments it. Every E2 record therefore carries a `hypothesis_family_id`, and the counter is
keyed on that. Spawning a "new" experiment id from a holdout-informed insight is the obvious way to
launder an adaptive test into a fresh one, and it is closed here explicitly.

**13.9.1 Deployment authority — CONFIRMED BY THE USER 2026-08-07.** E2 can establish that a model is
**deployment-READY**. **Deployment itself and any financial commitment remain the user's decision**
(§6). The coordinator's D063 interpretation is ratified: E2 makes the case, the user makes the call.

**13.2.1 The manifest check — how §13.2 is actually enforced** (`H1`, 2026-08-07). Before using ANY
pre-built artifact at E0/E1, read its sibling `<artifact>.manifest.json` and inspect `fit_seasons`
and `fit_through_season`. **If either includes 2025 or 2026, the artifact is holdout-contaminated and
may not be used** — rebuild from raw per-season files instead. A sweep on 2026-08-07 found **19 of 29
manifested artifacts contaminated**, including all five `data/zone_maps/*` files (whose own manifests
state *"a 2021 row's shrunk value saw later seasons"*) and `data/w1_truth/player_game_availability.csv`
— exactly what an absence or minutes screen reaches for first. There is no error, warning or visible
symptom when a contaminated artifact is used; the check is the only defence.

**13.2.2 CORRECTION to 13.2.1 — the check keys on `asof_granularity`, not on which seasons appear.**
13.2.1 as first written was wrong in both its sweep (run in the data worktree, 29 manifests, instead
of the program worktree, 162) and its criterion. The correct rule:

* **`asof_granularity: "row"`** — each row is bounded by its own date. **Filtering to 2021-2024 is
  SUFFICIENT**; the artifact is usable. `master_player.parquet` and `master_team.parquet` are of this
  kind.
* **`asof_granularity: "artifact"`** — the whole file is bounded by its latest input, so a 2021 row's
  value may have been computed from 2026 data. **Filtering does NOT help; unusable at E0/E1.** The
  `zone_maps` manifests state it outright: *"a 2021 row's shrunk value saw later seasons."*

Corrected sweep of the program worktree: **65 artifact-granular files spanning the holdout are
unusable**; **13 row-granular files are safe if filtered**; 84 others are clean. `fit_seasons` alone
means only which seasons a file *contains* — it is not evidence of contamination.

**This correction has a cost on the record:** the over-broad rule reached a running screen mid-flight
and caused it to disqualify a valid result. Over-broad safety rules are not free — they destroy true
findings as efficiently as loose ones admit false ones.

**12.3.2 AMENDMENT — retire on SYMPTOMS, not on a guessed percentage** (`D068`, user directive
2026-08-07). The "~60%, err EARLY" wording in 12.3.1 caused repeated premature handoffs:
Coordinators #03 and #04 each retired inside an hour, on a guess, with context nowhere near full.

**Premature retirement is the more common failure and it is expensive.** Every handoff costs a full
packet write PLUS a full re-read by the successor (packet + policy + ledger + state). A coordinator
retiring after 45 minutes can spend a third of its budget on ceremony. That is overhead, not caution.

**You are NOT near the threshold** if you can still dispatch an agent, verify a result on bytes, and
write a full annotation. In that state, keep working. Do not wind down "to be safe".

**Retire only on an observable symptom:** you are summarising agent returns instead of reading them;
you are skipping verification you would normally do; the harness has actually warned you about
context, or auto-compaction has occurred; one more agent return would leave no room to process it;
or the user says to hand off.

**Floor:** do not retire before completing and closing a substantial unit of work. Retiring mid-unit
forces the successor to reconstruct context you already had — the most wasteful possible handoff.

**Numbering:** successor tasks are `wnba-coordinator-NN`, zero-padded increment, never date-stamped
(dates collide when two coordinators retire the same day). The briefing must tell the successor its
number, tell it to identify itself by that number in every ledger event and its closing note, and
tell it to name ITS successor with the next increment. Without the third, the numbering dies at the
first handoff.

**Operational limit worth knowing:** a scheduled task is registered on the **machine that created
it**. A successor summoned from a different device or a cloud session may exist on disk but never
appear in the user's local scheduler, and therefore never fire there. State the task id you created
in your closing note and ask the user to confirm it appears in their Scheduled list.
