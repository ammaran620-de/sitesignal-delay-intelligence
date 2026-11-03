from __future__ import annotations

from typing import Any

from app.construction_rag import search_construction_evidence
from app.construction_service import get_project_overview, investigate_delay, simulate_named_recovery
from app.db import write_audit

SITE_SIGNAL_TOOL_DECLARATIONS = [
    {
        "type": "function", "name": "get_project_schedule",
        "description": "Calculate the baseline and event-adjusted construction schedule using the deterministic Critical Path Method engine. Use this for project duration, forecast completion, critical path, total float and delay totals.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function", "name": "investigate_delay_event",
        "description": "Investigate one specific delay event. Returns its synthetic incident evidence, baseline context, calculated downstream activity shifts and completion impact. Never infer causes not present in the evidence.",
        "parameters": {"type": "object", "properties": {"event_id": {"type": "string", "description": "Event identifier such as EV-001 or EV-002."}}, "required": ["event_id"]},
    },
    {
        "type": "function", "name": "simulate_recovery_scenario",
        "description": "Run a predefined schedule-only recovery scenario and compare baseline, delayed and recovered completion. It does not change the approved schedule and does not verify cost, resources, safety or contractual feasibility.",
        "parameters": {"type": "object", "properties": {"scenario_id": {"type": "string", "description": "Scenario identifier, for example REC-001."}}, "required": ["scenario_id"]},
    },
    {
        "type": "function", "name": "search_project_evidence",
        "description": "Use semantic retrieval over the synthetic construction incident reports and demonstration procedure. Cite filenames and distinguish recorded facts from calculated results and assumptions.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Question to retrieve relevant construction evidence for."}}, "required": ["query"]},
    },
]


def dispatch_site_signal_tool(name: str, arguments: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    if user.get("role") not in {"manager", "technician"}:
        result = {"error": "Access denied: construction project information is restricted to manager and project delivery roles."}
        write_audit(user["id"], name, "construction_project", None, "denied", result["error"])
        return result
    if name == "simulate_recovery_scenario" and user.get("role") != "manager":
        result = {"error": "Only a project manager can run recovery scenario simulations."}
        write_audit(user["id"], name, "recovery_scenario", arguments.get("scenario_id"), "denied", result["error"])
        return result
    try:
        if name == "get_project_schedule":
            result = get_project_overview()
        elif name == "investigate_delay_event":
            result = investigate_delay(str(arguments.get("event_id", "")))
        elif name == "simulate_recovery_scenario":
            result = simulate_named_recovery(str(arguments.get("scenario_id", "")))
        elif name == "search_project_evidence":
            result = search_construction_evidence(str(arguments.get("query", "")))
        else:
            return {"error": f"Unknown SiteSignal tool: {name}"}
        write_audit(user["id"], name, "construction_project", str(arguments.get("event_id") or arguments.get("scenario_id") or ""), "allowed")
        return result
    except (ValueError, LookupError, RuntimeError, OSError) as exc:
        write_audit(user["id"], name, "construction_project", None, "failed", str(exc))
        return {"error": str(exc)}
