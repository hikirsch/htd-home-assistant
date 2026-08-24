"""Tests for EQ control helpers and dispatch logic in number.py."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.htd.number import _eq_range, _eq_enabled_default, HtdEqNumber


# --- Range lookup ---

def test_lync_bass_range():
    assert _eq_range("lync", "bass") == (-10.0, 10.0, 1.0)


def test_lync_treble_range():
    assert _eq_range("lync", "treble") == (-10.0, 10.0, 1.0)


def test_lync_balance_range():
    assert _eq_range("lync", "balance") == (-18.0, 18.0, 1.0)


def test_mca_bass_range():
    assert _eq_range("mca", "bass") == (-12.0, 12.0, 4.0)


def test_mca_treble_range():
    assert _eq_range("mca", "treble") == (-12.0, 12.0, 4.0)


def test_mca_balance_range():
    assert _eq_range("mca", "balance") == (-12.0, 12.0, 6.0)


# --- Enabled defaults ---

def test_bass_enabled_by_default():
    assert _eq_enabled_default("bass") is True


def test_treble_enabled_by_default():
    assert _eq_enabled_default("treble") is True


def test_balance_disabled_by_default():
    assert _eq_enabled_default("balance") is False


# --- Dispatch ---

def _make_client(kind_value="lync", zone_name=None):
    client = MagicMock()
    client.model = {"kind": MagicMock(value=kind_value)}
    client.async_set_bass = AsyncMock()
    client.async_set_treble = AsyncMock()
    client.async_set_balance = AsyncMock()
    client.get_zone_name = MagicMock(return_value=zone_name)
    return client


def _make_config_entry(zone_names=None):
    entry = MagicMock()
    entry.data = {"zone_names": zone_names or {}}
    return entry


def _make_entity(client, control, zone=1, zone_names=None):
    return HtdEqNumber(client, "uid", zone=zone, control=control, config_entry=_make_config_entry(zone_names))


# --- Name resolution ---

def test_name_uses_config_override():
    client = _make_client(zone_name="Library")
    entity = _make_entity(client, "bass", zone=1, zone_names={"1": "01-Family Room"})
    assert entity.name == "01-Family Room - Bass"


def test_name_falls_back_to_client_zone_name():
    client = _make_client(zone_name="Library")
    entity = _make_entity(client, "treble", zone=1)
    assert entity.name == "Library - Treble"


def test_name_falls_back_to_zone_number():
    client = _make_client(zone_name=None)
    entity = _make_entity(client, "balance", zone=3)
    assert entity.name == "Zone 3 - Balance"


# --- Dispatch ---

def test_bass_dispatch():
    client = _make_client("lync")
    entity = _make_entity(client, "bass", zone=1)
    asyncio.run(entity.async_set_native_value(5.0))
    client.async_set_bass.assert_called_once_with(1, 5)
    client.async_set_treble.assert_not_called()
    client.async_set_balance.assert_not_called()


def test_treble_dispatch():
    client = _make_client("lync")
    entity = _make_entity(client, "treble", zone=2)
    asyncio.run(entity.async_set_native_value(-3.0))
    client.async_set_treble.assert_called_once_with(2, -3)
    client.async_set_bass.assert_not_called()
    client.async_set_balance.assert_not_called()


def test_balance_dispatch():
    client = _make_client("mca")
    entity = _make_entity(client, "balance", zone=3)
    asyncio.run(entity.async_set_native_value(6.0))
    client.async_set_balance.assert_called_once_with(3, 6)
    client.async_set_bass.assert_not_called()
    client.async_set_treble.assert_not_called()
