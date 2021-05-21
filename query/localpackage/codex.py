import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
import requests
import json


def codex_name_ref(request):
    setup_sql_conn()

    with get_cursor() as cursor:
        sql = """
            select * from codex_name_ref
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
    for entry in r:
        res[entry.get("entryid")] = entry
    return res
