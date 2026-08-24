"""EQ controls (bass, treble, balance) as NumberEntity sliders for HTD zones."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import CONF_UNIQUE_ID

from .const import CONF_ZONE_NAMES

# Ranges as (min, max, step). String keys match HtdDeviceKind.value ("lync"/"mca").
_RANGES: dict[str, dict[str, tuple[float, float, float]]] = {
    "lync": {
        "bass":    (-10.0, 10.0, 1.0),
        "treble":  (-10.0, 10.0, 1.0),
        "balance": (-18.0, 18.0, 1.0),
    },
    "mca": {
        "bass":    (-12.0, 12.0, 4.0),
        "treble":  (-12.0, 12.0, 4.0),
        "balance": (-12.0, 12.0, 6.0),
    },
}


def _eq_range(kind_value: str, control: str) -> tuple[float, float, float]:
    """Return (min, max, step) for the given device kind value and control name."""
    return _RANGES[kind_value][control]


def _eq_enabled_default(control: str) -> bool:
    """Balance is hidden by default; bass and treble are shown."""
    return control != "balance"


async def async_setup_entry(_, config_entry, async_add_entities):
    client = config_entry.runtime_data
    unique_id = config_entry.data.get(CONF_UNIQUE_ID)
    entities = [
        HtdEqNumber(client, unique_id, zone, control, config_entry)
        for zone in range(1, client.get_zone_count() + 1)
        for control in ("bass", "treble", "balance")
    ]
    async_add_entities(entities)


class HtdEqNumber(NumberEntity):
    _attr_mode = NumberMode.SLIDER
    should_poll = False

    def __init__(self, client, unique_id: str, zone: int, control: str, config_entry):
        self.client = client
        self.zone = zone
        self.control = control
        self.config_entry = config_entry
        kind_value = client.model["kind"].value
        min_val, max_val, step = _eq_range(kind_value, control)
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_unique_id = f"{unique_id}_zone_{zone}_{control}"
        self._attr_entity_registry_enabled_default = _eq_enabled_default(control)

    @property
    def name(self) -> str:
        overrides = self.config_entry.data.get(CONF_ZONE_NAMES, {})
        zone_name = (
            overrides.get(str(self.zone))
            or self.client.get_zone_name(self.zone)
            or f"Zone {self.zone}"
        )
        return f"{zone_name} - {self.control.capitalize()}"

    @property
    def native_value(self) -> float | None:
        if not self.client.has_zone_data(self.zone):
            return None
        return getattr(self.client.get_zone(self.zone), self.control)

    async def async_set_native_value(self, value: float) -> None:
        int_val = round(value)
        if self.control == "bass":
            await self.client.async_set_bass(self.zone, int_val)
        elif self.control == "treble":
            await self.client.async_set_treble(self.zone, int_val)
        else:
            await self.client.async_set_balance(self.zone, int_val)

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
