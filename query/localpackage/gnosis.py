import datetime
from datetime import date
import pytz


def gnosis(ds=None):

    def weeks_between(d1, d2):
        result = (d1-d2).days//7
        return result

    if ds:
        target = pytz.utc.localize(
            datetime.datetime.strptime(ds+" 07", "%Y-%m-%d %H"))
    else:
        target = pytz.utc.localize(datetime.datetime.utcnow())

    ref_date = pytz.utc.localize(
        datetime.datetime.strptime("2020-09-17 07", "%Y-%m-%d %H"))

    systems = [
        {"system": "HIP 17862",
            "desc": "Join the Gnosis to investigate the thargoid wreckage", "coords": [-81.4375, -151.90625, -359.59375]},
        {"system": "Pleiades Sector PN-T b3-0",
            "desc": "All aboard the Gnosis to investigate the Barnacle Forest", "coords": [-79.53125, -199.9375, -361.593750]},
        {"system": "Synuefe PR-L b40-1",
            "desc": "Visit the protolagrange clouds on the Gnosis (Subject to availability)", "coords": [365.78125, -291.75, -188.65625]},
        {"system": "HIP 18120",
            "desc": "Space pumpkin carving on board the Gnosis", "coords": [345.75, -435.71875, -125.5]},
        {"system": "IC 2391 Sector CQ-Y c16",
            "desc": "Light up the guardian beacons on the Gnosis", "coords": [559.875, -87.15625, -33.15625]},
        {"system": "Kappa-1 Volantis",
            "desc": "Join the Gnosis for a relaxing meditation session to the sound of the brain trees", "coords": [396.90625, -142.5625, 106.09375]},
        {"system": "Epsilon Indi",
            "desc": "Take a thrilling trip around Mitterand Hollow on the Gnosis", "coords": [3.125, -8.875, 7.125]},
        {"system": "Varati", "desc": "Visit the home of Canonn Interstellar Research on the Gnosis",
            "coords": [-178.65625, 77.125, -87.125]}
    ]

    wb = weeks_between(target, ref_date)
    wp = wb % 8

    return systems[wp]


def entry_point(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    request_args = request.args

    if request_args and 'date' in request_args:
        return gnosis(request_args["date"])
    else:
        return gnosis()
