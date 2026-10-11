"""Pure BGS logic (no database, no Flask): trend/swing maths, coverage
buckets, the activity heat-map summary, parameter parsing and the
architect-sheet parsing. Ported from the bgslisten tracker modules
(tracker/trend.py, coverage.py, activity.py, architect.py, api/params.py)
so the behaviour matches the existing dashboard.
"""
from __future__ import annotations

import datetime as dt
import re

Series = list[tuple[dt.datetime, float]]


# ---------------------------------------------------------------------------
# request parameters
# ---------------------------------------------------------------------------
class BadRequest(ValueError):
    """Malformed query parameter; the route maps it to HTTP 400."""


def int_arg(args, name, default, minimum=None, maximum=None):
    raw = args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise BadRequest(f"'{name}' must be an integer")
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def dt_arg(args, name) -> dt.datetime | None:
    """ISO-8601 -> naive UTC datetime (the DB stores naive UTC)."""
    raw = args.get(name)
    if not raw:
        return None
    text = raw.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    # An unescaped '+' in a query string is decoded to a space.
    text = re.sub(r" (\d\d:\d\d)$", r"+\1", text)
    try:
        value = dt.datetime.fromisoformat(text)
    except ValueError:
        raise BadRequest(f"'{name}' must be an ISO-8601 date/time")
    if value.tzinfo is not None:
        value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return value


# ---------------------------------------------------------------------------
# trend / swing
# ---------------------------------------------------------------------------
TREND_DEFAULTS = {
    "trend_flat_per_day": 0.002,
    "trend_steep_per_day": 0.01,
    "trend_horizon_days": 30.0,
    "trend_warn_days": 7.0,
}

# (name, window in days, minimum observed span in days to trust the number)
WINDOWS = (("24h", 1.0, 0.25), ("7d", 7.0, 1.0))


def _setting(thresholds: dict, key: str) -> float:
    return float(thresholds.get(key, TREND_DEFAULTS[key]))


def average_excluding_latest(sum_influence, day_count, last_influence) -> float | None:
    """Mean daily influence over the days before the latest one."""
    if not day_count:
        return None
    if day_count == 1 or last_influence is None:
        return float(sum_influence) / day_count
    return (float(sum_influence) - float(last_influence)) / (day_count - 1)


def value_at(series: Series, when: dt.datetime) -> float | None:
    found = None
    for ts, value in series:
        if ts <= when:
            found = value
        else:
            break
    return found


def window_change(series: Series, now, window_days, min_span_days) -> dict | None:
    if not series:
        return None
    current = series[-1][1]
    start = now - dt.timedelta(days=window_days)
    base = value_at(series, start)
    base_time = start
    if base is None:
        base_time, base = series[0]
    span = (now - base_time).total_seconds() / 86400.0
    if span < min_span_days:
        return None
    change = current - base
    return {"change": change, "per_day": change / span, "span_days": span}


def _direction(rate, flat) -> str:
    if rate is None:
        return "unknown"
    if rate > flat:
        return "up"
    if rate < -flat:
        return "down"
    return "flat"


def _days_or_none(days, horizon):
    return round(days, 1) if 0 <= days <= horizon else None


def compute_trends(series_by_faction, current, tracked, neighbors, now, thresholds) -> dict:
    flat = _setting(thresholds, "trend_flat_per_day")
    horizon = _setting(thresholds, "trend_horizon_days")
    low = float(thresholds.get("low_influence", 0.05))

    def rate_of(name):
        out = {}
        for label, days, min_span in WINDOWS:
            out[label] = window_change(series_by_faction.get(name, []), now, days, min_span)
        chosen = out["7d"] or out["24h"]
        return out, (chosen["per_day"] if chosen else None)

    result = {}
    for name in tracked:
        if name not in current:
            continue
        windows, rate = rate_of(name)
        cur = float(current[name])
        chosen = windows["7d"] or windows["24h"]

        days_to_low = None
        if cur <= low:
            days_to_low = 0.0
        elif rate is not None and rate < 0:
            days_to_low = _days_or_none((cur - low) / -rate, horizon)

        vs = None
        rival = neighbors.get(name)
        if rival and rival in current:
            rival_rate = rate_of(rival)[1]
            gap = cur - float(current[rival])
            if rate is not None and rival_rate is not None:
                relative = rate - rival_rate
                days = None
                kind = None
                if gap > 0 and relative < 0:
                    kind, days = "lead_loss", _days_or_none(gap / -relative, horizon)
                elif gap < 0 and relative > 0:
                    kind, days = "overtake", _days_or_none(-gap / relative, horizon)
                vs = {
                    "against": rival,
                    "gap": gap,
                    "relative_per_day": relative,
                    "kind": kind if days is not None else None,
                    "days_to_cross": days,
                }

        result[name] = {
            "current": cur,
            "change_24h": windows["24h"]["change"] if windows["24h"] else None,
            "change_7d": windows["7d"]["change"] if windows["7d"] else None,
            "per_day": rate,
            "span_days": chosen["span_days"] if chosen else None,
            "direction": _direction(rate, flat),
            "days_to_low": days_to_low,
            "vs": vs,
        }
    return result


def largest_swing(series_by_faction, present, tracked, now) -> dict | None:
    best = None
    for name in tracked:
        if name not in present:
            continue
        series = series_by_faction.get(name, [])
        for label, days, min_span in reversed(WINDOWS):  # 7d first, then 24h
            w = window_change(series, now, days, min_span)
            if w is not None:
                if best is None or abs(w["change"]) > abs(best["change"]):
                    best = {"faction": name, "change": w["change"], "window": label}
                break
    return best


def faction_series(rows: list[dict]) -> dict[str, Series]:
    series: dict[str, Series] = {}
    for r in rows:
        series.setdefault(r["faction_name"], []).append((r["first_seen"], float(r["influence"])))
    return series


def swing_from_rows(rows: list[dict], tracked, now) -> dict | None:
    present = {r["faction_name"] for r in rows if r.get("superseded_at") is None}
    return largest_swing(faction_series(rows), present, tracked, now)


def order_by_swing(systems, series_by_system, tracked, now, biggest_first=True) -> list[dict]:
    """Systems with no measurable swing always come last; ties break on name."""
    magnitude = {}
    for s in systems:
        swing = swing_from_rows(series_by_system.get(s["system_address"], []), tracked, now)
        magnitude[s["system_address"]] = abs(swing["change"]) if swing else None
    have = [s for s in systems if magnitude[s["system_address"]] is not None]
    none = [s for s in systems if magnitude[s["system_address"]] is None]
    if biggest_first:
        have.sort(key=lambda s: (-magnitude[s["system_address"]], s["name"]))
    else:
        have.sort(key=lambda s: (magnitude[s["system_address"]], s["name"]))
    return have + sorted(none, key=lambda s: s["name"])


def trend_flags(trends: dict, thresholds: dict) -> list[str]:
    steep = _setting(thresholds, "trend_steep_per_day")
    warn = _setting(thresholds, "trend_warn_days")
    low = float(thresholds.get("low_influence", 0.05))
    flags = []
    for name, t in trends.items():
        if t["per_day"] is not None and t["per_day"] <= -steep:
            flags.append(f"{name}_falling_fast")
        if t["days_to_low"] is not None and 0 < t["days_to_low"] <= warn and t["current"] > low:
            flags.append(f"{name}_low_soon")
        vs = t["vs"]
        if vs and vs["kind"] == "lead_loss" and vs["days_to_cross"] is not None and vs["days_to_cross"] <= warn:
            flags.append(f"{name}_losing_lead")
    return flags


def conflict_frequency(pair_stats: list[dict], now: dt.datetime) -> list[dict]:
    out = []
    for p in pair_stats:
        total = p["war_count"] + p["election_count"]
        days = (now - p["first_observed_together"]).days
        if days < 14 or total == 0:
            out.append({
                "faction_a": p["faction_a"],
                "faction_b": p["faction_b"],
                "days_per_conflict": None,
                "label": f"no conflicts in {days} days" if total == 0 else "insufficient history",
            })
        else:
            out.append({
                "faction_a": p["faction_a"],
                "faction_b": p["faction_b"],
                "days_per_conflict": days / total,
                "war_count": p["war_count"],
                "election_count": p["election_count"],
            })
    return out


# ---------------------------------------------------------------------------
# coverage
# ---------------------------------------------------------------------------
# key, label, upper age bound in hours (exclusive; None = unbounded)
BUCKETS = [
    ("lt_1h", "Under 1 hour", 1),
    ("1h_6h", "1 – 6 hours", 6),
    ("6h_24h", "6 – 24 hours", 24),
    ("1d_7d", "1 – 7 days", 24 * 7),
    ("gt_7d", "Over 7 days", None),
    ("no_snapshot", "No data (blind)", None),
]
BUCKET_KEYS = [b[0] for b in BUCKETS]


def _iso(value):
    return value.isoformat() if value else None


def observed_at(row):
    if row.get("last_confirmed") is None:
        return None
    candidates = [row["last_confirmed"]]
    if row.get("last_seen") is not None:
        candidates.append(row["last_seen"])
    return max(candidates)


def age_hours(row, now):
    seen = observed_at(row)
    return None if seen is None else max((now - seen).total_seconds() / 3600.0, 0.0)


def bucket_of(row, now) -> str:
    age = age_hours(row, now)
    if age is None:
        return "no_snapshot"
    for key, _label, upper in BUCKETS:
        if upper is not None and age < upper:
            return key
    return "gt_7d"


def summarise_coverage(rows, now) -> dict:
    counts = {k: 0 for k in BUCKET_KEYS}
    by_source = {"eddn": 0, "spansh": 0, "none": 0}
    by_status: dict[str, int] = {}
    for r in rows:
        counts[bucket_of(r, now)] += 1
        src = r.get("source") or "none"
        by_source[src] = by_source.get(src, 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    total = len(rows)

    def pct(n):
        return round(100.0 * n / total, 1) if total else 0.0

    fresh = counts["lt_1h"] + counts["1h_6h"] + counts["6h_24h"]
    return {
        "total": total,
        "buckets": [
            {"key": k, "label": label, "count": counts[k], "pct": pct(counts[k])}
            for k, label, _u in BUCKETS
        ],
        "with_snapshot": total - counts["no_snapshot"],
        "blind": counts["no_snapshot"],
        "fresh_24h": fresh,
        "fresh_24h_pct": pct(fresh),
        "fresh_7d_pct": pct(total - counts["gt_7d"] - counts["no_snapshot"]),
        "by_source": by_source,
        "eddn_confirmed_pct": pct(by_source["eddn"]),
        "by_status": by_status,
    }


def _coverage_row(r, now) -> dict:
    return {
        "system_address": str(r["system_address"]),
        "name": r["name"],
        "status": r["status"],
        "canonn_present": bool(r["canonn_present"]),
        "cdsr_present": bool(r["cdsr_present"]),
        "source": r.get("source"),
        "last_observed": _iso(observed_at(r)),
        "age_hours": age_hours(r, now),
        "bucket": bucket_of(r, now),
    }


def list_bucket(rows, bucket, now) -> list[dict]:
    picked = [r for r in rows if bucket_of(r, now) == bucket]
    picked.sort(key=lambda r: (observed_at(r) or r.get("last_seen") or dt.datetime.min, r["name"]))
    return [_coverage_row(r, now) for r in picked]


def stalest(rows, now, limit) -> list[dict]:
    candidates = [r for r in rows if observed_at(r) is not None and r["status"] != "retreated"]
    candidates.sort(key=lambda r: (observed_at(r), r["name"]))
    return [_coverage_row(r, now) for r in candidates[:limit]]


def _counter_time(counters, key):
    raw = counters.get(key)
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def _int(counters, key) -> int:
    try:
        return int(counters.get(key, 0))
    except (TypeError, ValueError):
        return 0


def pipeline(counters: dict, extras: dict, now: dt.datetime, opts: dict) -> dict:
    heartbeat = _counter_time(counters, "listener_last_message")
    if heartbeat is None:
        listener = {"status": "unknown", "last_message": None, "age_minutes": None,
                    "note": "No heartbeat recorded yet (tracker not running, or not yet restarted on this version)."}
    else:
        minutes = (now - heartbeat).total_seconds() / 60.0
        status = ("stale" if minutes >= opts["listener_stale_minutes"]
                  else "warn" if minutes >= opts["listener_warn_minutes"] else "ok")
        listener = {"status": status, "last_message": _iso(heartbeat),
                    "age_minutes": round(minutes, 1), "note": None}

    last_sync = max(
        [t for t in (_counter_time(counters, "last_spansh_reconcile"),
                     _counter_time(counters, "last_spansh_seed")) if t],
        default=None,
    )
    if last_sync is None:
        spansh = {"status": "unknown", "last_sync": None, "age_days": None}
    else:
        days = (now - last_sync).total_seconds() / 86400.0
        spansh = {"status": "warn" if days >= opts["spansh_warn_days"] else "ok",
                  "last_sync": _iso(last_sync), "age_days": round(days, 1)}

    received = _int(counters, "messages_received")
    rejected = _int(counters, "messages_rejected")
    return {
        "listener": listener,
        "spansh": spansh,
        "messages": {
            "received": received,
            "rejected": rejected,
            "rejected_pct": round(100.0 * rejected / received, 1) if received else 0.0,
            "confirmed": _int(counters, "messages_confirmed"),
            "promoted": _int(counters, "snapshots_promoted"),
            "stale_rejected": _int(counters, "stale_rejected"),
        },
        "candidates_pending": extras.get("candidates_pending", 0),
        "absence_watch": extras.get("absence_watch", 0),
        "outbox_pending": extras.get("outbox_pending", 0),
        "duplicate_current_snapshots": extras.get("duplicate_current_snapshots", 0),
        "last_publish": counters.get("last_publish"),
        "activity_since": counters.get("activity_since"),
    }


# ---------------------------------------------------------------------------
# activity heat map
# ---------------------------------------------------------------------------
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MIN_CONFIDENT_TOTAL = 50


def empty_grid() -> list[list[int]]:
    return [[0] * 24 for _ in range(7)]


def best_window(profile, width=3, busiest=True) -> dict | None:
    if not any(profile):
        return None
    best = None
    for start in range(24):
        total = sum(profile[(start + i) % 24] for i in range(width))
        if best is None or (total > best[1] if busiest else total < best[1]):
            best = (start, total)
    start, total = best
    return {"start_hour": start, "end_hour": (start + width) % 24, "count": total}


def summarise_activity(grid, top=3) -> dict:
    total = sum(sum(row) for row in grid)
    cells = [
        {"dow": d, "day": DAYS[d], "hour": h, "count": grid[d][h]}
        for d in range(7) for h in range(24)
    ]
    busiest = [c for c in sorted(cells, key=lambda c: (-c["count"], c["dow"], c["hour"]))[:top]
               if c["count"] > 0]
    profile = [sum(grid[d][h] for d in range(7)) for h in range(24)]
    return {
        "total": total,
        "max_cell": max((c["count"] for c in cells), default=0),
        "peak_cells": busiest,
        "busiest_window": best_window(profile, 3, True),
        "quietest_window": best_window(profile, 3, False),
        "hourly": profile,
        "confidence": "ok" if total >= MIN_CONFIDENT_TOTAL else "low",
    }


# ---------------------------------------------------------------------------
# architect sheet
# ---------------------------------------------------------------------------
PLACEHOLDERS = {
    "", "-", "--", "n/a", "na", "none", "nobody", "unknown", "?",
    "don't know", "dont know", "do not know", "no preference", "no preferred faction",
    "nobody the system is not a colony",
}


def norm_system(name) -> str:
    return " ".join((name or "").split()).casefold()


def clean_cell(value) -> str:
    value = (value or "").strip().strip("`").strip()
    return "" if value.casefold() in PLACEHOLDERS else value


def parse_sheet_timestamp(value) -> dt.datetime | None:
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime((value or "").strip(), fmt)
        except ValueError:
            continue
    return None


def latest_by_system(records: list[dict]) -> dict[str, dict]:
    """{normalised system name: {architect, preferred_faction}} from csv
    DictReader records. The most recent row per system wins (timestamp,
    then sheet order, so a later row wins ties); placeholder / blank cells
    mean 'no value'."""
    best: dict[str, tuple] = {}
    for order, record in enumerate(records):
        row = {(k or "").strip().casefold(): v for k, v in record.items()}
        system = " ".join((row.get("system name") or "").split())
        if not system:
            continue
        key = (parse_sheet_timestamp(row.get("timestamp")) or dt.datetime.min, order)
        norm = norm_system(system)
        if norm in best and best[norm][0] > key:
            continue
        best[norm] = (key, {
            "architect": clean_cell(row.get("architect name")),
            "preferred_faction": clean_cell(row.get("preferred faction")),
        })
    return {norm: entry for norm, (_k, entry) in best.items()}


def match_systems(entries: dict, system_names) -> dict:
    out = {}
    for name in system_names:
        entry = entries.get(norm_system(name))
        if entry and (entry["architect"] or entry["preferred_faction"]):
            out[name] = dict(entry)
    return out
