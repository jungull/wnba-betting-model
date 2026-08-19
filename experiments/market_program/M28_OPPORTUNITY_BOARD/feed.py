"""feed.py -- resolve the odds capture root and normalise snapshots into quotes.

THE DATA ROOT PROBLEM THIS SOLVES (D138). The research worktree does not carry gitignored
directories, so `data/odds_capture` is invisible from inside it even though the main
checkout has been capturing continuously. Every screen this programme ran was blind to it.
This module resolves the root explicitly and FAILS LOUDLY when it cannot find one, so an
environmental absence can never again be recorded as a repository fact.

Resolution order, first hit wins:
  1. `$WNBA_DATA_ROOT`                      -- explicit override, always respected
  2. `<repo>/data`                          -- normal checkout
  3. `<repo>/../../../../data`              -- climbing out of .claude/worktrees/<name>/
  4. hard-coded main checkout               -- last resort, reported as such

The chosen root and how it was chosen are recorded on the returned object, because "which
data was this built from" is the question that decides whether a result means anything.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent          # .../player-model-program
MAIN_CHECKOUT_DATA = Path(r"C:\Users\jgallagher\wnba-betting-model\data")


@dataclass(frozen=True)
class DataRoot:
    path: Path
    how: str

    @property
    def odds_capture(self) -> Path:
        return self.path / "odds_capture"


def resolve_data_root(explicit: str | os.PathLike | None = None) -> DataRoot:
    candidates: list[tuple[Path, str]] = []
    if explicit:
        candidates.append((Path(explicit), "explicit argument"))
    env = os.environ.get("WNBA_DATA_ROOT")
    if env:
        candidates.append((Path(env), "$WNBA_DATA_ROOT"))
    candidates.append((REPO / "data", "repo-relative <repo>/data"))
    candidates.append((REPO.parent.parent.parent / "data", "worktree parent climb"))
    candidates.append((MAIN_CHECKOUT_DATA, "hard-coded main checkout (D138 fallback)"))

    tried = []
    for path, how in candidates:
        tried.append(f"{how}: {path}")
        if (path / "odds_capture").is_dir():
            return DataRoot(path=path.resolve(), how=how)

    raise FileNotFoundError(
        "No odds capture directory found. This is an ENVIRONMENTAL absence, not evidence "
        "that no data exists (D138). Tried, in order:\n  " + "\n  ".join(tried)
        + "\nSet WNBA_DATA_ROOT to the checkout that owns data/odds_capture."
    )


# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Quote:
    game_id: str
    commence_time: str
    home_team: str
    away_team: str
    book: str
    book_title: str
    market: str            # h2h | spreads | totals
    outcome: str
    price: float           # American
    point: float | None
    last_update: str       # ISO8601 from the book
    snapshot_utc: str      # when WE captured it

    @property
    def matchup(self) -> str:
        return f"{self.away_team} @ {self.home_team}"


@dataclass(frozen=True)
class Snapshot:
    path: Path
    snapshot_utc: str
    captured_at: datetime
    quotes: tuple[Quote, ...]
    games: tuple[dict, ...]
    data_root: DataRoot

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.captured_at).total_seconds()

    @property
    def n_books(self) -> int:
        return len({q.book for q in self.quotes})

    @property
    def n_games(self) -> int:
        return len({q.game_id for q in self.quotes})


def _parse_snapshot_stamp(name: str) -> datetime:
    """live_20260818T210003Z.json -> aware datetime."""
    stem = name.replace("live_", "").replace(".json", "")
    return datetime.strptime(stem, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def list_snapshots(root: DataRoot | None = None) -> list[Path]:
    root = root or resolve_data_root()
    return sorted(root.odds_capture.glob("live_*.json"))


def load_snapshot(path: Path, root: DataRoot | None = None) -> Snapshot:
    root = root or resolve_data_root()
    raw = json.loads(path.read_text(encoding="utf-8"))
    stamp = path.name.replace("live_", "").replace(".json", "")
    quotes: list[Quote] = []
    for game in raw:
        for bk in game.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                for out in mkt.get("outcomes", []):
                    price = out.get("price")
                    if price is None:
                        continue
                    quotes.append(Quote(
                        game_id=game["id"],
                        commence_time=game["commence_time"],
                        home_team=game["home_team"],
                        away_team=game["away_team"],
                        book=bk["key"],
                        book_title=bk.get("title", bk["key"]),
                        market=mkt["key"],
                        outcome=out["name"],
                        price=float(price),
                        point=(float(out["point"]) if out.get("point") is not None else None),
                        last_update=mkt.get("last_update") or bk.get("last_update", ""),
                        snapshot_utc=stamp,
                    ))
    return Snapshot(
        path=path,
        snapshot_utc=stamp,
        captured_at=_parse_snapshot_stamp(path.name),
        quotes=tuple(quotes),
        games=tuple(raw),
        data_root=root,
    )


def load_latest(root: DataRoot | None = None) -> Snapshot:
    root = root or resolve_data_root()
    snaps = list_snapshots(root)
    if not snaps:
        raise FileNotFoundError(f"no live_*.json snapshots under {root.odds_capture}")
    return load_snapshot(snaps[-1], root)


def measure_cadence(root: DataRoot | None = None, sample: int = 24) -> dict:
    """Median gap between consecutive captures.

    This is the single most important number for interpreting anything this node finds.
    An arbitrage detected on an hourly grid is a statement about a price that existed at
    some point in the last hour -- not one you could have taken. M00 forbids an
    executability claim without the EXECUTION_FEASIBLE rung, and cadence is why.
    """
    snaps = list_snapshots(root)[-sample:]
    if len(snaps) < 2:
        return {"n": len(snaps), "median_gap_s": None, "note": "insufficient snapshots"}
    times = [_parse_snapshot_stamp(p.name) for p in snaps]
    gaps = sorted((times[i + 1] - times[i]).total_seconds() for i in range(len(times) - 1))
    mid = len(gaps) // 2
    median = gaps[mid] if len(gaps) % 2 else (gaps[mid - 1] + gaps[mid]) / 2
    return {
        "n": len(snaps),
        "median_gap_s": median,
        "min_gap_s": gaps[0],
        "max_gap_s": gaps[-1],
        "first": times[0].isoformat(),
        "last": times[-1].isoformat(),
    }
