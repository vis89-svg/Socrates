import json
import re
import time
from urllib.parse import quote

from django.conf import settings
from .feature_flags import FeatureFlags
from .observability import Observability


IMD_BASE_URL = "https://mausam.imd.gov.in/api/v1"
IMD_CITY_MAP = {
    'kerala': 'Kerala',
    'thiruvananthapuram': 'Thiruvananthapuram',
    'kochi': 'Kochi',
    'calicut': 'Calicut',
    'kozhikode': 'Kozhikode',
    'ernakulam': 'Ernakulam',
    'thrissur': 'Thrissur',
    'palakkad': 'Palakkad',
    'malappuram': 'Malappuram',
    'kannur': 'Kannur',
    'kasaragod': 'Kasaragod',
    'idukki': 'Idukki',
    'wayanad': 'Wayanad',
    'alappuzha': 'Alappuzha',
    'pathanamthitta': 'Pathanamthitta',
    'kolam': 'Kolam',
    'trivandrum': 'Thiruvananthapuram',
    'cochin': 'Kochi',
}


def _extract_location(query):
    q = query.lower().strip()
    for keyword, location in IMD_CITY_MAP.items():
        if keyword in q:
            return location
    match = re.search(r'weather\s+(?:in|at|for)\s+(\w+)', q)
    if match:
        return match.group(1).title()
    return None


def _fetch_imd_weather(location):
    if not FeatureFlags.is_enabled('ENABLE_WEATHER_IMD'):
        return None
    try:
        import urllib.request
        encoded = quote(location)
        url = f"{IMD_BASE_URL}/current?city={encoded}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return _parse_imd_response(data, location)
    except Exception:
        return None


def _parse_imd_response(data, location):
    if not data or not isinstance(data, dict):
        return None
    current = data.get('current') or data
    temp = current.get('temperature') or current.get('temp')
    humidity = current.get('humidity')
    wind = current.get('wind_speed') or current.get('wind')
    condition = current.get('condition') or current.get('weather') or current.get('description')
    alert = current.get('alert') or current.get('warning') or current.get('alerts')

    result = {'location': location}
    if temp is not None:
        result['temperature'] = f"{temp}°C"
    if humidity is not None:
        result['humidity'] = f"{humidity}%"
    if wind is not None:
        result['wind'] = f"{wind} km/h"
    if condition:
        result['condition'] = str(condition)
    if alert:
        result['alert'] = str(alert)
    return result


def _fetch_weather_from_search(query):
    from .search_service import search_service
    results, provider = search_service.search(query, max_results=5)
    if not results:
        return None
    return {
        'source': 'web_search',
        'provider': provider,
        'results': results[:3],
    }


class WeatherService:
    @staticmethod
    def get_weather(query):
        start = time.time()
        location = _extract_location(query)
        imd_result = None
        search_result = None

        if location:
            imd_result = _fetch_imd_weather(location)

        if imd_result is None:
            search_query = f"current weather {query}"
            search_result = _fetch_weather_from_search(search_query)

        elapsed = int((time.time() - start) * 1000)

        return {
            'imd_data': imd_result,
            'search_data': search_result,
            'location': location,
            'time_ms': elapsed,
        }

    @staticmethod
    def format_answer(weather_data, query):
        imd = weather_data.get('imd_data')
        search = weather_data.get('search_data')
        location = weather_data.get('location') or query

        if imd and imd.get('temperature'):
            lines = [f"**Current Weather ({location})**", ""]
            if imd.get('temperature'):
                lines.append(f"* Temperature: {imd['temperature']}")
            if imd.get('condition'):
                lines.append(f"* Conditions: {imd['condition']}")
            if imd.get('humidity'):
                lines.append(f"* Humidity: {imd['humidity']}")
            if imd.get('wind'):
                lines.append(f"* Wind: {imd['wind']}")
            if imd.get('alert'):
                lines.append("")
                lines.append(f"* ⚠ Alert: {imd['alert']}")
            lines.append("")
            lines.append(f"Source: IMD (India Meteorological Department)")
            if search and search.get('provider'):
                lines.append(f"Additional: {search['provider']}")
            return '\n'.join(lines)

        if search and search.get('results'):
            lines = [f"**Weather ({location})**", ""]
            for i, r in enumerate(search['results'][:3], 1):
                title = r.get('title', 'Untitled')
                snippet = r.get('snippet', '')[:300]
                lines.append(f"{i}. {title}")
                if snippet:
                    lines.append(f"   {snippet}")
            lines.append("")
            lines.append(f"Source: {search.get('provider', 'web search')}")
            return '\n'.join(lines)

        return f"I couldn't find current weather data for {location}. Please try again later."