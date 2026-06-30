import pandas as pd
from pathlib import Path
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input pattern CSV")
    parser.add_argument("--output", required=True, help="Output sliced CSV")
    parser.add_argument("--start-index", type=int, required=True, help="Start row index (0-based)")
    parser.add_argument("--end-index", type=int, required=True, help="End row index (exclusive)")
    args = parser.parse_args()

    df = pd.read_csv(args.input)

    # Slice by row indices (easiest for now)
    sliced = df.iloc[args.start_index:args.end_index].copy()

    # Recompute minute_offset for the sliced window
    sliced["minute_offset"] = range(len(sliced))

    sliced.to_csv(args.output, index=False)
    print(f"Saved slice {args.start_index}:{args.end_index} -> {args.output}")

if __name__ == "__main__":
    main()