from datetime import datetime

from pydantic import BaseModel


class ToolResult(BaseModel):
    tool_name: str
    query: str
    content: str
    sources: list[str]
    success: bool
    error: str | None = None


class TraceStep(BaseModel):
    step: int
    thought: str
    tool_name: str
    tool_input: str
    tool_output: ToolResult
    timestamp: datetime
