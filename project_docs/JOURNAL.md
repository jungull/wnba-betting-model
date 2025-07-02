# Project Journal

A running log of progress, experiments, decisions, and reflections for the WNBA Prediction Engine project.

---

## [2024-07-01] Advanced Normalization, Player Value, PDA, and Modeling Bake-Off

**Progress:**
- Implemented advanced opponent strength normalization using multi-metric, weighted 10-game lookback
- Developed comprehensive player value and PhD-level PDA (Point Differential Added) metrics
- Built and ran bake-off modeling framework for stat prediction, including model ranking script
- Organized all documentation into a new `docs/` directory for clarity

**Experiments/Findings:**
- Found that multi-metric normalization improves context for player stats
- PDA metric provides an intuitive, all-in-one measure of player impact
- Model bake-off reveals strengths/weaknesses of different algorithms for each stat

**Decisions:**
- Use advanced normalization and PDA as core features for future modeling
- Maintain modular documentation in `docs/` for easier navigation

**Next Steps:**
- Expand bake-off to more stats and advanced features
- Integrate betting analysis and edge calculation
- Continue refining player value and normalization formulas

**Notes:**
- Documentation and journal now organized for easier project tracking

---

## [YYYY-MM-DD] Title or Summary

**Progress:**
- 

**Experiments/Findings:**
- 

**Decisions:**
- 

**Next Steps:**
- 

**Notes:**
- 

---

## [2024-05-30] Example Entry

**Progress:**
- Created setup scripts for full environment and data pipeline reproduction on Windows
- Added comprehensive project plan and future optimizations documentation

**Experiments/Findings:**
- Validated that possession-based features are generated with opponent normalization
- Noted edge cases in on-court tracking (possessions with <5 players)

**Decisions:**
- Proceed with per-100 possession stats for now; revisit on-court validation later

**Next Steps:**
- Begin model development phase
- Add journal and documentation system for ongoing tracking

**Notes:**
- Token limits can be a challenge for large project summaries; keep documentation modular

---

# Instructions
- Add a new section for each entry, using the template above
- Use this file for daily/weekly logs, experiment results, and key project decisions
- Keep entries concise but informative 