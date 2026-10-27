from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def q2(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
