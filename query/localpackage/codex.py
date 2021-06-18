import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
import requests
import json
from flask import jsonify


def codex_name_ref(request):
    setup_sql_conn()

    with get_cursor() as cursor:
        sql = """
               select c.*,data2.reward from codex_name_ref c
            left join (
                SELECT 
                                entryid,max(reward) as reward
                                from (		 
                                select 
                                cnr.entryid,
                                cast(concat('{"p": ["',replace(english_name,' - ','","'),'"]}') as json) sub_species,reward,sub_class
                            FROM organic_sales os
                            LEFT JOIN codex_name_ref cnr ON cnr.name LIKE
                            REPLACE(os.species,'_Name;','%%')

                            ) data
                            group by entryid
                ) as data2
            on data2.entryid =  c.entryid
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
    if request.args.get("hierarchy"):

        for entry in r:
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
                    "reward": entry.get("reward")
                }

    else:
        for entry in r:
            res[entry.get("entryid")] = entry
    return res


def odyssey_subclass(request):
    setup_sql_conn()

    with get_cursor() as cursor:
        sql = """
            select sub_class,count(*) as species from codex_name_ref where platform="odyssey"
            group by sub_class
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
    totals = 0
    for entry in r:
        totals = totals+int(entry.get("species"))
        res[entry.get("sub_class")] = entry.get("species")

    res["* Total Species"] = totals
    return res


def species_prices(request):
    setup_sql_conn()

    r = None
    with get_cursor() as cursor:
        sql = """
            SELECT 
                distinct replace(sub_species->"$.p[0]",'"','') as sub_species,reward,sub_class
                from (		 
                select 
                cast(concat('{"p": ["',replace(english_name,' - ','","'),'"]}') as json) sub_species,reward,sub_class
            FROM organic_sales os
            LEFT JOIN codex_name_ref cnr ON cnr.name LIKE
            REPLACE(os.species,'_Name;','%%')
            ) data
            ORDER BY reward DESC
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
    for entry in r:
        res[entry.get("sub_species")] = {
            "reward": entry.get("reward"),
            "bonus": int(entry.get("reward"))*2
        }
    return res


def codex_data(request):
    setup_sql_conn()

    hud = request.args.get("hud_category")
    sub = request.args.get("sub_class")
    eng = request.args.get("english_name")
    system = request.args.get("system")

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
        clause = f"{clause} and system = %s "

    params.append(int(offset))
    params.append(int(limit))

    with get_cursor() as cursor:
        sql = f"""
            select s.system,cast(s.x as char) x,cast(s.y as char) y,cast(s.z as char) z,
            cr.*
            from codex_systems s
            join codex_name_ref cr on cr.entryid = s.entryid
            where 1 = 1
            {clause}
            order by system
            limit %s,%s
        """
        cursor.execute(sql, (params))
        r = cursor.fetchall()
        cursor.close()

    return r


def codex_systems(request):
    r = codex_data(request)

    res = {}

    for entry in r:
        if not res.get(entry.get("system")):
            res[entry.get("system")] = {"codex": [], "coords": [
                entry.get("x"), entry.get("y"), entry.get("z")]}

        res[entry.get("system")]["codex"].append(
            {
                "category": entry.get("category"),
                "english_name": entry.get("english_name"),
                "entryid": entry.get("entryid"),
                "hud_category": entry.get("hud_category"),
                "name": entry.get("name"),
                "platform": entry.get("platform"),
                "sub_category": entry.get("sub_category"),
                "sub_class": entry.get("sub_class")
            }
        )
    return res

    for entry in r:
        if not res.get(entry.get("system")):
            res[entry.get("system")] = {"codex": [], "coords": [
                entry.get("x"), entry.get("y"), entry.get("z")]}

        res[entry.get("system")]["codex"].append(
            {
                "category": entry.get("category"),
                "english_name": entry.get("english_name"),
                "entryid": entry.get("entryid"),
                "hud_category": entry.get("hud_category"),
                "name": entry.get("name"),
                "platform": entry.get("platform"),
                "sub_category": entry.get("sub_category"),
                "sub_class": entry.get("sub_class")
            }
        )
    return res
    # return jsonify(codex_data(request))


def capi_systems(request):
    data = codex_data(request)
    retval = []
    for r in data:
        retval.append({
            "system": {
                "systemName": r.get("system"),
                "edsmCoordX": r.get("x"),
                "edsmCoordY": r.get("y"),
                "edsmCoordZ": r.get("z"),
            },
            "type": {
                "hud_category": r.get("hud_category"),
                "type": r.get("sub_class"),
                "journalName": r.get("english_name"),
                "journalID": r.get("entryid")
            }
        })
    return jsonify(retval)
