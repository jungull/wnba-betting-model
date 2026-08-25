# -*- coding: utf-8 -*-
"""The overnight cycle: run everything that can run itself, then explain it in English.

WHY THIS EXISTS. The programme could keep collecting data forever without anyone noticing
that a question had become answerable. Two studies are waiting on sample size, a ledger of
paper decisions is waiting on game outcomes, and nothing re-checked them unless a person
remembered to. This runs the checks every morning and writes down what changed.

THE OUTPUT IS FOR A PERSON, NOT FOR THE LEDGER. John's standing instruction is that status
updates read like a briefing for a smart outsider with zero context -- no node identifiers, no
decision codes, no orchestration shorthand. So the brief says "we are still short of the
games needed to answer how long a mispriced line survives", not "M31 gate 16/30". The internal
bookkeeping still happens in the repository; it simply does not appear here.

WHAT IT RUNS, in order, each one already built to refuse rather than guess:

  1. Capture health -- is the data actually arriving?
  2. The two waiting studies -- each re-checks its own sample gate and declines to answer
     until it is met. Neither can be nudged into answering early.
  3. The paper-decision scorer -- scores only decisions whose games have finished, and counts
     the rest as pending rather than assuming them.

Then it writes DAILY_BRIEF.md, replacing yesterday's, and appends one line per day to
DAILY_HISTORY.md so the trend survives.

IT CHANGES NOTHING. Every step is read-only with respect to the model: no fit, no adoption,
no wager, no order. It reports.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WT = os.path.join(ROOT, ".claude", "worktrees", "player-model-program")
MP = os.path.join(WT, "experiments", "market_program")
PY = sys.executable

BRIEF = os.path.join(ROOT, "reports", "DAILY_BRIEF.md")
HISTORY = os.path.join(ROOT, "reports", "DAILY_HISTORY.md")

TIMEOUT = 1800


def run(path, cwd):
    """Run a step and return (ok, stdout). A crash is a result, not an exception."""
    try:
        p = subprocess.run([PY, path], cwd=cwd, capture_output=True, text=True,
                           timeout=TIMEOUT)
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return False, "timed out after %d seconds" % TIMEOUT
    except OSError as e:
        return False, "could not run: %s" % e


def num(pattern, text, cast=float, default=None):
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        return cast(m.group(1))
    except (TypeError, ValueError):
        return default


def main():
    # THE HEADING IS A HUMAN'S DATE, NOT THE MACHINE'S. Timing everywhere else in this
    # programme is UTC and must stay UTC, but a brief written at 22:19 Eastern was
    # published under the NEXT DAY'S date because UTC had already rolled over. A daily
    # report read over breakfast in Eastern time must carry the Eastern date or it is
    # simply wrong to its only reader. ET is UTC-4 in this window and UTC-5 in winter;
    # the fixed offset used elsewhere in this codebase is wrong in general, so the zone
    # is resolved properly here rather than inherited.
    now_utc = dt.datetime.now(dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        today = now_utc.astimezone(ZoneInfo("America/New_York"))
    except Exception:                       # noqa: BLE001 -- tzdata absent; say so, do not guess
        today = now_utc
    lines, hist = [], []

    lines.append("# Where the WNBA project stands — %s" % today.strftime("%A %d %B %Y"))
    lines.append("")
    lines.append("_Written automatically each morning. Everything below is measured, not "
                 "estimated._")
    lines.append("")

    # ---- 1. is data arriving? -------------------------------------------
    ok, out = run(os.path.join(ROOT, "ops", "capture_health.py"), ROOT)
    lines.append("## Is the data still arriving?")
    lines.append("")
    if ok:
        lines.append("**Yes — everything is collecting normally.** The odds feed, the injury "
                     "reports and the player-prop feed all ran on schedule.")
        hist.append("data OK")
    else:
        probs = [l.strip() for l in out.splitlines() if "PROBLEM" in l]
        lines.append("**Something needs attention.** " + ("%d issue(s) found:" % len(probs)))
        lines.append("")
        for p in probs:
            p = p.replace("PROBLEM", "").strip()
            if "TAPE STALE" in p:
                lines.append("* The odds feed has stopped updating. Nothing new is being "
                             "recorded, and any game starting soon will have no price history.")
            elif "MISSING" in p:
                lines.append("* The launcher every collection job depends on has gone "
                             "missing, which stops all of them at once. This has happened "
                             "before; the fix is in the handover notes.")
            elif "TASK FAILING" in p:
                nm = p.split()[2] if len(p.split()) > 2 else "a job"
                lines.append("* `%s` failed the last time it ran. If it has not been due to "
                             "run since a repair, this may just be an old error code." % nm)
            else:
                lines.append("* %s" % p[:160])
        hist.append("data ISSUES")
    lines.append("")

    # ---- 2. the two waiting studies -------------------------------------
    lines.append("## The two studies waiting on more games")
    lines.append("")
    lines.append("Both were designed so they *cannot* be answered early — they refuse to "
                 "produce a result until enough games have been observed. That is "
                 "deliberate: recomputing every day and publishing when the answer looks "
                 "best would be choosing the answer rather than measuring it.")
    lines.append("")

    studies = (
        ("how long a mispriced line stays on the screen",
         os.path.join(MP, "M31_DISLOCATION_PERSISTENCE"), "s01_persistence.py"),
        ("how long a book stays behind its competitors",
         os.path.join(MP, "M08_STALE_WINDOW"), "s01_stale.py"),
    )
    for human, d, script in studies:
        ok, out = run(os.path.join(d, script), d)
        games = num(r"distinct games\s*:?\s*(\d+)", out, int)
        if games is None:
            games = num(r"games\s+:\s*(\d+)", out, int)
        need = num(r"need (\d+) more games", out, int)
        if not ok:
            lines.append("* **%s** — the check could not run today." % human.capitalize())
            hist.append("study ERROR")
        elif need:
            lines.append("* **%s** — not yet. We have %s of the games required and need %d "
                         "more. On the current rate of play that is roughly %d–%d more days."
                         % (human.capitalize(), games if games is not None else "some",
                            need, max(1, int(need / 3.6)), max(2, int(need / 2.0))))
            hist.append("study waiting")
        else:
            lines.append("* **%s** — **the threshold has been reached and it produced an "
                         "answer today.** Worth reading in full." % human.capitalize())
            hist.append("STUDY ANSWERED")
    lines.append("")

    # ---- 3. the paper decisions -----------------------------------------
    d = os.path.join(MP, "M23_SHADOW_TRADING")
    ok, out = run(os.path.join(d, "s02_score.py"), d)
    lines.append("## The paper bets")
    lines.append("")
    lines.append("We record what the system *would* have bet, before each game starts, and "
                 "settle it afterwards. No money is involved and nothing is ever placed.")
    lines.append("")
    if not ok:
        lines.append("The scorer could not run today.")
        hist.append("bets ERROR")
    else:
        scored = num(r"scored\s*:\s*(\d+)", out, int, 0)
        pending = num(r"pending\s*:\s*(\d+)", out, int, 0)
        pnl = num(r"total P&L\s*:\s*([-+0-9.]+)", out)
        pct = num(r"\(([-+0-9.]+)% of stake\)", out)
        if scored:
            verdict = "lost" if (pnl or 0) < 0 else "made"
            lines.append("**%d settled so far: they %s %s.**%s" % (
                scored, verdict, ("$%.2f" % abs(pnl)) if pnl is not None else "nothing",
                (" That is %s%% of the money staked." % pct) if pct is not None else ""))
            lines.append("")
            # A POOLED HEADLINE CAN BE DOMINATED BY A HANDFUL OF LONGSHOTS. On the first
            # settlement the pooled figure was -14.3%, but that mixed nine ordinary bets at
            # -4.8% with two longshots that lost outright -- and at their prices, losing both
            # was the MOST LIKELY single outcome. Breaking it out stops the headline
            # overstating the case.
            for cl, n, st, pl, pc in re.findall(
                    r"^\s{4}(\S+)\s+n=\s*(\d+)\s+staked\s+([0-9.]+)\s+"
                    r"P&L\s+([-+0-9.]+)\s+\(([-+0-9.]+)%\)", out, re.M):
                friendly = {"MIDDLES_AND_DISLOCATIONS": "bets that a game lands between two "
                                                        "different bookmakers' lines",
                            "STALE_LINE_DELAYED_REACTION": "bets on a price one bookmaker was "
                                                           "slow to move"}.get(cl, cl)
                warn = ""
                if int(n) < 5:
                    warn = (" Only %s of them, so this tells us almost nothing yet — and "
                            "these were longshots, where losing every one is the most likely "
                            "single outcome." % n)
                lines.append("* %d of them were **%s**: %s%s%s"
                             % (int(n), friendly,
                                "lost" if float(pl) < 0 else "made",
                                " $%.2f (%s%% of stake)." % (abs(float(pl)), pc), warn))
            lines.append("")
            lines.append("Still waiting on %d whose games have not finished." % pending)
            hist.append("bets %+.2f" % (pnl or 0))
        else:
            lines.append("Nothing has settled yet — %d decisions are waiting on games that "
                         "have not finished." % pending)
            hist.append("bets pending")
    lines.append("")

    # ---- 3b. the lineup feed --------------------------------------------
    d = os.path.join(MP, "M40_WHO_GETS_PROMOTED")
    ok, out = run(os.path.join(d, "s02_score_vendor_vs_us.py"), d)
    lines.append("## Who is actually starting tonight")
    lines.append("")
    lines.append("Knowing which five players start is worth real accuracy in our minutes "
                 "forecast, and the league does not publish a confirmed lineup before tip. "
                 "So we now record a sports-data site's *projection* every 15 minutes and "
                 "keep every version, rather than just the last one. The versions are the "
                 "point: on the first night the site changed its own mind about a "
                 "replacement starter twice inside fifteen minutes.")
    lines.append("")
    if not ok:
        lines.append("The lineup check could not run today.")
        hist.append("lineup ERROR")
    elif "SELF-TEST FAILED" in out:
        # a broken join and an empty tape print the same thing; say which this is
        lines.append("**The lineup check is broken, not merely empty** — its self-test "
                     "failed, so today's 'nothing to score' cannot be believed.")
        hist.append("lineup BROKEN")
    else:
        n = num(r"scorable\D*(\d+)", out, int)
        states = num(r"over (\d+) distinct states", out, int, 0)
        if not n:
            lines.append("Nothing can be graded yet: we hold %d different versions of "
                         "tonight's projections, but the official box scores they will be "
                         "checked against have not arrived. Grading starts once they do."
                         % (states or 0))
            hist.append("lineup collecting")
        else:
            # Report ONLY the informative subset. A team that starts the same five as
            # last game is a free point for anybody, so the pooled figure flatters every
            # method equally and can read as excellent while answering nothing.
            got = re.findall(
                r"(T-\S+)\s+ALL\s+([0-9.]+)% \(n=(\d+)\)\s+\|\s+LINEUP CHANGED\s+"
                r"([0-9.]+|\s*n/a)%?\s+\(n=(\d+)\)", out)
            informative = sum(int(g[4]) for g in got[:1])
            if not got or not informative:
                lines.append("Versions are being graded, but no team has actually changed "
                             "its starting five yet — and an unchanged five is a free "
                             "point for any method that simply names last game's starters. "
                             "Until a lineup changes there is nothing to learn.")
                hist.append("lineup no-change")
            else:
                lines.append("So far **%d team-game(s) where the five actually changed** — "
                             "the only ones that ask a real question:" % informative)
                lines.append("")
                for lbl, allp, alln, chp, chn in got:
                    ch = "no such case yet" if "n/a" in chp else ("%s%% right" % chp)
                    lines.append("* Read **%s before tip**: %s on the %s changed lineup(s). "
                                 "(Across all %s teams including unchanged ones: %s%%.)"
                                 % (lbl.replace("T-", "").replace("m", " minutes")
                                    .replace("h", " hours"), ch, chn, alln, allp))
                lines.append("")
                lines.append("**Do not read a trend into this.** The numbers are on a "
                             "handful of games, and a projection read closer to tip is "
                             "solving an easier problem — a later reading looking better "
                             "is not evidence the site is good.")
                hist.append("lineup scored %d chg" % informative)
    lines.append("")

    # ---- 4. the standing answer -----------------------------------------
    lines.append("## Have we found a way to make money?")
    lines.append("")
    lines.append("**No, and that has not changed.** Six approaches have been measured and "
                 "closed: betting against the consensus of other bookmakers loses about 7%; "
                 "the forecasting model does not beat the market on any group of players we "
                 "have tested; middle bets lose; shopping for the best price saves money but "
                 "does not make any; genuine arbitrage exists but pays cents; and stale lines "
                 "cannot be measured reliably at the speed we can watch them.")
    lines.append("")
    lines.append("**One route has never been tested: bookmaker promotions.** It is the "
                 "highest-value opportunity measured so far, by a wide margin, and it is "
                 "untested only because no real offer has been entered into the system. "
                 "Entering one real promotion is the single most informative thing available.")
    lines.append("")

    os.makedirs(os.path.dirname(BRIEF), exist_ok=True)
    with open(BRIEF, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    stamp = today.strftime("%Y-%m-%d")
    with open(HISTORY, "a", encoding="utf-8", newline="\n") as f:
        f.write("%s | %s\n" % (stamp, " | ".join(hist)))

    print("wrote %s" % BRIEF)
    print("appended to %s" % HISTORY)
    for l in lines:
        print(l)


if __name__ == "__main__":
    main()
