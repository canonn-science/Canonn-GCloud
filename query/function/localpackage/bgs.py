"""Read-only BGS tracker API, served under /bgs/* (see docs/gcloud-api-spec.md
in the bgslisten repo; /canonnbgs/* in that spec is /bgs/* here).

Reads the replica tables in the `canonn_bgs` schema through the existing
tunnelled connection (dbutils.get_cursor). Never writes.
"""
import datetime as dt
import json
from decimal import Decimal
from functools import wraps
from os import getenv

from flask import jsonify, request

import localpackage.canonnbgs as canonnbgs
from localpackage.bgs_logic import (
    BUCKET_KEYS,
    BadRequest,
    average_excluding_latest,
    compute_trends,
    conflict_frequency,
    dt_arg,
    empty_grid,
    faction_series,
    int_arg,
    list_bucket,
    clean_cell,
    norm_system,
    order_by_swing,
    pipeline,
    stalest,
    summarise_activity,
    summarise_coverage,
    swing_from_rows,
    trend_flags,
    DAYS,
)
from localpackage.dbutils import get_cursor

BGS_DB = getenv("BGS_DATABASE", "canonn_bgs")

TRACKED_NAMES = [
    n.strip()
    for n in getenv("BGS_TRACKED_NAMES", "Canonn,Canonn Deep Space Research").split(",")
    if n.strip()
]
MAX_PAGE_SIZE = int(getenv("BGS_MAX_PAGE_SIZE", "100"))
THRESHOLDS = {
    "low_influence": float(getenv("BGS_LOW_INFLUENCE", "0.05")),
    "close_gap": float(getenv("BGS_CLOSE_GAP", "0.02")),
    "trend_flat_per_day": 0.002,
    "trend_steep_per_day": 0.01,
    "trend_horizon_days": 30.0,
    "trend_warn_days": 7.0,
}
FRESHNESS = {
    "listener_warn_minutes": 5.0,
    "listener_stale_minutes": 15.0,
    "spansh_warn_days": 9.0,
    "stalest_limit": 25,
}
SERIES_DAYS = 30
SWING_DAYS = 8
ARCHITECTS_BROWSER_CACHE_SECONDS = 3600

SYSTEMS_SORT_KEYS = {"name", "controlling_faction", "status", "data_age_hours", "influence", "swing"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _t(name):
    """Schema-qualified table name. Never built from request input."""
    return f"`{BGS_DB}`.`{name}`"


def _in(values):
    values = list(values)
    return ",".join(["%s"] * len(values)), values


def _utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _rows(sql, params=()):
    cur = get_cursor()
    try:
        cur.execute(sql, params)
        return list(cur.fetchall())
    finally:
        cur.close()


def _scalar(sql, params=()):
    rows = _rows(sql, params)
    return next(iter(rows[0].values())) if rows else None


def _clean(obj):
    """Make a value JSON-safe: Decimal -> float, datetime (naive UTC) -> ISO
    with Z, bytes -> str."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, dt.datetime):
        return obj.isoformat() + "Z"
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return obj


def _respond(data, max_age=None, compress=False):
    data = _clean(data)
    response = canonnbgs._gzip_json_response(data) if compress else jsonify(data)
    if max_age:
        response.headers["Cache-Control"] = f"public, max-age={max_age}"
    return response


def _api(f):
    """Maps BadRequest to HTTP 400 (the route wrapper turns anything else
    into a 500 and drops the connection)."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except BadRequest as err:
            return jsonify({"error": str(err)}), 400

    return wrapper


def _page_params():
    page = int_arg(request.args, "page", 0, minimum=0)
    size = int_arg(request.args, "size", 50, minimum=1, maximum=MAX_PAGE_SIZE)
    return page, size


def _envelope(data, page, size, total):
    return {
        "data": data,
        "page": page,
        "size": size,
        "total": total,
        "next": page + 1 if (page + 1) * size < total else None,
    }


def _faction_arg():
    faction = request.args.get("faction")
    if faction == "both":
        faction = None
    if faction not in (None, "", "canonn", "cdsr"):
        raise BadRequest("'faction' must be 'canonn', 'cdsr' or 'both'")
    return faction or None


def _system_filters(status, q, faction):
    conditions, params = [], []
    if status:
        conditions.append("s.status = %s")
        params.append(status)
    if faction == "canonn":
        conditions.append("s.canonn_present = 1")
    elif faction == "cdsr":
        conditions.append("s.cdsr_present = 1")
    if q:
        escaped = q.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        conditions.append("LOWER(s.name) LIKE LOWER(%s) ESCAPE '!'")
        params.append(f"%{escaped}%")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


def _json_or_none(text):
    try:
        return json.loads(text) if text else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# batched data access (one query per table per page)
# ---------------------------------------------------------------------------
def _current_factions(addresses):
    """{address: [faction_influence rows of its newest current snapshot]}"""
    if not addresses:
        return {}
    marks, params = _in(addresses)
    rows = _rows(
        f"SELECT sn.system_address AS _addr, sn.id AS _snap, sn.first_seen AS _first, fi.* "
        f"FROM {_t('snapshots')} sn JOIN {_t('faction_influence')} fi ON fi.snapshot_id = sn.id "
        f"WHERE sn.system_address IN ({marks}) AND sn.superseded_at IS NULL",
        params,
    )
    newest = {}
    for r in rows:
        key = (r["_first"], r["_snap"])
        if r["_addr"] not in newest or key > newest[r["_addr"]]:
            newest[r["_addr"]] = key
    out = {}
    for r in rows:
        if (r["_first"], r["_snap"]) == newest[r["_addr"]]:
            out.setdefault(r["_addr"], []).append(r)
    return out


def _series_many(addresses, since):
    if not addresses:
        return {}
    marks, params = _in(addresses)
    rows = _rows(
        f"SELECT sn.system_address, sn.first_seen, sn.superseded_at, fi.faction_name, fi.influence "
        f"FROM {_t('snapshots')} sn JOIN {_t('faction_influence')} fi ON fi.snapshot_id = sn.id "
        f"WHERE sn.system_address IN ({marks}) "
        f"AND (sn.superseded_at IS NULL OR sn.superseded_at >= %s) "
        f"ORDER BY sn.first_seen, sn.id",
        params + [since],
    )
    out = {}
    for r in rows:
        out.setdefault(r["system_address"], []).append(r)
    return out


def _tracked_series_since(since):
    marks, params = _in(TRACKED_NAMES)
    rows = _rows(
        f"SELECT sn.system_address, sn.first_seen, sn.superseded_at, fi.faction_name, fi.influence "
        f"FROM {_t('snapshots')} sn JOIN {_t('faction_influence')} fi ON fi.snapshot_id = sn.id "
        f"WHERE fi.faction_name IN ({marks}) "
        f"AND (sn.superseded_at IS NULL OR sn.superseded_at >= %s) "
        f"ORDER BY sn.first_seen, sn.id",
        params + [since],
    )
    out = {}
    for r in rows:
        out.setdefault(r["system_address"], []).append(r)
    return out


def _by_address(table, addresses, extra_where="", order=""):
    if not addresses:
        return {}
    marks, params = _in(addresses)
    rows = _rows(
        f"SELECT * FROM {_t(table)} WHERE system_address IN ({marks}) {extra_where} {order}",
        params,
    )
    out = {}
    for r in rows:
        out.setdefault(r["system_address"], []).append(r)
    return out


def _last_conflict_end(addresses):
    if not addresses:
        return {}
    marks, params = _in(addresses)
    rows = _rows(
        f"SELECT * FROM {_t('events')} WHERE system_address IN ({marks}) AND type = 'conflict_end' "
        f"ORDER BY ts DESC, id DESC",
        params,
    )
    out = {}
    for r in rows:
        out.setdefault(r["system_address"], r)
    return out


def _latest_architects(names):
    """{lower name: newest architects row}. A system can have several
    submissions; the newest by submitted_at (then id) wins."""
    if not names:
        return {}
    marks, params = _in(names)
    rows = _rows(
        f"SELECT system_name, architect_name, canonn_architect, preferred_faction "
        f"FROM {_t('architects')} WHERE system_name IN ({marks}) "
        f"ORDER BY submitted_at, id",
        params,
    )
    # ascending order: later rows overwrite earlier ones
    return {r["system_name"].lower(): r for r in rows}


def _overrides(names):
    """{lower name: bgs_overrides row}"""
    if not names:
        return {}
    marks, params = _in(names)
    rows = _rows(
        f"SELECT system_name, faction, position, details "
        f"FROM {_t('bgs_overrides')} WHERE system_name IN ({marks})",
        params,
    )
    return {r["system_name"].lower(): r for r in rows}


def _summary_context(systems, now):
    addresses = [s["system_address"] for s in systems]
    names = [s["name"] for s in systems]
    return {
        "architects": _latest_architects(names),
        "overrides": _overrides(names),
        "now": now,
        "series": _series_many(addresses, now - dt.timedelta(days=SERIES_DAYS)),
        "factions": _current_factions(addresses),
        "running": _by_address("faction_running", addresses),
        "pairs": _by_address("pair_stats", addresses),
        "open_conflicts": _by_address(
            "conflicts", addresses, "AND status <> 'ended'", "ORDER BY first_seen, id"
        ),
        "last_conflict_end": _last_conflict_end(addresses),
    }


def _build_summary(system, ctx):
    address = system["system_address"]
    now = ctx["now"]
    running = {r["faction_name"]: r for r in ctx["running"].get(address, [])}
    series = faction_series(ctx["series"].get(address, []))
    sparkline = {n: [v for _ts, v in pts] for n, pts in series.items() if n in TRACKED_NAMES}

    current = ctx["factions"].get(address, [])
    ordered = sorted(current, key=lambda f: -float(f["influence"]))

    flags, lead_gap = [], []
    for idx, f in enumerate(ordered):
        if f["faction_name"] not in TRACKED_NAMES:
            continue
        influence = float(f["influence"])
        if influence < THRESHOLDS["low_influence"]:
            flags.append(f"{f['faction_name']}_below_threshold")
        neighbours = []
        if idx > 0:
            neighbours.append(ordered[idx - 1])
        if idx + 1 < len(ordered):
            neighbours.append(ordered[idx + 1])
        if neighbours:
            near = min(neighbours, key=lambda n: abs(influence - float(n["influence"])))
            margin = influence - float(near["influence"])
            lead_gap.append({"faction": f["faction_name"], "margin": margin, "against": near["faction_name"]})
            if abs(margin) <= THRESHOLDS["close_gap"]:
                flags.append(f"{f['faction_name']}_close_gap")

    if system["status"] == "retreated":
        flags.append("recent_retreat")

    trends = compute_trends(
        series,
        {f["faction_name"]: float(f["influence"]) for f in current},
        TRACKED_NAMES,
        {g["faction"]: g["against"] for g in lead_gap},
        now,
        THRESHOLDS,
    )
    flags.extend(trend_flags(trends, THRESHOLDS))

    last_event = ctx["last_conflict_end"].get(address)
    last_seen = system["last_seen"]
    key = (system["name"] or "").lower()
    architect = ctx["architects"].get(key)
    override = ctx["overrides"].get(key)
    return {
        "architect": (
            {
                "architect_name": architect["architect_name"],
                "canonn_architect": architect["canonn_architect"],
                "preferred_faction": architect["preferred_faction"],
            }
            if architect
            else None
        ),
        "bgs_override": (
            {
                "faction": override["faction"],
                "position": override["position"],
                "details": override["details"],
            }
            if override
            else None
        ),
        # string: id64 values exceed JavaScript's safe integer range
        "system_address": str(address),
        "name": system["name"],
        "controlling_faction": system["controlling_faction"],
        "status": system["status"],
        "canonn_present": bool(system["canonn_present"]),
        "cdsr_present": bool(system["cdsr_present"]),
        "stations_controlled": system["stations_controlled"],
        "stations_named": system["stations_named"],
        "sparkline": sparkline,
        "lead_gap": lead_gap,
        "trend": trends,
        "swing": swing_from_rows(ctx["series"].get(address, []), TRACKED_NAMES, now),
        "states": [
            {
                "faction": f["faction_name"],
                "active": _json_or_none(f["active_states"]) or [],
                "pending": _json_or_none(f["pending_states"]) or [],
            }
            for f in current
            if f["faction_name"] in TRACKED_NAMES
        ],
        "last_conflict": _json_or_none(last_event["detail"]) if last_event else None,
        "conflicts": [
            {
                "war_type": c["war_type"],
                "status": c["status"],
                "faction_a": c["faction_a"],
                "faction_b": c["faction_b"],
                "won_days_a": c["won_days_a"],
                "won_days_b": c["won_days_b"],
                "stake_a": c["stake_a"],
                "stake_b": c["stake_b"],
                "involves_us": c["faction_a"] in TRACKED_NAMES or c["faction_b"] in TRACKED_NAMES,
                "first_seen": c["first_seen"],
            }
            for c in ctx["open_conflicts"].get(address, [])
        ],
        "conflict_frequency": conflict_frequency(ctx["pairs"].get(address, []), now),
        "avg_influence": {
            name: average_excluding_latest(r["sum_influence"], r["day_count"], r["last_influence"])
            for name, r in running.items()
            if name in TRACKED_NAMES
        },
        "data_age_hours": (now - last_seen).total_seconds() / 3600.0 if last_seen else None,
        "last_seen": last_seen.isoformat() + "Z" if last_seen else None,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@_api
def systems():
    generated_at = _utcnow()  # before any query: it is the client's refresh cursor
    page, size = _page_params()
    status = request.args.get("status") or None
    q = request.args.get("q") or None
    sort = request.args.get("sort")
    direction = "DESC" if request.args.get("dir") == "desc" else "ASC"
    faction = _faction_arg()
    changed_since = dt_arg(request.args, "changed_since")
    where, params = _system_filters(status, q, faction)

    if changed_since is not None:
        cutoff = changed_since - dt.timedelta(seconds=10)
        join = f"{_t('systems')} s JOIN {_t('system_changes')} c ON c.system_address = s.system_address"
        changed_where = (where + " AND " if where else "WHERE ") + "c.changed_at > %s"
        changed_total = _scalar(f"SELECT COUNT(*) FROM {join} {changed_where}", params + [cutoff])
        rows = _rows(
            f"SELECT s.* FROM {join} {changed_where} ORDER BY s.name LIMIT %s",
            params + [cutoff, MAX_PAGE_SIZE * 2],
        )
        total = _scalar(f"SELECT COUNT(*) FROM {_t('systems')} s {where}", params)
        ctx = _summary_context(rows, generated_at)
        return _respond(
            {
                "data": [_build_summary(r, ctx) for r in rows],
                "changed_total": changed_total,
                "overflow": changed_total > len(rows),
                "total": total,
                "since": changed_since.isoformat(),
                "generated_at": generated_at.isoformat(),
            }
        )

    if sort not in SYSTEMS_SORT_KEYS:
        sort = "name"
    total = _scalar(f"SELECT COUNT(*) FROM {_t('systems')} s {where}", params)

    if sort == "swing":
        # Not a column: order the whole filtered set, then slice the page.
        all_rows = _rows(f"SELECT s.* FROM {_t('systems')} s {where}", params)
        ordered = order_by_swing(
            all_rows,
            _tracked_series_since(generated_at - dt.timedelta(days=SWING_DAYS)),
            TRACKED_NAMES,
            generated_at,
            biggest_first=(direction == "DESC"),
        )
        rows = ordered[page * size:(page + 1) * size]
    else:
        join = f"{_t('systems')} s"
        if sort == "influence":
            marks, tracked = _in(TRACKED_NAMES)
            join += (
                f" LEFT JOIN (SELECT sn.system_address, MAX(fi.influence) AS influence "
                f"FROM {_t('snapshots')} sn JOIN {_t('faction_influence')} fi ON fi.snapshot_id = sn.id "
                f"WHERE sn.superseded_at IS NULL AND fi.faction_name IN ({marks}) "
                f"GROUP BY sn.system_address) ia ON ia.system_address = s.system_address"
            )
            params_join = tracked
            order = f"COALESCE(ia.influence, -1) {direction}"
        else:
            params_join = []
            if sort == "controlling_faction":
                order = f"s.controlling_faction {direction}"
            elif sort == "status":
                order = (
                    "CASE s.status WHEN 'active' THEN 0 WHEN 'watching' THEN 1 "
                    f"WHEN 'retreated' THEN 2 ELSE 3 END {direction}"
                )
            elif sort == "data_age_hours":
                # smaller age (larger last_seen) first on asc: flip the column
                order = f"s.last_seen {'ASC' if direction == 'DESC' else 'DESC'}"
            else:
                order = f"s.name {direction}"
        rows = _rows(
            f"SELECT s.* FROM {join} {where} ORDER BY {order}, s.name ASC LIMIT %s OFFSET %s",
            params_join + params + [size, page * size],
        )

    ctx = _summary_context(rows, generated_at)
    body =_envelope([_build_summary(r, ctx) for r in rows], page, size, total)
    body["generated_at"] = generated_at.isoformat()
    return _respond(body, max_age=30, compress=True)


@_api
def system_detail(address):
    now = _utcnow()
    rows = _rows(f"SELECT * FROM {_t('systems')} WHERE system_address = %s", [address])
    if not rows:
        return jsonify({"error": "not found"}), 404
    summary = _build_summary(rows[0], _summary_context(rows, now))
    summary["pair_stats"] = [
        dict(r, system_address=str(r["system_address"]))
        for r in _rows(f"SELECT * FROM {_t('pair_stats')} WHERE system_address = %s", [address])
    ]
    running = _rows(f"SELECT * FROM {_t('faction_running')} WHERE system_address = %s", [address])
    summary["running"] = [
        dict(
            r,
            system_address=str(r["system_address"]),
            avg_influence=average_excluding_latest(r["sum_influence"], r["day_count"], r["last_influence"]),
        )
        for r in running
    ]
    return _respond(summary, max_age=30)


@_api
def system_history(address):
    since = dt_arg(request.args, "from") or _utcnow() - dt.timedelta(days=SERIES_DAYS)
    to = dt_arg(request.args, "to")
    sql = (
        f"SELECT sn.id AS snapshot_id, sn.utc_day, sn.first_seen, sn.last_confirmed, sn.source, "
        f"fi.faction_name, fi.influence, fi.faction_state, fi.active_states, fi.pending_states, "
        f"fi.recovering_states, fi.government, fi.allegiance "
        f"FROM {_t('snapshots')} sn JOIN {_t('faction_influence')} fi ON fi.snapshot_id = sn.id "
        f"WHERE sn.system_address = %s AND sn.first_seen >= %s"
    )
    params = [address, since]
    if to is not None:
        sql += " AND sn.first_seen <= %s"
        params.append(to)
    sql += " ORDER BY sn.first_seen, sn.id"
    return _respond({"data": _rows(sql, params)}, max_age=30)


@_api
def system_conflicts(address):
    page, size = _page_params()
    total = _scalar(f"SELECT COUNT(*) FROM {_t('conflicts')} WHERE system_address = %s", [address])
    rows = _rows(
        f"SELECT * FROM {_t('conflicts')} WHERE system_address = %s "
        f"ORDER BY first_seen DESC, id DESC LIMIT %s OFFSET %s",
        [address, size, page * size],
    )
    data = [
        dict(r, system_address=str(r["system_address"]), outcome_inferred=bool(r["outcome_inferred"]))
        for r in rows
    ]
    return _respond(_envelope(data, page, size, total), max_age=30)


@_api
def events():
    page, size = _page_params()
    system_address = int_arg(request.args, "system_address", None)
    since = dt_arg(request.args, "since")
    event_type = request.args.get("type") or None
    conditions, params = [], []
    if system_address is not None:
        conditions.append("system_address = %s")
        params.append(system_address)
    if since is not None:
        conditions.append("ts >= %s")
        params.append(since)
    if event_type:
        conditions.append("type = %s")
        params.append(event_type)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    total = _scalar(f"SELECT COUNT(*) FROM {_t('events')} {where}", params)
    rows = _rows(
        f"SELECT id, ts, system_address, faction_name, type, detail FROM {_t('events')} {where} "
        f"ORDER BY ts DESC, id DESC LIMIT %s OFFSET %s",
        params + [size, page * size],
    )
    data = [dict(r, system_address=str(r["system_address"])) for r in rows]
    return _respond(_envelope(data, page, size, total), max_age=30)


@_api
def activity():
    address = int_arg(request.args, "system_address", None)
    faction = _faction_arg()
    conditions, params = [], []
    join = ""
    if address is not None:
        conditions.append("a.system_address = %s")
        params.append(address)
    if faction:
        join = f"JOIN {_t('systems')} s ON s.system_address = a.system_address"
        conditions.append("s.canonn_present = 1" if faction == "canonn" else "s.cdsr_present = 1")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    grid = empty_grid()
    for r in _rows(
        f"SELECT a.dow, a.hour, SUM(a.count) AS total FROM {_t('activity_hourly')} a {join} "
        f"{where} GROUP BY a.dow, a.hour",
        params,
    ):
        if 0 <= r["dow"] < 7 and 0 <= r["hour"] < 24:
            grid[r["dow"]][r["hour"]] = int(r["total"])
    n_systems = _scalar(
        f"SELECT COUNT(DISTINCT a.system_address) FROM {_t('activity_hourly')} a {join} {where}", params
    )
    since = _scalar(f"SELECT `value` FROM {_t('health_counters')} WHERE `key` = 'activity_since'")

    body = summarise_activity(grid)
    body.update(
        {"grid": grid, "days": DAYS, "timezone": "UTC", "systems": int(n_systems or 0), "since": since or None}
    )
    return _respond(body, max_age=60)


def _counters():
    return {r["key"]: r["value"] for r in _rows(f"SELECT `key`, `value` FROM {_t('health_counters')}")}


def _coverage_rows(faction):
    where = ""
    if faction == "canonn":
        where = "WHERE s.canonn_present = 1"
    elif faction == "cdsr":
        where = "WHERE s.cdsr_present = 1"
    return _rows(
        f"SELECT s.system_address, s.name, s.status, s.canonn_present, s.cdsr_present, s.last_seen, "
        f"n.last_confirmed, sn.source "
        f"FROM {_t('systems')} s LEFT JOIN ("
        f"SELECT system_address, MAX(id) AS snapshot_id, MAX(last_confirmed) AS last_confirmed "
        f"FROM {_t('snapshots')} WHERE superseded_at IS NULL GROUP BY system_address) n "
        f"ON n.system_address = s.system_address "
        f"LEFT JOIN {_t('snapshots')} sn ON sn.id = n.snapshot_id {where}"
    )


@_api
def coverage():
    now = _utcnow()
    limit = int_arg(request.args, "stale_limit", int(FRESHNESS["stalest_limit"]), minimum=0, maximum=200)
    rows = _coverage_rows(_faction_arg())
    counters = _counters()
    extras = {
        # the tracker publishes the live counts of its un-replicated tables
        "candidates_pending": _int(counters.get("pending_candidates")),
        "absence_watch": _int(counters.get("absence_watch")),
        "outbox_pending": _int(counters.get("outbox_pending")),
        "duplicate_current_snapshots": _int(counters.get("duplicate_current_snapshots")),
    }
    body = summarise_coverage(rows, now)
    body["stalest"] = stalest(rows, now, limit)
    body["pipeline"] = pipeline(counters, extras, now, FRESHNESS)
    body["generated_at"] = now.isoformat()
    return _respond(body, max_age=60, compress=True)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@_api
def coverage_systems():
    bucket = request.args.get("bucket", "")
    if bucket not in BUCKET_KEYS:
        raise BadRequest("'bucket' must be one of: " + ", ".join(BUCKET_KEYS))
    faction = _faction_arg()
    page, size = _page_params()
    items = list_bucket(_coverage_rows(faction), bucket, _utcnow())
    return _respond(
        _envelope(items[page * size:(page + 1) * size], page, size, len(items)), max_age=60, compress=True
    )


@_api
def architects():
    """Latest architect submission per system, read from the architects table.
    Response shape is unchanged from the sheet-backed version; the sheet-only
    fields are kept for client compatibility."""
    rows = _rows(
        f"SELECT system_name, architect_name, canonn_architect, preferred_faction "
        f"FROM {_t('architects')} ORDER BY submitted_at, id"
    )
    # ascending order: the newest row per system overwrites earlier ones
    latest = {norm_system(r["system_name"]): r for r in rows}

    systems_out = {}
    for r in _rows(f"SELECT name FROM {_t('systems')}"):
        row = latest.get(norm_system(r["name"]))
        if not row:
            continue
        entry = {
            "architect": clean_cell(row["architect_name"]),
            "preferred_faction": clean_cell(row["preferred_faction"]),
        }
        if entry["architect"] or entry["preferred_faction"]:
            entry["canonn_architect"] = row["canonn_architect"]
            systems_out[r["name"]] = entry

    return _respond(
        {
            "enabled": True,
            "systems": systems_out,
            "sheet_fetched_at": None,
            "stale": False,
            "error": None,
            "browser_cache_seconds": ARCHITECTS_BROWSER_CACHE_SECONDS,
            "generated_at": _utcnow().isoformat(),
        },
        max_age=300,
    )


@_api
def health():
    return _respond(_counters())
