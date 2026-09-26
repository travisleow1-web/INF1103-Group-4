import pandas as pd
import questionary

import validator


def ask_port(message):
    answer = questionary.autocomplete(
        message,
        choices=validator.PORT_CHOICES,
        match_middle=True,
        validate=validator.validate_port,
    ).ask()
    return answer.split(" - ")[0].strip().upper()


def shipment_id():
    answer = questionary.text("Shipment ID:").ask()
    return answer


def origin_port():
    return ask_port("Origin port:")


def destination_port():
    return ask_port("Destination port:")


def departure_time():
    answer = questionary.text(
        "Departure time (DD/MM/YYYY):", validate=validator.validate_date
    ).ask()
    return answer.strip()


def arrival_time():
    answer = questionary.text(
        "Arrival time (DD/MM/YYYY):", validate=validator.validate_date
    ).ask()
    return answer.strip()


def get_shipments():
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

        origin = origin_port()
        origin_lat, origin_lon = validator.port_coordinates(origin)
        origin_ports.append(origin)
        origin_lats.append(origin_lat)
        origin_lons.append(origin_lon)

        destination = destination_port()
        destination_lat, destination_lon = validator.port_coordinates(destination)
        destination_ports.append(destination)
        destination_lats.append(destination_lat)
        destination_lons.append(destination_lon)

        departure_times.append(departure_time())
        arrival_times.append(arrival_time())

        if questionary.confirm("Add another shipment?").ask():
            continue
        break

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


if __name__ == "__main__":
    print(get_shipments())
