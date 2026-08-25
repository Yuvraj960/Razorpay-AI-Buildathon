# 03 — Canonical Commerce Schema & Catalog Compiler

Owner: Module A. Consumers: every other module.

## Problem being solved

Human-readable catalog entries are unusable by AI buyers:

```text
"Premium Running Shoes"
₹4,999
Great shoes for athletes. Available in multiple colours. Fast delivery.
```

An AI buyer needs machine-readable structure:

```json
{
  "sku": "RUN-042-BLK-10",
  "product": "Velocity Pro Running Shoe",
  "category": "running_shoes",
  "brand": "Velocity",
  "gender": "unisex",
  "color": "black",
  "size": "10",
  "terrain": ["road"],
  "cushioning": "high",
  "weight_g": 276,
  "price": 4999,
  "currency": "INR",
  "availability": "in_stock",
  "stock": 14,
  "delivery": { "min_days": 2, "max_days": 4 },
  "return_policy": { "days": 7, "fee": 0 }
}
```

The compiler converts the first form into the second — then the rest of the system asks whether an AI buyer can actually *use* it.

## Compiler responsibilities

### Schema normalization (deterministic, unit-testable)

```text
"₹4,999"            → 4999 INR
"Available"         → "in_stock"
"black / blk / Black" → "black"
```

### AI enrichment (LLM, non-transactional fields only)

Given `"Premium running shoe suitable for athletes and daily runners."`, infer:

```json
{ "use_cases": ["road_running", "daily_training"], "audience": ["runners", "athletes"] }
```

### Validation

Deterministic checks for missing title/SKU/price/stock/category/variant/shipping/return-policy feed `06-readiness-scoring.md`.

## Canonical schema

One internal schema is the source of truth for the entire system:

```text
Merchant
 ├── merchant_id
 ├── name
 ├── currency
 ├── policies
 └── products[]
      ├── product_id
      ├── sku
      ├── title
      ├── description
      ├── category
      ├── brand
      ├── attributes
      ├── variants[]
      │    ├── sku
      │    ├── color
      │    ├── size
      │    └── stock
      ├── price
      ├── availability
      ├── shipping
      └── returns
```

Implement as Pydantic models in `backend/app/catalog/schema.py`. All other modules import from there.

## Provenance on AI-generated attributes — critical design principle

Every enriched field carries provenance:

```json
{
  "field": "terrain", "value": "road",
  "source": "llm_inference", "confidence": 0.91, "verified": false
}
```

```json
{
  "field": "price", "value": 4999,
  "source": "merchant_csv", "confidence": 1.0, "verified": true
}
```

**The agent must never override verified transactional facts with an LLM guess.** This guardrail matters because Razorpay itself emphasizes verified first-party data, merchant-defined controls, and validation over letting agents invent prices or discounts.

## Variants are first-class

"Black size 10" targets a purchasable **variant**, not a product:

```text
Product → ProductGroup
             ├── Variant A (black / 8)
             ├── Variant B (black / 9)
             └── Variant C (black / 10)
```

Never model a product as one giant flat object. This mirrors Google's structured-data guidance (`ProductGroup`, `Product`, `hasVariant`, `variesBy`, per-variant SKU/price/availability). Variant resolution bugs are the project's canonical failure story (see `13-demo-and-failure-story.md`) — build a canonical variant key and a regression test (`test_variant_exact_match`).

## Emitted artifacts

1. **JSON feed** — normalized catalog for agents
2. **JSON-LD** — `generated/product-schema.jsonld` demonstrating standards compliance (proves we're not inventing a proprietary format)
3. **MCP tools** — see `04-agent-tools-and-mcp.md`
4. **Policies as first-class objects** — shipping and returns live as structured objects in the schema, not prose. AI buyers ask "Can I return it?", "How fast is delivery?", "Is it available in my location?" — Shopify/Stripe guidance treats structured policy data as foundational.

## API surface owned by this module

```text
GET  /products
GET  /products/:id
POST /catalog/import
```

## Acceptance criteria

- [ ] CSV with messy values normalizes correctly (subunit-safe money parsing, stock synonyms, color aliases)
- [ ] Every enriched attribute has provenance; verified facts never overwritten by inference
- [ ] Variants modeled per ProductGroup pattern; exact variant match covered by test
- [ ] JSON-LD artifact generated and validates against Google Product structured-data shape
- [ ] Deliberately-broken sample catalog (from `11-synthetic-dataset.md`) produces expected validation findings
