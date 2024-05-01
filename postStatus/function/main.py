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


def insertReport(request_args):

    cmdrName = (request_args.get("cmdr"),)
    system = (request_args.get("system"),)
    x = (request_args.get("x"),)
    y = (request_args.get("y"),)
    z = (request_args.get("z"),)
    latitude = (request_args.get("lat"),)
    longitude = (request_args.get("lon"),)
    body = (request_args.get("body"),)
    client = (request_args.get("client"),)
    comment = (request_args.get("comment"),)
    heading = (request_args.get("heading"),)
    altitude = (request_args.get("altitude"),)
    category = (request_args.get("site_type"),)
    index_id = (request_args.get("site_index"),)

    if request_args.get("beta") == True:
        beta = "Y"
    else:
        beta = "N"

    raw_json = json.dumps(request_args.get("status"))

    with get_cursor() as cursor:
        cursor.execute(
            """
            insert into status_reports (
                cmdr,
                system,
                x,
                y,
                z,
                Body,
                latitude,
                longitude,
	            raw_status,
	            comment,
                heading,
                altitude,
                category,
                index_id
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
                nullif(%s,'')
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
                raw_json,
                comment,
                heading,
                altitude,
                category,
                index_id,
            ),
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


@app.route("/", methods=["POST"])
@wrap_route
def root():
    request_args = request.json

    insertReport(request_args)
    return json.dumps(request_args)


@functions_framework.http
def payload(request):

    return "404 not found", 404
