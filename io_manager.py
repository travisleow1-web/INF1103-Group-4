"""
io_manager.py
ALL input() and print() calls live here. No AI calls, no business rules, no file access.
Data comes in/out as plain dicts; anything stored or filtered goes through DATA_MANAGER.
"""

from datetime import datetime

TRANSPORT_MODES = ["sea", "air", "road", "rail"]
TRANSPORT_TYPES = ["Light Freight", "Heavy Freight", "Cargo Vessel", "Air Freight", "Rail Freight"]


# --------------------------------------------------------------------------
# Small reusable prompts (each one re-prompts until the answer is valid)
# --------------------------------------------------------------------------
def _ask_text(label, required=True):
    while True:
        value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print("  This field is required. Please try again.")


def _ask_number(label, minimum=0.0, required=True):
    while True:
        raw = input(f"{label}: ").strip()
        if not raw and not required:
            return None
        try:
            value = float(raw)
            if value > minimum:
                return value
            print(f"  Enter a number greater than {minimum}.")
        except ValueError:
            print("  Please enter a valid number.")


def _ask_choice(label, options):
    menu = " / ".join(f"{i}) {o}" for i, o in enumerate(options, 1))
    while True:
        raw = input(f"{label} [{menu}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw.title() in options or raw.lower() in options:
            return raw.title() if raw.title() in options else raw.lower()
        print("  Please pick one of the listed options.")


def _ask_yes_no(label):
    while True:
        raw = input(f"{label} (y/n): ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please answer y or n.")


def _ask_date(label):
    while True:
        raw = input(f"{label} (YYYY-MM-DD): ").strip()
        try:
            return datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            print("  Use the format YYYY-MM-DD, for example 2026-10-05.")


# --------------------------------------------------------------------------
# 1. Collect + validate user input  ->  "input record"
# --------------------------------------------------------------------------
def collect_shipment_input():
    print("\n--- New shipment ---")
    origin = _ask_text("Origin (city or port)")
    destination = _ask_text("Destination (city or port)")

    while destination.lower() == origin.lower():
        print("  Origin and destination cannot be the same.")
        destination = _ask_text("Destination (city or port)")

    waypoints_raw = _ask_text("Waypoints / checkpoints, comma separated (optional)", required=False)
    waypoints = [w.strip() for w in waypoints_raw.split(",") if w.strip()]

    transport_mode = _ask_choice("Transport mode", TRANSPORT_MODES)
    transport_type = _ask_choice("Transport type", TRANSPORT_TYPES)
    max_weight = _ask_number("Load weight (kg)")
    volume = _ask_number("Load volume (m3)")

    departure = _ask_date("Planned departure")
    arrival = _ask_date("Expected arrival")
    while arrival <= departure:
        print("  Arrival must be after departure.")
        arrival = _ask_date("Expected arrival")

    carrier = _ask_text("Carrier name")
    goods_desc = _ask_text("Goods description")
    goods = {
        "description": goods_desc,
        "perishable": _ask_yes_no("Perishable?"),
        "time_sensitive": _ask_yes_no("Time-sensitive?"),
        "fragile": _ask_yes_no("Fragile?"),
        "high_value": _ask_yes_no("High-value?"),
        "hazardous": _ask_yes_no("Hazardous material?"),
    }
    distance = _ask_number("Planned route distance in km (optional, Enter to skip)", required=False)

    return {
        "shipment_id": f"SG-{datetime.now():%y%m%d%H%M%S}",
        "route_id": f"{origin[:3].upper()}-{destination[:3].upper()}",
        "origin": origin,
        "destination": destination,
        "waypoints": waypoints,
        "transport_mode": transport_mode,
        "transport_type": transport_type,
        "load_weight_kg": max_weight,
        "load_volume_m3": volume,
        "departure_date": departure.strftime("%Y-%m-%d"),
        "expected_arrival": arrival.strftime("%Y-%m-%d"),
        "carrier": carrier,
        "goods": goods,
        "baseline_distance_km": distance,
    }


# --------------------------------------------------------------------------
# 2. Display results
# --------------------------------------------------------------------------
def show_message(text):
    print(text)


def show_ai_unavailable(shipment_id):
    print(f"\n[!] AI analysis was unavailable for {shipment_id}.")
    print("    The shipment has been saved as 'needs manual review'.")


def display_decision(record, decision):
    """decision is the dict form of logic_manager.Decision."""
    line = "=" * 60
    print(f"\n{line}\n RISK ASSESSMENT: {decision['shipment_id']}\n{line}")
    print(f" Route        : {record['origin']} -> {record['destination']}")
    print(f" Overall risk : {decision['overall_risk']}")
    print(f" Outcome      : {decision['outcome']}"
          + ("  (ON HOLD)" if decision["hold_shipment"] else ""))
    if record.get("primary_risk_factor"):
        print(f" Main risk    : {record['primary_risk_factor']} at {record.get('affected_location')}")
        print(f" AI confidence: {record.get('confidence_score', 0):.0%}")

    _print_list("Flags", decision["flags"])
    _print_list("Recommended actions", decision["actions"])
    _print_list("Why (audit trail)", decision["rationale"])
    _print_list("AI insights", record.get("insights", []))

    if decision["alerts"]:
        print("\n Alerts sent:")
        for a in decision["alerts"]:
            print(f"   -> {a['recipient']} via {'+'.join(a['channels'])}: {a['message']}")
    if decision["needs_human"]:
        print("\n >> HUMAN REVIEW REQUIRED <<")
    print(line)


def _print_list(title, items):
    if items:
        print(f"\n {title}:")
        for item in items:
            print(f"   - {item}")


def display_records(records):
    if not records:
        print("\nNo matching shipments found.")
        return
    print(f"\n{'ID':<18}{'Route':<22}{'Risk':<8}{'Outcome':<10}{'Human?'}")
    print("-" * 64)
    for r in records:
        d = r["decision"]
        route = f"{r['origin'][:9]}->{r['destination'][:9]}"
        print(f"{d['shipment_id']:<18}{route:<22}{d['overall_risk']:<8}"
              f"{d['outcome']:<10}{'yes' if d['needs_human'] else 'no'}")


# --------------------------------------------------------------------------
# 3. Menu + filter/query requests
# --------------------------------------------------------------------------
def main_menu():
    print("\n=== Logistics Risk Assessment ===")
    print("1) Assess a new shipment")
    print("2) View / filter saved assessments")
    print("3) Quit")
    while True:
        choice = input("Choose 1-3: ").strip()
        if choice in ("1", "2", "3"):
            return choice
        print("  Please enter 1, 2 or 3.")


def collect_filter():
    """Returns a filter dict for DATA_MANAGER.query_records()."""
    print("\nFilter saved assessments (press Enter to skip any filter)")
    risk = input("Risk level (Low/Medium/High): ").strip().capitalize()
    outcome = input("Outcome (PROCEED/DELAY/REROUTE/INSURE/ESCALATE/REJECT): ").strip().upper()
    text = input("Text in origin/destination: ").strip()
    human_only = input("Only cases needing human review? (y/n): ").strip().lower() == "y"
    return {
        "risk": risk if risk in ("Low", "Medium", "High") else None,
        "outcome": outcome or None,
        "text": text or None,
        "needs_human": True if human_only else None,
    }
