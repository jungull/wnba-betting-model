"""
Channel bake-off: raw trend vs structural (offense-tendency x opponent-tendency x conversion)
per scoring channel, with walk-forward validation.

Conventions (inherited from the project):
- Shifted EWMA only: trend entering a game uses strictly prior games (.shift(1)).
- Trends reset each season (within-season streams), >=5 prior games required for eval rows.
- Tune alphas / calibration ONLY on train years; test = 2024-2025.
- 2023 granular (paint/pfd) data is corrupted -> paint & np2 channels exclude 2023 entirely.
- FT & 3PT channels use clean team box data, 2021-2023 train.
"""
import pandas as pd, numpy as np

D = pd.read_csv('channel_base.csv', parse_dates=['GAME_DATE'])
D = D.sort_values(['TEAM_ID', 'GAME_DATE']).reset_index(drop=True)
D['season'] = D['year']

TRAIN_YEARS_BOX = [2021, 2022, 2023]
TRAIN_YEARS_GRAN = [2021, 2022]          # paint/np2: 2023 corrupted
TEST_YEARS = [2024, 2025]
MIN_PRIOR = 5
ALPHAS = [0.05, 0.08, 0.10, 0.15, 0.20, 0.30]

def ewma_shifted(series, alpha):
    """EWMA of prior observations only."""
    return series.ewm(alpha=alpha, adjust=True).mean().shift(1)

def add_trend(df, col, alpha, out):
    df[out] = df.groupby(['TEAM_ID', 'season'], sort=False)[col] \
                .transform(lambda s: ewma_shifted(s, alpha))
    return df

def add_opp_trend(df, col, alpha, out):
    """Trend of what a team ALLOWS (opponent's production against them), shifted."""
    df[out] = df.groupby(['TEAM_ID', 'season'], sort=False)[col] \
                .transform(lambda s: ewma_shifted(s, alpha))
    return df

D['prior_games'] = D.groupby(['TEAM_ID', 'season']).cumcount()

# league per-season running mean (shifted, computed date-ordered across league)
def league_running(df, col):
    t = df.sort_values('GAME_DATE').copy()
    r = t.groupby('season', sort=False)[col].transform(
        lambda s: s.expanding().mean().shift(1))
    return r.reindex(df.index)

# ---------------- channel configs ----------------
# raw:       trend of the channel points itself
# structural: attempts-side (own tendency x opp allowed ratio) x conversion-side
CHANNELS = {
    'ft': dict(actual='ch_ft', train_years=TRAIN_YEARS_BOX,
               own_att='team_fta', opp_allow='opp_pf',    # opp fouls committed drives FTA
               conv='team_ft_pct', conv_mult=1.0),
    '3pt': dict(actual='ch_3pt', train_years=TRAIN_YEARS_BOX,
                own_att='team_fg3a', opp_allow='opp_fg3a',  # 3PA opponent allows
                conv=None, conv_mult=3.0),                  # conv handled separately (3P%)
    'paint': dict(actual='ch_paint', train_years=TRAIN_YEARS_GRAN,
                  own_att=None, opp_allow='opp_ch_paint', conv=None, conv_mult=1.0),
    'np2': dict(actual='ch_np2', train_years=TRAIN_YEARS_GRAN,
                own_att=None, opp_allow='opp_ch_np2', conv=None, conv_mult=1.0),
}

results = []
pred_cols = {}

for ch, cfg in CHANNELS.items():
    act = cfg['actual']
    mask_ok = D[act].notna()
    if ch in ('paint', 'np2'):
        mask_ok &= D.season != 2023

    # ---- tune alpha for RAW trend on train years ----
    best = (None, np.inf)
    for a in ALPHAS:
        tmp = D.copy()
        tmp = add_trend(tmp, act, a, 'p')
        m = mask_ok & tmp.season.isin(cfg['train_years']) & (tmp.prior_games >= MIN_PRIOR)
        mae = (tmp.loc[m, 'p'] - tmp.loc[m, act]).abs().mean()
        if mae < best[1]:
            best = (a, mae)
    a_raw = best[0]
    D = add_trend(D, act, a_raw, f'raw_{ch}')

    # ---- structural chain ----
    a = a_raw  # same smoothing for ingredients (isolates structure-vs-raw, not alpha)
    if ch == 'ft':
        D = add_trend(D, 'team_fta', a, 'fta_t')          # own FTA tendency
        D = add_opp_trend(D, 'opp_pf', a, 'opp_pf_allow') # fouls this team's opponents commit...
        # NOTE: opp_pf on team T's row = fouls committed BY T's opponent in that game.
        # Trend of it grouped by T = fouls T's opponents commit vs T (i.e., fouls T draws) -> own side.
        # The opponent-side signal must come from the OPPONENT's own foul trend:
        D = add_trend(D, 'team_pf', a, 'pf_t')            # each team's own fouls-committed trend
        pf_map = D[['GAME_ID', 'TEAM_ID', 'pf_t']].rename(
            columns={'TEAM_ID': 'OPP_TEAM_ID', 'pf_t': 'opp_pf_trend'})
        D = D.merge(pf_map, on=['GAME_ID', 'OPP_TEAM_ID'], how='left')
        D['lg_pf'] = league_running(D, 'team_pf')
        D['ftpct_t'] = D.groupby(['TEAM_ID', 'season'], sort=False)['team_ft_pct'] \
                        .transform(lambda s: ewma_shifted(s, a))
        D[f'str_{ch}'] = D['fta_t'] * (D['opp_pf_trend'] / D['lg_pf']) * D['ftpct_t']
    elif ch == '3pt':
        D = add_trend(D, 'team_fg3a', a, 'fg3a_t')
        D = add_opp_trend(D, 'opp_fg3a', a, 'fg3a_allow_t')   # 3PA this team allows
        allow_map = D[['GAME_ID', 'TEAM_ID', 'fg3a_allow_t']].rename(
            columns={'TEAM_ID': 'OPP_TEAM_ID', 'fg3a_allow_t': 'opp_fg3a_allow'})
        D = D.merge(allow_map, on=['GAME_ID', 'OPP_TEAM_ID'], how='left')
        D['lg_fg3a'] = league_running(D, 'team_fg3a')
        D['fg3pct_t'] = D.groupby(['TEAM_ID', 'season'], sort=False)['team_fg3m'] \
                          .transform(lambda s: ewma_shifted(s, a)) / D['fg3a_t']
        D[f'str_{ch}'] = D['fg3a_t'] * (D['opp_fg3a_allow'] / D['lg_fg3a']) * D['fg3pct_t'] * 3.0
    else:  # paint / np2 : points-level opponent adjustment (no attempts data)
        src = act
        D = add_opp_trend(D, cfg['opp_allow'], a, f'{ch}_allow_t')   # what team allows
        allow_map = D[['GAME_ID', 'TEAM_ID', f'{ch}_allow_t']].rename(
            columns={'TEAM_ID': 'OPP_TEAM_ID', f'{ch}_allow_t': f'opp_{ch}_allow'})
        D = D.merge(allow_map, on=['GAME_ID', 'OPP_TEAM_ID'], how='left')
        D[f'lg_{ch}'] = league_running(D, src)
        D[f'str_{ch}'] = D[f'raw_{ch}'] * (D[f'opp_{ch}_allow'] / D[f'lg_{ch}'])

    # ---- evaluate on test years ----
    m = (mask_ok & D.season.isin(TEST_YEARS) & (D.prior_games >= MIN_PRIOR)
         & D[f'raw_{ch}'].notna() & D[f'str_{ch}'].notna())
    n = int(m.sum())
    err_r = (D.loc[m, f'raw_{ch}'] - D.loc[m, act]).abs()
    err_s = (D.loc[m, f'str_{ch}'] - D.loc[m, act]).abs()
    # paired sign test-ish: bootstrap the MAE difference
    rng = np.random.default_rng(7)
    diffs = err_s.values - err_r.values
    boots = [diffs[rng.integers(0, len(diffs), len(diffs))].mean() for _ in range(2000)]
    p_str_better = float(np.mean(np.array(boots) < 0))
    results.append(dict(channel=ch, alpha=a_raw, n_test=n,
                        mae_raw=err_r.mean(), mae_structural=err_s.mean(),
                        delta=err_s.mean() - err_r.mean(),
                        prob_structural_better=p_str_better))
    pred_cols[ch] = (f'raw_{ch}', f'str_{ch}')

res = pd.DataFrame(results)
res.to_csv('channel_results.csv', index=False)
print(res.round(3).to_string(index=False))
D.to_csv('channel_with_preds.csv', index=False)
