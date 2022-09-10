from math import acos, degrees, sqrt, radians
import json
from this import d
import requests
from trianglesolver import solve
from flask import jsonify

def get_systems(target, dest, observer):
    url = f"https://www.edsm.net/api-v1/systems?showCoordinates=1&systemName[]={target}&systemName[]={dest}&systemName[]={observer}"
    r = requests.get(url)

    values = r.json()
    systems = {}
    for system in values:
        if system.get("name") == target:
            systems["target"] = list(system.get("coords").values())
        if system.get("name") == dest:
            systems["dest"] = list(system.get("coords").values())
        if system.get("name") == observer:
            systems["observer"] = list(system.get("coords").values())
    return systems


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
    return {
        "a": a,
        "b": b,
        "c": c,
        "A": A,
        "B": B,
        "C": C,
    }


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

    a = dist(systems.get("observer"), systems.get("dest"))
    b = dist(systems.get("observer"), systems.get("target"))
    c = dist(systems.get("target"), systems.get("dest"))
    
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

