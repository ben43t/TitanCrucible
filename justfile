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
