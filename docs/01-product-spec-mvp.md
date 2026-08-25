# 01 — Product Spec & Frozen MVP Scope

This is the scope freeze. Anything not listed here is post-hackathon. Do not expand scope without updating this file.

## The four readiness layers

A merchant is **Agent Ready** only if an AI buyer can perform all four layers against their catalog.

### Layer 1 — Discover

Can the agent find the product?

- Is the SKU identifiable?
- Is the product categorized?
- Are variants represented?
- Is the catalog queryable?
- Are product IDs stable?

### Layer 2 — Understand

Can the agent correctly understand what it found?

- What does it do? Who is it for?
- What attributes matter?
- What does it cost? Is it in stock?
- What are the restrictions?

### Layer 3 — Decide

Can the AI choose correctly under constraints? Given:

> "Find me black running shoes under ₹5,000 for road running, size 10, deliverable to Chandigarh within four days."

The agent must enforce — deterministically, not by semantic similarity:

```text
price <= 5000
color = black
terrain = road
size = 10
delivery <= 4 days
availability = in_stock
```

### Layer 4 — Transact

Can it prepare and execute the purchase?

```text
Product → Variant → Cart → Price verification
       → Razorpay Order → Checkout → Payment → Verification
```

This layer is what elevates the project from "AI catalog tool" to **agent commerce system**.

## The frozen MVP (scope freeze)

### Merchant inputs

```text
catalog.csv
policies.json
shipping.json
```

### Compiler outputs

```text
canonical catalog (DB)
JSON-LD  (generated/product-schema.jsonld)
agent feed (JSON)
MCP tools (6)
```

### Readiness engine

- Deterministic checks: missing title / SKU / price / stock / category / variant / shipping / return policy
- Weighted 0–100 score across 8 dimensions (spec: `06-readiness-scoring.md`)

### AI Buyer

- Natural language → structured constraints via LLM (spec: `05-ai-buyer-orchestration.md`)

### Deterministic commerce engine

- search, filter, variant resolution, stock, price, shipping, returns — all DB-driven

### Razorpay

- Create Order → Standard Checkout → Payment Verification → Webhooks (spec: `08-razorpay-integration.md`)

### Evaluation

- 50 golden tasks → Precision, Recall, Constraint Satisfaction, Hallucination Rate, Transaction Accuracy, Task Success (spec: `07-evaluation-engine.md`)

### Proof artifacts

- `docker compose up` from clean clone
- `python eval/run_eval.py`
- AI Buyer → Razorpay Test Checkout → verified payment, recorded on video

## Design target numbers

Do not fabricate results. Design the system so these are realistically achievable, then publish **actual measured numbers** in the README:

```text
Catalog readiness          >90%
Constraint satisfaction    >95%
Variant accuracy           >98%
Policy accuracy            >95%
Hallucination              <2%  (0% for transaction-critical facts)
Transaction accuracy       100%
Evaluation reproducibility 100%
```

## The killer feature: Agent Commerce Certification

After evaluation passes, generate a publishable artifact:

```text
AGENT COMMERCE CERTIFIED
Score: 96/100
Discovery ✓  Understanding ✓  Constraints ✓  Policies ✓  Transaction ✓
50/50 buyer tests passed
```

Files: `agent-readiness.json` (and optionally `agent-readiness.md`). This is an artifact a merchant could publish.

## The before/after story (non-negotiable deliverable)

The system must be able to show, for the same catalog:

```text
BEFORE compile+enrich          AFTER
Agent Readiness      61        94
Task Success         63%       96%
Constraint Accuracy  78%       99%
Hallucination        7%        1%
```

Message: *"We didn't merely calculate a score. We improved the merchant's ability to transact with AI."* The evaluation engine must therefore support running the golden set against both the raw imported catalog and the compiled/enriched one.

## What NOT to spend time on

Login, multi-tenancy, complex settings, dark/light themes, notification systems, fancy animations, refunds, payouts, settlements, subscriptions, QR codes, invoices, Route, RazorpayX. The evaluator cares whether the system works.
