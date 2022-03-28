from flask import current_app
from flask import request, jsonify
from flask_cors import CORS
import json
import requests
import zipfile
from math import sqrt
import gzip

app = current_app
CORS(app)

systems_idx = []
buying_idx = []
selling_idx = []
DSSA = []


def load_data():
    global stations
    global systems
    global systems_idx
    global buying_idx
    global selling_idx

    # print("Loading data")

    if not systems_idx:
        # systems_idx = json.loads(zipfile.ZipFile(
        #    "data.zip").open("systems_idx.json").read())
        with gzip.open("system_idx.json.gz", 'rt', encoding='UTF-8') as zipfile:
            systems_idx = json.load(zipfile)
        with gzip.open("buying_idx.json.gz", 'rt', encoding='UTF-8') as zipfile:
            buying_idx = json.load(zipfile)
        with gzip.open("selling_idx.json.gz", 'rt', encoding='UTF-8') as zipfile:
            selling_idx = json.load(zipfile)


# can we load this at build time?
load_data()


def padcheck(key, ship, station):
    pad = station.get("pad")
    horizons = (request.args.get("horizons")
                and request.args.get("horizons") == 'y')
    odyssey = (station.get("type") == "Settlement")
    if horizons and odyssey:
        return False

    if key.endswith("_economy") and odyssey:
        return False

    if ship == "S":
        return True
    if ship == "M" and pad in ("M", "L"):
        return True
    if ship == "L" and pad == "L":
        return True
    return False


"""
a little helper to get coords out of the params
"""


def get_param_coords(request):

    x = float(request.args.get("x").replace(',', '.'))
    y = float(request.args.get("y").replace(',', '.'))
    z = float(request.args.get("z").replace(',', '.'))
    return x, y, z


def get_system_coords(system):
    x = float(system.get("x"))
    y = float(system.get("y"))
    z = float(system.get("z"))
    return x, y, z


"""
The original function looked for a boolean has_key
now we are just looking for presence in services
"""


def closest_station(key, system, ship):
    distance = 999999999999999999999
    result = ""

    stations = system.get("stations")
    for station in stations:
        if key in station.get("services") and padcheck(key, ship, station) and station.get("distance") < distance:
            result = station.get("name")
            distance = station.get("distance")
    return result


def closest_commodity(key, system, ship, quantity, direction):
    distance = 999999999999999999999
    result = ""

    stations = system.get("stations")
    for station in stations:
        if key in station.get("commodities"):
            qvalue = int(station.get("commodities").get(key).get(direction))
        if key in station.get("commodities") and padcheck(key, ship, station) and station.get("distance") < distance and int(quantity) < int(qvalue):
            result = station.get("name")
            distance = station.get("distance")
    return result


"""
Legacy version of the route replaces with services
"""


@app.route("/nearest/<key>/<ship>")
def legacy(key, ship):
    return services(key, ship)


@app.route("/system/<name>")
def get_system(name):
    global systems_idx

    target = {}
    for system in systems_idx:
        if system.get("name") == name:
            target = system
            break

    for system in buying_idx:
        if system.get("name") == name:
            target["buying"] = system.get("stations")
            break

    for system in selling_idx:
        if system.get("name") == name:
            target["selling"] = system.get("stations")
            break

    return jsonify(target)


"""
The index uses in game names transformed but we want to recognise variants.
as the canon plugin will be constructing names
"""


def getkey(key):
    aliases = {
        "apex": "apex_interstellar",
        "vista": "vista_genomics",
        "genomics": "vista_genomics",
        "barkeep": "bartender",
        "barman": "bartender",
        "blackmarket": "black_market",
        "commodities ": "market",
        "commodity_market": "market",
        "frontline": "frontline_solutions",
        "facilitator": "interstellar_factors_contact",
        "interstellar_factors": "interstellar_factors_contact",
        "interstellar": "interstellar_factors_contact",
        "carrier_vendor": "fleet_carrier_vendor",
        "commodities": "market",
        "commodity market": "market",
        "commodity": "market",
        "docking": "dock",
        "station": "dock",
        "carrier_administration": "fleet_carrier_administration",
        "carrier_admin": "fleet_carrier_administration",
        "module_packs": "fleet_carrier_administration",
        "rearm": "restock",
        "reload": "restock",
        "cartographics": "universal_cartographics",
        "tech_broker": "technology_broker",
        "human_tech_broker": "human_technology_broker",
        "guardian_tech_broker": "guardian_technology_broker",
        "human_broker": "human_technology_broker",
        "guardian_broker": "guardian_technology_broker",
        "mat_trader": "material_trader",
        "raw_mat_trader": "raw_material_trader",
        "encoded_mat_trader": "encoded_material_trader",
        "manufactured_mat_trader": "manufactured_material_trader",
        "raw_trader": "raw_material_trader",
        "encoded_trader": "encoded_material_trader",
        "manufactured_trader": "manufactured_material_trader",
        "imperial_station": "empire_station",
        "federal_station": "federation_station",
    }
    if aliases.get(key.strip()):
        return aliases.get(key.strip()).strip()
    return key


"""
Find the nearest services
"""


@ app.route("/services/<keyval>/<ship>")
def services(keyval, ship):
    load_data()
    global stations
    global systems
    global systems_idx

    key = getkey(keyval)
    print(key)

    print(f"{keyval} {key} {ship} {request.args}")

    try:
        x, y, z = get_param_coords(request)
    except:
        print("coordinate failure")
        return jsonify({})

    #
    distance = 999999999999999999999
    result = {}

    for system in systems_idx:

        if key.endswith("_allegiance"):
            if system.get("allegiance") and system.get("allegiance").lower()+"_allegiance" == key:
                a, b, c = get_system_coords(system)

                cdist = pow(a-x, 2)+pow(b-y, 2)+pow(c-z, 2)
                if cdist <= distance:
                    distance = cdist
                    result = {"system": system.get("name"),
                              "station": None,
                              "distance": round(sqrt(cdist), 0)}
                # we can exit if we are close
                if distance == 0:
                    return result
        else:
            for station in system.get("stations"):
                # print(station)

                if station and system and key in station.get("services") and padcheck(key, ship, station):
                    a, b, c = get_system_coords(system)

                    cdist = pow(a-x, 2)+pow(b-y, 2)+pow(c-z, 2)
                    if cdist <= distance:
                        distance = cdist
                        result = {"system": system.get("name"),
                                  "station": closest_station(key, system, ship),
                                  "distance": round(sqrt(cdist), 0)}
                    # we can exit if we are close
                    if distance == 0:
                        return result
    if result:
        return result

    # don't return anything if we get here
    return jsonify({})


"""
Find the buying and selling
"""


@ app.route("/buying/<keyval>/<ship>/<quantity>")
def get_buying(keyval, ship, quantity):
    return get_commodity(keyval, ship, int(quantity), "demand")


@ app.route("/selling/<keyval>/<ship>/<quantity>")
def get_selling(keyval, ship, quantity):
    return get_commodity(keyval, ship, int(quantity), "supply")


def get_commodity(keyval, ship, quantity, direction):
    load_data()
    global stations
    global systems
    global systems_idx
    global buying_idx
    global selling_idx

    key = getkey(keyval)

    print(f"{keyval} {key} {ship} {request.args}")

    try:
        x, y, z = get_param_coords(request)
    except:
        print("coordinate failure")
        return jsonify({})

    #
    distance = 999999999999999999999
    result = {}

    if direction == "supply":
        index = selling_idx
    else:
        index = buying_idx

    for system in index:

        for station in system.get("stations"):
            # print(station)

            has_commodity = (key in station.get("commodities"))
            qvalue = 0
            if has_commodity:

                qvalue = int(station.get(
                    "commodities").get(key).get(direction))

            if station and system and has_commodity and quantity < qvalue and padcheck(key, ship, station):

                a, b, c = get_system_coords(system)

                cdist = pow(a-x, 2)+pow(b-y, 2)+pow(c-z, 2)
                if cdist <= distance:
                    distance = cdist
                    result = {"system": system.get("name"),
                              "station": closest_commodity(key, system, ship, quantity, direction),
                              "distance": round(sqrt(cdist), 0),
                              "commodity": station.get("commodities").get(key)
                              }
                # we can exit if we are close
                if distance == 0:
                    return result
    if result:
        return result

    # don't return anything if we get here
    return jsonify({})


@ app.route("/")
def root():
    load_data()
    return "Data Loaded"


def payload(request):
    load_data()
    return "what happen"
