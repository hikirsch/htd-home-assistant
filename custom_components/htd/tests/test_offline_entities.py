"""Offline behavior across all three platforms (issue #30).

Entities must exist and be legible while the amplifier is off, must be honest that what they
are showing is assumed, and must fail loudly rather than silently when commanded.
"""
import asyncio
from unittest.mock import MagicMock

import pytest
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.exceptions import HomeAssistantError

from custom_components.htd.const import CONF_RESTORE_LAST_STATE
from custom_components.htd.entity import HtdEntity


class _Entity(HtdEntity):
    """Minimal concrete consumer — the mixin's contract is what is under test here."""

    def __init__(self, client, config_entry, zone=1):
        self.client = client
        self.config_entry = config_entry
        self.zone = zone


def _entry(restore: bool):
    entry = MagicMock()
    entry.data = {CONF_UNIQUE_ID: "uid", CONF_RESTORE_LAST_STATE: restore}
    return entry


def _client(*, ready=True, has_data=True, connected=True, enabled=True):
    client = MagicMock()
    client.ready = ready
    client.connected = connected
    client.has_zone_data = MagicMock(return_value=has_data)
    client.get_zone = MagicMock(return_value=MagicMock(enabled=enabled))
    return client


# --- availability matrix ---

def test_live_data_is_available_regardless_of_the_restore_setting():
    """Restoration must not change anything while the device is reachable — the option is
    about outages only."""
    for restore in (True, False):
        entity = _Entity(_client(), _entry(restore))
        assert entity.available is True
        assert entity.assumed_state is False


def test_offline_with_restore_off_is_unavailable():
    """With the option off, behavior is exactly what it is today, except that the entity now
    exists during an outage instead of being missing from the state machine entirely."""
    entity = _Entity(_client(ready=False, has_data=False, connected=False), _entry(False))
    assert entity.available is False


def test_offline_with_restore_on_is_available_and_assumed():
    """The requested behavior: the dashboard reads "off" rather than Unavailable, and Home
    Assistant renders explicit on/off buttons instead of a toggle, because the value may be
    stale."""
    entity = _Entity(_client(ready=False, has_data=False, connected=False), _entry(True))
    assert entity.available is True
    assert entity.assumed_state is True


def test_connected_but_no_zone_data_yet_follows_the_same_rule():
    """The window between connecting and the first zone frame is an outage as far as the card
    is concerned, and must not flicker to a third presentation."""
    entity = _Entity(_client(ready=False, has_data=False, connected=True), _entry(True))
    assert entity.available is True
    assert entity.assumed_state is True


def test_no_config_entry_means_no_restoration():
    """The YAML setup path passes no config entry, so there is nowhere for the option to
    live. It must default to today's behavior rather than crashing on a None lookup."""
    entity = _Entity(_client(ready=False, has_data=False, connected=False), None)
    assert entity.available is False


# --- the protocol's own zone-enabled flag ---

def test_a_zone_the_controller_reports_as_disabled_is_unavailable():
    """This is what the removed Entity.enabled override actually meant: a zone with no keypad
    wired to it should not present as a working speaker."""
    entity = _Entity(_client(enabled=False), _entry(False))
    assert entity.available is False


def test_a_disabled_zone_is_unavailable_even_with_live_data_and_restore_on():
    """Discriminates the `enabled` branch from the restore fallback: with restore on and live
    zone data present, `_restore_enabled` alone would say available. Only consulting
    `ZoneDetail.enabled` when there is live data to consult can produce `False` here."""
    entity = _Entity(_client(enabled=False), _entry(True))
    assert entity.available is False


def test_the_disabled_flag_is_not_inferred_from_missing_data():
    """Absence of data is not the controller saying "disabled". Conflating the two is what
    made every entity vanish during an outage in the first place."""
    entity = _Entity(
        _client(ready=False, has_data=False, connected=False, enabled=False),
        _entry(True),
    )
    assert entity.available is True


# --- commands while offline ---

def test_a_command_issued_while_offline_raises_a_visible_error():
    """A silently dropped command produces an automation trace that claims success and a card
    that snaps back a second later. An error is the only honest outcome, and it is why there
    is deliberately no replay queue."""
    client = _client(connected=False)
    entity = _Entity(client, _entry(True))

    async def _run():
        await entity._async_command(lambda: client.async_power_on(1), "turn on")

    with pytest.raises(HomeAssistantError):
        asyncio.run(_run())


def test_a_connection_dropping_mid_command_also_raises_a_visible_error():
    """The connection check and the write are not atomic. The library's own exception is the
    backstop for the race, and it must reach the user as the same error."""
    from htd_client.exceptions import HtdConnectionError

    client = _client(connected=True)

    async def _boom():
        raise HtdConnectionError("not connected")

    entity = _Entity(client, _entry(True))

    async def _run():
        await entity._async_command(_boom, "turn on")

    with pytest.raises(HomeAssistantError):
        asyncio.run(_run())


def test_a_command_that_succeeds_raises_nothing():
    """Guards the guard: the wrapper must not turn a working command into an error."""
    client = _client(connected=True)
    calls = []

    async def _ok():
        calls.append("sent")

    entity = _Entity(client, _entry(False))

    asyncio.run(entity._async_command(_ok, "turn on"))
    assert calls == ["sent"]


# --- media_player ---

from custom_components.htd.const import (
    CONF_CACHED_SOURCE_NAMES,
    CONF_CACHED_ZONE_NAMES,
    CONF_SOURCE_NAMES,
    CONF_ZONE_NAMES,
)
from custom_components.htd.media_player import HtdDevice


def _mp_entry(restore=False, cached_zones=None, cached_sources=None, overrides=None):
    entry = MagicMock()
    entry.data = {
        CONF_UNIQUE_ID: "uid",
        CONF_RESTORE_LAST_STATE: restore,
        CONF_ZONE_NAMES: overrides or {},
        CONF_SOURCE_NAMES: {},
        CONF_CACHED_ZONE_NAMES: cached_zones or {},
        CONF_CACHED_SOURCE_NAMES: cached_sources or {},
    }
    return entry


def _mp_client(*, connected=False, zone_names=None, source_names=None):
    client = MagicMock()
    client.model = {"zones": 12, "kind": MagicMock(value="lync")}
    client.connected = connected
    client.ready = connected
    client.has_zone_data = MagicMock(return_value=False)
    client.get_zone_name = MagicMock(side_effect=lambda z: (zone_names or {}).get(z))
    client.get_source_names = MagicMock(return_value=source_names or {})
    client.get_source_name = MagicMock(side_effect=lambda s: (source_names or {}).get(s, f"Source {s}"))
    return client


def test_htd_device_does_not_shadow_the_reserved_enabled_property():
    """Home Assistant reads Entity.enabled to decide whether an entity joins the state
    machine at all, and drives it from registry_entry.disabled_by. Shadowing it both blocked
    offline entities outright and left the zone-filter feature unable to hide a zone."""
    assert "enabled" not in vars(HtdDevice)


def test_an_offline_zone_falls_back_to_its_cached_controller_name():
    """Home Assistant passes entity.name to the registry as original_name and the registry
    overwrites what it stored. Without the cache, one offline restart renames "Kitchen" to
    "Zone 3" permanently — it does not come back when the amplifier does."""
    client = _mp_client(connected=False)
    entry = _mp_entry(cached_zones={"3": "kitchen"})
    device = HtdDevice("uid", "HTD", 3, [], client, entry)

    assert device.name == "kitchen"


def test_a_live_controller_name_still_beats_the_cache():
    """The cache is a fallback, not a replacement. A zone renamed at the keypad must show its
    new name immediately, not the stale one from last restart."""
    client = _mp_client(connected=True, zone_names={3: "dining"})
    entry = _mp_entry(cached_zones={"3": "kitchen"})
    device = HtdDevice("uid", "HTD", 3, [], client, entry)

    assert device.name == "dining"


def test_a_user_override_still_beats_everything():
    """Resolution order is user override -> live -> cached -> Zone N, unchanged at the top."""
    client = _mp_client(connected=True, zone_names={3: "dining"})
    entry = _mp_entry(cached_zones={"3": "kitchen"}, overrides={"3": "Mine"})
    device = HtdDevice("uid", "HTD", 3, [], client, entry)

    assert device.name == "Mine"


def test_volume_and_source_are_none_rather_than_raising_without_zone_data():
    """These three dereferenced zone_info unguarded. That was safe only because entities could
    not exist before data arrived — an invariant this change deliberately removes."""
    client = _mp_client(connected=False)
    device = HtdDevice("uid", "HTD", 1, [], client, _mp_entry(restore=True))
    device.zone_info = None

    assert device.volume_level is None
    assert device.is_volume_muted is None
    assert device.source is None


def test_restored_values_are_used_when_there_is_no_live_data():
    """The reporter's actual request: the dashboard should read what the zone was doing the
    last time Home Assistant could see it."""
    client = _mp_client(connected=False)
    device = HtdDevice("uid", "HTD", 1, [], client, _mp_entry(restore=True))
    device.zone_info = None
    device._restored = MagicMock(
        state="off",
        attributes={
            "volume_level": 0.25,
            "is_volume_muted": False,
            "source": "turntable",
            "source_id": "Source 2",
        },
    )

    assert device.state == "off"
    assert device.volume_level == 0.25
    assert device.is_volume_muted is False
    assert device.source == "turntable"
    assert device.extra_state_attributes == {"source_id": "Source 2"}


def test_restore_with_nothing_saved_is_available_but_unknown():
    """On a first-ever offline start, or after the recorder database is cleared, there is
    nothing to restore. Falling back to unavailable here would make the presentation depend on
    database contents and oscillate between two different looks."""
    from homeassistant.const import STATE_UNKNOWN

    client = _mp_client(connected=False)
    device = HtdDevice("uid", "HTD", 1, [], client, _mp_entry(restore=True))
    device.zone_info = None
    device._restored = None

    assert device.available is True
    assert device.assumed_state is True
    assert device.state == STATE_UNKNOWN


def test_a_restored_unavailable_state_is_not_passed_through_verbatim():
    """Reachable sequence: restore is off (the default) during an outage, so the entity
    correctly persists a literal "unavailable" state when Home Assistant shuts down. The
    user then turns restore on and reloads while still offline. `available` is now True, so
    without this guard Home Assistant would write the string "unavailable" as the entity's
    state — the exact broken card this feature exists to eliminate, with assumed_state
    layered on top. A restored unavailable must degrade to unknown instead, and the same
    guard applies to every attribute read off the same restored State object."""
    from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

    client = _mp_client(connected=False)
    device = HtdDevice("uid", "HTD", 1, [], client, _mp_entry(restore=True))
    device.zone_info = None
    device._restored = MagicMock(
        state=STATE_UNAVAILABLE,
        attributes={
            "volume_level": 0.25,
            "is_volume_muted": False,
            "source": "turntable",
            "source_id": "Source 2",
        },
    )

    assert device.available is True
    assert device.assumed_state is True
    assert device.state == STATE_UNKNOWN
    assert device.volume_level is None
    assert device.is_volume_muted is None
    assert device.source is None
    assert device.extra_state_attributes == {}


def test_turn_on_while_offline_raises_a_visible_error():
    """Every command method must pre-check, not just the ones that happen to be tested."""
    client = _mp_client(connected=False)
    device = HtdDevice("uid", "HTD", 1, [], client, _mp_entry(restore=True))

    with pytest.raises(HomeAssistantError):
        asyncio.run(device.async_turn_on())


def test_do_update_repaints_even_when_there_is_no_zone_data():
    """should_poll is False on every platform, so a card only repaints on a broadcast. The old
    early-return meant the library's new connection_lost broadcast changed nothing on screen
    and stale live values stayed up for the whole outage."""
    from unittest.mock import patch

    class _SomeOtherClient:
        """`htd_client` is a MagicMock here, so media_player's `isinstance(self.client,
        HtdMcaClient)` check needs a real class as its second argument or it raises TypeError
        before reaching the behavior under test."""

    client = _mp_client(connected=False)
    device = HtdDevice("uid", "HTD", 1, [], client, _mp_entry(restore=True))
    device.zone_info = None
    written = []
    device.async_write_ha_state = lambda: written.append(True)

    with patch("custom_components.htd.media_player.HtdMcaClient", _SomeOtherClient):
        device._do_update(None)

    assert written == [True]


def test_an_offline_source_falls_back_to_its_cached_controller_name():
    """Mirrors the zone-name cache: get_source_names() reports nothing while offline, so
    without the cached tier a source silently reverts to the generic "Source N" label
    instead of the name the controller last reported."""
    client = _mp_client(connected=False)
    entry = _mp_entry(cached_sources={"2": "turntable"})
    device = HtdDevice("uid", "HTD", 1, [], client, entry)

    assert device._resolve_source_name(2) == "turntable"


# --- number and switch ---

from custom_components.htd.number import HtdEqNumber
from custom_components.htd.switch import HtdDndSwitch


def _eq_client(*, connected=False, zone_names=None):
    client = MagicMock()
    client.model = {"zones": 12, "kind": MagicMock(value="lync")}
    client.connected = connected
    client.ready = connected
    client.has_zone_data = MagicMock(return_value=connected)
    client.get_zone = MagicMock(return_value=MagicMock(enabled=True, bass=4.0, dnd=True))
    client.get_zone_name = MagicMock(side_effect=lambda z: (zone_names or {}).get(z))
    return client


def test_number_restores_its_last_value_offline():
    """A zone card showing "Off" above "Bass: Unavailable" reads as more broken than the bug
    this fixes, which is why restoration covers all three platforms or none."""
    client = _eq_client(connected=False)
    number = HtdEqNumber(client, "uid", 1, "bass", _mp_entry(restore=True))
    number._restored_value = 4.0

    assert number.available is True
    assert number.assumed_state is True
    assert number.native_value == 4.0


def test_number_is_unavailable_offline_with_restore_off():
    """The default must stay today's semantics: no invented values unless asked for."""
    client = _eq_client(connected=False)
    number = HtdEqNumber(client, "uid", 1, "bass", _mp_entry(restore=False))

    assert number.available is False


def test_number_prefers_live_data_over_the_restored_value():
    """Once the amplifier is back the restored value must be dropped immediately, or a card
    keeps showing a stale slider position that no longer matches the hardware."""
    client = _eq_client(connected=True)
    number = HtdEqNumber(client, "uid", 1, "bass", _mp_entry(restore=True))
    number._restored_value = -8.0

    assert number.native_value == 4.0
    assert number.assumed_state is False


def test_setting_a_number_while_offline_raises_a_visible_error():
    """A slider that snaps back with no explanation is the worst of both worlds."""
    client = _eq_client(connected=False)
    number = HtdEqNumber(client, "uid", 1, "bass", _mp_entry(restore=True))

    with pytest.raises(HomeAssistantError):
        asyncio.run(number.async_set_native_value(3.0))


def test_number_falls_back_to_the_cached_zone_name():
    """Same registry-overwrite hazard as media_player: the EQ entity's name embeds the zone
    name, so an offline restart would rewrite "Kitchen - Bass" to "Zone 3 - Bass"."""
    client = _eq_client(connected=False)
    entry = _mp_entry(cached_zones={"3": "kitchen"})
    number = HtdEqNumber(client, "uid", 3, "bass", entry)

    assert number.name == "kitchen - Bass"


def test_switch_restores_its_last_state_offline():
    """DND is Lync-only and lives on the same device card as the zone's media player."""
    client = _eq_client(connected=False)
    switch = HtdDndSwitch(client, "uid", 1, _mp_entry(restore=True))
    switch._restored_is_on = True

    assert switch.available is True
    assert switch.assumed_state is True
    assert switch.is_on is True


def test_switch_is_unavailable_offline_with_restore_off():
    """Default semantics, unchanged."""
    client = _eq_client(connected=False)
    switch = HtdDndSwitch(client, "uid", 1, _mp_entry(restore=False))

    assert switch.available is False


def test_toggling_a_switch_while_offline_raises_a_visible_error():
    """Both directions — a DND toggle silently dropped is an automation that thinks it
    silenced a room and did not."""
    client = _eq_client(connected=False)
    switch = HtdDndSwitch(client, "uid", 1, _mp_entry(restore=True))

    with pytest.raises(HomeAssistantError):
        asyncio.run(switch.async_turn_on())

    with pytest.raises(HomeAssistantError):
        asyncio.run(switch.async_turn_off())


def test_number_do_update_repaints_without_zone_data():
    """Same reason as media_player: the connection_lost broadcast must actually repaint."""
    client = _eq_client(connected=False)
    number = HtdEqNumber(client, "uid", 1, "bass", _mp_entry(restore=True))
    written = []
    number.async_write_ha_state = lambda: written.append(True)

    number._do_update(None)

    assert written == [True]


def test_switch_do_update_repaints_without_zone_data():
    """Same reason again."""
    client = _eq_client(connected=False)
    switch = HtdDndSwitch(client, "uid", 1, _mp_entry(restore=True))
    written = []
    switch.async_write_ha_state = lambda: written.append(True)

    switch._do_update(None)

    assert written == [True]


# --- async_added_to_hass actually wires restoration up ---
#
# Every test above assigns _restored / _restored_value / _restored_is_on directly. None of
# them would catch async_added_to_hass failing to populate those fields itself. These stub
# async_get_last_state / async_get_last_number_data per instance and drive the real method.
#
# Ceiling: conftest.py's RestoreEntity stub makes async_get_last_state always return None,
# so this only guards against a future refactor of our own wiring code. It cannot verify
# real RestoreEntity/RestoreNumber inheritance, and it cannot verify Home Assistant's own
# async_internal_added_to_hass -> async_added_to_hass ordering, since none of that exists
# in this test double.

from unittest.mock import AsyncMock


def test_media_player_async_added_to_hass_populates_restored_from_last_state():
    client = _mp_client(connected=False)
    client.async_subscribe = AsyncMock()
    device = HtdDevice("uid", "HTD", 1, [], client, _mp_entry(restore=True))
    fake_state = MagicMock(state="off", attributes={})
    device.async_get_last_state = AsyncMock(return_value=fake_state)

    asyncio.run(device.async_added_to_hass())

    assert device._restored is fake_state
    client.async_subscribe.assert_awaited_once_with(device._do_update)


def test_switch_async_added_to_hass_populates_restored_is_on_from_last_state():
    from homeassistant.const import STATE_ON

    client = _eq_client(connected=False)
    client.async_subscribe = AsyncMock()
    switch = HtdDndSwitch(client, "uid", 1, _mp_entry(restore=True))
    switch.async_get_last_state = AsyncMock(return_value=MagicMock(state=STATE_ON))

    asyncio.run(switch.async_added_to_hass())

    assert switch._restored_is_on is True


def test_number_async_added_to_hass_populates_restored_value_from_last_number_data():
    client = _eq_client(connected=False)
    client.async_subscribe = AsyncMock()
    number = HtdEqNumber(client, "uid", 1, "bass", _mp_entry(restore=True))
    number.async_get_last_number_data = AsyncMock(
        return_value=MagicMock(native_value=4.0)
    )

    asyncio.run(number.async_added_to_hass())

    assert number._restored_value == 4.0
