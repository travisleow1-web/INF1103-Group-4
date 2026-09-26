import json

with open("ports_reference_4.json") as f:
    PORTS = json.load(f)["ports"]

PORT_CODES = [p["code"] for p in PORTS]
PORT_CHOICES = [f"{p['code']} - {p['name']}, {p['country']}" for p in PORTS]

print(PORT_CHOICES)