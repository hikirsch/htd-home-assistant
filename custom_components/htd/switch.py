"""DND (Do Not Disturb) per-zone switch entity for HTD Lync devices."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_UNIQUE_ID

from .const import CONF_ZONE_NAMES


async def async_setup_entry(_, config_entry, async_add_entities):
    client = config_entry.runtime_data
    if client.model["kind"].value != "lync":
        return
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
    entities = [
        HtdDndSwitch(client, unique_id, zone, config_entry)
        for zone in range(1, client.get_zone_count() + 1)
    ]
    async_add_entities(entities)


class HtdDndSwitch(SwitchEntity):
    should_poll = False
    _attr_entity_registry_enabled_default = True

    def __init__(self, client, unique_id: str, zone: int, config_entry):
        self.client = client
        self.zone = zone
        self.config_entry = config_entry
        self._attr_unique_id = f"{unique_id}_zone_{zone}_dnd"

    @property
    def name(self) -> str:
        overrides = self.config_entry.data.get(CONF_ZONE_NAMES, {})
        zone_name = (
            overrides.get(str(self.zone))
            or self.client.get_zone_name(self.zone)
            or f"Zone {self.zone}"
        )
        return f"{zone_name} - DND"

    @property
    def is_on(self) -> bool | None:
        if not self.client.has_zone_data(self.zone):
            return None
        return self.client.get_zone(self.zone).dnd

    async def async_turn_on(self, **kwargs) -> None:
        await self.client.async_set_dnd(self.zone, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.client.async_set_dnd(self.zone, False)

    def _do_update(self, zone: int) -> None:
        if zone is None and not self.client.has_zone_data(self.zone):
            return
        if zone is not None and zone != 0 and zone != self.zone:
            return
        if not self.client.has_zone_data(self.zone):
            return
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await self.client.async_subscribe(self._do_update)

    async def async_will_remove_from_hass(self) -> None:
        await self.client.async_unsubscribe(self._do_update)
