from datetime import UTC, datetime


def validate_date(text):
    value = text.strip()
    if value == "":
        return "Departure time is required."
    try:
        datetime.strptime(value, "%d/%m/%Y").replace(tzinfo=UTC)
    except ValueError:
        return "Use DD/MM/YYYY , e.g. 01/01/2026"
    return True
