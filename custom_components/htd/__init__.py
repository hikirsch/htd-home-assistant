"""Support for Home Theatre Direct's MC series"""

from __future__ import annotations, annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_PORT, CONF_HOST
from homeassistant.core import HomeAssistant
from htd_client import get_client, HtdDeviceKind

from .const import DOMAIN, CONF_DEVICE_KIND
from .utils import _async_cleanup_registry_entries

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigEntry):
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    kind_raw = config_entry.data.get(CONF_DEVICE_KIND)
    kind = HtdDeviceKind(kind_raw)
    host = config_entry.data.get(CONF_HOST)
    port = config_entry.data.get(CONF_PORT)

    config_entry.runtime_data = get_client(kind, host, port)
    config_entry.runtime_data.wait_until_ready()

    config_entry.async_on_unload(
        config_entry.add_update_listener(update_listener)
    )

    _async_cleanup_registry_entries(hass, config_entry)

    await hass.config_entries.async_forward_entry_setups(
        config_entry, PLATFORMS
    )

    return True


async def update_listener(
    hass: HomeAssistant,
    config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
