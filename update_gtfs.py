import csv
import zipfile
import urllib.request
import io
import json
import datetime as d
import re

from zoneinfo import ZoneInfo
from pathlib import Path

URL = 'https://www.transportforireland.ie/transitData/Data/GTFS_All.zip'
BUS_ROUTE = '1_39_c_a'
TZ = ZoneInfo('Europe/Dublin')

with urllib.request.urlopen(URL, timeout=180) as r:
    z = zipfile.ZipFile(io.BytesIO(r.read()))

def rows(name):
    return csv.DictReader(
        io.TextIOWrapper(
            z.open(name + '.txt'),
            encoding='utf-8-sig'
        )
    )

now = d.datetime.now(TZ)
today = now.date()

days = [
    today + d.timedelta(days=i)
    for i in range(-1, 15)
]

def date(s):
    return d.datetime.strptime(s, '%Y%m%d').date()

def seconds(tm):
    h, m, s = map(int, tm.split(':'))
    return h * 3600 + m * 60 + s

# CALENDAR

active = {}

for r in rows('calendar') if 'calendar.txt' in z.namelist() else []:
    active[r['service_id']] = {
        x for x in days
        if date(r['start_date']) <= x <= date(r['end_date'])
        and r[x.strftime('%A').lower()] == '1'
    }

for r in rows('calendar_dates') if 'calendar_dates.txt' in z.namelist() else []:
    x = date(r['date'])
    a = active.setdefault(r['service_id'], set())

    if x in days:
        if r['exception_type'] == '1':
            a.add(x)
        else:
            a.discard(x)

# STOPS

stops = {}
destinations = set()
stop_details = {}

for r in rows('stops'):
    sid = r['stop_id']
    code = r.get('stop_code', '')
    name = r['stop_name'].lower()

    stop_details[sid] = {
        'name': r['stop_name'],
        'lat': r.get('stop_lat'),
        'lon': r.get('stop_lon')
    }

    for n in ('1903', '1853'):
        if code == n or re.search(
            r'DB0*' + n + r'(?!\d)', sid, re.I
        ):
            stops[sid] = n

    if 'coolmine' in name and (
        'station' in name
        or 'rail' in name
        or name.strip() == 'coolmine'
    ):
        stops[sid] = 'rail'

    if 'connolly' in name or 'pearse' in name:
        destinations.add(sid)

# ROUTES AND TRIPS

routes = {
    r['route_id']: r
    for r in rows('routes')
    if r['route_short_name'].strip() == '39'
    or r['route_type'] == '2'
}

trips = {
    r['trip_id']: r
    for r in rows('trips')
    if r['route_id'] in routes
    and active.get(r['service_id'])
}

board = {}
dest = {}
bus_times = {}

# STOP TIMES

for r in rows('stop_times'):

    tid = r['trip_id']
    sid = r['stop_id']

    if tid not in trips:
        continue

    trip = trips[tid]
    seq = int(r['stop_sequence'])
    typ = routes[trip['route_id']]['route_type']

    if sid in stops and r.get('pickup_type', '0') != '1':

        key = stops[sid]

        if (key == 'rail') == (typ == '2'):
            board.setdefault(tid, []).append(
                (key, seq, r['departure_time'])
            )

    if typ == '2' and sid in destinations:
        dest.setdefault(tid, []).append(seq)

    if trip['route_id'] == BUS_ROUTE:

        tm = r.get('departure_time') or r.get('arrival_time')

        if tm:
            bus_times.setdefault(tid, []).append([
                seq,
                sid,
                seconds(tm)
            ])

# ORIGINAL SCHEDULE

out = {
    k: []
    for k in ('1903', '1853', 'rail')
}

for tid, entries in board.items():

    t = trips[tid]
    head = t.get('trip_headsign', '')

    for key, seq, tm in entries:

        if key == 'rail' and not any(
            s > seq for s in dest.get(tid, [])
        ):
            continue

        if key == '1903' and 'ongar' in head.lower():
            continue

        if key == '1853' and 'burlington' in head.lower():
            continue

        if not tm:
            continue

        for day in active[t['service_id']]:

            dt = d.datetime.combine(
                day, d.time(), TZ
            ) + d.timedelta(seconds=seconds(tm))

            if dt >= now - d.timedelta(hours=2):

                out[key].append({
                    'time': dt.isoformat(),
                    'destination': head or (
                        'Connolly / Pearse'
                        if key == 'rail' else ''
                    )
                })

for k, v in out.items():

    unique = {
        x['time']: x
        for x in v
    }

    out[k] = sorted(
        unique.values(),
        key=lambda x: x['time']
    )

    if not out[k]:
        raise RuntimeError(
            'No departures for ' + k
        )

# BUS REALTIME SUPPORT

bus_trips = []
used_stops = set()
used_services = set()

for tid, times in bus_times.items():

    t = trips[tid]
    direction = t.get('direction_id', '')

    target = {
        '0': '8240DB001853',
        '1': '8240DB001903'
    }.get(direction)

    if not target:
        continue

    times.sort(key=lambda x: x[0])

    if not any(x[1] == target for x in times):
        continue

    used_services.add(t['service_id'])

    for x in times:
        used_stops.add(x[1])

    bus_trips.append({
        'trip_id': tid,
        'service_id': t['service_id'],
        'direction_id': int(direction),
        'destination': t.get('trip_headsign', ''),
        'target_stop': target,
        'stops': times
    })

if not bus_trips:
    raise RuntimeError('No route 39 trip data')

bus_services = {
    sid: sorted(
        day.isoformat()
        for day in active[sid]
    )
    for sid in used_services
}

bus_stops = {
    sid: stop_details[sid]
    for sid in sorted(used_stops)
    if sid in stop_details
}

# SAVE

result = {
    'generated': now.isoformat(),
    'source': URL,
    'departures': out,
    'bus_data': {
        'route_id': BUS_ROUTE,
        'timezone': 'Europe/Dublin',
        'services': bus_services,
        'stops': bus_stops,
        'trips': bus_trips
    }
}

Path('schedule.json').write_text(
    json.dumps(
        result,
        ensure_ascii=False,
        separators=(',', ':')
    ),
    encoding='utf-8'
)

print('Schedule generated successfully')
print('Bus trips:', len(bus_trips))
print('Bus stops:', len(bus_stops))
print('Bus services:', len(bus_services))
print('Broadway Road:', len(out['1903']))
print('Coolmine Woods:', len(out['1853']))
print('Trains:', len(out['rail']))
