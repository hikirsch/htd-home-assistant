"""Mock HA and external dependencies so tests run without a full HA install."""
import sys
from unittest.mock import MagicMock

_MOCK_MODULES = [
    "voluptuous",
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.discovery",
    "homeassistant.components",
    "homeassistant.components.media_player",
    "homeassistant.components.media_player.const",
    "htd_client",
    "htd_client.constants",
    "htd_client.models",
]

for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# homeassistant.components.media_player needs a real class for HtdDevice to inherit from
class _MediaPlayerEntityStub:
    """Stub base — lets HtdDevice be defined and instantiated in tests."""
    should_poll = False
    def async_write_ha_state(self): pass
    def schedule_update_ha_state(self, force_refresh=False): pass

_media_player_mod = sys.modules["homeassistant.components.media_player"]
_media_player_mod.MediaPlayerEntity = _MediaPlayerEntityStub

# homeassistant.components.number needs a real class for HtdEqNumber to inherit from
_number_mod = MagicMock()

class _NumberEntityStub:
    """Stub base — lets HtdEqNumber be defined and instantiated in tests."""
    should_poll = False
    def async_write_ha_state(self): pass

_number_mod.NumberEntity = _NumberEntityStub
sys.modules["homeassistant.components.number"] = _number_mod

# homeassistant.helpers.entity_registry needs a real RegistryEntryDisabler enum
# so that disabled_by comparisons work in tests.
from enum import Enum as _Enum

class _RegistryEntryDisabler(str, _Enum):
    INTEGRATION = "integration"
    USER = "user"
    CONFIG_ENTRY = "config_entry"

_er_mod = MagicMock()
_er_mod.RegistryEntryDisabler = _RegistryEntryDisabler
sys.modules["homeassistant.helpers.entity_registry"] = _er_mod
