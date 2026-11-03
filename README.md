# SiteSignal — Delay Cascade Intelligence

**Independent portfolio prototype.** SiteSignal investigates a synthetic construction schedule by combining deterministic Critical Path Method (CPM), evidence-grounded retrieval, Gemini function calling, role-based access, and schedule-only recovery simulation.

It was conceived after reviewing Escalo AI's public discussion of construction delays. It is not affiliated with, connected to, or endorsed by Escalo AI; it does not use Escalo/client data or connect to any production construction system.

## Core capabilities

- **Deterministic schedule engine:** topological sorting, dependency validation, CPM forward/backward passes, total float, critical-path identification, and finish-date calculation.
- **Delay propagation:** applies explicitly modelled event adjustments to the dependency network and calculates downstream shifts. Event-to-duration mapping is a declared scenario assumption, not an ML prediction.
- **Recovery simulation:** runs a named duration-reduction scenario and reports schedule-only results plus feasibility limitations.
- **Gemini agent:** uses the Google Gen AI SDK `generate_content` API with native function calling to select allow-listed SiteSignal tools. Python, not the LLM, calculates CPM.
- **Construction RAG:** Gemini embeddings index synthetic incident reports and an illustrative procedure in a dedicated ChromaDB collection.
- **Evidence provenance:** investigation results retain source filenames and synthetic source text. Missing causes remain unknown.
- **Security demonstration:** local demo authentication, server-side role checks, manager-only recovery simulation, and audit events.

## Data notice and assumptions

All records in `data/construction_project.json` and `data/construction_docs/` are synthetic. They are not real incident reports, client records, policies, or project evidence.

The schedule uses calendar days and finish-to-start relationships. Weekends, holidays, resource availability, resource levelling, costs, overtime, procurement feasibility, permits, safety, and contractual constraints are not modelled. Recovery calculations are what-if outputs only and do not update an approved baseline.

## Run locally on Windows

Use the project's virtual environment consistently:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Create `.env` only if it does not already exist. Do not overwrite an existing `.env`:

```powershell
Copy-Item .env.example .env
notepad .env
```

Configure the key locally. Do not commit or share `.env`:

```env
GEMINI_API_KEY=YOUR_KEY
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSIONS=768
```

Index the synthetic construction evidence (this sends an embeddings request to Gemini):

```powershell
.\.venv\Scripts\python.exe -m app.ingest_construction
```

Start the service:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

Demo accounts:

- Manager: `manager` / `Manager@123`
- Technician: `technician` / `Tech@123`
- Restricted sales: `sales` / `Sales@123`

These fixed accounts and in-memory sessions are for a public portfolio demonstration only, not production authentication.

## Deploy to Render Free

The repository includes `render.yaml` for a Render Blueprint. Connect this GitHub repository through Render's dashboard and create the Blueprint. During initial setup, provide `GEMINI_API_KEY` when Render prompts for the secret. Never put the key in `render.yaml`, GitHub, or the README.

The Blueprint configures:

- Python 3.11.9
- Free Python web service
- `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- `/api/health` health check
- Gemini model `gemini-3.5-flash-lite`
- Chroma and SQLite paths under `/tmp/sitesignal`

At startup, the app initializes its demo SQLite database and, when the RAG collection is empty, indexes the small synthetic construction evidence set. The health endpoint reports whether Gemini is configured and how many RAG chunks are indexed.

After deployment, test `https://YOUR-SERVICE.onrender.com/api/health`, then open the service homepage and sign in with the manager demo account above.

### Render Free limitations

This is a recruiter preview, not a production deployment. Render Free web services spin down after 15 minutes without inbound traffic and take about a minute to wake. Their filesystem is ephemeral: SQLite data, Chroma indexes, in-memory sessions, and audit records can be lost on restart, redeploy, or spin-down. SiteSignal rebuilds the demo database and RAG index at startup; this may consume Gemini embedding quota again. Users may need to sign in again after a restart.

Render Free includes monthly instance-hour and bandwidth allowances. Excess bandwidth can incur supplementary charges under Render's current terms. Monitor workspace usage and do not upgrade or enable paid add-ons if maintaining a zero-spend setup is essential. If absolute zero billing risk is required, keep the demo local rather than exposing it publicly.

## Tests and limitations

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Automated tests do not call Gemini. Live Gemini generation/function-calling and RAG ingestion must be smoke-tested separately using a private API key.

This is a synthetic proof-of-concept, not a production construction-management system. Event-to-duration mapping requires an explicit project-controls decision. Recovery scenarios do not optimise labour/resources or establish feasibility. No historical project dataset is included, so no predictive ML performance claim is made.
