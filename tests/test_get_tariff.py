import pytest

from ra.shared.tool_base import NotFound
from ra.tools.get_tariff import get_tariff

CATALOG = [
    {"product_code": "ROAM-EU-DATA", "version": "v13", "effective_from": "2026-01-01",
     "effective_to": "2026-09-30", "record_uid": "S7:a1"},
    {"product_code": "ROAM-EU-DATA", "version": "v14", "effective_from": "2026-10-01",
     "effective_to": None, "record_uid": "S7:b2"},
]


def test_effective_date_selects_v14():
    out = get_tariff("ROAM-EU-DATA", "2026-10-15", CATALOG)
    assert out["data"]["version"] == "v14"
    assert out["record_uids"] == ["S7:b2"]


def test_before_any_tariff_raises():
    with pytest.raises(NotFound):
        get_tariff("ROAM-EU-DATA", "2025-12-31", CATALOG)
