from datetime import datetime
from flask import jsonify


def format_dn(dn):
    temp = dn.isoformat()
    if len(temp) < len("2022-04-10T07:00:23.53"):
        return temp+"+00:00"
    else:
        return temp[:-4]+"+00:00"


def parse_events(range_start, range_end, start_dt, interval, duration, url, description, bgcolour):
    results = []
    year = 31536000
    d = datetime.fromisoformat(start_dt)
    t = datetime.fromisoformat(range_start)
    re = datetime.fromisoformat(range_end)

    # we are going to limit it to the end date
    # var limit=Math.trunc((year*3)/interval)

    ref = d.timestamp()
    cur = t.timestamp()
    end = re.timestamp()

    diff = cur - ref
    interval_count = int(diff / interval)

    rem = diff % interval

    event_date = ref + (interval_count * interval)
    while event_date < end:
        dn = datetime.utcfromtimestamp(event_date)

        display_dt = format_dn(dn)

        result = {
            "title": description,
            "start": display_dt,
            "end": display_dt,
            "url": url
        }
        if duration > 0:
            end_dt = datetime.utcfromtimestamp(event_date+duration)
            result["end"] = format_dn(end_dt)

        if (bgcolour != "defaultbg"):
            result["backgroundColor"] = bgcolour

        results.append(result)
        event_date = event_date + interval

    return results


def fetch_events(request):
    start = request.args.get("start").replace("Z", "")
    end = request.args.get("end").replace("Z", "")
    anniversary = 31536000

    events = []

    events.extend(parse_events(start, end, '2022-04-07T18:38:53', 217290.538549, 0, 'https://www.edsm.net/en_GB/system/id/31640419/name/Blaa+Eohn+YZ-G+d10-0',
                               'Blaa Eohn YZ-G d10-0 (Planet of Slightly Lesser Death) - Periapsis', 'defaultbg'))
    events.extend(parse_events(start, end, '2022-04-09T00:49:00', 217290.538549, 0, 'https://www.edsm.net/en_GB/system/id/31640419/name/Blaa+Eohn+YZ-G+d10-0',
                               'Blaa Eohn YZ-G d10-0 (Planet of Slightly Lesser Death) - Apoapsis', 'defaultbg'))
    events.extend(parse_events(start, end, '2022-03-24T12:31:00', 695478.442, 0,
                               'https://www.edsm.net/en_GB/system/id/4308078/name/Synuefe+WH-F+c0', 'Synuefe WH-F c0 (Cyanean Rocks)', 'defaultbg'))
    events.extend(parse_events(start, end, '2021-05-18T07:00:00', anniversary, 3600*5,
                               'https://canonn.science/codex/the-gnosis/', 'Gnosis Launch Anniversary', '#ef7b04'))

    return jsonify(events)
