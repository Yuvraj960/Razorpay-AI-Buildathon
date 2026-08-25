# 02 — System Architecture

## End-to-end pipeline

```text
                         ┌───────────────────────┐
                         │      MERCHANT         │
                         │ CSV / JSON / Catalog  │
                         └───────────┬───────────┘
                                     ▼
                         ┌───────────────────────┐
                         │ Catalog Ingestion     │
                         │ & Normalization       │
                         └───────────┬───────────┘
                                     ▼
                         ┌───────────────────────┐
                         │ AI Catalog Enrichment │
                         │ + Validation          │
                         └───────────┬───────────┘
                                     ▼
                         ┌───────────────────────┐
                         │ Canonical Commerce    │
                         │ Schema (SQLite)       │
                         └───────────┬───────────┘
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              JSON Feed         MCP Tools       JSON-LD
                    └────────────────┼────────────────┘
                                     ▼
                         ┌───────────────────────┐
                         │     AI BUYER          │
                         │ Intent Parser         │
                         │ Product Search        │
                         │ Constraint Solver     │
                         │ Product Ranker        │
                         └───────────┬───────────┘
                                     ▼
                         ┌───────────────────────┐
                         │ Commerce Validator    │
                         │ Price/Stock/Variant/  │
                         │ Shipping/Returns      │
                         └───────────┬───────────┘
                                     ▼
                         ┌───────────────────────┐
                         │ Razorpay Transaction  │
                         │ Orders API / Checkout │
                         │ Payment Links/Webhooks│
                         └───────────┬───────────┘
                                     ▼
                         ┌───────────────────────┐
                         │ Evaluation Engine     │
                         │ Precision/Recall/     │
                         │ Success/Hallucination/│
                         │ Transaction Accuracy  │
                         └───────────────────────┘
```

## The three major components

### A. Catalog Compiler
CSV/JSON in → canonical schema out. Performs schema normalization (`"₹4,999"` → `4999 INR`; `"Available"` → `"in_stock"`; `"black / blk / Black"` → `"black"`), AI enrichment with provenance, and validation. Spec: `03-canonical-schema.md`, `11-synthetic-dataset.md`.

### B. AI Buyer + Deterministic Commerce Engine
LLM converts natural language to a structured constraint object; everything after that is deterministic database work. Spec: `05-ai-buyer-orchestration.md`.

### C. Evaluation Engine
Golden benchmark runner producing the six metrics plus failed-case diagnostics. Spec: `07-evaluation-engine.md`.

## AI architecture (single pipeline, not a swarm)

```text
USER → Intent Parser → Constraint Object → Catalog Search
     → Candidate Set → Constraint Solver → Policy Validator
     → Purchase Planner → Razorpay Executor
```

**LLM handles:** intent understanding, semantic interpretation, explanation, ambiguous NL constraints.
**LLM must NEVER handle:** price, inventory, payment amount, payment status, refund amount, transaction authorization. Those come from deterministic systems.

## Repository layout (target)

```text
razorpay-agent-commerce-lab/
├── frontend/                  # Next.js + TS + Tailwind + shadcn/ui
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── styles/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── catalog.py
│   │   │   ├── buyer.py
│   │   │   ├── checkout.py
│   │   │   ├── evaluation.py
│   │   │   └── webhooks.py
│   │   ├── agents/
│   │   │   ├── buyer.py
│   │   │   ├── enrichment.py
│   │   │   └── evaluator.py
│   │   ├── catalog/
│   │   │   ├── normalizer.py
│   │   │   ├── validator.py
│   │   │   └── schema.py      # canonical Pydantic models — shared foundation
│   │   ├── razorpay/
│   │   │   ├── client.py
│   │   │   ├── orders.py
│   │   │   ├── payment_links.py
│   │   │   └── webhooks.py
│   │   └── scoring/
│   │       ├── readiness.py
│   │       └── metrics.py
│   └── requirements.txt
├── mcp-server/
│   ├── server.py
│   └── tools/
├── data/
│   ├── raw/
│   ├── normalized/
│   └── test_cases/
├── eval/
│   ├── golden_set.json
│   ├── run_eval.py
│   ├── metrics.py
│   └── expected_results.json
├── docs/                      # these spec files
├── docker-compose.yml
├── .env.example
├── README.md
└── Makefile
```

## Service topology

```text
Frontend  → http://localhost:3000
Backend   → http://localhost:8000  (FastAPI, docs at /docs)
MCP       → stdio / wrapped by backend
Database  → SQLite file (MVP). PostgreSQL+pgvector only if pre-existing; never sacrifice transaction correctness for vector search.
```

Search strategy inside the engine: Phase 1 structured filtering (price/stock/category/color/size/brand) → Phase 2 keyword → Phase 3 (optional) semantic similarity. Normalized fields + fuzzy matching is enough for MVP.

## Future architecture (present, don't claim built)

```text
Merchant ──→ Agent Commerce Layer ──→ Discovery/Cart/Checkout ──→ Razorpay
                        ↑
   ChatGPT / Claude / Gemini / Perplexity / Custom Agents

Canonical Commerce Schema
        ├── MCP tools   → AI
        ├── JSON-LD     → Search
        └── UCP Adapter → AI Commerce (future)
```

The canonical schema is the abstraction layer; MCP/JSON-LD/UCP/feeds are adapters over it.
