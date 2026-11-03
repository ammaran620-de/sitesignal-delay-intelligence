from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import connection, write_audit
from app.rag import search_policies


TOOL_DECLARATIONS = [
    {
        "type": "function",
        "name": "find_overdue_vehicles",
        "description": "Find vehicles in reconditioning for at least the requested number of days. Managers can see their branch; technicians can only see jobs assigned to them. Sales users are not permitted to use this tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "minimum_days": {"type": "integer", "description": "Minimum whole number of days in reconditioning; use 5 for “at least five days” and 6 for “more than five days.”"}
            },
            "required": ["minimum_days"],
        },
    },
    {
        "type": "function",
        "name": "get_vehicle_details",
        "description": "Retrieve a vehicle's details and authorized reconditioning information using its stock number.",
        "parameters": {
            "type": "object",
            "properties": {"stock_number": {"type": "string", "description": "Inventory stock number, for example HB-2401."}},
            "required": ["stock_number"],
        },
    },
    {
        "type": "function",
        "name": "search_operational_policy",
        "description": "Search the dealership's indexed policy documents using semantic retrieval. Use this for questions about procedures, escalation, approval rules or reconditioning standards. Cite the returned source filename in your answer.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A concise natural-language policy question."}},
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "propose_follow_up_tasks",
        "description": "Prepare follow-up tasks for a manager to review. This tool only creates a pending approval request; it does NOT create tasks. Actual task creation requires a manager to approve the pending request through the application.",
        "parameters": {
            "type": "object",
            "properties": {
                "stock_numbers": {"type": "array", "items": {"type": "string"}, "description": "Vehicle stock numbers for which follow-up tasks should be proposed."},
                "task_note": {"type": "string", "description": "Concise action to be completed by the assigned employee."},
            },
            "required": ["stock_numbers", "task_note"],
        },
    },
]


def _days_since(value: str) -> int:
    started = datetime.fromisoformat(value)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - started.astimezone(timezone.utc)).days)


def find_overdue_vehicles(minimum_days: int, user: dict[str, Any]) -> dict[str, Any]:
    if user["role"] not in {"manager", "technician"}:
        raise PermissionError("Only managers and technicians can view reconditioning delay records.")
    minimum_days = max(1, min(int(minimum_days), 365))
    sql = """
        SELECT v.stock_number, v.make, v.model, v.year, v.status,
               j.status AS job_status, j.started_at, j.blocker, j.notes, j.assigned_to
        FROM vehicles v
        JOIN reconditioning_jobs j ON j.vehicle_id = v.id
        WHERE v.branch_id = ? AND j.status IN ('waiting_parts', 'in_progress', 'blocked')
    """
    params: list[Any] = [user["branch_id"]]
    if user["role"] == "technician":
        sql += " AND j.assigned_to = ?"
        params.append(user["id"])
    sql += " ORDER BY j.started_at ASC"
    with connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    matches = []
    for row in rows:
        days = _days_since(row["started_at"])
        if days >= minimum_days:
            matches.append(
                {
                    "stock_number": row["stock_number"],
                    "vehicle": f"{row['year']} {row['make']} {row['model']}",
                    "days_in_reconditioning": days,
                    "job_status": row["job_status"],
                    "documented_blocker": row["blocker"] or "No blocker recorded",
                    "notes": row["notes"] or "No notes recorded",
                    "assigned_to": row["assigned_to"],
                }
            )
    write_audit(user["id"], "find_overdue_vehicles", "reconditioning_jobs", None, "allowed", f"minimum_days={minimum_days}; results={len(matches)}")
    return {"minimum_days": minimum_days, "count": len(matches), "vehicles": matches}


def get_vehicle_details(stock_number: str, user: dict[str, Any]) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            """SELECT v.*, j.status AS job_status, j.started_at, j.blocker, j.notes, j.assigned_to
               FROM vehicles v LEFT JOIN reconditioning_jobs j ON j.vehicle_id = v.id
               WHERE v.stock_number = ? AND v.branch_id = ?""",
            (stock_number.strip().upper(), user["branch_id"]),
        ).fetchone()
    if not row:
        raise LookupError("Vehicle not found in the signed-in user's branch.")
    if user["role"] == "technician" and row["assigned_to"] not in (None, user["id"]):
        raise PermissionError("Technicians can only inspect jobs assigned to them.")
    result = {
        "stock_number": row["stock_number"],
        "vin": row["vin"],
        "vehicle": f"{row['year']} {row['make']} {row['model']}",
        "vehicle_status": row["status"],
    }
    if user["role"] in {"manager", "technician"} and row["job_status"]:
        result.update(
            {
                "job_status": row["job_status"],
                "days_in_reconditioning": _days_since(row["started_at"]),
                "documented_blocker": row["blocker"] or "No blocker recorded",
                "notes": row["notes"] or "No notes recorded",
            }
        )
    write_audit(user["id"], "get_vehicle_details", "vehicle", stock_number, "allowed")
    return result


def search_operational_policy(query: str, user: dict[str, Any]) -> dict[str, Any]:
    results = search_policies(query, top_k=3)
    write_audit(user["id"], "search_operational_policy", "policy_knowledge_base", None, "allowed", f"query={query[:160]}")
    return {"query": query, "matches": results}


def propose_follow_up_tasks(stock_numbers: list[str], task_note: str, user: dict[str, Any]) -> dict[str, Any]:
    if user["role"] != "manager":
        raise PermissionError("Only a manager can propose follow-up tasks.")
    normalized = list(dict.fromkeys(s.strip().upper() for s in stock_numbers if s.strip()))[:10]
    if not normalized:
        raise ValueError("At least one valid stock number is required.")
    with connection() as conn:
        placeholders = ",".join("?" for _ in normalized)
        rows = conn.execute(
            f"""SELECT v.stock_number, j.assigned_to
                FROM vehicles v JOIN reconditioning_jobs j ON j.vehicle_id = v.id
                WHERE v.branch_id = ? AND v.stock_number IN ({placeholders})""",
            [user["branch_id"], *normalized],
        ).fetchall()
    found = {row["stock_number"]: row["assigned_to"] for row in rows}
    missing = [stock for stock in normalized if stock not in found]
    if missing:
        raise LookupError(f"These stock numbers are not available in your branch: {', '.join(missing)}")

    payload = {"stock_numbers": normalized, "task_note": task_note.strip()[:500], "assignees": found}
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO pending_actions(action_type, payload_json, requested_by, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            ("create_follow_up_tasks", json.dumps(payload), user["id"], created_at),
        )
        action_id = cursor.lastrowid
    write_audit(user["id"], "propose_follow_up_tasks", "pending_action", str(action_id), "awaiting_approval", json.dumps(payload))
    return {
        "pending_action_id": action_id,
        "status": "awaiting_manager_approval",
        "message": "A task proposal has been prepared. No task has been created yet.",
        "stock_numbers": normalized,
    }


def dispatch_tool(name: str, arguments: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    handlers = {
        "find_overdue_vehicles": lambda: find_overdue_vehicles(arguments.get("minimum_days", 5), user),
        "get_vehicle_details": lambda: get_vehicle_details(arguments.get("stock_number", ""), user),
        "search_operational_policy": lambda: search_operational_policy(arguments.get("query", ""), user),
        "propose_follow_up_tasks": lambda: propose_follow_up_tasks(
            arguments.get("stock_numbers", []), arguments.get("task_note", "Follow up on reconditioning delay"), user
        ),
    }
    if name not in handlers:
        return {"error": f"Tool '{name}' is not available."}
    try:
        return handlers[name]()
    except (PermissionError, LookupError, ValueError, RuntimeError) as exc:
        write_audit(user["id"], name, "tool", None, "denied_or_failed", str(exc))
        return {"error": str(exc)}


def approve_pending_action(action_id: int, user: dict[str, Any]) -> dict[str, Any]:
    if user["role"] != "manager":
        raise PermissionError("Only managers can approve business actions.")
    now = datetime.now(timezone.utc)
    with connection() as conn:
        action = conn.execute(
            "SELECT * FROM pending_actions WHERE id = ? AND requested_by = ? AND status = 'pending'",
            (action_id, user["id"]),
        ).fetchone()
        if not action:
            raise LookupError("Pending approval not found, already resolved, or not requested by this manager.")
        payload = json.loads(action["payload_json"])
        due_date = (now + timedelta(days=2)).date().isoformat()
        created = []
        for stock_number in payload["stock_numbers"]:
            assigned_to = payload["assignees"][stock_number]
            cursor = conn.execute(
                "INSERT INTO tasks(title, description, stock_number, assigned_to, created_by, due_date, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)",
                (
                    f"Reconditioning follow-up: {stock_number}",
                    payload["task_note"],
                    stock_number,
                    assigned_to,
                    user["id"],
                    due_date,
                    now.isoformat(timespec="seconds"),
                ),
            )
            created.append({"task_id": cursor.lastrowid, "stock_number": stock_number, "assigned_to": assigned_to})
        conn.execute(
            "UPDATE pending_actions SET status = 'approved', resolved_at = ? WHERE id = ?",
            (now.isoformat(timespec="seconds"), action_id),
        )
        conn.execute(
            "INSERT INTO audit_logs(actor_id, action, resource_type, resource_id, outcome, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"], "approve_pending_action", "pending_action", str(action_id), "approved", json.dumps(created), now.isoformat(timespec="seconds")),
        )
    return {"status": "approved", "created_tasks": created}


def reject_pending_action(action_id: int, user: dict[str, Any]) -> dict[str, Any]:
    if user["role"] != "manager":
        raise PermissionError("Only managers can reject business actions.")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connection() as conn:
        cursor = conn.execute(
            "UPDATE pending_actions SET status = 'rejected', resolved_at = ? WHERE id = ? AND requested_by = ? AND status = 'pending'",
            (now, action_id, user["id"]),
        )
        if cursor.rowcount == 0:
            raise LookupError("Pending approval not found, already resolved, or not requested by this manager.")
        conn.execute(
            "INSERT INTO audit_logs(actor_id, action, resource_type, resource_id, outcome, details, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"], "reject_pending_action", "pending_action", str(action_id), "rejected", "Manager rejected the proposed tasks.", now),
        )
    return {"status": "rejected", "pending_action_id": action_id}


def get_pending_actions(user: dict[str, Any]) -> list[dict[str, Any]]:
    if user["role"] != "manager":
        raise PermissionError("Only managers can view pending approvals.")
    with connection() as conn:
        rows = conn.execute(
            "SELECT id, action_type, payload_json, status, created_at FROM pending_actions WHERE requested_by = ? AND status = 'pending' ORDER BY id DESC",
            (user["id"],),
        ).fetchall()
    return [
        {"id": row["id"], "action_type": row["action_type"], "payload": json.loads(row["payload_json"]), "status": row["status"], "created_at": row["created_at"]}
        for row in rows
    ]


def get_overview(user: dict[str, Any]) -> dict[str, int]:
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM vehicles WHERE branch_id = ?", (user["branch_id"],)).fetchone()[0]
        active_jobs = []
        if user["role"] == "manager":
            active_jobs = conn.execute(
                "SELECT j.started_at, j.assigned_to FROM reconditioning_jobs j JOIN vehicles v ON v.id = j.vehicle_id WHERE v.branch_id = ? AND j.status IN ('waiting_parts', 'in_progress', 'blocked')",
                (user["branch_id"],),
            ).fetchall()
        elif user["role"] == "technician":
            active_jobs = conn.execute(
                "SELECT j.started_at, j.assigned_to FROM reconditioning_jobs j JOIN vehicles v ON v.id = j.vehicle_id WHERE v.branch_id = ? AND j.assigned_to = ? AND j.status IN ('waiting_parts', 'in_progress', 'blocked')",
                (user["branch_id"], user["id"]),
            ).fetchall()
        task_sql = "SELECT COUNT(*) FROM tasks WHERE status = 'open' AND assigned_to = ?"
        task_params: tuple[Any, ...] = (user["id"],)
        if user["role"] == "manager":
            task_sql = "SELECT COUNT(*) FROM tasks t JOIN users u ON u.id = t.assigned_to WHERE t.status = 'open' AND u.branch_id = ?"
            task_params = (user["branch_id"],)
        open_tasks = conn.execute(task_sql, task_params).fetchone()[0]
    overdue = sum(1 for row in active_jobs if _days_since(row["started_at"]) >= 5)
    return {"vehicles": total, "active_reconditioning": len(active_jobs), "overdue_5_days": overdue, "open_tasks": open_tasks}


def get_tasks(user: dict[str, Any]) -> list[dict[str, Any]]:
    with connection() as conn:
        if user["role"] == "manager":
            rows = conn.execute(
                "SELECT t.*, u.full_name AS assignee_name FROM tasks t JOIN users u ON u.id = t.assigned_to WHERE u.branch_id = ? ORDER BY t.id DESC LIMIT 30",
                (user["branch_id"],),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT t.*, u.full_name AS assignee_name FROM tasks t JOIN users u ON u.id = t.assigned_to WHERE u.branch_id = ? AND t.assigned_to = ? ORDER BY t.id DESC LIMIT 30",
                (user["branch_id"], user["id"]),
            ).fetchall()
    return [dict(row) for row in rows]


def get_audit_logs(user: dict[str, Any], limit: int = 40) -> list[dict[str, Any]]:
    if user["role"] != "manager":
        raise PermissionError("Only managers can view the audit trail.")
    with connection() as conn:
        rows = conn.execute(
            """SELECT a.id, a.actor_id, u.full_name AS actor_name, a.action, a.resource_type,
                      a.resource_id, a.outcome, a.details, a.created_at
               FROM audit_logs a JOIN users u ON u.id = a.actor_id
               WHERE u.branch_id = ? ORDER BY a.id DESC LIMIT ?""",
            (user["branch_id"], min(max(limit, 1), 100)),
        ).fetchall()
    return [dict(row) for row in rows]
