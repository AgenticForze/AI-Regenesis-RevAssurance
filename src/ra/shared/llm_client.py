"""Single entry point for Bedrock calls: routing, budgets, request metadata, tracing.

Construction task T4.01 wires this to the Bedrock Converse API with application inference
profiles from the AppConfig routing table. Agents must not call boto3 bedrock-runtime directly.
"""
from __future__ import annotations

from dataclasses import dataclass

from ra.shared.budgets import CaseBudget


@dataclass
class Route:
    step: str
    inference_profile_arn: str
    max_output_tokens: int
    fallback_arn: str | None = None


class LlmClient:
    def __init__(self, routing: dict[str, Route], bedrock_client=None):
        self.routing = routing
        self.bedrock = bedrock_client  # boto3.client("bedrock-runtime") in deployed code

    def converse(self, *, step: str, case_id: str, release: str, system: list, messages: list,
                 budget: CaseBudget, est_input_tokens: int) -> dict:
        route = self.routing[step]
        budget.reserve(est_input_tokens, route.max_output_tokens)
        if self.bedrock is None:
            raise RuntimeError("Bedrock client not configured (see task T4.01)")
        response = self.bedrock.converse(
            modelId=route.inference_profile_arn,
            system=system,
            messages=messages,
            inferenceConfig={"maxTokens": route.max_output_tokens},
            requestMetadata={"case_id": case_id, "step": step, "release": release},
        )
        usage = response.get("usage", {})
        budget.record(usage.get("inputTokens", 0), usage.get("outputTokens", 0))
        return response
