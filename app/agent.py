from __future__ import annotations

import json
from typing import Any

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.construction_tools import SITE_SIGNAL_TOOL_DECLARATIONS, dispatch_site_signal_tool

SYSTEM_INSTRUCTIONS = """
You are SiteSignal, an AI-assisted construction delay investigation and schedule intelligence prototype.

Your job is to investigate schedule events using the provided deterministic tools and evidence retrieval.

MANDATORY RULES:
1. For any question about project duration, critical path, float, delay impact or recovery, call the relevant tool. Do not calculate CPM mentally.
2. For an incident question, call investigate_delay_event and search_project_evidence. Cite the exact source filename in your answer.
3. Separate: RECORDED FACTS (from supplied evidence), CALCULATED RESULTS (from the schedule engine), ASSUMPTIONS (declared scenario inputs), and UNKNOWN INFORMATION (not in the data).
4. Never invent a root cause, contract clause, supplier commitment, cost, crew availability, safety outcome, or actual project impact.
5. Recovery simulations are schedule-only what-if calculations. They are not approvals or instructions to contractors. Explicitly state the feasibility warning.
6. The project and evidence are synthetic portfolio data, not real client records and not Escalo systems.
7. Respect backend authorization errors. Do not try another tool to bypass a denied request.
8. Use concise, structured answers. Explain why a delay does or does not move the overall completion date by referencing the calculated float and dependency path.
""".strip()


def run_agent(message: str, user: dict[str, Any]) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini API key is missing. Add GEMINI_API_KEY to the local .env file.")
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = (
        f"SYSTEM INSTRUCTIONS:\n{SYSTEM_INSTRUCTIONS}\n\n"
        f"AUTHENTICATED USER CONTEXT (server verified):\n"
        f"Name: {user['full_name']}\nRole: {user['role']}\n\n"
        f"USER REQUEST:\n{message.strip()}"
    )
    history: list[dict[str, Any]] = [
        {"type": "user_input", "content": [{"type": "text", "text": prompt}]}
    ]
    tool_events: list[dict[str, Any]] = []

    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL, input=history,
            tools=SITE_SIGNAL_TOOL_DECLARATIONS, store=False,
        )
        for _ in range(4):
            steps = list(interaction.steps or [])
            function_calls = [step for step in steps if step.type == "function_call"]
            if not function_calls:
                break
            history.extend(step.model_dump(exclude_none=True) for step in steps)
            function_results: list[dict[str, Any]] = []
            for call in function_calls:
                arguments = call.arguments or {}
                result = dispatch_site_signal_tool(call.name, arguments, user)
                tool_events.append({
                    "name": call.name, "arguments": arguments,
                    "result": result,
                    "status": "error" if "error" in result else "success",
                })
                function_results.append({
                    "type": "function_result", "name": call.name,
                    "call_id": call.id,
                    "result": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                })
            history.extend(function_results)
            interaction = client.interactions.create(
                model=GEMINI_MODEL, input=history,
                tools=SITE_SIGNAL_TOOL_DECLARATIONS, store=False,
            )
        else:
            return {
                "answer": "I stopped after four tool rounds to prevent an uncontrolled workflow. Please narrow the request.",
                "tool_events": tool_events, "model": GEMINI_MODEL,
            }
        answer = (interaction.output_text or "I could not produce a final response. Please retry.").strip()
        return {"answer": answer, "tool_events": tool_events, "model": GEMINI_MODEL}
    finally:
        client.close()
