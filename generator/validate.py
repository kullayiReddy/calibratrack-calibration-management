import argparse
import json
from pathlib import Path


def validate_files(input_dir: str) -> dict:
    folder=Path(input_dir); result={"row_counts":{},"violations":[],"detected_anomalies":{},"expected_anomalies":{}}
    data={}
    for path in folder.glob("*.json"):
        if path.name in {"validation_summary.json"}: continue
        try:
            rows=json.loads(path.read_text(encoding="utf-8")); data[path.stem]=rows
            if isinstance(rows,list): result["row_counts"][path.stem]=len(rows)
        except json.JSONDecodeError as exc: result["violations"].append(f"Invalid JSON {path.name}: {exc}")
    assets={x["asset_id"] for x in data.get("assets",[])}; cals={x["calibration_id"]:x for x in data.get("calibrations",[])}
    plans={x["plan_id"]:x for x in data.get("calibration_plans",[])}
    for c in data.get("calibrations",[]):
        p=plans.get(c["plan_id"])
        if c["asset_id"] not in assets: result["violations"].append(f"Calibration {c['calibration_id']} has unknown asset")
        if p:
            from datetime import date,timedelta
            expected=date.fromisoformat(c["calibration_date"])+timedelta(days=p["interval_days"])
            if str(expected)!=c["next_due_date"]:
                result["detected_anomalies"]["DUE_DATE_MISMATCH"]=result["detected_anomalies"].get("DUE_DATE_MISMATCH",0)+1
                if c["calibration_id"] not in {x["entity_id"] for x in data.get("ground_truth",[]) if x["issue_type"]=="DUE_DATE_MISMATCH"}: result["violations"].append(f"Unexpected due-date mismatch for {c['calibration_id']}")
    for c in data.get("certificates",[]):
        event=cals.get(c["calibration_id"])
        if not event or c["asset_id"]!=event["asset_id"]:
            result["detected_anomalies"]["CERTIFICATE_WRONG_ASSET"]=result["detected_anomalies"].get("CERTIFICATE_WRONG_ASSET",0)+1
            if c["certificate_id"] not in {x["entity_id"] for x in data.get("ground_truth",[]) if x["issue_type"]=="CERTIFICATE_WRONG_ASSET"}: result["violations"].append(f"Unexpected certificate mismatch for {c['certificate_id']}")
    assessment_ids={x["calibration_id"] for x in data.get("impact_assessments",[])}
    for c in data.get("calibrations",[]):
        if c["result"]=="FAIL" and c["impact_assessment_required"] and c["calibration_id"] not in assessment_ids:
            result["detected_anomalies"]["MISSING_IMPACT_ASSESSMENT"]=result["detected_anomalies"].get("MISSING_IMPACT_ASSESSMENT",0)+1
    for u in data.get("production_uses",[]):
        if u["decision"]=="BLOCKED" and "overdue" in u["decision_reason"].lower() and not u.get("exception_id"):
            result["detected_anomalies"]["EXPIRED_USE_WITHOUT_EXCEPTION"]=result["detected_anomalies"].get("EXPIRED_USE_WITHOUT_EXCEPTION",0)+1; break
    expected_entities={(a["issue_type"],a["entity_id"]) for a in data.get("ground_truth",[])}
    for c in data.get("calibrations",[]):
        if c["result"]=="FAIL" and c["impact_assessment_required"] and c["calibration_id"] not in assessment_ids and ("MISSING_IMPACT_ASSESSMENT",c["calibration_id"]) not in expected_entities:
            result["violations"].append(f"Unexpected missing impact assessment for {c['calibration_id']}")
    for a in data.get("ground_truth",[]): result["expected_anomalies"][a["issue_type"]]=result["expected_anomalies"].get(a["issue_type"],0)+1
    result["ground_truth_evaluation"]={k:{"expected":v,"detected":result["detected_anomalies"].get(k,0),"matched":result["detected_anomalies"].get(k,0)>=v} for k,v in result["expected_anomalies"].items()}
    result["primary_key_violations"]=[]
    key_by_collection={"assets":"asset_id","suppliers":"supplier_id","instrument_types":"instrument_type_id","calibration_plans":"plan_id","calibrations":"calibration_id","certificates":"certificate_id","work_orders":"work_order_id","production_batches":"batch_id","production_uses":"use_id","alerts":"alert_id","impact_assessments":"assessment_id","corrective_actions":"action_id","audit_records":"audit_id","ground_truth":"case_id"}
    for name, rows in data.items():
        if not rows or not isinstance(rows,list): continue
        key=key_by_collection.get(name)
        if key:
            vals=[x[key] for x in rows]
            if len(vals)!=len(set(vals)): result["primary_key_violations"].append(f"Duplicate {key} in {name}")
    result["foreign_key_violations"]=[x for x in result["violations"] if "unknown asset" in x]
    return result


def validate_database(db):
    from sqlalchemy import select
    from backend.models import Asset, CalibrationEvent, Certificate, ProductionUse
    assets=db.scalar(select(Asset).count()) if False else db.query(Asset).count()
    cals=db.query(CalibrationEvent).count(); certs=db.query(Certificate).count(); uses=db.query(ProductionUse).count()
    return {"database_counts":{"assets":assets,"calibrations":cals,"certificates":certs,"production_uses":uses},"violations":[],"note":"Use generator.validate for complete synthetic export validation."}


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--input-dir",default="data/generated"); a=p.parse_args(); result=validate_files(a.input_dir)
    Path(a.input_dir,"validation_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True),encoding="utf-8"); print(json.dumps(result,indent=2))
