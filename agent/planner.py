import os
import re
import sys

import google.generativeai as genai
from dotenv import load_dotenv

from agent.models import TraceStep
from agent.tools.base import BaseTool

_SYSTEM_PROMPT = """\
You are a research agent for a banking startup. You answer questions by searching \
external sources and synthesizing cited answers.

You operate in a strict ReAct loop. On each turn, emit exactly ONE of the following:

== Option A: Use a tool ==
Thought: <your reasoning about what to do next>
Action: <tool name — must be one of the listed tools>
Action Input: <the search query to send to the tool>

== Option B: Deliver the final answer ==
Thought: <your reasoning about why you have enough information>
Final Answer: <your complete, cited answer>

RULES:
- ALWAYS start with a Thought line.
- Never emit both an Action and a Final Answer in the same turn.
- When you have gathered enough information, synthesize a Final Answer.
- In your Final Answer, clearly distinguish between facts retrieved from tools \
and your own inference or interpretation. Use phrases like "According to [source]" \
for retrieved facts and "Based on this data, it appears that..." for inference.
- Cite your sources inline (e.g. "According to Wikipedia [1]...") and list source \
URLs at the end.
- If the question is outside your research scope (e.g. restaurant recommendations, \
personal advice, opinions), respond with:
  Final Answer: This is outside my research scope. I can help with questions about \
economics, finance, banking, academic research, and related factual topics.
- Do not fabricate data. If a tool returns no results, say so.
- Do not repeat a tool call with the exact same query — try a different query or tool.

AVAILABLE TOOLS:
{tool_descriptions}
"""


def _build_system_prompt(tools: list[BaseTool]) -> str:
    tool_lines = "\n".join(
        f"- {tool.name}: {tool.description}" for tool in tools
    )
    return _SYSTEM_PROMPT.format(tool_descriptions=tool_lines)


def _build_history_text(history: list[TraceStep]) -> str:
    if not history:
        return ""
    parts: list[str] = []
    for step in history:
        result = step.tool_output
        status = "SUCCESS" if result.success else f"FAILED: {result.error}"
        parts.append(
            f"Thought: {step.thought}\n"
            f"Action: {step.tool_name}\n"
            f"Action Input: {step.tool_input}\n"
            f"Observation: [{status}] {result.content[:2000]}"
        )
    return "\n\n".join(parts)


# Patterns for parsing the LLM response
_THOUGHT_RE = re.compile(r"Thought:\s*(.+?)(?=\n(?:Action:|Final Answer:)|$)", re.DOTALL)
_ACTION_RE = re.compile(r"Action:\s*(.+)")
_ACTION_INPUT_RE = re.compile(r"Action Input:\s*(.+)")
_FINAL_ANSWER_RE = re.compile(r"Final Answer:\s*(.+)", re.DOTALL)


class Planner:
    def __init__(self) -> None:
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print(
                "Error: GEMINI_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com/app/apikey",
                file=sys.stderr,
            )
            sys.exit(1)
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel("gemini-2.5-flash")

    def think(
        self,
        question: str,
        tools: list[BaseTool],
        history: list[TraceStep],
    ) -> str:
        system_prompt = _build_system_prompt(tools)
        history_text = _build_history_text(history)

        user_content = f"Question: {question}"
        if history_text:
            user_content = f"{user_content}\n\nPrevious steps:\n{history_text}\n\nContinue the ReAct loop."

        response = self._model.generate_content(
            contents=[user_content],
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=2048,
            ),
        )
        return response.text

    def parse_response(self, response: str) -> dict[str, str | None]:
        thought_match = _THOUGHT_RE.search(response)
        action_match = _ACTION_RE.search(response)
        action_input_match = _ACTION_INPUT_RE.search(response)
        final_answer_match = _FINAL_ANSWER_RE.search(response)

        return {
            "thought": thought_match.group(1).strip() if thought_match else None,
            "action": action_match.group(1).strip() if action_match else None,
            "action_input": action_input_match.group(1).strip() if action_input_match else None,
            "final_answer": final_answer_match.group(1).strip() if final_answer_match else None,
        }
