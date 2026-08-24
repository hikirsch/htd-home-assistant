"""Setup must succeed with the amplifier powered off once the model has been seen once, and
must still raise ConfigEntryNotReady when it has not (issues #23 and #30).

Imports the real __init__.py, following the pattern in test_config_flow_probe.py, since this
tests actual control flow rather than replicated logic.
"""
import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady
from htd_client.exceptions import HtdConnectionError

from custom_components.htd.const import (
    CONF_CACHED_SOURCE_NAMES,
    CONF_CACHED_ZONE_NAMES,
    CONF_MODEL_KEY,
)

htd_init = importlib.import_module("custom_components.htd")

MCA66 = {"key": "mca66", "zones": 6, "sources": 6, "kind": MagicMock(value="mca")}


def _config_entry(data):
    entry = MagicMock()
    entry.data = data
    return entry


def _hass():
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    return hass


def _client(*, key="mca66", connected=True, zone_names=None, source_names=None):
    client = MagicMock()
    client.model = {"key": key, "zones": 6, "sources": 6, "kind": MagicMock(value="mca")}
    client.connected = connected
    client.get_source_count = MagicMock(return_value=6)
    client.get_zone_count = MagicMock(return_value=6)
    client.get_zone_names = MagicMock(return_value=zone_names or {})
    client.get_source_names = MagicMock(return_value=source_names or {})
    client.async_query_source_name = AsyncMock()
    client.async_query_zone_name = AsyncMock()
    client.async_start = AsyncMock()
    client.disconnect = MagicMock()
    return client


# --- legacy entries: unchanged behavior ---

def test_serial_setup_raises_config_entry_not_ready_when_device_unreachable():
    """Issue #23's guarantee. A first-time install still needs a live device, and when it is
    missing HA must retry with backoff rather than failing the entry permanently."""
    entry = _config_entry({CONF_PATH: "/dev/ttyUSB0"})
    hass = _hass()

    with patch.object(htd_init, "get_model_info", return_value=None), patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.side_effect = HtdConnectionError("no reply from device")

        with pytest.raises(ConfigEntryNotReady):
            asyncio.run(htd_init.async_setup_entry(hass, entry))


def test_network_setup_raises_config_entry_not_ready_when_device_unreachable():
    """Same guarantee over TCP."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006})
    hass = _hass()

    with patch.object(htd_init, "get_model_info", return_value=None), patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.side_effect = HtdConnectionError("no reply from device")

        with pytest.raises(ConfigEntryNotReady):
            asyncio.run(htd_init.async_setup_entry(hass, entry))


def test_setup_still_propagates_unrelated_errors():
    """Confirms the catch is scoped to HtdConnectionError, not a blanket except."""
    entry = _config_entry({CONF_PATH: "/dev/ttyUSB0"})
    hass = _hass()

    with patch.object(htd_init, "get_model_info", return_value=None), patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.side_effect = ValueError("Unknown Device Kind: foo")

        with pytest.raises(ValueError):
            asyncio.run(htd_init.async_setup_entry(hass, entry))


# --- migration: the first successful probe records the model ---

def test_legacy_entry_persists_the_model_key_after_a_successful_probe():
    """Until the key is stored, every restart needs a live device. This single write is what
    makes every later offline restart possible, and it is why upgrading users see no change
    until their amplifier is reachable once."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006})
    hass = _hass()
    client = _client()

    with patch.object(htd_init, "get_model_info", return_value=None), patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock, return_value=client
    ):
        assert asyncio.run(htd_init.async_setup_entry(hass, entry)) is True

    data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
    assert data[CONF_MODEL_KEY] == "mca66"


def test_model_key_is_persisted_before_the_update_listener_is_registered():
    """async_update_entry fires the update listener, and async_update_listener reloads the
    entry. Registering the listener first turns the first successful probe into an endless
    setup -> write -> reload -> setup loop that never lets Home Assistant finish starting."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006})
    hass = _hass()
    client = _client()

    order = []
    hass.config_entries.async_update_entry.side_effect = lambda *a, **k: order.append("persist")
    entry.add_update_listener.side_effect = lambda cb: order.append("listener")

    with patch.object(htd_init, "get_model_info", return_value=None), patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock, return_value=client
    ):
        asyncio.run(htd_init.async_setup_entry(hass, entry))

    assert order.index("persist") < order.index("listener")


def test_unrecognized_model_key_falls_back_to_the_probe():
    """An entry written by a newer version and then rolled back must degrade to today's
    behavior rather than failing the entry outright."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006, CONF_MODEL_KEY: "lync24"})
    hass = _hass()
    client = _client()

    with patch.object(htd_init, "get_model_info", return_value=None), patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock, return_value=client
    ) as probe, patch.object(htd_init, "build_client") as build:
        assert asyncio.run(htd_init.async_setup_entry(hass, entry)) is True

    probe.assert_awaited_once()
    build.assert_not_called()


# --- the fix: a migrated entry comes up with the amplifier off ---

def test_migrated_entry_sets_up_with_the_device_offline():
    """The entire point of issue #30. Entity creation is gated on knowing the zone and source
    counts; once the model is stored, that no longer needs a live device."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006, CONF_MODEL_KEY: "mca66"})
    hass = _hass()
    client = _client(connected=False)

    with patch.object(htd_init, "get_model_info", return_value=MCA66), patch.object(
        htd_init, "build_client", return_value=client
    ), patch.object(htd_init, "async_get_client", new_callable=AsyncMock) as probe:
        assert asyncio.run(htd_init.async_setup_entry(hass, entry)) is True

    probe.assert_not_called()
    client.async_start.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()


def test_offline_setup_does_not_query_names():
    """Name queries are writes to the transport. Issuing them while disconnected raises
    HtdConnectionError out of setup and puts the entry back to Unavailable."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006, CONF_MODEL_KEY: "mca66"})
    hass = _hass()
    client = _client(connected=False)

    with patch.object(htd_init, "get_model_info", return_value=MCA66), patch.object(
        htd_init, "build_client", return_value=client
    ):
        asyncio.run(htd_init.async_setup_entry(hass, entry))

    client.async_query_source_name.assert_not_awaited()


def test_offline_setup_never_overwrites_cached_names_with_nothing():
    """Home Assistant passes entity.name as original_name and the registry overwrites what it
    stored. If an offline start wrote an empty cache, a single offline restart would destroy
    every controller-reported zone name permanently, and it would not come back on its own."""
    entry = _config_entry({
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 10006,
        CONF_MODEL_KEY: "mca66",
        CONF_CACHED_ZONE_NAMES: {"1": "kitchen"},
        CONF_CACHED_SOURCE_NAMES: {"2": "turntable"},
    })
    hass = _hass()
    client = _client(connected=False)

    with patch.object(htd_init, "get_model_info", return_value=MCA66), patch.object(
        htd_init, "build_client", return_value=client
    ):
        asyncio.run(htd_init.async_setup_entry(hass, entry))

    # nothing changed, so nothing should have been written at all
    hass.config_entries.async_update_entry.assert_not_called()


def test_a_connection_drop_during_name_caching_does_not_abort_setup():
    """Since library 0.1.8, `_send_cmd` raises HtdConnectionError when disconnected. If the
    link drops between the `client.connected` check and the name-query gather, that
    exception must not propagate out of async_setup_entry: HA would mark the entry
    SETUP_ERROR (unlike ConfigEntryNotReady, not retried), and the retry task that
    connection_lost already armed would leak because async_unload_entry never runs. The
    name cache is best-effort by design and may give up quietly."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006, CONF_MODEL_KEY: "mca66"})
    hass = _hass()
    client = _client(connected=True)
    client.async_query_source_name.side_effect = HtdConnectionError("dropped mid-query")

    with patch.object(htd_init, "get_model_info", return_value=MCA66), patch.object(
        htd_init, "build_client", return_value=client
    ):
        assert asyncio.run(htd_init.async_setup_entry(hass, entry)) is True

    hass.config_entries.async_forward_entry_setups.assert_awaited_once()


def test_online_setup_caches_the_names_the_controller_reported():
    """The cache is only ever written while online, and only from names the controller
    actually gave us — never from get_source_name's invented "Source N" placeholders."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006, CONF_MODEL_KEY: "mca66"})
    hass = _hass()
    client = _client(
        connected=True,
        zone_names={1: "kitchen"},
        source_names={2: "turntable"},
    )

    with patch.object(htd_init, "get_model_info", return_value=MCA66), patch.object(
        htd_init, "build_client", return_value=client
    ):
        asyncio.run(htd_init.async_setup_entry(hass, entry))

    data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
    assert data[CONF_CACHED_ZONE_NAMES] == {"1": "kitchen"}
    assert data[CONF_CACHED_SOURCE_NAMES] == {"2": "turntable"}


# --- teardown ---

def test_unload_disconnects_the_client():
    """disconnect() also cancels the background retry loop. Without this call, removing or
    reloading an entry leaves a task dialing hardware Home Assistant no longer manages."""
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006, CONF_MODEL_KEY: "mca66"})
    hass = _hass()
    client = _client(connected=False)
    entry.runtime_data = client

    assert asyncio.run(htd_init.async_unload_entry(hass, entry)) is True
    client.disconnect.assert_called_once()
