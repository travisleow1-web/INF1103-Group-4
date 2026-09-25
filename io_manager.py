import pandas as pd
import questionary


def shipment_id():
    answer = questionary.text("Shipment ID:").ask()
    return answer


def origin_port():
    answer = questionary.text("Origin port (e.g. SGSIN):").ask()
    return answer.strip().upper()


def destination_port():
    answer = questionary.text("Destination port (e.g. SGSIN):").ask()
    return answer.strip().upper()


def display():
    ids = []
    origin_ports = []
    destination_ports = []

    while True:
        ids.append(shipment_id())
        origin_ports.append(origin_port())
        destination_ports.append(destination_port())
        if not questionary.confirm("Add another shipment?").ask():
            break

    return pd.DataFrame(
        {
            "shipment_id": ids,
            "origin_port": origin_ports,
            "destination_port": destination_ports,
        },
        dtype="str",
    )


if __name__ == "__main__":
    print(display())
