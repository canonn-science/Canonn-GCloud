from flask import current_app
from flask import request, jsonify
from flask_cors import CORS
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

import json
import requests
from math import sqrt
import logging
from os import getenv
import functions_framework
from functools import wraps
from flask import url_for
import uuid
import base64
import logging
from math import sqrt, pow, trunc

SOL = [0, 0, 0]
MEROPE = [-78.59375, -149.625, -340.53125]
COALSACK = [423.5625, 0.5, 277.75]  # Musca Dark Region PJ-P b6-8
WITCHHEAD = [355.75, -400.5, -707.21875]  # Ronemar
CALIFORNIA = [-299.0625, -229.25, -876.125]  # HIP 18390
CONESECTOR = [609.4375, 154.25, -1503.59375]  # Outotz ST-I d9-4

hooklist = {}

app = current_app
CORS(app)


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
            logging.error(f"An error occurred: {str(e)}")
            # close mysql
            close_mysql()
            # close the tunnel
            if app.tunnel:
                try:
                    app.tunnel.close()
                    app.tunnel = None
                    print("Tunnel closed down")
                except Exception as t:
                    logging.error(f"Tunnel closure failure: {str(t)}")
            # close the mysql connection

            return "I'm sorry Dave I'm afraid I can't do that", 500

    return decorated_function


def is_database_up(host, port):
    # Create a socket object
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Attempt to connect to the MySQL server
        s.connect((host, port))
        s.close()  # Close the socket
        return True  # Connection successful, database is up
    except ConnectionRefusedError:
        print(
            "Connection failed, database is not up or not listening on the specified port"
        )
        return False  # Connection failed, database is not up or not listening on the specified port


def create_tunnel():
    # f

    if app.tunnel_config.get("keyfile") is not None:
        print("create tunnel")
        key = RSAKey.from_private_key_file(app.tunnel_config.get("keyfile"))

        tunnel = SSHTunnelForwarder(
            ssh_address_or_host=(app.tunnel_config.get("host"), 22),
            ssh_username=app.tunnel_config.get("user"),
            ssh_pkey=key,
            local_bind_address=("localhost", app.tunnel_config.get("local_port")),
            remote_bind_address=("localhost", app.tunnel_config.get("remote_port")),
            compression=True,
        )
        try:
            tunnel.start()
            print("tunnel started")
        except:
            print("Failed to start tunnel")

        return tunnel
    return None


@app.before_request
def before_request():
    """Establishes the SSH tunnel before each request."""
    if not hasattr(app, "tunnel") or app.tunnel is None:
        app.tunnel = create_tunnel()
    else:
        # we created a tunnel but is it still working?
        if not is_database_up("localhost", app.tunnel_config.get("local_port")):
            print("database or tunnel is down")
            app.tunnel.check_tunnels()
            if next(iter(app.tunnel.tunnel_is_up.values())):
                print("Tunnel is up")
            else:
                print("Retry tunnel")
                app.tunnel = create_tunnel()
    """Lazy sql connection"""
    setup_sql_conn()


def getDistance(a, b):
    return sqrt(pow(a[0] - b[0], 2) + pow(a[1] - b[1], 2) + pow(a[2] - b[2], 2))


def is_notable(nearest):
    with get_cursor() as cursor:
        cursor.execute("select * from v_hdsystems_limits", ())
        limits = cursor.fetchone()

    logging.info(limits)

    if nearest.get("name") == "Sol" and float(nearest.get("distance")) < float(
        limits.get("min_sol")
    ):
        return True
    if nearest.get("name") == "Merope" and float(nearest.get("distance")) > float(
        limits.get("max_merope")
    ):
        return True
    if nearest.get("name") == "Coalsack" and float(nearest.get("distance")) > float(
        limits.get("max_coalsack")
    ):
        return True
    if nearest.get("name") == "Witchhead" and float(nearest.get("distance")) > float(
        limits.get("max_witchhead")
    ):
        return True
    if nearest.get("name") == "California" and float(nearest.get("distance")) > float(
        limits.get("max_california")
    ):
        return True
    if nearest.get("name") == "Cone Sector" and float(nearest.get("distance")) > float(
        limits.get("max_conesector")
    ):
        return True

    return False


def getNearest(r):
    x = r.get("x")
    y = r.get("y")
    z = r.get("z")
    d = [
        {"name": "Sol", "distance": getDistance([x, y, z], SOL), "coords": SOL},
        {
            "name": "Merope",
            "distance": getDistance([x, y, z], MEROPE),
            "coords": MEROPE,
        },
        {
            "name": "Coalsack",
            "distance": getDistance([x, y, z], COALSACK),
            "coords": COALSACK,
        },
        {
            "name": "Witchhead",
            "distance": getDistance([x, y, z], WITCHHEAD),
            "coords": WITCHHEAD,
        },
        {
            "name": "California",
            "distance": getDistance([x, y, z], CALIFORNIA),
            "coords": CALIFORNIA,
        },
        {
            "name": "Cone Sector",
            "distance": getDistance([x, y, z], CONESECTOR),
            "coords": CONESECTOR,
        },
    ]
    d.sort(key=lambda dx: dx["distance"], reverse=False)
    logging.info(d[0])
    return d[0]


def hdExists(r):
    s = r.get("system")
    sqltext = """
        select c FROM (SELECT 1 AS c FROM hdreports WHERE systemName = %s LIMIT 1) a
        union
        select c FROM (SELECT 1 AS c FROM hd_detected where `system` = %s LIMIT 1) b
        union
        select c FROM (SELECT 1 AS c FROM hd_monitor where `system` = %s LIMIT 1) c
        union
        select c FROM (SELECT 1 AS c FROM hdsystems where systemName = %s LIMIT 1) d
    """
    with get_cursor() as cursor:
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
    data = {}

    cmdr = r.get("cmdr")
    system = r.get("system")
    destination = r.get("destination")
    distance = trunc(n.get("distance"))
    ref = n.get("name")
    jump = getJumpDistance(r)
    ref_coords = n.get("coords")
    dest_distance = round(
        getDistance(
            ref_coords, [float(r.get("dx")), float(r.get("dy")), float(r.get("dz"))]
        ),
        1,
    )

    url = get_webhooks().get("Hyperdiction")

    game = ""
    if r.get("odyssey"):
        if r.get("odyssey") == "Y":
            game = " (Odyssey)"
        if r.get("odyssey") == "N":
            game = " (Horizons)"

    hostile = " "
    if r.get("hostile"):
        logging.info("hostile hyperdiction")
        hostile = " hostile "

    # we only got accurate xyz when client was added so we will skip old versions

    content = f"Commander {cmdr} reporting{hostile}hyperdiction at {system} while jumping {jump}ly to {destination}. The hyperdiction was {distance}ly from {ref}, the destination was {dest_distance} from {ref}.{game}"

    # ishostile = (r.get("hostile") and r.get("hostile") == 'Y')
    # notable = (is_notable(n) or ishostile)

    if is_notable(n) and system != "TEST":
        data["content"] = f"@here {content}"
    else:
        data["content"] = content

    r = requests.post(
        url, data=json.dumps(data), headers={"Content-Type": "application/json"}
    )


def insertReport(r):
    system = (r.get("system"),)
    # timestamp":"2019-10-11T15:47:06Z"
    timestamp = (r.get("timestamp").replace("T", " ").replace("Z", ""),)
    cmdr = (r.get("cmdr"),)
    game = r.get("odyssey")
    hostile = ""
    if r.get("hostile") is not None:
        if r.get("hostile"):
            hostile = "Y"
        else:
            hostile = "N"

    with get_cursor() as cursor:
        sql = """
        	INSERT ignore INTO hd_detected (cmdr,`system`,timestamp,x,y,z,destination,dx,dy,dz,client,odyssey,hostile) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        cursor.execute(
            sql,
            (
                cmdr,
                system,
                timestamp,
                r.get("x"),
                r.get("y"),
                r.get("z"),
                r.get("destination"),
                r.get("dx"),
                r.get("dy"),
                r.get("dz"),
                r.get("client"),
                game,
                hostile,
            ),
        )
        cursor.execute(
            "insert ignore into hdsystems (systemName,x,y,z) values (%s,%s,%s,%s)",
            (system, r.get("x"), r.get("y"), r.get("z")),
        )


@app.route("/cleanup")
@wrap_route
def cleanup():
    with get_cursor() as cursor:
        cursor.execute("delete from hd_monitor where `system` = 'TEST'", ())
        deleted_rows = cursor.rowcount
        cursor.execute("delete from hd_detected where `system` = 'TEST'", ())
        deleted_rows += cursor.rowcount
    return f"{deleted_rows} rows deleted"


@app.route("/", methods=["POST"])
@wrap_route
def root():
    request_json = request.json
    hdFound = hdExists(request_json)
    nearest = getNearest(request_json)

    ishostile = request_json.get("hostile") and request_json.get("hostile") == "Y"

    if ishostile:
        logging.info("hostile hyperdiction")
    else:
        logging.info("pacific hyperdiction")

    hdNotFound = not hdFound

    if hdNotFound or ishostile:
        postDiscord(nearest, request_json)

    insertReport(request_json)
    return json.dumps(request_json)


@functions_framework.http
def payload(request):

    return "404 not found", 404
