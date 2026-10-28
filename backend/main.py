from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import logging
import uuid
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.config import settings
from backend.db import Base, engine, get_db
from backend.models import *
from backend.schemas import AssetCreate, AssetOut, CalibrationCreate, ProductionUseCreate, LoginInput, TokenOut, DecisionOut
from backend.security import current_user, create_token, hash_password, verify_password, require_roles
from backend.services.compliance import derive_outcome, expected_due_date, evaluate_use, audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("calibratrack")
app = FastAPI(title="CalibraTrack API", version="1.0.0", description="Instrument calibration compliance decision support")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
router = __import__("fastapi").APIRouter(prefix="/api/v1")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username, User.active.is_(True)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return TokenOut(access_token=create_token(user))


@router.get("/dashboard/summary")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = datetime.now(timezone.utc).date()
    active = db.scalar(select(func.count()).select_from(Asset).where(Asset.lifecycle_status == "ACTIVE")) or 0
    latest = select(CalibrationEvent.asset_id, func.max(CalibrationEvent.calibration_date).label("d")).group_by(CalibrationEvent.asset_id).subquery()
    rows = db.execute(select(CalibrationEvent).join(latest, (CalibrationEvent.asset_id == latest.c.asset_id) & (CalibrationEvent.calibration_date == latest.c.d))).scalars().all()
    overdue = sum(e.next_due_date < today for e in rows)
    soon = sum(today <= e.next_due_date <= today + timedelta(days=30) for e in rows)
    passing = sum(e.result == "PASS" and e.next_due_date >= today for e in rows)
    failed = db.scalar(select(func.count()).select_from(CalibrationEvent).where(CalibrationEvent.result == "FAIL")) or 0
    alerts = db.scalar(select(func.count()).select_from(Alert).where(Alert.status.in_(["OPEN", "ACKNOWLEDGED"]), Alert.severity == "CRITICAL")) or 0
    actions = db.scalar(select(func.count()).select_from(CorrectiveAction).where(CorrectiveAction.status != "CLOSED")) or 0
    downtime = db.scalar(select(func.coalesce(func.sum(WorkOrder.downtime_minutes), 0))) or 0
    uses_blocked = db.scalar(select(func.count()).select_from(ProductionUse).where(ProductionUse.decision == "BLOCKED")) or 0
    cert_missing = db.scalar(select(func.count()).select_from(Certificate).where(Certificate.verification_status != "VERIFIED")) or 0
    return {"active_instruments": active, "due_soon": soon, "overdue": overdue, "compliance_rate": round(100 * passing / max(len(rows), 1), 1), "failed_calibrations": failed, "missing_or_invalid_certificates": cert_missing, "prohibited_uses": uses_blocked, "open_corrective_actions": actions, "downtime_minutes": downtime, "critical_alerts": alerts}


@router.get("/dashboard/trends")
def trends(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(select(CalibrationEvent.calibration_date, CalibrationEvent.result)).all()
    buckets = {}
    for calibration_date, state in rows:
        month = calibration_date.strftime("%Y-%m")
        buckets.setdefault(month, {"month": month, "PASS": 0, "FAIL": 0, "INDETERMINATE": 0})[state] += 1
    return {"calibration_results": [buckets[month] for month in sorted(buckets)]}


@router.get("/assets", response_model=list[AssetOut])
def assets(search: str | None = None, department: str | None = None, criticality: str | None = None, lifecycle_status: str | None = None,
           page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Asset)
    if search:
        term = f"%{search}%"
        q = q.where((Asset.asset_id.ilike(term)) | (Asset.asset_name.ilike(term)) | (Asset.serial_number.ilike(term)) | (Asset.location.ilike(term)))
    if department: q = q.where(Asset.department == department)
    if criticality: q = q.where(Asset.criticality == criticality)
    if lifecycle_status: q = q.where(Asset.lifecycle_status == lifecycle_status)
    return db.scalars(q.order_by(Asset.asset_id).offset((page - 1) * page_size).limit(page_size)).all()


@router.post("/assets", response_model=AssetOut, status_code=201)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN, Role.MAINTENANCE))):
    if not db.get(InstrumentType, payload.instrument_type_id): raise HTTPException(422, "Unknown instrument type")
    seq = (db.scalar(select(func.count()).select_from(Asset)) or 0) + 1
    row = Asset(asset_id=f"AST-{seq:06d}", **payload.model_dump())
    db.add(row); db.flush(); audit(db, "Asset", row.asset_id, "CREATE", user.username, {"asset_name": row.asset_name}); db.commit(); db.refresh(row)
    return row


@router.get("/assets/{asset_id}")
def asset_detail(asset_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.get(Asset, asset_id)
    if not row: raise HTTPException(404, "Asset not found")
    latest = db.scalar(select(CalibrationEvent).where(CalibrationEvent.asset_id == asset_id).order_by(CalibrationEvent.calibration_date.desc()).limit(1))
    decision = evaluate_use(db, asset_id, datetime.now(timezone.utc))
    return {"asset": AssetOut.model_validate(row), "latest_calibration": latest, "compliance": decision.__dict__}


@router.get("/assets/{asset_id}/history")
def asset_history(asset_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(Asset, asset_id): raise HTTPException(404, "Asset not found")
    return {"calibrations": db.scalars(select(CalibrationEvent).where(CalibrationEvent.asset_id == asset_id).order_by(CalibrationEvent.calibration_date.desc())).all(),
            "uses": db.scalars(select(ProductionUse).where(ProductionUse.asset_id == asset_id).order_by(ProductionUse.used_at.desc()).limit(200)).all(),
            "alerts": db.scalars(select(Alert).where(Alert.asset_id == asset_id).order_by(Alert.created_at.desc())).all(),
            "work_orders": db.scalars(select(WorkOrder).where(WorkOrder.asset_id == asset_id).order_by(WorkOrder.opened_at.desc())).all(),
            "audit": db.scalars(select(AuditRecord).where(AuditRecord.entity_id == asset_id).order_by(AuditRecord.event_timestamp.desc())).all()}


@router.get("/calibration-plans")
def plans(asset_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(CalibrationPlan).order_by(CalibrationPlan.asset_id, CalibrationPlan.effective_from.desc())
    if asset_id: q = q.where(CalibrationPlan.asset_id == asset_id)
    return db.scalars(q.limit(500)).all()


@router.post("/calibration-plans", status_code=201)
def create_plan(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.MAINTENANCE, Role.ADMIN))):
    data = dict(payload); row = CalibrationPlan(**data)
    if row.interval_days <= 0 or row.effective_to and row.effective_to < row.effective_from: raise HTTPException(422, "Invalid effective dates or interval")
    overlap = db.scalar(select(CalibrationPlan).where(CalibrationPlan.asset_id == row.asset_id, (CalibrationPlan.effective_to.is_(None)) | (CalibrationPlan.effective_to >= row.effective_from), (row.effective_to is None) | (CalibrationPlan.effective_from <= row.effective_to)))
    if overlap: raise HTTPException(409, "Plan effective dates overlap an existing plan")
    db.add(row); db.flush(); audit(db, "CalibrationPlan", str(row.plan_id), "CREATE", user.username); db.commit(); db.refresh(row); return row


@router.get("/calibrations")
def calibrations(asset_id: str | None = None, result: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(CalibrationEvent).order_by(CalibrationEvent.calibration_date.desc())
    if asset_id: q = q.where(CalibrationEvent.asset_id == asset_id)
    if result: q = q.where(CalibrationEvent.result == result)
    return db.scalars(q.offset((page-1)*page_size).limit(page_size)).all()


@router.post("/calibrations", status_code=201)
def create_calibration(payload: CalibrationCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.MAINTENANCE, Role.ADMIN))):
    asset = db.get(Asset, payload.asset_id)
    if not asset: raise HTTPException(404, "Asset not found")
    plan = db.scalar(select(CalibrationPlan).where(CalibrationPlan.asset_id == asset.asset_id, CalibrationPlan.effective_from <= payload.calibration_date, (CalibrationPlan.effective_to.is_(None)) | (CalibrationPlan.effective_to >= payload.calibration_date)).order_by(CalibrationPlan.effective_from.desc()).limit(1))
    if not plan: raise HTTPException(422, "No effective calibration plan for event date")
    error, outcome = derive_outcome(payload.measured_value, payload.reference_value, plan.acceptance_lower, plan.acceptance_upper)
    year_start = date(payload.calibration_date.year, 1, 1)
    year_end = date(payload.calibration_date.year + 1, 1, 1)
    seq = (db.scalar(select(func.count()).select_from(CalibrationEvent).where(CalibrationEvent.asset_id == asset.asset_id, CalibrationEvent.calibration_date >= year_start, CalibrationEvent.calibration_date < year_end)) or 0) + 1
    cid = f"CAL-{asset.asset_id}-{payload.calibration_date.year}-{seq:06d}"
    row = CalibrationEvent(calibration_id=cid, asset_id=asset.asset_id, plan_id=plan.plan_id, supplier_id=payload.supplier_id,
        calibration_date=payload.calibration_date, measured_value=payload.measured_value, reference_value=payload.reference_value,
        measurement_error=error, tolerance_limit=max(abs(plan.acceptance_lower), abs(plan.acceptance_upper)), result=outcome,
        next_due_date=expected_due_date(payload.calibration_date, plan.interval_days), performed_by=user.username,
        impact_assessment_required=outcome == "FAIL")
    db.add(row)
    if outcome == "FAIL":
        wo_seq = (db.scalar(select(func.count()).select_from(WorkOrder)) or 0) + 1
        db.add(WorkOrder(work_order_id=f"WO-{payload.calibration_date.year}-{wo_seq:06d}", asset_id=asset.asset_id, calibration_id=cid,
            work_order_type="CORRECTIVE_ACTION", priority="HIGH", status="OPEN", description=f"Investigate failed calibration {cid}"))
        db.add(ImpactAssessment(assessment_id=f"IA-{cid}", calibration_id=cid, affected_from=datetime.combine(payload.calibration_date, time.min, timezone.utc),
            affected_to=datetime.combine(payload.calibration_date, time.max, timezone.utc), risk_evaluation="Required: assess uses since last known good calibration", status="REQUIRED"))
        db.add(Alert(asset_id=asset.asset_id, calibration_id=cid, alert_type="FAILED_CALIBRATION", severity="HIGH", description=f"Calibration {cid} failed"))
    db.flush(); audit(db, "CalibrationEvent", cid, "CREATE", user.username, {"result": outcome, "measurement_error": error}); db.commit(); db.refresh(row)
    return row


@router.get("/certificates")
def certificates(asset_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Certificate).order_by(Certificate.created_at.desc())
    if asset_id: q = q.where(Certificate.asset_id == asset_id)
    return db.scalars(q.limit(500)).all()


@router.post("/certificates/upload", status_code=201)
async def upload_certificate(calibration_id: str, asset_id: str, certificate_number: str, issue_date: date, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_roles(Role.QUALITY, Role.ADMIN))):
    event = db.get(CalibrationEvent, calibration_id)
    if not event or event.asset_id != asset_id: raise HTTPException(422, "Certificate asset must match its calibration event")
    if file.content_type not in {"application/pdf", "image/png", "image/jpeg"}: raise HTTPException(415, "Only PDF, PNG, and JPEG files are accepted")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes: raise HTTPException(413, "File exceeds configured size limit")
    folder = Path(settings.upload_dir).resolve(); folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "certificate.pdf").suffix.lower()
    key = f"{uuid.uuid4().hex}{suffix}"; (folder / key).write_bytes(content)
    cert = Certificate(certificate_id=f"CERT-{calibration_id}", calibration_id=calibration_id, asset_id=asset_id, certificate_number=certificate_number, issue_date=issue_date, document_uri=key, verification_status="PENDING")
    db.add(cert); audit(db, "Certificate", cert.certificate_id, "CREATE", user.username); db.commit(); return {"certificate_id": cert.certificate_id, "verification_status": cert.verification_status}


@router.post("/certificates/{certificate_id}/verify")
def verify_certificate(certificate_id: str, decision: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.QUALITY, Role.ADMIN))):
    cert = db.get(Certificate, certificate_id)
    if not cert: raise HTTPException(404, "Certificate not found")
    if decision not in {"VERIFIED", "REJECTED"}: raise HTTPException(422, "Decision must be VERIFIED or REJECTED")
    event = db.get(CalibrationEvent, cert.calibration_id)
    if event.asset_id != cert.asset_id: raise HTTPException(409, "Certificate asset does not match calibration asset")
    cert.verification_status = decision; cert.verified_by = user.username; cert.verified_at = datetime.now(timezone.utc)
    audit(db, "Certificate", certificate_id, "APPROVE" if decision == "VERIFIED" else "REJECT", user.username, {"status": decision}); db.commit(); return cert


@router.get("/production-uses")
def uses(asset_id: str | None = None, decision: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(ProductionUse).order_by(ProductionUse.used_at.desc())
    if asset_id: q = q.where(ProductionUse.asset_id == asset_id)
    if decision: q = q.where(ProductionUse.decision == decision)
    return db.scalars(q.offset((page-1)*page_size).limit(page_size)).all()


@router.post("/production-uses", status_code=201)
def create_use(payload: ProductionUseCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.OPERATOR, Role.ADMIN))):
    result = evaluate_use(db, payload.asset_id, payload.used_at)
    uid = f"USE-{payload.asset_id}-{payload.used_at.strftime('%Y%m%dT%H%M%S%fZ')}"
    row = ProductionUse(use_id=uid, **payload.model_dump(), calibration_status_at_use=result.decision, decision=result.decision,
        exception_id=result.exception_id, decision_reason=result.reason)
    db.add(row)
    if result.decision == "BLOCKED": db.add(Alert(asset_id=payload.asset_id, use_id=uid, alert_type="PROHIBITED_USE", severity="HIGH", description=result.reason))
    db.flush(); audit(db, "ProductionUse", uid, "DECISION", user.username, {"decision": result.decision, "reason": result.reason}); db.commit(); db.refresh(row); return row


@router.post("/compliance/evaluate", response_model=DecisionOut)
def evaluate(payload: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try: at = datetime.fromisoformat(payload["used_at"].replace("Z", "+00:00"))
    except Exception: raise HTTPException(422, "used_at must be an ISO 8601 timestamp")
    d = evaluate_use(db, payload["asset_id"], at)
    return DecisionOut(decision=d.decision, reason=d.reason, calibration_id=d.calibration_id, exception_id=d.exception_id)


@router.get("/work-orders")
def work_orders(status: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(WorkOrder).order_by(WorkOrder.opened_at.desc())
    if status: q = q.where(WorkOrder.status == status)
    return db.scalars(q.limit(500)).all()


@router.post("/work-orders", status_code=201)
def create_work_order(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.MAINTENANCE, Role.ADMIN))):
    seq = (db.scalar(select(func.count()).select_from(WorkOrder)) or 0)+1
    data = dict(payload); row = WorkOrder(work_order_id=f"WO-{date.today().year}-{seq:06d}", **data)
    db.add(row); audit(db, "WorkOrder", row.work_order_id, "CREATE", user.username); db.commit(); db.refresh(row); return row


@router.patch("/work-orders/{work_order_id}")
def update_work_order(work_order_id: str, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.MAINTENANCE, Role.ADMIN))):
    row = db.get(WorkOrder, work_order_id)
    if not row: raise HTTPException(404, "Work order not found")
    allowed = {"status", "priority", "assigned_to", "scheduled_start", "started_at", "completed_at", "downtime_minutes", "description"}
    for key, val in payload.items():
        if key not in allowed: raise HTTPException(422, f"Field {key} cannot be updated")
        setattr(row, key, val)
    if row.completed_at and not row.started_at: raise HTTPException(422, "Completed work order requires started_at")
    audit(db, "WorkOrder", work_order_id, "STATUS_CHANGE", user.username, payload); db.commit(); return row


@router.get("/impact-assessments")
def assessments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(ImpactAssessment).order_by(ImpactAssessment.affected_from.desc()).limit(500)).all()


@router.post("/impact-assessments", status_code=201)
def create_assessment(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.QUALITY, Role.ADMIN))):
    row = ImpactAssessment(**payload, reviewer=user.username)
    db.add(row); db.flush(); audit(db, "ImpactAssessment", row.assessment_id, "CREATE", user.username); db.commit(); db.refresh(row); return row


@router.get("/corrective-actions")
def corrective_actions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(CorrectiveAction).order_by(CorrectiveAction.due_date)).all()


@router.post("/corrective-actions", status_code=201)
def create_corrective_action(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.MAINTENANCE, Role.QUALITY, Role.ADMIN))):
    row = CorrectiveAction(**payload); db.add(row); db.flush(); audit(db, "CorrectiveAction", row.action_id, "CREATE", user.username); db.commit(); db.refresh(row); return row


@router.get("/alerts")
def alerts(status: str | None = None, severity: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Alert).order_by(Alert.created_at.desc())
    if status: q = q.where(Alert.status == status)
    if severity: q = q.where(Alert.severity == severity)
    return db.scalars(q.limit(500)).all()


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.QUALITY, Role.MAINTENANCE, Role.ADMIN))):
    row = db.get(Alert, alert_id)
    if not row: raise HTTPException(404, "Alert not found")
    row.status = "ACKNOWLEDGED"; row.acknowledged_at = datetime.now(timezone.utc); audit(db, "Alert", str(alert_id), "STATUS_CHANGE", user.username, {"status": row.status}); db.commit(); return row


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.QUALITY, Role.ADMIN))):
    row = db.get(Alert, alert_id)
    if not row: raise HTTPException(404, "Alert not found")
    row.status = "RESOLVED"; row.resolved_at = datetime.now(timezone.utc); row.resolved_by = user.username; row.resolution_notes = payload.get("resolution_notes", "")
    audit(db, "Alert", str(alert_id), "STATUS_CHANGE", user.username, {"status": row.status}, row.resolution_notes); db.commit(); return row


@router.post("/exceptions", status_code=201)
def request_exception(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.MAINTENANCE, Role.QUALITY, Role.ADMIN))):
    data = dict(payload); data["requested_by"] = user.username; data["status"] = "PENDING"; row = CalibrationException(**data)
    if row.expires_at <= row.effective_from: raise HTTPException(422, "Exception expiry must follow its start")
    db.add(row); db.flush(); audit(db, "CalibrationException", row.exception_id, "CREATE", user.username, {"status": "PENDING"}); db.commit(); db.refresh(row); return row


@router.post("/exceptions/{exception_id}/approve")
def approve_exception(exception_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.QUALITY, Role.ADMIN))):
    row = db.get(CalibrationException, exception_id)
    if not row: raise HTTPException(404, "Exception not found")
    row.status = "APPROVED"; row.approved_by = user.username; audit(db, "CalibrationException", exception_id, "APPROVE", user.username, {"status": "APPROVED"}); db.commit(); return row


@router.post("/exceptions/{exception_id}/reject")
def reject_exception(exception_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.QUALITY, Role.ADMIN))):
    row = db.get(CalibrationException, exception_id)
    if not row: raise HTTPException(404, "Exception not found")
    row.status = "REJECTED"; row.approved_by = user.username; audit(db, "CalibrationException", exception_id, "REJECT", user.username); db.commit(); return row


@router.get("/audit-records")
def audit_records(entity_type: str | None = None, entity_id: str | None = None, actor_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN, Role.QUALITY))):
    q = select(AuditRecord).order_by(AuditRecord.event_timestamp.desc())
    if entity_type: q = q.where(AuditRecord.entity_type == entity_type)
    if entity_id: q = q.where(AuditRecord.entity_id == entity_id)
    if actor_id: q = q.where(AuditRecord.actor_id == actor_id)
    return db.scalars(q.limit(1000)).all()


@router.post("/validation/run")
def run_validation(db: Session = Depends(get_db), user: User = Depends(require_roles(Role.ADMIN, Role.QUALITY))):
    from generator.validate import validate_database
    return validate_database(db)


@router.get("/validation/results")
def validation_results(user: User = Depends(require_roles(Role.ADMIN, Role.QUALITY))):
    path = Path("data/generated/validation_summary.json")
    if not path.exists(): raise HTTPException(404, "No generated validation summary exists")
    import json
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/reports/compliance")
def compliance_report(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return dashboard(db, user)


@app.get("/health")
def health(): return {"status": "ok"}

app.include_router(router)
