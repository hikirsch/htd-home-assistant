import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import dhcp
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow, OptionsFlowWithConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_UNIQUE_ID
from homeassistant.core import callback, HomeAssistant
from htd_client import get_model_info, HtdDeviceKind
from htd_client.constants import HtdConstants

from .const import CONF_DEVICE_KIND, CONF_DEVICE_NAME, CONF_RETRY_ATTEMPTS, CONF_SOCKET_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


def configured_instances(hass: HomeAssistant):
    """Return a set of configured instances."""
    return set(
        entry.title for entry in hass.config_entries.async_entries(DOMAIN)
    )


class HtdConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    kind: HtdDeviceKind = None
    host: str = None
    port: int = HtdConstants.DEFAULT_PORT
    unique_id: str = None

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ):
        """Handle dhcp discovery."""
        _LOGGER.info("HTD device detected: %s %s" % (discovery_info.ip, self.port))
        host = discovery_info.ip

        model_info = get_model_info(discovery_info.ip, self.port)

        if model_info is None:
            return self.async_abort(reason="unknown_model")

        _LOGGER.info("Model identified as: %s" % model_info)

        unique_id = "htd-%s-%s" % (discovery_info.macaddress, model_info["name"])

        await self.async_set_unique_id(unique_id)

        self.unique_id = unique_id
        new_user_input = {
            CONF_DEVICE_KIND: model_info["kind"],
            CONF_HOST: discovery_info.ip,
            CONF_PORT: self.port,
            CONF_UNIQUE_ID: unique_id,
        }

        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {
            CONF_NAME: f"{model_info["friendly_name"]} ({host})",
        }

        return await self.async_step_custom_connection(new_user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        return await self.async_step_custom_connection(user_input)

    async def async_step_custom_connection(
        self, user_input: dict[str, Any] | None = None
    ):
        errors = {}

        if user_input is not None:
            success = False

            kind = user_input[CONF_DEVICE_KIND]
            host = user_input[CONF_HOST]
            port = int(user_input[CONF_PORT])
            unique_id = user_input[CONF_UNIQUE_ID] if CONF_UNIQUE_ID in user_input else "htd-%s-%s" % (host, port)

            try:
                response = get_model_info(host, port)

                if response is not None:
                    success = True

            except Exception as e:
                _LOGGER.error("Exception occurred while trying to connect to Htd Gateway")
                _LOGGER.exception(e)
                pass

            if success:
                self.kind = kind
                self.host = host
                self.port = port
                self.unique_id = unique_id

                return await self.async_step_options()

            errors['base'] = "no_connection"

        return self.async_show_form(
            step_id='user',
            data_schema=get_connection_settings_schema(),
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HtdOptionsFlowHandler(config_entry)

    async def async_step_options(self, user_input=None):
        model_info = get_model_info(self.host, self.port)

        if user_input is not None:
            config_entry = {
                CONF_DEVICE_KIND: self.kind,
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_UNIQUE_ID: self.unique_id,
            }

            options = {
                **user_input,
            }

            return self.async_create_entry(
                title=user_input[CONF_DEVICE_NAME],
                data=config_entry,
                options=options
            )

        return self.async_show_form(
            step_id='options',
            data_schema=get_options_schema(
                model_info["friendly_name"],
            )
        )


class HtdOptionsFlowHandler(OptionsFlowWithConfigEntry):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            options = {
                **self.options, **user_input,
            }

            return self.async_create_entry(
                title=options[CONF_DEVICE_NAME], data=options
            )

        friendly_name = self.config_entry.title

        return self.async_show_form(
            step_id='options',
            data_schema=get_options_schema(
                friendly_name=friendly_name,
            )
        )

def get_options_schema(
    friendly_name: str,
):
    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE_NAME, default=friendly_name
            ): cv.string,
        }
    )


def get_connection_settings_schema(config_entry: ConfigEntry | None = None):
    if config_entry is not None:
        kind = config_entry.data.get(CONF_DEVICE_KIND)
        host = config_entry.data.get(CONF_HOST)
        port = config_entry.data.get(CONF_PORT)
    else:
        kind = None
        host = None
        port = HtdConstants.DEFAULT_PORT

    return vol.Schema(
        {
            vol.Required(CONF_DEVICE_KIND, default=kind): vol.In([k.value for k in HtdDeviceKind]),
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Required(CONF_PORT, default=port): cv.port,
        }
    )
