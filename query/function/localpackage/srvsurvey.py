import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
import requests
import json
from flask import jsonify
from collections import defaultdict
import math

sql = """
    select raw_json from station_subtype where system_address = %s
"""


def fetch_system(id64):
    setup_sql_conn()
    sql = """
        select raw_json from station_subtype where system_address = %s
    """

    with get_cursor() as cursor:

        cursor.execute(sql, (id64))
        results = cursor.fetchall()
        cursor.close()

    return jsonify(results)
