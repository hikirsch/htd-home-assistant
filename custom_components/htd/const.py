MANUFACTURER = "Home Theater Direct"
DOMAIN = "htd"

CONF_DEVICE_KIND = 'device_kind'
CONF_DEVICE_NAME = 'device_name'
CONF_SOURCES = 'sources'
CONF_RETRY_ATTEMPTS = 'retry_attempts'
CONF_SOCKET_TIMEOUT = 'socket_timeout'

# Naming UX additions (fork - UI labels & per-zone source filtering)
CONF_SOURCE_LABELS = 'source_labels'          # dict: { "1": "Sonos", "7": "Apple TV", ... }
CONF_ZONES = 'zones'                          # dict keyed by zone number:
                                              #   { "1": { "name": "Kitchen",
                                              #            "enabled": true,
                                              #            "allowed_sources": [1, 3, 7] } }
CONF_ZONE_NAME = 'name'
CONF_ZONE_ENABLED = 'enabled'
CONF_ZONE_ALLOWED_SOURCES = 'allowed_sources'
