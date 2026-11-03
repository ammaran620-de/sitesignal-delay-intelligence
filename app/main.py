from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.agent import run_agent
from app.config import FRONTEND_PATH, GEMINI_API_KEY, GEMINI_MODEL
from app.construction_rag import (
    construction_rag_status,
    ingest_construction_evidence,
    search_construction_evidence,
)
from app.construction_service import (
    get_project_overview,
    investigate_delay,
    list_evidence,
    simulate_named_recovery,
)
from app.db import connection, init_db, write_audit
from app.passwords import verify_password
from app.security import create_session, get_current_user, revoke_session
from app.tools import get_audit_logs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Recreate the demo database after a free-host restart if its filesystem
    # was reset. Demo users are seeded by init_db() when the database is empty.
    init_db()

    # Render Free uses ephemeral storage. Rebuild the small synthetic RAG
    # collection whenever it is absent after startup/redeploy/idle spin-down.
    if GEMINI_API_KEY:
        rag_status = construction_rag_status()
        if not rag_status.get("ready", False):
            try:
                indexed = ingest_construction_evidence()
                logger.info(
                    "SiteSignal construction RAG initialized: %s chunks indexed",
                    indexed,
                )
            except Exception:
                # Keep the web app available even if Gemini embeddings are
                # temporarily unavailable. /api/health reports RAG readiness.
                logger.exception(
                    "Construction RAG startup indexing failed; app will start without indexed evidence"
                )
    else:
        logger.warning(
            "GEMINI_API_KEY is not configured; live Gemini and RAG are unavailable"
        )

    yield


app = FastAPI(
    title="SiteSignal — Delay Cascade Intelligence",
    description=(
        "Independent portfolio prototype combining deterministic CPM, evidence retrieval, "
        "Gemini function calling, RBAC and auditable schedule-only recovery simulations."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(FRONTEND_PATH)), name="static")


class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=2000)


def _require_project_access(user: dict[str, Any], manager_only: bool = False) -> None:
    allowed = {"manager"} if manager_only else {"manager", "technician"}
    if user.get("role") not in allowed:
        raise HTTPException(status_code=403, detail="Access denied for this construction project operation.")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(FRONTEND_PATH / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    evidence = construction_rag_status()
    return {
        "status": "healthy",
        "service": "sitesignal",
        "gemini_configured": bool(GEMINI_API_KEY),
        "gemini_model": GEMINI_MODEL,
        "gemini_api": "generate_content",
        "construction_rag_ready": evidence.get("ready", False),
        "construction_rag_chunks": evidence.get("chunks", 0),
    }


@app.post("/api/login")
def login(request: LoginRequest) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            "SELECT id, username, full_name, password_hash, role, branch_id FROM users WHERE username = ? AND is_active = 1",
            (request.username.strip(),),
        ).fetchone()
    if not row or not verify_password(request.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")
    token = create_session(row["username"])
    user = {
        "id": row["id"], "username": row["username"], "full_name": row["full_name"],
        "role": row["role"], "branch_id": row["branch_id"],
    }
    write_audit(user["id"], "login", "session", None, "success")
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return user


@app.post("/api/logout")
def logout(authorization: str | None = Header(default=None), user: dict[str, Any] = Depends(get_current_user)) -> dict[str, str]:
    if authorization and authorization.lower().startswith("bearer "):
        revoke_session(authorization.split(" ", 1)[1].strip())
    write_audit(user["id"], "logout", "session", None, "success")
    return {"status": "signed_out"}


@app.get("/api/construction/overview")
def construction_overview(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _require_project_access(user)
    try:
        result = get_project_overview()
        write_audit(user["id"], "get_project_schedule", "construction_project", result["project"]["id"], "allowed")
        return result
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/construction/evidence")
def construction_evidence(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _require_project_access(user)
    items = list_evidence()
    write_audit(user["id"], "list_construction_evidence", "construction_evidence", None, "allowed")
    return {"items": items, "synthetic": True}


@app.get("/api/construction/events/{event_id}")
def construction_event(event_id: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _require_project_access(user)
    try:
        result = investigate_delay(event_id)
        write_audit(user["id"], "investigate_delay_event", "construction_event", event_id, "allowed")
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/construction/recovery/{scenario_id}")
def construction_recovery(scenario_id: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _require_project_access(user, manager_only=True)
    try:
        result = simulate_named_recovery(scenario_id)
        write_audit(user["id"], "simulate_recovery_scenario", "recovery_scenario", scenario_id, "allowed")
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/construction/search")
def construction_search(q: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _require_project_access(user)
    try:
        result = search_construction_evidence(q)
        write_audit(user["id"], "search_project_evidence", "construction_evidence", None, "allowed", q[:160])
        return result
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/chat")
async def chat(request: ChatRequest, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Gemini API key is not configured in the service environment.")
    try:
        return await run_in_threadpool(run_agent, request.message, user)
    except Exception as exc:
        logger.exception(
            "Gemini chat failed user_id=%s role=%s model=%s",
            user.get("id"), user.get("role"), GEMINI_MODEL,
        )
        message = str(exc).lower()
        code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if code == 429 or "429" in message or "quota" in message or "rate" in message:
            detail = "Gemini API quota/rate limit reached. Check AI Studio usage and retry later."
        elif code in (400, 404) or "invalid_argument" in message or "not found" in message:
            detail = "Gemini rejected the model or request format. The technical error is printed in the server logs."
        elif code in (401, 403) or "api key" in message or "unauthorized" in message or "permission" in message:
            detail = "Gemini rejected the API request. Check the service API key and selected model access."
        else:
            detail = "The Gemini agent request failed. The technical traceback is printed in the server logs."
        raise HTTPException(status_code=502, detail=detail) from exc


@app.get("/api/audit")
def audit(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return {"items": get_audit_logs(user)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
