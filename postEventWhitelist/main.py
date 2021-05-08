import json
import pymysql
import requests
from os import getenv
from pymysql.err import OperationalError

CONNECTION_NAME = getenv('INSTANCE_CONNECTION_NAME',
                         'XXX')
DB_USER = getenv('MYSQL_USER', 'canonn')
DB_PASSWORD = getenv('MYSQL_PASSWORD', 'FROM_ENV')
DB_NAME = getenv('MYSQL_DATABASE', 'canonn')
DB_HOST = getenv('MYSQL_HOST', 'localhost')

mysql_config = {
    'user': DB_USER,
    'password': DB_PASSWORD,
    'db': DB_NAME,
    'host': DB_HOST,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True
}

# Create SQL connection globally to enable reuse
# PyMySQL does not include support for connection pooling
mysql_conn = None


def __get_cursor():
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


def notNone(value):
    if value == 'None':
        return ''
    else:
        return value


def get_signal_stats(request_args):
    system = request_args.get("system")

    with __get_cursor() as cursor:
        sql = """select * from postEvent_whitelist"""
        cursor.execute(sql, ())
        r = cursor.fetchall()
        result = []
        for v in r:
            result.append({"description": v.get("description"),
                           "definition": json.loads(v.get("definition"))})
        return result


def payload(request):
    global mysql_conn

    if request.method == 'OPTIONS':
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }

        return ('', 204, headers)

    # Initialize connections lazily, in case SQL access isn't needed for this
    # GCF instance. Doing so minimizes the number of active SQL connections,
    # which helps keep your GCF instances under SQL connection limits.
    if not mysql_conn:
        try:
            mysql_conn = pymysql.connect(**mysql_config)
        except OperationalError:
            # If production settings fail, use local development ones
            mysql_config['unix_socket'] = f'/cloudsql/{CONNECTION_NAME}'
            mysql_conn = pymysql.connect(**mysql_config)

    #request_json = request.get_json(force=True)
    request_args = request.args

    # insertReport(request_args)
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }

    retval = get_signal_stats(request_args)

    if request.method == 'GET':
        return (json.dumps(retval), 200, headers)
    else:
        return (json.dumps({"error": "only GET operations allowed"}), 418, headers)
