import csv,json,zipfile,io,sys,urllib.request,tempfile
from pathlib import Path
URL='https://www.transportforireland.ie/transitData/Data/GTFS_Realtime.zip'
def main(path):
 with zipfile.ZipFile(path) as z:
  def rows(name):
   with z.open(name+'.txt') as f: yield from csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig'))
  trips={r['trip_id']:r for r in rows('trips') if r['route_id']=='1_39_c_a'}
  stops={'8240DB001903':'city','8240DB001853':'ongar'}
  out=[]
  for r in rows('stop_times'):
   t=trips.get(r['trip_id']); k=stops.get(r['stop_id'])
   if t and k and t['direction_id']==('1' if k=='city' else '0') and r['pickup_type']!='1':
    out.append(dict(id=r['trip_id'],service=t['service_id'],key=k,seq=int(r['stop_sequence']),time=r['departure_time'],destination=t['trip_headsign']))
  services={r['service'] for r in out}
  data=dict(trips=out,calendar=[r for r in rows('calendar') if r['service_id'] in services],exceptions=[r for r in rows('calendar_dates') if r['service_id'] in services])
  assert {r['key'] for r in out}=={'city','ongar'}
  Path(__file__).with_name('bus_schedule.json').write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
  print(len(out),[(r['id'],r['key'],r['seq'],r['time']) for r in out if r['id'] in ('6056_13187','6056_12994')])
if __name__=='__main__':
 if len(sys.argv)>1: main(sys.argv[1])
 else:
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'feed.zip'; urllib.request.urlretrieve(URL,p); main(p)
