# resolve_chartmetric_artist_ids.py
#
# Purpose:
# - Read artist names from pull_artists_db.csv
# - Search Chartmetric for matching artists
# - Save best match per artist
# - Save all candidates for manual checking
# - Save raw JSON responses for debugging
#
# Input file:
#   pull_artists_db.csv
#
# Expected columns:
#   name
#
# Also accepts:
#   artist_name
#   Artist
#   artist
#
# WARNING:
# This is intentionally small-scale. Use for ~10 names first.
# Do not run this on 1700 artists until the endpoint + matching quality is verified.

import csv
import json
import os
import re
import time
from difflib import SequenceMatcher
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

INPUT_CSV = Path("pull_artists_db.csv")
OUTPUT_BEST_MATCHES = Path("chartmetric_artist_id_matches.csv")
OUTPUT_ALL_CANDIDATES = Path("chartmetric_artist_id_candidates.csv")
RAW_DIR = Path("chartmetric_artist_search_raw")

SLEEP_SECONDS = 1
LIMIT = 10

# Main endpoint we are testing.
# Free-text artist search endpoint.
SEARCH_PATH = "/api/search"

SEARCH_PARAM_VARIANTS = [
    {
        "q": None,
        "type": "artists",
        "limit": LIMIT,
        "offset": 0,
        "beta": "false",
    }
]


# -----------------------------
# API HELPERS
# -----------------------------

def get_token() -> str:
    if not REFRESH_TOKEN:
        raise RuntimeError(
            "Missing CHARTMETRIC_REFRESH_TOKEN in .env or environment."
        )

    response = requests.post(
        f"{HOST}/api/token",
        json={"refreshtoken": REFRESH_TOKEN},
        timeout=30,
    )
    response.raise_for_status()

    return response.json()["token"]


def get_json(
    path: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    response = requests.get(
        f"{HOST}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )

    print(f"STATUS {response.status_code}: {response.url}")

    if response.status_code == 200:
        return response.json()

    print("ERROR RESPONSE:")
    print(response.text)
    return None


def safe_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "unknown"


def save_raw_json(artist_name: str, variant_index: int, data: Dict[str, Any]) -> Path:
    RAW_DIR.mkdir(exist_ok=True)

    path = RAW_DIR / f"{safe_name(artist_name)}__variant_{variant_index}.json"

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)

    return path


# -----------------------------
# CSV INPUT
# -----------------------------

def read_artist_names(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path.resolve()}")

    names = []

    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError("Input CSV has no header row.")

        possible_name_columns = [
            "name",
            "artist_name",
            "Artist",
            "artist",
        ]

        name_column = None
        for column in possible_name_columns:
            if column in reader.fieldnames:
                name_column = column
                break

        if name_column is None:
            # Fall back to first column.
            name_column = reader.fieldnames[0]
            print(
                f"No standard name column found. "
                f"Using first column instead: {name_column}"
            )

        for row in reader:
            raw_name = row.get(name_column, "")
            name = str(raw_name).strip()

            if name:
                names.append(name)

    return names


# -----------------------------
# CANDIDATE EXTRACTION
# -----------------------------

def normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def similarity(a: str, b: str) -> float:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)

    if not a_norm or not b_norm:
        return 0.0

    if a_norm == b_norm:
        return 1.0

    return SequenceMatcher(None, a_norm, b_norm).ratio()


def extract_candidate_dicts(obj: Any) -> List[Dict[str, Any]]:
    artists = obj.get("obj", {}).get("artists", [])

    if isinstance(artists, list):
        return artists

    return []


def find_first_value(obj: Dict[str, Any], possible_keys: List[str]) -> Optional[Any]:
    for key in possible_keys:
        if key in obj and obj[key] not in [None, ""]:
            return obj[key]
    return None


def candidate_to_row(
    input_name: str,
    candidate: Dict[str, Any],
    variant_index: int,
    raw_json_path: str,
) -> Dict[str, Any]:
    chartmetric_id = candidate.get("id")
    chartmetric_name = candidate.get("name")

    score = similarity(input_name, str(chartmetric_name))

    return {
        "input_name": input_name,
        "chartmetric_artist_id": chartmetric_id,
        "chartmetric_name": chartmetric_name,
        "match_score": round(score, 4),
        "search_variant": variant_index,
        "sp_followers": candidate.get("sp_followers"),
        "sp_monthly_listeners": candidate.get("sp_monthly_listeners"),
        "cm_artist_score": candidate.get("cm_artist_score"),
        "image_url": candidate.get("image_url"),
        "raw_json_path": raw_json_path,
        "candidate_json": json.dumps(candidate, ensure_ascii=False),
    }


# -----------------------------
# SEARCH LOGIC
# -----------------------------

def build_params_for_variant(artist_name: str, variant: Dict[str, Any]) -> Dict[str, Any]:
    params = {}

    for key, value in variant.items():
        if value is None:
            params[key] = artist_name
        else:
            params[key] = value

    return params


def search_artist(
    artist_name: str,
    token: str,
) -> Dict[str, Any]:
    """
    Try several query parameter variants.

    Returns:
    {
        "best": best candidate row or empty row,
        "candidates": all candidate rows
    }
    """

    all_candidate_rows = []

    for index, variant in enumerate(SEARCH_PARAM_VARIANTS, start=1):
        params = build_params_for_variant(artist_name, variant)

        print("\n" + "-" * 80)
        print(f"Searching artist: {artist_name}")
        print(f"Variant {index}: {params}")

        data = get_json(SEARCH_PATH, token, params=params)

        if data is None:
            time.sleep(SLEEP_SECONDS)
            continue

        raw_path = save_raw_json(artist_name, index, data)
        candidates = extract_candidate_dicts(data)

        print(f"Candidates found: {len(candidates)}")

        for candidate in candidates:
            row = candidate_to_row(
                input_name=artist_name,
                candidate=candidate,
                variant_index=index,
                raw_json_path=str(raw_path),
            )
            all_candidate_rows.append(row)

        # Stop after first variant that returns candidates.
        # This prevents wasting extra calls once one query style works.
        if all_candidate_rows:
            break

        time.sleep(SLEEP_SECONDS)

    if all_candidate_rows:
        all_candidate_rows.sort(
            key=lambda row: row["match_score"],
            reverse=True,
        )
        best = all_candidate_rows[0]
    else:
        best = {
            "input_name": artist_name,
            "chartmetric_artist_id": "",
            "chartmetric_name": "",
            "match_score": 0,
            "search_variant": "",
            "spotify_id": "",
            "image_url": "",
            "raw_json_path": "",
            "candidate_json": "",
        }

    return {
        "best": best,
        "candidates": all_candidate_rows,
    }


# -----------------------------
# OUTPUT
# -----------------------------

def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# -----------------------------
# MAIN
# -----------------------------

def main() -> None:
    artist_names = read_artist_names(INPUT_CSV)

    if not artist_names:
        raise RuntimeError(f"No artist names found in {INPUT_CSV.resolve()}")

    print(f"Loaded {len(artist_names)} artist names from {INPUT_CSV.resolve()}")

    if len(artist_names) > 20:
        print(
            "WARNING: More than 20 artists found. "
            "This script is meant for small verification runs first."
        )

    token = get_token()

    best_rows = []
    all_candidate_rows = []

    for index, artist_name in enumerate(artist_names, start=1):
        print("\n" + "=" * 80)
        print(f"{index}/{len(artist_names)}: {artist_name}")

        result = search_artist(artist_name, token)

        best_rows.append(result["best"])
        all_candidate_rows.extend(result["candidates"])

        time.sleep(SLEEP_SECONDS)

    output_fields = [
        "input_name",
        "chartmetric_artist_id",
        "chartmetric_name",
        "match_score",
        "search_variant",
        "sp_followers",
        "sp_monthly_listeners",
        "cm_artist_score",
        "image_url",
        "raw_json_path",
        "candidate_json",
    ]

    write_csv(
        OUTPUT_BEST_MATCHES,
        best_rows,
        output_fields,
    )

    write_csv(
        OUTPUT_ALL_CANDIDATES,
        all_candidate_rows,
        output_fields,
    )

    print("\n" + "=" * 80)
    print("DONE")
    print(f"Best matches saved to: {OUTPUT_BEST_MATCHES.resolve()}")
    print(f"All candidates saved to: {OUTPUT_ALL_CANDIDATES.resolve()}")
    print(f"Raw JSON saved to: {RAW_DIR.resolve()}")


if __name__ == "__main__":
    main()