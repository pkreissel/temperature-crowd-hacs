"""Config flow for TemperaturCrowd integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import secrets
import aiohttp

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)

from .const import DOMAIN, CONF_API_KEY, CONF_EMAIL, CONF_SERVER_URL
from .blind_rsa import get_blinded_message, unblind_signature

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SERVER_URL, default="http://192.168.178.109:3000"): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required("consent", default=False): bool,
    }
)

STEP_SENSORS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("sensors"): EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="temperature", multiple=True)
        ),
        vol.Required("postal_code"): str, # Used for coarse location/climate region mapping
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TemperaturCrowd."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.email: str | None = None
        self.server_url: str | None = None
        self.api_key: str | None = None
        self.session_id: str | None = None
        self._X: bytes | None = None
        self._blind_factor: int | None = None
        self._server_n: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get("consent"):
                errors["base"] = "consent_required"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )

            self.email = user_input[CONF_EMAIL]
            self.server_url = user_input[CONF_SERVER_URL].rstrip('/')
            
            # Generate a random 32-byte pseudonym X
            self._X = secrets.token_hex(32).encode()
            
            # Fetch Server Public Key and Blind X
            try:
                async with aiohttp.ClientSession() as session:
                    # 1. Fetch public key
                    pk_resp = await session.get(f"{self.server_url}/v1/auth/public-key")
                    pk_resp.raise_for_status()
                    pk_data = await pk_resp.json()
                    self._server_n = pk_data["n"]
                    server_e = pk_data["e"]
                    
                    # 2. Blind the message
                    self._blind_factor, blinded_hex = get_blinded_message(self._X, self._server_n, server_e)
                    
                    # 3. Request Link
                    resp = await session.post(
                        f"{self.server_url}/v1/auth/request-link", 
                        json={"email": self.email, "blinded_element": blinded_hex}
                    )
                    resp.raise_for_status()
                    data = await resp.json()
                    self.session_id = data["session_id"]
            except Exception as e:
                _LOGGER.error(f"Failed to request link: {e}")
                errors["base"] = "auth_failed"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )
                
            return await self.async_step_wait_for_email()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_wait_for_email(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Wait for the user to click the magic link."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                async with aiohttp.ClientSession() as session:
                    resp = await session.get(f"{self.server_url}/v1/auth/poll/{self.session_id}")
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    if data.get("status") == "verified":
                        evaluated_element_hex = data["evaluated_element"]
                        
                        # 4. Unblind the signature
                        final_signature = unblind_signature(
                            self._blind_factor, 
                            evaluated_element_hex, 
                            self._server_n
                        )
                        
                        # The token format is X:Signature
                        self.api_key = f"{self._X.decode()}:{final_signature}"
                        
                        return await self.async_step_sensors()
                    else:
                        errors["base"] = "not_verified"
            except Exception as e:
                _LOGGER.error(f"Failed to poll status: {e}")
                errors["base"] = "poll_failed"

        return self.async_show_form(
            step_id="wait_for_email", data_schema=vol.Schema({}), errors=errors
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the sensor selection and coarse location."""
        if user_input is not None:
            # Map the postal code to climate region A/B/C locally
            # Store the resulting config entry
            data = {
                CONF_API_KEY: self.api_key,
                CONF_SERVER_URL: self.server_url,
                "sensors": user_input["sensors"],
                "postal_code": user_input["postal_code"]
            }
            return self.async_create_entry(title="TemperaturCrowd", data=data)

        return self.async_show_form(
            step_id="sensors", data_schema=STEP_SENSORS_DATA_SCHEMA
        )
