from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.models import Asset, CalibrationEvent, CalibrationPlan, Certificate, CalibrationException


@dataclass(frozen=True)
class Decision:
    decision: str
    reason: str
    calibration_id: str | None = None
    exception_id: str | None = None


def expected_due_date(calibration_date: date, interval_days: int) -> date:
    if interval_days <= 0:
        raise ValueError("interval_days must be positive")
    return calibration_date + timedelta(days=interval_days)


def derive_outcome(measured_value: float, reference_value: float, lower: float, upper: float) -> tuple[float, str]:
    error = measured_value - reference_value
    return error, "PASS" if lower <= error <= upper else "FAIL"


def plan_for(db: Session, asset_id: str, on_date: date) -> CalibrationPlan | None:
    return db.scalar(select(CalibrationPlan).where(CalibrationPlan.asset_id == asset_id,
        CalibrationPlan.effective_from <= on_date,
        (CalibrationPlan.effective_to.is_(None)) | (CalibrationPlan.effective_to >= on_date)
    ).order_by(CalibrationPlan.effective_from.desc()).limit(1))


def evaluate_use(db: Session, asset_id: str, used_at: datetime) -> Decision:
    if used_at.tzinfo is None:
        used_at = used_at.replace(tzinfo=timezone.utc)
    asset = db.get(Asset, asset_id)
    if not asset:
        return Decision("BLOCKED", "Unknown asset")
    if asset.lifecycle_status != "ACTIVE" or (asset.retired_at and asset.retired_at <= used_at.date()):
        return Decision("BLOCKED", f"Asset lifecycle is {asset.lifecycle_status}")
    event = db.scalar(select(CalibrationEvent).where(CalibrationEvent.asset_id == asset_id,
        CalibrationEvent.calibration_date <= used_at.date()).order_by(CalibrationEvent.calibration_date.desc(), CalibrationEvent.created_at.desc()).limit(1))
    if event and datetime.combine(event.calibration_date, time.min, tzinfo=timezone.utc) > used_at:
        event = None
    if not event:
        return Decision("BLOCKED", "No completed calibration exists as of use time")
    if event.result != "PASS":
        return Decision("BLOCKED", f"Latest calibration {event.calibration_id} result is {event.result}", event.calibration_id)
    if used_at.date() > event.next_due_date:
        plan = db.get(CalibrationPlan, event.plan_id)
        if plan and plan.use_restriction_policy == "REVIEW":
            return Decision("REQUIRES_REVIEW", f"Calibration due {event.next_due_date}; policy requires review", event.calibration_id)
        exceptions = db.scalars(select(CalibrationException).where(
            CalibrationException.asset_id == asset_id, CalibrationException.status == "APPROVED",
            CalibrationException.effective_from <= used_at, CalibrationException.expires_at >= used_at
        )).all()
        scoped = next((x for x in exceptions if x.permitted_use_scope in {"ALL", "PRODUCTION", asset.location, asset.department}), None)
        if scoped:
            return Decision("ALLOWED", f"Approved scoped exception {scoped.exception_id} applies", event.calibration_id, scoped.exception_id)
        return Decision("BLOCKED", f"Calibration overdue since {event.next_due_date}; no applicable approved exception", event.calibration_id)
    plan = db.get(CalibrationPlan, event.plan_id)
    if plan and plan.certificate_required:
        certs = db.scalars(select(Certificate).where(Certificate.calibration_id == event.calibration_id, Certificate.asset_id == asset_id)).all()
        valid = any(c.verification_status == "VERIFIED" and (not c.valid_until or c.valid_until >= used_at.date()) for c in certs)
        if not valid:
            return Decision("BLOCKED", "A verified, currently valid certificate is required", event.calibration_id)
    return Decision("ALLOWED", f"Latest calibration {event.calibration_id} passed and is due {event.next_due_date}", event.calibration_id)


def audit(db: Session, entity_type: str, entity_id: str, action: str, actor: str, new_state: dict | None = None, reason: str | None = None):
    from backend.models import AuditRecord
    db.add(AuditRecord(entity_type=entity_type, entity_id=entity_id, action=action, actor_id=actor, new_state=new_state, reason=reason))
