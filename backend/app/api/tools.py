"""REST exposure of the six merchant tools + MCP-style discovery (docs/04)."""
from fastapi import APIRouter
from pydantic import BaseModel

from ..tools import commerce

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolCall(BaseModel):
    name: str
    arguments: dict = {}


@router.get("")
def list_tools():
    """Tool discovery for agents (mirrors the MCP tools/list shape)."""
    return {"tools": commerce.TOOL_SPECS}


@router.post("/call")
def call_tool(req: ToolCall):
    return commerce.call_tool(req.name, req.arguments)
