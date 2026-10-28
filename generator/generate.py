"""Deterministic synthetic generator. Ground truth is emitted separately from operational inputs."""
import argparse
import csv
import hashlib
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((Path(__file__).with_name("config.json")).read_text(encoding="utf-8"))
TYPES = [
    ("Pressure Transmitter", "bar", -0.10, 0.10),
    ("Temperature Sensor", "°C", -0.50, 0.50),
    ("Flow Meter", "L/min", -1.00, 1.00),
    ("pH Meter", "pH", -0.05, 0.05),
    ("Load Cell", "kg", -0.25, 0.25),
]


def write_rows(folder: Path, name: str, rows: list[dict]):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(rows, sort_keys=True, indent=2, ensure_ascii=False), encoding="utf-8")
    if rows:
        with (folder / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)


def generate(profile: str = "starter", seed: int = 20261022, output_dir: str = "data/generated", config: dict | None = None):
    cfg = config or CONFIG
    counts = cfg["profiles"][profile]
    random.seed(seed)
    if np is not None: np.random.seed(seed)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    start = date.fromisoformat(cfg["start_date"]); end = date.fromisoformat(cfg["end_date"])
    span = max((end - start).days, 1)
    suppliers = [{"supplier_id": f"SUP-{i:03d}", "supplier_name": f"Accredited Calibration Services {i:02d}", "contact_email": f"service{i}@example.test", "accreditation_reference": f"ISO17025-{i:04d}", "accreditation_valid_until": str(end + timedelta(days=365)), "status": "ACTIVE"} for i in range(1, 11)]
    types = [{"instrument_type_id": i, "type_name": t[0], "measurement_unit": t[1], "lower_tolerance": t[2], "upper_tolerance": t[3], "default_calibration_interval_days": random.choice(cfg["interval_days"]), "description": f"Synthetic {t[0]}"} for i, t in enumerate(TYPES, 1)]
    assets=[]; plans=[]
    for i in range(1, counts["assets"]+1):
        typ = types[(i-1) % len(types)]; aid=f"AST-{i:06d}"
        assets.append({"asset_id":aid,"asset_name":f"{typ['type_name']} {i:04d}","serial_number":f"SN-{seed}-{i:06d}","instrument_type_id":typ["instrument_type_id"],"supplier_id":suppliers[(i-1)%len(suppliers)]["supplier_id"],"location":random.choice(cfg["locations"]),"department":random.choice(cfg["departments"]),"criticality":random.choices(cfg["criticality"],[10,45,35,10])[0],"commissioned_at":str(start-timedelta(days=random.randint(30,2000))),"retired_at":"","lifecycle_status":"ACTIVE"})
        interval = random.choice(cfg["interval_days"]); plan_id=i
        plans.append({"plan_id":plan_id,"asset_id":aid,"interval_days":interval,"effective_from":str(start-timedelta(days=interval)),"effective_to":"","acceptance_lower":typ["lower_tolerance"],"acceptance_upper":typ["upper_tolerance"],"certificate_required":True,"use_restriction_policy":"BLOCK"})
    calibrations=[]; certificates=[]; correctives=[]; assessments=[]; work_orders=[]; alerts=[]; audits=[]; batches=[]
    calibration_dates_by_asset={a["asset_id"]:[] for a in assets}
    for i in range(counts["calibrations"]):
        asset=assets[i % len(assets)]; plan=plans[i % len(plans)]; typ=types[asset["instrument_type_id"]-1]
        day=start+timedelta(days=random.randint(0,span)); ref=round(random.uniform(1,100),4)
        error=round(random.gauss(0, (typ["upper_tolerance"]-typ["lower_tolerance"])/7),5)
        # occasional real measurement-driven failures
        if i % 35 == 0: error=typ["upper_tolerance"]*1.8
        measured=round(ref+error,5); outcome="PASS" if typ["lower_tolerance"] <= measured-ref <= typ["upper_tolerance"] else "FAIL"
        aid=asset["asset_id"]; n=sum(1 for d in calibration_dates_by_asset[aid] if d.year==day.year)+1
        cid=f"CAL-{aid}-{day.year}-{n:06d}"; due=day+timedelta(days=plan["interval_days"])
        row={"calibration_id":cid,"asset_id":aid,"plan_id":plan["plan_id"],"supplier_id":asset["supplier_id"],"calibration_date":str(day),"measured_value":measured,"reference_value":ref,"measurement_error":round(measured-ref,5),"tolerance_limit":max(abs(typ["lower_tolerance"]),abs(typ["upper_tolerance"])),"result":outcome,"next_due_date":str(due),"performed_by":f"tech-{i%30+1:02d}","impact_assessment_required":outcome=="FAIL"}
        calibration_dates_by_asset[aid].append(day); calibrations.append(row)
        certificates.append({"certificate_id":f"CERT-{cid}","calibration_id":cid,"asset_id":aid,"certificate_number":f"CERTNO-{seed}-{i+1:07d}","issue_date":str(day),"valid_until":str(due),"document_uri":"synthetic://certificate","verification_status":"VERIFIED","verified_by":"quality-demo","verified_at":f"{day.isoformat()}T12:00:00+00:00"})
        audits.append({"audit_id":len(audits)+1,"entity_type":"CalibrationEvent","entity_id":cid,"action":"CREATE","actor_id":row["performed_by"],"event_timestamp":f"{day.isoformat()}T12:00:00+00:00","previous_state":"","new_state":json.dumps({"result":outcome},sort_keys=True),"reason":"Synthetic generated calibration","correlation_id":cid})
        if outcome=="FAIL":
            wo_id=f"WO-{day.year}-{len(work_orders)+1:06d}"; work_orders.append({"work_order_id":wo_id,"asset_id":aid,"calibration_id":cid,"work_order_type":"CORRECTIVE_ACTION","priority":"HIGH","status":"OPEN","description":f"Investigate failed calibration {cid}","opened_at":f"{day.isoformat()}T12:00:00+00:00","scheduled_start":"","started_at":"","completed_at":"","downtime_minutes":random.randint(15,600),"assigned_to":"maintenance-demo"})
            assessments.append({"assessment_id":f"IA-{cid}","calibration_id":cid,"affected_from":f"{day.isoformat()}T00:00:00+00:00","affected_to":f"{day.isoformat()}T23:59:59+00:00","affected_batch_ids":"[]","risk_evaluation":"Assess uses since prior known-good calibration","disposition":"Pending review","reviewer":"","status":"REQUIRED"})
            alerts.append({"alert_id":len(alerts)+1,"asset_id":aid,"calibration_id":cid,"use_id":"","alert_type":"FAILED_CALIBRATION","severity":"HIGH","description":f"Calibration {cid} failed","status":"OPEN","created_at":f"{day.isoformat()}T12:00:00+00:00"})
            correctives.append({"action_id":f"CA-{cid}","calibration_id":cid,"root_cause":"Pending investigation","measures":"Containment and root-cause analysis required","owner":"maintenance-demo","due_date":str(day+timedelta(days=14)),"status":"OPEN","closure_evidence":""})
    batches=[]
    for i in range(1, max(1, counts["production_uses"]//20)+1):
        bday=start+timedelta(days=random.randint(0,span)); batches.append({"batch_id":f"BATCH-{bday.year}-{i:07d}","started_at":f"{bday.isoformat()}T08:00:00+00:00","ended_at":f"{bday.isoformat()}T16:00:00+00:00","status":"COMPLETED","disposition":"RELEASED"})
    # Use the latest calibration before each event; results are derived from historical records.
    cal_by_asset={a["asset_id"]:sorted([r for r in calibrations if r["asset_id"]==a["asset_id"]],key=lambda r:r["calibration_date"]) for a in assets}
    uses=[]
    for i in range(counts["production_uses"]):
        asset=assets[random.randrange(len(assets))]; aid=asset["asset_id"]; moment=datetime.combine(start+timedelta(days=random.randint(0,span)),datetime.min.time(),timezone.utc)+timedelta(minutes=random.randint(0,1439))
        hist=[c for c in cal_by_asset[aid] if datetime.fromisoformat(c["calibration_date"]).date() <= moment.date()]
        latest=hist[-1] if hist else None
        decision="BLOCKED" if not latest or latest["result"]!="PASS" or moment.date()>date.fromisoformat(latest["next_due_date"]) else "ALLOWED"
        reason="No passing calibration as of use" if not latest or latest["result"]!="PASS" else (f"Calibration overdue since {latest['next_due_date']}" if decision=="BLOCKED" else f"Passing calibration {latest['calibration_id']} valid through {latest['next_due_date']}")
        bid=batches[i%len(batches)]["batch_id"] if batches else ""
        uses.append({"use_id":f"USE-{aid}-{moment.strftime('%Y%m%dT%H%M%S%fZ')}-{i:06d}","asset_id":aid,"production_batch_id":bid,"used_at":moment.isoformat(),"duration_minutes":random.randint(1,120),"production_status":"COMPLETED","calibration_status_at_use":"NO_CALIBRATION" if not latest else latest["result"],"decision":decision,"exception_id":"","decision_reason":reason})
    # Isolated anomaly records, each indexed in ground truth and detectable via validation.
    ground=[]
    if calibrations:
        c=calibrations[0]; plan=plans[c["plan_id"]-1]; expected=date.fromisoformat(c["calibration_date"])+timedelta(days=plan["interval_days"]); observed=expected+timedelta(days=3); c["next_due_date"]=str(observed)
        for cert in certificates:
            if cert["calibration_id"] == c["calibration_id"]: cert["valid_until"] = str(observed)
        ground.append({"case_id":"ANOM-001","entity_type":"CalibrationEvent","entity_id":c["calibration_id"],"issue_type":"DUE_DATE_MISMATCH","severity":"HIGH","expected_decision":"DETECTED","expected_value":str(expected),"observed_value":str(observed),"injected_at":f"{end.isoformat()}T23:59:00+00:00","explanation":"Stored due date differs from plan-derived date"})
    expired=next((u for u in uses if u["decision"]=="BLOCKED"),None)
    if expired:
        ground.append({"case_id":"ANOM-002","entity_type":"ProductionUse","entity_id":expired["use_id"],"issue_type":"EXPIRED_USE_WITHOUT_EXCEPTION","severity":"HIGH","expected_decision":"BLOCKED","expected_value":"BLOCKED","observed_value":expired["decision"],"injected_at":expired["used_at"],"explanation":"Use occurred outside calibration interval without applicable approved exception"})
    if len(assets)>1 and certificates:
        cert=certificates[-1]; wrong=assets[0]["asset_id"]
        if cert["asset_id"]==wrong: wrong=assets[1]["asset_id"]
        cert["asset_id"]=wrong
        ground.append({"case_id":"ANOM-003","entity_type":"Certificate","entity_id":cert["certificate_id"],"issue_type":"CERTIFICATE_WRONG_ASSET","severity":"CRITICAL","expected_decision":"DETECTED","expected_value":cert["calibration_id"],"observed_value":wrong,"injected_at":f"{end.isoformat()}T23:59:00+00:00","explanation":"Certificate asset differs from calibration event asset"})
    fail=next((c for c in calibrations if c["result"]=="FAIL"),None)
    if fail:
        assessments[:]=[a for a in assessments if a["calibration_id"]!=fail["calibration_id"]]
        ground.append({"case_id":"ANOM-004","entity_type":"CalibrationEvent","entity_id":fail["calibration_id"],"issue_type":"MISSING_IMPACT_ASSESSMENT","severity":"HIGH","expected_decision":"DETECTED","expected_value":"ImpactAssessment required","observed_value":"missing","injected_at":f"{end.isoformat()}T23:59:00+00:00","explanation":"Failed calibration lacks its required impact assessment"})
    collections={"suppliers":suppliers,"instrument_types":types,"assets":assets,"calibration_plans":plans,"calibrations":calibrations,"certificates":certificates,"work_orders":work_orders,"production_batches":batches,"production_uses":uses,"alerts":alerts,"impact_assessments":assessments,"corrective_actions":correctives,"audit_records":audits,"ground_truth":ground}
    for name, rows in collections.items(): write_rows(out,name,rows)
    # SQL seed export is intentionally raw synthetic data; application schema migrations remain authoritative.
    (out/"seed.sql").write_text("-- Synthetic CalibraTrack seed export. Apply schema migrations before import.\n",encoding="utf-8")
    checksums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*.json"))}
    summary={"seed":seed,"profile":profile,"row_counts":{k:len(v) for k,v in collections.items()},"checksums":checksums,"expected_anomaly_counts":{x["issue_type"]:1 for x in ground},"generated_at":"deterministic-from-config"}
    (out/"validation_summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2),encoding="utf-8")
    (out/"source_manifest.md").write_text("# Source manifest\n\nAll records are synthetic and generated locally with a fixed seed. No external dataset was used.\n",encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--profile",choices=["starter","full"],default="starter"); parser.add_argument("--seed",type=int,default=20261022); parser.add_argument("--output-dir",default="data/generated")
    args=parser.parse_args(); print(json.dumps(generate(args.profile,args.seed,args.output_dir),indent=2))
