"""Ninebark Community Bank: the fictional institution the B01 template is drawn for.

One source for the template's shapes and for the sample NetBox export, so the
two never disagree. B01 is the main office: the banking hall (teller line,
platform desks, drive-up, ATM, vault) on floor 1, operations (back office, the
wire room, the card room) on floor 2. B02 is a full-service branch. The core
processor, the card and ATM processor, the Federal Reserve and the alarm
company are outside parties, drawn as boundaries. Addresses are private or
documentation ranges; serials and circuit IDs are placeholders.
"""

from __future__ import annotations

SITE = {"code": "B01", "name": "Ninebark main office", "slug": "b01"}
BRANCH = {"code": "B02", "name": "Elm Street branch", "slug": "b02"}

# Zones: slug, short name, title, band code, what lives there, rule, (fill, stroke, font)
ZONES = [
    ("zone-internet", "INTERNET", "Internet and outside parties", "OUT",
     "ISP-A, ISP-B, SaaS, the Federal Reserve's FedLine service, the alarm monitoring center, remote staff",
     "Untrusted. Everything from here ends on the firewall.", ("#F8FAFC", "#CBD5E1", "#475569")),
    ("zone-partner", "PARTNER", "Core and card processor links", "EDGE",
     "The core processor's router and private circuit; the card and ATM processor over it",
     "Provider-owned router, our firewall in front of it. Only teller, staff, wire, ATM, card and servers reach it.",
     ("#F5F3FF", "#C4B5FD", "#6D28D9")),
    ("zone-edge", "EDGE", "Firewall and remote access", "EDGE", "The firewall HA pair, the VPN address pool",
     "The one place zones meet. Every inter-zone packet is inspected here.", ("#F1F5F9", "#94A3B8", "#334155")),
    ("zone-teller", "TELLER", "Teller line", "BANK", "Teller workstations, cash recyclers, the drive-up teller",
     "Reaches the core processor and named servers. No internet.", ("#F4F7FE", "#B3C8F8", "#2563EB")),
    ("zone-staff", "STAFF", "Platform and back office", "BANK",
     "Account and loan officers, operations, accounting; staff Wi-Fi; printers",
     "Reaches the core processor, servers and filtered internet. Nothing reaches into it.",
     ("#F2F9FC", "#A6D4EB", "#0284C7")),
    ("zone-wire", "WIRE", "Wire room", "BANK", "Two wire workstations in the wire room",
     "Reaches the Federal Reserve's FedLine service and the core processor. Nothing else, nothing in.",
     ("#FEF2F2", "#FCA5A5", "#B91C1C")),
    ("zone-card", "CARD", "Card issuing", "BANK", "The instant-issue card printer and its workstation",
     "Reaches the card processor only. Nothing reaches in.", ("#FFF7ED", "#FDBA74", "#C2410C")),
    ("zone-servers", "SERVERS", "Servers", "SERV", "Virtualization hosts, the backup NAS",
     "Reached from teller and staff on named ports. Backs up to the cloud vault.", ("#F3FAF9", "#AADAD5", "#0D9488")),
    ("zone-voice", "VOICE", "Voice", "SERV", "Desk phones",
     "Talks to the cloud phone service only.", ("#F4FAF5", "#B4DDBF", "#16A34A")),
    ("zone-atm", "ATM", "ATMs", "CUST", "The drive-up and lobby ATMs",
     "Reach the ATM processor only. Nothing reaches into them but the servicer, booked.",
     ("#FDF4FF", "#F0ABFC", "#A21CAF")),
    ("zone-guest", "GUEST", "Lobby guests", "CUST", "Customers' and visitors' phones on NB-GUEST",
     "Internet only. Clients can't see each other.", ("#FDF8F3", "#F2CFA8", "#D97706")),
    ("zone-security", "SECURITY", "Physical security", "MGMT", "Cameras, the NVR, the alarm panel, door controllers",
     "Cameras talk to the NVR only. The alarm panel talks to its monitoring center only.",
     ("#FDF4F9", "#F3B8D6", "#DB2777")),
    ("zone-mgmt", "MGMT", "Network management", "MGMT",
     "Firewall, switch, AP and UPS management; the console server",
     "Reached only by IT and the MSP, through the VPN with MFA.", ("#F0FAFC", "#A5DCE8", "#0891B2")),
]
ZONE = {z[0]: z for z in ZONES}

BANDS = [
    ("OUT", "OUTSIDE · INTERNET & PARTIES", ("internet", "isp", "wan", "cloud", "saas", "remote")),
    ("EDGE", "EDGE · FIREWALL & PROCESSOR LINKS", ("edge", "partner", "core-link", "dmz", "vpn", "perimeter")),
    ("BANK", "BANKING · TELLER, STAFF, WIRE & CARD", ("teller", "staff", "platform", "wire", "card", "corp")),
    ("SERV", "SERVICES · SERVERS & VOICE", ("servers", "voice", "print")),
    ("CUST", "CUSTOMER-FACING · ATM & GUEST", ("atm", "itm", "guest", "lobby")),
    ("MGMT", "SECURITY & MANAGEMENT", ("security", "alarm", "cameras", "building", "mgmt", "oob")),
]

# VLANs: vid, name, zone, subnet, gateway text
VLANS = [
    (10, "TELLER", "zone-teller", "10.30.10.0/24", "FW HA .1"),
    (20, "STAFF-WIRED", "zone-staff", "10.30.20.0/23", "FW HA .1"),
    (21, "STAFF-WIFI", "zone-staff", "10.30.22.0/24", "FW HA .1"),
    (25, "WIRE", "zone-wire", "10.30.25.0/27", "FW HA .1"),
    (26, "CARD", "zone-card", "10.30.26.0/27", "FW HA .1"),
    (30, "VOICE", "zone-voice", "10.30.30.0/24", "FW HA .1"),
    (40, "SERVERS", "zone-servers", "10.30.40.0/24", "FW HA .1"),
    (45, "BACKUP", "zone-servers", "10.30.45.0/24", "FW HA .1"),
    (60, "ATM", "zone-atm", "10.30.60.0/27", "FW HA .1"),
    (70, "GUEST", "zone-guest", "172.16.70.0/23", "FW HA .1"),
    (80, "CAMERAS", "zone-security", "10.30.80.0/24", "FW HA .1"),
    (81, "ALARM-DOOR", "zone-security", "10.30.81.0/24", "FW HA .1"),
    (99, "NET-MGMT", "zone-mgmt", "10.30.99.0/24", "FW HA .1"),
    (100, "CORE-LINK", "zone-partner", "10.30.100.0/29", "FW HA .1"),
]
BRANCH_VLANS = [
    (10, "TELLER", "zone-teller", "10.32.10.0/24"), (20, "STAFF", "zone-staff", "10.32.20.0/24"),
    (30, "VOICE", "zone-voice", "10.32.30.0/24"), (60, "ATM", "zone-atm", "10.32.60.0/28"),
    (70, "GUEST", "zone-guest", "172.17.70.0/24"), (80, "SECURITY", "zone-security", "10.32.80.0/24"),
    (99, "NET-MGMT", "zone-mgmt", "10.32.99.0/24"),
]

ARUBA, FORTI, DELL, SYN, APC, OPEN, AXIS, NCR, GLORY, ENTRUST, BOSCH, CISCO = (
    "HPE Aruba Networking", "Fortinet", "Dell", "Synology", "APC", "Opengear", "Axis", "NCR Atleos", "Glory",
    "Entrust", "Bosch", "Cisco")


# Asset criticality by role: what stops for the bank when the box fails. The firewall pair, the core, the hosts
# and the core processor's router stop every teller; an access stack, the backup target, the UPSs, the cash
# recyclers, the alarm panel and the wire and card gear stop a line, a safeguard or a payment; the rest
# inconvenience a desk.
CRITICALITY = {"firewall": "critical", "core-switch": "critical", "hypervisor": "critical", "provider-router": "critical",
               "access-switch": "high", "storage": "high", "ups": "high", "alarm-panel": "high", "atm": "high",
               "cash-recycler": "high", "wire-workstation": "high", "card-printer": "high",
               "access-point": "medium", "console-server": "medium", "nvr": "medium", "door-controller": "medium",
               "printer": "low", "camera": "low", "router": "high"}


def _dev(name, role, mfr, model, platform, location, rack, pos, ip, zone, desc, serial, tag, vc="", vcpos="",
         sw="", contract="", modules="", power="", status="active"):
    return {"name": name, "role": role, "manufacturer": mfr, "device_type": model, "platform": platform,
            "location": location, "rack": rack, "position": pos, "primary_ip4": ip, "tags": zone,
            "description": desc, "serial": serial, "asset_tag": tag, "virtual_chassis": vc, "vc_position": vcpos,
            "status": status, "cf_sw_version": sw, "cf_support_contract": contract,
            "cf_lifecycle": "In support" if contract else "", "x_modules": modules, "x_power": power,
            "cf_ap_mode": "cloud" if role == "access-point" else "", "cf_criticality": CRITICALITY.get(role, "")}


DEVICES = [
    _dev("B01-FW-01", "firewall", FORTI, "FortiGate 120G", "fortios", "COMMS-1", "R01", "40", "10.30.99.2/24",
         "zone-edge", "Internet edge and inter-zone firewall (HA primary)", "FGxxxxxxxxxx01", "NB-0001",
         sw="FortiOS 7.4.x", contract="FortiCare 24x7",
         modules="x1–x2 SFP+ (DAC to core) · wan1, wan2 RJ45 · port5 core link · ha RJ45", power="2× AC PSU"),
    _dev("B01-FW-02", "firewall", FORTI, "FortiGate 120G", "fortios", "COMMS-1", "R02", "40", "10.30.99.3/24",
         "zone-edge", "Internet edge and inter-zone firewall (HA secondary)", "FGxxxxxxxxxx02", "NB-0002",
         sw="FortiOS 7.4.x", contract="FortiCare 24x7",
         modules="x1–x2 SFP+ (DAC to core) · wan1, wan2 RJ45 · port5 core link · ha RJ45", power="2× AC PSU"),
    _dev("B01-CPR-01", "provider-router", CISCO, "ISR 1111-4P", "", "COMMS-1", "R01", "42", "10.30.100.6/29",
         "zone-partner", "Core processor's router (provider owned and managed; we hold no login)", "FGLxxxxxx01",
         "NB-0004", modules="Private circuit B01-CORE-01 · ge0/1/0 to our firewalls", power="1× AC"),
    _dev("B01-OOB-01", "console-server", OPEN, "OM1204-4E-L", "opengear", "COMMS-1", "R01", "41", "10.30.99.5/24",
         "zone-mgmt", "Out-of-band console with cellular", "OMxxxxxx01", "NB-0003", sw="Opengear 24.x",
         modules="4× serial (FW-01, FW-02, CORE-1, CORE-2) · LTE", power="2× DC"),
    _dev("B01-CORE-1", "core-switch", ARUBA, "CX 6300M 24SFP+", "aos-cx", "COMMS-1", "R01", "38", "10.30.99.10/24",
         "zone-mgmt", "Core stack member 1 (conductor)", "SGxxxxxx11", "NB-0010", "B01-CORE", "1",
         sw="AOS-CX 10.13.x", contract="Foundation Care NBD", modules="24× SFP+ · 4× SFP56 · VSF on 1/1/27–28",
         power="2× JL086A"),
    _dev("B01-CORE-2", "core-switch", ARUBA, "CX 6300M 24SFP+", "aos-cx", "COMMS-1", "R02", "38", "",
         "zone-mgmt", "Core stack member 2 (standby)", "SGxxxxxx12", "NB-0011", "B01-CORE", "2",
         sw="AOS-CX 10.13.x", contract="Foundation Care NBD", modules="24× SFP+ · 4× SFP56 · VSF on 2/1/27–28",
         power="2× JL086A"),
] + [
    _dev(f"B01-ACC-F1-{n}", "access-switch", ARUBA, "CX 6200F 48G Class4 PoE", "aos-cx", "COMMS-1", "R02",
         str(37 - n), "10.30.99.21/24" if n == 1 else "", "zone-staff",
         f"Floor 1 (banking hall) access stack member {n}" + (" (conductor)" if n == 1 else ""), f"CNxxxxxx1{n}",
         f"NB-002{n}", "B01-ACC-F1", str(n), sw="AOS-CX 10.13.x", contract="Foundation Care NBD",
         modules="48× 1G Class 4 PoE (740 W) · 4× SFP+", power="1× 740 W PSU")
    for n in (1, 2)
] + [
    _dev(f"B01-ACC-F2-{n}", "access-switch", ARUBA, "CX 6200F 48G Class4 PoE", "aos-cx", "IDF-2", "R01",
         str(22 - n), "10.30.99.22/24" if n == 1 else "", "zone-staff",
         f"Floor 2 (operations) access stack member {n}" + (" (conductor)" if n == 1 else ""), f"CNxxxxxx2{n}",
         f"NB-003{n}", "B01-ACC-F2", str(n), sw="AOS-CX 10.13.x", contract="Foundation Care NBD",
         modules="48× 1G Class 4 PoE (740 W) · 4× SFP+ · 10G-SR to core", power="1× 740 W PSU")
    for n in (1, 2)
] + [
    _dev("B01-HV-01", "hypervisor", DELL, "PowerEdge R660xs", "", "COMMS-1", "R01", "30", "10.30.40.11/24",
         "zone-servers", "Virtualization host 1 (directory, file, check imaging VMs)", "SVCTAGxx01", "NB-0040",
         sw="Hypervisor 8.0", contract="ProSupport NBD", modules="2× 10G SFP+ (DAC) · iDRAC 10.30.99.31",
         power="2× 700 W"),
    _dev("B01-HV-02", "hypervisor", DELL, "PowerEdge R660xs", "", "COMMS-1", "R01", "28", "10.30.40.12/24",
         "zone-servers", "Virtualization host 2", "SVCTAGxx02", "NB-0041", sw="Hypervisor 8.0",
         contract="ProSupport NBD", modules="2× 10G SFP+ (DAC) · iDRAC 10.30.99.32", power="2× 700 W"),
    _dev("B01-NAS-01", "storage", SYN, "RS2423RP+", "dsm", "COMMS-1", "R01", "25", "10.30.45.20/24",
         "zone-servers", "Backup target, replicates to the cloud vault (immutable copies)", "SYxxxxxx01", "NB-0042",
         sw="DSM 7.2", modules="12 bays · 2× 10G RJ45", power="2× redundant"),
    _dev("B01-UPS-01", "ups", APC, "Smart-UPS SRT 3000", "", "COMMS-1", "R01", "1", "10.30.99.41/24",
         "zone-mgmt", "Rack R01 UPS (network card)", "ASxxxxxx01", "NB-0050", modules="NMC3 network card",
         power="3 kVA · about 20 min at today's load; generator transfer at 30 s"),
    _dev("B01-UPS-02", "ups", APC, "Smart-UPS SRT 3000", "", "COMMS-1", "R02", "1", "10.30.99.42/24",
         "zone-mgmt", "Rack R02 UPS (network card)", "ASxxxxxx02", "NB-0051", modules="NMC3 network card",
         power="3 kVA · about 24 min at today's load; generator transfer at 30 s"),
    _dev("B01-NVR-01", "nvr", AXIS, "S3016", "", "COMMS-1", "R02", "30", "10.30.80.10/24", "zone-security",
         "Video recorder for 12 cameras (90-day retention)", "AXxxxxxx01", "NB-0060", modules="32 TB"),
    _dev("B01-ALARM-01", "alarm-panel", BOSCH, "B6512", "", "Vault", "", "", "10.30.81.10/24", "zone-security",
         "Intrusion and holdup alarm panel; IP to the monitoring center, cellular backup", "BSxxxxxx01", "NB-0061"),
    _dev("B01-DOOR-01", "door-controller", AXIS, "A1601", "", "COMMS-1", "", "", "10.30.81.20/24", "zone-security",
         "Door controller (staff entrance, operations floor, comms room)", "AXxxxxxx02", "NB-0062"),
    _dev("B01-ATM-01", "atm", NCR, "SelfServ 84", "", "Drive-up", "", "", "10.30.60.11/27", "zone-atm",
         "Drive-up ATM, lane 3", "NCxxxxxx01", "NB-0070"),
    _dev("B01-ATM-02", "atm", NCR, "SelfServ 82", "", "Lobby", "", "", "10.30.60.12/27", "zone-atm",
         "Lobby vestibule ATM", "NCxxxxxx02", "NB-0071"),
    _dev("B01-TCR-01", "cash-recycler", GLORY, "RBG-200", "", "Teller line", "", "", "10.30.10.21/24", "zone-teller",
         "Teller cash recycler, stations 1–3", "GLxxxxxx01", "NB-0072"),
    _dev("B01-TCR-02", "cash-recycler", GLORY, "RBG-200", "", "Drive-up", "", "", "10.30.10.22/24", "zone-teller",
         "Teller cash recycler, drive-up window", "GLxxxxxx02", "NB-0073"),
    _dev("B01-WIRE-01", "wire-workstation", DELL, "OptiPlex 7020", "", "Wire room", "", "", "10.30.25.11/27",
         "zone-wire", "Wire workstation 1 (FedLine, dual control)", "SVCTAGxx11", "NB-0080"),
    _dev("B01-WIRE-02", "wire-workstation", DELL, "OptiPlex 7020", "", "Wire room", "", "", "10.30.25.12/27",
         "zone-wire", "Wire workstation 2 (FedLine, dual control)", "SVCTAGxx12", "NB-0081"),
    _dev("B01-CARD-01", "card-printer", ENTRUST, "Sigma DS3", "", "Card room", "", "", "10.30.26.11/27", "zone-card",
         "Instant-issue debit card printer", "ENxxxxxx01", "NB-0082"),
]
for floor, n_ap in ((1, 4), (2, 6)):
    for n in range(1, n_ap + 1):
        DEVICES.append(_dev(f"B01-AP-F{floor}-{n:02d}", "access-point", ARUBA, "AP-635", "aos-ap", f"Floor {floor}",
                            "", "", f"10.30.99.{100 + (floor - 1) * 10 + n}/24", "zone-staff",
                            f"Floor {floor} ceiling AP {n}", f"CNAPxx{floor}{n:02d}", ""))
    DEVICES.append(_dev(f"B01-PRN-F{floor}-01", "printer", "Ricoh", "IM C3000", "", f"Floor {floor}", "", "",
                        f"10.30.20.{10 + floor}/23", "zone-staff", f"Floor {floor} print corner",
                        f"RCxxxxx{floor}1", ""))
for n in range(1, 13):
    DEVICES.append(_dev(f"B01-CAM-{n:02d}", "camera", AXIS, "P3268-LV", "", "Floor 1" if n <= 9 else "Floor 2", "",
                        "", f"10.30.80.{20 + n}/24", "zone-security",
                        "Teller line, lobby, drive-up and vault camera" if n <= 9 else "Operations floor camera",
                        f"AXCAMxx{n:02d}", ""))

BRANCH_DEVICES = [
    _dev("B02-FW-01", "firewall", FORTI, "FortiGate 60F", "fortios", "CAB-1", "CAB-1", "10", "10.32.99.2/24",
         "zone-edge", "Branch firewall; SD-WAN over broadband and LTE", "FGxxxxxxxx21", "NB-0201", sw="FortiOS 7.4.x",
         contract="FortiCare 24x7"),
    _dev("B02-LTE-01", "router", FORTI, "FortiExtender 211F", "", "CAB-1", "CAB-1", "11", "10.32.99.3/24",
         "zone-edge", "Cellular backup for the branch firewall", "FXxxxxxxxx21", "NB-0202"),
    _dev("B02-ACC-1", "access-switch", ARUBA, "CX 6100 24G Class4 PoE", "aos-cx", "CAB-1", "CAB-1", "8",
         "10.32.99.10/24", "zone-staff", "Branch access switch", "CNxxxxxx41", "NB-0203", sw="AOS-CX 10.13.x"),
    _dev("B02-AP-01", "access-point", ARUBA, "AP-615", "aos-ap", "Ground floor", "", "", "10.32.99.101/24",
         "zone-staff", "Branch ceiling AP 1", "CNAPxx41", ""),
    _dev("B02-AP-02", "access-point", ARUBA, "AP-615", "aos-ap", "Ground floor", "", "", "10.32.99.102/24",
         "zone-staff", "Branch ceiling AP 2", "CNAPxx42", ""),
    _dev("B02-ATM-01", "atm", NCR, "SelfServ 84", "", "Drive-up", "", "", "10.32.60.11/28", "zone-atm",
         "Drive-up ATM", "NCxxxxxx21", "NB-0270"),
    _dev("B02-TCR-01", "cash-recycler", GLORY, "RBG-200", "", "Ground floor", "", "", "10.32.10.21/24", "zone-teller",
         "Teller cash recycler", "GLxxxxxx21", "NB-0272"),
    _dev("B02-ALARM-01", "alarm-panel", BOSCH, "B6512", "", "Vault", "", "", "10.32.80.10/24", "zone-security",
         "Intrusion and holdup alarm panel, cellular backup", "BSxxxxxx21", "NB-0261"),
    _dev("B02-NVR-01", "nvr", AXIS, "S3008", "", "CAB-1", "CAB-1", "4", "10.32.80.11/24", "zone-security",
         "Video recorder for 6 cameras", "AXxxxxxx21", "NB-0260", modules="8 TB"),
]


# Links: label(s), A ends, B ends, type, color, speed, media, VLANs (tagged), name
def _cable(labels, a, b, ctype, color, speed, media, vlans="", lag=""):
    return {"labels": labels, "a": a, "b": b, "type": ctype, "color": color, "speed": speed, "media": media,
            "vlans": vlans, "lag": lag}


ALL_VLANS = "10, 20, 21, 25, 26, 30, 40, 45, 60, 70, 80, 81, 99"
TRUNK_F1 = "10, 20, 21, 30, 60, 70, 80, 81, 99"     # the banking hall: no wire, card or servers
TRUNK_F2 = "20, 21, 25, 26, 30, 70, 80, 81, 99"     # operations: the wire room and the card room live here
CABLES = [
    _cable(["B01-CBL-00001", "B01-CBL-00002"], ["B01-FW-01:x1", "B01-FW-01:x2"],
           ["B01-CORE-1:1/1/1", "B01-CORE-2:1/1/1"], "dac-passive", "111111", "2×10G", "DAC", ALL_VLANS, "Po1"),
    _cable(["B01-CBL-00003", "B01-CBL-00004"], ["B01-FW-02:x1", "B01-FW-02:x2"],
           ["B01-CORE-1:1/1/2", "B01-CORE-2:1/1/2"], "dac-passive", "111111", "2×10G", "DAC", ALL_VLANS, "Po2"),
    _cable(["B01-CBL-00005"], ["B01-FW-01:ha"], ["B01-FW-02:ha"], "cat6", "9e9e9e", "1G", "Cat6", "", "HA"),
    # The core processor's router hands off on its own copper ports, one to each firewall; never via our switches.
    _cable(["B01-CBL-00006"], ["B01-FW-01:port5"], ["B01-CPR-01:ge0/1/0"], "cat6", "9c27b0", "1G", "Cat6", "", ""),
    _cable(["B01-CBL-00007"], ["B01-FW-02:port5"], ["B01-CPR-01:ge0/1/1"], "cat6", "9c27b0", "1G", "Cat6", "", ""),
    _cable(["B01-CBL-00011", "B01-CBL-00012"], ["B01-CORE-1:1/1/11", "B01-CORE-2:1/1/11"],
           ["B01-ACC-F1-1:1/1/49", "B01-ACC-F1-2:1/1/49"], "dac-passive", "111111", "2×10G", "DAC", TRUNK_F1, "Po11"),
    _cable(["B01-CBL-00013", "B01-CBL-00014"], ["B01-CORE-1:1/1/12", "B01-CORE-2:1/1/12"],
           ["B01-ACC-F2-1:1/1/49", "B01-ACC-F2-2:1/1/49"], "mmf-om4", "00bcd4", "2×10G", "MMF OM4", TRUNK_F2,
           "Po12"),
    _cable(["B01-CBL-00021", "B01-CBL-00022"], ["B01-CORE-1:1/1/21", "B01-CORE-2:1/1/21"],
           ["B01-HV-01:nic1", "B01-HV-01:nic2"], "dac-passive", "111111", "2×10G", "DAC", "40, 45", "Po21"),
    _cable(["B01-CBL-00023", "B01-CBL-00024"], ["B01-CORE-1:1/1/22", "B01-CORE-2:1/1/22"],
           ["B01-HV-02:nic1", "B01-HV-02:nic2"], "dac-passive", "111111", "2×10G", "DAC", "40, 45", "Po22"),
    _cable(["B01-CBL-00025"], ["B01-CORE-1:1/1/23"], ["B01-NAS-01:lan1"], "cat6a", "2196f3", "10G", "Cat6A", "", ""),
    _cable(["B01-CBL-00031"], ["B01-ACC-F1-2:1/1/45"], ["B01-NVR-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["B01-CBL-00032"], ["B01-ACC-F1-2:1/1/46"], ["B01-DOOR-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["B01-CBL-00033"], ["B01-CORE-1:1/1/24"], ["B01-UPS-01:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["B01-CBL-00034"], ["B01-CORE-2:1/1/24"], ["B01-UPS-02:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["B01-CBL-00035"], ["B01-CORE-1:1/1/20"], ["B01-OOB-01:net1"], "cat6", "2196f3", "1G", "Cat6", "", ""),
]
# Endpoint drops on their floor's stack: APs, printers, cameras, the alarm panel, ATMs, recyclers, wire and card.
_FLOOR = {"Floor 1": 1, "Teller line": 1, "Drive-up": 1, "Lobby": 1, "Vault": 1, "Floor 2": 2, "Wire room": 2,
          "Card room": 2}
_port = {1: 1, 2: 1}
_drop = iter(range(101, 1000))
for d in DEVICES:
    floor = _FLOOR.get(d["location"])
    if not floor:
        continue
    stack = f"B01-ACC-F{floor}"
    n = _port[floor]
    _port[floor] += 1
    member = (n - 1) % 2 + 1
    iface = f"1/1/{(n - 1) // 2 + 1}"
    ap = d["role"] == "access-point"
    CABLES.append(_cable([f"B01-CBL-{next(_drop):05d}"], [f"{stack}-{member}:{iface}"], [f"{d['name']}:eth0"],
                         "cat6a" if ap else "cat6", "2196f3", "1G", "Cat6A" if ap else "Cat6",
                         "21, 70, 99" if ap else "", ""))

# A stack member's ports carry its member number (AOS-CX VSF): B01-CORE-2's first port is 2/1/1.
_MEMBER = {d["name"]: int(d["vc_position"]) for d in DEVICES if d["vc_position"]}


def _member_port(end: str) -> str:
    dev, port = end.split(":", 1)
    if _MEMBER.get(dev, 1) > 1 and port.startswith("1/1/"):
        port = f"{_MEMBER[dev]}/1/{port[4:]}"
    return f"{dev}:{port}"


for _c in CABLES:
    _c["a"], _c["b"] = [_member_port(e) for e in _c["a"]], [_member_port(e) for e in _c["b"]]

CIRCUITS = [
    {"cid": "B01-ISP-A-01", "provider": "Provider A", "type": "Dedicated internet access", "speed": "1G",
     "handoff": "B01-FW-01:wan1, B01-FW-02:wan1", "media": "Cat6", "label": "DIA 1G · fiber ONT"},
    {"cid": "B01-ISP-B-01", "provider": "Provider B", "type": "Business cable", "speed": "500/50M",
     "handoff": "B01-FW-01:wan2, B01-FW-02:wan2", "media": "Cat6", "label": "Cable 500/50 · modem"},
    {"cid": "B01-CORE-01", "provider": "Core processor", "type": "Private circuit (provider-managed router)",
     "speed": "100M", "handoff": "B01-CPR-01", "media": "Fiber", "label": "Private 100M · their router B01-CPR-01"},
]

SSIDS = [
    ("NB-STAFF", "WPA3-Enterprise · 802.1X", 21, "zone-staff",
     "Staff laptops on the platform and operations floor; EAP-TLS with device certificates"),
    ("NB-GUEST", "Captive portal · client isolation", 70, "zone-guest",
     "Lobby customers and visitors; internet only, 10 Mb/s per client"),
]
# No SSID reaches teller, wire, card or ATM: those zones are wired only.
BRANCH_SSIDS = [
    ("NB-STAFF", "WPA3-Enterprise · 802.1X", 20, "zone-staff", "Platform staff; same SSID as the main office"),
    ("NB-GUEST", "Captive portal · client isolation", 70, "zone-guest", "Lobby; internet only, local breakout"),
]

# The access VLAN of each end device's switch port. APs trunk: native 99, tagged AP_VLANS.
AP_VLANS = (21, 70)
ACCESS_VLAN = {"printer": 20, "camera": 80, "nvr": 80, "alarm-panel": 81, "door-controller": 81, "ups": 99,
               "console-server": 99, "storage": 45, "atm": 60, "cash-recycler": 10, "wire-workstation": 25,
               "card-printer": 26}

# Flows: id, from, to, what, verdict, conditions, owner
FLOWS = [
    ("F01", "Teller line", "Core processor", "Teller and branch apps · TLS over the private circuit", "Allow",
     "Via B01-CPR-01 only · named ports", "IT"),
    ("F02", "Platform and back office", "Core processor", "Account, loan and operations apps · TLS", "Allow",
     "Via B01-CPR-01 only · named ports", "IT"),
    ("F03", "Teller line", "Internet", "Anything", "Deny", "Logged · updates come from the servers", "IT"),
    ("F04", "Platform and back office", "Internet and SaaS", "Web, email, files, meetings · HTTPS", "Allow",
     "Web filter · TLS inspection on, except banking and health sites", "IT"),
    ("F05", "Teller line, platform and back office", "Servers", "Directory, files, check imaging · named ports",
     "Allow", "", "IT"),
    ("F06", "Wire room", "Federal Reserve (FedLine)", "Wire and ACH origination · FedLine VPN client", "Conditional",
     "B01-WIRE-01/02 only · Fed's published ranges · no other internet", "Operations"),
    ("F07", "Wire room", "Core processor", "Post wires to accounts · TLS", "Allow", "Via B01-CPR-01", "Operations"),
    ("F08", "Any other zone", "Wire room", "Anything", "Deny", "Logged · alert on any hit", "IT"),
    ("F09", "Card issuing", "Card and ATM processor", "Instant-issue card data · TLS", "Conditional",
     "B01-CARD-01 only · via B01-CPR-01", "Card services"),
    ("F10", "Any other zone", "Card issuing", "Anything", "Deny", "Logged · alert on any hit", "IT"),
    ("F11", "ATMs", "Card and ATM processor", "ATM transactions · TLS", "Allow", "Via B01-CPR-01 · ATM VLAN only",
     "Card services"),
    ("F12", "ATM servicer (remote)", "ATMs", "Software and journal pulls", "Conditional",
     "VPN + MFA · booked window · logged", "Card services"),
    ("F13", "Servers", "Core processor", "Nightly files: reports, ACH, positive pay · SFTP", "Conditional",
     "One host · 19:00–06:00", "Operations"),
    ("F14", "Servers", "Cloud backup vault", "Backup replication (immutable) · HTTPS", "Allow",
     "Nightly, 22:00–05:00", "IT"),
    ("F15", "Voice", "Cloud phone service", "SIP, RTP", "Allow", "Provider's published ranges", "IT"),
    ("F16", "Lobby guests", "Internet", "Web", "Allow", "10 Mb/s per client · DNS filter", "Branch manager"),
    ("F17", "Lobby guests", "Any internal zone", "Anything", "Deny", "Logged", "IT"),
    ("F18", "Cameras", "NVR", "Video (RTSP)", "Allow", "Inside zone-security", "Security officer"),
    ("F19", "Alarm panels", "Alarm monitoring center", "Alarm signals · IP, cellular backup", "Conditional",
     "One destination · supervised every 90 s", "Security officer"),
    ("F20", "NVRs, cameras, door controller", "Internet", "Anything", "Deny", "No cloud recording", "Security officer"),
    ("F21", "MSP and IT (remote)", "Network management", "SSH, HTTPS to device management", "Conditional",
     "VPN + MFA · named admins · logged", "IT"),
    ("F22", "Remote staff (VPN)", "Servers, core processor", "Files · core apps", "Conditional",
     "VPN + MFA · bank-owned laptops only", "IT"),
    ("F23", "B02 branch", "B01 main office and core processor", "Teller, staff, ATM traffic · IPsec",
     "Allow", "Same zone rules on B02-FW-01 and at B01", "IT"),
    ("F24", "Every zone but guests", "Network management", "Anything", "Deny", "Logged", "IT"),
    ("F25", "APs (management, VLAN 99)", "Cloud Wi-Fi service", "AP management · HTTPS", "Conditional",
     "Provider's published ranges · APs only", "IT"),
    ("F26", "Every zone", "Firewall services", "DHCP, DNS, NTP", "Allow", "The firewall's own address on each VLAN",
     "IT"),
    ("F27", "Network management, servers", "MSSP log service", "Syslog over TLS · alerts", "Conditional",
     "One destination: the MSSP's collectors", "ISO"),
    # The rooms start these sessions themselves: patched, protected and logged, yet still answering nobody.
    ("F28", "Wire room, card issuing", "Servers (named hosts), MSSP", "Updates, endpoint protection, log forwarding",
     "Conditional", "Named hosts and ports only · initiated from the room", "IT"),
]
