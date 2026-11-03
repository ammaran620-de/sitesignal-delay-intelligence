from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR
from app.schedule_engine import analyze_delay_events, calculate_cpm, simulate_recovery

PROJECT_PATH = ROOT_DIR / "data" / "construction_project.json"
EVIDENCE_DIR = ROOT_DIR / "data" / "construction_docs"


class ConstructionDataError(ValueError):
    """Raised when the construction demo dataset or its evidence is invalid."""


def load_project(path: Path | None = None) -> dict[str, Any]:
    source = path or PROJECT_PATH
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConstructionDataError(f"Construction project file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ConstructionDataError(f"Construction project JSON is invalid: {exc}") from exc

    required = {"project", "activities", "delay_events", "recovery_scenarios"}
    missing = sorted(required - set(data))
    if missing:
        raise ConstructionDataError(f"Project file is missing sections: {', '.join(missing)}")
    if not isinstance(data["activities"], list) or not data["activities"]:
        raise ConstructionDataError("Project activities must be a non-empty list.")
    if not isinstance(data["delay_events"], list):
        raise ConstructionDataError("delay_events must be a list.")
    return data


def _safe_evidence_path(filename: str) -> Path:
    name = Path(filename).name
    if name != filename or not name.endswith(".md"):
        raise ConstructionDataError("Evidence references must be Markdown filenames without paths.")
    path = (EVIDENCE_DIR / name).resolve()
    if path.parent != EVIDENCE_DIR.resolve():
        raise ConstructionDataError("Evidence path is outside the construction evidence directory.")
    return path


def validate_evidence_links(project: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = project or load_project()
    registry: list[dict[str, Any]] = []
    for event in data["delay_events"]:
        filename = str(event.get("evidence_source", ""))
        path = _safe_evidence_path(filename)
        exists = path.is_file()
        registry.append({
            "event_id": event.get("id"),
            "source": filename,
            "available": exists,
            "title": path.stem.replace("_", " ").title(),
            "excerpt": path.read_text(encoding="utf-8")[:500] if exists else None,
        })
    return registry


def get_project_overview() -> dict[str, Any]:
    data = load_project()
    meta = data["project"]
    start = meta.get("project_start_date")
    baseline = calculate_cpm(data["activities"], start)
    impact = analyze_delay_events(data["activities"], data["delay_events"], start)
    recoveries = []
    for scenario in data["recovery_scenarios"]:
        simulation = simulate_recovery(
            data["activities"], data["delay_events"],
            scenario.get("duration_reductions", {}), start
        )
        recoveries.append({
            "id": scenario["id"], "name": scenario["name"],
            "assumption": scenario.get("assumption", ""),
            "simulation": simulation,
        })
    evidence = validate_evidence_links(data)
    return {
        "project": meta,
        "baseline": baseline,
        "impact": impact,
        "recovery_scenarios": recoveries,
        "evidence_registry": evidence,
        "metrics": {
            "baseline_duration_days": baseline["project_duration_days"],
            "baseline_finish_date": baseline.get("project_finish_date"),
            "forecast_duration_days": impact["impacted_schedule"]["project_duration_days"],
            "forecast_finish_date": impact["impacted_schedule"].get("project_finish_date"),
            "completion_delay_days": impact["total_project_completion_delay_days"],
            "delay_events": len(data["delay_events"]),
            "evidence_files_available": sum(1 for item in evidence if item["available"]),
        },
        "limitations": baseline["calendar_assumptions"],
        "data_notice": "All project records and evidence are synthetic demonstration data.",
    }


def investigate_delay(event_id: str) -> dict[str, Any]:
    data = load_project()
    matches = [event for event in data["delay_events"] if event.get("id") == event_id]
    if not matches:
        raise LookupError(f"Unknown delay event: {event_id}")
    overview = get_project_overview()
    impact = next(item for item in overview["impact"]["events"] if item["event_id"] == event_id)
    event = matches[0]
    evidence_path = _safe_evidence_path(event["evidence_source"])
    if not evidence_path.is_file():
        raise ConstructionDataError(f"Evidence file is missing: {event['evidence_source']}")
    return {
        "event": event,
        "schedule_impact": impact,
        "baseline": {
            "duration_days": overview["metrics"]["baseline_duration_days"],
            "finish_date": overview["metrics"]["baseline_finish_date"],
        },
        "combined_forecast": {
            "duration_days": overview["metrics"]["forecast_duration_days"],
            "finish_date": overview["metrics"]["forecast_finish_date"],
            "delay_days": overview["metrics"]["completion_delay_days"],
        },
        "evidence": {
            "source": evidence_path.name,
            "content": evidence_path.read_text(encoding="utf-8"),
            "synthetic": True,
        },
        "interpretation_rule": "Separate recorded facts from CPM calculations and assumptions. Do not infer root cause or contractual responsibility.",
    }


def simulate_named_recovery(scenario_id: str) -> dict[str, Any]:
    data = load_project()
    scenario = next((x for x in data["recovery_scenarios"] if x.get("id") == scenario_id), None)
    if not scenario:
        raise LookupError(f"Unknown recovery scenario: {scenario_id}")
    start = data["project"].get("project_start_date")
    result = simulate_recovery(
        data["activities"], data["delay_events"],
        scenario.get("duration_reductions", {}), start
    )
    return {
        "scenario": scenario,
        "simulation": result,
        "approval_required": True,
        "notice": "This is a schedule-only simulation, not an approved schedule change. Verify resources, cost, procurement, safety and contractual constraints before adoption.",
    }


def list_evidence() -> list[dict[str, Any]]:
    data = load_project()
    registry = validate_evidence_links(data)
    items = []
    for entry in registry:
        path = _safe_evidence_path(entry["source"])
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            items.append({
                "event_id": entry["event_id"],
                "source": path.name,
                "title": content.splitlines()[0].lstrip("# ").strip(),
                "excerpt": " ".join(content.split())[:420],
                "synthetic": True,
            })
    policy = EVIDENCE_DIR / "construction_delay_policy.md"
    if policy.is_file():
        content = policy.read_text(encoding="utf-8")
        items.append({
            "event_id": "POLICY",
            "source": policy.name,
            "title": content.splitlines()[0].lstrip("# ").strip(),
            "excerpt": " ".join(content.split())[:420],
            "synthetic": True,
        })
    return items
