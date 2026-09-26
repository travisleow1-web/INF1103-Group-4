import json
import os
from datetime import UTC, datetime

# Load the port reference once at import time. The path is relative, so the
# program must be run from the repo root.
with open("ports_reference_4.json") as f:
    PORTS = json.load(f)["ports"]

# Autocomplete entries shown to the user, e.g. "<code> - <name>, <country>".
PORT_CHOICES = [f"{p['code']} - {p['name']}, {p['country']}" for p in PORTS]
# Lookup table from port code to its full reference record.
PORTS_BY_CODE = {p["code"]: p for p in PORTS}


def port_coordinates(code):
    """Return the (lat, lon) of the port with this code.

    Raises KeyError if the code isn't in the reference, so only pass codes
    that have already been validated.
    """
    port = PORTS_BY_CODE[code]
    return port["lat"], port["lon"]


def validate_date(text):
    """Check that text is a DD/MM/YYYY date, for use as a questionary validator.

    Returns True when valid, otherwise an error message string that
    questionary shows to the user before asking again.
    """
    value = text.strip()
    if value == "":
        return "Departure time is required."
    # strptime raises ValueError for wrong formats and impossible dates
    # such as 31/02/2026.
    try:
        datetime.strptime(value, "%d/%m/%Y").replace(tzinfo=UTC)
    except ValueError:
        return "Use DD/MM/YYYY , e.g. 01/01/2026"
    return True


def validate_port(answer):
    """Check that answer is exactly one of PORT_CHOICES, for use as a questionary validator.

    Returns True when valid, otherwise an error message string. Partially
    typed text is rejected, so the user has to pick an entry from the list.
    """
    if answer in PORT_CHOICES:
        return True
    return "Unknown port, pick one from the list"

def validate_csv_path(text):
    """Check that text is a path to an existing .csv file, for use as a questionary validator."""
    value = text.strip()
    if value == "":
        return "File path is required."
    if not value.lower().endswith(".csv"):
        return "File must be a .csv file."
    if not os.path.isfile(value):
        return "File not found."
    return True