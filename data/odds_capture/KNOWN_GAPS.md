# Known gaps in the live odds tape

Any analysis that reads `capture_log.csv` or `live_*.json` as a point-in-time series must
account for these. A gap is not a quiet market — it is an absence of observation, and the two
are indistinguishable downstream unless they are written down.

Machine-checkable: re-derive with a `diff()` over `snapshot_utc` and flag anything above the
cadence tier's tolerance. This file is the human record of *why* each one exists.

| start (UTC) | end (UTC) | duration | cause |
|---|---|---|---|
| 2026-08-24T21:10:02Z | 2026-08-25T01:40:02Z | **4h 30m** | Battery gate (D202) |

## 2026-08-24 — the 4.5-hour evening outage

**What happened.** 14 of 19 scheduled tasks carried `DisallowStartIfOnBatteries=true`, the
default from `New-ScheduledTaskSettingsSet` rather than a deliberate choice. The laptop went to
battery around 16:42 ET and every capture stopped — odds, injury-live, market ladder, props,
news. Nothing reported it, because `WNBA_CaptureHealth` had itself expired the previous day
(bounded `Duration=PT13H` + `StopAtDurationEnd`), leaving it `Ready` with no next run time.

**Why this gap is worse than its length suggests.** 21:10–01:40 UTC is 17:10–21:40 ET, which
covers:

- **GSV @ MIN, tip 20:10 ET** — the entire pre-tip approach *and* the whole in-play period.
- **ATL @ LAS, tip 22:00 ET** — the full pre-tip approach.

So for both of 2026-08-24's games the tape holds **no closing approach**. Treat any
closing-line, line-movement, or steam analysis touching 2026-08-24 as unsupported rather than
as showing a flat market. Note that M00-U4 already forbids the final-state archive as a feature
or benchmark, so the loss here is specifically of the *point-in-time* series.

**Fixed.** All 19 tasks ungated (originals backed up in `logs/task_xml_backup_20260824/`), the
watchdog and opportunity board re-registered with unbounded repetition, and `capture_health.py`
now flags any task with **no next run time** — the signature this failure presents, since such
a task reports `Ready`, `rc=0`, and looks perfectly healthy. That check runs *before* the
watchdog's self-exclusion, so it can catch its own silence.

**The residual risk this does not remove.** The machine still has to be awake. A sleeping or
powered-off laptop produces exactly this signature, and no in-process watchdog can report from
a machine that is not running. The next-run check catches expired triggers; it cannot catch a
closed lid.
