INF1103 - Team 4 Project Scope Brief
Team Members: Travis, Ming An, Jun Jie, Stephen, Phuc, Marcus
1. Problem Statement and Target Users
Singapore is unusually exposed to supply chain risk as it imports over 90% of its food from 187 countries,
and trade equals 322% of GDP (2024), which is one of the highest such ratios in the world. At the same time,
PSA Singapore is the world's largest container transshipment hub. They handled a record of 41.12 million
TEUs in 2024, about 90% of its transshipment cargo, retaining its title as the world's top maritime hub for
the 11th consecutive year. A disruption anywhere along a shipping route doesn't just delay a delivery to
Singapore, it delays cargo passing through Singapore on its way elsewhere, which is the country's core
economic function.
To give some examples, on 20 May 2026, two bulk carriers Capesize CAPE XL and Newcastlemax HUGE
KUMANO collided near Singapore's eastern anchorage, disabling both vessels. The same strait recorded 55
piracy and armed-robbery incidents in 2022 alone (65% of every such incident in Asia that year), and
ReCAAP's 2026 tracking shows the pattern remains active. Weather also has the same ripple effect at a larger
scale. In 2026, Typhoon Bavi shut the ports of Shanghai, Ningbo, and Qingdao, delaying roughly 2 million TEU
of capacity; a second storm, Typhoon Dolphin, struck the same ports again and stranded a further 2.4 million
TEU. Disrupted shipments can lead to detrimental effects. When Malaysia abruptly halted exports of roughly
3.6 million live chickens a month in 2022, Singapore avoided empty shelves only by substituting frozen imports
from Brazil and the US within days while prices still rose and quality still suffered in the meantime.
Our aim is to give logistics and supply chain planners a way to see that risk before it becomes a loss.
We aim to give stakeholders confidence in a shipment before it leaves the dock and not just a delivery
estimate, but a clear picture of what could go wrong along the way and what to do about it.
Target users: logistics and supply chain planners at Singapore-based importers, exporters, freight forwarders,
and shipping agents who need to decide whether to proceed, delay, reroute, or insure an upcoming shipment
before conditions along its route turn into a loss.
2. User Inputs (What information or data will users provide to the system?)
● Route Origin and Destination: Our core geospatial and facility data, including specific origin facility
codes, destination addresses, and possible geographic coordinates (latitude and longitude) to plot
cargo transit path
● Waypoints and Checkpoints: This includes intermediate stops, custom clearance points, or
mandatory transfer hubs required during transit.
● Transit and Load Constraints: Operational limits tied to the route, such as maximum weight
thresholds (kg), volumetric limits (m³) , and regulatory indicators (e.g., hazardous material flags).
● Scheduling Parameters: The planned departure time, expected arrival window, and how long the
shipment is expected to sit at each checkpoint.
● Logistics Metadata: Administrative identifiers including carrier names, transport modes (e.g., heavy
goods vehicle, cargo vessel), and internal route tracking IDs.
● Goods Information: What kind of cargo is being transported, including whether it is perishable,
time-sensitive, fragile, or classified as high-value.
3. Use of AI
The application uses AI primarily to gather, analyse, and structure information from shipment data and external
sources. The AI does not make the final operational decision, that responsibility stays with the Logic Manager.
● 1. Data Gathering & Analysis: The AI combines user-provided shipment information with external
data, including weather and severe weather alerts, port congestion and disruptions, piracy and
maritime security alerts, geopolitical and civil unrest news, and infrastructure or transport disruptions.
● 2. Risk Information Extraction: From this combined information, the AI identifies the relevant risk
factors and produces a structured output containing the primary risk factor, the affected location, the
expected impact, a confidence score, and supporting source information.
● 3. AI Insights: Beyond a single risk assessment, the AI can also flag potential delays or disruptions,
multiple risks occurring simultaneously, historical issues on the same route, conflicting, outdated, or
missing information, and situations that require human attention.
4. Business Rules
The Logic Manager will take the AIs validated JSON risk assessment. Run it through a strict set of business
rules to decide the final operational outcome. These rules are split into three parts: validation checks,
operational decision making and escalation protocols.
● Stakeholder Alerting: When a shipment is marked as "risk" the system immediately sends an urgent
SMS and email to the registered owner of the cargo and the active supply chain manager. The
message includes the AI’s summarized news and weather data.
● The "Perfect Storm" Rule: of only focusing on the single highest risk factor the Logic Manager looks
at the combination of smaller risks. If the AI identifies three Medium risks. Such as Medium Rain,
Medium Port Congestion and Medium Labor Shortage. The Logic Manager combines them
mathematically. This combination upgrades the overall shipment status to "High Risk", and activates
the emergency protocols.
● Asset Reallocation: If the AI flags "Severe Crosswinds" along a route, the logic checks the assigned
transport type. If the vehicle is a "Light Freight," it automatically reassigns the load to a "Heavy Freight"
carrier to prevent rollover accidents.
● Low-Risk Route Validation: Before auto-approving a route that the AI deems "Low Risk," the Logic Manager
queries the Data Manager for the last 21 days of logs. If previous shipments on this exact route were flagged or
delayed recently despite a low AI risk score, the system applies a "Cautionary Override" and requires a human
dispatcher to sign off.
● Dynamic Insurance Declaration: If the AI outputs a specific high-liability risk factor like "Piracy
Threat" or "Severe Civil Unrest" along a maritime or land route, the Logic Manager automatically
updates the shipment's financial profile. It logs a "Premium Increase Required" flag and holds the
shipment until a human confirms the extended insurance coverage has been purchased.
● Inventory Replacement Trigger: In cases where the AI predicts a "risk of cargo destruction due to a
sudden extreme event. Like a "Category 5 Hurricane making landfall at the origin port”. The Logic
Manager doesn’t just stop the shipment. It generates a "Procurement Alert" suggesting that the
company should immediately reorder those goods, this helps avoid inventory shortages.
● Financial Threshold Check: If any automated reroute suggested by Rule 1 or Rule 2 increases the
expected journey distance by more than 20% the system stops the automatic rerouting and sends an
"Excessive Cost" alert, to the Operations Director.
Repository Link:
https://github.com/travisleow1-web/INF1103-Group-4
