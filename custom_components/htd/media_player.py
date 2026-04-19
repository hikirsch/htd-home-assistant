"""Support for HTD with per-zone naming and source filtering.

This is a fork of hikirsch's excellent htd-home-assistant integration
(https://github.com/hikirsch/htd-home-assistant).  The protocol, transport,
and hardware-facing logic are entirely his and unchanged - all audio /
power / source / mute commands still go through the upstream htd_client
PyPI package.

What this fork adds on top (UI-only, no hardware changes):
  * Per-zone friendly names that replace the default "Zone N (device)" label.
  * Per-zone source filtering - each zone's source dropdown shows only the
    sources you've marked allowed for it, instead of all 6/12/18.
  * Global source labels - rename "Source 3" to "Sonos" everywhere in HA.
  * An "Enabled" toggle per zone so unused zones can be suppressed.

None of these touch the HTD controller itself - the names stored on the
physical keypads are left alone.  This lives entirely in Home Assistant's
config entry options.
"""

import logging
import re

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_UNIQUE_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from htd_client import BaseClient, HtdConstants, HtdMcaClient
from htd_client.models import ZoneDetail

from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    CONF_SOURCE_LABELS,
    CONF_ZONES,
    CONF_ZONE_NAME,
    CONF_ZONE_ENABLED,
    CONF_ZONE_ALLOWED_SOURCES,
)


def make_alphanumeric(input_string):
    temp = re.sub(r'[^a-zA-Z0-9]', '_', input_string)
    return re.sub(r'_+', '_', temp).strip('_')

get_media_player_entity_id = lambda name, zone_number, zone_fmt: f"media_player.{make_alphanumeric(name)}_zone_{zone_number:{zone_fmt}}".lower()

SUPPORT_HTD = (
    MediaPlayerEntityFeature.SELECT_SOURCE |
    MediaPlayerEntityFeature.TURN_OFF |
    MediaPlayerEntityFeature.TURN_ON |
    MediaPlayerEntityFeature.VOLUME_MUTE |
    MediaPlayerEntityFeature.VOLUME_SET |
    MediaPlayerEntityFeature.VOLUME_STEP
)

_LOGGER = logging.getLogger(__name__)

type HtdClientConfigEntry = ConfigEntry[BaseClient]


def _build_source_labels(client: BaseClient, options: dict) -> list[str]:
    """Construct the MASTER source list indexed 0..N-1.

    Every physical source index the hardware has gets an entry here, because
    the entity's ``source`` property indexes into this list with
    ``zone_info.source - 1``.  Disabled/hidden sources are filtered later by
    ``source_list``, not here.
    """
    source_count = client.get_source_count()
    overrides: dict[str, str] = options.get(CONF_SOURCE_LABELS, {}) or {}
    result = []
    for i in range(source_count):
        src_num = i + 1
        label = overrides.get(str(src_num)) or f"Source {src_num}"
        result.append(label)
    return result


def _zone_config(options: dict, zone: int) -> dict:
    """Return the per-zone options dict for a given zone number."""
    zones = options.get(CONF_ZONES, {}) or {}
    return zones.get(str(zone), {}) or {}


async def async_setup_platform(hass, _, async_add_entities, __=None):
    """Legacy YAML setup path - kept for backward compatibility with
    hikirsch's original ``htd:`` YAML config.  The fork's per-zone naming
    only applies to config-entry installs; YAML users get the plain
    default behavior.
    """
    htd_configs = hass.data[DOMAIN]
    entities = []

    for device_index in range(len(htd_configs)):
        config = htd_configs[device_index]

        unique_id = config[CONF_UNIQUE_ID]
        device_name = config[CONF_DEVICE_NAME]
        client = config["client"]

        zone_count = client.get_zone_count()
        source_count = client.get_source_count()
        sources = [f"Source {i + 1}" for i in range(source_count)]
        allowed_sources = list(range(1, source_count + 1))
        for zone in range(1, zone_count + 1):
            entity = HtdDevice(
                unique_id,
                device_name,
                zone,
                sources,
                allowed_sources,
                None,   # zone_display_name override
                client,
            )

            entities.append(entity)

    async_add_entities(entities)

    return True


async def async_setup_entry(_: HomeAssistant, config_entry: HtdClientConfigEntry, async_add_entities):
    entities = []

    client = config_entry.runtime_data
    zone_count = client.get_zone_count()
    source_count = client.get_source_count()
    device_name = config_entry.title
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
    options = config_entry.options or {}

    # Master source list - every physical source gets a slot so index math
    # against zone_info.source continues to work.
    sources = _build_source_labels(client, options)

    for zone in range(1, zone_count + 1):
        zopt = _zone_config(options, zone)

        # Skip zones the user has explicitly disabled.
        if zopt.get(CONF_ZONE_ENABLED, True) is False:
            continue

        # Per-zone allowed sources (list of 1-based source numbers).  If
        # unset, show all of them.
        allowed = zopt.get(CONF_ZONE_ALLOWED_SOURCES)
        if not allowed:
            allowed = list(range(1, source_count + 1))

        # Optional friendly override for the zone display name.
        zone_display_name = zopt.get(CONF_ZONE_NAME) or None

        entity = HtdDevice(
            unique_id,
            device_name,
            zone,
            sources,
            allowed,
            zone_display_name,
            client,
        )

        entities.append(entity)

    async_add_entities(entities)


class HtdDevice(MediaPlayerEntity):
    should_poll = False

    unique_id: str = None
    device_name: str = None
    client: BaseClient = None
    sources: list[str] = None
    allowed_sources: list[int] = None
    zone_display_name: str | None = None
    zone: int = None
    changing_volume: int | None = None
    zone_info: ZoneDetail = None

    def __init__(
        self,
        unique_id,
        device_name,
        zone,
        sources,
        allowed_sources,
        zone_display_name,
        client,
    ):
        self.unique_id = f"{unique_id}_{zone:02}"
        self.device_name = device_name
        self.zone = zone
        self.client = client
        self.sources = sources
        self.allowed_sources = allowed_sources
        self.zone_display_name = zone_display_name
        zone_fmt = f"02" if self.client.model["zones"] > 10 else "01"
        self.entity_id = get_media_player_entity_id(device_name, zone, zone_fmt)

    @property
    def enabled(self) -> bool:
        return self.zone_info is not None and self.zone_info.enabled

    @property
    def supported_features(self):
        return SUPPORT_HTD

    @property
    def name(self):
        if self.zone_display_name:
            return self.zone_display_name
        return f"Zone {self.zone} ({self.device_name})"

    def update(self):
        self.zone_info = self.client.get_zone(self.zone)

    @property
    def state(self):
        if not self.client.connected:
            return STATE_UNAVAILABLE

        if self.zone_info is None:
            return STATE_UNKNOWN

        if self.zone_info.power:
            return STATE_ON

        return STATE_OFF

    @property
    def volume_step(self) -> float:
        return 1 / HtdConstants.MAX_VOLUME

    async def async_volume_up(self) -> None:
        await self.client.async_volume_up(self.zone)

    async def async_volume_down(self) -> None:
        await self.client.async_volume_down(self.zone)

    async def async_turn_on(self):
        await self.client.async_power_on(self.zone)

    async def async_turn_off(self):
        await self.client.async_power_off(self.zone)

    @property
    def volume_level(self) -> float:
        return self.zone_info.volume / HtdConstants.MAX_VOLUME

    @property
    def available(self) -> bool:
        return self.client.ready and self.zone_info is not None

    async def async_set_volume_level(self, volume: float):
        converted_volume = round(volume * HtdConstants.MAX_VOLUME)
        _LOGGER.info("setting new volume for zone %d to %f, raw htd = %d" % (self.zone, volume, converted_volume))
        await self.client.async_set_volume(self.zone, converted_volume)

    @property
    def is_volume_muted(self) -> bool:
        return self.zone_info.mute

    async def async_mute_volume(self, mute):
        if mute:
            await self.client.async_mute(self.zone)
        else:
            await self.client.async_unmute(self.zone)

    @property
    def source(self) -> str:
        """Return the currently selected source's friendly label.

        ``zone_info.source`` is 1-based over the full hardware source range,
        so we index ``self.sources`` (the master list) with ``source - 1``
        regardless of the per-zone filter.  This keeps the displayed name
        correct even if the active source isn't in the allowed list (which
        can happen if someone selects it from a physical keypad).
        """
        if self.zone_info is None:
            return None
        idx = self.zone_info.source - 1
        if 0 <= idx < len(self.sources):
            return self.sources[idx]
        return None

    @property
    def source_list(self):
        """Only show the user-allowed subset in the dropdown."""
        return [self.sources[src - 1] for src in self.allowed_sources
                if 1 <= src <= len(self.sources)]

    @property
    def media_title(self):
        return self.source

    async def async_select_source(self, source: str):
        """Translate a friendly label back to a 1-based source number.

        We look up against the master ``self.sources`` list (not just the
        filtered ``source_list``) so a user-labeled source always resolves
        even if the filter has changed.
        """
        try:
            source_index = self.sources.index(source)
        except ValueError:
            _LOGGER.warning(
                "Unknown source '%s' for zone %d; list=%s",
                source, self.zone, self.sources
            )
            return
        await self.client.async_set_source(self.zone, source_index + 1)

    @property
    def icon(self):
        return "mdi:disc-player"

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Sensors should also register callbacks to HA when their state changes
        # print('registering callback')
        await self.client.async_subscribe(self._do_update)
        await self.client.refresh()

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        await self.client.async_unsubscribe(self._do_update)

    def _do_update(self, zone: int):
        if zone is None and self.zone_info is not None:
            return

        if zone is not None and zone != 0 and zone != self.zone:
            return

        if not self.client.has_zone_data(self.zone):
            return

        # if there's a target volume for mca, don't update yet
        if isinstance(self.client, HtdMcaClient) and self.client.has_volume_target(self.zone):
            return

        if zone is not None and self.client.has_zone_data(zone):
            self.zone_info = self.client.get_zone(zone)
            self.schedule_update_ha_state(force_refresh=True)
