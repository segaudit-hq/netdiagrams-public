"""Make the warehouse template and its samples from the bundled S01 template.

    python scripts/make_warehouse.py

Writes, under src/netdiagrams/data/:

- W01-Warehouse-Network-Template.drawio: the eleven-sheet standard drawn for
  "W01 · Riverside DC", a fictional distribution center. The layout, shapes,
  NetBox fields and layers are the S01 template's; the words are a
  warehouse's: inbound conveyor, sortation and AMRs, dock doors and the yard
  gate in the cell/area zones, WES/WCS in site operations, handhelds on the
  operations Wi-Fi, carriers and the cloud WMS through the integration DMZ.
- sample-warehouse-w01.json: the NetBox export that rebuilds it.
- sample-warehouse-w02.json: "W02 · Northgate Cross-Dock", a small site on
  day one (a firewall, a core, an IDF, a dock cell and Wi-Fi, with gaps).

The S01 template stays the source: a change to it is carried into the
warehouse by running this script again. Element ids, layer names and table
headers are never rewritten, so the build reads both templates the same way.
"""

from __future__ import annotations

import copy
import ipaddress
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import make_sample  # noqa: E402
from make_sample import channel_label  # noqa: E402  NetBox's own label for a channel choice
DATA = ROOT / "src" / "netdiagrams" / "data"
SOURCE = DATA / "S01-Network-Architecture-Template.drawio"
TEMPLATE = DATA / "W01-Warehouse-Network-Template.drawio"
SAMPLE = DATA / "sample-warehouse-w01.json"
SMALL = DATA / "sample-warehouse-w02.json"
SITE_NAME = "Riverside DC"

# Attributes that hold ids, geometry or style, never words.
SKIP = {"id", "parent", "source", "target", "style", "as", "x", "y", "width", "height", "dx", "dy",
        "pageWidth", "pageHeight", "background", "grid", "gridSize", "math", "placeholders"}

# Whole names first, so the shorter words below don't split them.
NAMES = [
    ("S01-SIS-SW01", "S01-SAF-SW01"), ("S01-SIS-LS01", "S01-SAF-PLC01"),
    ("S01-SIS-EWS01", "S01-SAF-EWS01"), ("S01-SIS-ROGW01", "S01-SAF-ROGW01"),
    ("SIS-SW01", "SAF-SW01"), ("SIS-LS01", "SAF-PLC01"), ("SIS-EWS01", "SAF-EWS01"), ("SIS-ROGW01", "SAF-ROGW01"),
    ("S01-WGB-AGV-01", "S01-WGB-AMR-01"), ("WGB-AGV-01", "WGB-AMR-01"),
    ("S01-C03-PH-SW01", "S01-C03-GH-SW01"), ("S01-C03-PH-PLC01", "S01-C03-GH-PLC01"),
    ("S01-C03-PH-VFD01", "S01-C03-GH-GATE01"), ("C03-PH-SW01", "C03-GH-SW01"),
    ("S01-PTP-PH-", "S01-PTP-GH-"), ("PTP-PH-", "PTP-GH-"), ("PH-SW01", "GH-SW01"),
    ("PH-A eth0", "GH-A eth0"), ("PH-B eth0", "GH-B eth0"), ("PH-C01", "GH-C01"), ("PH-01", "GH-01"),
    ("S01-WH-ACC-", "S01-AX-ACC-"), ("WH-ACC-", "AX-ACC-"), ("S01-PTP-WH-", "S01-PTP-AX-"), ("PTP-WH-", "PTP-AX-"),
    ("S01-AP-WH-", "S01-AP-AX-"), ("AP-WH-", "AP-AX-"), ("WH-A eth0", "AX-A eth0"), ("WH-B eth0", "AX-B eth0"),
    ("WH-R01", "AX-R01"), ("WH-LEG", "AX-LEG"), ("WH-01", "AX-01"), ("WH-02", "AX-02"),
    ("RT-S01-AGV", "RT-S01-AMR"), ("RT-S01-PLANT", "RT-S01-FLOOR"), ("RT-S01-HIGHBAY", "RT-S01-ANNEX"),
    ("C02-AGV", "C02-AMR"), ("OT-MOBILE", "WH-SCAN"), ("OT-WLAN", "RF-HANDHELD"),
    ("IDMZ-DATA", "IDMZ-RPT"), ("IDMZ-FILE", "IDMZ-EDI"), ("OT-SERVERS", "WCS-SERVERS"),
    ("zone-sis", "zone-safety"), ("Zone SIS", "Zone SAFETY"),
]

# Sentences and labels, longest first within each group.
WORDS = [
    # Band strips
    ("INDUSTRIAL DMZ", "INTEGRATION DMZ"), ("SITE OPERATIONS (OT)", "WAREHOUSE OPERATIONS (OT)"),
    ("CELL/AREA & SAFETY", "AUTOMATION & SAFETY"), ("CELLS & SAFETY", "AUTOMATION & SAFETY"),
    ("SITE OPERATIONS", "WAREHOUSE OPERATIONS"),
    # Sheet 1 · overview
    ("How every plant network is protected", "How every warehouse network is protected"),
    ("The same design is used at every plant.", "The same design is used at every building."),
    ("Plant DMZ — the only meeting point\nOffice and plant systems exchange data here. Nothing passes straight through.",
     "Warehouse DMZ — the only meeting point\nOffice, carriers and floor systems exchange data here. Nothing passes straight through."),
    ("Plant DMZ — the only meeting point", "Warehouse DMZ — the only meeting point"),
    ("Office and plant systems exchange data here.", "Office, carriers and floor systems exchange data here."),
    ("Same security gate — checks everything going into or out of the plant",
     "Same security gate — checks everything going onto or off the warehouse floor"),
    ("Plant operations\nProduction data, scheduling and engineering stations",
     "Warehouse operations\nWCS, label printing, handhelds and engineering stations"),
    ("Production data, scheduling and engineering stations", "WCS, label printing, handhelds and engineering stations"),
    ("Plant operations", "Warehouse operations"),
    ("Same security gate — between operations and every production line",
     "Same security gate — between operations and every automation area"),
    ("Production lines — each line is its own sealed zone", "Automation areas — each system is its own sealed zone"),
    ("Line 1\nAssembly", "Inbound\nConveyor"), ("Line 2\nPackaging", "Sortation\nSorter · AMRs"),
    ("Utilities\nAir · boilers", "Dock & yard\nDoors · gate"),
    ("Vendors & remote staff:\nstop in the DMZ", "Vendors, carriers & staff:\nstop in the DMZ"),
    ("supervised, recorded\nsession to one machine", "supervised, recorded\nsession to one controller"),
    ("Nothing from the internet or the office network can reach a machine directly.",
     "Nothing from the internet, the office or a carrier can reach a conveyor or sorter directly."),
    ("Each production line is its own zone, so an incident on one line cannot spread to the next.",
     "Each automation system is its own zone, so an incident in one cannot spread to the next."),
    ("Keeps running offline\nPlants keep producing if the internet or the link to head office goes down.",
     "Keeps moving offline\nConveyors and the sorter keep running if the internet drops; the WMS link has a second circuit."),
    ("Plants keep producing if the internet or the link to head office goes down.",
     "Conveyors and the sorter keep running if the internet drops; the WMS link has a second circuit."),
    ("Firewalls, core switches and line networks all have a backup that takes over automatically.",
     "Firewalls, core switches, Wi-Fi controllers and the sorter network all have a backup that takes over automatically."),
    # Logical sheet
    ("ZONE IDMZ · Industrial DMZ", "ZONE IDMZ · Integration DMZ"),
    ("no traffic traverses the IDMZ — every session terminates on an IDMZ host",
     "carriers, the cloud WMS and vendors end here — every session terminates on an IDMZ host"),
    ("ZONE OT-OPS · Site Operations", "ZONE OT-OPS · Warehouse operations (WES · WCS · handhelds)"),
    ("ZONE GUEST · Visitor Wi-Fi", "ZONE GUEST · Driver & visitor Wi-Fi"),
    ("ZONE IT-ENT · Site Enterprise LAN", "ZONE IT-ENT · Site business LAN"),
    ("ZONE CELL01 · Line 1 — Assembly", "ZONE CELL01 · Inbound — receiving conveyor"),
    ("ZONE CELL02 · Line 2 — Packaging", "ZONE CELL02 · Sortation — cross-belt sorter · AMRs"),
    ("ZONE CELL03 · Utilities (air · boilers · BMS)", "ZONE CELL03 · Dock & yard — doors · levelers · gate"),
    ("ZONE SIS · Safety Instrumented System", "ZONE SAFETY · Conveyor & sorter safety"),
    ("No SVI on OT-CORE for 590, so no VRF route reaches the SIS — only an explicit PA-450 rule. SIS engineering is local only. Data out = read-only (F16).",
     "No SVI on OT-CORE for 590, so no VRF route reaches the safety PLC — only an explicit PA-450 rule. Safety engineering is local only. Data out = read-only (F16)."),
    ("IE3400 REP ring (segment 11) closed on OT-CORE", "IE3400 REP ring (segment 11) along the receiving conveyor, closed on OT-CORE"),
    ("IE3400 REP ring (segment 12) closed on OT-CORE", "IE3400 REP ring (segment 12) around the sorter, closed on OT-CORE"),
    ("IE3400 REP ring (segment 13) closed on OT-CORE", "IE3400 REP ring (segment 13) along the dock doors, closed on OT-CORE"),
    ("HMI ⇄ PLC ⇄ I/O stays L2 inside the cell.", "HMI ⇄ PLC ⇄ I/O, scanners and drives stay L2 inside the area."),
    ("Anything leaving the cell is routed in VRF", "Anything leaving the area is routed in VRF"),
    ("L2 · HMI / SCADA", "L2 · HMI · WCS client"), ("L0 · I/O · drives", "L0 · I/O · drives · scanners"),
    ("Historian (primary)", "WCS database"), ("SCADA / MES", "WES / WCS"), ("Engineering WS", "Controls eng. WS"),
    ("PTP/NTP grandmaster", "Label print servers"), ("Cyber Vision Center", "OT visibility (Cyber Vision)"),
    ("Historian replica", "Reporting replica"), ("MES ⇄ ERP broker", "WMS ⇄ WCS broker"),
    ("Secure file transfer", "EDI · carrier API gateway"),
    ("SIS logic solver", "Safety PLC"), ("SIS EWS (local)", "Safety eng. WS (local)"),
    ("3rd-party vendors / OEMs\nvia SRA broker only", "Vendors / MHE integrators\nvia SRA broker only"),
    ("3rd-party vendors / OEMs", "Vendors / MHE integrators"),
    ("HQ data center\nERP · Corp AD/IdP (MFA) · SIEM/SOC\nCentral RA-VPN · Enterprise historian",
     "HQ & cloud\nERP · cloud WMS · Corp AD/IdP (MFA)\nSIEM/SOC · carrier & client APIs"),
    ("Corp PCs / laptops", "Office PCs / laptops"),
    ("OT address plan · 10.(100+site).0.0/16", "Floor address plan · 10.(100+site).0.0/16"),
    ("Add a cell — copy a CELL zone", "Add an automation area — copy a CELL zone"),
    ("Switch / AP / IE / OT-WLC / PtP radio mgmt only — no end hosts.", "Switch / AP / IE / OT-WLC / PtP radio mgmt only — no end hosts, no handhelds."),
    # Physical sheet
    ("CELL01 · Line 1 — Assembly  REP 11 · cabinet CP-101", "CELL01 · Inbound conveyor  REP 11 · cabinet CP-101"),
    ("CELL02 · Line 2 — Packaging  REP 12 · cabinet CP-201", "CELL02 · Sortation & AMRs  REP 12 · cabinet CP-201"),
    ("CELL03 · Utilities  REP 13 · cabinet UR-301", "CELL03 · Dock & yard  REP 13 · cabinet DK-301"),
    ("CELL03 ext. · Pump house GH-01  via PtP2 · cabinet GH-C01", "CELL03 ext. · Gate house GH-01  via PtP2 · cabinet GH-C01"),
    ("SIS · Safety zone  isolated · VLAN 590 · cabinet SC-01", "SAFETY · Safety zone  isolated · VLAN 590 · cabinet SC-01"),
    ("WAREHOUSE AX-01 · remote IT building", "ANNEX AX-01 · returns building"),
    ("Logic solver", "Safety PLC"), ("RO gateway", "RO gateway"),
    ("UR-301", "DK-301"), ("Utilities roof", "Dock roof"), ("PH-01 wall", "Gate house wall"),
    ("Pump house access", "Gate house access"), ("Shipping office access", "Annex office access"),
    ("Warehouse access", "Annex access"), ("AX-01 ship office", "AX-01 office"),
    ("Cell01 access", "Inbound access"), ("Cell02 access", "Sorter access"), ("Cell03 access", "Dock access"),
    ("Cell01 floor", "Receiving"), ("Cell02 floor", "Sorter mezzanine"), ("Cell03 floor", "Dock doors"),
    ("SIS network", "Safety network"), ("SIS room", "Safety room"),
    ("Control room", "Controls room"), ("Production hall", "Pick aisles"),
    ("OT server cluster node 1 of 3 (historian, MES, AD, CV Center)", "OT server cluster node 1 of 3 (WCS, WES, AD, CV Center)"),
    ("OT wireless controller (active) · plant SSIDs", "OT wireless controller (active) · handheld and AMR SSIDs"),
    ("Drive (endpoint)", "Gate operator (endpoint)"),
    ("HIST-R, SFT, LOG", "RPT, EDI, LOG"),
    ("only for central OT services in the HQ IDMZ (F21)", "only for central OT services in the HQ IDMZ (no register row yet: write one before using it)"),
    ("Safety logic solver (endpoint)", "Safety PLC (endpoint)"), ("Safety logic solver", "Safety PLC"),
    ("SIS EWS (endpoint)", "Safety engineering WS (endpoint)"),
    ("SIS network (single uplink, VLAN 590)", "Safety network (single uplink, VLAN 590)"),
    ("PtP2 radio — pump house end", "PtP2 radio — gate house end"), ("PtP2 radio — utilities end", "PtP2 radio — dock end"),
    ("Pump house access (legacy)", "Gate house access (legacy)"),
    ("Variable frequency drive", "Barrier gate operator"),
    ("Workgroup bridge on AGV (C02-AMR)", "Workgroup bridge on AMR (C02-AMR)"),
    ("rugged / LH optics on all cell runs", "rugged / LH optics on all conveyor runs"),
    ("every cell repeats this ring pattern", "every automation area repeats this ring pattern"),
    # Wireless sheet
    ("serves plant SSIDs from Level 3", "serves handheld and AMR SSIDs from Level 3"),
    ("= plant SSIDs.", "= handheld and AMR SSIDs."),
    ("(tablets, handheld HMIs) → VLAN 350 in OT-OPS", "(handhelds, vehicle-mount terminals, wearables) → VLAN 350 in OT-OPS"),
    ("so AGV traffic stays in the cell", "so AMR traffic stays in the sortation zone"),
    ("no DFS on AGV aisles", "no DFS on AMR aisles"), ("on AGV aisles (no DFS)", "on AMR aisles (no DFS)"),
    ("CELL02 · Line 2 — Packaging AGV workgroup bridges · FlexConnect", "CELL02 · Sortation — AMR workgroup bridges · FlexConnect"),
    ("CELL03 ext. · Pump house PtP2 backhaul — not WLAN", "CELL03 ext. · Gate house PtP2 backhaul — not WLAN"),
    ("IW9167EH in WGB mode · on AGV", "IW9167EH in WGB mode · on AMR"), ("Line 2 PLC", "Sorter PLC"),
    ("AGV PLC · VLAN 520", "AMR controller · VLAN 520"),
    ("The WGB bridges the AGV PLC into CELL02 VLAN 520 — the AGV is a member of the cell zone.",
     "The WGB bridges the AMR controller into CELL02 VLAN 520 — the AMR is a member of the sortation zone."),
    ("Plant floor: industrial APs", "Warehouse floor: industrial APs high in the racking"),
    ("Plant APs · IW9167EH · CAPWAP", "Floor APs · IW9167EH · CAPWAP"), ("Plant APs (OT-01…03)", "Floor APs (OT-01…03)"),
    ("Production hall · Line 1", "Pick aisles · north"), ("Production hall · Line 2", "Pick aisles · south"),
    ("Pick aisles · utilities", "Pick aisles · dock"), ("Utilities · boiler house", "Dock · doors 1–24"),
    ("Pick aisles · Line 1", "Pick aisles · north"), ("Pick aisles · Line 2", "Pick aisles · south"),
    ("AP · Pick aisles · Line 1 · Local", "AP · Pick aisles · north · Local"), ("AP · Pick aisles · Line 2 · Local", "AP · Pick aisles · south · Local"),
    ("AP · Utilities · boiler house · Local", "AP · Dock · doors 1–24 · Local"),
    ("AP · CELL02 · AGV aisle", "AP · CELL02 · AMR aisle"),
    ("CELL02 · Line 2 · AGV aisle", "CELL02 · Sorter · AMR aisle"), ("CELL02 · AGV aisle", "CELL02 · AMR aisle"),
    ("CELL02 AGV aisle", "CELL02 AMR aisle"), ("CELL01 · Line 1", "CELL01 · Inbound conveyor"),
    ("CELL03 · Utilities / boiler house", "CELL03 · Dock doors"), ("PUMP HOUSE GH-01", "GATE HOUSE GH-01"),
    ("WAREHOUSE AX-01", "ANNEX AX-01"), ("MAIN BUILDING", "MAIN DC BUILDING"), ("AGV route", "AMR route"),
    ("MDF-01 · control room", "MDF-01 · controls room"), ("Office · canteen · lab", "Office · breakroom · training"),
    ("Canteen · training", "Breakroom · training"), ("Lab · QA", "Returns desk"),
    ("Office + warehouse APs", "Office + annex APs"), ("Warehouse (via PtP1)", "Annex (via PtP1)"),
    ("Warehouse · high bay N", "Annex · north"), ("Warehouse · high bay S", "Annex · south"),
    ("Warehouse APs ride PtP1 to the core", "Annex APs ride PtP1 to the core"),
    # Riverside's WH-SCAN is a floor SSID on the OT controller; the IT controller and the annex carry CORP (and GUEST).
    ("SSIDs CORP (802.1X → VLAN 130), WH-SCAN (802.1X → VLAN 131, warehouse APs) and GUEST",
     "SSIDs CORP (802.1X → VLAN 130) and GUEST"),
    ("via PtP1 · CORP and WH-SCAN", "via PtP1 · CORP"),
    ("PtP2 · 5 GHz · ~600 m", "PtP2 · 5 GHz · ~600 m to the gate"),
    # Traffic flows
    ("L2–L0 · CELL01–03 (VLAN 5x0–5x9)", "L2–L0 · CELL01–03 conveyor · sorter · dock (VLAN 5x0–5x9)"),
    ("PA-450 · ae2.590 (SIS gateway)", "PA-450 · ae2.590 (safety gateway)"), ("SIS · Safety zone (VLAN 590)", "SAFETY · Safety zone (VLAN 590)"),
    ("Remote OT support", "Remote controls support"), ("Vendor / OEM access", "Vendor / integrator access"),
    ("Historian replication", "WCS reporting replica"), ("ERP ⇄ MES", "WMS ⇄ WCS"), ("File transfer in/out", "EDI · carrier APIs"),
    ("Supervisory data", "Sort & route control"), ("PLC programming", "PLC programming"),
    ("Business users", "Business users"), ("Hist. replica", "Report replica"), ("ERP (HQ)", "WMS (cloud)"),
    ("MES broker", "WMS broker"), ("SFT + scan", "EDI gateway"), ("SCADA · Hist.", "WCS · WES"),
    ("Cell & safety detail", "Area & safety detail"), ("Inside the cell/area and safety zones", "Inside the automation and safety zones"),
    ("F13–F16 · inside the cell and safety panel on the right →", "F13–F16 · inside the automation and safety panel on the right →"),
    ("Same VLAN / L2 ring inside the cell — never routed, never crosses a firewall.",
     "Same VLAN / L2 ring inside the area — never routed, never crosses a firewall."),
    ("F15 · cell ⇄ cell produced/consumed tags (CIP 44818 / UDP 2222) — exception rule on PA-450 only, per tag pair, documented in the register.",
     "F15 · inbound ⇄ sorter handoff tags (CIP 44818 / UDP 2222) — exception rule on PA-450 only, per tag pair, documented in the register."),
    ("Historian / HMI\nOT-OPS · CELLxx", "WCS / HMI\nOT-OPS · CELLxx"),
    ("SIS logic solver", "Safety PLC"), ("SIS EWS\nlocal only", "Safety eng. WS\nlocal only"),
    ("SIS gateway lives on the PA-450 (ae2.590), so every packet to or from the SIS is policy-checked. No remote path to the SIS EWS — vendor and remote sessions (F04/F05) stop at cell assets.",
     "The safety gateway lives on the PA-450 (ae2.590), so every packet to or from the safety PLC is policy-checked. No remote path to the safety engineering WS — vendor and remote sessions (F04/F05) stop at conveyor and sorter assets."),
    # Failover
    ("Failover scenarios — how the S01 design behaves when something breaks",
     "Failover scenarios — how the S01 design behaves when something breaks during peak"),
    ("Remote-support path (F04): internet → IT-CORE → PA-450-01 (active) → OT-CORE → cell ring → PLC.",
     "Remote-support path (F04): internet → IT-CORE → PA-450-01 (active) → OT-CORE → sorter ring → PLC."),
    ("Control inside a cell (HMI ⇄ PLC ⇄ I/O) is never routed — unaffected.",
     "Control inside an area (HMI ⇄ PLC ⇄ I/O) is never routed — the sorter keeps sorting; WCS sort decisions pause."),
    ("Power off FW-01 during a continuous ping + OPC UA read", "Power off FW-01 during a continuous ping + a WCS sort test"),
    ("None for OT.", "None for the floor."), ("so REP opens the ALT port and the cell now reaches member 2",
                                               "so REP opens the ALT port and the area now reaches member 2"),
    ("other cells are separate segments and see nothing.", "other areas are separate segments and see nothing."),
    ("Production continues", "Floor keeps moving"),
    ("Cells, OT-OPS, the IDMZ and the PA-450 are all local, so production and local IT ⇄ IDMZ exchange keep running.",
     "Conveyors, the sorter, OT-OPS, the IDMZ and the PA-450 are all local, so automation and local exchange keep running."),
    ("Lost until the link returns: HQ apps, central RA-VPN and vendor access, SIEM forwarding (forwarder buffers), ERP ⇄ MES (broker queues).",
     "Lost until the link returns: the cloud WMS (handhelds stop picking), carrier label APIs, central RA-VPN and vendor access, SIEM forwarding (forwarder buffers)."),
    ("Disable both WAN circuits; confirm OT AD/DNS/NTP are local and buffers are big enough.",
     "Disable both WAN circuits; confirm OT AD/DNS/NTP are local, WCS buffers sort decisions and labels pre-print."),
    # Multi-site
    ("Multi-site overview — every plant is a copy of the S01 template", "Multi-site overview — every building is a copy of the S01 template"),
    ("so a WAN outage never stops production.", "so a WAN outage never stops the conveyors."),
    ("Enterprise historian (L4)", "Cloud WMS (L4)"),
    ("L3.5 · IDMZ · RD Gateway · SRA broker · patch/AV relay · historian replica · MES broker · SFT",
     "L3.5 · IDMZ · RD Gateway · SRA broker · patch/AV relay · report replica · WMS broker · EDI"),
    ("L2–L0 · Cells & safety", "L2–L0 · Automation & safety"),
    ("Cross-site OT data goes up through the site IDMZ to the enterprise historian (L4).",
     "Cross-site data goes up through the site IDMZ to the cloud WMS (L4)."),
    ("Plant A", SITE_NAME), ("Plant B", "Northgate Cross-Dock"), ("Plant C", "Lakeside Returns"),
    ("3 + SIS", "3 + safety"), ("2 + SIS", "2 + safety"),
    # Flow register
    ("IDMZ RDG → OT jump → cell", "IDMZ RDG → OT jump → area"), ("PA-450: IT⇄IDMZ, IDMZ⇄OT-OPS, OT-OPS⇄CELL", "PA-450: IT⇄IDMZ, IDMZ⇄OT-OPS, OT-OPS⇄CELL"),
    ("OT-OPS historian / IT users", "OT-OPS WCS / IT users"), ("IDMZ replica", "IDMZ report replica"),
    ("HQ ERP / OT-OPS MES", "Cloud WMS / OT-OPS WCS"), ("IDMZ MES broker", "IDMZ WMS broker"),
    ("IT users / OT eng WS", "Carriers · clients / WMS"), ("IDMZ SFT", "IDMZ EDI gateway"),
    ("AV / CDR scan, quarantine", "Partner allow-list, API keys, schema check"),
    ("OT-OPS historian / SCADA HMI", "OT-OPS WCS / HMI"), ("OT-OPS SCADA / historian", "OT-OPS WCS / WES"), ("App-ID, read where possible", "App-ID, WCS service accounts"),
    ("CELLxx I/O · drives", "CELLxx I/O · drives · scanners"),
    ("Cell ⇄ cell tags", "Inbound ⇄ sorter handoff"), ("SIS read-only gateway", "Safety read-only gateway"),
    ("SIS read-only", "Safety read-only"), ("Historian / HMI", "WCS / HMI"),
    ("OT-OPS / CELL / SIS", "OT-OPS / CELL / SAFETY"), ("Cell ⇄ cell direct", "Area ⇄ area direct"),
    ("SIS write / engineering", "Safety write / engineering"), ("Local SIS EWS only", "Local safety eng. WS only"),
    ("2. Add a cell — copy a CELL container", "2. Add an automation area — copy a CELL container"),
    ("CELLxx ⇄ CELLyy is F15 (exception) only.", "CELLxx ⇄ CELLyy is F15 (inbound ⇄ sorter handoff) only."),
    ("OT / plant eng.", "OT / controls eng."), ("Plant eng.", "Controls eng."),
    ("One zone per line / utility", "One zone per conveyor, sorter or dock system"),
    ("Process safety", "Machine safety"),
    ("S01-IT-CORE-1 · S01-FW-ITOT-01 · S01-C02-IE03 · S01-SAF-SW01", "S01-IT-CORE-1 · S01-FW-ITOT-01 · S01-C02-IE03 · S01-SAF-SW01"),
    ("Cell02 floor · CP-201 · DIN", "Sorter mezzanine · CP-201 · DIN"),
    # Legend and NetBox sheet
    ("Safety system (SIS)", "Safety system"), ("SIS controller", "Safety PLC"), ("SIS switch", "Safety switch"),
    ("devices tagged zone-it-ent … zone-safety", "devices tagged zone-it-ent … zone-safety"),
    ("Remote I/O · drive", "Remote I/O · conveyor drive"),
    # Leftovers: one word at a time, last.
    ("SIS EWS", "Safety eng. WS"), ("SIS\nisolated", "SAFETY\nisolated"),
    ("SIS-SW01", "SAF-SW01"), ("VLAN 590 = L2 only", "VLAN 590 = L2 only"),
    ("· CELL01–03 · SIS", "· CELL01–03 · SAFETY"), ("+ SIS 590", "+ SAFETY 590"), ("(SIS)", "(safety)"),
]

# Words split by the template's own markup (a bold heading, a grey subtitle).
HTML = [
    ("HQ apps, central RA-VPN and vendor access",
     "the cloud WMS (handhelds stop picking), carrier label APIs, central RA-VPN and vendor access"),
    ("· Line 1 — Assembly", "· Inbound — receiving conveyor"),
    ("· Line 2 — Packaging", "· Sortation — cross-belt sorter · AMRs"),
    ("· Utilities (air · boilers · BMS)", "· Dock & yard — doors · levelers · gate"),
    ("Email, ERP and HQ systems · remote employees · equipment vendors",
     "Email, ERP, cloud WMS and carriers · remote employees · equipment vendors"),
    ("between operations and every production line", "between operations and every automation area"),
    ("checks everything going into or out of the plant", "checks everything going onto or off the warehouse floor"),
    ("Production lines</span></b> — each line is its own sealed zone",
     "Automation areas</span></b> — each system is its own sealed zone"),
    ("· HMI / SCADA", "· HMI · WCS client"), ("<b>L0</b> · I/O · drives", "<b>L0</b> · I/O · drives · scanners"),
    ("<b>OT address plan</b>", "<b>Floor address plan</b>"), ("<b>Add a cell</b>", "<b>Add an automation area</b>"),
    ("CELL01 · Line 1 — Assembly  <span", "CELL01 · Inbound conveyor  <span"),
    ("CELL02 · Line 2 — Packaging  <span", "CELL02 · Sortation & AMRs  <span"),
    ("CELL03 · Utilities  <span", "CELL03 · Dock & yard  <span"),
    ("CELL02 · Line 2 — Packaging <span", "CELL02 · Sortation <span"), ("AGV workgroup bridges", "AMR workgroup bridges"),
    ("CELL03 ext. · Pump house", "CELL03 ext. · Gate house"), ("SIS · Safety zone", "SAFETY · Safety zone"),
    ("<b>AGV PLC</b>", "<b>AMR controller</b>"),
    ("· cell ⇄ cell produced/consumed tags", "· inbound ⇄ sorter handoff tags"),
    ("· historian replica · MES broker · SFT", "· report replica · WMS broker · EDI"),
    ("<b>SIS</b>", "<b>SAFETY</b>"),
]

# Values that are a whole cell's text: replaced only when the cell says exactly this.
EXACT = {
    "Plant": "Floor", "Machines": "Automation", "SIS": "SAFETY", "MES": "WCS", "Historian": "WCS", "File transfer": "EDI · carrier APIs",
    "VFDs": "Gate", "Production hall": "Pick aisles", "SIS logic solver": "Safety PLC",
}

WIRELESS_ID = re.compile(r"(?<![A-Za-z0-9-])W0([1-9])(?![0-9])")
SITE_CODE = re.compile(r"(?<![A-Za-z0-9])S0([1-3])(?![0-9])")


# Cells the word lists can't reach, by id: the flows a warehouse runs on that a plant
# doesn't. F21 (central OT services, optional) becomes handhelds to the WMS, F09's lane
# starts at the carriers, and the zone matrix gains F21.
BY_ID = {
    "overview-c29": {"value": '<b><span style="font-size:15px">Keeps moving offline</span></b><br>Conveyors and the sorter keep running if the internet drops. Handheld picking needs the cloud WMS, so its link has a second circuit.'},
    "flows-c90": {"recolor": True},
    "flows-c91": {"value": "Handhelds → WMS"},
    "flows-c170": {"value": "Handhelds", "recolor": True, "parent": "flows-L5"},
    "flows-c171": {"value": "WMS broker", "y": "569", "recolor": True, "parent": "flows-L5"},
    "flows-e172": {"value": "HTTPS 443", "recolor": True, "parent": "flows-L5"},
    "flows-c142": {"value": "Carriers · clients", "y": "322"},
    "flows-c144": {"value": "WCS"},
    "register-c200": {"value": "Handhelds → WMS"},
    "register-c201": {"value": "OT-OPS · RF-HANDHELD"},
    "register-c202": {"value": "IDMZ WMS broker → cloud WMS"},
    "register-c203": {"value": "HTTPS 443"},
    "register-c204": {"value": "PA-450 (OT-OPS ⇄ IDMZ)"},
    "register-c205": {"value": "EAP-TLS device, WMS user login"},
    "register-c206": {"value": "Allow"},
    "register-c334": {"value": "—"},
    "register-c337": {"value": "F06–F10 · F21"},
    # Northgate is a small Cisco cross-dock with one dock area, as its NetBox export has it.
    "multisite-c45": {"value": "<b>Cisco build</b>"},
    "multisite-c50": {"value": "<b>L4 · IT-ENT / GUEST</b><br>W02-IT-CORE · C9500 · C9300 IDF stack · VRF CORP / GUEST"},
    "multisite-c55": {"value": "<b>L3 · OT-OPS / OT-MGMT</b><br>W02-OT-CORE · C9300 · one VRF per zone"},
    "multisite-c59": {"value": '<b>CELL03</b><br><span style="font-size:9px;color:#64748B">Dock · IE3400 · REP</span>'},
    "multisite-c60": {"value": '<b>SAFETY</b><br><span style="font-size:9px;color:#64748B">planned · no zone yet</span>'},
    "multisite-c61": {"delete": True},
    "multisite-c121": {"value": "1 (dock)"},
    "multisite-c122": {"value": "Cisco"},
    "multisite-c123": {"value": "Built"},
    # The 60 GHz radios' link interface is ath0, as NetBox has it; their channels and the AMR's SSID.
    "hardware-c259": {"value": '<b>ath0</b><br><span style="font-size:9px">RF60</span>'},
    "hardware-c1044": {"value": "PTP-AX-A ath0"},
    "hardware-c1046": {"value": "PTP-AX-B ath0"},
    "wireless-c409": {"value": "60 GHz ch 2 + 5 GHz backup"},
    "wireless-c217": {"value": "Floor, cold store, yard APs"},
    "wireless-c226": {"value": "AP-C02-01 · 02"},
    "wireless-c253": {"value": "Pick aisles · dock · cold store · yard"},
    "wireless-c254": {"value": "PT-W01-OT (WH-SCAN, WH-IOT)"},
    "wireless-c258": {"value": "AP-OT-01 … 03 · CS-01 · YD-01"},
    "wireless-c265": {"value": "AP-C02-01 · 02"},
    "wireless-c420": {"value": "5 GHz ch 151 · 40 MHz"},
    "wireless-c85": {"subs": [("on AP-C02-01 so", "on AP-C02-01 and -02 so")]},
    "wireless-c108": {"subs": [("between cell APs only; no WH-SCAN or IT SSID on this AP.",
                                "between the two cell APs only, so one AP can fail; no WH-SCAN or IT SSID on them.")]},
    "wireless-e99": {"attrs": {"ssid": "C02-AMR", "status": "connected", "auth_type": "wpa-enterprise",
                               "interface_a": "W01-AP-C02-01:radio1", "interface_b": "W01-WGB-AMR-01:radio1",
                               "distance_unit": "", "x_media": "Wi-Fi (WGB)", "x_patch_a": "", "x_patch_b": ""}},
}


# Shapes the plant template doesn't have, cloned from a neighbour: a second sortation AP so
# the AMR fleet survives one AP failing, a freezer-rated AP in the cold store, an outdoor AP
# on the dock apron, and their cells on the AP placement plan. Each entry: page, source id,
# new id, text replacements, then attribute and geometry overrides.
AP_DESC = {
    "W01-AP-C02-02": "AP · CELL02 · AMR aisle, second AP · FlexConnect (local switching) · W01-OT-WLC",
    "W01-AP-CS-01": "AP · cold store (−30 °C) · freezer-rated, heater on · Local · W01-OT-WLC",
    "W01-AP-YD-01": "AP · outdoor · dock apron and trailer yard · WH-SCAN only · Local · W01-OT-WLC",
}
CLONES = [
    ("wireless", "wireless-c89", "wireless-c89b", [("AP-C02-01", "AP-C02-02"), ("A-02-01", "A-02-02")],
     {"description": AP_DESC["W01-AP-C02-02"], "serial": "FOC2719LLM2"}, {"y": "1192"}),
    ("wireless", "wireless-e97", "wireless-e97b", [("AP-C02-01", "AP-C02-02"), ("W01-CBL-100", "W01-CBL-101"),
                                                 ("GigabitEthernet1/5", "GigabitEthernet1/6"), ("Gi1/5", "Gi1/6"),
                                                 ("exitY=0.5000", "exitY=0.8000"), ("wireless-c89", "wireless-c89b")], {}, {}),
    ("wireless", "wireless-c73", "wireless-c73b", [("AP-OT-03", "AP-CS-01"), ("A-OT-03", "A-OT-04"), ("Dock doors", "Cold store")],
     {"description": AP_DESC["W01-AP-CS-01"], "serial": "FOC2730CQ6A"}, {"x": "82", "width": "100"}),
    ("wireless", "wireless-e82", "wireless-e82b", [("AP-OT-03", "AP-CS-01"), ("W01-CBL-099", "W01-CBL-102"),
                                                 ("W01-OT-ACC-01-1:GigabitEthernet1/0/2", "W01-OT-ACC-01-2:GigabitEthernet2/0/3"),
                                                 ("Gi1/0/2", "Gi2/0/3"),
                                                 ("wireless-c73", "wireless-c73b")], {}, {}),
    ("wireless", "wireless-c73", "wireless-c73c", [("AP-OT-03", "AP-YD-01"), ("A-OT-03", "A-OT-05"), ("Dock doors", "Dock apron")],
     {"description": AP_DESC["W01-AP-YD-01"], "serial": "FOC2730CQ7B"}, {"x": "187", "width": "100"}),
    ("wireless", "wireless-e82", "wireless-e82c", [("AP-OT-03", "AP-YD-01"), ("W01-CBL-099", "W01-CBL-103"),
                                                 ("GigabitEthernet1/0/2", "GigabitEthernet1/0/4"), ("Gi1/0/2", "Gi1/0/4"),
                                                 ("wireless-c73", "wireless-c73c")], {}, {}),
    # The placement plan: the second sortation cell overlapping the first, the cold store, the yard.
    ("wireless", "wireless-c145", "wireless-c145b", [], {}, {"x": "712", "y": "1500", "width": "92", "height": "92"}),
    ("wireless", "wireless-c146", "wireless-c146b", [], {}, {"x": "745", "y": "1533"}),
    ("wireless", "wireless-c147", "wireless-c147b", [("C02-01", "C02-02")], {}, {"x": "715", "y": "1560"}),
    ("wireless", "wireless-c116", "wireless-c116b", [("CELL01 · Inbound conveyor", "Cold store")], {}, {"y": "1610", "width": "84", "height": "116"}),
    ("wireless", "wireless-c124", "wireless-c124b", [], {}, {"x": "356", "y": "1646", "width": "70", "height": "70"}),
    ("wireless", "wireless-c125", "wireless-c125b", [], {}, {"x": "378", "y": "1664"}),
    ("wireless", "wireless-c126", "wireless-c126b", [("OF-01", "CS-01")], {}, {"x": "348", "y": "1691"}),
    ("wireless", "wireless-c116", "wireless-c116c", [("CELL01 · Inbound conveyor", "Dock apron · trailer yard (outdoor)")], {},
     {"x": "60", "y": "1896", "width": "820", "height": "40"}),
    ("wireless", "wireless-c151", "wireless-c151c", [], {}, {"x": "520", "y": "1899", "width": "150", "height": "34"}),
    ("wireless", "wireless-c125", "wireless-c125c", [], {}, {"x": "552", "y": "1903"}),
    ("wireless", "wireless-c126", "wireless-c126c", [("OF-01", "YD-01")], {}, {"x": "578", "y": "1909", "width": "60"}),
]
LABEL_AT = {"wireless-e82b": "-0.45", "wireless-e82c": "-0.45"}
GROWN = {"wireless-c84": {"x": "76", "width": "614"},
         "wireless-c145": {"x": "630", "y": "1500", "width": "92", "height": "92"},
         "wireless-c146": {"x": "663", "y": "1533"}, "wireless-c147": {"x": "633", "y": "1560"}}


# The SSID table's row for the operations IoT SSID: the columns NetBox has no field for.
IOT_ROW = ["WH-IOT", "WPA2-PSK · MPSK, one key per device class", "W01-OT-WLC", "360 WH-IOT · 10.101.60.0/24",
           "OT-OPS", "Central (local mode)", "2.4 · 5 GHz", "Floor and cold store APs"]

# Wireless flows the plant has no rows for: the IoT SSID's devices, voice picking on WH-SCAN, and the handheld filter.
FLOW_ROWS = [
    ["WF07", "Printers · scales", "WH-IOT · VLAN 360", "WCS · print broker · VLAN 310", "TCP 9100 · HTTPS 443",
     "OT-CORE · VRF OT-OPS ACL", "Intra-zone"],
    ["WF08", "Voice picking", "WH-SCAN terminals · VLAN 350", "Voice server · VLAN 310", "Vendor ports · WMM voice",
     "OT-CORE · Vlan350 inbound ACL", "Intra-zone"],
    ["WF09", "Handhelds to OT hosts", "WH-SCAN · VLAN 350", "Eng. 320 · jump hosts 340", "Any",
     "OT-CORE · Vlan350 inbound ACL", "Deny"],
]

# The operations IoT VLAN on the logical page, between the handhelds and the transit.
IOT_VLAN = ["360", "WH-IOT", "10.101.60.0/24", "OT-CORE .1 · OT-OPS"]


def _insert_row(diagram: ET.Element, parents: dict, after: str, new: str, values: list[str], below: list[str],
                note: str) -> None:
    """A row in the middle of a table: the rows under it move down, the note under the table gives up the room."""
    cells = {e.get("id"): (e.find("mxCell") if e.tag == "object" else e) for e in diagram.iter() if e.get("id")}
    height = float(cells[after].find("mxGeometry").get("height"))
    for row in below:
        g = cells[row].find("mxGeometry")
        g.set("y", f"{float(g.get('y')) + height:g}")
    table = cells[after].get("parent")
    g = cells[table].find("mxGeometry")
    g.set("height", f"{float(g.get('height')) + height:g}")
    g = cells[note].find("mxGeometry")
    g.set("y", f"{float(g.get('y')) + height:g}")
    g.set("height", f"{float(g.get('height')) - height:g}")
    _add_row(diagram, parents, after, new, values)


def _grow(diagram: ET.Element, table: str, card: str, delta: float) -> None:
    """Make room for added rows: the table and its card grow, and the column below moves down.

    Edges move too (their points are absolute); the title block at the page foot stays.
    """
    cells = {e.get("id"): (e.find("mxCell") if e.tag == "object" else e) for e in diagram.iter() if e.get("id")}
    tg = cells[table].find("mxGeometry")
    x_from, bottom = float(tg.get("x")) - 30, float(tg.get("y")) + float(tg.get("height"))
    for cell in cells.values():
        if cell is None or not (cell.get("parent") or "").startswith(diagram.get("id") + "-L"):
            continue
        geo = cell.find("mxGeometry")
        if geo is None:
            continue
        if cell.get("edge") == "1":
            points = list(geo.iter("mxPoint"))
            if points and all(float(p.get("x", 0)) >= x_from and float(p.get("y", 0)) >= bottom for p in points):
                for p in points:
                    p.set("y", f"{float(p.get('y')) + delta:g}")
        elif float(geo.get("x", 0)) >= x_from and bottom - 1 <= float(geo.get("y", 0)) < 1850:
            geo.set("y", f"{float(geo.get('y')) + delta:g}")
    for i in (table, card):
        g = cells[i].find("mxGeometry")
        g.set("height", f"{float(g.get('height')) + delta:g}")


# The AP register's rows for the APs the plant template doesn't have.
AP_ROWS = [
    ["W01-AP-C02-02", "IW9167EH", "CELL02 · AMR aisle", "FlexConnect", "C02-IE02 Gi1/6", "CBL-101", "Rugged injector",
     "W01-OT-WLC", "‹serial›"],
    ["W01-AP-CS-01", "IW9167EH", "Cold store (−30 °C)", "Local", "OT-ACC-01-2 Gi2/0/3", "CBL-102", "802.3at",
     "W01-OT-WLC", "‹serial›"],
    ["W01-AP-YD-01", "IW9167EH", "Dock apron · yard", "Local", "OT-ACC-01-1 Gi1/0/4", "CBL-103", "802.3at",
     "W01-OT-WLC", "‹serial›"],
]


def _add_row(diagram: ET.Element, parents: dict, after: str, new: str, values: list[str]) -> None:
    row = next(e for e in diagram.iter("mxCell") if e.get("id") == after)
    twin = copy.deepcopy(row)
    twin.set("id", new)
    geo = twin.find("mxGeometry")
    geo.set("y", f"{float(geo.get('y')) + float(geo.get('height')):g}")
    holder = parents[row]
    at = list(holder).index(row) + 1
    holder.insert(at, twin)
    cells = [e for e in holder if (e.find("mxCell") if e.tag == "object" else e) is not None
             and (e.find("mxCell") if e.tag == "object" else e).get("parent") == after]
    cells.sort(key=lambda e: float((e.find("mxCell") if e.tag == "object" else e).find("mxGeometry").get("x")))
    for n, (cell, value) in enumerate(zip(cells, values)):
        c = copy.deepcopy(cell)
        c.set("id", f"{new}-{n}")
        inner = c.find("mxCell") if c.tag == "object" else c
        inner.set("parent", new)
        if c.tag == "object":
            c.set("label", value)
            for key in ("link", "tooltip"):
                c.attrib.pop(key, None)
        else:
            c.set("value", value)
        at += 1
        holder.insert(at, c)


def _entries(diagram: ET.Element, switch: str) -> None:
    """Point each AP's cable at the switch straight above it, or at its side for APs to its left."""
    cells = {e.get("id"): e for e in diagram.iter() if e.get("id")}
    geo = lambda i: (cells[i].find("mxCell") if cells[i].tag == "object" else cells[i]).find("mxGeometry")
    sx, sw = float(geo(switch).get("x")), float(geo(switch).get("width"))
    for el in cells.values():
        cell = el.find("mxCell") if el.tag == "object" else el
        if cell is None or cell.get("target") != switch or cell.get("source") not in cells:
            continue
        g = geo(cell.get("source"))
        centre = float(g.get("x")) + float(g.get("width")) / 2
        # APs left of the switch come in at its left side, the outer one higher.
        entry = (f"entryX={(centre - sx) / sw:.4f};entryY=1.0000" if centre > sx
                 else f"entryX=0.0000;entryY={0.3 if centre < sx - 150 else 0.7:.4f}")
        style = re.sub(r"entryX=[0-9.]+;entryY=[0-9.]+", entry, cell.get("style"))
        cell.set("style", style)


def _clone(diagram: ET.Element, parents: dict, src: str, new: str, swaps, attrs, geo) -> None:
    orig = next(e for e in diagram.iter() if e.get("id") == src)
    twin = copy.deepcopy(orig)
    for el in twin.iter():
        for key, value in list(el.attrib.items()):
            for old, rep in swaps:
                value = value.replace(old, rep)
            el.set(key, value)
    twin.set("id", new)
    for key, value in attrs.items():
        twin.set(key, value)
    g = twin.find(".//mxGeometry")
    for key, value in geo.items():
        g.set(key, value)
    holder = parents[orig]
    holder.insert(list(holder).index(orig) + 1, twin)
    # The edge's port labels hang off it by id.
    for child in [c for c in diagram.iter("mxCell") if c.get("parent") == src and c.get("id")]:
        label = copy.deepcopy(child)
        label.set("id", child.get("id") + new[-1])
        label.set("parent", new)
        for old, rep in swaps:
            label.set("value", (label.get("value") or "").replace(old, rep))
        if new in LABEL_AT:  # a port pill that would sit on the switch: move it down the AP's riser
            label.find("mxGeometry").set("x", LABEL_AT[new])
        holder.append(label)


def _is_layer(el: ET.Element) -> bool:
    cell = el if el.tag == "mxCell" else el.find("mxCell")
    return cell is not None and cell.get("parent") == "0"


def rewrite(text: str) -> str:
    # The wireless sheet numbers its flows W01-W06; here W01 is the site, so they become WF01-WF06.
    text = WIRELESS_ID.sub(r"WF0\1", text)
    # The gate-house radio's data port is eth0, as its faceplate and cable notes already say.
    text = re.sub(r"\blan0\b", "eth0", text)
    if text in EXACT:
        return EXACT[text]
    for old, new in NAMES + HTML + WORDS:
        if old == new:
            continue
        if old in text:
            text = text.replace(old, new)
        elif "\n" in old:
            # A heading and its subtitle drawn as separate runs: replace line by line.
            olds, news = old.split("\n"), new.split("\n")
            if len(olds) == len(news) and all(o in text for o in olds):
                for o, n in zip(olds, news):
                    text = text.replace(o, n, 1)
    # The site codes last: S01 is W01 (Riverside DC), S02 and S03 its sister sites.
    return SITE_CODE.sub(r"W0\1", text).replace("S{SS}", "W{SS}")


def _html_variants(pairs):
    out = []
    for old, new in pairs:
        if "\n" in old:
            out.append((old.replace("\n", "<br>"), new.replace("\n", "<br>")))
    return out


def transform(src: Path, dst: Path) -> None:
    global WORDS
    WORDS = WORDS + _html_variants(WORDS)
    tree = ET.parse(src)
    doomed = []
    for diagram in tree.getroot().iter("diagram"):
        for el in diagram.iter():
            if _is_layer(el):
                continue
            for key, value in list(el.attrib.items()):
                if key in SKIP or not value:
                    continue
                new = rewrite(value)
                if new != value:
                    el.set(key, new)
            edit = BY_ID.get(el.get("id", ""))
            if edit and edit.get("delete"):
                doomed.append(el)
            elif edit:
                if "value" in edit:
                    el.set("value" if el.get("value") is not None else "label", edit["value"])
                for old, rep in edit.get("subs", []):
                    key = "value" if el.get("value") is not None else "label"
                    assert old in el.get(key), (el.get("id"), old)
                    el.set(key, el.get(key).replace(old, rep))
                for key, value in edit.get("attrs", {}).items():
                    el.set(key, value)
                if edit.get("recolor"):
                    # Into the IT ⇄ OT via IDMZ lane colour and layer, as a plain allow (solid line).
                    style = el.get("style").replace("#475569", "#0D9488").replace("dashed=1;dashPattern=6 4;", "")
                    el.set("style", style)
                if "parent" in edit:
                    el.set("parent", edit["parent"])
                if "y" in edit:
                    geo = el.find(".//mxGeometry")
                    geo.set("y", edit["y"])
    parents = {child: parent for parent in tree.getroot().iter() for child in parent}
    for el in doomed:
        parents[el].remove(el)
    pages = {d.get("id"): d for d in tree.getroot().iter("diagram")}
    for page, src, new, swaps, attrs, geo in CLONES:
        _clone(pages[page], parents, src, new, swaps, attrs, geo)
    for el in tree.getroot().iter():
        if el.get("id") in GROWN:
            g = el.find(".//mxGeometry")
            for key, value in GROWN[el.get("id")].items():
                g.set(key, value)
    parents = {child: parent for parent in tree.getroot().iter() for child in parent}
    _insert_row(pages["logical"], parents, "logical-c187", "logical-c187b", IOT_VLAN, ["logical-c192"], "logical-c206")
    w = pages["wireless"]
    _grow(w, "wireless-c181", "wireless-c179", 26)
    _add_row(w, parents, "wireless-c218", "wireless-c218b", IOT_ROW)
    _grow(w, "wireless-c268", "wireless-c266", 22 * len(AP_ROWS))
    rows = [("wireless-c379", "wireless-c379b", AP_ROWS[0]), ("wireless-c379b", "wireless-c379c", AP_ROWS[1]),
            ("wireless-c379c", "wireless-c379d", AP_ROWS[2])]
    _grow(w, "wireless-c429", "wireless-c427", 24 * len(FLOW_ROWS))
    after = "wireless-c494"
    for suffix, values in zip("bcd", FLOW_ROWS):
        rows.append((after, f"wireless-c494{suffix}", values))
        after = f"wireless-c494{suffix}"
    for after, new, values in rows:
        parents = {child: parent for parent in tree.getroot().iter() for child in parent}
        _add_row(w, parents, after, new, values)
    _entries(pages["wireless"], "wireless-c70")
    tree.write(dst, encoding="utf-8", xml_declaration=False)


def residue(path: Path) -> list[str]:
    """Manufacturing words left in the warehouse template, for a person to look at."""
    words = re.compile(r"\b(plant|production|assembly|packaging|boiler|pump|historian|HIST-R|MES|AGV|OEM|SIS)\b(?!-)", re.I)
    found = set()
    for diagram in ET.parse(path).getroot().iter("diagram"):
        for el in diagram.iter():
            if _is_layer(el):
                continue
            for key, value in el.attrib.items():
                if key not in SKIP and value and words.search(value):
                    found.add(f"{diagram.get('id')}: {value[:140]!r}")
    return sorted(found)


def main() -> None:
    transform(SOURCE, TEMPLATE)
    # The sample export comes from the drawing, as Plant A's does, with Riverside's SSIDs in place of the plant's.
    # Fail loudly if core renames a hook: assigning a missing name would be silently ignored.
    missing = [n for n in ("WLANS", "CARRIES", "RADIOS", "wireless", "audit_evidence") if not hasattr(make_sample, n)]
    assert not missing, f"make_sample no longer has {missing}; update make_warehouse.py"
    make_sample.WLANS, make_sample.CARRIES, make_sample.RADIOS = SAMPLE_WLANS, CARRIES, {}
    plant = make_sample.wireless

    def riverside(root, devices, ids, interfaces, vlans, prefixes):
        nv, np_ = len(vlans), len(prefixes)
        out = plant(root, devices, ids, interfaces, vlans, prefixes)
        del vlans[nv:], prefixes[np_:]  # the plant's extra SSID VLANs; Riverside's are all on the logical page
        return out

    make_sample.wireless = riverside
    make_sample.audit_evidence = audit_evidence
    sys.argv = ["make_sample.py", "--template", str(TEMPLATE), "--site-name", SITE_NAME, "--site-slug", "w01",
                "-o", str(SAMPLE)]
    make_sample.main()
    export = criticality(wireless(json.loads(SAMPLE.read_text())))
    SAMPLE.write_text(json.dumps(export, indent=1) + "\n", "utf-8")
    SMALL.write_text(json.dumps(cross_dock(export), indent=1) + "\n", "utf-8")
    left = residue(TEMPLATE)
    print(f"wrote {TEMPLATE.name}, {SAMPLE.name}, {SMALL.name}; {len(left)} values still use plant words")
    for line in left:
        print("  ", line)


def _iface(iid, device, name, kind, description, rf=None):
    out = {"id": iid, "device": {"id": device["id"], "name": device["name"]}, "name": name,
           "type": {"value": kind}, "enabled": True, "lag": None, "mode": None, "untagged_vlan": None,
           "tagged_vlans": [], "description": description, "vrf": None}
    if rf:
        role, channel, freq, width, power = rf
        out.update({"rf_role": {"value": role, "label": "Access point" if role == "ap" else "Station"},
                    "rf_channel": {"value": channel, "label": channel_label(channel)}, "rf_channel_frequency": freq,
                    "rf_channel_width": width, "tx_power": power})
    return out


def _end(iface):
    return {"id": iface["id"], "name": iface["name"], "device": iface["device"]}


# The site's wireless LANs in make_sample's shape: (ssid, vid, auth, cipher, wlan_security, wlan_eap,
# wlan_switching, wlan_bands, client isolation, portal, description, location scope). No PSK is ever stored here.
SAMPLE_WLANS = [
    ("CORP", 130, "wpa-enterprise", "aes", "wpa3-enterprise", "EAP-TLS", "tunnelled", ["5ghz", "6ghz"], None, "",
     "802.1X EAP-TLS to Corp ISE · office, annex and driver lounge APs", None),
    ("GUEST", 190, "open", None, "owe", "", "tunnelled", ["2.4ghz", "5ghz"], True, "captive",
     "OWE with a captive portal · client isolation · internet only · office APs and the driver lounge", None),
    ("WH-SCAN", 350, "wpa-enterprise", "aes", "wpa3-enterprise", "EAP-TLS", "tunnelled", ["5ghz"], None, "",
     "EAP-TLS · 802.11r/k/v and OKC · 5 GHz only · Vlan350 inbound ACL: DHCP, DNS, WCS, print and the IDMZ WMS broker only · voice picking with WMM voice priority", None),
    ("C02-AMR", 520, "wpa-enterprise", "aes", "wpa3-enterprise", "EAP-TLS", "local", ["5ghz"], None, "",
     "EAP-TLS per workgroup bridge · fixed 5 GHz channels · FlexConnect local switching and local authentication (APs ask the OT RADIUS server, so AMRs rejoin while the controller is down)", None),
    ("WH-IOT", 360, "wpa-personal", "aes", "mpsk", "", "tunnelled", ["2.4ghz", "5ghz"], None, "",
     "One key per device class (MPSK), kept in the controller · label printers and scales (door controllers are wired, in CELL03)", None),
]
# SSIDs each AP group's radios carry (interface.wireless_lans); the first matching prefix wins.
CARRIES = {"W01-AP-OF": ["CORP", "GUEST"], "W01-AP-AX": ["CORP"], "W01-AP-OT": ["WH-SCAN", "WH-IOT"],
           "W01-AP-CS": ["WH-SCAN", "WH-IOT"], "W01-AP-YD": ["WH-SCAN"], "W01-AP-C02": ["C02-AMR"]}
AUTH = {"open": "Open", "wpa-personal": "WPA Personal (PSK)", "wpa-enterprise": "WPA Enterprise"}


CHANNELS = {  # AP -> (2.4 GHz channel, 5 GHz channel, 5 GHz width)
    "W01-AP-OF-01": (1, 36, 40), "W01-AP-OF-02": (6, 44, 40), "W01-AP-OF-03": (11, 149, 40),
    "W01-AP-OF-04": (1, 157, 40), "W01-AP-OF-05": (6, 36, 40), "W01-AP-AX-01": (1, 36, 40),
    "W01-AP-AX-02": (11, 149, 40), "W01-AP-OT-01": (1, 149, 20), "W01-AP-OT-02": (6, 157, 20),
    "W01-AP-OT-03": (11, 165, 20), "W01-AP-CS-01": (6, 153, 20), "W01-AP-YD-01": (1, 161, 20),
}


def wireless(export: dict) -> dict:
    """Riverside DC's Wi-Fi as NetBox holds it: wireless LANs, radio interfaces and wireless links.

    The plant template draws the radios and SSIDs but its sample carries no wireless objects,
    so the PtP and SSID fills had nothing to read.
    """
    devices = {d["name"]: d for d in export["devices"]}
    site = export["site"]
    # Radio interfaces: both ends of each PtP hop, and the sortation AP with the AMR's bridge.
    iid = max(i["id"] for i in export["interfaces"]) + 1
    have = {(i["device"]["name"], i["name"]): i for i in export["interfaces"]}
    radios = [
        ("W01-PTP-AX-A", "ath0", "ieee802.11ad", "→ W01-PTP-AX-B ath0", ("ap", "60g-2-60480-2160", 60480, 2160, 20)),
        ("W01-PTP-AX-B", "eth0", "1000base-t", "→ W01-AX-ACC-01 24", None),
        ("W01-PTP-AX-B", "ath0", "ieee802.11ad", "→ W01-PTP-AX-A ath0", ("station", "60g-2-60480-2160", 60480, 2160, 20)),
        ("W01-PTP-GH-A", "wlan0", "ieee802.11ac", "→ W01-PTP-GH-B wlan0", ("ap", "5g-151-5755-40", 5755, 40, 18)),
        ("W01-PTP-GH-B", "eth0", "1000base-t", "→ W01-C03-GH-SW01 24", None),
        ("W01-PTP-GH-B", "wlan0", "ieee802.11ac", "→ W01-PTP-GH-A wlan0", ("station", "5g-151-5755-40", 5755, 40, 18)),
        ("W01-AP-C02-01", "radio1", "ieee802.11ax", "5 GHz · C02-AMR", ("ap", "5g-36-5180-20", 5180, 20, 14)),
        ("W01-AP-C02-02", "radio1", "ieee802.11ax", "5 GHz · C02-AMR", ("ap", "5g-48-5240-20", 5240, 20, 14)),
        ("W01-WGB-AMR-01", "radio1", "ieee802.11ax", "Workgroup bridge to C02-AMR", ("station", "5g-36-5180-20", 5180, 20, 14)),
    ]
    ends = {}
    for device, name, kind, description, rf in radios:
        iface = have.get((device, name))
        if iface is None:
            iface = _iface(iid, devices[device], name, kind, description)
            export["interfaces"].append(iface)
            have[(device, name)] = iface
            iid += 1
        if rf:
            iface.update(_iface(iface["id"], devices[device], name, kind, description, rf))
        ends[(device, name)] = iface
    link = lambda lid, a, b, ssid, auth, distance, description: {
        "id": lid, "interface_a": _end(ends[a]), "interface_b": _end(ends[b]), "ssid": ssid,
        "status": {"value": "connected", "label": "Connected"},
        "auth_type": {"value": auth, "label": AUTH[auth]}, "auth_cipher": {"value": "aes", "label": "AES"},
        "distance": distance, "distance_unit": {"value": "m", "label": "Meters"} if distance else None,
        "description": description, "tags": []}
    export["wireless_links"] = [
        link(1, ("W01-PTP-AX-A", "ath0"), ("W01-PTP-AX-B", "ath0"), "W01-PTP1", "wpa-personal", 350,
             "Main building mast M1 → annex AX-01 mast M2 · 60 GHz with 5 GHz backup"),
        link(2, ("W01-PTP-GH-A", "wlan0"), ("W01-PTP-GH-B", "wlan0"), "W01-PTP2", "wpa-personal", 600,
             "Dock mast M3 → gate house mast M4"),
        link(3, ("W01-AP-C02-01", "radio1"), ("W01-WGB-AMR-01", "radio1"), "C02-AMR", "wpa-enterprise", None,
             "AMR workgroup bridge association · roams between W01-AP-C02-01 and -02"),
    ]
    # Each AP's radios as the controller last set them: floor APs on non-DFS 5 GHz channels clear of the
    # AMR aisle's pinned 36 and 48, 2.4 GHz on 1, 6 and 11.
    # NetBox names a 40 MHz channel by its centre (36+40 is "38 (5190/40 MHz)") and a 2.4 GHz one at 22 MHz.
    for name, (low, high, width) in CHANNELS.items():
        centre = high + 2 if width == 40 else high
        for port, value, freq, w in (("radio0", f"2.4g-{low}-{2407 + 5 * low}-22", 2407 + 5 * low, 22),
                                     ("radio1", f"5g-{centre}-{5000 + 5 * centre}-{width}", 5000 + 5 * centre, width)):
            have[(name, port)].update(rf_channel={"value": value, "label": channel_label(value)},
                                      rf_channel_frequency=freq, rf_channel_width=w)
    # The annex APs draw 802.3at from AX-ACC-01, the budget the book's PoE rule works from.
    for name in ("W01-AP-AX-01", "W01-AP-AX-02"):
        have[(name, "GigabitEthernet0")]["poe_type"] = {"value": "type2-ieee802.3at", "label": "802.3at (Type 2)"}
    # The radios' wired ports trunk what each hop bridges: the annex's IT VLANs, the gate house's cell and OT mgmt.
    for vids, radios in (((110, 130, 135, 199), ("W01-PTP-AX-A", "W01-PTP-AX-B")),
                         ((390, 530, 531), ("W01-PTP-GH-A", "W01-PTP-GH-B"))):
        for device in radios:
            iface = have.get((device, "eth0"))
            if iface is None:
                iface = _iface(iid, devices[device], "eth0", "1000base-t", "")
                export["interfaces"].append(iface)
                have[(device, "eth0")] = iface
                iid += 1
            iface.update(mode={"value": "tagged", "label": "Tagged"}, tagged_vlans=[{"vid": v} for v in vids])
    # A radio carries only the SSIDs on its band: 2.4 GHz is GUEST and WH-IOT, and the AMR aisle's is off.
    low = {w["id"] for w in export["wireless_lans"] if "2.4ghz" in w["custom_fields"].get("wlan_bands", [])}
    for i in export["interfaces"]:
        if i["name"] == "radio0" and i.get("wireless_lans") is not None:
            i["wireless_lans"] = [w for w in i["wireless_lans"] if w["id"] in low]
            if not i["wireless_lans"]:
                i.update(enabled=False, description="2.4 GHz off · 5 GHz only on the AMR aisle")
    # make_sample wrote the wireless LANs; scope them to the site and name the group after it.
    for w in export["wireless_lans"]:
        w.update(group={"id": 1, "name": "W01-WLAN", "slug": "w01-wlan"}, scope_type="dcim.site",
                 scope_id=site["id"], scope={"id": site["id"], "name": site["name"], "slug": site["slug"]})
    return export


CROSS_DOCK = {"W01-FW-EDGE-01", "W01-IT-CORE-1", "W01-IT-ACC-IDF1-1", "W01-FW-ITOT-01", "W01-OT-CORE-1",
              "W01-C03-IE01", "W01-C03-IE02", "W01-C03-PLC01", "W01-C03-HMI01", "W01-AP-OF-01",
              "W01-WLC-01", "W01-OT-WLC-01", "W01-AP-OT-01", "W01-AP-OT-02"}


# Asset criticality by role: what stops the building is critical, what stops a zone is high, a single AP is medium.
CRITICALITY = {"core-switch": "critical", "firewall": "critical", "hypervisor": "critical", "plc": "critical",
               "sis-switch": "critical", "sis-controller": "critical", "access-point": "medium",
               "workgroup-bridge": "medium"}


def criticality(export: dict) -> dict:
    for d in export["devices"]:
        role = d["role"].get("slug") if isinstance(d.get("role"), dict) else d.get("role")
        d.setdefault("custom_fields", {})["criticality"] = CRITICALITY.get(role, "high")
    return export


# Riverside's rooms: who owns them, how they are locked, the most sensitive data on the gear inside, and
# when someone last walked them against NetBox. The safety room is in safety scope; the IDMZ hypervisor
# carries the WMS-to-ERP inventory postings, so it is in SOX scope.
ROOMS = {  # room -> (owner, custodian, physical access, data classification, last verified)
    "MDF-01": ("Marcus Bell", "DC IT team", "badge-camera", "internal", "2026-09-15"),
    "IDF-1": ("Marcus Bell", "DC IT team", "locked-room", "internal", "2026-09-15"),
    "IDF-2": ("Marcus Bell", "DC IT team", "locked-room", "internal", "2026-09-15"),
    "Office": ("Marcus Bell", "DC IT team", "locked-cabinet", "internal", None),
    "AX-01": ("Marcus Bell", "DC IT team", "locked-cabinet", "internal", "2026-05-06"),
    "AX-01 office": ("Marcus Bell", "DC IT team", "open", "internal", "2026-05-06"),
    "Pick aisles": ("Marcus Bell", "DC IT team", None, "internal", None),
    "Cold store": ("Marcus Bell", "DC IT team", None, "internal", None),
    "Dock apron": ("Marcus Bell", "DC IT team", None, "internal", None),
    "Mast M1": ("Marcus Bell", "DC IT team", "locked-cabinet", None, None),
    "Mast M2": ("Marcus Bell", "DC IT team", "locked-cabinet", None, None),
    "Mast M3": ("Elena Ruiz", "MHE controls team", "locked-cabinet", None, None),
    "Mast M4": ("Elena Ruiz", "MHE controls team", "locked-cabinet", None, None),
    "Controls room": ("Elena Ruiz", "MHE controls team", "badge", "confidential", "2026-07-22"),
    "Receiving": ("Elena Ruiz", "MHE controls team", "locked-cabinet", "confidential", "2026-07-22"),
    "Sorter mezzanine": ("Elena Ruiz", "MHE controls team", "locked-cabinet", "confidential", "2026-07-22"),
    "Dock doors": ("Elena Ruiz", "MHE controls team", "locked-cabinet", "confidential", "2026-07-22"),
    "GH-01": ("Elena Ruiz", "MHE controls team", "locked-cabinet", "confidential", "2026-07-22"),
    "Safety room": ("Tom Becker", "Safety systems team", "badge-camera", "restricted", "2026-08-27"),
}
OT_IN_MDF = {"W01-FW-ITOT-01", "W01-FW-ITOT-02", "W01-IDMZ-SW-01", "W01-IDMZ-HV-01", "W01-OT-CORE-1",
             "W01-OT-CORE-2", "W01-OT-HCI-01", "W01-OT-WLC-01", "W01-OT-WLC-02"}


def audit_evidence(devices):
    """make_sample.audit_evidence for Riverside: rooms, owners and custodians, and dated evidence per device."""
    rooms = sorted({(d.get("location") or {}).get("name") for d in devices.values() if d.get("location")})
    locations, contacts, people = [], [], {}

    def assign(kind, ident, person, role):
        people.setdefault(person, len(people) + 1)
        contacts.append({"id": len(contacts) + 1, "object_type": kind, "object_id": ident,
                         "contact": {"id": people[person], "name": person},
                         "role": {"slug": role, "name": role.replace("-", " ").capitalize()},
                         "priority": {"value": "primary"}})

    assign("dcim.site", 1, "Priya Shah", "asset-owner")
    assign("dcim.site", 1, "DC IT team", "custodian")
    for i, name in enumerate(rooms, start=1):
        owner, custodian, access, data_class, verified = ROOMS[name]
        cf = {k: v for k, v in (("physical_access", access), ("data_classification", data_class),
                                ("last_verified", verified)) if v}
        if name == "Safety room":
            cf["compliance_scope"] = ["safety"]
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        locations.append({"id": i, "name": name, "slug": slug, "parent": None, "custom_fields": cf})
        assign("dcim.location", i, owner, "asset-owner")
        assign("dcim.location", i, custodian, "custodian")
    for name in sorted(OT_IN_MDF):   # OT gear in the IT room belongs to MHE controls
        assign("dcim.device", devices[name]["id"], "Elena Ruiz", "asset-owner")
        assign("dcim.device", devices[name]["id"], "MHE controls team", "custodian")
    devices["W01-IDMZ-HV-01"]["custom_fields"]["compliance_scope"] = ["sox"]
    controllers = ("plc", "hmi", "io", "sis-controller")
    for d in devices.values():
        role, cf, name = d["role"]["slug"], d["custom_fields"], d["name"]
        procurve = "ProCurve" in d["device_type"]["model"]
        if role != "access-point":
            # The sorter HMI's project was last saved off the panel before peak planning started.
            cf["last_config_backup"] = "2026-07-02" if name == "W01-C02-HMI01" else \
                "2026-10-01" if role in controllers else "2026-10-16"
            cf["last_patched"] = "2026-02-04" if procurve else make_sample.PATCHED.get(role, "2026-08-05")
        cf["install_date"] = "2014-06-03" if procurve else make_sample.INSTALLED.get(role, "2023-05-15")
        if cf.get("support_contract"):
            cf["support_contract_end"] = "2025-12-31" if procurve else \
                "2026-12-31" if role == "ptp-radio" else "2027-06-30"
        if role in controllers:
            cf["monitoring"], cf["monitored_by"] = "passive", "OT sensor on the area SPAN port"
            cf["log_forwarding"] = "local"
        if procurve:
            cf["monitoring"] = "polling"
    site_fields = {"monitoring": "alerting", "monitored_by": "LibreNMS", "log_forwarding": "siem",
                   "log_destination": "Corporate SIEM, syslog over TLS", "log_retention_days": 400,
                   "last_verified": "2026-04-14"}
    return locations, contacts, site_fields


def cross_dock(export: dict) -> dict:
    """W02 · Northgate Cross-Dock on day one: one of everything, a dock cell, Wi-Fi, and gaps.

    Some serials, addresses and cable labels are not collected yet and only the
    floor's VLANs are entered, so the drawing shows its plan cards.
    """
    e = copy.deepcopy(export)
    e["devices"] = [d for d in e["devices"] if d["name"] in CROSS_DOCK]
    ids = {d["id"] for d in e["devices"]}
    ends = lambda c: c.get("a_terminations", []) + c.get("b_terminations", [])
    e["cables"] = [c for c in e["cables"] if ends(c) and all(t["object"]["device"]["id"] in ids for t in ends(c))]
    e["interfaces"] = [i for i in e["interfaces"] if i["device"]["id"] in ids]
    e["ip_addresses"] = [i for i in e["ip_addresses"]
                         if ((i.get("assigned_object") or {}).get("device") or {}).get("id") in ids]
    # The floor's VLANs and AP management, plus the three firewall transits (IT, operations, management) and the dock's.
    keep = {110, 130, 135, 190, 191, 310, 350, 390, 392, 395, 399, 530, 531, 539}
    # Interfaces for VLANs and areas Northgate doesn't have (the plant's SVIs, the CELL01, CELL02 and
    # SAFETY firewall sub-interfaces) would otherwise carry addresses with no prefix behind them.
    gone = {f"ae2.{vid}" for vid in (519, 529, 590)}
    unused = lambda name: name in gone or (re.fullmatch(r"Vlan(\d+)", name or "") is not None
                                          and int(name[4:]) not in keep)
    e["interfaces"] = [i for i in e["interfaces"] if not unused(i.get("name"))]
    e["ip_addresses"] = [i for i in e["ip_addresses"] if not unused((i.get("assigned_object") or {}).get("name"))]
    # Modules, bays and inventory items (optics, PSUs, fans) go with their devices, and an optic with its
    # port (one on a cable end the export has no interface row for carries the port's name only).
    kept = {i["id"] for i in e["interfaces"]} | {None}
    e["modules"] = [m for m in e.get("modules", []) if m["device"]["id"] in ids]
    e["module_bays"] = [b for b in e.get("module_bays", []) if b["device"]["id"] in ids]
    e["inventory_items"] = [i for i in e.get("inventory_items", []) if i["device"]["id"] in ids
                            and (i.get("component_type") != "dcim.interface" or i["component"]["id"] in kept)]
    # Rooms and contacts go with the devices that are left; the site's own owner and custodian stay.
    rooms = {(d.get("location") or {}).get("name") for d in e["devices"]}
    e["locations"] = [loc for loc in e.get("locations", []) if loc["name"] in rooms]
    # Only the models still in use: an export lists the device types its devices name.
    models = {d["device_type"].get("id") for d in e["devices"]}
    e["device_types"] = [t for t in e.get("device_types", []) if t["id"] in models]
    room_ids = {loc["id"] for loc in e["locations"]}
    e["contact_assignments"] = [c for c in e.get("contact_assignments", [])
                                if c["object_type"] == "dcim.site"
                                or (c["object_type"] == "dcim.location" and c["object_id"] in room_ids)
                                or (c["object_type"] == "dcim.device" and c["object_id"] in ids)]
    e["vlans"] = [v for v in e["vlans"] if v["vid"] in keep]
    vids = {v["id"] for v in e["vlans"]}
    e["prefixes"] = [p for p in e["prefixes"] if (p.get("vlan") or {}).get("id") in vids]
    e["circuits"] = [c for c in e["circuits"] if c["cid"].endswith("A-01")]
    # Northgate's Wi-Fi: the office and floor SSIDs; no PtP radios and no AMRs.
    e["wireless_links"] = [w for w in e["wireless_links"]
                           if {w["interface_a"]["device"]["id"], w["interface_b"]["device"]["id"]} <= ids]
    e["wireless_lans"] = [w for w in e["wireless_lans"] if w["vlan"]["id"] in vids]
    renumber = {}
    for n, w in enumerate(e["wireless_lans"]):
        renumber[w["id"]] = w["id"] = n + 1
    for i in e["interfaces"]:
        if i.get("wireless_lans"):
            i["wireless_lans"] = [dict(w, id=renumber[w["id"]]) for w in i["wireless_lans"] if w["id"] in renumber]
    # An SVI must sit in its VLAN's prefix; the plant's transit SVIs on the IT core don't, so they go.
    nets = {p["vlan"]["vid"]: ipaddress.ip_network(p["prefix"]) for p in e["prefixes"] if p.get("vlan")}
    svi = lambda i: re.fullmatch(r"Vlan(\d+)", (i.get("assigned_object") or {}).get("name") or "")
    e["ip_addresses"] = [i for i in e["ip_addresses"] if not svi(i) or int(svi(i)[1]) not in nets
                         or ipaddress.ip_interface(i["address"]).ip in nets[int(svi(i)[1])]]
    text = json.dumps(e).replace("W01-", "W02-").replace('"W01"', '"W02"').replace("10.101.", "10.102.").replace("10.1.", "10.2.")
    text = text.replace('"Riverside DC"', '"Northgate Cross-Dock"').replace("10.250.1.", "10.250.2.")
    e = json.loads(text)
    e["site"] = {"id": 2, "name": "Northgate Cross-Dock", "slug": "w02",
                 # Northgate records who watches it but not where its logs go yet.
                 "custom_fields": {"monitoring": "alerting", "monitored_by": "LibreNMS"}}
    for w in e["wireless_lans"]:
        w["group"]["slug"] = "w02-wlan"
        if w["ssid"] == "CORP":
            w["description"] = "802.1X EAP-TLS to Corp ISE · office and driver lounge APs"
    by_name = {d["name"]: d for d in e["devices"]}
    for name in ("W02-C03-PLC01", "W02-C03-HMI01", "W02-AP-OT-02"):
        by_name[name]["serial"] = ""
    # The dock HMI's project was last saved off the panel in July.
    by_name["W02-C03-HMI01"]["custom_fields"]["last_config_backup"] = "2026-07-02"
    # Someone typed a placeholder to get two AP rows through an import: one "serial" on two devices.
    for name in ("W02-AP-OF-01", "W02-AP-OT-01"):
        by_name[name]["serial"] = "TBD"
    for name in ("W02-C03-IE02", "W02-AP-OT-02"):
        by_name[name]["primary_ip4"] = None
        by_name[name]["rack"] = None
    for c in e["cables"][:2]:
        c["label"] = ""
    # The OT core's uplink to the floor controller is fibre, and nobody has recorded the optic in its cage yet.
    e["inventory_items"] = [i for i in e["inventory_items"] if not (
        i["device"]["name"] == "W02-OT-CORE-1" and (i.get("component") or {}).get("name") == "TenGigabitEthernet1/1/3")]
    return e


if __name__ == "__main__":
    main()
