
from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from typing import Any

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.construction_tools import (
    SITE_SIGNAL_TOOL_DECLARATIONS,
    dispatch_site_signal_tool,
)

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTIONS = """
You are SiteSignal, an AI-assisted construction delay investigation
and schedule intelligence prototype.

Use the provided deterministic tools and evidence retrieval.
Follow these rules:

1. For project duration, critical path, float, delay impact, or recovery,
   call the relevant tool. Never calculate CPM mentally.

2. For an incident question, call investigate_delay_event and
   search_project_evidence. Cite exact source filenames returned
   by retrieval.

3. Separate RECORDED FACTS, CALCULATED RESULTS, ASSUMPTIONS,
   and UNKNOWN INFORMATION.

4. Never invent a root cause, contract clause, supplier commitment,
   cost, crew availability, safety outcome, or real project impact.

5. Recovery simulations are schedule-only what-if calculations,
   not approvals or contractor instructions. State the feasibility warning.

6. Project data and evidence are synthetic portfolio data,
   not real client records and not Escalo systems.

7. Respect authorization errors returned by tools.
   Never attempt to bypass a denied action.

8. Explain whether delay affects project completion by using
   the deterministic float and dependency results.
""".strip()

MAX_TOOL_ROUNDS = 4


def _build_tool(types: Any) -> Any:
    """Convert app tool declarations into Gemini function declarations."""
    functions = []

    for declaration in SITE_SIGNAL_TOOL_DECLARATIONS:
        functions.append(
            types.FunctionDeclaration(
                name=declaration["name"],
                description=declaration.get("description", ""),
                parameters_json_schema=declaration.get(
                    "parameters",
                    {"type": "object", "properties": {}},
                ),
            )
        )

    return types.Tool(function_declarations=functions)


def _response_content(response: Any) -> Any | None:
    """Return the first Gemini candidate's complete content."""
    candidates = getattr(response, "candidates", None) or []

    if not candidates:
        return None

    return getattr(candidates[0], "content", None)


def _extract_function_calls(response: Any) -> list[Any]:
    """Extract function calls across supported Google SDK response formats."""

    calls = getattr(response, "function_calls", None)

    if calls:
        return list(calls)

    found: list[Any] = []
    content = _response_content(response)

    for part in getattr(content, "parts", None) or []:
        function_call = getattr(part, "function_call", None)

        if function_call is not None:
            found.append(part)

    return found


def _call_details(call: Any) -> tuple[str, dict[str, Any]]:
    """Normalize function name and arguments across SDK response formats."""

    function_call = getattr(call, "function_call", None) or call

    name = (
        getattr(function_call, "name", None)
        or getattr(call, "name", None)
    )

    arguments = getattr(function_call, "args", None)

    if arguments is None:
        arguments = getattr(call, "args", None)

    if arguments is None:
        arguments = {}

    if not isinstance(arguments, dict):
        try:
            arguments = dict(arguments)
        except Exception as exc:
            raise ValueError(
                f"Gemini returned invalid arguments for tool {name!r}."
            ) from exc

    if not name:
        raise ValueError(
            "Gemini returned a function call without a function name."
        )

    return str(name), arguments


def _response_problem(response: Any) -> str:
    """Describe an empty or incomplete Gemini response."""

    details: list[str] = []

    prompt_feedback = getattr(response, "prompt_feedback", None)

    if prompt_feedback:
        details.append(f"prompt_feedback={prompt_feedback}")

    candidates = getattr(response, "candidates", None) or []

    if candidates:
        finish_reason = getattr(candidates[0], "finish_reason", None)

        if finish_reason:
            details.append(f"finish_reason={finish_reason}")

    return (
        "; ".join(details)
        or "The model returned neither text nor a function call."
    )


_SOURCE_NAME = re.compile(r"[\w\-./\\]+\.md\b")


def _returned_sources(tool_events: list[dict[str, Any]]) -> set[str]:
    """Evidence filenames that successful tool calls in this run actually returned."""
    found: set[str] = set()
    for event in tool_events:
        result = event.get("result")
        if event.get("status") != "success" or not isinstance(result, dict):
            continue
        evidence = result.get("evidence")
        if isinstance(evidence, dict) and evidence.get("source"):
            found.add(str(evidence["source"]))
        for match in result.get("matches") or []:
            if isinstance(match, dict) and match.get("source"):
                found.add(str(match["source"]))
        for entry in result.get("evidence_registry") or []:
            if isinstance(entry, dict) and entry.get("available") and entry.get("source"):
                found.add(str(entry["source"]))
    return found


def check_citations(answer: str, tool_events: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Which Markdown source files the answer cites, and which of them no tool returned in this run.

    A cited filename that no successful tool call returned cannot be traced to evidence, whether the model
    made it up or recalled it from elsewhere, so it is reported as unsupported."""
    available = _returned_sources(tool_events)
    cited = sorted({PurePosixPath(m.replace("\\", "/")).name for m in _SOURCE_NAME.findall(answer or "")})
    return {
        "cited": cited,
        "supported": [c for c in cited if c in available],
        "unsupported": [c for c in cited if c not in available],
    }


def _execute_call(call: Any, user: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Run one model-requested tool call. A malformed call or a failing tool becomes an error result
    that is handed back to the model; it never aborts the whole investigation."""
    try:
        name, arguments = _call_details(call)
    except ValueError as exc:
        inner = getattr(call, "function_call", None) or call
        name = str(getattr(inner, "name", None) or "unknown_function")
        logger.warning("Rejected malformed tool call name=%s", name)
        return name, {}, {"error": f"Invalid tool call: {exc}"}

    logger.info("Executing SiteSignal tool name=%s", name)
    try:
        result = dispatch_site_signal_tool(name, arguments, user)
        if not isinstance(result, dict):
            result = {"result": result}
    except Exception as exc:
        logger.exception("SiteSignal tool execution failed name=%s", name)
        result = {"error": f"Tool execution failed: {type(exc).__name__}."}
    return name, arguments, result


def run_agent(
    message: str,
    user: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute a bounded and auditable Gemini function-calling workflow.

    Flow:
        User request
        -> Gemini
        -> Function call
        -> Python tool execution
        -> Function result returned to Gemini
        -> Final Gemini response
    """

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Gemini API key is missing. "
            "Add GEMINI_API_KEY to the local .env file."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    tool = _build_tool(types)
    tool_events: list[dict[str, Any]] = []

    authenticated_context = (
        f"Authenticated user (verified by backend): "
        f"{user.get('full_name', 'Unknown')}; "
        f"role={user.get('role', 'unknown')}. "
        "Never infer or elevate permissions."
    )

    contents: list[Any] = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=(
                        f"{authenticated_context}\n\n"
                        f"USER REQUEST:\n{message.strip()}"
                    )
                )
            ],
        )
    ]

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTIONS,
        tools=[tool],
        temperature=0.2,
        max_output_tokens=2048,
    )

    try:
        logger.info(
            "Starting Gemini Generate Content request model=%s role=%s",
            GEMINI_MODEL,
            user.get("role"),
        )

        for round_index in range(MAX_TOOL_ROUNDS + 1):

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            calls = _extract_function_calls(response)

            logger.info(
                "Gemini generate_content round=%s "
                "text_present=%s function_calls=%s",
                round_index + 1,
                bool((getattr(response, "text", None) or "").strip()),
                len(calls),
            )

            # No function calls: Gemini has produced its final answer.
            if not calls:
                answer = (
                    getattr(response, "text", None) or ""
                ).strip()

                if not answer:
                    raise RuntimeError(
                        "Gemini returned an empty response. "
                        f"{_response_problem(response)}"
                    )

                logger.info(
                    "Gemini agent completed tool_events=%s",
                    len(tool_events),
                )

                citations = check_citations(answer, tool_events)
                if citations["unsupported"]:
                    answer += (
                        "\n\nCitation check: "
                        + ", ".join(citations["unsupported"])
                        + " was not returned by any tool in this investigation; do not rely on it as evidence."
                    )

                return {
                    "answer": answer,
                    "tool_events": tool_events,
                    "citations": citations,
                    "model": GEMINI_MODEL,
                }

            # Prevent uncontrolled or recursive tool execution.
            if round_index >= MAX_TOOL_ROUNDS:
                logger.warning(
                    "Gemini agent reached the %s-round tool limit",
                    MAX_TOOL_ROUNDS,
                )

                return {
                    "answer": (
                        f"I stopped after {MAX_TOOL_ROUNDS} tool rounds "
                        "to prevent an uncontrolled workflow. "
                        "The executed tool results are shown below; "
                        "please narrow the request for a final analysis."
                    ),
                    "tool_events": tool_events,
                    "citations": check_citations("", tool_events),
                    "model": GEMINI_MODEL,
                }

            # Preserve the complete model response when continuing
            # the function-calling conversation.
            model_content = _response_content(response)

            if model_content is None:
                raise RuntimeError(
                    "Gemini requested a tool but returned no candidate "
                    "content to continue the conversation."
                )

            contents.append(model_content)

            function_response_parts = []

            # Execute each requested SiteSignal function.
            for call in calls:

                name, arguments, result = _execute_call(call, user)

                event_status = (
                    "error" if "error" in result else "success"
                )

                tool_events.append(
                    {
                        "name": name,
                        "arguments": arguments,
                        "result": result,
                        "status": event_status,
                    }
                )

                # Construct the function response for Gemini.
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=name,
                        response={"result": result},
                    )
                )

            # IMPORTANT:
            # Generate Content API expects function responses
            # inside a user-role Content object.
            #
            # Do NOT use role="tool"; Gemini rejects that role
            # with HTTP 400 INVALID_ARGUMENT.

            contents.append(
                types.Content(
                    role="user",
                    parts=function_response_parts,
                )
            )

        raise RuntimeError(
            "Gemini agent exited unexpectedly without a final response."
        )

    except Exception:
        logger.exception(
            "Gemini Generate Content API failed model=%s",
            GEMINI_MODEL,
        )
        raise

    finally:
        client.close()
