# WARNING:
# This script is intentionally limited to one artist only.
# Do not modify it to loop over large artist lists unless API credits are confirmed.

import csv
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

HOST = "https://api.chartmetric.com"
REFRESH_TOKEN = os.getenv("CHARTMETRIC_REFRESH_TOKEN")

ARTIST_ID = 240495
ARTIST_NAME = "Len Faki"

SINCE = "2025-06-09"
UNTIL = "2026-06-09"
SLEEP_SECONDS = 1

RAW_DIR = Path("chartmetric_len_faki_history_raw")
SUMMARY_CSV = Path("len_faki_timeseries_probe_summary.csv")

MATCH_TERMS = [
    "date",
    "followers",
    "listeners",
    "monthly",
    "instagram",
    "tiktok",
    "youtube",
    "views",
    "rank",
    "score",
    "stage",
    "momentum",
    "trend",
]


def get_token():
    response = requests.post(
        f"{HOST}/api/token",
        json={"refreshtoken": REFRESH_TOKEN},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["token"]


def get_json(path, token, params=None):
    url = f"{HOST}{path}"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )

    print(f"STATUS {response.status_code}: {response.url}")

    if response.status_code == 200:
        return response.json()

    print(response.text)
    return None


def safe_endpoint_name(path, params=None):
    name = path.strip("/").replace("/", "__")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)

    if params:
        suffix = "__" + "__".join(f"{key}-{value}" for key, value in sorted(params.items()))
        suffix = re.sub(r"[^A-Za-z0-9_.-]+", "_", suffix)
        name = f"{name}{suffix}"

    return name


def save_raw_json(endpoint_name, data):
    RAW_DIR.mkdir(exist_ok=True)
    path = RAW_DIR / f"{endpoint_name}.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def find_matching_key_paths(obj, path=""):
    matches = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}" if path else key
            lower_key = key.lower()

            if any(term in lower_key for term in MATCH_TERMS):
                matches.append((next_path, value))

            matches.extend(find_matching_key_paths(value, next_path))

    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            matches.extend(find_matching_key_paths(item, f"{path}[{index}]"))

    return matches


def example_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)[:250]
    return value


def build_candidates():
    return [
        (
            f"/api/artist/{ARTIST_ID}/career",
            {"since": "2023-01-01", "until": "2024-01-01", "limit": 50},
        ),
        (
            f"/api/artist/{ARTIST_ID}/social-audience-stats",
            {
                "domain": "instagram",
                "audienceType": "followers",
                "statsType": "stat",
                "since": "2024-01-01",
                "until": "2024-12-31",
                "limit": 100,
            },
        ),
        (
            f"/api/artist/{ARTIST_ID}/past-artist-rank",
            {"metric": "cm_artist_rank", "date": "2024-06-15"},
        ),
        (
            f"/api/artist/{ARTIST_ID}/stat/spotify",
            {
                "field": "listeners",
                "since": "2024-01-01",
                "until": "2024-12-31",
            },
        ),
        (
            f"/api/artist/{ARTIST_ID}/stat/spotify",
            {
                "field": "followers",
                "since": "2024-01-01",
                "until": "2024-12-31",
            },
        ),
    ]


def process_endpoint(index, total, path, params, token, summary_rows):
    endpoint_name = safe_endpoint_name(path, params)

    print("\n" + "=" * 80)
    print(f"{ARTIST_NAME} historical probe {index}/{total}")
    print(path)

    data = get_json(path, token, params=params)

    if data is None:
        summary_rows.append(
            {
                "endpoint": endpoint_name,
                "status_code": "",
                "success": "False",
                "matched_key_path": "",
                "example_value": "",
            }
        )
        return False

    save_raw_json(endpoint_name, data)

    matches = find_matching_key_paths(data)
    if not matches:
        print("No matching key paths found.")
        summary_rows.append(
            {
                "endpoint": endpoint_name,
                "status_code": 200,
                "success": "True",
                "matched_key_path": "",
                "example_value": "",
            }
        )
    else:
        print("Matching key paths:")
        for matched_path, value in matches:
            preview = example_value(value)
            print(f"- {matched_path}: {preview}")
            summary_rows.append(
                {
                    "endpoint": endpoint_name,
                    "status_code": 200,
                    "success": "True",
                    "matched_key_path": matched_path,
                    "example_value": preview,
                }
            )

    return True


def main():
    token = get_token()
    candidates = build_candidates()
    summary_rows = []

    if not candidates:
        raise SystemExit("No candidate endpoints configured.")

    first_path, first_params = candidates[0]
    first_ok = process_endpoint(1, len(candidates), first_path, first_params, token, summary_rows)

    if not first_ok:
        with open(SUMMARY_CSV, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["endpoint", "status_code", "success", "matched_key_path", "example_value"],
            )
            writer.writeheader()
            writer.writerows(summary_rows)

        print(f"\nSaved summary CSV to: {SUMMARY_CSV.resolve()}")
        return

    time.sleep(SLEEP_SECONDS)

    for index, (path, params) in enumerate(candidates[1:], start=2):
        process_endpoint(index, len(candidates), path, params, token, summary_rows)
        time.sleep(SLEEP_SECONDS)

    with open(SUMMARY_CSV, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["endpoint", "status_code", "success", "matched_key_path", "example_value"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nSaved raw JSON to: {RAW_DIR.resolve()}")
    print(f"Saved summary CSV to: {SUMMARY_CSV.resolve()}")


if __name__ == "__main__":
    main()