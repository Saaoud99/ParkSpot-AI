from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.booking import Booking, Payment
from app.db.models.enums import PaymentStatus
from app.utils.money import q2


async def charge(db: AsyncSession, booking: Booking) -> Payment:
    payment = Payment(
        booking_id=booking.id, amount=q2(Decimal(booking.total_price)), currency=booking.currency,
        status=PaymentStatus.succeeded, provider="mock", provider_ref=f"mock_{uuid.uuid4().hex[:12]}",
    )
    db.add(payment)
    await db.flush()
    return payment


async def refund(db: AsyncSession, booking: Booking) -> Payment | None:
    if booking.payment and booking.payment.status == PaymentStatus.succeeded:
        booking.payment.status = PaymentStatus.refunded
        await db.flush()
        return booking.payment
    return booking.payment
