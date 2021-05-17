import pymysql
from pymysql.err import OperationalError
from os import getenv

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

mysql_conn = None


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
