# 11 — Synthetic Dataset & Deliberate Data Problems

Owner: Module A (generator) — consumed by readiness engine and eval suite.

## Core rule

**Do NOT use a giant external dataset.** It makes the demo harder to understand and introduces licensing/data-quality issues. Use a **synthetic but realistic Indian merchant catalog**. What matters is not product count but: *can the agent correctly transact against them?*

Public ecommerce datasets are acceptable for offline experimentation only; the submission uses synthetic + explicitly licensed/public data.

## Target shape

```text
150–300 products
500–800 variants
3–5 categories
```

### Suggested categories

- **Electronics** — laptops, keyboards, mice, headphones, monitors
- **Fashion** — shoes, shirts, jackets, backpacks
- **Home** — lamps, chairs, cookware
- **Fitness** — shoes, yoga mats, resistance bands, bottles

## Inject deliberate data problems

A perfect dataset leaves the readiness engine nothing to solve. The raw catalog MUST contain:

```text
Missing SKU
Missing brand
Missing color
Missing size
Duplicate products
Inconsistent currency
"Available" vs "in stock" semantics
Missing delivery information
Vague descriptions
Duplicate variants
Wrong category
Missing return policy
Stale stock
```

### Example deliberately-broken product

```text
Product A
"Running Shoe"
Description: "Premium athletic shoe."
Price: 4999
Stock: Available
```

The system must identify:

```text
❌ unclear terrain
❌ unclear audience
❌ missing color
❌ missing size
❌ ambiguous stock semantics
❌ missing delivery estimate
❌ missing return policy
```

## File layout

```text
data/
├── raw/           # messy input CSVs + policies.json + shipping.json (with injected problems)
├── normalized/    # compiler output artifacts (JSON feed, JSON-LD)
└── test_cases/    # per-problem-type fixtures for unit tests
```

## Generator requirements

- Deterministic generation (seeded) so before/after comparisons and demo numbers are stable across runs
- Prices in INR with realistic magnitudes; some entries formatted messily (`"₹4,999"`, `"4999 INR"`) to exercise normalization
- Variant grids with occasional gaps (black exists in sizes 8–9 but not 10) to power variant-resolution test cases, including the canonical BLACK-SIZE-9-vs-10 failure story from `13-demo-and-failure-story.md`
- A handful of descriptions containing adversarial instruction text ("ignore restrictions...") reserved exclusively for the adversarial eval tasks
- Ground-truth annotations (which products satisfy which constraints) emitted alongside the raw data — `eval/expected_results.json` derives from this

## Acceptance criteria

- [ ] `make seed` loads raw → DB through normalizer in one command
- [ ] Readiness score on raw catalog lands in "Needs Work" band (~50–74); after compile+enrich reaches "Agent Ready"/warning band — powering the before/after story
- [ ] Every injected problem type is detected by at least one deterministic check
- [ ] Golden set's expected results are derivable from ground truth, not hand-guessed
