# 13 — Demo Script & Failure Story

The hackathon requires three proofs: **(1)** a repository that actually runs, **(2)** a five-minute video of it working, **(3)** what broke at 2 AM and how you recovered.

## Five-minute video script

### 0:00–0:30 — Problem
> "AI agents are becoming buyers, but most merchant catalogs were designed for humans. Agent Commerce Readiness Lab converts a merchant catalog into an executable AI-commerce interface and then proves that an AI buyer can actually use it."

### 0:30–1:15 — Upload catalog
Show `300 products / 617 variants` imported. Readiness lands at:

```text
Agent Readiness: 62/100 · 12 critical issues · 31 warnings
```

### 1:15–2:00 — Fix
Click "Enrich catalog". Show missing attributes detected (terrain, material, audience, delivery, return policy); AI generates structured fields with provenance. Score moves **62 → 93** on screen.

### 2:00–3:00 — AI Buyer
Enter: *"Find black road-running shoes under ₹5,000, size 10, deliverable to Chandigarh within four days."* Show the live agent trace → product card → click **Buy with Razorpay**.

### 3:00–3:45 — Actual transaction
Razorpay Order created → Test Checkout opens → simulated payment completes → show:

```text
Payment captured ✓   Order verified ✓   Signature verified ✓
```

(Razorpay Test Mode uses simulated transactions — appropriate and safe for the demo.)

### 3:45–4:30 — Evaluation
Run `python eval/run_eval.py` live:

```text
50 tasks · 48 passed · 2 failed
Task Success 96% · Precision 97% · Recall 95%
Hallucination 0% · Transaction 100%
```

### 4:30–5:00 — The failure story
Show a real git commit/issue:

```text
FAILURE #1
Variant resolver selected BLACK-SIZE-9 instead of BLACK-SIZE-10.
Root cause: variant normalization treated numeric size as string.
Fix: canonical variant key.
Regression test added: test_variant_exact_match()
Before: 48/50 → After: 50/50
```

---

## The "what broke at 2 AM" playbook

**Do not fake a dramatic story — and do not invent a bug you never hit.** Two honest options:

1. **Best:** a real failure actually encountered during the build, with its genuine commit history, root cause, fix, and added regression test.
2. **Acceptable:** one *controlled* bug introduced deliberately before recording, which the test suite catches on camera:

```text
Bug: ₹4,999 became 4999 instead of 499900

FAILED: test_razorpay_amount_conversion
Fix: Money type / subunit conversion
Regression:
  ✓ ₹4999  → 499900
  ✓ ₹999   → 99900
  ✓ ₹49.50 → 4950
```

Either way, present the full arc:

```text
Failure → Detection → Root cause → Fix → Regression test → Improved score
```

This arc directly matches the proof requirement and demonstrates engineering maturity. Keep every real failure logged as it happens during the build (commit messages + a running `docs/failure-log.md` if useful) so the story is authentic at recording time.

## Recording checklist

- [ ] Clean-environment run recorded first (`docker compose up` from scratch)
- [ ] Live eval run shown, not pre-baked output
- [ ] Real Razorpay Test Mode transaction completed on camera
- [ ] Failure story backed by actual commit/test visible on screen
- [ ] Total ≤ 5 minutes
