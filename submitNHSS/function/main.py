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
import traceback


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


def getDistance(a, b):
    return sqrt(pow(a[0] - b[0], 2) + pow(a[1] - b[1], 2) + pow(a[2] - b[2], 2))


def is_notable(nearest):

    with get_cursor() as cursor:
        cursor.execute("select * from v_nhsssystems_limits", ())
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
    x = float(r.get("x"))
    y = float(r.get("y"))
    z = float(r.get("z"))
    d = [
        {"name": "Sol", "distance": getDistance([x, y, z], SOL)},
        {"name": "Merope", "distance": getDistance([x, y, z], MEROPE)},
        {"name": "Coalsack", "distance": getDistance([x, y, z], COALSACK)},
        {"name": "Witchhead", "distance": getDistance([x, y, z], WITCHHEAD)},
        {"name": "California", "distance": getDistance([x, y, z], CALIFORNIA)},
        {"name": "Cone Sector", "distance": getDistance([x, y, z], CONESECTOR)},
    ]
    d.sort(key=lambda dx: dx["distance"], reverse=False)
    logging.info(d[0])
    return d[0]


def nhssExists(r):
    print("nhssExists")

    s = r.get("systemName")
    sqltext = """
        select * FROM (SELECT 1 AS c FROM nhsssystems where systemName = %s LIMIT 1) d
    """
    with get_cursor() as cursor:
        #'9999-12-31 23:59:59'
        # timestamp":"2019-10-11T15:47:06Z"
        cursor.execute(sqltext, (s))
        result = cursor.fetchone()

    if result:
        return True
    else:
        return False


def postDiscord(n, r):
    print("postDiscord")
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
        data["content"] = (
            f"@here Commander {cmdr} found a non-human signal source in {system}. Located {distance}ly from {ref}"
        )
    else:
        data["content"] = (
            f"Commander {cmdr} found a non-human signal source in {system}. Located {distance}ly from {ref}"
        )

    if threat_level < 3:
        data["content"] = (
            f"@here Commander {cmdr} found a threat_level {threat_level} non-human signal source in {system}. Located {distance}ly from {ref}"
        )

    r = requests.post(
        url, data=json.dumps(data), headers={"Content-Type": "application/json"}
    )


def insertReport(request_args):
    print("insertReport")
    systemName = request_args.get("systemName")
    cmdrName = request_args.get("cmdrName")
    x = request_args.get("x")
    y = request_args.get("y")
    z = request_args.get("z")
    threat_level = int(request_args.get("threat_level"))

    with get_cursor() as cursor:
        cursor.execute(
            "insert ignore into nhsssystems (systemName,x,y,z,threat_level) values (%s,%s,%s,%s,%s)",
            (systemName, x, y, z, threat_level),
        )
        cursor.execute(
            "insert ignore into nhssreports (cmdrName,systemName,x,y,z,threat_level) values (%s,%s,%s,%s,%s,%s)",
            (cmdrName, systemName, x, y, z, threat_level),
        )


@app.route("/cleanup")
@wrap_route
def cleanup():
    with get_cursor() as cursor:
        cursor.execute("delete from nhsssystems where systemName = 'TEST'", ())
        deleted_rows = cursor.rowcount
        cursor.execute("delete from nhssreports  where systemName = 'TEST'", ())
        deleted_rows += cursor.rowcount
    return f"{deleted_rows} rows deleted"


@app.route("/")
@wrap_route
def root():
    request_args = request.args

    nhssFound = nhssExists(request_args)
    nearest = getNearest(request_args)

    if not nhssFound:
        postDiscord(nearest, request_args)

    insertReport(request_args)
    return json.dumps(request.args)


@functions_framework.http
def payload(request):

    return "404 not found", 404
