"""Train and save the single bundled Random Forest soil-moisture pipeline."""

import json
import logging
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "synthetic" / "soil_moisture_dataset.csv"
MODEL_PATH = ROOT / "ai" / "model" / "soil_moisture_model.joblib"
METRICS_PATH = ROOT / "ai" / "model" / "training_metrics.json"
FEATURES = ["x_m", "y_m", "soil_type", "humidity_pct", "depth_mm", "hours_since_irrigation"]


def train_model() -> dict[str, float]:
    """Train the specified reproducible pipeline and return synthetic validation metrics."""
    dataset = pd.read_csv(DATASET_PATH)
    train_x, test_x, train_y, test_y = train_test_split(dataset[FEATURES], dataset["soil_moisture_pct"], test_size=0.2, random_state=42)
    preprocessing = ColumnTransformer([("soil_type", OneHotEncoder(handle_unknown="ignore"), ["soil_type"]),
                                        ("numeric", "passthrough", ["x_m", "y_m", "humidity_pct", "depth_mm", "hours_since_irrigation"])])
    pipeline = Pipeline([("preprocessing", preprocessing), ("model", RandomForestRegressor(n_estimators=250, max_depth=14, min_samples_leaf=3, random_state=42, n_jobs=-1))])
    pipeline.fit(train_x, train_y)
    predicted = pipeline.predict(test_x)
    metrics = {"label": "Synthetic Dataset Validation", "mae": float(mean_absolute_error(test_y, predicted)),
               "rmse": float(mean_squared_error(test_y, predicted) ** 0.5), "r2": float(r2_score(test_y, predicted))}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    LOGGER.info("Synthetic Dataset Validation: MAE=%.3f RMSE=%.3f R2=%.3f", metrics["mae"], metrics["rmse"], metrics["r2"])
    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train_model()
