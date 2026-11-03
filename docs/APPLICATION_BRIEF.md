# SiteSignal — Technical Demonstration Brief

## Why this project

SiteSignal is an independent proof-of-concept inspired by Escalo AI's publicly shared discussion of construction delays and operational automation. It is not an Escalo assignment, a client deliverable, or a connection to Escalo infrastructure.

## Problem framed

A project delay should not be treated as a standalone status label. Its effect depends on the activity dependency network, available float, critical path and the evidence available for the reported event.

## Engineering approach

1. **Schedule mathematics:** deterministic Python implementation of a directed acyclic activity network and CPM forward/backward pass.
2. **Delay investigation:** apply explicitly declared event adjustments and trace downstream activity shifts.
3. **Evidence:** incident reports and an illustrative procedure are indexed in a dedicated ChromaDB collection using Gemini embeddings.
4. **Agent:** Gemini Interactions API native function calling orchestrates allow-listed tools; the model is instructed to use the deterministic engine for schedule facts.
5. **Controls:** FastAPI authentication, server-side role checks, manager-only recovery simulation and an audit log.

## Synthetic demonstration result

The supplied dataset has a 33-calendar-day baseline and two synthetic incidents. The structural approval event moves the modelled project finish by two days. The independent site mobilisation event is absorbed by available float. A named one-day procurement-duration reduction scenario recovers one day in the schedule model.

These results are test-data calculations, not measured savings or real project outcomes.

## Recruiter demonstration

The dashboard opens on a Guided demo panel. Its one-click walkthrough calls the local API to demonstrate CPM baseline/forecast calculations, source-linked investigations of two contrasting delay events, the recovery what-if, and two server-side authorization boundaries. A separate live Gemini investigation button runs the LLM/function-calling path after the construction RAG index is configured. The deterministic walkthrough does not call Gemini or consume API quota. See `docs/DEMO_RUNBOOK.md` and `frontend/demo_script.md`.

## Verification status

- 20 automated Python tests pass in the packaged development environment.
- JavaScript syntax check passes.
- Python compilation checks pass.
- Construction project JSON parses successfully.
- FastAPI tests verify manager access, technician read-only access, manager-only recovery simulation and sales-user denial.
- Live Gemini embedding ingestion and live Gemini function-calling must be smoke-tested with the developer's local API key before describing the end-to-end agent as live-verified.

## Limitations

All project records, reports and procedure text are synthetic. The schedule engine uses calendar days and finish-to-start links; it does not model working calendars, resource levelling, crews, cost, overtime, supplier feasibility, permits, safety or contract terms. Recovery is a schedule-only what-if result and does not change the baseline. No historical dataset is present, so SiteSignal makes no predictive-ML accuracy claim.
