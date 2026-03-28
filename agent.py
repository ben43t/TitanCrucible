import argparse
import sys

from agent.core import ResearchAgent
from agent.planner import Planner
from agent.tools.arxiv import ArxivTool
from agent.tools.fred import FredTool
from agent.tools.wikipedia import WikipediaTool


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-tool research agent for banking and economics questions.",
    )
    parser.add_argument("question", help="The research question to answer")
    parser.add_argument(
        "--verbose", action="store_true", help="Show full tool outputs during execution"
    )
    parser.add_argument(
        "--no-trace", action="store_true", help="Skip writing a trace file"
    )
    args = parser.parse_args()

    try:
        tools = [WikipediaTool(), ArxivTool(), FredTool()]
        planner = Planner()
        agent = ResearchAgent(tools, planner, verbose=args.verbose, write_trace=not args.no_trace)
        answer, sources = agent.run(args.question)

        print(f"\nAnswer: {answer}")
        if sources:
            print("\nSources:")
            for i, url in enumerate(sources, 1):
                print(f"  [{i}] {url}")
        print()

    except SystemExit:
        raise
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
