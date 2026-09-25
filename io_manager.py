import questionary


def ask_shipment_id():
    answer = questionary.text("Shipment ID:").ask()
    return answer


if __name__ == "__main__":
    print(ask_shipment_id())