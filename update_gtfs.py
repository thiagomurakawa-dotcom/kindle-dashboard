import csv, zipfile, urllib.request, io, json, datetime as d, re
from zoneinfo import ZoneInfo
from pathlib import Path
URL='https://www.transportforireland.ie/transitData/Data/GTFS_All.zip'
with urllib.request.urlopen(URL,timeout=180) as r: z=zipfile.ZipFile(io.BytesIO(r.read()))
def rows(name):
    return csv.DictReader(io.TextIOWrapper(z.open(name+'.txt'),encoding='utf-8-sig'))
now=d.datetime.now(ZoneInfo('Europe/Dublin')); today=now.date(); days=[today+d.timedelta(days=i) for i in range(-1,15)]
def date(s): return d.datetime.strptime(s,'%Y%m%d').date()
active={}
for r in rows('calendar') if 'calendar.txt' in z.namelist() else []:
    active[r['service_id']]={x for x in days if date(r['start_date'])<=x<=date(r['end_date']) and r[x.strftime('%A').lower()]=='1'}
for r in rows('calendar_dates') if 'calendar_dates.txt' in z.namelist() else []:
    x=date(r['date']); a=active.setdefault(r['service_id'],set())
    if x in days:
        if r['exception_type']=='1': a.add(x)
        else: a.discard(x)
stops={}; destinations=set()
for r in rows('stops'):
    sid=r['stop_id']; code=r.get('stop_code',''); name=r['stop_name'].lower()
    for n in ('1903','1853'):
        if code==n or re.search(r'DB0*'+n+r'(?!\d)',sid,re.I): stops[sid]=n
    if 'coolmine' in name and ('station' in name or 'rail' in name or name.strip()=='coolmine'): stops[sid]='rail'
    if 'connolly' in name or 'pearse' in name: destinations.add(sid)
routes={r['route_id']:r for r in rows('routes') if r['route_short_name'].strip()=='39' or r['route_type']=='2'}
trips={r['trip_id']:r for r in rows('trips') if r['route_id'] in routes and active.get(r['service_id'])}
board={}; dest={}
for r in rows('stop_times'):
    tid=r['trip_id']; sid=r['stop_id']
    if tid not in trips: continue
    seq=int(r['stop_sequence']); typ=routes[trips[tid]['route_id']]['route_type']
    if sid in stops and r.get('pickup_type','0')!='1':
        key=stops[sid]
        if (key=='rail')==(typ=='2'): board.setdefault(tid,[]).append((key,seq,r['departure_time']))
    if typ=='2' and sid in destinations: dest.setdefault(tid,[]).append(seq)
out={k:[] for k in ('1903','1853','rail')}
for tid, entries in board.items():
    t=trips[tid]; head=t.get('trip_headsign','');
    for key,seq,tm in entries:
        if key=='rail' and not any(s>seq for s in dest.get(tid,[])): continue
        if key=='1903' and 'ongar' in head.lower(): continue
        if key=='1853' and 'burlington' in head.lower(): continue
        if not tm: continue
        h,m,s=map(int,tm.split(':'))
        for day in active[t['service_id']]:
            dt=d.datetime.combine(day,d.time(),ZoneInfo('Europe/Dublin'))+d.timedelta(hours=h,minutes=m,seconds=s)
            if dt>=now-d.timedelta(hours=2): out[key].append({'time':dt.isoformat(),'destination':head or ('Connolly / Pearse' if key=='rail' else '')})
for k,v in out.items():
    unique={x['time']:x for x in v}; out[k]=sorted(unique.values(),key=lambda x:x['time'])
    if not out[k]: raise RuntimeError('No departures for '+k+'; check stop identifiers and feed')
Path('schedule.json').write_text(json.dumps({'generated':now.isoformat(),'source':URL,'departures':out},ensure_ascii=False),encoding='utf-8')
