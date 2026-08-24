"""Seed entrypoint: generate synthetic raw data + run the compiler pipeline.

Usage:  cd backend && python -m app.seed [--force]
Idempotent: skips when DB already has products unless --force.
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="regenerate even if already seeded")
    args = parser.parse_args()

    from . import db
    from .catalog.generator import generate
    from .catalog.importer import run_compiler

    if db.is_seeded() and not args.force:
        print("already seeded — use --force to regenerate")
        return 0

    if args.force:
        db.reset_db()

    stats = generate()
    print(f"generated {stats['products']} products / {stats['rows']} rows")
    result = run_compiler()
    print(f"compiled {result['products']} products / {result['variants']} variants "
          f"| readiness findings: {result['critical']} critical, {result['warnings']} warnings")

    from .scoring.readiness import compute_readiness
    score = compute_readiness()
    print(f"readiness: {score['total']}/100 ({score['band']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
