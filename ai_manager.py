"""
ai_manager.py
API interaction ONLY. Zero domain logic (no proceed/delay/reroute decisions here).
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import requests

log = logging.getLogger("ai_manager")

# --------------------------------------------------------------------------
# Configuration & Constants (Extracted Hardcoded Values)2
# --------------------------------------------------------------------------
MAX_RETRIES = 3
HTTP_TIMEOUT = 20
MAX_PLACES_LIMIT = 4
GDELT_MAX_RECORDS = 8
GDELT_TIMESPAN = "3d"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# --------------------------------------------------------------------------
# Fail-Fast Validation
# --------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("CRITICAL ERROR: 'GEMINI_API_KEY' is not set. The application cannot start.")

# --------------------------------------------------------------------------
# Connection Pooling
# --------------------------------------------------------------------------
http_session = requests.Session()

# --------------------------------------------------------------------------
# Schema & Prompts (Native Structured Outputs via Gemini API)
# --------------------------------------------------------------------------
ALLOWED_RISK_TYPES = [
    "weather", "severe_crosswinds", "port_congestion", "labor_shortage",
    "piracy_threat", "severe_civil_unrest", "geopolitical",
    "infrastructure_disruption"
]
ALLOWED_SEVERITY = ["Low", "Medium", "High"]
ALLOWED_IMPACT = ["Delay", "Cost Increase", "Cargo Damage", "Cargo Destruction", "None"]

SYSTEM_PROMPT = """You are a logistics risk analyst for shipments through Singapore.
You only analyse and structure information. You NEVER decide whether to proceed,
delay, reroute or insure: another system does that.
Rules:
- Use ONLY the shipment data and external data provided. Do not invent facts.
- If data is missing, old, or contradictory, lower confidence_score and set
  conflicting_sources to true when sources disagree."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "risk_factors": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {"type": "STRING", "enum": ALLOWED_RISK_TYPES},
                    "severity": {"type": "STRING", "enum": ALLOWED_SEVERITY},
                    "detail": {"type": "STRING"}
                },
                "required": ["type", "severity", "detail"]
            }
        },
        "primary_risk_factor": {"type": "STRING", "enum": ALLOWED_RISK_TYPES},
        "affected_location": {"type": "STRING"},
        "expected_impact": {"type": "STRING", "enum": ALLOWED_IMPACT},
        "confidence_score": {"type": "NUMBER"},
        "sources": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "conflicting_sources": {"type": "BOOLEAN"},
        "extreme_event": {"type": "STRING"},
        "insights": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "alternative_route": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING"},
                "distance_km": {"type": "NUMBER"}
            }
        }
    },
    "required": [
        "risk_factors", "primary_risk_factor", "affected_location", 
        "expected_impact", "confidence_score", "sources", 
        "conflicting_sources", "extreme_event", "insights"
    ]
}

# --------------------------------------------------------------------------
# External data gathering

# Changes Made: 3/10/2026 3AM 
# Replaced individual requests.get() calls with a shared http_session.get().
# Instead of creating a new connection for each request, we now reuse a single session, which improves performance and reduces overhead.
# --------------------------------------------------------------------------
def _geocode(place: str) -> Optional[Tuple[float, float]]:
    r = http_session.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": place, "count": 1}, timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    results = r.json().get("results")
    if not results:
        return None
    return results[0]["latitude"], results[0]["longitude"]


def _weather(place: str) -> Dict[str, Any]:
    coords = _geocode(place)
    if coords is None:
        return {"place": place, "error": "location not found"}
    lat, lon = coords
    r = http_session.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
            "daily": "precipitation_sum,wind_gusts_10m_max,weather_code",
        },
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    return {"place": place, "source": "open-meteo.com", "daily": r.json().get("daily", {})}


def _news(places: List[str]) -> List[Dict[str, Any]]:
    place_q = " OR ".join(f'"{p}"' for p in places if p)
    topic_q = 'piracy OR "armed robbery" OR "port congestion" OR strike OR protest OR unrest'
    r = http_session.get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={"query": f"({place_q}) ({topic_q})", "mode": "ArtList",
                "maxrecords": GDELT_MAX_RECORDS, "format": "json", "timespan": GDELT_TIMESPAN},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    articles = r.json().get("articles", [])
    return [{"title": a.get("title"), "url": a.get("url"), "seen": a.get("seendate")} for a in articles]


def fetch_external_data(record: Dict[str, Any]) -> Dict[str, Any]:
    places = [record.get("origin"), record.get("destination")] + list(record.get("waypoints", []))
    places = [p for p in places if p] # Filter empty values
    
    data: Dict[str, Any] = {"weather": [], "news": [], "errors": []}

    for place in places[:MAX_PLACES_LIMIT]:
        try:
            data["weather"].append(_weather(place))
        except Exception as exc:
            log.warning("weather feed failed for %s: %s", place, exc)
            data["errors"].append(f"weather:{place}")

    try:
        data["news"] = _news(places[:MAX_PLACES_LIMIT])
    except Exception as exc:
        log.warning("news feed failed: %s", exc)
        data["errors"].append("news")

    return data

#Replaced hardcoded numbers with top-level constants (MAX_PLACES_LIMIT) and added a filter for empty location strings. 

# --------------------------------------------------------------------------
# Prompt -> API -> Validate
# --------------------------------------------------------------------------
def build_prompt(record: Dict[str, Any], external: Dict[str, Any]) -> str:
    shipment = {k: record[k] for k in (
        "origin", "destination", "waypoints", "transport_mode", "transport_type",
        "goods", "departure_date", "expected_arrival", "baseline_distance_km",
    ) if k in record}
    return (
        "SHIPMENT:\n" + json.dumps(shipment, default=str) +
        "\n\nEXTERNAL DATA:\n" + json.dumps(external, default=str)
    )


def _call_gemini(prompt: str) -> Dict[str, Any]:
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2, 
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA
        },
    }
    r = http_session.post(
        GEMINI_URL,
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json=body, timeout=HTTP_TIMEOUT * 2,
    )
    r.raise_for_status()
    
    # Due to responseSchema, Gemini is strictly constrained to valid JSON matching our exact shape.
    raw_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_text)

#What changed: Added Google's native responseSchema configuration to the API request, basically telling Gemini to return a JSON object that matches our expected structure. 
#This allows us to skip the manual parsing and validation step, as Gemini will enforce the schema on its end.
#parse_json() & validate _schema() functions have been removed since they are no longer needed. 
#The Gemini API will now return a JSON object that matches our expected structure, so we can directly use the response without additional parsing or validation.

# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def enrich_record(input_record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    input_record (from IO_MANAGER)  ->  AI-enriched record (for LOGIC_MANAGER)
    Returns None if the AI could not produce a valid answer. Never crashes the system.
    """
    external = fetch_external_data(input_record)
    prompt = build_prompt(input_record, external)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ai_part = _call_gemini(prompt)
            break
        except (ValueError, json.JSONDecodeError, KeyError) as exc:
            log.warning("malformed AI reply (attempt %d): %s", attempt, exc)
        except requests.RequestException as exc:
            log.warning("AI API failure (attempt %d): %s", attempt, exc)
            time.sleep(2 ** attempt)
    else:
        log.error("AI enrichment failed after %d attempts", MAX_RETRIES)
        return None

    enriched = dict(input_record)
    enriched.update(ai_part)
    enriched["external_data_fetched_at"] = datetime.now()
    enriched["external_data_errors"] = external["errors"]
    return enriched

# What changed: Simplified the execution flow and added Python type hints.

# Simplified explanation: Because the AI response is already validated by Google on arrival, 
# this main coordinator function now directly attaches the clean AI results to our shipment record without needing to run extra parsing checks first.