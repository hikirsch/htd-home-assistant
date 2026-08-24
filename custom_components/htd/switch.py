"""DND (Do Not Disturb) per-zone switch entity for HTD Lync devices."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from .const import CONF_ZONE_NAMES, CONF_ZONE_FILTER_ENABLED, CONF_ENABLED_ZONES, DOMAIN


async def async_setup_platform(hass, _, async_add_entities, __=None):
    """Set up DND switch entities for devices configured via YAML (e.g. serial)."""
    htd_configs = hass.data[DOMAIN]
    entities = []

    for config in htd_configs:
        unique_id = config[CONF_UNIQUE_ID]
        client = config["client"]

        if client.model["kind"].value != "lync":
            continue

        for zone in range(1, client.get_zone_count() + 1):
            entities.append(HtdDndSwitch(client, unique_id, zone, None))

    async_add_entities(entities)
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    client = config_entry.runtime_data
    if client.model["kind"].value != "lync":
        return
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)

    zone_filter_enabled = config_entry.data.get(CONF_ZONE_FILTER_ENABLED, False)
    enabled_zones = set(config_entry.data.get(CONF_ENABLED_ZONES, []))
    registry = er.async_get(hass)

    entities = []
    for zone in range(1, client.get_zone_count() + 1):
        entities.append(HtdDndSwitch(client, unique_id, zone, config_entry))

        should_enable = not zone_filter_enabled or zone in enabled_zones
        uid = f"{unique_id}_zone_{zone}_dnd"
        entity_id = registry.async_get_entity_id("switch", DOMAIN, uid)
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


class HtdDndSwitch(SwitchEntity):
    should_poll = False

    def __init__(self, client, unique_id: str, zone: int, config_entry):
        self.client = client
        self.zone = zone
        self.config_entry = config_entry
        self._attr_unique_id = f"{unique_id}_zone_{zone}_dnd"

    @property
    def entity_registry_enabled_default(self) -> bool:
        if self.config_entry is None:
            return True
        if self.config_entry.data.get(CONF_ZONE_FILTER_ENABLED, False):
            return self.zone in self.config_entry.data.get(CONF_ENABLED_ZONES, [])
        return True

    @property
    def name(self) -> str:
        overrides = self.config_entry.data.get(CONF_ZONE_NAMES, {}) if self.config_entry else {}
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
