# OTEL Build Challenge

A LangChain Deep Agents Revenue Manager for the Grand Harbour Hotel, built on reservation data with judgment skills, subagents, and human-in-the-loop gating.

**Submitter:** Lakshman
**Skill pack version:** `otel-rm-v2`

## Live Agent

**URL:** https://otel-agent.onrender.com
**Login credentials:** provided privately via the submission intake.

The deployed UI shows tool calls and skill loads inline so the reviewer can verify routing and progressive disclosure live.

## Health Check

`GET /health` returns the DB fingerprint, dataset revision, row hash, and posted-row count for cross-checking against `etl/LOAD_PROOF.json`.

```
curl https://otel-agent.onrender.com/health -UseBasicParsing | Select-Object -ExpandProperty Content
```

## Architecture

See `ARCHITECTURE.md` for the full system design, agent/subagent structure, and the reasoning behind those choices.

## Run Locally

```
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

## Tests

44+ test cases across 4 test files:

- `tests/test_etl.py` — 3+ ETL scenarios
- `tests/test_tools.py` — 20 tool property tests (grain, cancellation, segment shares, pickup, HITL, bonus tools)
- `tests/test_skills.py` — 5+ skill structural tests (thresholds, routing, version pin)
- `tests/test_agent.py` — 4+ agent tests (HITL gating, subagent routing, multi-tool plans)

```
pytest tests/ -v
```

## Design Highlights

See `ARCHITECTURE.md` for the full design choices and justification of those choices.