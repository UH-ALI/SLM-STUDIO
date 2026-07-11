"""add_deployment_feature

Revision ID: 9a1b2c3d4e5f
Revises: 8ab63d886f89
Create Date: 2026-06-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9a1b2c3d4e5f'
down_revision: Union[str, None] = '8ab63d886f89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add deployment columns to projects table
    op.add_column('projects', sa.Column('is_public', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('projects', sa.Column('deploy_key', sa.String(), nullable=True))
    op.add_column('projects', sa.Column('deploy_key_created_at', sa.DateTime(), nullable=True))
    op.add_column('projects', sa.Column('widget_config', sa.JSON(), nullable=True))
    op.add_column('projects', sa.Column('allowed_origins', sa.JSON(), nullable=True))
    op.create_index(op.f('ix_projects_deploy_key'), 'projects', ['deploy_key'], unique=True)

    # 2. Create deployment_usage table
    # [FIX] Removed a live-DB Inspector.has_table() guard that was here to avoid
    # conflicting with `Base.metadata.create_all()` having already made this
    # table during local dev. That guard required a real database connection
    # and broke `alembic upgrade head --sql` (offline SQL generation/dry-run).
    # This migration is the only place deployment_usage is created, so on a
    # migration-managed database (fresh or otherwise) it will never already exist.
    op.create_table('deployment_usage',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('usage_date', sa.Date(), nullable=False),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'usage_date', name='uq_project_usage_date')
    )
    op.create_index(op.f('ix_deployment_usage_project_id'), 'deployment_usage', ['project_id'], unique=False)

    # 3. Drop deployments table and clean up
    op.drop_table('deployments')

    # Note: postgresql ENUMs need to be dropped manually if they exist
    # op.execute("DROP TYPE IF EXISTS deploymentstatus;")


def downgrade() -> None:
    # 1. Recreate deployments table
    op.create_table('deployments',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('model_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('status', postgresql.ENUM('ACTIVE', 'INACTIVE', name='deploymentstatus'), autoincrement=False, nullable=True),
        sa.Column('inference_url', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['model_artifacts.id'], name='deployments_model_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='deployments_pkey')
    )

    # 2. Drop deployment_usage table
    op.drop_index(op.f('ix_deployment_usage_project_id'), table_name='deployment_usage')
    op.drop_table('deployment_usage')

    # 3. Remove deployment columns from projects
    op.drop_index(op.f('ix_projects_deploy_key'), table_name='projects')
    op.drop_column('projects', 'allowed_origins')
    op.drop_column('projects', 'widget_config')
    op.drop_column('projects', 'deploy_key_created_at')
    op.drop_column('projects', 'deploy_key')
    op.drop_column('projects', 'is_public')
