import csv, collections, statistics, json
from datetime import datetime, timedelta, timezone
D=r"C:/Users/jgallagher/wnba-betting-model/data/injury_official_live/"

def parse_tip(game_date, gt):
    # gt like '07:30 (ET)' -> assume PM unless hour >= 11 and < 12 handled; WNBA tips are 11:00 (ET) morning rarely
    gt=gt.split(' ')[0]
    try: h,m=[int(x) for x in gt.split(':')]
    except: return None
    if h<11: h+=12  # PM
    try: d=datetime.strptime(game_date,'%Y-%m-%d')
    except:
        try: d=datetime.strptime(game_date,'%m/%d/%Y')
        except: return None
    # ET = UTC-4 in Aug
    return d.replace(hour=h%24,minute=m)+timedelta(hours=4)

rows=list(csv.DictReader(open(D+'injury_snapshots.csv',encoding='utf-8-sig',errors='replace')))
print('snapshot rows',len(rows))
gd=sorted(set(r['game_date'] for r in rows if r['game_date']))
print('game_date span',gd[0],'->',gd[-1],'n days',len(gd))
print('url_slot_label',collections.Counter(r['url_slot_label'] for r in rows).most_common(12))
print('status',collections.Counter(r['status'] for r in rows).most_common())
# publication lead relative to tip
leads=collections.defaultdict(list)
for r in rows:
    tip=parse_tip(r['game_date'],r['game_time_et'])
    p=r['provider_publication_ts_et']
    if not tip or not p: continue
    try: pt=datetime.fromisoformat(p)+timedelta(hours=4)
    except: continue
    leads[r['status']].append((tip-pt).total_seconds()/3600.0)
print()
print('PUBLICATION LEAD (hours before tip) of the official report carrying each status:')
for s,v in sorted(leads.items(), key=lambda kv:-len(kv[1])):
    v=sorted(v)
    print(f'  {s:14s} n={len(v):5d}  min={v[0]:7.2f} p10={v[int(.1*len(v))]:7.2f} med={statistics.median(v):7.2f} p90={v[int(.9*len(v))]:7.2f} max={v[-1]:7.2f}')

# transitions
tr=list(csv.DictReader(open(D+'status_transitions.csv',encoding='utf-8-sig',errors='replace')))
print()
print('transitions',len(tr))
print('censor_type',collections.Counter(r['censor_type'] for r in tr))
print('tier',collections.Counter(r['tier'] for r in tr))
print('top transitions:',collections.Counter((r['status_before'] or 'NEW')+'->'+r['status_after'] for r in tr).most_common(15))
ub=sorted(r['t_upper_utc_bound'] for r in tr if r['t_upper_utc_bound'])
print('t_upper span',ub[0],'->',ub[-1])
