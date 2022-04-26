from flask import escape
import json
import requests

from flask import current_app
from flask import request, jsonify
from flask_cors import CORS
from flask import Response

app = current_app
CORS(app)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

@app.route("/publish/id")
def publish(id):
    webhook=requests.args.get("webhook")
    if not id and not webhook:
        return Response({"error": "id and webkook url empty"},500, mimetype='application/json')


@app.route("/")
def root():
    return ""


def payload(request):
    return "what happen"