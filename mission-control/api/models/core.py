import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from api.db.session import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    budget_cap_default = Column(Numeric, default=10.00)
    budget_mode_default = Column(String, default="warn")
    gate_role_requirements = Column(JSON, default=lambda: {"publish": "owner"})
    max_concurrent_runs = Column(Integer, default=3)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    users = relationship("User", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    id = Column(UUID, primary_key=True, default=_uuid)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="editor")
    invited_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    tenant = relationship("Tenant", back_populates="users")


class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID, primary_key=True, default=_uuid)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)
    pipeline_type = Column(String, nullable=False)
    status = Column(String, default="draft")
    render_runtime = Column(String, nullable=True)
    style_playbook = Column(String, nullable=True)
    platform_profile = Column(String, nullable=True)
    duration_target_seconds = Column(Integer, nullable=True)
    parent_project_id = Column(UUID, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    runs = relationship("Run", back_populates="project", cascade="all, delete-orphan")
    tenant = relationship("Tenant")


class Run(Base):
    __tablename__ = "runs"
    id = Column(UUID, primary_key=True, default=_uuid)
    project_id = Column(UUID, ForeignKey("projects.id"), nullable=False)
    engine_container_id = Column(String, nullable=True)
    engine_version = Column(String, nullable=False)
    status = Column(String, default="provisioning")
    current_stage = Column(String, nullable=True)
    anomaly_reason = Column(Text, nullable=True)
    last_good_checkpoint_id = Column(UUID, ForeignKey("stage_checkpoints.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), default=_utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    queue_position = Column(Integer, nullable=True)

    studio_params = Column(JSON, nullable=True)

    project = relationship("Project", back_populates="runs")
    checkpoints = relationship(
        "StageCheckpoint", back_populates="run",
        cascade="all, delete-orphan",
        foreign_keys="StageCheckpoint.run_id",
    )
    gates = relationship("ApprovalGate", back_populates="run", cascade="all, delete-orphan")


class StageCheckpoint(Base):
    __tablename__ = "stage_checkpoints"
    id = Column(UUID, primary_key=True, default=_uuid)
    run_id = Column(UUID, ForeignKey("runs.id"), nullable=False)
    stage = Column(String, nullable=False)
    checkpoint_json = Column(JSON, nullable=False)
    decision_log_json = Column(JSON, nullable=True)
    cost_snapshot_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    run = relationship("Run", back_populates="checkpoints", foreign_keys=[run_id])


class ApprovalGate(Base):
    __tablename__ = "approval_gates"
    id = Column(UUID, primary_key=True, default=_uuid)
    run_id = Column(UUID, ForeignKey("runs.id"), nullable=False)
    stage = Column(String, nullable=False)
    gate_type = Column(String, nullable=False)
    payload_json = Column(JSON, nullable=True)
    status = Column(String, default="pending")
    revision_notes = Column(Text, nullable=True)
    resolved_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    required_role = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    run = relationship("Run", back_populates="gates")


class Asset(Base):
    __tablename__ = "assets"
    id = Column(UUID, primary_key=True, default=_uuid)
    run_id = Column(UUID, ForeignKey("runs.id"), nullable=False)
    stage = Column(String, nullable=False)
    type = Column(String, nullable=False)
    storage_path = Column(String, nullable=True)
    provider_used = Column(String, nullable=True)
    cost = Column(Numeric, nullable=True)
    is_locked = Column(Boolean, default=False)
    scene_number = Column(Integer, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    id = Column(UUID, primary_key=True, default=_uuid)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    provider_key = Column(String, nullable=False)
    encrypted_value = Column(String, nullable=False)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class MissionProfile(Base):
    __tablename__ = "mission_profiles"
    id = Column(UUID, primary_key=True, default=_uuid)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)
    pipeline_type = Column(String, nullable=False)
    params = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class TenantStylePlaybook(Base):
    __tablename__ = "tenant_style_playbooks"
    id = Column(UUID, primary_key=True, default=_uuid)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False)
    source_playbook_id = Column(String, nullable=True)
    yaml_content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class DecisionLog(Base):
    __tablename__ = "decision_logs"
    id = Column(UUID, primary_key=True, default=_uuid)
    run_id = Column(UUID, ForeignKey("runs.id"), nullable=False)
    stage = Column(String, nullable=False)
    gate_type = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    resolved_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class BudgetLedger(Base):
    __tablename__ = "budget_ledger"
    id = Column(UUID, primary_key=True, default=_uuid)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    project_id = Column(UUID, ForeignKey("projects.id"), nullable=False)
    run_id = Column(UUID, ForeignKey("runs.id"), nullable=False)
    action = Column(String, nullable=False)
    estimated_cost = Column(Numeric, nullable=True)
    actual_cost = Column(Numeric, nullable=True)
    mode = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
