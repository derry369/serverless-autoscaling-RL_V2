#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# End-to-end experiment script:
# - Build & push Docker images
# - Deploy Knative services
# - Debug with kubectl (pods, logs, describe)
# - Run bursty injector
# - Export Prometheus metrics to CSV
#
# Adjust image tags, injector args, and paths as needed.
# ============================================================

NAMESPACE="default"
PROM_URL="http://localhost:9090"     # Prometheus HTTP endpoint
PATTERN="bursty_15min"

# -------------------------------
# 0. Docker: build & push images
# -------------------------------

echo "=== Building & pushing Docker images ==="

# light-api image
docker build -t derry369/light-api:phase2 .
docker push derry369/light-api:phase2

# ml-inference image (with histogram middleware)
docker build -t derry369/ml-inference:phase2-histogram .
docker push derry369/ml-inference:phase2-histogram

# long-task image (with histogram middleware)
docker build -t derry369/long-task:phase2-histogram .
docker push derry369/long-task:phase2-histogram

# -------------------------------
# 1. Deploy Knative services
# -------------------------------

echo "=== Deploying Knative services ==="

kubectl apply -f light-api-ksvc.yaml
kubectl apply -f ml-inference-ksvc.yaml
kubectl apply -f long-task-ksvc.yaml

kubectl wait kservice/light-api     --for=condition=Ready -n "$NAMESPACE" --timeout=600s
kubectl wait kservice/ml-inference  --for=condition=Ready -n "$NAMESPACE" --timeout=600s
kubectl wait kservice/long-task     --for=condition=Ready -n "$NAMESPACE" --timeout=600s

echo
kubectl get kservice -n "$NAMESPACE"
kubectl get pods -n "$NAMESPACE" -o wide

# -------------------------------
# 2. Debugging helpers (kubectl)
# -------------------------------

echo
echo "=== Debugging pods (optional checks) ==="

# Example: ml-inference pod debugging
ML_POD=$(kubectl get pods -n "$NAMESPACE" | grep ml-inference | awk '{print $1}')

echo "# Describe ml-inference pod"
kubectl describe pod "$ML_POD" -n "$NAMESPACE"

echo
echo "# Logs (current) for ml-inference"
kubectl logs "$ML_POD" -n "$NAMESPACE" --all-containers=true

echo
echo "# Logs (previous) for ml-inference (if restarted)"
kubectl logs "$ML_POD" -n "$NAMESPACE" --previous --all-containers=true || true

# You can repeat similar blocks for light-api and long-task when needed.

# -------------------------------
# 3. Quick curl checks
# -------------------------------

echo
echo "=== Curl checks for services ==="

curl -v "http://light-api.default.127.0.0.1.sslip.io/"
curl -v "http://ml-inference.default.127.0.0.1.sslip.io/"
curl -v "http://long-task.default.127.0.0.1.sslip.io/?duration_seconds=5"

curl "http://ml-inference.default.127.0.0.1.sslip.io/metrics" | head
curl "http://long-task.default.127.0.0.1.sslip.io/metrics" | head

# -------------------------------
# 4. Bursty injector run
# -------------------------------

echo
echo "=== Running bursty injector for ml-inference (15 min) ==="

# Record run start time (epoch seconds)
START=$(date +%s)
echo "Run start: $START"

# Example injector command — adjust to your real one:
# Replace this with the actual script / binary you’ve been using.
python3 injector_bursty.py \
  --target-url "http://ml-inference.default.127.0.0.1.sslip.io/" \
  --pattern "$PATTERN" \
  --duration-seconds 900

# Record run end time
END=$(date +%s)
echo "Run end:   $END"

# -------------------------------
# 5. Export metrics (Python script)
# -------------------------------

echo
echo "=== Exporting Prometheus metrics for ml-inference ==="

# This assumes you have ml_inf_export.py as we discussed,
# taking --start, --end, --pattern and writing CSVs.
python3 ml_inf_export.py \
  --start "$START" \
  --end "$END" \
  --pattern "$PATTERN"

echo
echo "CSV files produced for ml-inference (expected):"
echo "  p99_ml_inference_${PATTERN}.csv"
echo "  rate_ml_inference_${PATTERN}.csv"
echo "  pods_ml_inference_${PATTERN}.csv"
echo "  cold_starts_ml_inference_${PATTERN}.csv"

# You can repeat similar export calls for light-api and long-task
# using equivalent Python scripts (light_api_export.py, long_task_export.py)
# wired to their respective metrics.

echo
echo "=== Experiment script completed ==="


# For ml-inference
python3 export_unified.py \
  --service ml-inference \
  --start "$START" \
  --end "$END" \
  --pattern bursty_15min

# For light-api
python3 export_unified.py \
  --service light-api \
  --start "$START" \
  --end "$END" \
  --pattern bursty_15min

# For long-task
python3 export_unified.py \
  --service long-task \
  --start "$START" \
  --end "$END" \
  --pattern bursty_15min

# For image-resize
python3 export_unified.py \
  --service image-resize \
  --start "$START" \
  --end "$END" \
  --pattern bursty_15min

# For data-processor
python3 export_unified.py \
  --service data-processor \
  --start "$START" \
  --end "$END" \
  --pattern bursty_15min