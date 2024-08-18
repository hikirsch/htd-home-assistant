"""Support for HTD"""

import logging

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SOURCE,
    CONF_UNIQUE_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from htd_client import HtdClient, HtdConstants
from htd_client.models import ZoneDetail

from .const import CONF_ACTIVE_ZONES, CONF_UPDATE_VOLUME_ON_CHANGE

MEDIA_PLAYER_PREFIX = "media_player.htd_"

SUPPORT_HTD = (
    MediaPlayerEntityFeature.SELECT_SOURCE |
    MediaPlayerEntityFeature.TURN_OFF | MediaPlayerEntityFeature.TURN_ON |
    MediaPlayerEntityFeature.VOLUME_MUTE |
    MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_STEP)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    entities = []

    device_name = config_entry.title
    host = config_entry.data.get(CONF_HOST)
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
    port = config_entry.data.get(CONF_PORT)
    active_zones = config_entry.options.get(CONF_ACTIVE_ZONES)
    sources = [config_entry.options.get(f"{CONF_SOURCE}_{index}") for index in
        range(1, HtdConstants.MAX_HTD_SOURCES + 1)]
    update_volume_on_change = config_entry.options.get(
        CONF_UPDATE_VOLUME_ON_CHANGE
    )

    client = HtdClient(host, port)

    for zone in range(0, active_zones):
        entity = HtdDevice(
            unique_id,
            device_name,
            zone + 1,
            sources,
            update_volume_on_change,
            client, )
        entities.append(entity)

    async_add_entities(entities)


class HtdDevice(MediaPlayerEntity):
    unique_id: str = None
    device_name: str = None
    client: HtdClient = None
    sources: [str] = None
    zone: int = None
    changing_volume: int | None = None
    zone_info: ZoneDetail = None

    def __init__(
        self,
        unique_id,
        device_name,
        zone,
        sources,
        update_volume_on_change,
        client
    ):
        self.unique_id = f"{unique_id}_{zone}"
        self.device_name = device_name
        self.zone = zone
        self.client = client
        self.sources = sources
        self.update_volume_on_change = update_volume_on_change
        self.my_entity_id = (f"{MEDIA_PLAYER_PREFIX}"
                             f"{device_name.lower()}_zone_{zone}")
        self.update()

    @property
    def enabled(self) -> bool:
        return self.zone_info is not None

    @property
    def supported_features(self):
        return SUPPORT_HTD

    @property
    def name(self):
        return f"Zone {self.zone} ({self.device_name})"

    def update(self):
        self.zone_info = self.client.query_zone(self.zone)
        _LOGGER.debug(
            "got new update for Zone %d, zone_info = %s" % (
                self.zone, self.zone_info)
        )

    @property
    def state(self):
        if self.zone_info.power is None:
            return STATE_UNKNOWN
        if self.zone_info.power:
            return STATE_ON
        return STATE_OFF

    def turn_on(self):
        self.client.power_on(self.zone)

    def turn_off(self):
        self.client.power_off(self.zone)

    @property
    def volume_level(self) -> float:
        return self.zone_info.htd_volume / HtdConstants.MAX_HTD_VOLUME

    def set_volume_level(self, new_volume: float):
        if self.changing_volume is not None:
            _LOGGER.debug(
                "changing new desired volume for zone %d to %d" % (
                self.zone, new_volume)
            )
            self.changing_volume = int(new_volume * 100)
            return

        def on_increment(desired: float, zone_info: ZoneDetail) -> int | None:
            if self.update_volume_on_change:
                self.zone_info = zone_info
                self.schedule_update_ha_state()

            _LOGGER.debug(
                "updated zone = %d, desired = %f, current = %f" % (
                self.zone, desired, self.zone_info.volume)
            )

            if desired != self.changing_volume:
                _LOGGER.debug(
                    "a new volume for zone %d has been chosen, value = %d" % (
                    self.zone, self.changing_volume)
                )
                return self.changing_volume

            return None

        self.changing_volume = int(new_volume * 100)
        self.client.set_volume(self.zone, self.changing_volume, on_increment)
        self.changing_volume = None
        self.schedule_update_ha_state()

    @property
    def is_volume_muted(self) -> bool:
        return self.zone_info.mute

    def mute_volume(self, mute):
        self.client.toggle_mute(self.zone)

    @property
    def source(self) -> int:
        return self.sources[self.zone_info.source - 1]

    @property
    def source_list(self):
        return self.sources

    @property
    def media_title(self):
        return self.source

    def select_source(self, source: int):
        index = self.sources.index(source)
        self.client.set_source(self.zone, index + 1)

    @property
    def icon(self):
        return "mdi:disc-player"
