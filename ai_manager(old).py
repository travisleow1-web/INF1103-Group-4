"""
ai_manager.py
API interaction ONLY. Zero domain logic (no proceed/delay/reroute decisions here).

Free services used:
  - Google Gemini API (free tier via Google AI Studio, no credit card)
        key: https://aistudio.google.com/apikey  ->  set env var GEMINI_API_KEY
  - Open-Meteo  (weather forecast + geocoding, free, no API key)
  - GDELT DOC 2.0 (global news search, free, no API key)

Install:  pip install requests
"""

import os
import json
import time
import logging
import requests

log = logging.getLogger("ai_manager2")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")  # any free-tier model name
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_RETRIES = 3
HTTP_TIMEOUT = 20

ALLOWED_RISK_TYPES = {
    "weather", "severe_crosswinds", "port_congestion", "labor_shortage",
    "piracy_threat", "severe_civil_unrest", "geopolitical",
    "infrastructure_disruption",
}
ALLOWED_SEVERITY = {"Low", "Medium", "High"}
ALLOWED_IMPACT = {"Delay", "Cost Increase", "Cargo Damage", "Cargo Destruction", "None"}

SYSTEM_PROMPT = """You are a logistics risk analyst for shipments through Singapore.
You only analyse and structure information. You NEVER decide whether to proceed,
delay, reroute or insure: another system does that.
Rules:
- Use ONLY the shipment data and external data provided. Do not invent facts.
- If data is missing, old, or contradictory, lower confidence_score and set
  conflicting_sources to true when sources disagree.
- Reply with a single JSON object and nothing else."""

OUTPUT_SCHEMA_HINT = {
    "risk_factors": [
        {"type": "one of: " + ", ".join(sorted(ALLOWED_RISK_TYPES)),
         "severity": "Low | Medium | High",
         "detail": "short reason"}
    ],
    "primary_risk_factor": "the single most important risk type",
    "affected_location": "place name where the primary risk applies",
    "expected_impact": "one of: " + ", ".join(sorted(ALLOWED_IMPACT)),
    "confidence_score": "number 0.0 to 1.0",
    "sources": ["urls or feed names used"],
    "conflicting_sources": "true or false",
    "extreme_event": "name of extreme event (e.g. Category 5 hurricane) or empty string",
    "insights": ["optional: multiple simultaneous risks, past route issues, missing info"],
    "alternative_route": {"name": "optional safer route", "distance_km": "number"},
}


# --------------------------------------------------------------------------
# External data gathering (Data Gathering & Analysis, step 4.1)
# --------------------------------------------------------------------------
def _geocode(place):
    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": place, "count": 1}, timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    results = r.json().get("results")
    if not results:
        return None
    return results[0]["latitude"], results[0]["longitude"]


def _weather(place):
    coords = _geocode(place)
    if coords is None:
        return {"place": place, "error": "location not found"}
    lat, lon = coords
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
            "daily": "precipitation_sum,wind_gusts_10m_max,weather_code",
        },
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    return {"place": place, "source": "open-meteo.com", "daily": r.json().get("daily", {})}


def _news(places):
    """One combined GDELT query (GDELT asks for roughly one request per 5 seconds)."""
    place_q = " OR ".join(f'"{p}"' for p in places if p)
    topic_q = 'piracy OR "armed robbery" OR "port congestion" OR strike OR protest OR unrest'
    r = requests.get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={"query": f"({place_q}) ({topic_q})", "mode": "ArtList",
                "maxrecords": 8, "format": "json", "timespan": "3d"},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    articles = r.json().get("articles", [])
    return [{"title": a.get("title"), "url": a.get("url"), "seen": a.get("seendate")}
            for a in articles]


def fetch_external_data(record):
    """Never raises. Any failed feed is recorded as an error string instead."""
    places = [record["origin"], record["destination"]] + list(record.get("waypoints", []))
    data = {"weather": [], "news": [], "errors": []}

    for place in places[:4]:  # cap calls to stay inside free limits
        try:
            data["weather"].append(_weather(place))
        except Exception as exc:
            log.warning("weather feed failed for %s: %s", place, exc)
            data["errors"].append(f"weather:{place}")

    try:
        data["news"] = _news(places[:4])
    except Exception as exc:
        log.warning("news feed failed: %s", exc)
        data["errors"].append("news")

    return data


# --------------------------------------------------------------------------
# Prompt -> API -> parse -> validate
# --------------------------------------------------------------------------
def build_prompt(record, external):
    shipment = {k: record[k] for k in (
        "origin", "destination", "waypoints", "transport_mode", "transport_type",
        "goods", "departure_date", "expected_arrival", "baseline_distance_km",
    ) if k in record}
    return (
        "SHIPMENT:\n" + json.dumps(shipment, default=str) +
        "\n\nEXTERNAL DATA:\n" + json.dumps(external, default=str) +
        "\n\nReturn JSON matching this shape:\n" + json.dumps(OUTPUT_SCHEMA_HINT)
    )


def _call_gemini(prompt):
    """Returns raw text from the model, or raises requests.RequestException."""
    api_key = os.getenv("GEMINI_API_KEY") #please fking get the API key and put here ffs
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set") #ffs no.2 need put API key 

    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    r = requests.post(
        GEMINI_URL.format(model=GEMINI_MODEL),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=body, timeout=HTTP_TIMEOUT * 2,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json(text):
    text = text.strip()
    if text.startswith("```"):  # strip markdown fences if the model added them
        text = text.strip("`")
        text = text[text.find("{"):]
    return json.loads(text)


def validate_schema(data):
    """Return a cleaned dict, or raise ValueError if the reply is unusable."""
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")

    factors = data.get("risk_factors")
    if not isinstance(factors, list) or not factors:
        raise ValueError("risk_factors missing or empty")

    clean_factors = []
    for f in factors:
        ftype = str(f.get("type", "")).strip().lower().replace(" ", "_")
        sev = str(f.get("severity", "")).strip().capitalize()
        if ftype not in ALLOWED_RISK_TYPES or sev not in ALLOWED_SEVERITY:
            raise ValueError(f"bad risk factor: {f}")
        clean_factors.append({"type": ftype, "severity": sev, "detail": f.get("detail", "")})

    conf = data.get("confidence_score")
    if not isinstance(conf, (int, float)) or not 0.0 <= conf <= 1.0:
        raise ValueError("confidence_score must be a number from 0 to 1")

    impact = str(data.get("expected_impact", "")).strip().title()
    if impact not in ALLOWED_IMPACT:
        raise ValueError(f"unknown expected_impact: {impact}")

    for key in ("primary_risk_factor", "affected_location"):
        if not data.get(key):
            raise ValueError(f"{key} missing")

    return {
        "risk_factors": clean_factors,
        "primary_risk_factor": str(data["primary_risk_factor"]).strip().lower().replace(" ", "_"),
        "affected_location": data["affected_location"],
        "expected_impact": impact,
        "confidence_score": float(conf),
        "sources": data.get("sources") or ["none provided"],
        "conflicting_sources": bool(data.get("conflicting_sources", False)),
        "extreme_event": data.get("extreme_event", "") or "",
        "insights": data.get("insights", []),
        "alternative_route": data.get("alternative_route") or None,
    }


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def enrich_record(input_record):
    """
    input_record (from IO_MANAGER)  ->  AI-enriched record (for LOGIC_MANAGER)
    Returns None if the AI could not produce a valid answer. Never crashes the system.
    """
    from datetime import datetime

    external = fetch_external_data(input_record)
    prompt = build_prompt(input_record, external)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = _call_gemini(prompt)
            ai_part = validate_schema(_parse_json(raw))
            break
        except (ValueError, json.JSONDecodeError, KeyError) as exc:
            log.warning("malformed AI reply (attempt %d): %s", attempt, exc)
        except requests.RequestException as exc:
            log.warning("AI API failure (attempt %d): %s", attempt, exc)
            time.sleep(2 ** attempt)
        except RuntimeError as exc:  # missing API key: retrying will not help
            log.error("%s", exc)
            return None
    else:
        log.error("AI enrichment failed after %d attempts", MAX_RETRIES)
        return None

    # Shipment facts come from the USER, never from the AI
    enriched = dict(input_record)
    enriched.update(ai_part)
    enriched["external_data_fetched_at"] = datetime.now()
    enriched["external_data_errors"] = external["errors"]
    return enriched
