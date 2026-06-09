"""
Streamlit demo for Len Faki Chartmetric probe data.

Usage:
  pip install streamlit pandas altair
  streamlit run streamlit_len_faki_demo.py

This app loads:
- `len_faki_timeseries_probe_summary.csv` (if present)
- raw JSON files in `chartmetric_len_faki_history_raw/`

It extracts simple time series from JSON objects that contain a `date` key
and numeric metric fields (followers/listeners/views/etc) and makes plots.
"""

from pathlib import Path
import json
import re
from typing import List

import pandas as pd
import streamlit as st
import altair as alt


# Paths
RAW_DIR = Path("chartmetric_len_faki_history_raw")
NORMALIZED_PATH = Path("artist_metrics_normalized.csv")
SUMMARY_CSV = Path("len_faki_timeseries_probe_summary.csv")

# Artist defaults
DEFAULT_ARTIST_ID = 240495
DEFAULT_ARTIST_NAME = "Len Faki"

# Expected signals for completeness
EXPECTED_SIGNALS = [
    "spotify_followers",
    "spotify_listeners",
    "instagram_followers",
    "instagram_engagement_rate",
    "career_stage",
    "career_momentum",
    "artist_rank",
]


def _read_json(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _find_list_with_keys(obj, required_keys):
    """Recursively find a list whose first item is a dict containing required_keys."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            res = _find_list_with_keys(v, required_keys)
            if res is not None:
                return res
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], dict):
            if all(any(rk in key for key in obj[0].keys()) for rk in required_keys):
                return obj
        for item in obj:
            res = _find_list_with_keys(item, required_keys)
            if res is not None:
                return res
    return None


def _extract_date_from_filename(name: str):
    m = re.search(r"date-(\d{4}-\d{2}-\d{2})", name)
    if m:
        return m.group(1)
    return None


def parse_spotify_stat(data, metric, source_endpoint):
    """Parse Spotify stat JSON structures into normalized rows."""
    rows = []
    # look for list with timestp and value
    lst = None
    # common keys: timestp, timestmp, timestamp, date
    for key in ("obj", "data", "stats", "items"):
        if isinstance(data, dict) and key in data and isinstance(data[key], list):
            lst = data[key]
            break

    if lst is None:
        lst = _find_list_with_keys(data, ["timestp", "value"]) or _find_list_with_keys(data, ["timestp"]) or _find_list_with_keys(data, ["date"])

    if not lst:
        return rows

    for item in lst:
        if not isinstance(item, dict):
            continue
        date = item.get("timestp") or item.get("date") or item.get("timestamp")
        value = item.get("value") or item.get("v") or item.get(metric)
        if value is None:
            continue

        row = {
            "artist_id": DEFAULT_ARTIST_ID,
            "artist_name": DEFAULT_ARTIST_NAME,
            "date": date,
            "platform": "spotify",
            "metric": metric,
            "value_numeric": _safe_numeric(value),
            "value_text": None,
            "diff": item.get("diff") or item.get("delta"),
            "monthly_diff": item.get("monthly_diff"),
            "monthly_diff_percent": item.get("monthly_diff_percent"),
            "is_interpolated": item.get("is_interpolated") or item.get("interpolated") or False,
            "source_endpoint": source_endpoint,
            "status": "ok",
        }
        rows.append(row)

    return rows


def parse_social_audience_stats(data, source_endpoint):
    rows = []
    lst = data.get("obj") if isinstance(data, dict) else None
    if not lst:
        lst = _find_list_with_keys(data, ["timestp", "followers"]) or []

    for item in lst:
        if not isinstance(item, dict):
            continue
        date = item.get("timestp") or item.get("date")
        def push(metric, val, numeric=False):
            rows.append(
                {
                    "artist_id": DEFAULT_ARTIST_ID,
                    "artist_name": DEFAULT_ARTIST_NAME,
                    "date": date,
                    "platform": "instagram",
                    "metric": metric,
                    "value_numeric": _safe_numeric(val) if numeric else None,
                    "value_text": None if numeric else (str(val) if val is not None else None),
                    "diff": item.get("diff"),
                    "monthly_diff": item.get("monthly_diff"),
                    "monthly_diff_percent": item.get("monthly_diff_percent"),
                    "is_interpolated": item.get("is_interpolated") or False,
                    "source_endpoint": source_endpoint,
                    "status": "ok",
                }
            )

        # map expected instagram fields
        if "followers" in item:
            push("instagram_followers", item.get("followers"), numeric=True)
        if "avg_likes_per_post" in item:
            push("instagram_avg_likes_per_post", item.get("avg_likes_per_post"), numeric=True)
        if "avg_comments_per_post" in item:
            push("instagram_avg_comments_per_post", item.get("avg_comments_per_post"), numeric=True)
        if "avg_views_per_post" in item:
            push("instagram_avg_views_per_post", item.get("avg_views_per_post"), numeric=True)
        if "engagement_rate" in item:
            push("instagram_engagement_rate", item.get("engagement_rate"), numeric=True)

    return rows


def parse_career(data, source_endpoint):
    rows = []
    lst = data.get("obj") if isinstance(data, dict) else None
    if not lst:
        lst = _find_list_with_keys(data, ["timestp", "stage"]) or []

    for item in lst:
        if not isinstance(item, dict):
            continue
        date = item.get("timestp") or item.get("date")
        # stage (text) and stage_score (numeric)
        rows.append(
            {
                "artist_id": DEFAULT_ARTIST_ID,
                "artist_name": DEFAULT_ARTIST_NAME,
                "date": date,
                "platform": "chartmetric",
                "metric": "career_stage",
                "value_numeric": _safe_numeric(item.get("stage_score")),
                "value_text": item.get("stage"),
                "diff": None,
                "monthly_diff": None,
                "monthly_diff_percent": None,
                "is_interpolated": False,
                "source_endpoint": source_endpoint,
                "status": "ok",
            }
        )

        # momentum fields
        if item.get("momentum") is not None or item.get("momentum_score") is not None:
            rows.append(
                {
                    "artist_id": DEFAULT_ARTIST_ID,
                    "artist_name": DEFAULT_ARTIST_NAME,
                    "date": date,
                    "platform": "chartmetric",
                    "metric": "career_momentum",
                    "value_numeric": _safe_numeric(item.get("momentum_score")),
                    "value_text": item.get("momentum"),
                    "diff": None,
                    "monthly_diff": None,
                    "monthly_diff_percent": None,
                    "is_interpolated": False,
                    "source_endpoint": source_endpoint,
                    "status": "ok",
                }
            )

    return rows


def parse_past_artist_rank(data, filename, source_endpoint):
    rows = []
    # data likely has obj as list with artist_rank
    obj = data.get("obj") if isinstance(data, dict) else None
    date = _extract_date_from_filename(filename)
    if isinstance(obj, list) and obj:
        first = obj[0]
        rank = first.get("artist_rank") or first.get("rank")
        if rank is not None:
            rows.append(
                {
                    "artist_id": DEFAULT_ARTIST_ID,
                    "artist_name": DEFAULT_ARTIST_NAME,
                    "date": date,
                    "platform": "chartmetric",
                    "metric": "artist_rank",
                    "value_numeric": _safe_numeric(rank),
                    "value_text": None,
                    "diff": None,
                    "monthly_diff": None,
                    "monthly_diff_percent": None,
                    "is_interpolated": False,
                    "source_endpoint": source_endpoint,
                    "status": "ok",
                }
            )

    return rows


def _safe_numeric(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def parse_raw_file(path: Path):
    data = _read_json(path)
    if data is None:
        return []

    name = path.name
    rows = []

    # select parser by filename
    if "stat__spotify" in name or "stat__spotify" in name.replace("-", "_"):
        # determine metric from filename
        if "field-followers" in name:
            rows.extend(parse_spotify_stat(data, "followers", name))
        elif "field-listeners" in name:
            rows.extend(parse_spotify_stat(data, "listeners", name))
        else:
            # try both
            rows.extend(parse_spotify_stat(data, "listeners", name))
            rows.extend(parse_spotify_stat(data, "followers", name))

    elif "social-audience-stats" in name:
        rows.extend(parse_social_audience_stats(data, name))

    elif name.startswith("api__artist__") and "career" in name:
        rows.extend(parse_career(data, name))

    elif "past-artist-rank" in name:
        rows.extend(parse_past_artist_rank(data, name, name))

    else:
        # fallback: try to find timeseries automatically
        rows.extend(_generic_timeseries_parse(data, name))

    return rows


def _generic_timeseries_parse(data, source_endpoint):
    # similar to earlier extract_time_series but returns normalized rows
    rows = []

    def recurse(obj, path=""):
        if isinstance(obj, list):
            for i, it in enumerate(obj):
                recurse(it, f"{path}[{i}]")

        elif isinstance(obj, dict):
            # look for timestp or date
            keys = obj.keys()
            date_key = None
            for k in keys:
                if k.lower() in ("timestp", "timestamp", "date") or k.lower().endswith("date"):
                    date_key = k
                    break

            if date_key:
                date = obj.get(date_key)
                for k, v in obj.items():
                    if k == date_key:
                        continue
                    num = _safe_numeric(v)
                    metric_name = f"{path}.{k}" if path else k
                    rows.append(
                        {
                            "artist_id": DEFAULT_ARTIST_ID,
                            "artist_name": DEFAULT_ARTIST_NAME,
                            "date": date,
                            "platform": None,
                            "metric": metric_name,
                            "value_numeric": num,
                            "value_text": None if num is not None else (str(v) if v is not None else None),
                            "diff": None,
                            "monthly_diff": None,
                            "monthly_diff_percent": None,
                            "is_interpolated": False,
                            "source_endpoint": source_endpoint,
                            "status": "ok",
                        }
                    )
                return

            for k, v in obj.items():
                recurse(v, f"{path}.{k}" if path else k)

    recurse(data)
    return rows


@st.cache_data
def load_normalized_metrics() -> pd.DataFrame:
    # Attempt to load existing normalized file
    if NORMALIZED_PATH.exists():
        try:
            return pd.read_csv(NORMALIZED_PATH, parse_dates=["date"], keep_default_na=False)
        except Exception:
            pass

    # else build from raw files
    all_rows = []
    if RAW_DIR.exists():
        for path in sorted(RAW_DIR.glob("*.json")):
            try:
                rows = parse_raw_file(path)
                all_rows.extend(rows)
            except Exception:
                continue

    if not all_rows:
        df = pd.DataFrame(columns=["artist_id", "artist_name", "date", "platform", "metric", "value_numeric", "value_text", "diff", "monthly_diff", "monthly_diff_percent", "is_interpolated", "source_endpoint", "status"])
        df.to_csv(NORMALIZED_PATH, index=False)
        return df

    df = pd.DataFrame(all_rows)
    # normalize date
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df.to_csv(NORMALIZED_PATH, index=False)
    return df


def _display_kpi(col, label, value, fmt="{:,}"):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        col.markdown(f"**{label}**")
        col.write("Missing")
    else:
        col.metric(label, fmt.format(int(value)) if isinstance(value, (int, float)) else str(value))


def main():
    st.title("Artist Intelligence Demo — Len Faki")

    df = load_normalized_metrics()

    artists = df["artist_name"].dropna().unique().tolist() if not df.empty else [DEFAULT_ARTIST_NAME]
    if DEFAULT_ARTIST_NAME not in artists:
        artists.insert(0, DEFAULT_ARTIST_NAME)

    st.sidebar.header("Controls")
    artist = st.sidebar.selectbox("Artist", options=artists, index=0)

    # Tabs: Overview, Trends, Data Availability, Raw Debug
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Trends", "Data Availability", "Raw Debug"])

    artist_df = df[df["artist_name"] == artist] if not df.empty else pd.DataFrame()

    # Overview
    with tab1:
        st.header("Overview")
        cols = st.columns(4)

        def latest_value(metric_key, platform=None):
            if artist_df.empty:
                return None
            q = artist_df[artist_df["metric"] == metric_key]
            if platform:
                q = q[q["platform"] == platform]
            q = q.dropna(subset=["date"]) if "date" in q.columns else q
            if q.empty:
                return None
            q = q.sort_values("date", ascending=False)
            v = q.iloc[0]["value_numeric"] if "value_numeric" in q.columns else None
            if pd.isna(v):
                return None
            return v

        sp_followers = latest_value("followers") if not artist_df.empty else None
        sp_listeners = latest_value("listeners") if not artist_df.empty else None
        ig_followers = latest_value("instagram_followers") if not artist_df.empty else None
        ig_eng = latest_value("instagram_engagement_rate") if not artist_df.empty else None
        career_stage = None
        career_momentum = None
        artist_rank = None

        # career stage & momentum
        q_stage = artist_df[artist_df["metric"] == "career_stage"] if not artist_df.empty else pd.DataFrame()
        if not q_stage.empty:
            # take latest
            q_stage = q_stage.sort_values(by="date", ascending=False)
            career_stage = q_stage.iloc[0]["value_text"]
            career_stage_score = q_stage.iloc[0]["value_numeric"]
        else:
            career_stage_score = None

        q_mom = artist_df[artist_df["metric"] == "career_momentum"] if not artist_df.empty else pd.DataFrame()
        if not q_mom.empty:
            q_mom = q_mom.sort_values(by="date", ascending=False)
            career_momentum = q_mom.iloc[0]["value_text"]
            career_momentum_score = q_mom.iloc[0]["value_numeric"]
        else:
            career_momentum_score = None

        q_rank = artist_df[artist_df["metric"] == "artist_rank"] if not artist_df.empty else pd.DataFrame()
        if not q_rank.empty:
            q_rank = q_rank.sort_values(by="date", ascending=False)
            artist_rank = q_rank.iloc[0]["value_numeric"]

        _display_kpi(cols[0], "Spotify Followers", sp_followers)
        _display_kpi(cols[1], "Spotify Listeners", sp_listeners)
        _display_kpi(cols[2], "Instagram Followers", ig_followers)
        _display_kpi(cols[3], "Instagram Engagement Rate", ig_eng)

        cols2 = st.columns(4)
        _display_kpi(cols2[0], "Career Stage Score", career_stage_score)
        cols2[1].markdown("**Career Stage**")
        cols2[1].write(career_stage or "Missing")
        _display_kpi(cols2[2], "Career Momentum Score", career_momentum_score)
        _display_kpi(cols2[3], "Artist Rank", artist_rank)

        # completeness
        available = 0
        for sig in EXPECTED_SIGNALS:
            if sig == "spotify_followers":
                if not artist_df[artist_df["metric"] == "followers"].empty:
                    available += 1
            elif sig == "spotify_listeners":
                if not artist_df[artist_df["metric"] == "listeners"].empty:
                    available += 1
            elif sig == "instagram_followers":
                if not artist_df[artist_df["metric"] == "instagram_followers"].empty:
                    available += 1
            elif sig == "instagram_engagement_rate":
                if not artist_df[artist_df["metric"] == "instagram_engagement_rate"].empty:
                    available += 1
            elif sig == "career_stage":
                if not artist_df[artist_df["metric"] == "career_stage"].empty:
                    available += 1
            elif sig == "career_momentum":
                if not artist_df[artist_df["metric"] == "career_momentum"].empty:
                    available += 1
            elif sig == "artist_rank":
                if not artist_df[artist_df["metric"] == "artist_rank"].empty:
                    available += 1

        completeness = int(100 * available / len(EXPECTED_SIGNALS)) if EXPECTED_SIGNALS else 0
        if completeness >= 70:
            confidence = "High"
        elif completeness >= 40:
            confidence = "Medium"
        else:
            confidence = "Low"

        st.markdown(f"**Data completeness:** {completeness}% — {confidence} confidence")

        # Interpretation
        st.subheader("Interpretation")
        lines = []
        lines.append(f"{artist} data coverage: {completeness}% ({confidence}).")
        if not artist_df.empty and not artist_df[artist_df["metric"] == "followers"].empty:
            lines.append("Spotify follower data available.")
        else:
            lines.append("No Spotify follower data found.")

        if not artist_df.empty and not artist_df[artist_df["metric"] == "instagram_followers"].empty:
            lines.append("Instagram data available.")
        else:
            lines.append("No Instagram data found; artist may not have a linked Instagram in Chartmetric.")

        st.write(" ".join(lines))

    # Trends
    with tab2:
        st.header("Trends")
        if artist_df.empty:
            st.info("No normalized data available for this artist.")
        else:
            metrics_map = {
                "Spotify Followers": ("followers", "spotify"),
                "Spotify Listeners": ("listeners", "spotify"),
                "Instagram Followers": ("instagram_followers", "instagram"),
                "Instagram Engagement Rate": ("instagram_engagement_rate", "instagram"),
                "Career Stage Score": ("career_stage", "chartmetric"),
                "Career Momentum Score": ("career_momentum", "chartmetric"),
                "Artist Rank": ("artist_rank", "chartmetric"),
            }

            chosen_label = st.selectbox("Choose metric", options=list(metrics_map.keys()), index=0)
            metric_key, platform = metrics_map[chosen_label]

            chart_df = artist_df[artist_df["metric"] == metric_key].copy()
            if chart_df.empty:
                st.info("No data available for this metric.")
            else:
                chart_df = chart_df.dropna(subset=["date"]).sort_values(by="date")
                if chart_df.empty:
                    st.info("No dated observations available for this metric.")
                else:
                    c = (
                        alt.Chart(chart_df)
                        .mark_line(point=True)
                        .encode(x=alt.X("date:T", title="Date"), y=alt.Y("value_numeric:Q", title=chosen_label), tooltip=["date", "value_numeric"])
                        .interactive()
                    )
                    st.altair_chart(c, use_container_width=True)

    # Data Availability
    with tab3:
        st.header("Data Availability")
        table = []
        for sig in EXPECTED_SIGNALS:
            present = False
            note = ""
            used = True
            if sig == "spotify_followers":
                present = not artist_df[artist_df["metric"] == "followers"].empty
                note = "" if present else "No Spotify follower time series found."
            elif sig == "spotify_listeners":
                present = not artist_df[artist_df["metric"] == "listeners"].empty
            elif sig == "instagram_followers":
                present = not artist_df[artist_df["metric"] == "instagram_followers"].empty
                if not present:
                    note = "No Instagram data found. This may mean the artist has no linked Instagram profile in Chartmetric."
            elif sig == "instagram_engagement_rate":
                present = not artist_df[artist_df["metric"] == "instagram_engagement_rate"].empty
            elif sig == "career_stage":
                present = not artist_df[artist_df["metric"] == "career_stage"].empty
            elif sig == "career_momentum":
                present = not artist_df[artist_df["metric"] == "career_momentum"].empty
            elif sig == "artist_rank":
                present = not artist_df[artist_df["metric"] == "artist_rank"].empty

            table.append({"signal": sig, "available": "Yes" if present else "Missing", "used_in_demo": "Yes" if used else "No", "notes": note})

        st.table(pd.DataFrame(table))

    # Raw Debug
    with tab4:
        st.header("Raw Debug")
        if SUMMARY_CSV.exists():
            if st.checkbox("Show probe summary CSV"):
                try:
                    summary = pd.read_csv(SUMMARY_CSV)
                    st.dataframe(summary)
                except Exception as e:
                    st.error(f"Could not read summary CSV: {e}")

        raw_files = sorted(RAW_DIR.glob("*.json")) if RAW_DIR.exists() else []
        if not raw_files:
            st.info("No raw JSON files found in chartmetric_len_faki_history_raw/")
        else:
            choice = st.selectbox("Choose raw file", options=[p.name for p in raw_files])
            sel = RAW_DIR / choice
            if st.checkbox("Show raw JSON"):
                data = _read_json(sel)
                st.json(data)

            if st.checkbox("Show extracted normalized rows from this file"):
                rows = parse_raw_file(sel)
                if not rows:
                    st.info("No normalized rows could be extracted from this file.")
                else:
                    st.dataframe(pd.DataFrame(rows).head(200))


if __name__ == "__main__":
    main()
