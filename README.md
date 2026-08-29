# Agent Commerce Readiness Lab

The QA/compiler/certification layer for AI commerce — **not** a shopping chatbot.
It compiles a messy merchant catalog into machine-readable commerce, scores
agent-readiness on a weighted rubric, simulates an AI buyer against six
deterministic commerce tools (REST + MCP), evaluates behavior on a 50-task golden
benchmark, and proves transactability via Razorpay Test Mode.

## Measured results (seed=42, deterministic, reproducible)

| Metric | Raw catalog | Compiled catalog |
|---|---|---|
| Overall task success (50 tasks) | 76.0% | **100.0%** |
| Hallucination rate | 18.6% | **0.0%** |
| Discovery accuracy | 86.1% | 100.0% |
| Constraint precision | 81.4% | 100.0% |
| Agent-readiness score | 78.8/100 | **89.0/100** ("ready with warnings") |

Every number above is produced by `make eval` / `make eval-raw` — run them yourself.
No metric in this README is hand-written; the eval runner writes `data/normalized/eval-latest.json`.

## One-command startup

```bash
cp .env.example .env
docker compose up --build
# Dashboard  http://localhost:3000   (Dashboard · AI Buyer Lab · Evaluation Lab)
# API        http://localhost:8000/docs
```

## Local development

```bash
make seed      # generate messy catalog + compile + score readiness
make test      # backend pytest suite (13 tests incl. security invariants)
make eval      # golden benchmark, compiled catalog
make eval-raw  # same 50 tasks against the raw export (the 'before' story)
make run       # FastAPI on :8000
cd frontend && npm install && npm run dev   # Next.js on :3000
```

## Architecture

```
data/raw (messy CSV) ──> Catalog Compiler ──> SQLite (canonical)
                              │                     │
                              ▼                     ├── six tools: REST /api/tools + MCP server
                       agent-feed.json              ├── AI Buyer pipeline (intent → constraints → tools)
                       product-schema.jsonld        ├── Razorpay orders/verify/webhooks (server-side HMAC)
                              │                     └── eval/run_eval.py (50-task golden benchmark)
                              ▼
                       Readiness scorer ──> Dashboard UI
```

### The six merchant tools (one service layer, three transports)

`search_products` · `get_product` · `check_availability` · `get_shipping` ·
`get_return_policy` · `prepare_checkout` — exposed over REST (`/api/tools/call`,
typed endpoints) and MCP (`mcp-server/server.py`, stdio JSON-RPC).

## Security model (`docs/09`, enforced in code and tests)

1. **LLM never touches transactional facts.** Price/inventory/amounts come from
   the database. The LLM selects IDs only.
2. **No LLM→SQL.** Intent parses into a Pydantic `IntentConstraints` object; a
   deterministic builder translates it to queries.
3. **AI-enriched attributes carry provenance** (`verified=False`) and never
   override verified merchant facts.
4. **Descriptions are data, not instructions** — adversarial benchmark tasks
   prove injected "discounts" never change quoted prices.
5. **Subunits everywhere**: ₹4,999 → `499900`. Regression-tested.
6. **`RAZORPAY_KEY_SECRET` never leaves the server**; only the key id is public.
7. Order creation re-quotes from the DB server-side; checkout signature is
   recomputed via HMAC-SHA256; webhooks verify the RAW body. Tampered
   signatures are rejected (tested).

## Golden benchmark

50 seeded tasks across five classes: 15 simple, 15 constrained, 10 policy,
5 impossible (must return no-match), 5 adversarial (price-integrity +
instruction-injection). Expectations are locked to the compiled canonical
catalog so raw vs compiled runs are judged against one yardstick.

## Docs

`AGENTS.md` is the build map; `docs/00`–`docs/14` hold the full specs
(vision, MVP scope, architecture, schema, tools/MCP, buyer orchestration,
scoring, evaluation, Razorpay, security, UI, dataset, devops, demo script).
