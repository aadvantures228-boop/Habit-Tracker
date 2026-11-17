"""City geocoding via OpenWeatherMap; IANA timezone for daylight-saving support."""
import logging
import requests
from config.env import WEATHER_TOKEN

logger = logging.getLogger(__name__)


def get_timezone_info_by_city(city_name):
    """Return (UTC offset seconds, IANA zone name or None), or None for unknown city."""
    if not WEATHER_TOKEN or not city_name.strip():
        return None
    try:
        response = requests.get('https://api.openweathermap.org/data/2.5/weather',
                                params={'q': city_name.strip(), 'appid': WEATHER_TOKEN}, timeout=10)
        if response.status_code != 200:
            logger.warning('OpenWeatherMap rejected city request status=%s', response.status_code)
            return None
        result = response.json()
        offset = int(result['timezone'])
        if not -43200 <= offset <= 50400:
            return None
        zone_name = None
        coord = result.get('coord', {})
        if 'lat' in coord and 'lon' in coord:
            try:
                from timezonefinder import TimezoneFinder
                zone_name = TimezoneFinder(in_memory=True).timezone_at(lat=coord['lat'], lng=coord['lon'])
            except ImportError:
                logger.warning('timezonefinder missing: daylight-saving changes not automatic')
            except Exception as exc:
                logger.warning('Timezone lookup failed (%s)', type(exc).__name__)
        return offset, zone_name
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        # Some requests exceptions contain the full URL, including the API key.
        logger.warning('Could not detect timezone for city (%s)', type(exc).__name__)
        return None


def get_timezone_by_city(city_name):
    result = get_timezone_info_by_city(city_name)
    return result[0] if result else None
