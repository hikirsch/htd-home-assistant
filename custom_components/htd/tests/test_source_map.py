from unittest.mock import MagicMock


def _make_map_fn(filter_enabled, zone_filters, source_overrides=None, controller_names=None, source_count=3, zone=1):
    """Replicate _build_source_map logic for isolated testing (no HA imports needed)."""
    source_overrides = source_overrides or {}
    controller_names = controller_names or {}

    def _controller_name(i):
        return controller_names.get(str(i))

    def _resolve(i):
        return source_overrides.get(str(i)) or _controller_name(i) or f"Source {i}"

    def build():
        allowed_filter = zone_filters.get(str(zone)) if filter_enabled else None
        allowed = [
            i for i in range(1, source_count + 1)
            if allowed_filter is None or not allowed_filter or i in allowed_filter
        ]
        result = {}
        for i in allowed:
            controller_name = _controller_name(i)
            if controller_name:
                result[controller_name] = i
            result[_resolve(i)] = i
        for i in allowed:
            result[f"Source {i}"] = i
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


def test_map_contains_generic_and_resolved_keys_for_same_index():
    fn = _make_map_fn(
        filter_enabled=False, zone_filters={},
        source_overrides={"2": "Spotify"}, source_count=3
    )
    m = fn()
    assert m["Source 2"] == 2
    assert m["Spotify"] == 2


def test_map_contains_controller_native_key_when_distinct_from_override():
    fn = _make_map_fn(
        filter_enabled=False, zone_filters={},
        source_overrides={"2": "Living Room"},
        controller_names={"2": "AppleTV"},
        source_count=3,
    )
    m = fn()
    assert m["Source 2"] == 2
    assert m["AppleTV"] == 2
    assert m["Living Room"] == 2


def test_filtered_source_has_no_aliases_in_map():
    fn = _make_map_fn(
        filter_enabled=True, zone_filters={"1": [1, 3]},
        source_overrides={"2": "Living Room"},
        controller_names={"2": "AppleTV"},
        source_count=3, zone=1,
    )
    m = fn()
    assert "Living Room" not in m
    assert "AppleTV" not in m
    assert "Source 2" not in m


def test_generic_label_wins_over_colliding_override():
    fn = _make_map_fn(
        filter_enabled=False, zone_filters={},
        source_overrides={"5": "Source 3"}, source_count=5,
    )
    m = fn()
    assert m["Source 3"] == 3
    assert m["Source 5"] == 5


# --- Real-import coverage: HtdDevice source aliasing (issue #26) ---

import asyncio
import logging
from unittest.mock import AsyncMock

from homeassistant.const import CONF_UNIQUE_ID

from custom_components.htd.const import (
    CONF_SOURCE_NAMES,
    CONF_SOURCE_FILTER_ENABLED,
    CONF_ZONE_SOURCE_FILTERS,
)
from custom_components.htd.media_player import HtdDevice


def _make_source_entry(source_overrides=None, filter_enabled=False, zone_filters=None):
    entry = MagicMock()
    entry.data = {
        CONF_SOURCE_NAMES: source_overrides or {},
        CONF_SOURCE_FILTER_ENABLED: filter_enabled,
        CONF_ZONE_SOURCE_FILTERS: zone_filters or {},
        CONF_UNIQUE_ID: "uid",
    }
    return entry


def _make_source_client(controller_names=None):
    controller_names = controller_names or {}
    client = MagicMock()
    client.get_source_name = MagicMock(side_effect=lambda i: controller_names.get(i) or f"Source {i}")
    # get_source_names reports only what the controller actually said (no invented
    # "Source N" entries), matching the real htd-client-ha contract that
    # _resolve_source_name's cached-name fallback relies on.
    client.get_source_names = MagicMock(return_value=dict(controller_names))
    client.async_set_source = AsyncMock()
    client.model = {"zones": 6}
    return client


def _make_device(client, entry, zone=1, source_count=3):
    sources = [f"Source {i}" for i in range(1, source_count + 1)]
    return HtdDevice("uid", "HTD", zone=zone, sources=sources, client=client, config_entry=entry)


def test_select_source_by_old_generic_name_after_rename():
    # Source 2 renamed to "Spotify" via the options flow.
    client = _make_source_client()
    entry = _make_source_entry(source_overrides={"2": "Spotify"})
    device = _make_device(client, entry)

    asyncio.run(device.async_select_source("Source 2"))

    client.async_set_source.assert_called_once_with(1, 2)


def test_select_source_by_controller_native_name_after_rename():
    # Controller reports "AppleTV" for source 2; HA override renames it to "Living Room".
    client = _make_source_client(controller_names={2: "AppleTV"})
    entry = _make_source_entry(source_overrides={"2": "Living Room"})
    device = _make_device(client, entry)

    asyncio.run(device.async_select_source("AppleTV"))

    client.async_set_source.assert_called_once_with(1, 2)


def test_select_source_by_current_name_still_works():
    client = _make_source_client(controller_names={2: "AppleTV"})
    entry = _make_source_entry(source_overrides={"2": "Living Room"})
    device = _make_device(client, entry)

    asyncio.run(device.async_select_source("Living Room"))

    client.async_set_source.assert_called_once_with(1, 2)


def test_filtered_out_source_does_not_resolve_via_any_alias():
    # Zone 1 only allows sources [1, 3]; source 2 is renamed but excluded by the filter.
    client = _make_source_client(controller_names={2: "AppleTV"})
    entry = _make_source_entry(
        source_overrides={"2": "Living Room"},
        filter_enabled=True,
        zone_filters={"1": [1, 3]},
    )
    device = _make_device(client, entry)

    asyncio.run(device.async_select_source("Source 2"))
    asyncio.run(device.async_select_source("AppleTV"))
    asyncio.run(device.async_select_source("Living Room"))

    client.async_set_source.assert_not_called()


def test_source_list_shows_one_entry_per_visible_index_using_current_name():
    client = _make_source_client(controller_names={2: "AppleTV"})
    entry = _make_source_entry(source_overrides={"2": "Living Room"})
    device = _make_device(client, entry)

    assert device.source_list == ["Source 1", "Living Room", "Source 3"]


def test_source_list_respects_filter():
    client = _make_source_client(controller_names={2: "AppleTV"})
    entry = _make_source_entry(
        source_overrides={"2": "Living Room"},
        filter_enabled=True,
        zone_filters={"1": [1, 3]},
    )
    device = _make_device(client, entry)

    assert device.source_list == ["Source 1", "Source 3"]


def test_generic_label_wins_over_colliding_display_name():
    # Source 5's display name has been overridden to the literal label of source 3.
    # "Source 3" must still select source 3 — that string is the stable handle
    # exposed as the source_id attribute, so it cannot be hijacked by a rename.
    client = _make_source_client()
    entry = _make_source_entry(source_overrides={"5": "Source 3"})
    device = _make_device(client, entry, source_count=5)

    asyncio.run(device.async_select_source("Source 3"))

    client.async_set_source.assert_called_once_with(1, 3)


def test_every_generic_label_maps_to_its_own_index():
    client = _make_source_client(controller_names={2: "AppleTV"})
    entry = _make_source_entry(source_overrides={"5": "Source 3", "2": "Living Room"})
    device = _make_device(client, entry, source_count=5)

    source_map = device._build_source_map()

    for i in range(1, 6):
        assert source_map[f"Source {i}"] == i


def test_source_id_reports_generic_label_for_current_index():
    client = _make_source_client()
    entry = _make_source_entry()
    device = _make_device(client, entry)
    device.zone_info = MagicMock(source=3)

    assert device.extra_state_attributes == {"source_id": "Source 3"}


def test_source_id_survives_rename_while_source_follows_it():
    # The whole point of the feature: renaming a source changes what a human
    # sees, and must not change what an automation matches on.
    client = _make_source_client()
    entry = _make_source_entry(source_overrides={"3": "Spotify"})
    device = _make_device(client, entry)
    device.zone_info = MagicMock(source=3)

    assert device.source == "Spotify"
    assert device.extra_state_attributes["source_id"] == "Source 3"


def test_source_id_follows_active_source_change():
    client = _make_source_client()
    entry = _make_source_entry()
    device = _make_device(client, entry)

    device.zone_info = MagicMock(source=1)
    assert device.extra_state_attributes["source_id"] == "Source 1"

    device.zone_info = MagicMock(source=2)
    assert device.extra_state_attributes["source_id"] == "Source 2"


def test_extra_state_attributes_empty_without_zone_info():
    client = _make_source_client()
    entry = _make_source_entry()
    device = _make_device(client, entry)
    device.zone_info = None

    assert device.extra_state_attributes == {}


def test_source_id_reports_current_source_even_when_filtered_out_of_zone():
    # State must stay truthful: a source filter restricts what this zone can be
    # *switched to*, it does not change what the zone is actually playing.
    client = _make_source_client()
    entry = _make_source_entry(filter_enabled=True, zone_filters={"1": [1, 3]})
    device = _make_device(client, entry)
    device.zone_info = MagicMock(source=2)

    assert device.extra_state_attributes["source_id"] == "Source 2"


def test_source_id_round_trips_into_select_source():
    # An automation can read source_id off one zone and feed it straight back
    # into select_source on another, with no name lookup in between.
    client = _make_source_client(controller_names={3: "AppleTV"})
    entry = _make_source_entry(source_overrides={"3": "Spotify"})
    device = _make_device(client, entry)
    device.zone_info = MagicMock(source=3)

    asyncio.run(device.async_select_source(device.extra_state_attributes["source_id"]))

    client.async_set_source.assert_called_once_with(1, 3)


def test_select_source_warns_on_unresolvable_name(caplog):
    client = _make_source_client()
    entry = _make_source_entry()
    device = _make_device(client, entry)

    with caplog.at_level(logging.WARNING, logger="custom_components.htd.media_player"):
        asyncio.run(device.async_select_source("Nonexistent"))

    client.async_set_source.assert_not_called()
    assert "Nonexistent" in caplog.text


def test_select_source_warns_when_source_filtered_out_of_zone(caplog):
    # The most likely real cause: the name is perfectly valid, just not
    # available to this zone. Silence here is what made issue #26 hard to
    # diagnose, so the warning must name the values that would have worked.
    client = _make_source_client()
    entry = _make_source_entry(filter_enabled=True, zone_filters={"1": [1, 3]})
    device = _make_device(client, entry)

    with caplog.at_level(logging.WARNING, logger="custom_components.htd.media_player"):
        asyncio.run(device.async_select_source("Source 2"))

    client.async_set_source.assert_not_called()
    assert "Source 1" in caplog.text
    assert "Source 3" in caplog.text


def test_select_source_does_not_warn_on_success(caplog):
    client = _make_source_client()
    entry = _make_source_entry()
    device = _make_device(client, entry)

    with caplog.at_level(logging.WARNING, logger="custom_components.htd.media_player"):
        asyncio.run(device.async_select_source("Source 2"))

    client.async_set_source.assert_called_once_with(1, 2)
    assert caplog.text == ""
