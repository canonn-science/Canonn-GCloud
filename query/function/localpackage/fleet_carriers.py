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

sql = """
        select 
            serial_no,
            name,
            cast(jump_dt as char) as jump_dt,
            current_system,
            cast(current_x as char) as current_x,
            cast(current_y as char) as current_y,
            cast(current_z as char) as current_z,	
            previous_system,
            cast(previous_x as char) as previous_x,
            cast(previous_y as char) as previous_y,
            cast(previous_z as char) as previous_z,
            cast(last_jump_dt as char) as last_jump_dt,
            services,
            case when current_system = previous_system then 'Y' else 'N' end as static,
            case when date(jump_dt) = date(now()) then 'Y' else 'N' end as current
        from fleet_carriers
"""

"""
dumps all the data
"""


def show_all():
    global sql
    setup_sql_conn()

    with get_cursor() as cursor:
        cursor.execute(sql, ())
        cr = cursor.fetchall()
    return jsonify(cr)


def show_serial(serial):
    global sql
    setup_sql_conn()
    results = []
    sqltext = sql + " where serial_no = %s"

    with get_cursor() as cursor:
        cursor.execute(sqltext, (serial))
        results = cursor.fetchall()
        cursor.close()

    return jsonify(results)


def show_name(path, name):
    if path not in ("beginning", "ending", "like", "named"):
        return f"{path} is not recognised", 404
    global sql
    setup_sql_conn()
    results = []
    if path == "beginning":
        name = name + "%"
        sqltext = sql + " where name like %s"
    if path == "ending":
        name = "%" + name
        sqltext = sql + " where name like %s"
    if path == "like":
        name = "%" + name + "%"
        sqltext = sql + " where name like %s"
    if path == "named":
        sqltext = sql + " where name = %s"
    print(sqltext.replace("%s", name))
    with get_cursor() as cursor:
        cursor.execute(sqltext, (name))
        results = cursor.fetchall()
        cursor.close()

    return jsonify(results)


def show_systems(systems):
    setup_sql_conn()
    system_names_list = systems.split(",")
    placeholders = ", ".join(["%s" for _ in system_names_list])
    sqltext = sql + f" where current_system in ({placeholders})"

    with get_cursor() as cursor:
        cursor.execute(sqltext, (system_names_list))
        results = cursor.fetchall()
        cursor.close()
    return jsonify(results)


def show_nearest(x, y, z):
    setup_sql_conn()
    sql = """
        select 
            serial_no,
            name,
            cast(jump_dt as char) as jump_dt,
            current_system,
            cast(current_x as char) as current_x,
            cast(current_y as char) as current_y,
            cast(current_z as char) as current_z,	
            previous_system,
            cast(previous_x as char) as previous_x,
            cast(previous_y as char) as previous_y,
            cast(previous_z as char) as previous_z,
            cast(last_jump_dt as char) as last_jump_dt,
            services,
            case when current_system = previous_system then 'Y' else 'N' end as static,
            case when date(jump_dt) = date(now()) then 'Y' else 'N' end as current,
            sqrt(pow(current_x-cast(%s as decimal),2)+pow(current_y-cast(%s as decimal),2)+pow(current_z-cast(%s as decimal),2)) as distance
        from fleet_carriers
        order by 
                pow(current_x-cast(%s as decimal),2)+pow(current_y-cast(%s as decimal),2)+pow(current_z-cast(%s as decimal),2) asc,
                jump_dt desc
            limit 10
    """

    with get_cursor() as cursor:

        cursor.execute(sql, (str(x), str(y), str(z), str(x), str(y), str(z)))
        results = cursor.fetchall()
        cursor.close()

    return jsonify(results)
