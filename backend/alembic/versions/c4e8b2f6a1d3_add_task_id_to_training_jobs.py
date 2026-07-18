"""add_task_id_to_training_jobs

Revision ID: c4e8b2f6a1d3
Revises: b3f7a1c9d2e4
Create Date: 2026-07-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4e8b2f6a1d3'
down_revision: Union[str, None] = 'b3f7a1c9d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # [FEATURE] Backs true "cancel training" via Celery revoke — without a
    # stored task id there was nothing valid to revoke() (an earlier version
    # passed the TrainingJob's own UUID, which is not a Celery task id, and
    # never actually worked).
    op.add_column('training_jobs', sa.Column('task_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('training_jobs', 'task_id')
