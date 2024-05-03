import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
# from EDRegionMap.RegionMap import findRegion
import requests
import json
from flask import jsonify
import urllib.parse
from math import sqrt

SOL = [0, 0, 0]
MEROPE = [-78.59375, -149.625, -340.53125]
COALSACK = [423.5625, 0.5, 277.75]  # Musca Dark Region PJ-P b6-8
WITCHHEAD = [355.75, -400.5, -707.21875]  # Ronemar
CALIFORNIA = [-299.0625, -229.25, -876.125]  # HIP 18390
CONESECTOR = [609.4375, 154.25, -1503.59375]  # Outotz ST-I d9-4
WAYPOINT1 = [686.125,   -372.875, -1832.375]  # Oochorrs UF-J c11-0
WAYPOINT2 = [658.625,   -384.21875, -1783.53125]  # Oochorrs CS-F c13-0
WAYPOINT3 = [650.46875,	-382.9375,	-1777.0625]
WAYPOINT4 = [619.25,	-358.375,	-1721]
WAYPOINT5 = [634.25,	-349.9375,	-1700.40625]
WAYPOINT6 = [642.625,	-345.5,	    -1676.125]
UIA2_1 = [-2016.65625,	-654.6875,	-2637.65625]
UIA2_2 = [-2000.40625,	-640.75,	-2624.5625]
UIA2_3 = [-1977.1875,	-651.375,	-2581.5625]


def getDistance(a, b):
    return round(sqrt(pow(float(a[0])-float(b[0]), 2)+pow(float(a[1])-float(b[1]), 2)+pow(float(a[2])-float(b[2]), 2)), 1)


""" replace with an array or dict """


def getNearest(r):
    x = r.get("x")
    y = r.get("y")
    z = r.get("z")
    d = [
        {"name": "Sol", "distance": getDistance(
            [x, y, z], SOL), "coords": SOL},
        {"name": "Merope", "distance": getDistance(
            [x, y, z], MEROPE), "coords": MEROPE},
        {"name": "Coalsack", "distance": getDistance(
            [x, y, z], COALSACK), "coords": COALSACK},
        {"name": "Witchhead", "distance": getDistance(
            [x, y, z], WITCHHEAD), "coords": WITCHHEAD},
        {"name": "California", "distance": getDistance(
            [x, y, z], CALIFORNIA), "coords": CALIFORNIA},
        {"name": "Cone Sector", "distance": getDistance(
            [x, y, z], CONESECTOR), "coords": CONESECTOR},
        {"name": "UIA Route", "distance": getDistance(
            [x, y, z], WAYPOINT1), "coords": WAYPOINT1},
        {"name": "UIA Route", "distance": getDistance(
            [x, y, z], WAYPOINT2), "coords": WAYPOINT2},
        {"name": "UIA Route", "distance": getDistance(
            [x, y, z], WAYPOINT3), "coords": WAYPOINT3},
        {"name": "UIA Route", "distance": getDistance(
            [x, y, z], WAYPOINT4), "coords": WAYPOINT4},
        {"name": "UIA Route", "distance": getDistance(
            [x, y, z], WAYPOINT5), "coords": WAYPOINT5},
        {"name": "UIA Route", "distance": getDistance(
            [x, y, z], WAYPOINT6), "coords": WAYPOINT6},
        {"name": "UIA Route 2", "distance": getDistance(
            [x, y, z], UIA2_1), "coords": UIA2_1},
        {"name": "UIA Route 2", "distance": getDistance(
            [x, y, z], UIA2_2), "coords": UIA2_2},
        {"name": "UIA Route 2", "distance": getDistance(
            [x, y, z], UIA2_3), "coords": UIA2_3},
    ]
    d.sort(key=lambda dx: dx["distance"], reverse=False)

    return d[0]


def get_nhss_systems(request):
    setup_sql_conn()

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)
    if request.args.get("_start"):
        offset = request.args.get("_start")
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    params = []
    clause = ""
    having = ""

    threat = request.args.get("threat")
    system = request.args.get("system")

    if system:
        params.append(system)
        clause = f"{clause} and systemName = %s"

    if threat:
        params.append(threat)
        having = "having sum(case when threat_level = %s then 1 else 0 end) > 0"

    params.append(int(offset))
    params.append(int(limit))

    data = []

    with get_cursor() as cursor:
        sql = f"""
          select systemName,
 		  cast(min(found_at) as char) as first_seen,
		  cast(max(found_at) as char) as last_seen,
		  cast(sum(case when threat_level=0 then 1 else 0 end) as char) as threat_0,
		  cast(sum(case when threat_level=1 then 1 else 0 end) as char) as threat_1,
		  cast(sum(case when threat_level=2 then 1 else 0 end) as char) as threat_2,
		  cast(sum(case when threat_level=3 then 1 else 0 end) as char) as threat_3,
		  cast(sum(case when threat_level=4 then 1 else 0 end) as char) as threat_4,
		  cast(sum(case when threat_level=5 then 1 else 0 end) as char) as threat_5,
		  cast(sum(case when threat_level=6 then 1 else 0 end) as char) as threat_6,
		  cast(sum(case when threat_level=7 then 1 else 0 end) as char) as threat_7,
		  cast(sum(case when threat_level=8 then 1 else 0 end) as char) as threat_8,
		  cast(sum(case when threat_level=9 then 1 else 0 end) as char) as threat_9,
          cast(min(x) as char) as x,
          cast(min(y) as char) as y,
          cast(min(z) as char) as z
        from nhssreports
        where 1 = 1
        {clause}
        group by systemName 
        {having}
        order by 2 desc
        limit %s,%s
        """
        cursor.execute(sql, (params))
        r = cursor.fetchall()
        cursor.close()

        for row in r:
            nearest = getNearest(row)
            entry = {
                "systemName": row.get("systemName"),
                "first_seen": row.get("first_seen"),
                "last_seen": row.get("last_seen"),
                "threat_0": row.get("threat_0"),
                "threat_1": row.get("threat_1"),
                "threat_2": row.get("threat_2"),
                "threat_3": row.get("threat_3"),
                "threat_4": row.get("threat_4"),
                "threat_5": row.get("threat_5"),
                "threat_6": row.get("threat_6"),
                "threat_7": row.get("threat_7"),
                "threat_8": row.get("threat_8"),
                "threat_9": row.get("threat_9"),
                "x": str(row.get("x")),
                "y": str(row.get("y")),
                "z": str(row.get("z")),
                "bubble": nearest.get("name"),
                "bubble_distance": nearest.get("distance")
            }
            data.append(entry)

    return jsonify(data)


def get_nhss_reports(request):
    setup_sql_conn()

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)
    if request.args.get("_start"):
        offset = request.args.get("_start")
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    params = []
    clause = ""
    threat = request.args.get("threat")
    system = request.args.get("system")

    if threat:
        params.append(threat)
        clause = "and threat_level = %s"

    if system:
        params.append(system)
        clause = f"{clause} and systemName = %s"

    params.append(int(offset))
    params.append(int(limit))

    data = []

    with get_cursor() as cursor:
        sql = f"""
        select
          cast(created_at as char) as created_at, 
		  cast(found_at as char) as found_at,          
		  cmdrName as cmdr,
          systemName as system,
          cast(x as char) as x,
          cast(y as char) as y,
          cast(z as char) as z,
 		  threat_level
        from nhssreports
        where 1 = 1
        {clause}
        order by 2 desc
        limit %s,%s
        """
        cursor.execute(sql, (params))
        r = cursor.fetchall()
        cursor.close()

        for row in r:
            nearest = getNearest(row)
            entry = {
                "created_at": row.get("created_at"),
                "found_at": row.get("found_at"),
                "cmdr": row.get("cmdr"),
                "system": row.get("system"),
                "x": str(row.get("x")),
                "y": str(row.get("y")),
                "z": str(row.get("z")),
                "threat_level": row.get("threat_level"),
                "bubble": nearest.get("name"),
                "bubble_distance": nearest.get("distance")
            }
            data.append(entry)

    return jsonify(data)


def get_hyperdiction_detections(request):
    setup_sql_conn()

    data = []

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)
    if request.args.get("_start"):
        offset = request.args.get("_start")
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    params = []
    clause = ""

    system = request.args.get("system")

    if system:
        params.append(system)
        clause = f"{clause} and system = %s"

    params.append(int(offset))
    params.append(int(limit))

    with get_cursor() as cursor:
        sql = f"""
        select * from hd_detected 
        where dx is not null 
        and dy is not null 
        and dz is not null
        {clause}
        order by timestamp desc
        limit %s,%s
        """
        cursor.execute(sql, (params))
        r = cursor.fetchall()
        cursor.close()

        for row in r:
            entry = {
                "cmdr": row.get("cmdr"),
                "timestamp": str(row.get("timestamp")),
                "hostile": row.get("hostile"),
                "start": {
                    "system": row.get("system"),
                    "x": str(row.get("x")),
                    "y": str(row.get("y")),
                    "z": str(row.get("z")),
                    "nearest": getNearest(row)
                },
                "destination": {
                    "system": row.get("destination"),
                    "x": str(row.get("dx")),
                    "y": str(row.get("dy")),
                    "z": str(row.get("dz")),
                    "nearest": getNearest({
                        "x": row.get("dx"),
                        "y": row.get("dy"),
                        "z": row.get("dz"),
                    })
                }
            }
            data.append(entry)

    return jsonify(data)
