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
                    print("Tunnel closed down")
                except Exception as t:
                    logging.error(f"Tunnel closure failure: {str(t)}")
                app.tunnel = None
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
    print("create tunnel")
    if app.tunnel_config.get("keyfile") is not None:
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
        print("creating tunnel")
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
    """Setup the mysql connection before each request (lazy)"""
    setup_sql_conn()


def submitKills(cmdrName, systemName, isBeta, reward, victimFaction):
    setup_sql_conn()

    if (
        cmdrName is None
        or systemName is None
        or reward is None
        or victimFaction is None
    ):
        return jsonify(
            {
                "fieldCount": 0,
                "affectedRows": 0,
                "insertId": 0,
                "serverStatus": 2,
                "warningCount": 1,
                "changedRows": 0,
            }
        )

    with get_cursor() as cursor:
        sqltext = """
            insert ignore into killreports (cmdrName,systemName,isBeta,reward,victimFaction) values (%s,%s,%s,%s,%s)
        """
        cursor.execute(sqltext, (cmdrName, systemName, isBeta, reward, victimFaction))
        num_rows_affected = cursor.rowcount
        cursor.close()

    return jsonify(
        {
            "fieldCount": 0,
            "affectedRows": num_rows_affected,
            "insertId": 0,
            "serverStatus": 2,
            "warningCount": 0,
            "changedRows": 0,
        }
    )


@app.route("/test")
@wrap_route
def test_route():
    return "test finished"


@app.route("/")
@wrap_route
def root():
    """
    This function is used for submitting Thargoid kills to the Canonn database from the FactionKillBond
    event from the player journal.

    {
        "timestamp":"2018-10-07T13:03:47Z",
        "event":"FactionKillBond",
        "Reward":10000,
        "AwardingFaction":"$faction_PilotsFederation;",
        "AwardingFaction_Localised":"Pilots Federation",
        "VictimFaction":"$faction_Thargoid;",
        "VictimFaction_Localised":"Thargoids"
    }

    :param cmdrName: The name of your commander
    :param systemName: The name of the system you were in when you made the kill
    :param isBeta: Set to Y if you are running a beta version of the game
    :param reward: The value of the combat bond
    :param victimFaction: The value of the VictimFaction item in the event
    """

    # Retrieve parameters from the URL query parameters
    cmdrName = request.args.get("cmdrName")
    systemName = request.args.get("systemName")
    isBeta = request.args.get("isBeta")
    reward = request.args.get("reward")
    victimFaction = request.args.get("victimFaction")

    retval = submitKills(cmdrName, systemName, isBeta, reward, victimFaction)
    return retval


@functions_framework.http
def payload(request):
    return "what happen?"
