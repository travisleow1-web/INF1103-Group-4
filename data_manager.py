"""
data_manager.py  (minimal version so the other managers can run)
Storage + retrieval only. No domain decisions.
"""

import json
import logging
import os
from datetime import datetime

log = logging.getLogger("data_manager")
DB_FILE = "shipments.json"


class DataManager:
    def __init__(self, path=DB_FILE):
        self.path = path
        self.records = []
        self._load()

    def _load(self):
        """Startup: load all records. Missing or corrupt file -> start empty + log."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.records = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Could not read %s (%s). Starting with an empty dataset.", self.path, exc)
            self.records = []

    def save_record(self, record, decision):
        """decision is a dict. Stores both, plus fields used for history look-ups."""
        entry = {
            **record,
            "decision": decision,
            "saved_at": datetime.now().isoformat(),
            "flagged": decision["needs_human"] or decision["overall_risk"] != "Low",
            "delayed": decision["outcome"] == "DELAY",
        }
        self.records.append(json.loads(json.dumps(entry, default=str)))
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2)

    def get_route_history(self, route_id, since):
        """Used by Logic Manager Rule 3 (last 21 days on the same route)."""
        out = []
        for r in self.records:
            if r.get("route_id") != route_id:
                continue
            saved = datetime.fromisoformat(r["saved_at"])
            if saved >= since:
                out.append({"date": saved, "flagged": r["flagged"], "delayed": r["delayed"]})
        return out

    def query_records(self, flt):
        """Used by IO Manager filter/query."""
        result = self.records
        if flt.get("risk"):
            result = [r for r in result if r["decision"]["overall_risk"] == flt["risk"]]
        if flt.get("outcome"):
            result = [r for r in result if r["decision"]["outcome"] == flt["outcome"]]
        if flt.get("needs_human") is not None:
            result = [r for r in result if r["decision"]["needs_human"] == flt["needs_human"]]
        if flt.get("text"):
            t = flt["text"].lower()
            result = [r for r in result
                      if t in r["origin"].lower() or t in r["destination"].lower()]
        return result
