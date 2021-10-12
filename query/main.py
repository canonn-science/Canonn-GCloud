from flask import current_app
from flask import request, jsonify
from flask_cors import CORS


import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import localpackage.challenge
import localpackage.codex
import localpackage.poidata
import localpackage.gnosis
import json
import requests

app = current_app
CORS(app)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

biodata = {}


@app.route("/getSystemPoi")
def getSystemPoi():
    return localpackage.poidata.getSystemPoi(request)


@app.route("/codex/prices")
def codex_prices():
    return localpackage.codex.species_prices(request)


@app.route("/codex/systems")
def codex_systems():
    return localpackage.codex.codex_systems(request)


@app.route("/codex/capi")
def codex_capi():
    return localpackage.codex.capi_systems(request)


@app.route("/codex/odyssey/subclass")
def codex_odyssey_subclass():
    return localpackage.codex.odyssey_subclass(request)


@app.route("/codex/ref")
def codex_ref():
    return localpackage.codex.codex_name_ref(request)


@app.route("/challenge/next")
def challenge_next():
    return localpackage.challenge.challenge_next(request)


@app.route("/challenge/fastest_scans")
def challenge_fastest_scans():
    return localpackage.challenge.fastest_scans(request)


@app.route("/challenge/speed")
def challenge_speed():
    return localpackage.challenge.speed_challenge(request)


@app.route("/challenge/status")
def challenge_status():
    return localpackage.challenge.challenge_status(request)


# @app.route("/nearest/codex/")
# def __codex():
#    return localpackage.challenge.nearest_codex(request)


@app.route("/nearest/codex")
def nearest_codex():
    return localpackage.challenge.nearest_codex(request)


@app.route("/gnosis")
def gnosis():
    return localpackage.gnosis.entry_point(request)


@app.route("/biostats")
def biostats():
    global biodata
    if not biodata:
        r = requests.get(
            "https://drive.google.com/uc?export=download&id=14t7SKjLyATHVipuqNiGT-ziA2nRW8sKj")
        biodata = r.json()
    return jsonify(biodata)


@app.route("/survey/temperature")
def temperature():
    setup_sql_conn()

    with get_cursor() as cursor:
        sql = """
            select 
                cmdr,
                system,
                body,
                cast(latitude as CHAR) as latitude,
                cast(longitude as CHAR) as longitude,
                comment,
                cast(raw_status->"$.Temperature" as CHAR) as temperature, 
                cast(raw_status->"$.Gravity" as CHAR) as gravity 
            from status_reports where raw_status->"$.Temperature" is not null
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    return jsonify(r)


@app.route("/carrier/<serial>")
def get_carrier(serial):
    setup_sql_conn()

    with get_cursor() as cursor:
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
            cast(services as char) service,
            case when current_system = previous_system then 'Y' else 'N' end as static,
            case when date(jump_dt) = date(now()) then 'Y' else 'N' end as current
            from fleet_carriers
            where serial_no = %s
        """
        cursor.execute(sql, (serial))
        r = cursor.fetchone()
        cursor.close()
        if r:
            r["service"] = json.loads(r.get("service"))

    return jsonify(r)


@app.route("/raw")
def raw_data():
    setup_sql_conn()

    evt = request.args.get("event")
    system = request.args.get("system")

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)
    if request.args.get("_start"):
        offset = request.args.get("_start")
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    params = []
    clause = ""

    if evt:
        params.append(evt)
        clause = "and event = %s"

    if system:
        params.append(system)
        clause = f"{clause} and systemName = %s "

    params.append(int(offset))
    params.append(int(limit))

    raw = []

    with get_cursor() as cursor:
        sql = f"""
            select s.systemName,s.bodyName,cast(s.x as char) x,cast(s.y as char) y,cast(s.z as char) z,raw_event
            from raw_events s
            where 1 = 1
            {clause}
            order by systemName
            limit %s,%s
        """
        cursor.execute(sql, (params))
        r = cursor.fetchall()
        for row in r:
            raw.append({
                "system": row.get("systemName"),
                "body": row.get("bodyName"),
                "x": row.get("x"),
                "y": row.get("y"),
                "z": row.get("z"),
                "raw_event": json.loads(row.get("raw_event"))
            }
            )
        cursor.close()

    return jsonify(raw)


@app.route("/")
def root():
    return ""


def payload(request):
    return "what happen"
