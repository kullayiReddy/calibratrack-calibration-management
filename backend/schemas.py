from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AssetCreate(BaseModel):
    asset_name: str = Field(min_length=1, max_length=160)
    serial_number: str = Field(min_length=1, max_length=100)
    instrument_type_id: int
    supplier_id: str | None = None
    location: str
    department: str
    criticality: str = "MEDIUM"
    commissioned_at: date


class AssetOut(ORMModel):
    asset_id: str
    asset_name: str
    serial_number: str
    instrument_type_id: int
    location: str
    department: str
    criticality: str
    lifecycle_status: str


class CalibrationCreate(BaseModel):
    asset_id: str
    calibration_date: date
    measured_value: float
    reference_value: float = 0.0
    supplier_id: str | None = None


class ProductionUseCreate(BaseModel):
    asset_id: str
    production_batch_id: str | None = None
    used_at: datetime
    duration_minutes: int = Field(gt=0, le=1440)
    production_status: str = "RUNNING"


class LoginInput(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DecisionOut(BaseModel):
    decision: str
    reason: str
    calibration_id: str | None = None
    exception_id: str | None = None
