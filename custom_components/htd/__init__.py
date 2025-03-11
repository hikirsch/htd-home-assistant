"""Support for Home Theater Direct products"""

import logging
import pathlib

import voluptuous as vol
from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform, CONF_PORT, CONF_HOST, CONF_PATH, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from htd_client import async_get_client, BaseClient

from .const import DOMAIN, CONF_DEVICE_KIND, CONF_DEVICE_NAME
from .utils import _async_cleanup_registry_entries
from .websocket_api import async_load_api
from .models import HtdConfigEntry

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

did_init = False


async def register_panel(hass: HomeAssistant) -> None:
    assets_path = pathlib.Path(__file__).parent / "assets"

    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=f"{DOMAIN}-config",
        webcomponent_name=f"{DOMAIN}-config-panel",
        config_panel_domain=DOMAIN,
        # module_url=str(f"/{DOMAIN}-assets/config-panel/index.js"),
        module_url=f"http://localhost:3000/config-panel/index.ts",
        embed_iframe=False,
        # sidebar_title="HTD",
        # sidebar_icon="mdi:cog",
        require_admin=True,
    )

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                f"/{DOMAIN}-assets",
                str(assets_path),
                cache_headers=True
            )
        ]
    )


async def async_setup(hass: HomeAssistant, config: dict):
    async_load_api(hass)
    await register_panel(hass)

    htd_config = config.get(DOMAIN)

    if htd_config is None:
        return True

    devices = []

    for config in htd_config:
        serial_address = config[CONF_PATH]
        device_name = config[CONF_DEVICE_NAME]

        client = await async_get_client(
            serial_address=serial_address,
            loop=hass.loop
        )

        unique_id = f"{client.model['name']}-{serial_address}"

        devices.append(
            {
                "client": client,
                CONF_UNIQUE_ID: unique_id,
                CONF_DEVICE_NAME: device_name
            }
        )

    hass.data[DOMAIN] = devices

    for component in PLATFORMS:
        await discovery.async_load_platform(hass, component, DOMAIN, {}, config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HtdConfigEntry):
    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT)

    network_address = (host, port)

    print("setting up config entry: ", network_address, entry.unique_id)
    client = await async_get_client(
        network_address=network_address,
        loop=hass.loop
    )

    entry.runtime_data = client

    # entry.async_on_unload(
    #     entry.add_update_listener(async_reload_entry)
    # )

    _async_cleanup_registry_entries(hass, entry)

    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS
    )

    return True

async def async_remove_entry(hass: HomeAssistant, entry: HtdConfigEntry) -> None:
    """Cleanup when an entry is removed."""
    _LOGGER.info("REMOVING CONFIG ENTRY FOR HTD %s" % entry.unique_id)

    for platform in PLATFORMS:
        _LOGGER.info("REMOVING ENTRY: %s %s" % (platform, entry.unique_id))
        await hass.config_entries.async_forward_entry_unload(entry, platform)


# async def async_reload_entry(hass: HomeAssistant, entry: HtdConfigEntry) -> None:
#     """Handle options update."""
#     await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HtdConfigEntry) -> bool:
    """Handle removal of an entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = entry.runtime_data

        # await client.disconnect()
    return unload_ok
