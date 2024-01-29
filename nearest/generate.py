#!/bin/env python3

import json
import zipfile
import requests
import os
import time
import datetime
import gzip
import csv

services = set()
systems_idx = []
buying_stats = {}
selling_stats = {}
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
    remote_source = "https://downloads.spansh.co.uk/" + os.path.basename(file_path)
    local_source = file_path

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36"
    }
    response = requests.head(remote_source, headers=headers)
    remote_source_last_modified = response.headers["last-modified"]
    remote_source_last_modified = time.mktime(
        datetime.datetime.strptime(
            remote_source_last_modified[:-4], "%a, %d %b %Y %H:%M:%S"
        ).timetuple()
    )

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
                os.utime(
                    local_source,
                    (remote_source_last_modified, remote_source_last_modified),
                )
                return True

        else:
            print("no galaxy file uploading")
            urlretrieve(remote_source, local_source)
            os.utime(
                local_source, (remote_source_last_modified, remote_source_last_modified)
            )
            return True

    except HTTPError(e):
        print("HTTP Error: " + str(e.fp.read()))

    return False


class Index:
    def __init__(self, name):
        self.file = gzip.open(name, "wt", encoding="UTF-8")
        self.file.write("[")
        self.first = True

    def write(self, text):
        if not self.first:
            self.file.write(",")
        else:
            self.first = False
        self.file.write(text)

    def close(self):
        self.file.write("]")
        self.file.close()


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

    basic_index = Index("function/system_idx.json.gz")
    buying_index = Index("function/buying_idx.json.gz")
    selling_index = Index("function/selling_idx.json.gz")

    # we need to open a gzip to populate first

    with gzip.open("galaxy_stations.json.gz", "rt") as f:
        for line in f:
            if line[0] in ["[", "]"]:
                """Do nothing"""
            else:
                try:
                    j = json.loads(line[:-2])
                except:
                    j = json.loads(line[:-1])
                system_basic = populate_basic(j)
                system_buying = populate_commodities(j, "buying")
                system_selling = populate_commodities(j, "selling")

                has_stations = (
                    system_basic.get("stations")
                    and len(system_basic.get("stations")) > 0
                )
                has_aliens = system_basic.get("allegiance") in ("Thargoid", "Guardian")
                if has_stations or has_aliens:
                    # systems_idx.append(s)
                    basic_index.write(json.dumps(system_basic))

                has_stations = (
                    system_buying.get("stations")
                    and len(system_buying.get("stations")) > 0
                )
                if has_stations:
                    # systems_idx.append(s)
                    buying_index.write(json.dumps(system_buying))

                has_stations = (
                    system_selling.get("stations")
                    and len(system_selling.get("stations")) > 0
                )
                if has_stations:
                    # systems_idx.append(s)
                    selling_index.write(json.dumps(system_selling))
        # terminate the file
        basic_index.close()
        buying_index.close()
        selling_index.close()


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

def load_traders():
    url="https://docs.google.com/spreadsheets/d/e/2PACX-1vRewVlCuLP07LVqy9PpzmjpVxU2kA-Xq7fbG-6zNCXtlZ2lCMmDJGVSv6SHlvkjYzzvSIDCvqRCLWOB/pub?gid=0&single=true&output=csv"
    response = requests.get(url)
    if response.status_code == 200:
        content = response.text.splitlines()
        reader = csv.DictReader(content, delimiter=',')
        data_dict = {}
        for row in reader:
            key = (row['System'], row['Station'])
            #values = {k: row[k] for k in row.keys() if 'Column' in k and 'A' not in k and 'B' not in k}
            data_dict[key] = row
        return data_dict
    else:
        print("Failed to fetch data. Status code:", response.status_code)
        return None

def trader(station, type, system):
    global traders
    material_trader = type == "Material Trader"
    technology_broker = type == "Technology Broker"

    primary_economy = station.get("primaryEconomy")

    secondary_economy = station.get("secondaryEconomy")
    if station.get("economies"):
        for economy in station.get("economies").keys():
            if economy != primary_economy:
                secondary_economy = economy

    system_name = system["name"]
    sys_primary_economy = system.get("primaryEconomy")
    sys_secondary_economy = system.get("secondaryEconomy")

    station_name = station.get("name")

    if material_trader:
        trade_cache=traders.get((system_name,station_name))

        if trade_cache is not None:
            trade=trade_cache["Actual Values"]
            print("fetched trader from data")
            print(
                f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},{trade}"
            )
            return trade

        if primary_economy in ("Refinery") and secondary_economy == "Tourism":
            print(
                f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},encoded_material_trader"
            )
            return "encoded_material_trader"
        if primary_economy in ("High Tech", "Military", "Agriculture"):
            print(
                f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},encoded_material_trader"
            )
            return "encoded_material_trader"
        if primary_economy in ("Extraction", "Refinery", "Colony"):
            print(
                f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},raw_material_trader"
            )
            return "raw_material_trader"
        if primary_economy in ("Industrial", "Service"):
            print(
                f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},manufactured_material_trader"
            )
            return "manufactured_material_trader"
        if secondary_economy == "High Tech" or secondary_economy == "Military":
            print(
                f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},encoded_material_trader"
            )
            return "encoded_material_trader"
        if secondary_economy == "Extraction" or secondary_economy == "Refinery":
            print(
                f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},raw_material_trader"
            )
            return "raw_material_trader"
        if secondary_economy == "Industrial":
            print(
                f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},manufactured_material_trader"
            )
            return "manufactured_material_trader"
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
    print(
        f"{system_name},{station_name},{type},{sys_primary_economy},{primary_economy},{sys_secondary_economy},{secondary_economy},unknown"
    )


def get_services(station, system, record):
    global services
    global buying_stats
    global selling_stats
    retval = []
    # 2023-01-04 at least one station out there has no services at all...
    for service in station.get("services", []):
        if service:
            service_name = service.lower().replace(" ", "_")

            retval.append(service_name)

            if service in ["Technology Broker", "Material Trader"]:
                retval.append(trader(station, service, record))

    # we will treat primary economy as a service
    if station.get("primaryEconomy"):
        tag = (
            station.get("primaryEconomy").lower().replace(" ", "_").strip() + "_economy"
        )
        retval.append(tag)

    # we will treat allegiance as a name
    if station.get("allegiance"):
        tag = station.get("allegiance").lower().replace(" ", "_").strip() + "_station"
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

    carrier = station.get("controllingFaction") == "FleetCarrier"
    carrier = carrier and station.get("primaryEconomy") == "Private Enterprise"
    carrier = carrier and station.get("government") == "Private Ownership"

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


def populate_basic(record):
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
            types.add(station.get("type"))
            if isStation(station):
                name = station.get("name")
                if dssa.get(name):
                    name = name + " " + dssa.get(name).strip()

                commodities = []
                if station.get("market"):
                    commodities = station.get("market").get("commodities")

                system["stations"].append(
                    {
                        "name": name,
                        "type": station.get("type"),
                        "distance": station.get("distanceToArrival"),
                        "services": get_services(station, system, record),
                        # "outfitting": station.get("outfitting"),
                        "economy": station.get("primaryEconomy"),
                        "pad": padsize(station.get("landingPads")),
                    }
                )
    return system


def populate_commodities(record, direction):
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

    if direction == "buying":
        price = "sellPrice"
        stock = "demand"

    if direction == "selling":
        price = "buyPrice"
        stock = "supply"

    stations = get_stations(record)

    if stations:
        for station in stations:
            types.add(station.get("type"))
            if isStation(station):
                name = station.get("name")
                if dssa.get(name):
                    name = name + " " + dssa.get(name).strip()

                commodities = []
                if station.get("market"):
                    commodities = station.get("market").get("commodities")

                has_commodity = False
                if commodities:
                    shoppingList = {}
                    for commodity in commodities:
                        if (
                            commodity.get(stock) > 0
                            and commodity.get(price) > 0
                            #and commodity.get("name") == "Tritium"
                            and direction=='selling'
                        ):
                            label = (
                                commodity.get("name").lower().replace(" ", "_").strip()
                            )
                            shoppingList[label] = {
                                stock: commodity.get(stock),
                                price: commodity.get(price),
                            }

                            has_commodity = True
                        # if direction == "buying" and commodity.get(price) > 0 and commodity.get(stock) > 1:
                        #    print({stock: commodity.get(stock),
                        #           price: commodity.get(price)})

                    if has_commodity:
                        system["stations"].append(
                            {
                                "name": name,
                                "type": station.get("type"),
                                "distance": station.get("distanceToArrival"),
                                "commodities": shoppingList,
                                # "outfitting": station.get("outfitting"),
                                "economy": station.get("primaryEconomy"),
                                "pad": padsize(station.get("landingPads")),
                            }
                        )
    return system


def store_data():
    global systems_idx

    with zipfile.ZipFile(
        "function/data.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zip_archive:
        zip_archive.writestr("systems_idx.json", json.dumps(systems_idx))
        # for id in systems.keys():
        #    zip_archive.writestr(
        #        f"{id}.json",  # File to replace
        #        json.dumps(systems.get(id))   # Data
        #    )


traders=load_traders()

stations_updated = syncCheck("galaxy_stations.json.gz")

if stations_updated:
    print("stations has been updated")

load_dssa()
load_data()

# we are going to create the file as we go along
# store_data()

try:
    services.remove(None)
except:
    print("No none services")

for service in sorted(list(services)):
    print(service)

print(json.dumps(list(types), indent=4))
print(json.dumps(buying_stats, indent=4))


if not stations_updated:
    print("nothing to see here")
    exit(False)

exit(True)


# load_data()
