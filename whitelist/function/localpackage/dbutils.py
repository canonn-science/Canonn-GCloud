import pymysql
from pymysql.err import OperationalError
from os import getenv
import os
import logging
from paramiko import RSAKey
from sshtunnel import SSHTunnelForwarder
import functions_framework


CONNECTION_NAME = getenv("INSTANCE_CONNECTION_NAME", None)
DB_USER = getenv("MYSQL_USER", "canonn")
DB_PASSWORD = getenv("MYSQL_PASSWORD", "secret")
DB_NAME = getenv("MYSQL_DATABASE", "canonn")
DB_HOST = getenv("MYSQL_HOST", "localhost")
DB_PORT = getenv("MYSQL_PORT", 3306)

# get tunnel config from the environment
tunnel_config = {
    "host": getenv("TUNNEL_HOST", None),
    "keyfile": getenv("TUNNEL_KEY", None),
    "user": getenv("TUNNEL_USER", "tunneluser"),
    "local_port": int(getenv("MYSQL_PORT", "3308")),
    "remote_port": int(getenv("TUNNEL_PORT", "3306")),
}

mysql_config = {
    "user": DB_USER,
    "password": DB_PASSWORD,
    "db": DB_NAME,
    "host": DB_HOST,
    "port": int(DB_PORT),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

mysql_conn = None
tunnel = None


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
    global tunnel_config
    global tunnel
    if tunnel:
        print("tunnel already started")
    else:
        print("create tunnel")
        if tunnel_config.get("keyfile") is not None:
            key = RSAKey.from_private_key_file(tunnel_config.get("keyfile"))

            tunnel = SSHTunnelForwarder(
                ssh_address_or_host=(tunnel_config.get("host"), 22),
                ssh_username=tunnel_config.get("user"),
                ssh_pkey=key,
                local_bind_address=("localhost", tunnel_config.get("local_port")),
                remote_bind_address=("localhost", tunnel_config.get("remote_port")),
                compression=True,
            )
            try:
                tunnel.start()
                print("tunnel started")
            except:
                print("Failed to start tunnel")
                return None

        return tunnel
    return None


def close_mysql():
    global mysql_conn
    global tunnel
    # just close it
    try:
        print("Closing mysql connection")
        mysql_conn.close()
        mysql_conn = None
    except:
        logging.error("Could not close connection")
    try:
        tunnel.close()
    except:
        logging.error("error closing tunnel")
    mysql_conn = None
    tunnel = None


def get_cursor():
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


"""
    It should only connect once
    
"""


def setup_sql():
    global mysql_conn
    if not mysql_conn:
        try:
            if CONNECTION_NAME is not None:
                mysql_config["unix_socket"] = f"/cloudsql/{CONNECTION_NAME}"
            mysql_conn = pymysql.connect(**mysql_config)
        except OperationalError:
            # If we fail try again
            if CONNECTION_NAME is not None:
                mysql_config["unix_socket"] = f"/cloudsql/{CONNECTION_NAME}"
            mysql_conn = pymysql.connect(**mysql_config)
    else:
        print("already connected to mysql")


def setup_sql_conn():
    global mysql_conn
    global tunnel

    create_tunnel()
    setup_sql()
    ## try and pingh it. If it fails re-establish the connection
    try:
        mysql_conn.ping(reconnect=True)
    except:
        close_mysql()
        setup_sql()
