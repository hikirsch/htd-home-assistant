from unittest.mock import MagicMock


def _make_device(zone_names_override=None, source_names_override=None,
                  controller_zone_name=None, controller_source_name=None):
    """Build a minimal HtdDevice-like object to test name resolution."""
    config_entry = MagicMock()
    config_entry.data = {
        "zone_names": zone_names_override or {},
        "source_names": source_names_override or {},
    }
    client = MagicMock()
    client.get_zone_name.return_value = controller_zone_name
    client.get_source_name.return_value = controller_source_name or f"Source 1"
    return config_entry, client


def resolve_zone_name(zone, config_entry, client):
    overrides = config_entry.data.get("zone_names", {})
    return overrides.get(str(zone)) or client.get_zone_name(zone) or f"Zone {zone}"


def resolve_source_name(source, config_entry, client):
    overrides = config_entry.data.get("source_names", {})
    return overrides.get(str(source)) or client.get_source_name(source) or f"Source {source}"


def test_zone_name_uses_ha_override_first():
    config_entry, client = _make_device(
        zone_names_override={"1": "Living Room"},
        controller_zone_name="lounge"
    )
    assert resolve_zone_name(1, config_entry, client) == "Living Room"


def test_zone_name_falls_back_to_controller():
    config_entry, client = _make_device(controller_zone_name="office")
    assert resolve_zone_name(1, config_entry, client) == "office"


def test_zone_name_falls_back_to_numeric():
    config_entry, client = _make_device(controller_zone_name=None)
    client.get_zone_name.return_value = None
    assert resolve_zone_name(3, config_entry, client) == "Zone 3"


def test_source_name_uses_ha_override_first():
    config_entry, client = _make_device(
        source_names_override={"1": "Spotify"},
        controller_source_name="source 1"
    )
    assert resolve_source_name(1, config_entry, client) == "Spotify"


def test_source_name_falls_back_to_controller():
    config_entry, client = _make_device(controller_source_name="Apple TV")
    assert resolve_source_name(2, config_entry, client) == "Apple TV"


def test_source_name_falls_back_to_numeric():
    config_entry, client = _make_device()
    client.get_source_name.return_value = None
    assert resolve_source_name(5, config_entry, client) == "Source 5"


def test_empty_string_override_treated_as_no_override():
    config_entry, client = _make_device(
        zone_names_override={"1": ""},
        controller_zone_name="den"
    )
    assert resolve_zone_name(1, config_entry, client) == "den"
