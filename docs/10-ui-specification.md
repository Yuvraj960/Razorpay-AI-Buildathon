# 10 — UI Specification (Three Screens)

Owner: Module G. Stack: Next.js + React + TypeScript + Tailwind CSS + shadcn/ui.

Deliberately minimal chrome: **no login, no multi-tenant settings, no theme switcher, no notification system, no fancy animations.** Three screens, clean and legible.

---

## Screen 1 — Merchant Dashboard

Header:

```text
Agent Commerce Readiness
```

Hero block:

```text
94
AGENT READY
```

Stat strip:

```text
Products 248 · Variants 613 · Agent tasks tested 50
Successful 48 · Razorpay transactions 3
```

### Readiness breakdown (per-dimension cards)

```text
PRODUCT DATA  ██████████████████░░ 92%
VARIANTS      ███████████████████░ 96%
POLICIES      █████████───────░░░░ 82%
INVENTORY     ███████████████████░ 97%
TRANSACTION   ████████████████████ 100%

3 Critical Issues · 7 Warnings · 238 Passed
```

Data source: readiness API from `06-readiness-scoring.md` (one response must drive the whole screen). Clicking a dimension lists its underlying findings.

---

## Screen 2 — AI Buyer Lab (the "wow" screen)

Top:

```text
AI BUYER LAB
Give the buyer a goal.
```

Input example (prefill for demo):

> Find black running shoes under ₹5,000, size 10, suitable for road running and deliverable to Chandigarh within four days.

### Live trace panel (streamed from buyer trace events)

```text
10:31:04  Parse intent
10:31:04  Extract constraints
10:31:05  Search catalog        → 17 candidates
10:31:05  Apply price constraint → 9 candidates
10:31:05  Apply size constraint  → 4 candidates
10:31:06  Verify inventory       → 3 candidates
10:31:06  Verify delivery        → 1 candidate
10:31:06  Prepare checkout
```

### Result card

```text
BEST MATCH
Velocity Pro Running Shoe
₹4,999 · Black · Size 10 · Road · In stock
Delivery: 2–4 days
Return: 7 days
Confidence: 97%
```

Actions:

```text
[ Buy with Razorpay ]
[ Generate Payment Link ]   ← fallback path per 08-razorpay-integration.md
```

On purchase completion, show the **Transaction Evidence** checklist from `09-security-and-audit.md`.

---

## Screen 3 — Evaluation Lab

Summary panel:

```text
AGENT EVALUATION — 50 scenarios
✓ 48 passed   ✕ 2 failed

Precision             96.4%
Recall                 94.8%
Constraint accuracy    98.1%
Hallucination           0.8%
Transaction accuracy  100%
```

Plus the before/after comparison table (`07-evaluation-engine.md`).

### Failed-test drill-down

Clicking a case opens full transparency:

```text
FAILED TEST #37
User:    "Black shoe size 10."
Agent:   Selected SKU SHOE-BLK-9
Expected: SHOE-BLK-10
Reason:  Variant mapping error.
Fix:     Variant resolver updated.
```

And passing impossible-task cases render as explicit passes:

```text
#37  User: "Find a red laptop under ₹2,000."
     Agent: No product found.   Expected: No product found.
     Status: ✓ PASS
```

Data source: `python eval/run_eval.py` output persisted via `backend/app/api/evaluation.py`; clicking re-runs single cases where feasible.

---

## Acceptance criteria

- [ ] All three screens render from real backend APIs (no hard-coded demo data)
- [ ] Buyer Lab streams live trace events during a run
- [ ] Evaluation Lab drill-down shows reason + fix per failed case
- [ ] Transaction Evidence checklist appears after checkout flow
- [ ] Responsive enough to record cleanly at 1080p for the demo video
