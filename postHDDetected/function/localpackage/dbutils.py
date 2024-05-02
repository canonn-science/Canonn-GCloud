import pymysql
from pymysql.err import OperationalError
from os import getenv
import os


CONNECTION_NAME = getenv("INSTANCE_CONNECTION_NAME", None)
DB_USER = getenv("MYSQL_USER", "canonn")
DB_PASSWORD = getenv("MYSQL_PASSWORD", "secret")
DB_NAME = getenv("MYSQL_DATABASE", "canonn")
DB_HOST = getenv("MYSQL_HOST", "localhost")
DB_PORT = getenv("MYSQL_PORT", 3306)

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


def close_mysql():
    global mysql_conn
    # just close it
    try:
        print("Closing mysql connection")
        mysql_conn.close()
        mysql_conn = None
    except:
        pass


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

    # setup the sql
    setup_sql()
    ## try and pingh it. If it fails re-establish the connection
    try:
        mysql_conn.ping(reconnect=True)
    except:
        mysql_conn = None
        setup_sql()
