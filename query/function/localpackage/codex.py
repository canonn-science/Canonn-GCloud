import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
from EDRegionMap.RegionMap import findRegion
import requests
import json
from flask import jsonify
import urllib.parse

biostats = {}
spanshdump = {}
id64list = []


# get the id64 for a given system


def getId64(systemName):
    global id64list
    for system in id64list:
        id = system.get(systemName)
        if id:
            print("id64 from cache")
            return id
    try:
        print(systemName)

        param = urllib.parse.quote(systemName)
        print(param)

        url = f"https://www.edsm.net/api-v1/system?systemName={param}&showId=1"
        print(url)
        r = requests.get(url)
        j = r.json()
        if j.get("id64"):
            # we will store 200 id64 in memory
            if len(id64list) > 200:
                id64list.pop()

            item = {}
            item[systemName] = j.get("id64")
            id64list.append(item)
            return j.get("id64")
    except:
        print("Error getting request")
        print(url)
        print(j)
        return None


def findRegion64(id):
    id64 = int(id)
    masscode = id64 & 7
    z = (((id64 >> 3) & (0x3FFF >> masscode)) << masscode) * 10 - 24105
    y = (((id64 >> (17 - masscode)) & (0x1FFF >> masscode)) << masscode) * 10 - 40985
    x = (
        ((id64 >> (30 - masscode * 2)) & (0x3FFF >> masscode)) << masscode
    ) * 10 - 49985
    try:
        return findRegion(x, y, z)
    except:
        return 0, "Unknown"


def get_biostats(cache=True):
    global biostats
    if not biostats or not cache:
        print("fetching stats")
        r = requests.get(
            "https://drive.google.com/uc?id=14t7SKjLyATHVipuqNiGT-ziA2nRW8sKj"
        )
        biostats = r.json()
    else:
        print("stats cached")


def biostats_cache(cache):
    global biostats
    get_biostats(cache)
    return jsonify(biostats)


def get_spansh_by_id(id64):
    global spanshdump

    cached = (
        spanshdump.get("system")
        and spanshdump.get("system").get("id64")
        and str(spanshdump.get("system").get("id64")) == str(id64)
    )

    # ignore caching as we want latest data
    # if not cached:
    if True:
        print("fetching from spansh")
        r = requests.get(f"https://spansh.co.uk/api/dump/{id64}")
        spanshdump = r.json()
        if spanshdump.get("system"):
            if spanshdump.get("system").get("factions"):
                del spanshdump["system"]["factions"]
            if spanshdump.get("system").get("stations"):
                del spanshdump["system"]["stations"]

        # check that id64 matches
        cached = (
            spanshdump.get("system")
            and spanshdump.get("system").get("id64")
            and str(spanshdump.get("system").get("id64")) == str(id64)
        )
        if not cached:
            spanshdump = {}
    else:
        print("spansh cached")


def get_mainstar_type():
    global spanshdump
    system = spanshdump.get("system")
    for body in system.get("bodies"):
        if body.get("mainStar") == True:
            return body.get("subType")
    return None


def get_primary_star(system):
    bodies = system.get("bodies")
    for body in bodies:
        if body.get("mainStar"):
            return body.get("subType")


def get_parent_type(system, body):
    bodyName = body.get("name")
    systemName = system.get("name")
    shortName = bodyName.replace(f"{systemName} ", "")
    bodies = system.get("bodies")

    parts = shortName.split(" ")

    for n in range(len(parts) - 1, -1, -1):
        newpart = " ".join(parts[:n])
        if newpart.isupper():
            # print(f"converting newpart {newpart} to {newpart[0]}")
            newpart = newpart[0]
        newname = systemName + " " + newpart
        # :qprint(newname)
        for b in bodies:
            if b.get("name") == newname and b.get("type") == "Star":
                # print(f"{newname} = Star")
                # print("{} {}".format(b.get("name"), parentName))
                return b.get("subType")

    # fall back to this
    primary = get_mainstar_type()
    return primary


def get_system_codex(system):

    with get_cursor() as cursor:
        sqltext = """
            select distinct cr.system,nullif(body,'') as body,english_name,hud_category from codexreport cr 
            join codex_name_ref cnr on cnr.entryid = cr.entryid
            where cr.system = %s
            union             
            select distinct cr.system,nullif(body,'') as body,english_name,hud_category from organic_scans cr 
            join codex_name_ref cnr on cnr.name = cr.variant
            where cr.system = %s
        """
        cursor.execute(sqltext, (system, system))
        r = cursor.fetchall()
        cursor.close()
        return r
    return None


def get_id64_codex(id64):
    sqltext = "select entryid,body_id from codex_bodies where system_address = %s"
    with get_cursor() as cursor:
        cursor.execute(sqltext, (id64))
        r = cursor.fetchall()
        cursor.close()
        return jsonify(r)
    return jsonify([])


def mat_species(species):
    id = species.get("id")

    if id:
        for material in (
            "Technetium",
            "Molybdenum",
            "Ruthenium",
            "Tellurium",
            "Antimony",
            "Tungsten",
            "Polonium",
            "Yttrium",
            "Cadmium",
            "Niobium",
            "Mercury",
            "Tin",
        ):
            if material in id:
                return True
    else:
        return False


def checkMats(body, species):
    materials = body.get("materials")
    count = 0
    target = len(species.get("materials"))

    # its its not a materials based species we can return true
    if not mat_species(species):
        return True

    matmatch = False

    if materials:
        for mat in species.get("materials"):
            if mat in materials.keys():
                count += 1

        # if we have all required materials we should be good.
        matmatch = count == target
        # the species id contains the key material that must be present
        # we shouldn't have to do this but there may be some misreported bodies

        hasmat = False
        for key in materials.keys():
            if key in species.get("id"):
                hasmat = True
                break

    # We need matching materials and for our material to be present
    matmatch = matmatch and hasmat

    return matmatch


"""
  If the species is tied to a star type and the star type does not match 
  then return false all other cases we can return true
"""


def checkStar(codex, system):
    fdevname = codex.get("fdevname")
    try:
        h1, h1, genus, species, star, t = fdevname.split("_")
    except:
        # we don't know so let it got
        # print(f"exception: {fdevname}")
        return True

    stars = {
        "O": ["O (Blue-White) Star"],
        "B": ["B (Blue-White) Star"],
        "A": ["A (Blue-White super giant) Star", "A (Blue-White) Star"],
        "F": ["F (White) Star", "F (White super giant) Star"],
        "G": ["G (White-Yellow super giant) Star", "G (White-Yellow) Star"],
        "K": ["K (Yellow-Orange giant) Star", "K (Yellow-Orange) Star"],
        "M": ["M (Red dwarf) Star", "M (Red super giant) Star"],
        "L": ["L (Brown dwarf) Star"],
        "T": ["T (Brown dwarf) Star"],
        "TTS": ["T Tauri Star"],
        "Y": ["Y (Brown dwarf) Star"],
        "W": ["Wolf-Rayet Star"],
        "D": [
            "White Dwarf (D) Star",
            "White Dwarf (DA) Star",
            "White Dwarf (DAB) Star",
            "White Dwarf (DAV) Star",
            "White Dwarf (DAZ) Star",
            "White Dwarf (DB) Star",
            "White Dwarf (DBV) Star",
            "White Dwarf (DC) Star",
            "White Dwarf (DCV) Star",
            "White Dwarf (DQ) Star",
        ],
        "N": ["Neutron Star"],
        "Ae": ["Herbig Ae/Be Star"],
    }
    # if star is defined and in the star list we have a star class
    if star and stars.get(star):
        subTypes = stars.get(star)
        for body in system.get("bodies"):
            if subTypes and body.get("subType") and body.get("subType") in subTypes:
                return True
    else:
        # we don't know so let it through
        # print(f"lookup failed: {codex}")
        return True
    # We didn't find the right starclass
    return False


def guess_biology(body, codex):
    global biostats
    global spanshdump
    system = spanshdump.get("system")
    results = []

    region, region_name = findRegion64(system.get("id64"))

    if body.get("type") != "Planet" or not landable(body):
        return []

    parentType = get_parent_type(system, body)

    for key in biostats.keys():
        species = biostats.get(key)

        if species.get("hud_category") == "Biology":
            validStar = checkStar(species, system)

            odyssey = species.get("platform") == "odyssey"

            # don't match regions on odyssey bios
            # NB we now know that there is region specific biology
            # But we don't want to miss guesses we would have to build
            # some reference data
            regionMatch = odyssey or (
                species.get("regions") and region_name in species.get("regions")
            )

            parentMatch = parentType in species.get("localStars")
            # materials is highly dependednt on species
            validMaterials = checkMats(body, species)

            volcanismMatch = (
                body.get("volcanismType") or "No volcanism"
            ) in species.get("volcanism")

            atmosphereTypeMatch = (
                body.get("atmosphereType") or "No atmosphere"
            ) in species.get("atmosphereType")

            mainstarMatch = get_mainstar_type() in species.get("primaryStars")

            if body.get("subType") is None:
                body["subType"] = "Unknown"
            # use combined body and volcanism
            # bodyMatch = (body.get("subType") in species.get("bodies"))
            volcanicbodytype = None
            if body.get("subType"):
                volcanicbodytype = (
                    body.get("subType")
                    + " - "
                    + (body.get("volcanismType") or "No volcanism")
                )

            if (
                species.get("histograms").get("volcanic_body_types")
                and volcanicbodytype
                in species.get("histograms").get("volcanic_body_types").keys()
            ):
                bodyMatch = True
            else:
                bodyMatch = False

            if bodyMatch and species.get("ming"):
                gravityMatch = (
                    float(species.get("ming"))
                    <= float(body.get("gravity"))
                    <= float(species.get("maxg"))
                )

                pressureMatch = (
                    float(species.get("minp") or 0)
                    <= float((body.get("surfacePressure") or 0))
                    <= float(species.get("maxp") or 0)
                )

                tempMatch = (
                    float(species.get("mint"))
                    <= float(body.get("surfaceTemperature"))
                    <= float(species.get("maxt"))
                )

                distanceMatch = (
                    float(species.get("mind"))
                    <= float(body.get("distanceToArrival"))
                    <= float(species.get("maxd"))
                )

                # if there are genuses recorded then only matching genus should be included in the guesses
                if body.get("signals") and body.get("signals").get("genuses"):
                    matchgenus = False
                    genus = species.get("fdevname").split("_")[2]
                    # print(genus)
                    for g in body.get("signals").get("genuses"):
                        # print(g)
                        if g.split("_")[2] == genus:
                            matchgenus = matchgenus or True
                else:
                    matchgenus = True

                if (
                    matchgenus
                    and validStar
                    and mainstarMatch
                    and bodyMatch
                    and gravityMatch
                    and tempMatch
                    and atmosphereTypeMatch
                    and volcanismMatch
                    and pressureMatch
                    and validMaterials
                    and parentMatch
                    and regionMatch
                ):
                    genus = species.get("name").split(" ")[0]
                    # print(genus)
                    # print(get_body_codex(codex, 'Biology', body.get("name")))
                    ba = get_body_codex(codex, "Biology", body.get("name"))
                    # if not genus in str(get_body_codex(codex, 'Biology', body.get("name"))):
                    #    print(f"using {genus} {ba}")
                    results.append(species.get("name"))
        # else:
        #    if (mainstarMatch and regionMatch):
        #        results.append(species.get("name"))

    return results


def get_body_codex(codex, type, body=None):
    results = []
    for row in codex:
        if row.get("hud_category") == type and row.get("body") == body:
            results.append(row.get("english_name"))
    return results


def set_codex(i, type, body, codex):
    value = get_body_codex(codex, type, body.get("name"))
    if value:
        spanshdump["system"]["bodies"][i]["signals"][type.lower()] = value


def landable(body):
    if body.get("isLandable"):
        return True
    signals = body.get("signals")
    has_biology = signals and body.get("signals").get("signals").get(
        "$SAA_SignalType_Biological;"
    )
    has_geology = signals and body.get("signals").get("signals").get(
        "$SAA_SignalType_Geological;"
    )

    if has_biology or has_geology:
        return True
    return False


def get_stats_by_id(entryid):
    global biostats
    get_biostats()
    return jsonify(biostats.get(entryid))


def get_stats_by_name(names):
    retval = {}
    global biostats
    get_biostats()
    allnames = names.split(",")
    for name in allnames:
        for id, entry in biostats.items():
            if entry.get("name") and name.lower().strip() in entry.get("name").lower():
                retval[id] = entry
    return jsonify(retval)


def system_biostats(request):
    global biostats
    global spanshdump

    id = request.args.get("id")
    systemName = request.args.get("system")
    if request.args.get("system"):
        id = getId64(systemName)

    # lazy loaders
    get_biostats()
    get_spansh_by_id(id)

    if not spanshdump:
        return jsonify({"error": "no spansh data"})

    system = spanshdump.get("system")
    codex = get_system_codex(system.get("name"))

    scloud = get_body_codex(codex, "Cloud")
    sanomaly = get_body_codex(codex, "Anomaly")

    region, region_name = findRegion64(system.get("id64"))
    spanshdump["system"]["region"] = {"region": region, "name": region_name}

    if scloud or sanomaly:
        spanshdump["system"]["signals"] = {}

        if scloud:
            spanshdump["system"]["signals"]["cloud"] = scloud
        if sanomaly:
            spanshdump["system"]["signals"]["anomaly"] = sanomaly

    for i, body in enumerate(system.get("bodies")):
        if landable(body):
            if not spanshdump["system"]["bodies"][i].get("signals"):
                spanshdump["system"]["bodies"][i]["signals"] = {}

            guess = guess_biology(body, codex)
            if guess:
                spanshdump["system"]["bodies"][i]["signals"]["guesses"] = guess

            set_codex(i, "Biology", body, codex)
            set_codex(i, "Geology", body, codex)
            set_codex(i, "Thargoid", body, codex)
            set_codex(i, "Guardian", body, codex)
            set_codex(i, "Cloud", body, codex)
            set_codex(i, "Anomaly", body, codex)

    # return jsonify(biostats.get("2100407"))
    return jsonify(spanshdump)


def quantify_codex(entryid):
    with get_cursor() as cursor:
        sql = """
            SELECT 
                `system` as systemName, 
                SQRT(POW(x - -178.65625, 2) + POW(y - 77.125, 2) + POW(z - -87.125, 2)) AS distance,
                COUNT(*) OVER () AS total_count  
            FROM 
                codex_systems
                where entryid  = %s
            ORDER BY 
                distance ASC
            LIMIT 1;

        """
        cursor.execute(sql, (entryid))
        r = cursor.fetchone()
        cursor.close()
        return jsonify(r)


def codex_name_ref(request):

    with get_cursor() as cursor:
        sql = """
            SELECT c.*,data2.reward,ci.cmdr as image_cmdr,ci.url as image_url
            FROM codex_name_ref c
            left join codex_images ci on ci.entryid = c.entryid
            LEFT JOIN (
            SELECT
                            entryid, CAST(SUBSTRING_INDEX(GROUP_CONCAT(reward
                            ORDER BY created_at DESC), ',', 1) AS SIGNED) AS reward
            FROM (
            SELECT
            entryid,
            reward,created_at
            FROM organic_sales os
            LEFT JOIN codex_name_ref cnr ON cnr.name LIKE
            REPLACE(os.species,'_Name;','%%')
            where os.reported_at < '2024-10-31'
            ) DATA
                 GROUP BY entryid
            ) AS data2 ON data2.entryid = c.entryid
            WHERE 1 = 1 
        """
        hud_category = request.args.get("category")
        sub_class = request.args.get("species")
        english_name = None
        if request.args.get("variant") is not None:
            english_name = "%" + request.args.get("variant") + "%"

        params = []
        if hud_category is not None:
            sql += " AND c.hud_category = %s"
            params.append(hud_category)

        # Check if sub_class is populated
        if sub_class is not None:
            sql += " AND c.sub_class = %s"
            params.append(sub_class)

        # Check if english_name is populated
        if english_name is not None:
            sql += " AND c.english_name like %s"
            params.append(english_name)

        cursor.execute(sql, params)
        r = cursor.fetchall()
        cursor.close()

    res = {}

    for entry in r:
        entry["dump"] = (
            f"https://storage.googleapis.com/canonn-downloads/dumpr/{entry.get('hud_category')}/{entry.get('entryid')}.csv"
        )
        if request.args.get("hierarchy"):
            hud = entry.get("hud_category")
            genus = entry.get("sub_class")
            species = entry.get("english_name")
            if not res.get(hud):
                res[hud] = {}
            if not res.get(hud).get(genus):
                res[hud][genus] = {}
            if not res.get(hud).get(genus).get(species):
                res[hud][genus][species] = {
                    "name": entry.get("name"),
                    "entryid": entry.get("entryid"),
                    "category": entry.get("category"),
                    "sub_category": entry.get("sub_category"),
                    "platform": entry.get("platform"),
                    "reward": entry.get("reward"),
                    "dump": entry.get("dump"),
                }
        else:
            for entry in r:
                res[entry.get("entryid")] = entry
    return res


def get_gr_data():

    with get_cursor() as cursor:
        sql = """
            select distinct systemName as `system`,cast(x as char) x,cast(y as char) y,cast(z as char) z
            FROM guardian_settlements
            WHERE name LIKE '$Ancient:%%';
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        return jsonify(r)


def odyssey_subclass(request):

    with get_cursor() as cursor:
        sql = """
            select sub_class,count(*) as species from codex_name_ref where platform='odyssey'
            group by sub_class
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
    totals = 0
    for entry in r:
        totals = totals + int(entry.get("species"))
        res[entry.get("sub_class")] = entry.get("species")

    res["* Total Species"] = totals
    return res


def species_prices(request):

    r = None
    with get_cursor() as cursor:
        sql = """
            SELECT
                REPLACE(JSON_EXTRACT(sub_species, '$.p[0]'),'"','') as sub_species,
                CAST(SUBSTRING_INDEX(GROUP_CONCAT(reward ORDER BY created_at DESC), ',', 1) as SIGNED) as reward,
                sub_class
            FROM (
                SELECT
                    CAST(CONCAT('{"p": ["', REPLACE(english_name,' - ','","'),'"]}') as JSON) sub_species,
                    reward,
                    sub_class,
                    created_at
                FROM organic_sales os
                JOIN codex_name_ref cnr ON cnr.name LIKE REPLACE(os.species,'_Name;','%%')
                WHERE os.reported_at < '2024-10-11'
            ) data
            GROUP BY REPLACE(JSON_EXTRACT(sub_species, '$.p[0]'),'"',''), sub_class
            ORDER BY reward DESC;       
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
    for entry in r:
        res[entry.get("sub_species")] = {
            "reward": entry.get("reward"),
            "bonus": int(entry.get("reward")) * 2,
        }
    return res


def cmdr(cmdr, request):
    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)

    print(f"limit {limit}")

    with get_cursor() as cursor:
        sql = f"""
            SELECT
                cs.`system` ,
                cs.system_address,
                JSON_ARRAYAGG(
                    JSON_OBJECT(
                        'category', cnr.category,
                        'english_nane', cnr.english_name,
                        'entryid', cnr.entryid,
                        'hud_category', cnr.hud_category,
                        'name', cnr.name,
                        'platform', cnr.platform,
                        'sub_category', cnr.sub_category,
                        'sub_class', cnr.sub_class,
                        'species', trim(SUBSTRING_INDEX(cnr.english_name,'-',1))
                    )
                )
                 AS hud_details,
                ss.x,ss.y,ss.z
            from codex_systems  cs
            join star_systems ss on ss.id64 = cs.system_address
            join codex_name_ref cnr on cs.entryid = cnr.entryid
            where cs.cmdr = %s
            GROUP BY
                cs.`system`,ss.x,ss.y,ss.z,cs.system_address
            order by cs.system_address 
            limit %s,%s	
        """
        cursor.execute(sql, (cmdr, int(offset), int(limit)))
        r = cursor.fetchall()
        cursor.close()

        retval = {}
        for entry in r:
            print(f"name :{entry.get('system')}")
            retval[entry.get("system")] = {
                "codex": json.loads(entry.get("hud_details")),
                "coords": [entry.get("x"), entry.get("y"), entry.get("z")],
            }

    return jsonify(retval)


def codex_data(request):

    hud = request.args.get("hud_category")
    sub = request.args.get("sub_class")
    eng = request.args.get("english_name")
    system = request.args.get("system")
    spe = request.args.get("species")

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)
    if request.args.get("_start"):
        offset = request.args.get("_start")
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    params = []
    clause = ""

    if hud:
        params.append(hud)
        clause = "and hud_category = %s"
    if sub:
        params.append(sub)
        clause = f"{clause} and sub_class = %s "
    if eng:
        params.append(eng)
        clause = f"{clause} and english_name = %s "
    if system:
        params.append(system)
        clause = f"{clause} and `system` = %s "
    if spe:
        params.append(spe)
        clause = f"{clause} and english_name like concat(%s,'%%') "

    params.append(int(offset))
    params.append(int(limit))

    with get_cursor() as cursor:
        sql = f"""
        select `system`,entryid,cast(x as char) x,cast(y as char) y,cast(z as char) z,
            cr.*,trim(SUBSTRING_INDEX(cr.english_name,'-',1)) as species
            FROM codex_systems cs
            INNER JOIN codex_name_ref as cr using (entryid)
            INNER JOIN (
            select s.system,s.entryid from 
            codex_systems s
                        join codex_name_ref cr on cr.entryid = s.entryid
                        where 1 = 1
                        {clause}
            limit %s,%s)
            AS my_results USING(`system`,entryid)
        """
        cursor.execute(sql, (params))
        r = cursor.fetchall()
        cursor.close()

    return r


def codex_bodies(request):

    eng = request.args.get("english_name")

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)
    if request.args.get("_start"):
        offset = request.args.get("_start")
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    params = []
    clause = ""

    if eng:
        params.append(eng)
        clause = f"{clause} and cnr.english_name = %s "

    params.append(int(offset))
    params.append(int(limit))

    with get_cursor() as cursor:
        sql = f"""
    with base_data as (
		# We can select the base data then any joins are only joining on the page that we are selecting      
    	select 
    		cs.id as system_seq,
    		cs.system as tmp_system_name,
    		cs.x,cs.y,cs.z,
    		cs.system_address,
    		cnr.*,
    		case 
	    		when cnr.hud_category = 'Biology' and 
	    			REGEXP_LIKE(cnr.name, '_(Ae|B|D|F|G|K|L|M|N|A|O|T|TTS|W|Y)_Name;$') 
	    		then SUBSTRING_INDEX(SUBSTRING_INDEX(cnr.name, '_', -2), '_', 1) 
	    		else null 
	    	end as codex_star,
    		z_order,
    		ifnull(cb.cmdr,cs.cmdr) as cmdr,
    		ifnull(cb.reported_at,cs.reported_at) as reported_at,
    		cb.id as body_seq,
    		cb.body_id
    	from codex_systems cs
    	left join codex_bodies cb on cb.entryid = cs.entryid and cb.system_address = cs.system_address 
    	join codex_name_ref cnr on cnr.entryid = cs.entryid 
        {clause}
    	order by cs.reported_at desc 
    	limit %s,%s
    ), star_systems as (
    	# now we will join on star system 
        select 
    		base_data.system_seq,
    		ifnull(ss.x,base_data.x) as x,
    		ifnull(ss.y,base_data.y) as y,
    		ifnull(ss.z,base_data.z) as z,
    		base_data.system_address,
    		base_data.english_name,
    		base_data.entryid,
    		base_data.hud_category,
    		base_data.sub_class,
    		base_data.name as variant,
    		base_data.codex_star,
    		base_data.z_order,
    		base_data.cmdr,
    		base_data.reported_at,
    		base_data.body_seq,
    		base_data.body_id,
        	ifnull(ss.name,base_data.tmp_system_name) as system_name,
        	ss.bodies_match
        from base_data
        left join star_systems ss on ss.id64 = base_data.system_address
    )     , ne as (	
    	# joining to get the nearest nebula
       	select 
    		star_systems.*,
 			(select sqrt(pow(star_systems.x-neb.x,2)+pow(star_systems.y-neb.y,2)+pow(star_systems.z-neb.z,2)) from edastro_pois neb where neb.poi_type in ('nebula','planetaryNebula') order by pow(star_systems.x-neb.x,2)+pow(star_systems.y-neb.y,2)+pow(star_systems.z-neb.z,2) asc limit 1) as nearest_nebula,
 			(select poi_type from edastro_pois neb where neb.poi_type in ('nebula','planetaryNebula') order by pow(star_systems.x-neb.x,2)+pow(star_systems.y-neb.y,2)+pow(star_systems.z-neb.z,2) asc limit 1) as nearest_nebula_type
    	from star_systems
    ), system_ids as (
    	# get a unique list of system addresses
    	select distinct system_address from base_data
    ), body_ids as (
    	# get a unique list of system addresses
    	select distinct system_address,body_id,system_name from star_systems    
    ), body_info as (
    	# We will get info on all bodies in the system and as well as current body
    	# 
    	select
    			sbs.system_address,body_ids.body_id,
    			# data for the current body
		    	max(case when sbs.body_id =  body_ids.body_id then trim(replace(sbs.name,body_ids.system_name,'')) else null end) as body,
    	    	max(case when sbs.body_id =  body_ids.body_id then sbs.sub_type else null end) as body_type,
	            max(case when sbs.body_id =  body_ids.body_id then cast(JSON_EXTRACT(sbs.raw_json,'$.rings') as json) else null end) as rings,
	            max(case when sbs.body_id =  body_ids.body_id then JSON_EXTRACT(sbs.raw_json,'$.distanceToArrival') else null end) as distanceToArrival,
				max(case when sbs.body_id =  body_ids.body_id then ifnull(nullif(JSON_UNQUOTE(sbs.raw_json->'$.atmosphereType'),'null'),'No atmosphere') else null end) as atmosphereType,
				max(case when sbs.body_id =  body_ids.body_id then cast(JSON_EXTRACT(sbs.raw_json,'$.atmosphereComposition') as json) else null end) as atmosphereComposition,
				max(case when sbs.body_id =  body_ids.body_id then JSON_UNQUOTE(sbs.raw_json->'$.gravity') else null end) as gravity,
				max(case when sbs.body_id =  body_ids.body_id then JSON_UNQUOTE(sbs.raw_json->'$.surfaceTemperature') else null end) as temperature,
				max(case when sbs.body_id =  body_ids.body_id then ifnull(JSON_UNQUOTE(sbs.raw_json->'$.volcanismType'),'No volcanism') else null end) as volcanismType,
				max(case when sbs.body_id =  body_ids.body_id then cast(JSON_EXTRACT(sbs.raw_json,'$.materials') as json) else null end) as materials,
				max(case when sbs.body_id =  body_ids.body_id then JSON_EXTRACT(sbs.raw_json,'$.orbitalEccentricity') else null end) as orbitalEccentricity,
                max(case when sbs.body_id =  body_ids.body_id then JSON_EXTRACT(sbs.raw_json,'$.parents') else null end) as parents,
                max(case when sbs.body_id =  body_ids.body_id then JSON_EXTRACT(sbs.raw_json,'$.semiMajorAxis') else null end) as semiMajorAxis,
				# aggregate data
				group_concat(distinct case when `type` = 'Planet' then sub_type else null end) as body_types_present,
				max(case when json_extract(sbs.raw_json,'$.mainStar') = true then sbs.sub_type else null end) as star_class  ,
    			GROUP_CONCAT(
    					case when sbs.type = 'Star' then
    					concat(ifnull(nullif(JSON_UNQUOTE(sbs.raw_json->'$.spectralClass'),'null'),sbs.sub_type),' ',nullif(JSON_UNQUOTE(sbs.raw_json->'$.luminosity'),'null'))
    					else null end
    				SEPARATOR ',') AS star_types
    	from body_ids
       	left join system_bodies sbs on sbs.system_address = body_ids.system_address 
    	group by body_ids.system_address,body_id 
    ), unranked_stars AS (
    SELECT 
    	bi.system_address,bi.body_id,sb.sub_type,sb.name,
    	cast(JSON_UNQUOTE(sb.raw_json->'$.absoluteMagnitude') as DECIMAL(65,30)) as absoluteMagnitude,
    	JSON_UNQUOTE(sb.raw_json->'$.surfaceTemperature') as surfaceTemperature,
    	JSON_UNQUOTE(sb.raw_json->'$.spectralClass') as spectralClass,
    	JSON_UNQUOTE(sb.raw_json->'$.luminosity') as luminosity,    	
        CASE 
            WHEN json_extract(bi.parents,'$[0].Star') = sb.body_id then
                cast(JSON_UNQUOTE(sb.raw_json->'$.absoluteMagnitude') as DECIMAL(65,30)) + 5 * LOG10(cast((bi.semiMajorAxis / 206265) / 10 as DECIMAL(65,30)))
            WHEN ABS(bi.distanceToArrival - JSON_UNQUOTE(sb.raw_json->'$.distanceToArrival')) != 0 THEN
                cast(JSON_UNQUOTE(sb.raw_json->'$.absoluteMagnitude') as DECIMAL(65,30)) + 5 * LOG10(cast((ABS(bi.distanceToArrival- JSON_UNQUOTE(sb.raw_json->'$.distanceToArrival')) * 3.08567758e-14) / 10 as DECIMAL(65,30))) 
            ELSE 
                NULL
        END AS apparent_magnitude
    FROM system_bodies sb
    join body_info bi on bi.system_address = sb.system_address
    WHERE sb.type = 'Star' 
), illuminating_stars AS (
	select data.* from (
    SELECT us.*,
        RANK() OVER (PARTITION BY system_address,body_id ORDER BY apparent_magnitude ASC) AS magrank
    FROM unranked_stars us
    ) data where magrank = 1
), codex_stars as (
	select ne.system_address,ne.body_id,
	sum(case 
		when codex_star = 'G' and sb.sub_type in ('G (White-Yellow super giant) Star', 'G (White-Yellow) Star') then 1 
     	when codex_star = 'Ae' and sb.sub_type in ('Herbig Ae/Be Star') then 1
     	when codex_star = 'D' and sb.sub_type in (
	        'White Dwarf (D) Star',
	        'White Dwarf (DA) Star',
	        'White Dwarf (DAB) Star',
	        'White Dwarf (DAV) Star',
	        'White Dwarf (DAZ) Star',
	        'White Dwarf (DB) Star',
	        'White Dwarf (DBV) Star',
	        'White Dwarf (DBZ) Star',
	        'White Dwarf (DC) Star',
	        'White Dwarf (DCV) Star',
	        'White Dwarf (DQ) Star'
    	) then 1
    	when codex_star = 'L' and sb.sub_type in ('L (Brown dwarf) Star') then 1
    	when codex_star = 'F' and sb.sub_type in ('F (White super giant) Star', 'F (White) Star') then 1
    	when codex_star = 'B' and sb.sub_type in ('B (Blue-White super giant) Star', 'B (Blue-White) Star') then 1
    	when codex_star = 'K' and sb.sub_type in ('K (Yellow-Orange giant) Star', 'K (Yellow-Orange) Star') then 1
    	when codex_star = 'M' and sb.sub_type in ('M (Red dwarf) Star', 'M (Red giant) Star', 'M (Red super giant) Star') then 1
	    when codex_star = 'N' and sb.sub_type in ('Neutron Star') then 1
	    when codex_star = 'A' and sb.sub_type in ('A (Blue-White super giant) Star', 'A (Blue-White) Star') then 1
	    when codex_star = 'O' and sb.sub_type in ('O (Blue-White) Star') then 1
	    when codex_star = 'T' and sb.sub_type in ('T (Brown dwarf) Star') then 1
	    when codex_star = 'TTS' and sb.sub_type in ('T Tauri Star') then 1
	    when codex_star = 'W' and sb.sub_type in (
			'Wolf-Rayet C Star',
	        'Wolf-Rayet N Star',
	        'Wolf-Rayet NC Star',
	        'Wolf-Rayet O Star',
	        'Wolf-Rayet Star'
	    ) then 'Y'
		when codex_star = 'Y' and sb.sub_type in ('Y (Brown dwarf) Star') then 1
		when codex_star is null then null
    else 0
    end) as codex_star_match
	from ne
	join system_bodies sb on sb.system_address = ne.system_address
	group by ne.system_address,ne.body_id
)
    # we need something that joins on body info and uses the distanceToArrival to identify the star with the highest apparent magnitude 
    # Sadly this means we have to hit system_bodies twice unless I did something clever on the body_info to get the data I want?
    select 
    	ne.*,
 	    body_info.star_class,
   	    body_info.star_types,
    	body_info.body,
    	body_info.body_type,
    	body_info.rings,
        body_info.distanceToArrival,
        body_info.atmosphereType,
        body_info.atmosphereComposition,
        body_info.gravity,
        body_info.temperature,
        body_info.volcanismType,
        body_info.materials,
        body_info.orbitalEccentricity,
        body_info.body_types_present,
        body_info.parents,
        body_info.semiMajorAxis,
        case when ne.bodies_match = 1 and ifnull(body_info.star_class,'null') != 'null' then 'Y' else 'N' end as complete,
        il.sub_type as illuminating_subtype,
        il.name as illuminating_name,
        il.apparent_magnitude,
        il.absoluteMagnitude,
        il.surfaceTemperature,
        il.spectralClass,
        il.luminosity,
                case 
	    when codex_star = 'G' and il.sub_type in ('G (White-Yellow super giant) Star', 'G (White-Yellow) Star') then 'Y' 
     	when codex_star = 'Ae' and il.sub_type in ('Herbig Ae/Be Star') then 'Y'
     	when codex_star = 'D' and il.sub_type in (
	        'White Dwarf (D) Star',
	        'White Dwarf (DA) Star',
	        'White Dwarf (DAB) Star',
	        'White Dwarf (DAV) Star',
	        'White Dwarf (DAZ) Star',
	        'White Dwarf (DB) Star',
	        'White Dwarf (DBV) Star',
	        'White Dwarf (DBZ) Star',
	        'White Dwarf (DC) Star',
	        'White Dwarf (DCV) Star',
	        'White Dwarf (DQ) Star'
    	) then 'Y'
    	when codex_star = 'L' and il.sub_type in ('L (Brown dwarf) Star') then 'Y'
    	when codex_star = 'F' and il.sub_type in ('F (White super giant) Star', 'F (White) Star') then 'Y'
    	when codex_star = 'B' and il.sub_type in ('B (Blue-White super giant) Star', 'B (Blue-White) Star') then 'Y'
    	when codex_star = 'K' and il.sub_type in ('K (Yellow-Orange giant) Star', 'K (Yellow-Orange) Star') then 'Y'
    	when codex_star = 'M' and il.sub_type in ('M (Red dwarf) Star', 'M (Red giant) Star', 'M (Red super giant) Star') then 'Y'
	    when codex_star = 'N' and il.sub_type in ('Neutron Star') then 'Y'
	    when codex_star = 'A' and il.sub_type in ('A (Blue-White super giant) Star', 'A (Blue-White) Star') then 'Y'
	    when codex_star = 'O' and il.sub_type in ('O (Blue-White) Star') then 'Y'
	    when codex_star = 'T' and il.sub_type in ('T (Brown dwarf) Star') then 'Y'
	    when codex_star = 'TTS' and il.sub_type in ('T Tauri Star') then 'Y'
	    when codex_star = 'W' and il.sub_type in (
			'Wolf-Rayet C Star',
	        'Wolf-Rayet N Star',
	        'Wolf-Rayet NC Star',
	        'Wolf-Rayet O Star',
	        'Wolf-Rayet Star'
	    ) then 'Y'
		when codex_star = 'Y' and il.sub_type in ('Y (Brown dwarf) Star') then 'Y'
		when codex_star is null then '-'
    else 'N'
    end as star_type_match,
    cs.codex_star_match
    from ne
    left join body_info on body_info.system_address = ne.system_address and body_info.body_id = ne.body_id
    left join illuminating_stars il on body_info.system_address = il.system_address and body_info.body_id = il.body_id
    left join codex_stars cs on body_info.system_address = cs.system_address and body_info.body_id = cs.body_id
        """
        cursor.execute(sql, (params))
        processed_rows = []

        # Fetch and process rows one by one
        while True:
            row = cursor.fetchone()
            if row is None:
                break

            # Create a new dictionary for the processed row
            processed_row = {}

            # Iterate over the columns in the row
            for key, value in row.items():
                try:
                    # Try to load the JSON value
                    processed_row[key] = json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    # If it's not a JSON string, just use the original value
                    processed_row[key] = value

            # Append the processed row to the list
            processed_rows.append(processed_row)
        cursor.close()

    return jsonify(processed_rows)


## replaces /poiListSignals used by Triumvitate
def poi_list_signals(request):

    systemName = request.args.get("system")
    with get_cursor() as cursor:
        sql = """
          select distinct cnr.hud_category,cnr.english_name,cr.body
          from codexreport cr 
          join codex_name_ref cnr 
          on cnr.entryid = cr.entryid 
          where cr.system  = %s
        """
        cursor.execute(sql, (systemName))
        r = cursor.fetchall()
        cursor.close()

        return jsonify(r)

    return jsonify([])


def codex_systems(request):
    r = codex_data(request)

    res = {}

    for entry in r:
        if not res.get(entry.get("system")):
            res[entry.get("system")] = {
                "codex": [],
                "coords": [entry.get("x"), entry.get("y"), entry.get("z")],
            }

        res[entry.get("system")]["codex"].append(
            {
                "category": entry.get("category"),
                "english_name": entry.get("english_name"),
                "entryid": entry.get("entryid"),
                "hud_category": entry.get("hud_category"),
                "name": entry.get("name"),
                "platform": entry.get("platform"),
                "sub_category": entry.get("sub_category"),
                "sub_class": entry.get("sub_class"),
                "species": entry.get("species"),
            }
        )
    return res


def capi_systems(request):
    data = codex_data(request)
    retval = []
    for r in data:
        retval.append(
            {
                "system": {
                    "systemName": r.get("system"),
                    "edsmCoordX": r.get("x"),
                    "edsmCoordY": r.get("y"),
                    "edsmCoordZ": r.get("z"),
                },
                "type": {
                    "hud_category": r.get("hud_category"),
                    "species": r.get("species"),
                    "type": r.get("sub_class"),
                    "journalName": r.get("english_name"),
                    "journalID": r.get("entryid"),
                },
            }
        )
    return jsonify(retval)
