# Phase 2 – Reactive Baseline and Observability Lab

## Overview

Phase 2 focused on building a **reactive baseline** for several FastAPI functions running on Knative, and instrumenting them with Prometheus so we could measure p99 latency, request rates, pod counts, and cold starts. The goal was to understand how services behave under load *without* forecasting-based pre-warming, so that Phase 3’s LSTM controller has a clear comparison point. [web:1773][web:1780]

We worked with five services:

- `light-api`
- `ml-inference`
- `long-task`
- `image-resize`
- `data-processor`

Each was deployed as a Knative service in a Kind cluster, with a `/metrics` endpoint and Prometheus scraping.

---

## Services and Metrics: Making Everything Uniform

### Initial state

At the start of Phase 2:

- Some services only exposed a **cold-start counter**.
- Others had ad-hoc latency metrics (like a generic `http_request_duration_seconds` for `light-api`).
- Not all services had a consistent histogram for request duration, making it hard to export p99 and rate in a unified way. [web:1691][web:1703]

### The uniform observability pattern

We gradually converged all five functions to a common observability pattern:

1. **Cold-start counter** per service:
   - `light_api_cold_starts_total`
   - `ml_inference_cold_starts_total`
   - `long_task_cold_starts_total`
   - `image_resize_cold_starts_total`
   - `data_processor_cold_starts_total`

   Each counter is incremented once per pod process at module import time, giving a simple way to count cold starts. [web:1716]

2. **Request-duration histogram** per service:
   - `light_api_request_duration_seconds`
   - `ml_inference_request_duration_seconds`
   - `long_task_request_duration_seconds`
   - `image_resize_request_duration_seconds`
   - `data_processor_request_duration_seconds`

   All histograms share the same labels: `method` and `handler`. This allows us to query p99 and rate per HTTP path and method using uniform PromQL. [web:1707][web:1715]

3. **Middleware-based instrumentation**:
   - Each FastAPI app now has a `@app.middleware("http")` that:
     - Skips `/metrics` requests (so scraping doesn’t skew latency).
     - Measures request duration with `time.perf_counter()`.
     - Records the observation with `.labels(method=request.method.lower(), handler=request.url.path).observe(elapsed)` into the service-specific histogram. [web:1691][web:1694]

4. **Metrics endpoint**:
   - Every service exposes `/metrics` returning `generate_latest()` with `CONTENT_TYPE_LATEST`, so Prometheus can scrape all metrics in a consistent format. [web:1703]

This uniformity was essential to support a single export script for all services later on.

---

## Errors Encountered and How They Were Fixed

### 1. Pods in `Error` state and internal server errors

At one point, the `ml-inference` pod showed `0/2 Error` with multiple restarts, and `curl` calls returned `500 Internal Server Error`. This indicated crashes during startup or request handling. [web:1602][web:1615]

**Diagnosis:**

- Used `kubectl describe pod <pod> -n default` to inspect events and exit codes.
- Viewed logs with:
  - `kubectl logs <pod> -n default --all-containers=true`
  - `kubectl logs <pod> -n default --previous` (after restarts).

We looked for:

- Missing imports (e.g., `Request` from FastAPI, `time`).
- Name errors (histogram used before definition).
- Issues with `prometheus_client` import or installation.
- Tracebacks from the new middleware code.

**Fixes:**

- Ensured correct imports:

  ```python
  from fastapi import FastAPI, Response, Request
  import time
  from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
  ```

- Defined histograms and counters **before** the middleware and route functions.
- Confirmed `prometheus-client` was installed in the image (via `requirements.txt` and rebuild).
- Rebuilt and pushed updated Docker images for the affected services, then redeployed Knative services and waited for Ready status.

After these fixes, pods went to `2/2 Running` and `curl` to `/` and `/metrics` succeeded without errors.

### 2. Inconsistent metric names and labels

Originally, `light-api` used a generic `http_request_duration_seconds` histogram. Other services used per-service names like `ml_inference_request_duration_seconds`. This made cross-service PromQL and export scripts harder to keep consistent. [web:1714]

**Fixes:**

- Renamed `REQUEST_LATENCY` in `light-api` to `light_api_request_duration_seconds`.
- Standardized labels to `["method", "handler"]` across all services.
- Updated middleware to set `.labels(method=request.method.lower(), handler=request.url.path)` everywhere.

Now a single PromQL template works for all services.

### 3. Export script argument issues

The original export script failed with `argument --start: expected one argument` when running:

```bash
python3 ml_inf_export.py --start $START --end $END --pattern bursty_15min
```

**Diagnosis and fix:**

- `START` or `END` environment variables were empty, so argparse saw the flag but no value. We checked with `echo "$START"` / `echo "$END"`. [web:1622][web:1623]
- Ensured `START` and `END` were set using `date +%s` around injector runs, and passed them quoted:
  ```bash
  python3 ml_inf_export.py --start "$START" --end "$END" --pattern "$PATTERN"
  ```

This resolved the argparse issue and allowed CSV export.

---

## Exporting Metrics: From Service-Specific to Universal

### Service-specific exporter (ml-inference)

Initially, we had a script tailored to `ml-inference`:

- Request rate:

  ```promql
  sum by (handler) (
    rate(ml_inference_request_duration_seconds_count{handler="/"}[5m])
  )
  ```

- p99 latency:

  ```promql
  histogram_quantile(
    0.99,
    sum by (le) (
      rate(ml_inference_request_duration_seconds_bucket{handler="/"}[5m])
    )
  )
  ```

- Pod count:

  ```promql
  sum by (namespace) (
    kube_pod_status_phase{
      phase="Running",
      namespace="default",
      pod=~"ml-inference-.*"
    }
  )
  ```

- Cold starts:

  ```promql
  increase(ml_inference_cold_starts_total[10m])
  ```

The script queried Prometheus (`/api/v1/query_range` and `/api/v1/query`), then wrote CSVs for p99, rate, pods, and cold starts over a given `[START, END]` window. [web:1714]

### Universal exporter for all five services

To avoid duplication, we generalized the script:

- Added `--service` argument.
- Mapped `service` to:
  - `hist_metric` (e.g., `light_api_request_duration_seconds`)
  - `cold_metric` (e.g., `light_api_cold_starts_total`)
  - `pod_regex` (e.g., `light-api-.*`).

PromQL strings now use these parameters, and filenames are generated like:

- `p99_<service>_<pattern>.csv`
- `rate_<service>_<pattern>.csv`
- `pods_<service>_<pattern>.csv`
- `cold_starts_<service>_<pattern>.csv`

This unified exporter completes the observability story for phase 2 and prepares clean inputs for phase 3’s forecasting experiments. [web:1716]

---

## Baseline Experiment Plan for Phase 3 Comparison

To give Phase 3 a **solid, fair baseline**, Phase 2 concludes with a small set of standard runs on `ml-inference` (and optionally other services). These runs capture both “easy” and “hard” reactive behavior.

### 1. Bursty 15-minute baseline (`bursty_15min_baseline`)

**Purpose:** Show how the system behaves under a moderate, smooth burst with reactive scaling only. This is a case where forecasting might not change much, but is important for showing it doesn’t hurt stable scenarios.

**Pattern (example):**

- Minutes 0–15: request rate follows a bursty pattern (gradual ramp up to a moderate level, then down).

**Procedure:**

1. Run injector:

   ```bash
   START=$(date +%s)
   python3 injector_bursty.py \
     --target-url "http://ml-inference.default.127.0.0.1.sslip.io/" \
     --pattern bursty_15min \
     --duration-seconds 900
   END=$(date +%s)
   ```

2. Export metrics:

   ```bash
   python3 export_unified.py \
     --service ml-inference \
     --start "$START" \
     --end "$END" \
     --pattern bursty_15min_baseline
   ```

**Expected baseline behavior (based on earlier run):**

- Pods: stay at 1.
- Cold starts: only the initial one.
- p99: around ~5 ms, flat, even as rate moves from ~1.4 to ~5+ req/s.  
This becomes the **“good” reactive baseline** for comparison.

### 2. Spike 15-minute baseline (`spike_15min_baseline`)

**Purpose:** Create a “hard” scenario where reactive scaling struggles, leading to multiple cold starts and p99 spikes—ideal for showing the benefit of LSTM-based pre-warming. [web:1724][web:1736]

**Pattern (example):**

- Minutes 0–5: low load (~0.5–1 req/s).
- Minutes 5–6: rapid ramp up to high load (~8–10 req/s).
- Minutes 6–12: hold high load (~8–10 req/s).
- Minutes 12–15: drop back to low load.

**Procedure:**

1. Run injector with spike pattern, **without** LSTM controller:

   ```bash
   START=$(date +%s)
   python3 injector_spike.py \
     --target-url "http://ml-inference.default.127.0.0.1.sslip.io/" \
     --pattern spike_15min \
     --duration-seconds 900
   END=$(date +%s)
   ```

2. Export metrics:

   ```bash
   python3 export_unified.py \
     --service ml-inference \
     --start "$START" \
     --end "$END" \
     --pattern spike_15min_baseline
   ```

**Desired baseline effects:**

- p99 latency spikes around and shortly after the load spike.
- Cold starts > 1 as new pods come up under pressure.
- Pod count curve that lags behind the spike (scaling only after thresholds are breached). [web:1722][web:1740]

This becomes the **“poor/challenging” reactive baseline** that Phase 3’s LSTM pre-warming aims to improve.

### 3. Optional ramp baseline (`ramp_15min_baseline`)

If time allows, a third pattern can show a more gradual but still challenging scenario:

- Load increases steadily over the 15 minutes.
- Autoscaling may be in a constant catch-up mode.

Run and export analogously:

```bash
START=$(date +%s)
python3 injector_ramp.py \
  --target-url "http://ml-inference.default.127.0.0.1.sslip.io/" \
  --pattern ramp_15min \
  --duration-seconds 900
END=$(date +%s)

python3 export_unified.py \
  --service ml-inference \
  --start "$START" \
  --end "$END" \
  --pattern ramp_15min_baseline
```

This gives Phase 3 a third comparison point.

---

## Key Baseline Observations (Example: ml-inference, Bursty 15 Minutes)

For the 15-minute bursty pattern on `ml-inference`:

- Pods: stayed at 1 the whole time.
- Cold starts: only 1 (initial pod start).
- p99 latency: ~4.95 ms, almost perfectly flat even as request rate ramped up and down.
- Rate: increased from ~1.4 req/s up to ~5.3 req/s and then tapered down, tracking the burst pattern. [conversation_history:1]

This shows `ml-inference` is very stable under this moderate burst, giving us a **“good” reactive baseline** where LSTM may not dramatically improve QoS, but can still be evaluated.

The spike and (optionally) ramp baselines are expected to show more stress: increased cold starts and p99 spikes, providing a **contrast** that Phase 3 forecasting can improve upon. [web:1724][web:1736]

---

## Phase 2 Summary

Phase 2 achieved:

- A **uniform observability setup** for five FastAPI services on Knative:
  - Cold-start counters per service.
  - Consistent request-duration histograms.
  - Middleware-based timing and Prometheus-friendly `/metrics` endpoints.
- Resolution of multiple errors:
  - Pod `Error` states and internal server errors via logs and `kubectl describe`.
  - Metric naming and label inconsistencies.
  - Export script argument and environment variable issues.
- Definition of **reactive baseline experiments**:
  - Bursty 15-minute pattern (`bursty_15min_baseline`) for `ml-inference` as a “good” baseline.
  - Spike 15-minute pattern (`spike_15min_baseline`) (and optionally ramp) as “hard” baselines with expected cold starts and p99 spikes.

This sets the stage for Phase 3, where an LSTM trained on Azure traces will drive a forecasting-based controller that pre-warms capacity, allowing direct comparison of cold starts, p99 latency, and pod behavior against these Phase 2 reactive baselines. [web:1761][web:1762][web:1724]