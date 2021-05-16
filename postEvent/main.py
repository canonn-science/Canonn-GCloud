from pymysql.err import OperationalError
from flask import escape
import json
import logging
from math import pow, sqrt, trunc
from os import getenv
from urllib.parse import quote_plus
import requests
import pymysql
import sys

import google.cloud.logging
import logging

# Instantiates a client
glogclient = google.cloud.logging.Client()
glogclient.get_default_handler()
glogclient.setup_logging(log_level=logging.INFO)


# TODO(developer): specify SQL connection details
CONNECTION_NAME = getenv(
    'INSTANCE_CONNECTION_NAME',
    'canonn-api-236217:europe-north1:canonnpai')
DB_USER = getenv('MYSQL_USER', 'canonn')
DB_PASSWORD = getenv('MYSQL_PASSWORD', 'secret')
DB_NAME = getenv('MYSQL_DATABASE', 'canonn')
DB_HOST = getenv('MYSQL_HOST', 'localhost')

mysql_config = {
    'user': DB_USER,
    'password': DB_PASSWORD,
    'db': DB_NAME,
    'host': DB_HOST,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True
}

# Create SQL connection globally to enable reuse
# PyMySQL does not include support for connection pooling
mysql_conn = None

whitelist = []
hooklist = {}


def is_odyssey(value):
    if value is False:
        return "N"
    if value is True:
        return "Y"
    return


def __get_cursor():
    """
    Helper function to get a cursor
      PyMySQL does NOT automatically reconnect,
      so we must reconnect explicitly using ping()
    """
    try:
        return mysql_conn.cursor()
    except OperationalError:
        mysql_conn.ping(reconnect=True)
        return mysql_conn.cursor()


def __get_whitelist():
    global whitelist
    if not whitelist:
        with __get_cursor() as cursor:
            sql = """select * from postEvent_whitelist"""
            cursor.execute(sql, ())
            r = cursor.fetchall()
            result = []
            cursor.close()
        for v in r:
            result.append({"description": v.get("description"),
                           "definition": json.loads(v.get("definition"))})
        whitelist = result

    return whitelist


def get_webhooks():
    global hooklist
    if not hooklist:
        with __get_cursor() as cursor:
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


def event_handled(event):

    wl = [
        {"description": "Organic Scans", "definition": {"event": "ScanOrganic"}},
        {"description": "All Codex Events", "definition": {"event": "CodexEntry"}},
        {"description": "Signals Found Scanning Bodies",
            "definition": {"event": "SAASignalsFound"}},
        {"description": "Commander event for codex reports",
            "definition": {"event": "Commander"}},
        {"description": "Cloud NSP", "definition": {
            "event": "FSSSignalDiscovered", "SignalName": "$Fixed_Event_Life_Cloud;"}},
        {"description": "Ring NSP", "definition": {
            "event": "FSSSignalDiscovered", "SignalName": "$Fixed_Event_Life_Ring;"}},
        {"description": "Belt NSP", "definition": {"event": "FSSSignalDiscovered",
                                                   "SignalName": "$Fixed_Event_Life_Belt;"}},
        {"description": "Stations",            "definition": {
            "event": "FSSSignalDiscovered",                "IsStation": True}},
    ]
    return event_parse(wl, event)


def event_parse(wl, event):
    keycount = 0
    keymatch = 0
    for wlevent in wl:
        keycount = len(wlevent.get("definition").keys())
        for wlkey in wlevent.get("definition").keys():
            if event.get(wlkey) and event.get(wlkey) == wlevent["definition"].get(wlkey):
                keymatch += 1
        if keymatch == keycount:
            return True
    logging.error(json.dumps(wl))
    return False


def event_known(event):
    wl = __get_whitelist()
    return event_parse(wl, event)


def notNone(value):
    if value == 'None':
        return ''
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

    cmdrName = request_args.get("cmdr"),
    system = request_args.get("system"),
    x = request_args.get("x"),
    y = request_args.get("y"),
    z = request_args.get("z"),
    latitude = request_args.get("lat"),
    longitude = request_args.get("lon"),
    body = request_args.get("body"),
    client = request_args.get("client"),
    if request_args.get("beta") == True:
        beta = 'Y'
    else:
        beta = 'N'
    raw_json = json.dumps(request_args.get("entry"))
    entryid = request_args.get("entry").get("EntryID")
    name = request_args.get("entry").get("Name")
    name_localised = request_args.get("entry").get("Name_Localised")
    category = request_args.get("entry").get("Category")
    category_localised = request_args.get("entry").get("Category_Localised")
    sub_category = request_args.get("entry").get("SubCategory")
    sub_category_localised = request_args.get(
        "entry").get("SubCategory_Localised")
    region_name = request_args.get("entry").get("Region")
    region_name_localised = request_args.get("entry").get("Region_Localised")
    nearest_destination = request_args.get("entry").get("NearestDestination")
    reported_at = request_args.get("reported_at")
    platform = request_args.get("platform")
    odyssey = request_args.get("odyssey")
    id64 = request_args.get("entry").get("SystemAddress")

    index_id = None
    signal_type = None

    # if set and we have an index then we can decode
    if nearest_destination and "index" in nearest_destination:
        signal_type = None
        ndarray = nearest_destination.split('#')
        if len(ndarray) == 2:
            dummy, c = nearest_destination.split('#')
            dummy, index_id = c.split("=")
            index_id = index_id[:-1]
        else:
            dummy, b, c = nearest_destination.split('#')
            dummy, signal_type = b.split("=")
            dummy, index_id = c.split("=")
            signal_type = signal_type[:-1]
            index_id = index_id[:-1]

    with __get_cursor() as cursor:
        cursor.execute('''
            insert into codexreport (
                cmdrName,
                system,
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
                id64
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
	            nullif(%s,'')
                )''', (
            cmdrName,
            system,
            x,
            y,
            z,
            body,
            latitude,
            longitude,
            entryid,
            name, name_localised,
            category, category_localised,
            sub_category, sub_category_localised,
            region_name, region_name_localised,
            beta,
            raw_json,
            index_id,
            signal_type,
            client,
            reported_at,
            platform,
            odyssey,
            id64
        ))
        mysql_conn.commit()
        cursor.close()


def insertCodex(request_args):
    entryid = request_args.get("entry").get("EntryID")
    cmdrName = request_args.get("cmdr")
    system = request_args.get("system")
    name_localised = request_args.get("entry").get("Name_Localised")
    category_localised = request_args.get("entry").get("Category_Localised")
    sub_category_localised = request_args.get(
        "entry").get("SubCategory_Localised")
    region = request_args.get("entry").get("Region_Localised")

    webhooks = get_webhooks()

    webhook = webhooks.get("Codex")

    stmt = 'insert ignore into codex_entries (entryid) values(%s)'
    with __get_cursor() as cursor:
        cursor.execute(stmt, (entryid))
        if cursor.rowcount == 1:
            canonnsearch = "https://canonn.science/?s="
            codexsearch = "https://tools.canonn.tech/Signals/?system="

            content = "@here Commander {} has discovered [{}](<{}{}>) ({}) in system [{}]({}{}) of region {} category: {} sub category: {}".format(
                cmdrName, name_localised, canonnsearch, quote_plus(
                    name_localised),
                entryid, system, codexsearch, quote_plus(system),
                region, category_localised, sub_category_localised)
            payload = {}
            payload["content"] = content

            requests.post(webhook, data=json.dumps(payload), headers={
                "Content-Type": "application/json"})
        cursor.close()


def get_hud_category(entryid, name_localised):
    stmt = "select hud_category,english_name from codex_name_ref where entryid = %s"
    with __get_cursor() as cursor:
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
    sub_category_localised = request_args.get(
        "entry").get("SubCategory_Localised")
    region = request_args.get("entry").get("Region_Localised")
    x = request_args.get("x")
    y = request_args.get("y")
    z = request_args.get("z")

    hud, english_name = get_hud_category(entryid, name_localised)
    webhooks = get_webhooks()

    if hud != 'Unknown':
        stmt = "insert ignore into codex_systems (system,x,y,z,entryid) values (%s,%s,%s,%s,%s)"

        with __get_cursor() as cursor:
            cursor.execute(stmt, (system, x, y, z, entryid))
            if cursor.rowcount == 1:
                canonnsearch = "https://canonn.science/?s="
                codexsearch = "https://tools.canonn.tech/Signals/?system="

                content = "Commander {} has discovered [{}](<{}{}>) ({}) in system [{}]({}{}) of region {} category: {} sub category: {}".format(
                    cmdrName, english_name, canonnsearch, quote_plus(
                        english_name),
                    entryid, system, codexsearch, quote_plus(system),
                    region, category_localised, sub_category_localised)
                payload = {}
                payload["content"] = content
                requests.post(webhooks.get(hud), data=json.dumps(
                    payload), headers={"Content-Type": "application/json"})
            cursor.close()


def setup_sql_conn():
    global mysql_conn
    # Initialize connections lazily, in case SQL access isn't needed for this
    # GCF instance. Doing so minimizes the number of active SQL connections,
    # which helps keep your GCF instances under SQL connection limits.
    if not mysql_conn:
        try:
            mysql_conn = pymysql.connect(**mysql_config)
        except OperationalError:
            # If production settings fail, use local development ones
            mysql_config['unix_socket'] = f'/cloudsql/{CONNECTION_NAME}'
            mysql_conn = pymysql.connect(**mysql_config)
    mysql_conn.ping()


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
    if 'Journal Limpet' in gs.get("clientVersion"):
        gs["autoupdate"] = True
    return gs


def postCodex(payload):
    eventType = payload.get("eventType")
    entry = payload.get("entry")

    if eventType == "CodexEntry":
        name = entry.get("Name")
        stellar_bodies = (entry.get("Category") ==
                          '$Codex_Category_StellarBodies;')
        green_giant = (stellar_bodies and "Green" in name)
        if not stellar_bodies or green_giant:
            insertCodexReport(payload)
            insertCodex(payload)
            insert_codex_systems(payload)
        else:
            logging.info(f"Ignoring codex entry: {name}")

        return True
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
            "lat": gs.get("latitude"),
            "lon": gs.get("longitude"),
            "entry": entry,
            "client": gs.get("clientVersion"),
            "reported_at": entry.get("timestamp"),
            "autoupdate": gs.get("autoupdate"),
            "platform": gs.get("platform"),
            "odyssey": is_odyssey(gs.get("odyssey"))
        }
        if postCodex(payload):
            results.append((
                entry.get("event"),
                cmdr,
                gs.get("isBeta"),
                gs.get("systemName"),
                gs.get("station"),
                x,
                y,
                z,
                gs.get("bodyName"),
                gs.get("latitude"),
                gs.get("longitude"),
                entry,
                gs.get("clientVersion"),
                entry.get("timestamp"),
                gs.get("autoupdate"))
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
            beta = 'Y'
        else:
            beta = 'N'

        results.append((cmdr, clientVersion, reported_at, autoupdate, beta))

    return results


def extendLife(gs, event, cmdr):
    results = []
    if event.get("event") == "FSSSignalDiscovered":

        if gs.get("isBeta") == True:
            beta = 'Y'
        else:
            beta = 'N'

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
                gs.get("clientVersion")
            )
            results.append(sqlparm)
    return results


def extendOrganicScans(gs, event, cmdr):
    results = []
    if event.get("event") == "ScanOrganic":

        if gs.get("isBeta") == True:
            beta = 'Y'
        else:
            beta = 'N'

        timestamp = event.get("timestamp")
        clientVersion = gs.get("clientVersion")

        bodyName = event.get("BodyName")
        if not bodyName:
            bodyName = gs.get("bodyName")

        x, y, z = gs.get("systemCoordinates")

        sqlparm = (
            cmdr,
            gs.get("systemName"),
            event.get("systemAddress"),
            bodyName,
            event.get("Body"),
            x, y, z,
            gs.get("latitude"),
            gs.get("longitude"),
            event.get("ScanType"),
            event.get("Species"),
            event.get("Species_Localised"),
            event.get("Genus"),
            event.get("Genus_Localised"),
            json.dumps(event),
            clientVersion,
            timestamp,
            beta
        )
        results.append(sqlparm)
    return results


def extendRawEvents(gs, entry, cmdr):
    results = []

    if event_known(entry) and not event_handled(entry):
        systemName = entry.get("StarSystem")
        if not systemName:
            systemName = gs.get("systemName")
        bodyName = entry.get("BodyName")
        if not bodyName:
            bodyName = gs.get("bodyName")

        x, y, z = gs.get("systemCoordinates")
        station = None
        lat = entry.get("Latitude")
        lon = entry.get("Longitude")
        if not lat:
            lat = gs.get("latitude")
            lon = gs.get("longitude")

        event = entry.get("event")
        timestamp = entry.get("timestamp")
        clientVersion = gs.get("clientVersion")

        results.append(
            (cmdr, systemName, bodyName, station, x, y, z,
             lat, lon, event, json.dumps(entry), clientVersion, timestamp)
        )

    return results


def extendCarriersFSS(gs, event, cmdr):
    results = []

    bFSSSignalDiscovered = (event.get("event") == "FSSSignalDiscovered")
    bIsStation = event.get("IsStation")

    try:
        bFleetCarrier = (
            bFSSSignalDiscovered and
            bIsStation and
            event.get("SignalName") and
            event.get("SignalName")[-4] == '-' and
            event.get("SignalName")[-8] == ' '
        )
    except:
        bFleetCarrier = False

    if bFleetCarrier:
        # logging.info("Fleet Carrier {}".format(event.get("SignalName")))

        serial_no = event.get("SignalName")[-7:]
        name = event.get("SignalName")[:-8]
        system = gs.get("systemName")
        x, y, z = gs.get("systemCoordinates")
        timestamp = event.get("timestamp")
        service_list = "unknown"

        results.append((serial_no, name, timestamp, system,
                        x, y, z, service_list, serial_no))

    return results


def extendSignals(gs, event, cmdr):
    eventType = event.get("event")
    results = []

    if eventType == "SAASignalsFound":
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
            odyssey = 'X'
        if gs.get("odyssey") == True:
            odyssey = 'Y'
        if gs.get("odyssey") == False:
            odyssey = 'N'

        if gs.get("isBeta"):
            beta = 'Y'
        else:
            beta = 'N'

        for signal in signals:
            if signal.get("Type") != '$SAA_SignalType_Human;':

                sigtype = signal.get("Type"),
                type_localised = signal.get("Type_Localised"),
                count = signal.get("Count"),
                results.append((cmdr, system, system_address, x, y, z, body, body_id, sigtype, type_localised,
                                odyssey, count, client, beta, odyssey, count, odyssey, count, odyssey, count, odyssey, count, odyssey, count))

            else:
                logging.info("Skipping Human Event")
    return results


def postRawEvents(values):
    return execute_many("postRawEvents",
                        """
            insert into raw_events (cmdrName,systemName,bodyName,station,x,y,z,lat,lon,event,raw_event,clientVersion,created_at)
            values (nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),nullif(%s,''),str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'))
        """,
                        values
                        )


def postOrganicScans(values):

    return execute_many("postOrganicScans",
                        """
            insert into organic_scans (
                cmdr,
                system,
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
                raw_json,
                clientVersion,
                reported_at,
                is_beta)
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
                str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ'),
                nullif(%s,'')
                )
        """,
                        values
                        )


def postLifeEvents(values):

    return execute_many("postLifeEvents",
                        """
            insert ignore into fss_events (signalname,signalNameLocalised,cmdr,system,x,y,z,raw_json,beta,clientVersion)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
                        values
                        )


def postCommanders(values):
    return execute_many("postCommanders",
                        """
            insert ignore into client_reports (cmdr,client,day,autoupdate,is_beta)
            values (%s,%s,date(str_to_date(%s,'%%Y-%%m-%%dT%%H:%%i:%%SZ')),%s,%s)
        """,
                        values
                        )


def postSignals(values):

    return execute_many("postSignals",
                        """
            insert into SAASignals (
                cmdr,
                system,
                system_address,
                x,y,z,
                body,
                body_id,
                type,
                type_localised,
                count,
                client,
                beta,
                species,
                sites
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
                case when %s = 'N' then %s else null end,              
                # client
                nullif(%s,''),
                nullif(%s,''),                                         
                case when %s = 'Y' then %s else null end,              
                case when %s = 'X' then %s else null end               
            ) on duplicate key update 
                species = case
                    when %s = 'Y' then %s                               
                    else species
                end,
                count = case
                    when %s = 'N' then %s                               
                    else count
                end,
                sites = case
                    when %s = 'X' then %s                               
                    else sites
                end
        """,
                        values
                        )


def postCarriers(values):

    return execute_many("postCarriers",
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
                        values
                        )


def collateCodex(values):
    value_count = len(values)
    retval = {
        "name": "collateCodex",
        "rows": value_count,
        "inserted": value_count
    }
    return retval


def execute_many(function, sqltext, sqlparm):
    global mysql_conn
    try:
        value_count = len(sqlparm)
        retval = {
            "name": function,
            "rows": value_count,
            "inserted": 0
        }
        if value_count == 0:
            return retval

        with __get_cursor() as cursor:
            cursor.executemany(
                sqltext,
                sqlparm
            )
            mysql_conn.commit()
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


def entrypoint(request):
    retval = {}
    try:
        return entrywrap(request)
    except:
        headers = {
            'Content-Type': 'application/json'
        }

        retval["error"] = "Error in entrypoint: check google cloud log explorer"
        logging.exception("message")
        return (json.dumps(retval), 500, headers)


def entrywrap(request):

    headers = {
        'Content-Type': 'application/json'
    }

    if request.method != 'POST':
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

    try:

        for row in rj:
            gs = gamestate(row)

            clientversion = {"client": gs.get("clientVersion")}

            cmdr = row.get("cmdrName")
            events = get_events(row.get("rawEvent"), row.get("rawEvents"))

            logging.debug(gs.get("isBeta"))
            if not gs.get("isBeta"):
                for event in events:
                    # we copy the events into arrays that can be bulk inserted
                    saaevents.extend(extendSignals(gs, event, cmdr))
                    fleet_carriers.extend(extendCarriersFSS(gs, event, cmdr))
                    commanders.extend(extendCommanders(gs, event, cmdr))
                    lifevents.extend(extendLife(gs, event, cmdr))
                    rawevents.extend(extendRawEvents(gs, event, cmdr))
                    # we will actually post the codex events and collate results
                    codexevents.extend(extendCodex(gs, event, cmdr))
                    organicscans.extend(extendOrganicScans(gs, event, cmdr))
            else:
                logging.info("beta events")

        # once all arrays have been created we can call function to bulk insert
        # the results are gathered into an array for output
        results.append(postSignals(saaevents))
        results.append(postCarriers(fleet_carriers))
        results.append(postCommanders(commanders))
        results.append(postLifeEvents(lifevents))
        results.append(postRawEvents(rawevents))
        results.append(postOrganicScans(organicscans))
        # codex events are already posted we just collate the results
        results.append(collateCodex(codexevents))
    except:
        logging.error(rj)
        logging.exception("message")

    retval = compress_results(results, rj)
    retval.append(clientversion)
    logging.info(retval)
    # we will always return 200 because errors
    # are logged and we want to stay in memory
    return (json.dumps(retval), 200, headers)
