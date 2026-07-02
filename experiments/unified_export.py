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


def get_service_config(service: str):
    """
    Map service name to metrics and pod pattern.
    """
    if service == "ml-inference":
        return {
            "hist_metric": "ml_inference_request_duration_seconds",
            "cold_metric": "ml_inference_cold_starts_total",
            "pod_regex": 'ml-inference-.*',
        }
    if service == "light-api":
        return {
            "hist_metric": "light_api_request_duration_seconds",
            "cold_metric": "light_api_cold_starts_total",
            "pod_regex": 'light-api-.*',
        }
    if service == "long-task":
        return {
            "hist_metric": "long_task_request_duration_seconds",
            "cold_metric": "long_task_cold_starts_total",
            "pod_regex": 'long-task-.*',
        }
    if service == "image-resize":
        return {
            "hist_metric": "image_resize_request_duration_seconds",
            "cold_metric": "image_resize_cold_starts_total",
            "pod_regex": 'image-resize-.*',
        }
    if service == "data-processor":
        return {
            "hist_metric": "data_processor_request_duration_seconds",
            "cold_metric": "data_processor_cold_starts_total",
            "pod_regex": 'data-processor-.*',
        }
    raise ValueError(f"Unknown service: {service}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", required=True,
                        help="Service name: ml-inference, light-api, long-task, image-resize, data-processor")
    parser.add_argument("--start", type=int, required=True, help="run_start epoch seconds")
    parser.add_argument("--end", type=int, required=True, help="run_end epoch seconds")
    parser.add_argument("--pattern", required=True, help="pattern name, e.g. bursty_15min")
    args = parser.parse_args()

    service = args.service
    run_start = args.start
    run_end = args.end
    step = "15s"
    pattern = args.pattern

    cfg = get_service_config(service)
    hist_metric = cfg["hist_metric"]
    cold_metric = cfg["cold_metric"]
    pod_regex = cfg["pod_regex"]

    # --- PromQL for given service ---

    # Request rate (req/s) over 5-minute windows
    rate_q = f'''
    sum by (handler) (
      rate({hist_metric}_count{{handler="/"}}[5m])
    )
    '''.strip()

    # p99 latency using histogram buckets
    p99_q = f'''
    histogram_quantile(
      0.99,
      sum by (le) (
        rate({hist_metric}_bucket{{handler="/"}}[5m])
      )
    )
    '''.strip()

    # Pod count (Running pods for this service)
    pod_q = f'''
    sum by (namespace) (
      kube_pod_status_phase{{
        phase="Running",
        namespace="default",
        pod=~"{pod_regex}"
      }}
    )
    '''.strip()

    # Cold starts
    cold_q = f'increase({cold_metric}[10m])'

    # --- Range queries ---
    rate_ts = query_range(rate_q, run_start, run_end, step)
    p99_ts = query_range(p99_q, run_start, run_end, step)
    pod_ts = query_range(pod_q, run_start, run_end, step)

    export_timeseries(rate_ts, f"rate_{service}_{pattern}.csv")
    export_timeseries(p99_ts, f"p99_{service}_{pattern}.csv")
    export_timeseries(pod_ts, f"pods_{service}_{pattern}.csv")

    # --- Cold starts as scalar ---
    cold_res = query_instant(cold_q, run_end)
    cold_count = export_scalar(cold_res)
    with open(f"cold_starts_{service}_{pattern}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["run_start", "run_end", "cold_starts"])
        writer.writerow([run_start, run_end, cold_count)


if __name__ == "__main__":
    main()