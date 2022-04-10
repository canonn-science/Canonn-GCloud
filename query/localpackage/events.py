from datetime import datetime
from pickletools import read_unicodestring1
from flask import jsonify
from math import cos, acos, sin, asin, sqrt, radians, degrees


def format_dn(dn):
    temp = dn.isoformat()
    if len(temp) < len("2022-04-10T07:00:23.53"):
        return temp+"+00:00"
    else:
        return temp[:-4]+"+00:00"


def parse_events(system, range_start, range_end, reference_dt, interval, duration, url, description, bgcolour="defaultbg"):
    results = []
    year = 31536000
    ref_dt = datetime.fromisoformat(reference_dt)
    range_start_dt = datetime.fromisoformat(range_start)
    range_end_dt = datetime.fromisoformat(range_end)

    # we are going to limit it to the end date
    # var limit=Math.trunc((year*3)/interval)

    reference_ts = ref_dt.timestamp()
    range_start_ts = range_start_dt.timestamp()
    range_end_ts = range_end_dt.timestamp()

    if interval != 0:
        interval_count = int((range_start_ts - reference_ts) / interval)
        event_ts = reference_ts + (interval_count * interval)
    else:
        range_end_ts = reference_ts
        event_ts = reference_ts
        interval = 99999999999999999999999

    while event_ts <= range_end_ts:
        dn = datetime.utcfromtimestamp(event_ts)

        result = {
            "system": system,
            "title": description,
            "start": format_dn(dn),
            "url": url
        }
        if duration > 0:
            end_dt = datetime.utcfromtimestamp(event_ts+duration)
            result["end"] = format_dn(end_dt)

        if (bgcolour != "defaultbg"):
            result["backgroundColor"] = bgcolour

        results.append(result)
        event_ts = event_ts + interval

    return results


def getSeperation(angle, orbitalInclination1, orbitalInclination2, semiMajorAxisKm, radius1, radius2):
    orbital_angle = abs(orbitalInclination1 - orbitalInclination2)
    """
        First calculate the height of triangle bounded by the focus of the orbit, the point where the orbital plane
        crosses the circumference and the point where the planets will be on the circumference using the semiMajorAxis
        and the angle opposite the line between the two points on the circumference.
    """
    a = semiMajorAxisKm
    c = a

    b = sqrt(pow(a, 2) + pow(c, 2) - (2 * a * c * cos(radians(angle))))
    C = degrees(acos((pow(b, 2) + pow(a, 2) - pow(c, 2)) / (2 * b * a)))

    area = (a * b * sin(radians(C))) / 2
    hc = (2 * area) / c

    """
        The height of the triangle calculated above can now be used to calculate the length of the shortest side
        of an isocelese triangle with an opposite angle equal to the difference between the orbital inclination
        of the two planets.

    """
    b2 = hc
    c2 = b2 / cos(radians(orbital_angle / 2))
    a2 = sqrt(pow(c2, 2) - pow(b2, 2))

    # subtract radii to give us the surface to surface distance
    return (a2 * 2) - (radius1 + radius2)


def overlap_text(overlap):
    if overlap < 2:
        return "Glancing blow"
    if overlap < 50:
        return "Minor impact"
    if overlap < 98:
        return "Major impact"
    return "Head on collision"


def koi_events(range_start, range_end):
    # 28/07/3306 21:16:29
    # 09/08/3306 09:05:27
    # 23/06/3307 15:30:18
    # 23/06/3307 15:30:47
    # 09/08/3306 09:05:27
    reference_dt = "2020-08-09T09:05:27"
    interval = 3437286.34266023
    #interval = 3437999.99999665000
    # two hour duration
    duration = 3600*2
    url = "https://canonn.science/codex/cartographics/rhubarb-and-custard/"
    description = "KOI 413 (Rhubarb and Custard) - "
    reference_angle = 36.36
    # orbital period in seconds
    orbital_period = 15.2289970881365*24*60*60
    radius = 71231.248

    results = []

    ref_dt = datetime.fromisoformat(reference_dt)
    range_start_dt = datetime.fromisoformat(range_start)
    range_end_dt = datetime.fromisoformat(range_end)

    # we are going to limit it to the end date
    # var limit=Math.trunc((year*3)/interval)

    reference_ts = ref_dt.timestamp()
    range_start_ts = range_start_dt.timestamp()
    range_end_ts = range_end_dt.timestamp()

    interval_count = int((range_start_ts - reference_ts) / interval)

    # calculate rotation angle

    # going to subtract an hour
    event_ts = reference_ts + (interval_count * interval)
    print(event_ts)

    while event_ts <= range_end_ts:
        dn = datetime.utcfromtimestamp(event_ts)
        current_angle = reference_angle + \
            ((360/orbital_period)*(event_ts-reference_ts)) % 360

        current_separation = getSeperation(
            current_angle, 88.809996, 89.379995, 24085273.790976, radius, radius)
        current_seperation_radii = abs(
            round(current_separation/(radius*2)*100, 1))

        # print(event_ts)
        result = {
            "system": 'KOI 413',
            "angle": current_angle,
            "seperation_km": current_separation,
            "seperation_radii": current_seperation_radii,
            "title": description + overlap_text(abs(current_seperation_radii)),
            "start": format_dn(dn),
            "url": url
        }
        if duration > 0:
            end_dt = datetime.utcfromtimestamp(event_ts+duration)
            result["end"] = format_dn(end_dt)
        # only show collisions
        if current_separation+1 <= 0 and event_ts >= range_start_ts:
            results.append(result)
        event_ts = event_ts + interval

    return results


def extract_events(request):
    if request.args.get("start"):
        start = request.args.get("start").replace("Z", "")
    else:
        now_ts = datetime.now().timestamp()
        start = datetime.utcfromtimestamp(now_ts).isoformat()

    if request.args.get("nend"):
        end = request.args.get("end").replace("Z", "")
    else:
        # end will be 700 days from today
        now_ts = datetime.fromisoformat(start).timestamp()
        end = datetime.utcfromtimestamp(now_ts+(24*60*60*700)).isoformat()

    anniversary = 31536000

    events = []

    events.extend(parse_events('Blaa Eohn YZ-G d10-0', start, end, '2022-04-07T18:38:53', 217290.538549, 0, 'https://www.edsm.net/en_GB/system/id/31640419/name/Blaa+Eohn+YZ-G+d10-0',
                               'Blaa Eohn YZ-G d10-0 (Planet of Slightly Lesser Death) - Periapsis', 'defaultbg'))
    events.extend(parse_events('Blaa Eohn YZ-G d10-0', start, end, '2022-04-09T00:49:00', 217290.538549, 0, 'https://www.edsm.net/en_GB/system/id/31640419/name/Blaa+Eohn+YZ-G+d10-0',
                               'Blaa Eohn YZ-G d10-0 (Planet of Slightly Lesser Death) - Apoapsis', 'defaultbg'))

    events.extend(parse_events('Varati', start, end, '2021-05-18T07:00:00', anniversary, 0,
                               'https://canonn.science/codex/the-gnosis/', 'Gnosis Launch Anniversary', '#ef7b04'))

    events.extend(koi_events(start, end))
    events.extend(parse_events('Synuefe WH-F c0', start, end, '2020-12-13T14:35:11', 695478.441973363, 0,
                               'https://www.edsm.net/en_GB/system/id/4308078/name/Synuefe+WH-F+c0', 'Synuefe WH-F c0 (Cyanean Rocks)'))

    events.extend(parse_events('Varati', start, end, '2021-05-23T07:00:00', anniversary, 0,
                               'https://canonn.science/lore/', "Dr Arcanonn's Birthday", '#ef7b04'))
    return events


def fetch_events(request):
    system = request.args.get("system")
    events = []

    for event in extract_events(request):
        match_system = (system and system == event.get("system"))
        if match_system or not system:
            events.append(event)

    return jsonify(events)
