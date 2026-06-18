# Revenue Manager Agent — OTEL Build Challenge

A LangChain Deep Agents Revenue Manager for the Grand Harbour Hotel, built on
reservation data with judgment skills, subagents, and human-in-the-loop gating.

**Submitter:** Lakshman
**Skill pack version:** `otel-rm-v2`

---

## Live agent

URL and credentials are provided privately via the submission intake.

The deployed UI shows tool calls and skill loads inline so the reviewer can
verify routing and progressive disclosure live.

`GET /health` (separate port) returns the DB fingerprint, dataset revision,
row hash, and posted-row count for cross-checking against `etl/LOAD_PROOF.json`.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Chainlit UI (app.py)                        │
│  - Streams tool calls and skill loads inline                      │
│  - Basic auth from env vars                                       │
└──────────────┬───────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│              Deep Agent (agent.py)                                │
│  - create_deep_agent(model, tools, system_prompt, subagents,      │
│                       interrupt_on, checkpointer)                 │
│  - Memory: MemorySaver checkpointer per thread                    │
│  - HITL: get_as_of_otb gated on interrupt_on={get_as_of_otb:True} │
└──────────────┬───────────────────────────────────────────────────┘
               │
               ├── Main agent (planning + synthesis)
               │
               ├── Subagent: segment-analyst
               │     Tools: get_segment_mix, get_block_vs_transient_mix,
               │            get_otb_summary, get_top_companies,
               │            get_room_type_performance
               │
               └── Subagent: demand-analyst
                     Tools: get_pickup_delta, get_otb_summary

               Skills loaded on demand (progressive disclosure):
               - otb_position
               - pickup_and_pace
               - segment_concentration
               - channel_dependency
               - concentration_risk
               - cancellation_patterns
               - group_block_management
               - rate_integrity
               - point_in_time
               - CHALLENGE_SKILL  (otel-rm-v2)
```

---

## Repo layout

```
.
├── agent.py                 # Deep Agent assembly
├── app.py                   # Chainlit UI
├── tools.py                 # 5 required + 2 bonus tools
├── etl.py                   # Playwright scraper
├── schema.sql               # Tables
├── seed.sql                 # Seed lookups (reference page)
├── docker-compose.yml       # Local Postgres
├── health_server.py         # /health endpoint (FastAPI)
├── start.sh                 # Production entrypoint
├── requirements.txt
├── nixpacks.toml            # Railway build config
├── railway.json
├── Procfile
├── .env.example
├── ARCHITECTURE.md          # Skill→tool routing matrix
├── ATTESTATION.md           # Phase 0 comprehension prompts
├── ENGINEERING_DECISIONS.md # Design choices with rationale
├── REQUIRED_TOOLS.md        # Tool spec
├── SUBMISSION.md            # Submission checklist
├── README.md                # This file
├── etl/
│   ├── SCRAPE_MANIFEST.json
│   └── LOAD_PROOF.json
├── scripts/
│   └── compute_load_fingerprint.py
├── memory/
│   └── AGENTS.md            # Long-term agent memory
├── skills/                  # 10 SKILL.md files
│   ├── otb_position.md
│   ├── pickup_and_pace.md
│   ├── segment_concentration.md
│   ├── channel_dependency.md
│   ├── concentration_risk.md
│   ├── cancellation_patterns.md
│   ├── group_block_management.md
│   ├── rate_integrity.md
│   ├── point_in_time.md
│   └── CHALLENGE_SKILL.md
├── tools/
│   └── METRIC_DEFINITIONS.md
├── sql/
│   └── VIEWS.example.sql
└── tests/
    ├── test_etl.py          (3+ cases)
    ├── test_tools.py        (20 cases)
    ├── test_skills.py       (5+ cases)
    └── test_agent.py        (4+ cases)
```

---

## Run locally

```bash
docker compose up -d                # Postgres on :5432
python etl.py                       # Scrape + load
pytest tests/ -v                    # 44+ tests
chainlit run app.py                 # UI on :8000
```

Set in `.env`:
```
ANTHROPIC_API_KEY=...
DATABASE_URL=postgresql://...
BASIC_AUTH_USER=otel
BASIC_AUTH_PASS=revenue2026
CHAINLIT_AUTH_SECRET=...
```

---

## Tests

44+ test cases across 4 test files:
- `tests/test_etl.py` — 3+ ETL scenarios
- `tests/test_tools.py` — 20 tool property tests (grain, cancellation, segment shares, pickup, HITL, bonus tools)
- `tests/test_skills.py` — 5+ skill structural tests (thresholds, routing, version pin)
- `tests/test_agent.py` — 4+ agent tests (HITL gating, subagent routing, multi-tool plans)

```bash
pytest tests/ -v
```

---

## Design highlights

See `ARCHITECTURE.md` for the full design choices and justification of those choices.
---


