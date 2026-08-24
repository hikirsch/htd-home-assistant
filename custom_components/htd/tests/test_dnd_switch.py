"""Tests for HtdDndSwitch in switch.py."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.htd.const import CONF_ZONE_NAMES
from custom_components.htd.switch import HtdDndSwitch, async_setup_entry


def _make_client(kind_value="lync", zone_name=None, has_zone_data=True, dnd=False):
    client = MagicMock()
    client.model = {"kind": MagicMock(value=kind_value)}
    client.async_set_dnd = AsyncMock()
    client.get_zone_name = MagicMock(return_value=zone_name)
    client.has_zone_data = MagicMock(return_value=has_zone_data)
    zone = MagicMock()
    zone.dnd = dnd
    client.get_zone = MagicMock(return_value=zone)
    return client


def _make_config_entry(zone_names=None):
    entry = MagicMock()
    entry.data = {CONF_ZONE_NAMES: zone_names or {}}
    return entry


def _make_entity(client, zone=1, zone_names=None):
    return HtdDndSwitch(client, "uid", zone=zone, config_entry=_make_config_entry(zone_names))


def test_is_on_reflects_zone_dnd():
    client = _make_client(dnd=True)
    entity = _make_entity(client)
    assert entity.is_on is True


def test_is_on_false_when_dnd_off():
    client = _make_client(dnd=False)
    entity = _make_entity(client)
    assert entity.is_on is False


def test_is_on_none_when_no_zone_data():
    client = _make_client(has_zone_data=False)
    entity = _make_entity(client)
    assert entity.is_on is None


def test_async_turn_on_calls_set_dnd():
    client = _make_client()
    entity = _make_entity(client, zone=2)
    asyncio.run(entity.async_turn_on())
    client.async_set_dnd.assert_called_once_with(2, True)


def test_async_turn_off_calls_set_dnd():
    client = _make_client()
    entity = _make_entity(client, zone=3)
    asyncio.run(entity.async_turn_off())
    client.async_set_dnd.assert_called_once_with(3, False)


def test_no_entities_for_mca():
    client = _make_client(kind_value="mca")
    config_entry = MagicMock()
    config_entry.runtime_data = client

    captured = []
    asyncio.run(async_setup_entry(None, config_entry, lambda ents: captured.extend(ents)))
    assert captured == []
    client.get_zone_count.assert_not_called()


def test_entity_name_uses_zone_override():
    client = _make_client(zone_name="Kitchen")
    entity = _make_entity(client, zone=1, zone_names={"1": "01-Family Room"})
    assert entity.name == "01-Family Room - DND"


def test_entity_name_falls_back_to_client_zone_name():
    client = _make_client(zone_name="Kitchen")
    entity = _make_entity(client, zone=1)  # no zone_names override
    assert entity.name == "Kitchen - DND"


def test_entity_name_falls_back_to_zone_n():
    client = _make_client(zone_name=None)
    entity = _make_entity(client, zone=4)
    assert entity.name == "Zone 4 - DND"
