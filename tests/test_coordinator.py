from datetime import datetime, timezone
import aiohttp
import sys
from unittest.mock import AsyncMock, patch, MagicMock

# Mock homeassistant before importing coordinator
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.config_entries'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
sys.modules['homeassistant.components'] = MagicMock()
sys.modules['homeassistant.components.recorder'] = MagicMock()
sys.modules['homeassistant.components.recorder.models'] = MagicMock()
sys.modules['homeassistant.components.recorder.statistics'] = MagicMock()

# Create a dummy DataUpdateCoordinator
class DummyCoordinator:
    def __init__(self, hass, logger, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval

sys.modules['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator = DummyCoordinator
sys.modules['homeassistant.helpers.update_coordinator'].UpdateFailed = Exception

mock_get_instance = MagicMock()
sys.modules['homeassistant.components.recorder'].get_instance = mock_get_instance

from custom_components.temperaturcrowd.coordinator import TemperaturCrowdCoordinator
import pytest

@pytest.mark.asyncio
@patch('aiohttp.ClientSession.post')
async def test_coordinator_mapping(mock_post):
    hass = MagicMock()
    hass.data = {"core.uuid": "test-uuid"}
    
    mock_instance = MagicMock()
    mock_instance.async_add_executor_job = AsyncMock(return_value={
        "sensor.bedroom_temperature": [
            {
                "start": 1719658800, # 2024-06-29T11:00:00Z
                "mean": 26.5,
                "min": 25.0,
                "max": 28.0
            }
        ]
    })
    mock_get_instance.return_value = mock_instance
    
    mock_resp = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_resp
    mock_post.return_value = mock_ctx
    
    coordinator = TemperaturCrowdCoordinator(hass, "test-api-key", "http://test-server", ["sensor.bedroom_temperature"], "12345")
    
    result = await coordinator._async_update_data()
    
    assert result is True
    mock_post.assert_called_once()
    
    # Verify the payload structure
    call_kwargs = mock_post.call_args.kwargs
    payload = call_kwargs["json"]
    
    assert payload["device_id"] == "test-uuid"
    assert payload["api_key"] == "test-api-key"
    assert len(payload["readings"]) == 1
    
    reading = payload["readings"][0]
    assert reading["temp_c"] == 26.5
    assert reading["temp_c_min"] == 25.0
    assert reading["temp_c_max"] == 28.0
    assert reading["room_ref"] == "sensor.bedroom_temperature"
    # Ensure it converted the unix timestamp to ISO format
    assert "T11:00:00+00:00" in reading["ts"]
