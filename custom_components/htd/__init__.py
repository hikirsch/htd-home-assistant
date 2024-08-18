"""Support for Home Theatre Direct's MC series"""

from __future__ import annotations, annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .utils import _async_cleanup_registry_entries

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigEntry):
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    # Forward to platform setup (e.g., media_player)
    await hass.config_entries.async_forward_entry_setups(
        config_entry, PLATFORMS, )
    config_entry.async_on_unload(
        config_entry.add_update_listener(update_listener)
    )

    _async_cleanup_registry_entries(hass, config_entry)

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
