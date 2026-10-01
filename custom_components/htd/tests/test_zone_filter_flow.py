"""Tests for zone filter submission logic in config_flow.py."""


def _zone_filter_result(user_input: dict, zone_count: int) -> tuple[bool, list]:
    """Replicate the zone filter reduction logic from async_step_zone_filter."""
    enabled = [
        i for i in range(1, zone_count + 1)
        if user_input.get(f"zone_{i}_enabled", True)
    ]
    if len(enabled) == zone_count:
        return False, []
    return True, enabled


def test_all_checked_filter_disabled():
    # When every zone is checked, filter flag is False and list is empty
    ui = {f"zone_{i}_enabled": True for i in range(1, 4)}
    flag, zones = _zone_filter_result(ui, 3)
    assert flag is False
    assert zones == []


def test_missing_keys_default_true_no_filter():
    # Absent keys default to True → same as all checked
    flag, zones = _zone_filter_result({}, 3)
    assert flag is False
    assert zones == []


def test_some_unchecked_filter_enabled():
    ui = {"zone_1_enabled": True, "zone_2_enabled": False, "zone_3_enabled": True}
    flag, zones = _zone_filter_result(ui, 3)
    assert flag is True
    assert zones == [1, 3]


def test_single_zone_enabled():
    ui = {"zone_1_enabled": False, "zone_2_enabled": True, "zone_3_enabled": False}
    flag, zones = _zone_filter_result(ui, 3)
    assert flag is True
    assert zones == [2]


def test_all_unchecked_filter_enabled_empty_list():
    # All unchecked → filter_enabled=True, enabled_zones=[]
    # (user would have no active zones — unusual but valid; HA can show nothing)
    ui = {f"zone_{i}_enabled": False for i in range(1, 4)}
    flag, zones = _zone_filter_result(ui, 3)
    assert flag is True
    assert zones == []
