from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from htd_client import BaseClient

type HtdConfigEntry = ConfigEntry[BaseClient]


class HtdSourceConfig(TypedDict):
    zone: int
    alias: str
    enabled: bool
    intercom: bool
