"""Evaluation harness for the research agent.

Runs each question from questions.json through the agent, scores the result
against expected criteria, and prints a summary table.
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path so we can import the agent package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.core import ResearchAgent
from agent.planner import Planner
from agent.tools.arxiv import ArxivTool
from agent.tools.fred import FredTool
from agent.tools.wikipedia import WikipediaTool

_REFUSAL_PHRASES = [
    "outside my research scope",
    "outside of my research scope",
    "i can't help with",
    "i cannot help with",
    "not within my scope",
    "i'm not able to",
]

_QUESTIONS_PATH = Path(__file__).parent / "questions.json"


def _load_questions() -> list[dict]:
    with open(_QUESTIONS_PATH) as f:
        return json.load(f)


def _check_sources(answer: str, sources: list[str], expected: list[str]) -> bool:
    """Check if the agent used the expected tool types based on source URLs."""
    if not expected:
        return True

    source_text = " ".join(sources).lower() + " " + answer.lower()
    tool_url_markers = {
        "wikipedia": "wikipedia.org",
        "arxiv": "arxiv.org",
        "fred": "fred.stlouisfed.org",
    }

    for tool_name in expected:
        marker = tool_url_markers.get(tool_name, tool_name)
        if marker not in source_text:
            return False
    return True


def _check_keywords(answer: str, must_include: list[str]) -> bool:
    """Check if all required keywords appear in the answer (case-insensitive)."""
    answer_lower = answer.lower()
    return all(kw.lower() in answer_lower for kw in must_include)


def _check_no_keywords(answer: str, must_not_include: list[str]) -> bool:
    """Check that none of the forbidden keywords appear in the answer."""
    if not must_not_include:
        return True
    answer_lower = answer.lower()
    return all(kw.lower() not in answer_lower for kw in must_not_include)


def _check_refusal(answer: str, should_refuse: bool) -> bool:
    """Check if the agent correctly refused (or didn't refuse) the question."""
    answer_lower = answer.lower()
    did_refuse = any(phrase in answer_lower for phrase in _REFUSAL_PHRASES)
    return did_refuse == should_refuse


def run_benchmark() -> None:
    questions = _load_questions()
    print(f"Loaded {len(questions)} benchmark questions.\n")

    tools = [WikipediaTool(), ArxivTool(), FredTool()]
    planner = Planner()
    agent = ResearchAgent(tools, planner, write_trace=False, max_steps=6)

    results: list[dict] = []

    for i, q in enumerate(questions):
        qid = q["id"]
        question = q["question"]
        q_type = q["type"]

        print(f"[{i + 1}/{len(questions)}] Q{qid}: {question[:70]}...")

        try:
            answer, sources = agent.run(question)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append(
                {
                    "id": qid,
                    "type": q_type,
                    "sources_ok": False,
                    "keywords_ok": False,
                    "no_keywords_ok": True,
                    "refusal_ok": False,
                    "error": str(exc),
                }
            )
            continue

        sources_ok = _check_sources(answer, sources, q["expected_sources"])
        keywords_ok = _check_keywords(answer, q["must_include"])
        no_keywords_ok = _check_no_keywords(answer, q["must_not_include"])
        refusal_ok = _check_refusal(answer, q["should_refuse"])

        passed = sources_ok and keywords_ok and no_keywords_ok and refusal_ok
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] sources={sources_ok} keywords={keywords_ok} refusal={refusal_ok}")

        results.append(
            {
                "id": qid,
                "type": q_type,
                "sources_ok": sources_ok,
                "keywords_ok": keywords_ok,
                "no_keywords_ok": no_keywords_ok,
                "refusal_ok": refusal_ok,
                "error": None,
            }
        )

        # Respect rate limits between questions
        time.sleep(2)

    # Print summary table
    print("\n" + "=" * 72)
    print(f"{'ID':>4}  {'Type':<13}  {'Sources':>7}  {'Keywords':>8}  {'Refusal':>7}  {'Result':>6}")
    print("-" * 72)

    total = len(results)
    passed_count = 0

    for r in results:
        if r["error"]:
            row_result = "ERROR"
        else:
            all_ok = r["sources_ok"] and r["keywords_ok"] and r["no_keywords_ok"] and r["refusal_ok"]
            row_result = "PASS" if all_ok else "FAIL"
            if all_ok:
                passed_count += 1

        print(
            f"  {r['id']:>2}  {r['type']:<13}  "
            f"{'OK' if r['sources_ok'] else 'MISS':>7}  "
            f"{'OK' if r['keywords_ok'] else 'MISS':>8}  "
            f"{'OK' if r['refusal_ok'] else 'MISS':>7}  "
            f"{row_result:>6}"
        )

    print("-" * 72)
    pct = (passed_count / total * 100) if total else 0
    print(f"Score: {passed_count}/{total} ({pct:.0f}%)")
    print("=" * 72)


if __name__ == "__main__":
    run_benchmark()
