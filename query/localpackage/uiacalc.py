from math import acos, degrees, sqrt, radians, sin
import json
from this import d
import requests
from trianglesolver import solve
from flask import jsonify


class objdict(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            None

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError("No such attribute: " + name)


def get_systems(target, dest, observer):
    url = f"https://www.edsm.net/api-v1/systems?showCoordinates=1&systemName[]={target}&systemName[]={dest}&systemName[]={observer}"
    r = requests.get(url)

    values = r.json()
    systems = {}
    for system in values:
        if system.get("name") == target:
            systems["target"] = list(system.get("coords").values())
        if system.get("name") == target:
            systems["origin"] = list(system.get("coords").values())
        if system.get("name") == dest:
            systems["dest"] = list(system.get("coords").values())
        if system.get("name") == observer:
            systems["observer"] = list(system.get("coords").values())
    return objdict(systems)


def dist(a, b):
    return sqrt(pow(a[0]-b[0], 2)+pow(a[1]-b[1], 2)+pow(a[2]-b[2], 2))


def display(a, b, c, A, B, C):
    print([a, b, c, degrees(A), degrees(B), degrees(C)])


def getdatum(C, a, A):
    a, b, c, A, B, C = solve(A=A, C=C, a=a)
    #display(a, b, c, A, B, C)
    return c, b


def resolve(a=None, b=None, c=None, A=None, B=None, C=None):
    a, b, c, A, B, C = solve(a=a, b=b, c=c, A=A, B=B, C=C)
    return objdict({
        "a": a,
        "b": b,
        "c": c,
        "A": A,
        "B": B,
        "C": C,
    })


"""
    Three system names,
    The distance between target and dest measured on the screen using IC Measure
    The distance from target to anomaly measured on the screen using IC Measure

    It will look up the system coords
    perform all calculations
    spit out a value in ly

"""


def calc_position(target, dest, observer, length, sample):
    systems = get_systems(target, dest, observer)
    # print(systems)

    a = dist(systems.observer, systems.dest)
    b = dist(systems.observer, systems.target)
    c = dist(systems.target, systems.dest)

    a, b, c, A, B, C = solve(a=a, b=b, c=c)
    A1 = radians(90)

    c1, b1 = getdatum(C, a, A1)
    # c1 is the line between the target and destination measured in light years
    # so now we can convert the units to ly
    units = c1/length
    # we need to get the angle C2 with length c2 and b1 A1=90
    c2 = sample*units
    C2 = resolve(c=c2, A=radians(90), b=b1).get("C")
    result = resolve(C=C2, b=b, A=A).get("c")
    print(f"result {result} out of {c}")
    return jsonify(result)


def calc_uia(origin, dest, observer, limit, offset, length, sample):
    # limit/offset are expressed as a percentage of length
    # 100% 50% etc
    tEG = sample/length
    tGB = (length-sample)/length

    systems = get_systems(origin, dest, observer)
    # print(systems)

    BC = dist(systems.observer, systems.dest)
    AC = dist(systems.observer, systems.origin)
    AB = dist(systems.origin, systems.dest)

    # this is the distance from the start we are going to test
    # this will be half way between the range
    print(f"AB {AB} {limit} {offset}")
    AD = (AB/100) * ((offset-limit)/2)
    print(f"AD {AD}")
    DB = AB-AD

    # ABC is the triangle formed by observer origin and destination
    print(f"resolve(a={BC}, c={AC}, b={AB})")
    ABC = resolve(a=BC, b=AC, c=AB)
    DBC = resolve(a=BC, c=DB, B=ABC.B)
    DC = DBC.b

    # get the height
    GB = BC*(sin(radians(ABC.C)))
    GC = DBC.b

    print(f"resolve(a={DC}, c={AD}, b={AC})")
    ADC = resolve(a=DC, c=AD, b=AC)
    print(f"resolve(a={GC}, B=90, C={ABC.C})")
    EGC = resolve(a=GC, B=90, C=ADC.C)
    EG = EGC.c
    EB = EGC.c+GB

    # now we have lengths we can convert into fractions of length
    rEG = EG/EB
    rGB = (EB-EG)/EB

    print(f"{rEG} vs {tEG}")
