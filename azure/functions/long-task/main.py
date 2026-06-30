from fastapi import FastAPI, Query, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime
import time


app = FastAPI()

LONG_TASK_COLD_STARTS = Counter(
    "long_task_cold_starts_total",
    "Cold starts for long-task pods"
)

LONG_TASK_COLD_STARTS.inc()


@app.get("/")
def run_long_task(duration_seconds: float = Query(30.0, ge=0.0, le=300.0)):
    """
    Simulate a long-running task by sleeping for duration_seconds.
    Default: 30 seconds, capped at 300.
    """
    start = datetime.utcnow().isoformat() + "Z"
    time.sleep(duration_seconds)
    end = datetime.utcnow().isoformat() + "Z"

    return {
        "service": "long-task",
        "start": start,
        "end": end,
        "duration_requested": duration_seconds,
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)