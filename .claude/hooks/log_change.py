"""PostToolUse hook: append an audit line for every file the agent writes."""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input", {})
    now = dt.datetime.now(dt.UTC)
    record = {
        "ts": now.isoformat(),
        "session_id": payload.get("session_id"),
        "tool": payload.get("tool_name"),
        "path": tool_input.get("file_path"),
        "user": os.environ.get("USER", "unknown"),
    }
    log_dir = pathlib.Path("logs/agent-runs")
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{now.date().isoformat()}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
