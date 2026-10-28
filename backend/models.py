from datetime import date, datetime
from enum import StrEnum
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db import Base


class Role(StrEnum):
    OPERATOR = "PLANT_OPERATOR"
    MAINTENANCE = "MAINTENANCE_ENGINEER"
    QUALITY = "QUALITY_ENGINEER"
    PLANNER = "PRODUCTION_PLANNER"
    ADMIN = "OT_IT_ADMINISTRATOR"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"
    supplier_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String(160))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    accreditation_reference: Mapped[str | None] = mapped_column(String(100))
    accreditation_valid_until: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class InstrumentType(Base):
    __tablename__ = "instrument_types"
    instrument_type_id: Mapped[int] = mapped_column(primary_key=True)
    type_name: Mapped[str] = mapped_column(String(100), unique=True)
    measurement_unit: Mapped[str] = mapped_column(String(32))
    lower_tolerance: Mapped[float] = mapped_column(Float)
    upper_tolerance: Mapped[float] = mapped_column(Float)
    default_calibration_interval_days: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Asset(Base):
    __tablename__ = "assets"
    asset_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    asset_name: Mapped[str] = mapped_column(String(160))
    serial_number: Mapped[str] = mapped_column(String(100), unique=True)
    instrument_type_id: Mapped[int] = mapped_column(ForeignKey("instrument_types.instrument_type_id"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id"))
    location: Mapped[str] = mapped_column(String(120), index=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    criticality: Mapped[str] = mapped_column(String(16), index=True)
    commissioned_at: Mapped[date] = mapped_column(Date)
    retired_at: Mapped[date | None] = mapped_column(Date)
    lifecycle_status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class CalibrationPlan(Base):
    __tablename__ = "calibration_plans"
    plan_id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    interval_days: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    acceptance_lower: Mapped[float] = mapped_column(Float)
    acceptance_upper: Mapped[float] = mapped_column(Float)
    certificate_required: Mapped[bool] = mapped_column(Boolean, default=True)
    use_restriction_policy: Mapped[str] = mapped_column(String(24), default="BLOCK")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    __table_args__ = (Index("ix_plan_asset_dates", "asset_id", "effective_from", "effective_to"), CheckConstraint("interval_days > 0"), CheckConstraint("effective_to IS NULL OR effective_to >= effective_from"))


class CalibrationEvent(Base):
    __tablename__ = "calibration_events"
    calibration_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("calibration_plans.plan_id"))
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id"))
    calibration_date: Mapped[date] = mapped_column(Date, index=True)
    measured_value: Mapped[float] = mapped_column(Float)
    reference_value: Mapped[float] = mapped_column(Float)
    measurement_error: Mapped[float] = mapped_column(Float)
    tolerance_limit: Mapped[float] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(16), index=True)
    next_due_date: Mapped[date] = mapped_column(Date, index=True)
    performed_by: Mapped[str] = mapped_column(String(80))
    impact_assessment_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    asset: Mapped[Asset] = relationship()


class Certificate(Base):
    __tablename__ = "certificates"
    certificate_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    calibration_id: Mapped[str] = mapped_column(ForeignKey("calibration_events.calibration_id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    certificate_number: Mapped[str | None] = mapped_column(String(120), unique=True)
    issue_date: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    document_uri: Mapped[str | None] = mapped_column(String(255))
    verification_status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    verified_by: Mapped[str | None] = mapped_column(String(80))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    work_order_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    calibration_id: Mapped[str | None] = mapped_column(ForeignKey("calibration_events.calibration_id"))
    work_order_type: Mapped[str] = mapped_column(String(24))
    priority: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    description: Mapped[str] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    assigned_to: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class ProductionBatch(Base):
    __tablename__ = "production_batches"
    batch_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24))
    disposition: Mapped[str | None] = mapped_column(String(120))


class CalibrationException(Base):
    __tablename__ = "calibration_exceptions"
    exception_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(80))
    approved_by: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    permitted_use_scope: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ProductionUse(Base):
    __tablename__ = "production_uses"
    use_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    production_batch_id: Mapped[str | None] = mapped_column(ForeignKey("production_batches.batch_id"), index=True)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    production_status: Mapped[str] = mapped_column(String(24))
    calibration_status_at_use: Mapped[str] = mapped_column(String(24))
    decision: Mapped[str] = mapped_column(String(24), index=True)
    exception_id: Mapped[str | None] = mapped_column(ForeignKey("calibration_exceptions.exception_id"))
    decision_reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ImpactAssessment(Base):
    __tablename__ = "impact_assessments"
    assessment_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    calibration_id: Mapped[str] = mapped_column(ForeignKey("calibration_events.calibration_id"), unique=True)
    affected_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    affected_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    affected_batch_ids: Mapped[list] = mapped_column(JSON, default=list)
    risk_evaluation: Mapped[str] = mapped_column(Text)
    disposition: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="REQUIRED", index=True)


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"
    action_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    calibration_id: Mapped[str] = mapped_column(ForeignKey("calibration_events.calibration_id"), index=True)
    root_cause: Mapped[str] = mapped_column(Text)
    measures: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(80))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    closure_evidence: Mapped[str | None] = mapped_column(Text)


class Alert(Base):
    __tablename__ = "alerts"
    alert_id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), index=True)
    calibration_id: Mapped[str | None] = mapped_column(ForeignKey("calibration_events.calibration_id"))
    use_id: Mapped[str | None] = mapped_column(ForeignKey("production_uses.use_id"))
    alert_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(16), index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(80))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_open_alert_business", "asset_id", "alert_type", "calibration_id", "use_id"),)


class AuditRecord(Base):
    __tablename__ = "audit_records"
    audit_id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(24))
    actor_id: Mapped[str] = mapped_column(String(80), index=True)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    previous_state: Mapped[dict | None] = mapped_column(JSON)
    new_state: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(64))


Index("ix_calibration_asset_due", CalibrationEvent.asset_id, CalibrationEvent.next_due_date)
