"""Leaderboard renderer — four boards, frozen floors, everything posts.

ROADMAP "Leaderboards (replaces the single MAE leaderboard)":

    leaderboards/FORECASTING.md   score/margin/total point error, by decision time
    leaderboards/PROBABILISTIC.md CRPS, log loss, Brier, calibration
    leaderboards/MARKET.md        close-prediction error, line-path models
    leaderboards/BETTING.md       simulated ROI, CLV, drawdown — decision policies
    Market rows appear as benchmarks in all four. Quarantined experiments post
    win or lose.

Rendering rules enforced here:
  * The frozen reference baselines (baselines.py — tamper-checked) appear on
    EVERY board render, so no result is ever displayed without the honest
    floors (11.22 / 10.53 / 9.54 / 5.42 / 5.12) and market benchmarks beside it.
  * Every evaluation run in the registry renders — win or lose, including
    quarantined experiments (flagged) and repeat runs (run_number shown), so
    repeated experimentation is visible, never hidden.
  * Boards are derived from the registration's ``board`` field, else inferred
    from ``primary_metric`` via METRIC_BOARD (default FORECASTING).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import registry as _reg
from .baselines import load_frozen_baselines

BOARDS = ("FORECASTING", "PROBABILISTIC", "MARKET", "BETTING")

BOARD_TITLES = {
    "FORECASTING": "Forecasting leaderboard — score/margin/total point error, by decision time",
    "PROBABILISTIC": "Probabilistic leaderboard — CRPS, log loss, Brier, calibration",
    "MARKET": "Market leaderboard — close-prediction error, line-path models",
    "BETTING": "Betting leaderboard — simulated ROI, CLV, drawdown (decision policies)",
}

# primary_metric -> board (lowercased substring match, first hit wins)
METRIC_BOARD = [
    ("crps", "PROBABILISTIC"), ("log_loss", "PROBABILISTIC"),
    ("logloss", "PROBABILISTIC"), ("brier", "PROBABILISTIC"),
    ("pinball", "PROBABILISTIC"), ("calibration", "PROBABILISTIC"),
    ("reliability", "PROBABILISTIC"),
    ("close", "MARKET"), ("line_path", "MARKET"), ("market", "MARKET"),
    ("roi", "BETTING"), ("clv", "BETTING"), ("drawdown", "BETTING"),
    ("bankroll", "BETTING"), ("kelly", "BETTING"),
]


def board_for(registration: dict) -> str:
    explicit = registration.get("board")
    if explicit:
        b = str(explicit).upper()
        if b not in BOARDS:
            raise ValueError(f"unknown board {explicit!r}; use one of {BOARDS}")
        return b
    metric = str(registration.get("primary_metric", "")).lower()
    for key, board in METRIC_BOARD:
        if key in metric:
            return board
    return "FORECASTING"


def _fmt(x, nd=4) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def _gate_cell(gates: dict) -> str:
    marks = []
    for i, name in enumerate([
        "gate1_pooled_improvement", "gate2_ci_excludes_harm",
        "gate3_per_season_non_inferiority", "gate4_joint_forecast",
        "gate5_coverage",
    ], start=1):
        v = gates.get(name)
        marks.append(f"{i}:" + ("P" if v is True else "F" if v is False else "·"))
    return " ".join(marks)


def _baseline_section(frozen) -> list[str]:
    lines = [
        "## Frozen reference baselines (pinned permanently — never re-run, never removed)",
        "",
        "| model | metric | value | sample | provenance |",
        "|---|---|---|---|---|",
    ]
    for _, r in frozen.iterrows():
        tag = " *(market benchmark)*" if r["kind"] == "market_benchmark" else ""
        lines.append(
            f"| {r['model']}{tag} | {r['metric']} | **{r['value']}** | "
            f"{r['sample']} | {r['provenance']} |"
        )
    lines.append("")
    return lines


def render_leaderboards(
    registry_path: "Path | str | None" = None,
    out_dir: "Path | str | None" = None,
) -> dict:
    """Render all four leaderboard files from the registry. Returns
    {board: path}. Idempotent — output is a pure function of the registry,
    the frozen baselines, and the render timestamp header."""
    records = _reg.read_records(registry_path)
    registrations = {
        r["experiment_id"]: r for r in records if r.get("kind") == "experiment"
    }
    evaluations = [r for r in records if r.get("kind") == "evaluation"]
    claims = [r for r in records if r.get("kind") == "holdout_claimed"]
    frozen = load_frozen_baselines()

    out = Path(out_dir) if out_dir is not None else _reg.REPO_ROOT / "leaderboards"
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reg_display = str(registry_path or _reg.DEFAULT_REGISTRY)
    paths = {}

    for board in BOARDS:
        rows = []
        for ev in evaluations:
            reg = registrations.get(ev.get("experiment_id"), {})
            if board_for(reg) != board:
                continue
            res = ev.get("results", {}) or {}
            rows.append((reg, ev, res))
        # rank: evaluated metric ascending (lower=better for every error metric
        # the project uses); rows without a metric value sink to the bottom.
        rows.sort(key=lambda t: (
            t[2].get("metric_challenger") is None,
            t[2].get("metric_challenger", float("inf")),
        ))

        lines = [
            f"# {BOARD_TITLES[board]}",
            "",
            f"*Rendered {now} from `{reg_display}` by evalharness.leaderboards "
            "(ROADMAP §Leaderboards). Every registered evaluation posts here — "
            "win or lose, every run. Unregistered results are void and cannot "
            "appear.*",
            "",
        ]
        lines += _baseline_section(frozen)
        lines += [
            f"## Registered experiment evaluations ({board})",
            "",
        ]
        if not rows:
            lines.append("*No registered evaluations on this board yet.*")
        else:
            lines += [
                "| rank | experiment (run) | regime | decision time | primary metric | "
                "challenger | incumbent | Δ pooled | 90% CI (date-cluster) | "
                "gates 1-5 | verdict | n | evaluated |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
            for rank, (reg, ev, res) in enumerate(rows, start=1):
                exp_id = ev.get("experiment_id")
                quarantine = " **[QUARANTINED]**" if reg.get("quarantined") else ""
                ci = (
                    f"[{_fmt(res.get('ci_low'))}, {_fmt(res.get('ci_high'))}]"
                    if res.get("ci_low") is not None else "—"
                )
                verdict = res.get("verdict", "—")
                verdict_cell = f"**{verdict}**" if verdict == "PASS" else verdict
                lines.append(
                    f"| {rank} | `{exp_id}`{quarantine} (run {ev.get('run_number')}) "
                    f"| {reg.get('regime') or '—'} "
                    f"| {reg.get('decision_time') or '—'} "
                    f"| {reg.get('primary_metric', '—')} "
                    f"| {_fmt(res.get('metric_challenger'))} "
                    f"| {_fmt(res.get('metric_incumbent'))} "
                    f"| {_fmt(res.get('pooled_improvement'))} "
                    f"| {ci} "
                    f"| {_gate_cell(res.get('gates', {}))} "
                    f"| {verdict_cell} "
                    f"| {res.get('n_games', '—')} "
                    f"| {str(ev.get('eval_time', '—'))[:10]} |"
                )
            lines += [
                "",
                "Gate legend (ROADMAP §Standard promotion gate): 1 pooled "
                "improvement ≥ registered minimum · 2 90% clustered-bootstrap CI "
                "excludes harm beyond bound · 3 per-season non-inferiority · "
                "4 joint forecast non-degradation · 5 coverage maintained. "
                "P=pass F=fail ·=not provided (visible, not hidden).",
            ]
        if claims:
            lines += ["", "## Locked-holdout claims (single use, irreversible)", ""]
            for c in claims:
                lines.append(
                    f"- holdout `{c.get('holdout_name')}` claimed by "
                    f"`{c.get('experiment_id')}` at {c.get('recorded_at')}"
                )
        lines.append("")
        path = out / f"{board}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        paths[board] = path
    return paths
