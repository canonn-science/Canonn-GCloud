import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
#from EDRegionMap.RegionMap import findRegion
import requests
import json
from flask import jsonify
import urllib.parse


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

    with get_cursor() as cursor:
        sql = f"""
          select systemName,
 		  cast(min(found_at) as char) as first_seen, 
		  cast(max(found_at) as char) as last_seen, 
		  sum(case when threat_level = 0 then 1 else 0 end) as threat_0,
		  sum(case when threat_level = 1 then 1 else 0 end) as threat_1,
		  sum(case when threat_level = 2 then 1 else 0 end) as threat_2,
		  sum(case when threat_level = 3 then 1 else 0 end) as threat_3,		  		  
		  sum(case when threat_level = 4 then 1 else 0 end) as threat_4,
		  sum(case when threat_level = 5 then 1 else 0 end) as threat_5,
		  sum(case when threat_level = 6 then 1 else 0 end) as threat_6,
		  sum(case when threat_level = 7 then 1 else 0 end) as threat_7,		  		  
		  sum(case when threat_level = 8 then 1 else 0 end) as threat_8,
		  sum(case when threat_level = 9 then 1 else 0 end) as threat_9,
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

    return jsonify(r)


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

    return jsonify(r)
