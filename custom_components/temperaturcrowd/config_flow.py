"""Config flow for TemperaturCrowd integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import secrets
import aiohttp
import uuid

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

STEP_METADATA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("building_age"): vol.In(["pre_1977", "1978_1994", "1995_2015", "new_build"]),
        vol.Required("floor_level"): vol.In(["ground", "middle", "top"]),
        vol.Required("orientation"): vol.In(["south_west", "north_east"]),
        vol.Required("insulation_status"): vol.In(["unrenovated", "retrofit"]),
        vol.Required("consent_2025", default=False): bool,
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TemperaturCrowd."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.server_url: str | None = None
        self.api_key: str | None = None
        self.session_id: str | None = None
        self._X: bytes | None = None
        self._blind_factor: int | None = None
        self._server_n: str | None = None
        self.sensors: list[str] = []
        self.postal_code: str | None = None

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
                    
                    # 3. Init session
                    resp = await session.post(
                        f"{self.server_url}/v1/auth/init", 
                        json={"blinded_element": blinded_hex}
                    )
                    resp.raise_for_status()
                    data = await resp.json()
                    self.session_id = data["session_id"]
            except Exception as e:
                _LOGGER.error(f"Failed to initialize session: {e}")
                errors["base"] = "auth_failed"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
                )
                
            return await self.async_step_wait_for_browser()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_wait_for_browser(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Wait for the user to complete verification in their browser."""
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

        setup_url = f"{self.server_url}/v1/auth/setup?session_id={self.session_id}"
        
        return self.async_show_form(
            step_id="wait_for_browser", 
            description_placeholders={"setup_url": setup_url},
            data_schema=vol.Schema({}), 
            errors=errors
        )

  async def async_step_sensors(
      self, user_input: dict[str, Any] | None = None
  ) -> FlowResult:
      """Handle the sensor selection and coarse location."""
      if user_input is not None:
          self.sensors = user_input["sensors"]
          # Coarsen postal code to first 2 digits for privacy (ADR-0004)
          self.postal_code = user_input["postal_code"][:2]
          return await self.async_step_metadata()

      return self.async_show_form(
          step_id="sensors", data_schema=STEP_SENSORS_DATA_SCHEMA
      )

  async def async_step_metadata(
      self, user_input: dict[str, Any] | None = None
  ) -> FlowResult:
      """Handle the metadata collection step."""
      errors: dict[str, str] = {}
      if user_input is not None:
          if not user_input.get("consent_2025"):
              errors["base"] = "consent_required"
              return self.async_show_form(
                  step_id="metadata", data_schema=STEP_METADATA_DATA_SCHEMA, errors=errors
              )
          
          data = {
              CONF_API_KEY: self.api_key,
              CONF_SERVER_URL: self.server_url,
              "device_id": str(uuid.uuid4()), # Generate stable random UUID per install
              "sensors": self.sensors,
              "postal_code": self.postal_code,
              "building_age": user_input["building_age"],
              "floor_level": user_input["floor_level"],
              "orientation": user_input["orientation"],
              "insulation_status": user_input["insulation_status"]
          }
          return self.async_create_entry(title="TemperaturCrowd", data=data)

      return self.async_show_form(
          step_id="metadata", data_schema=STEP_METADATA_DATA_SCHEMA, errors=errors
      )
