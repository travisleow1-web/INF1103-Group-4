import pandas as pd
import questionary


def shipment_id():
    answer = questionary.text("Shipment ID:").ask()
    return answer


def display():
    ids = []
    while True:
        ids.append(shipment_id())
        if not questionary.confirm("Add another shipment?").ask():
            break

    return pd.DataFrame(
        {
            "shipment_id": ids,
        },
        dtype="str",
    )


if __name__ == "__main__":
    print(display())
