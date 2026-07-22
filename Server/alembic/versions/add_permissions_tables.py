"""Retire the obsolete parallel permissions schema.

Revision ID: add_permissions_tables
Revises: v0.3.0_workflows
"""

from typing import Sequence, Union


revision: str = "add_permissions_tables"
down_revision: Union[str, Sequence[str], None] = "v0.3.0_workflows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The application uses fundinv_auth.role_claims. Do not create the old
    # permissions/user_permissions/role_permissions tables again.
    pass


def downgrade() -> None:
    pass
