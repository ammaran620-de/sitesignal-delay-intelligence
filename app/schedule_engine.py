"""Deterministic CPM, delay propagation, and recovery-scenario calculations.

This module deliberately makes no LLM calls. It computes schedule facts from
explicit activity dependencies and durations; an LLM may explain these results,
but must not invent or calculate them.
"""
from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from datetime import date, timedelta
from math import isclose
from typing import Any, Iterable


class ScheduleValidationError(ValueError):
    """Raised when schedule or delay-event input is inconsistent."""


def _prepare(activities: Iterable[dict[str, Any]]):
    items: dict[str, dict[str, Any]] = {}
    order_in: list[str] = []
    for raw in activities:
        if not isinstance(raw, dict):
            raise ScheduleValidationError("Each activity must be an object.")
        aid = str(raw.get("id", "")).strip()
        if not aid or aid in items:
            raise ScheduleValidationError(f"Missing or duplicate activity id: {aid!r}")
        try:
            duration = float(raw["duration_days"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ScheduleValidationError(f"Activity {aid} needs numeric duration_days.") from exc
        if duration <= 0:
            raise ScheduleValidationError(f"Activity {aid} duration_days must be greater than zero.")
        preds = raw.get("predecessors", [])
        if not isinstance(preds, list):
            raise ScheduleValidationError(f"Activity {aid} predecessors must be a list.")
        preds = [str(p).strip() for p in preds]
        if aid in preds or len(preds) != len(set(preds)):
            raise ScheduleValidationError(f"Activity {aid} has a self or duplicate predecessor.")
        items[aid] = {**deepcopy(raw), "id": aid, "name": str(raw.get("name") or aid),
                      "duration_days": duration, "predecessors": preds}
        order_in.append(aid)
    if not items:
        raise ScheduleValidationError("Schedule must contain at least one activity.")

    successors = {aid: [] for aid in items}
    indegree = {}
    for aid, item in items.items():
        indegree[aid] = len(item["predecessors"])
        for pred in item["predecessors"]:
            if pred not in items:
                raise ScheduleValidationError(f"Activity {aid} references missing predecessor {pred}.")
            successors[pred].append(aid)
    queue = deque(aid for aid in order_in if indegree[aid] == 0)
    order = []
    while queue:
        aid = queue.popleft()
        order.append(aid)
        for nxt in successors[aid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(items):
        cycle_nodes = [aid for aid in order_in if indegree[aid] > 0]
        raise ScheduleValidationError("Circular dependency detected: " + ", ".join(cycle_nodes))
    return items, order, successors


def _apply_adjustments(activities, adjustments: dict[str, float]):
    result = deepcopy(list(activities))
    ids = {str(x.get("id")) for x in result}
    unknown = sorted(set(adjustments) - ids)
    if unknown:
        raise ScheduleValidationError("Unknown activity ids: " + ", ".join(unknown))
    for item in result:
        aid = str(item["id"])
        if aid in adjustments:
            duration = float(item["duration_days"]) + float(adjustments[aid])
            if duration <= 0:
                raise ScheduleValidationError(f"Adjustment makes activity {aid} duration non-positive.")
            item["duration_days"] = duration
    return result


def calculate_cpm(activities: Iterable[dict[str, Any]], project_start_date: str | None = None) -> dict[str, Any]:
    """Return forward/backward pass, total float and critical path.

    Durations are calendar days and relationships are finish-to-start. The
    prototype does not model working calendars, resources or resource levelling.
    """
    items, order, successors = _prepare(activities)
    start = None
    if project_start_date:
        try:
            start = date.fromisoformat(project_start_date)
        except ValueError as exc:
            raise ScheduleValidationError("project_start_date must be YYYY-MM-DD.") from exc

    es, ef = {}, {}
    for aid in order:
        es[aid] = max((ef[p] for p in items[aid]["predecessors"]), default=0.0)
        ef[aid] = es[aid] + items[aid]["duration_days"]
    project_duration = max(ef.values())

    ls, lf = {}, {}
    for aid in reversed(order):
        lf[aid] = min((ls[n] for n in successors[aid]), default=project_duration)
        ls[aid] = lf[aid] - items[aid]["duration_days"]

    rows, critical = [], []
    for aid in order:
        slack = max(0.0, ls[aid] - es[aid])
        is_critical = isclose(slack, 0.0, abs_tol=1e-8)
        if is_critical:
            critical.append(aid)
        row = {
            "id": aid, "name": items[aid]["name"],
            "duration_days": items[aid]["duration_days"],
            "predecessors": items[aid]["predecessors"], "successors": successors[aid],
            "early_start_day": round(es[aid], 4), "early_finish_day": round(ef[aid], 4),
            "late_start_day": round(ls[aid], 4), "late_finish_day": round(lf[aid], 4),
            "total_float_days": round(slack, 4), "is_critical": is_critical,
        }
        if start:
            row["early_start_date"] = (start + timedelta(days=es[aid])).isoformat()
            row["early_finish_date"] = (start + timedelta(days=ef[aid])).isoformat()
        rows.append(row)

    # Select one deterministic longest path for display; all zero-float nodes
    # are also returned because a project can have multiple critical paths.
    terminals = [aid for aid in order if not successors[aid] and isclose(ef[aid], project_duration, abs_tol=1e-8)]
    current = terminals[0]
    path = [current]
    while items[current]["predecessors"]:
        drivers = [p for p in items[current]["predecessors"] if isclose(ef[p], es[current], abs_tol=1e-8)]
        if not drivers:
            break
        current = drivers[0]
        path.append(current)
    path.reverse()

    result = {"project_duration_days": round(project_duration, 4), "critical_path": path,
              "critical_activities": critical, "activities": rows,
              "calendar_assumptions": [
                  "Durations are calendar days, not working days.",
                  "Weekends, holidays, resource constraints and resource levelling are not modelled.",
                  "Only finish-to-start dependencies are supported."]}
    if start:
        result["project_start_date"] = start.isoformat()
        result["project_finish_date"] = (start + timedelta(days=project_duration)).isoformat()
    return result


def _descendants(aid: str, successors: dict[str, list[str]]) -> list[str]:
    seen, queue = set(), deque(successors[aid])
    while queue:
        nxt = queue.popleft()
        if nxt not in seen:
            seen.add(nxt)
            queue.extend(successors[nxt])
    return sorted(seen)


def analyze_delay_events(activities, events, project_start_date: str | None = None) -> dict[str, Any]:
    """Apply evidence-backed delay events as duration increases and trace impact.

    Each event requires id, activity_id, delay_days, summary and evidence_source.
    Event-to-duration mapping is a declared scenario assumption, not ML prediction.
    """
    base = deepcopy(list(activities))
    items, _, successors = _prepare(base)
    events = list(events)
    adjustments: dict[str, float] = defaultdict(float)
    event_ids = set()
    for event in events:
        eid, aid = str(event.get("id", "")).strip(), str(event.get("activity_id", "")).strip()
        if not eid or eid in event_ids:
            raise ScheduleValidationError("Every delay event needs a unique, non-empty id.")
        event_ids.add(eid)
        if aid not in items:
            raise ScheduleValidationError(f"Delay event {eid} references unknown activity {aid}.")
        try:
            days = float(event["delay_days"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ScheduleValidationError(f"Delay event {eid} needs numeric delay_days.") from exc
        if days <= 0:
            raise ScheduleValidationError(f"Delay event {eid} delay_days must be greater than zero.")
        if not str(event.get("evidence_source", "")).strip():
            raise ScheduleValidationError(f"Delay event {eid} needs evidence_source.")
        adjustments[aid] += days

    baseline = calculate_cpm(base, project_start_date)
    adjusted = _apply_adjustments(base, adjustments)
    impacted = calculate_cpm(adjusted, project_start_date)
    base_rows = {r["id"]: r for r in baseline["activities"]}
    impact_rows = {r["id"]: r for r in impacted["activities"]}
    impacts = []
    for event in events:
        aid, days = str(event["activity_id"]), float(event["delay_days"])
        single = calculate_cpm(_apply_adjustments(base, {aid: days}), project_start_date)
        shifted = []
        for child in _descendants(aid, successors):
            delta = impact_rows[child]["early_start_day"] - base_rows[child]["early_start_day"]
            if delta > 1e-8:
                shifted.append({"activity_id": child, "activity_name": items[child]["name"],
                                "start_shift_days": round(delta, 4)})
        impacts.append({
            "event_id": str(event["id"]), "activity_id": aid,
            "activity_name": items[aid]["name"], "delay_days": days,
            "summary": str(event.get("summary", "")),
            "evidence_source": str(event["evidence_source"]),
            "baseline_activity_was_critical": base_rows[aid]["is_critical"],
            "project_completion_delta_if_applied_alone_days": round(
                single["project_duration_days"] - baseline["project_duration_days"], 4),
            "downstream_activities_shifted_under_all_events": shifted,
        })
    return {
        "baseline": baseline, "impacted_schedule": impacted,
        "total_project_completion_delay_days": round(
            impacted["project_duration_days"] - baseline["project_duration_days"], 4),
        "events": impacts,
        "attribution_note": (
            "Standalone event impacts are calculated independently and may not be additive "
            "when events interact across parallel paths."
        ),
    }


def simulate_recovery(activities, events, duration_reductions: dict[str, float],
                      project_start_date: str | None = None) -> dict[str, Any]:
    """Compare baseline, delayed and proposed reduced-duration schedule.

    This is schedule-only. It does not validate cost, crew availability, overtime,
    procurement feasibility or safety constraints.
    """
    events = list(events)
    impact = analyze_delay_events(activities, events, project_start_date)
    event_adjustments: dict[str, float] = defaultdict(float)
    for event in events:
        event_adjustments[str(event["activity_id"])] += float(event["delay_days"])
    delayed_activities = _apply_adjustments(list(activities), event_adjustments)
    reductions = {str(k): float(v) for k, v in duration_reductions.items()}
    if any(v <= 0 for v in reductions.values()):
        raise ScheduleValidationError("Recovery reductions must be greater than zero.")
    recovered_activities = _apply_adjustments(delayed_activities, {k: -v for k, v in reductions.items()})
    recovered = calculate_cpm(recovered_activities, project_start_date)
    baseline_days = impact["baseline"]["project_duration_days"]
    delayed_days = impact["impacted_schedule"]["project_duration_days"]
    recovered_days = recovered["project_duration_days"]
    return {
        "baseline_duration_days": baseline_days,
        "delayed_duration_days": delayed_days,
        "recovered_duration_days": recovered_days,
        "delay_vs_baseline_days": round(delayed_days - baseline_days, 4),
        "days_recovered_vs_delayed_schedule": round(delayed_days - recovered_days, 4),
        "remaining_delay_vs_baseline_days": round(recovered_days - baseline_days, 4),
        "duration_reductions_assumed": reductions,
        "recovered_schedule": recovered,
        "feasibility_warning": (
            "Schedule-only scenario; this does not verify crew availability, cost, overtime, procurement, "
            "site safety or contractual feasibility. Validate these factors before adopting a recovery option."
        ),
    }
