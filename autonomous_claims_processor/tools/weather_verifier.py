"""
Weather Verification Tool
=========================
Integration with NOAA, Tomorrow.io, and Weather Underground APIs
for weather data verification.
"""
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import hashlib

from ..core.settings import settings


class WeatherVerifier:
    """
    Verify weather-related claims using multiple weather data sources.
    """
    
    def __init__(self):
        self.logger = logger.bind(module="weather_verifier")
        
        # API configurations
        self.tomorrow_io_key = settings.tomorrow_io_api_key
        self.noaa_api_key = settings.noaa_api_key
        self.weather_underground_key = settings.weather_underground_api_key
        
        # Rate limiting
        self.request_cache: Dict[str, Dict] = {}
        
    def verify_weather(
        self,
        location: str,
        date_of_loss: datetime,
        reported_cause: str,
        coordinates: tuple = None
    ) -> Dict[str, Any]:
        """
        Verify weather conditions for a claim.
        
        Args:
            location: Text description of loss location
            date_of_loss: Date when loss occurred
            reported_cause: Reported weather cause (hail, wind, flood, etc.)
            coordinates: Optional (lat, lng) tuple for precise lookup
            
        Returns:
            Weather verification results
        """
        result = {
            "verification_id": self._generate_id(location, date_of_loss),
            "loss_location": location,
            "loss_date": date_of_loss.isoformat(),
            "reported_cause": reported_cause,
            "weather_data": {
                "sources_queried": [],
                "temperature_f": None,
                "wind_speed_mph": None,
                "wind_gust_mph": None,
                "precipitation_inches": None,
                "hail_recorded": False,
                "hail_size_inches": None,
                "severe_weather_alert_active": False,
                "alert_type": None,
                "lightning_strikes_nearby": False,
                "flood_advisory": False,
                "data_confidence": "LOW"
            },
            "verdict": "INCONCLUSIVE",
            "verdict_detail": "",
            "fraud_signal_to_fraud_agent": False,
            "fraud_signal_reason": None,
            "weather_data_citations": []
        }
        
        try:
            # Determine which APIs to query based on reported cause
            sources_to_query = self._determine_sources(reported_cause, coordinates)
            
            # Query each source
            for source in sources_to_query:
                try:
                    if source == "tomorrow_io" and coordinates:
                        source_data = self._query_tomorrow_io(coordinates, date_of_loss)
                        if source_data:
                            result["weather_data"]["sources_queried"].append("Tomorrow.io")
                            self._merge_weather_data(result["weather_data"], source_data)
                            result["weather_data_citations"].append({
                                "source": "Tomorrow.io",
                                "query_time": datetime.utcnow().isoformat()
                            })
                    
                    elif source == "noaa" and coordinates:
                        source_data = self._query_noaa(coordinates, date_of_loss)
                        if source_data:
                            result["weather_data"]["sources_queried"].append("NOAA")
                            self._merge_weather_data(result["weather_data"], source_data)
                            result["weather_data_citations"].append({
                                "source": "NOAA",
                                "query_time": datetime.utcnow().isoformat()
                            })
                    
                    elif source == "weather_underground" and coordinates:
                        source_data = self._query_weather_underground(coordinates, date_of_loss)
                        if source_data:
                            result["weather_data"]["sources_queried"].append("Weather Underground")
                            self._merge_weather_data(result["weather_data"], source_data)
                            result["weather_data_citations"].append({
                                "source": "Weather Underground",
                                "query_time": datetime.utcnow().isoformat()
                            })
                            
                except Exception as e:
                    self.logger.warning(f"Error querying {source}: {str(e)}")
            
            # Determine data confidence based on sources queried
            num_sources = len(result["weather_data"]["sources_queried"])
            if num_sources >= 2:
                result["weather_data"]["data_confidence"] = "HIGH"
            elif num_sources == 1:
                result["weather_data"]["data_confidence"] = "MEDIUM"
            
            # Generate verdict based on reported cause vs actual weather
            result["verdict"], result["verdict_detail"] = self._generate_verdict(
                reported_cause,
                result["weather_data"]
            )
            
            # Check for fraud signals
            if result["verdict"] == "INCONSISTENT":
                result["fraud_signal_to_fraud_agent"] = True
                result["fraud_signal_reason"] = f"Weather data does not support reported cause: {reported_cause}"
            
            self.logger.info(
                f"Weather verification complete",
                verdict=result["verdict"],
                confidence=result["weather_data"]["data_confidence"]
            )
            
        except Exception as e:
            self.logger.error(f"Weather verification error: {str(e)}")
            result["verdict"] = "INCONCLUSIVE"
            result["verdict_detail"] = f"Error during verification: {str(e)}"
        
        return result
    
    def _determine_sources(
        self,
        reported_cause: str,
        coordinates: tuple = None
    ) -> List[str]:
        """Determine which weather sources to query based on cause."""
        sources = []
        cause_lower = reported_cause.lower()
        
        # Always try Tomorrow.io if available (most reliable)
        if self.tomorrow_io_key:
            sources.append("tomorrow_io")
        
        # NOAA best for: hail, tornado, official storm data
        if any(term in cause_lower for term in ["hail", "tornado", "storm", "thunder"]):
            if self.noaa_api_key or True:  # NOAA basic endpoints don't need key
                sources.append("noaa")
        
        # Weather Underground good for: hyperlocal precipitation
        if any(term in cause_lower for term in ["flood", "rain", "water"]):
            if self.weather_underground_key:
                sources.append("weather_underground")
        
        return sources
    
    def _query_tomorrow_io(
        self,
        coordinates: tuple,
        date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Query Tomorrow.io API for historical weather."""
        if not self.tomorrow_io_key:
            return None
        
        lat, lng = coordinates
        cache_key = f"tomorrow_{lat}_{lng}_{date.strftime('%Y-%m-%d')}"
        
        # Check cache
        if cache_key in self.request_cache:
            return self.request_cache[cache_key]
        
        try:
            # Tomorrow.io historical weather endpoint
            url = "https://api.tomorrow.io/v4/weather/replay"
            params = {
                "lat": lat,
                "lon": lng,
                "start_time": date.strftime("%Y-%m-%dT00:00:00Z"),
                "end_time": (date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
                "timesteps": ["1h"],
                "apikey": self.tomorrow_io_key
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            result = self._parse_tomorrow_io_data(data)
            self.request_cache[cache_key] = result
            return result
            
        except Exception as e:
            self.logger.error(f"Tomorrow.io API error: {str(e)}")
            return None
    
    def _parse_tomorrow_io_data(self, data: Dict) -> Dict[str, Any]:
        """Parse Tomorrow.io API response."""
        result = {}
        
        try:
            timelines = data.get("data", {}).get("timelines", [])
            if not timelines:
                return result
            
            hourly = timelines[0].get("intervals", [])
            if not hourly:
                return result
            
            # Find peak conditions
            max_wind = 0
            max_gust = 0
            total_precip = 0
            max_hail = 0
            
            for interval in hourly:
                values = interval.get("values", {})
                
                wind = values.get("windSpeed", 0) or 0
                gust = values.get("windGust", 0) or 0
                precip = values.get("precipitationIntensity", 0) or 0
                hail = values.get("hailIntensity", 0) or 0
                
                max_wind = max(max_wind, wind)
                max_gust = max(max_gust, gust)
                total_precip += precip or 0
                max_hail = max(max_hail, hail)
                
                # Temperature at time of loss (use first interval as approximation)
                if "temperature" not in result:
                    temp_f = values.get("temperature", 0)
                    if temp_f is not None:
                        result["temperature_f"] = (temp_f * 9/5) + 32  # C to F
            
            # Convert units
            result["wind_speed_mph"] = max_wind * 2.237 if max_wind else None  # m/s to mph
            result["wind_gust_mph"] = max_gust * 2.237 if max_gust else None
            result["precipitation_inches"] = total_precip * 0.03937 if total_precip else None  # mm/hr to inches
            
            # Hail detection
            if max_hail > 0:
                result["hail_recorded"] = True
                # Estimate hail size from intensity (rough approximation)
                result["hail_size_inches"] = min(max_hail * 10, 3.0)  # Cap at 3 inches
            
        except Exception as e:
            self.logger.error(f"Error parsing Tomorrow.io data: {str(e)}")
        
        return result
    
    def _query_noaa(
        self,
        coordinates: tuple,
        date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Query NOAA APIs for historical weather and storm events."""
        lat, lng = coordinates
        cache_key = f"noaa_{lat}_{lng}_{date.strftime('%Y-%m-%d')}"
        
        if cache_key in self.request_cache:
            return self.request_cache[cache_key]
        
        result = {}
        
        try:
            # Query NOAA Storm Events API for severe weather
            storm_url = "https://www.ncdc.noaa.gov/stormevents/api/event"
            params = {
                "beginDate": date.strftime("%Y%m%d"),
                "endDate": (date + timedelta(days=1)).strftime("%Y%m%d"),
                "dataType": "StormEvents",
                "outputType": "JSON"
            }
            
            # Note: NOAA Storm Events API requires specific formatting
            # This is a simplified version - production would need proper endpoint
            try:
                response = requests.get(storm_url, params=params, timeout=15)
                if response.status_code == 200:
                    storm_data = response.json()
                    result.update(self._parse_noaa_storm_data(storm_data, lat, lng))
            except:
                pass  # NOAA API can be unreliable
            
            self.request_cache[cache_key] = result
            return result
            
        except Exception as e:
            self.logger.error(f"Noaa API error: {str(e)}")
            return None
    
    def _parse_noaa_storm_data(
        self,
        data: Any,
        lat: float,
        lng: float
    ) -> Dict[str, Any]:
        """Parse NOAA storm events data."""
        result = {
            "severe_weather_alert_active": False,
            "lightning_strikes_nearby": False
        }
        
        try:
            if isinstance(data, list):
                for event in data:
                    # Check for hail
                    if event.get("eventType", "").lower() == "hail":
                        result["hail_recorded"] = True
                        hail_size = event.get("hailSize", "")
                        if hail_size:
                            try:
                                result["hail_size_inches"] = float(hail_size.replace('"', ''))
                            except:
                                pass
                    
                    # Check for tornado
                    if event.get("eventType", "").lower() == "tornado":
                        result["severe_weather_alert_active"] = True
                        result["alert_type"] = "Tornado"
                    
                    # Check for thunderstorm wind
                    if "thunderstorm" in event.get("eventType", "").lower():
                        result["severe_weather_alert_active"] = True
                        result["alert_type"] = "Thunderstorm"
                        
        except Exception as e:
            self.logger.error(f"Error parsing NOAA storm data: {str(e)}")
        
        return result
    
    def _query_weather_underground(
        self,
        coordinates: tuple,
        date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Query Weather Underground for historical data."""
        if not self.weather_underground_key:
            return None
        
        lat, lng = coordinates
        cache_key = f"wu_{lat}_{lng}_{date.strftime('%Y-%m-%d')}"
        
        if cache_key in self.request_cache:
            return self.request_cache[cache_key]
        
        try:
            # Weather Underground historical API
            url = f"https://api.weather.com/v2/pws/history/hourly"
            params = {
                "stationId": "AUTO",  # Auto-select nearest station
                "format": "json",
                "units": "e",  # Imperial units
                "date": date.strftime("%Y%m%d"),
                "apiKey": self.weather_underground_key
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            result = self._parse_wu_data(data)
            self.request_cache[cache_key] = result
            return result
            
        except Exception as e:
            self.logger.error(f"Weather Underground API error: {str(e)}")
            return None
    
    def _parse_wu_data(self, data: Dict) -> Dict[str, Any]:
        """Parse Weather Underground API response."""
        result = {}
        
        try:
            observations = data.get("observations", [])
            if not observations:
                return result
            
            # Find max values
            for obs in observations:
                if obs.get("windGust", 0):
                    if result.get("wind_gust_mph") is None or obs["windGust"] > result["wind_gust_mph"]:
                        result["wind_gust_mph"] = obs["windGust"]
                
                if obs.get("precipTotal", 0):
                    result["precipitation_inches"] = result.get("precipitation_inches", 0) + obs["precipTotal"]
                
                if obs.get("temperature", 0):
                    result["temperature_f"] = obs["temperature"]
                    
        except Exception as e:
            self.logger.error(f"Error parsing WU data: {str(e)}")
        
        return result
    
    def _merge_weather_data(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any]
    ):
        """Merge weather data from multiple sources."""
        for key, value in source.items():
            if key == "sources_queried":
                continue
            if value is not None:
                # Prefer non-None values
                if target.get(key) is None:
                    target[key] = value
                elif key in ["wind_gust_mph", "wind_speed_mph"]:
                    # Take max for wind values
                    target[key] = max(target[key], value)
                elif key == "precipitation_inches":
                    # Sum precipitation
                    target[key] = max(target[key], value)
    
    def _generate_verdict(
        self,
        reported_cause: str,
        weather_data: Dict[str, Any]
    ) -> tuple:
        """Generate verification verdict."""
        cause_lower = reported_cause.lower()
        
        # Hail verification
        if "hail" in cause_lower:
            if weather_data.get("hail_recorded"):
                hail_size = weather_data.get("hail_size_inches", 0)
                if hail_size and hail_size >= 0.75:
                    return "CONFIRMED", f"Hail of {hail_size}\" recorded at location"
                else:
                    return "PARTIALLY_CONFIRMED", "Hail recorded but size may be insufficient for reported damage"
            else:
                return "INCONSISTENT", "No hail recorded at location on date of loss"
        
        # Wind verification
        if any(term in cause_lower for term in ["wind", "gust", "storm"]):
            wind_gust = weather_data.get("wind_gust_mph", 0) or 0
            if wind_gust >= 58:
                return "CONFIRMED", f"Wind gusts of {wind_gust} mph recorded - sufficient for structural damage"
            elif wind_gust >= 40:
                return "PARTIALLY_CONFIRMED", f"Wind gusts of {wind_gust} mph - may cause minor damage"
            else:
                return "INCONSISTENT", f"Wind speeds too low ({wind_gust} mph) for reported damage"
        
        # Flood/water verification
        if any(term in cause_lower for term in ["flood", "rain", "water"]):
            precip = weather_data.get("precipitation_inches", 0) or 0
            if precip >= 2.0:
                return "CONFIRMED", f"Significant precipitation ({precip:.2f}\") recorded"
            elif precip >= 0.5:
                return "PARTIALLY_CONFIRMED", f"Moderate precipitation ({precip:.2f}\") recorded"
            else:
                return "INCONSISTENT", f"Minimal precipitation ({precip:.2f}\") recorded"
        
        # Lightning verification
        if "lightning" in cause_lower:
            if weather_data.get("lightning_strikes_nearby") or weather_data.get("severe_weather_alert_active"):
                return "CONFIRMED", "Thunderstorm activity recorded in area"
            else:
                return "INCONCLUSIVE", "Unable to verify lightning strike specifically"
        
        # Default - not a weather-related claim
        return "NOT_APPLICABLE", "Claim does not appear to be weather-related"
    
    def _generate_id(self, location: str, date: datetime) -> str:
        """Generate unique verification ID."""
        data = f"{location}_{date.isoformat()}_{datetime.utcnow().isoformat()}"
        return "WX-" + hashlib.md5(data.encode()).hexdigest()[:12].upper()


# Singleton instance
_weather_verifier = None

def get_weather_verifier() -> WeatherVerifier:
    """Get or create weather verifier singleton."""
    global _weather_verifier
    if _weather_verifier is None:
        _weather_verifier = WeatherVerifier()
    return _weather_verifier
