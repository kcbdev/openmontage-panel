"""phase5_auth_tenants

Revision ID: 2a962e619a19
Revises:
Create Date: 2026-07-14 03:42:14.028844
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '2a962e619a19'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are ordered to respect FK dependencies (no forward references)
    # 1. tenants — no FKs
    op.create_table('tenants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('budget_cap_default', sa.Numeric(), nullable=True),
    sa.Column('budget_mode_default', sa.String(), nullable=True),
    sa.Column('gate_role_requirements', sa.JSON(), nullable=True),
    sa.Column('max_concurrent_runs', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )

    # 2. users — FK to tenants, self-FK to users
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=True),
    sa.Column('invited_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )

    # 3. projects — FK to tenants
    op.create_table('projects',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('pipeline_type', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('render_runtime', sa.String(), nullable=True),
    sa.Column('style_playbook', sa.String(), nullable=True),
    sa.Column('platform_profile', sa.String(), nullable=True),
    sa.Column('duration_target_seconds', sa.String(), nullable=True),
    sa.Column('parent_project_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 4. runs — FK to projects (no FK to stage_checkpoints yet to avoid circular dep)
    op.create_table('runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('engine_container_id', sa.String(), nullable=True),
    sa.Column('engine_version', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('current_stage', sa.String(), nullable=True),
    sa.Column('anomaly_reason', sa.Text(), nullable=True),
    sa.Column('last_good_checkpoint_id', sa.UUID(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('queue_position', sa.Integer(), nullable=True),
    sa.Column('studio_params', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 5. stage_checkpoints — FK to runs
    op.create_table('stage_checkpoints',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('stage', sa.String(), nullable=False),
    sa.Column('checkpoint_json', sa.JSON(), nullable=False),
    sa.Column('decision_log_json', sa.JSON(), nullable=True),
    sa.Column('cost_snapshot_json', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 6. assets — FK to runs
    op.create_table('assets',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('stage', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('storage_path', sa.String(), nullable=True),
    sa.Column('provider_used', sa.String(), nullable=True),
    sa.Column('cost', sa.Numeric(), nullable=True),
    sa.Column('is_locked', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 7. provider_credentials — FK to tenants
    op.create_table('provider_credentials',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('provider_key', sa.String(), nullable=False),
    sa.Column('encrypted_value', sa.String(), nullable=False),
    sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 8. approval_gates — FK to runs, FK to users
    op.create_table('approval_gates',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('stage', sa.String(), nullable=False),
    sa.Column('gate_type', sa.String(), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('revision_notes', sa.Text(), nullable=True),
    sa.Column('resolved_by', sa.UUID(), nullable=True),
    sa.Column('required_role', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 9. budget_ledger — FK to tenants, projects, runs
    op.create_table('budget_ledger',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('estimated_cost', sa.Numeric(), nullable=True),
    sa.Column('actual_cost', sa.Numeric(), nullable=True),
    sa.Column('mode', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Add the circular FK last: runs → stage_checkpoints
    op.create_foreign_key(
        'fk_runs_last_good_checkpoint',
        'runs', 'stage_checkpoints',
        ['last_good_checkpoint_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_runs_last_good_checkpoint', 'runs', type_='foreignkey')
    op.drop_table('budget_ledger')
    op.drop_table('approval_gates')
    op.drop_table('provider_credentials')
    op.drop_table('assets')
    op.drop_table('stage_checkpoints')
    op.drop_table('runs')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('tenants')
