"""
main.py: wires the four managers together.

    IO  ->  AI  ->  LOGIC  ->  DATA  ->  IO (display)

Run:
    pip install requests
    export GEMINI_API_KEY="your-free-key-from-aistudio.google.com" #you need to put API key here or it wont work lol
    python main.py
"""

import logging
from dataclasses import asdict

import io_manager
import ai_manager
import logic_manager
from data_manager import DataManager

logging.basicConfig(filename="app.log", level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")


def assess_new_shipment(data):
    record = io_manager.collect_shipment_input()             # 1. input record
    io_manager.show_message("\nGathering weather and news, then asking the AI...")

    enriched = ai_manager.enrich_record(record)              # 2. AI-enriched record
    if enriched is None:
        # AI failed: never crash, save for manual review
        io_manager.show_ai_unavailable(record["shipment_id"])
        failed = logic_manager.evaluate_shipment(record, data)   # will REJECT (missing AI fields)
        data.save_record(record, asdict(failed))
        return

    decision = logic_manager.evaluate_shipment(enriched, data)   # 3. final outcome
    decision_dict = asdict(decision)
    data.save_record(enriched, decision_dict)                    # 4. saved record
    io_manager.display_decision(enriched, decision_dict)         # display


def main():
    data = DataManager()
    while True:
        choice = io_manager.main_menu()
        if choice == "1":
            assess_new_shipment(data)
        elif choice == "2":
            flt = io_manager.collect_filter()
            io_manager.display_records(data.query_records(flt))
        else:
            io_manager.show_message("Goodbye.")
            break


if __name__ == "__main__":
    main()
