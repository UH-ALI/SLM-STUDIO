"""fix_training_job_columns

Revision ID: 701d86b7ea0d
Revises: 504bfdc043c7
Create Date: 2026-06-23 10:49:47.128584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '701d86b7ea0d'
down_revision: Union[str, None] = '504bfdc043c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Step 1: Backfill old TrainingJob records ────────────────────────────
    # Must run BEFORE alter_column to avoid NOT NULL constraint violation
    op.execute("""
        UPDATE training_jobs
        SET base_model_name = CASE use_case
            WHEN 'medical' THEN 'unsloth/Phi-2-bnb-4bit'
            ELSE 'unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit'
        END
        WHERE base_model_name IS NULL
    """)

    op.execute("""
        UPDATE training_jobs
        SET persona = 'You are a highly capable AI domain expert.
You are an expert AI assistant for the content of this document.
You explain concepts clearly and concisely.
You only answer questions grounded in the provided documents.'
        WHERE persona IS NULL
    """)

    # ─── Step 2: Make TrainingJob columns non-nullable ───────────────────────
    # NOTE: We ONLY alter training_jobs, NOT projects or model_artifacts.
    # Project.persona and Project.base_model_name stay nullable (set in Steps 2/3).
    op.alter_column('training_jobs', 'base_model_name',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('training_jobs', 'persona',
               existing_type=sa.TEXT(),
               nullable=False)


def downgrade() -> None:
    # Revert only training_jobs
    op.alter_column('training_jobs', 'persona',
               existing_type=sa.TEXT(),
               nullable=True)
    op.alter_column('training_jobs', 'base_model_name',
               existing_type=sa.VARCHAR(),
               nullable=True)