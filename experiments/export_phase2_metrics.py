import requests
import csv
import time

PROM_URL = "http://localhost:9090"  # using port-forward; change if you call in-cluster

def query_range(promql, start, end, step="15s"):
    resp = requests.get(
        f"{PROM_URL}/api/v1/query_range",
        params={"query": promql, "start": start, "end": end, "step": step},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["result"]

def query_instant(promql, ts):
    resp = requests.get(
        f"{PROM_URL}/api/v1/query",
        params={"query": promql, "time": ts},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["result"]

def export_timeseries(result, csv_path):
    if not result:
        print(f"No data for {csv_path}")
        return
    series = result[0]  # first series; extend later if needed
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "value"])
        for ts, val in series["values"]:
            writer.writerow([ts, val])

def export_scalar(result):
    if not result:
        return 0.0
    value = result[0]["value"][1]
    return float(value)

def main():
    # Example: 10-minute experiment window, replace with real timestamps
    run_start = int(time.time()) - 600
    run_end = int(time.time())
    step = "15s"

    # PromQL queries
    rate_q = 'sum by (handler) (rate(http_request_duration_seconds_count{app="light-api", handler="/"}[5m]))'
    p99_q = 'histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{app="light-api", handler="/"}[5m])))'
    pod_q = 'sum by (namespace) (kube_pod_status_phase{phase="Running", namespace="default", pod=~"light-api-.*"})'
    cold_q = 'increase(light_api_cold_starts_total[10m])'

    # Range queries
    rate_ts = query_range(rate_q, run_start, run_end, step)
    p99_ts = query_range(p99_q, run_start, run_end, step)
    pod_ts = query_range(pod_q, run_start, run_end, step)

    export_timeseries(rate_ts, "rate_light_api_bursty.csv")
    export_timeseries(p99_ts, "p99_light_api_bursty.csv")
    export_timeseries(pod_ts, "pods_light_api_bursty.csv")

    # Cold starts as scalar
    cold_res = query_instant(cold_q, run_end)
    cold_count = export_scalar(cold_res)
    with open("cold_starts_light_api_bursty.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["run_start", "run_end", "cold_starts"])
        writer.writerow([run_start, run_end, cold_count])

if __name__ == "__main__":
    main()