from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_ENABLED, CONF_ALIAS, CONF_ZONE, CONF_ID
from homeassistant.core import HomeAssistant, callback

from htd_client import HtdModelInfo, HtdDeviceKind

from .const import TYPE, ENTRY_ID, CONF_SOURCES, CONF_INTERCOM
from .models import HtdConfigEntry


@callback
def async_load_api(hass):
    websocket_api.async_register_command(hass, websocket_get_config)
    websocket_api.async_register_command(hass, websocket_set_config)
    websocket_api.async_register_command(hass, websocket_get_sources)
    websocket_api.async_register_command(hass, websocket_set_sources)


def generate_sources(model_info: HtdModelInfo):
    source_list = []

    for i in range(0, model_info['sources']):
        number = i + 1
        intercom = False

        # the client has the total number of sources for the given device
        # only on lync is the last one the intercom, label it as such
        if model_info['kind'] == HtdDeviceKind.lync and i == model_info['sources'] - 1:
            intercom = True

        source_list.append(
            {
                CONF_ZONE: number,
                CONF_ALIAS: "Intercom" if intercom else f"Source {number}",
                CONF_ENABLED: True,
                CONF_INTERCOM: intercom
            }
        )

    return source_list


HTD_SOURCES_GET_WEBSOCKET_SCHEMA = {
    vol.Required(TYPE): "htd/sources/get",
    vol.Required(ENTRY_ID): str
}

HTD_SOURCES_SET_WEBSOCKET_SCHEMA = {
    vol.Required(TYPE): "htd/sources/set",
    vol.Required(ENTRY_ID): str,
    vol.Required(CONF_SOURCES): [
        vol.Schema(
            {
                CONF_ZONE: int,
                CONF_ALIAS: str,
                CONF_ENABLED: bool,
                CONF_INTERCOM: bool
            }
        )
    ],
}

HTD_CONFIG_GET_WEBSOCKET_SCHEMA = {
    vol.Required(TYPE): "htd/config/get",
    vol.Required(ENTRY_ID): str
}

HTD_CONFIG_SET_WEBSOCKET_SCHEMA = {
    vol.Required(TYPE): "htd/config/set",
    vol.Required(ENTRY_ID): str,
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT): int
}


@websocket_api.websocket_command(HTD_SOURCES_GET_WEBSOCKET_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_sources(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    config_entry: HtdConfigEntry = hass.config_entries.async_get_entry(msg[ENTRY_ID])
    client = config_entry.runtime_data

    sources = config_entry.options.get(CONF_SOURCES, None)

    if sources is None:
        sources = generate_sources(client.model)

    connection.send_result(msg[CONF_ID], sources)


@websocket_api.websocket_command(HTD_SOURCES_SET_WEBSOCKET_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_set_sources(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    config_entry = hass.config_entries.async_get_entry(msg[ENTRY_ID])

    hass.config_entries.async_update_entry(
        config_entry,
        data=config_entry.data,
        options={
            **config_entry.options,
            CONF_SOURCES: msg[CONF_SOURCES],
        },
    )

    connection.send_result(msg[CONF_ID], {"success": True})


@websocket_api.websocket_command(HTD_CONFIG_GET_WEBSOCKET_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_config(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    config_entry = hass.config_entries.async_get_entry(msg[ENTRY_ID])
    connection.send_result(
        msg[CONF_ID], {
            CONF_HOST: config_entry.data[CONF_HOST],
            CONF_PORT: config_entry.data[CONF_PORT]
        }
    )


@websocket_api.websocket_command(HTD_CONFIG_SET_WEBSOCKET_SCHEMA)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_set_config(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    config_entry = hass.config_entries.async_get_entry(msg[ENTRY_ID])

    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_HOST: msg[CONF_HOST],
            CONF_PORT: msg[CONF_PORT],
        },
        options=config_entry.options,
    )

    connection.send_result(msg[CONF_ID], {"success": True})
