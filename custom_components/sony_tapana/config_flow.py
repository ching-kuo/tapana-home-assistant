"""Config flow for the Sony Tapana integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_NODE_ID, DOMAIN
from .tapana_client import AuthenticationError, SonyMflightError, TapanaClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_NODE_ID): vol.Coerce(int),
    }
)


class SonyTapanaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Sony Tapana."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            node_id = user_input[CONF_NODE_ID]

            await self.async_set_unique_id(f"sony_tapana_{node_id}")
            self._abort_if_unique_id_configured()

            try:
                await self._test_credentials(email, password, node_id)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except SonyMflightError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Sony LGTG (node {node_id})",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_NODE_ID: node_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def _test_credentials(
        self, email: str, password: str, node_id: int
    ) -> None:
        """Validate credentials and that the node ID exists.

        authenticate() raises AuthenticationError on bad credentials.
        get_node() raises ApiError (a SonyMflightError) when the cloud is
        unreachable or the node ID is unknown; both surface as cannot_connect.
        """
        client = TapanaClient(email=email, password=password, node_id=node_id)
        await self.hass.async_add_executor_job(client.authenticate)
        await self.hass.async_add_executor_job(client.get_node)
