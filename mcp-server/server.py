"""MCP server (docs/05): exposes the six deterministic merchant tools over the
Model Context Protocol stdio transport.

Same service layer as REST (`backend/app/tools/commerce.py`) — one source of
truth, three transports. NO LLM here: these tools are pure database reads and
a verified-quote builder.

Run:  python mcp-server/server.py
Test: echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python mcp-server/server.py

Hand-rolled JSON-RPC 2.0 stdio loop (no SDK dependency) implementing just what
MCP clients need: initialize, tools/list, tools/call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.tools.commerce import TOOL_SPECS, call_tool  # noqa: E402

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "agent-commerce-tools", "version": "0.1.0"}


def _result(req_id, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": payload}


def _error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": message}}


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    req_id = msg.get("id")

    if method == "initialize":
        return _result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "notifications/initialized":
        return None  # notification — no response
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": TOOL_SPECS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            data = call_tool(name, arguments)
        except Exception as e:  # noqa: BLE001 — surface tool errors in-band
            data = {"error": str(e)}
        text = json.dumps(data, ensure_ascii=False, indent=2)
        if isinstance(data, dict) and data.get("error"):
            # tool-level failure is still a valid result for the caller to read
            return _result(req_id, {
                "content": [{"type": "text", "text": text}],
                "isError": True,
            })
        return _result(req_id, {"content": [{"type": "text", "text": text}]})

    if req_id is not None:
        return _error(req_id, -32601, f"method not found: {method}")
    return None


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = _error(None, -32700, "parse error")
        else:
            resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
