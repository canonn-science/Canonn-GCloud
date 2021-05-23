import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
import requests
import json


def codex_name_ref(request):
    setup_sql_conn()

    with get_cursor() as cursor:
        sql = """
            select * from codex_name_ref
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
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


def codex_systems(request):
    setup_sql_conn()

    hud = request.args.get("hud_category")
    sub = request.args.get("sub_class")
    eng = request.args.get("engish_name")
    system = request.args.get("system")

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)

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
            select s.system,cast(s.x as char) x,cast(s.y as char) x,cast(s.z as char) z,
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
