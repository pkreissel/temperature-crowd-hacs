"""Sensor platform for TemperaturCrowd."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_API_KEY
from .coordinator import TemperaturCrowdCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TemperaturCrowd sensor."""
    api_key = entry.data[CONF_API_KEY]
    sensors = entry.data.get("sensors", [])
    postal_code = entry.data.get("postal_code", "")
    
    # Instantiate the coordinator
    coordinator = TemperaturCrowdCoordinator(hass, api_key, sensors, postal_code)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Add the dummy status entity
    async_add_entities([TemperaturCrowdStatusSensor(coordinator)])


class TemperaturCrowdStatusSensor(CoordinatorEntity[TemperaturCrowdCoordinator], SensorEntity):
    """Representation of a TemperaturCrowd Status Sensor."""

    def __init__(self, coordinator: TemperaturCrowdCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "TemperaturCrowd Upload Status"
        self._attr_unique_id = f"{DOMAIN}_status"
        self._attr_icon = "mdi:cloud-upload"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        # If the coordinator successfully ran, its data is True
        if self.coordinator.last_update_success:
            return "OK"
        return "Failed"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "monitored_sensors": self.coordinator.sensors,
            "postal_code": self.coordinator.postal_code,
            "last_upload": self.coordinator.last_update_success,
        }
