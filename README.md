# SiteSignal — Delay Cascade Intelligence

**Independent portfolio prototype for an AI/ML Engineer application.** SiteSignal investigates a synthetic construction schedule by combining deterministic Critical Path Method (CPM), source-grounded evidence retrieval, Gemini native function calling, role-based access and schedule-only recovery simulation.

It was conceived after reviewing Escalo AI's public discussion of construction delays. It is not affiliated with, connected to, or endorsed by Escalo AI; it does not use Escalo/client data or connect to any production construction system.

## What is meaningfully engineered

- **Deterministic schedule engine:** topological sorting, missing/circular dependency validation, CPM forward/backward passes, total float, critical-path identification and finish-date calculation.
- **Delay propagation:** applies explicit, evidence-linked event adjustments to the dependency network and calculates downstream date shifts. Event-to-duration mapping is a declared scenario assumption, not an ML prediction.
- **Recovery simulation:** runs a named duration-reduction scenario and reports schedule-only results plus feasibility limitations.
- **Gemini agent:** uses the Interactions API and native function calling to select allow-listed SiteSignal tools. The model does not calculate CPM itself.
- **Construction RAG:** Gemini embeddings index synthetic incident reports and an illustrative procedure in a dedicated ChromaDB collection, separate from the former dealership collection.
- **Evidence provenance:** investigation results return source filename and original synthetic report content. Missing causes remain unknown.
- **Security:** local demo authentication, server-side role checks, manager-only recovery simulation and audit events.

## Data notice and assumptions

All records in `data/construction_project.json` and `data/construction_docs/` are synthetic. They are not real incident reports, client records, policies or project evidence.

The schedule uses calendar days and finish-to-start relationships. Weekends, holidays, resource availability, resource levelling, costs, overtime, procurement feasibility, permits, safety and contractual constraints are not modelled. Recovery calculations are what-if outputs only and do not update an approved baseline.

## Run on Windows

Use the existing `.venv` in this project:

```powershell
python -m pytest -q
```

Set up `.env` if not already present (do not overwrite an existing `.env`):

```powershell
Copy-Item .env.example .env
notepad .env
```

Set your Gemini key locally in `.env`. Do not commit or share `.env`.

The current configuration expects:

```env
GEMINI_API_KEY=YOUR_KEY
GEMINI_MODEL=gemini-3.8-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSIONS=768
```

Index construction evidence (this sends embedding requests to Gemini and uses API quota):

```powershell
python -m app.ingest_construction
```

Start the application:

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and sign in as the demo project manager:

- Username: `manager`
- Password: `Manager@123`

A technician account can read project information but cannot simulate recovery. The sales account is intentionally denied access to construction data.

## Suggested demonstration

1. Open **Schedule analysis**. Show baseline duration, forecast duration, critical path and non-critical float.
2. Ask: “Investigate EV-001. Separate recorded facts, calculated impact, assumptions and unknowns. Cite the source filename.”
3. Ask: “Compare EV-001 with EV-002. Why does one move the project finish while the other is absorbed by float?”
4. Run **REC-001** using the recovery simulation button. Explain that the schedule model shows one day recovered but does not prove resources/cost/feasibility.
5. Open **Evidence register** and show each synthetic source.
6. Sign in as technician and verify recovery simulation is forbidden.
7. Sign in as sales and verify construction endpoints are forbidden.
8. Review the manager audit trail.

## Tests

```powershell
python -m pytest -q
```

Tests cover CPM, float, circular/missing dependencies, delay propagation, evidence requirements, recovery assumptions and construction dataset/service outputs. The automated tests do not call Gemini. Live Gemini generation/function-calling and construction embedding ingestion must be smoke-tested separately using the user's local API key.

## Limitations to state in an interview

- This is a synthetic proof-of-concept, not a production construction-management system.
- The current event model represents a reported variance as an effective activity-duration adjustment. Real schedule updates require an explicit modelling decision and project-control approval.
- The recovery scenario modifies a synthetic duration; it does not optimise labour/resources or establish feasibility.
- The Gemini model extracts/explains and orchestrates tool use; deterministic Python code calculates schedule facts.
- The local authentication/session setup is for demonstration only, not production deployment. SiteSignal uses a new `data/sitesignal.db` database, separate from the previous dealership prototype database.
- No historical project dataset is included, so no predictive ML performance claim is made.
