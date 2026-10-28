import argparse
import json
from datetime import date, datetime
from pathlib import Path
from sqlalchemy import Date, DateTime, JSON
from backend.db import Base, engine, SessionLocal
from backend.models import User, Role
from backend.security import hash_password

DATASETS = [
    ("suppliers", "suppliers", "supplier_id"),
    ("instrument_types", "instrument_types", "instrument_type_id"),
    ("assets", "assets", "asset_id"),
    ("calibration_plans", "calibration_plans", "plan_id"),
    ("calibrations", "calibration_events", "calibration_id"),
    ("certificates", "certificates", "certificate_id"),
    ("work_orders", "work_orders", "work_order_id"),
    ("production_batches", "production_batches", "batch_id"),
    ("impact_assessments", "impact_assessments", "assessment_id"),
    ("corrective_actions", "corrective_actions", "action_id"),
    ("production_uses", "production_uses", "use_id"),
    ("alerts", "alerts", "alert_id"),
    ("audit_records", "audit_records", "audit_id"),
]


def import_starter_data(db, folder: Path):
    """Import the deterministic starter exports in foreign-key order; skips existing rows."""
    from backend import models
    total = 0
    for filename, model_name, key in DATASETS:
        # Explicit class mappings avoid inferring model names from irregular plurals.
        model = {
            "suppliers": models.Supplier, "instrument_types": models.InstrumentType,
            "assets": models.Asset, "calibration_plans": models.CalibrationPlan,
            "calibrations": models.CalibrationEvent, "certificates": models.Certificate,
            "work_orders": models.WorkOrder, "production_batches": models.ProductionBatch,
            "impact_assessments": models.ImpactAssessment, "corrective_actions": models.CorrectiveAction,
            "production_uses": models.ProductionUse, "alerts": models.Alert, "audit_records": models.AuditRecord,
        }[filename]
        rows = json.loads((folder / f"{filename}.json").read_text(encoding="utf-8"))
        existing = {row[0] for row in db.query(getattr(model, key)).all()}
        for item in rows:
            if item[key] in existing:
                continue
            values = {}
            for column in model.__table__.columns:
                if column.name not in item:
                    continue
                value = item[column.name]
                if value == "" and column.nullable:
                    value = None
                elif isinstance(column.type, Date) and not isinstance(column.type, DateTime) and isinstance(value, str):
                    value = date.fromisoformat(value)
                elif isinstance(column.type, DateTime) and isinstance(value, str):
                    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                elif isinstance(column.type, JSON) and isinstance(value, str):
                    try: value = json.loads(value)
                    except json.JSONDecodeError: pass
                values[column.name] = value
            db.add(model(**values)); total += 1
        db.flush()
    return total

def seed(with_starter_data=False):
    Base.metadata.create_all(engine)
    db=SessionLocal()
    try:
        for username, role in [("operator",Role.OPERATOR),("maintenance",Role.MAINTENANCE),("quality",Role.QUALITY),("planner",Role.PLANNER),("admin",Role.ADMIN)]:
            if not db.query(User).filter_by(username=username).first(): db.add(User(username=username,role=role,password_hash=hash_password("CalibraTrack-Demo-2026!"),active=True))
        imported = import_starter_data(db, Path("data/generated")) if with_starter_data else 0
        db.commit()
        return imported
    finally: db.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--with-starter-data",action="store_true"); args=parser.parse_args()
    print(f"Imported {seed(args.with_starter_data)} synthetic records.")
