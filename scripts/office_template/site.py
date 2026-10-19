"""Alder & Finch: the fictional office the O01 template is drawn for.

One source for the template's shapes and for the sample NetBox export, so the
two never disagree. Addresses are private or documentation ranges; serials and
circuit IDs are placeholders.
"""

from __future__ import annotations

SITE = {"code": "O01", "name": "Alder & Finch HQ", "slug": "o01"}
BRANCH = {"code": "O02", "name": "Riverside branch", "slug": "o02"}

# Zones: slug, short name, title, band code, what lives there, rule, (fill, stroke, font)
ZONES = [
    ("zone-internet", "INTERNET", "Internet and providers", "OUT", "ISP-A, ISP-B, SaaS, the cloud VNet, home workers",
     "Untrusted. Everything from here ends on the firewall.", ("#F8FAFC", "#CBD5E1", "#475569")),
    ("zone-edge", "EDGE", "Firewall and remote access", "EDGE", "The firewall HA pair, the VPN address pool",
     "The one place zones meet. Every inter-zone packet is inspected here.", ("#F1F5F9", "#94A3B8", "#334155")),
    ("zone-staff", "STAFF", "Staff", "STAFF", "Laptops and desktops, wired and on AF-STAFF",
     "Reaches the internet, servers and printers. Nothing reaches into it.", ("#F4F7FE", "#B3C8F8", "#2563EB")),
    ("zone-voice", "VOICE", "Voice", "STAFF", "Desk phones and meeting-room phones",
     "Talks to the cloud phone service only.", ("#F2F9FC", "#A6D4EB", "#0284C7")),
    ("zone-print", "PRINT", "Printers", "STAFF", "Multifunction printers",
     "Answers staff. Starts nothing, except scan-to-email out.", ("#F4FAF5", "#B4DDBF", "#16A34A")),
    ("zone-servers", "SERVERS", "Servers", "STAFF", "Virtualization hosts, the NAS, backup",
     "Reached from staff and VPN users on named ports. Backs up to the cloud.", ("#F3FAF9", "#AADAD5", "#0D9488")),
    ("zone-meeting", "MEETING", "Meeting rooms", "SHARED", "Room systems and displays",
     "Reaches the cloud meeting service. Staff may cast to it.", ("#F8F5FE", "#D1BAF9", "#7C3AED")),
    ("zone-guest", "GUEST", "Guests", "SHARED", "Visitors' phones and laptops on AF-GUEST",
     "Internet only. Clients can't see each other.", ("#FDF8F3", "#F2CFA8", "#D97706")),
    ("zone-building", "BUILDING", "Building systems", "MGMT", "Cameras, the NVR, door controllers",
     "Cameras talk to the NVR only. The NVR has no internet.", ("#FDF4F9", "#F3B8D6", "#DB2777")),
    ("zone-mgmt", "MGMT", "Network management", "MGMT", "Firewall, switch, AP and UPS management; the console server",
     "Reached only by IT and the MSP, through the VPN with MFA.", ("#F0FAFC", "#A5DCE8", "#0891B2")),
]
ZONE = {z[0]: z for z in ZONES}

BANDS = [
    ("OUT", "OUTSIDE · INTERNET & CLOUD", ("internet", "isp", "wan", "cloud", "saas", "remote-users")),
    ("EDGE", "EDGE · FIREWALL & REMOTE ACCESS", ("edge", "dmz", "vpn", "perimeter")),
    ("STAFF", "STAFF & SERVICES", ("staff", "corp", "it", "voice", "print", "servers", "office")),
    ("SHARED", "SHARED SPACES & GUEST", ("meeting", "guest", "av", "iot")),
    ("MGMT", "BUILDING & MANAGEMENT", ("building", "cameras", "security", "mgmt", "oob")),
]

# VLANs: vid, name, zone, subnet, gateway text, note
VLANS = [
    (10, "STAFF-WIRED", "zone-staff", "10.10.10.0/23", "FW HA .1"),
    (11, "STAFF-WIFI", "zone-staff", "10.10.12.0/22", "FW HA .1"),
    (20, "VOICE", "zone-voice", "10.10.20.0/24", "FW HA .1"),
    (30, "PRINT", "zone-print", "10.10.30.0/24", "FW HA .1"),
    (40, "SERVERS", "zone-servers", "10.10.40.0/24", "FW HA .1"),
    (45, "BACKUP", "zone-servers", "10.10.45.0/24", "FW HA .1"),
    (50, "MEETING", "zone-meeting", "10.10.50.0/24", "FW HA .1"),
    (70, "GUEST", "zone-guest", "172.16.70.0/23", "FW HA .1"),
    (80, "CAMERAS", "zone-building", "10.10.80.0/24", "FW HA .1"),
    (81, "DOOR-ACCESS", "zone-building", "10.10.81.0/24", "FW HA .1"),
    (99, "NET-MGMT", "zone-mgmt", "10.10.99.0/24", "FW HA .1"),
]
BRANCH_VLANS = [
    (10, "STAFF", "zone-staff", "10.20.10.0/24"), (20, "VOICE", "zone-voice", "10.20.20.0/24"),
    (30, "PRINT", "zone-print", "10.20.30.0/24"), (70, "GUEST", "zone-guest", "172.17.70.0/24"),
    (99, "NET-MGMT", "zone-mgmt", "10.20.99.0/24"),
]

ARUBA, FORTI, DELL, SYN, APC, OPEN, RICOH, AXIS, LOGI = (
    "HPE Aruba Networking", "Fortinet", "Dell", "Synology", "APC", "Opengear", "Ricoh", "Axis", "Logitech")


# Asset criticality by role: what stops for the office when the box fails. The firewall pair, the core and the
# hosts take everyone offline; an access stack, the backup target, the UPSes or the suite doors stop a floor or
# a safeguard; the rest inconvenience a room or a desk.
CRITICALITY = {"firewall": "critical", "core-switch": "critical", "hypervisor": "critical",
               "access-switch": "high", "storage": "high", "ups": "high", "door-controller": "high",
               "access-point": "medium", "console-server": "medium", "nvr": "medium",
               "printer": "low", "camera": "low", "room-system": "low"}


def _dev(name, role, mfr, model, platform, location, rack, pos, ip, zone, desc, serial, tag, vc="", vcpos="",
         sw="", contract="", modules="", power="", status="active"):
    return {"name": name, "role": role, "manufacturer": mfr, "device_type": model, "platform": platform,
            "location": location, "rack": rack, "position": pos, "primary_ip4": ip, "tags": zone,
            "description": desc, "serial": serial, "asset_tag": tag, "virtual_chassis": vc, "vc_position": vcpos,
            "status": status, "cf_sw_version": sw, "cf_support_contract": contract,
            "cf_lifecycle": "In support" if contract else "", "x_modules": modules, "x_power": power,
            "cf_ap_mode": "cloud" if role == "access-point" else "", "cf_criticality": CRITICALITY.get(role, "")}


DEVICES = [
    _dev("O01-FW-01", "firewall", FORTI, "FortiGate 120G", "fortios", "COMMS-2", "R01", "40", "10.10.99.2/24",
         "zone-edge", "Internet edge and inter-zone firewall (HA primary)", "FGxxxxxxxxxx01", "AF-0001",
         sw="FortiOS 7.4.x", contract="FortiCare 8x5", modules="x1–x2 SFP+ (DAC to core) · wan1, wan2 RJ45 · ha RJ45",
         power="2× AC PSU"),
    _dev("O01-FW-02", "firewall", FORTI, "FortiGate 120G", "fortios", "COMMS-2", "R02", "40", "10.10.99.3/24",
         "zone-edge", "Internet edge and inter-zone firewall (HA secondary)", "FGxxxxxxxxxx02", "AF-0002",
         sw="FortiOS 7.4.x", contract="FortiCare 8x5", modules="x1–x2 SFP+ (DAC to core) · wan1, wan2 RJ45 · ha RJ45",
         power="2× AC PSU"),
    _dev("O01-OOB-01", "console-server", OPEN, "OM1204-4E-L", "opengear", "COMMS-2", "R01", "41", "10.10.99.5/24",
         "zone-mgmt", "Out-of-band console with cellular", "OMxxxxxx01", "AF-0003", sw="Opengear 24.x",
         modules="4× serial (FW-01, FW-02, CORE-1, CORE-2) · LTE", power="2× DC"),
    _dev("O01-CORE-1", "core-switch", ARUBA, "CX 6300M 24SFP+", "aos-cx", "COMMS-2", "R01", "38", "10.10.99.10/24",
         "zone-mgmt", "Core stack member 1 (conductor)", "SGxxxxxx11", "AF-0010", "O01-CORE", "1",
         sw="AOS-CX 10.13.x", contract="Foundation Care NBD", modules="24× SFP+ · 4× SFP56 · VSF on 1/1/27–28",
         power="2× JL086A"),
    _dev("O01-CORE-2", "core-switch", ARUBA, "CX 6300M 24SFP+", "aos-cx", "COMMS-2", "R02", "38", "",
         "zone-mgmt", "Core stack member 2 (standby)", "SGxxxxxx12", "AF-0011", "O01-CORE", "2",
         sw="AOS-CX 10.13.x", contract="Foundation Care NBD", modules="24× SFP+ · 4× SFP56 · VSF on 2/1/27–28",
         power="2× JL086A"),
] + [
    _dev(f"O01-ACC-F2-{n}", "access-switch", ARUBA, "CX 6200F 48G Class4 PoE", "aos-cx", "COMMS-2", "R02",
         str(37 - n), "10.10.99.21/24" if n == 1 else "", "zone-staff",
         f"Floor 2 access stack member {n}" + (" (conductor)" if n == 1 else ""), f"CNxxxxxx2{n}", f"AF-002{n}",
         "O01-ACC-F2", str(n), sw="AOS-CX 10.13.x", contract="Foundation Care NBD",
         modules="48× 1G Class 4 PoE (740 W) · 4× SFP+", power="1× 740 W PSU")
    for n in (1, 2, 3)
] + [
    _dev(f"O01-ACC-F3-{n}", "access-switch", ARUBA, "CX 6200F 48G Class4 PoE", "aos-cx", "IDF-3", "R01",
         str(22 - n), "10.10.99.22/24" if n == 1 else "", "zone-staff",
         f"Floor 3 access stack member {n}" + (" (conductor)" if n == 1 else ""), f"CNxxxxxx3{n}", f"AF-003{n}",
         "O01-ACC-F3", str(n), sw="AOS-CX 10.13.x", contract="Foundation Care NBD",
         modules="48× 1G Class 4 PoE (740 W) · 4× SFP+ · 10G-SR to core", power="1× 740 W PSU")
    for n in (1, 2)
] + [
    _dev("O01-HV-01", "hypervisor", DELL, "PowerEdge R660xs", "", "COMMS-2", "R01", "30", "10.10.40.11/24",
         "zone-servers", "Virtualization host 1 (file, print, directory VMs)", "SVCTAGxx01", "AF-0040",
         sw="Hypervisor 8.0", contract="ProSupport NBD", modules="2× 10G SFP+ (DAC) · iDRAC 10.10.99.31",
         power="2× 700 W"),
    _dev("O01-HV-02", "hypervisor", DELL, "PowerEdge R660xs", "", "COMMS-2", "R01", "28", "10.10.40.12/24",
         "zone-servers", "Virtualization host 2", "SVCTAGxx02", "AF-0041", sw="Hypervisor 8.0",
         contract="ProSupport NBD", modules="2× 10G SFP+ (DAC) · iDRAC 10.10.99.32", power="2× 700 W"),
    _dev("O01-NAS-01", "storage", SYN, "RS2423RP+", "dsm", "COMMS-2", "R01", "25", "10.10.40.20/24",
         "zone-servers", "Backup target, replicates to the cloud vault", "SYxxxxxx01", "AF-0042", sw="DSM 7.2",
         modules="12 bays · 2× 10G RJ45", power="2× redundant"),
    _dev("O01-UPS-01", "ups", APC, "Smart-UPS SRT 3000", "", "COMMS-2", "R01", "1", "10.10.99.41/24",
         "zone-mgmt", "Rack R01 UPS (network card)", "ASxxxxxx01", "AF-0050", modules="NMC3 network card",
         power="3 kVA · about 18 min at today's load"),
    _dev("O01-UPS-02", "ups", APC, "Smart-UPS SRT 3000", "", "COMMS-2", "R02", "1", "10.10.99.42/24",
         "zone-mgmt", "Rack R02 UPS (network card)", "ASxxxxxx02", "AF-0051", modules="NMC3 network card",
         power="3 kVA · about 22 min at today's load"),
    _dev("O01-NVR-01", "nvr", AXIS, "S3016", "", "COMMS-2", "R02", "30", "10.10.80.10/24", "zone-building",
         "Video recorder for 10 cameras", "AXxxxxxx01", "AF-0060", modules="16 TB"),
    _dev("O01-DOOR-01", "door-controller", AXIS, "A1601", "", "COMMS-2", "", "", "10.10.81.10/24", "zone-building",
         "Suite door controller (tenant doors only)", "AXxxxxxx02", "AF-0061"),
]
for floor in (2, 3):
    for n in range(1, 9):
        DEVICES.append(_dev(f"O01-AP-F{floor}-{n:02d}", "access-point", ARUBA, "AP-635", "aos-ap", f"Floor {floor}", "",
                            "", f"10.10.99.{100 + (floor - 2) * 10 + n}/24", "zone-staff",
                            f"Floor {floor} ceiling AP {n}", f"CNAPxx{floor}{n:02d}", ""))
    for n in (1, 2):
        DEVICES.append(_dev(f"O01-PRN-F{floor}-{n:02d}", "printer", RICOH, "IM C3000", "", f"Floor {floor}", "", "",
                            f"10.10.30.{10 + (floor - 2) * 2 + n}/24", "zone-print", f"Floor {floor} print corner",
                            f"RCxxxxx{floor}{n}", ""))
    for room in "ABC":
        DEVICES.append(_dev(f"O01-MR-{floor}{room}", "room-system", LOGI, "Rally Bar", "", f"Floor {floor}", "", "",
                            f"10.10.50.{10 + (floor - 2) * 3 + 'ABC'.index(room) + 1}/24", "zone-meeting",
                            f"Meeting room {floor}{room}", f"LGxxxx{floor}{room}", ""))
for n in range(1, 11):
    DEVICES.append(_dev(f"O01-CAM-{n:02d}", "camera", AXIS, "P3268-LV", "", "Floor 2" if n <= 6 else "Floor 3", "", "",
                        f"10.10.80.{20 + n}/24", "zone-building", "Entrance and corridor camera", f"AXCAMxx{n:02d}", ""))

BRANCH_DEVICES = [
    _dev("O02-FW-01", "firewall", FORTI, "FortiGate 40F-3G4G", "fortios", "CAB-1", "CAB-1", "8", "10.20.99.2/24",
         "zone-edge", "Branch firewall with cellular backup", "FGxxxxxxxx21", "AF-0201", sw="FortiOS 7.4.x"),
    _dev("O02-ACC-1", "access-switch", ARUBA, "CX 6100 24G Class4 PoE", "aos-cx", "CAB-1", "CAB-1", "10", "10.20.99.10/24",
         "zone-staff", "Branch access switch", "CNxxxxxx41", "AF-0202", sw="AOS-CX 10.13.x"),
    _dev("O02-AP-01", "access-point", ARUBA, "AP-615", "aos-ap", "Ground floor", "", "", "10.20.99.101/24",
         "zone-staff", "Branch ceiling AP 1", "CNAPxx41", ""),
    _dev("O02-AP-02", "access-point", ARUBA, "AP-615", "aos-ap", "Ground floor", "", "", "10.20.99.102/24",
         "zone-staff", "Branch ceiling AP 2", "CNAPxx42", ""),
    _dev("O02-PRN-01", "printer", RICOH, "IM C3000", "", "Ground floor", "", "", "10.20.30.11/24", "zone-print",
         "Branch printer", "RCxxxxx41", ""),
]

# Links: label(s), A ends, B ends, type, color, speed, media, VLANs (tagged), name
def _cable(labels, a, b, ctype, color, speed, media, vlans="", lag=""):
    return {"labels": labels, "a": a, "b": b, "type": ctype, "color": color, "speed": speed, "media": media,
            "vlans": vlans, "lag": lag}


TRUNK = "10, 11, 20, 30, 50, 70, 80, 81, 99"
CABLES = [
    _cable(["O01-CBL-00001", "O01-CBL-00002"], ["O01-FW-01:x1", "O01-FW-01:x2"],
           ["O01-CORE-1:1/1/1", "O01-CORE-2:1/1/1"], "dac-passive", "111111", "2×10G", "DAC",
           "10, 11, 20, 30, 40, 45, 50, 70, 80, 81, 99", "Po1"),
    _cable(["O01-CBL-00003", "O01-CBL-00004"], ["O01-FW-02:x1", "O01-FW-02:x2"],
           ["O01-CORE-1:1/1/2", "O01-CORE-2:1/1/2"], "dac-passive", "111111", "2×10G", "DAC",
           "10, 11, 20, 30, 40, 45, 50, 70, 80, 81, 99", "Po2"),
    _cable(["O01-CBL-00005"], ["O01-FW-01:ha"], ["O01-FW-02:ha"], "cat6", "9e9e9e", "1G", "Cat6", "", "HA"),
    _cable(["O01-CBL-00011", "O01-CBL-00012"], ["O01-CORE-1:1/1/11", "O01-CORE-2:1/1/11"],
           ["O01-ACC-F2-1:1/1/49", "O01-ACC-F2-3:1/1/49"], "dac-passive", "111111", "2×10G", "DAC", TRUNK, "Po11"),
    _cable(["O01-CBL-00013", "O01-CBL-00014"], ["O01-CORE-1:1/1/12", "O01-CORE-2:1/1/12"],
           ["O01-ACC-F3-1:1/1/49", "O01-ACC-F3-2:1/1/49"], "mmf-om4", "00bcd4", "2×10G", "MMF OM4",
           "10, 11, 20, 30, 50, 70, 99", "Po12"),
    _cable(["O01-CBL-00021", "O01-CBL-00022"], ["O01-CORE-1:1/1/21", "O01-CORE-2:1/1/21"],
           ["O01-HV-01:nic1", "O01-HV-01:nic2"], "dac-passive", "111111", "2×10G", "DAC", "40, 45", "Po21"),
    _cable(["O01-CBL-00023", "O01-CBL-00024"], ["O01-CORE-1:1/1/22", "O01-CORE-2:1/1/22"],
           ["O01-HV-02:nic1", "O01-HV-02:nic2"], "dac-passive", "111111", "2×10G", "DAC", "40, 45", "Po22"),
    _cable(["O01-CBL-00025"], ["O01-CORE-1:1/1/23"], ["O01-NAS-01:lan1"], "cat6a", "2196f3", "10G", "Cat6A", "", ""),
    _cable(["O01-CBL-00031"], ["O01-ACC-F2-2:1/1/45"], ["O01-NVR-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["O01-CBL-00032"], ["O01-ACC-F2-2:1/1/46"], ["O01-DOOR-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    # Management drops on the core: 1G copper SFPs, in the rack beside the gear they watch.
    _cable(["O01-CBL-00033"], ["O01-CORE-1:1/1/24"], ["O01-UPS-01:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["O01-CBL-00034"], ["O01-CORE-2:1/1/24"], ["O01-UPS-02:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["O01-CBL-00035"], ["O01-CORE-1:1/1/20"], ["O01-OOB-01:net1"], "cat6", "2196f3", "1G", "Cat6", "", ""),
]
# Endpoint drops: APs, printers, meeting rooms and cameras on their floor's stack.
_port = {2: 1, 3: 1}
_drop = iter(range(101, 1000))
for d in DEVICES:
    floor = d["location"][-1:] if d["location"].startswith("Floor") else ""
    if not floor:
        continue
    stack = f"O01-ACC-F{floor}"
    members = 3 if floor == "2" else 2
    n = _port[int(floor)]
    _port[int(floor)] += 1
    member = (n - 1) % members + 1
    iface = f"1/1/{(n - 1) // members + 1}"
    CABLES.append(_cable([f"O01-CBL-{next(_drop):05d}"], [f"{stack}-{member}:{iface}"], [f"{d['name']}:eth0"],
                         "cat6a" if d["role"] == "access-point" else "cat6", "2196f3", "1G", "Cat6A" if d["role"] ==
                         "access-point" else "Cat6", "11, 50, 70, 99" if d["role"] == "access-point" else "", ""))

# A stack member's ports carry its member number (AOS-CX VSF): O01-CORE-2's first port is 2/1/1.
_MEMBER = {d["name"]: int(d["vc_position"]) for d in DEVICES if d["vc_position"]}


def _member_port(end: str) -> str:
    dev, port = end.split(":", 1)
    if _MEMBER.get(dev, 1) > 1 and port.startswith("1/1/"):
        port = f"{_MEMBER[dev]}/1/{port[4:]}"
    return f"{dev}:{port}"


for _c in CABLES:
    _c["a"], _c["b"] = [_member_port(e) for e in _c["a"]], [_member_port(e) for e in _c["b"]]

CIRCUITS = [
    {"cid": "O01-ISP-A-01", "provider": "Provider A", "type": "Dedicated internet access", "speed": "1G",
     "handoff": "O01-FW-01:wan1, O01-FW-02:wan1", "media": "Cat6", "label": "DIA 1G · fiber ONT"},
    {"cid": "O01-ISP-B-01", "provider": "Provider B", "type": "Business cable", "speed": "500/50M",
     "handoff": "O01-FW-01:wan2, O01-FW-02:wan2", "media": "Cat6", "label": "Cable 500/50 · modem"},
]

SSIDS = [
    ("AF-STAFF", "WPA3-Enterprise · 802.1X", 11, "zone-staff", "Staff laptops and phones; EAP-TLS with device certificates, dynamic VLAN off"),
    ("AF-GUEST", "Captive portal · client isolation", 70, "zone-guest", "Visitors; internet only, 25 Mb/s per client"),
    ("AF-DEVICES", "WPA3-Personal · PSK rotated quarterly and on leavers", 50, "zone-meeting", "Meeting-room systems only; key rotated quarterly and on leavers"),
]

# Riverside (O02) runs the same two SSIDs as HQ's staff and guest, on its own VLANs, from the same cloud dashboard.
BRANCH_SSIDS = [
    ("AF-STAFF", "WPA3-Enterprise · 802.1X", 10, "zone-staff", "Staff laptops and phones; same SSID as HQ"),
    ("AF-GUEST", "Captive portal · client isolation", 70, "zone-guest", "Visitors; internet only, local breakout"),
]

# The access VLAN of each end device's switch port. APs trunk: native 99, tagged AP_VLANS.
AP_VLANS = (11, 50, 70)
ACCESS_VLAN = {"printer": 30, "room-system": 50, "camera": 80, "nvr": 80, "door-controller": 81, "ups": 99,
               "console-server": 99, "storage": 45}

# Flows: id, from, to, what, verdict, conditions, owner
FLOWS = [
    ("F01", "Staff", "Internet and SaaS", "Web, email, files, meetings · HTTPS", "Allow", "Web filter, TLS inspection off for banking", "IT"),
    ("F02", "Staff", "Servers", "File shares (SMB) · accounting app (HTTPS)", "Allow", "Named ports only", "IT"),
    ("F03", "Staff", "Printers", "IPP, 9100 · printer web page", "Allow", "", "IT"),
    ("F04", "Printers", "Staff", "Anything a printer starts", "Deny", "Logged", "IT"),
    ("F05", "Printers", "Internet (mail relay)", "Scan-to-email · SMTP submission", "Conditional", "One destination: the SaaS relay", "IT"),
    ("F06", "Voice", "Cloud phone service", "SIP, RTP", "Allow", "Provider's published ranges", "Office manager"),
    ("F07", "Guests", "Internet", "Web", "Allow", "25 Mb/s per client · DNS filter", "Office manager"),
    ("F08", "Guests", "Any internal zone", "Anything", "Deny", "Logged", "IT"),
    ("F09", "Meeting rooms", "Cloud meeting service", "Meeting traffic", "Allow", "Provider's published ranges", "IT"),
    ("F10", "Staff", "Meeting rooms", "Casting to the room display", "Conditional", "Casting ports only", "IT"),
    ("F11", "Cameras", "NVR", "Video (RTSP)", "Allow", "Inside zone-building", "Facilities"),
    ("F12", "NVR, cameras, door controller", "Internet", "Anything", "Deny", "No cloud recording", "Facilities"),
    ("F13", "MSP (remote)", "Network management", "SSH, HTTPS to device management", "Conditional", "VPN + MFA · booked window · logged", "IT"),
    ("F14", "Remote staff (VPN)", "Servers", "File shares · accounting app", "Allow", "VPN + MFA", "IT"),
    ("F15", "Servers", "Cloud VNet", "Backup replication · accounting back end (IPsec)", "Allow", "Backups nightly, 22:00–05:00", "IT"),
    ("F16", "O02 branch", "HQ servers", "File shares · accounting app (IPsec)", "Allow", "Site-to-site tunnel", "IT"),
    ("F17", "Staff, guests, meeting, building", "Network management", "Anything", "Deny", "Logged", "IT"),
    ("F18", "APs (management, VLAN 99)", "Cloud Wi-Fi service", "AP management and config · HTTPS", "Conditional", "Provider's published ranges · APs only", "IT"),
    ("F19", "APs (management, VLAN 99)", "Cloud identity (RADIUS)", "802.1X for AF-STAFF · RADIUS over TLS", "Conditional", "Identity service's ranges · APs only", "IT"),
    ("F20", "Every zone", "Firewall services", "DHCP, DNS, NTP", "Allow", "The firewall's own address on each VLAN", "IT"),
    ("F21", "Network management", "MSP monitoring and SIEM", "Syslog over TLS · monitoring", "Conditional", "One destination: the MSP's collectors", "IT"),
]
