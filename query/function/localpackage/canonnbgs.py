import time
import requests
from flask import jsonify

SEARCH_URL = "https://spansh.co.uk/api/systems/search/save"
RECALL_URL = "https://spansh.co.uk/api/systems/search/recall/{search_reference}/{page}"

SEARCH_BODY = {
    "filters": {
        "minor_faction_presences": [
            {"name": ["Canonn", "Canonn Deep Space Research"]}
        ]
    },
    "sort": [{"distance": {"direction": "asc"}}],
    "size": 100,
    "page": 0,
    "reference_system": "Varati",
}

CACHE_TTL_SECONDS = 3600
PAGE_CACHE_LIMIT = 200

_reference_cache = {"reference": None, "expires": 0}
_page_cache = {}


def query():
    now = time.time()
    if _reference_cache["reference"] and _reference_cache["expires"] > now:
        return jsonify(_reference_cache["reference"])

    r = requests.post(SEARCH_URL, json=SEARCH_BODY, timeout=10)
    r.raise_for_status()
    reference = r.json().get("search_reference")

    _reference_cache["reference"] = reference
    _reference_cache["expires"] = now + CACHE_TTL_SECONDS

    return jsonify(reference)


def query_page(search_reference, page):
    now = time.time()
    key = (search_reference, page)

    cached = _page_cache.get(key)
    if cached and cached["expires"] > now:
        return jsonify(cached["data"])

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

    return jsonify(data)
