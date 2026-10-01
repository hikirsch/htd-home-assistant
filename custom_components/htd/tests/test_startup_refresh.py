"""Startup query volume (issue #31).

refresh() with no zone is an all-zones query, and the client already issues one from its
heartbeat the moment the connection comes up. Any refresh an entity adds on top of that is
pure duplication, multiplied by the zone count, at the moment the hardware is least tolerant
of load — and on serial it lands inside the settle window the heartbeat deliberately waits out.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from homeassistant.const import CONF_UNIQUE_ID

from custom_components.htd.const import CONF_RESTORE_LAST_STATE
from custom_components.htd.media_player import HtdDevice

ZONES = 12


def test_adding_every_zone_entity_issues_no_extra_all_zone_query():
    client = MagicMock()
    client.model = {"zones": ZONES, "kind": MagicMock(value="lync")}
    client.connected = True
    client.ready = True
    client.async_subscribe = AsyncMock()
    client.refresh = AsyncMock()
    entry = MagicMock()
    entry.data = {CONF_UNIQUE_ID: "uid", CONF_RESTORE_LAST_STATE: False}

    devices = [HtdDevice("uid", "HTD", zone, [], client, entry) for zone in range(1, ZONES + 1)]

    async def add_all():
        for device in devices:
            await device.async_added_to_hass()

    asyncio.run(add_all())

    client.refresh.assert_not_awaited()
    # every entity still subscribes, which is how it gets its first paint: the client replays
    # to late subscribers once ready, and broadcasts the heartbeat's reply to early ones
    assert client.async_subscribe.await_count == ZONES
