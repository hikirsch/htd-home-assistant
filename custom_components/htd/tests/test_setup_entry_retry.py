"""async_setup_entry must raise ConfigEntryNotReady (not propagate a bare exception) when the
HTD device is unreachable at startup, so Home Assistant retries with backoff instead of
permanently failing the config entry (issue #23).

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

htd_init = importlib.import_module("custom_components.htd")


def _config_entry(data):
    entry = MagicMock()
    entry.data = data
    return entry


def test_serial_setup_raises_config_entry_not_ready_when_device_unreachable():
    entry = _config_entry({CONF_PATH: "/dev/ttyUSB0"})
    hass = MagicMock()

    with patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.side_effect = HtdConnectionError("no reply from device")

        with pytest.raises(ConfigEntryNotReady):
            asyncio.run(htd_init.async_setup_entry(hass, entry))


def test_network_setup_raises_config_entry_not_ready_when_device_unreachable():
    entry = _config_entry({CONF_HOST: "1.2.3.4", CONF_PORT: 10006})
    hass = MagicMock()

    with patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.side_effect = HtdConnectionError("no reply from device")

        with pytest.raises(ConfigEntryNotReady):
            asyncio.run(htd_init.async_setup_entry(hass, entry))


def test_setup_still_propagates_unrelated_errors():
    """Confirms the catch is scoped to HtdConnectionError, not a blanket except."""
    entry = _config_entry({CONF_PATH: "/dev/ttyUSB0"})
    hass = MagicMock()

    with patch.object(
        htd_init, "async_get_client", new_callable=AsyncMock
    ) as mock_get_client:
        mock_get_client.side_effect = ValueError("Unknown Device Kind: foo")

        with pytest.raises(ValueError):
            asyncio.run(htd_init.async_setup_entry(hass, entry))
