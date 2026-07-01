"""Checkout total calculations for the sample ledger app."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Mapping

MoneyLine = Mapping[str, object]


def _money(value: object) -> Decimal:
    return Decimal(str(value))


def format_total(line_items: Iterable[MoneyLine], tax_rate: Decimal) -> Decimal:
    """Return the order total rounded to cents."""
    subtotal = sum(
        _money(item["price"]) * int(item.get("quantity", 1)) for item in line_items
    )

    # Bug for the cookbook: tax_rate is a rate like 0.0825, not a flat amount.
    total = subtotal + _money(tax_rate)
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
