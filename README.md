# TitanCrucible — Multi-Tool Research Agent

A CLI research agent for a banking startup that accepts natural-language questions,
searches multiple external sources, and returns cited answers. Built with a
hand-rolled ReAct (Reason-Act-Observe) loop — no agent frameworks.

```
python agent.py "What is the Federal Reserve's discount window?"
```

## Architecture

### Why ReAct?

The agent uses the **ReAct** (Reason → Act → Observe) orchestration pattern.
On each step the LLM emits a Thought explaining its reasoning, selects a tool,
and observes the result before deciding the next action. This was chosen over
plan-and-execute because:

- Questions vary widely in complexity and can't always be planned upfront
- The agent can refine its search strategy based on intermediate results
  (e.g., finding a specific FRED series ID mentioned in a Wikipedia article)
- Each step's reasoning is naturally traceable — a reviewer can follow exactly
  why each tool was called
- It handles multi-step synthesis without a separate planning phase

### Component Map

```
agent.py              CLI entrypoint (argparse)
agent/
├── core.py           ResearchAgent — ReAct loop orchestrator
├── planner.py        Planner — Gemini 2.5 Flash wrapper, prompt, response parser
├── state.py          AgentState — step counter, duplicate call guard
├── tracer.py         Tracer — JSON trace file writer
├── models.py         ToolResult, TraceStep (Pydantic)
└── tools/
    ├── base.py       BaseTool abstract class
    ├── wikipedia.py  WikipediaTool — REST + summary API
    ├── arxiv.py      ArxivTool — Atom XML search API
    └── fred.py       FredTool — FRED series search + observations
eval/
├── benchmark.py      Evaluation harness
└── questions.json    15 benchmark questions
tests/                Unit tests (all network calls mocked)
traces/               JSON trace files (one per agent run)
```

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- [just](https://github.com/casey/just) (command runner)

### Install

```bash
git clone <repo-url> && cd TitanCrucible
uv sync
cp .env.example .env
# Edit .env — add your API keys:
#   GEMINI_API_KEY (required) — https://aistudio.google.com/app/apikey
#   FRED_API_KEY   (optional) — https://fred.stlouisfed.org/docs/api/api_key.html
```

### Run

```bash
just run "What are the Basel III capital requirements for banks?"
just demo        # Run all 8 reference questions
just check       # Lint + typecheck + tests
just eval        # Run the full benchmark harness
```

## Tools

| Tool | API | Key Required | What It Does |
|------|-----|:---:|---|
| **WikipediaTool** | Wikipedia REST v1 (search) + Summary API | No | Searches for articles, returns clean summaries with source URLs |
| **ArxivTool** | arXiv Atom API | No | Searches academic papers by relevance, returns top 3 with titles, authors, dates, abstracts |
| **FredTool** | FRED REST API | Yes (free) | Searches economic data series or fetches observations for a known series ID; auto-detects which operation to use |

All tools implement `BaseTool` with a uniform `run(query, force_fail=False) -> ToolResult`
interface. Adding a new tool means creating one file — nothing else changes.

## Multi-Step Reasoning — Tier 2 Evidence

The following comparison demonstrates the value of multi-step ReAct reasoning
over a single-pass approach. Each question was run twice: once with a 2-step
limit (simulating a naive single-tool lookup) and once with the full 6-step
ReAct loop.

### Question 4: "How did the Federal Reserve's monetary policy response to the 2008 financial crisis differ from its response to COVID-19?"

**Single-step (max 2 steps):**
```
[Step 1] Action: wikipedia → "Federal Reserve response 2008 financial crisis"
         Result: Raw article fragment about the subprime crisis response
[Step 2] Action: wikipedia → "Federal Reserve response COVID-19"
         Result: Raw article fragment about COVID-19 government response

Answer: Unable to reach a complete answer. Raw fragments only.
Sources: 2 Wikipedia URLs
```

**Multi-step (full ReAct loop):**
```
[Step 1] Action: wikipedia → "Federal Reserve response 2008 financial crisis"
[Step 2] Action: wikipedia → "Federal Reserve response COVID-19"
[Step 3] Action: wikipedia → "Federal Reserve monetary policy response COVID-19"
         → Found Quantitative Easing article
[Step 4-5] Further Wikipedia refinement for specific Fed actions
[Step 6] Synthesized final answer

Answer: Structured comparison covering:
  - Shared use of emergency authority and QE in both crises
  - Differences in interest rate cuts (immediate near-zero in COVID-19)
  - Scope of asset purchases ("unlimited QE" in COVID-19)
  - Targeted lending programs unique to COVID-19 (MSLP, MLF, PPPLF, PMCCF/SMCCF)
  - Nature of shock (financial system origin vs. external pandemic)
Sources: 4 Wikipedia URLs (subprime crisis, COVID response, Federal Reserve, QE)
```

**What multi-step added:** The agent gathered context from 4 articles, discovered
the QE article through iterative search refinement, and produced a structured
comparison with specific program names and policy differences — none of which
appeared in the initial two fragments.

### Question 6: "Explain the relationship between yield curve inversions and recessions. Are there recent academic papers on this topic?"

**Single-step (max 2 steps):**
```
[Step 1] Action: wikipedia → "yield curve inversion recession"
         Result: Generic "Yield curve" article (definitions only)
[Step 2] Action: wikipedia → "yield curve inversion recession relationship"
         Result: Same generic article again

Answer: Unable to reach a complete answer. Same fragment repeated twice.
Sources: 1 Wikipedia URL
```

**Multi-step (full ReAct loop):**
```
[Step 1-2] Wikipedia → generic "Yield curve" article (insufficient)
[Step 3] Wikipedia → "inverted yield curve recession predictor"
         → Found the specific "Inverted yield curve" article
[Step 4-5] Further refinement for economic implications
[Step 6] Synthesized final answer

Answer: Complete explanation covering:
  - What an inverted yield curve is and why it forms
  - Economic theory (market expectations, monetary policy, credit conditions)
  - Historical track record (predicted every US recession since 1956)
  - Lead time of 6-24 months
  - Referenced academic papers on the topic
Sources: 2 Wikipedia URLs (Yield curve, Inverted yield curve)
```

**What multi-step added:** The agent recovered from an overly general initial
search, found the specific "Inverted yield curve" article on step 3, and
synthesized the economic theory with historical data. The single-step version
returned the same generic definition twice with no analysis.

## Performance Assessment

### Where it does well

- **Factual lookups:** Single-concept questions (discount window, Basel III,
  fractional reserve banking) reliably return accurate, well-cited answers
  from Wikipedia
- **Error handling:** Gracefully handles missing API keys, network failures,
  and disambiguation pages without crashing
- **Traceability:** Every run produces a JSON trace file showing each reasoning
  step, making it easy to debug why the agent made specific choices
- **Out-of-scope refusal:** Correctly identifies and refuses questions outside
  its research domain (restaurant recommendations, investment advice, poetry)

### Where it falls short

- **Cross-tool synthesis is inconsistent:** The model sometimes spends all 6
  steps on Wikipedia variants instead of switching to arXiv or FRED. The prompt
  encourages cross-tool use, but Gemini 2.5 Flash doesn't always follow through.
- **Wikipedia search specificity:** The Wikipedia REST API returns summary-level
  articles. For detailed topics, the agent may get the same generic article
  repeatedly with slightly different queries instead of finding the specific
  sub-article.
- **Rate limiting on free tier:** Gemini's free tier allows only ~5 requests/minute
  and ~20/day, making the full demo and benchmark runs slow. The planner has
  retry logic with backoff, but sustained use requires a paid API key.
- **Thought line parsing:** Gemini 2.5 Flash sometimes omits the "Thought:" prefix
  despite explicit instructions. The regex parser handles this gracefully (defaults
  to "No thought provided"), but the missing thought means the model's internal
  reasoning isn't always captured in traces.

## Limitations

- **No conversation memory:** Each `agent.py` invocation is stateless. The agent
  cannot reference previous questions or build on prior research.
- **Wikipedia summaries only:** The agent reads article summaries, not full
  articles. Complex topics may require details only found deeper in an article.
- **arXiv relevance:** The arXiv API's relevance ranking is basic keyword
  matching. Queries about financial topics often return tangentially related
  papers from other fields.
- **FRED requires domain knowledge:** The FRED tool works best when the LLM
  knows the exact series ID (e.g., UNRATE, GDP). Keyword searches sometimes
  return obscure series instead of the canonical one.
- **Single LLM provider:** Tied to Gemini 2.5 Flash. If the API is down or
  rate-limited, the entire agent is blocked.
- **No caching:** Identical tool calls across runs hit the network every time.

## What I Would Do Differently With More Time

1. **Migrate to `google-genai`:** The `google-generativeai` package is deprecated.
   The new `google-genai` SDK has a cleaner API and better error handling.
2. **Add a tool registry with dynamic dispatch:** Currently tools are hardcoded in
   `agent.py`. A registry pattern would let tools self-register, making it trivial
   to add new data sources.
3. **Implement response caching:** Cache tool results by (tool_name, query) hash
   to avoid redundant network calls across runs and within the same ReAct loop.
4. **Use structured output:** Instead of regex-parsing the LLM's text response,
   use Gemini's structured output mode to get typed JSON with guaranteed fields.
5. **Add a Wikipedia full-article fallback:** When the summary API returns
   insufficient content, fall back to the Action API for the full article extract.
6. **Streaming output:** Stream the LLM's reasoning to stdout in real-time
   instead of waiting for the full response.
7. **Parallel tool execution:** When the LLM identifies multiple independent
   queries, dispatch them concurrently instead of sequentially.
8. **Better evaluation:** The current benchmark scores presence/absence of
   keywords and sources. A more meaningful evaluation would use an LLM-as-judge
   to score answer quality, completeness, and citation accuracy.

## Running Tests

```bash
just test        # Unit tests only
just check       # Lint + typecheck + tests
just eval        # Full benchmark (requires API keys)
```

27 unit tests, all with mocked network calls. No real API requests in the
test suite.

## Observability

Every agent run writes a structured JSON trace to `traces/<timestamp>.json`:

```json
{
  "question": "What is the Federal Reserve's discount window?",
  "steps": [
    {
      "step": 1,
      "thought": "I need to search Wikipedia for information...",
      "tool_name": "wikipedia",
      "tool_input": "Federal Reserve discount window",
      "tool_output": { "success": true, "content": "...", "sources": ["..."] },
      "timestamp": "2026-03-28T03:57:06Z"
    }
  ],
  "final_answer": "The Federal Reserve's discount window is...",
  "total_duration_seconds": 12.345
}
```
