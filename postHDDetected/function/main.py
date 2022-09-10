from calendar import monthcalendar
import requests
import json
from flask import escape
from os import getenv
import pymysql
from pymysql.err import OperationalError
from math import sqrt, pow, trunc

import google.cloud.logging
import logging

# Instantiates a client
glogclient = google.cloud.logging.Client()
glogclient.get_default_handler()
glogclient.setup_logging()

# TODO(developer): specify SQL connection details
CONNECTION_NAME = getenv(
    'INSTANCE_CONNECTION_NAME',
    'XXX')
DB_USER = getenv('MYSQL_USER', 'canonn')
DB_PASSWORD = getenv('MYSQL_PASSWORD', 'FROM_ENV')
DB_NAME = getenv('MYSQL_DATABASE', 'canonn')

mysql_config = {
    'user': DB_USER,
    'password': DB_PASSWORD,
    'db': DB_NAME,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True
}

# Create SQL connection globally to enable reuse
# PyMySQL does not include support for connection pooling
mysql_conn = None
discordurl = None


def gethook():
    global discordurl
    if not discordurl:
        with open('secret.json') as f:
            discordurl = json.load(f)


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


def notNone(value):
    if value == 'None':
        return ''
    else:
        return value


def insertReport(r):
    system = r.get("system"),
    # timestamp":"2019-10-11T15:47:06Z"
    timestamp = r.get("timestamp").replace('T', ' ').replace('Z', ''),
    cmdr = r.get("cmdr"),
    game = r.get("odyssey")
    hostile = ""
    if r.get("hostile") is not None:
        if r.get("hostile"):
            hostile = 'Y'
        else:
            hostile = 'N'

    with __get_cursor() as cursor:
        # '9999-12-31 23:59:59'
        # timestamp":"2019-10-11T15:47:06Z"
        sql = """
        	INSERT ignore INTO hd_detected (cmdr,system,timestamp,x,y,z,destination,dx,dy,dz,client,odyssey,hostile) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(sql, (cmdr, system, timestamp, r.get("x"), r.get("y"), r.get(
            "z"), r.get("destination"), r.get("dx"), r.get("dy"), r.get("dz"), r.get("client"), game, hostile))

        mysql_conn.commit()

        cursor.execute('insert ignore into hdsystems (systemName,x,y,z) values (%s,%s,%s,%s)',
                       (system, r.get("x"), r.get("y"), r.get("z")))
        mysql_conn.commit()


SOL = [0, 0, 0]
MEROPE = [-78.59375, -149.625, -340.53125]
COALSACK = [423.5625, 0.5, 277.75]  # Musca Dark Region PJ-P b6-8
WITCHHEAD = [355.75, -400.5, -707.21875]  # Ronemar
CALIFORNIA = [-299.0625, -229.25, -876.125]  # HIP 18390
CONESECTOR = [609.4375, 154.25, -1503.59375]  # Outotz ST-I d9-4


def getDistance(a, b):
    return sqrt(pow(a[0]-b[0], 2)+pow(a[1]-b[1], 2)+pow(a[2]-b[2], 2))


def is_notable(nearest):
    with __get_cursor() as cursor:
        cursor.execute("select * from v_hdsystems_limits", ())
        limits = cursor.fetchone()

    logging.info(limits)

    if nearest.get("name") == "Sol" and float(nearest.get("distance")) < float(limits.get("min_sol")):
        return True
    if nearest.get("name") == "Merope" and float(nearest.get("distance")) > float(limits.get("max_merope")):
        return True
    if nearest.get("name") == "Coalsack" and float(nearest.get("distance")) > float(limits.get("max_coalsack")):
        return True
    if nearest.get("name") == "Witchhead" and float(nearest.get("distance")) > float(limits.get("max_witchhead")):
        return True
    if nearest.get("name") == "California" and float(nearest.get("distance")) > float(limits.get("max_california")):
        return True
    if nearest.get("name") == "Cone Sector" and float(nearest.get("distance")) > float(limits.get("max_conesector")):
        return True

    return False


def getNearest(r):
    x = r.get("x")
    y = r.get("y")
    z = r.get("z")
    d = [
        {"name": "Sol", "distance": getDistance(
            [x, y, z], SOL), "coords": SOL},
        {"name": "Merope", "distance": getDistance(
            [x, y, z], MEROPE), "coords": MEROPE},
        {"name": "Coalsack", "distance": getDistance(
            [x, y, z], COALSACK), "coords": COALSACK},
        {"name": "Witchhead", "distance": getDistance(
            [x, y, z], WITCHHEAD), "coords": WITCHHEAD},
        {"name": "California", "distance": getDistance(
            [x, y, z], CALIFORNIA), "coords": CALIFORNIA},
        {"name": "Cone Sector", "distance": getDistance(
            [x, y, z], CONESECTOR), "coords": CONESECTOR},
    ]
    d.sort(key=lambda dx: dx["distance"], reverse=False)
    logging.info(d[0])
    return d[0]


def hdExists(r):
    s = r.get("system")
    sqltext = """
        select * FROM (SELECT 1 AS c FROM hdreports WHERE systemName = %s LIMIT 1) a
        union
        select * FROM (SELECT 1 AS c FROM hd_detected where system = %s LIMIT 1) b
        union
        select * FROM (SELECT 1 AS c FROM hd_monitor where system = %s LIMIT 1) c
        union
        select * FROM (SELECT 1 AS c FROM hdsystems where systemName = %s LIMIT 1) d
    """
    with __get_cursor() as cursor:
        # '9999-12-31 23:59:59'
        # timestamp":"2019-10-11T15:47:06Z"
        cursor.execute(sqltext, (s, s, s, s))
        result = cursor.fetchone()

    if result:
        return True
    else:
        return False


def getJumpDistance(r):
    a = [float(r.get("x")), float(r.get("y")), float(r.get("z"))]
    b = [float(r.get("dx")), float(r.get("dy")), float(r.get("dz"))]
    return round(getDistance(a, b), 2)


def postDiscord(n, r):
    logging.info("posting to discord")
    global discordurl
    gethook()

    data = {}

    cmdr = r.get("cmdr")
    system = r.get("system")
    destination = r.get("destination")
    distance = trunc(n.get("distance"))
    ref = n.get("name")
    jump = getJumpDistance(r)
    ref_coords = n.get("coords")
    dest_distance = round(getDistance(
        ref_coords, [float(r.get("dx")), float(r.get("dy")), float(r.get("dz"))]), 1)
    url = discordurl.get("url")

    game = ""
    if r.get("odyssey"):
        if r.get("odyssey") == 'Y':
            game = " (Odyssey)"
        if r.get("odyssey") == 'N':
            game = " (Horizons)"

    hostile = " "
    if r.get("hostile"):
        logging.info("hostile hyperdiction")
        hostile = " hostile "

    # we only got accurate xyz when client was added so we will skip old versions

    content = f"Commander {cmdr} reporting{hostile}hyperdiction at {system} while jumping {jump}ly to {destination}. The hyperdiction was {distance}ly from {ref}, the destination was {dest_distance} from {ref}.{game}"

    #ishostile = (r.get("hostile") and r.get("hostile") == 'Y')
    #notable = (is_notable(n) or ishostile)

    if is_notable(n) and system != "TEST":
        data["content"] = f"@here {content}"
    else:
        data["content"] = content

    r = requests.post(url, data=json.dumps(data), headers={
                      "Content-Type": "application/json"})


def payload(request):
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

    request_json = request.get_json(force=True)
    request_args = request.args

    # insertReport(request_args)
    headers = {
        'Content-Type': 'application/json'
    }

    hdFound = hdExists(request_json)
    nearest = getNearest(request_json)

    ishostile = (request_json.get("hostile")
                 and request_json.get("hostile") == 'Y')

    if ishostile:
        logging.info("hostile hyperdiction")
    else:
        logging.info("pacific hyperdiction")

    hdNotFound = (not hdFound)

    if hdNotFound or ishostile:
        postDiscord(nearest, request_json)

    insertReport(request_json)

    if request.method == 'POST':
        return (json.dumps(request_json), 200, headers)
    else:
        return (json.dumps({"error": "only POST operations allowed"}), 500, headers)
