# SiteSignal Architecture

```text
Browser UI
  └── Guided demo runner (seven live local API checks; no Gemini request)
  └── FastAPI (authenticated session)
       ├── GET /api/construction/overview
       │    └── construction_service
       │         ├── load synthetic project JSON
       │         └── schedule_engine (DAG + CPM + delay + scenario)
       ├── GET /api/construction/evidence
       │    └── synthetic Markdown source register
       ├── GET /api/construction/events/{id}
       │    └── event-to-source provenance
       ├── POST /api/construction/recovery/{id}
       │    └── manager-only, read-only what-if simulation
       └── POST /api/chat
            └── Gemini Interactions API
                 └── allow-listed function calling
                      ├── get_project_schedule
                      ├── investigate_delay_event
                      ├── simulate_recovery_scenario
                      └── search_project_evidence
                           └── Gemini embeddings → ChromaDB collection
                                sitesignal_construction_evidence
```

## Trust boundaries

- Browser identity is established by FastAPI session; model-supplied identity is not trusted.
- Server-side role checks protect project read and recovery simulation tools.
- Gemini can select only declared functions; it cannot execute arbitrary SQL, Python or shell commands.
- Schedule calculations are deterministic Python functions. The LLM explains tool outputs but does not calculate CPM.
- Evidence documents are treated as untrusted data, not instructions.
- RAG stores construction evidence in a separate ChromaDB collection to avoid dealership-document contamination.
- All schedule and incident inputs are synthetic; no production system is connected.
