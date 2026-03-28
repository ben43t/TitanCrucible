# CLAUDE.md — Research Agent Project Rules

This file serves two purposes: it instructs Claude on how to build this project,
and it documents the key architectural decisions for anyone reviewing the codebase.
Every decision here was made deliberately before writing any code.

---

## 1. AI INTERACTION LOGGING

All AI-assisted work is logged in `prompt-log.md` at the project root. Claude is
instructed to append every prompt and a summary of its response to this file
autonomously on each turn, before writing any code. This creates a complete audit
trail of how the agent was designed and built.

If `prompt-log.md` does not exist, create it. Do not ask for permission — just do it.

---

## 2. PROJECT CONTEXT

This is a multi-tool research agent for a banking startup. The agent accepts a
natural language question, decides which tools to use, executes searches across
multiple sources, and returns a cited answer.

**Deliverable:** a CLI tool (`python agent.py "question"`) that prints a cited
answer to stdout.

**Tools integrated:**
- Wikipedia (REST + Action API) — general knowledge and definitions
- arXiv API — academic papers and research
- FRED API (Federal Reserve Economic Data) — economic data series

---

## 3. ARCHITECTURE

**Orchestration pattern: ReAct (Reason → Act → Observe)**

ReAct was chosen over plan-and-execute because:
- Questions vary widely in complexity and can't always be planned upfront
- The agent needs to refine its search strategy based on intermediate results
- Each step's reasoning is naturally traceable — a reviewer can follow exactly
  why each tool was called
- It handles multi-step synthesis (e.g. fetch Wikipedia, then decide to search
  arXiv based on what Wikipedia returned) without a separate planning phase

Do not switch to a different orchestration pattern without discussion.

**No agent frameworks.** No LangChain, LlamaIndex, or similar. The ReAct loop
is hand-rolled. This keeps the codebase readable to a reviewer unfamiliar with
framework abstractions, and demonstrates understanding of the underlying pattern.

**Tool interface:** Every tool implements the abstract `BaseTool` class in
`agent/tools/base.py`. Adding a new tool means creating one new file — nothing
else in the codebase changes. This is the primary extensibility mechanism.

---

## 4. TOOLCHAIN

These choices reflect current Python best practices and minimize reviewer friction:

| Tool | Purpose | Why |
|------|---------|-----|
| **uv** | Package manager + venv | Faster than pip; single-command setup for reviewer |
| **ruff** | Linter + formatter | Replaces black/flake8/isort; zero config |
| **ty** | Type checker | Pairs with ruff; catches interface mismatches early |
| **pytest** | Testing | Standard; needed for tool unit tests and eval harness |
| **pydantic** | Data models | Used for `ToolResult` and `TraceStep` only (see section 5) |

**Runtime:** Python 3.12+

**LLM:** Gemini 2.5 Flash (`gemini-2.5-flash`) via `google-generativeai`. This is
the current free-tier stable model as of March 2026. Do not use 1.5 Flash (outdated)
or any 3.x model (paid preview only). The reviewer must be able to run this without
spending money.

**CLI:** `argparse` only. No Typer, no Click — the interface is a single argument.

---

## 5. PYDANTIC USAGE

Pydantic is used in exactly two places:

**`ToolResult`** — ensures every tool returns a consistent shape regardless of
which tool ran or whether it errored:

```python
class ToolResult(BaseModel):
    tool_name: str
    query: str
    content: str
    sources: list[str]
    success: bool
    error: str | None = None
```

**`TraceStep`** — each ReAct step, serialized to JSON via `.model_dump_json()`:

```python
class TraceStep(BaseModel):
    step: int
    thought: str
    tool_name: str
    tool_input: str
    tool_output: ToolResult
    timestamp: datetime
```

Do not use Pydantic for LLM output parsing (Thought/Action/Final Answer) — that
is string manipulation. Do not model other parts of the codebase with Pydantic
without discussion.

---

## 6. CODE STYLE

- Ruff handles all formatting — do not manually enforce line length, import order,
  or quote style.
- Type-annotate all public functions and class methods.
- No `Any` types without a comment explaining why.
- Prefer explicit over clever. This codebase will be read by a reviewer who hasn't
  seen it before.

---

## 7. OBSERVABILITY & TRACING

Every agent run writes a structured JSON trace to `traces/<timestamp>.json`.
Traces are append-only — never deleted or overwritten between runs.

Each trace must include:
- The original question
- Each ReAct step: tool selected, input query, raw tool output, LLM reasoning
- The final synthesized answer

This is a first-class requirement, not an afterthought. A reviewer should be able
to open any trace file and understand exactly why the agent made each decision.

---

## 8. SECRETS & CONFIGURATION

- All API keys stored in `.env`. Never hardcoded.
- `.env` is gitignored. A `.env.example` with placeholder values is committed.
- The FRED API key is the only required external key (free, instant signup at
  fred.stlouisfed.org). If missing, the agent skips FRED tools and warns the user
  — it does not crash.
- The Gemini API key is required. If missing, the agent exits with a clear error.

---

## 9. TESTING

- Tool wrappers have unit tests with all network calls mocked (`pytest-mock` or
  `responses` library).
- The eval harness (`eval/benchmark.py`) is separate from unit tests — do not mix.
- Every tool accepts a `force_fail: bool = False` parameter for synthetic failure
  testing, enabling circuit breaker and fallback logic to be exercised in tests.

---

## 10. JUSTFILE

The `justfile` is the single source of truth for how to operate the project.
A reviewer should never need to read the code to figure out how to run something.

```just
# List available recipes
default:
    just --list

# Install dependencies
install:
    uv sync

# Run the agent
run question:
    uv run python agent.py "{{question}}"

# Lint and format check
lint:
    uv run ruff check .
    uv run ruff format --check .

# Auto-fix lint and format
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# Type check
typecheck:
    uv run ty check

# Run tests
test:
    uv run pytest tests/ -v

# Run full eval benchmark
eval:
    uv run python eval/benchmark.py

# Run all checks (lint + typecheck + tests)
check: lint typecheck test

# Run agent against all 8 reference questions
demo:
    uv run python agent.py "What is the Federal Reserve's discount window and how does it work?"
    uv run python agent.py "What are the Basel III capital requirements for banks?"
    uv run python agent.py "What recent academic research exists on using machine learning for credit risk assessment?"
    uv run python agent.py "How did the Federal Reserve's monetary policy response to the 2008 financial crisis differ from its response to COVID-19?"
    uv run python agent.py "What is the current US unemployment rate and how has it changed over the past year?"
    uv run python agent.py "Explain the relationship between yield curve inversions and recessions. Are there recent academic papers on this topic?"
    uv run python agent.py "What is the best restaurant in New York City?"
    uv run python agent.py "What are the implications of quantum computing for banking encryption?"

# Clean traces and cache
clean:
    rm -rf traces/*.json __pycache__ .ruff_cache .pytest_cache
```

---

## 11. COMMIT CHECKPOINTS

The commit history is part of the project evaluation. Each commit must represent
one logical, reviewable unit of work. After completing each checkpoint, output the
exact git commit message to use before proceeding to the next step. Never bundle
two checkpoints into one commit.

| # | Checkpoint | Commit message |
|---|-----------|---------------|
| 1 | Project scaffold (pyproject.toml, justfile, .env.example, directory structure) | `feat: scaffold project structure and toolchain` |
| 2 | BaseTool abstract interface + Pydantic models | `feat: add BaseTool interface and ToolResult/TraceStep models` |
| 3 | Wikipedia tool wrapper | `feat: implement Wikipedia tool wrapper` |
| 4 | arXiv tool wrapper | `feat: implement arXiv tool wrapper` |
| 5 | FRED tool wrapper | `feat: implement FRED tool wrapper` |
| 6 | Tracer + state management | `feat: add JSON tracer and agent state management` |
| 7 | ReAct core loop | `feat: implement ReAct orchestration loop` |
| 8 | CLI entrypoint — first working end-to-end run | `feat: wire up CLI entrypoint and end-to-end agent run` |
| 9 | Multi-step reasoning and loop guard | `feat: add multi-step reasoning with deduplication guard` |
| 10 | Unit tests with mocked network calls | `test: add unit tests for all tool wrappers` |
| 11 | Eval harness and benchmark questions | `feat: add evaluation harness and benchmark question set` |
| 12 | README + prompt-log.md | `docs: add README and finalize prompt log` |