
import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
import requests
import json
from flask import jsonify


def codex_reports(cmdr, system, odyssey):
    setup_sql_conn()

    if odyssey == 'N':
        odycheck = 'N'
    else:
        odycheck = 'Y'

    print(f"odycheck {odycheck}")

    sql = """
        SELECT 
            case when body LIKE '%% Ring' then SUBSTR(body,1,LENGTH(body)-5) ELSE body end as body,
            coords->'$.latitude' AS latitude,
            coords->'$.longitude' AS longitude, 
            entryid,
            english_name,
            hud_category,
            index_id,
            scanned
            FROM (
                SELECT  
                    max(case when cmdrname = %s then 'true' ELSE 'false' END) AS scanned,
                    replace(body,concat(system,' '),'') as body,
                    cast(
                        case 
                            when odyssey = 'N' and %s = 'Y' then null
                            when odyssey = 'Y' and %s = 'N' then null
                            when odyssey is null then null
                            when latitude is null or longitude is null then null 
                            else CONCAT('{"latitude": ',cast(latitude as CHAR),', "longitude":', cast(longitude as CHAR),'}') 
                    end AS JSON) as coords  ,
                    cr.entryid,
                    english_name,
                    hud_category,
                    index_id
                    FROM codexreport cr 
                    JOIN codex_name_ref cnr ON cnr.entryid = cr.entryid
                    WHERE system = %s
                    and hud_category != 'None'
                    and (
                        (   
                            %s = 'Y'
                            or
                            (odyssey = 'N' or odyssey is NULL) and %s = 'N'
                        )
                    )
                    GROUP BY 
                    cast(
                        case 
                            when odyssey = 'N' and %s = 'Y' then null
                            when odyssey = 'Y' and %s = 'N' then null
                            when odyssey is null then null
                            when latitude is null or longitude is null then null 
                            else CONCAT('{"latitude": ',cast(latitude as CHAR),', "longitude":', cast(longitude as CHAR),'}') 
                    end AS JSON),
                    replace(body,concat(system,' '),''),
                    cr.entryid,
                    english_name,
                    hud_category,
                    index_id
        ) data
    """
    with get_cursor() as cursor:

        cursor.execute(sql, (cmdr, odycheck, odycheck, system,
                       odycheck, odycheck, odycheck, odycheck))
        cr = cursor.fetchall()

    exclude={}
    for entry in cr:
        
        if entry.get("body"):
            exclude[entry.get("entryid")]=True

    result=[]
    i = 0
    while i < len(cr):
        entry=cr[i]
        if entry.get("body") or not exclude.get(entry.get("entryid")):
            print(entry.get("body"))
            result.append(entry)
        i+=1

    return result


def saa_signals(system, odyssey):
    setup_sql_conn()
    if odyssey == 'Y':
        count = "species"
        alt = "sites"
    else:
        count = "sites"
        alt = "species"
    sql = f"""
        select 
            distinct 
            case when replace(body,concat(system,' '),'') LIKE '%% Ring' then SUBSTR(replace(body,concat(system,' '),''),1,LENGTH(replace(body,concat(system,' '),''))-5) ELSE replace(body,concat(system,' '),'') end as body,
            case 
                when type not like '%%SAA%%' then 'Ring' 
                when type like '%%Biological%%' then 'Biology' 
                when type like '%%Geological%%' then 'Geology' 
                when type like '%%Guardian%%' then 'Guardian' 
                when type like '%%Thargoid%%' then 'Thargoid' 
                when type like '%%Human%%' then 'Human' 
                else 'Unknown' 
            end as hud_category,
            case 
                when type not like '%%SAA%%' then type
                when type like '%%Biological%%' then 'Biology' 
                when type like '%%Geological%%' then 'Geology' 
                when type like '%%Guardian%%' then 'Guardian' 
                when type like '%%Thargoid%%' then 'Thargoid' 
                when type like '%%Human%%' then 'Human' 
                else 'Unknown' 
            end as english_name,
            ifnull({count},{alt}) count 
        from SAASignals where system = %s
        and ifnull({count},{alt}) is not null
    """
    with get_cursor() as cursor:

        cursor.execute(sql, (system))
        cr = cursor.fetchall()

    return cr


def fss_events(system, odyssey):
    setup_sql_conn()
    sql = """
        SELECT 
            signalname,
            signalnamelocalised,
            raw_json->"$.IsStation" AS isStation 
            FROM fss_events WHERE system = %s
            and raw_json like '%%Fixed_Event_Life_%%'
    """
    with get_cursor() as cursor:

        cursor.execute(sql, (system))
        cr = cursor.fetchall()

    return cr


def cmdr_poi(cmdr, system, odyssey):
    setup_sql_conn()
    sql = """
        SELECT 
                case when body LIKE '%% Ring' then SUBSTR(body,1,LENGTH(body)-5) ELSE body end as body,
                coords->'$.latitude' AS latitude,
                coords->'$.longitude' AS longitude, 
                comment description,
                category        
        from (
            select replace(body,concat(system,' '),'') as body,
            cast(max(
                case 
                when latitude is null or longitude is null then null 
                else CONCAT('{"latitude": ',cast(latitude as CHAR),', "longitude":', cast(longitude as CHAR),'}') 
            end) AS JSON) as coords,s.comment,s.category
            from status_reports s  where 
            cmdr = %s
            and system = %s
            group by category,comment 
        ) data
    """
    with get_cursor() as cursor:

        cursor.execute(sql, (cmdr, system))
        cr = cursor.fetchall()

    return cr


def getSystemPoi(request):

    cmdr = request.args.get("cmdr")
    system = request.args.get("system")
    odyssey = request.args.get("odyssey")
    print(f"odyssey {odyssey}")
    result = {
        "cmdrName": cmdr,
        "system": system,
        "odyssey": odyssey
    }

    codex = codex_reports(cmdr, system, odyssey)
    saa = saa_signals(system, odyssey)
    cpoi = cmdr_poi(cmdr, system, odyssey)
    fss = fss_events(system, odyssey)

    if codex:
        result["codex"] = codex
    if saa:
        result["SAAsignals"] = saa
    if cpoi:
        result["cmdr"] = cpoi
    if fss:
        result["FSSsignals"] = fss

    return result
