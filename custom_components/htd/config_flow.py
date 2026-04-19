"""Config flow for HTD (forked by @yourusername).

Builds on hikirsch's original connection flow.  Adds options steps for
source labels and per-zone configuration (friendly name, enabled toggle,
allowed-source filter).
"""

import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_UNIQUE_ID
from homeassistant.core import callback, HomeAssistant
from htd_client import async_get_model_info
from htd_client.constants import HtdConstants

from .const import (
    CONF_DEVICE_NAME,
    CONF_SOURCE_LABELS,
    CONF_ZONE_ALLOWED_SOURCES,
    CONF_ZONE_ENABLED,
    CONF_ZONE_NAME,
    CONF_ZONES,
    DOMAIN,
)

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
    port: int = HtdConstants.DEFAULT_PORT
    unique_id: str = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ):
        """Handle dhcp discovery."""
        _LOGGER.info("HTD device detected: %s %s" % (discovery_info.ip, self.port))
        host = discovery_info.ip
        network_address = (host, self.port)
        model_info = await async_get_model_info(network_address=network_address)

        if model_info is None:
            return self.async_abort(reason="unknown_model")

        _LOGGER.info("Model identified as: %s" % model_info)

        unique_id = "htd-%s" % discovery_info.macaddress

        await self.async_set_unique_id(unique_id)

        self.unique_id = unique_id
        new_user_input = {
            CONF_HOST: discovery_info.ip,
            CONF_PORT: self.port,
            CONF_UNIQUE_ID: unique_id,
        }

        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {
            CONF_NAME: f"{model_info['friendly_name']} ({host})",
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
            port = int(user_input[CONF_PORT])
            unique_id = user_input[CONF_UNIQUE_ID] if CONF_UNIQUE_ID in user_input else "htd-%s-%s" % (host, port)

            try:
                network_address = host, port
                response = await async_get_model_info(network_address=network_address)

                if response is not None:
                    success = True

            except Exception as e:
                _LOGGER.error("Exception occurred while trying to connect to Htd Gateway")
                _LOGGER.exception(e)
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
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HtdOptionsFlowHandler(config_entry)

    async def async_step_options(self, user_input=None):
        if user_input is not None:
            config_entry = {
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_UNIQUE_ID: self.unique_id,
            }

            return self.async_create_entry(
                title=user_input[CONF_DEVICE_NAME],
                data=config_entry,
                options={}
            )

        network_address = (self.host, self.port)
        model_info = await async_get_model_info(network_address=network_address)

        return self.async_show_form(
            step_id='options',
            data_schema=get_options_schema(
                model_info["friendly_name"],
            )
        )


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


class HtdOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Options flow with connection settings + naming UX.

    The original hikirsch flow only had connection settings.  We add:
      * A top-level action picker (menu)
      * A 'Source labels' step to rename Source 1..N globally
      * A per-zone wizard (Name, Enabled, allowed sources)
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        super().__init__(config_entry)
        # Copies we mutate as the user walks the wizard.
        self._opts_draft: dict[str, Any] = dict(config_entry.options or {})
        self._zone_cursor: int = 1
        # These are set lazily the first time we need the model.
        self._zone_count: int | None = None
        self._source_count: int | None = None

    async def _ensure_model(self) -> None:
        if self._zone_count is not None:
            return
        host = self.config_entry.data.get(CONF_HOST)
        port = self.config_entry.data.get(CONF_PORT)
        try:
            info = await async_get_model_info(network_address=(host, port))
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not reach controller to query model: %s", err)
            info = None
        # Fall back to Lync 12 dimensions if the controller isn't reachable.
        if info:
            self._zone_count = int(info.get("zones") or 12)
            self._source_count = int(info.get("sources") or 18)
        else:
            self._zone_count = 12
            self._source_count = 18

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Top-level menu: connection / source labels / zones / save."""
        await self._ensure_model()

        if user_input is not None:
            action = user_input.get("action")
            if action == "connection":
                return await self.async_step_connection()
            if action == "source_labels":
                return await self.async_step_source_labels()
            if action == "zones":
                self._zone_cursor = 1
                return await self.async_step_zone()
            if action == "save":
                return self.async_create_entry(title="", data=self._opts_draft)

        schema = vol.Schema({
            vol.Required("action", default="zones"): vol.In({
                "zones": "Configure Zones (name, enabled, allowed sources)",
                "source_labels": "Rename Sources (global labels)",
                "connection": "Connection Settings",
                "save": "Save & Exit",
            })
        })
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_connection(self, user_input: dict[str, Any] | None = None):
        """Original connection-settings step from hikirsch."""
        if user_input is not None:
            # Merge into data (host/port are data, not options).
            data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id="connection",
            data_schema=get_connection_settings_schema(self.config_entry),
        )

    async def async_step_source_labels(self, user_input: dict[str, Any] | None = None):
        """Rename Source 1..N globally.  Blank = default label."""
        await self._ensure_model()
        existing: dict[str, str] = self._opts_draft.get(CONF_SOURCE_LABELS, {}) or {}

        if user_input is not None:
            new_labels: dict[str, str] = {}
            for i in range(1, self._source_count + 1):
                val = (user_input.get(f"source_{i}") or "").strip()
                if val:
                    new_labels[str(i)] = val
            self._opts_draft[CONF_SOURCE_LABELS] = new_labels
            return await self.async_step_init()

        schema_dict: dict = {}
        for i in range(1, self._source_count + 1):
            schema_dict[
                vol.Optional(f"source_{i}", default=existing.get(str(i), ""))
            ] = str
        return self.async_show_form(
            step_id="source_labels",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_zone(self, user_input: dict[str, Any] | None = None):
        """Per-zone wizard: walks through zones one at a time."""
        await self._ensure_model()
        zone_key = str(self._zone_cursor)
        zones_map: dict = self._opts_draft.get(CONF_ZONES, {}) or {}
        zopt: dict = zones_map.get(zone_key, {}) or {}

        if user_input is not None:
            allowed: list[int] = []
            for i in range(1, self._source_count + 1):
                if user_input.get(f"src_{i}", False):
                    allowed.append(i)
            zones_map[zone_key] = {
                CONF_ZONE_NAME: (user_input.get(CONF_ZONE_NAME) or "").strip(),
                CONF_ZONE_ENABLED: bool(user_input.get(CONF_ZONE_ENABLED, True)),
                CONF_ZONE_ALLOWED_SOURCES: allowed,
            }
            self._opts_draft[CONF_ZONES] = zones_map

            self._zone_cursor += 1
            if self._zone_cursor > self._zone_count:
                return await self.async_step_init()
            return await self.async_step_zone()

        # Build the form.  Source checkboxes are labeled with the most
        # useful name we have (user override > default).
        labels: dict[str, str] = self._opts_draft.get(CONF_SOURCE_LABELS, {}) or {}
        default_allowed = zopt.get(
            CONF_ZONE_ALLOWED_SOURCES,
            list(range(1, self._source_count + 1)),
        )
        schema_dict: dict = {
            vol.Optional(
                CONF_ZONE_NAME,
                default=zopt.get(CONF_ZONE_NAME, f"Zone {self._zone_cursor}"),
            ): str,
            vol.Optional(
                CONF_ZONE_ENABLED,
                default=zopt.get(CONF_ZONE_ENABLED, True),
            ): bool,
        }
        for i in range(1, self._source_count + 1):
            schema_dict[
                vol.Optional(f"src_{i}", default=i in default_allowed)
            ] = bool

        return self.async_show_form(
            step_id="zone",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "zone_num": str(self._zone_cursor),
                "total": str(self._zone_count),
            },
        )


def get_options_schema(friendly_name: str):
    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE_NAME, default=friendly_name
            ): cv.string,
        }
    )


def get_connection_settings_schema(config_entry: ConfigEntry | None = None):
    if config_entry is not None:
        host = config_entry.data.get(CONF_HOST)
        port = config_entry.data.get(CONF_PORT)
    else:
        host = None
        port = HtdConstants.DEFAULT_PORT

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Required(CONF_PORT, default=port): cv.port,
        }
    )
