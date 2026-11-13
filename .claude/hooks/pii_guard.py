"""PreToolUse hook: block writes that contain PII-like patterns.

Claude Code passes the tool call as JSON on stdin. Exit code 2 blocks the call and
returns stderr to Claude so it can fix the content. Also usable in CI with --scan-repo.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

PATTERNS = {
    "card_number": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "us_ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_e164": re.compile(r"\+\d{10,14}\b"),
}
ALLOWED_EMAIL_DOMAINS = ("example.com", "anthropic.com")


def find_pii(text: str) -> list[str]:
    hits = []
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0)
            if name == "email" and value.lower().endswith(ALLOWED_EMAIL_DOMAINS):
                continue
            hits.append(name)
    return sorted(set(hits))


def _content_from_tool_input(payload: dict) -> str:
    tool_input = payload.get("tool_input", {})
    return "\n".join(
        str(tool_input.get(key, "")) for key in ("content", "new_string", "new_str")
    )


def scan_repo() -> int:
    files = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=False
    ).stdout.split()
    bad = []
    for path in files:
        if path.startswith((".claude/hooks/", "tests/")) or not path.endswith(
            (".md", ".yaml", ".yml", ".json", ".py", ".csv", ".feature")
        ):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        hits = find_pii(text)
        if hits:
            bad.append(f"{path}: {', '.join(hits)}")
    if bad:
        print("PII-like content found:\n" + "\n".join(bad), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    if "--scan-repo" in sys.argv:
        return scan_repo()
    payload = json.load(sys.stdin)
    hits = find_pii(_content_from_tool_input(payload))
    if hits:
        print(
            f"Blocked: content looks like it contains PII ({', '.join(hits)}). "
            "Use tokenized IDs or example.com addresses.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
