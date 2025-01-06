import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant

_LOGGER = logging.getLogger(__name__)


@callback
def _async_cleanup_registry_entries(
    hass: HomeAssistant,
    config_entry: ConfigEntry
) -> None:
    """Remove extra entities that are no longer part of the integration."""
    pass

    # entity_registry = er.async_get(hass)

    # existing_entries = er.async_entries_for_config_entry(
    #     entity_registry,
    #     config_entry.entry_id
    # )
    # entities = {(entity.domain, entity.unique_id): entity.entity_id for entity
    #             in existing_entries}

    # active_zones = config_entry.options.get(CONF_ACTIVE_ZONES)
    #
    # extra_entities = existing_entries[active_zones:]
    #
    # # extra_entities = set(entities.keys()).difference(htd_data.unique_ids)
    # # if not extra_entities:
    # #     return
    #
    # for entity in extra_entities:
    #     if entity_registry.async_is_registered(entity.entity_id):
    #         entity_registry.async_remove(entity.entity_id)
    #
    # _LOGGER.info(
    #     "Cleaning up  HTD entities: removed %s extra entities for config "
    #     "entry %s",
    #     len(extra_entities),
    #     config_entry.entry_id
    # )
