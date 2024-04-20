import requests
import json
from flask import escape
from os import getenv
import pymysql
from pymysql.err import OperationalError
from math import sqrt, pow, trunc

import google.cloud.logging
import logging
import functions_framework

# Instantiates a client
glogclient = google.cloud.logging.Client()
glogclient.get_default_handler()
glogclient.setup_logging()

# TODO(developer): specify SQL connection details
CONNECTION_NAME = getenv(
    'INSTANCE_CONNECTION_NAME',
    'canonn-api-236217:europe-north1:canonnpai')
DB_USER = getenv('MYSQL_USER', 'canonn')
DB_PASSWORD = getenv('MYSQL_PASSWORD', 'This is not it')
DB_NAME = getenv('MYSQL_DATABASE', 'canonn')

hooklist = {}


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
        cursor.execute("select * from v_nhsssystems_limits", ())
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
    x = float(r.get("x"))
    y = float(r.get("y"))
    z = float(r.get("z"))
    d = [
        {"name": "Sol", "distance": getDistance([x, y, z], SOL)},
        {"name": "Merope", "distance": getDistance([x, y, z], MEROPE)},
        {"name": "Coalsack", "distance": getDistance([x, y, z], COALSACK)},
        {"name": "Witchhead", "distance": getDistance([x, y, z], WITCHHEAD)},
        {"name": "California", "distance": getDistance([x, y, z], CALIFORNIA)},
        {"name": "Cone Sector", "distance": getDistance(
            [x, y, z], CONESECTOR)},
    ]
    d.sort(key=lambda dx: dx["distance"], reverse=False)
    logging.info(d[0])
    return d[0]


def nhssExists(r):
    s = r.get("systemName")
    sqltext = """
        select * FROM (SELECT 1 AS c FROM nhsssystems where systemName = %s LIMIT 1) d
    """
    with __get_cursor() as cursor:
        #'9999-12-31 23:59:59'
        # timestamp":"2019-10-11T15:47:06Z"
        cursor.execute(sqltext, (s))
        result = cursor.fetchone()

    if result:
        return True
    else:
        return False


def postDiscord(n, r):
    logging.info("posting to discord")

    data = {}

    cmdr = r.get("cmdrName")
    system = r.get("systemName")
    distance = trunc(n.get("distance"))
    ref = n.get("name")
    threat_level = int(r.get("threat_level"))

    webhooks = get_webhooks()
    url = webhooks.get("NHSS")

    if is_notable(n):
        data["content"] = f"@here Commander {cmdr} found a non-human signal source in {system}. Located {distance}ly from {ref}"
    else:
        data["content"] = f"Commander {cmdr} found a non-human signal source in {system}. Located {distance}ly from {ref}"

    if threat_level < 3:
        data["content"] = f"@here Commander {cmdr} found a threat_level {threat_level} non-human signal source in {system}. Located {distance}ly from {ref}"

    r = requests.post(url, data=json.dumps(data), headers={
                      "Content-Type": "application/json"})


def insertReport(request_args):
    systemName = request_args.get("systemName")
    cmdrName = request_args.get("cmdrName")
    x = request_args.get("x")
    y = request_args.get("y")
    z = request_args.get("z")
    threat_level = int(request_args.get("threat_level"))

    with __get_cursor() as cursor:
        cursor.execute('insert ignore into nhsssystems (systemName,x,y,z,threat_level) values (%s,%s,%s,%s,%s)',
                       (systemName, x, y, z, threat_level))
        mysql_conn.commit()
        cursor.execute('insert ignore into nhssreports (cmdrName,systemName,x,y,z,threat_level) values (%s,%s,%s,%s,%s,%s)',
                       (cmdrName, systemName, x, y, z, threat_level))
        mysql_conn.commit()

@functions_framework.http
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

    request_json = request.get_json(silent=True)
    request_args = request.args

    nhssFound = nhssExists(request_args)
    nearest = getNearest(request_args)

    if not nhssFound:
        postDiscord(nearest, request_args)

    insertReport(request_args)

    return json.dumps(request_args)
