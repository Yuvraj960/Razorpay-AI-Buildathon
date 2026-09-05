"""Run the Agent Commerce Readiness Lab without Docker.

Usage:
    python run_project.py
    python run_project.py --force-seed
    python run_project.py --skip-install
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
NPM = "npm.cmd" if os.name == "nt" else "npm"


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_checked(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def process_options() -> dict[str, object]:
    options: dict[str, object] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return options


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the backend and frontend locally.")
    parser.add_argument(
        "--force-seed",
        action="store_true",
        help="regenerate and recompile the synthetic catalog before starting",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="do not run npm install when frontend/node_modules is missing",
    )
    args = parser.parse_args()

    if not command_exists(NPM):
        raise SystemExit("npm was not found. Install Node.js 20+ and ensure npm is on PATH.")

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(BACKEND))
    env.setdefault("BACKEND_URL", "http://localhost:8000")
    env.setdefault("NEXT_PUBLIC_BACKEND_URL", "http://localhost:8000")

    print("Seeding catalog...", flush=True)
    seed_command = [sys.executable, "-m", "app.seed"]
    if args.force_seed:
        seed_command.append("--force")
    run_checked(seed_command, BACKEND, env)

    node_modules = FRONTEND / "node_modules"
    if not node_modules.exists():
        if args.skip_install:
            raise SystemExit(
                "frontend/node_modules is missing. Run 'npm install' in frontend "
                "or omit --skip-install."
            )
        print("Installing frontend dependencies...", flush=True)
        run_checked([NPM, "install"], FRONTEND, env)

    processes: list[subprocess.Popen[bytes]] = []
    try:
        print("Starting backend at http://localhost:8000", flush=True)
        processes.append(
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
                cwd=BACKEND,
                env=env,
                **process_options(),
            )
        )
        print("Starting frontend at http://localhost:3000", flush=True)
        processes.append(
            subprocess.Popen(
                [NPM, "run", "dev"],
                cwd=FRONTEND,
                env=env,
                **process_options(),
            )
        )
        print("Press Ctrl+C to stop both services.", flush=True)

        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    raise SystemExit(f"A service exited unexpectedly with code {return_code}.")
            threading.Event().wait(1)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in reversed(processes):
            stop_process(process)


if __name__ == "__main__":
    raise SystemExit(main())