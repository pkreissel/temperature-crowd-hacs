import logging
import random
from datetime import timedelta, datetime, timezone
import hashlib
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    statistics_during_period,
    async_import_statistics,
    StatisticData,
    StatisticMetaData,
)

from .const import DOMAIN, CONF_API_KEY, CONF_SERVER_URL

_LOGGER = logging.getLogger(__name__)

class TemperaturCrowdCoordinator(DataUpdateCoordinator):
    """Class to manage fetching LTS and pushing to server."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api_key: str, server_url: str,
        device_id: str, sensors: list[str], postal_code: str,
        building_age: str | None = None,
        floor_level: str | None = None,
        orientation: str | None = None,
        insulation_status: str | None = None
    ) -> None:
        """Initialize."""
        self.entry = entry
        self.api_key = api_key
        self.server_url = server_url
        self.device_id = device_id
        self.sensors = sensors
        self.postal_code = postal_code
        self.building_age = building_age
        self.floor_level = floor_level
        self.orientation = orientation
        self.insulation_status = insulation_status
        
        last_upload_iso = entry.data.get("last_successful_upload")
        if last_upload_iso:
            self.last_successful_upload = datetime.fromisoformat(last_upload_iso)
        else:
            self.last_successful_upload = None
            
        self.overheating_hours: int = entry.data.get("overheating_hours", 0)

        # Add randomness to prevent thundering herd spikes (interval between 50 and 70 minutes)
        jitter_minutes = random.randint(0, 20)
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=50 + jitter_minutes),
        )

    async def _async_calculate_historical_overheating(self):
        """Calculate overheating hours since Jan 1 2025 and backfill."""
        start_of_history = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        stats = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start_of_history,
            end_time,
            self.sensors,
            "hour",
            None,
            {"mean", "min", "max"}
        )
        
        overheating_points = set()
        all_readings = []
        
        for sensor_id, data_points in stats.items():
            for point in data_points:
                mean_temp = point.get("mean")
                if mean_temp is not None:
                    if mean_temp > 26.0:
                        overheating_points.add(point["start"])
                        
                    all_readings.append({
                        "ts": datetime.fromtimestamp(point["start"], tz=timezone.utc).isoformat(),
                        "temp_c": mean_temp,
                        "temp_c_min": point.get("min"),
                        "temp_c_max": point.get("max"),
                        "room_ref": hashlib.sha256(sensor_id.encode('utf-8')).hexdigest()[:16]
                    })
        
        # 1. Backfill HA Statistics Database
        if overheating_points:
            sorted_hours = sorted(list(overheating_points))
            cumulative_sum = 0
            statistics = []
            for hour_ts in sorted_hours:
                cumulative_sum += 1
                statistics.append(
                    StatisticData(
                        start=datetime.fromtimestamp(hour_ts, tz=timezone.utc),
                        state=cumulative_sum,
                        sum=cumulative_sum
                    )
                )
            
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name="TemperaturCrowd Überhitzestunden",
                source=DOMAIN,
                statistic_id=f"sensor.{DOMAIN}_overheating",
                unit_of_measurement="h"
            )
            
            async_import_statistics(self.hass, metadata, statistics)
            self.overheating_hours = cumulative_sum

        # 2. Backfill the Server in chunks of 1000
        if all_readings:
            chunk_size = 1000
            session = async_get_clientsession(self.hass)
            for i in range(0, len(all_readings), chunk_size):
                chunk = all_readings[i:i + chunk_size]
                payload = {
                    "device_id": self.device_id,
                    "api_key": self.api_key,
                    "postal_code": self.postal_code,
                    "building_age": self.building_age,
                    "floor_level": self.floor_level,
                    "orientation": self.orientation,
                    "insulation_status": self.insulation_status,
                    "readings": chunk
                }
                
                try:
                    async with session.post(f"{self.server_url}/v1/ingest", json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        resp.raise_for_status()
                except aiohttp.ClientError as e:
                    _LOGGER.error(f"Failed to backfill historic chunk: {e}")

    async def _async_update_data(self):
        """Fetch stats from Home Assistant DB and push to server."""
        try:
            if self.last_successful_upload is None:
                await self._async_calculate_historical_overheating()
            
            end_time = datetime.now(timezone.utc)
            if self.last_successful_upload:
                start_time = self.last_successful_upload
            else:
                start_time = end_time - timedelta(hours=4)
            
            # This fetches the hour's stats from the DB
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
            
            readings = []
            overheating_points = set()
            
            for sensor_id, data_points in stats.items():
                for point in data_points:
                    mean_temp = point.get("mean")
                    if mean_temp is not None:
                        if mean_temp > 26.0:
                            overheating_points.add(point["start"])
                            
                        readings.append({
                            "ts": datetime.fromtimestamp(point["start"], tz=timezone.utc).isoformat(),
                            "temp_c": mean_temp,
                            "temp_c_min": point.get("min"),
                            "temp_c_max": point.get("max"),
                            "room_ref": hashlib.sha256(sensor_id.encode('utf-8')).hexdigest()[:16]
                        })
            
            if overheating_points:
                self.overheating_hours += len(overheating_points)
                
                # Push the new statistics to HA history database
                metadata = StatisticMetaData(
                    has_mean=False,
                    has_sum=True,
                    name="TemperaturCrowd Überhitzestunden",
                    source=DOMAIN,
                    statistic_id=f"sensor.{DOMAIN}_overheating",
                    unit_of_measurement="h"
                )
                
                sorted_hours = sorted(list(overheating_points))
                statistics = []
                current_sum = self.overheating_hours - len(overheating_points)
                
                for hour_ts in sorted_hours:
                    current_sum += 1
                    statistics.append(
                        StatisticData(
                            start=datetime.fromtimestamp(hour_ts, tz=timezone.utc),
                            state=current_sum,
                            sum=current_sum
                        )
                    )
                async_import_statistics(self.hass, metadata, statistics)
            
            if not readings:
                # Update last_successful_upload anyway to slide window
                self.last_successful_upload = end_time
                new_data = dict(self.entry.data)
                new_data["last_successful_upload"] = self.last_successful_upload.isoformat()
                new_data["overheating_hours"] = self.overheating_hours
                self.hass.config_entries.async_update_entry(self.entry, data=new_data)
                return True
            
            # 2. Map to Canonical Schema format
            payload = {
                "device_id": self.device_id,
                "api_key": self.api_key,
                "postal_code": self.postal_code,
                "building_age": self.building_age,
                "floor_level": self.floor_level,
                "orientation": self.orientation,
                "insulation_status": self.insulation_status,
                "readings": readings
            }
            
            # 3. POST to server
            session = async_get_clientsession(self.hass)
            async with session.post(f"{self.server_url}/v1/ingest", json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()

            self.last_successful_upload = end_time
            
            # Save durable state
            new_data = dict(self.entry.data)
            new_data["last_successful_upload"] = self.last_successful_upload.isoformat()
            new_data["overheating_hours"] = self.overheating_hours
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            
            return True
            
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
