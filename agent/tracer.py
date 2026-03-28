import json
import os
import time
from datetime import datetime, timezone

from agent.models import TraceStep


class Tracer:
    def __init__(self, question: str) -> None:
        self._question = question
        self._steps: list[TraceStep] = []
        self._start_time = time.monotonic()

    def add_step(self, step: TraceStep) -> None:
        self._steps.append(step)

    def finalize(self, answer: str) -> str:
        """Write the trace to traces/<timestamp>.json and return the file path."""
        duration = time.monotonic() - self._start_time
        trace = {
            "question": self._question,
            "steps": [json.loads(s.model_dump_json()) for s in self._steps],
            "final_answer": answer,
            "total_duration_seconds": round(duration, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        os.makedirs("traces", exist_ok=True)
        filename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f") + ".json"
        path = os.path.join("traces", filename)

        # Never overwrite — append a counter if the file somehow exists
        base, ext = os.path.splitext(path)
        counter = 1
        while os.path.exists(path):
            path = f"{base}_{counter}{ext}"
            counter += 1

        with open(path, "w") as f:
            json.dump(trace, f, indent=2)

        return path
