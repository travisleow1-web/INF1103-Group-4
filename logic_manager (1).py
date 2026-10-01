"""
logic_manager.py
Business rules for the Logistics Risk Assessment System (Singapore).

Design notes (matches the four-manager flow):
  - LOGIC_MANAGER holds domain logic ONLY. No print(), no file access, no API calls.
  - It receives the AI Manager's validated JSON record (as a dict) and a
    DataManager-like object for history look-ups.
  - It returns a Decision object. IO_MANAGER displays it, DATA_MANAGER saves it.
  - The AI never makes the final decision. Every outcome is decided here.

Rule pipeline:
  Part 1  Validation checks
  Part 2  Operational decision making (Rules 1-6)
  Part 3  Escalation protocols (financial check, alerts, human review)
"""

from dataclasses import dataclass, field
from enum import IntEnum
from datetime import datetime, timedelta


# --------------------------------------------------------------------------
# Constants (change thresholds here, not inside the rules)
# --------------------------------------------------------------------------
class Level(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


LEVEL_FROM_TEXT = {"low": Level.LOW, "medium": Level.MEDIUM, "high": Level.HIGH}

CONFIDENCE_MIN = 0.60             # below this, AI output needs a human
HISTORY_WINDOW_DAYS = 21          # Rule 4 look-back
PERFECT_STORM_MIN_MEDIUMS = 3     # Rule 1
REROUTE_COST_LIMIT_PCT = 20.0     # Part 3 financial threshold
DATA_MAX_AGE_HOURS = 24           # external data older than this is "outdated"

PERFECT_STORM_FACTORS = {"weather", "port_congestion", "labor_shortage"}
INSURANCE_TRIGGERS = {"piracy_threat", "severe_civil_unrest"}

REQUIRED_FIELDS = [
    "shipment_id", "route_id", "origin", "destination", "transport_type",
    "transport_mode", "goods", "risk_factors", "primary_risk_factor",
    "affected_location", "expected_impact", "confidence_score", "sources",
]


# --------------------------------------------------------------------------
# Output object
# --------------------------------------------------------------------------
@dataclass
class Decision:
    shipment_id: str
    overall_risk: str = "Low"
    outcome: str = "PROCEED"      # PROCEED / DELAY / REROUTE / INSURE / ESCALATE / REJECT
    hold_shipment: bool = False
    needs_human: bool = False
    flags: list = field(default_factory=list)      # e.g. "Premium Increase Required"
    actions: list = field(default_factory=list)    # business actions to carry out
    alerts: list = field(default_factory=list)     # dicts: who / channel / message
    rationale: list = field(default_factory=list)  # audit trail (why each rule fired)


# --------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------
def _level(text):
    """Convert 'Medium' / 'medium' / 'MEDIUM' into a Level. Unknown -> LOW."""
    return LEVEL_FROM_TEXT.get(str(text).strip().lower(), Level.LOW)


def _key(text):
    """Normalise labels like 'Piracy Threat' -> 'piracy_threat'."""
    return str(text).strip().lower().replace(" ", "_")


def _add_alert(decision, recipient, channels, message):
    decision.alerts.append(
        {"recipient": recipient, "channels": channels, "message": message}
    )


# --------------------------------------------------------------------------
# PART 1: VALIDATION CHECKS (data consistency and completeness)
# --------------------------------------------------------------------------
def validate_record(record, decision, now):
    """Return True if the record is safe to run through the rules."""
    missing = [f for f in REQUIRED_FIELDS if f not in record or record[f] in (None, "", [])]
    if missing:
        decision.outcome = "REJECT"
        decision.needs_human = True
        decision.flags.append("Incomplete AI record")
        decision.rationale.append(f"Validation failed: missing fields {missing}")
        return False

    confidence = record["confidence_score"]
    if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
        decision.outcome = "REJECT"
        decision.needs_human = True
        decision.flags.append("Invalid confidence score")
        decision.rationale.append("Validation failed: confidence_score not in 0-1")
        return False

    # Softer problems: keep going, but a human must look at it
    if confidence < CONFIDENCE_MIN:
        decision.needs_human = True
        decision.flags.append("Low AI confidence")
        decision.rationale.append(
            f"Confidence {confidence:.2f} is below {CONFIDENCE_MIN:.2f}"
        )

    fetched_at = record.get("external_data_fetched_at")
    if fetched_at and now - fetched_at > timedelta(hours=DATA_MAX_AGE_HOURS):
        decision.needs_human = True
        decision.flags.append("Outdated external data")
        decision.rationale.append(
            f"External data is older than {DATA_MAX_AGE_HOURS}h"
        )

    if record.get("conflicting_sources"):
        decision.needs_human = True
        decision.flags.append("Conflicting sources")
        decision.rationale.append("AI reported conflicting information")

    return True


# --------------------------------------------------------------------------
# PART 2: OPERATIONAL DECISION MAKING
# --------------------------------------------------------------------------
def rule_perfect_storm(record, decision):
    """
    Rule 1: several smaller risks combine into one emergency.
    Medium Rain + Medium Port Congestion + Medium Labor Shortage -> High Risk.
    """
    levels = {_key(r["type"]): _level(r["severity"]) for r in record["risk_factors"]}

    # Any single High factor already makes the shipment High risk
    if any(lv == Level.HIGH for lv in levels.values()):
        decision.overall_risk = "High"
        decision.rationale.append("Rule 1: at least one risk factor is High")

    mediums = [
        f for f in PERFECT_STORM_FACTORS
        if levels.get(f, Level.LOW) >= Level.MEDIUM
    ]
    if len(mediums) >= PERFECT_STORM_MIN_MEDIUMS:
        decision.overall_risk = "High"
        decision.flags.append("Perfect Storm")
        decision.rationale.append(
            f"Rule 1 (Perfect Storm): {', '.join(sorted(mediums))} all >= Medium, upgraded to High"
        )
    elif decision.overall_risk != "High" and any(lv == Level.MEDIUM for lv in levels.values()):
        decision.overall_risk = "Medium"


def rule_asset_reallocation(record, decision):
    """
    Rule 2: Severe Crosswinds on a Light Freight vehicle -> reassign to Heavy Freight.
    """
    factor_keys = {_key(r["type"]) for r in record["risk_factors"]}
    primary = _key(record["primary_risk_factor"])

    if "severe_crosswinds" in factor_keys or primary == "severe_crosswinds":
        if record["transport_type"] == "Light Freight":
            record["transport_type"] = "Heavy Freight"
            decision.actions.append("Reassign load to a Heavy Freight carrier")
            decision.flags.append("Asset Reallocated")
            decision.rationale.append(
                "Rule 2: Severe Crosswinds + Light Freight, moved to Heavy Freight (rollover risk)"
            )
        else:
            decision.rationale.append(
                "Rule 2: Severe Crosswinds noted, transport already suitable"
            )


def rule_low_risk_validation(record, decision, data_manager, now):
    """
    Rule 3: never auto-approve a 'Low' route that recently failed.
    Ask the Data Manager for the last 21 days of logs on this exact route.
    """
    if decision.overall_risk != "Low":
        return

    since = now - timedelta(days=HISTORY_WINDOW_DAYS)
    past = data_manager.get_route_history(record["route_id"], since)
    problem_runs = [p for p in past if p.get("flagged") or p.get("delayed")]

    if problem_runs:
        decision.needs_human = True
        decision.hold_shipment = True
        decision.flags.append("Cautionary Override")
        decision.actions.append("Require human dispatcher sign-off")
        decision.rationale.append(
            f"Rule 3: AI says Low but {len(problem_runs)} shipment(s) on route "
            f"{record['route_id']} were flagged or delayed in the last {HISTORY_WINDOW_DAYS} days"
        )
    else:
        decision.rationale.append("Rule 3: Low risk and clean 21-day history, auto-approve")


def rule_dynamic_insurance(record, decision):
    """
    Rule 4: Piracy Threat or Severe Civil Unrest -> update financial profile
    and hold until a human confirms extended insurance was bought.
    """
    factor_keys = {_key(r["type"]) for r in record["risk_factors"]}
    triggered = INSURANCE_TRIGGERS & (factor_keys | {_key(record["primary_risk_factor"])})

    if triggered:
        decision.hold_shipment = True
        decision.needs_human = True
        decision.flags.append("Premium Increase Required")
        decision.actions.append("Update financial profile: extended insurance needed")
        decision.rationale.append(
            f"Rule 4: {', '.join(sorted(triggered))} detected, holding until insurance confirmed"
        )
        if decision.overall_risk != "High":
            decision.overall_risk = "High"


def rule_inventory_replacement(record, decision):
    """
    Rule 5: cargo likely destroyed by a sudden extreme event
    (e.g. Category 5 hurricane at the origin port) -> Procurement Alert.
    Do not just stop the shipment: tell the company to reorder now.
    """
    impact = _key(record["expected_impact"])
    event = _key(record.get("extreme_event", ""))
    at_origin = _key(record["affected_location"]) == _key(record["origin"])

    cargo_destruction_likely = impact in {"cargo_destruction", "total_loss"}
    if cargo_destruction_likely and event and at_origin:
        decision.hold_shipment = True
        decision.flags.append("Procurement Alert")
        decision.actions.append(
            f"Reorder goods immediately: {record['goods']['description']} "
            f"(extreme event: {record['extreme_event']})"
        )
        _add_alert(
            decision, "procurement_team", ["email", "sms"],
            f"Shipment {record['shipment_id']} is at risk of destruction. "
            f"Consider reordering to avoid stock-out.",
        )
        decision.rationale.append(
            "Rule 5: cargo destruction predicted from an extreme event at origin"
        )


def decide_outcome(record, decision):
    """Turn the accumulated flags into one final operational outcome."""
    if decision.outcome == "REJECT":
        return

    goods = record["goods"]
    time_sensitive = goods.get("perishable") or goods.get("time_sensitive")

    if "Procurement Alert" in decision.flags:
        decision.outcome = "DELAY"
    elif "Premium Increase Required" in decision.flags:
        decision.outcome = "INSURE"
    elif decision.overall_risk == "High":
        # Prefer rerouting for time-sensitive cargo, otherwise delay the departure
        if time_sensitive and record.get("alternative_route"):
            decision.outcome = "REROUTE"
            decision.actions.append(f"Reroute via {record['alternative_route']['name']}")
        else:
            decision.outcome = "DELAY"
            decision.actions.append("Delay departure until conditions clear")
        decision.needs_human = True
    elif decision.overall_risk == "Medium":
        decision.outcome = "PROCEED"
        decision.actions.append("Proceed with monitoring")
    else:
        decision.outcome = "PROCEED"

    # Anything a human must look at is not fully automatic
    if decision.hold_shipment and decision.outcome == "PROCEED":
        decision.outcome = "ESCALATE"


# --------------------------------------------------------------------------
# PART 3: ESCALATION PROTOCOLS
# --------------------------------------------------------------------------
def check_financial_threshold(record, decision):
    """
    If an automated reroute adds more than 20% distance, stop the auto-reroute
    and send an 'Excessive Cost' alert to the Operations Director.
    """
    if decision.outcome != "REROUTE":
        return

    base = record.get("baseline_distance_km")
    new = record.get("alternative_route", {}).get("distance_km")
    if not base or not new:
        decision.needs_human = True
        decision.flags.append("Reroute distance unknown")
        decision.rationale.append("Financial check: cannot compare distances, needs human")
        return

    increase_pct = (new - base) / base * 100
    if increase_pct > REROUTE_COST_LIMIT_PCT:
        decision.outcome = "ESCALATE"
        decision.hold_shipment = True
        decision.needs_human = True
        decision.flags.append("Excessive Cost")
        decision.actions = [a for a in decision.actions if not a.startswith("Reroute")]
        decision.actions.append("Automatic rerouting stopped")
        _add_alert(
            decision, "operations_director", ["email"],
            f"Excessive Cost: reroute for {record['shipment_id']} adds "
            f"{increase_pct:.1f}% distance (limit {REROUTE_COST_LIMIT_PCT:.0f}%).",
        )
        decision.rationale.append(
            f"Financial check: reroute +{increase_pct:.1f}% > {REROUTE_COST_LIMIT_PCT:.0f}%, stopped"
        )
    else:
        decision.rationale.append(
            f"Financial check: reroute +{increase_pct:.1f}% is within the limit"
        )


def stakeholder_alerting(record, decision):
    """
    Stakeholder Alerting: a shipment marked risky sends an urgent SMS and email
    to the cargo owner and the active supply chain manager.
    """
    if decision.overall_risk != "High":
        return

    summary = (
        f"URGENT: shipment {record['shipment_id']} is HIGH RISK. "
        f"Main risk: {record['primary_risk_factor']} at {record['affected_location']}. "
        f"Expected impact: {record['expected_impact']}. "
        f"Recommended: {decision.outcome}."
    )
    for recipient in ("cargo_owner", "supply_chain_manager"):
        _add_alert(decision, recipient, ["sms", "email"], summary)


def escalation_protocol(decision):
    """Final gate: anything needing a human is never marked as fully automatic."""
    if decision.needs_human and decision.outcome == "PROCEED":
        decision.outcome = "ESCALATE"
    if decision.needs_human:
        decision.actions.append("Route to human review queue")


# --------------------------------------------------------------------------
# MAIN ENTRY POINT
# --------------------------------------------------------------------------
def evaluate_shipment(ai_record, data_manager, now=None):
    """
    Run one AI-enriched record through every rule and return a Decision.
    This is the only function IO_MANAGER needs to call.
    """
    now = now or datetime.now()
    record = dict(ai_record)  # do not mutate the caller's data
    decision = Decision(shipment_id=record.get("shipment_id", "UNKNOWN"))

    # Part 1
    if not validate_record(record, decision, now):
        return decision

    # Part 2
    rule_perfect_storm(record, decision)
    rule_asset_reallocation(record, decision)
    rule_dynamic_insurance(record, decision)
    rule_low_risk_validation(record, decision, data_manager, now)
    rule_inventory_replacement(record, decision)
    decide_outcome(record, decision)

    # Part 3
    check_financial_threshold(record, decision)
    stakeholder_alerting(record, decision)
    escalation_protocol(decision)

    return decision


# --------------------------------------------------------------------------
# Demo (remove in production: print() belongs to IO_MANAGER only)
# --------------------------------------------------------------------------
if __name__ == "__main__":
    class FakeDataManager:
        def __init__(self, history):
            self._history = history

        def get_route_history(self, route_id, since):
            return [h for h in self._history if h["route_id"] == route_id and h["date"] >= since]

    now = datetime(2026, 9, 28, 9, 0)

    base = {
        "shipment_id": "SG-1001", "route_id": "SGSIN-NLRTM", "origin": "Singapore",
        "destination": "Rotterdam", "transport_type": "Cargo Vessel",
        "transport_mode": "sea", "goods": {"description": "Electronics", "perishable": False},
        "primary_risk_factor": "Weather", "affected_location": "Malacca Strait",
        "expected_impact": "Delay", "confidence_score": 0.82,
        "sources": ["MPA advisory"], "baseline_distance_km": 15000,
        "external_data_fetched_at": now - timedelta(hours=2),
    }

    cases = {
        "Perfect Storm": {
            **base, "shipment_id": "SG-1001",
            "risk_factors": [
                {"type": "Weather", "severity": "Medium"},
                {"type": "Port Congestion", "severity": "Medium"},
                {"type": "Labor Shortage", "severity": "Medium"},
            ],
            "goods": {"description": "Fresh fruit", "perishable": True},
            "alternative_route": {"name": "Cape of Good Hope", "distance_km": 20000},
        },
        "Piracy": {
            **base, "shipment_id": "SG-1002", "primary_risk_factor": "Piracy Threat",
            "risk_factors": [{"type": "Piracy Threat", "severity": "High"}],
        },
        "Low risk but bad history": {
            **base, "shipment_id": "SG-1003", "primary_risk_factor": "Weather",
            "risk_factors": [{"type": "Weather", "severity": "Low"}],
        },
        "Bad AI record": {"shipment_id": "SG-1004"},
    }

    dm = FakeDataManager([
        {"route_id": "SGSIN-NLRTM", "date": now - timedelta(days=10), "delayed": True}
    ])

    for name, rec in cases.items():
        d = evaluate_shipment(rec, dm, now)
        print(f"\n=== {name} ===")
        print("Outcome :", d.outcome, "| Risk:", d.overall_risk, "| Human:", d.needs_human)
        print("Flags   :", d.flags)
        print("Actions :", d.actions)
        print("Alerts  :", [(a['recipient'], a['channels']) for a in d.alerts])
        for line in d.rationale:
            print("  -", line)
