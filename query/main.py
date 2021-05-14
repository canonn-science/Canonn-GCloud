from flask import current_app
from flask import request
from localpackage.canonn import silly
from os import getenv
import json
import pymysql
from pymysql.err import OperationalError
import google.cloud.logging
import logging

# Instantiates a client
glogclient = google.cloud.logging.Client()
glogclient.get_default_handler()
glogclient.setup_logging(log_level=logging.INFO)

# TODO(developer): specify SQL connection details
CONNECTION_NAME = getenv(
    'INSTANCE_CONNECTION_NAME',
    'canonn-api-236217:europe-north1:canonnpai')
DB_USER = getenv('MYSQL_USER', 'canonn')
DB_PASSWORD = getenv('MYSQL_PASSWORD', 'secret')
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

def setup_sql_conn():
    global mysql_conn
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
    mysql_conn.ping()


app = current_app


@app.route("/nearest/codex/")
def __codex(name=None):
    logging.warning("deprecated")
    return codex(name)

@app.route("/nearest/codex")
def codex(name=None):
    x=request.args.get("x", 0.0)
    y=request.args.get("y", 0.0)
    z=request.args.get("z", 0.0)

    setup_sql_conn()
    with __get_cursor() as cursor:
        sql = """
            select english_name,entryid,system,round(sqrt(pow(x-%s,2)+pow(y-%s,2)+pow(z-%s,2)),2) as distance
            from (
            select distinct english_name,cs.entryid,system,x,y,z
            from codex_systems cs 
            join codex_name_ref cnr on cnr.entryid = cs.entryid
            order by (pow(x-%s,2)+pow(y-%s,2)+pow(z-%s,2)) asc 
            limit 20) data
        """
        cursor.execute(sql, (x,y,z,x,y,z))
        r = cursor.fetchall()
        cursor.close()

    return {"nearest": r}

@app.route("/hello/<name>")
def hello(name=None):
    system = request.args.get("system", 'Sol')
    return f"Hello {name} from {system}"


@app.route("/goodbye", methods=['GET'])
def goodbye():
    return request.args


@app.route("/canonn")
def external():
    return silly(request)


@app.route("/")
def root():
    return "root"


# if __name__ == "__main__":
#    app.run(debug=False)


def payload(request):
    return "what happen"
