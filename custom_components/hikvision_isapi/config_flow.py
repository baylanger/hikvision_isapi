"""Config flow for Hikvision ISAPI integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_NAME_COMPONENTS,
    DEFAULT_NAME_COMPONENTS,
    DOMAIN,
    NAME_COMPONENT_DEVICE_NAME,
    NAME_COMPONENT_HOST,
    NAME_COMPONENT_MODEL,
)
from .coordinator import build_device_name
from .isapi_client import DeviceInfo, ISAPIClient

_LOGGER = logging.getLogger(__name__)


def _at_least_one(value: list[str]) -> list[str]:
    """Validate that the naming-components multi-select isn't left empty."""
    if not value:
        raise vol.Invalid("select_at_least_one")
    return value


_NAME_COMPONENTS_SELECTOR = vol.All(
    selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                NAME_COMPONENT_DEVICE_NAME,
                NAME_COMPONENT_MODEL,
                NAME_COMPONENT_HOST,
            ],
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
            translation_key=CONF_NAME_COMPONENTS,
        )
    ),
    _at_least_one,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(
            CONF_NAME_COMPONENTS, default=DEFAULT_NAME_COMPONENTS
        ): _NAME_COMPONENTS_SELECTOR,
    }
)


async def _validate_credentials(
    host: str, username: str, password: str
) -> tuple[Optional[DeviceInfo], Dict[str, str]]:
    """Return (device_info, {}) on success or (None, errors) on failure."""
    client = ISAPIClient(host, username, password)
    try:
        device_info = await client.get_device_info()
    except httpx.HTTPStatusError as err:
        if err.response.status_code == 401:
            return None, {"base": "invalid_auth"}
        _LOGGER.error("ISAPI HTTP error: %s", err)
        return None, {"base": "cannot_connect"}
    except (httpx.ConnectError, httpx.TimeoutException):
        return None, {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unexpected error during config flow")
        return None, {"base": "unknown"}
    finally:
        await client.close()
    return device_info, {}


class HikvisionISAPIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision ISAPI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Handle the initial step: host + credentials + naming preference."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            name_components = user_input[CONF_NAME_COMPONENTS]

            device_info, errors = await _validate_credentials(
                host, username, password
            )
            if device_info is not None:
                # Use MAC as unique ID to prevent duplicate entries
                await self.async_set_unique_id(device_info.unique_id)
                self._abort_if_unique_id_configured()

                # Don't create the entry yet - show the user what the
                # resulting device name and an example entity_id will
                # actually look like, using this camera's real data, before
                # committing. Home Assistant's flow dialog provides a back
                # button automatically, so they can return here and change
                # their naming selection if they don't like the preview.
                self._pending_data = {
                    CONF_HOST: host,
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                    CONF_NAME_COMPONENTS: name_components,
                }
                self._pending_device_info = device_info
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Show the actual computed device name and an example entity_id
        for this camera, built from its real data, before creating the entry.
        """
        device_info = self._pending_device_info
        data = self._pending_data

        if user_input is not None:
            return self.async_create_entry(
                title=f"{device_info.model} ({data[CONF_HOST]})",
                data=data,
            )

        preview_name = build_device_name(
            device_info, data[CONF_HOST], data[CONF_NAME_COMPONENTS]
        )
        example_entity_id = f"select.{slugify(preview_name)}_blc_mode"

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "device_name": preview_name,
                "example_entity_id": example_entity_id,
            },
        )

    async def async_step_reconfigure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Handle a reconfigure: let the user change host or credentials."""
        entry = self._get_reconfigure_entry()
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            device_info, errors = await _validate_credentials(
                host, username, password
            )
            if device_info is not None:
                # Ensure the new host still points at the SAME physical camera
                # (MAC match) — prevents accidentally repointing an entry at a
                # different camera, which would leave its entities orphaned.
                await self.async_set_unique_id(device_info.unique_id)
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        # Prefill host + username from current entry; leave password blank.
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=entry.data[CONF_HOST]
                    ): str,
                    vol.Required(
                        CONF_USERNAME, default=entry.data[CONF_USERNAME]
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
