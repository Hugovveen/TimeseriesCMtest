import os
import time
import json
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

HOST = "https://api.chartmetric.com"
REFRESH_TOKEN = os.getenv("CHARTMETRIC_REFRESH_TOKEN")

artists = pd.read_csv("cm_lofi_artist_genres_first10.csv")

def flatten_artist(data):
    obj = data["obj"]

    primary_genre = None
    secondary_genres = []

    genres = obj.get("genres") or {}

    if genres.get("primary"):
        primary_genre = genres["primary"].get("name")

    secondary_genres = [
        g.get("name")
        for g in genres.get("secondary", [])
        if g.get("name")
    ]

    return {
        "cm_artist_id": obj.get("id"),
        "name": obj.get("name"),
        "cm_artist_rank": obj.get("cm_artist_rank"),
        "cm_artist_score": obj.get("cm_artist_score"),
        "hometown_city": obj.get("hometown_city"),
        "current_city": obj.get("current_city"),
        "booking_agent": obj.get("booking_agent"),
        "record_label": obj.get("record_label"),
        "press_contact": obj.get("press_contact"),
        "general_manager": obj.get("general_manager"),
        "primary_genre": primary_genre,
        "secondary_genres": ", ".join(secondary_genres),
        "image_url": obj.get("image_url"),
        "cover_url": obj.get("cover_url"),
    }

def get_token():
    r = requests.post(
        f"{HOST}/api/token",
        json={"refreshtoken": REFRESH_TOKEN}
    )
    r.raise_for_status()
    return r.json()["token"]

def get_artist(cm_artist_id, token):
    r = requests.get(
        f"{HOST}/api/artist/{int(cm_artist_id)}",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    return r.json()

token = get_token()

rows = []

for _, artist in artists.iterrows():
    cm_id = artist["cm_artist_id"]
    name = artist["name"]

    print(f"Fetching {name} ({cm_id})")

    data = get_artist(cm_id, token)
    row = flatten_artist(data)

    rows.append(row)

out = pd.DataFrame(rows)
out.to_csv("chartmetric_artist_snapshot_first10.csv", index=False)

print("Saved chartmetric_artist_snapshot_first10.csv")