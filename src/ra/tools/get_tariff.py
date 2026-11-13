"""get_tariff: the tariff effective for a product at a date (contract: specs/get_tariff.yaml)."""
from __future__ import annotations

import re

from ra.shared.tool_base import NotFound, result

PRODUCT_CODE = re.compile(r"^[A-Z0-9-]{3,32}$")


def get_tariff(product_code: str, as_of: str, catalog: list[dict]) -> dict:
    if not PRODUCT_CODE.match(product_code):
        raise ValueError("invalid product_code")
    matches = [
        t for t in catalog
        if t["product_code"] == product_code
        and t["effective_from"] <= as_of
        and (t.get("effective_to") is None or as_of <= t["effective_to"])
    ]
    if not matches:
        raise NotFound(f"no tariff for {product_code} on {as_of}")
    tariff = max(matches, key=lambda t: t["effective_from"])
    return result(tariff, [tariff["record_uid"]], as_of=as_of)
