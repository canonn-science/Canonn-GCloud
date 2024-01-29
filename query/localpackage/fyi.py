import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
from EDRegionMap.RegionMap import findRegion
import requests
import json
from flask import jsonify


def get_url(path):
    setup_sql_conn()

    with get_cursor() as cursor:
        sqltext = """
            select path,url from canonn_fyi where path = %s
        """
        cursor.execute(sqltext, (path))
        r = cursor.fetchone()
        cursor.close()
        return jsonify(r)
    return None
