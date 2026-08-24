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
