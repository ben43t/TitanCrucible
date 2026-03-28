import os
import re
import sys
import time

import google.generativeai as genai
from dotenv import load_dotenv

from agent.models import TraceStep
from agent.tools.base import BaseTool

_SYSTEM_PROMPT = """\
You are a research agent for a banking startup. You answer questions by searching \
external sources and synthesizing cited answers.

You operate in a strict ReAct loop. On each turn you MUST emit exactly ONE of the \
following two formats. Every response MUST begin with "Thought:" on the first line.

FORMAT A — Use a tool:
Thought: <your reasoning about what information you still need and which tool to use>
Action: <tool name — must be one of the listed tools>
Action Input: <the search query to send to the tool>

FORMAT B — Deliver the final answer (only when you have enough information):
Thought: <your reasoning about why you have enough information to answer>
Final Answer: <your complete, cited answer>

CRITICAL RULES:
1. You MUST start every response with "Thought:" — never skip it.
2. Never emit both an Action and a Final Answer in the same response.
3. Use at least 2-3 different tools before giving a Final Answer when the question \
is complex or spans multiple topics.
4. In your Final Answer, distinguish between retrieved facts and your own inference. \
Use "According to [source]" for retrieved facts and "Based on this data" for inference.
5. Cite sources inline (e.g. "According to Wikipedia [1]...") and list URLs at the end.
6. If the question is outside your research scope (e.g. restaurant recommendations, \
personal advice, opinions), respond with:
   Thought: This question is outside my research scope.
   Final Answer: This is outside my research scope. I can help with questions about \
economics, finance, banking, academic research, and related factual topics.
7. Do not fabricate data. If a tool returns no results, say so.
8. Do not repeat a tool call with the exact same query — vary the query or try a \
different tool.

MULTI-STEP REASONING STRATEGY:
- After each tool result, reflect on what you learned and what gaps remain.
- Use intermediate results to decide your next tool call. For example, if Wikipedia \
mentions a specific economic indicator, follow up with FRED for the actual data.
- When a question asks about both concepts and research, combine Wikipedia for \
background context with arXiv for academic papers.
- When a question involves economic data, supplement Wikipedia explanations with \
real numbers from FRED to make the answer concrete and current.
- Prefer cross-referencing multiple sources — it produces more complete, verifiable answers.

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


# Patterns for parsing the LLM response — tolerate optional markdown bold (**) wrapping
_THOUGHT_RE = re.compile(r"\*{0,2}Thought:?\*{0,2}\s*(.+?)(?=\n\*{0,2}(?:Action|Final Answer):?\*{0,2}|$)", re.DOTALL)
_ACTION_RE = re.compile(r"\*{0,2}Action:?\*{0,2}\s*(.+)")
_ACTION_INPUT_RE = re.compile(r"\*{0,2}Action Input:?\*{0,2}\s*(.+)")
_FINAL_ANSWER_RE = re.compile(r"\*{0,2}Final Answer:?\*{0,2}\s*(.+)", re.DOTALL)


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

    def think(
        self,
        question: str,
        tools: list[BaseTool],
        history: list[TraceStep],
    ) -> str:
        system_prompt = _build_system_prompt(tools)
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            system_instruction=system_prompt,
        )
        history_text = _build_history_text(history)

        user_content = f"Question: {question}"
        if history_text:
            user_content = f"{user_content}\n\nPrevious steps:\n{history_text}\n\nContinue the ReAct loop."

        response = self._generate_with_retry(model, user_content)
        return response.text

    @staticmethod
    def _generate_with_retry(
        model: genai.GenerativeModel,
        content: str,
        max_retries: int = 5,
    ) -> genai.types.GenerateContentResponse:
        for attempt in range(max_retries):
            try:
                return model.generate_content(
                    contents=[content],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        max_output_tokens=2048,
                    ),
                )
            except Exception as exc:
                if "429" in str(exc) and attempt < max_retries - 1:
                    # Extract retry delay from error message
                    delay_match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc))
                    wait = int(float(delay_match.group(1))) + 5 if delay_match else 60
                    print(f"  [Rate limited, retrying in {wait}s...]", file=sys.stderr)
                    time.sleep(wait)
                else:
                    raise

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
