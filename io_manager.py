import os

import pandas as pd
import questionary

import validator


def ask_port(message, validate=validator.validate_port):
    """Prompt for a port with autocomplete over the port reference list.

    Typing any part of the entry (code, name or country) narrows the
    suggestions. Answers that fail validate are rejected and the prompt
    repeats. The chosen entry looks like "<code> - <name>, <country>", so
    only the code before " - " is returned, upper-cased.
    """
    answer = questionary.autocomplete(
        message,
        choices=validator.PORT_CHOICES,
        match_middle=True,
        validate=validate,
    ).ask()
    return answer.split(" - ")[0].strip().upper()


def shipment_id():
    """Prompt for a shipment ID and return it as typed (not validated yet)."""
    answer = questionary.text("Shipment ID:").ask()
    return answer


def origin_port():
    """Prompt for the origin port and return its code."""
    return ask_port("Origin port:")


def destination_port(origin):
    """Prompt for the destination port and return its code.

    The origin port code is rejected so a shipment can't start and end at
    the same port.
    """
    return ask_port(
        "Destination port:",
        validate=lambda answer: validator.validate_destination_port(answer, origin),
    )


def departure_time():
    """Prompt for the departure date, re-asking until it is a valid DD/MM/YYYY.

    Returns the date as a string with surrounding whitespace removed.
    """
    answer = questionary.text(
        "Departure time (DD/MM/YYYY):", validate=validator.validate_date
    ).ask()
    return answer.strip()


def arrival_time():
    """Prompt for the arrival date, re-asking until it is a valid DD/MM/YYYY.

    Returns the date as a string with surrounding whitespace removed.
    """
    answer = questionary.text(
        "Arrival time (DD/MM/YYYY):", validate=validator.validate_date
    ).ask()
    return answer.strip()


def manual_shipments():
    """Collect one or more shipments from the user and return them as a DataFrame.

    Each loop asks for one shipment's fields and appends them to one list per
    column. Port latitude/longitude are looked up from the port reference, not
    asked for. After each shipment the user chooses whether to add another.
    The lists are then combined into a DataFrame with one row per shipment.
    """
    # One list per output column; index i across all lists is shipment i.
    ids = []
    origin_ports = []
    origin_lats = []
    origin_lons = []
    destination_ports = []
    destination_lats = []
    destination_lons = []
    departure_times = []
    arrival_times = []
    while True:
        ids.append(shipment_id())

        # Fill in the origin's coordinates from the chosen port code.
        origin = origin_port()
        origin_lat, origin_lon = validator.port_coordinates(origin)
        origin_ports.append(origin)
        origin_lats.append(origin_lat)
        origin_lons.append(origin_lon)

        # Same for the destination.
        destination = destination_port(origin)
        destination_lat, destination_lon = validator.port_coordinates(destination)
        destination_ports.append(destination)
        destination_lats.append(destination_lat)
        destination_lons.append(destination_lon)

        departure_times.append(departure_time())
        arrival_times.append(arrival_time())

        if questionary.confirm("Add another shipment?").ask():
            continue
        break

    # Explicit dtypes keep columns typed correctly even when the lists are empty.
    return pd.DataFrame(
        {
            "shipment_id": pd.Series(ids, dtype="str"),
            "origin_port": pd.Series(origin_ports, dtype="str"),
            "origin_lat": pd.Series(origin_lats, dtype="float"),
            "origin_lon": pd.Series(origin_lons, dtype="float"),
            "destination_port": pd.Series(destination_ports, dtype="str"),
            "destination_lat": pd.Series(destination_lats, dtype="float"),
            "destination_lon": pd.Series(destination_lons, dtype="float"),
            "departure_time": pd.Series(departure_times, dtype="str"),
            "arrival_time": pd.Series(arrival_times, dtype="str"),
        }
    )


def input_method():
    """Ask whether shipments are entered manually or loaded from a CSV file."""
    selection = questionary.select(
        "How do you want to add shipments?",
        choices=["Enter manually", "Upload a CSV file"],
    ).ask()
    if selection == "Upload a CSV file":
        return csv_shipments()
    return manual_shipments()


def csv_shipments():
    """Load shipments from a CSV file and return them as a DataFrame.

    The file needs the columns in CSV_COLUMNS; port lat/lon are looked up from
    the port reference like in manual entry. If the file can't be read or any
    row is invalid, the errors are shown and the user is asked for a path again.
    """
    while True:
        path = questionary.path("CSV file path:", validate=validator.validate_csv_path).ask()
        try:
            # Read everything as text and turn blank cells into "" so the
            # checks below don't have to deal with NaN.
            df = pd.read_csv(path.strip(), dtype=str, keep_default_na=False)
        except (
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
            UnicodeDecodeError,
        ) as e:
            print(f"Could not read file: {e}")
            continue
        print(df)

if __name__ == "__main__":
    print(input_method())

