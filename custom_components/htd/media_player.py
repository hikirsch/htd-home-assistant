"""Support for HTD"""

import logging

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
from htd_client import BaseClient, HtdConstants, HtdDeviceKind, HtdMcaClient
from htd_client.models import ZoneDetail

MEDIA_PLAYER_PREFIX = "media_player.htd_"

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


async def async_setup_entry(_: HomeAssistant, config_entry: HtdClientConfigEntry, async_add_entities):
    entities = []

    client = config_entry.runtime_data
    zone_count = client.get_zone_count()
    source_count = client.get_source_count()
    device_name = config_entry.title
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
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


class HtdDevice(MediaPlayerEntity):
    should_poll = False

    unique_id: str = None
    device_name: str = None
    client: BaseClient = None
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
        client
    ):
        self.unique_id = f"{unique_id}_{zone}"
        self.device_name = device_name
        self.zone = zone
        self.client = client
        self.sources = sources

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

    def turn_on(self):
        self.client.power_on(self.zone)

    def turn_off(self):
        self.client.power_off(self.zone)

    @property
    def volume_level(self) -> float:
        return  self.zone_info.volume / HtdConstants.MAX_VOLUME

    @property
    def available(self) -> bool:
        return self.client.ready and self.zone_info is not None

    def set_volume_level(self, new_volume: float):
        converted_volume = int(new_volume * HtdConstants.MAX_VOLUME)
        _LOGGER.info("setting new volume for zone %d to %f, raw htd = %d" % (self.zone, new_volume, converted_volume))
        self.client.set_volume(self.zone, converted_volume)

    @property
    def is_volume_muted(self) -> bool:
        return self.zone_info.mute

    def mute_volume(self, mute):
        self.client.toggle_mute(self.zone)

    @property
    def source(self) -> str:
        return self.sources[self.zone_info.source - 1]

    @property
    def source_list(self):
        return self.sources

    @property
    def media_title(self):
        return self.source

    def select_source(self, source: int):
        source_index = self.sources.index(source)
        self.client.set_source(self.zone, source_index + 1)

    @property
    def icon(self):
        return "mdi:disc-player"

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Sensors should also register callbacks to HA when their state changes
        # print('registering callback')
        self.client.subscribe(self._do_update)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.client.unsubscribe(self._do_update)

    def _do_update(self, zone: int):
        if zone is not None and zone != self.zone and self.zone_info is not None:
            return

        # if there's a target volume for mca, don't update yet
        if isinstance(self.client, HtdMcaClient) and self.client._target_volumes.get(self.zone) is not None:
            return

        self.zone_info = self.client.get_zone(self.zone)
        self.schedule_update_ha_state()
