# SiteSignal — Delay Cascade Intelligence

**Independent portfolio prototype for an AI/ML Engineer application.** SiteSignal investigates a synthetic construction schedule by combining deterministic Critical Path Method (CPM), source-grounded evidence retrieval, Gemini native function calling, role-based access and schedule-only recovery simulation.

It was conceived after reviewing Escalo AI's public discussion of construction delays. It is not affiliated with, connected to, or endorsed by Escalo AI; it does not use Escalo/client data or connect to any production construction system.

## Deployment security note

All project records are synthetic. For a public Render deployment, set unique values for `DEMO_MANAGER_PASSWORD` and `DEMO_TECHNICIAN_PASSWORD` in Render's secret environment-variable form. Do not rely on the local development defaults, and do not publish deployment passwords in this repository, screenshots, or public messages. The manager account can run Gemini requests, so protecting its password also protects the project's Gemini quota.

For local development, the default demo accounts remain available unless overridden in `.env`:

- Manager username: `manager`; local default password: `Manager@123`.
- Technician username: `technician`; local default password: `Tech@123`.
- Sales username: `sales`; local default password: `Sales@123` (restricted from construction data).

The public deployment should use the unique passwords entered as Render environment secrets, not these local defaults.

## What is meaningfully engineered

- **Deterministic schedule engine:** topological sorting, missing/circular dependency validation, CPM forward/backward passes, total float, critical-path identification and finish-date calculation.
- **Delay propagation:** applies explicit, evidence-linked event adjustments to the dependency network and calculates downstream date shifts. Event-to-duration mapping is a declared scenario assumption, not an ML prediction.
- **Recovery simulation:** runs a named duration-reduction scenario and reports schedule-only results plus feasibility limitations.
- **Gemini agent:** uses Gemini Generate Content and native function calling to select allow-listed SiteSignal tools. The model does not calculate CPM itself.
- **Construction RAG:** Gemini embeddings index synthetic incident reports and an illustrative procedure in a dedicated ChromaDB collection.
- **Evidence provenance:** investigation results return source filenames and synthetic report content. Missing causes remain unknown.
- **Security:** local demo authentication, server-side role checks, manager-only recovery simulation and audit events.

## Data notice and assumptions

All records in `data/construction_project.json` and `data/construction_docs/` are synthetic. They are not real incident reports, client records, policies or project evidence.

The schedule uses calendar days and finish-to-start relationships. Weekends, holidays, resource availability, resource levelling, costs, overtime, procurement feasibility, permits, safety and contractual constraints are not modelled. Recovery calculations are what-if outputs only and do not update an approved baseline.

## Run locally on Windows

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The application reads `GEMINI_API_KEY` and optional `DEMO_MANAGER_PASSWORD`, `DEMO_TECHNICIAN_PASSWORD`, and `DEMO_SALES_PASSWORD` from a local `.env`. Do not commit or share `.env`.

## Render deployment

The repository includes a root-level `render.yaml` Blueprint. Connect the repository through **Render Dashboard → New → Blueprint**, select branch `main`, and keep Blueprint Path as `render.yaml`.

When prompted, enter the Gemini API key and unique manager and technician demo passwords in the private environment-variable fields. Do not put these secrets in YAML or GitHub.

Render Free uses ephemeral storage. The demo database and Chroma index are recreated at startup; audit history and sessions can be lost after restart or sleep. Startup re-indexes the small synthetic evidence set when the Chroma collection is empty, consuming Gemini embedding quota. The free service can sleep when idle and cold-start on the next visit.

## Suggested demonstration

1. Open **Schedule analysis**. Show baseline duration, forecast duration, critical path and non-critical float.
2. Ask: “Investigate EV-001. Separate recorded facts, calculated impact, assumptions and unknowns. Cite the source filename.”
3. Ask: “Compare EV-001 with EV-002. Why does one move the project finish while the other is absorbed by float?”
4. Run **REC-001** using the recovery simulation button. Explain that the schedule model shows one day recovered but does not prove resources/cost/feasibility.
5. Open **Evidence register** and show each synthetic source.
6. Sign in as technician and verify recovery simulation is forbidden.
7. Sign in as sales and verify construction endpoints are forbidden.
8. Review the manager audit trail.

## Limitations to state in an interview

- This is a synthetic proof-of-concept, not a production construction-management system.
- The current event model represents a reported variance as an effective activity-duration adjustment. Real schedule updates require an explicit modelling decision and project-control approval.
- The recovery scenario modifies a synthetic duration; it does not optimise labour/resources or establish feasibility.
- The Gemini model explains and orchestrates tool use; deterministic Python code calculates schedule facts.
- Authentication/session setup is for demonstration only, not production identity management.
- No historical project dataset is included, so no predictive ML performance claim is made.
