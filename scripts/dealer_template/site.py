"""Kestrel Valley Motors: the fictional franchised dealership the D01 template is drawn for.

One source for the template's shapes and for the sample NetBox export, so the
two never disagree. Addresses are private or documentation ranges; serials and
circuit IDs are placeholders. The manufacturer and the DMS vendor stay unnamed:
"the manufacturer", "the DMS vendor".
"""

from __future__ import annotations

SITE = {"code": "D01", "name": "Kestrel Valley Motors", "slug": "d01"}
BRANCH = {"code": "D02", "name": "Kestrel Valley Pre-Owned", "slug": "d02"}

# Zones: slug, short name, title, band code, what lives there, rule, (fill, stroke, font)
ZONES = [
    ("zone-internet", "INTERNET", "Internet, DMS and lenders", "OUT",
     "ISP-A, ISP-B, the hosted DMS, lender portals and credit bureaus, SaaS, the MSP",
     "Untrusted. Everything from here ends on the firewall.", ("#F8FAFC", "#CBD5E1", "#475569")),
    ("zone-edge", "EDGE", "Firewall and remote access", "EDGE", "The firewall HA pair, the DMS tunnel, the VPN pool",
     "The one place zones meet. Every inter-zone packet is inspected here.", ("#F1F5F9", "#94A3B8", "#334155")),
    ("zone-fi", "FI", "Finance and insurance", "DEALS", "F&I desks, the deal-jacket scanner, the F&I printer",
     "Reaches the DMS, the lenders and the bureaus. Wired only; nothing reaches into it.",
     ("#F5F5FE", "#C2C4F6", "#4F46E5")),
    ("zone-sales", "SALES", "Sales floor", "DEALS", "Sales desks, the managers' tower, sales tablets on KV-STAFF",
     "Reaches the DMS, the CRM and the manufacturer's sales portal. Not the credit tools.",
     ("#F4F7FE", "#B3C8F8", "#2563EB")),
    ("zone-office", "OFFICE", "Back office", "DEALS", "Accounting, title clerks, HR, the controller; the deal-jacket NAS",
     "Reaches the DMS, the banks and payroll. The NAS answers office and F&I only.",
     ("#F3FAF9", "#AADAD5", "#0D9488")),
    ("zone-cde", "CDE", "Card terminals", "DEALS", "Card terminals at the service cashier, the parts counter and F&I",
     "Talks to the payment processor only. Nothing else talks to it.", ("#FEF6F2", "#F6C3A9", "#EA580C")),
    ("zone-service", "SERVICE", "Service drive", "FIXED", "Service advisors, the cashier PC, write-up tablets on KV-SERVICE",
     "Reaches the DMS, the manufacturer's warranty systems and the service printer.",
     ("#F4FAF5", "#B4DDBF", "#16A34A")),
    ("zone-shop", "SHOP", "Shop and technicians", "FIXED", "Manufacturer diagnostic PCs, shop tablets on KV-SHOP",
     "Reaches the manufacturer's network and its update servers. Never the front office.",
     ("#FBFAF0", "#E3DB9A", "#A16207")),
    ("zone-parts", "PARTS", "Parts", "FIXED", "Parts counter PCs, the parts printer, warehouse scanners",
     "Reaches the DMS and the manufacturer's parts systems.", ("#F2F9FC", "#A6D4EB", "#0284C7")),
    ("zone-oem", "OEM", "Manufacturer link", "FIXED", "The manufacturer's router and its own circuit",
     "The manufacturer's box. We give it one port and one VLAN, and filter what crosses.",
     ("#F7F6FA", "#CCC7DD", "#6B5B95")),
    ("zone-guest", "GUEST", "Customer Wi-Fi", "SHARED", "Customers' phones and laptops on KV-GUEST in the lounge",
     "Internet only. Clients can't see each other.", ("#FDF8F3", "#F2CFA8", "#D97706")),
    ("zone-voice", "VOICE", "Phones", "SHARED", "Desk phones and the service drive's paging",
     "Talks to the cloud phone service only.", ("#F8F5FE", "#D1BAF9", "#7C3AED")),
    ("zone-building", "BUILDING", "Building and lot", "SHARED", "Cameras, the NVR, the key cabinet, EV chargers",
     "Cameras talk to the NVR only. Key cabinet and EV chargers: their makers' clouds only.",
     ("#FDF4F9", "#F3B8D6", "#DB2777")),
    ("zone-mgmt", "MGMT", "Network management", "SHARED", "Firewall, switch, AP and UPS management; the console server",
     "Reached only by the MSP and the IT manager, through the VPN with MFA.", ("#F0FAFC", "#A5DCE8", "#0891B2")),
]
ZONE = {z[0]: z for z in ZONES}

BANDS = [
    ("OUT", "OUTSIDE · INTERNET & DMS", ("internet", "isp", "wan", "cloud", "saas", "dms", "lender", "remote")),
    ("EDGE", "EDGE · FIREWALL & REMOTE ACCESS", ("edge", "dmz", "vpn", "perimeter")),
    ("DEALS", "SALES, F&I & OFFICE", ("fi", "sales", "office", "cde", "card", "staff")),
    ("FIXED", "SERVICE, SHOP & PARTS", ("service", "shop", "parts", "oem", "body")),
    ("SHARED", "GUESTS, BUILDING & MGMT", ("guest", "voice", "building", "lot", "cameras", "mgmt", "oob")),
]

# VLANs: vid, name, zone, subnet, gateway text
VLANS = [
    (10, "SALES", "zone-sales", "10.30.10.0/24", "FW HA .1"),
    (11, "SALES-WIFI", "zone-sales", "10.30.11.0/24", "FW HA .1"),
    (15, "FI", "zone-fi", "10.30.15.0/24", "FW HA .1"),
    (20, "OFFICE", "zone-office", "10.30.20.0/24", "FW HA .1"),
    (25, "FILES", "zone-office", "10.30.25.0/24", "FW HA .1"),
    (30, "CARD", "zone-cde", "10.30.30.0/26", "FW HA .1"),
    (40, "SERVICE", "zone-service", "10.30.40.0/24", "FW HA .1"),
    (41, "SERVICE-WIFI", "zone-service", "10.30.41.0/24", "FW HA .1"),
    (50, "SHOP", "zone-shop", "10.30.50.0/24", "FW HA .1"),
    (51, "SHOP-WIFI", "zone-shop", "10.30.51.0/24", "FW HA .1"),
    (55, "PARTS", "zone-parts", "10.30.55.0/24", "FW HA .1"),
    (65, "OEM-LINK", "zone-oem", "10.30.65.0/29", "FW HA .1"),
    (70, "GUEST", "zone-guest", "172.16.70.0/23", "FW HA .1"),
    (75, "VOICE", "zone-voice", "10.30.75.0/24", "FW HA .1"),
    (80, "CAMERAS", "zone-building", "10.30.80.0/24", "FW HA .1"),
    (81, "BLDG-SYS", "zone-building", "10.30.81.0/24", "FW HA .1"),
    (99, "NET-MGMT", "zone-mgmt", "10.30.99.0/24", "FW HA .1"),
]
BRANCH_VLANS = [
    (10, "SALES", "zone-sales", "10.31.10.0/24"), (15, "FI", "zone-fi", "10.31.15.0/24"),
    (30, "CARD", "zone-cde", "10.31.30.0/26"), (70, "GUEST", "zone-guest", "172.17.70.0/24"),
    (99, "NET-MGMT", "zone-mgmt", "10.31.99.0/24"),
]

ARUBA, FORTI, CISCO, SYN, APC, OPEN, HP, AXIS, GENERIC = (
    "HPE Aruba Networking", "Fortinet", "Cisco", "Synology", "APC", "Opengear", "HP", "Axis", "Generic")

# Asset criticality by role: what stops at the dealership when the box fails. The firewall pair and the core
# stop every desk and the DMS; an access stack, the NAS, the card terminals, the UPSes or the manufacturer's
# router stop a department; the rest inconvenience a desk or a bay.
CRITICALITY = {"firewall": "critical", "core-switch": "critical",
               "access-switch": "high", "storage": "high", "ups": "high", "card-terminal": "high", "router": "high",
               "access-point": "medium", "console-server": "medium", "nvr": "medium", "diag-tool": "medium",
               "key-cabinet": "medium", "printer": "low", "camera": "low"}


def _dev(name, role, mfr, model, platform, location, rack, pos, ip, zone, desc, serial, tag, vc="", vcpos="",
         sw="", contract="", modules="", power="", status="active"):
    return {"name": name, "role": role, "manufacturer": mfr, "device_type": model, "platform": platform,
            "location": location, "rack": rack, "position": pos, "primary_ip4": ip, "tags": zone,
            "description": desc, "serial": serial, "asset_tag": tag, "virtual_chassis": vc, "vc_position": vcpos,
            "status": status, "cf_sw_version": sw, "cf_support_contract": contract,
            "cf_lifecycle": "In support" if contract else "", "x_modules": modules, "x_power": power,
            "cf_ap_mode": "cloud" if role == "access-point" else "", "cf_criticality": CRITICALITY.get(role, "")}


DEVICES = [
    _dev("D01-FW-01", "firewall", FORTI, "FortiGate 120G", "fortios", "MDF", "R01", "40", "10.30.99.2/24",
         "zone-edge", "Internet edge and inter-zone firewall (HA primary)", "FGxxxxxxxxxx01", "KV-0001",
         sw="FortiOS 7.4.x", contract="FortiCare 8x5", modules="x1–x2 SFP+ (DAC to core) · wan1, wan2 RJ45 · ha RJ45",
         power="2× AC PSU"),
    _dev("D01-FW-02", "firewall", FORTI, "FortiGate 120G", "fortios", "MDF", "R02", "40", "10.30.99.3/24",
         "zone-edge", "Internet edge and inter-zone firewall (HA secondary)", "FGxxxxxxxxxx02", "KV-0002",
         sw="FortiOS 7.4.x", contract="FortiCare 8x5", modules="x1–x2 SFP+ (DAC to core) · wan1, wan2 RJ45 · ha RJ45",
         power="2× AC PSU"),
    _dev("D01-OOB-01", "console-server", OPEN, "OM1204-4E-L", "opengear", "MDF", "R01", "41", "10.30.99.5/24",
         "zone-mgmt", "Out-of-band console with cellular", "OMxxxxxx01", "KV-0003", sw="Opengear 24.x",
         modules="4× serial (FW-01, FW-02, CORE-1, CORE-2) · LTE", power="2× DC"),
    _dev("D01-CORE-1", "core-switch", ARUBA, "CX 6300M 24SFP+", "aos-cx", "MDF", "R01", "38", "10.30.99.10/24",
         "zone-mgmt", "Core stack member 1 (conductor)", "SGxxxxxx11", "KV-0010", "D01-CORE", "1",
         sw="AOS-CX 10.13.x", contract="Foundation Care NBD", modules="24× SFP+ · 4× SFP56 · VSF on 1/1/27–28",
         power="2× JL086A"),
    _dev("D01-CORE-2", "core-switch", ARUBA, "CX 6300M 24SFP+", "aos-cx", "MDF", "R02", "38", "",
         "zone-mgmt", "Core stack member 2 (standby)", "SGxxxxxx12", "KV-0011", "D01-CORE", "2",
         sw="AOS-CX 10.13.x", contract="Foundation Care NBD", modules="24× SFP+ · 4× SFP56 · VSF on 2/1/27–28",
         power="2× JL086A"),
] + [
    _dev(f"D01-ACC-MAIN-{n}", "access-switch", ARUBA, "CX 6200F 48G Class4 PoE", "aos-cx", "MDF", "R02",
         str(37 - n), "10.30.99.21/24" if n == 1 else "", "zone-mgmt",
         f"Main building access stack member {n}" + (" (conductor)" if n == 1 else ""), f"CNxxxxxx2{n}",
         f"KV-002{n}", "D01-ACC-MAIN", str(n), sw="AOS-CX 10.13.x", contract="Foundation Care NBD",
         modules="48× 1G Class 4 PoE (740 W) · 4× SFP+", power="1× 740 W PSU")
    for n in (1, 2, 3)
] + [
    _dev(f"D01-ACC-SHOP-{n}", "access-switch", ARUBA, "CX 6200F 48G Class4 PoE", "aos-cx", "IDF-SHOP", "R01",
         str(22 - n), "10.30.99.22/24" if n == 1 else "", "zone-mgmt",
         f"Service building access stack member {n}" + (" (conductor)" if n == 1 else ""), f"CNxxxxxx3{n}",
         f"KV-003{n}", "D01-ACC-SHOP", str(n), sw="AOS-CX 10.13.x", contract="Foundation Care NBD",
         modules="48× 1G Class 4 PoE (740 W) · 4× SFP+ · 10G-SR to core", power="1× 740 W PSU")
    for n in (1, 2)
] + [
    _dev("D01-OEM-RTR-01", "router", CISCO, "ISR1111-4P", "", "MDF", "R01", "36", "10.30.65.2/29", "zone-oem",
         "The manufacturer's router: their box, their circuit, their password", "FGLxxxxxxx01", "",
         modules="gi0/0/0 to the manufacturer's circuit · gi0/1/0 to our core", power="1× AC"),
    _dev("D01-NAS-01", "storage", SYN, "RS2423RP+", "dsm", "MDF", "R01", "25", "10.30.25.20/24",
         "zone-office", "Deal-jacket scans and the office share; encrypted volume, copies to the cloud vault",
         "SYxxxxxx01", "KV-0042", sw="DSM 7.2", modules="12 bays · 2× 10G RJ45", power="2× redundant"),
    _dev("D01-UPS-01", "ups", APC, "Smart-UPS SRT 3000", "", "MDF", "R01", "1", "10.30.99.41/24",
         "zone-mgmt", "Rack R01 UPS (network card)", "ASxxxxxx01", "KV-0050", modules="NMC3 network card",
         power="3 kVA · about 20 min at today's load"),
    _dev("D01-UPS-02", "ups", APC, "Smart-UPS SRT 3000", "", "MDF", "R02", "1", "10.30.99.42/24",
         "zone-mgmt", "Rack R02 UPS (network card)", "ASxxxxxx02", "KV-0051", modules="NMC3 network card",
         power="3 kVA · about 25 min at today's load"),
    _dev("D01-NVR-01", "nvr", AXIS, "S3016", "", "MDF", "R02", "30", "10.30.80.10/24", "zone-building",
         "Video recorder for 8 lot and building cameras", "AXxxxxxx01", "KV-0060", modules="16 TB"),
    _dev("D01-KEY-01", "key-cabinet", GENERIC, "Key cabinet controller", "", "Sales tower", "", "",
         "10.30.81.10/24", "zone-building", "Vehicle key cabinet (sales tower); reports to its vendor's cloud",
         "KCxxxxxx01", "KV-0061"),
]
# Access points: the main building's rooms on the MAIN stack, the shop's bays on the SHOP stack.
AP_ROOMS = {"MAIN": ["Showroom", "Showroom", "Showroom", "Sales tower", "F&I offices", "Upstairs offices",
                     "Service drive", "Lounge"],
            "SHOP": ["Shop", "Shop", "Shop", "Shop"]}
for bld, rooms in AP_ROOMS.items():
    for n, room in enumerate(rooms, 1):
        DEVICES.append(_dev(f"D01-AP-{bld}-{n:02d}", "access-point", ARUBA, "AP-635", "aos-ap", room, "", "",
                            f"10.30.99.{(100 if bld == 'MAIN' else 120) + n}/24", "zone-mgmt",
                            f"{room} ceiling AP", f"CNAPxx{bld[0]}{n:02d}", ""))
# Printers and card terminals sit in the zone of the desk they serve.
for n, (room, zone, ip, what) in enumerate([("F&I offices", "zone-fi", "10.30.15.31", "F&I printer"),
                                            ("Service drive", "zone-service", "10.30.40.31", "Service write-up printer"),
                                            ("Parts", "zone-parts", "10.30.55.31", "Parts counter printer"),
                                            ("Upstairs offices", "zone-office", "10.30.20.31", "Office printer")], 1):
    DEVICES.append(_dev(f"D01-PRN-{n:02d}", "printer", HP, "LaserJet M610", "", room, "", "", f"{ip}/24", zone,
                        what, f"HPxxxxx{n:02d}", ""))
for n, (room, what) in enumerate([("Service drive", "Service cashier"), ("Parts", "Parts counter"),
                                  ("F&I offices", "F&I desk")], 1):
    DEVICES.append(_dev(f"D01-PAY-{n:02d}", "card-terminal", GENERIC, "Card terminal (P2PE)", "", room, "", "",
                        f"10.30.30.{10 + n}/26", "zone-cde", f"Card terminal, {what.lower()}", f"PTxxxxx{n:02d}", ""))
for n in range(1, 4):
    DEVICES.append(_dev(f"D01-DIAG-{n:02d}", "diag-tool", GENERIC, "Diagnostic PC (manufacturer spec)", "", "Shop", "",
                        "", f"10.30.50.{10 + n}/24", "zone-shop",
                        f"Manufacturer diagnostic and programming PC, bay {(2, 8, 14)[n - 1]}", f"DGxxxxx{n:02d}", ""))
for n in range(1, 9):
    DEVICES.append(_dev(f"D01-CAM-{n:02d}", "camera", AXIS, "P3268-LVE", "",
                        ("Showroom", "Service drive", "Lot", "Lot", "Shop", "Shop", "Lot", "Lot")[n - 1], "", "",
                        f"10.30.80.{20 + n}/24", "zone-building", "Lot and building camera", f"AXCAMxx{n:02d}", ""))

# Which building's stack each room's drops come from.
BUILDING = {"Showroom": "MAIN", "Sales tower": "MAIN", "F&I offices": "MAIN", "Upstairs offices": "MAIN",
            "Service drive": "MAIN", "Parts": "MAIN", "Lounge": "MAIN", "Shop": "SHOP", "Lot": "SHOP"}
# Each room's place in NetBox's location tree.
PARENT = {"MDF": "Main building", **{r: "Main building" for r, b in BUILDING.items() if b == "MAIN"},
          "IDF-SHOP": "Service building", "Shop": "Service building", "Lot": None}

BRANCH_DEVICES = [
    _dev("D02-FW-01", "firewall", FORTI, "FortiGate 40F-3G4G", "fortios", "CAB-1", "CAB-1", "8", "10.31.99.2/24",
         "zone-edge", "Pre-owned store firewall with cellular backup", "FGxxxxxxxx21", "KV-0201", sw="FortiOS 7.4.x"),
    _dev("D02-ACC-1", "access-switch", ARUBA, "CX 6100 24G Class4 PoE", "aos-cx", "CAB-1", "CAB-1", "10",
         "10.31.99.10/24", "zone-mgmt", "Pre-owned store access switch", "CNxxxxxx41", "KV-0202", sw="AOS-CX 10.13.x"),
    _dev("D02-AP-01", "access-point", ARUBA, "AP-615", "aos-ap", "Sales floor", "", "", "10.31.99.101/24",
         "zone-mgmt", "Sales floor ceiling AP", "CNAPxx41", ""),
    _dev("D02-AP-02", "access-point", ARUBA, "AP-615", "aos-ap", "Sales floor", "", "", "10.31.99.102/24",
         "zone-mgmt", "Closing office ceiling AP", "CNAPxx42", ""),
    _dev("D02-PRN-01", "printer", HP, "LaserJet M610", "", "Sales floor", "", "", "10.31.15.31/24", "zone-fi",
         "Closing office printer", "HPxxxxx41", ""),
    _dev("D02-PAY-01", "card-terminal", GENERIC, "Card terminal (P2PE)", "", "Sales floor", "", "", "10.31.30.11/26",
         "zone-cde", "Card terminal, closing office", "PTxxxxx41", ""),
]


# Links: label(s), A ends, B ends, type, color, speed, media, VLANs (tagged), name
def _cable(labels, a, b, ctype, color, speed, media, vlans="", lag=""):
    return {"labels": labels, "a": a, "b": b, "type": ctype, "color": color, "speed": speed, "media": media,
            "vlans": vlans, "lag": lag}


ALL = ", ".join(str(v[0]) for v in VLANS)
MAIN_TRUNK = "10, 11, 15, 20, 30, 40, 41, 55, 70, 75, 80, 81, 99"
SHOP_TRUNK = "50, 51, 70, 75, 80, 99"
CABLES = [
    _cable(["D01-CBL-00001", "D01-CBL-00002"], ["D01-FW-01:x1", "D01-FW-01:x2"],
           ["D01-CORE-1:1/1/1", "D01-CORE-2:1/1/1"], "dac-passive", "111111", "2×10G", "DAC", ALL, "Po1"),
    _cable(["D01-CBL-00003", "D01-CBL-00004"], ["D01-FW-02:x1", "D01-FW-02:x2"],
           ["D01-CORE-1:1/1/2", "D01-CORE-2:1/1/2"], "dac-passive", "111111", "2×10G", "DAC", ALL, "Po2"),
    _cable(["D01-CBL-00005"], ["D01-FW-01:ha"], ["D01-FW-02:ha"], "cat6", "9e9e9e", "1G", "Cat6", "", "HA"),
    _cable(["D01-CBL-00011", "D01-CBL-00012"], ["D01-CORE-1:1/1/11", "D01-CORE-2:1/1/11"],
           ["D01-ACC-MAIN-1:1/1/49", "D01-ACC-MAIN-3:1/1/49"], "dac-passive", "111111", "2×10G", "DAC", MAIN_TRUNK,
           "Po11"),
    _cable(["D01-CBL-00013", "D01-CBL-00014"], ["D01-CORE-1:1/1/12", "D01-CORE-2:1/1/12"],
           ["D01-ACC-SHOP-1:1/1/49", "D01-ACC-SHOP-2:1/1/49"], "mmf-om4", "00bcd4", "2×10G", "MMF OM4", SHOP_TRUNK,
           "Po12"),
    _cable(["D01-CBL-00025"], ["D01-CORE-1:1/1/23"], ["D01-NAS-01:lan1"], "cat6a", "2196f3", "10G", "Cat6A", "", ""),
    _cable(["D01-CBL-00026"], ["D01-CORE-2:1/1/19"], ["D01-OEM-RTR-01:gi0/1/0"], "cat6", "2196f3", "1G", "Cat6", "",
           ""),
    _cable(["D01-CBL-00031"], ["D01-ACC-MAIN-2:1/1/45"], ["D01-NVR-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["D01-CBL-00032"], ["D01-ACC-MAIN-2:1/1/46"], ["D01-KEY-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    # Management drops on the core: 1G copper SFPs, in the rack beside the gear they watch.
    _cable(["D01-CBL-00033"], ["D01-CORE-1:1/1/24"], ["D01-UPS-01:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["D01-CBL-00034"], ["D01-CORE-2:1/1/24"], ["D01-UPS-02:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["D01-CBL-00035"], ["D01-CORE-1:1/1/20"], ["D01-OOB-01:net1"], "cat6", "2196f3", "1G", "Cat6", "", ""),
]
NETWORK_CABLES = len(CABLES)  # the link register lists these; the endpoint drops follow

# The access VLAN of each end device's switch port: the VLAN of its zone's wired desks. APs trunk.
ZONE_VLAN = {"zone-fi": 15, "zone-sales": 10, "zone-office": 20, "zone-cde": 30, "zone-service": 40,
             "zone-shop": 50, "zone-parts": 55, "zone-building": 80, "zone-mgmt": 99, "zone-oem": 65}
ROLE_VLAN = {"key-cabinet": 81, "storage": 25}
AP_VLANS = {"MAIN": (11, 41, 70), "SHOP": (51, 70)}


def access_vlan(d: dict) -> int | None:
    if d["role"] == "access-point":
        return None
    return ROLE_VLAN.get(d["role"]) or ZONE_VLAN.get(d["tags"])


# Endpoint drops: APs, printers, card terminals, diagnostic PCs and cameras on their building's stack.
_port = {"MAIN": 1, "SHOP": 1}
_drop = iter(range(101, 1000))
_wired = {e.split(":")[0] for c in CABLES for e in c["b"]}  # the key cabinet already has its drop above
for d in DEVICES:
    bld = BUILDING.get(d["location"])
    if not bld or d["name"] in _wired:
        continue
    stack_name = f"D01-ACC-{bld}"
    members = 3 if bld == "MAIN" else 2
    n = _port[bld]
    _port[bld] += 1
    member = (n - 1) % members + 1
    iface = f"1/1/{(n - 1) // members + 1}"
    ap = d["role"] == "access-point"
    CABLES.append(_cable([f"D01-CBL-{next(_drop):05d}"], [f"{stack_name}-{member}:{iface}"], [f"{d['name']}:eth0"],
                         "cat6a" if ap else "cat6", "2196f3", "1G", "Cat6A" if ap else "Cat6",
                         ", ".join(map(str, AP_VLANS[bld] + (99,))) if ap else "", ""))

# A stack member's ports carry its member number (AOS-CX VSF): D01-CORE-2's first port is 2/1/1.
_MEMBER = {d["name"]: int(d["vc_position"]) for d in DEVICES if d["vc_position"]}


def _member_port(end: str) -> str:
    dev, port = end.split(":", 1)
    if _MEMBER.get(dev, 1) > 1 and port.startswith("1/1/"):
        port = f"{_MEMBER[dev]}/1/{port[4:]}"
    return f"{dev}:{port}"


for _c in CABLES:
    _c["a"], _c["b"] = [_member_port(e) for e in _c["a"]], [_member_port(e) for e in _c["b"]]

CIRCUITS = [
    {"cid": "D01-ISP-A-01", "provider": "Provider A", "type": "Dedicated internet access", "speed": "1G",
     "handoff": "D01-FW-01:wan1, D01-FW-02:wan1", "media": "Cat6", "label": "DIA 1G · fiber ONT"},
    {"cid": "D01-ISP-B-01", "provider": "Provider B", "type": "Business cable", "speed": "500/50M",
     "handoff": "D01-FW-01:wan2, D01-FW-02:wan2", "media": "Cat6", "label": "Cable 500/50 · modem"},
]
# The manufacturer's own line: theirs end to end, ending on their router (drawn in the OEM zone, not as an ISP).
OEM_CIRCUIT = {"cid": "D01-OEM-01", "provider": "Manufacturer network", "type": "Manufacturer dealer network",
               "speed": "100M", "handoff": "D01-OEM-RTR-01:gi0/0/0", "label": "Manufacturer's circuit · 100M"}

SSIDS = [
    ("KV-STAFF", "WPA3-Enterprise · 802.1X", 11, "zone-sales", "Sales tablets and staff laptops; EAP-TLS with device certificates"),
    ("KV-SERVICE", "WPA3-Enterprise · 802.1X", 41, "zone-service", "Write-up tablets in the service drive; EAP-TLS"),
    ("KV-SHOP", "WPA2-PSK · key rotated quarterly", 51, "zone-shop", "Shop tablets and diagnostic interfaces that can't do 802.1X"),
    ("KV-GUEST", "Captive portal · client isolation", 70, "zone-guest", "Customers in the lounge and showroom; internet only, 25 Mb/s per client"),
]
# The pre-owned store runs staff and guest only, on its own VLANs, from the same cloud dashboard.
BRANCH_SSIDS = [
    ("KV-STAFF", "WPA3-Enterprise · 802.1X", 10, "zone-sales", "Sales tablets; same SSID as D01"),
    ("KV-GUEST", "Captive portal · client isolation", 70, "zone-guest", "Customers; internet only, local breakout"),
]

# Flows: id, from, to, what, verdict, conditions, owner
FLOWS = [
    ("F01", "F&I", "DMS (hosted)", "Deals, contracts, customer records · HTTPS over the DMS tunnel", "Allow", "Through the DMS IPsec tunnel only · MFA at sign-in (provider setting)", "Controller"),
    ("F02", "F&I", "Lenders and credit bureaus", "Credit applications and pulls · HTTPS", "Conditional", "Named destinations only · MFA on every portal", "F&I director"),
    ("F03", "Sales, service, parts, office", "DMS (hosted)", "Desking, repair orders, parts, accounting · HTTPS", "Allow", "Through the DMS IPsec tunnel only · MFA at sign-in (provider setting)", "Controller"),
    ("F04", "Sales", "Internet and SaaS", "CRM, email, the manufacturer's sales portal · HTTPS", "Allow", "Web filter · MFA at sign-in (provider setting)", "IT manager"),
    ("F05", "Sales, shop, guests", "F&I", "Anything", "Deny", "Logged", "IT manager"),
    ("F06", "Shop", "Manufacturer network", "Diagnostics, programming, software updates", "Allow", "Through the manufacturer's router only", "Service director"),
    ("F07", "Service, parts", "Manufacturer network", "Warranty claims, parts ordering, recalls", "Allow", "Through the manufacturer's router only", "Service director"),
    ("F08", "Manufacturer network", "Any internal zone", "Anything it starts", "Deny", "Logged · the router answers, never initiates", "IT manager"),
    ("F09", "Shop", "Sales, office, F&I", "Anything", "Deny", "Logged", "IT manager"),
    ("F10", "Card terminals", "Payment processor", "Card authorizations · TLS", "Allow", "One destination · P2PE", "Controller"),
    ("F11", "Any other zone", "Card terminals", "Anything", "Deny", "Logged", "Controller"),
    ("F12", "Office, F&I", "NAS (deal-jacket scans)", "File share (SMB 3, encrypted)", "Allow", "Named groups only", "Controller"),
    ("F13", "NAS", "Cloud backup vault", "Nightly copy · HTTPS", "Allow", "22:00–05:00 · immutable 30 days", "IT manager"),
    ("F14", "Office", "Banks and payroll", "Funding, deposits, payroll · HTTPS", "Conditional", "Named destinations · MFA", "Controller"),
    ("F15", "Guests", "Internet", "Web", "Allow", "25 Mb/s per client · DNS filter", "General manager"),
    ("F16", "Guests", "Any internal zone", "Anything", "Deny", "Logged", "IT manager"),
    ("F17", "Phones", "Cloud phone service", "SIP, RTP", "Allow", "Provider's published ranges", "General manager"),
    ("F18", "Cameras", "NVR", "Video (RTSP)", "Allow", "Inside zone-building", "General manager"),
    ("F19", "Key cabinet", "Key cabinet vendor's cloud", "Key logs and alerts · HTTPS", "Conditional", "One destination", "Used car manager"),
    ("F20", "MSP (remote)", "Network management", "SSH, HTTPS to device management", "Conditional", "VPN + MFA · logged", "IT manager"),
    ("F21", "Vendors (DMS, manufacturer support)", "A named desk or device", "Remote support session", "Conditional", "Requested per ticket · MFA · recorded · closed after", "IT manager"),
    ("F22", "D02 pre-owned store", "D01 firewall", "DMS and the office share (IPsec)", "Allow", "Site-to-site tunnel", "IT manager"),
    ("F23", "APs (management, VLAN 99)", "Cloud Wi-Fi service", "AP management and 802.1X · HTTPS, RADIUS over TLS", "Conditional", "Provider's published ranges · APs only", "IT manager"),
    ("F24", "Every zone", "Firewall services", "DHCP, DNS, NTP", "Allow", "The firewall's own address on each VLAN", "IT manager"),
    ("F25", "Network management", "MSP monitoring and SIEM", "Syslog over TLS · monitoring", "Conditional", "One destination: the MSP's collectors", "IT manager"),
    ("F26", "Every other zone", "Network management", "Anything", "Deny", "Logged", "IT manager"),
    ("F27", "MSP (cellular OOB)", "D01-OOB-01 console ports", "Console access when the network is down", "Conditional", "Named accounts · MFA · logged · no public listener (private APN)", "IT manager"),
    ("F28", "Managers (named group)", "NVR", "Live and recorded video · HTTPS", "Conditional", "Named group only · MFA · no port forward to the NVR", "General manager"),
    ("F29", "EV chargers", "Charger maker's cloud", "Charging sessions and billing · OCPP over TLS", "Conditional", "One destination", "General manager"),
]
