# chartmetric_artist_timeseries_pull.py
#
# Chartmetric time-series pull for a CSV of resolved artists.
#
# Purpose:
# - Read artist IDs from `chartmetric_artist_id_matches.csv`.
# - Pull raw Chartmetric time-series data for each artist.
# - Save raw JSON responses.
# - Flatten known time-series responses into one long CSV table.
# - Do NOT calculate growth here. Growth belongs in the analytics layer.
#
# WARNING:
# This script is intentionally designed for a small-to-moderate artist list.
# Verify the endpoint behavior and credit usage before running on large batches.
# Civilization has suffered enough.

import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


# -----------------------------
# CONFIG
# -----------------------------

load_dotenv()

HOST = "https://api.chartmetric.com"
REFRESH_TOKEN = os.getenv("CHARTMETRIC_REFRESH_TOKEN")

ARTIST_ID = 240495
ARTIST_NAME = "Len Faki"

# Use these globally. No more fake config variables pretending to matter.
SINCE = "2025-06-09"
UNTIL = "2026-06-09"

SLEEP_SECONDS = 1

RAW_DIR = Path("chartmetric_len_faki_raw")
OUTPUT_LONG_CSV = Path("len_faki_timeseries_long.csv")
OUTPUT_ENDPOINT_SUMMARY_CSV = Path("len_faki_endpoint_summary.csv")
INPUT_ARTIST_IDS_CSV = Path("chartmetric_artist_id_matches.csv")


# -----------------------------
# API HELPERS
# -----------------------------

def get_token() -> str:
    if not REFRESH_TOKEN:
        raise RuntimeError(
            "Missing CHARTMETRIC_REFRESH_TOKEN in environment/.env file."
        )

    response = requests.post(
        f"{HOST}/api/token",
        json={"refreshtoken": REFRESH_TOKEN},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["token"]


def get_json(path: str, token: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    url = f"{HOST}{path}"

    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=90,
        )

        print(f"STATUS {response.status_code}: {response.url}")

        if response.status_code == 200:
            return response.json()

        print("ERROR RESPONSE:")
        print(response.text)
        return None

    except requests.exceptions.ReadTimeout:
        print(f"TIMEOUT: {url}")
        print(f"PARAMS: {params}")
        return None

    except requests.exceptions.ConnectionError as error:
        print(f"CONNECTION ERROR: {url}")
        print(error)
        return None

    except requests.exceptions.RequestException as error:
        print(f"REQUEST ERROR: {url}")
        print(error)
        return None


def safe_endpoint_name(path: str, params: Optional[Dict[str, Any]] = None) -> str:
    name = path.strip("/").replace("/", "__")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)

    if params:
        suffix = "__" + "__".join(
            f"{key}-{value}" for key, value in sorted(params.items())
        )
        suffix = re.sub(r"[^A-Za-z0-9_.-]+", "_", suffix)
        name = f"{name}{suffix}"

    return name


def save_raw_json(endpoint_name: str, data: Dict[str, Any]) -> Path:
    RAW_DIR.mkdir(exist_ok=True)
    path = RAW_DIR / f"{endpoint_name}.json"

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)

    return path


def read_artist_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Artist ID CSV not found: {path.resolve()}")

    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError("Artist ID CSV has no header row.")

        for row in reader:
            raw_id = row.get("chartmetric_artist_id") or row.get("cm_artist_id") or row.get("artist_id")
            raw_name = row.get("chartmetric_name") or row.get("input_name") or row.get("name") or row.get("artist_name")

            if raw_id in [None, ""]:
                continue

            try:
                chartmetric_artist_id = int(str(raw_id).strip())
            except Exception:
                continue

            artist_name = str(raw_name).strip() if raw_name is not None else ""

            rows.append(
                {
                    "chartmetric_artist_id": chartmetric_artist_id,
                    "artist_name": artist_name or f"Artist {chartmetric_artist_id}",
                }
            )

    return rows


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------
# ENDPOINT LIST
# -----------------------------

def build_candidates(artist_id: int) -> List[Dict[str, Any]]:
    """
    All calls are Len Faki-only.

    Types:
    - metadata: saved raw, not flattened into time-series rows.
    - stat_source: /api/artist/{id}/stat/{source}
    - cpp: /api/artist/{id}/cpp
    - where_people_listen: /api/artist/{id}/where-people-listen
    """

    return [
        # Basic identity / context
        {
            "label": "artist_metadata",
            "type": "metadata",
            "path": f"/api/artist/{artist_id}",
            "params": {},
        },
        {
            "label": "artist_urls",
            "type": "metadata",
            "path": f"/api/artist/{artist_id}/urls",
            "params": {},
        },

        # Spotify
        {
            "label": "spotify_followers",
            "type": "stat_source",
            "source": "spotify",
            "metric": "followers",
            "path": f"/api/artist/{artist_id}/stat/spotify",
            "params": {
                "field": "followers",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },
        {
            "label": "spotify_listeners",
            "type": "stat_source",
            "source": "spotify",
            "metric": "listeners",
            "path": f"/api/artist/{artist_id}/stat/spotify",
            "params": {
                "field": "listeners",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },
        {
            "label": "spotify_popularity",
            "type": "stat_source",
            "source": "spotify",
            "metric": "popularity",
            "path": f"/api/artist/{artist_id}/stat/spotify",
            "params": {
                "field": "popularity",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },

        # Instagram
        {
            "label": "instagram_followers",
            "type": "stat_source",
            "source": "instagram",
            "metric": "followers",
            "path": f"/api/artist/{artist_id}/stat/instagram",
            "params": {
                "field": "followers",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },

        # TikTok
        {
            "label": "tiktok_followers",
            "type": "stat_source",
            "source": "tiktok",
            "metric": "followers",
            "path": f"/api/artist/{artist_id}/stat/tiktok",
            "params": {
                "field": "followers",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },
        {
            "label": "tiktok_likes",
            "type": "stat_source",
            "source": "tiktok",
            "metric": "likes",
            "path": f"/api/artist/{artist_id}/stat/tiktok",
            "params": {
                "field": "likes",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },

        # YouTube channel stats
        {
            "label": "youtube_channel_subscribers",
            "type": "stat_source",
            "source": "youtube_channel",
            "metric": "subscribers",
            "path": f"/api/artist/{artist_id}/stat/youtube_channel",
            "params": {
                "field": "subscribers",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },
        {
            "label": "youtube_channel_views",
            "type": "stat_source",
            "source": "youtube_channel",
            "metric": "views",
            "path": f"/api/artist/{artist_id}/stat/youtube_channel",
            "params": {
                "field": "views",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },

        # YouTube artist aggregate stats
        {
            "label": "youtube_artist_daily_views",
            "type": "stat_source",
            "source": "youtube_artist",
            "metric": "daily_views",
            "path": f"/api/artist/{artist_id}/stat/youtube_artist",
            "params": {
                "field": "daily_views",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },
        {
            "label": "youtube_artist_monthly_views",
            "type": "stat_source",
            "source": "youtube_artist",
            "metric": "monthly_views",
            "path": f"/api/artist/{artist_id}/stat/youtube_artist",
            "params": {
                "field": "monthly_views",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },

        # SoundCloud
        {
            "label": "soundcloud_followers",
            "type": "stat_source",
            "source": "soundcloud",
            "metric": "followers",
            "path": f"/api/artist/{artist_id}/stat/soundcloud",
            "params": {
                "field": "followers",
                "since": SINCE,
                "until": UNTIL,
                "interpolated": "false",
            },
        },

        # Chartmetric CPP score/rank
        {
            "label": "cpp_score",
            "type": "cpp",
            "source": "chartmetric",
            "metric": "cpp_score",
            "path": f"/api/artist/{artist_id}/cpp",
            "params": {
                "stat": "score",
                "since": SINCE,
                "until": UNTIL,
            },
        },
        {
            "label": "cpp_rank",
            "type": "cpp",
            "source": "chartmetric",
            "metric": "cpp_rank",
            "path": f"/api/artist/{artist_id}/cpp",
            "params": {
                "stat": "rank",
                "since": SINCE,
                "until": UNTIL,
            },
        },
        
        #Not required for first draft
        # Spotify geo listeners by city/country
    #     {
    #         "label": "where_people_listen",
    #         "type": "where_people_listen",
    #         "source": "spotify",
    #         "metric": "listeners",
    #         "path": f"/api/artist/{artist_id}/where-people-listen",
    #         "params": {
    #             "since": SINCE,
    #             "until": UNTIL,
    #             "limit": 50,
    #             "offset": 0,
    #             "includeEstimates": "true",
    #         },
    #     },
    # ]
    ]


# -----------------------------
# FLATTENERS
# -----------------------------

def flatten_stat_source(
    data: Dict[str, Any],
    source: str,
    requested_metric: str,
    endpoint_label: str,
    pulled_at: str,
) -> List[Dict[str, Any]]:
    """
    Flatten /api/artist/{id}/stat/{source}

    Expected response shape roughly:
    {
        "obj": {
            "followers": [
                {"value": ..., "timestp": "...", "diff": ..., ...}
            ],
            "listeners": [...]
        }
    }

    Sometimes the API may return extra fields. We only flatten list fields
    whose items contain a timestamp and value.
    """

    rows = []
    obj = data.get("obj", {})

    if not isinstance(obj, dict):
        return rows

    for metric_name, points in obj.items():
        if not isinstance(points, list):
            continue

        for point in points:
            if not isinstance(point, dict):
                continue

            timestamp = point.get("timestp") or point.get("date")
            value = point.get("value")

            if timestamp is None or value is None:
                continue

            rows.append(
                {
                    "artist_id": f"cm_{ARTIST_ID}",
                    "chartmetric_artist_id": ARTIST_ID,
                    "artist_name": ARTIST_NAME,
                    "source": source,
                    "metric": metric_name,
                    "date": timestamp,
                    "value": value,
                    "unit": infer_unit(source, metric_name),
                    "endpoint_label": endpoint_label,
                    "pulled_at": pulled_at,
                    "extra_json": json.dumps(
                        {
                            key: val
                            for key, val in point.items()
                            if key not in {"timestp", "date", "value"}
                        },
                        ensure_ascii=False,
                    ),
                }
            )

    return rows


def flatten_cpp(
    data: Dict[str, Any],
    source: str,
    metric: str,
    endpoint_label: str,
    pulled_at: str,
) -> List[Dict[str, Any]]:
    """
    Flatten /api/artist/{id}/cpp

    Expected response shape:
    {
        "obj": [
            {"score": 0.81, "timestp": "..."}
        ]
    }
    or:
    {
        "obj": [
            {"rank": 1234, "timestp": "..."}
        ]
    }
    """

    rows = []
    points = data.get("obj", [])

    if not isinstance(points, list):
        return rows

    for point in points:
        if not isinstance(point, dict):
            continue

        timestamp = point.get("timestp") or point.get("date")

        if "score" in point:
            value = point.get("score")
            metric_name = "cpp_score"
            unit = "score_0_1"
        elif "rank" in point:
            value = point.get("rank")
            metric_name = "cpp_rank"
            unit = "rank"
        else:
            continue

        if timestamp is None or value is None:
            continue

        rows.append(
            {
                "artist_id": f"cm_{ARTIST_ID}",
                "chartmetric_artist_id": ARTIST_ID,
                "artist_name": ARTIST_NAME,
                "source": source,
                "metric": metric_name,
                "date": timestamp,
                "value": value,
                "unit": unit,
                "endpoint_label": endpoint_label,
                "pulled_at": pulled_at,
                "extra_json": json.dumps(
                    {
                        key: val
                        for key, val in point.items()
                        if key not in {"timestp", "date", "score", "rank"}
                    },
                    ensure_ascii=False,
                ),
            }
        )

    return rows


def flatten_where_people_listen(
    data: Dict[str, Any],
    endpoint_label: str,
    pulled_at: str,
) -> List[Dict[str, Any]]:
    """
    Flatten /api/artist/{id}/where-people-listen

    Expected response shape roughly:
    {
        "obj": {
            "cities": {
                "Amsterdam": [
                    {"timestp": "...", "listeners": 1234, "code2": "NL", ...}
                ]
            },
            "countries": {
                "Netherlands": [
                    {"timestp": "...", "listeners": 12345, "code2": "NL", ...}
                ]
            }
        }
    }
    """

    rows = []
    obj = data.get("obj", {})

    if not isinstance(obj, dict):
        return rows

    for region_group in ["cities", "countries"]:
        locations = obj.get(region_group, {})

        if not isinstance(locations, dict):
            continue

        for location_name, points in locations.items():
            if not isinstance(points, list):
                continue

            for point in points:
                if not isinstance(point, dict):
                    continue

                timestamp = point.get("timestp") or point.get("date")
                listeners = point.get("listeners")

                if timestamp is None or listeners is None:
                    continue

                extra = {
                    key: val
                    for key, val in point.items()
                    if key not in {"timestp", "date", "listeners"}
                }

                extra["location_name"] = location_name
                extra["location_group"] = region_group

                rows.append(
                    {
                        "artist_id": f"cm_{ARTIST_ID}",
                        "chartmetric_artist_id": ARTIST_ID,
                        "artist_name": ARTIST_NAME,
                        "source": "spotify",
                        "metric": f"{region_group}_listeners",
                        "date": timestamp,
                        "value": listeners,
                        "unit": "count",
                        "endpoint_label": endpoint_label,
                        "pulled_at": pulled_at,
                        "extra_json": json.dumps(extra, ensure_ascii=False),
                    }
                )

    return rows


def infer_unit(source: str, metric: str) -> str:
    metric_lower = metric.lower()

    if "rank" in metric_lower:
        return "rank"

    if "score" in metric_lower or "popularity" in metric_lower:
        return "score"

    if "ratio" in metric_lower or "percent" in metric_lower:
        return "ratio"

    return "count"


# -----------------------------
# OUTPUT
# -----------------------------

def write_long_csv(rows: List[Dict[str, Any]], output_path: Path) -> None:
    fieldnames = [
        "artist_id",
        "chartmetric_artist_id",
        "artist_name",
        "source",
        "metric",
        "date",
        "value",
        "unit",
        "endpoint_label",
        "pulled_at",
        "extra_json",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_endpoint_summary(rows: List[Dict[str, Any]], output_path: Path) -> None:
    fieldnames = [
        "artist_id",
        "artist_name",
        "endpoint_label",
        "path",
        "params",
        "success",
        "row_count",
        "raw_json_path",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# -----------------------------
# MAIN
# -----------------------------

def main() -> None:
    print("Starting Chartmetric batch pull from artist ID CSV")
    print(f"Input CSV: {INPUT_ARTIST_IDS_CSV.resolve()}")
    print(f"Window: {SINCE} → {UNTIL}")

    token = get_token()
    artist_rows = read_artist_rows(INPUT_ARTIST_IDS_CSV)

    all_long_rows = []
    endpoint_summary_rows = []

    try:
        for artist_index, artist_row in enumerate(artist_rows, start=1):
            artist_id = int(artist_row["chartmetric_artist_id"])
            artist_name = artist_row["artist_name"]
            candidates = build_candidates(artist_id)

            print("\n" + "#" * 80)
            print(f"{artist_index}/{len(artist_rows)}: {artist_name} ({artist_id})")

            for index, candidate in enumerate(candidates, start=1):
                label = candidate["label"]
                endpoint_type = candidate["type"]
                path = candidate["path"]
                params = candidate.get("params", {})

                print("\n" + "=" * 80)
                print(f"Endpoint {index}/{len(candidates)}: {label}")
                print(path)
                print(params)

                pulled_at = now_utc_iso()
                endpoint_name = safe_endpoint_name(f"{artist_id}__{path}", params)

                data = get_json(path, token, params=params)

                if data is None:
                    endpoint_summary_rows.append(
                        {
                            "artist_id": artist_id,
                            "artist_name": artist_name,
                            "endpoint_label": label,
                            "path": path,
                            "params": json.dumps(params, ensure_ascii=False),
                            "success": "False",
                            "row_count": 0,
                            "raw_json_path": "",
                        }
                    )
                    time.sleep(SLEEP_SECONDS)
                    continue

                raw_path = save_raw_json(endpoint_name, data)

                if endpoint_type == "stat_source":
                    long_rows = flatten_stat_source(
                        data=data,
                        source=candidate["source"],
                        requested_metric=candidate["metric"],
                        endpoint_label=label,
                        pulled_at=pulled_at,
                    )

                elif endpoint_type == "cpp":
                    long_rows = flatten_cpp(
                        data=data,
                        source=candidate["source"],
                        metric=candidate["metric"],
                        endpoint_label=label,
                        pulled_at=pulled_at,
                    )

                elif endpoint_type == "where_people_listen":
                    long_rows = flatten_where_people_listen(
                        data=data,
                        endpoint_label=label,
                        pulled_at=pulled_at,
                    )

                else:
                    long_rows = []

                for row in long_rows:
                    row["artist_id"] = f"cm_{artist_id}"
                    row["chartmetric_artist_id"] = artist_id
                    row["artist_name"] = artist_name

                all_long_rows.extend(long_rows)

                endpoint_summary_rows.append(
                    {
                        "artist_id": artist_id,
                        "artist_name": artist_name,
                        "endpoint_label": label,
                        "path": path,
                        "params": json.dumps(params, ensure_ascii=False),
                        "success": "True",
                        "row_count": len(long_rows),
                        "raw_json_path": str(raw_path),
                    }
                )

                print(f"Flattened rows: {len(long_rows)}")
                time.sleep(SLEEP_SECONDS)

    finally:
        write_long_csv(all_long_rows, OUTPUT_LONG_CSV)
        write_endpoint_summary(endpoint_summary_rows, OUTPUT_ENDPOINT_SUMMARY_CSV)

        print("\n" + "=" * 80)
        print("PARTIAL OR FULL OUTPUT WRITTEN")
        print(f"Raw JSON saved to: {RAW_DIR.resolve()}")
        print(f"Long time-series CSV saved to: {OUTPUT_LONG_CSV.resolve()}")
        print(f"Endpoint summary saved to: {OUTPUT_ENDPOINT_SUMMARY_CSV.resolve()}")
        print(f"Total long rows: {len(all_long_rows)}")
        print(f"Total endpoint summary rows: {len(endpoint_summary_rows)}")


if __name__ == "__main__":
    main()