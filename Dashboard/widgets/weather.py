"""Weather from Open-Meteo (free, no key): place lookup by city name, then current conditions + forecast."""

import time
import urllib.parse

from . import SourceError, fetch_json

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search?{q}"
FORECAST = "https://api.open-meteo.com/v1/forecast?{q}"
CACHE_SECONDS = 15 * 60

# WMO weather codes -> (label, icon name used by the UI)
CODES = {
    0: ("Clear", "sun"), 1: ("Mostly clear", "sun"), 2: ("Partly cloudy", "cloudsun"), 3: ("Overcast", "cloud"),
    45: ("Fog", "fog"), 48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"), 53: ("Drizzle", "drizzle"), 55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"), 57: ("Freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"), 77: ("Snow grains", "snow"),
    80: ("Light showers", "rain"), 81: ("Showers", "rain"), 82: ("Heavy showers", "rain"),
    85: ("Snow showers", "snow"), 86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "storm"), 96: ("Thunderstorm with hail", "storm"), 99: ("Thunderstorm with hail", "storm"),
}

_cache = {}


def describe_code(code):
    return CODES.get(int(code or 0), ("Unknown", "cloud"))


def find_place(name):
    data = fetch_json(GEOCODE.format(q=urllib.parse.urlencode({"name": name, "count": 5, "language": "en"})),
                      what="Open-Meteo place search")
    hits = data.get("results") or []
    if not hits:
        raise SourceError(f"Couldn't find a place called {name!r}.")
    h = hits[0]
    label = ", ".join(x for x in (h.get("name"), h.get("admin1"), h.get("country_code")) if x)
    return {"lat": h["latitude"], "lon": h["longitude"], "label": label, "timezone": h.get("timezone", "auto")}


def forecast(lat, lon, units="celsius", force=False):
    key = (round(lat, 3), round(lon, 3), units)
    hit = _cache.get(key)
    if hit and not force and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
        "temperature_unit": "fahrenheit" if units == "fahrenheit" else "celsius",
        "wind_speed_unit": "mph" if units == "fahrenheit" else "kmh",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day",
        "hourly": "temperature_2m,precipitation_probability,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
    })
    d = fetch_json(FORECAST.format(q=q), what="Open-Meteo forecast")
    cur, hourly, daily = d.get("current", {}), d.get("hourly", {}), d.get("daily", {})
    now = cur.get("time", "")
    times = hourly.get("time", [])
    start = next((i for i, t in enumerate(times) if t >= now[:13]), 0)
    hours = [{"time": times[i], "temp": hourly["temperature_2m"][i],
              "rain": hourly["precipitation_probability"][i], "code": hourly["weather_code"][i],
              "icon": describe_code(hourly["weather_code"][i])[1]}
             for i in range(start, min(start + 24, len(times)))]
    days = [{"date": daily["time"][i], "max": daily["temperature_2m_max"][i], "min": daily["temperature_2m_min"][i],
             "rain": daily["precipitation_probability_max"][i], "code": daily["weather_code"][i],
             "label": describe_code(daily["weather_code"][i])[0], "icon": describe_code(daily["weather_code"][i])[1],
             "sunrise": daily["sunrise"][i], "sunset": daily["sunset"][i]}
            for i in range(len(daily.get("time", [])))]
    label, icon = describe_code(cur.get("weather_code"))
    out = {"temp": cur.get("temperature_2m"), "feels": cur.get("apparent_temperature"),
           "humidity": cur.get("relative_humidity_2m"), "wind": cur.get("wind_speed_10m"),
           "label": label, "icon": icon, "is_day": cur.get("is_day", 1), "time": now,
           "unit": "°F" if units == "fahrenheit" else "°C", "wind_unit": "mph" if units == "fahrenheit" else "km/h",
           "hours": hours, "days": days, "fetched": time.time()}
    _cache[key] = (time.time(), out)
    return out


def spoken(w, place):
    """One or two sentences to say out loud."""
    today = w["days"][0] if w["days"] else None
    text = f"In {place.split(',')[0]} it's {round(w['temp'])} degrees and {w['label'].lower()}"
    if w.get("feels") is not None and abs(w["feels"] - w["temp"]) >= 2:
        text += f", feels like {round(w['feels'])}"
    text += "."
    if today:
        text += f" Today's high is {round(today['max'])} and the low {round(today['min'])}"
        text += f", with a {today['rain']} percent chance of rain." if today.get("rain") else "."
    return text


def summary_for_ai(w, place):
    days = "; ".join(f"{d['date']}: {d['label']}, {round(d['min'])}-{round(d['max'])}{w['unit']}, rain {d['rain']}%"
                     for d in w["days"][:4])
    return f"{place}: now {w['temp']}{w['unit']} {w['label']}, humidity {w['humidity']}%. Next days: {days}"
