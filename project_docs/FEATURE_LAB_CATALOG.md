# FEATURE LAB CATALOG — 100 candidate features for the per-player engine

*Drafted 2026-07-31 on John's directive: stay in the lab; engineer and test features at
scale before layering news on top. Every candidate below is tagged with its data status:*

- **HAVE** — buildable today from committed data (masters, play-by-play, stints,
  possessions, 202,987 shot locations, officials, schedules, odds-derived tip times).
- **COLLECT-S** — needs a small one-time collection (player bios: height/weight/age/draft;
  a static city-coordinates table). In flight.
- **PROXY** — the direct quantity does not exist publicly for the WNBA (e.g. tracking
  speed); an honest proxy from our data is listed instead.
- **N/A** — not available and no honest proxy; listed so nobody wastes a week rediscovering.

*Testing discipline: every feature is screened under the preregistered protocol
`player_feature_screen_v1` — screening years 2021–2024 ONLY, the 2025 and 2026 seasons
quarantined untouched for confirmation; every trend inside a feature is shifted (no
same-game information); alphas swept per feature on inner walk-forward folds; significance
against a within-season permutation null with false-discovery control across the whole
catalog (with ~100 candidates, ~5 will look good by pure luck — the protocol prices that
in). Survivors graduate to a registered confirmation experiment on the quarantined years
with real promotion gates.*

## The epistemics template (the Caitlin Clark case study, computed 2026-07-31)

Home/away is **measurable** (Clark 2026: 24.0 pts at home vs 17.9 away; 2024: 20.9 vs
17.6). But measurable ≠ useful: across 438 qualifying player-seasons the average home
lift is only **+0.38 pts/36**, the player-to-player spread is ±2.5, and the year-over-year
correlation of a player's *personal* home lift is **r = +0.054 — essentially zero**. A
player's split this season tells you almost nothing about next season; the league-average
home effect (already in the model as the home-court intercept) plus heavy shrinkage is the
correct encoding, and an unshrunken "Clark is a home player" feature would be noise
chasing. **Every candidate below faces the same three questions: measurable? stable?
predictive beyond the trend baseline?** The screen answers all three mechanically.

---

## A. Venue, time, and travel context (11)

| # | Feature | Status | Sketch |
|---|---|---|---|
| 1 | Personal home-lift, shrunken | HAVE | per-36 scoring home−away EWMA, shrunk hard toward the +0.38 league mean (case study above — expected weak) |
| 2 | Personal home 3P% differential | HAVE | shooting-background sensitivity; shrunken |
| 3 | Personal home FT% differential | HAVE | routine/crowd sensitivity; FT% is the lowest-noise shooting stat |
| 4 | Home/away usage shift | HAVE | does the offense run through them more at home |
| 5 | Home/away minutes shift | HAVE | coach-trust asymmetry |
| 6 | Rest-bucket performance profile | HAVE | per-36 rate by days-rest {0,1,2,3+}, pooled then personalized |
| 7 | Back-to-back penalty × age | COLLECT-S | B2B rate drop interacted with age (bios) |
| 8 | Timezone-shift effect | HAVE | ET↔PT crossings from city sequence of the schedule |
| 9 | Travel distance since last game | COLLECT-S | haversine from static city coordinates; × age |
| 10 | Afternoon vs evening tip split | HAVE | tip hours from captured odds commence times (new era) + schedule |
| 11 | Road-trip game number / home-stand length | HAVE | position within the trip from city sequences |

## B. Opponent-profile conditionals — "how does X do against Y-type teams" (15)

| # | Feature | Status | Sketch |
|---|---|---|---|
| 12 | Rate vs opponent defensive-rating tercile | HAVE | performance vs top/mid/bottom defenses, shrunken |
| 13 | 3pt attempts vs opponent 3pt-allowed profile | HAVE | player-level version of the team chain factor |
| 14 | Paint rate vs opponent rim protection | HAVE | opp blocks-per-paint-attempt index × player paint reliance |
| 15 | FT rate vs opponent foul propensity | HAVE | opp fouls/min × player drive-heavy profile |
| 16 | Rate vs opponent pace tercile | HAVE | who benefits from fast games (uses possessions data) |
| 17 | **Rate vs opponent lineup height** | COLLECT-S | minutes-weighted average height of the opponent's recent rotation (bios); John's question — buildable once heights land |
| 18 | Height differential vs opponent at-position | COLLECT-S | player height − opponent same-position rotation height |
| 19 | Career head-to-head vs franchise | HAVE | tiny samples; extreme shrinkage; expected weak but cheap |
| 20 | Production vs specific defender on floor | HAVE | stint-overlap splits (X's rate with Y on/off floor), heavily shrunken |
| 21 | Opponent turnover-forcing × player TO-proneness | HAVE | usage-risk interaction |
| 22 | Opponent defensive-rebound strength × second-chance rate | HAVE | channel-specific matchup |
| 23 | Opponent bench depth × blowout-minutes exposure | HAVE | rotation-length interaction |
| 24 | Opponent 3pt-variance profile | HAVE | high-variance defenses (gamble/close-out style) vs shooters |
| 25 | Opponent transition defense (fastbreak pts allowed) × player transition share | HAVE | channel matchup |
| 26 | Zone-mix displacement vs opponent allowed-zone profile | HAVE | shot-location overlap: where their diet meets the defense's leak |

## C. Physical and biographical priors (9) — all pending the small bios pull

| # | Feature | Status | Sketch |
|---|---|---|---|
| 27 | Age curve (age, age², distance-from-peak) | COLLECT-S | per stat family; peaks differ (shooting late, athleticism early) |
| 28 | Height × paint-conversion stability | COLLECT-S | tall finishers' rates are steadier — test it |
| 29 | Experience years × role stability | COLLECT-S | vets' minutes/roles drift less |
| 30 | Draft-pedigree prior for cold starts | COLLECT-S | draft slot → expected production for debuts (fixes the cold-start tier honestly) |
| 31 | Weight class × back-to-back fatigue | COLLECT-S | speculative, cheap to test |
| 32 | Career minutes odometer | HAVE | cumulative WNBA minutes as a wear proxy |
| 33 | Age × travel-distance interaction | COLLECT-S | do vets suffer road trips more |
| 34 | Rookie month-by-month learning template | HAVE | pooled rookie progression curve applied to current rookies |
| 35 | Offseason overseas load | N/A | no reliable public source for overseas minutes; noted so nobody chases it |

## D. Form and trend refinements — the alpha playground (13)

| # | Feature | Status | Sketch |
|---|---|---|---|
| 36 | Fast-vs-slow EWMA gap per stat | HAVE | α=0.4 minus α=0.05: form-vs-identity divergence; the purest "sweep alphas" family |
| 37 | Rate volatility (rolling std) | HAVE | consistency as a signal in itself |
| 38 | Hot-hand 3P% deviation | HAVE | last-k makes vs baseline; literature says myth — test honestly, cheaply |
| 39 | Role-expansion detector | HAVE | minutes-share trend × usage trend rising together |
| 40 | Usage-vs-efficiency divergence | HAVE | volume up + efficiency down = forced offense flag |
| 41 | FT% as leading indicator of shooting form | HAVE | lowest-noise stat leads 3P% recovery |
| 42 | Rim-rate trend | HAVE | share of attempts at the rim (x-y) — athleticism/health footprint |
| 43 | Shot-distance drift | HAVE | average attempt distance EWMA — range expanding or collapsing |
| 44 | Self-creation index | HAVE | unassisted share of makes (play-by-play assist tags) |
| 45 | Garbage-time-cleaned rates | HAVE | strip ≥15-point-margin minutes via stints before computing all trends |
| 46 | Early-foul tendency | HAVE | first-period foul rate → minutes-risk feature |
| 47 | Post-absence ramp curve | HAVE | pooled games-since-return performance profile (injury-history archive + boxes) |
| 48 | Structural-break detector | HAVE | rolling mean-shift test on rates (role changed, not drifted) |

## E. Lineup context and teammate interaction (12) — stints and possessions data

| # | Feature | Status | Sketch |
|---|---|---|---|
| 49 | With/without-star splits | HAVE | production with top-usage teammate on vs off floor, shrunken |
| 50 | Usage-absorption elasticity | HAVE | historical usage lift per point of vacated teammate usage — personalizes redistribution |
| 51 | Lineup familiarity | HAVE | possessions logged with the current projected five |
| 52 | **On-floor pace differential** | PROXY | possessions/min in the player's stints vs team average — the honest "speed" proxy (see N/A note below) |
| 53 | Teammate 3pt gravity × paint rate | HAVE | spacing: shooters around a slasher |
| 54 | Starter-unit vs bench-unit production split | HAVE | who they share the floor with matters |
| 55 | Closing-lineup membership rate | HAVE | last-5-minutes-of-close-games share — coach trust revealed |
| 56 | Best-pair lift | HAVE | production with their #1 synergy teammate on floor |
| 57 | Competition quality of minutes | HAVE | share of minutes vs opposing starters |
| 58 | Personal stint plus-minus stability | HAVE | RAPM-lite consistency |
| 59 | System dependence | HAVE | player 3PA rate × team assist rate (catch-and-shoot ecosystems) |
| 60 | Second-unit anchor flag | HAVE | bench player who plays with starters vs pure bench units |

## F. Shot quality and location — 202,987 shots with x-y (12)

| # | Feature | Status | Sketch |
|---|---|---|---|
| 61 | Shot-diet expected points | HAVE | player's zone mix priced at league conversion — diet quality separate from shooting skill |
| 62 | Zone-mix drift | HAVE | divergence of recent vs season shot mix (role/health signal) |
| 63 | Rim-vs-floater ratio trend | HAVE | finishing profile shift |
| 64 | Corner-3 vs above-break-3 mix | HAVE | corner threes are teammate-created — system signal |
| 65 | Early-clock (transition) scoring share | HAVE | play-by-play clock: open-floor dependence |
| 66 | Late-clock bailout share | HAVE | last-4-seconds attempts — usage burden quality |
| 67 | 3P% by rest days | HAVE | legs and the long ball |
| 68 | Court-side asymmetry | HAVE | left/right preference from x-sign — probably noise, one line to test |
| 69 | Midrange reliance | HAVE | dying-diet indicator |
| 70 | Personal zone conversion vs league, shrunken | HAVE | the zone-map machinery at player level (K per zone already validated) |
| 71 | Clutch FT split | HAVE | FT% in close-late situations from play-by-play |
| 72 | Shot-quality-allowed when defending? | N/A | no defender-matching on shots without tracking data — noted |

## G. Officiating interactions (6) — expectations LOW (team-level crew test was a clean null)

| # | Feature | Status | Sketch |
|---|---|---|---|
| 73 | FT-dependent player × crew FT propensity | HAVE | player-level heterogeneity might exist where the team-level effect didn't |
| 74 | Star-whistle proxy | HAVE | high-usage FTr lift under tight crews |
| 75 | Foul-prone player × tight crew → foul-out risk | HAVE | minutes-risk channel |
| 76 | Crew pace effect × transition-dependent player | HAVE | whistle tempo interaction |
| 77 | Technical-foul-prone × technical-prone refs | HAVE | tiny samples; flagged speculative |
| 78 | Personal ref-crew history | HAVE | player rates under specific refs — likely pure noise; cheap to kill |

## H. Schedule and fatigue engineering (8)

| # | Feature | Status | Sketch |
|---|---|---|---|
| 79 | Rolling 7-day minutes load | HAVE | fatigue odometer |
| 80 | Minutes load × age | COLLECT-S | vets under heavy recent load |
| 81 | 3-in-5 flag × team bench depth | HAVE | thin teams can't rest anyone |
| 82 | Season-phase adjustments | HAVE | opening ramp / dog days / late-season |
| 83 | All-Star-break reset | HAVE | before/after break splits |
| 84 | Rest differential vs opponent | HAVE | my rest minus yours |
| 85 | Games-in-14-days density | HAVE | the 44-game 2026 calendar is denser — era-aware |
| 86 | Altitude / arena elevation | COLLECT-S | static table; near-zero expected, one line to test |

## I. Cross-season identity and stability (6)

| # | Feature | Status | Sketch |
|---|---|---|---|
| 87 | Previous-season rate as shrinkage anchor | HAVE | the multi-season prior idea (validated machinery from the player-value work) applied to rates |
| 88 | Career trajectory slope | HAVE | year-over-year rate deltas → projected drift |
| 89 | Team-change reset speed | HAVE | how fast rates re-stabilize after a trade — learned pooling |
| 90 | Coach-change rotation shock | PROXY | coach IDs not in repo; proxy = team rotation-trait shift detection |
| 91 | Contract-year effect | N/A | contract data not collected; noted |
| 92 | Two-season blended identity | HAVE | optimal old/new season weight per stat family (decay half-life sweep) |

## J. Team-context conditionals that sharpen player predictions (8)

| # | Feature | Status | Sketch |
|---|---|---|---|
| 93 | Possession-denominated rates | HAVE | per-possession instead of per-minute production × team pace forecast — pace-proof rates |
| 94 | Blowout-expectation × personal minutes elasticity | HAVE | who gains/loses minutes in expected blowouts (internal proxy, never the betting line) |
| 95 | Team 3pt-volume trend spillover | HAVE | rising team volume lifts whose attempts |
| 96 | Opponent recent defensive-profile drift | HAVE | scheme-change detection via allowed-channel mix shift |
| 97 | Playoff-race desperation context | HAVE | standings pressure computable from results |
| 98 | Season-series familiarity | HAVE | 1st vs 3rd meeting adjustments |
| 99 | Attendance/TV context | N/A | not captured; noted |
| 100 | Within-season head-to-head micro-update | HAVE | this-season vs this-opponent prior, shrunken into the matchup |

---

## Honest unavailability notes (so nobody re-chases these)

- **Player speed / athleticism tracking** (John's question): Second-Spectrum-style tracking
  (speed, distance, acceleration) is not publicly available for the WNBA. The honest
  proxies we CAN build: on-floor pace differential (#52), transition scoring share (#65),
  fastbreak-points rate (already a channel), rim-rate trend (#42). If league tracking data
  ever becomes purchasable, that decision goes to John.
- **Defender-matchup shot quality** (#72), **overseas offseason load** (#35),
  **contract years** (#91), **attendance** (#99): no honest source today.
- **Heights/weights/age/draft**: one small collection closes candidates #7, 9, 17, 18,
  27–31, 33, 80, 86 — in flight now.

## What happens next (the lab loop)

1. Screen all HAVE-status candidates under `player_feature_screen_v1` (registered):
   2021–2024 only, shifted everything, alpha sweeps, permutation nulls, false-discovery
   control. 2025–2026 stay untouched.
2. Bios land → the COLLECT-S wave screens the same way.
3. Survivors + their interactions go into a registered confirmation experiment on the
   quarantined years with real promotion gates.
4. Confirmed features feed the joint player→team rebuild (the differential system the
   coherence study designed) — and only then does news go on top.
