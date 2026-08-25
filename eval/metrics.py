"""Metric computation over eval task outcomes (docs/07 §metrics).

All metrics are computed from trace outcomes + DB ground truth — no LLM
judgment anywhere, so identical inputs reproduce identical numbers.
"""
from __future__ import annotations

from typing import Any


def empty_metrics() -> dict[str, Any]:
    return {
        "dataset": 0, "passed": 0, "failed": 0,
        "discovery_accuracy": 0.0, "constraint_precision": 0.0,
        "constraint_recall": 0.0, "policy_accuracy": 0.0,
        "variant_accuracy": 0.0, "hallucination_rate": 0.0,
        "checkout_accuracy": 0.0, "task_success": 0.0,
        "failed_cases": [],
    }


class Accumulator:
    def __init__(self) -> None:
        self.n = 0
        self.passed = 0
        self.retrieval = 0
        self.discovery_hits = 0
        self.precision_num = 0
        self.precision_den = 0
        self.recall_num = 0          # satisfiable tasks with >=1 expected found
        self.recall_den = 0          # satisfiable tasks (non-empty expected)
        self.policy_n = 0
        self.policy_pass = 0
        self.variant_n = 0
        self.variant_pass = 0
        self.recommended = 0
        self.hallucinated = 0
        self.checkout_n = 0
        self.checkout_pass = 0

    def add_task(self, outcome: dict) -> None:
        self.n += 1
        if outcome["passed"]:
            self.passed += 1
        kind = outcome.get("kind", "retrieval")
        if kind == "policy":
            self.policy_n += 1
            self.policy_pass += 1 if outcome["passed"] else 0
            return
        if kind == "price_integrity":
            self.checkout_n += 1
            self.checkout_pass += 1 if outcome["passed"] else 0
            return

        self.retrieval += 1
        exp = set(outcome.get("expected_variant_ids") or [])
        ret = outcome.get("returned_variant_ids") or []
        correct = [r for r in ret if r in exp]

        # discovery: correct no-match for impossible, or best match in expected
        if not exp:
            self.discovery_hits += 1 if outcome["status"] == "no_match" else 0
        else:
            self.discovery_hits += 1 if outcome.get("best_variant_id") in exp else 0

        if exp:
            self.recall_den += 1
            self.recall_num += 1 if correct else 0

        self.precision_den += len(ret)
        self.precision_num += len(correct)

        self.recommended += len(ret)
        self.hallucinated += len(ret) - len(correct)

        # variant accuracy: exact variant (color+size) match when constrained
        if outcome.get("variant_check") is not None:
            self.variant_n += 1
            self.variant_pass += 1 if outcome["variant_check"] else 0

        if outcome.get("checkout_check") is not None:
            self.checkout_n += 1
            self.checkout_pass += 1 if outcome["checkout_check"] else 0

    def finalize(self) -> dict:
        pct = lambda a, b: round(100 * a / b, 1) if b else 100.0  # noqa: E731
        return {
            "dataset": self.n,
            "passed": self.passed,
            "failed": self.n - self.passed,
            "discovery_accuracy": pct(self.discovery_hits, self.retrieval),
            "constraint_precision": pct(self.precision_num, self.precision_den),
            "constraint_recall": pct(self.recall_num, self.recall_den),
            "policy_accuracy": pct(self.policy_pass, self.policy_n),
            "variant_accuracy": pct(self.variant_pass, self.variant_n),
            "hallucination_rate": pct(self.hallucinated, self.recommended),
            "checkout_accuracy": pct(self.checkout_pass, self.checkout_n),
            "task_success": pct(self.passed, self.n),
        }


def failed_case(task: dict, outcome: dict) -> dict:
    return {
        "id": task["id"],
        "type": task["type"],
        "query": task["query"],
        "status": outcome["status"],
        "best_variant_id": outcome.get("best_variant_id"),
        "reason": outcome.get("reason", ""),
        "detail": outcome.get("detail", ""),
    }
