"""Amazon Bedrock back end (Converse API).

Model IDs or application inference profile ARNs come from RA_BEDROCK_TRIAGE_MODEL and
RA_BEDROCK_REASON_MODEL. The system prompt is marked as a cache point so repeated calls reuse it.
This path needs AWS credentials and has not been exercised by the repo's offline test suite.
"""
from __future__ import annotations

import json
from typing import Any

from ra.llm import MAX_OUTPUT
from ra.settings import get_settings


class BedrockClient:
    name = "aws.bedrock"

    def __init__(self, client=None):
        if client is None:
            import boto3
            client = boto3.client("bedrock-runtime")
        self.client = client
        s = get_settings()
        self.models = {"triage": s.bedrock_triage_model, "investigate": s.bedrock_reason_model}
        missing = [k for k, v in self.models.items() if not v]
        if missing:
            raise RuntimeError(f"set the Bedrock model for: {missing}")

    def complete_json(self, step: str, system: str, payload: dict[str, Any]):
        resp = self.client.converse(
            modelId=self.models[step],
            system=[{"text": system}, {"cachePoint": {"type": "default"}}],
            messages=[{"role": "user", "content": [{"text": json.dumps(payload, default=str)}]}],
            inferenceConfig={"maxTokens": MAX_OUTPUT[step], "temperature": 0},
            requestMetadata={"step": step, "release": get_settings().release},
        )
        text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"])
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < 0:
            raise ValueError("model did not return JSON")
        usage = resp.get("usage", {})
        return (json.loads(text[start:end + 1]), usage.get("inputTokens", 0),
                usage.get("outputTokens", 0))
