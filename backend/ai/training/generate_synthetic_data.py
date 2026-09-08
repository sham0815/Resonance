"""Generate deterministic, balanced synthetic soil-moisture training data."""

from pathlib import Path

import numpy as np
import pandas as pd

from ai.constants import SUPPORTED_SOIL_TYPES


OUTPUT_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "soil_moisture_dataset.csv"
SEED = 42
# These approximate relative water retention: clay has many fine pores while sandy soil drains quickly.
RETENTION_MULTIPLIERS = {"clay": 1.4, "silt": 1.2, "loam": 1.0, "red_soil": 0.9, "sandy": 0.6}


def generate_dataset(rows_per_soil_type: int = 400) -> pd.DataFrame:
    """Return a deterministic synthetic dataset with nonlinear irrigation decay."""
    rng = np.random.default_rng(SEED)
    rows = []
    for soil_type in SUPPORTED_SOIL_TYPES:
        for _ in range(rows_per_soil_type):
            x_m, y_m = rng.uniform(0, 100, size=2)
            humidity_pct = rng.uniform(20, 100)
            depth_mm = rng.uniform(25, 300)
            hours = rng.uniform(0, 168)
            # Exponential decay encodes drying after irrigation; spatial and depth terms add realistic variation.
            base = 55 * np.exp(-hours / 72) * RETENTION_MULTIPLIERS[soil_type]
            moisture = base + humidity_pct * 0.18 + depth_mm * 0.015 + 3 * np.sin(x_m / 15) * np.cos(y_m / 15)
            moisture += rng.normal(0, 3.0)  # bounded after noise as required.
            rows.append({"x_m": x_m, "y_m": y_m, "soil_type": soil_type, "humidity_pct": humidity_pct,
                         "depth_mm": depth_mm, "hours_since_irrigation": hours,
                         "soil_moisture_pct": float(np.clip(moisture, 0, 100))})
    return pd.DataFrame(rows)


def main() -> None:
    """Write the standard 2,000-row CSV dataset to the backend data directory."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    generate_dataset().to_csv(OUTPUT_PATH, index=False)


if __name__ == "__main__":
    main()
