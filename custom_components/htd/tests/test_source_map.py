from unittest.mock import MagicMock


def _make_map_fn(filter_enabled, zone_filters, source_overrides=None, source_count=3, zone=1):
    """Replicate _build_source_map logic for isolated testing (no HA imports needed)."""
    source_overrides = source_overrides or {}

    def _resolve(i):
        return source_overrides.get(str(i)) or f"Source {i}"

    def build():
        allowed = zone_filters.get(str(zone)) if filter_enabled else None
        result = {}
        for i in range(1, source_count + 1):
            if allowed is None or not allowed or i in allowed:
                result[_resolve(i)] = i
        return result

    return build


def test_filter_disabled_returns_all_sources():
    fn = _make_map_fn(filter_enabled=False, zone_filters={}, source_count=3)
    assert fn() == {"Source 1": 1, "Source 2": 2, "Source 3": 3}


def test_filter_enabled_whitelist_restricts_sources():
    fn = _make_map_fn(filter_enabled=True, zone_filters={"1": [1, 3]}, source_count=3, zone=1)
    result = fn()
    assert list(result.values()) == [1, 3]
    assert "Source 2" not in result


def test_filter_enabled_empty_whitelist_shows_all():
    fn = _make_map_fn(filter_enabled=True, zone_filters={"1": []}, source_count=3, zone=1)
    assert list(fn().values()) == [1, 2, 3]


def test_filter_enabled_zone_absent_shows_all():
    fn = _make_map_fn(filter_enabled=True, zone_filters={}, source_count=3, zone=1)
    assert list(fn().values()) == [1, 2, 3]


def test_selected_source_maps_to_controller_index_not_list_position():
    # Zone 1 whitelist: [1, 3] → display list ["Source 1", "Source 3"]
    # Selecting "Source 3" must yield controller index 3, not 2 (list position + 1)
    fn = _make_map_fn(filter_enabled=True, zone_filters={"1": [1, 3]}, source_count=3, zone=1)
    assert fn()["Source 3"] == 3  # not 2


def test_source_name_override_appears_in_map():
    fn = _make_map_fn(
        filter_enabled=False, zone_filters={},
        source_overrides={"2": "Spotify"}, source_count=3
    )
    m = fn()
    assert "Spotify" in m
    assert m["Spotify"] == 2
