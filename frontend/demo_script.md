# SiteSignal — 90-second recruiter demo script

**Purpose:** Show a concrete engineering workflow, not just a chatbot UI.

**Before recording**

1. Start the app with `uvicorn app.main:app --reload`.
2. Ensure `.env` contains the user's Gemini API key.
3. Run `python -m app.ingest_construction` once if the construction evidence index is empty.
4. Open `http://127.0.0.1:8000` and sign in as `manager` / `Manager@123`.
5. Open **Guided demo** and click **Run guided demo**. Wait for all seven checks to pass.
6. Then click **Run live Gemini investigation**. This uses the real Gemini API and consumes API quota.

## Suggested narration (about 90 seconds)

**0–12 seconds — Problem framing**

"SiteSignal is an independent proof-of-concept inspired by a construction-delay problem Escalo has publicly discussed. It investigates how a reported delay can propagate through dependent activities. All project records in this prototype are synthetic."

**12–30 seconds — Deterministic engineering**

"The schedule engine validates the dependency graph and calculates the Critical Path Method. It does not ask the LLM to calculate dates. In this scenario, the baseline is 33 calendar days, and the combined event-adjusted forecast is 35 days."

**30–48 seconds — Why impact differs**

"EV-001 affects a critical-path approval activity and shifts project completion by two days. EV-002 is also reported as a two-day delay, but its activity has available float, so that event alone does not move the project finish. The impact is calculated from the graph, not guessed by the model."

**48–62 seconds — Evidence and RAG**

"Each event links to a source report. The Gemini agent can retrieve relevant passages and must distinguish recorded facts, calculated results, assumptions and unknowns."

**62–75 seconds — Recovery what-if**

"The recovery simulation reduces the assumed procurement duration by one day and recalculates the finish. This is a schedule-only what-if; it does not prove supplier capacity, cost or resource feasibility, and it does not change an approved baseline."

**75–90 seconds — Security and close**

"The guided test also verifies server-side role restrictions: a technician cannot run the manager-only recovery endpoint, and a restricted sales role cannot read construction data. The point is to combine deterministic domain logic, evidence-grounded AI orchestration and explicit authorization boundaries."

## Recording checklist

- Record the app, not the source code editor.
- Show the guided demo results panel with all seven checks passing.
- Show the live Gemini tool events only after the live call succeeds.
- Show the evidence register and audit trail briefly.
- Keep the project synthetic-data notice visible.
- Do not show the `.env` file, API key, terminal environment variables or private credentials.
- Do not claim live client integration, real project savings, predictive ML accuracy, resource optimization or production readiness.

## If the Gemini call fails during recording

Do not fake or edit a successful response. Record the deterministic guided workflow, state that Gemini inference is an optional live step, and fix the API/model/quota issue before claiming the LLM demo works.
