from flask import current_app
from flask import request, jsonify
from flask_cors import CORS
import localpackage.tableutils

import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import localpackage.challenge
import localpackage.codex
import localpackage.poidata
import localpackage.gnosis
import localpackage.thargoids
import localpackage.regionsvg
import localpackage.linkdecoder
import localpackage.events
import localpackage.fyi
import functions_framework

import json
import requests
from math import sqrt
from os import getenv


app = current_app
CORS(app)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True


@app.route("/poiListSignals")
def poiListSignals():
    return localpackage.codex.poi_list_signals(request)


@app.route("/linkDecode")
def link_decode():
    return localpackage.linkdecoder.decodeit(request)


@app.route("/uia/waypoints")
def uiawaypoints():
    return localpackage.poidata.uai_waypoints()


@app.route("/uia/waypoints/<uia>")
def uiawaypoints2(uia):
    return localpackage.poidata.uai_waypoints(int(uia))


@app.route("/fyi/<path>")
def canonn_fyi(path):
    return localpackage.fyi.get_url(path)


@app.route("/events")
def getevents():
    return localpackage.events.fetch_events(request)


@app.route("/collision_table")
def collision_table():
    events = localpackage.events.collision_dates(request)
    image_data = localpackage.tableutils.generate_table_image(events)
    headers = {
        "Content-Type": "image/png",
        "Content-Disposition": "inline; filename=table.png",
    }
    return image_data, 200, headers


@app.route("/events/<limit>/<page>")
def pageevents(limit, page):
    system = request.args.get("system")

    return localpackage.events.page_events(int(limit), int(page), system)


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


@app.route("/challenge/svg")
def challenge_svg():
    return localpackage.challenge.challenge_svg(request)


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


@app.route("/gnosis/schedule")
def gnosis_schedule():
    schedule = localpackage.gnosis.get_schedule()
    return jsonify(schedule)


@app.route("/settlement/<id64>")
def get_settlement(id64):
    settlement = localpackage.poidata.get_settlement(id64)
    return jsonify(settlement)


@app.route("/gnosis/schedule/table")
def gnosis_schedule_tab():
    system = request.args.get("system")
    schedule = []
    data = localpackage.gnosis.get_schedule()
    for item in data:
        if system is None or system == item.get("system"):
            schedule.append(
                {
                    "Arrival": item.get("arrival"),
                    "System": item.get("system"),
                    "Description": item.get("desc"),
                    "Departure": item.get("departure"),
                }
            )
    image_data = localpackage.tableutils.generate_table_image(schedule)
    headers = {
        "Content-Type": "image/png",
        "Content-Disposition": "inline; filename=table.png",
    }
    return image_data, 200, headers


@app.route("/region/<regions>/<size>")
def region_svg(regions, size):
    return localpackage.regionsvg.region_svg(regions, size)


@app.route("/biostats/<entryid>")
def get_stats_by_id(entryid):
    if entryid.isnumeric():
        return localpackage.codex.get_stats_by_id(entryid)
    else:
        return localpackage.codex.get_stats_by_name(entryid)


@app.route("/biostats")
def biostats():
    return localpackage.codex.biostats_cache(True)


@app.route("/get_compres")
def get_compromised():
    return localpackage.poidata.get_compres(request)


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


@app.route("/thargoid/nhss/systems")
def get_nhss_systems():
    return localpackage.thargoids.get_nhss_systems(request)


@app.route("/thargoid/nhss/reports")
def get_nhss_reports():
    return localpackage.thargoids.get_nhss_reports(request)


@app.route("/thargoid/hyperdiction/reports")
def get_hd_reports():
    return localpackage.thargoids.get_hyperdiction_detections(request)


@app.route("/codex/biostats")
def system_biostats():
    return localpackage.codex.system_biostats(request)


@app.route("/get_gr_data")
def get_gr_data():
    return localpackage.codex.get_gr_data()


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
            raw.append(
                {
                    "system": row.get("systemName"),
                    "body": row.get("bodyName"),
                    "x": row.get("x"),
                    "y": row.get("y"),
                    "z": row.get("z"),
                    "raw_event": json.loads(row.get("raw_event")),
                }
            )
        cursor.close()

    return jsonify(raw)


@app.route("/")
def root():
    return ""


@functions_framework.http
def payload(request):
    return "what happen"
