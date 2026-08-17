import csv, collections, statistics
from datetime import datetime, timezone
P=r"C:/Users/jgallagher/wnba-betting-model/data/odds_capture/capture_log.csv"
rows=[]
for r in csv.DictReader(open(P,encoding='utf-8-sig',errors='replace')):
    rows.append(r)
print('capture_log rows',len(rows))
print('cols',list(rows[0].keys()))
snaps=sorted(set(r['snapshot_utc'] for r in rows))
print('n snapshots',len(snaps),'first',snaps[0],'last',snaps[-1])
print('books',len(set(r['bookmaker'] for r in rows)), collections.Counter(r['bookmaker'] for r in rows).most_common(8))
print('markets',collections.Counter(r['market'] for r in rows).most_common())
com=sorted(set(r['commence_time'] for r in rows))
print('commence span',com[0],'->',com[-1],'n games(distinct commence)',len(com))

def T(s):
    return datetime.strptime(s,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
def C(s):
    return datetime.fromisoformat(s.replace('Z','+00:00'))

# consensus total per game per snapshot, movement vs time-to-tip
key=lambda r:(r['home_team'],r['away_team'],r['commence_time'])
tot=collections.defaultdict(dict)   # game -> snapshot -> list of points (totals, Over)
for r in rows:
    if r['market']!='totals' or r['outcome']!='Over' or not r['point']: continue
    tot[key(r)].setdefault(r['snapshot_utc'],[]).append(float(r['point']))
print('\ngames with totals tape:',len(tot))
moves=[]; buckets=collections.defaultdict(list)
for g,d in tot.items():
    tip=C(g[2])
    series=sorted(((T(s),statistics.mean(v)) for s,v in d.items()))
    series=[(t,v) for t,v in series if t<=tip]
    if len(series)<3: continue
    open_v=series[0][1]; close_v=series[-1][1]
    moves.append(abs(close_v-open_v))
    for t,v in series:
        h=(tip-t).total_seconds()/3600.0
        b = '>24h' if h>24 else '12-24h' if h>12 else '6-12h' if h>6 else '3-6h' if h>3 else '1-3h' if h>1 else '<1h'
        buckets[b].append(abs(close_v-v))
print('games with >=3 pre-tip snapshots:',len(moves))
if moves:
    m=sorted(moves)
    print('|close-open| total pts: med %.2f  p90 %.2f  max %.2f  mean %.3f'%(statistics.median(m),m[int(.9*len(m))],m[-1],statistics.mean(m)))
print('\nMean |consensus total at time t - closing consensus total|, by time-to-tip bucket:')
for b in ['>24h','12-24h','6-12h','3-6h','1-3h','<1h']:
    v=buckets.get(b,[])
    if v: print('  %-7s n=%5d  mean residual to close = %.3f pts   p90 %.2f'%(b,len(v),statistics.mean(v),sorted(v)[int(.9*len(v))]))
