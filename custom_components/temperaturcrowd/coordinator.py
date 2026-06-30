import logging
import random
from datetime import timedelta, datetime, timezone
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period

from .const import DOMAIN, CONF_API_KEY, CONF_SERVER_URL

_LOGGER = logging.getLogger(__name__)

class TemperaturCrowdCoordinator(DataUpdateCoordinator):
    """Class to manage fetching LTS and pushing to server."""

    def __init__(self, hass: HomeAssistant, api_key: str, server_url: str, sensors: list[str], postal_code: str) -> None:
        """Initialize."""
        self.api_key = api_key
        self.server_url = server_url
        self.sensors = sensors
        self.postal_code = postal_code
        self.session = aiohttp.ClientSession()
        
        self.last_successful_upload: datetime | None = None
        self.overheating_hours: int = 0

        # Add randomness to prevent thundering herd spikes (interval between 50 and 70 minutes)
        jitter_minutes = random.randint(0, 20)
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=50 + jitter_minutes),
        )

    async def _async_calculate_historical_overheating(self):
        """Calculate overheating hours for the current year."""
        start_of_year = datetime(datetime.now(timezone.utc).year, 1, 1, tzinfo=timezone.utc)
        end_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start_of_year,
            end_time,
            self.sensors,
            "hour",
            None,
            {"mean"}
        )
        
        overheated_hours = set()
        for sensor_id, data_points in stats.items():
            for point in data_points:
                mean_temp = point.get("mean")
                if mean_temp is not None and mean_temp > 26.0:
                    overheated_hours.add(point["start"])
        
        self.overheating_hours = len(overheated_hours)

    async def _async_update_data(self):
        """Fetch stats from Home Assistant DB and push to server."""
        try:
            if self.last_successful_upload is None:
                await self._async_calculate_historical_overheating()
            # 1. Fetch long-term statistics for the last hour
            # (In a real implementation, we'd track the last sent timestamp
            # to handle the initial backfill vs ongoing updates)
            
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=1)
            
            # This fetches the hour's stats from the DB
            print("Before async_add_executor_job")
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_time,
                end_time,
                self.sensors,
                "hour",
                None,
                {"mean", "min", "max"}
            )
            print("After async_add_executor_job")
            
            readings = []
            any_overheated = False
            
            for sensor_id, data_points in stats.items():
                for point in data_points:
                    mean_temp = point.get("mean", 0)
                    if mean_temp > 26.0:
                        any_overheated = True
                        
                    readings.append({
                        "ts": datetime.fromtimestamp(point["start"], tz=timezone.utc).isoformat(),
                        "temp_c": mean_temp,
                        "temp_c_min": point.get("min", 0),
                        "temp_c_max": point.get("max", 0),
                        "room_ref": sensor_id
                    })
            
            if any_overheated:
                self.overheating_hours += 1
            
            if not readings:
                return True
            
            # 2. Map to Canonical Schema format
            payload = {
                "device_id": self.hass.data["core.uuid"], # HA instance UUID
                "api_key": self.api_key,
                "postal_code": self.postal_code,
                "readings": readings
            }
            
            # 3. POST to server
            print("Before session.post")
            async with self.session.post(f"{self.server_url}/v1/ingest", json=payload) as resp:
                print("Inside session.post")
                resp.raise_for_status()

            self.last_successful_upload = datetime.now(timezone.utc)
            print("Returning True")
            return True
            
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
