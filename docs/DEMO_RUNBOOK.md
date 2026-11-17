# SiteSignal demonstration runbook

## What a reviewer can verify

The walkthrough covers seven checks. The in-app Guided demo runs the first five automatically against the running local API; the last two are role-boundary checks that need a separate manual sign-in:

Automated by the Guided demo (signed in as the manager):

1. Baseline and event-adjusted schedule analysis.
2. Investigation of critical-path event EV-001 with linked incident report.
3. Investigation of float-absorbed event EV-002.
4. Evidence register and available synthetic source records.
5. Manager-only recovery what-if simulation.

Manual, by signing in as each role:

6. Technician can read the schedule but receives HTTP 403 on recovery.
7. Sales role receives HTTP 403 on construction project data.

The five automated checks are API-backed. They are not screenshots or hard-coded success messages. The Guided demo holds only the manager's session, so it cannot test the technician and sales boundaries itself. Both are also covered by the automated test suite (`tests/test_sitesignal_api.py`, `tests/test_agent.py`), which does not need a manual sign-in.

## Two distinct demo modes

### 1. Guided demo (deterministic local API)

This uses local JSON/Markdown data, the CPM engine, FastAPI endpoints and SQLite audit records. It does not call Gemini and does not consume Gemini API quota.

### 2. Live Gemini investigation

The separate button calls `/api/chat`, using the configured Gemini model and native function declarations. It requires a valid local `GEMINI_API_KEY` and the construction evidence collection to be indexed. This uses API quota. Tool events are shown in the AI investigation panel.

## Run locally on Windows

```powershell
# Activate the existing environment
.\.venv\Scripts\Activate.ps1

# Run tests
python -m pytest -q

# Index synthetic construction documents (Gemini API quota is used)
python -m app.ingest_construction

# Start the application
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Sign in as `manager` with the password you set in `DEMO_MANAGER_PASSWORD`, open Guided demo, and click Run guided demo.

## Limitations

- All project records and documents are synthetic.
- The schedule uses calendar-day finish-to-start relationships.
- Resource levelling, working calendars, holidays, costs, safety constraints, supplier commitments and contractual feasibility are not modelled.
- Recovery is a schedule-only what-if; it does not modify an approved baseline.
- Gemini output is not a validated engineering instruction. A human must review it.
- Demo authentication is not suitable for production. On a hosted service the manager and technician passwords must be configured as secrets (see README, Security and deployment).
