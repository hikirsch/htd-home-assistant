"""Support for HTD"""

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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from htd_client import BaseClient, HtdConstants, HtdMcaClient
from htd_client.models import ZoneDetail
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    CONF_ZONE_NAMES,
    CONF_SOURCE_NAMES,
    CONF_ZONE_FILTER_ENABLED,
    CONF_ENABLED_ZONES,
    CONF_SOURCE_FILTER_ENABLED,
    CONF_ZONE_SOURCE_FILTERS,
    CONF_CACHED_ZONE_NAMES,
    CONF_CACHED_SOURCE_NAMES,
)
from .entity import HtdEntity


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


async def async_setup_platform(hass, _, async_add_entities, __=None):
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
        for zone in range(1, zone_count + 1):
            entity = HtdDevice(
                unique_id,
                device_name,
                zone,
                sources,
                client
            )

            entities.append(entity)

    async_add_entities(entities)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: HtdClientConfigEntry, async_add_entities):
    client = config_entry.runtime_data
    zone_count = client.get_zone_count()
    source_count = client.get_source_count()
    device_name = config_entry.title
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
    sources = [f"Source {i + 1}" for i in range(source_count)]

    zone_filter_enabled = config_entry.data.get(CONF_ZONE_FILTER_ENABLED, False)
    enabled_zones = set(config_entry.data.get(CONF_ENABLED_ZONES, []))
    registry = er.async_get(hass)

    entities = []
    for zone in range(1, zone_count + 1):
        entity = HtdDevice(
            unique_id,
            device_name,
            zone,
            sources,
            client,
            config_entry
        )
        entities.append(entity)

        should_enable = not zone_filter_enabled or zone in enabled_zones
        uid = f"{unique_id}_{zone:02}"
        entity_id = registry.async_get_entity_id("media_player", DOMAIN, uid)
        if entity_id:
            entry = registry.async_get(entity_id)
            if entry:
                if should_enable and entry.disabled_by == RegistryEntryDisabler.INTEGRATION:
                    registry.async_update_entity(entity_id, disabled_by=None)
                elif not should_enable and entry.disabled_by is None:
                    registry.async_update_entity(
                        entity_id, disabled_by=RegistryEntryDisabler.INTEGRATION
                    )

    async_add_entities(entities)


class HtdDevice(HtdEntity, MediaPlayerEntity, RestoreEntity):
    should_poll = False

    unique_id: str = None
    device_name: str = None
    client: BaseClient = None
    sources: [str] = None
    zone: int = None
    changing_volume: int | None = None
    zone_info: ZoneDetail = None
    _restored = None

    def __init__(
        self,
        unique_id,
        device_name,
        zone,
        sources,
        client,
        config_entry=None
    ):
        self.unique_id = f"{unique_id}_{zone:02}"
        self.device_name = device_name
        self.zone = zone
        self.client = client
        self.sources = sources
        self.config_entry = config_entry
        zone_fmt = f"02" if self.client.model["zones"] > 10 else "01"
        self.entity_id = get_media_player_entity_id(device_name, zone, zone_fmt)

    def _live_zone(self):
        """media_player keeps its own cached copy, updated in _do_update, so that stays the
        single source of truth for this platform rather than reading the client twice.

        Invariant this relies on: connection_lost sets client.ready False, and it only
        returns to True after every zone's status frame has been parsed, with each frame
        broadcasting to its own entity first. So by the instant `ready` flips True, every
        HtdDevice.zone_info has already been refreshed — this cached override cannot serve
        a stale zone in practice.
        """
        if not self.client.ready:
            return None

        return self.zone_info

    def _usable_restored(self):
        """The restored State, or None if there is nothing usable to restore.

        Home Assistant's RestoreStateData persists whatever this entity last reported,
        including "unavailable" — reachable when restore was off during a prior outage, and
        then turned on while still offline. Passing that through verbatim would reproduce
        the exact broken card this feature exists to eliminate, now with assumed_state
        layered on top, so a restored "unavailable" is treated as nothing to restore.
        """
        if self._restored is None or self._restored.state == STATE_UNAVAILABLE:
            return None

        return self._restored

    @property
    def entity_registry_enabled_default(self) -> bool:
        if self.config_entry is None:
            return True
        if not self.config_entry.data.get(CONF_ZONE_FILTER_ENABLED, False):
            return True
        return self.zone in self.config_entry.data.get(CONF_ENABLED_ZONES, [])

    @property
    def supported_features(self):
        return SUPPORT_HTD

    @property
    def name(self) -> str:
        if self.config_entry is None:
            return f"Zone {self.zone} ({self.device_name})"
        overrides = self.config_entry.data.get(CONF_ZONE_NAMES, {})
        cached = self.config_entry.data.get(CONF_CACHED_ZONE_NAMES, {})
        return (
            overrides.get(str(self.zone))
            or self.client.get_zone_name(self.zone)
            or cached.get(str(self.zone))
            or f"Zone {self.zone}"
        )

    def update(self):
        self.zone_info = self.client.get_zone(self.zone)

    @property
    def state(self):
        zone_info = self._live_zone()

        if zone_info is not None:
            return STATE_ON if zone_info.power else STATE_OFF

        restored = self._usable_restored()
        if self._restore_enabled and restored is not None:
            return restored.state

        return STATE_UNKNOWN

    @property
    def volume_step(self) -> float:
        return 1 / HtdConstants.MAX_VOLUME

    async def async_volume_up(self) -> None:
        await self._async_command(
            lambda: self.client.async_volume_up(self.zone), "raise the volume"
        )

    async def async_volume_down(self) -> None:
        await self._async_command(
            lambda: self.client.async_volume_down(self.zone), "lower the volume"
        )

    async def async_turn_on(self):
        await self._async_command(
            lambda: self.client.async_power_on(self.zone), "turn on"
        )

    async def async_turn_off(self):
        await self._async_command(
            lambda: self.client.async_power_off(self.zone), "turn off"
        )

    @property
    def volume_level(self) -> float | None:
        zone_info = self._live_zone()

        if zone_info is not None:
            return zone_info.volume / HtdConstants.MAX_VOLUME

        restored = self._usable_restored()
        if self._restore_enabled and restored is not None:
            return restored.attributes.get("volume_level")

        return None

    async def async_set_volume_level(self, volume: float):
        converted_volume = round(volume * HtdConstants.MAX_VOLUME)
        _LOGGER.info("setting new volume for zone %d to %f, raw htd = %d" % (self.zone, volume, converted_volume))
        await self._async_command(
            lambda: self.client.async_set_volume(self.zone, converted_volume),
            "set the volume",
        )

    @property
    def is_volume_muted(self) -> bool | None:
        zone_info = self._live_zone()

        if zone_info is not None:
            return zone_info.mute

        restored = self._usable_restored()
        if self._restore_enabled and restored is not None:
            return restored.attributes.get("is_volume_muted")

        return None

    async def async_mute_volume(self, mute):
        if mute:
            await self._async_command(
                lambda: self.client.async_mute(self.zone), "mute"
            )
        else:
            await self._async_command(
                lambda: self.client.async_unmute(self.zone), "unmute"
            )

    def _resolve_source_name(self, source: int) -> str:
        if self.config_entry is None:
            return self.client.get_source_name(source)
        overrides = self.config_entry.data.get(CONF_SOURCE_NAMES, {})
        cached = self.config_entry.data.get(CONF_CACHED_SOURCE_NAMES, {})
        return (
            overrides.get(str(source))
            # get_source_names reports only what the controller actually said, so a missing
            # entry falls through to the cache instead of to an invented "Source N"
            or self.client.get_source_names().get(source)
            or cached.get(str(source))
            or f"Source {source}"
        )

    @property
    def source(self) -> str | None:
        zone_info = self._live_zone()

        if zone_info is not None:
            return self._resolve_source_name(zone_info.source)

        restored = self._usable_restored()
        if self._restore_enabled and restored is not None:
            return restored.attributes.get("source")

        return None

    @property
    def extra_state_attributes(self):
        zone_info = self._live_zone()

        if zone_info is None:
            restored = self._usable_restored()
            if self._restore_enabled and restored is not None:
                source_id = restored.attributes.get("source_id")
                if source_id is not None:
                    return {"source_id": source_id}
            return {}

        # The controller's source index never changes when a source is renamed,
        # so this gives automations a stable handle. "Source N" rather than the
        # bare integer because select_source accepts that exact string back.
        return {"source_id": f"Source {zone_info.source}"}

    def _allowed_source_indices(self) -> list[int]:
        filter_enabled = (
            self.config_entry.data.get(CONF_SOURCE_FILTER_ENABLED, False)
            if self.config_entry is not None else False
        )
        filters = (
            self.config_entry.data.get(CONF_ZONE_SOURCE_FILTERS, {})
            if self.config_entry is not None else {}
        )
        allowed = filters.get(str(self.zone)) if filter_enabled else None
        return [
            i for i in range(1, len(self.sources) + 1)
            if allowed is None or not allowed or i in allowed
        ]

    def _build_source_map(self) -> dict[str, int]:
        result = {}
        allowed = self._allowed_source_indices()
        for i in allowed:
            # Insertion order matters: controller-native -> resolved/override, so the
            # currently active name is written last and wins on a collision between them.
            controller_name = self.client.get_source_name(i)
            result[controller_name] = i
            result[self._resolve_source_name(i)] = i
        # Generic labels are reserved: "Source N" always resolves to index N, so the
        # source_id attribute round-trips even if a display name collides with one.
        for i in allowed:
            result[f"Source {i}"] = i
        return result

    @property
    def source_list(self) -> list[str]:
        return [self._resolve_source_name(i) for i in self._allowed_source_indices()]

    @property
    def media_title(self):
        return self.source

    async def async_select_source(self, source: str) -> None:
        source_map = self._build_source_map()
        controller_index = source_map.get(source)
        if controller_index is None:
            _LOGGER.warning(
                "zone %d: cannot select unknown source %r, valid values are %s",
                self.zone, source, sorted(source_map),
            )
            return
        await self._async_command(
            lambda: self.client.async_set_source(self.zone, controller_index),
            "select a source",
        )

    @property
    def icon(self):
        return "mdi:disc-player"

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()

        if self._restore_enabled:
            self._restored = await self.async_get_last_state()

        # no refresh here: the client's heartbeat issues the all-zones query on every connect,
        # and subscribing is enough to receive it (or a replay, if it already arrived)
        await self.client.async_subscribe(self._do_update)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        await self.client.async_unsubscribe(self._do_update)

    def _do_update(self, zone: int):
        if zone is not None and zone != 0 and zone != self.zone:
            return

        # if there's a target volume for mca, don't update yet
        if isinstance(self.client, HtdMcaClient) and self.client.has_volume_target(self.zone):
            return

        if self.client.has_zone_data(self.zone):
            self.zone_info = self.client.get_zone(self.zone)

        # unconditional: the library now broadcasts zone=None on connect and disconnect, and
        # should_poll is False, so this is the only thing that repaints a card during an
        # outage or when one ends.
        self.async_write_ha_state()
