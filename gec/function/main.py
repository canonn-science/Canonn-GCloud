from markupsafe import escape
import json
import requests

from flask import current_app
from flask import request, jsonify
from flask_cors import CORS
from flask import Response
import functions_framework

app = current_app
CORS(app)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

@app.route("/publish/<id>")
def publish(id):
    webhook=request.args.get("webhook")
    if not id and not webhook:
        return Response({'error': "id and webkook url empty"},500, mimetype='application/json')
    else:
        return jsonify({"success": True})

@app.route("/")
def root():
    return ""

@functions_framework.http
def payload(request):
    return "what happen"
