"""add facility capacity model (total vs ParkSpot-authorized)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Non-destructive: existing facilities keep single-space semantics (1/1).
    with op.batch_alter_table("parking_spots") as batch:
        batch.add_column(sa.Column("total_capacity", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("authorized_capacity", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("parking_spots") as batch:
        batch.drop_column("authorized_capacity")
        batch.drop_column("total_capacity")
