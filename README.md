SiteSignal — Delay Cascade Intelligence
SiteSignal is a Python-based construction schedule analysis prototype. It combines a deterministic Critical Path Method (CPM) engine with source-grounded evidence retrieval and a Gemini-powered tool-calling agent to investigate schedule delays and explore recovery scenarios.

All project records and evidence included in this repository are synthetic. SiteSignal is an independent demonstration and is not connected to any live construction project or production system.
Features
- Critical Path Method (CPM): dependency graph validation, topological sorting, forward and backward passes, total-float calculation, critical-path identification, and project finish-date calculation.
- Delay propagation: applies explicitly defined, evidence-linked event adjustments to the schedule and calculates downstream date changes.
- Recovery simulation: evaluates a proposed activity-duration reduction and reports the resulting schedule impact and feasibility limitations.
- Gemini tool orchestration: uses Gemini Generate Content and native function calling to select from allow-listed application tools.
- Construction evidence retrieval: uses Gemini embeddings and ChromaDB to retrieve relevant synthetic incident reports and supporting procedures.
- Evidence provenance: returns source filenames and supporting report content; causes not established by the available evidence remain unknown.
- Role-based access: provides manager, technician, and sales roles with server-side permission checks and audit events.
How it works
1. The schedule engine validates activity dependencies and calculates the baseline schedule using CPM.
2. A delay investigation retrieves the relevant event record and supporting evidence.
3. The agent selects the appropriate allow-listed tools and combines their results.
4. Python calculates schedule impacts; Gemini coordinates the investigation and explains the returned results.
5. A recovery scenario can be run to compare a proposed duration change against the current schedule.
The language model does not calculate CPM values. Schedule dates, float, critical-path status, and delay propagation are calculated by the deterministic Python schedule engine.
Technology
- Backend: Python, FastAPI
- Schedule analysis: deterministic CPM and dependency-graph calculations
- LLM integration: Gemini Generate Content API and native function calling
- Retrieval: ChromaDB and Gemini embeddings
- Frontend: HTML, CSS, and JavaScript
- Testing: pytest
Data and modelling assumptions
The records in data/construction_project.json and data/construction_docs/ are synthetic examples. They are not real incident reports, client records, policies, or project evidence.

The schedule uses calendar days and finish-to-start relationships. Weekends, holidays, resource availability, resource levelling, costs, overtime, procurement feasibility, permits, safety constraints, and contractual constraints are not modelled.

An event's effective activity-duration adjustment is an explicit scenario assumption, not an automatically inferred measurement or an ML prediction. Recovery calculations are what-if outputs only and do not update an approved project baseline.
Requirements
- Python 3.11
- A Gemini API key for Gemini-powered agent and embedding features
Run locally on Windows
Create and activate a virtual environment, then install the dependencies:
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Create a local .env file in the project root and configure the required values:
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSIONS=768

DEMO_MANAGER_PASSWORD=replace_with_a_unique_password
DEMO_TECHNICIAN_PASSWORD=replace_with_a_unique_password
DEMO_SALES_PASSWORD=replace_with_a_unique_password
Set the demo passwords before the database is initialized for the first time. Keep .env private and never commit API keys or passwords to the repository.

Run the test suite:
python -m pytest -q
Start the application:
python -m uvicorn app.main:app --reload
Open http://127.0.0.1:8000/ in a browser.
Suggested walkthrough
1. Open Schedule analysis and review the baseline duration, forecast duration, critical path, and non-critical float.
2. Investigate EV-001 and review the recorded facts, calculated impact, assumptions, unknowns, and cited source filename.
3. Compare EV-001 with EV-002 to see how available float affects the project finish date.
4. Run REC-001 using the recovery simulation and review the schedule-only result and feasibility limitations.
5. Open the Evidence register to inspect the synthetic supporting sources.
6. Review role permissions and the manager audit trail.
Security and deployment considerations
- Configure unique demo passwords through environment variables before initializing the database.
- Keep .env, API keys, and credentials out of Git, screenshots, and public documentation.
- Use HTTPS and a production-grade authentication and session-management approach before exposing the application publicly.
- Configure persistent storage for the database and ChromaDB data when deploying to an environment where local filesystem data may be temporary.
- Restrict access to manager-only operations using the server-side authorization checks; frontend visibility alone is not a security boundary.
Current limitations
- This is a proof of concept using synthetic data, not a production construction-management system.
- Event-to-duration mapping requires an explicit modelling decision and project-control approval in a real project.
- Recovery scenarios do not optimise labour or resources and do not establish operational feasibility.
- Authentication and session configuration are demonstration-level and require hardening before production use.
- No historical project dataset is included, so the project makes no predictive ML performance claim.