"""Support for Home Theater Direct products"""

import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_PORT, CONF_HOST, CONF_PATH, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from htd_client import async_get_client
from htd_client.constants import HtdDeviceKind

from .const import DOMAIN, CONF_DEVICE_NAME
from .utils import _async_cleanup_registry_entries

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            [
                vol.Schema(
                    {
                        vol.Required(CONF_DEVICE_NAME): cv.string,
                        vol.Required(CONF_PATH): cv.string,
                    }
                )
            ]
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    htd_config = config.get(DOMAIN)

    if htd_config is None:
        return True

    devices = []

    for config in htd_config:
        serial_address = config[CONF_PATH]
        device_name = config[CONF_DEVICE_NAME]

        client = await async_get_client(
            serial_address=serial_address,
        )

        unique_id = f"{client.model['name']}-{serial_address}"

        devices.append({
            "client": client,
            CONF_UNIQUE_ID: unique_id,
            CONF_DEVICE_NAME: device_name
        })

    hass.data[DOMAIN] = devices

    for component in PLATFORMS:
        await discovery.async_load_platform(hass, component, DOMAIN, {}, config)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    host = config_entry.data.get(CONF_HOST)
    port = config_entry.data.get(CONF_PORT)

    network_address = (host, port)

    client = await async_get_client(
        network_address=network_address,
    )

    config_entry.runtime_data = client

    source_count = client.get_source_count()
    await asyncio.gather(*[
        client.async_query_source_name(i)
        for i in range(1, source_count + 1)
    ])

    if client.model.get("kind") == HtdDeviceKind.lync:
        zone_count = client.get_zone_count()
        try:
            await asyncio.gather(*[
                client.async_query_zone_name(z)
                for z in range(1, zone_count + 1)
            ])
        except NotImplementedError:
            _LOGGER.warning("Zone name queries not supported on this model")

    config_entry.async_on_unload(
        config_entry.add_update_listener(async_update_listener)
    )

    _async_cleanup_registry_entries(hass, config_entry)

    await hass.config_entries.async_forward_entry_setups(
        config_entry, PLATFORMS
    )

    return True


async def async_update_listener(
    hass: HomeAssistant,
    config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
