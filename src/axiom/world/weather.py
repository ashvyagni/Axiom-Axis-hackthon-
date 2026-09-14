import httpx
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class WeatherProvider:
    """Live weather data provider using Open-Meteo (free, no API key required)."""
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self):
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl = 600  # 10 minutes
    
    async def get_weather(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Get current weather for a location."""
        cache_key = f"{latitude:.2f},{longitude:.2f}"
        now = datetime.now(timezone.utc).timestamp()
        
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_data
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                        "timezone": "auto",
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    result = self._normalize(data)
                    self._cache[cache_key] = (now, result)
                    return result
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")
        
        return self._default()
    
    def _normalize(self, data: dict) -> dict[str, Any]:
        """Normalize weather data to a standard format."""
        current = data.get("current", {})
        weather_code = current.get("weather_code", 0)
        
        return {
            "temperature_c": current.get("temperature_2m", 0),
            "humidity_pct": current.get("relative_humidity_2m", 0),
            "precipitation_mm": current.get("precipitation", 0),
            "wind_speed_kmh": current.get("wind_speed_10m", 0),
            "weather_code": weather_code,
            "condition": self._code_to_condition(weather_code),
            "is_adverse": self._is_adverse(weather_code, current),
            "risk_factors": self._assess_risks(weather_code, current),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    def _code_to_condition(self, code: int) -> str:
        """Convert WMO weather code to human-readable condition."""
        conditions = {
            0: "clear",
            1: "mainly_clear",
            2: "partly_cloudy",
            3: "overcast",
            45: "fog",
            48: "rime_fog",
            51: "light_drizzle",
            53: "moderate_drizzle",
            55: "dense_drizzle",
            61: "slight_rain",
            63: "moderate_rain",
            65: "heavy_rain",
            71: "slight_snow",
            73: "moderate_snow",
            75: "heavy_snow",
            80: "slight_rain_showers",
            81: "moderate_rain_showers",
            82: "violent_rain_showers",
            95: "thunderstorm",
            96: "thunderstorm_with_hail",
            99: "thunderstorm_with_heavy_hail",
        }
        return conditions.get(code, "unknown")
    
    def _is_adverse(self, code: int, current: dict) -> bool:
        """Determine if weather conditions are adverse."""
        adverse_codes = {45, 48, 51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 95, 96, 99}
        wind = current.get("wind_speed_10m", 0)
        return code in adverse_codes or wind > 50
    
    def _assess_risks(self, code: int, current: dict) -> list[str]:
        """Assess weather-related risks for city operations."""
        risks = []
        wind = current.get("wind_speed_10m", 0)
        precip = current.get("precipitation", 0)
        temp = current.get("temperature_2m", 20)
        
        if code in {65, 82, 95, 96, 99}:
            risks.append("heavy_precipitation")
        if wind > 60:
            risks.append("high_wind")
        elif wind > 40:
            risks.append("moderate_wind")
        if temp < 0:
            risks.append("freezing")
        if temp > 35:
            risks.append("extreme_heat")
        if code in {45, 48}:
            risks.append("low_visibility")
        if code in {71, 73, 75}:
            risks.append("snow_accumulation")
        if code in {61, 63, 65, 80, 81, 82}:
            risks.append("flooding_risk")
        
        return risks
    
    def _default(self) -> dict[str, Any]:
        """Return default weather data when fetch fails."""
        return {
            "temperature_c": 20,
            "humidity_pct": 50,
            "precipitation_mm": 0,
            "wind_speed_kmh": 0,
            "weather_code": 0,
            "condition": "unknown",
            "is_adverse": False,
            "risk_factors": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "default",
        }


weather_provider = WeatherProvider()
