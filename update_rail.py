import csv, io, json, sys, zipfile, urllib.request
from pathlib import Path
URL='https://www.transportforireland.ie/transitData/Data/GTFS_Irish_Rail.zip'
raw=Path(sys.argv[1]).read_bytes() if len(sys.argv)>1 else urllib.request.urlopen(URL,timeout=120).read()
with zipfile.ZipFile(io.BytesIO(raw)) as z:
 def rows(n): return list(csv.DictReader(io.TextIOWrapper(z.open(n+'.txt'),encoding='utf-8-sig')))
 stops=rows('stops'); ids={s['stop_id'] for s in stops if s['stop_name'].strip().lower()=='coolmine'}
 trips={t['trip_id']:t for t in rows('trips') if t['direction_id']=='1' and t['trip_headsign'] in ('Dublin Connolly','Dublin Pearse')}
 out=[]
 for s in rows('stop_times'):
  if s['stop_id'] in ids and s['trip_id'] in trips and s.get('pickup_type')!='1':
   t=trips[s['trip_id']]; out.append(dict(service=t['service_id'],train=t['trip_short_name'],destination=t['trip_headsign'],time=s['departure_time']))
 if not out: raise RuntimeError('No Coolmine departures')
 data=dict(trips=out,calendar=rows('calendar'),exceptions=rows('calendar_dates'))
 Path('rail_schedule.json').write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
 print(len(out),'departures')
