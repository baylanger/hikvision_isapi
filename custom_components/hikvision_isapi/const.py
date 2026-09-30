"""Constants for the Hikvision ISAPI integration."""

DOMAIN = "hikvision_isapi"
PLATFORMS = ["switch", "number", "select"]

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_NAME_COMPONENTS = "entity_name_components"

DEFAULT_SCAN_INTERVAL = 30

# Which pieces make up the device name (and therefore the entity_id prefix)
# for a NEWLY-added camera. The user picks any combination of these three
# in the config flow. Only affects new devices - Home Assistant never
# renames an existing entity_id automatically once it's been created.
NAME_COMPONENT_DEVICE_NAME = "device_name"  # camera's own configured name, e.g. "cam-office"
NAME_COMPONENT_MODEL = "model"              # e.g. "DS-2CD2385G1-I"
NAME_COMPONENT_HOST = "host"                # whatever was typed in the Host field

# Matches the integration's original (pre-multi-language) behavior, so a
# camera added without touching this new setting looks the same as before.
DEFAULT_NAME_COMPONENTS = [NAME_COMPONENT_MODEL, NAME_COMPONENT_HOST]
