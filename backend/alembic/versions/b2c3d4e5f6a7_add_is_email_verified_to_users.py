"""add is_email_verified to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-17

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_email_verified with a server default of FALSE so existing rows
    # are backfilled immediately without touching every existing user record.
    # Existing accounts created before this migration are treated as UNVERIFIED;
    # if you want existing users to stay verified, change server_default to 'true'.
    op.add_column(
        'users',
        sa.Column(
            'is_email_verified',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
    )


def downgrade() -> None:
    op.drop_column('users', 'is_email_verified')
