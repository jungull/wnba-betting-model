"""
U10_PREDICTION_API_SCHEMA -- deterministic fixture generator.

Writes `fixtures/*.json`: the request/input fixtures and the golden responses
built from them.  Every byte here is SYNTHETIC.  Nothing is read from a fitted
model, an out-of-fold artifact, a registry arm or any sealed result, and the
artifact hashes are sha256 of fixture LABELS, not of any real artifact -- so a
golden response can never be mistaken for a real prediction.

Run:  python experiments/player_program/product_lane/U10_PREDICTION_API_SCHEMA/build_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from prediction_response_schema import (  # noqa: E402
    Component,
    GameRef,
    InputRecord,
    MarketComparison,
    ModelDescriptor,
    ProjectionSpec,
    build_response,
)

FIXTURES = HERE / "fixtures"
CODE_VERSION = "U10_schema_1.0.0"


def fake_sha(label: str) -> str:
    """A deterministic, obviously-synthetic 64-hex hash for a fixture label."""
    return hashlib.sha256(("FIXTURE::" + label).encode("utf-8")).hexdigest()


GAME = GameRef(
    game_id="FIXTURE_GAME_0001",
    game_cluster_id="FIXTURE_CLUSTER_0001",
    season=2026,
    home_team_id="FIXTURE_TEAM_H",
    away_team_id="FIXTURE_TEAM_A",
    scheduled_tip_utc="2026-08-05T23:00:00Z",
    forecast_cutoff_utc="2026-08-05T21:00:00Z",
)

REQUEST = {
    "game_id": "FIXTURE_GAME_0001",
    "as_of_utc": "2026-08-05T20:00:00Z",
    "subjects": ["team", "player"],
    "requested_targets": [
        "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
        "PLAYER_PROJECTED_OFFENSIVE_POSSESSION_EXPOSURE",
    ],
}

# Two DIFFERENT model descriptors over identical fixtures.  Neither names an
# arm from the registry; both are opaque to the schema.  Their existence is the
# demonstration that the response is model-agnostic: swap the descriptor, the
# document keeps its shape and its meaning.
MODEL_ALPHA = ModelDescriptor(
    model_version="fixture_model_alpha/0.0.1",
    model_family="fixture_family_synthetic",
    artifact_sha256={
        "exposure_artifact": fake_sha("alpha/exposure"),
        "rate_artifact": fake_sha("alpha/rate"),
    },
    promotion_status="no_challenger_promoted",
    control_pairing="fixture_control_declared_by_producer",
    registry_record=None,
    produced_by="fixtures/build_fixtures.py",
)

MODEL_BETA = ModelDescriptor(
    model_version="fixture_model_beta/0.0.1",
    model_family="fixture_family_synthetic_other",
    artifact_sha256={
        "exposure_artifact": fake_sha("beta/exposure"),
        "rate_artifact": fake_sha("beta/rate"),
        "adjustment_artifact": fake_sha("beta/adjustment"),
    },
    promotion_status="no_challenger_promoted",
    control_pairing=None,
    registry_record=None,
    produced_by="fixtures/build_fixtures.py",
)


def base_inputs() -> list[InputRecord]:
    return [
        InputRecord(
            input_id="team_history",
            source="fixtures/team_history.parquet",
            sha256=fake_sha("team_history"),
            as_of_utc="2026-08-05T19:00:00Z",
            observed_at_utc="2026-08-05T19:05:00Z",
            age_seconds=3600.0,
            max_age_seconds=86400.0,
            job_status="ok",
        ),
        InputRecord(
            input_id="lineup_report",
            source="fixtures/lineup_report.json",
            sha256=fake_sha("lineup_report"),
            as_of_utc="2026-08-05T20:30:00Z",
            observed_at_utc="2026-08-05T20:31:00Z",
            age_seconds=1800.0,
            max_age_seconds=7200.0,
            job_status="ok",
        ),
        InputRecord(
            input_id="market_capture",
            source="fixtures/market_capture.json",
            sha256=fake_sha("market_capture"),
            as_of_utc="2026-08-05T20:45:00Z",
            observed_at_utc="2026-08-05T20:46:00Z",
            age_seconds=900.0,
            max_age_seconds=3600.0,
            job_status="ok",
        ),
    ]


def base_projections() -> list[ProjectionSpec]:
    return [
        ProjectionSpec(
            projection_id="team_H_possessions",
            subject_type="team",
            subject_id="FIXTURE_TEAM_H",
            team_id="FIXTURE_TEAM_H",
            target="REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
            unit="possessions",
            point=81.4,
            uncertainty={"sd": 3.1, "p10": 77.5, "p50": 81.4, "p90": 85.3},
            components=[
                Component("league_prior", "prior", 79.9, "possessions"),
                Component("team_trailing_window", "trailing_window", 1.8, "possessions"),
                Component("opponent_adjustment", "adjustment", -0.3, "possessions"),
            ],
            depends_on=["team_history"],
            market=MarketComparison(
                available=True,
                book="FIXTURE_BOOK",
                line=80.5,
                over_price=-110,
                under_price=-110,
                captured_at_utc="2026-08-05T20:45:00Z",
            ),
        ),
        ProjectionSpec(
            projection_id="player_0001_exposure",
            subject_type="player",
            subject_id="FIXTURE_PLAYER_0001",
            team_id="FIXTURE_TEAM_H",
            target="PLAYER_PROJECTED_OFFENSIVE_POSSESSION_EXPOSURE",
            unit="possessions",
            point=52.7,
            uncertainty={"sd": 6.4, "p10": 44.6, "p50": 52.7, "p90": 60.8},
            components=[
                Component("team_exposure_offset", "offset", 81.4, "possessions"),
                Component("rotation_share_prior", "prior", -24.1, "possessions"),
                Component("availability_probability", "adjustment", -4.6, "possessions"),
            ],
            depends_on=["team_history", "lineup_report"],
            market=MarketComparison(
                available=False,
                unavailable_reason="no_player_possession_market_in_fixture_capture",
            ),
        ),
        ProjectionSpec(
            projection_id="player_0002_exposure",
            subject_type="player",
            subject_id="FIXTURE_PLAYER_0002",
            team_id="FIXTURE_TEAM_A",
            target="PLAYER_PROJECTED_OFFENSIVE_POSSESSION_EXPOSURE",
            unit="possessions",
            point=38.2,
            uncertainty={"sd": 7.9, "p10": 28.1, "p50": 38.2, "p90": 48.3},
            components=[
                Component("team_exposure_offset", "offset", 80.1, "possessions"),
                Component("rotation_share_prior", "prior", -41.9, "possessions"),
            ],
            depends_on=["team_history", "lineup_report"],
            market=MarketComparison(
                available=True,
                book="FIXTURE_BOOK",
                line=36.5,
                over_price=-115,
                under_price=-105,
                captured_at_utc="2026-08-05T20:45:00Z",
            ),
        ),
    ]


def _degrade(inputs: list[InputRecord], input_id: str, **changes) -> list[InputRecord]:
    out = []
    for r in inputs:
        if r.input_id == input_id:
            d = {
                "input_id": r.input_id,
                "source": r.source,
                "sha256": r.sha256,
                "as_of_utc": r.as_of_utc,
                "observed_at_utc": r.observed_at_utc,
                "age_seconds": r.age_seconds,
                "max_age_seconds": r.max_age_seconds,
                "job_status": r.job_status,
                "declared_freshness": r.declared_freshness,
            }
            d.update(changes)
            out.append(InputRecord(**d))
        else:
            out.append(r)
    return out


def scenarios() -> dict[str, dict]:
    out: dict[str, dict] = {}

    out["nominal"] = dict(
        response_id="FIXTURE_RESP_NOMINAL",
        generated_at_utc="2026-08-05T20:50:00Z",
        request=REQUEST,
        game=GAME,
        model=MODEL_ALPHA,
        inputs=base_inputs(),
        projections=base_projections(),
        code_version=CODE_VERSION,
        fixture_mode=True,
    )

    # Same fixtures, different model.  Only the model block changes.
    out["nominal_other_model"] = dict(out["nominal"])
    out["nominal_other_model"].update(
        response_id="FIXTURE_RESP_NOMINAL_OTHER_MODEL",
        model=MODEL_BETA,
        inputs=base_inputs(),
        projections=base_projections(),
    )

    # Stale history: everything that depends on it is withheld.
    out["stale_input"] = dict(
        response_id="FIXTURE_RESP_STALE",
        generated_at_utc="2026-08-05T20:50:00Z",
        request=REQUEST,
        game=GAME,
        model=MODEL_ALPHA,
        inputs=_degrade(base_inputs(), "team_history", age_seconds=259200.0),
        projections=base_projections(),
        code_version=CODE_VERSION,
        fixture_mode=True,
    )

    # Missing lineup: the team projection survives, the player projections do not.
    out["missing_lineup"] = dict(
        response_id="FIXTURE_RESP_MISSING_LINEUP",
        generated_at_utc="2026-08-05T20:50:00Z",
        request=REQUEST,
        game=GAME,
        model=MODEL_ALPHA,
        inputs=_degrade(
            base_inputs(),
            "lineup_report",
            sha256=None,
            as_of_utc=None,
            observed_at_utc=None,
            age_seconds=None,
            max_age_seconds=None,
        ),
        projections=base_projections(),
        code_version=CODE_VERSION,
        fixture_mode=True,
    )

    # Failed job: the input file may still be on disk and look fresh.  It is
    # still degraded, and its dependants are still withheld.
    out["failed_job"] = dict(
        response_id="FIXTURE_RESP_FAILED_JOB",
        generated_at_utc="2026-08-05T20:50:00Z",
        request=REQUEST,
        game=GAME,
        model=MODEL_ALPHA,
        inputs=_degrade(base_inputs(), "lineup_report", job_status="failed"),
        projections=base_projections(),
        code_version=CODE_VERSION,
        fixture_mode=True,
    )

    # No market capture at all.
    no_market = base_projections()
    for p in no_market:
        p.market = MarketComparison(
            available=False, unavailable_reason="market_capture_job_not_run"
        )
    out["no_market"] = dict(
        response_id="FIXTURE_RESP_NO_MARKET",
        generated_at_utc="2026-08-05T20:50:00Z",
        request=REQUEST,
        game=GAME,
        model=MODEL_ALPHA,
        inputs=_degrade(base_inputs(), "market_capture", job_status="not_run"),
        projections=no_market,
        code_version=CODE_VERSION,
        fixture_mode=True,
    )

    # A model that produced no number for one subject.  No substitution.
    partial = base_projections()
    partial[2].point = None
    partial[2].uncertainty = {"sd": None, "p10": None, "p50": None, "p90": None}
    out["no_value_produced"] = dict(
        response_id="FIXTURE_RESP_NO_VALUE",
        generated_at_utc="2026-08-05T20:50:00Z",
        request=REQUEST,
        game=GAME,
        model=MODEL_ALPHA,
        inputs=base_inputs(),
        projections=partial,
        code_version=CODE_VERSION,
        fixture_mode=True,
    )

    return out


def write_fixtures() -> list[pathlib.Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    written: list[pathlib.Path] = []

    # The raw request/input fixtures, written separately so a consumer can
    # rebuild the golden responses from inputs alone.
    req_path = FIXTURES / "request.json"
    req_path.write_text(json.dumps(REQUEST, indent=2) + "\n", encoding="utf-8")
    written.append(req_path)

    game_path = FIXTURES / "game.json"
    game_path.write_text(json.dumps(GAME.to_json(), indent=2) + "\n", encoding="utf-8")
    written.append(game_path)

    models_path = FIXTURES / "models.json"
    models_path.write_text(
        json.dumps(
            {"alpha": MODEL_ALPHA.to_json(), "beta": MODEL_BETA.to_json()}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(models_path)

    resp_dir = FIXTURES / "responses"
    resp_dir.mkdir(exist_ok=True)
    for name, kwargs in scenarios().items():
        doc = build_response(**kwargs)
        p = resp_dir / f"{name}.json"
        p.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        written.append(p)

    return written


def main() -> int:
    written = write_fixtures()
    for p in written:
        print(f"wrote {p.relative_to(HERE)}")
    print(f"{len(written)} fixture files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
