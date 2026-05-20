import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ledger import format_total


def test_format_total_applies_tax_rate_to_subtotal():
    items = [
        {"price": "10.00", "quantity": 2},
        {"price": "5.50", "quantity": 1},
    ]

    assert format_total(items, Decimal("0.0825")) == Decimal("27.60")


def test_format_total_rounds_half_up():
    items = [{"price": "19.99", "quantity": 1}]

    assert format_total(items, Decimal("0.08875")) == Decimal("21.76")
