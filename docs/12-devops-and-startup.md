# 12 — DevOps, Startup & README Contract

Owner: Module H. **One-command startup is an explicitly graded deliverable** ("a repo that actually runs").

## The entire setup experience

```bash
git clone ...
cd razorpay-agent-commerce-lab
cp .env.example .env
docker compose up --build
```

Then:

```bash
make seed    # load synthetic catalog through normalizer into DB
make eval    # python eval/run_eval.py
```

Service endpoints after startup:

```text
Frontend → http://localhost:3000
Backend  → http://localhost:8000
API docs → http://localhost:8000/docs
```

## `.env.example` contract

```text
LLM_PROVIDER=openai          # provider-configurable AI — never hard-code a model
LLM_MODEL=...
RAZORPAY_KEY_ID=...          # safe client-side where needed
RAZORPAY_KEY_SECRET=...      # server only — NEVER expose to frontend
RAZORPAY_WEBHOOK_SECRET=...
DATABASE_URL=sqlite:///./data/app.db
```

Backend Python requirement: **3.12+** (Razorpay SDK prerequisite).

## Makefile targets

```text
seed   — import data/raw → normalize → SQLite
eval   — run golden benchmark
run    — local non-docker dev startup
test   — backend test suite (subunit conversion, variant exact match, webhook signature at minimum)
```

## docker-compose.yml

Services: `frontend` (3000), `backend` (8000), shared volume for SQLite file. MCP server runs inside/alongside backend. Must come up clean on a fresh clone with only `.env` copied.

## Test suite minimums (regression-proofing the demo)

```text
test_razorpay_amount_conversion   # ₹4999→499900, ₹999→99900, ₹49.50→4950
test_variant_exact_match          # size "10" ≠ size "9"; canonical variant key
test_webhook_signature            # HMAC-SHA256 over raw body
test_impossible_query_no_hallucination
test_adversarial_instruction_ignored
```

## README structure (submission contract)

Not a wall of text. Start with:

```text
# Agent Commerce Readiness Lab
Make merchants discoverable, understandable, and transactable by AI buyers.
[Demo] [Architecture] [Evaluation] [Razorpay Integration]
```

Sections, in order:

```text
Problem · Solution · Architecture · Quick Start
Razorpay Integration · AI Buyer · Evaluation · Results
Failure Cases · Limitations
```

**Results must be actual measured numbers** from running the benchmark — never aspirational targets presented as results.

## Pre-submission checklist

- [ ] `docker compose up --build` verified from a clean environment
- [ ] `make seed` and `python eval/run_eval.py` succeed on fresh clone
- [ ] Full demo flow recorded (see `13-demo-and-failure-story.md`)
- [ ] All five regression tests green
