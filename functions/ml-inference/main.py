from fastapi import FastAPI, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from datetime import datetime
import torch
import torch.nn as nn


app = FastAPI()

ML_INFERENCE_COLD_STARTS = Counter(
    "ml_inference_cold_starts_total",
    "Cold starts for ml-inference pods"
)

ML_INFERENCE_COLD_STARTS.inc()


# Define a tiny model
class TinyNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(16, 32)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(32, 4)

    def forward(self, x):
        x = self.relu(self.fc1(x))
        return self.fc2(x)


# Load model at startup (cold-start cost)
model = TinyNet()
model.eval()


@app.get("/")
def infer():
    now = datetime.utcnow().isoformat() + "Z"

    with torch.no_grad():
        x = torch.randn(1, 16)
        y = model(x)
        result = y.squeeze(0).tolist()

    return {
        "service": "ml-inference",
        "timestamp": now,
        "output": result,
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)