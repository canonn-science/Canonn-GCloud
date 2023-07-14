import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
import requests
import json
from flask import request, jsonify
import flask
from math import sqrt, trunc


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
    px = request.args.get("x")
    py = request.args.get("y")
    pz = request.args.get("z")
    x, y, z = None, None, None
    limit=""
    if request.args.get("horizons") in ('Y','y'):
        limit=" platform = 'legacy' and "

    if system:
        s = getCoordinates(system)


    if system and s:
        x = s[0]
        y = s[1]
        z = s[2]
    if px is not None and py is not None and pz is not None:
        x = float(px)
        y = float(py)
        z = float(pz)

    if x is None:
        return {"error": "cant find source system"}

    entries=[]
    entrysql=f"""
    select entryid from codex_name_ref cnr where {limit} hud_category not in ('None') and not exists
        (select 1 from codexreport cr where cmdrname = %s and cnr.entryid = cr.entryid)
    """
    setup_sql_conn()
    with get_cursor() as cursor:
        cursor.execute(entrysql, cmdr)
        rows = cursor.fetchall()
        entries = [row['entryid'] for row in rows]
    placeholders = ', '.join(['%s'] * len(entries))
    

    sql = f"""
        select system,cnr.english_name,cast(round(sqrt(pow(x-%s,2)+pow(y-%s,2)+pow(z-%s,2)),2) as char) as distance from (
        select * from (
            select * from codex_systems 
            where zorder(%s,%s,%s) > z_order
            and entryid in ({placeholders})
            order by z_order desc
            limit 100) data
        union
        select * from (
            select * from codex_systems 
            where zorder(%s,%s,%s) <= z_order
            and entryid in ( {placeholders})
            order by z_order asc
            limit 100
        ) data2
    ) all_data
    join codex_name_ref cnr on cnr.entryid = all_data.entryid
    order by pow(x-%s,2)+pow(y-%s,2)+pow(z-%s,2) asc limit 1
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
            params=[x,y,z]
            params.extend([x,y,z])
            params.extend(entries)
            params.extend([x,y,z])
            params.extend(entries)
            params.extend([x,y,z])
            cursor.execute(sql, tuple(params))
            # cursor.execute(sql,(sx,sy,sz,ex,ey,ez,sx,sy,sz,ex,ey,ez,jumpRange))
            cr = cursor.fetchall()
    except Exception as e:
        cr = [{"error": str(e)}]
    return cr[0]


def challenge_status(request):
    cmdr = request.args.get("cmdr", None)
    platform = request.args.get("platform", None)
    setup_sql_conn()

    where1 = " "
    where2 = " "
    if platform == "legacy":
        where1 = "where platform='legacy'"
        where2 = "and platform='legacy'"
    if platform == "odyssey":
        where1 = "where platform='odyssey'"
        where2 = "and platform='odyssey'"

    with get_cursor() as cursor:
        sql = f"""
            select 
            cnr.entryid as codex,
            cmdr_stats.entryid as cmdr ,
            sub_class,
				case when sub_class = 'Thargoid' and hud_category = 'None' then 'Thargoid' else hud_category end as hud_category,
				cmdr_stats.english_name as type_found,
				cnr.english_name as type_available 
            from codex_name_ref cnr
            left join (
                        select distinct entryid,english_name 
                        from codex_name_ref cn 
                        where exists (
                            select 1 from codexreport cr where cmdrname = %s and cr.entryid = cn.entryid 
                        ) 
                        {where2}
				) cmdr_stats on cnr.entryid = cmdr_stats.entryid
            {where1}
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
                           "types_available": [], "types_missing": [], "codex_count": 0, "cmdr_count": 0}
            if val.get("type_found"):
                data[s]["types_found"].append(val.get("type_found"))
                data[s]["cmdr_count"] = len(data[s]["types_found"])
            if val.get("type_available"):
                data[s]["types_available"].append(val.get("type_available"))
                data[s]["codex_count"] = len(data[s]["types_available"])
            if val.get("type_available") and not val.get("type_found"):
                data[s]["types_missing"].append(val.get("type_available"))

        retval = []
        for r in data.keys():
            retval.append({
                "codex": str(data.get(r).get("codex_count")),
                "cmdr": str(data.get(r).get("cmdr_count")),
                "sub_class": r,
                "hud_category": data.get(r).get("hud_category"),
                "types_found": data.get(r).get("types_found"),
                "types_available": data.get(r).get("types_available"),
                "types_missing": data.get(r).get("types_missing")
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

            if val.get("types_missing"):
                types_missing = val.get("types_missing")
            else:
                types_missing = []

            retval[val.get("sub_class")] = {
                "hud_category": val.get("hud_category"),
                "visited": int(val.get("cmdr")),
                "available": int(val.get("codex")),
                "types_found": types_found,
                "types_available": types_available,
                "types_missing": types_missing,
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


def challenge_svg(request):
    # maybe I should tailor a query but I'll just reuse what we have got.
    data = challenge_status(request)

    titles = {}
    c = 0
    for group in data.keys():
        found = data.get(group).get("types_found")
        #print(f"group {found}")
        if data.get(group).get("types_available"):
            for name in data.get(group).get("types_found"):
                c += 1
                titles["I"+str(c)] = {"name": name, "class": "found"}
                # print(titles["I"+str(c)])
            for name in data.get(group).get("types_missing"):
                c += 1
                titles["I"+str(c)] = {"name": name, "class": "missing"}
    maxcol = trunc(sqrt(c))
    width = maxcol*21
    height = maxcol*21+100

    svg_start = f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}px\" height=\"{height}px\" viewBox=\"0 0 {width} {height}\" style=\"background-color: black\" >"
    svg_header = """
        
           <style>
                .description { font: italic 40px serif; fill: darkorange; }
                .missing {
                    stroke: orange;
                    stroke-width: 0.5px;
                    fill: darkorange;
                    fill-opacity: 10%;
                }

                .found {
                    stroke: orange;
                    stroke-width: 0.5px;
                    fill: darkorange;
                    fill-opacity: 30%;
                }

                .missing:hover {
                    stroke: white;
                    fill: red;
                    fill-opacity: 50%;
                }

                .found:hover {
                    stroke: white;
                    fill: red;
                    fill-opacity: 50%;
                }
                

            </style>
            <script>
              // <![CDATA[
                window.addEventListener('DOMContentLoaded', () => {
                    var items={
        """
    svg_struct = ""
    for id in titles.keys():

        idstr = titles.get(id)
        svg_struct = svg_struct + "\n" + '"'+id+'": '+str(idstr)+",\n"
    script_end = """
                       
                    }  
                    
                    Object.keys(items).map(function (keyid) {
                        document.querySelector('#'+keyid).addEventListener('mouseover', (e) => {
                            var wordy  = document.querySelector('text');
                            wordy.textContent = items[e.target.id]["name"]+" "+items[e.target.id]["class"];
                        });
                    });
                    Object.keys(items).map(function (keyid) {
                        document.querySelector('#'+keyid).addEventListener('click', (e) => {
                            window.open("https://canonn-science.github.io/bioforge/?entryid="+items[e.target.id]["name"],"_blank");
                            console.log('onclick')
                        });
                    });
                })
                // ]]>
                </script>

        """
    svg_rects = ""
    svg_text = '<text id="lower" x="10" y="50" dy=".35em" class = "description" text-anchor="left">Hover to see the codex name</text>'

    x = 0
    y = 100
    counter = 0
    maxcol = trunc(sqrt(c))
    for id in titles.keys():
        rectclass = titles.get(id).get("class")
        svg_rects = svg_rects + '<rect id="'+id + \
            '" x="'+str(x) + \
            '" width="19" y="'+str(y)+'" height="19" class="' + \
            rectclass+'" rx="3" ry="3"></rect>'
        x = x+21
        counter += 1
        if counter == maxcol:
            x = 0
            y = y+21
            counter = 0
    # print(titles["I1"])
    svg_trailer = "</svg>"
    svg = svg_start + svg_header + svg_struct + \
        script_end + svg_rects + svg_text + svg_trailer

    return flask.Response(svg, mimetype='image/svg+xml')


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
	case when 
		a > 0 and
		b > 0 and
		c > 0 and
		d > 0 and
		e > 0 and
		f > 0 and
		g > 0 and
		h > 0 and
		i > 0 
	then ended else null end as ended,
	TIMESTAMPDIFF(SECOND,started,ifnull(ended,now())) seconds,
	if (a > 0,a,null) as osseus,
	if (b > 0,b,null) as aleoid,
	if (c > 0,c,null) as cactoid,
	if (d > 0,d,null) as stratum,	
	if (e > 0,e,null) as bacterium,
	if (f > 0,f,null) as fungoid,
	if (g > 0,g,null) as tussock,
	if (h > 0,h,null) as concha,
	if (i > 0,i,null) as shrub
 from (
select cmdr,
max(case when scantype = 'Log' then least(
ifnull(a,STR_TO_DATE("August 10 3307", "%%M %%d %%Y")),
ifnull(b,STR_TO_DATE("August 10 3307", "%%M %%d %%Y")),
ifnull(c,STR_TO_DATE("August 10 3307", "%%M %%d %%Y")),
ifnull(d,STR_TO_DATE("August 10 3307", "%%M %%d %%Y")),
ifnull(e,STR_TO_DATE("August 10 3307", "%%M %%d %%Y")),
ifnull(f,STR_TO_DATE("August 10 3307", "%%M %%d %%Y")),
ifnull(g,STR_TO_DATE("August 10 3307", "%%M %%d %%Y")),
ifnull(h,STR_TO_DATE("August 10 3307", "%%M %%d %%Y")),
ifnull(i,STR_TO_DATE("August 10 3307", "%%M %%d %%Y"))
) else null end) as started,
max(case 
	when scantype = 'Analyse' 
	then greatest(a,b,c,d,e,f,g,h,i) else null end) as ended,
if (a IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then a else null END),
max(case when scantype = 'Analyse' then a else null END))) AS a,
if (b IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then b else null END),
max(case when scantype = 'Analyse' then b else null END))) AS b,
if (c IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then c else null END),
max(case when scantype = 'Analyse' then c else null END))) AS c,
if (d IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then d else null END),
max(case when scantype = 'Analyse' then d else null END))) AS d,
if (e IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then e else null END),
max(case when scantype = 'Analyse' then e else null END))) AS e,
if (f IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then f else null END),
max(case when scantype = 'Analyse' then f else null END))) AS f,
if (g IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then g else null END),
max(case when scantype = 'Analyse' then g else null END))) AS g,
if (h IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then h else null END),
max(case when scantype = 'Analyse' then h else null END))) AS h,
if (i IS NULL,NULL,TIMESTAMPDIFF(SECOND,max(case when scantype = 'Log' then i else null END),
max(case when scantype = 'Analyse' then i else null END))) AS i
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
from organic_scans where system = 'Tucanae Sector AF-A d71' and body_id = 23 {where}
group by cmdr,scantype
) data
group by cmdr) data2
WHERE started IS NOT NULL 
and started != STR_TO_DATE("August 10 3307", "%%M %%d %%Y")
order by case when 
	ended is null or 
		a < 0 or
		b < 0 or
		c < 0 or
		d < 0 or
		e < 0 or
		f < 0 or
		g < 0 or
		h < 0 or
		i < 0 
then 999999 else 0 end + seconds asc
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
