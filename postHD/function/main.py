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


def insertReport(request_args):
    system = request_args.get("system")
    # timestamp":"2019-10-11T15:47:06Z"
    timestamp = request_args.get("timestamp").replace("T", " ").replace("Z", "")
    cmdr = (request_args.get("cmdr"),)
    x = request_args.get("x")
    y = request_args.get("y")
    z = request_args.get("z")

    with get_cursor() as cursor:
        #'9999-12-31 23:59:59'
        # timestamp":"2019-10-11T15:47:06Z"
        if x:
            sql = """
                INSERT ignore INTO hd_monitor (cmdr,`system`,timestamp,x,y,z) VALUES (%s,%s,convert(%s,DATETIME),%s,%s,%s)
            """
            cursor.execute(sql, (cmdr, system, timestamp, x, y, z))
        else:
            sql = """
                INSERT ignore INTO hd_monitor (cmdr,`system`,timestamp) VALUES (%s,%s,convert(%s,DATETIME))
            """
            cursor.execute(sql, (cmdr, system, timestamp))


@app.route("/cleanup")
@wrap_route
def cleanup():
    with get_cursor() as cursor:
        cursor.execute("delete from hd_monitor where `system` = 'TEST'", ())
        deleted_rows = cursor.rowcount
    return f"{deleted_rows} rows deleted"


@app.route("/", methods=["POST"])
@wrap_route
def root():
    request_args = request.json

    insertReport(request_args)
    return json.dumps(request_args)


@functions_framework.http
def payload(request):

    return "404 not found", 404
