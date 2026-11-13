"""Typed agent outputs. Every agent returns JSON validated against these models."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

_TAXONOMY = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "data" / "taxonomy.yaml").read_text()
)
ROOT_CAUSES = set(_TAXONOMY["root_causes"])
ACTIONS = set(_TAXONOMY["actions"])


class TriageResult(BaseModel):
    root_cause: str
    action: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    rationale: str = Field(max_length=600)

    @field_validator("root_cause")
    @classmethod
    def known_root_cause(cls, value: str) -> str:
        if value not in ROOT_CAUSES:
            raise ValueError(f"unknown root cause {value}")
        return value

    @field_validator("action")
    @classmethod
    def known_action(cls, value: str) -> str:
        if value not in ACTIONS:
            raise ValueError(f"unknown action {value}")
        return value
