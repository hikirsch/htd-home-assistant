"""The device-naming step must reuse the model info already obtained by the
connection-validation step instead of probing the device again.

Every serial probe opens the port, and a port open can DTR-reset the gateway
(cheap USB-serial adapters especially). Probing twice in one flow doubles the
chance the second probe hits a mid-reset gateway — which aborted the whole
flow with 'unknown_model' even though validation just succeeded.

Unlike the other test modules (which replicate flow logic), this module
imports the real config_flow by upgrading the conftest mocks just enough for
the class definitions to work.
"""
import asyncio
import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _ConfigFlowStub:
    """Minimal stand-in for homeassistant ConfigFlow."""

    def __init_subclass__(cls, **kwargs):
        pass

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}

    async def async_set_unique_id(self, unique_id):
        pass

    def _abort_if_unique_id_configured(self):
        pass


class _OptionsFlowStub:
    def __init__(self, *args, **kwargs):
        pass


_config_entries = MagicMock()
_config_entries.ConfigFlow = _ConfigFlowStub
_config_entries.OptionsFlow = _OptionsFlowStub
_config_entries.OptionsFlowWithConfigEntry = _OptionsFlowStub
sys.modules["homeassistant.config_entries"] = _config_entries
sys.modules["homeassistant.helpers.service_info"] = MagicMock()
sys.modules["homeassistant.helpers.service_info.dhcp"] = MagicMock()

config_flow = importlib.import_module("custom_components.htd.config_flow")

from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT  # noqa: E402

MCA66_MODEL = {
    "identifier": b"Wangine_MCA66",
    "zones": 6,
    "sources": 6,
    "friendly_name": "MCA66",
    "name": "MCA66",
    "kind": "mca",
}


def test_serial_flow_probes_device_only_once():
    flow = config_flow.HtdConfigFlow()

    with patch.object(
        config_flow, "async_get_model_info", new_callable=AsyncMock
    ) as probe:
        probe.return_value = MCA66_MODEL

        result = asyncio.run(
            flow.async_step_serial_connection({CONF_PATH: "/dev/ttyUSB0"})
        )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
    assert flow._model_info == MCA66_MODEL
    assert probe.call_count == 1


def test_network_flow_probes_device_only_once():
    flow = config_flow.HtdConfigFlow()

    with patch.object(
        config_flow, "async_get_model_info", new_callable=AsyncMock
    ) as probe:
        probe.return_value = MCA66_MODEL

        result = asyncio.run(
            flow.async_step_network_connection(
                {CONF_HOST: "1.2.3.4", CONF_PORT: 10006}
            )
        )

    assert result["type"] == "form"
    assert result["step_id"] == "device"
    assert flow._model_info == MCA66_MODEL
    assert probe.call_count == 1


def test_device_step_still_probes_when_no_cached_model_info():
    """Safety net: entry paths that never probed still work."""
    flow = config_flow.HtdConfigFlow()
    flow.serial_address = "/dev/ttyUSB0"
    flow._model_info = None

    with patch.object(
        config_flow, "async_get_model_info", new_callable=AsyncMock
    ) as probe:
        probe.return_value = MCA66_MODEL

        result = asyncio.run(flow.async_step_device())

    assert result["type"] == "form"
    assert result["step_id"] == "device"
    assert probe.call_count == 1


def test_create_entry_persists_the_detected_model_key():
    """Without a stored key every restart must re-probe the device, which is exactly why an
    offline restart today produces no entities at all. Every creation path — user, network,
    serial and DHCP — funnels through _create_entry, so this one write covers all of them."""
    from custom_components.htd.config_flow import HtdConfigFlow
    from custom_components.htd.const import CONF_MODEL_KEY, CONF_RESTORE_LAST_STATE

    flow = HtdConfigFlow()
    flow.host = "1.2.3.4"
    flow.port = 10006
    flow.unique_id = "uid"
    flow._device_name = "HTD"
    flow._model_info = {"key": "mca66", "zones": 6, "sources": 6}
    flow.async_create_entry = MagicMock()

    flow._create_entry()

    data = flow.async_create_entry.call_args.kwargs["data"]
    assert data[CONF_MODEL_KEY] == "mca66"


def test_create_entry_defaults_state_restoration_to_off():
    """Restoration changes what a state means — an "off" zone may actually be on. It has to
    be something the user opts into, not something an upgrade turns on underneath them."""
    from custom_components.htd.config_flow import HtdConfigFlow
    from custom_components.htd.const import CONF_RESTORE_LAST_STATE

    flow = HtdConfigFlow()
    flow.host = "1.2.3.4"
    flow.port = 10006
    flow.unique_id = "uid"
    flow._device_name = "HTD"
    flow._model_info = {"key": "lync12", "zones": 12, "sources": 19}
    flow.async_create_entry = MagicMock()

    flow._create_entry()

    data = flow.async_create_entry.call_args.kwargs["data"]
    assert data[CONF_RESTORE_LAST_STATE] is False
