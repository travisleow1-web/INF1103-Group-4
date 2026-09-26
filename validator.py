import json
from datetime import UTC, datetime

with open("ports_reference_4.json") as f:
    PORTS = json.load(f)["ports"]

PORT_CHOICES = [f"{p['code']} - {p['name']}, {p['country']}" for p in PORTS]
PORTS_BY_CODE = {p["code"]: p for p in PORTS}


def port_coordinates(code):
    port = PORTS_BY_CODE[code]
    return port["lat"], port["lon"]


def validate_date(text):
    value = text.strip()
    if value == "":
        return "Departure time is required."
    try:
        datetime.strptime(value, "%d/%m/%Y").replace(tzinfo=UTC)
    except ValueError:
        return "Use DD/MM/YYYY , e.g. 01/01/2026"
    return True


def validate_port(answer):
    if answer in PORT_CHOICES:
        return True
    return "Unknown port, pick one from the list"
