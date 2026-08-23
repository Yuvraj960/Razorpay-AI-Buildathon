"""Evaluation API — runs the golden benchmark through the same buyer pipeline
and returns metrics + failed-case detail (docs/07)."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.post("/run")
def run_evaluation(catalog: str = "compiled"):
    """catalog: 'compiled' (default) or 'raw' — powers the before/after story."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    from .. import config
    runner = config.EVAL_DIR / "run_eval.py"
    if not runner.exists():
        return {"error": f"eval runner missing: {runner}"}

    proc = subprocess.run(
        [sys.executable, str(runner), "--catalog", catalog, "--json"],
        capture_output=True, text=True, timeout=600,
        cwd=str(config.BACKEND_DIR),
    )
    if proc.returncode != 0:
        return {"error": "eval_failed", "stderr": proc.stderr[-2000:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "eval_output_unparseable", "stdout": proc.stdout[-2000:]}


@router.get("/latest")
def latest():
    from .. import config
    path = config.NORMALIZED_DIR / "eval-latest.json"
    if not path.exists():
        return {"error": "no evaluation run yet — POST /api/evaluation/run first"}
    import json
    return json.loads(path.read_text(encoding="utf-8"))
