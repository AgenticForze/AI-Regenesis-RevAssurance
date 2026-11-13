import pytest
from pydantic import ValidationError

from ra.shared.schemas import TriageResult


def test_valid_triage_result():
    result = TriageResult(root_cause="RC02_price_book_mismatch", action="correct_catalog",
                          confidence=0.91, rationale="Tariff v14 not applied")
    assert result.confidence == 0.91


def test_unknown_root_cause_rejected():
    with pytest.raises(ValidationError):
        TriageResult(root_cause="RC77_made_up", action="rebill", confidence=0.5, rationale="x")
