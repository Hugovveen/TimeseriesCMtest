import argparse
import csv
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from grab_trending_data import flatten_chartmetric_metrics


load_dotenv()

HOST = "https://api.chartmetric.com"
REFRESH_TOKEN = os.getenv("CHARTMETRIC_REFRESH_TOKEN")


def get_token():
    response = requests.post(
        f"{HOST}/api/token",
        json={"refreshtoken": REFRESH_TOKEN},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["token"]


def get_artist(cm_artist_id, token):
    response = requests.get(
        f"{HOST}/api/artist/{cm_artist_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def load_artist_ids(csv_path):
    artist_ids = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            value = row.get("cm_artist_id")
            if value is None or value == "":
                continue
            artist_ids.append(int(value))
    return artist_ids


def probe_artist_ids(artist_ids, output_path, sleep_seconds=0.6):
    token = get_token()
    rows = []

    for index, cm_artist_id in enumerate(artist_ids, start=1):
        print(f"Fetching {index}/{len(artist_ids)}: {cm_artist_id}")

        try:
            data = get_artist(cm_artist_id, token)
            row = flatten_chartmetric_metrics(data)
            row["probe_status"] = "ok"
            row["probe_error"] = ""
        except Exception as exc:
            row = {
                "cm_artist_id": cm_artist_id,
                "name": "",
                "probe_status": "error",
                "probe_error": str(exc),
            }

        rows.append(row)

        if sleep_seconds:
            time.sleep(sleep_seconds)

    if not rows:
        raise ValueError("No artist IDs were provided.")

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def parse_args():
    parser = argparse.ArgumentParser(
        description="Probe Chartmetric artist metrics for one or more artist IDs and flatten the results."
    )
    parser.add_argument(
        "--artist-ids",
        nargs="*",
        type=int,
        help="One or more Chartmetric artist IDs to probe.",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        help="CSV file containing a `cm_artist_id` column to probe.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("chartmetric_metrics.csv"),
        help="Output CSV file path.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.6,
        help="Delay between requests to avoid rate limiting.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.artist_ids:
        artist_ids = args.artist_ids
    elif args.input_csv:
        artist_ids = load_artist_ids(args.input_csv)
    else:
        raise SystemExit("Provide either --artist-ids or --input-csv.")

    rows = probe_artist_ids(artist_ids, args.output, sleep_seconds=args.sleep_seconds)
    print(f"Wrote {len(rows)} rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()