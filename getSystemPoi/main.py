from os import getenv

import json
from math import sqrt
import pymysql
from pymysql.err import OperationalError

import google.cloud.logging
import logging

# Instantiates a client
glogclient = google.cloud.logging.Client()
glogclient.get_default_handler()
# glogclient.setup_logging(log_level=logging.INFO)

# TODO(developer): specify SQL connection details
CONNECTION_NAME = getenv(
    'INSTANCE_CONNECTION_NAME',
    'canonn-api-236217:europe-north1:canonnpai')
DB_USER = getenv('MYSQL_USER', 'canonn')
DB_PASSWORD = getenv('MYSQL_PASSWORD', '<Your Password>')
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


def codex_reports(system):
    sql = """
        SELECT 
            case when body LIKE '%% Ring' then SUBSTR(body,1,LENGTH(body)-5) ELSE body end as body,
            coords->'$.latitude' AS latitude,
            coords->'$.longitude' AS longitude, 
            entryid,
            english_name,
            hud_category,
            index_id
            FROM (
                SELECT  
                    replace(body,concat(system,' '),'') as body,
                    cast(max(
                        case 
                            when latitude is null or longitude is null then null 
                            else CONCAT('{"latitude": ',cast(latitude as CHAR),', "longitude":', cast(longitude as CHAR),'}') 
                    end) AS JSON) as coords  ,
                    cr.entryid,
                    english_name,
                    hud_category,
                    index_id
                    FROM codexreport cr 
                    JOIN codex_name_ref cnr ON cnr.entryid = cr.entryid
                    WHERE system = %s
                    and hud_category != 'None'
                    GROUP BY 
                    replace(body,concat(system,' '),''),
                    cr.entryid,
                    english_name,
                    hud_category,
                    index_id
        ) data
    """
    with __get_cursor() as cursor:

        cursor.execute(sql, (system))
        cr = cursor.fetchall()

    return cr


def saa_signals(system):
    sql = """
        select 
            distinct 
            case when replace(body,concat(system,' '),'') LIKE '%% Ring' then SUBSTR(replace(body,concat(system,' '),''),1,LENGTH(replace(body,concat(system,' '),''))-5) ELSE replace(body,concat(system,' '),'') end as body,
            case 
                when type not like '%%SAA%%' then 'Ring' 
                when type like '%%Biological%%' then 'Biology' 
                when type like '%%Geological%%' then 'Geology' 
                when type like '%%Guardian%%' then 'Guardian' 
                when type like '%%Thargoid%%' then 'Thargoid' 
                when type like '%%Human%%' then 'Human' 
                else 'Unknown' 
            end as hud_category,
            case 
                when type not like '%%SAA%%' then type
                when type like '%%Biological%%' then 'Biology' 
                when type like '%%Geological%%' then 'Geology' 
                when type like '%%Guardian%%' then 'Guardian' 
                when type like '%%Thargoid%%' then 'Thargoid' 
                when type like '%%Human%%' then 'Human' 
                else 'Unknown' 
            end as english_name,
            count 
        from SAASignals where system = %s
    """
    with __get_cursor() as cursor:

        cursor.execute(sql, (system))
        cr = cursor.fetchall()

    return cr


def fss_events(system):
    sql = """
        SELECT 
            signalname,
            signalnamelocalised,
            raw_json->"$.IsStation" AS isStation 
            FROM fss_events WHERE system = %s
    """
    with __get_cursor() as cursor:

        cursor.execute(sql, (system))
        cr = cursor.fetchall()

    return cr


def cmdr_poi(cmdr, system):
    sql = """
        SELECT 
                case when body LIKE '%% Ring' then SUBSTR(body,1,LENGTH(body)-5) ELSE body end as body,
                coords->'$.latitude' AS latitude,
                coords->'$.longitude' AS longitude, 
                comment description,
                category        
        from (
            select replace(body,concat(system,' '),'') as body,
            cast(max(
                case 
                when latitude is null or longitude is null then null 
                else CONCAT('{"latitude": ',cast(latitude as CHAR),', "longitude":', cast(longitude as CHAR),'}') 
            end) AS JSON) as coords,s.comment,s.category
            from status_reports s  where category is not null
            and cmdr = %s
            and system = %s
            group by category,comment 
        ) data
    """
    with __get_cursor() as cursor:

        cursor.execute(sql, (cmdr, system))
        cr = cursor.fetchall()

    return cr


def payload(request):
    global mysql_conn

    # respond to Cors request
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

    # set headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }

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

    request_args = request.args

    cmdr = request_args.get("cmdr")
    system = request_args.get("system")

    try:
        logging.debug(f"system {system}")
        result = {
            "system": system
        }

        codex = codex_reports(system)
        saa = saa_signals(system)
        cpoi = cmdr_poi(cmdr, system)
        fss = fss_events(system)

        if codex:
            result["codex"] = codex
        if saa:
            result["SAAsignals"] = saa
        if cpoi:
            result["cmdr"] = cpoi
        if fss:
            result["FSSsignals"] = fss

        logging.debug(f"got results")

        return (json.dumps(result, indent=4), 200, headers)
    except Exception as e:
        logging.error(str(e))
        logging.exception("message")
        result["error"] = str(e)

        return (json.dumps(result, indent=4), 200, headers)
