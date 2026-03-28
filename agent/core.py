import sys
from datetime import datetime, timezone

from agent.models import ToolResult, TraceStep
from agent.planner import Planner
from agent.state import AgentState
from agent.tools.base import BaseTool
from agent.tracer import Tracer


class ResearchAgent:
    def __init__(self, tools: list[BaseTool], planner: Planner) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._planner = planner

    def run(self, question: str) -> str:
        state = AgentState()
        tracer = Tracer(question)
        history: list[TraceStep] = []

        print(f"\n{'='*60}")
        print(f"Question: {question}")
        print(f"{'='*60}\n")

        while state.should_continue():
            step_num = state.increment()

            # Get next action from LLM
            try:
                raw_response = self._planner.think(
                    question, list(self._tools.values()), history
                )
            except Exception as exc:
                print(f"\n[Step {step_num}] Planner error: {exc}", file=sys.stderr)
                break

            parsed = self._planner.parse_response(raw_response)
            thought = parsed["thought"] or "No thought provided"
            print(f"[Step {step_num}] Thought: {thought}")

            # Check for final answer
            if parsed["final_answer"]:
                print(f"\nFinal Answer: {parsed['final_answer']}\n")
                tracer.finalize(parsed["final_answer"])
                return parsed["final_answer"]

            action = parsed["action"]
            action_input = parsed["action_input"]

            if not action or not action_input:
                print(f"[Step {step_num}] Malformed response — no action or input found.")
                # Record step and continue so the LLM can recover
                result = ToolResult(
                    tool_name="none",
                    query="",
                    content="",
                    sources=[],
                    success=False,
                    error="Malformed LLM response: missing Action or Action Input",
                )
                step = TraceStep(
                    step=step_num,
                    thought=thought,
                    tool_name="none",
                    tool_input="",
                    tool_output=result,
                    timestamp=datetime.now(timezone.utc),
                )
                history.append(step)
                tracer.add_step(step)
                continue

            print(f"[Step {step_num}] Action: {action}")
            print(f"[Step {step_num}] Action Input: {action_input}")

            # Check for duplicate calls
            if state.is_duplicate(action, action_input):
                print(f"[Step {step_num}] Skipping duplicate call: {action}({action_input})")
                result = ToolResult(
                    tool_name=action,
                    query=action_input,
                    content="",
                    sources=[],
                    success=False,
                    error=f"Duplicate call skipped: {action}({action_input})",
                )
            else:
                result = self._dispatch(action, action_input)

            status = "OK" if result.success else f"FAILED: {result.error}"
            print(f"[Step {step_num}] Result: [{status}] {result.content[:200]}")

            step = TraceStep(
                step=step_num,
                thought=thought,
                tool_name=action,
                tool_input=action_input,
                tool_output=result,
                timestamp=datetime.now(timezone.utc),
            )
            history.append(step)
            tracer.add_step(step)

        # Max iterations reached without a final answer
        fallback = (
            "I was unable to reach a complete answer within the allowed number of "
            "reasoning steps. Here is what I found so far:\n\n"
            + "\n".join(
                f"- [{s.tool_name}] {s.tool_output.content[:300]}"
                for s in history
                if s.tool_output.success
            )
        )
        print(f"\n{fallback}\n")
        tracer.finalize(fallback)
        return fallback

    def _dispatch(self, tool_name: str, query: str) -> ToolResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(
                tool_name=tool_name,
                query=query,
                content="",
                sources=[],
                success=False,
                error=f"Unknown tool: {tool_name}. Available: {', '.join(self._tools)}",
            )
        try:
            return tool.run(query)
        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                query=query,
                content="",
                sources=[],
                success=False,
                error=f"Tool execution failed: {exc}",
            )
