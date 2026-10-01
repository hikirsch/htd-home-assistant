"""Tests for serial connection support added to config_flow.py.

These replicate the pure logic added to HtdConfigFlow, HtdOptionsFlowHandler,
and __init__.py's async_setup_entry — see the Global Constraints note in
docs/superpowers/plans/2026-07-05-serial-config-flow.md for why these are
local replicas rather than direct imports of config_flow.py.
"""


def _build_unique_id(host=None, port=None, serial_address=None):
    """Replicate unique_id generation from async_step_network_connection /
    async_step_serial_connection in config_flow.py."""
    if serial_address:
        return "htd-serial-%s" % serial_address
    return "htd-%s-%s" % (host, port)


def _build_connection_data(host=None, port=None, serial_address=None):
    """Replicate the connection-data dict construction in
    HtdConfigFlow._create_entry."""
    if serial_address:
        return {"path": serial_address}
    return {"host": host, "port": port}


def _route_connection_type(connection_type: str) -> str:
    """Replicate the routing decision in async_step_connection_type."""
    if connection_type == "serial":
        return "serial_connection"
    return "network_connection"


def _is_serial_config(data: dict) -> bool:
    """Replicate the CONF_PATH-presence branch used in _create_entry,
    async_setup_entry (__init__.py), and HtdOptionsFlowHandler.async_step_init."""
    return bool(data.get("path"))


def test_network_unique_id():
    assert _build_unique_id(host="192.168.1.5", port=10006) == "htd-192.168.1.5-10006"


def test_serial_unique_id():
    assert _build_unique_id(serial_address="/dev/ttyUSB0") == "htd-serial-/dev/ttyUSB0"


def test_serial_unique_id_with_by_id_path():
    path = "/dev/serial/by-id/usb-FTDI_USB-RS232_Cable-if00-port0"
    assert _build_unique_id(serial_address=path) == f"htd-serial-{path}"


def test_network_connection_data_shape():
    data = _build_connection_data(host="192.168.1.5", port=10006)
    assert data == {"host": "192.168.1.5", "port": 10006}


def test_serial_connection_data_shape():
    data = _build_connection_data(serial_address="/dev/ttyUSB0")
    assert data == {"path": "/dev/ttyUSB0"}


def test_serial_connection_data_excludes_host_port_keys():
    data = _build_connection_data(serial_address="/dev/ttyUSB0")
    assert "host" not in data
    assert "port" not in data


def test_routes_to_serial_step():
    assert _route_connection_type("serial") == "serial_connection"


def test_routes_to_network_step():
    assert _route_connection_type("network") == "network_connection"


def test_serial_config_detected_when_path_present():
    assert _is_serial_config({"path": "/dev/ttyUSB0"}) is True


def test_network_config_detected_when_path_absent():
    assert _is_serial_config({"host": "192.168.1.5", "port": 10006}) is False


def test_empty_path_treated_as_network():
    assert _is_serial_config({"path": ""}) is False
