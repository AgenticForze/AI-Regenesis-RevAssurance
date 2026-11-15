"""Runtime skills: folders under `skills/` with a SKILL.md.

The front matter (name, description, root causes, tools) is always loaded and is cheap. The
body, which holds the investigation procedure, is read only when the skill is selected for a
case. That keeps prompts small: a case carries one procedure, not all of them.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ra.settings import get_settings


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    root_causes: tuple[str, ...]
    tools: tuple[str, ...]
    path: Path

    def body(self) -> str:
        return self.path.read_text().split("---", 2)[2].strip()


@lru_cache(maxsize=1)
def load_all() -> dict[str, Skill]:
    out: dict[str, Skill] = {}
    for md in sorted(get_settings().skills_dir.glob("*/SKILL.md")):
        parts = md.read_text().split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"{md}: missing front matter")
        meta = yaml.safe_load(parts[1])
        out[meta["name"]] = Skill(meta["name"], meta["description"],
                                  tuple(meta.get("root_causes", [])),
                                  tuple(meta.get("tools", [])), md)
    return out


def select(root_cause: str) -> Skill:
    skills = load_all()
    for s in skills.values():
        if root_cause in s.root_causes:
            return s
    return skills["general-investigation"]


def index() -> list[dict]:
    return [{"name": s.name, "description": s.description, "root_causes": list(s.root_causes),
             "tools": list(s.tools)} for s in load_all().values()]
