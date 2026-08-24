"""Tests for zone-filter entity_registry_enabled_default across all entity platforms."""
import sys
from unittest.mock import MagicMock

from homeassistant.const import CONF_UNIQUE_ID

from custom_components.htd.const import (
    CONF_ZONE_FILTER_ENABLED,
    CONF_ENABLED_ZONES,
    CONF_ZONE_NAMES,
)
from custom_components.htd.media_player import HtdDevice
from custom_components.htd.number import HtdEqNumber
from custom_components.htd.switch import HtdDndSwitch


def _make_filter_entry(filter_enabled: bool, enabled_zones: list):
    entry = MagicMock()
    entry.data = {
        CONF_ZONE_FILTER_ENABLED: filter_enabled,
        CONF_ENABLED_ZONES: enabled_zones,
        CONF_ZONE_NAMES: {},
        CONF_UNIQUE_ID: "uid",
    }
    return entry


def _make_client(kind_value="lync"):
    client = MagicMock()
    client.model = {"kind": MagicMock(value=kind_value), "zones": 12}
    client.get_zone_name = MagicMock(return_value=None)
    return client


# --- HtdDevice (media_player) ---

def test_media_player_enabled_when_filter_off():
    entry = _make_filter_entry(False, [])
    client = _make_client()
    device = HtdDevice("uid", "HTD", zone=3, sources=[], client=client, config_entry=entry)
    assert device.entity_registry_enabled_default is True


def test_media_player_enabled_when_zone_in_filter():
    entry = _make_filter_entry(True, [1, 3, 5])
    client = _make_client()
    device = HtdDevice("uid", "HTD", zone=3, sources=[], client=client, config_entry=entry)
    assert device.entity_registry_enabled_default is True


def test_media_player_disabled_when_zone_not_in_filter():
    entry = _make_filter_entry(True, [1, 3, 5])
    client = _make_client()
    device = HtdDevice("uid", "HTD", zone=2, sources=[], client=client, config_entry=entry)
    assert device.entity_registry_enabled_default is False


def test_media_player_no_config_entry_returns_true():
    client = _make_client()
    device = HtdDevice("uid", "HTD", zone=2, sources=[], client=client, config_entry=None)
    assert device.entity_registry_enabled_default is True


# --- HtdEqNumber (number) ---

def test_eq_number_enabled_when_filter_off():
    entry = _make_filter_entry(False, [])
    client = _make_client()
    entity = HtdEqNumber(client, "uid", zone=2, control="bass", config_entry=entry)
    assert entity.entity_registry_enabled_default is True


def test_eq_number_disabled_when_zone_not_in_filter():
    entry = _make_filter_entry(True, [1, 3])
    client = _make_client()
    entity = HtdEqNumber(client, "uid", zone=2, control="bass", config_entry=entry)
    assert entity.entity_registry_enabled_default is False


def test_eq_number_enabled_when_zone_in_filter():
    entry = _make_filter_entry(True, [1, 3])
    client = _make_client()
    entity = HtdEqNumber(client, "uid", zone=3, control="bass", config_entry=entry)
    assert entity.entity_registry_enabled_default is True


def test_eq_balance_hidden_by_default_when_filter_off():
    # Balance is hidden by default even when filter is off
    entry = _make_filter_entry(False, [])
    client = _make_client()
    entity = HtdEqNumber(client, "uid", zone=1, control="balance", config_entry=entry)
    assert entity.entity_registry_enabled_default is False


def test_eq_balance_disabled_when_zone_not_in_filter():
    # Zone filter takes priority (zone disabled → entity disabled)
    entry = _make_filter_entry(True, [1, 3])
    client = _make_client()
    entity = HtdEqNumber(client, "uid", zone=2, control="balance", config_entry=entry)
    assert entity.entity_registry_enabled_default is False


# --- HtdDndSwitch (switch) ---

def test_dnd_enabled_when_filter_off():
    entry = _make_filter_entry(False, [])
    client = _make_client()
    entity = HtdDndSwitch(client, "uid", zone=1, config_entry=entry)
    assert entity.entity_registry_enabled_default is True


def test_dnd_enabled_when_zone_in_filter():
    entry = _make_filter_entry(True, [1, 4])
    client = _make_client()
    entity = HtdDndSwitch(client, "uid", zone=1, config_entry=entry)
    assert entity.entity_registry_enabled_default is True


def test_dnd_disabled_when_zone_not_in_filter():
    entry = _make_filter_entry(True, [1, 4])
    client = _make_client()
    entity = HtdDndSwitch(client, "uid", zone=2, config_entry=entry)
    assert entity.entity_registry_enabled_default is False
