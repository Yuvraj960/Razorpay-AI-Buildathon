# 14 — Build Roadmap (8–12 Hour MVP)

Execution order with hard exit criteria. Matches the dependency order in `AGENTS.md`. Do not attempt everything — this is a scope-discipline document as much as a schedule.

## Hour 0–1 — Foundation
Create Next.js app, FastAPI app, SQLite, Docker Compose, `.env`, Makefile. Create Razorpay **Test Mode** credentials.
**Exit:** `docker compose up --build` serves :3000 and :8000 from clean clone.

## Hour 1–2 — Catalog
Generate 150 products / 300–500 variants (synthetic, per `11-synthetic-dataset.md`). Build CSV → normalized database. Implement:
```text
GET /products · GET /products/:id · POST /catalog/import
```
**Exit:** messy CSV round-trips into clean canonical rows; normalization unit tests pass.

## Hour 2–3 — Readiness engine
Deterministic checks: missing title/SKU/price/stock/category/variant/shipping/return policy → `readiness_score`.
**Exit:** dashboard renders score + breakdown from live API.

## Hour 3–5 — AI Buyer
```text
user query → LLM structured intent → DB filters → ranking → result
```
No elaborate autonomous agent yet — the buyer must simply work end-to-end with trace events.
**Exit:** sample constrained query returns correct product via deterministic funnel.

## Hour 5–6 — Agent tools
```text
search_products · get_product · check_inventory · get_shipping · get_returns · prepare_checkout
```
As REST endpoints first; MCP wrapper if time permits.
**Exit:** all six callable; prepare_checkout returns verification block without charging.

## Hour 6–7 — Razorpay
`POST /v1/orders` → Standard Checkout → signature verification → payment status → webhook.
**Exit:** AI-selected product → test payment → server-verified, evidence checklist populated.

## Hour 7–8 — Evaluation engine
Write 50 golden tasks; implement precision/recall/constraint-satisfaction/hallucination/transaction accuracy.
**Exit:** `python eval/run_eval.py` prints full table + failed cases.

## Hour 8–10 — UI polish
Three screens only (Dashboard, AI Buyer Lab, Evaluation Lab). Explicitly do NOT build login/multi-tenant/settings/themes/notifications/animations.
**Exit:** all screens render live API data; Buyer Lab streams traces.

## Hour 10–12 — Proof
```bash
docker compose up        # from clean environment
python eval/run_eval.py
```
Then perform and record: AI buyer → discovery → checkout → Razorpay test payment → verification.
**Exit:** demo video captured per `13-demo-and-failure-story.md`.

## Time-boxing rules

- If a phase overruns, cut breadth (fewer categories, fewer tools wrapped in MCP) — never cut the transaction path or the eval runner.
- The three priorities above everything else, in order:
  1. **Real transaction** (actual Test Mode order)
  2. **Automated evaluation** (`run_eval.py` is the most polished part of the repo — it separates "cool demo" from "working AI engineering project")
  3. **Failure recovery** story with regression test
