from fastapi import FastAPI, Response, Request
from prometheus_client import Histogram, Counter, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime
from io import BytesIO
from PIL import Image
import time

app = FastAPI()

IMAGE_RESIZE_COLD_STARTS = Counter(
    "image_resize_cold_starts_total",
    "Cold starts for image-resize pods"
)

IMAGE_RESIZE_REQUEST_DURATION = Histogram(
    "image_resize_request_duration_seconds",
    "Request duration for image-resize",
    ["method", "handler"],
)

IMAGE_RESIZE_COLD_STARTS.inc()

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    # Avoid counting /metrics itself
    if request.url.path == "/metrics":
        return await call_next(request)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    IMAGE_RESIZE_REQUEST_DURATION.labels(
        method=request.method.lower(),
        handler=request.url.path,
    ).observe(elapsed)

    return response

def create_sample_image():
    # Generate a simple in-memory RGB image (e.g. 400x400 red square)
    img = Image.new("RGB", (400, 400), color=(255, 0, 0))
    return img


@app.get("/")
def resize_image():
    now = datetime.utcnow().isoformat() + "Z"

    # Original image
    img = create_sample_image()
    original_size = img.size  # (width, height)

    # Resize to a smaller thumbnail
    resized = img.resize((100, 100))
    resized_size = resized.size

    # Exercise encoding path
    buf = BytesIO()
    resized.save(buf, format="JPEG")
    encoded_bytes = buf.getvalue()

    return {
        "service": "image-resize",
        "timestamp": now,
        "original_size": {"width": original_size[0], "height": original_size[1]},
        "resized_size": {"width": resized_size[0], "height": resized_size[1]},
        "encoded_bytes": len(encoded_bytes),
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)