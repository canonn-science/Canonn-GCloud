#!/bin/env python3

import json
import zipfile
import requests
import os
import time
import datetime
import gzip

services = set()
systems_idx = []
types = set()
dssa = {}

"""
grab a file from a url and save it to a local file
"""


def urlretrieve(remote_source, local_source):
    url = remote_source
    filename = local_source
    with open(filename, "wb") as f:
        r = requests.get(url)
        f.write(r.content)


"""
compare the header from spansh with the current file. Upload only if new.
"""


def syncCheck(file_path):
    remote_source = "https://downloads.spansh.co.uk/" + \
        os.path.basename(file_path)
    local_source = file_path

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36'}
    response = requests.head(remote_source, headers=headers)
    remote_source_last_modified = response.headers["last-modified"]
    remote_source_last_modified = time.mktime(datetime.datetime.strptime(
        remote_source_last_modified[:-4], "%a, %d %b %Y %H:%M:%S").timetuple())

    try:
        if os.path.exists(local_source):
            local_source_last_modified = os.path.getmtime(local_source)
            if local_source_last_modified == remote_source_last_modified:
                print("Stations not updated")
                print(remote_source_last_modified)
                print(local_source_last_modified)
            else:
                print("updated galaxy file uploading")
                try:
                    os.remove(local_source)
                except:
                    print("couldnt remove file")
                urlretrieve(remote_source, local_source)
                os.utime(local_source, (remote_source_last_modified,
                                        remote_source_last_modified))
                return True

        else:
            print("no galaxy file uploading")
            urlretrieve(remote_source, local_source)
            os.utime(local_source, (remote_source_last_modified,
                                    remote_source_last_modified))
            return True

    except HTTPError(e):
        print("HTTP Error: " + str(e.fp.read()))

    return False


def load_dssa():
    global dssa

    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSVO1H5hsLmEIklsqlV-G3kL5l8mx2eM-JheRIX89G2hZ0mCCfEDUofUsLMy5o6VzeWNVYuVXz0Qk4g/pub?gid=0&single=true&output=tsv"

    r = requests.get(url, stream=True)

    for line in r.text.split("\n"):
        id, name = line.split("\t", 1)
        dssa[id] = name
    return dssa


def load_data():
    global systems_idx
    errors = []

    # print("Loading data")

    with gzip.open("galaxy_stations.json.gz", "rt") as f:
        for line in f:
            if line[0] in ["[", "]"]:
                """Do nothing"""
            else:
                try:
                    j = json.loads(line[:-2])
                except:
                    j = json.loads(line[:-1])
                s = populate(j)
                has_stations = (s.get("stations")
                                and len(s.get("stations")) > 0)
                has_aliens = (s.get("allegiance") in ("Thargoid", "Guardian"))
                if has_stations or has_aliens:
                    systems_idx.append(s)


"""
How to determine material trader and technology broker type by the station economies in simple pseudocode:

Material trader type:
IF (primary_economy == "hightech" OR primary_economy == "military") trader_type = "Encoded";
IF (primary_economy == "extraction" OR primary_economy == "refinery") trader_type = "Raw material";
IF (primary_economy == "industrial") trader_type = "Manufactured";
IF (secondary_economy == "hightech" OR secondary_economy == "military") trader_type = "Encoded";
IF (secondary_economy == "extraction" OR secondary_economy == "refinery") trader_type = "Raw material";
IF (secondary_economy == "industrial") trader_type = "Manufactured";

Tech broker type:
IF (primary_economy == "hightech") broker_type = "Guardian";
IF (primary_economy == "industrial") broker_type = "Human"; // human may be set as a default and it is not needed
IF (secondary_economy == "hightech") broker_type = "Guardian";
IF (secondary_economy != null AND secondary_economy != "hightech") broker_type = "Human"; // needs a confirmation"""


def trader(station, type):
    material_trader = (type == "Material Trader")
    technology_broker = (type == "Technology Broker")

    primary_economy = station.get("primaryEconomy")
    secondary_economy = station.get("secondaryEconomy")

    # print(f"{material_trader} {technology_broker} {primary_economy} {secondary_economy}")

    if material_trader:
        if primary_economy == "High Tech" or primary_economy == "Military":
            return "encoded_material_trader"
        if primary_economy == "Extraction" or primary_economy == "Refinery":
            return "raw_material_trader"
        if primary_economy == "Industrial":
            return "manufactured_material_trader"
        if secondary_economy == "High Tech" or secondary_economy == "Military":
            return "encoded_material_trader"
        if secondary_economy == "Extraction" or secondary_economy == "Refinery":
            return "raw_material_trader"
        if secondary_economy == "Industrial":
            trader_type = "Manufactured"
    if technology_broker:
        if primary_economy == "High Tech":
            return "guardian_technology_broker"
        if primary_economy == "Industrial":
            return "human_technology_broker"
        if secondary_economy == "High Tech":
            return "guardian_technology_broker"
        if not secondary_economy is None or not secondary_economy == "High Tech":
            return "human_technology_broker"
        return "human_technology_broker"
    station_name = station.get("name")
    print(f"{station_name} {material_trader} {technology_broker} {primary_economy} {secondary_economy}")


def get_services(station, system):
    global services
    retval = []
    for service in station.get("services"):
        if service:
            service_name = service.lower().replace(" ", "_")

            retval.append(service_name)

            if service_name == "on_dock_mission":
                print(
                    f"on dock mission,{system.get('name')},{station.get('name')}")

            if service in ["Technology Broker", "Material Trader"]:

                retval.append(trader(station, service))

    # we will treat primary economy as a service
    if station.get("primaryEconomy"):
        tag = station.get("primaryEconomy").lower().replace(
            " ", "_").strip()+"_economy"
        retval.append(tag)

    # we will treat allegiance as a name
    if station.get('allegiance'):
        tag = station.get('allegiance').lower().replace(
            " ", "_").strip()+"_station"
        retval.append(tag)
    else:
        retval.append("independent_station")
    # print(services,flush=True)

    if retval:
        services.update(retval)

    return retval


def isStation(station):
    global dssa
    if dssa.get(station.get("name")):
        # this is a DSSA Carrier we can treat it as a station
        return True

    carrier = (station.get("controllingFaction") == "FleetCarrier")
    carrier = (carrier and station.get(
        "primaryEconomy") == "Private Enterprise")
    carrier = (carrier and station.get("government") == "Private Ownership")

    if carrier:
        return False

    return True


def padsize(v):
    if v:
        if v.get("large") > 0:
            return "L"
        if v.get("medium") > 0:
            return "M"

    return "S"


def get_stations(system):
    stations = []
    stations.extend(system.get("stations"))
    if system.get("bodies"):
        for body in system.get("bodies"):
            if body.get("stations"):
                stations.extend(body.get("stations"))
    return stations


def populate(record):
    global types
    global dssa
    system = {}

    # print(record)
    # quit()
    system["name"] = record.get("name")
    system["x"] = record.get("coords").get("x")
    system["y"] = record.get("coords").get("y")
    system["z"] = record.get("coords").get("z")
    system["stations"] = []
    system["allegiance"] = record.get("allegiance")

    stations = get_stations(record)

    if stations:
        for station in stations:

            if station.get("name") == "Marshall's Drift":
                print("Marshalls Drift is here")

            types.add(station.get("type"))
            if isStation(station):
                # print(json.dumps(station,indent=4))
                # quit()
                if station.get("name") == "Marshall's Drift":
                    print("Marshalls Drift is here")

                name = station.get("name")
                if dssa.get(name):
                    name = name + " " + dssa.get(name).strip()

                system["stations"].append(
                    {
                        "name": name,
                        "distance": station.get("distanceToArrival"),
                        "services": get_services(station, system),
                        "economy": station.get("primaryEconomy"),
                        "pad": padsize(station.get("landingPads"))
                    }
                )
    return system


def store_data():
    global systems_idx

    with zipfile.ZipFile('function/data.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zip_archive:
        zip_archive.writestr('systems_idx.json', json.dumps(systems_idx))
        # for id in systems.keys():
        #    zip_archive.writestr(
        #        f"{id}.json",  # File to replace
        #        json.dumps(systems.get(id))   # Data
        #    )


stations_updated = syncCheck("galaxy_stations.json.gz")

if stations_updated:
    print("stations has been updated")

load_dssa()
load_data()
store_data()

services.remove(None)

for service in sorted(list(services)):
    print(service)

print(json.dumps(list(types), indent=4))

if not stations_updated:
    print("nothing to see here")
    exit(False)

exit(True)


# load_data()
