def is_player_inside_district(lat: float, lng: float, district) -> bool:
    """Проверяет, находятся ли координаты внутри границ района."""
    return (
        district.min_lat <= lat <= district.max_lat and
        district.min_lng <= lng <= district.max_lng
    )