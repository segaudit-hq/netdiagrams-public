"""Alder Bay: the fictional hotel the H01 template is drawn for.

One source for the template's shapes and for the sample NetBox export, so the
two never disagree. The facts follow the book's sample-site sheet
(book8-hospitality/_research/sample-site.md). Addresses are private or
documentation ranges; serials and circuit IDs are placeholders; every company
is fictional, and hotel-specific gear (POS, locks, TV, room controls, building
controllers) is "Generic" so no real hospitality vendor is named.
"""

from __future__ import annotations

SITE = {"code": "H01", "name": "Alder Bay Hotel and Conference Center", "slug": "h01"}
BRANCH = {"code": "H02", "name": "Alder Bay Airport", "slug": "h02"}
OWNER, OPERATOR, BRAND_CO = "Alder Bay Owner LLC", "Kestrel Hospitality", "Larkline Hotels"
HSIA = "Guest Wi-Fi vendor"   # runs the guest gateway; named by role, never by a real company

# Zones: slug, short name, title, band code, what lives there, rule, (fill, stroke, font)
ZONES = [
    ("zone-internet", "INTERNET", "Internet and providers", "OUT",
     "ISP-A, ISP-B, cloud PMS, processor, vendor clouds",
     "Untrusted. Everything ends on the firewall.", ("#F8FAFC", "#CBD5E1", "#475569")),
    ("zone-brand", "BRAND", "Brand and management company", "OUT",
     "Larkline brand router and circuit, Kestrel VPN and SIEM",
     "Partners, not insiders: named systems, named ports.", ("#F5F5FF", "#C7C9F9", "#4F46E5")),
    ("zone-edge", "EDGE", "Firewall pair", "EDGE", "H01-FW-01/02",
     "The one place zones meet.", ("#F1F5F9", "#94A3B8", "#334155")),
    ("zone-payments", "PAYMENTS", "Payments", "BUSINESS",
     "Card terminals (front desk, restaurant, bar, spa, gift shop), POS workstations, POS server, handheld POS on Wi-Fi",
     "Talks to the processor and its own POS server. Posts charges to rooms without card data. Nothing else reaches in.",
     ("#FEF5F5", "#F5B5B5", "#DC2626")),
    ("zone-ops", "OPS", "Hotel operations", "BUSINESS",
     "Front desk and back-office PCs, sales and catering, housekeeping and engineering tablets (AB-STAFF), printers",
     "Reaches the cloud PMS, brand systems and the internet. Never reaches payments.",
     ("#F4F7FE", "#B3C8F8", "#2563EB")),
    ("zone-servers", "SERVERS", "Property servers and interfaces", "BUSINESS",
     "Virtualization hosts: PMS interface server, lock server, call accounting, IPTV middleware VMs",
     "Talks to each vendor system on its named port. The hub everyone forgets to draw.",
     ("#F3FAF9", "#AADAD5", "#0D9488")),
    ("zone-voice", "VOICE", "Voice", "BUSINESS", "Call server, room and admin phones",
     "Talks to the interface server (check-in, wake-up) and the SIP provider.", ("#F2F9FC", "#A6D4EB", "#0284C7")),
    ("zone-guest", "GUEST", "Guests", "GUEST",
     "Guest gateway (run by the Wi-Fi vendor), room and public Wi-Fi, wired room ports",
     "Internet only. Guests can't see each other.", ("#FDF8F3", "#F2CFA8", "#D97706")),
    ("zone-events", "EVENTS", "Meetings and events", "GUEST", "Ballroom and meeting-room event networks",
     "Internet only. One event can't see another.", ("#FEFBEF", "#EBD38E", "#A16207")),
    ("zone-roomtech", "ROOMTECH", "Guest room technology", "GUEST",
     "TV head-end and room TVs, casting devices, room-controls gateway, lock gateways and encoders",
     "Talks to its own servers and vendor clouds. Guests reach only their own room's casting device.",
     ("#F8F5FE", "#D1BAF9", "#7C3AED")),
    ("zone-building", "BUILDING", "Building systems", "BUILDING",
     "BMS supervisor, chiller, boiler and air-handler controllers, kitchen refrigeration monitor, pool controller",
     "Reached only by engineering and the BMS contractor through the VPN. No internet.",
     ("#F4FAF5", "#B4DDBF", "#16A34A")),
    ("zone-safety", "SAFETY", "Safety and security", "BUILDING",
     "NVR and cameras, back-of-house door controller, staff safety-button gateway",
     "Cameras to NVR only. Safety buttons reach their monitoring service only.", ("#FDF4F9", "#F3B8D6", "#DB2777")),
    ("zone-mgmt", "MGMT", "Network management", "BUILDING",
     "Firewall, switch, AP and UPS management; console server",
     "IT and Kestrel only, VPN with MFA.", ("#F0FAFC", "#A5DCE8", "#0891B2")),
]
ZONE = {z[0]: z for z in ZONES}

BANDS = [
    ("OUT", "OUTSIDE · INTERNET, BRAND & VENDORS", ("internet", "isp", "wan", "cloud", "brand", "vendor", "remote")),
    ("EDGE", "EDGE · FIREWALL PAIR", ("edge", "dmz", "vpn", "perimeter")),
    ("BUSINESS", "PAYMENTS & HOTEL OPERATIONS", ("payments", "pay", "pos", "cde", "ops", "staff", "office", "servers",
                                                 "interfaces", "voice", "corp")),
    ("GUEST", "GUESTS, EVENTS & ROOMS", ("guest", "hsia", "events", "event", "meeting", "roomtech", "room", "iptv")),
    ("BUILDING", "BUILDING, SAFETY & MANAGEMENT", ("building", "bms", "plant", "safety", "security", "cameras",
                                                    "mgmt", "oob")),
]

FW = "FW HA .1"
GW = "GW-01 .1"
# VLANs: vid, name, zone, subnet, gateway text. The guest-side VLANs route on the guest gateway, not the firewall.
# Firewall ports with no VLAN behind them: the line, the brand handoff and the guest gateway's outside leg.
FW_ADDRESSES = [("H01-FW-01", "wan1", "203.0.113.2/29", "zone-internet"),
                ("H01-FW-01", "brand", "10.40.250.1/29", "zone-brand"),
                ("H01-FW-01", "dmz-guest", "10.40.251.1/29", "zone-guest")]

VLANS = [
    (10, "OPS-WIRED", "zone-ops", "10.40.10.0/24", FW),
    (11, "OPS-WIFI", "zone-ops", "10.40.11.0/24", FW),
    (20, "PAY-TERMINALS", "zone-payments", "10.40.20.0/26", FW),
    (21, "POS", "zone-payments", "10.40.21.0/26", FW),
    (22, "PAY-WIFI", "zone-payments", "10.40.22.0/27", FW),
    (30, "SERVERS", "zone-servers", "10.40.30.0/26", FW),
    (40, "VOICE", "zone-voice", "10.40.40.0/24", FW),
    (60, "IPTV", "zone-roomtech", "10.40.60.0/23", FW),
    (61, "CASTING", "zone-roomtech", "10.40.62.0/24", FW),
    (62, "ROOM-CONTROLS", "zone-roomtech", "10.40.63.0/24", FW),
    (63, "LOCKS", "zone-roomtech", "10.40.64.0/26", FW),
    (70, "BMS", "zone-building", "10.40.70.0/26", FW),
    (72, "KITCHEN-POOL", "zone-building", "10.40.72.0/27", FW),
    (80, "CAMERAS", "zone-safety", "10.40.80.0/25", FW),
    (81, "DOOR-ACCESS", "zone-safety", "10.40.81.0/27", FW),
    (82, "STAFF-SAFETY", "zone-safety", "10.40.82.0/27", FW),
    (99, "NET-MGMT", "zone-mgmt", "10.40.99.0/24", FW),
    (100, "GUEST", "zone-guest", "172.20.0.0/21", GW),
    (101, "GUEST-WIRED", "zone-guest", "172.20.8.0/24", GW),
    (110, "EVENTS", "zone-events", "172.20.12.0/23", GW),
] + [(110 + n, f"EVENT-{n}", "zone-events", f"172.20.14.{(n - 1) * 32}/27", GW) for n in range(1, 9)]
EVENT_VLANS = tuple(range(111, 119))

# H02, the select-service sister: no restaurant (a market pantry POS), one firewall, its own brand router and gateway.
BRANCH_VLANS = [
    (10, "OPS", "zone-ops", "10.41.10.0/24", "FW-01 .1"), (20, "PAY", "zone-payments", "10.41.20.0/26", "FW-01 .1"),
    (40, "VOICE", "zone-voice", "10.41.40.0/24", "FW-01 .1"), (60, "IPTV", "zone-roomtech", "10.41.60.0/24", "FW-01 .1"),
    (63, "LOCKS", "zone-roomtech", "10.41.64.0/26", "FW-01 .1"), (70, "BMS", "zone-building", "10.41.70.0/26", "FW-01 .1"),
    (80, "CAMERAS", "zone-safety", "10.41.80.0/25", "FW-01 .1"), (99, "NET-MGMT", "zone-mgmt", "10.41.99.0/24", "FW-01 .1"),
    (100, "GUEST", "zone-guest", "172.21.0.0/21", "GW-01 .1"),
]

ARUBA, FORTI, DELL, APC, OPEN, AXIS, GEN = (
    "HPE Aruba Networking", "Fortinet", "Dell", "APC", "Opengear", "Axis", "Generic")


# Asset criticality by role (the sample sheet's list): what stops for the hotel when the box fails. Two additions
# the sheet doesn't rate: the brand router (high: reservations and loyalty ride on it) and the elevator monitor
# (low: it is on its own cellular, not the hotel network). The plant splits by device: chillers and boilers high,
# air handlers, the kitchen monitor and the pool controller medium.
CRITICALITY = {"firewall": "critical", "core-switch": "critical", "hypervisor": "critical", "pos-server": "critical",
               "guest-gateway": "critical",
               "access-switch": "high", "call-server": "high", "lock-gateway": "high", "key-encoder": "high",
               "bms-server": "high", "building-controller": "high", "ups": "high", "safety-gateway": "high",
               "router": "high",
               "access-point": "medium", "tv-headend": "medium", "room-controls": "medium", "nvr": "medium",
               "door-controller": "medium", "console-server": "medium",
               "printer": "low", "camera": "low", "payment-terminal": "low", "pos-terminal": "low",
               "elevator-monitor": "low"}
CRITICALITY_BY_NAME = {"AHU": "medium", "KIT": "medium", "POOL": "medium"}


def _dev(name, role, mfr, model, platform, location, rack, pos, ip, zone, desc, serial, tag, vc="", vcpos="",
         sw="", contract="", modules="", power="", status="active", tenant=""):
    crit = next((v for k, v in CRITICALITY_BY_NAME.items() if f"-{k}-" in name), CRITICALITY.get(role, ""))
    return {"name": name, "role": role, "manufacturer": mfr, "device_type": model, "platform": platform,
            "location": location, "rack": rack, "position": pos, "primary_ip4": ip, "tags": zone,
            "description": desc, "serial": serial, "asset_tag": tag, "virtual_chassis": vc, "vc_position": vcpos,
            "status": status, "cf_sw_version": sw, "cf_support_contract": contract,
            "cf_lifecycle": "In support" if contract else "", "x_modules": modules, "x_power": power,
            "cf_ap_mode": "cloud" if role == "access-point" else "", "cf_criticality": crit, "tenant": tenant}


CORE_MODULES = "24× SFP+ · 4× SFP56 · VSF on {m}/1/27–28"
ACC_MODULES = "48× 1G Class 4 PoE (740 W) · 4× SFP+"
DEVICES = [
    _dev("H01-FW-01", "firewall", FORTI, "FortiGate 200G", "fortios", "MDF-LL", "R01", "40", "10.40.99.2/24",
         "zone-edge", "Property firewall, every zone's gateway (HA primary)", "FGxxxxxxxxxx01", "AB-0001",
         sw="FortiOS 7.4.x", contract="FortiCare 24x7",
         modules="x1–x2 SFP+ (DAC to core) · wan1, wan2 · brand · dmz-guest · ha", power="2× AC PSU"),
    _dev("H01-FW-02", "firewall", FORTI, "FortiGate 200G", "fortios", "MDF-LL", "R02", "40", "10.40.99.3/24",
         "zone-edge", "Property firewall (HA secondary)", "FGxxxxxxxxxx02", "AB-0002",
         sw="FortiOS 7.4.x", contract="FortiCare 24x7",
         modules="x1–x2 SFP+ (DAC to core) · wan1, wan2 · brand · dmz-guest · ha", power="2× AC PSU"),
    _dev("H01-BRAND-RTR-01", "router", GEN, "Brand-managed router", "", "MDF-LL", "R01", "42", "10.40.250.2/29",
         "zone-brand", f"Owned and managed by {BRAND_CO} (brand); the hotel has no login. Ends circuit H01-BRAND-01, "
         "hands off to the firewall port 'brand'", "BRxxxxxx01", "", sw="Brand image",
         modules="wan · lan1, lan2", power="1× AC", tenant=BRAND_CO),
    _dev("H01-GW-01", "guest-gateway", GEN, "Guest gateway GW-2000", "", "MDF-LL", "R02", "42", "10.40.99.6/24",
         "zone-guest", f"Owned and run by the {HSIA.lower()} under contract: portal, room billing, bandwidth tiers. "
         "Gateway for VLANs 100, 101, 110-118; outside leg on the firewall port 'dmz-guest'", "GWxxxxxx01", "",
         sw="Vendor image", contract="Wi-Fi vendor managed service",
         modules="wan1–wan2 1G · lan1–lan2 SFP+ (DAC to core)", power="2× AC PSU", tenant=HSIA),
    _dev("H01-OOB-01", "console-server", OPEN, "OM1204-4E-L", "opengear", "MDF-LL", "R01", "41", "10.40.99.5/24",
         "zone-mgmt", "Out-of-band console with cellular", "OMxxxxxx01", "AB-0003", sw="Opengear 24.x",
         modules="4× serial (FW-01, FW-02, CORE-1, CORE-2) · LTE", power="2× DC"),
    _dev("H01-CORE-1", "core-switch", ARUBA, "CX 6300M 24SFP+", "aos-cx", "MDF-LL", "R01", "38", "10.40.99.10/24",
         "zone-mgmt", "Core stack member 1 (conductor)", "SGxxxxxx11", "AB-0010", "H01-CORE", "1",
         sw="AOS-CX 10.13.x", contract="Foundation Care NBD", modules=CORE_MODULES.format(m=1), power="2× JL086A"),
    _dev("H01-CORE-2", "core-switch", ARUBA, "CX 6300M 24SFP+", "aos-cx", "MDF-LL", "R02", "38", "",
         "zone-mgmt", "Core stack member 2 (standby)", "SGxxxxxx12", "AB-0011", "H01-CORE", "2",
         sw="AOS-CX 10.13.x", contract="Foundation Care NBD", modules=CORE_MODULES.format(m=2), power="2× JL086A"),
]
# Access stacks: one per closet. Lower level on DAC in the MDF; floor 1 and the guest floors on OM4 up the riser.
STACKS = [("LL", "MDF-LL", "R02", 2, 20), ("F1", "IDF-1", "CAB-1", 3, 21)] + [
    (f"F{f}", f"IDF-{f}", f"CAB-{f}", 2, 20 + f) for f in range(2, 7)]
for key, closet, rack, members, ip in STACKS:
    where = "Lower level" if key == "LL" else f"Floor {key[1:]}"
    for n in range(1, members + 1):
        DEVICES.append(_dev(
            f"H01-ACC-{key}-{n}", "access-switch", ARUBA, "CX 6200F 48G Class4 PoE", "aos-cx", closet, rack,
            str((36 if key == "LL" else 12) - n), f"10.40.99.{ip}/24" if n == 1 else "", "zone-mgmt",
            f"{where} access stack member {n}" + (" (conductor)" if n == 1 else ""), f"CNxxxxx{key}{n}",
            f"AB-0{ip}{n}", f"H01-ACC-{key}", str(n), sw="AOS-CX 10.13.x", contract="Foundation Care NBD",
            modules=ACC_MODULES + ("" if key == "LL" else " · 10G-SR up the riser"), power="1× 740 W PSU"))
DEVICES += [
    _dev("H01-HV-01", "hypervisor", DELL, "PowerEdge R660xs", "", "MDF-LL", "R01", "30", "10.40.30.11/26",
         "zone-servers", "Host 1: PMS interface server, lock server VMs", "SVCTAGxx01", "AB-0040",
         sw="Hypervisor 8.0", contract="ProSupport NBD", modules="2× 10G SFP+ (DAC) · iDRAC 10.40.99.31",
         power="2× 700 W"),
    _dev("H01-HV-02", "hypervisor", DELL, "PowerEdge R660xs", "", "MDF-LL", "R02", "30", "10.40.30.12/26",
         "zone-servers", "Host 2: call accounting, IPTV middleware VMs (and the failover copies)", "SVCTAGxx02",
         "AB-0041", sw="Hypervisor 8.0", contract="ProSupport NBD", modules="2× 10G SFP+ (DAC) · iDRAC 10.40.99.32",
         power="2× 700 W"),
    _dev("H01-POS-SRV-01", "pos-server", GEN, "POS server 1U", "", "MDF-LL", "R01", "26", "10.40.21.10/26",
         "zone-payments", "Restaurant, bar, spa and gift shop POS server", "PSxxxxxx01", "AB-0042",
         sw="POS 12.x", contract="POS vendor support", modules="2× 1G RJ45", power="1× 350 W"),
    _dev("H01-PBX-01", "call-server", GEN, "Hospitality call server", "", "MDF-LL", "R01", "24", "10.40.40.10/24",
         "zone-voice", "Call server: room and admin phones, wake-up calls, SIP trunk H01-SIP-01", "PBxxxxxx01",
         "AB-0043", sw="Call server 9.x", contract="Voice vendor support", modules="2× 1G RJ45", power="1× 300 W"),
    _dev("H01-IPTV-01", "tv-headend", GEN, "TV head-end 1U", "", "MDF-LL", "R02", "26", "10.40.60.10/23",
         "zone-roomtech", "TV head-end: channels and guide data to the room TVs", "TVxxxxxx01", "AB-0044",
         sw="Head-end 5.x", contract="TV vendor support", modules="1× 10G SFP+ · 4× tuner", power="2× 400 W"),
    _dev("H01-GRMS-01", "room-controls", GEN, "Room-controls gateway", "", "MDF-LL", "R02", "24", "10.40.63.10/24",
         "zone-roomtech", "Room-controls gateway: thermostats on a wireless mesh, not network devices",
         "RCxxxxxx01", "AB-0045", sw="GRMS 3.x", modules="1× 1G RJ45 · mesh radio", power="1× AC"),
    _dev("H01-UPS-01", "ups", APC, "Smart-UPS SRT 5000", "", "MDF-LL", "R01", "1", "10.40.99.41/24",
         "zone-mgmt", "Rack R01 UPS (network card)", "ASxxxxxx01", "AB-0050", modules="NMC3 network card",
         power="5 kVA · about 25 min at today's load"),
    _dev("H01-UPS-02", "ups", APC, "Smart-UPS SRT 5000", "", "MDF-LL", "R02", "1", "10.40.99.42/24",
         "zone-mgmt", "Rack R02 UPS (network card)", "ASxxxxxx02", "AB-0051", modules="NMC3 network card",
         power="5 kVA · about 30 min at today's load"),
    _dev("H01-NVR-01", "nvr", AXIS, "S3016", "", "MDF-LL", "R02", "20", "10.40.80.10/25", "zone-safety",
         "Video recorder for 16 cameras", "AXxxxxxx01", "AB-0060", modules="32 TB"),
    _dev("H01-DOOR-01", "door-controller", AXIS, "A1601", "", "Security office", "", "", "10.40.81.10/27",
         "zone-safety", "Back-of-house door controller (dock, kitchen, plant, MDF)", "AXxxxxxx02", "AB-0061"),
    _dev("H01-SAFE-01", "safety-gateway", GEN, "Staff safety-button gateway", "", "Security office", "", "",
         "10.40.82.10/27", "zone-safety", "Staff safety buttons: alerts to the monitoring service", "SBxxxxxx01",
         "AB-0062"),
    _dev("H01-BMS-01", "bms-server", GEN, "BMS supervisor", "", "Central plant", "", "", "10.40.70.10/26",
         "zone-building", "Building management supervisor (engineering's workstation server)", "BMxxxxxx01",
         "AB-0070", sw="BMS 4.x", contract="BMS contractor service"),
] + [
    _dev(f"H01-{kind}-{n:02d}", "building-controller", GEN, model, "", "Central plant", "", "",
         f"10.40.70.{base + n}/26", "zone-building", f"{what} {n} controller", f"{kind[:2]}xxxxxx{n:02d}", "")
    for kind, model, what, base, count in (("CHLR", "Chiller controller", "Chiller", 20, 2),
                                           ("BLR", "Boiler controller", "Boiler", 22, 2),
                                           ("AHU", "Air-handler controller", "Air handler", 30, 4))
    for n in range(1, count + 1)
] + [
    _dev("H01-KIT-01", "building-controller", GEN, "Refrigeration monitor", "", "Kitchen", "", "", "10.40.72.10/27",
         "zone-building", "Kitchen refrigeration and freezer monitor", "KMxxxxxx01", ""),
    _dev("H01-POOL-01", "building-controller", GEN, "Pool controller", "", "Central plant", "", "", "10.40.72.11/27",
         "zone-building", "Pool chemistry and pump controller", "PLxxxxxx01", ""),
    # On its own cellular modem to the elevator company: recorded, with no network link (planned decision).
    _dev("H01-ELEV-01", "elevator-monitor", GEN, "Elevator monitoring unit", "", "Lower level", "", "", "",
         "zone-building", "Elevator company's remote monitoring, own cellular modem; not on the hotel network. "
         "Planned: decide whether it belongs on the network", "ELxxxxxx01", ""),
    _dev("H01-ENC-01", "key-encoder", GEN, "Key encoder", "", "Front desk", "", "", "10.40.64.21/26", "zone-roomtech",
         "Front desk key encoder 1", "KExxxxxx01", ""),
    _dev("H01-ENC-02", "key-encoder", GEN, "Key encoder", "", "Front desk", "", "", "10.40.64.22/26", "zone-roomtech",
         "Front desk key encoder 2", "KExxxxxx02", ""),
    _dev("H01-PRN-FD-01", "printer", GEN, "Laser printer", "", "Front desk", "", "", "10.40.10.31/24", "zone-ops",
         "Front desk printer (folios, registration cards)", "PRxxxxxx01", ""),
    _dev("H01-PRN-BO-01", "printer", GEN, "Laser printer", "", "Floor 1", "", "", "10.40.10.32/24", "zone-ops",
         "Back-office printer", "PRxxxxxx02", ""),
    _dev("H01-PRN-KIT-01", "printer", GEN, "Kitchen ticket printer", "", "Kitchen", "", "", "10.40.21.30/26",
         "zone-payments", "Kitchen ticket printer (POS VLAN 21)", "PRxxxxxx03", ""),
]
for floor in range(2, 7):
    DEVICES.append(_dev(f"H01-LOCKGW-F{floor}", "lock-gateway", GEN, "Lock gateway", "", f"IDF-{floor}", "", "",
                        f"10.40.64.{10 + floor}/26", "zone-roomtech",
                        f"Floor {floor} lock gateway; the room locks talk to it over a low-power radio",
                        f"LGxxxxxx0{floor}", ""))
PAYMENTS = [("PT-FD", 3, "payment-terminal", "Card terminal (P2PE)", "Front desk", 10, 20),
            ("POS-RST", 2, "pos-terminal", "POS terminal 15in", "Restaurant", 20, 21),
            ("POS-BAR", 1, "pos-terminal", "POS terminal 15in", "Bar", 22, 21),
            ("POS-SPA", 1, "pos-terminal", "POS terminal 15in", "Spa", 23, 21),
            ("POS-GIFT", 1, "pos-terminal", "POS terminal 15in", "Floor 1", 24, 21),
            ("PT-RST", 2, "payment-terminal", "Card terminal (P2PE)", "Restaurant", 20, 20),
            ("PT-SPA", 1, "payment-terminal", "Card terminal (P2PE)", "Spa", 30, 20)]
PLACE = {"PT-FD": "Front desk", "POS-RST": "Tidewater Grill", "POS-BAR": "Bar", "POS-SPA": "Spa",
         "POS-GIFT": "Gift shop", "PT-RST": "Tidewater Grill", "PT-SPA": "Spa"}
for key, count, role, model, room, base, vid in PAYMENTS:
    for n in range(1, count + 1):
        DEVICES.append(_dev(f"H01-{key}-{n:02d}", role, GEN, model, "", room, "", "",
                            f"10.40.{vid}.{base + n}/26", "zone-payments",
                            f"{PLACE[key]} {'card terminal' if role == 'payment-terminal' else 'POS workstation'} {n}",
                            f"{key.replace('-', '')[:5]}xx{n:02d}", ""))
for n in range(1, 17):
    DEVICES.append(_dev(f"H01-CAM-{n:02d}", "camera", AXIS, "P3268-LV", "", "Lower level" if n <= 8 else "Floor 1",
                        "", "", f"10.40.80.{20 + n}/25", "zone-safety",
                        "Back-of-house camera" if n <= 8 else "Public-area camera", f"AXCAMxx{n:02d}", ""))

# Access points: in-room wall plates on the guest floors (one every other room), ceiling APs elsewhere.
AP_AREAS = {"LL": ["Kitchen", "Laundry", "Engineering shop", "Security office"],
            "F1": ["Lobby and front desk", "Tidewater Grill", "Bar", "Spa", "Ballroom A", "Ballroom B", "Ballroom C",
                   "Ballroom pre-function", "Meeting rooms 1-3", "Meeting rooms 4-6"]}
_ap_ip = iter(range(101, 255))
for key, areas in [("LL", AP_AREAS["LL"]), ("F1", AP_AREAS["F1"])] + [
        (f"F{f}", [f"Rooms {f}{2 * k - 1:02d}-{f}{2 * k:02d}" for k in range(1, 17)]) for f in range(2, 7)]:
    guest_floor = key not in ("LL", "F1")
    for n, area in enumerate(areas, 1):
        DEVICES.append(_dev(f"H01-AP-{key}-{n:02d}", "access-point", ARUBA, "AP-503H" if guest_floor else "AP-635",
                            "aos-ap", "Lower level" if key == "LL" else f"Floor {key[1:]}", "", "",
                            f"10.40.99.{next(_ap_ip)}/24", "zone-mgmt",
                            f"{area} {'wall-plate' if guest_floor else 'ceiling'} AP",
                            f"CNAP{key}{n:02d}", ""))

BRANCH_DEVICES = [
    _dev("H02-FW-01", "firewall", FORTI, "FortiGate 120G", "fortios", "MDF", "R01", "40", "10.41.99.2/24",
         "zone-edge", "Property firewall (single)", "FGxxxxxxxx21", "AB-2001", sw="FortiOS 7.4.x",
         contract="FortiCare 8x5"),
    _dev("H02-BRAND-RTR-01", "router", GEN, "Brand-managed router", "", "MDF", "R01", "42", "10.41.250.2/29",
         "zone-brand", f"Owned and managed by {BRAND_CO} (brand); the hotel has no login", "BRxxxxxx21", "",
         tenant=BRAND_CO),
    _dev("H02-GW-01", "guest-gateway", GEN, "Guest gateway GW-1000", "", "MDF", "R01", "36", "10.41.99.6/24",
         "zone-guest", f"Owned and run by the {HSIA.lower()}", "GWxxxxxx21", "", tenant=HSIA),
    _dev("H02-CORE-1", "core-switch", ARUBA, "CX 6300F 48G Class4 PoE", "aos-cx", "MDF", "R01", "38", "10.41.99.10/24",
         "zone-mgmt", "Core switch", "SGxxxxxx21", "AB-2010", sw="AOS-CX 10.13.x"),
    _dev("H02-POS-01", "pos-terminal", GEN, "POS terminal 15in", "", "Market pantry", "", "", "10.41.20.21/26",
         "zone-payments", "Market pantry POS workstation", "POSxx21", ""),
    _dev("H02-PT-FD-01", "payment-terminal", GEN, "Card terminal (P2PE)", "", "Front desk", "", "", "10.41.20.11/26",
         "zone-payments", "Front desk card terminal", "PTFDxx21", ""),
    _dev("H02-PBX-01", "call-server", GEN, "Hospitality call server", "", "MDF", "R01", "24", "10.41.40.10/24",
         "zone-voice", "Call server", "PBxxxxxx21", ""),
    _dev("H02-LOCKGW-01", "lock-gateway", GEN, "Lock gateway", "", "MDF", "", "", "10.41.64.11/26", "zone-roomtech",
         "Lock gateway (all floors)", "LGxxxxxx21", ""),
    _dev("H02-AP-01", "access-point", ARUBA, "AP-503H", "aos-ap", "Floor 1", "", "", "10.41.99.101/24", "zone-mgmt",
         "Lobby and market AP", "CNAPH201", ""),
    _dev("H02-AP-02", "access-point", ARUBA, "AP-503H", "aos-ap", "Floor 2", "", "", "10.41.99.102/24", "zone-mgmt",
         "Floor 2 corridor AP", "CNAPH202", ""),
]


# Links: label(s), A ends, B ends, type, color, speed, media, VLANs (tagged), name
def _cable(labels, a, b, ctype, color, speed, media, vlans="", lag=""):
    return {"labels": labels, "a": a, "b": b, "type": ctype, "color": color, "speed": speed, "media": media,
            "vlans": vlans, "lag": lag}


INSIDE = ", ".join(str(v[0]) for v in VLANS if v[4] == FW)          # what the firewall trunks to the core
GUEST_SIDE = ", ".join(str(v) for v in (100, 101, 110) + EVENT_VLANS)  # what the guest gateway trunks
AP_VLANS = (11, 61, 100)                     # tagged on every AP port, native 99
F1_AP_VLANS = AP_VLANS + (22, 110) + EVENT_VLANS  # floor 1 also: AB-PAY and the events pool broadcast there only


def _trunk(*vids) -> str:
    return ", ".join(str(v) for v in sorted(set(vids)))


FLOOR_TRUNK = {"LL": _trunk(10, 11, 21, 61, 70, 72, 80, 81, 82, 99, 100),
               "F1": _trunk(10, 11, 20, 21, 22, 61, 63, 80, 99, 100, 101, 110, *EVENT_VLANS)}
for _f in range(2, 7):
    FLOOR_TRUNK[f"F{_f}"] = _trunk(11, 40, 60, 61, 63, 99, 100, 101)

CABLES = [
    _cable(["H01-CBL-00001", "H01-CBL-00002"], ["H01-FW-01:x1", "H01-FW-01:x2"],
           ["H01-CORE-1:1/1/1", "H01-CORE-2:1/1/1"], "dac-passive", "111111", "2×10G", "DAC", INSIDE, "Po1"),
    _cable(["H01-CBL-00003", "H01-CBL-00004"], ["H01-FW-02:x1", "H01-FW-02:x2"],
           ["H01-CORE-1:1/1/2", "H01-CORE-2:1/1/2"], "dac-passive", "111111", "2×10G", "DAC", INSIDE, "Po2"),
    _cable(["H01-CBL-00005"], ["H01-FW-01:ha"], ["H01-FW-02:ha"], "cat6", "9e9e9e", "1G", "Cat6", "", "HA"),
    _cable(["H01-CBL-00006"], ["H01-BRAND-RTR-01:lan1"], ["H01-FW-01:brand"], "cat6", "673ab7", "1G", "Cat6", "",
           "BRAND1"),
    _cable(["H01-CBL-00007"], ["H01-BRAND-RTR-01:lan2"], ["H01-FW-02:brand"], "cat6", "673ab7", "1G", "Cat6", "",
           "BRAND2"),
    _cable(["H01-CBL-00008"], ["H01-FW-01:dmz-guest"], ["H01-GW-01:wan1"], "cat6", "ff9800", "1G", "Cat6", "",
           "DMZ1"),
    _cable(["H01-CBL-00009"], ["H01-FW-02:dmz-guest"], ["H01-GW-01:wan2"], "cat6", "ff9800", "1G", "Cat6", "",
           "DMZ2"),
    _cable(["H01-CBL-00010", "H01-CBL-00011"], ["H01-CORE-1:1/1/3", "H01-CORE-2:1/1/3"],
           ["H01-GW-01:lan1", "H01-GW-01:lan2"], "dac-passive", "111111", "2×10G", "DAC", GUEST_SIDE, "Po3"),
]
# Access stack uplinks: Po11 lower level (DAC), Po12-Po17 floors 1-6 (OM4 up the riser), one member each end.
for n, (key, closet, rack, members, _) in enumerate(STACKS):
    fibre = key != "LL"
    CABLES.append(_cable([f"H01-CBL-{21 + 2 * n:05d}", f"H01-CBL-{22 + 2 * n:05d}"],
                         [f"H01-CORE-1:1/1/{11 + n}", f"H01-CORE-2:1/1/{11 + n}"],
                         [f"H01-ACC-{key}-1:1/1/49", f"H01-ACC-{key}-{members}:1/1/49"],
                         "mmf-om4" if fibre else "dac-passive", "00bcd4" if fibre else "111111", "2×10G",
                         "MMF OM4" if fibre else "DAC", FLOOR_TRUNK[key], f"Po{11 + n}"))
CABLES += [
    _cable(["H01-CBL-00041", "H01-CBL-00042"], ["H01-CORE-1:1/1/21", "H01-CORE-2:1/1/21"],
           ["H01-HV-01:nic1", "H01-HV-01:nic2"], "dac-passive", "111111", "2×10G", "DAC", "30", "Po21"),
    _cable(["H01-CBL-00043", "H01-CBL-00044"], ["H01-CORE-1:1/1/22", "H01-CORE-2:1/1/22"],
           ["H01-HV-02:nic1", "H01-HV-02:nic2"], "dac-passive", "111111", "2×10G", "DAC", "30", "Po22"),
    _cable(["H01-CBL-00045"], ["H01-CORE-2:1/1/23"], ["H01-IPTV-01:eth0"], "dac-passive", "111111", "10G", "DAC"),
    # 1G drops on the core: copper SFPs, in the rack beside what they serve.
    _cable(["H01-CBL-00046"], ["H01-CORE-1:1/1/18"], ["H01-POS-SRV-01:eth0"], "cat6", "e91e63", "1G", "Cat6"),
    _cable(["H01-CBL-00047"], ["H01-CORE-2:1/1/18"], ["H01-PBX-01:eth0"], "cat6", "2196f3", "1G", "Cat6"),
    _cable(["H01-CBL-00048"], ["H01-CORE-1:1/1/19"], ["H01-GRMS-01:eth0"], "cat6", "2196f3", "1G", "Cat6"),
    _cable(["H01-CBL-00049"], ["H01-CORE-1:1/1/24"], ["H01-UPS-01:nmc"], "cat6", "2196f3", "1G", "Cat6"),
    _cable(["H01-CBL-00050"], ["H01-CORE-2:1/1/24"], ["H01-UPS-02:nmc"], "cat6", "2196f3", "1G", "Cat6"),
    _cable(["H01-CBL-00051"], ["H01-CORE-1:1/1/20"], ["H01-OOB-01:net1"], "cat6", "2196f3", "1G", "Cat6"),
]
INFRA_CABLES = len(CABLES)   # the link register lists these; end-device drops are in NetBox and the AP register

# The access VLAN of each end device's switch port (APs trunk: native 99, tagged AP_VLANS).
ACCESS_VLAN = {"payment-terminal": 20, "pos-terminal": 21, "pos-server": 21, "printer": 10, "key-encoder": 63,
               "lock-gateway": 63, "room-controls": 62, "tv-headend": 60, "call-server": 40, "bms-server": 70,
               "building-controller": 70, "camera": 80, "nvr": 80, "door-controller": 81, "safety-gateway": 82,
               "ups": 99, "console-server": 99}
ACCESS_VLAN_BY_NAME = {"H01-PRN-KIT-01": 21, "H01-KIT-01": 72, "H01-POOL-01": 72,
                       "H02-POS-01": 20}  # H02 has one PAY VLAN for terminals and the POS


def access_vlan(name: str, role: str):
    return ACCESS_VLAN_BY_NAME.get(name, ACCESS_VLAN.get(role))


# Which stack each end device hangs off: its closet's floor.
def _stack_of(d: dict) -> str:
    loc = d["location"]
    if loc in ("MDF-LL", "Lower level", "Central plant", "Kitchen", "Security office"):
        return "LL"
    if loc.startswith("IDF-"):
        return f"F{loc[4:]}"
    if loc.startswith("Floor "):
        return f"F{loc[6:]}"
    return "F1"   # front desk, restaurant, bar, spa


MEMBERS = {key: members for key, _, _, members, _ in STACKS}
_port: dict[str, int] = {}
_drop = iter(range(101, 2000))
DROP_ROLES = ("access-point", "printer", "camera", "nvr", "door-controller", "safety-gateway", "bms-server",
              "building-controller", "key-encoder", "lock-gateway", "payment-terminal", "pos-terminal")
for d in DEVICES:
    if d["role"] not in DROP_ROLES or d["role"] == "elevator-monitor" or d["name"] == "H01-ELEV-01":
        continue
    key = _stack_of(d)
    n = _port[key] = _port.get(key, 0) + 1
    members = MEMBERS[key]
    member, iface = (n - 1) % members + 1, f"1/1/{(n - 1) // members + 1}"
    ap = d["role"] == "access-point"
    CABLES.append(_cable([f"H01-CBL-{next(_drop):05d}"], [f"H01-ACC-{key}-{member}:{iface}"], [f"{d['name']}:eth0"],
                         "cat6a" if ap else "cat6", "2196f3", "1G", "Cat6A" if ap else "Cat6",
                         _trunk(*(F1_AP_VLANS if key == "F1" else AP_VLANS), 99) if ap else ""))

# A stack member's ports carry its member number (AOS-CX VSF): H01-CORE-2's first port is 2/1/1.
_MEMBER = {d["name"]: int(d["vc_position"]) for d in DEVICES if d["vc_position"]}


def _member_port(end: str) -> str:
    dev, port = end.split(":", 1)
    if _MEMBER.get(dev, 1) > 1 and port.startswith("1/1/"):
        port = f"{_MEMBER[dev]}/1/{port[4:]}"
    return f"{dev}:{port}"


for _c in CABLES:
    _c["a"], _c["b"] = [_member_port(e) for e in _c["a"]], [_member_port(e) for e in _c["b"]]

CIRCUITS = [
    {"cid": "H01-ISP-A-01", "provider": "Provider A", "type": "Dedicated internet access", "speed": "1G",
     "handoff": "H01-FW-01:wan1, H01-FW-02:wan1", "media": "Cat6", "label": "DIA 1G · fiber"},
    {"cid": "H01-ISP-B-01", "provider": "Provider B", "type": "Business cable", "speed": "1G/50M",
     "handoff": "H01-FW-01:wan2, H01-FW-02:wan2", "media": "Cat6", "label": "Cable 1G/50M · guest traffic prefers it"},
    {"cid": "H01-BRAND-01", "provider": BRAND_CO, "type": "Brand-managed broadband", "speed": "200M",
     "handoff": "H01-BRAND-RTR-01:wan", "media": "Cat6", "label": "Brand broadband 200M · the brand's, not the hotel's"},
    {"cid": "H01-SIP-01", "provider": "SIP provider", "type": "SIP trunk", "speed": "",
     "handoff": "H01-PBX-01 (logical, over ISP-A)", "media": "", "label": "SIP trunk over ISP-A (logical)"},
]

# SSIDs: name, security, VLAN, zone, note. Never a key: who holds it and how it rotates, that's all.
SSIDS = [
    ("ALDERBAY-GUEST", "Open + portal · client isolation", 100, "zone-guest",
     "Room and public areas; portal checks room number and last name against the PMS; per-room device limit"),
    ("ALDERBAY-EVENTS", "WPA2/WPA3-Personal · per-event key", 110, "zone-events",
     "Ballroom and meeting rooms only; event VLANs 111-118 assigned per booking"),
    ("AB-STAFF", "WPA3-Enterprise · EAP-TLS", 11, "zone-ops", "Front office, housekeeping and engineering tablets"),
    ("AB-PAY", "WPA3-Enterprise · EAP-TLS", 22, "zone-payments",
     "Handheld POS in the restaurant and bar only; broadcast on floor 1 APs only"),
    ("AB-ROOMTECH", "WPA3-Personal · key per device type", 61, "zone-roomtech",
     "Casting devices behind the room TVs; hidden"),
]
# Where each SSID is broadcast: AP name prefixes (the sample's radios carry only these).
SSID_ON = {"ALDERBAY-GUEST": ("H01-AP-F",), "ALDERBAY-EVENTS": tuple(f"H01-AP-F1-{n:02d}" for n in range(5, 11)),
           "AB-STAFF": ("H01-AP-",), "AB-PAY": ("H01-AP-F1-",),
           "AB-ROOMTECH": tuple(f"H01-AP-F{f}-" for f in range(2, 7))}

BRANCH_SSIDS = [
    ("ALDERBAY-GUEST", "Open + portal · client isolation", 100, "zone-guest", "Rooms and lobby; same portal as H01"),
    ("AB-STAFF", "WPA3-Enterprise · EAP-TLS", 10, "zone-ops", "Front desk and housekeeping tablets"),
]

# Flows: id, from, to, what, verdict, conditions, owner (the sample sheet's F01-F29).
FLOWS = [
    ("F01", "Card terminals", "Payment processor", "Card authorization (P2PE) · TLS", "Allow",
     "Processor's published ranges only", "F&B director / front office"),
    ("F02", "POS workstations", "POS server", "Checks, menus, tickets", "Allow", "Inside zone-payments",
     "F&B director"),
    ("F03", "POS server", "Payment processor and POS vendor cloud", "Settlement · menu and reporting sync", "Allow",
     "Named destinations", "F&B director"),
    ("F04", "POS server", "PMS interface server", "Post to room (room number, amount, check number; no card data)",
     "Conditional", "One port, one direction", "IT"),
    ("F05", "Interface server", "Cloud PMS", "PMS interface link · HTTPS", "Allow", "Brand-mandated PMS endpoint", "IT"),
    ("F06", "Interface server", "Lock server, call server, TV head-end, guest gateway",
     "Check-in, check-out, room moves, keys, wake-up, guest name, Wi-Fi login", "Conditional",
     "One named port per system", "IT"),
    ("F07", "Hotel operations", "Cloud PMS, brand systems", "PMS, reservations, loyalty · HTTPS", "Allow",
     "Via brand circuit for brand systems", "Front office manager"),
    ("F08", "Guests", "Internet", "Web", "Allow", "Bandwidth by room tier · DNS filter", "Wi-Fi vendor"),
    ("F09", "Guests, events", "Any internal zone", "Anything", "Deny", "Logged", "IT"),
    ("F10", "Guests", "Their room's casting device", "Casting", "Conditional",
     "Paired by room through the casting service; expires at check-out", "IT"),
    ("F11", "Events", "Internet", "Event traffic", "Allow", "One VLAN per booking; event-to-event denied",
     "Sales and catering"),
    ("F12", "Room technology", "TV and room-controls vendor clouds", "Content, guide data, controls", "Conditional",
     "Named destinations", "IT"),
    ("F13", "Lock server", "Lock vendor cloud", "Mobile key issue and revoke · HTTPS", "Conditional",
     "One destination", "Front office manager"),
    ("F14", "BMS contractor (remote)", "Building systems", "BMS supervisor web and engineering tools", "Conditional",
     "VPN + MFA · booked window · logged", "Director of engineering"),
    ("F15", "Building systems", "Internet, any other zone", "Anything", "Deny", "Logged", "Director of engineering"),
    ("F16", "Cameras", "NVR", "Video (RTSP)", "Allow", "Inside zone-safety", "Security director"),
    ("F17", "Safety-button gateway", "Monitoring service", "Alerts · HTTPS", "Conditional",
     "One destination; tested monthly", "Security director"),
    ("F18", "Kestrel (VPN)", "Network management, property servers", "SSH, HTTPS, RDP", "Conditional",
     "VPN + MFA · logged", "Kestrel IT"),
    ("F19", "Ops, servers, voice, guests, events, room tech, building, safety", "Payments", "Anything", "Deny", "Logged", "IT"),
    ("F20", "Every zone except guest and events", "Firewall services", "DHCP, DNS, NTP", "Allow",
     "Firewall's own address per VLAN", "IT"),
    ("F21", "APs (management, VLAN 99)", "Cloud Wi-Fi service", "AP management", "Conditional",
     "Provider ranges · APs only", "IT"),
    ("F22", "Network management, firewall", "Kestrel SIEM", "Syslog over TLS", "Conditional", "One destination",
     "Kestrel IT"),
    ("F23", "Call server", "SIP provider", "SIP, RTP", "Allow", "Provider ranges", "IT"),
    ("F24", "Elevator monitoring", "Elevator company", "Remote monitoring over its own cellular",
     "Not on the hotel network", "Drawn as a boundary; reviewed yearly", "Director of engineering"),
    ("F25", "Lock server (property servers)", "Lock gateways and key encoders", "Key encoding, lock audit trails",
     "Conditional", "Lock system's named ports only", "Front office manager"),
    ("F26", "TV middleware (property servers)", "TV head-end", "Guest name, channel line-up, folio view",
     "Conditional", "Named port only", "IT"),
    ("F27", "Ops, guests, events, room tech, building, safety", "Network management", "Anything", "Deny",
     "Logged", "IT"),
    ("F28", "Front office PCs (named, operations)", "Lock server, call accounting (property servers)",
     "Lock client: key issue, room moves · call accounting reports", "Conditional",
     "Named PCs; each vendor's client ports only", "Front office manager"),
    ("F29", "Engineering shop and security office PCs (named, operations)", "BMS supervisor, NVR",
     "BMS supervisor web · video viewing", "Conditional", "Named PCs; web and viewing ports only",
     "Director of engineering / security director"),
]
