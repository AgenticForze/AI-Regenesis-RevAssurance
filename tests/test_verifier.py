"""The verifier must block a finding the records do not support."""
from ra import db
from ra.agents import runtime


def test_verifier_blocks_wrong_amount_and_fake_evidence(run):
    exc = db.one("SELECT * FROM exceptions WHERE root_cause='RC05_provisioned_not_billed' LIMIT 1")
    good = {"root_cause": exc["root_cause"], "action": "rebill",
            "proposed_amount": exc["variance"], "confidence": 0.9,
            "evidence_ids": exc["record_uids"][:1], "narrative": "ok"}
    assert runtime.verify(exc, good, {})["passed"]
    inflated = {**good, "proposed_amount": exc["variance"] * 3}
    v = runtime.verify(exc, inflated, {})
    assert not v["passed"] and not next(c for c in v["checks"]
                                        if c["check"] == "amount_recomputed")["ok"]
    invented = {**good, "evidence_ids": ["made-up-record"]}
    assert not runtime.verify(exc, invented, {})["passed"]
    wrong_action = {**good, "action": "dispute_partner"}
    assert not runtime.verify(exc, wrong_action, {})["passed"]


def test_invalid_triage_output_is_downgraded(run, monkeypatch):
    from ra import llm

    class Hallucinating:
        name = "test"

        def complete_json(self, step, system, payload):
            return {"root_cause": "RC42_made_up", "action": "rebill", "confidence": 0.99,
                    "rationale": "x"}, 10, 10

    exc = db.one("SELECT * FROM exceptions LIMIT 1")
    monkeypatch.setattr(llm, "_backend", Hallucinating())
    t = runtime.triage(exc)
    assert t["root_cause"] == "RC99_other" and t["confidence"] == 0 and t["route"] == "investigate"
