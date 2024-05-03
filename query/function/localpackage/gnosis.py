import datetime
from datetime import date
import pytz
from datetime import datetime, timedelta


def count_thursdays(start_date):
    current_date = datetime.now()
    start_date = datetime.strptime(start_date, "%y-%m-%d")

    # Calculate the number of days between the start date and the current date
    num_days = (current_date - start_date).days

    # Count the number of Thursdays within the range
    count = 0
    for i in range(num_days + 1):
        date = start_date + timedelta(days=i)
        if date.weekday() == 3:  # Thursday is represented by 3
            count += 1

    return count


def cycle_list(lst, n):
    length = len(lst)
    final_index = (
        n - 1
    ) % length  # Calculate the final index based on the number of cycles

    return lst[final_index]


def get_next_thursday_date(current_date):
    days_ahead = (
        3 - current_date.weekday() + 7
    ) % 7  # Calculate the number of days until the next Thursday
    next_thursday = current_date + timedelta(days=days_ahead)
    return next_thursday


def last_thursday(current_date):
    # Get the weekday (0 = Monday, 1 = Tuesday, ..., 6 = Sunday)
    weekday = current_date.weekday()

    # Calculate the number of days to subtract to get to the last Thursday
    days_to_subtract = (weekday - 3) % 7

    # If today is Thursday, return today's date
    if weekday == 3:
        return current_date
    else:
        # Subtract the days to get to the last Thursday
        last_thursday_date = current_date - timedelta(days=days_to_subtract)
        return last_thursday_date


# Example usage:

systems = [
    {
        "system": "Varati",
        "desc": "Visit the home of Canonn Interstellar Research on the Gnosis",
        "coords": [-178.65625, 77.125, -87.125],
    },
    {
        "system": "HIP 17862",
        "desc": "Join the Gnosis to investigate the thargoid wreckage",
        "coords": [-81.4375, -151.90625, -359.59375],
    },
    {
        "system": "Pleiades Sector PN-T b3-0",
        "desc": "All aboard the Gnosis to investigate the Barnacle Forest",
        "coords": [-79.53125, -199.9375, -361.593750],
    },
    {
        "system": "Synuefe PR-L b40-1",
        "desc": "Visit the protolagrange clouds on the Gnosis (Subject to availability)",
        "coords": [365.78125, -291.75, -188.65625],
    },
    {
        "system": "HIP 18120",
        "desc": "Space pumpkin carving on board the Gnosis",
        "coords": [345.75, -435.71875, -125.5],
    },
    {
        "system": "IC 2391 Sector CQ-Y c16",
        "desc": "Light up the guardian beacons on the Gnosis",
        "coords": [559.875, -87.15625, -33.15625],
    },
    {
        "system": "Kappa-1 Volantis",
        "desc": "Join the Gnosis for a relaxing meditation session to the sound of the brain trees",
        "coords": [396.90625, -142.5625, 106.09375],
    },
    {
        "system": "Epsilon Indi",
        "desc": "Take a thrilling trip around Mitterand Hollow on the Gnosis",
        "coords": [3.125, -8.875, 7.125],
    },
]


def get_schedule():
    start_date = "20-09-17"
    thursdays_count = count_thursdays(start_date)
    schedule = []

    # sort the system list so the current week is first
    for r in range(len(systems)):
        schedule.append(cycle_list(systems, thursdays_count + r))

    arrival = last_thursday(datetime.now().date())
    for s in schedule:
        s["arrival"] = arrival.strftime("%Y-%m-%d")
        s["departure"] = arrival + timedelta(days=7)
        arrival = arrival + timedelta(days=7)

    return schedule


def gnosis(ds=None):
    global systems

    def weeks_between(d1, d2):
        result = (d1 - d2).days // 7
        return result

    if ds:
        target = pytz.utc.localize(datetime.strptime(ds + " 07", "%Y-%m-%d %H"))
    else:
        target = pytz.utc.localize(datetime.utcnow())

    ref_date = pytz.utc.localize(datetime.strptime("2020-09-17 07", "%Y-%m-%d %H"))

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

    if request_args and "date" in request_args:
        return gnosis(request_args["date"])
    else:
        return gnosis()
