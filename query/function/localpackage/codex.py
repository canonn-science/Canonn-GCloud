import localpackage.dbutils
from localpackage.dbutils import setup_sql_conn
from localpackage.dbutils import get_cursor
import pymysql
from pymysql.err import OperationalError
from EDRegionMap.RegionMap import findRegion
import requests
import json
import math
import re
import gzip
from datetime import datetime, timezone
from flask import jsonify, Response
import urllib.parse

biostats = {}
spanshdump = {}
id64list = []


# get the id64 for a given system
def getId64(system_name):
    global id64list
    for system in id64list:
        id = system.get(system_name)
        if id:
            print("id64 from cache")
            return id
    try:
        url = "https://spansh.co.uk/api/systems/field_values/system_names"
        r = requests.get(url, params={"q": system_name}, timeout=10)
        r.raise_for_status()

        data = r.json()

        for system in data["min_max"]:
            if system["name"].lower() == system_name.lower():
                if len(id64list) > 200:
                    id64list.pop()

                item = {}
                item[system_name] = system.get("id64")
                id64list.append(item)
                return system.get("id64")
            
        raise Exception(f"System '{system_name}' not found")

    except Exception as e:
        print("Error getting request")
        print(url)
        print(data)
        return None
   



def findRegion64(id):
    id64 = int(id)
    masscode = id64 & 7
    z = (((id64 >> 3) & (0x3FFF >> masscode)) << masscode) * 10 - 24105
    y = (((id64 >> (17 - masscode)) & (0x1FFF >> masscode)) << masscode) * 10 - 40985
    x = (
        ((id64 >> (30 - masscode * 2)) & (0x3FFF >> masscode)) << masscode
    ) * 10 - 49985
    try:
        return findRegion(x, y, z)
    except:
        return 0, "Unknown"


def get_biostats(cache=True):
    global biostats
    if not biostats or not cache:

        r = requests.get(
            "https://drive.google.com/uc?id=14t7SKjLyATHVipuqNiGT-ziA2nRW8sKj"
        )
        biostats = r.json()


def biostats_cache(cache):
    global biostats
    get_biostats(cache)
    return jsonify(biostats)


_FLEET_CARRIER_STATION_TYPE = "Drake-Class Carrier"


def _strip_fleet_carriers(system):
    """
    Removes fleet carrier entries from the system's station list and every body's own,
    leaving everything else (factions, non-carrier stations, settlements) untouched.
    """
    stations = system.get("stations")
    if stations:
        system["stations"] = [
            s for s in stations if s.get("type") != _FLEET_CARRIER_STATION_TYPE
        ]
    for body in system.get("bodies") or []:
        body_stations = body.get("stations")
        if body_stations:
            body["stations"] = [
                s for s in body_stations if s.get("type") != _FLEET_CARRIER_STATION_TYPE
            ]


def get_spansh_by_id(id64, keep_all_data=False):
    global spanshdump

    cached = (
        spanshdump.get("system")
        and spanshdump.get("system").get("id64")
        and str(spanshdump.get("system").get("id64")) == str(id64)
    )

    # ignore caching as we want latest data
    # if not cached:
    if True:
        r = requests.get(f"https://spansh.co.uk/api/dump/{id64}")
        spanshdump = r.json()
        if spanshdump.get("system"):
            if keep_all_data:
                _strip_fleet_carriers(spanshdump["system"])
            else:
                if spanshdump.get("system").get("factions"):
                    del spanshdump["system"]["factions"]
                if spanshdump.get("system").get("stations"):
                    del spanshdump["system"]["stations"]

        # check that id64 matches
        cached = (
            spanshdump.get("system")
            and spanshdump.get("system").get("id64")
            and str(spanshdump.get("system").get("id64")) == str(id64)
        )
        if not cached:
            spanshdump = {}
    else:
        print("spansh cached")


def get_mainstar_type():
    global spanshdump
    system = spanshdump.get("system")
    for body in system.get("bodies"):
        if body.get("mainStar") == True:
            return body.get("subType")
    return None


def get_primary_star(system):
    bodies = system.get("bodies")
    for body in bodies:
        if body.get("mainStar"):
            return body.get("subType")


def get_parent_type(system, body):
    bodyName = body.get("name")
    systemName = system.get("name")
    shortName = bodyName.replace(f"{systemName} ", "")
    bodies = system.get("bodies")

    parts = shortName.split(" ")

    for n in range(len(parts) - 1, -1, -1):
        newpart = " ".join(parts[:n])
        if newpart.isupper():
            # print(f"converting newpart {newpart} to {newpart[0]}")
            newpart = newpart[0]
        newname = systemName + " " + newpart
        # :qprint(newname)
        for b in bodies:
            if b.get("name") == newname and b.get("type") == "Star":
                # print(f"{newname} = Star")
                # print("{} {}".format(b.get("name"), parentName))
                return b.get("subType")

    # fall back to this
    primary = get_mainstar_type()
    return primary


def get_system_codex(system):

    with get_cursor() as cursor:
        sqltext = """
            select distinct cr.system,nullif(body,'') as body,english_name,hud_category from codexreport cr 
            join codex_name_ref cnr on cnr.entryid = cr.entryid
            where cr.system = %s
            union             
            select distinct cr.system,nullif(body,'') as body,english_name,hud_category from organic_scans cr 
            join codex_name_ref cnr on cnr.name = cr.variant
            where cr.system = %s
        """
        cursor.execute(sqltext, (system, system))
        r = cursor.fetchall()
        cursor.close()
        return r
    return None


def get_id64_codex(id64):
    sqltext = "select entryid,body_id from codex_bodies where system_address = %s"
    with get_cursor() as cursor:
        cursor.execute(sqltext, (id64))
        r = cursor.fetchall()
        cursor.close()
        return jsonify(r)
    return jsonify([])


def mat_species(species):
    id = species.get("id")

    if id:
        for material in (
            "Technetium",
            "Molybdenum",
            "Ruthenium",
            "Tellurium",
            "Antimony",
            "Tungsten",
            "Polonium",
            "Yttrium",
            "Cadmium",
            "Niobium",
            "Mercury",
            "Tin",
        ):
            if material in id:
                return True
    else:
        return False


def checkMats(body, species):
    materials = body.get("materials")
    count = 0
    target = len(species.get("materials"))

    # its its not a materials based species we can return true
    if not mat_species(species):
        return True

    matmatch = False

    if materials:
        for mat in species.get("materials"):
            if mat in materials.keys():
                count += 1

        # if we have all required materials we should be good.
        matmatch = count == target
        # the species id contains the key material that must be present
        # we shouldn't have to do this but there may be some misreported bodies

        hasmat = False
        for key in materials.keys():
            if key in species.get("id"):
                hasmat = True
                break

    # We need matching materials and for our material to be present
    matmatch = matmatch and hasmat

    return matmatch


"""
Ports of canonn-signals' influencing-star.ts (flux-dominance algorithm that determines
which star in a multi-star system governs a body's biology) and biology-star-class.ts
(filters a guessed biology signal against that star's class), so the CanonnBiostats API
can apply the same logic Canonn Signals uses in the browser.
See https://github.com/canonn-science/canonn-signals/blob/main/src/app/data/influencing-star.ts
and https://github.com/canonn-science/canonn-signals/blob/main/src/app/data/biology-star-class.ts
"""

KM_PER_AU = 149597870.7
KM_PER_LIGHT_SECOND = 299792.458
DEG_TO_RAD = math.pi / 180
MS_PER_DAY = 86400000

REFERENCE_MS = datetime(2021, 4, 1, tzinfo=timezone.utc).timestamp() * 1000
NEAR_TIE_RATIO_THRESHOLD = 2.0
TIME_AVERAGE_N_SAMPLES = 24
SAMPLE_TIMES_MS = [
    datetime(
        round(1500 + (2700 - 1500) * i / (TIME_AVERAGE_N_SAMPLES - 1)),
        1,
        1,
        tzinfo=timezone.utc,
    ).timestamp()
    * 1000
    for i in range(TIME_AVERAGE_N_SAMPLES)
]

# Y-class (brown dwarf) flux boost, see N_BOOST below for the rationale.
Y_BOOST = 1.75
# Neutron-star flux boost. Stefan-Boltzmann (R^2*T^4) systematically under-ranks neutron
# stars, since their microscopic radius crushes even their multi-million-K fictional
# surfaceTemperature, so a larger boost compensates.
N_BOOST = 2.5

_ORBITAL_FIELDS = (
    "semiMajorAxis",
    "orbitalEccentricity",
    "orbitalInclination",
    "ascendingNode",
    "argOfPeriapsis",
    "meanAnomaly",
)


def _body_index(system):
    return {
        b.get("bodyId"): b for b in system.get("bodies") or [] if b.get("bodyId") is not None
    }


def _ancestor_ids(body):
    ids = []
    for entry in body.get("parents") or []:
        ids.extend(entry.values())
    return ids


def _build_parent_map(system):
    """
    Maps every body id appearing anywhere in the system to its immediate parent id, built
    from consecutive pairs in every body's own flattened `parents` chain (nearest-first).
    This recovers the correct immediate parent even for a node (e.g. an intermediate
    barycentre) whose own record omits `parents` entirely, as long as some descendant's
    chain lists it - Spansh sometimes drops `parents` on such nodes even though they
    genuinely orbit something. An id that never appears as a non-terminal entry in any
    chain has no mapped parent and is the true system root.
    """
    parent_of = {}
    for b in system.get("bodies") or []:
        bid = b.get("bodyId")
        if bid is None:
            continue
        ids = [bid] + _ancestor_ids(b)
        for child_id, next_id in zip(ids, ids[1:]):
            parent_of.setdefault(child_id, next_id)
    return parent_of


def _mean_anomaly_now_deg(mean_anomaly_deg, orbital_period_days, timestamp, now_ms):
    if not orbital_period_days or not timestamp:
        return mean_anomaly_deg
    try:
        epoch_ms = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() * 1000
    except (ValueError, AttributeError):
        return mean_anomaly_deg
    cycles = ((now_ms - epoch_ms) / MS_PER_DAY) / orbital_period_days
    return (((mean_anomaly_deg + cycles * 360) % 360) + 360) % 360


def _orbital_state_vector_km(a_au, e, incl_deg, node_deg, argp_deg, mean_anomaly_deg):
    a = a_au * KM_PER_AU
    ecc = min(max(e, 0), 0.999)
    m = (((mean_anomaly_deg % 360) + 360) % 360) * DEG_TO_RAD
    E = m if ecc < 0.8 else math.pi
    for _ in range(12):
        delta = (E - ecc * math.sin(E) - m) / (1 - ecc * math.cos(E))
        E -= delta
        if abs(delta) < 1e-12:
            break
    xo = a * (math.cos(E) - ecc)
    yo = a * math.sqrt(1 - ecc * ecc) * math.sin(E)
    node = -node_deg * DEG_TO_RAD
    argp = -argp_deg * DEG_TO_RAD
    incl = incl_deg * DEG_TO_RAD
    cO, sO = math.cos(node), math.sin(node)
    cw, sw = math.cos(argp), math.sin(argp)
    ci, si = math.cos(incl), math.sin(incl)
    return (
        xo * (cO * cw - sO * sw * ci) - yo * (cO * sw + sO * cw * ci),
        xo * (sO * cw + cO * sw * ci) - yo * (sO * sw - cO * cw * ci),
        xo * (sw * si) + yo * (cw * si),
    )


def _body_offset_km(body, now_ms):
    if any(body.get(f) is None for f in _ORBITAL_FIELDS):
        return None
    timestamp = (body.get("timestamps") or {}).get("meanAnomaly")
    m = _mean_anomaly_now_deg(
        body.get("meanAnomaly"), body.get("orbitalPeriod"), timestamp, now_ms
    )
    return _orbital_state_vector_km(
        body.get("semiMajorAxis"),
        body.get("orbitalEccentricity"),
        body.get("orbitalInclination"),
        body.get("ascendingNode"),
        body.get("argOfPeriapsis"),
        m,
    )


def _absolute_position_km(body_id, index, parent_map, now_ms, cache):
    """
    Absolute position (km) in the system's shared frame: own orbital offset plus every
    ancestor's, walking `parent_map` (see `_build_parent_map`) rather than each node's own
    `parents` field, so a barycentre missing that field still resolves to its real parent.
    """
    if body_id in cache:
        return cache[body_id]
    parent_id = parent_map.get(body_id)
    if parent_id is None:
        cache[body_id] = (0.0, 0.0, 0.0)
        return cache[body_id]
    body = index.get(body_id)
    if body is None:
        cache[body_id] = (0.0, 0.0, 0.0)
        return cache[body_id]
    offset = _body_offset_km(body, now_ms)
    if offset is None:
        cache[body_id] = None
        return None
    parent_pos = _absolute_position_km(parent_id, index, parent_map, now_ms, cache)
    if parent_pos is None:
        cache[body_id] = None
        return None
    pos = tuple(o + p for o, p in zip(offset, parent_pos))
    cache[body_id] = pos
    return pos


def _calculated_distance_ls(target_id, star_id, index, parent_map, now_ms, cache):
    tp = _absolute_position_km(target_id, index, parent_map, now_ms, cache)
    if tp is None:
        return None
    sp = _absolute_position_km(star_id, index, parent_map, now_ms, cache)
    if sp is None:
        return None
    dx, dy, dz = tp[0] - sp[0], tp[1] - sp[1], tp[2] - sp[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz) / KM_PER_LIGHT_SECOND


def _flux(star, distance):
    if distance is None or distance == 0:
        return None
    r, t = star.get("solarRadius"), star.get("surfaceTemperature")
    if r is None or t is None:
        return None
    return (r * t * t / distance) ** 2


def _time_averaged_flux(target_id, star, index, parent_map):
    star_id = star.get("bodyId")
    total = 0
    for now_ms in SAMPLE_TIMES_MS:
        d = _calculated_distance_ls(target_id, star_id, index, parent_map, now_ms, {})
        f = _flux(star, d)
        if f is None:
            return None
        total += f
    return total / len(SAMPLE_TIMES_MS)


def _ancestor_chain_via_map(body_id, parent_map):
    """
    Full ancestor chain (nearest-first) for `body_id`, walking the robust `parent_map`
    (see `_build_parent_map`) rather than the body's own `parents` field - so a barycentre
    whose own record omits `parents` still contributes correctly when it's the target or
    star itself, not just when it's an ancestor encountered along the way.
    """
    chain = []
    current = parent_map.get(body_id)
    while current is not None:
        chain.append(current)
        current = parent_map.get(current)
    return chain


def _nearest_common_ancestor(target_id, star_id, parent_map):
    chain_star = set(_ancestor_chain_via_map(star_id, parent_map))
    for anc_id in _ancestor_chain_via_map(target_id, parent_map):
        if anc_id == star_id or anc_id in chain_star:
            return anc_id
    return None


def _sum_sq_sma_to(body_id, stop_id, index, parent_map):
    if body_id == stop_id:
        return 0
    body = index.get(body_id)
    if body is None:
        return None
    sma = body.get("semiMajorAxis")
    if sma is None:
        return None
    total = sma * sma
    current = body_id
    while True:
        anc_id = parent_map.get(current)
        if anc_id is None:
            # reached the true root without ever hitting stop_id - unresolved
            return None
        if anc_id == stop_id:
            return total
        anc = index.get(anc_id)
        if anc is None:
            return None
        anc_sma = anc.get("semiMajorAxis")
        if anc_sma is None:
            return None
        total += anc_sma * anc_sma
        current = anc_id


def _characteristic_distance_au(target, star, index, parent_map):
    target_id = target.get("bodyId")
    star_id = star.get("bodyId")
    common = _nearest_common_ancestor(target_id, star_id, parent_map)
    if common is None:
        return None
    d1 = _sum_sq_sma_to(target_id, common, index, parent_map)
    if d1 is None:
        return None
    d2 = _sum_sq_sma_to(star_id, common, index, parent_map)
    if d2 is None:
        return None
    return math.sqrt(d1 + d2)


def _is_y_star(star):
    if (star.get("spectralClass") or "")[:1] == "Y":
        return True
    return (star.get("subType") or "").startswith("Y (Brown dwarf")


def _is_n_star(star):
    if (star.get("spectralClass") or "")[:1] == "N":
        return True
    return star.get("subType") == "Neutron Star"


def _class_boost_factor(star):
    if _is_n_star(star):
        return N_BOOST
    if _is_y_star(star):
        return Y_BOOST
    return 1


def influencing_star(body, system, index=None, parent_map=None):
    """
    Determines the star that governs `body`'s biology, or None when the system has no
    stars or the winner can't be determined. Mirrors influencingStar() in influencing-star.ts:
    ranks stars by flux (R*T^2/distance)^2 at the body's real 3D orbital position
    (hypothesis N), falling back to the characteristic orbital-scale distance (hypothesis F)
    when the full orbital chain isn't resolvable for every candidate star.

    `index`/`parent_map` (see `_body_index`/`_build_parent_map`) may be precomputed once by
    the caller and reused across every body in the system - each build is O(bodies), so
    recomputing them per body here would make a whole-system pass O(bodies^2).
    """
    if index is None:
        index = _body_index(system)
    if parent_map is None:
        parent_map = _build_parent_map(system)
    stars = [b for b in system.get("bodies") or [] if b.get("type") == "Star"]
    if not stars:
        return None
    if len(stars) == 1:
        return {"star": stars[0], "method": "only-star", "starCount": 1}

    target_id = body.get("bodyId")

    pos_cache = {}
    snapshot = [
        (s, _flux(s, _calculated_distance_ls(target_id, s.get("bodyId"), index, parent_map, REFERENCE_MS, pos_cache)))
        for s in stars
    ]

    if all(score is not None for _, score in snapshot):
        effective = snapshot
        ranked = sorted((score for _, score in snapshot), reverse=True)
        near_tie = len(ranked) >= 2 and ranked[1] > 0 and ranked[0] / ranked[1] <= NEAR_TIE_RATIO_THRESHOLD
        if near_tie:
            effective = []
            for s, score in snapshot:
                avg = _time_averaged_flux(target_id, s, index, parent_map)
                effective.append((s, avg if avg is not None else score))
        boosted = [(s, sc * _class_boost_factor(s)) for s, sc in effective]
        winner = max(boosted, key=lambda x: x[1])[0]
        return {"star": winner, "method": "flux-3d", "starCount": len(stars)}

    # F fallback: characteristic orbital-scale distance flux.
    characteristic = [(s, _flux(s, _characteristic_distance_au(body, s, index, parent_map))) for s in stars]
    if any(score is None for _, score in characteristic):
        return None
    boosted = [(s, sc * _class_boost_factor(s)) for s, sc in characteristic]
    winner = max(boosted, key=lambda x: x[1])[0]
    return {"star": winner, "method": "flux-characteristic", "starCount": len(stars)}


# Star-class tokens Elite's codex names encode ahead of the trailing `_Name;`.
CODEX_STAR_CLASS_TOKENS = {
    "G", "M", "L", "F", "K", "TTS", "T", "N", "A", "B", "Y", "D", "O", "W", "Ae",
}
_CODEX_STAR_CLASS_RE = re.compile(r"_([A-Za-z]+)_Name;$")


def codex_star_class_token(codex_name):
    """
    Extracts the star-class token from a codex entry's internal `name` field (e.g.
    `$Codex_Ent_Aleoids_02_TTS_Name;` -> `"TTS"`), or None when the name doesn't end in a
    recognised token, meaning the species isn't tied to a specific star class.
    """
    if not codex_name:
        return None
    m = _CODEX_STAR_CLASS_RE.search(codex_name)
    if not m:
        return None
    token = m.group(1)
    return token if token in CODEX_STAR_CLASS_TOKENS else None


def _spectral_letter(spectral_class):
    if not spectral_class:
        return None
    m = re.match(r"^([OBAFGKMLTY])", spectral_class.strip(), re.IGNORECASE)
    return m.group(1).upper() if m else None


def _is_white_dwarf(spectral_class, sub_type):
    if (sub_type or "").startswith("White Dwarf"):
        return True
    return bool(re.match(r"^D", (spectral_class or "").strip(), re.IGNORECASE))


def _star_class_letter(spectral_class, sub_type):
    direct = _spectral_letter(spectral_class)
    if direct:
        return direct
    m = re.match(r"^([OBAFGKMLTY]) \(", sub_type or "")
    return m.group(1) if m else None


def influencing_star_class_token(star):
    """
    Maps a star's spectralClass/subType to the same star-class token vocabulary the codex
    uses in species names, or None when the star's class has no codex token at all (e.g. a
    Black Hole).
    """
    spectral_class = star.get("spectralClass")
    sub_type = star.get("subType") or ""
    if _is_white_dwarf(spectral_class, sub_type):
        return "D"
    if (spectral_class or "")[:1] == "N" or sub_type == "Neutron Star":
        return "N"
    if "Wolf-Rayet" in sub_type:
        return "W"
    if sub_type == "T Tauri Star":
        return "TTS"
    if sub_type == "Herbig Ae/Be Star":
        return "Ae"
    return _star_class_letter(spectral_class, sub_type)


def is_biology_guess_allowed(english_name, codex_name, influencing_star_token):
    """
    True when a guessed biology signal should be kept given the resolved Influencing Star's
    class token. `codex_name` is the guess's codex entry's internal `name` field.
    """
    # Stratum Araneamus - Emerald can occur around any star class.
    if english_name == "Stratum Araneamus - Emerald":
        return True

    required_token = codex_star_class_token(codex_name)
    if required_token is None or required_token == influencing_star_token:
        return True

    # Yellow Tussocks (codex star class F) also occur around Neutron Stars.
    if (
        required_token == "F"
        and influencing_star_token == "N"
        and english_name.startswith("Tussock")
        and english_name.endswith("Yellow 1")
    ):
        return True

    return False


def guess_biology(body, codex, inf_star=None):
    global biostats
    global spanshdump
    system = spanshdump.get("system")
    results = []

    region, region_name = findRegion64(system.get("id64"))

    if body.get("type") != "Planet" or not landable(body):
        return []

    parentType = get_parent_type(system, body)
    influencing_token = influencing_star_class_token(inf_star["star"]) if inf_star else None

    for key in biostats.keys():
        species = biostats.get(key)

        if species.get("hud_category") == "Biology":
            validStar = is_biology_guess_allowed(
                species.get("name"), species.get("fdevname"), influencing_token
            )

            odyssey = species.get("platform") == "odyssey"

            # don't match regions on odyssey bios
            # NB we now know that there is region specific biology
            # But we don't want to miss guesses we would have to build
            # some reference data
            regionMatch = odyssey or (
                species.get("regions") and region_name in species.get("regions")
            )

            parentMatch = parentType in species.get("localStars")
            # materials is highly dependednt on species
            validMaterials = checkMats(body, species)

            volcanismMatch = (
                body.get("volcanismType") or "No volcanism"
            ) in species.get("volcanism")

            atmosphereTypeMatch = (
                body.get("atmosphereType") or "No atmosphere"
            ) in species.get("atmosphereType")

            mainstarMatch = get_mainstar_type() in species.get("primaryStars")

            if body.get("subType") is None:
                body["subType"] = "Unknown"
            # use combined body and volcanism
            # bodyMatch = (body.get("subType") in species.get("bodies"))
            volcanicbodytype = None
            if body.get("subType"):
                volcanicbodytype = (
                    body.get("subType")
                    + " - "
                    + (body.get("volcanismType") or "No volcanism")
                )

            if (
                species.get("histograms").get("volcanic_body_types")
                and volcanicbodytype
                in species.get("histograms").get("volcanic_body_types").keys()
            ):
                bodyMatch = True
            else:
                bodyMatch = False

            if bodyMatch and species.get("ming"):
                gravityMatch = (
                    float(species.get("ming"))
                    <= float(body.get("gravity"))
                    <= float(species.get("maxg"))
                )

                pressureMatch = (
                    float(species.get("minp") or 0)
                    <= float((body.get("surfacePressure") or 0))
                    <= float(species.get("maxp") or 0)
                )

                tempMatch = (
                    float(species.get("mint"))
                    <= float(body.get("surfaceTemperature"))
                    <= float(species.get("maxt"))
                )

                distanceMatch = (
                    float(species.get("mind"))
                    <= float(body.get("distanceToArrival"))
                    <= float(species.get("maxd"))
                )

                # if there are genuses recorded then only matching genus should be included in the guesses
                if body.get("signals") and body.get("signals").get("genuses"):
                    matchgenus = False
                    genus = species.get("fdevname").split("_")[2]
                    # print(genus)
                    for g in body.get("signals").get("genuses"):
                        # print(g)
                        if g.split("_")[2] == genus:
                            matchgenus = matchgenus or True
                else:
                    matchgenus = True

                if (
                    matchgenus
                    and validStar
                    and mainstarMatch
                    and bodyMatch
                    and gravityMatch
                    and tempMatch
                    and atmosphereTypeMatch
                    and volcanismMatch
                    and pressureMatch
                    and validMaterials
                    and parentMatch
                    and regionMatch
                ):
                    genus = species.get("name").split(" ")[0]
                    # print(genus)
                    # print(get_body_codex(codex, 'Biology', body.get("name")))
                    ba = get_body_codex(codex, "Biology", body.get("name"))
                    # if not genus in str(get_body_codex(codex, 'Biology', body.get("name"))):
                    #    print(f"using {genus} {ba}")
                    results.append(species.get("name"))
        # else:
        #    if (mainstarMatch and regionMatch):
        #        results.append(species.get("name"))

    return results


def get_body_codex(codex, type, body=None):
    results = []
    for row in codex:
        if row.get("hud_category") == type and row.get("body") == body:
            results.append(row.get("english_name"))
    return results


def set_codex(i, type, body, codex):
    value = get_body_codex(codex, type, body.get("name"))
    if value:
        spanshdump["system"]["bodies"][i]["signals"][type.lower()] = value


def landable(body):
    if body.get("isLandable"):
        return True
    signals = body.get("signals")
    has_biology = signals and body.get("signals").get("signals").get(
        "$SAA_SignalType_Biological;"
    )
    has_geology = signals and body.get("signals").get("signals").get(
        "$SAA_SignalType_Geological;"
    )

    if has_biology or has_geology:
        return True
    return False


def get_stats_by_id(entryid):
    global biostats
    get_biostats()
    return jsonify(biostats.get(entryid))


def get_stats_by_name(names):
    retval = {}
    global biostats
    get_biostats()
    allnames = names.split(",")
    for name in allnames:
        for id, entry in biostats.items():
            if entry.get("name") and name.lower().strip() in entry.get("name").lower():
                retval[id] = entry
    return jsonify(retval)


def _resolve_system_id(request):
    id = request.args.get("id")
    caller = request.args.get("caller")
    systemName = request.args.get("system")
    if systemName:
        id = getId64(systemName)

    print(f"caller: {caller} id: {id} system: {systemName}")
    return id


def _augment_system_biostats(system, codex):
    """
    Shared by /codex/biostats and /codex/dump: attaches system-level cloud/anomaly signals
    and region, then per landable body attaches biology guesses, confirmed codex signals,
    and the influencing star. Mutates the `spanshdump` global (which owns `system`) in place.
    """
    global spanshdump

    scloud = get_body_codex(codex, "Cloud")
    sanomaly = get_body_codex(codex, "Anomaly")

    region, region_name = findRegion64(system.get("id64"))
    spanshdump["system"]["region"] = {"region": region, "name": region_name}

    if scloud or sanomaly:
        spanshdump["system"]["signals"] = {}

        if scloud:
            spanshdump["system"]["signals"]["cloud"] = scloud
        if sanomaly:
            spanshdump["system"]["signals"]["anomaly"] = sanomaly

    # Built once and shared across every body below - each body's own influencing_star()
    # call would otherwise rebuild these from the full body list, making the loop O(n^2).
    body_index = _body_index(system)
    parent_map = _build_parent_map(system)

    for i, body in enumerate(system.get("bodies")):
        if landable(body):
            if not spanshdump["system"]["bodies"][i].get("signals"):
                spanshdump["system"]["bodies"][i]["signals"] = {}

            inf_star = (
                influencing_star(body, system, body_index, parent_map)
                if body.get("type") == "Planet"
                else None
            )

            guess = guess_biology(body, codex, inf_star)
            if guess:
                spanshdump["system"]["bodies"][i]["signals"]["guesses"] = guess

            set_codex(i, "Biology", body, codex)
            set_codex(i, "Geology", body, codex)
            set_codex(i, "Thargoid", body, codex)
            set_codex(i, "Guardian", body, codex)
            set_codex(i, "Cloud", body, codex)
            set_codex(i, "Anomaly", body, codex)

            has_biology = guess or spanshdump["system"]["bodies"][i]["signals"].get(
                "biology"
            )
            if inf_star and has_biology:
                spanshdump["system"]["bodies"][i]["signals"]["influencingStar"] = {
                    "name": inf_star["star"].get("name"),
                    "bodyId": inf_star["star"].get("bodyId"),
                    "subType": inf_star["star"].get("subType"),
                    "method": inf_star["method"],
                    "starCount": inf_star["starCount"],
                }


def _gzip_json_response(data):
    body = gzip.compress(json.dumps(data, separators=(",", ":")).encode("utf-8"))
    response = Response(body, mimetype="application/json")
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(body))
    return response


def system_biostats(request):
    global biostats
    global spanshdump

    id = _resolve_system_id(request)

    # lazy loaders
    get_biostats()
    get_spansh_by_id(id)

    if not spanshdump:
        return jsonify({"error": "no spansh data"})

    system = spanshdump.get("system")
    codex = get_system_codex(system.get("name"))
    _augment_system_biostats(system, codex)

    # return jsonify(biostats.get("2100407"))
    return jsonify(spanshdump)


def codex_dump(request):
    """
    Same augmentation pass as /codex/biostats, but keeps the full Spansh dump (factions,
    stations, settlements - everything except fleet carriers) instead of stripping factions
    and stations outright, and gzips the JSON response body to stay under the cloud
    function output size limit that the fuller payload would otherwise risk hitting.
    """
    global biostats
    global spanshdump

    id = _resolve_system_id(request)

    get_biostats()
    get_spansh_by_id(id, keep_all_data=True)

    if not spanshdump:
        return jsonify({"error": "no spansh data"})

    system = spanshdump.get("system")
    codex = get_system_codex(system.get("name"))
    _augment_system_biostats(system, codex)

    return _gzip_json_response(spanshdump)


def quantify_codex(entryid):
    with get_cursor() as cursor:
        sql = """
            SELECT 
                `system` as systemName, 
                SQRT(POW(x - -178.65625, 2) + POW(y - 77.125, 2) + POW(z - -87.125, 2)) AS distance,
                COUNT(*) OVER () AS total_count  
            FROM 
                codex_systems
                where entryid  = %s
            ORDER BY 
                distance ASC
            LIMIT 1;

        """
        cursor.execute(sql, (entryid))
        r = cursor.fetchone()
        cursor.close()
        return jsonify(r)


def codex_name_ref(request):

    with get_cursor() as cursor:
        sql = """
            SELECT c.*,sp.reward,ci.cmdr as image_cmdr,ci.url as image_url
            FROM codex_name_ref c
            left join codex_images ci on ci.entryid = c.entryid
            left join species_prices sp on c.name LIKE REPLACE(sp.species,'_Name;','%%')
            WHERE 1 = 1 
        """
        hud_category = request.args.get("category")
        sub_class = request.args.get("species")
        english_name = None
        if request.args.get("variant") is not None:
            english_name = "%" + request.args.get("variant") + "%"

        params = []
        if hud_category is not None:
            sql += " AND c.hud_category = %s"
            params.append(hud_category)

        # Check if sub_class is populated
        if sub_class is not None:
            sql += " AND c.sub_class = %s"
            params.append(sub_class)

        # Check if english_name is populated
        if english_name is not None:
            sql += " AND c.english_name like %s"
            params.append(english_name)

        cursor.execute(sql, params)
        r = cursor.fetchall()
        cursor.close()

    res = {}

    for entry in r:
        entry["dump"] = (
            f"https://storage.googleapis.com/canonn-downloads/dumpr/{entry.get('hud_category')}/{entry.get('entryid')}.csv"
        )
        if request.args.get("hierarchy"):
            hud = entry.get("hud_category")
            genus = entry.get("sub_class")
            species = entry.get("english_name")
            if not res.get(hud):
                res[hud] = {}
            if not res.get(hud).get(genus):
                res[hud][genus] = {}
            if not res.get(hud).get(genus).get(species):
                res[hud][genus][species] = {
                    "name": entry.get("name"),
                    "entryid": entry.get("entryid"),
                    "category": entry.get("category"),
                    "sub_category": entry.get("sub_category"),
                    "platform": entry.get("platform"),
                    "reward": entry.get("reward"),
                    "dump": entry.get("dump"),
                }
        else:
            for entry in r:
                res[entry.get("entryid")] = entry
    return res


def get_gr_data():

    with get_cursor() as cursor:
        sql = """
            select distinct systemName as `system`,cast(x as char) x,cast(y as char) y,cast(z as char) z
            FROM guardian_settlements
            WHERE name LIKE '$Ancient:%%';
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        return jsonify(r)


def odyssey_subclass(request):

    with get_cursor() as cursor:
        sql = """
            select sub_class,count(*) as species from codex_name_ref where platform='odyssey'
            group by sub_class
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
    totals = 0
    for entry in r:
        totals = totals + int(entry.get("species"))
        res[entry.get("sub_class")] = entry.get("species")

    res["* Total Species"] = totals
    return res


def species_prices(request):

    r = None
    with get_cursor() as cursor:
        sql = """
            select distinct 
            SUBSTRING_INDEX(english_name,' - ',1) sub_species,
            reward,
            sub_class
            FROM codex_name_ref c
            join species_prices sp on c.name LIKE REPLACE(sp.species,'_Name;','%%')
            WHERE 1 = 1    
            order by reward desc  
        """
        cursor.execute(sql, ())
        r = cursor.fetchall()
        cursor.close()

    res = {}
    for entry in r:
        res[entry.get("sub_species")] = {
            "reward": entry.get("reward"),
            "bonus": int(entry.get("reward")) * 2,
        }
    return res


def cmdr(cmdr, request):
    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)

    print(f"limit {limit}")

    with get_cursor() as cursor:
        sql = f"""
            SELECT
                cs.`system` ,
                cs.system_address,
                JSON_ARRAYAGG(
                    JSON_OBJECT(
                        'category', cnr.category,
                        'english_nane', cnr.english_name,
                        'entryid', cnr.entryid,
                        'hud_category', cnr.hud_category,
                        'name', cnr.name,
                        'platform', cnr.platform,
                        'sub_category', cnr.sub_category,
                        'sub_class', cnr.sub_class,
                        'species', trim(SUBSTRING_INDEX(cnr.english_name,'-',1))
                    )
                )
                 AS hud_details,
                ss.x,ss.y,ss.z
            from codex_systems  cs
            join star_systems ss on ss.id64 = cs.system_address
            join codex_name_ref cnr on cs.entryid = cnr.entryid
            where cs.cmdr = %s
            GROUP BY
                cs.`system`,ss.x,ss.y,ss.z,cs.system_address
            order by cs.system_address 
            limit %s,%s	
        """
        cursor.execute(sql, (cmdr, int(offset), int(limit)))
        r = cursor.fetchall()
        cursor.close()

        retval = {}
        for entry in r:
            print(f"name :{entry.get('system')}")
            retval[entry.get("system")] = {
                "codex": json.loads(entry.get("hud_details")),
                "coords": [entry.get("x"), entry.get("y"), entry.get("z")],
            }

    return jsonify(retval)


def codex_data(request):

    hud = request.args.get("hud_category")
    sub = request.args.get("sub_class")
    eng = request.args.get("english_name")
    system = request.args.get("system")
    spe = request.args.get("species")

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)
    if request.args.get("_start"):
        offset = request.args.get("_start")
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    params = []
    clause = ""

    if hud:
        params.append(hud)
        clause = "and hud_category = %s"
    if sub:
        params.append(sub)
        clause = f"{clause} and sub_class = %s "
    if eng:
        params.append(eng)
        clause = f"{clause} and english_name = %s "
    if system:
        params.append(system)
        clause = f"{clause} and `system` = %s "
    if spe:
        params.append(spe)
        clause = f"{clause} and english_name like concat(%s,'%%') "

    params.append(int(offset))
    params.append(int(limit))

    with get_cursor() as cursor:
        sql = f"""
        select `system`,entryid,cast(x as char) x,cast(y as char) y,cast(z as char) z,
            cr.*,trim(SUBSTRING_INDEX(cr.english_name,'-',1)) as species
            FROM codex_systems cs
            INNER JOIN codex_name_ref as cr using (entryid)
            INNER JOIN (
            select s.system,s.entryid from 
            codex_systems s
                        join codex_name_ref cr on cr.entryid = s.entryid
                        where 1 = 1
                        {clause}
            limit %s,%s)
            AS my_results USING(`system`,entryid)
        """
        cursor.execute(sql, (params))
        r = cursor.fetchall()
        cursor.close()

    return r


def codex_bodies(request):

    eng = request.args.get("english_name")

    offset = request.args.get("offset", 0)
    limit = request.args.get("limit", 1000)
    if request.args.get("_start"):
        offset = request.args.get("_start")
    if request.args.get("_limit"):
        limit = request.args.get("_limit")

    params = []
    clause = ""

    if eng:
        params.append(eng)
        clause = f"{clause} and cnr.english_name = %s "

    params.append(int(offset))
    params.append(int(limit))

    with get_cursor() as cursor:
        sql = f"""
    with base_data as (
		# We can select the base data then any joins are only joining on the page that we are selecting      
    	select 
    		cs.id as system_seq,
    		cs.system as tmp_system_name,
    		cs.x,cs.y,cs.z,
    		cs.system_address,
    		cnr.*,
    		case 
	    		when cnr.hud_category = 'Biology' and 
	    			REGEXP_LIKE(cnr.name, '_(Ae|B|D|F|G|K|L|M|N|A|O|T|TTS|W|Y)_Name;$') 
	    		then SUBSTRING_INDEX(SUBSTRING_INDEX(cnr.name, '_', -2), '_', 1) 
	    		else null 
	    	end as codex_star,
    		z_order,
    		ifnull(cb.cmdr,cs.cmdr) as cmdr,
    		ifnull(cb.reported_at,cs.reported_at) as reported_at,
    		cb.id as body_seq,
    		cb.body_id
    	from codex_systems cs
    	left join codex_bodies cb on cb.entryid = cs.entryid and cb.system_address = cs.system_address 
    	join codex_name_ref cnr on cnr.entryid = cs.entryid 
        {clause}
    	order by cs.reported_at desc 
    	limit %s,%s
    ), star_systems as (
    	# now we will join on star system 
        select 
    		base_data.system_seq,
    		ifnull(ss.x,base_data.x) as x,
    		ifnull(ss.y,base_data.y) as y,
    		ifnull(ss.z,base_data.z) as z,
    		base_data.system_address,
    		base_data.english_name,
    		base_data.entryid,
    		base_data.hud_category,
    		base_data.sub_class,
    		base_data.name as variant,
    		base_data.codex_star,
    		base_data.z_order,
    		base_data.cmdr,
    		base_data.reported_at,
    		base_data.body_seq,
    		base_data.body_id,
        	ifnull(ss.name,base_data.tmp_system_name) as system_name,
        	ss.bodies_match
        from base_data
        left join star_systems ss on ss.id64 = base_data.system_address
    )     , ne as (	
    	# joining to get the nearest nebula
       	select 
    		star_systems.*,
 			(select sqrt(pow(star_systems.x-neb.x,2)+pow(star_systems.y-neb.y,2)+pow(star_systems.z-neb.z,2)) from edastro_pois neb where neb.poi_type in ('nebula','planetaryNebula') order by pow(star_systems.x-neb.x,2)+pow(star_systems.y-neb.y,2)+pow(star_systems.z-neb.z,2) asc limit 1) as nearest_nebula,
 			(select poi_type from edastro_pois neb where neb.poi_type in ('nebula','planetaryNebula') order by pow(star_systems.x-neb.x,2)+pow(star_systems.y-neb.y,2)+pow(star_systems.z-neb.z,2) asc limit 1) as nearest_nebula_type
    	from star_systems
    ), system_ids as (
    	# get a unique list of system addresses
    	select distinct system_address from base_data
    ), body_ids as (
    	# get a unique list of system addresses
    	select distinct system_address,body_id,system_name from star_systems    
    ), body_info as (
    	# We will get info on all bodies in the system and as well as current body
    	# 
    	select
    			sbs.system_address,body_ids.body_id,
    			# data for the current body
		    	max(case when sbs.body_id =  body_ids.body_id then trim(replace(sbs.name,body_ids.system_name,'')) else null end) as body,
    	    	max(case when sbs.body_id =  body_ids.body_id then sbs.sub_type else null end) as body_type,
	            max(case when sbs.body_id =  body_ids.body_id then cast(JSON_EXTRACT(sbs.raw_json,'$.rings') as json) else null end) as rings,
	            max(case when sbs.body_id =  body_ids.body_id then JSON_EXTRACT(sbs.raw_json,'$.distanceToArrival') else null end) as distanceToArrival,
				max(case when sbs.body_id =  body_ids.body_id then ifnull(nullif(JSON_UNQUOTE(sbs.raw_json->'$.atmosphereType'),'null'),'No atmosphere') else null end) as atmosphereType,
				max(case when sbs.body_id =  body_ids.body_id then cast(JSON_EXTRACT(sbs.raw_json,'$.atmosphereComposition') as json) else null end) as atmosphereComposition,
				max(case when sbs.body_id =  body_ids.body_id then JSON_UNQUOTE(sbs.raw_json->'$.gravity') else null end) as gravity,
				max(case when sbs.body_id =  body_ids.body_id then JSON_UNQUOTE(sbs.raw_json->'$.surfaceTemperature') else null end) as temperature,
				max(case when sbs.body_id =  body_ids.body_id then ifnull(JSON_UNQUOTE(sbs.raw_json->'$.volcanismType'),'No volcanism') else null end) as volcanismType,
				max(case when sbs.body_id =  body_ids.body_id then cast(JSON_EXTRACT(sbs.raw_json,'$.materials') as json) else null end) as materials,
				max(case when sbs.body_id =  body_ids.body_id then JSON_EXTRACT(sbs.raw_json,'$.orbitalEccentricity') else null end) as orbitalEccentricity,
                max(case when sbs.body_id =  body_ids.body_id then JSON_EXTRACT(sbs.raw_json,'$.parents') else null end) as parents,
                max(case when sbs.body_id =  body_ids.body_id then JSON_EXTRACT(sbs.raw_json,'$.semiMajorAxis') else null end) as semiMajorAxis,
				# aggregate data
				group_concat(distinct case when `type` = 'Planet' then sub_type else null end) as body_types_present,
				max(case when json_extract(sbs.raw_json,'$.mainStar') = true then sbs.sub_type else null end) as star_class  ,
    			GROUP_CONCAT(
    					case when sbs.type = 'Star' then
    					concat(ifnull(nullif(JSON_UNQUOTE(sbs.raw_json->'$.spectralClass'),'null'),sbs.sub_type),' ',nullif(JSON_UNQUOTE(sbs.raw_json->'$.luminosity'),'null'))
    					else null end
    				SEPARATOR ',') AS star_types
    	from body_ids
       	left join system_bodies sbs on sbs.system_address = body_ids.system_address 
    	group by body_ids.system_address,body_id 
    ), unranked_stars AS (
    SELECT 
    	bi.system_address,bi.body_id,sb.sub_type,sb.name,
    	cast(JSON_UNQUOTE(sb.raw_json->'$.absoluteMagnitude') as DECIMAL(65,30)) as absoluteMagnitude,
    	JSON_UNQUOTE(sb.raw_json->'$.surfaceTemperature') as surfaceTemperature,
    	JSON_UNQUOTE(sb.raw_json->'$.spectralClass') as spectralClass,
    	JSON_UNQUOTE(sb.raw_json->'$.luminosity') as luminosity,    	
        CASE 
            WHEN json_extract(bi.parents,'$[0].Star') = sb.body_id then
                cast(JSON_UNQUOTE(sb.raw_json->'$.absoluteMagnitude') as DECIMAL(65,30)) + 5 * LOG10(cast((bi.semiMajorAxis / 206265) / 10 as DECIMAL(65,30)))
            WHEN ABS(bi.distanceToArrival - JSON_UNQUOTE(sb.raw_json->'$.distanceToArrival')) != 0 THEN
                cast(JSON_UNQUOTE(sb.raw_json->'$.absoluteMagnitude') as DECIMAL(65,30)) + 5 * LOG10(cast((ABS(bi.distanceToArrival- JSON_UNQUOTE(sb.raw_json->'$.distanceToArrival')) * 3.08567758e-14) / 10 as DECIMAL(65,30))) 
            ELSE 
                NULL
        END AS apparent_magnitude
    FROM system_bodies sb
    join body_info bi on bi.system_address = sb.system_address
    WHERE sb.type = 'Star' 
), illuminating_stars AS (
	select data.* from (
    SELECT us.*,
        RANK() OVER (PARTITION BY system_address,body_id ORDER BY apparent_magnitude ASC) AS magrank
    FROM unranked_stars us
    ) data where magrank = 1
), codex_stars as (
	select ne.system_address,ne.body_id,
	sum(case 
		when codex_star = 'G' and sb.sub_type in ('G (White-Yellow super giant) Star', 'G (White-Yellow) Star') then 1 
     	when codex_star = 'Ae' and sb.sub_type in ('Herbig Ae/Be Star') then 1
     	when codex_star = 'D' and sb.sub_type in (
	        'White Dwarf (D) Star',
	        'White Dwarf (DA) Star',
	        'White Dwarf (DAB) Star',
	        'White Dwarf (DAV) Star',
	        'White Dwarf (DAZ) Star',
	        'White Dwarf (DB) Star',
	        'White Dwarf (DBV) Star',
	        'White Dwarf (DBZ) Star',
	        'White Dwarf (DC) Star',
	        'White Dwarf (DCV) Star',
	        'White Dwarf (DQ) Star'
    	) then 1
    	when codex_star = 'L' and sb.sub_type in ('L (Brown dwarf) Star') then 1
    	when codex_star = 'F' and sb.sub_type in ('F (White super giant) Star', 'F (White) Star') then 1
    	when codex_star = 'B' and sb.sub_type in ('B (Blue-White super giant) Star', 'B (Blue-White) Star') then 1
    	when codex_star = 'K' and sb.sub_type in ('K (Yellow-Orange giant) Star', 'K (Yellow-Orange) Star') then 1
    	when codex_star = 'M' and sb.sub_type in ('M (Red dwarf) Star', 'M (Red giant) Star', 'M (Red super giant) Star') then 1
	    when codex_star = 'N' and sb.sub_type in ('Neutron Star') then 1
	    when codex_star = 'A' and sb.sub_type in ('A (Blue-White super giant) Star', 'A (Blue-White) Star') then 1
	    when codex_star = 'O' and sb.sub_type in ('O (Blue-White) Star') then 1
	    when codex_star = 'T' and sb.sub_type in ('T (Brown dwarf) Star') then 1
	    when codex_star = 'TTS' and sb.sub_type in ('T Tauri Star') then 1
	    when codex_star = 'W' and sb.sub_type in (
			'Wolf-Rayet C Star',
	        'Wolf-Rayet N Star',
	        'Wolf-Rayet NC Star',
	        'Wolf-Rayet O Star',
	        'Wolf-Rayet Star'
	    ) then 'Y'
		when codex_star = 'Y' and sb.sub_type in ('Y (Brown dwarf) Star') then 1
		when codex_star is null then null
    else 0
    end) as codex_star_match
	from ne
	join system_bodies sb on sb.system_address = ne.system_address
	group by ne.system_address,ne.body_id
)
    # we need something that joins on body info and uses the distanceToArrival to identify the star with the highest apparent magnitude 
    # Sadly this means we have to hit system_bodies twice unless I did something clever on the body_info to get the data I want?
    select 
    	ne.*,
 	    body_info.star_class,
   	    body_info.star_types,
    	body_info.body,
    	body_info.body_type,
    	body_info.rings,
        body_info.distanceToArrival,
        body_info.atmosphereType,
        body_info.atmosphereComposition,
        body_info.gravity,
        body_info.temperature,
        body_info.volcanismType,
        body_info.materials,
        body_info.orbitalEccentricity,
        body_info.body_types_present,
        body_info.parents,
        body_info.semiMajorAxis,
        case when ne.bodies_match = 1 and ifnull(body_info.star_class,'null') != 'null' then 'Y' else 'N' end as complete,
        il.sub_type as illuminating_subtype,
        il.name as illuminating_name,
        il.apparent_magnitude,
        il.absoluteMagnitude,
        il.surfaceTemperature,
        il.spectralClass,
        il.luminosity,
                case 
	    when codex_star = 'G' and il.sub_type in ('G (White-Yellow super giant) Star', 'G (White-Yellow) Star') then 'Y' 
     	when codex_star = 'Ae' and il.sub_type in ('Herbig Ae/Be Star') then 'Y'
     	when codex_star = 'D' and il.sub_type in (
	        'White Dwarf (D) Star',
	        'White Dwarf (DA) Star',
	        'White Dwarf (DAB) Star',
	        'White Dwarf (DAV) Star',
	        'White Dwarf (DAZ) Star',
	        'White Dwarf (DB) Star',
	        'White Dwarf (DBV) Star',
	        'White Dwarf (DBZ) Star',
	        'White Dwarf (DC) Star',
	        'White Dwarf (DCV) Star',
	        'White Dwarf (DQ) Star'
    	) then 'Y'
    	when codex_star = 'L' and il.sub_type in ('L (Brown dwarf) Star') then 'Y'
    	when codex_star = 'F' and il.sub_type in ('F (White super giant) Star', 'F (White) Star') then 'Y'
    	when codex_star = 'B' and il.sub_type in ('B (Blue-White super giant) Star', 'B (Blue-White) Star') then 'Y'
    	when codex_star = 'K' and il.sub_type in ('K (Yellow-Orange giant) Star', 'K (Yellow-Orange) Star') then 'Y'
    	when codex_star = 'M' and il.sub_type in ('M (Red dwarf) Star', 'M (Red giant) Star', 'M (Red super giant) Star') then 'Y'
	    when codex_star = 'N' and il.sub_type in ('Neutron Star') then 'Y'
	    when codex_star = 'A' and il.sub_type in ('A (Blue-White super giant) Star', 'A (Blue-White) Star') then 'Y'
	    when codex_star = 'O' and il.sub_type in ('O (Blue-White) Star') then 'Y'
	    when codex_star = 'T' and il.sub_type in ('T (Brown dwarf) Star') then 'Y'
	    when codex_star = 'TTS' and il.sub_type in ('T Tauri Star') then 'Y'
	    when codex_star = 'W' and il.sub_type in (
			'Wolf-Rayet C Star',
	        'Wolf-Rayet N Star',
	        'Wolf-Rayet NC Star',
	        'Wolf-Rayet O Star',
	        'Wolf-Rayet Star'
	    ) then 'Y'
		when codex_star = 'Y' and il.sub_type in ('Y (Brown dwarf) Star') then 'Y'
		when codex_star is null then '-'
    else 'N'
    end as star_type_match,
    cs.codex_star_match
    from ne
    left join body_info on body_info.system_address = ne.system_address and body_info.body_id = ne.body_id
    left join illuminating_stars il on body_info.system_address = il.system_address and body_info.body_id = il.body_id
    left join codex_stars cs on body_info.system_address = cs.system_address and body_info.body_id = cs.body_id
        """
        cursor.execute(sql, (params))
        processed_rows = []

        # Fetch and process rows one by one
        while True:
            row = cursor.fetchone()
            if row is None:
                break

            # Create a new dictionary for the processed row
            processed_row = {}

            # Iterate over the columns in the row
            for key, value in row.items():
                try:
                    # Try to load the JSON value
                    processed_row[key] = json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    # If it's not a JSON string, just use the original value
                    processed_row[key] = value

            # Append the processed row to the list
            processed_rows.append(processed_row)
        cursor.close()

    return jsonify(processed_rows)


## replaces /poiListSignals used by Triumvitate
def poi_list_signals(request):

    systemName = request.args.get("system")
    with get_cursor() as cursor:
        sql = """
          select distinct cnr.hud_category,cnr.english_name,cr.body
          from codexreport cr 
          join codex_name_ref cnr 
          on cnr.entryid = cr.entryid 
          where cr.system  = %s
        """
        cursor.execute(sql, (systemName))
        r = cursor.fetchall()
        cursor.close()

        return jsonify(r)

    return jsonify([])


def codex_systems(request):
    r = codex_data(request)

    res = {}

    for entry in r:
        if not res.get(entry.get("system")):
            res[entry.get("system")] = {
                "codex": [],
                "coords": [entry.get("x"), entry.get("y"), entry.get("z")],
            }

        res[entry.get("system")]["codex"].append(
            {
                "category": entry.get("category"),
                "english_name": entry.get("english_name"),
                "entryid": entry.get("entryid"),
                "hud_category": entry.get("hud_category"),
                "name": entry.get("name"),
                "platform": entry.get("platform"),
                "sub_category": entry.get("sub_category"),
                "sub_class": entry.get("sub_class"),
                "species": entry.get("species"),
            }
        )
    return res


def capi_systems(request):
    data = codex_data(request)
    retval = []
    for r in data:
        retval.append(
            {
                "system": {
                    "systemName": r.get("system"),
                    "edsmCoordX": r.get("x"),
                    "edsmCoordY": r.get("y"),
                    "edsmCoordZ": r.get("z"),
                },
                "type": {
                    "hud_category": r.get("hud_category"),
                    "species": r.get("species"),
                    "type": r.get("sub_class"),
                    "journalName": r.get("english_name"),
                    "journalID": r.get("entryid"),
                },
            }
        )
    return jsonify(retval)
