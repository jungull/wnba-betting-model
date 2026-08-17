# What the shipped roster path actually does

**E1_I0048_shipped_roster_path.** Read out of the code, re-executed, and checked against the
shipped bytes. Nothing inferred from behaviour; nothing enacted; no production file modified.

---

## 0. The headline, before the detail

E1_I0045 reported that `daily_forecast.py:647-665` builds its own roster from a 3-game box-score
window keyed on `player_name`, with no departure check, on the critical scheduled path. **That was
true of the file it read.** It is no longer true of the file that runs.

**The defect was repaired in production on 2026-08-06, in commit `55d84f1e`, the day after
E1_I0045 was written.** The live `daily_forecast.py` no longer contains those lines. It delegates
the whole roster construction to `entity_resolution.player_layer_resolved`, which keys on
`player_id`, enforces single tenancy as of the cutoff (a departure check), binds designations by
identity, and fails closed.

E1_I0045 read `.claude/worktrees/player-model-program/daily_forecast.py`. That worktree file is
byte-identical in the relevant block to commit `735b63bc` (2026-08-01), which **was** production
at the time. The screen was right about the code in front of it, and its line numbers were
accurate. The worktree simply did not move when production did.

**Consequence for anyone reading E1_I0045's D-2 today: the live-path concern it raised is closed.
The forty shipped records emitted before the repair are quantified below, and the answer is that
they contain no phantom pairing, no duplicate, and no drop.**

---

## 1. The two code paths, named and dated

| | pre-repair | post-repair |
|---|---|---|
| roster key | `player_name` | `player_id` |
| lookback | last 3 team games, DNP rows included | last 3 team games, DNP rows included |
| departure check | **none** | **single tenancy (F2)** |
| minutes history | team-filtered frame | `player_id` across the whole season (F1) |
| designation binding | `_norm_name` string match per (franchise-name, spelling) | identity index + curated alias table (F3) |
| unbindable `Out` | `WARN`, player silently stays available | `BLOCK` + explicit cold-start object (F4) |
| commits | `f7f9a189`, `6fc79daf`, `b3026fc5`, `735b63bc` | `55d84f1e`, `9cfe22e6`, `5943846f` |
| shipped records | `record_idx` **0–39** | `record_idx` **40–63** |
| repair landed | — | **2026-08-06 15:47:04 −0400 (19:47 Z)** |

`entity_resolution.py` was created 2026-08-06 11:48 local and wired in four hours later. Its
provenance is `experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION` (design
`fix_entity_resolution.py`), adopted as D022.

---

## 2. The pre-repair path, in plain language

Before each game the job needs a list of players who might play for a team. There is no roster
feed in this repository — a dedicated audit found none that can be reconstructed as of a
historical cutoff — so the list is assembled from box scores.

The job read the box-score master, kept only rows from the current season dated strictly before
today, and for each team took **the last three games that team played**. Everyone who appears in
any of those three box scores — including players who dressed but did not play, who have a row
with no minutes — went onto the roster. Then a single filter was applied: if the latest official
injury report captured at or before the cutoff said `Out`, the player was moved to an "out" list.
Everything else — `Probable`, `Questionable`, `Available`, no designation at all — stayed on the
roster.

That list, and a per-player exponentially-weighted average of recent minutes, were written into
the shipped forecast record.

**The three things that construction never asked:**

1. **Has she left?** Nothing looked at whether the player had since played for another club. A
   player traded yesterday still appeared in her old club's last three box scores, so she stayed
   on that club's shipped roster for three more games.
2. **Is this name one person?** The roster was the set of distinct `player_name` **strings**. Two
   spellings of one player produce two roster entries; one spelling shared by two players produces
   one entry, silently merging their minutes histories.
3. **Is this the same person the injury feed means?** Designations were matched by stripping
   accents and punctuation and lowercasing — so `Azurá Stevens` binds to `Azura Stevens`, but
   `Eliska Hamzova` does not bind to `Eliska Joklova`, and nothing checked.

The code was not hiding any of this: it emits a `WARN` when an injury-report name matches nobody
on the roster, saying in as many words that "if the status is Out and the player is rostered under
another spelling, the gate did NOT fire". The gate's failure mode was documented at the point of
failure. What was missing was the identity key that would have prevented it.

---

## 3. The exact lines, as they stood in `735b63bc`

Roster construction (`daily_forecast.py:662-665`):

```python
        tgames = sorted(tp.game_id.unique(),
                        key=lambda gid: tp[tp.game_id == gid].game_date.iloc[0])
        recent = set(tgames[-RECENCY_GAMES:])
        roster = tp[tp.game_id.isin(recent)].player_name.unique()
```

`RECENCY_GAMES = 3` (`:120`). Per-player history and the promoted minutes component
(`:674-680`) — note the history is also selected **by name**, and team-filtered:

```python
            hist = (tp[(tp.player_name == name) & (tp.minutes.notna())
                       & (tp.minutes > 0)].sort_values(["game_date", "game_id"]))
            ...
                   "min_ewma": float(hist.minutes.ewm(alpha=MINUTES_ALPHA,
                                                      adjust=True).mean().iloc[-1])
```

The gate (`:685-693`), and the emission (`:1130-1140`):

```python
            hit = inj_by_norm.get(_norm_name(name))
            ...
            if rec["designation"] == "Out":
                outs.append(rec)       # Phase-3 rule gate: excluded
```

```python
                "player_layer_informational": {
                    "note": "v0: does NOT modify the team forecast",
                    "home": {k: pl_home.get(k) for k in
                             ("n_roster", "n_out", "vacated_min_ewma",
                              "sum_min_ewma_available", "n_cold_start")},
                    ...
                    "out_home": [o["player"] for o in pl_home.get("out", [])],
```

**The roster name list itself is never written.** Only the five aggregates and the names of
players designated `Out` reach the log. That is why quantifying the defect required re-executing
the rule rather than reading the artifact — see §5.

---

## 4. What a player who changed clubs actually experienced

Traced on the shipped window, not reasoned about:

* **Aneesah Morrow**, `player_id` 1642800. Played 20 games for Connecticut through 2026-07-30.
  First appears in Toronto's box score 2026-08-02 as a DNP row, debuts for Toronto 2026-08-04.
  On Toronto's 2026-08-04 shipped roster she is present and correct. On **Connecticut's** roster
  she would have persisted for three more Connecticut games under the pre-repair rule — but
  Connecticut has no pre-repair shipped record, so no such row was ever emitted (§5).
* **Chloe Bibby**, 1631064. Chicago through 2026-07-30, Minnesota DNP rows 08-02 and 08-06, no
  Minnesota appearance yet. Emitted on Minnesota's 2026-08-06 roster — correct, she is a
  Minnesota player.
* **Haley Jones**, 1641650. Five appearances for Portland in May, then six consecutive Dallas DNP
  rows from 2026-06-28 to 2026-08-05 with zero Dallas appearances. Emitted on Dallas's roster —
  correct.

The pattern that matters: **a mid-season move shows up in the acquiring club's box score
immediately (as a DNP row), so the acquiring side is right. The failure mode is on the losing
side, and it requires the losing club to play a shipped slate within three games of the move.**
In the pre-repair shipped window that never happened.

---

## 5. What a name collision or variant would have done

The roster is `unique()` over strings, so:

* **One player, two spellings** → two roster entries, each with its own minutes EWMA computed
  over a *partial* history (the games under that spelling only). The team's roster count is
  inflated by one and `sum_min_ewma_available` double-counts part of one player's minutes.
* **Two players, one spelling** → one roster entry, and `hist` selects **both** players' rows, so
  the EWMA is computed over an interleaved minutes series belonging to two people.

Both are live hazards in the master: 13 distinct `player_id` values carry more than one
`player_name` across the six seasons (accents, hyphenation, maiden/married names, and one
name-order transliteration). Zero names map to more than one `player_id` — so the *drop*
failure mode is available in principle but has no instance in this repository. Detail and counts
are in `NAME_KEY.md`.

---

## 6. Fidelity — why the numbers in `SHIPPED_DAMAGE.csv` are the shipped rosters

The claim "this is what the shipped code emitted" is only worth as much as its check. Both eras
were re-executed and required to reproduce the shipped aggregates exactly — `n_roster`, `n_out`,
the `out_home`/`out_away` name sets, and `sum_min_ewma_available` / `vacated_min_ewma` to 1e-9.

| era | team-slots | reproduced | by which code |
|---|---:|---:|---|
| pre-repair (`record_idx` 0–39) | 76 | **76 / 76** | my re-implementation of the naive name-keyed rule |
| post-repair (`record_idx` 40–63) | 44 | **41 / 44** | the production `entity_resolution.player_layer_resolved`, imported read-only |

**76/76 on the defective era is the load-bearing number.** It means the rosters analysed in
`SHIPPED_DAMAGE.csv` are not a reconstruction that resembles the shipped roster — they are the
shipped roster, to the last decimal place of a floating-point EWMA sum.

The 3 post-repair failures are one player on one team (Phoenix, `Kara Dunn`, records 45/48/51):
shipped `n_out` 1, re-executed 0. Her only master row is dated 2026-08-07, the slate date itself,
so it is excluded by the `game_date < slate_date` filter; at run time she entered via a
designation transfer whose supporting feed row has since changed. This is input drift, not a code
difference — but it is reported rather than explained away, and those three slots back no number.

**The reproduction split is also the evidence for the era boundary.** The naive rule reproduces
records 0–39 exactly and fails on records ≥40; the repaired module reproduces records ≥40. Neither
was told where the boundary was — it was read from `git show` on the `source_version` recorded in
each shipped record.
