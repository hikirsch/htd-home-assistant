import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import dhcp
from homeassistant.config_entries import (
    ConfigEntry, ConfigFlow, OptionsFlow, OptionsFlowWithConfigEntry,
)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_SOURCE, CONF_UNIQUE_ID,
)
from homeassistant.core import callback, HomeAssistant
from htd_client import HtdClient
from htd_client.constants import HtdConstants

from .const import (
    CONF_ACTIVE_ZONES,
    CONF_COMMAND_DELAY,
    CONF_DEVICE_NAME,
    CONF_RETRY_ATTEMPTS,
    CONF_SOCKET_TIMEOUT,
    CONF_UPDATE_VOLUME_ON_CHANGE,
    DOMAIN,
)
from .utils import get_friendly_name_from_host

_LOGGER = logging.getLogger(__name__)


def configured_instances(hass: HomeAssistant):
    """Return a set of configured instances."""
    return set(
        entry.title for entry in hass.config_entries.async_entries(DOMAIN)
    )


class HtdConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    host: str = None
    port: int = HtdConstants.DEFAULT_HTD_MC_PORT
    unique_id: str = None

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ):
        """Handle dhcp discovery."""

        host = discovery_info.ip

        (model_name, friendly_name) = get_friendly_name_from_host(
            discovery_info.ip, HtdConstants.DEFAULT_HTD_MC_PORT
        )

        unique_id = "htd-%s-%s" % (discovery_info.macaddress, model_name)

        await self.async_set_unique_id(unique_id)

        new_user_input = {
            CONF_HOST: discovery_info.ip,
            CONF_PORT: HtdConstants.DEFAULT_HTD_MC_PORT,
            CONF_UNIQUE_ID: unique_id,
        }

        self._abort_if_unique_id_configured(new_user_input)

        self.context["title_placeholders"] = {
            CONF_NAME: f"{friendly_name} ({host})",
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

            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            unique_id = user_input[CONF_UNIQUE_ID]

            try:
                client = HtdClient(host, port)
                response = client.get_model_info()

                if response is not None:
                    success = True

            except Exception as e:
                _LOGGER.error(
                    "Exception occurred while trying to connect to Htd Gateway",
                    e
                )
                pass

            if success:
                self.host = host
                self.port = port
                self.unique_id = unique_id

                return await self.async_step_options()

            errors['base'] = "no_connection"

        return self.async_show_form(
            step_id='user',
            data_schema=get_connection_settings_schema(),
            errors=errors, )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry, ) -> OptionsFlow:
        return HtdOptionsFlowHandler(config_entry)

    async def async_step_options(self, user_input=None):
        if user_input is not None:
            config_entry = {
                CONF_HOST: self.host, CONF_PORT: self.port,
            }

            options = {
                **{f"{CONF_SOURCE}_{index + 1}": source for index, source in
                    enumerate(HtdConstants.DEFAULT_SOURCE_NAMES)},
                CONF_COMMAND_DELAY: HtdConstants.DEFAULT_COMMAND_DELAY,
                CONF_RETRY_ATTEMPTS: HtdConstants.DEFAULT_RETRY_ATTEMPTS,
                CONF_SOCKET_TIMEOUT: HtdConstants.DEFAULT_SOCKET_TIMEOUT,
                **user_input,
            }

            return self.async_create_entry(
                title=user_input[CONF_DEVICE_NAME],
                data=config_entry,
                options=options
            )

        (_, friendly_name) = get_friendly_name_from_host(self.host, self.port)

        return self.async_show_form(
            step_id='options', data_schema=get_options_schema(friendly_name), )


class HtdOptionsFlowHandler(OptionsFlowWithConfigEntry):
    async def async_step_init(self):
        return self.async_show_menu(
            step_id='init', menu_options=['options', 'sources', 'advanced']
        )

    async def async_step_options(self, user_input):
        if user_input is not None:
            options = {
                **self.options, **user_input,
            }

            return self.async_create_entry(
                title=options[CONF_DEVICE_NAME], data=options, )

        friendly_name = self.config_entry.title
        active_zones = self.config_entry.options.get(CONF_ACTIVE_ZONES)
        update_volume = self.config_entry.options.get(
            CONF_UPDATE_VOLUME_ON_CHANGE
        )

        return self.async_show_form(
            step_id='options', data_schema=get_options_schema(
                friendly_name=friendly_name,
                active_zones=active_zones,
                update_volume=update_volume, ), )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ):
        if user_input is not None:
            options = {
                **self.options, **user_input,
            }

            return self.async_create_entry(
                title=options[CONF_DEVICE_NAME], data=options, )

        return self.async_show_form(
            step_id='advanced',
            data_schema=get_advanced_schema(self.config_entry), )

    async def async_step_sources(
        self, user_input: dict | None = None
    ):
        if user_input is not None:
            options = {
                **self.options, **user_input,
            }

            return self.async_create_entry(
                title=options[CONF_DEVICE_NAME], data=options, )

        return self.async_show_form(
            step_id='sources',
            data_schema=get_sources_schema(self.config_entry), )


def get_repeated_options_by_name(
    key: str, label: str, count: int, config_entry: ConfigEntry | None = None
):
    return vol.Schema(
        {vol.Required(
            f"{key}_{index}", default=config_entry.options.get(
                f"{key}_{index}"
            ) if config_entry is not None else f"{label} {index}"
        ): cv.string for index in range(1, count + 1)}
    )


def get_options_schema(
    friendly_name: str,
    active_zones: int = HtdConstants.MAX_HTD_ZONES,
    update_volume: bool = False
):
    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE_NAME, default=friendly_name
            ): cv.string,

            vol.Required(
                CONF_ACTIVE_ZONES, default=active_zones
            ): vol.In(list(range(1, HtdConstants.MAX_HTD_ZONES + 1))),

            vol.Required(
                CONF_UPDATE_VOLUME_ON_CHANGE, default=update_volume
            ): cv.boolean,
        }
    )


def get_connection_settings_schema(config_entry: ConfigEntry | None = None):
    if config_entry is not None:
        host = config_entry.data.get(CONF_HOST)
        port = config_entry.data.get(CONF_PORT)
    else:
        host = None
        port = HtdConstants.DEFAULT_HTD_MC_PORT

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Required(CONF_PORT, default=port): cv.port,
        }
    )


def get_sources_schema(config_entry: ConfigEntry | None = None):
    return get_repeated_options_by_name(
        CONF_SOURCE, "Source", HtdConstants.MAX_HTD_SOURCES, config_entry
    )


def get_advanced_schema(config_entry: ConfigEntry | None = None):
    if config_entry is not None:
        retry_attempts = config_entry.options.get(CONF_RETRY_ATTEMPTS)
        socket_timeout = config_entry.options.get(CONF_SOCKET_TIMEOUT)
        command_delay = config_entry.options.get(CONF_COMMAND_DELAY)
    else:
        retry_attempts = HtdConstants.DEFAULT_RETRY_ATTEMPTS
        socket_timeout = HtdConstants.DEFAULT_SOCKET_TIMEOUT
        command_delay = HtdConstants.DEFAULT_COMMAND_DELAY

    return vol.Schema(
        {
            vol.Required(
                CONF_RETRY_ATTEMPTS, default=retry_attempts
            ): cv.port, vol.Required(
            CONF_SOCKET_TIMEOUT, default=socket_timeout
        ): cv.port, vol.Required(
            CONF_COMMAND_DELAY, default=command_delay
        ): cv.port,
        }
    )
