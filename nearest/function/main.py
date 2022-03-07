from flask import current_app
from flask import request, jsonify
from flask_cors import CORS
import json
import requests
import zipfile
from math import sqrt

app = current_app
CORS(app)

systems_idx = []


def load_data():
    global stations
    global systems
    global systems_idx

    #print("Loading data")

    if not systems_idx:
        systems_idx = json.loads(zipfile.ZipFile(
            "data.zip").open("systems_idx.json").read())


# can we load this at build time?
load_data()

"""
Get the nearest system in <state>
"""


""" @app.route("/state/<state>")
def nearest_state(state):
    load_data()
    global stations
    global systems
    global systems_idx

    # print(state)
    x, y, z = get_param_coords(request)

    distance = 999999999999999999999
    result = {}

    for system_name, system in systems_idx.items():

        for station in system.get("stations"):
            if station and system and state in station.get("states"):
                a, b, c = get_system_coords(system)

                cdist = pow(a-x, 2)+pow(b-y, 2)+pow(c-z, 2)
                if cdist <= distance:
                    distance = cdist
                    result = {"system": system_name,
                              "distance": round(sqrt(cdist), 0)}
                # we can exit if we are close
                if distance == 0:
                    return result
    if result:
        return result

    # don't return anything if we get here
    return "Couldn't find anything" """


""" @app.route("/module/<module>/<ship>")
def nearest_module(module, ship):
    load_data()
    global stations
    global systems
    global systems_idx

    # print(state)
    x, y, z = get_param_coords(request)

    distance = 999999999999999999999
    result = {}

    for system_name, system in systems_idx.items():

        for station in system.get("stations"):
            print(module)
            if station and system and station.get("selling_modules") and int(module) in station.get("selling_modules") and padcheck(ship, station):
                a, b, c = get_system_coords(system)

                cdist = pow(a-x, 2)+pow(b-y, 2)+pow(c-z, 2)
                if cdist <= distance:
                    distance = cdist
                    result = {"system": system_name,
                              "distance": round(sqrt(cdist), 0)}
                # we can exit if we are close
                if distance == 0:
                    return result
    if result:
        return result

    # don't return anything if we get here
    return "Couldn't find anything"
 """

"""

Given a system name this will return all data for that system
eg system and stations

"""


""" @app.route("/current")
def current_system():
    global stations
    global systems
    global systems_idx

    system = request.args.get("system")

    load_data()
    current = request.args.get("system")
    system = systems_idx.get(current)

    if current and system:
        id = system.get("id")

        result = json.loads(zipfile.ZipFile(
            "data.zip").open(f"{id}.json").read())
        return result
    return request.args

"""


def padcheck(ship, station):
    pad = station.get("pad")
    horizons = (request.args.get("horizons")
                and request.args.get("horizons") == 'y')
    odyssey = (station.get("type") == "Settlement")
    if horizons and odyssey:
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
        if key in station.get("services") and padcheck(ship, station) and station.get("distance") < distance:
            result = station.get("name")
            distance = station.get("distance")
    return result


"""
Legacy version of the route replaces with services
"""


@app.route("/nearest/<key>/<ship>")
def legacy(key, ship):
    return services(key, ship)


"""
Find the nearest services
"""


@app.route("/services/<key>/<ship>")
def services(key, ship):
    load_data()
    global stations
    global systems
    global systems_idx

    x, y, z = get_param_coords(request)

    print(f"{key} {ship}")

    has_key = f"has_{key}"

    #
    distance = 999999999999999999999
    result = {}

    for system in systems_idx:

        for station in system.get("stations"):
            # print(station)
            if station and system and key in station.get("services") and padcheck(ship, station):
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
    return "Couldn't find anything"


@app.route("/")
def root():
    load_data()
    return "Data Loaded"


def payload(request):
    load_data()
    return "what happen"
