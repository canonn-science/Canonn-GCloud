import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
import requests
import json
from flask import request, jsonify


def getCoordinates(system):
    try:
        url = 'https://www.edsm.net/api-v1/system?systemName={}&showCoordinates=1'
        r = requests.get(url.format(system))
        s = r.json()
        c = s.get("coords")
        return [float(c.get("x")), float(c.get("y")), float(c.get("z"))]
    except:
        raise Exception("Unable to get system from EDSM")


def challenge_next(request):
    system = request.args.get("system")
    cmdr = request.args.get("cmdr")

    s = getCoordinates(system)
    x = s[0]
    y = s[1]
    z = s[2]

    sql = """
        select system,english_name,cast(round(sqrt(pow(x-%s,2)+pow(y-%s,2)+pow(z-%s,2)),2) as char) as distance from (
        select entryid,name_localised,system,cast(x as char) x,cast(y as char) y,cast(z as char) z from codexreport where cmdrName != 'EDSM User' and  entryid in (
        select entryid from codex_name_ref cnr where hud_category not in ('None') and not exists
        (select 1 from codexreport cr where cmdrname = %s and cnr.entryid = cr.entryid)
        ) order by pow(x-%s,2)+pow(y-%s,2)+pow(z-%s,2) asc limit 1
        ) challenge
        join codex_name_ref cnr on cnr.entryid = challenge.entryid
    """

    res = {}
    res["sql"] = sql

    try:
        result = []
        setup_sql_conn()

        # Remember to close SQL resources declared while running this function.
        # Keep any declared in global scope (e.g. mysql_conn) for later reuse.
        with get_cursor() as cursor:
            #startCoords=(sx, sy, sz)
            #endCoords=(ex, ey, ez)
            # lineDistance=(startCoords+endCoords)
            # limits=(offset,limit)

            cursor.execute(sql, (x, y, z, cmdr, x, y, z))
            # cursor.execute(sql,(sx,sy,sz,ex,ey,ez,sx,sy,sz,ex,ey,ez,jumpRange))
            cr = cursor.fetchall()
    except Exception as e:
        cr = [{"error": str(e)}]
    return cr[0]


def challenge_status(request):
    cmdr = request.args.get("cmdr", None)
    setup_sql_conn()

    with get_cursor() as cursor:
        sql = """
            select 
            cnr.entryid as codex,
            cmdr_stats.entryid as cmdr ,
            sub_class,
				hud_category,
				cmdr_stats.english_name as type_found,
				cnr.english_name as type_available 
            from codex_name_ref cnr
            left join (select distinct entryid,english_name from v_codex_report where cmdrName = %s) cmdr_stats on cnr.entryid = cmdr_stats.entryid
            order by hud_category,cnr.entryid
        """
        cursor.execute(sql, (cmdr))
        r = cursor.fetchall()
        cursor.close()

    def regroup(cr):
        data = {}
        for val in cr:
            h = val.get("hud_category")
            s = val.get("sub_class")
            if not data.get(s):
                data[s] = {"hud_category": h, "types_found": [],
                           "types_available": [], "codex_count": 0, "cmdr_count": 0}
            if val.get("type_found"):
                data[s]["types_found"].append(val.get("type_found"))
                data[s]["cmdr_count"] = len(data[s]["types_found"])
            if val.get("type_available"):
                data[s]["types_available"].append(val.get("type_available"))
                data[s]["codex_count"] = len(data[s]["types_available"])

        retval = []
        for r in data.keys():
            retval.append({
                "codex": str(data.get(r).get("codex_count")),
                "cmdr": str(data.get(r).get("cmdr_count")),
                "sub_class": r,
                "hud_category": data.get(r).get("hud_category"),
                "types_found": data.get(r).get("types_found"),
                "types_available": data.get(r).get("types_available")
            })
        return retval

    def enrich_data(cr):
        retval = {"challenge": {}}

        codex_count = 0
        cmdr_count = 0

        for val in cr:
            hud_category = val.get("hud_category")

            if val.get("types_found"):
                types_found = val.get("types_found")
            else:
                types_found = []

            if val.get("types_available"):
                types_available = val.get("types_available")
            else:
                types_available = []

            retval[val.get("sub_class")] = {
                "hud_category": val.get("hud_category"),
                "visited": int(val.get("cmdr")),
                "available": int(val.get("codex")),
                "types_found": types_found,
                "types_available": types_available,
                "percentage": int((int(val.get("cmdr"))/int(val.get("codex"))) * 1000)/10
            }
            if val.get("hud_category") in ("Cloud", "Anomaly", "Biology"):
                codex_count += int(val.get("codex"))
                cmdr_count += int(val.get("cmdr"))

            if retval.get(hud_category) and hud_category not in ("Guardian", "Thargoid"):
                retval[hud_category]["codex_count"] += int(val.get("codex"))
                retval[hud_category]["cmdr_count"] += int(val.get("cmdr"))
                retval[hud_category]["percentage"] = int((int(retval[hud_category].get(
                    "cmdr_count"))/int(retval[hud_category].get("codex_count"))) * 1000)/10

            if not retval.get(hud_category) and hud_category not in ("Guardian", "Thargoid"):
                retval[hud_category] = {"codex_count": int(
                    val.get("codex")), "cmdr_count": int(val.get("cmdr"))}
                retval[hud_category]["percentage"] = int((int(retval[hud_category].get(
                    "cmdr_count"))/int(retval[hud_category].get("codex_count"))) * 1000)/10

        # caclulate the canonn challenge percent

        pct = int((cmdr_count/codex_count) * 1000)/10
        retval["challenge"] = {"cmdr": cmdr_count,
                               "codex": codex_count, "pct": pct}

        return retval

    rg = regroup(r)
    res = {}
    res = enrich_data(rg)

    return res


def speed_challenge(request):
    where = ""
    params = ()
    if request.args.get("cmdr"):
        where = "and cmdr = %s"
        params = (request.args.get("cmdr"))
    limit = 10
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    setup_sql_conn()
    with get_cursor() as cursor:
        sql = f"""
    SELECT 
	cmdr,
	started,
	ended,
	TIMESTAMPDIFF(SECOND,started,ifnull(ended,now())) seconds,
	a as osseus,
	b as aleoid,
	c as cactoid,
	d as stratum,	
	e as bacterium,
	f as fungoid,
	g as tussock,
	h as concha,
	i as shrub
 from (
select cmdr,
max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null end) as started,
max(case when scantype = 'Analyse' then greatest(a,b,c,d,e,f,g,h,i) else null end) as ended,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then a else null END),NOW())) AS a,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then b else null END),NOW())) AS b,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then c else null END),NOW())) AS c,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then d else null END),NOW())) AS d,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then e else null END),NOW())) AS e,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then f else null END),NOW())) AS f,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then g else null END),NOW())) AS g,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then h else null END),NOW())) AS h,
TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then least(a,b,c,d,e,f,g,h,i) else null END),
ifnull(max(case when scantype = 'Analyse' then i else null END),NOW())) AS i
 from (
select cmdr,scantype,
max(case when species = '$Codex_Ent_Osseus_01_Name;' then reported_at else null end) as a,
max(case when species = '$Codex_Ent_Aleoids_02_Name;' then reported_at else null end) as b,
max(case when species = '$Codex_Ent_Cactoid_01_Name;' then reported_at else null end) as c,
max(case when species = '$Codex_Ent_Stratum_01_Name;' then reported_at else null end) as d,
max(case when species = '$Codex_Ent_Bacterial_01_Name;' then reported_at else null end) as e,
max(case when species = '$Codex_Ent_Fungoids_02_Name;' then reported_at else null end) as f,
max(case when species = '$Codex_Ent_Tussocks_11_Name;' then reported_at else null end) as g,
max(case when species = '$Codex_Ent_Conchas_01_Name;' then reported_at else null end) as h,
max(case when species = '$Codex_Ent_Shrubs_02_Name;' then reported_at else null end) as i
from organic_scans where system = 'Tucanae Sector AF-A d71' and body = 'Tucanae Sector AF-A d71 4 e' {where}
group by cmdr,scantype
) data
group by cmdr) data2
WHERE started IS NOT NULL
order by case when ended is null then 999999 else 0 end + seconds asc
limit {limit}
        """
        cursor.execute(sql, params)
        r = cursor.fetchall()
        cursor.close()

    return jsonify(r)


def fastest_scans(request):
    where = ""
    params = ()
    if request.args.get("cmdr"):
        where = "where cmdr = %s"
        params = (request.args.get("cmdr"))

    setup_sql_conn()
    with get_cursor() as cursor:
        sql = f"""
        select distinct data2.cmdr,data2.system,data2.body,ifnull(cnr.english_name,data2.species_localised) as species,data2.diff as seconds from (
        select cmdr,system,body,species,species_localised,started,ended,TIMESTAMPDIFF(SECOND,started,ended) as diff 
        from (
        select cmdr,system,body,species,species_localised,
        max(case when scantype = 'Log' then reported_at else null end) as started,
        min(case when scantype = 'Analyse' then reported_at else null end) as ended
        from organic_scans {where}
        group by cmdr,system,body,species,species_localised
        having min(case when scantype = 'Analyse' then reported_at else null end) is not null
        ) data1
        where started is not null and ended is not null and TIMESTAMPDIFF(SECOND,started,ended) > 0
        order by TIMESTAMPDIFF(SECOND,started,ended) asc limit 20
        ) data2 
        left join codexreport cr on cr.system = data2.system and cr.body = data2.body and cr.name like replace(data2.species,'_Name;','\_%%')
        left join codex_name_ref cnr on cnr.entryid = cr.entryid 
        order by diff asc
        """
        cursor.execute(sql, params)
        r = cursor.fetchall()
        cursor.close()

    return jsonify(r)


def nearest_codex(request):

    if request.args.get("system"):
        x, y, z = getCoordinates(request.args.get("system"))
    else:
        x = request.args.get("x", 0.0)
        y = request.args.get("y", 0.0)
        z = request.args.get("z", 0.0)

    if request.args.get("name"):
        where = "where english_name like concat('%%',%s,'%%')"
        params = (x, y, z, request.args.get("name"), x, y, z)
    else:
        where = "1=1"
        params = (x, y, z, x, y, z)

    if request.args.get("odyssey"):
        if request.args.get("odyssey") == 'Y':
            where = f"{where} and  odyssey='Y'"
        if request.args.get("odyssey") == 'N':
            where = f"{where} and  odyssey='N'"

    setup_sql_conn()
    with get_cursor() as cursor:
        sql = f"""
            select english_name,entryid,system,cast(round(sqrt(pow(x-%s,2)+pow(y-%s,2)+pow(z-%s,2)),2) as char) as distance
            from (
            select distinct english_name,cs.entryid,system,x,y,z
            from codexreport cs 
            join codex_name_ref cnr on cnr.entryid = cs.entryid
            {where}
            order by (pow(x-%s,2)+pow(y-%s,2)+pow(z-%s,2)) asc 
            limit 20) data
        """
        cursor.execute(sql, params)
        r = cursor.fetchall()
        cursor.close()

    return {"nearest": r}
