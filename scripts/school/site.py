"""Harbor Pines High School (HS1): the fictional school the education template is drawn for.

One table of facts feeds both the drawing (``pages.py``) and the sample NetBox
export, so ``netdiagrams build --template education --input`` on the export
reproduces the template.

Harbor Pines School District (HPSD) is fictional: a district office with the
data center and internet edge, a high school, a middle school, two elementary
schools and a transportation yard. Addresses, serial numbers and circuit IDs are
placeholders.
"""

from __future__ import annotations

import ipaddress
import re

from sample_kit import model_lifecycle

DISTRICT = "Harbor Pines School District"
SITE_CODE = "HS1"
SITE_NAME = "Harbor Pines High School"
SITE_SLUG = "hs1"

# ------------------------------------------------------------------ zones
# slug, title, subtitle, color key, VRF
ZONES = [
    ("staff", "Staff & classrooms", "Teachers' laptops, phones, printers, classroom displays", "staff", "STAFF"),
    ("admin", "Front office & student services", "Office, nurse and counseling: student records live here",
     "admin", "ADMIN"),
    ("student", "Student devices", "1:1 Chromebooks, labs, state testing", "student", "STUDENT"),
    ("guest", "Guest & BYOD", "Visitors and personal phones: internet only, filtered", "guest", "GUEST"),
    ("svc", "School services", "The meeting point: NVR, door access, PA and BAS servers, local cache", "svc",
     "SVC"),
    ("bldg", "Building systems", "Cameras, door controllers, HVAC, PA, bells and clocks", "bldg", "BLDG"),
    ("mgmt", "Network management", "Switch, AP, firewall and OOB management only", "mgmt", "MGMT"),
]
ZONE_VRF = {z[0]: z[4] for z in ZONES}

# VLAN id, name, subnet, gateway text (device .host · VRF), zone
VLANS = [
    (110, "STAFF-WIRED", "10.20.10.0/24", "CORE .1 · STAFF", "staff"),
    (120, "STAFF-WIFI", "10.20.12.0/22", "CORE .1 · STAFF", "staff"),
    (130, "VOICE", "10.20.30.0/24", "CORE .1 · STAFF", "staff"),
    (140, "PRINTERS", "10.20.40.0/24", "CORE .1 · STAFF", "staff"),
    (150, "CLASS-AV", "10.20.50.0/24", "CORE .1 · STAFF", "staff"),
    (199, "TR-STAFF", "10.20.255.0/29", "CORE .1 / FW .2", "staff"),
    (160, "OFFICE", "10.20.60.0/25", "CORE .1 · ADMIN", "admin"),
    (165, "HEALTH", "10.20.60.128/26", "CORE .129 · ADMIN", "admin"),
    (169, "TR-ADMIN", "10.20.255.8/29", "CORE .9 / FW .10", "admin"),
    (210, "STUDENT-WIFI", "10.20.64.0/19", "CORE .1 · STUDENT", "student"),
    (220, "STUDENT-LABS", "10.20.96.0/23", "CORE .1 · STUDENT", "student"),
    (230, "TESTING", "10.20.98.0/24", "CORE .1 · STUDENT", "student"),
    (299, "TR-STUDENT", "10.20.255.16/29", "CORE .17 / FW .18", "student"),
    (310, "GUEST-WIFI", "172.20.0.0/22", "FW-01 .1 · GUEST", "guest"),
    (320, "BYOD", "172.20.8.0/21", "FW-01 .1 · GUEST", "guest"),
    (510, "SERVERS", "10.20.200.0/26", "CORE .1 · SVC", "svc"),
    (520, "VMS", "10.20.200.64/27", "CORE .65 · SVC", "svc"),
    (599, "TR-SVC", "10.20.255.40/29", "CORE .41 / FW .42", "svc"),
    (410, "CAMERAS", "10.20.140.0/23", "CORE .1 · BLDG", "bldg"),
    (420, "DOOR-ACCESS", "10.20.142.0/24", "CORE .1 · BLDG", "bldg"),
    (430, "HVAC-BAS", "10.20.143.0/24", "CORE .1 · BLDG", "bldg"),
    (440, "PA-CLOCKS", "10.20.144.0/24", "CORE .1 · BLDG", "bldg"),
    (499, "TR-BLDG", "10.20.255.32/29", "CORE .33 / FW .34", "bldg"),
    (900, "NET-MGMT", "10.20.250.0/24", "CORE .1 · MGMT", "mgmt"),
    (910, "AP-MGMT", "10.20.248.0/23", "CORE .1 · MGMT", "mgmt"),
    (999, "TR-MGMT", "10.20.255.48/29", "CORE .49 / FW .50", "mgmt"),
]

# Wireless LANs: SSID, security, VLAN, controller note, bands
WLANS = [
    ("HPSD-STAFF", "WPA3-Enterprise (802.1X)", 120, "GW pair · tunneled", "5 · 6 GHz"),
    ("HPSD-STUDENT", "WPA3-Enterprise (802.1X)", 210, "GW pair · tunneled", "5 · 6 GHz"),
    ("HPSD-BYOD", "WPA3-Personal (rotating PSK)", 320, "GW pair · tunneled", "5 GHz"),
    ("HPSD-GUEST", "Open + captive portal (OWE)", 310, "GW pair · tunneled", "2.4 · 5 GHz"),
    ("HPSD-DEVICES", "WPA2-Personal (per-device PSK)", 150, "GW pair · tunneled", "2.4 · 5 GHz"),
    ("HPSD-BLDG", "WPA2-Personal (per-device PSK)", 430, "GW pair · tunneled", "2.4 GHz"),
]
# What NetBox itself stores for each kind (wireless.WirelessLAN auth_type / auth_cipher choices)
NB_AUTH = {"wpa-enterprise": "WPA Enterprise", "wpa-personal": "WPA Personal (PSK)", "open": "Open"}
WLAN_GROUP = {"id": 1, "name": "HPSD district", "slug": "hpsd-district"}
# The netbox-setup wlan_* fields per SSID: security, EAP method, bands, client isolation, portal, who it is for.
# NetBox holds no key: the BYOD key and the per-device keys live in the district's password vault.
WLAN_FIELDS = {
    "HPSD-STAFF": ("wpa3-enterprise", "EAP-TLS", ["5ghz", "6ghz"], None, "",
                   "Staff laptops, device certificate"),
    "HPSD-STUDENT": ("wpa3-enterprise", "EAP-TLS", ["5ghz", "6ghz"], None, "",
                     "Chromebooks, certificate; TESTING → 230"),
    "HPSD-BYOD": ("wpa3-sae", "", ["5ghz"], True, "none", "Personal phones; key rotates monthly"),
    "HPSD-GUEST": ("owe", "", ["2.4ghz", "5ghz"], True, "captive", "Visitors; portal, 4 h"),
    "HPSD-DEVICES": ("mpsk", "", ["2.4ghz", "5ghz"], None, "", "Displays and casting receivers"),
    "HPSD-BLDG": ("mpsk", "", ["2.4ghz"], None, "", "HVAC sensors, thermostats, signage"),
}
# How the APs are run: the gateway pair is the controller; configuration and firmware come from the
# vendor's cloud dashboard, which the district NOC uses for every school.
WIRELESS_SITE_FIELDS = {"wireless_management": "controller",
                        "wireless_manager": "Cloud dashboard (district NOC) · HS1-GW pair on site",
                        "wireless_survey": "https://hpsd.example/wireless/hs1-survey-2026-06"}
# Radios per AP model: (interface, band, channel, width in MHz). The 2.4 GHz plan is 1/6/11 at 20 MHz.
AP_RADIOS = {
    "AP-635": [("radio0", "2.4ghz", "2.4g-6-2437-20", 20), ("radio1", "5ghz", "5g-36-5180-40", 40),
               ("radio2", "6ghz", "6g-5-5975-80", 80)],
    "AP-655": [("radio0", "2.4ghz", "2.4g-11-2462-20", 20), ("radio1", "5ghz", "5g-149-5745-40", 40),
               ("radio2", "6ghz", "6g-37-6135-80", 80)],
    "AP-575": [("radio0", "2.4ghz", "2.4g-1-2412-20", 20), ("radio1", "5ghz", "5g-100-5500-40", 40)],
}

# ------------------------------------------------------------------ devices
ARUBA, FORTINET, DELL, AXIS = "Aruba", "Fortinet", "Dell", "Axis"


NAMING_PATTERN = r"^(DO|(HS|MS|ES|TY)\d)-[A-Z0-9]+(-[A-Z0-9]+)*$"

# NetBox device role names (the slugs are what the template matches on).
ROLE_NAMES = {
    "firewall": "Firewall", "core-switch": "Core switch", "access-switch": "Access switch",
    "wireless-controller": "Wireless gateway", "access-point": "Access point", "ptp-radio": "PtP radio",
    "hypervisor": "Hypervisor", "nvr": "NVR / VMS server", "camera": "Camera", "access-control": "Door controller",
    "bas-controller": "BAS controller", "pa-system": "PA / bells / clocks", "oob-switch": "OOB switch",
}


# Asset criticality by role: what stops when it fails. Critical is the school day itself (internet,
# core, Wi-Fi) and life safety (lockdown doors, emergency announcements).
CRITICALITY = {"firewall": "critical", "core-switch": "critical", "wireless-controller": "critical",
               "access-control": "critical", "pa-system": "critical",
               "access-switch": "high", "hypervisor": "high", "nvr": "high",
               "access-point": "medium", "ptp-radio": "medium", "bas-controller": "medium", "oob-switch": "medium",
               "camera": "low"}


def _dev(name, role, mfr, model, platform, serial, location, rack, position, ip, zone, desc, vc="", vcpos="",
         sw="", x=None, asset=""):
    return {"name": name, "role": role, "manufacturer": mfr, "device_type": model, "platform": platform,
            "serial": serial, "asset_tag": asset, "status": "active", "site": SITE_CODE, "location": location,
            "rack": rack, "position": str(position) if position else "", "face": "front" if position else "",
            "primary_ip4": ip, "virtual_chassis": vc, "vc_position": str(vcpos) if vcpos else "",
            "description": desc, "tags": [f"zone-{zone}"] if zone else [],
            "cf": {**({"sw_version": sw} if sw else {}), "criticality": CRITICALITY[role]}, "x": x or {}}


AOS = "aruba-aos-cx"
DEVICES = [
    _dev("HS1-FW-01", "firewall", FORTINET, "FortiGate 200F", "fortios", "FG200Fxxxx01", "MDF-101", "R01", 40,
         "10.20.250.2/24", "mgmt", "School firewall (HA active)", sw="FortiOS 7.4.x", asset="HPSD-0101",
         x={"modules": "8× SFP+ · 8× SFP · 16× RJ45", "power": "2× PSU"}),
    _dev("HS1-FW-02", "firewall", FORTINET, "FortiGate 200F", "fortios", "FG200Fxxxx02", "MDF-101", "R02", 40,
         "10.20.250.3/24", "mgmt", "School firewall (HA passive)", sw="FortiOS 7.4.x", asset="HPSD-0102"),
    _dev("HS1-CORE-1", "core-switch", ARUBA, "CX 8360-32Y4C", AOS, "TWxxxxxx11", "MDF-101", "R01", 37,
         "10.20.250.4/24", "mgmt", "Collapsed core (VSX primary)", vc="HS1-CORE", vcpos=1, sw="AOS-CX 10.13.x",
         asset="HPSD-0103", x={"modules": "32× SFP28 + 4× QSFP28", "power": "2× PSU · fan tray"}),
    _dev("HS1-CORE-2", "core-switch", ARUBA, "CX 8360-32Y4C", AOS, "TWxxxxxx12", "MDF-101", "R02", 37,
         "10.20.250.5/24", "mgmt", "Collapsed core (VSX secondary)", vc="HS1-CORE", vcpos=2, sw="AOS-CX 10.13.x",
         asset="HPSD-0104"),
    _dev("HS1-GW-01", "wireless-controller", ARUBA, "9240 Gateway", "aruba-aos", "CNxxxxxx21", "MDF-101", "R01", 34,
         "10.20.250.6/24", "mgmt", "Wireless gateway (cluster)", vc="", sw="AOS 10.6.x", asset="HPSD-0105"),
    _dev("HS1-GW-02", "wireless-controller", ARUBA, "9240 Gateway", "aruba-aos", "CNxxxxxx22", "MDF-101", "R02", 34,
         "10.20.250.7/24", "mgmt", "Wireless gateway (cluster)", sw="AOS 10.6.x", asset="HPSD-0106"),
    _dev("HS1-SRV-01", "hypervisor", DELL, "PowerEdge R660", "vmware-esxi", "7Hxxxx31", "MDF-101", "R02", 30,
         "10.20.250.10/24", "svc", "Local services host: cache, print, imaging", sw="ESXi 8.0", asset="HPSD-0107"),
    _dev("HS1-NVR-01", "nvr", DELL, "PowerEdge R760xd2", "windows", "7Hxxxx32", "MDF-101", "R02", 26,
         "10.20.200.70/27", "svc", "Camera recorder and VMS (90 days)", sw="VMS 6.x", asset="HPSD-0108"),
    _dev("HS1-PA-01", "pa-system", "Generic", "IP PA and bell server", "linux", "PAxxxxxx41", "MDF-101", "R01", 28,
         "10.20.200.12/26", "svc", "PA, bells, clocks and intercom server", asset="HPSD-0109"),
    _dev("HS1-ACS-01", "access-control", "Generic", "Door controller (8 doors)", "", "ACxxxxxx42", "MDF-101", "",
         "", "10.20.142.10/24", "bldg", "Door access panel: main entry, office, A and B wings", asset="HPSD-0110"),
    _dev("HS1-OOB-SW01", "oob-switch", ARUBA, "CX 6100 12G", AOS, "TWxxxxxx51", "MDF-101", "R01", 42,
         "10.20.251.2/28", "mgmt", "Out-of-band management", sw="AOS-CX 10.13.x", asset="HPSD-0111"),
    _dev("HS1-ACC-MDF-1", "access-switch", ARUBA, "CX 6300M 48P", AOS, "SGxxxxxx61", "MDF-101", "R01", 20,
         "10.20.250.20/24", "mgmt", "Front office and admin wing (VSF 1)", vc="HS1-ACC-MDF", vcpos=1,
         sw="AOS-CX 10.13.x", asset="HPSD-0112"),
    _dev("HS1-ACC-MDF-2", "access-switch", ARUBA, "CX 6300M 48P", AOS, "SGxxxxxx62", "MDF-101", "R01", 19,
         "10.20.250.21/24", "mgmt", "Front office and admin wing (VSF 2)", vc="HS1-ACC-MDF", vcpos=2,
         sw="AOS-CX 10.13.x", asset="HPSD-0113"),
]
IDFS = [  # key, room, rack, members, ip base, description, media of uplinks
    ("A", "IDF-A118", "A1", 3, 31, "A wing classrooms 100-130", "SMF OS2"),
    ("B", "IDF-B214", "B1", 3, 41, "B wing classrooms 200-230 and library", "SMF OS2"),
    ("C", "IDF-C010", "C1", 2, 51, "Gym, auditorium and cafeteria", "MMF OM4"),
    ("D", "IDF-D305", "D1", 2, 61, "CTE shops and science labs", "SMF OS2"),
]
for key, room, rack, members, base, desc, _ in IDFS:
    for m in range(1, members + 1):
        DEVICES.append(_dev(f"HS1-ACC-IDF{key}-{m}", "access-switch", ARUBA, "CX 6300M 48P", AOS,
                            f"SGxxxxx{base}{m}", room, rack, 40 - m, f"10.20.250.{base + m - 1}/24", "mgmt",
                            f"{desc} (VSF {m})", vc=f"HS1-ACC-IDF{key}", vcpos=m, sw="AOS-CX 10.13.x",
                            asset=f"HPSD-02{base}{m}"))
DEVICES += [
    _dev("HS1-PTP-A", "ptp-radio", "Generic", "60 GHz PtP radio", "", "PTxxxxxx71", "ROOF-B", "", "",
         "10.20.250.72/24", "mgmt", "Stadium link, B wing roof end", asset="HPSD-0371"),
    _dev("HS1-PTP-B", "ptp-radio", "Generic", "60 GHz PtP radio", "", "PTxxxxxx72", "STADIUM-PB", "", "",
         "10.20.250.73/24", "mgmt", "Stadium link, press box end", asset="HPSD-0372"),
    _dev("HS1-ACC-STAD-1", "access-switch", ARUBA, "CX 6100 12G PoE", AOS, "TWxxxxxx73", "STADIUM-PB", "", "",
         "10.20.250.71/24", "mgmt", "Stadium press box: scoreboard, AP, cameras",
         sw="AOS-CX 10.13.x", asset="HPSD-0373"),
    _dev("HS1-BAS-01", "bas-controller", "Generic", "BACnet/IP supervisor", "", "BAxxxxxx81",
         "D-BOILER", "", "", "10.20.143.10/24", "bldg", "HVAC supervisory controller, boiler room",
         asset="HPSD-0381"),
]
APS = [  # name, switch, location, model
    ("HS1-AP-ADM1", "HS1-ACC-MDF-1", "Front office", "AP-635"),
    ("HS1-AP-A101", "HS1-ACC-IDFA-1", "Room A101", "AP-635"),
    ("HS1-AP-A120", "HS1-ACC-IDFA-2", "Room A120", "AP-635"),
    ("HS1-AP-B201", "HS1-ACC-IDFB-1", "Library", "AP-635"),
    ("HS1-AP-B230", "HS1-ACC-IDFB-3", "Room B230", "AP-635"),
    ("HS1-AP-C-GYM1", "HS1-ACC-IDFC-1", "Main gym", "AP-655"),
    ("HS1-AP-C-AUD1", "HS1-ACC-IDFC-2", "Auditorium", "AP-655"),
    ("HS1-AP-D301", "HS1-ACC-IDFD-1", "CTE shop", "AP-635"),
    ("HS1-AP-STAD1", "HS1-ACC-STAD-1", "Stadium bleachers", "AP-575"),
]
FIRST_APS = list(APS)
# Added later: the bus loop's outdoor AP is drawn; the other two are in NetBox only, so the build
# folds each into the drawn AP on the same switch and the wing card reads "AP ×2".
LATE_APS = [("HS1-AP-BUS1", "HS1-ACC-IDFD-2", "Bus loop", "AP-575")]
NETBOX_ONLY_APS = [("HS1-AP-A110", "HS1-ACC-IDFA-1", "Room A110", "AP-635"),
                   ("HS1-AP-B202", "HS1-ACC-IDFB-1", "Library", "AP-635")]
APS += LATE_APS
for i, (name, _, loc, model) in enumerate(APS + NETBOX_ONLY_APS):
    DEVICES.append(_dev(name, "access-point", ARUBA, model, "aruba-aos", f"CNxxxxx9{i:02d}", loc, "", "",
                        f"10.20.248.{11 + i}/23", "mgmt", f"AP, {loc}", asset=f"HPSD-05{i:02d}"))
CAMERAS = [  # name, switch, location
    ("HS1-CAM-MDF01", "HS1-ACC-MDF-2", "Main entry"),
    ("HS1-CAM-A01", "HS1-ACC-IDFA-3", "A wing corridor"),
    ("HS1-CAM-B01", "HS1-ACC-IDFB-2", "B wing corridor"),
    ("HS1-CAM-C01", "HS1-ACC-IDFC-2", "Cafeteria"),
    ("HS1-CAM-D01", "HS1-ACC-IDFD-2", "Bus loop"),
    ("HS1-CAM-STAD1", "HS1-ACC-STAD-1", "Stadium gate"),
]
for i, (name, _, loc) in enumerate(CAMERAS):
    DEVICES.append(_dev(name, "camera", AXIS, "P3265-LVE", "", f"ACCCxxxx{i:02d}", loc, "", "",
                        f"10.20.140.{11 + i}/23", "bldg", f"Camera, {loc}", asset=f"HPSD-06{i:02d}"))

BY_NAME = {d["name"]: d for d in DEVICES}

# NetBox location tree: campus › building › floor › closet or room. Every device sits in a leaf.
# name, parent, description (buildings and floors carry no devices of their own)
LOCATIONS = [
    ("Main building", None, "Two stories: office and A wing below, B wing and library above"),
    ("Main · floor 1", "Main building", "Front office, MDF, A wing classrooms 100-130"),
    ("Main · floor 2", "Main building", "B wing classrooms 200-230 and library"),
    ("Main · roof", "Main building", "B wing roof: stadium radio"),
    ("Commons", None, "One story: gym, auditorium, cafeteria"),
    ("Commons · floor 0", "Commons", "Ground floor; the closet is under the stage"),
    ("Science and CTE building", None, "Three stories over a boiler room, across the bus loop"),
    ("CTE · lower level", "Science and CTE building", "Boiler room"),
    ("CTE · floor 1", "Science and CTE building", "CTE shops"),
    ("CTE · floor 3", "Science and CTE building", "Science labs and the building's closet"),
    ("Stadium", None, "Outbuilding: press box, bleachers, gate"),
    ("Grounds", None, "Outdoors: bus loop"),
    ("MDF-101", "Main · floor 1", "Main closet"), ("Front office", "Main · floor 1", ""),
    ("Main entry", "Main · floor 1", ""), ("IDF-A118", "Main · floor 1", "A wing closet"),
    ("Room A101", "Main · floor 1", ""), ("Room A110", "Main · floor 1", ""), ("Room A120", "Main · floor 1", ""),
    ("A wing corridor", "Main · floor 1", ""),
    ("IDF-B214", "Main · floor 2", "B wing closet"), ("Room B230", "Main · floor 2", ""),
    ("Library", "Main · floor 2", ""), ("B wing corridor", "Main · floor 2", ""),
    ("ROOF-B", "Main · roof", "Radio mast"),
    ("IDF-C010", "Commons · floor 0", "Commons closet"), ("Main gym", "Commons · floor 0", ""),
    ("Auditorium", "Commons · floor 0", ""), ("Cafeteria", "Commons · floor 0", ""),
    ("D-BOILER", "CTE · lower level", "Boiler room"), ("CTE shop", "CTE · floor 1", ""),
    ("IDF-D305", "CTE · floor 3", "Science and CTE closet"),
    ("STADIUM-PB", "Stadium", "Press box"), ("Stadium bleachers", "Stadium", ""),
    ("Stadium gate", "Stadium", ""), ("Bus loop", "Grounds", ""),
]

# ------------------------------------------------------------------ cables
# label, a device, a port, b device, b port, type, speed, media, lag
CABLES: list[tuple] = []


def _c(a, ap, b, bp, kind, speed, media, lag=""):
    CABLES.append((f"HS1-CBL-{len(CABLES) + 1:03d}", a, ap, b, bp, kind, speed, media, lag))


_c("HS1-FW-01", "ha1", "HS1-FW-02", "ha1", "cat6a", "1G", "Cat6A", "HA")
_c("HS1-FW-01", "ha2", "HS1-FW-02", "ha2", "cat6a", "1G", "Cat6A", "HA")
for fw, ports in (("HS1-FW-01", ("x1", "x2")), ("HS1-FW-02", ("x1", "x2"))):
    for core, port in zip(("HS1-CORE-1", "HS1-CORE-2"), ports):
        n = "1" if fw.endswith("01") else "2"
        _c(fw, port, core, f"1/1/{1 if n == '1' else 2}", "dac-passive", "10G", "DAC", f"lag1{n}")
_c("HS1-CORE-1", "1/1/31", "HS1-CORE-2", "1/1/31", "dac-passive", "100G", "DAC", "ISL")
_c("HS1-CORE-1", "1/1/32", "HS1-CORE-2", "1/1/32", "dac-passive", "100G", "DAC", "ISL")
_c("HS1-CORE-1", "mgmt", "HS1-CORE-2", "mgmt", "cat6a", "1G", "Cat6A", "KA")
for i, gw in enumerate(("HS1-GW-01", "HS1-GW-02")):
    _c(gw, "0/0/0", "HS1-CORE-1", f"1/1/{5 + i}", "dac-passive", "10G", "DAC", f"lag2{i + 1}")
    _c(gw, "0/0/1", "HS1-CORE-2", f"1/1/{5 + i}", "dac-passive", "10G", "DAC", f"lag2{i + 1}")
_c("HS1-SRV-01", "vmnic0", "HS1-CORE-1", "1/1/9", "dac-passive", "25G", "DAC", "lag30")
_c("HS1-SRV-01", "vmnic1", "HS1-CORE-2", "1/1/9", "dac-passive", "25G", "DAC", "lag30")
_c("HS1-NVR-01", "nic1", "HS1-CORE-1", "1/1/10", "dac-passive", "10G", "DAC", "lag31")
_c("HS1-NVR-01", "nic2", "HS1-CORE-2", "1/1/10", "dac-passive", "10G", "DAC", "lag31")
_c("HS1-ACC-MDF-1", "1/1/49", "HS1-CORE-1", "1/1/11", "dac-passive", "10G", "DAC", "lag40")
_c("HS1-ACC-MDF-2", "2/1/49", "HS1-CORE-2", "1/1/11", "dac-passive", "10G", "DAC", "lag40")
for n, (key, room, rack, members, base, desc, media) in enumerate(IDFS):
    kind = "smf-os2" if media == "SMF OS2" else "mmf-om4"
    _c(f"HS1-ACC-IDF{key}-1", "1/1/49", "HS1-CORE-1", f"1/1/{12 + n}", kind, "10G", media, f"lag4{n + 1}")
    _c(f"HS1-ACC-IDF{key}-{members}", f"{members}/1/49", "HS1-CORE-2", f"1/1/{12 + n}", kind, "10G", media,
       f"lag4{n + 1}")
_c("HS1-ACC-IDFB-2", "2/1/48", "HS1-PTP-A", "eth0", "cat6a", "1G", "Cat6A")
_c("HS1-PTP-B", "eth0", "HS1-ACC-STAD-1", "1/1/12", "cat6a", "1G", "Cat6A")
for dev, port in (("HS1-FW-01", "mgmt"), ("HS1-FW-02", "mgmt"), ("HS1-CORE-1", "oobm"), ("HS1-CORE-2", "oobm")):
    _c("HS1-OOB-SW01", f"1/1/{len(CABLES) % 12 + 1}", dev, port, "cat6", "1G", "Cat6")
_c("HS1-PA-01", "eth0", "HS1-ACC-MDF-1", "1/1/40", "cat6", "1G", "Cat6")
_c("HS1-ACS-01", "eth0", "HS1-ACC-MDF-2", "2/1/40", "cat6", "1G", "Cat6")
_c("HS1-BAS-01", "eth0", "HS1-ACC-IDFD-2", "2/1/44", "cat6", "1G", "Cat6")
for name, sw, _, _ in FIRST_APS:
    member = sw.rsplit("-", 1)[1] if sw[-1].isdigit() else "1"
    _c(name, "eth0", sw, f"{member}/1/{1 + len(CABLES) % 24}", "cat6a", "2.5G", "Cat6A")
for name, sw, _ in CAMERAS:
    member = sw.rsplit("-", 1)[1] if sw[-1].isdigit() else "1"
    _c(name, "eth0", sw, f"{member}/1/{25 + len(CABLES) % 12}", "cat6", "1G", "Cat6")
for name, sw, _, _ in LATE_APS + NETBOX_ONLY_APS:
    member = sw.rsplit("-", 1)[1]
    _c(name, "eth0", sw, f"{member}/1/22", "cat6a", "2.5G", "Cat6A")

# Switch ports to APs are access ports on AP-MGMT 910: client traffic rides the AP's tunnel to the gateways.
AP_PORTS = {(c[3], c[4]) for c in CABLES if c[1] in {a[0] for a in APS + NETBOX_ONLY_APS}}
# The stadium radio pair carries the AP tunnel and management, the gate camera and the scoreboard (440).
STADIUM_VLANS = "410 440 900 910"
STADIUM_PORTS = {("HS1-ACC-IDFB-2", "2/1/48"), ("HS1-PTP-A", "eth0"), ("HS1-PTP-B", "eth0"),
                 ("HS1-ACC-STAD-1", "1/1/12")}

# Trunked VLANs per link group (drawing pills and the link register)
TRUNKS = {
    "lag11": "199 169 299 599 499 999 990 + 310 320", "lag12": "199 169 299 599 499 999 990 + 310 320",
    "lag21": "120 150 210 230 310 320 430 · 900 910", "lag22": "120 150 210 230 310 320 430 · 900 910",
    "lag30": "510 900", "lag31": "520",
    "lag40": "110 120 130 140 150 160 165 410 420 440 900 910",
    "lag41": "110 130 140 150 210 220 230 410 420 900 910",
    "lag42": "110 130 140 150 210 220 230 410 420 440 900 910",
    "lag43": "110 130 150 210 410 420 440 900 910",
    "lag44": "110 130 150 210 220 410 430 900 910",
}

# The district fiber ring: one leg to the district office on CORE-1, the other to Cedar Middle School on
# CORE-2, so one cut (or one core) leaves HS1 connected the other way round. Broadband is the last resort.
CIRCUITS = [  # cid, title, provider, speed, lands on
    ("HPSD-DF-020", "WAN-A1 · ring to district office", "HPSD dark fiber, ring leg to DO", "10G", "HS1-CORE-1"),
    ("HPSD-DF-021", "WAN-A2 · ring to Cedar MS", "HPSD dark fiber, ring leg to MS1", "10G", "HS1-CORE-2"),
    ("ISP-B-77310", "WAN-B · backup broadband", "Cable broadband, IPsec to district office", "1G", "HS1-CORE-2"),
]


# What NetBox holds inside each box, as inventory items (Organization > Inventory items):
# power supplies and fans by role, and a transceiver bound to each fibre port it sits in.
ITEM_ROLES = {"optic": {"id": 1, "name": "Transceiver", "slug": "transceiver"},
              "power": {"id": 2, "name": "Power supply", "slug": "psu"},
              "fan": {"id": 3, "name": "Fan", "slug": "fan"}, "other": None}
HARDWARE = {  # device type -> (kind, item name, count) per box or stack member
    "FortiGate 200F": [("power", "AC PSU", 1)],
    "CX 8360-32Y4C": [("power", "AC PSU", 2), ("fan", "Fan tray", 3)],
    "9240 Gateway": [("power", "AC PSU", 2)],
    "CX 6300M 48P": [("power", "AC PSU 680W", 2), ("fan", "Fan tray", 1)],
    "CX 6100 12G": [("power", "Internal PSU", 1)],
    "CX 6100 12G PoE": [("power", "Internal PSU", 1)],
    "PowerEdge R660": [("power", "800W PSU", 2)],
    "PowerEdge R760xd2": [("power", "1400W PSU", 2)],
    "IP PA and bell server": [("power", "AC PSU", 1)],
    "Door controller (8 doors)": [("power", "12 VDC supply", 1), ("other", "Standby battery", 1)],
    "BACnet/IP supervisor": [("power", "24 VAC transformer", 1)],
    # PoE-powered from its switch; the mast gets a surge protector on the Cat6A before it comes indoors.
    "60 GHz PtP radio": [("other", "Ethernet surge protector", 1)],
}
OPTIC_BY_MEDIA = {"smf-os2": "SFP+ 10G-LR", "mmf-om4": "SFP+ 10G-SR"}


def hardware_items(ids, interfaces, cables):
    """Inventory items: PSUs and fans per box, a transceiver in each fibre port (both ends of each run)."""
    items = []
    prefix = {"optic": "OP", "power": "PS", "fan": "FN", "other": "SP"}

    def item(dev, kind, name, component=None):
        items.append({"id": len(items) + 1, "device": {"id": ids[dev], "name": dev}, "name": name, "label": "",
                      "role": ITEM_ROLES[kind], "manufacturer": None, "part_id": "",
                      "serial": f"{prefix[kind]}xxxxx{len(items) + 1:03d}", "asset_tag": None, "discovered": False,
                      "description": "", "component_type": "dcim.interface" if component else None,
                      "component": component})

    for d in DEVICES:
        for kind, name, count in HARDWARE.get(d["device_type"], []):
            for _ in range(count):
                item(d["name"], kind, name)
    port_id = {(i["device"]["name"], i["name"]): i["id"] for i in interfaces}
    for c in cables:
        optic = OPTIC_BY_MEDIA.get(c["type"])
        if not optic:
            continue
        for side in ("a_terminations", "b_terminations"):
            for t in c[side]:
                dev, port = t["object"]["device"]["name"], t["object"]["name"]
                item(dev, "optic", optic, {"id": port_id[(dev, port)], "name": port})
    return items


# ------------------------------------------------------------------ audit evidence
# The district keeps its audit facts once where it can: owners and the SIEM on the site, room access and
# the August closet walk on each room, FERPA scope on the student-records subnets and on the VMS (its video
# of students can be an education record; the district checks that with counsel). Every device
# carries its own backup, patch, install and support dates. The full sample is the school after the
# August cleanup, so it has no findings; day_one.py ages a few of these to show what a summer leaves.
EXPORTED_AT = "2026-10-17T06:00:00Z"
PEOPLE = {"Angela Ruiz": 1, "District network team": 2, "Keisha Grant": 3, "Security integrator": 4,
          "Tom Bradley": 5, "Controls contractor": 6}
OWNER = {"slug": "asset-owner", "name": "Asset owner"}
CUSTODIAN = {"slug": "custodian", "name": "Custodian"}
CLOSETS = {"MDF-101", "IDF-A118", "IDF-B214", "IDF-C010", "IDF-D305"}
ROOM_ACCESS = {"MDF-101": "badge-camera", "IDF-A118": "locked-room", "IDF-B214": "locked-room",
               "IDF-C010": "locked-room", "IDF-D305": "locked-room", "D-BOILER": "locked-room",
               "ROOF-B": "locked-cabinet", "STADIUM-PB": "locked-cabinet"}   # every other room: open area
WALKED = "2026-08-14"   # the August closet walk (Chapter 13, Rule 7)
FERPA_PREFIXES = {"OFFICE": "confidential", "HEALTH": "restricted"}
SAFETY_ROLES = {"camera", "nvr", "access-control"}   # owned by the safety and security coordinator
INSTALLED = {"firewall": "2023-07-20", "core-switch": "2023-07-20", "access-switch": "2023-07-20",
             "wireless-controller": "2023-07-20", "access-point": "2023-07-20", "oob-switch": "2023-07-20",
             "ptp-radio": "2024-06-18", "hypervisor": "2022-07-12", "nvr": "2022-07-12", "camera": "2022-07-12",
             "access-control": "2021-08-02", "bas-controller": "2019-06-24", "pa-system": "2020-07-15"}
PATCHED = {"firewall": "2026-09-24", "hypervisor": "2026-09-10", "nvr": "2026-09-10"}   # else the August window
CONTRACTS = {  # role -> (contract, end); the network refresh's five-year E-Rate support runs to 2028
    "firewall": ("FortiCare UTP 24x7", "2027-06-30"),
    "core-switch": ("Foundation Care NBD", "2028-06-30"),
    "access-switch": ("Foundation Care NBD", "2028-06-30"),
    "wireless-controller": ("Foundation Care NBD", "2028-06-30"),
    "oob-switch": ("Foundation Care NBD", "2028-06-30"),
    "hypervisor": ("ProSupport NBD", "2027-07-31"), "nvr": ("ProSupport NBD", "2027-07-31"),
    "ptp-radio": ("Advance replacement", "2027-06-18"),
    "access-control": ("Integrator service", "2027-06-30"),
    "pa-system": ("PA vendor service", "2027-06-30"),
}
SITE_EVIDENCE = {"monitoring": "alerting", "monitored_by": "LibreNMS (district NOC)", "log_forwarding": "siem",
                 "log_destination": "District SIEM, syslog over TLS", "log_retention_days": 365,
                 "last_verified": WALKED}


def device_evidence(d: dict) -> dict:
    """The audit custom fields one device carries; APs take config and software from the gateways."""
    role, cf = d["role"], {"install_date": INSTALLED[d["role"]]}
    if role != "access-point":
        cf["last_config_backup"] = "2026-10-16" if role in ("firewall", "core-switch", "access-switch",
                                                            "wireless-controller", "oob-switch", "ptp-radio") \
            else "2026-10-01"
        cf["last_patched"] = PATCHED.get(role, "2026-08-04")
    if role in CONTRACTS:
        cf["support_contract"], cf["support_contract_end"] = CONTRACTS[role]
    if d["name"] == "HS1-NVR-01":
        cf["compliance_scope"] = ["ferpa"]
        cf["data_classification"] = "confidential"
    return cf


def audit_contacts(ids: dict, loc_ids: dict) -> list[dict]:
    """Owners and custodians as NetBox contact assignments: the site, the boiler room, the safety systems."""
    contacts = []

    def assign(kind, ident, person, role):
        contacts.append({"id": len(contacts) + 1, "object_type": kind, "object_id": ident,
                         "contact": {"id": PEOPLE[person], "name": person}, "role": dict(role),
                         "priority": {"value": "primary"}})

    assign("dcim.site", 1, "Angela Ruiz", OWNER)
    assign("dcim.site", 1, "District network team", CUSTODIAN)
    assign("dcim.location", loc_ids["D-BOILER"], "Tom Bradley", OWNER)
    assign("dcim.location", loc_ids["D-BOILER"], "Controls contractor", CUSTODIAN)
    for d in DEVICES:
        if d["role"] in SAFETY_ROLES:
            assign("dcim.device", ids[d["name"]], "Keisha Grant", OWNER)
            assign("dcim.device", ids[d["name"]], "Security integrator", CUSTODIAN)
    return contacts


# Each network model's end of sale and end of support, kept once on its NetBox device type. Sample dates:
# a district copies them from the vendor's end-of-life notices. Building-system and server models carry none.
LIFECYCLE = {
    "FortiGate 200F": ("2028-12-31", "2033-12-31"), "9240 Gateway": ("2029-06-30", "2034-06-30"),
    "CX 8360-32Y4C": ("2028-10-31", "2033-10-31"), "CX 6300M 48P": ("2029-03-31", "2034-03-31"),
    "CX 6100 12G": ("2028-06-30", "2033-06-30"), "CX 6100 12G PoE": ("2028-06-30", "2033-06-30"),
    "AP-575": ("2027-09-30", "2032-09-30"), "AP-635": ("2029-01-31", "2034-01-31"),
    "AP-655": ("2029-01-31", "2034-01-31"), "60 GHz PtP radio": ("2028-12-31", "2031-12-31"),
    "P3265-LVE": ("2028-06-30", "2033-06-30"),
}


def export() -> dict:
    """The sample in NetBox REST shape, for ``netdiagrams build --input``."""
    ids = {d["name"]: i + 1 for i, d in enumerate(DEVICES)}

    def ref(v):
        return {"name": v, "slug": v.lower().replace(" ", "-")} if v else None

    def slug(v):
        return re.sub(r"[^a-z0-9]+", "-", v.lower()).strip("-")

    def shown(key):  # "Main · floor 2" is "Floor 2" under Main building; the slug keeps the building
        floor = key.split(" · ", 1)[1] if " · " in key else key
        return {"floor 0": "Ground floor"}.get(floor, floor[0].upper() + floor[1:])

    loc_ids = {name: i + 1 for i, (name, _, _) in enumerate(LOCATIONS)}
    parents = {name for _, name, _ in LOCATIONS if name}

    def room_evidence(name):  # rooms only: a building or floor holds no devices of its own
        if name in parents:
            return {}
        cf = {"physical_access": ROOM_ACCESS.get(name, "open")}
        if name in CLOSETS or name in ROOM_ACCESS:
            cf["last_verified"] = WALKED
        if name in CLOSETS:
            cf["data_classification"] = "internal"
        return cf

    locations = [{"id": loc_ids[name], "name": shown(name), "slug": slug(name), "description": desc,
                  "site": {"name": SITE_NAME, "slug": SITE_SLUG},
                  "parent": {"id": loc_ids[parent], "name": shown(parent), "slug": slug(parent)} if parent else None,
                  "custom_fields": room_evidence(name)}
                 for name, parent, desc in LOCATIONS]
    assert {d["location"] for d in DEVICES} <= set(loc_ids), "every device sits in a known location"

    devices = []
    for d in DEVICES:
        devices.append({
            "id": ids[d["name"]], "name": d["name"],
            "role": {"name": ROLE_NAMES.get(d["role"], d["role"]), "slug": d["role"]},
            "device_type": {"id": None, "model": d["device_type"],  # model_lifecycle numbers the types
                            "manufacturer": ref(d["manufacturer"])},
            "platform": ref(d["platform"]), "serial": d["serial"], "asset_tag": d["asset_tag"] or None,
            "status": {"value": "active"}, "site": {"name": SITE_NAME, "slug": SITE_SLUG},
            "location": {"id": loc_ids[d["location"]], "name": d["location"], "slug": slug(d["location"])},
            "rack": ref(d["rack"]),
            "position": float(d["position"]) if d["position"] else None,
            "face": {"value": "front"} if d["position"] else None,
            "primary_ip4": {"address": d["primary_ip4"]} if d["primary_ip4"] else None,
            "virtual_chassis": ref(d["virtual_chassis"]),
            "vc_position": int(d["vc_position"]) if d["vc_position"] else None,
            "description": d["description"], "tags": [{"name": t, "slug": t} for t in d["tags"]],
            # APs tunnel to the gateway pair ("Local" in the AP mode choices); the pair is the site's only controller.
            "custom_fields": {**d["cf"], **device_evidence(d),
                              **({"ap_mode": "local"} if d["role"] == "access-point" else {})},
        })
    types = model_lifecycle(devices, LIFECYCLE)
    cables, interfaces, seen = [], [], {}
    for n, (label, a, ap, b, bp, kind, speed, media, lag) in enumerate(CABLES):
        def term(dev, port):
            return [{"object_type": "dcim.interface",
                     "object": {"name": port, "device": {"id": ids[dev], "name": dev}}}]
        cables.append({"id": n + 1, "label": label, "type": kind, "status": {"value": "connected"},
                       "color": "", "length": None, "length_unit": None,
                       "a_terminations": term(a, ap), "b_terminations": term(b, bp)})
        for dev, port in ((a, ap), (b, bp)):
            if (dev, port) in seen:
                continue
            seen[(dev, port)] = len(interfaces) + 1
            vids = [int(v) for v in TRUNKS.get(lag, "").replace("+", " ").split() if v.isdigit()]
            if (dev, port) in STADIUM_PORTS:
                vids = [int(v) for v in STADIUM_VLANS.split()]
            access = (dev, port) in AP_PORTS
            interfaces.append({
                "id": len(interfaces) + 1, "device": {"id": ids[dev], "name": dev}, "name": port,
                "type": {"value": {"10G": "10gbase-x-sfpp", "25G": "25gbase-x-sfp28", "100G": "100gbase-x-qsfp28",
                                   "2.5G": "2.5gbase-t", "1G": "1000base-t"}.get(speed, "other")},
                "enabled": True, "lag": None,
                "mode": {"value": "access"} if access else {"value": "tagged"} if vids else None,
                "untagged_vlan": {"vid": 910} if access else None,
                "tagged_vlans": [{"vid": v} for v in vids], "description": "", "vrf": None})
    model = {d["name"]: d["device_type"] for d in DEVICES}
    for i in interfaces:
        dev = i["device"]["name"]
        if model.get(dev, "").startswith("AP-") and i["name"] == "eth0":
            bt = model[dev] == "AP-655"
            i["poe_mode"] = {"value": "pd", "label": "PD"}
            i["poe_type"] = ({"value": "type3-ieee802.3bt", "label": "802.3bt (Type 3)"} if bt
                             else {"value": "type2-ieee802.3at", "label": "802.3at (Type 2)"})
        elif (dev, i["name"]) in AP_PORTS:   # the switch end powers it
            i["poe_mode"] = {"value": "pse", "label": "PSE"}
    wlan_ids = {w[0]: n + 1 for n, w in enumerate(WLANS)}
    for d in DEVICES:
        for port, band, channel, width in AP_RADIOS.get(d["device_type"], []) if d["role"] == "access-point" else []:
            carried = [w for w in WLANS if band in WLAN_FIELDS[w[0]][2]]
            interfaces.append({
                "id": len(interfaces) + 1, "device": {"id": ids[d["name"]], "name": d["name"]}, "name": port,
                "type": {"value": "ieee802.11ax", "label": "IEEE 802.11ax"}, "enabled": True, "lag": None,
                "mode": None, "untagged_vlan": None, "tagged_vlans": [], "description": "", "vrf": None,
                "rf_role": {"value": "ap", "label": "Access point"},
                "rf_channel": {"value": channel, "label": channel.split("-", 1)[1]},
                "rf_channel_frequency": int(channel.split("-")[2]), "rf_channel_width": width, "tx_power": None,
                "wireless_lans": [{"id": wlan_ids[w[0]], "ssid": w[0]} for w in carried]})
    for dev, role in (("HS1-PTP-A", "ap"), ("HS1-PTP-B", "station")):
        interfaces.append({
            "id": len(interfaces) + 1, "device": {"id": ids[dev], "name": dev}, "name": "radio0",
            "type": {"value": "ieee802.11ad", "label": "IEEE 802.11ad"}, "enabled": True, "lag": None,
            "mode": None, "untagged_vlan": None, "tagged_vlans": [], "description": "60 GHz radio", "vrf": None,
            "rf_role": {"value": role, "label": role.upper() if role == "ap" else "Station"},
            "rf_channel": {"value": "60g-2-60480-2160", "label": "2 (60.48/2160 MHz)"},
            "rf_channel_frequency": 60480, "rf_channel_width": 2160, "tx_power": 12})
    inventory_items = hardware_items(ids, interfaces, cables)
    vlans, prefixes, ips = [], [], []
    for vid, name, subnet, gateway, zone in VLANS:
        vlan_id = len(vlans) + 1
        vlans.append({"id": vlan_id, "vid": vid, "name": name, "role": None, "status": {"value": "active"},
                      "tags": [{"slug": f"zone-{zone}", "name": f"zone-{zone}"}]})
        vrf = ZONE_VRF[zone]
        prefixes.append({"id": len(prefixes) + 1, "prefix": subnet, "vlan": {"id": vlan_id, "vid": vid},
                         "vrf": {"id": list(ZONE_VRF.values()).index(vrf) + 1, "name": vrf},
                         "status": {"value": "active"},
                         "custom_fields": {"compliance_scope": ["ferpa"],
                                           "data_classification": FERPA_PREFIXES[name]} if name in FERPA_PREFIXES
                         else {}})
        net = ipaddress.ip_network(subnet)
        # "CORE .1", "FW-01 .1" or "CORE .1 / FW .2": the core's SVI and the firewall's sub-interface.
        for host, octet in re.findall(r"([A-Za-z0-9-]+)\s+\.(\d+)", gateway):
            dev = "HS1-CORE-1" if host == "CORE" else "HS1-FW-01"
            ips.append({"id": len(ips) + 1, "address": f"{ipaddress.ip_address(int(net.network_address) & ~0xFF | int(octet))}"
                                                  f"/{net.prefixlen}",  # ".129" is the last octet
                        "vrf": {"id": list(ZONE_VRF.values()).index(vrf) + 1, "name": vrf},
                        "assigned_object": {"name": f"vlan{vid}" if host == "CORE" else f"lag1.{vid}",
                                            "device": {"id": ids[dev], "name": dev}}})
    # The district transit: VLAN 990 on the firewall's WAN sub-interface, in its own WAN VRF.
    vlans.append({"id": len(vlans) + 1, "vid": 990, "name": "TR-WAN", "role": None, "status": {"value": "active"},
                  "tags": [{"slug": "zone-wan", "name": "zone-wan"}]})
    prefixes.append({"id": len(prefixes) + 1, "prefix": "10.255.20.0/29", "vlan": {"id": len(vlans), "vid": 990},
                     "tags": [{"slug": "zone-wan", "name": "zone-wan"}],
                     "vrf": {"id": len(ZONE_VRF) + 1, "name": "WAN"}, "description": "HS1 transit to the district office",
                     "status": {"value": "active"}})
    ips.append({"id": len(ips) + 1, "address": "10.255.20.6/29", "vrf": {"id": len(ZONE_VRF) + 1, "name": "WAN"},
                "assigned_object": {"name": "lag1.990", "device": {"id": ids["HS1-FW-01"], "name": "HS1-FW-01"}}})
    wlans = []
    for n, (ssid, auth, vid, _, _) in enumerate(WLANS):
        vlan = next(v for v in vlans if v["vid"] == vid)
        kind, cipher = ("wpa-enterprise", "aes") if "Enterprise" in auth else (
            ("open", "") if "Open" in auth else ("wpa-personal", "aes"))
        # NetBox stores the kind (WPA Enterprise, WPA Personal, Open); the generation and the method
        # (WPA3, OWE, per-device keys) are the wlan_security and wlan_eap fields.
        security, eap, bands, isolation, portal, who = WLAN_FIELDS[ssid]
        fields = {"wlan_security": security, "wlan_switching": "tunnelled", "wlan_bands": bands}
        if eap:
            fields["wlan_eap"] = eap
        if isolation is not None:
            fields["wlan_client_isolation"] = isolation
        if portal:
            fields["wlan_portal"] = portal
        wlans.append({"id": n + 1, "ssid": ssid, "vlan": {"id": vlan["id"], "vid": vid, "name": vlan["name"]},
                      "group": dict(WLAN_GROUP), "description": who, "custom_fields": fields, "tags": [],
                      "scope_type": "dcim.region", "scope": {"name": DISTRICT, "slug": "hpsd"},
                      "auth_type": {"value": kind, "label": NB_AUTH[kind]},
                      "auth_cipher": {"value": cipher, "label": cipher.upper()} if cipher else None,
                      "status": {"value": "active"}})
    return {
        "format": "netdiagrams-export/1", "netbox_version": "sample", "netbox_url": "", "exported_at": EXPORTED_AT,
        "site": {"id": 1, "name": SITE_NAME, "slug": SITE_SLUG, "facility": SITE_CODE,
                 "description": f"{DISTRICT}: grades 9-12, about 1,850 students",
                 # The school standard and the district's naming standard, kept on the site in NetBox.
                 "custom_fields": {"netdiagrams": {"profile": "education",
                                                   "naming": {"pattern": NAMING_PATTERN}},
                                   **WIRELESS_SITE_FIELDS, **SITE_EVIDENCE}},
        "contact_assignments": audit_contacts(ids, loc_ids),
        "locations": locations, "device_types": types, "devices": devices, "virtual_chassis": [], "cables": cables, "vlans": vlans, "prefixes": prefixes,
        "circuits": [{"id": i + 1, "cid": c[0], "status": {"value": "active"}} for i, c in enumerate(CIRCUITS)],
        "interfaces": interfaces,
        "wireless_links": [{"id": 1, "ssid": "HS1-STADIUM", "status": {"value": "connected"},
                            "interface_a": {"device": {"name": "HS1-PTP-A"}, "name": "radio0"},
                            "interface_b": {"device": {"name": "HS1-PTP-B"}, "name": "radio0"},
                            "auth_type": {"value": "wpa-personal", "label": "WPA Personal (PSK)"},
                            "auth_cipher": {"value": "aes", "label": "AES"},
                            "distance": 180, "distance_unit": {"value": "m", "label": "Meters"},
                            "description": "B wing roof to the press box, clear line of sight"}],
        "wireless_lans": wlans, "ip_addresses": ips,
        # HS1 has no modular chassis: every switch is fixed-port, so no modules or module bays.
        "modules": [], "module_bays": [], "inventory_items": inventory_items,
    }
