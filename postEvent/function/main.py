from pymysql.err import OperationalError
import json
import logging
from math import pow, sqrt, trunc
from os import getenv
from urllib.parse import quote_plus, urlencode, quote
import requests
import pymysql
import sys
import logging
from functools import wraps
from flask import url_for
import uuid
import base64
import paramiko
import socket

from flask import current_app
from flask import request, jsonify
from flask_cors import CORS
from flask import Flask, g


import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
from localpackage.dbutils import close_mysql
from paramiko import RSAKey
from sshtunnel import SSHTunnelForwarder
import functions_framework
import traceback

whitelist = []
hooklist = {}
excuses = []

app = current_app
CORS(app)

import random


def load_excuses():
    global excuses
    with open("excuses.txt", "r") as file:
        excuses = file.readlines()
    return [excuse.strip() for excuse in excuses]


excuses = load_excuses()


def generate_random_excuse():
    global excuses
    return random.choice(excuses)


app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

# get tunnel config from the environment
app.tunnel_config = {
    "host": getenv("TUNNEL_HOST", None),
    "keyfile": getenv("TUNNEL_KEY", None),
    "user": getenv("TUNNEL_USER", "tunneluser"),
    "local_port": int(getenv("MYSQL_PORT", "3308")),
    "remote_port": int(getenv("TUNNEL_PORT", "3306")),
}

# This should identify the instance so I can see if the crashed instance is being closed
app.canonn_cloud_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode("utf-8")


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


def is_odyssey(value):
    if value is False:
        return "N"
    if value is True:
        return "Y"
    return


def __get_whitelist():
    global whitelist
    if not whitelist:
        with get_cursor() as cursor:
            sql = """select * from postEvent_whitelist"""
            cursor.execute(sql, ())
            r = cursor.fetchall()
            result = []
            cursor.close()
        for v in r:
            result.append(
                {
                    "description": v.get("description"),
                    "definition": json.loads(v.get("definition")),
                }
            )
        whitelist = result

    return whitelist


def get_webhooks():
    global hooklist
    if not hooklist:
        with get_cursor() as cursor:
            sql = """select * from webhooks"""
            cursor.execute(sql, ())
            r = cursor.fetchall()
            result = {}
            cursor.close()
        for v in r:
            result[v.get("category")] = v.get("url")

        hooklist = result

    return hooklist


"""
    This will tell us if the event is handled by code
    This list needs to be kept up to date otherwise events
    could end up in raw_events as well as the appropriate table

    It would be a good idea to add a flag to the database table
    so that the whitelist can tell us instead of maintaining a list here.
"""


def event_handled(event, gs):

    wl = [
        {
            "description": "FC Docked",
            "definition": {"event": "Docked", "StationType": "FleetCarrier"},
        },
        {
            "description": "Approached Settlements",
            "definition": {"event": "ApproachSettlement"},
        },
        {"description": "Promotion", "definition": {"event": "Promotion"}},
        {
            "description": "FC Jumped",
            "definition": {"event": "CarrierJump", "StationType": "FleetCarrier"},
        },
        {"description": "Organic Scans", "definition": {"event": "ScanOrganic"}},
        {"description": "Organic Sales", "definition": {"event": "SellOrganicData"}},
        {"description": "All Codex Events", "definition": {"event": "CodexEntry"}},
        {
            "description": "Signals Found Scanning Bodies",
            "definition": {"event": "SAASignalsFound"},
        },
        {
            "description": "Signals Found Scanning Bodies",
            "definition": {"event": "FSSBodySignals"},
        },
        {
            "description": "Commander event for codex reports",
            "definition": {"event": "Commander"},
        },
        {
            "description": "Cloud NSP",
            "definition": {
                "event": "FSSSignalDiscovered",
                "SignalName": "$Fixed_Event_Life_Cloud;",
            },
        },
        {
            "description": "Ring NSP",
            "definition": {
                "event": "FSSSignalDiscovered",
                "SignalName": "$Fixed_Event_Life_Ring;",
            },
        },
        {
            "description": "Belt NSP",
            "definition": {
                "event": "FSSSignalDiscovered",
                "SignalName": "$Fixed_Event_Life_Belt;",
            },
        },
        {
            "description": "Stations",
            "definition": {"event": "FSSSignalDiscovered", "IsStation": True},
        },
    ]
    return event_parse(wl, event, gs)


def event_parse(wl, event, gs):
    keycount = 0
    keymatch = 0
    for wlevent in wl:
        keycount = len(wlevent.get("definition").keys())
        for wlkey in wlevent.get("definition").keys():
            if event.get(wlkey) and event.get(wlkey) == wlevent["definition"].get(
                wlkey
            ):
                keymatch += 1
        if keymatch == keycount:
            return True
    logging.error("unknown event")
    logging.error(json.dumps(event))
    logging.error(json.dumps(gs))
    return False


def event_known(event, gs):
    wl = __get_whitelist()
    return event_parse(wl, event, gs)


def notNone(value):
    if value == "None":
        return ""
    else:
        return value


def insertCodexReport(request_args):
    """
    {
        "timestamp":"2019-09-02T22:15:55Z",
        "event":"CodexEntry",
        "EntryID":2100301,
        "Name":"$Codex_Ent_Cone_Name;",
        "Name_Localised":"Bark Mounds",
        "SubCategory":"$Codex_SubCategory_Organic_Structures;",
        "SubCategory_Localised":"Organic structures",
        "Category":"$Codex_Category_Biology;",
        "Category_Localised":"Biological and Geological",
        "Region":"$Codex_RegionName_18;",
        "Region_Localised":"Inner Orion Spur",
        "NearestDestination":"$SAA_Unknown_Signal:#type=$SAA_SignalType_Geological;:#index=9;",
        "System":"Pleiades Sector EA-Z b1",
        "SystemAddress":2869708727553
    }
    """

    cmdrName = (request_args.get("cmdr"),)
    system = (request_args.get("system"),)
    x = (request_args.get("x"),)
    y = (request_args.get("y"),)
    z = (request_args.get("z"),)
    latitude = (request_args.get("lat"),)
    longitude = (request_args.get("lon"),)
    body = (request_args.get("body"),)
    client = (request_args.get("client"),)
    if request_args.get("beta") == True:
        beta = "Y"
    else:
        beta = "N"
    raw_json = json.dumps(request_args.get("entry"))
    entryid = request_args.get("entry").get("EntryID")
    name = request_args.get("entry").get("Name")
    name_localised = request_args.get("entry").get("Name_Localised")
    category = request_args.get("entry").get("Category")
    category_localised = request_args.get("entry").get("Category_Localised")
    sub_category = request_args.get("entry").get("SubCategory")
    sub_category_localised = request_args.get("entry").get("SubCategory_Localised")
    region_name = request_args.get("entry").get("Region")
    region_name_localised = request_args.get("entry").get("Region_Localised")
    nearest_destination = request_args.get("entry").get("NearestDestination")
    reported_at = request_args.get("reported_at")
    platform = request_args.get("platform")
    odyssey = request_args.get("odyssey")
    id64 = request_args.get("entry").get("SystemAddress")
    temperature = request_args.get("temperature")

    index_id = None
    signal_type = None

    # if set and we have an index then we can decode
    if nearest_destination and "index" in nearest_destination:
        signal_type = None
        ndarray = nearest_destination.split("#")
        if len(ndarray) == 2:
            dummy, c = nearest_destination.split("#")
            dummy, index_id = c.split("=")
            index_id = index_id[:-1]
        else:
            dummy, b, c = nearest_destination.split("#")
            dummy, signal_type = b.split("=")
            dummy, index_id = c.split("=")
            signal_type = signal_type[:-1]
            index_id = index_id[:-1]

    # record the commender's find
    sqlstmt = """
        insert ignore into codex_cmdrs (cmdr,entryid)
        values (%s,%s)
    """
    with get_cursor() as cursor:
        cursor.execute(sqlstmt, (cmdrName, entryid))
        if cursor.rowcount == 1:
            print(f"Congratulations cmdr {cmdrName} you found {entryid}")

    # if there are 50 or more entries already we will skip writing
    with get_cursor() as cursor:
        cursor.execute(
            """
            select count(*) as quantity from (
            select 1 from codexreport c where c.system  = %s and ifnull(body,'nobody') = ifnull(%s,'nobody') and entryid = %s limit 50) data
        """,
            (system, body, entryid),
        )
        row = cursor.fetchone()
        quantity = row.get("quantity")
        if quantity == 50:
            cursor.close()
            return False

    hud, english_name = get_hud_category(entryid, name_localised)
    # Things that live in space do not need coordinates
    space_category = hud in ("Cloud", "Anomaly", "None", "Tourist")
    space_entry = entryid in (
        3101300,
        3200800,
        3100401,
        3100402,
        3100403,
        3100404,
        3100801,
        3100802,
        3100803,
        3100804,
        3100406,
        3100501,
        3100502,
        3100702,
    )

    if space_category or space_entry:
        print("Excluding Coordinates")
        latitude = None
        longitude = None

    with get_cursor() as cursor:
        cursor.execute(
            """
            insert ignore into codexreport (
                cmdrName,
                `system`,
                x,
                y,
                z,
                Body,
                latitude,
                longitude,
                entryid,
	            name,name_localised,
	            category,category_localised,
	            sub_category,sub_category_localised,
	            region_name,region_name_localised,
	            is_beta,
	            raw_json,
	            index_id,
	            signal_type,
	            clientVersion,
                reported_at,
                platform,
                odyssey,
                id64,
                temperature
	        ) values (
            	nullif(%s,''),
                nullif(%s,''),
                %s,
                %s,
                %s,
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                %s,
	            nullif(%s,''),
	            nullif(%s,''),
	            nullif(%s,''),
	            nullif(%s,''),
	            nullif(%s,''),
	            nullif(%s,''),
	            nullif(%s,''),
	            nullif(%s,''),
	            %s,
	            %s,
	            nullif(%s,''),
	            nullif(%s,''),
	            nullif(%s,''),
                str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'),
                nullif(%s,''),
	            nullif(%s,''),
	            nullif(%s,''),
                %s
                )""",
            (
                cmdrName,
                system,
                x,
                y,
                z,
                body,
                latitude,
                longitude,
                entryid,
                name,
                name_localised,
                category,
                category_localised,
                sub_category,
                sub_category_localised,
                region_name,
                region_name_localised,
                beta,
                raw_json,
                index_id,
                signal_type,
                client,
                reported_at,
                platform,
                odyssey,
                id64,
                temperature,
            ),
        )
        retval = False
        if cursor.rowcount == 1:
            retval = True

        cursor.close()
        return retval


def insertCodex(request_args):
    entryid = request_args.get("entry").get("EntryID")
    cmdrName = request_args.get("cmdr")
    system = request_args.get("system")
    name_localised = request_args.get("entry").get("Name_Localised")
    category_localised = request_args.get("entry").get("Category_Localised")
    sub_category_localised = request_args.get("entry").get("SubCategory_Localised")
    region = request_args.get("entry").get("Region_Localised")

    if name_localised is None:
        name_localised = (
            request_args.get("entry")
            .get("Name")
            .replace("$Codex_Ent_", "")
            .replace("_Name;", "")
            .replace("_", " ")
        )

    release = ""
    if request_args.get("odyssey") == "Y":
        release = " (Odyssey)"
    if request_args.get("odyssey") == "N":
        release = " (Horizons)"

    webhooks = get_webhooks()

    webhook = webhooks.get("Codex")

    stmt = "insert ignore into codex_entries (entryid) values(%s)"
    with get_cursor() as cursor:
        cursor.execute(stmt, (entryid))
        if cursor.rowcount == 1:
            canonnsearch = "https://canonn.science/?s="
            codexsearch = (
                "https://canonn-science.github.io/canonn-signals/index.html?system="
            )

            content = "Commander {} has discovered [{}](<{}{}>) ({}) in system [{}]({}{}) of region {} category: {} sub category: {}{}".format(
                cmdrName,
                name_localised,
                canonnsearch,
                quote_plus(name_localised),
                entryid,
                system,
                codexsearch,
                quote_plus(system),
                region,
                category_localised,
                sub_category_localised,
                release,
            )
            payload = {}
            payload["content"] = content

            requests.post(
                webhook,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        cursor.close()


def get_hud_category(entryid, name_localised):
    stmt = "select hud_category,english_name from codex_name_ref where entryid = %s"
    with get_cursor() as cursor:
        cursor.execute(stmt, (entryid))
        row = cursor.fetchone()
        if row:
            return row["hud_category"], row["english_name"]
        else:
            return "Unknown", name_localised
        cursor.close()


def insert_codex_systems(request_args):

    entryid = request_args.get("entry").get("EntryID")
    cmdrName = request_args.get("cmdr")
    system = request_args.get("system")
    name_localised = request_args.get("entry").get("Name_Localised")
    category_localised = request_args.get("entry").get("Category_Localised")
    sub_category_localised = request_args.get("entry").get("SubCategory_Localised")
    region = request_args.get("entry").get("Region_Localised")
    x = request_args.get("x")
    y = request_args.get("y")
    z = request_args.get("z")
    id64 = request_args.get("entry").get("SystemAddress")
    reported_at = request_args.get("entry").get("timestamp")

    if name_localised is None:
        name_localised = (
            request_args.get("entry")
            .get("Name")
            .replace("$Codex_Ent_", "")
            .replace("_Name;", "")
            .replace("_", " ")
        )

    hud, english_name = get_hud_category(entryid, name_localised)
    webhooks = get_webhooks()

    release = ""
    if request_args.get("odyssey") == "Y":
        release = " (Odyssey)"
    if request_args.get("odyssey") == "N":
        release = " (Horizons)"

    if hud != "Unknown":
        stmt = "insert ignore into codex_systems (`system`,x,y,z,entryid,z_order,system_address,cmdr,reported_at) values (%s,%s,%s,%s,%s,zorder(%s,%s,%s),%s,%s,str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'))"

        with get_cursor() as cursor:
            cursor.execute(
                stmt, (system, x, y, z, entryid, x, y, z, id64, cmdrName, reported_at)
            )
            if cursor.rowcount == 1:
                canonnsearch = "https://canonn.science/?s="
                codexsearch = (
                    "https://canonn-science.github.io/canonn-signals/index.html?system="
                )

                content = "Commander {} has discovered [{}](<{}{}>) ({}) in system [{}]({}{}) of region {} category: {} sub category: {} {}".format(
                    cmdrName,
                    english_name,
                    canonnsearch,
                    quote_plus(english_name),
                    entryid,
                    system,
                    codexsearch,
                    quote_plus(system),
                    region,
                    category_localised,
                    sub_category_localised,
                    release,
                )
                payload = {}
                payload["content"] = content
                requests.post(
                    webhooks.get(hud),
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                )
            cursor.close()


def get_records(value):

    if isinstance(value, list):
        # logging.info("Processing {} Containers".format(len(value)))
        return value
    else:
        # logging.info("Processing 1 Containers")
        return [value]


def get_events(one, many):
    if one:
        # logging.info("Processing 1 raw event")
        return [one]
    elif many:
        # logging.info("Processing {} raw events".format(len(many)))
        return many


def gamestate(row):
    gs = row.get("gameState")
    if "Journal Limpet" in gs.get("clientVersion"):
        gs["autoupdate"] = True
    return gs


def postCodex(payload):

    eventType = payload.get("eventType")
    entry = payload.get("entry")

    if eventType == "CodexEntry":
        name = entry.get("Name")
        stellar_bodies = entry.get("Category") == "$Codex_Category_StellarBodies;"
        green_giant = stellar_bodies and "Green" in name
        if not stellar_bodies or green_giant:
            retval = insertCodexReport(payload)
            insertCodex(payload)
            insert_codex_systems(payload)
        else:
            logging.info(f"Ignoring codex entry: {name}")
            return False

        if not retval:
            print(f"Too many entries {payload.get('system')} {payload.get('body')}")

        return retval

    else:
        return False


def extendCodex(gs, entry, cmdr):

    results = []
    if entry.get("event") == "CodexEntry":
        try:
            x, y, z = gs.get("systemCoordinates")
        except:
            logging.error(gs)
            logging.error(entry)
            logging.error("No System Coordinates")
            return results

        bodyname = gs.get("bodyName")
        if entry.get("BodyName"):
            bodyname = entry.get("bodyName")

        payload = {
            "eventType": entry.get("event"),
            "cmdr": cmdr,
            "beta": gs.get("isBeta"),
            "system": gs.get("systemName"),
            "station": gs.get("station"),
            "x": x,
            "y": y,
            "z": z,
            "body": gs.get("bodyName"),
            "lat": entry.get("Latitude") or gs.get("latitude"),
            "lon": entry.get("Longitude") or gs.get("longitude"),
            "entry": entry,
            "client": gs.get("clientVersion"),
            "reported_at": entry.get("timestamp"),
            "autoupdate": gs.get("autoupdate"),
            "platform": gs.get("platform"),
            "odyssey": is_odyssey(gs.get("odyssey")),
            "temperature": gs.get("temperature"),
        }
        if postCodex(payload):
            results.append(
                (
                    entry.get("event"),
                    cmdr,
                    gs.get("isBeta"),
                    gs.get("systemName"),
                    gs.get("station"),
                    x,
                    y,
                    z,
                    gs.get("bodyName"),
                    entry.get("Latitude") or gs.get("latitude"),
                    entry.get("Longitude") or gs.get("longitude"),
                    entry,
                    gs.get("clientVersion"),
                    entry.get("timestamp"),
                    gs.get("autoupdate"),
                )
            )
    return results


def extendCommanders(gs, event, cmdr):
    results = []
    if event.get("event") == "Commander":
        clientVersion = gs.get("clientVersion")
        reported_at = event.get("timestamp")

        if gs.get("autoupdate"):
            autoupdate = "Y"
        else:
            autoupdate = "N"

        if gs.get("isBeta") == True:
            beta = "Y"
        else:
            beta = "N"

        results.append((cmdr, clientVersion, reported_at, autoupdate, beta))

    return results


def extendLife(gs, event, cmdr):
    results = []

    clientVersion = gs.get("clientVersion")
    if "EDMC-Canonn" not in clientVersion:
        return results
    else:
        cname, v1, v2, v3 = clientVersion.split(".")

    # anything over 6.2 is good
    vNum = float(f"{v1}.{v2}")

    if vNum < 6.2:
        # print("Not accepting FSS events from < 6.2.0")
        return results

    if event.get("event") == "FSSSignalDiscovered":

        if gs.get("isBeta") == True:
            beta = "Y"
        else:
            beta = "N"

        signalName = event.get("SignalName")

        if "Fixed_Event_Life" in signalName:

            x, y, z = gs.get("systemCoordinates")
            sqlparm = (
                signalName,
                event.get("SignalNameLocalised"),
                cmdr,
                gs.get("systemName"),
                x,
                y,
                z,
                json.dumps(event),
                beta,
                gs.get("clientVersion"),
            )
            results.append(sqlparm)
    return results


def extendOrganicScans(gs, event, cmdr):
    results = []
    if event.get("event") == "ScanOrganic" and event.get("ScanType") in (
        "Log",
        "Sample",
    ):

        if gs.get("isBeta") == True:
            beta = "Y"
        else:
            beta = "N"

        timestamp = event.get("timestamp")
        clientVersion = gs.get("clientVersion")

        bodyName = event.get("BodyName")
        if not bodyName:
            bodyName = gs.get("bodyName")

        x, y, z = gs.get("systemCoordinates")

        # need to prevent too many entries being made
        with get_cursor() as cursor:
            cursor.execute(
                """
                select count(*) as quantity from (
                select 1 from organic_scans c where c.SystemAddress  = %s and ifnull(body,'nobody') = ifnull(%s,'nobody') and species = %s limit 50) data
            """,
                (event.get("SystemAddress"), bodyName, event.get("Species")),
            )
            row = cursor.fetchone()
            quantity = row.get("quantity")
            if quantity == 50:
                print(f"too many scans {gs.get('systemName')} body {bodyName}")
                return results
            else:
                print(f"{quantity} scans {gs.get('systemName')} body {bodyName}")
                sqlparm = (
                    cmdr,
                    gs.get("systemName"),
                    event.get("SystemAddress"),
                    bodyName,
                    event.get("Body"),
                    x,
                    y,
                    z,
                    gs.get("latitude"),
                    gs.get("longitude"),
                    event.get("ScanType"),
                    event.get("Species"),
                    event.get("Species_Localised"),
                    event.get("Genus"),
                    event.get("Genus_Localised"),
                    event.get("Variant"),
                    event.get("Variant_Localised"),
                    json.dumps(event),
                    clientVersion,
                    timestamp,
                    beta,
                    gs.get("temperature"),
                    gs.get("gravity"),
                )
                results.append(sqlparm)
    return results


def extendRawEvents(gs, entry, cmdr):
    results = []

    if event_known(entry, gs) and not event_handled(entry, gs):
        systemName = entry.get("StarSystem")
        if not systemName:
            systemName = gs.get("systemName")
        bodyName = entry.get("BodyName")
        if not bodyName:
            bodyName = gs.get("bodyName")

        try:
            x, y, z = gs.get("systemCoordinates")
        except:
            logging.error(f"x y z is null")
            logging.error(str(gs))
            x, y, z = [None, None, None]

        station = gs.get("station")
        lat = entry.get("Latitude")
        lon = entry.get("Longitude")
        if not lat:
            lat = gs.get("latitude")
            lon = gs.get("longitude")

        event = entry.get("event")
        timestamp = entry.get("timestamp")
        clientVersion = gs.get("clientVersion")

        results.append(
            (
                cmdr,
                systemName,
                bodyName,
                station,
                x,
                y,
                z,
                lat,
                lon,
                event,
                json.dumps(entry),
                clientVersion,
                timestamp,
            )
        )

    return results


def extendSettlements(gs, entry, cmdr):
    results = []

    if entry.get("event") == "ApproachSettlement":

        systemName = entry.get("StarSystem")
        if not systemName:
            systemName = gs.get("systemName")
        id64 = entry.get("SystemAddress")

        bodyName = entry.get("BodyName")

        if not bodyName:
            bodyName = gs.get("bodyName")

        bodyID = entry.get("BodyID")
        name = entry.get("Name")
        name_localised = entry.get("NameLocalised")
        market_id = entry.get("MarketID")

        x, y, z = gs.get("systemCoordinates")

        lat = entry.get("Latitude")
        lon = entry.get("Longitude")
        if not lat:
            lat = gs.get("latitude")
            lon = gs.get("longitude")

        event = entry.get("event")
        timestamp = entry.get("timestamp")
        clientVersion = gs.get("clientVersion")

        results.append(
            (
                cmdr,
                id64,
                systemName,
                bodyName,
                bodyID,
                name,
                name_localised,
                market_id,
                lat,
                lon,
                x,
                y,
                z,
                json.dumps(entry),
                clientVersion,
                timestamp,
            )
        )

    return results


# create an array of settlement values


def extendGuardianSettlements(gs, entry, cmdr):
    results = []

    if entry.get("event") == "ApproachSettlement":
        name = entry.get("Name")
        name_localised = entry.get("NameLocalised")

    if entry.get("event") == "CodexEntry":
        name = entry.get("NearestDestination")
        name_localised = entry.get("NearestDestination_Localised")

    # if set and we have an index then we can decode
    if entry.get("event") in ("CodexEntry", "ApproachSettlement"):
        if name and "index" in name:
            signal_type = None
            ndarray = name.split("#")
            if len(ndarray) == 2:
                dummy, c = name.split("#")
                dummy, index_id = c.split("=")
                index_id = index_id[:-1]
            else:
                dummy, b, c = name.split("#")
                dummy, signal_type = b.split("=")
                dummy, index_id = c.split("=")
                signal_type = signal_type[:-1]
                index_id = index_id[:-1]

    if (
        entry.get("event") in ("CodexEntry", "ApproachSettlement")
        and name
        and "$Ancient" in name
    ):

        market_id = entry.get("MarketID")
        systemName = entry.get("StarSystem")
        if not systemName:
            systemName = gs.get("systemName")
        id64 = entry.get("SystemAddress")

        bodyName = entry.get("BodyName")

        if not bodyName:
            bodyName = gs.get("bodyName")

        bodyID = entry.get("BodyID")
        if not bodyID:
            bodyID = gs.get("bodyId")

        market_id = entry.get("MarketID")

        x, y, z = gs.get("systemCoordinates")

        lat = entry.get("Latitude")
        lon = entry.get("Longitude")
        if not lat:
            lat = gs.get("latitude")
            lon = gs.get("longitude")

        event = entry.get("event")
        timestamp = entry.get("timestamp")
        clientVersion = gs.get("clientVersion")

        results.append(
            (
                cmdr,
                event,
                id64,
                systemName,
                bodyName,
                bodyID,
                name,
                name_localised,
                market_id,
                lat,
                lon,
                index_id,
                x,
                y,
                z,
                json.dumps(entry),
                clientVersion,
                timestamp,
            )
        )

    return results


def extendCarriersFSS(gs, event, cmdr):

    results = []

    clientVersion = gs.get("clientVersion")
    if "EDMC-Canonn" not in clientVersion:
        return results
    else:
        cname, v1, v2, v3 = clientVersion.split(".")

    # anything over 6.2 is good
    vNum = float(f"{v1}.{v2}")

    if vNum < 6.2:
        # print("Not accepting FSS events from < 6.2.0")
        return results

    bCarrierJump = (
        event.get("event") == "CarrierJump"
        and event.get("StationType") == "FleetCarrier"
    )
    bCarrierDock = (
        event.get("event") == "Docked" and event.get("StationType") == "FleetCarrier"
    )

    bFSSSignalDiscovered = event.get("event") == "FSSSignalDiscovered"

    bIsStation = event.get("IsStation")

    try:
        bFleetCarrier = (
            bFSSSignalDiscovered
            and bIsStation
            and event.get("SignalName")
            and event.get("SignalName")[-4] == "-"
            and event.get("SignalName")[-8] == " "
        )
    except:
        bFleetCarrier = False

    if bFleetCarrier or bCarrierJump or bCarrierDock:
        # logging.info("Fleet Carrier {}".format(event.get("SignalName")))

        serial_no = event.get("StationName")
        if not serial_no and bFleetCarrier:
            serial_no = event.get("SignalName")[-7:]

        name = None
        if bFleetCarrier:
            name = event.get("SignalName")[:-8]

        if event.get("StarSystem"):
            system = event.get("StarSystem")
        else:
            system = gs.get("systemName")

        if not system:
            logging.error(f"system is null")
            logging.error(str(gs))
            logging.error(str(event))
        else:

            x, y, z = gs.get("systemCoordinates")
            timestamp = event.get("timestamp")

            service_list = "unknown"
            if event.get("StationServices"):
                service_list = ",".join(event.get("StationServices"))

            ev = event.get("event")

            results.append(
                (
                    serial_no,
                    name,
                    timestamp,
                    system,
                    x,
                    y,
                    z,
                    json.dumps(service_list.split(",")),
                    serial_no,
                )
            )

    return results


def extendOrganicSales(gs, entry, cmdr):
    results = []
    if entry.get("event") == "SellOrganicData":
        x, y, z = gs.get("systemCoordinates")
        system = gs.get("systemName")
        body = gs.get("bodyName")
        station = gs.get("station")
        reported_at = entry.get("timestamp")
        market_id = entry.get("MarketID")
        clientVersion = gs.get("clientVersion")
        if gs.get("isBeta") == True:
            beta = "Y"
        else:
            beta = "N"

        for bioData in entry.get("BioData"):
            species = bioData.get("Species")
            genus = bioData.get("Genus")
            reward = bioData.get("Value")
            bonus = bioData.get("Bonus")

            results.append(
                (
                    cmdr,
                    system,
                    body,
                    station,
                    market_id,
                    species,
                    genus,
                    reward,
                    bonus,
                    clientVersion,
                    reported_at,
                    beta,
                    x,
                    y,
                    z,
                )
            )

    return results


def extendSignals(gs, event, cmdr):
    eventType = event.get("event")
    results = []

    if eventType in ("SAASignalsFound", "FSSBodySignals"):
        results = []
        signals = event.get("Signals")
        system = gs.get("systemName")
        system_address = event.get("SystemAddress")
        x, y, z = gs.get("systemCoordinates")
        body = event.get("BodyName")
        body_id = event.get("BodyID")
        signals = event.get("Signals")
        client = gs.get("clientVersion")
        if gs.get("odyssey") is None:
            odyssey = "X"
        if gs.get("odyssey") == True:
            odyssey = "Y"
        if gs.get("odyssey") == False:
            odyssey = "N"

        if gs.get("isBeta"):
            beta = "Y"
        else:
            beta = "N"

        for signal in signals:
            sigtype = signal.get("Type")
            if sigtype != "$SAA_SignalType_Human;":

                biology = sigtype == "$SAA_SignalType_Biological;"
                geology = sigtype == "$SAA_SignalType_Geological;"
                alien = (
                    sigtype == "$SAA_SignalType_Thargoid;"
                    or sigtype == "$SAA_SignalType_Guardian;"
                )

                if odyssey in ("N", "X") or alien:
                    update_type = "sites"
                elif odyssey == "Y" and (biology or geology):
                    update_type = "species"
                else:
                    update_type = "sites"

                type_localised = signal.get("Type_Localised")
                count = signal.get("Count")
                results.append(
                    (
                        cmdr,
                        system,
                        system_address,
                        x,
                        y,
                        z,
                        body,
                        body_id,
                        sigtype,
                        type_localised,
                        count,
                        client,
                        beta,
                        update_type,
                        count,
                        update_type,
                        count,
                        update_type,
                        count,
                        count,
                        count,
                        update_type,
                        count,
                    )
                )

            else:
                logging.info("Skipping Human Event")
    return results


def postRawEvents(values):
    return execute_many(
        "postRawEvents",
        """
            insert into raw_events (cmdrName,systemName,bodyName,station,x,y,z,lat,lon,event,raw_event,clientVersion,created_at)
            values (nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'))
        """,
        values,
    )


def postSettlements(values):
    return execute_many(
        "postSettlements",
        """
            insert ignore into settlements (cmdr,id64,systemName,bodyName,bodyid,Name,name_localised,market_id,lat,lon,x,y,z,raw_event,clientVersion,created_at)
            values (nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'))
        """,
        values,
    )


def postGuardianSettlements(values):
    return execute_many(
        "postGuardianSettlements",
        """
            insert ignore into guardian_settlements (cmdr,event,id64,systemName,bodyName,bodyid,Name,name_localised,market_id,lat,lon,index_id,x,y,z,raw_event,clientVersion,created_at)
            values (nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'))
        """,
        values,
    )


def updateNameRef():
    values = None

    return execute_many(
        "updateNameRef",
        """
            insert into codex_name_ref
            select name,entryid,category,sub_category,name_localised,'Biology' as hud_category,replace(name_components->"$.value[0]",'"','') as sub_class,'odyssey' as platform  from (
                select
                        v.*,
                        cast(concat('{"value": ["',replace(replace(replace(name,'$Codex_Ent_',''),'_Name;',''),'_','","'),'"]}') as json) as name_components,
                        cast(concat('{"species": "',replace(name_localised,' - ','","colour": "'),'"}') as json) as english_split
                from v_unknown_codex v
                ) data
                where replace(english_split->"$.colour",'"','') in (
                select distinct replace(english_split->"$.colour",'"','') as colour from (
                select replace(replace(name,'$Codex_Ent_',''),'_Name;','') as name,english_name ,
                cast(concat('{"species": "',replace(english_name,' - ','","colour": "'),'"}') as json) as english_split
                from codex_name_ref where platform = 'odyssey'
                order by 1
            ) data2
            )
        """,
        values,
    )


def postOrganicScans(values):

    return execute_many(
        "postOrganicScans",
        """
            insert ignore into organic_scans (
                cmdr,
                `system`,
                systemAddress,
                body,
                body_id,
                x,y,z,
                latitude,longitude,
                scantype,
                species,
                species_localised,
                genus,
                genus_localised,
                variant,
                variant_localised,
                raw_json,
                clientVersion,
                reported_at,
                is_beta,
                temperature,
                gravity)
            values (
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'),
                nullif(%s,''),
                %s,
                %s
                )
        """,
        values,
    )


def postOrganicSales(values):

    return execute_many(
        "postOrganicSales",
        """
            insert ignore into organic_sales (
                cmdr,
                `system`,
                body,
                station,
                market_id,
                species,
                genus,
                reward,
                bonus,
                client,
                reported_at,
                is_beta,x,y,z)
            values (
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                nullif(%s,''),
                str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'),
                nullif(%s,''),
                %s,
                %s,
                %s
                )
        """,
        values,
    )


def postLifeEvents(values):

    return execute_many(
        "postLifeEvents",
        """
            insert ignore into fss_events (signalname,signalNameLocalised,cmdr,`system`,x,y,z,raw_json,beta,clientVersion)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        values,
    )


def postCommanders(values):
    return execute_many(
        "postCommanders",
        """
            insert ignore into client_reports (cmdr,client,day,autoupdate,is_beta)
            values (%s,%s,date(str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ')),%s,%s)
        """,
        values,
    )


def postSignals(values):

    return execute_many(
        "postSignals",
        """
            insert into SAASignals (
                cmdr,
                `system`,
                system_address,
                x,y,z,
                body,
                body_id,
                type,
                type_localised,
                count,
                client,
                beta,
                species, #update_type
                sites    #update_type
            ) values (
                nullif(%s,''),             
                # system                
                nullif(%s,''),              
                %s,                                                    
                %s,%s,%s,                                              
                nullif(%s,''),                                         
                nullif(%s,''),                                         
                nullif(%s,''),                                         
                # type_localised
                nullif(%s,''),
                %s,
                # client
                nullif(%s,''),
                nullif(%s,''),                                         
                case when %s = 'species' then %s else null end,              
                case when %s = 'sites' then %s else null end               
            ) on duplicate key update 
                species = case
                    when %s = 'species' then %s                               #update_type,count
                    else species
                end,
                count = case
                    when %s > count then %s                                   #count count
                    else count
                end,
                sites = case
                    when %s = 'sites' then %s                               #update_type
                    else sites
                end
        """,
        values,
    )


def postCarriers(values):

    return execute_many(
        "postCarriers",
        """
            INSERT INTO fleet_carriers (
                serial_no,
                name,
                jump_dt,
                current_system,
                current_x,
                current_y,
                current_z,
                services,
                previous_system,
                previous_x,
                previous_y,
                previous_z,
                last_jump_dt
                )
                select * from ( SELECT
                    dummy.newserial,
                    ifnull(newname,name) as newname,
                    dummy.newdate,
                    dummy.newsystem,
                    dummy.newx,
                    dummy.newy,
                    dummy.newz,
                    case when dummy.newservices = 'unknown' then services else dummy.newservices end as newservices,
                    ifnull(current_system,dummy.newsystem) as oldsystem,
                    ifnull(current_x,dummy.newx) as oldx,
                    ifnull(current_y,dummy.newy )as oldy,
                    ifnull(current_z,dummy.newz) as oldz,
                    ifnull(jump_dt,dummy.newdate) as olddt
                from (  SELECT
                %s as newserial,
                %s as newname,
                str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ') as newdate,
                %s as newsystem,
                cast(%s as decimal(10,5)) as newx,
                cast(%s as decimal(10,5)) as newy,
                cast(%s as decimal(10,5)) as newz,
                %s as newservices from dual) dummy
            left join fleet_carriers on serial_no = %s  ) data
            ON DUPLICATE KEY UPDATE
                name = case when newdate > olddt then ifnull(newname,name) else name end,
                jump_dt = case when newdate > olddt then newdate else olddt end,
                current_system = case when newdate > olddt then newsystem else current_system end,
                current_x = case when newdate > olddt then newx else current_x end,
                current_y = case when newdate > olddt then newy else current_y end,
                current_z = case when newdate > olddt then newz else current_z end,
                services = case when newdate > olddt then newservices else services end,
                previous_system=case when
                    newdate > olddt and
                    newsystem != oldsystem
                    then oldsystem
                    else previous_system
                end,
                previous_x=case when
                    newdate > olddt and
                    newsystem != oldsystem
                    then oldx
                    else previous_x
                end,
                previous_y=case when
                    newdate > olddt and
                    newsystem != oldsystem
                    then oldy
                    else previous_y
                end,
                previous_z=case when
                    newdate > olddt and
                    newsystem != oldsystem
                    then oldz
                    else previous_z
                end,
                last_jump_dt=case when
                    newdate > olddt and
                    newsystem != oldsystem
                    then olddt
                    else last_jump_dt
                end;
        """,
        values,
    )


def collateCodex(values):
    value_count = len(values)
    retval = {"name": "collateCodex", "rows": value_count, "inserted": value_count}
    # updateNameRef()
    return retval


def execute_many(function, sqltext, sqlparm):
    try:
        value_count = len(sqlparm)
        retval = {"name": function, "rows": value_count, "inserted": 0}
        if value_count == 0:
            return retval

        with get_cursor() as cursor:
            cursor.executemany(sqltext, sqlparm)

            retval["inserted"] = cursor.rowcount
    except Exception as e:
        logging.exception("message")
        retval["error"] = str(e)

    return retval


def compress_results(values, rj):
    result = []
    for v in values:
        if int(v.get("rows")) > 0:
            result.append(v)

    if len(result) == 0:
        logging.info(rj)
    return result


def Promotion(gs, entry, cmdr):
    ranks = {
        "Exobiologist": [
            "Directionless",
            "Mostly Directionless",
            "Compiler",
            "Collector",
            "Cataloguer",
            "Taxonomist",
            "Ecologist",
            "Geneticist",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Soldier": [
            "Defenceless",
            "Mostly Defenceless",
            "Rookie",
            "Soldier",
            "Gunslinger",
            "Warrior",
            "Gladiator",
            "Deadeye",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Trade": [
            "Penniless",
            "Mostly Penniless",
            "Peddler",
            "Dealer",
            "Merchant",
            "Broker",
            "Entrepreneur",
            "Tycoon",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Combat": [
            "Harmless",
            "Mostly Harmless",
            "Novice",
            "Competent",
            "Expert",
            "Master",
            "Dangerous",
            "Deadly",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
        "Explore": [
            "Aimless",
            "Mostly Aimless",
            "Scout",
            "Surveyor",
            "Trailblazer",
            "Pathfinder",
            "Ranger",
            "Pioneer",
            "Elite",
            "Elite I",
            "Elite II",
            "Elite III",
            "Elite IV",
            "Elite V",
        ],
    }
    names = {
        "Explore": "Explorer",
        "Soldier": "Mercenary",
        "Trade": "Trade",
        "Combat": "Combat",
        "Exobiologist": "Exobiologist",
    }

    rank = None
    for k in ranks.keys():

        if entry.get(k) and ranks.get(k)[entry.get(k)]:
            rank = ranks.get(k)[entry.get(k)]
            role = names.get(k)

    if rank:
        webhooks = get_webhooks()
        webhook = webhooks.get("Promotion")

        payload = {}
        payload["content"] = (
            f"Congratulations Cmdr {cmdr} on your promotion to {role}: {rank}"
        )

        requests.post(
            webhook,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )


def buySuit(gs, entry, cmdr):
    try:
        suits = {
            "UtilitySuit": "Maverick",
            "ExplorationSuit": "Artemis",
            "TacticalSuit": "Dominator",
        }
        if entry.get("event") == "BuySuit":

            suit_type, suit_class = entry.get("Name").split("_")

            has_mods = entry.get("SuitMods") and len(entry.get("SuitMods")) > 0
            upper_class = not suit_class == "Class1"

            if has_mods or upper_class:

                suit_name = suits.get(suit_type)
                price = entry.get("Price")
                station = gs.get("station")
                system = gs.get("systemName")
                if not gs.get("station"):
                    station = gs.get("bodyName")
                content = f"**{suit_class} {suit_name} - ${price:,}**"
                content = f"{content}\nSystem: {system} - {station}"
                for suitmod in entry.get("SuitMods"):
                    content = f"{content}\n{suitmod}"

                webhooks = get_webhooks()
                webhook = webhooks.get("BuySuit")

                payload = {}
                payload["content"] = content

                requests.post(
                    webhook,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                )
    except Exception as e:
        logging.exception("message")
        raise


@app.route("/plugin/error", methods=["POST"])
@wrap_route
def plugin_error():
    webhook = get_webhooks().get("plugin_error")
    data = request.get_json(force=True)
    sqlinsert = """insert ignore into plugin_errors(
            system_name,
            function_name,
            error_text,
            client_version
        ) values (
            %s,
            %s,
            %s,
            %s
        )
    """
    cursor = get_cursor()
    cursor.execute(
        sqlinsert,
        (
            data.get("system_name"),
            data.get("function_name"),
            data.get("error_text"),
            data.get("clientVersion"),
        ),
    )
    rowcount = cursor.rowcount

    if rowcount == 1:

        excuse = generate_random_excuse()
        content = f"""Plugin error at [{data.get('system_name')}](https://signals.canonn.tech/?system={quote(data.get('system_name'))}) for {data.get('function_name')}()\nVersion: {data.get('clientVersion')}: {excuse}"""
        payload = {}
        payload["content"] = content
        requests.post(
            webhook,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    cursor.close()
    return f"inserted {rowcount} records"


@app.route("/", methods=["POST"])
@wrap_route
def entrywrap():

    headers = {"Content-Type": "application/json"}

    retval = {}

    if request.method != "POST":
        return (json.dumps({"error": "only POST operations allowed"}), 500, headers)

    setup_sql_conn()

    # get the records into a json
    rj = get_records(request.get_json(force=True))

    results = []
    saaevents = []
    fleet_carriers = []
    commanders = []
    lifevents = []
    rawevents = []
    codexevents = []
    clientversion = {}
    organicscans = []
    organicsales = []
    settlements = []
    guardian_settlements = []

    try:

        for row in rj:
            gs = gamestate(row)

            clientversion = {"client": gs.get("clientVersion")}

            cmdr = row.get("cmdrName")
            events = get_events(row.get("rawEvent"), row.get("rawEvents"))
            banned = "BETA" in cmdr
            notbeta = not gs.get("isBeta") or gs.get("isBeta") == "N"

            if notbeta and not banned:
                for event in events:

                    buySuit(gs, event, cmdr)
                    Promotion(gs, event, cmdr)

                    # we copy the events into arrays that can be bulk inserted
                    saaevents.extend(extendSignals(gs, event, cmdr))
                    fleet_carriers.extend(extendCarriersFSS(gs, event, cmdr))
                    commanders.extend(extendCommanders(gs, event, cmdr))
                    lifevents.extend(extendLife(gs, event, cmdr))
                    rawevents.extend(extendRawEvents(gs, event, cmdr))
                    settlements.extend(extendSettlements(gs, event, cmdr))
                    guardian_settlements.extend(
                        extendGuardianSettlements(gs, event, cmdr)
                    )
                    # we will actually post the codex events and collate results
                    codexevents.extend(extendCodex(gs, event, cmdr))
                    organicscans.extend(extendOrganicScans(gs, event, cmdr))
                    organicsales.extend(extendOrganicSales(gs, event, cmdr))
            else:
                logging.info("beta events")

        # once all arrays have been created we can call function to bulk insert
        # the results are gathered into an array for output
        results.append(postSignals(saaevents))
        results.append(postCarriers(fleet_carriers))
        results.append(postCommanders(commanders))
        results.append(postLifeEvents(lifevents))
        results.append(postRawEvents(rawevents))
        results.append(postSettlements(settlements))
        results.append(postGuardianSettlements(guardian_settlements))
        results.append(postOrganicScans(organicscans))
        results.append(postOrganicSales(organicsales))
        # codex events are already posted we just collate the results
        results.append(collateCodex(codexevents))
    except Exception as e:
        logging.error(rj)
        logging.exception("message")
        retval["error"] = str(e)

    retval = compress_results(results, rj)
    retval.append(clientversion)
    retval.append({"cmdr": cmdr})

    logging.info(retval)
    # we will always return 200 because errors
    # are logged and we want to stay in memory
    # print(json.dumps(retval, indent=4))
    return (json.dumps(retval), 200, headers)


@functions_framework.http
def payload(request):

    return "404 not found", 404
