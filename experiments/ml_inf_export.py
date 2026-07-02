import requests
import csv
import argparse

PROM_URL = "http://localhost:9090"  # adjust if needed

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
    series = result[0]
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True, help="run_start epoch seconds")
    parser.add_argument("--end", type=int, required=True, help="run_end epoch seconds")
    parser.add_argument("--pattern", required=True, help="pattern name, e.g. bursty_15min")
    args = parser.parse_args()

    run_start = args.start
    run_end = args.end
    step = "15s"
    pattern = args.pattern

    # --- PromQL for ml-inference ---

    # Request rate (req/s) over 5-minute windows
    rate_q = '''
    sum by (handler) (
      rate(ml_inference_request_duration_seconds_count{handler="/"}[5m])
    )
    '''.strip()

    # p99 latency using histogram buckets
    p99_q = '''
    histogram_quantile(
      0.99,
      sum by (le) (
        rate(ml_inference_request_duration_seconds_bucket{handler="/"}[5m])
      )
    )
    '''.strip()

    # Pod count (Running ml-inference pods)
    pod_q = '''
    sum by (namespace) (
      kube_pod_status_phase{
        phase="Running",
        namespace="default",
        pod=~"ml-inference-.*"
      }
    )
    '''.strip()

    # Cold starts
    cold_q = 'increase(ml_inference_cold_starts_total[10m])'

    # --- Range queries ---
    rate_ts = query_range(rate_q, run_start, run_end, step)
    p99_ts = query_range(p99_q, run_start, run_end, step)
    pod_ts = query_range(pod_q, run_start, run_end, step)

    export_timeseries(rate_ts, f"rate_ml_inference_{pattern}.csv")
    export_timeseries(p99_ts, f"p99_ml_inference_{pattern}.csv")
    export_timeseries(pod_ts, f"pods_ml_inference_{pattern}.csv")

    # --- Cold starts as scalar ---
    cold_res = query_instant(cold_q, run_end)
    cold_count = export_scalar(cold_res)
    with open(f"cold_starts_ml_inference_{pattern}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["run_start", "run_end", "cold_starts"])
        writer.writerow([run_start, run_end, cold_count])

if __name__ == "__main__":
    main()