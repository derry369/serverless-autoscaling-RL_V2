import pandas as pd
from pathlib import Path


RAW_TRACE = Path("./AzureFunctionsInvocationTrace2021.csv")
OUT_DIR = Path("./phase2_patterns")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_trace():
    df = pd.read_csv(RAW_TRACE)
    # end_timestamp is seconds since start of trace (per dataset docs).[web:1066][web:1065]
    df["end_timestamp"] = pd.to_timedelta(df["end_timestamp"], unit="s")
    # Anchor at an arbitrary start date: 2021-01-31 is the start of the trace.[web:1066]
    start = pd.Timestamp("2021-01-31T00:00:00Z")
    df["timestamp"] = start + df["end_timestamp"]
    df["minute"] = df["timestamp"].dt.floor("T")
    return df


def aggregate_per_minute(df: pd.DataFrame) -> pd.DataFrame:
    per_min = (
        df.groupby("minute")
        .size()
        .rename("invocations")
        .reset_index()
    )
    return per_min


def add_day_and_hour(df_minute: pd.DataFrame) -> pd.DataFrame:
    df_minute["date"] = df_minute["minute"].dt.date
    df_minute["hour"] = df_minute["minute"].dt.hour
    return df_minute


def save_pattern(df_minute: pd.DataFrame, mask, name: str):
    # Select the minutes and per-minute counts for this pattern
    out = (
        df_minute.loc[mask, ["minute", "invocations"]]
        .rename(columns={"invocations": "invocations_per_minute"})
        .reset_index(drop=True)
    )

    # Add relative minute index for the injector
    out["minute_offset"] = range(len(out))

    # Convert per-minute count to requests-per-second for the injector
    out["rps"] = out["invocations_per_minute"] / 60.0

    out.to_csv(OUT_DIR / f"pattern_{name}.csv", index=False)
    print(
        f"Saved {name} pattern with {len(out)} minutes "
        f"to {OUT_DIR / f'pattern_{name}.csv'}"
    )


def main():
    print("Loading raw trace...")
    df = load_trace()
    print(f"Loaded {len(df)} invocations")

    print("Aggregating per minute...")
    df_minute = aggregate_per_minute(df)
    df_minute = add_day_and_hour(df_minute)

    # Quick sanity: print first and last timestamps and basic stats
    print("Time range:", df_minute["minute"].min(), "to", df_minute["minute"].max())
    print("Per-minute stats (invocations):")
    print(df_minute["invocations"].describe())

    # Choose specific dates (you can refine after plotting)
    day1 = pd.to_datetime("2021-02-02").date()
    day2 = pd.to_datetime("2021-02-05").date()

    df_two_days = df_minute[df_minute["date"].isin([day1, day2])].copy()

    # --- Pattern 1: diurnal (one full day with smooth variation) ---
    diurnal_day = day1
    diurnal_mask = df_two_days["date"] == diurnal_day
    save_pattern(df_two_days, diurnal_mask, "diurnal")

    # --- Pattern 2: bursty (window with sharp spikes) ---
    high_thresh = df_two_days["invocations"].median() * 4
    bursty_mask = (df_two_days["invocations"] >= high_thresh)
    bursty_indices = df_two_days.index[bursty_mask]
    expanded = set()
    for idx in bursty_indices:
        for delta in range(-5, 6):
            expanded.add(idx + delta)
    expanded_mask = df_two_days.index.isin(expanded)
    save_pattern(df_two_days, expanded_mask, "bursty")

    # --- Pattern 3: idle with sporadic spikes ---
    low_thresh = max(1, int(df_two_days["invocations"].quantile(0.2)))
    idle_mask = df_two_days["invocations"] <= low_thresh
    df_two_days["idle_candidate"] = idle_mask
    spike_mask = (~idle_mask) & (
        df_two_days["invocations"] <= df_two_days["invocations"].median()
    )
    idle_spikes_mask = idle_mask | spike_mask
    save_pattern(df_two_days, idle_spikes_mask, "idle_spikes")


if __name__ == "__main__":
    main()