import csv
import gzip
import json
import time
from datetime import datetime
import requests
from flask import Response, jsonify

SEARCH_URL = "https://spansh.co.uk/api/systems/search/save"
RECALL_URL = "https://spansh.co.uk/api/systems/search/recall/{search_reference}/{page}"
ARCHITECTS_TSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vS5TMBu2KJQBaNqSBropWVdXUcOjz-wJe57e8h4pRPzr7zZ066yjO-H2Z7hqZe-fOVSpzy-7dzAqU2z"
    "/pub?gid=1448295597&single=true&output=tsv"
)
ARCHITECTS_FIELDS = ["System Name", "Architect Name", "Canonn Architect", "Preferred Faction"]
ARCHITECTS_PAGE_SIZE = 100
ARCHITECTS_TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M:%S"

SEARCH_BODY = {
    "filters": {
        "minor_faction_presences": [
            {"name": ["Canonn", "Canonn Deep Space Research"]}
        ]
    },
    "sort": [{"distance": {"direction": "asc"}}],
    "size": 50,
    "page": 0,
    "reference_system": "Varati",
}

CACHE_TTL_SECONDS = 3600
ARCHITECTS_CACHE_TTL_SECONDS = 7200
PAGE_CACHE_LIMIT = 200

_reference_cache = {"reference": None, "expires": 0}
_page_cache = {}
_architects_cache = {"records": None, "expires": 0}


def _gzip_json_response(data):
    body = gzip.compress(json.dumps(data, separators=(",", ":")).encode("utf-8"))
    response = Response(body, mimetype="application/json")
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(body))
    return response


def query():
    now = time.time()
    if _reference_cache["reference"] and _reference_cache["expires"] > now:
        return _gzip_json_response(_reference_cache["reference"])

    r = requests.post(SEARCH_URL, json=SEARCH_BODY, timeout=10)
    r.raise_for_status()
    reference = r.json().get("search_reference")

    _reference_cache["reference"] = reference
    _reference_cache["expires"] = now + CACHE_TTL_SECONDS

    return _gzip_json_response(reference)


def query_page(search_reference, page):
    now = time.time()
    key = (search_reference, page)

    cached = _page_cache.get(key)
    if cached and cached["expires"] > now:
        return _gzip_json_response(cached["data"])

    r = requests.get(
        RECALL_URL.format(search_reference=search_reference, page=page), timeout=10
    )
    r.raise_for_status()
    data = r.json()

    data.pop("search", None)
    data.pop("reference", None)
    data.pop("search_reference", None)

    if len(_page_cache) >= PAGE_CACHE_LIMIT:
        _page_cache.pop(next(iter(_page_cache)))
    _page_cache[key] = {"data": data, "expires": now + CACHE_TTL_SECONDS}

    return _gzip_json_response(data)


def _fetch_architects():
    now = time.time()
    if _architects_cache["records"] is not None and _architects_cache["expires"] > now:
        return _architects_cache["records"]

    r = requests.get(ARCHITECTS_TSV_URL, timeout=10)
    r.raise_for_status()

    reader = csv.DictReader(r.text.splitlines(), delimiter="\t")
    records = list(reader)

    _architects_cache["records"] = records
    _architects_cache["expires"] = now + ARCHITECTS_CACHE_TTL_SECONDS

    return records


def _project_architect(record):
    return {field: record.get(field, "") for field in ARCHITECTS_FIELDS}


def _architect_timestamp(record):
    try:
        return datetime.strptime(record.get("Timestamp", ""), ARCHITECTS_TIMESTAMP_FORMAT)
    except ValueError:
        return datetime.min


def architects_page(page):
    records = _fetch_architects()
    start = page * ARCHITECTS_PAGE_SIZE
    end = start + ARCHITECTS_PAGE_SIZE

    return _gzip_json_response([_project_architect(r) for r in records[start:end]])


def reload_cache():
    _reference_cache["reference"] = None
    _reference_cache["expires"] = 0
    _page_cache.clear()
    _architects_cache["records"] = None
    _architects_cache["expires"] = 0

    return jsonify({"reloaded": True})


def architect_by_system(system_name):
    records = _fetch_architects()
    matches = [
        record
        for record in records
        if record.get("System Name", "").lower() == system_name.lower()
    ]

    if not matches:
        return jsonify({"error": "not found", "system": system_name}), 404

    latest = max(matches, key=_architect_timestamp)

    return jsonify(_project_architect(latest))
