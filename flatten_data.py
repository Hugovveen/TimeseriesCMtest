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