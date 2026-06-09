def flatten_chartmetric_metrics(data):
    obj = data["obj"]
    stats = obj.get("cm_statistics") or {}
    career = obj.get("career_status") or {}

    return {
        "cm_artist_id": obj.get("id"),
        "name": obj.get("name"),

        # Chartmetric core
        "cm_artist_rank": stats.get("cm_artist_rank"),
        "cm_artist_score": stats.get("cm_artist_score"),
        "fan_base_rank": stats.get("fan_base_rank") or stats.get("rank_fb"),
        "engagement_rank": stats.get("engagement_rank") or stats.get("rank_eg"),

        # Spotify
        "spotify_followers": stats.get("sp_followers"),
        "spotify_monthly_listeners": stats.get("sp_monthly_listeners"),
        "spotify_popularity": stats.get("sp_popularity"),

        # Instagram
        "instagram_followers": stats.get("ins_followers"),

        # YouTube
        "youtube_subscribers": stats.get("ycs_subscribers"),
        "youtube_views": stats.get("ycs_views"),

        # TikTok
        "tiktok_followers": stats.get("tiktok_followers"),
        "tiktok_likes": stats.get("tiktok_likes"),
        "tiktok_top_video_views": stats.get("tiktok_top_video_views"),
        "tiktok_track_posts": stats.get("tiktok_track_posts"),

        # Career signal
        "career_stage_score": career.get("stage_score"),
        "career_trend_score": career.get("trend_score"),
    }