from flask import current_app
from flask import request, jsonify
from flask import Flask, g
import paramiko
from paramiko import RSAKey
from sshtunnel import SSHTunnelForwarder

import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
from localpackage.dbutils import close_mysql
from paramiko import RSAKey
from sshtunnel import SSHTunnelForwarder
import functions_framework

import pymysql
import socket
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
import localpackage.srvsurvey
import localpackage.fleet_carriers
import functions_framework
from paramiko import RSAKey
from sshtunnel import SSHTunnelForwarder
import logging

from functools import wraps
from flask import url_for
import uuid
import base64

import json
import requests
from math import sqrt
from os import getenv
import traceback


app = current_app
CORS(app)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True


# This should identify the instance so I can see if the crashed instance is being closed
app.canonn_cloud_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode("utf-8")

# get tunnel config from the environment
app.tunnel_config = {
    "host": getenv("TUNNEL_HOST", None),
    "keyfile": getenv("TUNNEL_KEY", None),
    "user": getenv("TUNNEL_USER", "tunneluser"),
    "local_port": int(getenv("MYSQL_PORT", "3308")),
    "remote_port": int(getenv("TUNNEL_PORT", "3306")),
}


def wrap_route(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # going to run the route and close down connections if it fails
        try:
            route_name = url_for(f.__name__, **kwargs)
            # Print route and instance id
            print(f"Route: {route_name} {app.canonn_cloud_id}")
            return f(*args, **kwargs)
        except Exception as e:
            # Log the error
            stack_trace = traceback.format_exc()
            logging.error(f"An error occurred: {str(e)}")
            logging.error(stack_trace)
            # close mysql
            close_mysql()
            return "I'm sorry Dave I'm afraid I can't do that", 500

    return decorated_function


@app.before_request
def before_request():
    setup_sql_conn()


@app.route("/srvsurvey/system/<id64>")
@wrap_route
def srv_fetch_system(id64):
    return localpackage.srvsurvey.fetch_system(id64)


@app.route("/typeahead")
@wrap_route
def typeahead():
    if request.args.get("q"):
        try:
            r = requests.get(
                f"https://spansh.co.uk/api/systems/field_values/system_names?q={request.args.get('q')}"
            )
            r.raise_for_status()  # Raises an exception for 4xx and 5xx status codes
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Connection error occurred: {conn_err}")
        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout error occurred: {timeout_err}")
        except requests.exceptions.RequestException as req_err:
            print(f"An error occurred: {req_err}")
        else:
            return jsonify(r.json())
    return jsonify({})


@app.route("/fleetCarriers/<path>/<name>")
@wrap_route
def getFleetNamed(path, name):
    return localpackage.fleet_carriers.show_name(path, name)


@app.route("/fleetCarrier/<serial>")
@wrap_route
def getFleetSerial(serial):
    return localpackage.fleet_carriers.show_serial(serial)


@app.route("/fleetCarriers/nearest")
@wrap_route
def getFleetNearest():
    x = request.args.get("x")
    y = request.args.get("y")
    z = request.args.get("z")
    return localpackage.fleet_carriers.show_nearest(x, y, z)


@app.route("/fleetCarriers")
@wrap_route
def getFleetSystems():
    systems = request.args.get("systems")
    if systems is None:
        return localpackage.fleet_carriers.show_all()
    else:
        return localpackage.fleet_carriers.show_systems(systems)


@app.route("/get_cmdr_status")
@wrap_route
def get_cmdr_status():
    return localpackage.poidata.get_status(request)


@app.route("/poiListSignals")
@wrap_route
def poiListSignals():
    return localpackage.codex.poi_list_signals(request)


@app.route("/linkDecode")
@wrap_route
def link_decode():
    return localpackage.linkdecoder.decodeit(request)


@app.route("/uia/waypoints")
@wrap_route
def uiawaypoints():
    return localpackage.poidata.uai_waypoints()


@app.route("/uia/waypoints/<uia>")
@wrap_route
def uiawaypoints2(uia):
    return localpackage.poidata.uai_waypoints(int(uia))


@app.route("/fyi/<path>")
@wrap_route
def canonn_fyi(path):
    return localpackage.fyi.get_url(path)


@app.route("/events")
@wrap_route
def getevents():
    return localpackage.events.fetch_events(request)


@app.route("/collision_table")
@wrap_route
def collision_table():
    events = localpackage.events.collision_dates(request)
    image_data = localpackage.tableutils.generate_table_image(events)
    headers = {
        "Content-Type": "image/png",
        "Content-Disposition": "inline; filename=table.png",
    }
    return image_data, 200, headers


@app.route("/events/<limit>/<page>")
@wrap_route
def pageevents(limit, page):
    system = request.args.get("system")

    return localpackage.events.page_events(int(limit), int(page), system)


@app.route("/getSystemPoi")
@wrap_route
def getSystemPoi():
    return localpackage.poidata.getSystemPoi(request)


@app.route("/codex/prices")
@wrap_route
def codex_prices():
    return localpackage.codex.species_prices(request)


@app.route("/codex/systems")
@wrap_route
def codex_systems():
    return localpackage.codex.codex_systems(request)


@app.route("/codex/bodies/<id64>")
@wrap_route
def get_id64_codex(id64):
    return localpackage.codex.get_id64_codex(id64)


@app.route("/codex/bodies")
@wrap_route
def codex_bodies():
    return localpackage.codex.codex_bodies(request)


@app.route("/codex/capi")
@wrap_route
def codex_capi():
    return localpackage.codex.capi_systems(request)


@app.route("/codex/odyssey/subclass")
@wrap_route
def codex_odyssey_subclass():
    return localpackage.codex.odyssey_subclass(request)


@app.route("/codex/ref")
@wrap_route
def codex_ref():
    return localpackage.codex.codex_name_ref(request)


@app.route("/codex/cmdr/<cmdrname>")
@wrap_route
def codex_cmdr(cmdrname):
    return localpackage.codex.cmdr(cmdrname, request)


@app.route("/challenge/next")
@wrap_route
def challenge_next():
    return localpackage.challenge.challenge_next(request)


@app.route("/next/missing/image")
@wrap_route
def next_missing_image():
    return localpackage.challenge.next_missing_image(request)


@app.route("/challenge/svg")
@wrap_route
def challenge_svg():
    return localpackage.challenge.challenge_svg(request)


@app.route("/challenge/fastest_scans")
@wrap_route
def challenge_fastest_scans():
    return localpackage.challenge.fastest_scans(request)


@app.route("/challenge/speed")
@wrap_route
def challenge_speed():
    return localpackage.challenge.speed_challenge(request)


@app.route("/challenge/status")
@wrap_route
def challenge_status():
    return localpackage.challenge.challenge_status(request)


@app.route("/missing/codex")
@wrap_route
def missing_codex():
    return localpackage.challenge.missing_codex(request)


@app.route("/nearest/codex")
@wrap_route
def nearest_codex():
    return localpackage.challenge.nearest_codex(request)


@app.route("/gnosis")
@wrap_route
def gnosis():
    return localpackage.gnosis.entry_point(request)


@app.route("/gnosis/schedule")
@wrap_route
def gnosis_schedule():
    schedule = localpackage.gnosis.get_schedule()
    return jsonify(schedule)


@app.route("/settlement/<id64>")
@wrap_route
def get_settlement(id64):
    settlement = localpackage.poidata.get_settlement(id64)
    return jsonify(settlement)


@app.route("/gnosis/schedule/table")
@wrap_route
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
@wrap_route
def region_svg(regions, size):
    return localpackage.regionsvg.region_svg(regions, size)


@app.route("/biostats/<entryid>")
@wrap_route
def get_stats_by_id(entryid):

    if entryid.isnumeric():
        return localpackage.codex.get_stats_by_id(entryid)
    else:
        return localpackage.codex.get_stats_by_name(entryid)


@app.route("/biostats")
@wrap_route
def biostats():
    return localpackage.codex.biostats_cache(True)


@app.route("/get_compres")
@wrap_route
def get_compromised():
    return localpackage.poidata.get_compres(request)


@app.route("/survey/temperature")
@wrap_route
def temperature():
    setup_sql_conn()

    with get_cursor() as cursor:
        sql = """
            SELECT 
                cmdr,
                `system`,
                body,
                CAST(latitude AS CHAR) AS latitude,
                CAST(longitude AS CHAR) AS longitude,
                comment,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(raw_status, '$.Temperature')) AS CHAR) AS temperature,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(raw_status, '$.Gravity')) AS CHAR) AS gravity
            FROM 
                status_reports 
            WHERE 
                JSON_EXTRACT(raw_status, '$.Temperature') IS NOT NULL
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    return jsonify(r)


@app.route("/thargoid/nhss/systems")
@wrap_route
def get_nhss_systems():
    return localpackage.thargoids.get_nhss_systems(request)


@app.route("/thargoid/nhss/reports")
@wrap_route
def get_nhss_reports():
    return localpackage.thargoids.get_nhss_reports(request)


@app.route("/thargoid/hyperdiction/reports")
@wrap_route
def get_hd_reports():
    return localpackage.thargoids.get_hyperdiction_detections(request)


@app.route("/codex/biostats")
@wrap_route
def system_biostats():
    return localpackage.codex.system_biostats(request)


@app.route("/get_gr_data")
@wrap_route
def get_gr_data():
    return localpackage.codex.get_gr_data()


@app.route("/carrier/<serial>")
@wrap_route
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
@wrap_route
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
@wrap_route
def root():
    return ""


@functions_framework.http
def payload(request):
    return "what happen", 400
