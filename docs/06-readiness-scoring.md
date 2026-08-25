# 06 — Readiness Scoring

Owner: Module D. Depends on: `03-canonical-schema.md` validation findings.

## Principle: explicit rubric, not vibes

Never produce an unexplained "AI score = 87". The score is a weighted sum over eight named dimensions with published weights:

| Dimension | Weight |
|---|---:|
| Product completeness | 20 |
| Attribute quality | 15 |
| Variant correctness | 10 |
| Price/inventory freshness | 15 |
| Shipping clarity | 10 |
| Return-policy clarity | 10 |
| Machine-readable interfaces | 10 |
| Transaction readiness | 10 |
| **Total** | **100** |

## Example output format

```text
AGENT COMMERCE READINESS
────────────────────────────
Product completeness       17/20
Attribute quality          11/15
Variant correctness         9/10
Price & inventory          12/15
Shipping clarity             7/10
Return clarity               8/10
Machine readability          8/10
Transaction readiness       10/10
TOTAL                       82/100
```

## Score bands

```text
90–100   Agent Ready
75–89    Ready with Warnings
50–74    Needs Work
0–49     Agent Invisible
```

## Inputs

Deterministic findings from the compiler/validator (missing title/SKU/price/stock/category/variant/shipping/return policy), plus interface-level checks (are MCP tools/JSON-LD/feed exposed?) and transaction-layer checks (can prepare_checkout succeed?).

## Static score is necessary but insufficient

A static score says "your catalog has good data". Simulation says "an AI buyer actually succeeded". Always present both:

```text
DATA QUALITY                BEHAVIORAL PROOF
Catalog score:   82/100     AI Buyer Success:        91%
                            Transaction Success:     88%
                            Hallucination Rate:       2%
                            Constraint Satisfaction: 96%
```

This pairing is the product's core differentiator — see `01-product-spec-mvp.md` (before/after story) and `07-evaluation-engine.md` for how behavioral numbers are produced.

## Acceptance criteria

- [ ] Scoring is fully deterministic and reproducible from DB state
- [ ] Every dimension's sub-score is explainable down to individual findings
- [ ] Dashboard can render per-dimension breakdown bars from one API response
- [ ] Same catalog state always yields the same score
