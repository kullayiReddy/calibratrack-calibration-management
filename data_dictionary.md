# Data dictionary

Primary keys are deterministic IDs and are immutable after creation. Nullable fields are marked optional. UTC timestamps are used throughout and calibration intervals count calendar days.

| Entity | Primary key | Relationships and lifecycle |
|---|---|---|
| Asset | `asset_id` (`AST-000001`) | Many assets to one instrument type; optional supplier. Active, under maintenance, or retired. Serial number is unique. |
| InstrumentType | `instrument_type_id` | One type to many assets; tolerance is measurement-error bounds and interval is in calendar days. |
| CalibrationPlan | `plan_id` | Many effective-dated plans per asset, no overlapping ranges enforced by service. Plan changes create new records. |
| CalibrationEvent | `calibration_id` | Many events per asset; each event refers to one plan, optionally one supplier. Result is derived from error and bounds. |
| Certificate | `certificate_id` | Certificate refers to one calibration and one asset; certificate number is unique when present. Asset must agree with event. |
| WorkOrder | `work_order_id` | Many work orders per asset, optional calibration. Completion requires a start time. |
| ProductionUse | `use_id` | Many uses per asset, optional batch and exception; decision records historical evaluation. |
| Supplier | `supplier_id` | One supplier to many assets/calibrations. |
| Alert | `alert_id` | Many alerts per asset, optional calibration or use. Open business keys are deduplicated by service. |
| AuditRecord | `audit_id` | Append-only application events reference an entity by type and ID. |
| ImpactAssessment | `assessment_id` | One assessment per failed calibration; status is independent from work order status. |
| CalibrationException | `exception_id` | Many scoped, time-limited requests per asset. Approval is quality/admin-only. |
| CorrectiveAction | `action_id` | Many corrective actions per calibration with owner, due date, status, and closure evidence. |
| ProductionBatch | `batch_id` | One batch to many production uses; time window is explicit. |
| User | `id` | Unique username, hashed password, one role, active flag. |

Database foreign keys protect core references. Certificate/event asset equality and cross-row temporal constraints are additionally checked in services and validation.
