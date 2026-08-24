"""Support for Home Theater Direct products"""

import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_PORT, CONF_HOST, CONF_PATH, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from htd_client import async_get_client, build_client, get_model_info
from htd_client.constants import HtdDeviceKind
from htd_client.exceptions import HtdConnectionError

from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    CONF_MODEL_KEY,
    CONF_CACHED_ZONE_NAMES,
    CONF_CACHED_SOURCE_NAMES,
)
from .utils import _async_cleanup_registry_entries

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SWITCH]

# how long to wait for the controller's replies to the name queries before giving up and
# persisting whatever arrived. the queries are fire-and-forget sends; the replies come back
# asynchronously through data_received, so without a wait the cache would capture nothing.
NAME_QUERY_TIMEOUT = 2.0
NAME_QUERY_POLL_INTERVAL = 0.1

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
    serial_address = config_entry.data.get(CONF_PATH)

    if serial_address:
        address_kwargs = {"serial_address": serial_address}
        address_description = f"on {serial_address}"
    else:
        network_address = (
            config_entry.data.get(CONF_HOST),
            config_entry.data.get(CONF_PORT),
        )
        address_kwargs = {"network_address": network_address}
        address_description = f"at {network_address}"

    model_info = get_model_info(config_entry.data.get(CONF_MODEL_KEY))

    if model_info is None:
        # Legacy entry, or a key this version does not recognize: probe as before. This is
        # the passive migration path — it still needs a live device, and it is what records
        # the model key so that later restarts do not.
        try:
            client = await async_get_client(**address_kwargs)
        except HtdConnectionError as e:
            raise ConfigEntryNotReady(
                f"Unable to connect to HTD device {address_description}: {e}"
            ) from e
    else:
        # We already know what the hardware is, so the zone and source counts — the only
        # things entity creation actually needs — are available with the device powered off.
        client = build_client(model_info, **address_kwargs)
        await client.async_start()

    config_entry.runtime_data = client

    if client.connected:
        try:
            await _async_cache_names(client)
        except HtdConnectionError:
            # Best-effort by design: the cache converges one restart later. Letting this
            # propagate would mark the entry SETUP_ERROR (unlike ConfigEntryNotReady, not
            # retried) and leak the retry task connection_lost has already armed, since
            # async_unload_entry would never run to cancel it.
            _LOGGER.debug("Connection dropped while caching names; will retry on next setup")

    # ORDERING IS LOAD-BEARING: async_update_entry fires the update listener, and
    # async_update_listener reloads the entry. Everything that writes to entry.data during
    # setup must happen here, before the listener below is registered, or the first write
    # becomes an endless setup -> reload loop.
    _persist_setup_data(hass, config_entry, client)

    config_entry.async_on_unload(
        config_entry.add_update_listener(async_update_listener)
    )

    _async_cleanup_registry_entries(hass, config_entry)

    await hass.config_entries.async_forward_entry_setups(
        config_entry, PLATFORMS
    )

    return True


async def _async_cache_names(client) -> None:
    """Ask the controller for its zone and source names and wait briefly for the replies.

    The query methods are fire-and-forget sends; replies arrive later through
    `data_received`. Without a bounded wait, the cache written moments later would be empty.
    """
    source_count = client.get_source_count()
    await asyncio.gather(*[
        client.async_query_source_name(i)
        for i in range(1, source_count + 1)
    ])

    zone_count = client.get_zone_count()
    expected_zone_names = 0

    if client.model.get("kind") == HtdDeviceKind.lync:
        try:
            await asyncio.gather(*[
                client.async_query_zone_name(z)
                for z in range(1, zone_count + 1)
            ])
            expected_zone_names = zone_count
        except NotImplementedError:
            _LOGGER.warning("Zone name queries not supported on this model")

    deadline = asyncio.get_running_loop().time() + NAME_QUERY_TIMEOUT

    while asyncio.get_running_loop().time() < deadline:
        if (
            len(client.get_source_names()) >= source_count
            and len(client.get_zone_names()) >= expected_zone_names
        ):
            return
        await asyncio.sleep(NAME_QUERY_POLL_INTERVAL)

    _LOGGER.debug(
        "Timed out waiting for controller name replies; caching %d source and %d zone names",
        len(client.get_source_names()),
        len(client.get_zone_names()),
    )


def _persist_setup_data(hass: HomeAssistant, config_entry: ConfigEntry, client) -> None:
    """Record the detected model and any controller-reported names into entry.data.

    Names are merged, never replaced: an offline start knows nothing, and overwriting the
    cache with nothing would destroy the stored names permanently, because Home Assistant
    passes entity.name to the registry as original_name and the registry overwrites it.

    MUST be called before add_update_listener — see async_setup_entry.
    """
    data = dict(config_entry.data)
    changed = False

    model_key = client.model.get("key")
    if model_key is not None and data.get(CONF_MODEL_KEY) != model_key:
        data[CONF_MODEL_KEY] = model_key
        changed = True

    for conf_key, reported in (
        (CONF_CACHED_ZONE_NAMES, client.get_zone_names()),
        (CONF_CACHED_SOURCE_NAMES, client.get_source_names()),
    ):
        if not reported:
            continue
        merged = {**data.get(conf_key, {}), **{str(k): v for k, v in reported.items()}}
        if merged != data.get(conf_key):
            data[conf_key] = merged
            changed = True

    if changed:
        hass.config_entries.async_update_entry(config_entry, data=data)


async def async_update_listener(
    hass: HomeAssistant,
    config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        client = getattr(entry, "runtime_data", None)
        if client is not None:
            # also cancels the library's background retry loop
            client.disconnect()

    return unloaded
