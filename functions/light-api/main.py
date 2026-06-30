from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from datetime import datetime
from prometheus_client import Histogram, generate_latest, CONTENT_TYPE_LATEST, Counter
import time

app = FastAPI()

# Define a counter for cold starts
COLD_STARTS = Counter(
    "light_api_cold_starts_total",
    "Cold starts for light-api pods"
)

# Increment once when the module is imported (per pod process)
COLD_STARTS.inc()

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests in seconds",
    ["method", "handler"]
)

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    REQUEST_LATENCY.labels(
        method=request.method.lower(),
        handler=request.url.path,
    ).observe(elapsed)
    return response

@app.get("/")
def read_root():
    now = datetime.utcnow().isoformat() + "Z"
    return {"service": "light-api", "timestamp": now}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)