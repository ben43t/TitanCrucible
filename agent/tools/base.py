from abc import ABC, abstractmethod

from agent.models import ToolResult


class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def run(self, query: str, *, force_fail: bool = False) -> ToolResult: ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"
