import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
import requests
import json
from flask import jsonify
from collections import defaultdict
import math


def uai_waypoints(uia=1):
    try:
        links = [
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=1795350434&single=true&output=tsv",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=1985235220&single=true&output=tsv",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=1157712983&single=true&output=tsv",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=1884103472&single=true&output=tsv",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=1784951467&single=true&output=tsv",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=844257496&single=true&output=tsv",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=280976695&single=true&output=tsv",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=1588175655&single=true&output=tsv",
            "https://docs.google.com/spreadsheets/d/e/2PACX-1vSWfL7b8-lV8uFCA2iUrKDI3Q9dSSraj8gbrt_ng0WIh1_qrS_GXZycmYdoaO7a3c_OON0t8LlYSO3f/pub?gid=84085245&single=true&output=tsv",
        ]

        if uia > len(links):
            return jsonify([])

        url = links[uia - 1]

        retval = []
        r = requests.get(url)
        lines = r.text.split("\r\n")
        for line in lines:
            l = line.split("\t")
            retval.append(l)

        return jsonify(retval)
    except:
        return jsonify([])


def organic_scans(cmdr, system, odyssey):
    if odyssey == "N" or odyssey == False:
        return []

    setup_sql_conn()
    sql = """
    SELECT 
        distinct 
        case when body LIKE '%% Ring' then SUBSTR(body,1,LENGTH(body)-5) ELSE replace(body,concat(os.system,' '),'') end as body,
        latitude,longitude,
        entryid,english_name,hud_category,null as index_id,
        max(case when cmdr = %s then 'true' ELSE 'false' END) AS scanned
        from organic_scans os
        left join codex_name_ref cnr on cnr.name = case 
            when variant not like concat(replace(species,'_Name;',''),'%%') then
                concat(
	                replace(species,'_Name;',''),
	                substr(variant,length(replace(species,'_Name;',''))+1))
            else variant 
        end
        where os.system = %s
        and variant is not null
        group by 
        case when body LIKE '%% Ring' then SUBSTR(body,1,LENGTH(body)-5) ELSE body end,
        latitude,longitude,
        entryid,english_name,hud_category
    """

    with get_cursor() as cursor:
        cursor.execute(sql, (cmdr, system))
        cr = cursor.fetchall()

    exclude = {}
    for entry in cr:
        if entry.get("body"):
            exclude[entry.get("entryid")] = True

    result = []
    i = 0
    while i < len(cr):
        entry = cr[i]
        if entry.get("body") or not exclude.get(entry.get("entryid")):
            # print(entry.get("body"))
            result.append(entry)
        i += 1

    return result


def codex_reports(cmdr, system, odyssey):
    setup_sql_conn()

    if odyssey == "N":
        odycheck = "N"
    else:
        odycheck = "Y"

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
                    replace(body,concat(cr.system,' '),'') as body,
                    cast(
                        case 
                            when odyssey = 'N' and %s = 'Y' then null
                            when odyssey = 'Y' and %s = 'N' then null
                            when odyssey is null then null
                            when latitude is null or longitude is null then null 
                            when hud_category in ('Thargoid','Guardian') then null
                            else CONCAT('{"latitude": ',cast(latitude as CHAR),', "longitude":', cast(longitude as CHAR),'}') 
                    end AS JSON) as coords  ,
                    cr.entryid,
                    english_name,
                    hud_category,
                    index_id
                    FROM codexreport cr 
                    JOIN codex_name_ref cnr ON cnr.entryid = cr.entryid
                    WHERE cr.system = %s and cr.entryid in (select cs.entryid from codex_systems cs where cs.system = cr.system)
                    and hud_category != 'None'
                    and (
                        (   
                            %s = 'Y'
                            or
                            ((odyssey = 'N' or odyssey is NULL) and %s = 'N')
                        )
                    )
                    GROUP BY 
                    cast(
                        case 
                            when odyssey = 'N' and %s = 'Y' then null
                            when odyssey = 'Y' and %s = 'N' then null
                            when odyssey is null then null
                            when latitude is null or longitude is null then null 
                            when hud_category in ('Thargoid','Guardian') then null
                            else CONCAT('{"latitude": ',cast(latitude as CHAR),', "longitude":', cast(longitude as CHAR),'}') 
                    end AS JSON),
                    replace(body,concat(cr.system,' '),''),
                    cr.entryid,
                    english_name,
                    hud_category,
                    index_id
        ) data where entryid in (select entryid from  codex_name_ref where %s = 'Y' or  (%s = 'N' and platform != 'odyssey'))
    """
    with get_cursor() as cursor:
        cursor.execute(
            sql,
            (
                cmdr,
                odycheck,
                odycheck,
                system,
                odycheck,
                odycheck,
                odycheck,
                odycheck,
                odycheck,
                odycheck,
            ),
        )
        cr = cursor.fetchall()

    exclude = {}
    for entry in cr:
        if entry.get("body"):
            exclude[entry.get("entryid")] = True

    result = []
    i = 0
    while i < len(cr):
        entry = cr[i]
        if entry.get("body") or not exclude.get(entry.get("entryid")):
            # print(entry.get("body"))
            result.append(entry)
        i += 1

    return result


def saa_signals(system, odyssey):
    setup_sql_conn()
    if odyssey == "Y":
        count = "species"
        alt = "sites"
    else:
        count = "sites"
        alt = "species"
    sql = f"""
        select 
            distinct 
            case when replace(body,concat(saa.system,' '),'') LIKE '%% Ring' then SUBSTR(replace(body,concat(saa.system,' '),''),1,LENGTH(replace(body,concat(saa.system,' '),''))-5) ELSE replace(body,concat(saa.system,' '),'') end as body,
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
        from SAASignals saa where saa.system = %s
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
            JSON_EXTRACT(raw_json, '$.IsStation') AS isStation 
            FROM fss_events fss WHERE fss.system = %s
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
            select replace(body,concat(s.system,' '),'') as body,
            cast(max(
                case 
                when latitude is null or longitude is null then null 
                else CONCAT('{"latitude": ',cast(latitude as CHAR),', "longitude":', cast(longitude as CHAR),'}') 
            end) AS JSON) as coords,s.comment,s.category
            from status_reports s  where 
            cmdr = %s
            and s.system = %s
            group by category,comment 
        ) data
    """
    with get_cursor() as cursor:
        cursor.execute(sql, (cmdr, system))
        cr = cursor.fetchall()

    return cr


def calc_distance(lat_a, lon_a, lat_b, lon_b, radius):
    if radius is None:
        return 0.0

    lat_a = lat_a * math.pi / 180.0
    lon_a = lon_a * math.pi / 180.0
    lat_b = lat_b * math.pi / 180.0
    lon_b = lon_b * math.pi / 180.0

    if lat_a != lat_b or lon_b != lon_a:
        d_lambda = lon_b - lon_a
        S_ab = math.acos(
            math.sin(lat_a) * math.sin(lat_b)
            + math.cos(lat_a) * math.cos(lat_b) * math.cos(d_lambda)
        )
        return S_ab * radius
    else:
        return 0.0


def limitPois(data):
    new_data = []

    def calculate_score(poi):
        max_distance = 0
        if poi is None:
            # print("poi undefined")
            return 0
        if poi.get("latitude") is None or poi.get("longitude") is None:
            # print(f"poi coords undefined {poi}")
            return 0

        # print(f"new_data {new_data}")

        for other in new_data:
            if (
                other
                and other.get("latitude") is not None
                and other.get("longitude") is not None
            ):
                distance = calc_distance(
                    float(poi.get("latitude")),
                    float(poi.get("longitude")),
                    float(other.get("latitude")),
                    float(other.get("longitude")),
                    10000,
                )
                max_distance = max(max_distance, distance)
            # else:
            #    print(f"What? {other}")

        return max_distance

    # store one null location
    null_loc = None

    # count the number of nulls
    for item in data:
        c = 1
        if item.get("latitude") is None or item.get("longitude") is None:
            null_loc = item
        else:
            c += 1
            if item:
                new_data.append(item)
    # we can add the null_loc back in
    if c < 5 and null_loc:
        new_data.append(null_loc)
    # if its less then 6 then we can just return it.
    if len(new_data) < 6:
        return new_data

    limited_data = sorted(new_data, key=calculate_score, reverse=True)[:5]

    return limited_data


def samplePoi(codex, scans):
    grouped_data = defaultdict(list)
    retval = []

    for item in codex + scans:
        body = item["body"]
        entryid = item["entryid"]
        grouped_data[(body, entryid)].append(item)

    grouped_data = dict(grouped_data)
    # print(grouped_data)
    # lets quit here

    for key, value in grouped_data.items():
        # print(value)
        retval += limitPois(value)

    return retval


def get_settlement(system):

    if system is None:
        return []
    if system.isdigit():
        col = "id64"
    else:
        col = "systemName"

    setup_sql_conn()
    sql = f"""
        select bodyid,name,name_localised,cast(lat as char) lat,cast(lon as char) lon,market_id from settlements 
        where {col} = %s and is_beta != 'Y';
    """

    with get_cursor() as cursor:
        cursor.execute(sql, (system))
        cr = cursor.fetchall()

    return cr


def getSystemPoi(request):
    cmdr = request.args.get("cmdr")
    system = request.args.get("system")
    odyssey = request.args.get("odyssey")
    result = {"cmdrName": cmdr, "system": system, "odyssey": odyssey}

    codex = codex_reports(cmdr, system, odyssey)
    saa = saa_signals(system, odyssey)
    cpoi = cmdr_poi(cmdr, system, odyssey)
    fss = fss_events(system, odyssey)
    scans = organic_scans(cmdr, system, odyssey)

    if codex:
        result["codex"] = samplePoi(codex, scans)
    if saa:
        result["SAAsignals"] = saa
    if cpoi:
        result["cmdr"] = cpoi
    if fss:
        result["FSSsignals"] = fss
    # if scans:
    #    result["ScanOrganic"] = scans

    return result


def get_status(request):
    setup_sql_conn()

    cmdr = request.args.get("cmdr")
    if cmdr is None:
        cmdr = ""

    with get_cursor() as cursor:
        sqltext = """
            SELECT 
            CAST(created_at as CHAR) as created_at,
                system,
                CAST(x AS CHAR) x,
                CAST(y as CHAR) y,
                CAST(z AS  CHAR) z,
                body,
                CAST(latitude  as CHAR) latitude,
                CAST(longitude as CHAR) longitude,
                raw_status,
                heading,
                altitude,
                category,
                index_id,
                comment
            FROM  status_reports 
            where cmdr = %s
    """
        cursor.execute(sqltext, (cmdr))
        r = cursor.fetchall()
        # num_rows_affected = cursor.rowcount
        cursor.close()

    return jsonify(r)


def get_compres(request):
    systems = tuple(request.args.get("systems").split(","))

    placeholders = []

    for _ in systems:
        placeholders.append("%s")

    placeholder = ",".join(placeholders)

    print(f"get_compres how many systems? {len(systems)}")

    sql = """
        select distinct  
        fss.system,
        case 
            when signalname = '$MULTIPLAYER_SCENARIO78_TITLE;' then 'Resource Extraction Site [High]' 
            when signalname = '$MULTIPLAYER_SCENARIO79_TITLE;' then 'Resource Extraction Site [Hazardous]' 
            when signalname = '$MULTIPLAYER_SCENARIO80_TITLE;' then 'Compromised Nav Beacon' 
        end as interesting
        from fss_events fss where signalname in (
            '$MULTIPLAYER_SCENARIO78_TITLE;',
            '$MULTIPLAYER_SCENARIO79_TITLE;',
            '$MULTIPLAYER_SCENARIO80_TITLE;'
        ) and fss.system in (
        {}
        )
    """.format(
        placeholder
    )

    setup_sql_conn()
    with get_cursor() as cursor:
        cursor.execute(sql, (systems))
        cr = cursor.fetchall()

    return jsonify(cr)
