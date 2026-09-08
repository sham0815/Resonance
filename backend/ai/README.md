# AI / Soil Moisture Prediction

This backend-only feature predicts soil moisture at an unsampled location from its local coordinates, soil type, ambient humidity, probe depth, and time since irrigation. It predicts only `soil_moisture_pct`; it does not infer NPK, pH, yield, disease, navigation, treatments, or control rover hardware. A physical `SENSOR` reading is always retained independently and is never overwritten by a prediction.

## Flow

```
ESP32 SENSOR telemetry → FastAPI raw-record persistence → context resolution
                                                    → threadpool Random Forest
                                                    → ML_MODEL JSONL record + AI websocket topic
```

Only telemetry whose `source` is exactly `SENSOR` can enter the prediction path. `ML_MODEL` records publish as `AI_SOIL_MOISTURE_PREDICTION`, a distinct path which never feeds telemetry ingestion.

## Train

From `backend/`, install requirements and run:

```bash
python -m ai.training.generate_synthetic_data
python -m ai.training.train_model
```

This deterministically creates `data/synthetic/soil_moisture_dataset.csv` (2,000 balanced rows) and writes the bundled sklearn pipeline to `ai/model/soil_moisture_model.joblib`. The model is `rf_v1`; bump that constant in `ai/constants.py` when shipping a deliberately versioned replacement. Set `SOIL_MOISTURE_MODEL_PATH` to override the default model path.

## API

`POST /ai/predict-soil-moisture` uses the active persisted field context. The request schema is:

```json
{"x_m":4.5,"y_m":12,"soil_type":"loam","humidity_pct":68.2,"depth_mm":150,"hours_since_irrigation":3.5}
```

```bash
curl -X POST http://localhost:8000/ai/predict-soil-moisture -H 'Content-Type: application/json' -d '{"x_m":4.5,"y_m":12,"soil_type":"loam","humidity_pct":68.2,"depth_mm":150,"hours_since_irrigation":3.5}'
```

A successful stored record has `timestamp`, `field_id`, `x_m`, `y_m`, `depth_mm`, `soil_type`, `humidity_pct`, `hours_since_irrigation`, `predicted_moisture_pct`, `source: "ML_MODEL"`, `model_name: "RandomForestRegressor"`, and `model_version: "rf_v1"`. Prediction records are JSONL at `data/ai/soil_moisture_predictions.jsonl`; sensor records are separately stored at `data/ai/soil_moisture_sensor_readings.jsonl`.

If the bundled model is missing or corrupt, startup remains healthy with `AI_UNAVAILABLE`; navigation and ordinary telemetry relay continue, while this endpoint returns HTTP 503.

## Metrics and testing

Latest **Synthetic Dataset Validation** (generated 2026-09-08): MAE 3.040, RMSE 3.787, R² 0.935. These are synthetic-data results, not field-validation claims. Run `python -m pytest tests test_fastapi.py -v` from `backend/`. The frontend soil-type control was intentionally skipped because this task is backend-only.
