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

# homeassistant.components.number needs a real class for HtdEqNumber to inherit from
_number_mod = MagicMock()

class _NumberEntityStub:
    """Stub base — lets HtdEqNumber be defined and instantiated in tests."""
    should_poll = False
    def async_write_ha_state(self): pass

_number_mod.NumberEntity = _NumberEntityStub
sys.modules["homeassistant.components.number"] = _number_mod

# homeassistant.components.switch needs a real class for HtdDndSwitch to inherit from
_switch_mod = MagicMock()

class _SwitchEntityStub:
    """Stub base — lets HtdDndSwitch be defined and instantiated in tests."""
    should_poll = False
    def async_write_ha_state(self): pass

_switch_mod.SwitchEntity = _SwitchEntityStub
sys.modules["homeassistant.components.switch"] = _switch_mod
