from fastapi import FastAPI, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime
import pandas as pd
import numpy as np


app = FastAPI()

DATA_PROCESSOR_COLD_STARTS = Counter(
    "data_processor_cold_starts_total",
    "Cold starts for data-processor pods"
)

# Increment once per pod start
DATA_PROCESSOR_COLD_STARTS.inc()


@app.get("/")
def process_data():
    # Simulate a small ETL-style workload
    now = datetime.utcnow().isoformat() + "Z"

    # Create a dummy DataFrame
    df = pd.DataFrame({
        "value": np.random.randn(1000),
        "category": np.random.choice(["A", "B", "C"], size=1000),
    })

    # Simple aggregation
    agg = df.groupby("category")["value"].agg(["mean", "std", "count"]).reset_index()

    # Convert to a JSON-friendly structure
    result = agg.to_dict(orient="records")

    return {
        "service": "data-processor",
        "timestamp": now,
        "summary": result,
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)