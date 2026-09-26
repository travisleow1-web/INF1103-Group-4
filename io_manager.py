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
    destination_ports = []
    departure_times = []
    arrival_times = []
    while True:
        ids.append(shipment_id())
        origin_ports.append(origin_port())
        destination_ports.append(destination_port())
        departure_times.append(departure_time())
        arrival_times.append(arrival_time())

        if questionary.confirm("Add another shipment?").ask():
            continue
        break

    return pd.DataFrame(
        {
            "shipment_id": ids,
            "origin_port": origin_ports,
            "destination_port": destination_ports,
            "departure_time": departure_times,
            "arrival_time": arrival_times,
        },
        dtype="str",
    )


if __name__ == "__main__":
    print(get_shipments())
