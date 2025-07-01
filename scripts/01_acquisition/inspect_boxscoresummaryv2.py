import os
from nba_api.stats.endpoints import boxscoresummaryv2
import pprint

GAME_IDS = ['1022100001', '1022100002', '1022100003', '1022100004', '1022100005']

if __name__ == "__main__":
    for game_id in GAME_IDS:
        print(f"\nFetching boxscoresummaryv2 for GAME_ID {game_id}...")
        try:
            summary = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id)
            json_data = summary.get_json()
            if isinstance(json_data, dict):
                print("Top-level keys:", list(json_data.keys()))
                if 'resultSets' in json_data:
                    for rs in json_data['resultSets']:
                        if isinstance(rs, dict):
                            print(f"ResultSet name: {rs.get('name')}")
                            print(f"Headers: {rs.get('headers')}")
                            if rs.get('rowSet'):
                                for i, header in enumerate(rs['headers']):
                                    if 'arena' in header.lower() or 'city' in header.lower():
                                        print(f"Arena/City field found: {header}")
                                        print(f"Sample value: {rs['rowSet'][0][i]}")
                else:
                    print("No 'resultSets' key in JSON.")
            else:
                print("Response is not a dict. Printing raw response:")
                pprint.pprint(json_data)
        except Exception as e:
            print(f"Error fetching GAME_ID {game_id}: {e}") 