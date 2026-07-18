"""add cascade deletes to foreign keys

Revision ID: a1b2c3d4e5f6
Revises: 9a1b2c3d4e5f
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9a1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade():
    # --- project_datasets association table ---
    op.drop_constraint('project_datasets_project_id_fkey', 'project_datasets', type_='foreignkey')
    op.create_foreign_key('project_datasets_project_id_fkey', 'project_datasets', 'projects',
                          ['project_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('project_datasets_dataset_id_fkey', 'project_datasets', type_='foreignkey')
    op.create_foreign_key('project_datasets_dataset_id_fkey', 'project_datasets', 'datasets',
                          ['dataset_id'], ['id'], ondelete='CASCADE')

    # --- training_jobs.project_id ---
    op.drop_constraint('training_jobs_project_id_fkey', 'training_jobs', type_='foreignkey')
    op.create_foreign_key('training_jobs_project_id_fkey', 'training_jobs', 'projects',
                          ['project_id'], ['id'], ondelete='CASCADE')

    # --- model_artifacts.job_id ---
    op.drop_constraint('model_artifacts_job_id_fkey', 'model_artifacts', type_='foreignkey')
    op.create_foreign_key('model_artifacts_job_id_fkey', 'model_artifacts', 'training_jobs',
                          ['job_id'], ['id'], ondelete='CASCADE')

    # --- job_logs.job_id ---
    op.drop_constraint('job_logs_job_id_fkey', 'job_logs', type_='foreignkey')
    op.create_foreign_key('job_logs_job_id_fkey', 'job_logs', 'training_jobs',
                          ['job_id'], ['id'], ondelete='CASCADE')

    # --- Add file_hash column to datasets ---
    op.add_column('datasets', sa.Column('file_hash', sa.String(), nullable=True))
    op.create_index('ix_datasets_file_hash', 'datasets', ['file_hash'])


def downgrade():
    # Remove file_hash
    op.drop_index('ix_datasets_file_hash', table_name='datasets')
    op.drop_column('datasets', 'file_hash')

    # Restore original FKs without ondelete
    op.drop_constraint('job_logs_job_id_fkey', 'job_logs', type_='foreignkey')
    op.create_foreign_key('job_logs_job_id_fkey', 'job_logs', 'training_jobs',
                          ['job_id'], ['id'])

    op.drop_constraint('model_artifacts_job_id_fkey', 'model_artifacts', type_='foreignkey')
    op.create_foreign_key('model_artifacts_job_id_fkey', 'model_artifacts', 'training_jobs',
                          ['job_id'], ['id'])

    op.drop_constraint('training_jobs_project_id_fkey', 'training_jobs', type_='foreignkey')
    op.create_foreign_key('training_jobs_project_id_fkey', 'training_jobs', 'projects',
                          ['project_id'], ['id'])

    op.drop_constraint('project_datasets_dataset_id_fkey', 'project_datasets', type_='foreignkey')
    op.create_foreign_key('project_datasets_dataset_id_fkey', 'project_datasets', 'datasets',
                          ['dataset_id'], ['id'])

    op.drop_constraint('project_datasets_project_id_fkey', 'project_datasets', type_='foreignkey')
    op.create_foreign_key('project_datasets_project_id_fkey', 'project_datasets', 'projects',
                          ['project_id'], ['id'])
