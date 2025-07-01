import os
import pandas as pd
import numpy as np
from tqdm import tqdm
import re

DATA_DIR = "data"
PBP_DIR = os.path.join(DATA_DIR, "playbyplay")

# --- Helper functions ---
def parse_shot_info(description):
    if pd.isna(description):
        return None, None, None
    desc = str(description).upper()
    shot_type = None
    if "3PT" in desc or "3-POINT" in desc:
        shot_type = "3PT"
    elif "LAYUP" in desc:
        shot_type = "LAYUP"
    elif "DUNK" in desc:
        shot_type = "DUNK"
    elif "FREE THROW" in desc or "FT" in desc:
        shot_type = "FT"
    elif "JUMP SHOT" in desc or "PULLUP" in desc:
        shot_type = "JUMP_SHOT"
    else:
        shot_type = "OTHER"
    distance_match = re.search(r'(\d+)\'', desc)
    distance = int(distance_match.group(1)) if distance_match else None
    points_match = re.search(r'\((\d+)\s*PTS?\)', desc)
    points = int(points_match.group(1)) if points_match else None
    return shot_type, distance, points

def parse_rebound_info(description):
    if pd.isna(description):
        return None
    desc = str(description).upper()
    if "OFF:" in desc:
        return "OFFENSIVE"
    elif "DEF:" in desc:
        return "DEFENSIVE"
    else:
        return "UNKNOWN"

def calculate_opponent_strength(game_df):
    """Calculate opponent strength metrics for normalization."""
    # Get team IDs
    teams = game_df['PLAYER1_TEAM_ID'].dropna().unique()
    if len(teams) != 2:
        return {}
    
    team1, team2 = teams
    opponent_strength = {}
    
    # Calculate basic team stats for this game
    for team_id in teams:
        team_events = game_df[game_df['PLAYER1_TEAM_ID'] == team_id]
        opponent_id = team2 if team_id == team1 else team1
        
        # Calculate offensive efficiency (points per possession)
        made_shots = team_events[team_events['EVENTMSGTYPE'] == 1]  # Made shots
        total_points = sum(parse_shot_info(desc)[2] or 0 for desc in made_shots['HOMEDESCRIPTION'].fillna('') + made_shots['VISITORDESCRIPTION'].fillna(''))
        
        # Count possessions (simplified - defensive rebounds + turnovers)
        def_rebounds = team_events[(team_events['EVENTMSGTYPE'] == 4) & 
                                  (team_events['HOMEDESCRIPTION'].str.contains('DEF:', na=False) | 
                                   team_events['VISITORDESCRIPTION'].str.contains('DEF:', na=False))]
        turnovers = team_events[team_events['EVENTMSGTYPE'] == 5]
        possessions = len(def_rebounds) + len(turnovers)
        
        offensive_efficiency = total_points / max(possessions, 1)
        
        opponent_strength[team_id] = {
            'opponent_id': opponent_id,
            'offensive_efficiency': offensive_efficiency,
            'total_points': total_points,
            'possessions': possessions
        }
    
    return opponent_strength

def track_on_court(game_df):
    """Track on-court players for each team throughout the game using substitution events."""
    print(f"Debug: Starting on-court tracking for game {game_df['GAME_ID'].iloc[0]}")
    on_court = {team_id: set() for team_id in game_df['PLAYER1_TEAM_ID'].dropna().unique()}
    print(f"Debug: Found teams: {list(on_court.keys())}")
    
    # Find first substitution to identify starters
    substitutions = game_df[game_df['EVENTMSGTYPE'] == 8]
    if len(substitutions) > 0:
        first_sub_event = substitutions['EVENTNUM'].min()
        print(f"Debug: First substitution at event {first_sub_event}")
        
        # Find all players who appear in first period before first substitution
        starters = game_df[
            (game_df['PERIOD'] == 1) & 
            (game_df['EVENTNUM'] < first_sub_event) & 
            (game_df['PLAYER1_ID'].notna()) & 
            (game_df['PLAYER1_ID'] != 0) &
            (game_df['PLAYER1_TEAM_ID'].notna())
        ]['PLAYER1_ID'].unique()
        
        # Assign starters to their teams
        for player_id in starters:
            player_row = game_df[game_df['PLAYER1_ID'] == player_id].iloc[0]
            team_id = player_row['PLAYER1_TEAM_ID']
            if team_id in on_court:
                on_court[team_id].add(player_id)
        
        print(f"Debug: Found {len(starters)} starters: {starters}")
    else:
        print("Debug: No substitutions found, using all players in first period")
        # If no substitutions, use all players in first period
        first_period_players = game_df[
            (game_df['PERIOD'] == 1) & 
            (game_df['PLAYER1_ID'].notna()) & 
            (game_df['PLAYER1_ID'] != 0) &
            (game_df['PLAYER1_TEAM_ID'].notna())
        ]['PLAYER1_ID'].unique()
        
        for player_id in first_period_players:
            player_row = game_df[game_df['PLAYER1_ID'] == player_id].iloc[0]
            team_id = player_row['PLAYER1_TEAM_ID']
            if team_id in on_court:
                on_court[team_id].add(player_id)
        
        print(f"Debug: Found {len(first_period_players)} players in first period")
    
    # Track substitutions
    on_court_by_event = {}
    substitution_count = 0
    for idx, row in game_df.iterrows():
        event_num = row['EVENTNUM']
        event_type = row['EVENTMSGTYPE']
        if event_type == 8:  # Substitution
            out_id = row['PLAYER2_ID']  # Player going OUT
            in_id = row['PLAYER1_ID']   # Player coming IN
            team_id = row['PLAYER1_TEAM_ID']
            if team_id in on_court and pd.notna(out_id) and pd.notna(in_id):
                if out_id in on_court[team_id]:
                    on_court[team_id].remove(out_id)
                on_court[team_id].add(in_id)
                substitution_count += 1
        # Record a snapshot of on-court players at this event
        on_court_by_event[event_num] = {tid: set(pids) for tid, pids in on_court.items()}
    
    print(f"Debug: Tracked {substitution_count} substitutions")
    print(f"Debug: Final on-court players: {sum(len(players) for players in on_court.values())}")
    return on_court_by_event

def track_possessions(game_df, on_court_by_event):
    print(f"Debug: Starting possession tracking")
    possessions = []
    current_possession = {
        'team_id': None,
        'start_event': None,
        'end_event': None,
        'events': [],
        'points': 0,
        'offensive_rebounds': 0,
        'turnovers': 0,
        'on_court': set()
    }
    possession_count = 0
    for idx, row in game_df.iterrows():
        event_type = row['EVENTMSGTYPE']
        event_num = row['EVENTNUM']
        team_id = row['PLAYER1_TEAM_ID']
        # Possession change events
        is_possession_change = False
        next_team_id = None
        if event_type == 4:  # Rebound
            rebound_type = parse_rebound_info(row['HOMEDESCRIPTION'] or row['VISITORDESCRIPTION'])
            if rebound_type == "DEFENSIVE":
                is_possession_change = True
                next_team_id = team_id
        elif event_type == 1:  # Made shot
            is_possession_change = True
            # After a made shot, possession goes to the other team
            if team_id is not None:
                teams = game_df['PLAYER1_TEAM_ID'].dropna().unique()
                next_team_id = [tid for tid in teams if tid != team_id]
                next_team_id = next_team_id[0] if next_team_id else None
        elif event_type == 5:  # Turnover
            is_possession_change = True
            # After a turnover, possession goes to the other team
            if team_id is not None:
                teams = game_df['PLAYER1_TEAM_ID'].dropna().unique()
                next_team_id = [tid for tid in teams if tid != team_id]
                next_team_id = next_team_id[0] if next_team_id else None
        # End and start new possession if needed
        if is_possession_change:
            if current_possession['team_id'] is not None:
                current_possession['end_event'] = event_num
                possessions.append(current_possession.copy())
                possession_count += 1
            current_possession = {
                'team_id': next_team_id,
                'start_event': event_num,
                'end_event': None,
                'events': [],
                'points': 0,
                'offensive_rebounds': 0,
                'turnovers': 0,
                'on_court': set()
            }
        # Track events within possession
        if current_possession['team_id'] is not None:
            current_possession['events'].append({
                'event_num': event_num,
                'event_type': event_type,
                'player_id': row['PLAYER1_ID'],
                'player_name': row['PLAYER1_NAME'],
                'team_id': row['PLAYER1_TEAM_ID'],
                'description': row['HOMEDESCRIPTION'] or row['VISITORDESCRIPTION']
            })
            # Track on-court for this possession
            if event_num in on_court_by_event:
                current_possession['on_court'] = on_court_by_event[event_num].get(current_possession['team_id'], set())
    print(f"Debug: Tracked {possession_count} possessions")
    for i, p in enumerate(possessions[:5]):
        print(f"Possession {i}: team_id={p['team_id']}, on_court={len(p['on_court'])} players, points={p['points']}")
    return possessions

def calculate_player_possession_stats(game_df, possessions, opponent_strength):
    print(f"Debug: Starting player stats calculation")
    player_stats = {}
    valid_possessions = 0
    
    for possession in possessions:
        team_id = possession['team_id']
        on_court = possession.get('on_court', set())
        if team_id is None or not on_court:
            continue
        
        valid_possessions += 1
        for player_id in on_court:
            if pd.isna(player_id):
                continue
            if player_id not in player_stats:
                player_stats[player_id] = {
                    'offensive_possessions': 0,
                    'offensive_points': 0,
                    'team_id': team_id,
                    # Add other stats as needed
                }
            player_stats[player_id]['offensive_possessions'] += 1
            player_stats[player_id]['offensive_points'] += possession['points']
    
    print(f"Debug: Processed {valid_possessions} valid possessions for {len(player_stats)} players")
    if valid_possessions > 0:
        print(f"Debug: Sample player stats - first player: {list(player_stats.keys())[0] if player_stats else 'None'}")
    
    # Normalize by opponent strength
    if opponent_strength:
        for player_id, stats in player_stats.items():
            team_id = stats['team_id']
            if team_id in opponent_strength:
                opp_efficiency = opponent_strength[team_id]['offensive_efficiency']
                # Normalize points per possession by opponent strength
                if stats['offensive_possessions'] > 0:
                    raw_ppp = stats['offensive_points'] / stats['offensive_possessions']
                    stats['normalized_ppp'] = raw_ppp / max(opp_efficiency, 0.1)  # Avoid division by zero
                    stats['opponent_efficiency'] = opp_efficiency
                else:
                    stats['normalized_ppp'] = 0
                    stats['opponent_efficiency'] = opp_efficiency
    
    return player_stats

def process_game_playbyplay(game_file):
    print(f"\nDebug: Processing {game_file}")
    game_df = pd.read_parquet(game_file)
    game_id = game_df['GAME_ID'].iloc[0]
    print(f"Debug: Game ID {game_id}, {len(game_df)} events")
    
    # Calculate opponent strength
    opponent_strength = calculate_opponent_strength(game_df)
    print(f"Debug: Calculated opponent strength for {len(opponent_strength)} teams")
    
    on_court_by_event = track_on_court(game_df)
    possessions = track_possessions(game_df, on_court_by_event)
    player_stats = calculate_player_possession_stats(game_df, possessions, opponent_strength)
    
    if player_stats:
        stats_df = pd.DataFrame.from_dict(player_stats, orient='index')
        stats_df['PLAYER_ID'] = stats_df.index
        stats_df['GAME_ID'] = game_id
        stats_df.reset_index(drop=True, inplace=True)
        print(f"Debug: Generated stats for {len(stats_df)} player-game records")
        return stats_df
    else:
        print(f"Debug: No player stats generated for game {game_id}")
    return pd.DataFrame()

def main():
    print("=== Building Possession-Based Player Features (On-Court Only) ===")
    pbp_files = [f for f in os.listdir(PBP_DIR) if f.endswith('.parquet')]
    print(f"Processing {len(pbp_files)} games...")
    all_player_stats = []
    for game_file in tqdm(pbp_files, desc="Processing games"):
        game_path = os.path.join(PBP_DIR, game_file)
        try:
            game_stats = process_game_playbyplay(game_path)
            if not game_stats.empty:
                all_player_stats.append(game_stats)
        except Exception as e:
            print(f"Error processing {game_file}: {e}")
    print(f"\nDebug: Processed {len(all_player_stats)} games with player stats")
    if all_player_stats:
        print(f"Debug: Total player-game records: {sum(len(stats) for stats in all_player_stats)}")
        combined_stats = pd.concat(all_player_stats, ignore_index=True)
        output_path = os.path.join(DATA_DIR, "player_possession_features.parquet")
        debug_output_path = os.path.join(DATA_DIR, "player_possession_features_debug.parquet")
        try:
            combined_stats.to_parquet(output_path, index=False)
            print(f"\n✅ Saved possession-based features to {output_path}")
        except Exception as e:
            print(f"❌ Error saving to {output_path}: {e}")
        try:
            combined_stats.to_parquet(debug_output_path, index=False)
            print(f"\n✅ Also saved possession-based features to {debug_output_path}")
        except Exception as e:
            print(f"❌ Error saving to {debug_output_path}: {e}")
        print(f"Features include: {len(combined_stats.columns)} columns")
        print(f"Sample columns: {list(combined_stats.columns[:10])}")
        return combined_stats
    else:
        print("❌ No player stats were generated from any games")
    return None

if __name__ == "__main__":
    main() 