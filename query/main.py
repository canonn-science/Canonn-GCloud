from flask import current_app
from flask import request

import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import localpackage.challenge
import localpackage.codex

app = current_app


@app.route("/codex/ref")
def codex_ref():
    print("Getting codex_name_ref")
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


@app.route("/")
def root():
    return ""


def payload(request):
    return "what happen"
