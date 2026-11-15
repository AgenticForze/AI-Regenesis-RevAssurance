---
name: investigate-pricing
description: "Use when rated usage does not match the catalog tariff: stale price book or rating error."
root_causes: [RC01_rating_error, RC02_price_book_mismatch]
tools: [get_rated_usage, get_tariff]
---

# investigate-pricing

1. Read the rated records and the tariff version each one used.
2. Fetch the tariff in force on the last day of the period for the product.
3. If the rated record used a superseded version, the cause is a price-book mismatch: recommend `correct_catalog`.
4. If the version is current but the amount differs, the cause is a rating error: recommend `fix_rating_config`.
5. The correction is quantity times the current unit price, minus the rated amount.
