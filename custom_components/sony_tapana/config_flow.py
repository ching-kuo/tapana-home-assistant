"""Config flow for the Sony Tapana integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_NODE_ID, DOMAIN
from .tapana_client import AuthenticationError, Node, SonyMflightError, TapanaClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _coerce_node_id(value: Any) -> int | None:
    """Parse a node id, which the cloud returns float-formatted (e.g. "1429475.0")."""
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None


class SonyTapanaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow for Sony Tapana."""

    VERSION = 1

    def __init__(self) -> None:
        self._email: str = ""
        self._password: str = ""
        self._devices: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect credentials and discover the account's devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                nodes = await self._fetch_nodes(email, password)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except SonyMflightError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"
            else:
                # Only devices with a numeric id can be queried/controlled.
                devices = {
                    str(n.id): (n.name or f"Node {n.id}")
                    for n in nodes
                    if _coerce_node_id(n.id) is not None
                }
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    self._email = email
                    self._password = password
                    self._devices = devices
                    return await self.async_step_select_device()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user pick which discovered device to add."""
        if user_input is not None:
            key = user_input[CONF_NODE_ID]
            title = self._devices.get(key) or f"Sony LGTG (node {key})"
            # key came from _devices, which only holds coercible ids.
            node_id = _coerce_node_id(key)

            await self.async_set_unique_id(f"sony_tapana_{node_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=title,
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_NODE_ID: node_id,
                },
            )

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema({vol.Required(CONF_NODE_ID): vol.In(self._devices)}),
        )

    async def _fetch_nodes(self, email: str, password: str) -> list[Node]:
        """Authenticate and list the account's devices.

        authenticate() raises AuthenticationError on bad credentials.
        get_nodes() raises ApiError (a SonyMflightError) when the cloud is
        unreachable; both surface to the caller for mapping.
        """
        client = TapanaClient(email=email, password=password, node_id=0)
        await self.hass.async_add_executor_job(client.authenticate)
        return await self.hass.async_add_executor_job(client.get_nodes)
