#!/usr/bin/env python3
"""
Read-only bridge to the program's single entity-resolution implementation.

Per the established program discipline (D033 mandate: "status-transition
detection ... via our entity resolution"; the same discipline already
applied to injury_capture_daily.py in production), this track does not fork
or reimplement identity resolution. It imports the live main worktree's
entity_resolution.py by path, read-only, exactly the same interface
production capture already uses: try_load_capture_index() and
resolve_player_id(name, index).

This is the ONE place in this track that reaches outside its own ownership
boundary (experiments/market_program/INJURY_OFFICIAL/live/) to read code --
never to write, never to import anything that could mutate state on the
live main worktree. If the import fails for any reason (path moved, module
error), resolution degrades to "no index" with every player_id left blank
and an explicit note -- a capture must never die because resolution is
unavailable (same discipline entity_resolution.py itself documents for
try_load_capture_index).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Read-only: the live main worktree, never written to by this track.
_LIVE_MAIN_WORKTREE = Path(r"C:\Users\jgallagher\wnba-betting-model")


def _import_live_entity_resolution():
    if str(_LIVE_MAIN_WORKTREE) not in sys.path:
        sys.path.insert(0, str(_LIVE_MAIN_WORKTREE))
    import entity_resolution  # noqa: the live main worktree module
    return entity_resolution


def try_load_index():
    """-> (index_dict, status_note). index_dict is {} on any failure."""
    try:
        er = _import_live_entity_resolution()
    except Exception as e:  # pragma: no cover - exercised only if path moves
        return {}, f"entity_resolution import failed: {type(e).__name__}: {e}"
    idx = er.try_load_capture_index()
    if not idx:
        return {}, "entity_resolution loaded but returned an empty index"
    return idx, f"entity_resolution index loaded, {len(idx)} identities"


def resolve(name, index):
    """None-safe, index-safe resolve. Returns int player_id or None."""
    if not index or name is None:
        return None
    try:
        er = _import_live_entity_resolution()
    except Exception:
        return None
    return er.resolve_player_id(name, index)
