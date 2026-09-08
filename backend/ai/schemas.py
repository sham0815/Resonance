"""Pydantic contracts used between the AI API, inference service, and storage."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import MODEL_NAME, MODEL_VERSION


class SoilPredictionInput(BaseModel):
    """Validated numerical and categorical inputs to the Random Forest model."""

    model_config = ConfigDict(extra="forbid")
    x_m: float
    y_m: float
    soil_type: Literal["loam", "sandy", "clay", "silt", "red_soil"]
    humidity_pct: float = Field(ge=0.0, le=100.0)
    depth_mm: float = Field(gt=0.0)
    hours_since_irrigation: float = Field(ge=0.0)

    @field_validator("x_m", "y_m", "humidity_pct", "depth_mm", "hours_since_irrigation")
    @classmethod
    def finite_value(cls, value: float) -> float:
        """Reject NaN and infinite feature values before inference."""
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("value must be finite")
        return value


class PredictionResult(BaseModel):
    """Fixed persisted and broadcast prediction record; timestamps are server-generated UTC."""

    model_config = ConfigDict(protected_namespaces=())
    timestamp: datetime
    field_id: str
    x_m: float
    y_m: float
    depth_mm: float
    soil_type: str
    humidity_pct: float
    hours_since_irrigation: float
    predicted_moisture_pct: float = Field(ge=0.0, le=100.0)
    source: Literal["ML_MODEL"] = "ML_MODEL"
    model_name: str = MODEL_NAME
    model_version: str = MODEL_VERSION
