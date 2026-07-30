"""evalharness — the governing evaluation spec of the WNBA prediction engine.

ROADMAP: "This project is three separate systems ... A model may never 'win'
through timestamp ambiguity, metric choice, or repeated experimentation."
This package is that sentence, in code (ROADMAP §Phase 0.5, §Standard
promotion gate; HANDOFF §3 constitution):

    splits       time-ordered outer/inner/calibration splitters; locked holdout
    registry     append-only preregistration ledger (experiments/registry.jsonl)
    compare      paired game-level comparison, clustered bootstrap, 5-part gate
    metrics      MAE/RMSE/pinball/CRPS/Brier/log-loss/reliability/coverage
    baselines    frozen reference rows (11.22 / 10.53 / 9.54 / 5.42 / 5.12 + market)
    leaderboards FORECASTING / PROBABILISTIC / MARKET / BETTING renderers

Canonical experiment lifecycle:
    register -> split -> fit (tune inside outer-train only) -> compare -> leaderboard
"""

from .registry import (
    GateThresholds,
    register,
    begin_evaluation,
    record_evaluation,
    evaluate,
    read_records,
    list_evaluations,
    get_registration,
    RegistryError,
    UnregisteredExperimentError,
    LateRegistrationError,
    DuplicateRegistrationError,
    DEFAULT_REGISTRY,
)
from .splits import (
    OuterSplit,
    InnerSplit,
    CalibrationSplit,
    walk_forward_by_season,
    walk_forward_by_date_blocks,
    inner_tuning_splits,
    calibration_carveout,
    declare_holdout,
    claim_holdout,
    expose_holdout,
    strip_holdout,
    holdout_mask,
    LeakageError,
    HoldoutError,
    HoldoutNotClaimedError,
    HoldoutAlreadyClaimedError,
)
from .compare import (
    compare_to_incumbent,
    cluster_bootstrap_ci,
    ComparisonResult,
    ComparisonError,
)
from . import metrics
from .baselines import (
    load_frozen_baselines,
    frozen_baseline_value,
    FrozenBaselineTamperedError,
)
from .leaderboards import render_leaderboards

__version__ = "0.1.0"
from .forecast_log import log_forecast, verify_chain, prospective_start, hash_model_config, hash_dataframe  # regime-D prospective forecast log (forecasts/forecast_log.jsonl)
