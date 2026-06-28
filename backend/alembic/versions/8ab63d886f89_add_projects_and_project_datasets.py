"""add_projects_and_project_datasets

Revision ID: 8ab63d886f89
Revises: 701d86b7ea0d
Create Date: 2026-06-27 08:30:30.107459

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8ab63d886f89'
down_revision: Union[str, None] = '701d86b7ea0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # [FIX] projects/project_datasets table creation and the training_jobs FK
    # were moved to 504bfdc043c7 (the migration immediately before this one in
    # the chain), which is where the original autogenerate run had already put
    # a FK reference to 'projects' — that FK would fail with
    # "relation \"projects\" does not exist" if this migration's table creation
    # ran second, as it originally did. This migration is now a no-op kept only
    # to preserve the revision chain (in case any environment already recorded
    # 8ab63d886f89 as applied via alembic_version during development).
    pass


def downgrade() -> None:
    pass
