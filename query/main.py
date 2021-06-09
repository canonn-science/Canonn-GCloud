from flask import current_app
from flask import request, jsonify


import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import localpackage.challenge
import localpackage.codex
import localpackage.poidata

app = current_app


@app.route("/getSystemPoi")
def getSystemPoi():
    return localpackage.poidata.getSystemPoi(request)


@app.route("/codex/prices")
def codex_prices():
    return localpackage.codex.species_prices(request)


@app.route("/codex/systems")
def codex_systems():
    return localpackage.codex.codex_systems(request)


@app.route("/codex/odyssey/subclass")
def codex_odyssey_subclass():
    return localpackage.codex.odyssey_subclass(request)


@app.route("/codex/ref")
def codex_ref():
    return localpackage.codex.codex_name_ref(request)


@app.route("/challenge/next")
def challenge_next():
    return localpackage.challenge.challenge_next(request)


@app.route("/challenge/status")
def challenge_status():
    return localpackage.challenge.challenge_status(request)


@app.route("/nearest/codex/")
def __codex():
    logging.warning("deprecated")
    return localpackage.challenge.nearest_codex(request)


@app.route("/nearest/codex")
def codex():
    return localpackage.challenge.nearest_codex(request)


@app.route("/survey/temperature")
def temperature():
    setup_sql_conn()

    with get_cursor() as cursor:
        sql = """
            select 
                cmdr,
                system,
                body,
                cast(latitude as CHAR) as latitude,
                cast(longitude as CHAR) as longitude,
                comment,
                cast(raw_status->"$.Temperature" as CHAR) as temperature, 
                cast(raw_status->"$.Gravity" as CHAR) as gravity 
            from status_reports where raw_status->"$.Temperature" is not null
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    return jsonify(r)


@app.route("/")
def root():
    return ""


def payload(request):
    return "what happen"
