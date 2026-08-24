"""Shared offline behavior for every HTD entity platform.

Availability, assumed state, restore plumbing and the offline-command guard are identical
across media_player, number and switch, so they live here rather than three times over.
"""
from homeassistant.exceptions import HomeAssistantError
from htd_client.exceptions import HtdConnectionError

from .const import CONF_RESTORE_LAST_STATE


class HtdEntity:
    """Mixin. Inherit it FIRST so its properties win over the Home Assistant base class."""

    client = None
    zone: int = None
    config_entry = None

    def _live_zone(self):
        """The controller's current data for this zone, or None if there is none to trust.

        Platforms that keep their own cached copy override this; see HtdDevice.
        """
        if not self.client.ready or not self.client.has_zone_data(self.zone):
            return None

        return self.client.get_zone(self.zone)

    @property
    def _restore_enabled(self) -> bool:
        if self.config_entry is None:
            return False

        return bool(self.config_entry.data.get(CONF_RESTORE_LAST_STATE, False))

    @property
    def available(self) -> bool:
        zone_info = self._live_zone()

        if zone_info is not None:
            # the controller told us this zone has no keypad wired to it; do not present it
            # as a working speaker. only consulted when there is live data to consult.
            return bool(zone_info.enabled)

        return self._restore_enabled

    @property
    def assumed_state(self) -> bool:
        """True exactly when what is displayed is restored rather than live."""
        return self._live_zone() is None

    async def _async_command(self, factory, description: str) -> None:
        """Run a client command, failing visibly rather than silently while offline.

        There is deliberately no replay queue: a queued "turn on the kitchen" firing hours
        later, when the amplifier happens to be powered for something else, is a worse
        outcome than an error the user can see.
        """
        if not self.client.connected:
            raise HomeAssistantError(
                f"HTD device is offline; cannot {description} for zone {self.zone}"
            )

        try:
            await factory()
        except HtdConnectionError as e:
            # the connection dropped between the check above and the write
            raise HomeAssistantError(
                f"HTD device is offline; cannot {description} for zone {self.zone}"
            ) from e
