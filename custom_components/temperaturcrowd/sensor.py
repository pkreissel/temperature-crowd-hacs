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
    server_url = entry.data["server_url"]
    sensors = entry.data.get("sensors", [])
    postal_code = entry.data.get("postal_code", "")
    
    # Instantiate the coordinator
    coordinator = TemperaturCrowdCoordinator(hass, api_key, server_url, sensors, postal_code)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Add the entities
    async_add_entities([
        TemperaturCrowdStatusSensor(coordinator),
        TemperaturCrowdOverheatingSensor(coordinator)
    ])


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
        last_upload_iso = None
        if self.coordinator.last_successful_upload:
            last_upload_iso = self.coordinator.last_successful_upload.isoformat()
            
        return {
            "monitored_sensors": self.coordinator.sensors,
            "postal_code": self.coordinator.postal_code,
            "last_upload_status": self.coordinator.last_update_success,
            "last_upload_time": last_upload_iso,
        }

class TemperaturCrowdOverheatingSensor(CoordinatorEntity[TemperaturCrowdCoordinator], SensorEntity):
    """Representation of the Überhitzestunden Sensor."""

    def __init__(self, coordinator: TemperaturCrowdCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "TemperaturCrowd Überhitzestunden"
        self._attr_unique_id = f"{DOMAIN}_overheating"
        self._attr_icon = "mdi:thermometer-alert"
        self._attr_native_unit_of_measurement = "h"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.overheating_hours
