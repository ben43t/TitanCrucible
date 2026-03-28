_DEFAULT_MAX_STEPS = 6


class AgentState:
    def __init__(self, max_steps: int = _DEFAULT_MAX_STEPS) -> None:
        self._max_steps = max_steps
        self._step_count = 0
        self._executed: set[tuple[str, str]] = set()

    @property
    def step_count(self) -> int:
        return self._step_count

    def increment(self) -> int:
        """Advance step counter and return the new step number."""
        self._step_count += 1
        return self._step_count

    def should_continue(self) -> bool:
        return self._step_count < self._max_steps

    def is_duplicate(self, tool_name: str, query: str) -> bool:
        key = (tool_name, query)
        if key in self._executed:
            return True
        self._executed.add(key)
        return False
