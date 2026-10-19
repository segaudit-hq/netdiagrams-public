"""Make the R01 retail standard: the template drawn for Store 014, and the sample estate's NetBox exports.

    python scripts/make_retail.py            # writes src/netdiagrams/data/R01-Retail-Store-Template.drawio
                                             # and src/netdiagrams/data/sample-retail-st014.json
    python scripts/make_retail.py --estate DIR   # also writes ST027 and ST031 exports to DIR

The estate is fictional: a head office (HQ1) and three stores (ST014, ST027, ST031)
built to one store design. Everything below is the single source for both the
drawing and the exports, so they always agree. Addresses, serials and circuit IDs
are made up.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drawkit as kit  # noqa: E402
from drawkit import FONT, NETBOX, Page  # noqa: E402
from sample_kit import model_lifecycle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from netdiagrams.retail import RETAIL  # noqa: E402  zone names and shape titles live in the profile

DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"
TEMPLATE = DATA / "R01-Retail-Store-Template.drawio"
STENCILS = DATA / "R01-Retail-Stencils.xml"
SAMPLE = DATA / "sample-retail-st014.json"
DATE = "2026-10-15"
SHEETS = 10
PROJECT = "Network standard — retail estate"

# ---------------------------------------------------------------------------- the estate
STORE = {"code": "ST014", "name": "Store 014", "slug": "st014", "id": 14, "net": 14,
         "description": "Riverside · street store · 2 floors"}

# Zones: slug -> (code shown on the drawing, name, band, palette color); code and name come from the profile.
_BAND_COLOR = {"zone-edge": ("OUTSIDE", "slate"), "zone-store": ("STORE", "green"), "zone-mgmt": ("STORE", "teal"),
               "zone-cde": ("CDE", "purple"), "zone-guest": ("GUEST", "amber"), "zone-iot": ("GUEST", "amber")}
ZONES = {z: (*RETAIL.zone_names[z].split(" · ", 1), *bc) for z, bc in _BAND_COLOR.items()}

# VLANs: vid, name, zone, prefix, gateway host, description
VLANS = [
    (10, "STORE-DATA", "zone-store", "10.{n}.10.0/24", 1, "Back office PC, printers"),
    (30, "STAFF-WIFI", "zone-store", "10.{n}.30.0/24", 1, "Handhelds and tablets"),
    (20, "POS", "zone-cde", "10.{n}.20.0/26", 1, "Registers"),
    (21, "PIN-PAD", "zone-cde", "10.{n}.21.0/27", 1, "PIN pads (P2PE)"),
    (22, "POS-SRV", "zone-cde", "10.{n}.22.0/28", 1, "Store POS server"),
    (50, "GUEST", "zone-guest", "10.{n}.50.0/23", 1, "Customer Wi-Fi, internet only"),
    (40, "IOT-CCTV", "zone-iot", "10.{n}.40.0/24", 1, "Cameras and NVR"),
    (41, "IOT-BLDG", "zone-iot", "10.{n}.41.0/26", 1, "Signage, refrigeration, door counter"),
    (42, "IOT-WIFI", "zone-iot", "10.{n}.42.0/26", 1, "Shelf labels, scales and handheld scanners' cradles on Wi-Fi"),
    (99, "NET-MGMT", "zone-mgmt", "10.{n}.99.0/26", 1, "Switch and AP management"),
    (98, "WAN2-LTE", "zone-edge", "10.{n}.98.0/30", 1, "Firewall to LTE router"),
]

# Devices: suffix, role, manufacturer, model, platform, zone, location, rack, U, host, description, sw
NET = [
    ("FW-01", "firewall", "Fortinet", "FortiGate 61F", "fortios", "zone-edge", "Back office", "CAB-01", 10,
     (99, 1), "Store firewall and SD-WAN edge", "FortiOS 7.4.x"),
    ("LTE-01", "lte-router", "Digi", "IX20", "digi-os", "zone-edge", "Back office", "CAB-01", 9, (98, 2),
     "LTE backup router", "DAL 24.x"),
    ("SW-01", "access-switch", "HPE Aruba", "CX 6100 24G PoE", "aoscx", "zone-mgmt", "Back office", "CAB-01", 8,
     (99, 2), "Store switch", "AOS-CX 10.13"),
    ("SW-02", "access-switch", "HPE Aruba", "CX 6000 12G PoE", "aoscx", "zone-mgmt", "Checkout", "", None,
     (99, 3), "Counter switch (under the checkout)", "AOS-CX 10.13"),
]
APS = [("AP-01", "Sales floor front"), ("AP-02", "Sales floor rear"), ("AP-03", "Stockroom"),
       ("AP-04", "Upstairs")]
ENDPOINTS = [
    # suffix, role, manufacturer, model, zone, location, vlan, host, switch, port, description
    ("POS-01", "pos-terminal", "Generic", "POS terminal 15in", "zone-cde", "Checkout", 20, 11, "SW-02", 1, "Register 1"),
    ("POS-02", "pos-terminal", "Generic", "POS terminal 15in", "zone-cde", "Checkout", 20, 12, "SW-02", 2, "Register 2"),
    ("POS-03", "pos-terminal", "Generic", "POS terminal 15in", "zone-cde", "Checkout", 20, 13, "SW-02", 3, "Register 3"),
    ("PED-01", "pin-pad", "Generic", "PIN pad (P2PE)", "zone-cde", "Checkout", 21, 11, "SW-02", 5, "PIN pad, register 1"),
    ("PED-02", "pin-pad", "Generic", "PIN pad (P2PE)", "zone-cde", "Checkout", 21, 12, "SW-02", 6, "PIN pad, register 2"),
    ("PED-03", "pin-pad", "Generic", "PIN pad (P2PE)", "zone-cde", "Checkout", 21, 13, "SW-02", 7, "PIN pad, register 3"),
    ("POS-SRV-01", "pos-server", "Generic", "Store server 1U", "zone-cde", "Back office", 22, 5, "SW-02", 9,
     "Store POS server (transactions, store-and-forward)"),
    ("BO-PC-01", "workstation", "Generic", "Desktop PC", "zone-store", "Back office", 10, 20, "SW-01", 13,
     "Manager's PC"),
    ("PRN-01", "printer", "Generic", "Laser printer", "zone-store", "Back office", 10, 30, "SW-01", 14,
     "Office printer"),
    ("NVR-01", "nvr", "Generic", "NVR 16-channel", "zone-iot", "Back office", 40, 5, "SW-01", 11, "Video recorder"),
    ("CAM-01", "camera", "Generic", "IP camera dome", "zone-iot", "Sales floor", 40, 11, "SW-01", 5, "Entrance"),
    ("CAM-02", "camera", "Generic", "IP camera dome", "zone-iot", "Checkout", 40, 12, "SW-01", 6, "Checkout"),
    ("CAM-03", "camera", "Generic", "IP camera dome", "zone-iot", "Stockroom", 40, 13, "SW-01", 7, "Stockroom door"),
    ("CAM-04", "camera", "Generic", "IP camera bullet", "zone-iot", "Rear yard", 40, 14, "SW-01", 8, "Delivery door"),
    ("SIGN-01", "signage", "Generic", "Signage player", "zone-iot", "Sales floor", 41, 10, "SW-01", 15,
     "Window display"),
    ("BMS-01", "building-controller", "Generic", "Refrigeration monitor", "zone-iot", "Stockroom", 41, 20, "SW-01",
     16, "Chiller and freezer alarms"),
    ("CNT-01", "sensor", "Generic", "Door counter", "zone-iot", "Sales floor", 41, 30, "SW-01", 17,
     "Footfall counter"),
]
CIRCUITS = [("{c}-BB-01", "Broadband 500M (primary)", "ISP-A"), ("{c}-LTE-01", "LTE backup", "Carrier-B")]
WLANS = [  # ssid, vlan, auth (as typed on the template), zone
    ("STORE-STAFF", 30, "WPA3-Enterprise (802.1X)", "zone-store"),
    ("STORE-GUEST", 50, "Open + captive portal, client isolation", "zone-guest"),
    ("STORE-IOT", 42, "WPA2-Personal, a key per device", "zone-iot"),
]
# The wlan_* custom fields netbox-setup creates: security, switching, bands, isolation, portal; and the
# client rules as the wireless LAN's description.
WLAN_FIELDS = {
    "STORE-STAFF": ({"wlan_security": "wpa3-enterprise", "wlan_switching": "local", "wlan_bands": ["2.4ghz", "5ghz"],
                     "wlan_client_isolation": False, "wlan_portal": "none"}, "802.1X via HQ1 RADIUS (F15)"),
    "STORE-GUEST": ({"wlan_security": "open-portal", "wlan_switching": "local", "wlan_bands": ["2.4ghz", "5ghz"],
                     "wlan_client_isolation": True, "wlan_portal": "captive"}, "internet only · 10 Mb/s per client"),
    "STORE-IOT": ({"wlan_security": "mpsk", "wlan_switching": "local", "wlan_bands": ["2.4ghz"],
                   "wlan_client_isolation": True, "wlan_portal": "none"}, "named vendor clouds only (F20)"),
}
# NetBox's own auth type and cipher for each SSID, as a real NetBox returns them (value and label).
WLAN_AUTH = {"STORE-STAFF": (("wpa-enterprise", "WPA Enterprise"), ("aes", "AES")),
             "STORE-GUEST": (("open", "Open"), None),
             "STORE-IOT": (("wpa-personal", "WPA Personal"), ("aes", "AES"))}
WLAN_GROUP = {"name": "R01 estate", "slug": "r01-estate"}
# AP radios: name, type, band, channel, width (MHz), SSIDs carried.
# NetBox's own channel choices: 40 MHz 5 GHz channels by their centre number, 2.4 GHz channels 22 MHz wide.
RADIOS = [("radio0", "ieee802.11ax", "5g", {"AP-01": 38, "AP-02": 54, "AP-03": 102, "AP-04": 118}, 40,
           ("STORE-STAFF", "STORE-GUEST")),
          ("radio1", "ieee802.11ax", "2.4g", {"AP-01": 1, "AP-02": 6, "AP-03": 11, "AP-04": 1}, 22,
           ("STORE-STAFF", "STORE-GUEST", "STORE-IOT"))]
# Inventory items in the network boxes, by device suffix (NetBox inventory item roles psu and fan).
ITEM_ROLES = {"psu": {"id": 2, "name": "Power supply", "slug": "psu"}, "fan": {"id": 3, "name": "Fan", "slug": "fan"}}
HARDWARE = {"FW-01": [("psu", "AC adapter 12 V")], "LTE-01": [("psu", "AC adapter 12 V")],
            "SW-01": [("psu", "Internal PSU 370 W"), ("fan", "Fan tray")], "SW-02": [("psu", "Internal PSU 139 W")]}
# Asset criticality by role (NetBox custom field criticality): what stops the tills or the card path is critical.
CRITICALITY = {"firewall": "critical", "access-switch": "critical", "pos-server": "critical", "lte-router": "high",
               "pos-terminal": "high", "pin-pad": "high", "access-point": "medium", "nvr": "medium",
               "building-controller": "medium", "workstation": "medium", "camera": "low", "signage": "low",
               "printer": "low", "sensor": "low"}
ROLE_NAMES = {"firewall": "Firewall", "lte-router": "LTE router", "access-switch": "Access switch",
              "access-point": "Access point", "pos-terminal": "POS terminal", "pin-pad": "PIN pad",
              "pos-server": "POS server", "workstation": "Workstation", "printer": "Printer", "nvr": "NVR",
              "camera": "Camera", "signage": "Signage player", "building-controller": "Building controller",
              "sensor": "Sensor"}
# End devices: the engine's end-device roles plus the retail profile's endpoint_roles (drops, not links between network devices).
ENDPOINT_ROLES = {"access-point", "pos-terminal", "pin-pad", "pos-server", "nvr", "camera", "signage",
                  "building-controller", "sensor", "printer", "workstation"}
ICON = {"lte-router": "lte-router", "building-controller": "building-controller"}


def name(store: dict, suffix: str) -> str:
    return f"{store['code']}-{suffix}"


def addr(store: dict, vid: int, host: int) -> str:
    vlan = next(v for v in VLANS if v[0] == vid)
    net = vlan[3].format(n=store["net"])
    base, plen = net.split("/")
    parts = base.split(".")
    parts[3] = str(int(parts[3]) + host)
    return ".".join(parts) + "/" + plen


# Cables: (a suffix, a port, b suffix, b port, type, VLANs carried / untagged, speed)
def cables(store: dict) -> list[tuple]:
    out = [
        ("FW-01", "internal1", "SW-01", "1/1/24", "cat6", "trunk 10,20-22,30,40-42,50,99", "1G"),
        ("FW-01", "wan2", "LTE-01", "eth1", "cat6", "98", "1G"),
        ("SW-01", "1/1/23", "SW-02", "1/1/12", "cat6", "trunk 20-22,99", "1G"),
    ]
    for n, (ap, _) in enumerate(store.get("aps", APS), start=1):
        out.append(("SW-01", f"1/1/{n}", ap, "eth0", "cat6", "trunk 30,42,50 (native 99)", "1G"))
    for e in store.get("endpoints", ENDPOINTS):
        out.append((e[8], f"1/1/{e[9]}", e[0], "eth0", "cat6", str(e[6]), "1G"))
    return out


# The estate's region carries the drawing standard once, for every store in it.
REGION = {"name": "Retail estate", "slug": "retail-estate",
          "custom_fields": {"netdiagrams": {"profile": "retail"},
                            # Store APs take their config from the AP vendor's cloud: no controller in any store.
                            "wireless_management": "cloud", "wireless_manager": "Store Wi-Fi cloud dashboard"}}


def zone_tag(zone: str) -> dict:
    code, zname = ZONES[zone][:2]
    return {"name": f"{code} · {zname}", "slug": zone}


def vlan_ref(store: dict, vid: int) -> dict:
    k = next(i for i, v in enumerate(VLANS, start=1) if v[0] == vid)
    return {"id": store["id"] * 100 + k, "vid": vid, "name": VLANS[k - 1][1]}


def port_vlans(store: dict, spec: str) -> dict:
    """'trunk 10,20-22 (native 99)' or '20' as NetBox interface mode and VLAN fields."""
    if not spec.startswith("trunk"):
        return {"mode": {"value": "access"}, "untagged_vlan": vlan_ref(store, int(spec)), "tagged_vlans": []}
    body, _, native = spec[6:].partition(" (native ")
    vids = []
    for part in body.split(","):
        lo, _, hi = part.partition("-")
        vids += range(int(lo), int(hi or lo) + 1)
    return {"mode": {"value": "tagged"},
            "untagged_vlan": vlan_ref(store, int(native.rstrip(")"))) if native else None,
            "tagged_vlans": [vlan_ref(store, v) for v in vids]}


def cable_label(store: dict, a: str, port: str) -> str:
    """The store standard labels a cable by the A-side port it leaves: ST014-SW01-P05, ST014-FW01-WAN2.

    Every store patches the same device to the same port, so the same cable has the same label
    (after the store code) in every store, and the template's cables match any store's NetBox."""
    tail = f"P{int(port.rsplit('/', 1)[1]):02d}" if "/" in port else port.upper().replace("INTERNAL", "INT")
    return f"{store['code']}-{a.replace('-', '')}-{tail}"


def export(store: dict) -> dict:
    """The NetBox export (netdiagrams-export/1) of one store."""
    n = store["net"]
    site = {"id": store["id"], "name": store["name"], "slug": store["slug"], "facility": store["code"],
            "description": store["description"]}
    devices, interfaces, ips, by_suffix = [], [], [], {}
    did = store["id"] * 1000

    def add(suffix, role, mfr, model, platform, zone, location, rack, u, ip, descr, sw="", status="active"):
        nonlocal did
        did += 1
        d = {"id": did, "name": name(store, suffix), "role": {"name": ROLE_NAMES[role], "slug": role},
             "device_type": {"model": model, "manufacturer": {"name": mfr, "slug": mfr.lower().replace(" ", "-")}},
             "platform": {"name": platform, "slug": platform} if platform else None,
             "serial": "" if suffix in store.get("no_serial", ()) else f"{store['net']:03d}{did % 1000:04d}", "asset_tag": f"{store['code']}-A{did % 1000:03d}",
             "status": {"value": status}, "site": {"name": store["name"], "slug": store["slug"]},
             "location": {"name": location, "slug": location.lower().replace(" ", "-")},
             "rack": {"name": f"{store['code']}-{rack}", "slug": f"{store['slug']}-{rack.lower()}"} if rack else None,
             "position": float(u) if u else None, "face": {"value": "front"} if u else None,
             "primary_ip4": {"address": ip} if ip else None, "virtual_chassis": None, "vc_position": None,
             "description": descr, "tags": [] if suffix in store.get("no_zone", ()) else [zone_tag(zone)],
             "tenant": {"name": OWNER_OF[ZONES[zone][0]], "slug": OWNER_OF[ZONES[zone][0]].lower().replace(" ", "-")},
             "custom_fields": {**({"sw_version": sw} if sw else {}),
                               **({"ap_mode": "cloud"} if role == "access-point" else {}),
                               "criticality": CRITICALITY[role]}}
        devices.append(d)
        by_suffix[suffix] = d
        return d

    statuses = store.get("status", {})
    for suffix, role, mfr, model, platform, zone, loc, rack, u, (vid, host), descr, sw in NET:
        if suffix in store.get("without", ()):
            continue
        add(suffix, role, mfr, model, platform, zone, loc, rack, u, addr(store, vid, host), descr, sw,
            statuses.get(suffix, "active"))
    for i, (ap, loc) in enumerate(store.get("aps", APS), start=1):
        add(ap, "access-point", "HPE Aruba", "AP-515", "aos10", "zone-mgmt", loc, "", None, addr(store, 99, 10 + i),
            f"Access point · {loc}", "AOS 10.6", statuses.get(ap, "active"))
    for suffix, role, mfr, model, zone, loc, vid, host, _, _, descr in store.get("endpoints", ENDPOINTS):
        add(suffix, role, mfr, model, None, zone, loc, "CAB-01" if role in ("pos-server", "nvr") else "",
            {"pos-server": 6, "nvr": 4}.get(role), addr(store, vid, host), descr, "", statuses.get(suffix, "active"))

    iid, cid = did * 10, 0
    cable_rows = []
    for a, ap, b, bp, kind, vlans, speed in cables(store):
        if a not in by_suffix or b not in by_suffix:
            continue
        cid += 1
        ends = []
        to_ap = by_suffix[b]["role"]["slug"] == "access-point"
        for suffix, port in ((a, ap), (b, bp)):
            iid += 1
            dev = by_suffix[suffix]
            poe = {}
            if to_ap:  # PoE: the switch port powers the AP's uplink (802.3at)
                poe = {"poe_mode": {"value": "pd" if suffix == b else "pse", "label": "PD" if suffix == b else "PSE"},
                       "poe_type": {"value": "type2-ieee802.3at", "label": "802.3at (Type 2)"}}
            interfaces.append({"id": iid, "device": {"id": dev["id"], "name": dev["name"]}, "name": port,
                               "type": {"value": "1000base-t"}, "enabled": True, "lag": None,
                               **port_vlans(store, vlans), "description": "", "vrf": None, **poe})
            ends.append([{"object_type": "dcim.interface",
                          "object": {"name": port, "device": {"id": dev["id"], "name": dev["name"]}}}])
        cable_rows.append({"id": store["id"] * 1000 + cid, "label": cable_label(store, a, ap), "type": kind,
                           "status": {"value": "connected"}, "color": "2196f3", "length": None, "length_unit": None,
                           "a_terminations": ends[0], "b_terminations": ends[1]})

    wlan_id = {ssid: store["id"] * 10 + k for k, (ssid, *_) in enumerate(WLANS, start=1)}
    for ap, _ in store.get("aps", APS):
        if ap not in by_suffix:
            continue
        dev = by_suffix[ap]
        for rname, rtype, band, channels, width, ssids in RADIOS:
            iid += 1
            ch = channels.get(ap, channels["AP-01"])
            freq = 2407 + 5 * ch if band == "2.4g" else 5000 + 5 * ch
            interfaces.append({"id": iid, "device": {"id": dev["id"], "name": dev["name"]}, "name": rname,
                               "type": {"value": rtype, "label": "IEEE 802.11ax"}, "enabled": True, "lag": None,
                               "mode": None, "untagged_vlan": None, "tagged_vlans": [], "vrf": None,
                               "description": f"{'5 GHz' if band == '5g' else '2.4 GHz'} radio",
                               "rf_role": {"value": "ap", "label": "Access point"},
                               "rf_channel": {"value": f"{band}-{ch}-{freq}-{width}",
                                              "label": f"{ch} ({freq}/{width} MHz)"},
                               "rf_channel_frequency": float(freq), "rf_channel_width": float(width),
                               "tx_power": 14 if band == "5g" else 8,
                               "wireless_lans": [{"id": wlan_id[x], "ssid": x} for x in ssids]})

    vlans, prefixes = [], []
    fw = by_suffix.get("FW-01")
    for k, (vid, vname, zone, net, gw, descr) in enumerate(VLANS, start=1):
        vlan_id = store["id"] * 100 + k
        owner = OWNER_OF[ZONES[zone][0]]
        tenant = {"name": owner, "slug": owner.lower().replace(" ", "-")}
        vlans.append({"id": vlan_id, "vid": vid, "name": vname, "role": None, "description": descr,
                      "tags": [zone_tag(zone)], "tenant": tenant})
        prefix = net.format(n=n)
        prefixes.append({"id": vlan_id, "prefix": prefix, "vlan": {"id": vlan_id, "vid": vid}, "vrf": None,
                         "description": descr, "tenant": tenant})
        if fw:
            iid += 1
            ifname = "wan2" if vid == 98 else f"internal1.{vid}"
            ips.append({"id": iid, "address": addr(store, vid, gw),
                        "assigned_object": {"name": ifname, "device": {"id": fw["id"], "name": fw["name"]}}})
    circuits = [{"id": store["id"] * 10 + k, "cid": c.format(c=store["code"]), "description": d,
                 "provider": {"name": p}, "status": {"value": "active"}}
                for k, (c, d, p) in enumerate(CIRCUITS, start=1)]
    wlans = []
    for k, (ssid, vid, auth, zone) in enumerate(WLANS, start=1):
        (atype, alabel), cipher = WLAN_AUTH[ssid]
        wlans.append({"id": store["id"] * 10 + k, "ssid": ssid, "group": WLAN_GROUP,
                      "auth_type": {"value": atype, "label": alabel},
                      "auth_cipher": {"value": cipher[0], "label": cipher[1]} if cipher else None,
                      "auth_psk": "",  # keys live in the Wi-Fi management system, never in NetBox or a drawing
                      "description": WLAN_FIELDS[ssid][1], "custom_fields": WLAN_FIELDS[ssid][0],
                      "vlan": {"id": store["id"] * 100 + next(i for i, v in enumerate(VLANS, 1) if v[0] == vid),
                               "vid": vid},
                      "scope_type": "dcim.site", "scope_id": store["id"],
                      "scope": {"id": store["id"], "name": store["name"], "slug": store["slug"]},
                      "status": {"value": "active", "label": "Active"}, "tags": [zone_tag(zone)]})
    # What a "show inventory" lists inside the network boxes. Every R01 box is fixed-configuration and
    # copper-only, so there are no module bays and no transceivers: power supplies and fans only.
    items = []
    for suffix, parts in HARDWARE.items():
        dev = by_suffix.get(suffix)
        if not dev:
            continue
        for kind, label in parts:
            items.append({"id": store["id"] * 100 + len(items) + 1, "device": {"id": dev["id"], "name": dev["name"]},
                          "name": label, "label": "", "role": ITEM_ROLES[kind], "manufacturer": None, "part_id": "",
                          "serial": f"{store['net']:03d}{kind[0].upper()}{len(items) + 1:03d}", "asset_tag": None,
                          "discovered": False, "description": "", "component_type": None, "component": None})
    device_types = model_lifecycle(devices, LIFECYCLE)
    locations, racks, contacts, site_fields = audit_evidence(store, devices, prefixes)
    site["custom_fields"] = site_fields
    return {"format": "netdiagrams-export/1", "netbox_version": "sample", "netbox_url": "",
            "exported_at": f"{DATE}T09:00:00Z", "site": site, "locations": locations, "racks": racks,
            "contact_assignments": contacts, "device_types": device_types, "regions": [REGION], "devices": devices, "virtual_chassis": [],
            "cables": cable_rows, "vlans": vlans, "prefixes": prefixes, "circuits": circuits,
            "interfaces": interfaces, "wireless_links": [], "wireless_lans": wlans, "ip_addresses": ips,
            "modules": [], "module_bays": [], "inventory_items": items}


# End of sale and end of support belong to the model, so they are set once on the device type and every
# store's units inherit them. A PIN pad's date is the one that moves first: payment terminals are retired
# on the terminal maker's schedule, whatever the hardware's condition.
LIFECYCLE = {  # model -> (end of sale, end of support)
    "FortiGate 61F": ("2028-06-30", "2033-06-30"), "IX20": ("2027-12-31", "2031-12-31"),
    "CX 6100 24G PoE": ("2029-10-31", "2034-10-31"), "CX 6000 12G PoE": ("2029-10-31", "2034-10-31"),
    "AP-515": ("2027-06-30", "2032-06-30"), "Store server 1U": ("2028-03-31", "2031-03-31"),
    "POS terminal 15in": ("2029-01-31", "2032-01-31"), "PIN pad (P2PE)": ("2027-09-30", "2030-09-30")}


# Audit evidence (sheet 3f): who owns each thing, how it is locked away, and when it was last backed up,
# patched and checked. The scope fields record what the store's last assessment agreed; the book never
# decides scope for the reader. The CDE subnets carry it, so the POS server in the back office inherits it.
ROOM_FACTS = {  # room -> (physical access, data classification)
    "Back office": ("locked-room", "confidential"), "Checkout": ("open", "restricted"),
    "Stockroom": ("locked-room", "internal"), "Upstairs": ("locked-room", "internal"),
    "Sales floor": ("open", "internal"), "Sales floor front": ("open", "internal"),
    "Sales floor rear": ("open", "internal"), "Rear yard": ("open", "internal")}
CONNECTED = ("FW-01", "SW-01", "SW-02")   # the network gear the CDE traffic crosses
CONTRACTS = {"FW-01": ("Hardware and firmware, next business day", "2027-03-31"),
             "LTE-01": ("Hardware replacement, 3 years", "2027-03-31"),
             "SW-01": ("Limited lifetime warranty", ""), "SW-02": ("Limited lifetime warranty", ""),
             "POS-SRV-01": ("POS vendor support, 4-hour on site", "2027-06-30")}
MANAGERS = {"ST014": "Alex Morgan", "ST027": "Sam Patel", "ST031": "Jordan Lee"}
FITTED = {"ST014": "2023-03-14", "ST027": "2021-09-06", "ST031": "2025-11-03"}


def audit_evidence(store: dict, devices: list[dict], prefixes: list[dict]):
    """Locations, the cabinet, contact assignments and site fields of one store, plus each device's dates."""
    used = sorted({d["location"]["name"] for d in devices if d.get("location")})
    locations = []
    for i, room in enumerate(used, start=1):
        access, data_class = ROOM_FACTS[room]
        locations.append({"id": store["id"] * 100 + i, "name": room, "slug": room.lower().replace(" ", "-"),
                          "parent": None, "custom_fields": {"physical_access": access,
                                                            "data_classification": data_class}})
    racks = [{"id": store["id"] * 10 + 1, "name": f"{store['code']}-CAB-01",
              "custom_fields": {"physical_access": "locked-cabinet"}}]
    for p in prefixes:
        if p["vlan"]["vid"] in (20, 21, 22):
            p["custom_fields"] = {"compliance_scope": ["pci-cde"], "data_classification": "restricted"}
    people = {MANAGERS[store["code"]]: 1, "Store IT": 2, "Network team": 3, "Payments team": 4, "POS team": 5}
    owner, custodian = {"slug": "asset-owner", "name": "Asset owner"}, {"slug": "custodian", "name": "Custodian"}
    contacts = []

    def assign(kind, ident, person, role):
        contacts.append({"id": store["id"] * 100 + len(contacts) + 1, "object_type": kind, "object_id": ident,
                         "contact": {"id": people[person], "name": person}, "role": role,
                         "priority": {"value": "primary"}})

    assign("dcim.site", store["id"], MANAGERS[store["code"]], owner)
    assign("dcim.site", store["id"], "Store IT", custodian)
    for d in devices:
        role, cf, suffix = d["role"]["slug"], d["custom_fields"], d["name"].split("-", 1)[1]
        if role in ("firewall", "lte-router", "access-switch", "access-point"):
            assign("dcim.device", d["id"], "Network team", owner)
            assign("dcim.device", d["id"], "Network team", custodian)
        elif role in ("pos-server", "pos-terminal", "pin-pad"):
            assign("dcim.device", d["id"], "Payments team", owner)
            assign("dcim.device", d["id"], "POS team", custodian)
        if suffix in CONNECTED:
            cf["compliance_scope"] = ["pci-connected"]
        if role != "access-point":
            cf["last_config_backup"] = "2026-10-14" if role in ("firewall", "lte-router", "access-switch",
                                                               "pos-server", "pos-terminal") else "2026-10-01"
            cf["last_patched"] = {"firewall": "2026-09-23", "access-switch": "2026-09-23", "lte-router": "2026-08-27",
                                  "pos-server": "2026-10-06", "pos-terminal": "2026-10-06",
                                  "pin-pad": "2026-09-15"}.get(role, "2026-08-12")
        cf["install_date"] = "2024-05-20" if role == "access-point" else FITTED[store["code"]]
        if role == "pos-server":  # its own logs, not just the network gear's (F27)
            cf["log_forwarding"], cf["monitoring"] = "siem", "alerting"
        if suffix in CONTRACTS:
            cf["support_contract"], end = CONTRACTS[suffix]
            if end:
                cf["support_contract_end"] = end
    site_fields = {"monitoring": "alerting",
                   "monitored_by": "Store estate monitoring (cloud NMS)", "log_forwarding": "siem",
                   "log_destination": "Central SIEM, syslog over TLS", "log_retention_days": 400,
                   "last_verified": "2026-06-04"}
    return locations, racks, contacts, site_fields


# The other two stores: same design, the differences a real estate has.
ST027 = {**STORE, "code": "ST027", "name": "Store 027", "slug": "st027", "id": 27, "net": 27,
         "description": "Market Square · street store", "aps": APS[:3],
         "endpoints": [e for e in ENDPOINTS if e[0] not in ("CAM-04", "CNT-01")]
         + [("POS-04", "pos-terminal", "Generic", "POS terminal 15in", "zone-cde", "Checkout", 20, 14, "SW-02", 4,
             "Register 4"),
            ("PED-04", "pin-pad", "Generic", "PIN pad (P2PE)", "zone-cde", "Checkout", 21, 14, "SW-02", 8,
             "PIN pad, register 4")],
         "status": {"AP-03": "offline"}}
ST031 = {**STORE, "code": "ST031", "name": "Store 031", "slug": "st031", "id": 31, "net": 31,
         "description": "Northfield Mall · mall unit, mall CCTV", "aps": APS[:2],
         "endpoints": [e for e in ENDPOINTS if e[1] not in ("camera", "nvr") and e[0] not in ("POS-03", "PED-03")],
         "status": {"SW-02": "planned"},
         # A mall unit fitted out by a contractor: two records the store team never finished.
         "no_serial": ("SIGN-01",), "no_zone": ("CNT-01",)}


# ---------------------------------------------------------------------------- drawing helpers
BANDS = [  # code, label, key (ZONES band), palette
    ("R5", "OUTSIDE · WAN", "OUTSIDE", "slate"),
    ("R4", "HEAD OFFICE", "HQ", "blue"),
    ("R3", "STORE OPERATIONS", "STORE", "green"),
    ("R2", "CARDHOLDER DATA (CDE)", "CDE", "purple"),
    ("R1", "GUEST & DEVICES", "GUEST", "amber"),
]
LINK_EDGE = kit.LINK_EDGE + "strokeColor=#2196F3;"
LOGICAL_EDGE = ("endArrow=none;startArrow=none;strokeColor=#475569;strokeWidth=1.4;html=1;fontSize=9;"
                "fontColor=#334155;labelBackgroundColor=#FFFFFF;labelBorderColor=#E2E8F0;spacing=3;edgeStyle=none;"
                + FONT)
CIRCUIT_EDGE = ("endArrow=none;startArrow=none;strokeColor=#94A3B8;strokeWidth=1.4;dashed=1;dashPattern=6 4;html=1;"
                "fontSize=9;fontColor=#475569;labelBackgroundColor=#FFFFFF;edgeStyle=orthogonalEdgeStyle;rounded=1;"
                + FONT)


def device_attrs(store: dict, d: dict, extra: dict | None = None) -> dict:
    a = {"name": d["name"], "role": d["role"]["slug"], "manufacturer": d["device_type"]["manufacturer"]["name"],
         "device_type": d["device_type"]["model"], "platform": (d.get("platform") or {}).get("slug", ""),
         "serial": d["serial"], "asset_tag": d["asset_tag"], "status": d["status"]["value"],
         "site": store["code"], "location": d["location"]["name"],
         "rack": (d.get("rack") or {}).get("name", ""),
         "position": f"{d['position']:g}" if d.get("position") else "", "face": (d.get("face") or {}).get("value", ""),
         "primary_ip4": (d.get("primary_ip4") or {}).get("address", ""), "virtual_chassis": "", "vc_position": "",
         "description": d["description"], "tags": ",".join(t["slug"] for t in d["tags"])}
    for k, v in (d.get("custom_fields") or {}).items():
        a[f"cf_{k}"] = v
    a.update(extra or {})
    a["link"] = f"{NETBOX}/dcim/devices/?name={d['name']}"
    a["linkTarget"] = "_blank"
    a["placeholders"] = "1"
    a["tooltip"] = kit.tooltip(a)
    return a


class Store:
    """The drawing helpers that need the store's data (device cards, cables)."""

    def __init__(self, store: dict):
        self.store = store
        self.data = export(store)
        self.dev = {d["name"].split("-", 1)[1]: d for d in self.data["devices"]}

    def card(self, p: Page, layer: str, ip_layer: str, sn_layer: str, suffix: str, x, y, w=200, h=56,
             extra: dict | None = None, pill: bool = True) -> str:
        d = self.dev[suffix]
        role = d["role"]["slug"]
        style = kit.CARD + kit.icon_style(ICON.get(role, role))
        cid = p.cell(layer, '<b>%name%</b><br><span style="font-size:9px;color:#64748B">%device_type%</span>', style,
                     x, y, w, h, device_attrs(self.store, d, extra))
        if pill:
            if d.get("rack"):
                link = f"{NETBOX}/dcim/racks/?site={self.store['slug']}&name={d['rack']['name']}"
                p.cell(cid, "%rack% · U%position%",
                       "rounded=1;absoluteArcSize=1;arcSize=8;fillColor=#EEF2F7;strokeColor=none;fontSize=6.5;"
                       "fontColor=#475569;html=1;spacing=0;" + kit.MONO, w - 76, 22, 72, 13,
                       {"placeholders": "1", "object": "dcim.rack", "link": link, "linkTarget": "_blank",
                        "tooltip": "Opens the rack (or location) in NetBox"})
            else:
                link = f"{NETBOX}/dcim/locations/?site={self.store['slug']}&name={d['location']['name']}"
                p.cell(cid, "%location%",
                       "rounded=1;absoluteArcSize=1;arcSize=8;fillColor=#EEF2F7;strokeColor=none;fontSize=6.5;"
                       "fontColor=#475569;html=1;spacing=0;" + FONT, w - 62, 22, 58, 13,
                       {"placeholders": "1", "object": "dcim.location", "link": link, "linkTarget": "_blank",
                        "tooltip": "Opens the location in NetBox"})
        ip = (d.get("primary_ip4") or {}).get("address", "").split("/")[0]
        if ip and ip_layer:
            p.cell(ip_layer, ip, "text;html=1;fontSize=9;fontColor=#475569;fillColor=#FFFFFF;fillOpacity=70;"
                                 "strokeColor=none;align=left;verticalAlign=middle;spacingLeft=2;spacing=0;" + FONT,
                   x + 38, y + h - 18, 90, 14)
        if sn_layer:
            p.cell(sn_layer, f"SN {d['serial']}", "text;html=1;fontSize=9;fontColor=#64748B;align=right;"
                   "verticalAlign=middle;spacing=0;spacingLeft=2;" + kit.MONO, x + w - 104, y + h - 18, 98, 14)
        return cid

    def cable(self, p: Page, layer: str, a: str, b: str, src: str, tgt: str, exit_=None, entry=None,
              points=None, pill: str = "", port_a_pos: float = -0.75, port_b_pos: float = 0.75,
              pill_pos: float | None = None) -> str:
        row = next(c for c in cables(self.store) if c[0] == a and c[2] == b)
        _, ap, _, bp, kind, vlans, speed = row
        n = cables(self.store).index(row) + 1
        label = cable_label(self.store, a, ap)
        da, db = self.dev[a], self.dev[b]
        attrs = {"object": "dcim.cable", "cable_label": label, "type": kind, "status": "connected",
                 "color": "2196f3", "length": "", "length_unit": "",
                 "a_terminations": f"{da['name']}:{ap}", "b_terminations": f"{db['name']}:{bp}",
                 "x_speed": speed, "x_media": "Cat6"}
        attrs["tooltip"] = kit.tooltip(attrs)
        attrs["link"] = f"{NETBOX}/dcim/cables/?label={label}"
        attrs["linkTarget"] = "_blank"
        style = LINK_EDGE
        if exit_:
            style += f"exitX={exit_[0]};exitY={exit_[1]};exitDx=0;exitDy=0;"
        if entry:
            style += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        e = p.edge(layer, src, tgt, style, pill or "", attrs, points, pos=pill_pos)
        if port_a_pos is not None:
            p.edge_label(e, ap, port_a_pos)
        if port_b_pos is not None:
            p.edge_label(e, bp, port_b_pos)
        return e


def vlan_rows(store: dict, zone: str) -> list[list]:
    rows = []
    for vid, vname, z, net, gw, descr in sorted(VLANS):
        if z != zone:
            continue
        prefix = net.format(n=store["net"])
        rows.append([(str(vid), f"{NETBOX}/ipam/vlans/?site={store['slug']}&vid={vid}"), vname,
                     (prefix, f"{NETBOX}/ipam/prefixes/?q={prefix}"), f"FW-01 .{gw}"])
    return rows


VLAN_COLS = [("VLAN", 46), ("NAME", 112), ("SUBNET", 118), ("GATEWAY · VRF", 110)]


def zone_card(p: Page, s: Store, zl: str, tl: str, zone: str, x, y, w, h, subtitle: str,
              rules: list[str] | None = None, rules_w: float = 300) -> str:
    code, zname, _, color = ZONES[zone]
    z = p.zone(zl, x, y, w, h, f"ZONE {code} · {zname}", subtitle, color)
    p.table(tl, x + 16, y + 48, VLAN_COLS, vlan_rows(s.store, zone))
    if rules:
        p.note(zl, x + w - rules_w - 16, y + 48, rules_w, h - 64, "Zone rules", rules, size=10)
    return z


def finish(p: Page, store: dict, border: str, drawing: str, sheet: int) -> None:
    p.title_block(border, store["code"], f"{drawing} — {store['code']}", f"{sheet} of {SHEETS}", DATE, PROJECT)


def std_legend(p: Page, layer: str, x, y, w=520, lines=True) -> None:
    roles = [("firewall", "Firewall · SD-WAN edge"), ("lte-router", "LTE / 5G router"),
             ("access-switch", "Switch"), ("access-point", "Wireless AP"),
             ("pos-terminal", "POS register"), ("pin-pad", "PIN pad"), ("pos-server", "Store POS server"),
             ("workstation", "PC / tablet"), ("nvr", "NVR"), ("camera", "Camera"),
             ("signage", "Signage"), ("building-controller", "Building / refrigeration")]
    line_samples = [
        (kit.LINK_EDGE + "strokeColor=#2196F3;", "Cable (Cat6) · pill: speed · VLANs · ports at each end"),
        (CIRCUIT_EDGE, "Carrier circuit (not a cable)"),
        (FLOW_OK, "Permitted flow (initiator → responder)"),
        (FLOW_COND, "Conditional (approval or failure state)"),
        (FLOW_DENY, "Denied path"),
    ] if lines else []
    chips = [("OUTSIDE", "slate"), ("HEAD OFFICE", "blue"), ("STORE", "green"), ("MGMT", "teal"),
             ("CDE", "purple"), ("GUEST · IOT", "amber")]
    p.legend(layer, x, y, w, roles, line_samples, chips)


FLOW_OK = ("endArrow=block;endFill=1;endSize=6;strokeWidth=2;html=1;fontSize=9;fontColor=#334155;"
           "labelBackgroundColor=#FFFFFF;edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#059669;" + FONT)
FLOW_COND = FLOW_OK.replace("strokeColor=#059669;", "strokeColor=#D97706;dashed=1;dashPattern=8 4;")
FLOW_DENY = FLOW_OK.replace("strokeColor=#059669;", "strokeColor=#DC2626;dashed=1;dashPattern=3 3;")


# ---------------------------------------------------------------------------- 1 · overview
S01 = DATA / "S01-Network-Architecture-Template.drawio"


class Copied:
    """A page copied from the S01 template (same element ids, so the engine fills it the same way)."""

    def __init__(self, page_id: str):
        tree = ET.parse(S01).getroot()
        self.diagram = copy.deepcopy(next(d for d in tree.findall("diagram") if d.get("id") == page_id))
        self.els = {el.get("id"): el for el in self.diagram.iter() if el.get("id")}

    def text(self, el_id: str, value: str) -> None:
        el = self.els[el_id]
        el.set("label" if el.tag == "object" else "value", value)

    def icon(self, el_id: str, name: str) -> None:
        cell = self.els[el_id]
        style = cell.get("style")
        head, rest = style.split("image=", 1)
        tail = rest.split(";", 1)[1]
        cell.set("style", f"{head}image=data:image/svg+xml,{kit.ICONS[name]};{tail}")

    def element(self) -> ET.Element:
        return self.diagram

    def style(self, el_id: str, old: str, new: str) -> None:
        cell = self.els[el_id]
        cell.set("style", cell.get("style").replace(old, new))


def _block(title: str, sub: str) -> str:
    return (f'<b><span style="font-size:16px">{html.escape(title)}</span></b><br>'
            f'<span style="color:#64748B">{html.escape(sub)}</span>')


def _card(title: str, sub: str) -> str:
    return (f'<b>{html.escape(title)}</b><br><span style="font-size:11px;color:#64748B">{html.escape(sub)}</span>')


def _statement(title: str, body: str) -> str:
    return f'<b><span style="font-size:15px">{html.escape(title)}</span></b><br>{html.escape(body)}'


def page_overview() -> Copied:
    """Sheet 1: the S01 overview's shapes and ids, worded for a store (derive_overview rewrites it from NetBox)."""
    p = Copied("overview")
    p.text("overview-c1", "How every store network is protected")
    p.text("overview-c2", "Management overview — no technical detail. The same design is used in every store.")
    p.text("overview-c3", _block("Internet, card processor & head office",
                                 "Card payments · price files · email and stock systems · support partners"))
    p.text("overview-c4", "Outside")
    p.text("overview-c5", _block("Back office", "Manager's PC, staff handhelds and printers"))
    p.icon("overview-c5", "workstation")
    p.text("overview-c6", "Office")
    p.text("overview-c7", "<b>Security gate</b> — the store firewall (the 4G line takes over if broadband fails)")
    p.text("overview-c8", _block("Head office link — the only way in",
                                 "Store systems talk to head office over an encrypted tunnel. Support staff "
                                 "come in through head office, never straight from the internet."))
    p.icon("overview-c8", "building")
    p.text("overview-c9", "Link")
    p.text("overview-c10", "<b>Same security gate</b> — checks everything going into or out of the store")
    p.text("overview-c11", _block("Network management", "Switches and Wi-Fi access points, managed only from "
                                                        "head office"))
    p.icon("overview-c11", "access-switch")
    p.text("overview-c12", "Store")
    p.text("overview-c13", "<b>Same security gate</b> — between the back office, the checkout and the shop floor")
    p.text("overview-c15", "Checkout & shop floor")
    p.text("overview-c16", '<b><span style="font-size:16px">Checkout and shop floor</span></b> — each its own '
                           "sealed zone")
    p.text("overview-c17", _card("Customer Wi-Fi", "internet only"))
    p.icon("overview-c17", "wifi")
    p.text("overview-c18", _card("Cameras", "record in the store"))
    p.icon("overview-c18", "camera")
    p.text("overview-c19", _card("Signage & fridges", "vendor clouds only"))
    p.icon("overview-c19", "building-controller")
    p.text("overview-c20", _card("Checkout", "card data · sealed"))
    p.icon("overview-c20", "pos-terminal")
    p.text("overview-e21", "Support partners:<br>through head office")
    p.text("overview-e22", "approved, recorded<br>session to one device")
    p.text("overview-e23", "Direct access from<br>internet or guest Wi-Fi")
    p.text("overview-c25", "What this means for the business")
    # In the order derive_overview writes them: zones, boundary, shop floor, card data, health, source.
    for el_id, icon, title, body in (
            ("overview-c26", "lock", "Sealed zones", "Checkout, back office, guest Wi-Fi and store devices are "
                                                     "separate zones; nothing crosses without a rule."),
            ("overview-c27", "firewall", "One gate", "Every conversation in or out of a zone passes the store "
                                                     "firewall, and partners come in only through head office."),
            ("overview-c28", "wifi", "Guests stay out", "Customer Wi-Fi reaches the internet and nothing in the "
                                                        "store."),
            ("overview-c29", "card", "Card data stays at the till",
             "Card numbers are encrypted in the PIN pad and the checkout is sealed off from everything else."),
            ("overview-c30", "clock", "Keeps trading offline", "If both lines fail, the tills keep taking cards "
                                                               "and send the sales when the line comes back."),
            ("overview-c31", "store", "Same design everywhere", "Every store is built the same way, so a fix in "
                                                                "one is a fix in all.")):
        p.icon(el_id, icon)
        p.text(el_id, _statement(title, body))
    p.text("overview-c44", "Network standard — retail estate")
    p.text("overview-c49", f"1 of {SHEETS}")
    p.text("overview-c48", DATE)
    p.diagram.set("name", "1 · Overview — for management")
    return p


# ---------------------------------------------------------------------------- 2 · logical
def page_logical(s: Store) -> Page:
    st = s.store
    W, H = 2400, 1440
    p = Page("logical", "2 · Logical — Zones, VLANs, Subnets", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    bl = p.layer("Zone bands", locked=True)
    zl = p.layer("Zones")
    tl = p.layer("VLAN & subnet tables (hide before sharing)")
    ll = p.layer("Logical links (L3 adjacencies)")
    dl = p.layer("Routing devices & hosts")
    nl = p.layer("Notes & breakouts")
    lg = p.layer("Legend")
    border = p.layer("Border & title block")
    p.title(bl, f"{st['code']} · {st['name']} — Logical Architecture",
            "Zones · VLANs · subnets. The store firewall is the only boundary: every VLAN ends on it, so every "
            "conversation between zones crosses a rule. Card data lives only in ZONE CDE.", "logical-c14")
    ys = {"R5": (82, 300), "R4": (296, 150), "R3": (460, 220), "R2": (694, 220), "R1": (928, 220)}
    for code, label, _, _ in BANDS:
        y, h = ys[code]
        p.band(bl, y, h, code, label)

    # Outside: internet, carriers, processor, MSP; EDGE zone.
    p.box(dl, 100, 102, 220, 60, "Internet", "via broadband (primary) · LTE (backup)", "cloud")
    p.box(dl, 100, 196, 220, 60, "Payment processor", "card authorization · TLS 1.2+", "card")
    p.box(dl, 340, 102, 220, 60, "SD-WAN overlay", "IPsec to head office HQ1", "cloud")
    p.box(dl, 340, 196, 220, 60, "MSP / vendors", "remote support via HQ jump host only", "people")
    zone_card(p, s, zl, tl, "zone-edge", 600, 96, 560, 172, "On the firewall · no hosts")
    fw = s.card(p, dl, "", "", "FW-01", 1250, 120, 300, 64, pill=False)
    p.cell(nl, "Store firewall and SD-WAN edge: every VLAN below ends here.",
           kit.TEXT + "fontSize=10;fontColor=#64748B;whiteSpace=wrap;", 1250, 190, 300, 30)
    # One row per sub-interface, as NetBox holds them, so a build fills each row in place.
    p.table(tl, 1600, 104, [("INTERFACE", 100), ("ZONE", 190), ("VLAN", 40), ("IP / PREFIX", 110), ("POLICY", 330)],
            [["wan1", "EDGE · Store WAN edge", "—", "DHCP from ISP-A", "SD-WAN member 1 · internet + tunnel"],
             ["wan2", "EDGE", "98", ".1 of the /30", "SD-WAN member 2 · via LTE-01"],
             ["internal1.10", "STORE", "10", ".1 of the subnet", "to HQ apps · internet (filtered)"],
             ["internal1.20", "CDE", "20", ".1 of the subnet", "registers: to PIN pads, POS server, HQ1 if it fails"],
             ["internal1.21", "CDE", "21", ".1 of the subnet", "PIN pads: to the processor only"],
             ["internal1.22", "CDE", "22", ".1 of the subnet", "POS server: to HQ POS and, offline, the processor"],
             ["internal1.30", "STORE", "30", ".1 of the subnet", "staff Wi-Fi: HQ apps · internet (filtered)"],
             ["internal1.40", "IOT", "40", ".1 of the subnet", "cameras: stay in the zone · HQ1 pulls clips"],
             ["internal1.41", "IOT", "41", ".1 of the subnet", "to named vendor clouds only"],
             ["internal1.42", "IOT", "42", ".1 of the subnet", "IoT Wi-Fi: to named vendor clouds only"],
             ["internal1.50", "GUEST", "50", ".1 of the subnet", "internet only · client isolation"],
             ["internal1.99", "MGMT", "99", ".1 of the subnet", "from HQ jump host only · RADIUS to HQ1"]],
            row_h=20, font=9)
    p.cell(tl, "<b>FW-01 logical interfaces (the store standard)</b>", kit.TEXT + "fontSize=12;fontColor=#0F172A;", 1600, 80, 400, 22)

    # Head office (drawn on sheet 6).
    for i, (t, sub, ic) in enumerate([
            ("HQ1 POS central", "price files · journals · store-and-forward drain", "pos-server"),
            ("HQ1 identity", "directory · RADIUS for STORE-STAFF", "lock"),
            ("HQ1 business apps", "ERP · inventory · email", "server"),
            ("HQ1 jump host", "MFA · recorded sessions · MSP entry", "wrench"),
            ("HQ1 video management", "pulls clips from store NVRs", "nvr")]):
        p.box(dl, 100 + i * 290, 330, 270, 64, t, sub, ic, 11)
    p.cell(nl, "Head office is drawn on sheet 6 and in its own drawing (site HQ1).",
           kit.TEXT + "fontSize=10;fontColor=#64748B;", 100, 404, 900, 20)

    # Store operations.
    zone_card(p, s, zl, tl, "zone-store", 100, 474, 700, 192, "Back office and staff devices",
              ["No card data: POS and PIN pads are not on these VLANs.",
               "Handhelds look up stock in HQ1 apps; they never reach the registers.",
               "Internet through the firewall's web filter."], 270)
    zone_card(p, s, zl, tl, "zone-mgmt", 820, 474, 680, 192, "Switch and AP management",
              ["Reachable only from the HQ1 jump host.", "No user devices on VLAN 99."], 250)

    # CDE.
    zone_card(p, s, zl, tl, "zone-cde", 100, 708, 1400, 192, "Registers, PIN pads and the store POS server",
              ["Card data is entered, processed and held only here.",
               "PIN pads encrypt at the reader (P2PE); registers never see clear card numbers.",
               "Out: PIN pads to the processor (TLS), POS server to HQ1 POS central. Nothing else.",
               "In: HQ1 POS central pushes price files; nothing from STORE, GUEST or IOT.",
               "All CDE ports are on the counter switch SW-02, VLANs 20 to 22 only."], 640)

    # Guest and devices.
    zone_card(p, s, zl, tl, "zone-guest", 100, 942, 680, 192, "Customer Wi-Fi",
              ["Internet only, through the firewall.", "Client isolation on the AP.",
               "No route to any store VLAN."], 230)
    zone_card(p, s, zl, tl, "zone-iot", 800, 942, 700, 192, "Cameras, signage, refrigeration, door counter",
              ["Each device type reaches only its own vendor cloud or HQ1.", "Nothing here reaches CDE or STORE."],
              270)

    # The spine: every zone's VLANs end on FW-01.
    spine_x = 1525
    p.edge(ll, fw, None, LOGICAL_EDGE + "exitX=0.92;exitY=1;exitDx=0;exitDy=0;", "",
           tgt_pt=(spine_x, 1038), points=[(spine_x, 260)])
    for y, text in ((570, "internal1.10 · .30 · .99"), (804, "internal1.20–.22"), (1038, "internal1.40 · .41 · .42 · .50")):
        p.edge(ll, None, None, LOGICAL_EDGE + "endArrow=oval;endFill=1;endSize=6;", text,
               src_pt=(spine_x, y), tgt_pt=(1500, y))

    # Right column: rules for the whole store, and the legend.
    p.note(nl, 1600, 474, 770, 210, "Store routing and filtering policy", [
        "One routing table on FW-01: every store VLAN is a subinterface of internal1 (trunk to SW-01).",
        "Default deny between zones; each permitted conversation is a row on sheet 7 (F01 to F28).",
        "Default route: SD-WAN (wan1, then wan2 over LTE). Head office prefixes ride the IPsec overlay.",
        "Guest, IOT and store web (F07) leave by the local internet breakout; from the CDE only F01 and F17, to the processor's addresses; from MGMT only the APs' cloud management (F18).",
        "Transit WAN2-LTE (VLAN 98) is a /30 with no hosts: it exists only to reach LTE-01."], size=11)
    p.note(nl, 1600, 700, 770, 150, "Addressing plan", [
        "Store nnn uses 10.nnn.0.0/16: third octet = VLAN ID (10.14.20.0/26 is store 014, VLAN 20).",
        "Gateways are .1 on FW-01; DHCP on FW-01 for STORE, GUEST and IOT; CDE is static.",
        "The same VLAN IDs and names in every store; only the second octet changes."], size=11)
    std_legend(p, lg, 1600, 942, 770, lines=False)
    p.note(guides, 100, 1166, 1000, 76, "How to extend this sheet", [
        "Add a VLAN: add a row to the zone's table and a subinterface row to FW-01's table.",
        "New store: build from NetBox; the prefix ST014- becomes the store's own.",
        "Hide the VLAN tables layer before sharing outside the company."])
    p.shift_below(290, 100)  # R5 is taller to hold one interface row per VLAN
    finish(p, st, border, "Logical", 2)
    return p


# ---------------------------------------------------------------------------- 3 · physical
def page_physical(s: Store) -> Page:
    st = s.store
    W, H = 2900, 1860
    p = Page("physical", "3 · Physical — Devices, Uplinks, Cables", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    bl = p.layer("Zone bands", locked=True)
    zl = p.layer("Zones (counter · cabinet)")
    ll = p.layer("2 · Links (speed · VLANs)")
    dl = p.layer("1 · Devices")
    ipl = p.layer("3 · Mgmt IPs (hide before sharing)")
    snl = p.layer("3b · Serial numbers")
    cidl = p.layer("4 · Circuit IDs (hide before sharing)")
    nl = p.layer("5 · Breakouts (notes)")
    lrl = p.layer("6 · Link register")
    arl = p.layer("7 · Asset register")
    lg = p.layer("Legend")
    border = p.layer("Border & title block")
    p.title(bl, f"{st['code']} · {st['name']} — Physical Architecture",
            "Devices · cables · ports · where each box lives. Every line is a labeled cable in NetBox; "
            "hover or Edit Data on any device for its full record.", "physical-c12")
    ys = {"R5": (82, 230), "R3": (326, 420), "R1": (760, 300), "R2": (1074, 350)}
    for code, label, _, _ in BANDS:
        if code in ys:
            p.band(bl, ys[code][0], ys[code][1], code, label)

    # Outside: carriers and the edge.
    isp = p.box(dl, 330, 100, 220, 50, "ISP-A · broadband 500M", "fiber to the premises · ONT in back office",
                "cloud", 11)
    car = p.box(dl, 900, 100, 220, 50, "Carrier-B · LTE", "SIM in LTE-01 · roof antenna", "cloud", 11)
    p.cell(cidl, f"CID {st['code']}-BB-01", "text;html=1;fontSize=9;fontColor=#475569;align=left;" + kit.MONO,
           560, 112, 150, 14)
    p.cell(cidl, f"CID {st['code']}-LTE-01", "text;html=1;fontSize=9;fontColor=#475569;align=left;" + kit.MONO,
           1130, 112, 150, 14)
    fw = s.card(p, dl, ipl, snl, "FW-01", 340, 220)
    lte = s.card(p, dl, ipl, snl, "LTE-01", 910, 220)
    p.edge(ll, isp, fw, CIRCUIT_EDGE, "wan1 · 500M")
    p.edge(ll, car, lte, CIRCUIT_EDGE, "LTE")
    s.cable(p, ll, "FW-01", "LTE-01", fw, lte, pill="1G · VLAN 98")

    # Store operations: the cabinet switch, APs, back office.
    cab = p.zone(zl, 300, 336, 880, 150, "Back office cabinet CAB-01 (12U wall cabinet)",
                 "Firewall, 4G router, store switch, POS server, NVR where fitted · UPS 1500VA", "slate")
    zc = p.root.find(f"mxCell[@id='{cab}']")  # title starts right of the firewall's trunk, which runs through here
    zc.set("style", zc.get("style").replace("spacingLeft=12;", "spacingLeft=160;"))
    sw1 = s.card(p, dl, ipl, snl, "SW-01", 340, 400, 240)
    s.cable(p, ll, "FW-01", "SW-01", fw, sw1, exit_=(0.5, 1), entry=(0.3, 0),
            pill="1G · trunk 10,20–22,30,40–42,50,99", pill_pos=-0.55)
    aps = []
    for i, (ap, loc) in enumerate(st.get("aps", APS)):
        x = 320 + i * 220
        aps.append(s.card(p, dl, ipl, snl, ap, x, 640, 200))
        s.cable(p, ll, "SW-01", ap, sw1, aps[-1], exit_=(0.35 + i * 0.12, 1), entry=(0.5, 0),
                points=[(340 + 84 + i * 29, 560 + i * 4), (x + 100, 560 + i * 4)], port_b_pos=None)
    p.cell(nl, "AP uplinks: 1G PoE+ · trunk 30, 42, 50 · native 99", kit.TEXT + "fontSize=10;fontColor=#475569;",
           320, 702, 400, 18)
    bo = s.card(p, dl, ipl, snl, "BO-PC-01", 1200, 640)
    prn = s.card(p, dl, ipl, snl, "PRN-01", 1420, 640)
    for suffix, tgt, i in (("BO-PC-01", bo, 0), ("PRN-01", prn, 1)):
        s.cable(p, ll, "SW-01", suffix, sw1, tgt, exit_=(1, 0.35 + i * 0.3), entry=(0.5, 0),
                points=[(1300 + i * 220, 420 + i * 17)], port_b_pos=None)

    # Guest & devices: NVR, cameras, building devices. Their cables and the counter run share the
    # left-hand riser, so nothing crosses a card.
    iot = [e[0] for e in st.get("endpoints", ENDPOINTS) if e[4] == "zone-iot"]
    for i, suffix in enumerate(iot):
        col, row = i % 6, i // 6
        x, y = 320 + col * 220, 800 + row * 100
        c = s.card(p, dl, ipl, snl, suffix, x, y, 200)
        rx = 270 - i * 4
        if row == 0:
            pts, entry = [(rx, 400 + 8 + i * 4), (rx, 776 - i * 2), (x + 100, 776 - i * 2)], (0.5, 0)
        else:
            pts, entry = [(rx, 400 + 8 + i * 4), (rx, 1000 + i * 2), (x + 100, 1000 + i * 2)], (0.5, 1)
        s.cable(p, ll, "SW-01", suffix, sw1, c, exit_=(0, 0.15 + i * 0.07), entry=entry, points=pts,
                port_a_pos=-0.97, port_b_pos=None)
    p.cell(nl, "IOT drops: 1G PoE · access VLAN 40 (cameras, NVR) or 41 (signage, refrigeration, counter) · "
               "cameras record to the store's NVR", kit.TEXT + "fontSize=10;fontColor=#475569;", 760, 916, 840, 18)

    # CDE: the counter switch and everything on it.
    p.zone(zl, 300, 1086, 1300, 320, "Checkout counter (CDE)",
           "SW-02 under the counter · registers, PIN pads · POS-SRV-01 in CAB-01 on its own run to SW-02", "purple")
    sw2 = s.card(p, dl, ipl, snl, "SW-02", 340, 1190, 240)
    s.cable(p, ll, "SW-01", "SW-02", sw1, sw2, exit_=(0, 0.9), entry=(0, 0.5),
            points=[(286, 450), (286, 1218)], pill="1G · trunk 20–22,99", port_a_pos=-0.98, port_b_pos=0.9, pill_pos=0.74)
    cde = [e[0] for e in st.get("endpoints", ENDPOINTS) if e[4] == "zone-cde"]
    for i, suffix in enumerate(cde):
        n = int(suffix[-2:]) - 1
        if suffix.startswith("POS-SRV"):
            x, y = 1340, 1190
        elif suffix.startswith("PED"):
            x, y = 640 + n * 220, 1290
        else:
            x, y = 640 + n * 220, 1190
        cw = 240 if suffix.startswith("POS-SRV") else 200
        c = s.card(p, dl, ipl, snl, suffix, x, y, cw)
        if suffix.startswith("PED"):
            rx, by = 612 + n * 4, 1276 - n * 4
            pts, entry = [(rx, 1232), (rx, by), (x - 10, by), (x - 10, 1318)], (0, 0.5)
        else:
            rx, by = 596 + i * 4, 1170 - i * 4
            pts, entry = [(rx, 1204), (rx, by), (x + cw / 2, by)], (0.5, 0)
        s.cable(p, ll, "SW-02", suffix, sw2, c, exit_=(1, 0.25 if not suffix.startswith("PED") else 0.75),
                entry=entry, points=pts, port_a_pos=-0.9, port_b_pos=None)
    p.cell(nl, "CDE drops: access VLAN 20 (registers), 21 (PIN pads), 22 (POS server) · only VLANs 20–22 and 99 "
               "exist on SW-02", kit.TEXT + "fontSize=10;fontColor=#475569;", 340, 1376, 1000, 18)

    # Registers: as the engine writes them (links between network devices; every device).
    reg = s.data
    by_name = {d["name"]: d for d in reg["devices"]}
    link_rows = []
    for c in reg["cables"]:
        a = c["a_terminations"][0]["object"]
        b = c["b_terminations"][0]["object"]
        roles = [by_name[x["device"]["name"]]["role"]["slug"] for x in (a, b)]
        if any(r in ENDPOINT_ROLES for r in roles):
            continue
        if roles[1] == "access-switch" and roles[0] != "access-switch":
            a, b = b, a
        row = next(r for r in cables(st) if cable_label(st, r[0], r[1]) == c["label"])
        vlans = row[5].replace("trunk ", "").replace("-", "–") if row[5].startswith("trunk") else f"access {row[5]}"
        link_rows.append([(c["label"].split("-", 1)[1], f"{NETBOX}/dcim/cables/?label={c['label']}"),
                          (f"#{c['id']}", f"{NETBOX}/dcim/cables/{c['id']}/"),
                          f"{a['device']['name'].split('-', 1)[1]} {a['name']}",
                          f"{b['device']['name'].split('-', 1)[1]} {b['name']}", row[6], "Cat6", "connected", vlans])
    p.cell(lrl, "<b>Link register — every link between network devices, both ends, speed, VLANs</b>",
           kit.TEXT + "fontSize=12;", 1660, 92, 1000, 22)
    p.table(lrl, 1660, 118, [("LINK", 110), ("CABLE ID", 70), ("A-SIDE (MEMBERS)", 190), ("B-SIDE (MEMBERS)", 190),
                             ("SPEED", 60), ("MEDIA", 60), ("STATUS", 90), ("TRUNKED VLANS", 410)],
            link_rows, row_h=20, font=9)
    p.cell(lrl, "Drops to end devices (registers, PIN pads, APs, cameras) are on the drawing and in NetBox, not in "
                "this table.", kit.TEXT + "fontSize=10;fontColor=#64748B;", 1660, 122 + 22 + 20 * len(link_rows),
           1000, 20)
    asset_rows = []
    for d in reg["devices"]:
        asset_rows.append([(d["name"], f"{NETBOX}/dcim/devices/?name={d['name']}"), ROLE_NAMES[d["role"]["slug"]],
                           (d["status"]["value"], "", "fontColor=#059669;"), d["device_type"]["model"], d["serial"],
                           (d.get("primary_ip4") or {}).get("address", "").split("/")[0], d["location"]["name"],
                           (d.get("rack") or {}).get("name", ""), f"U{d['position']:g}" if d.get("position") else "",
                           (d.get("custom_fields") or {}).get("sw_version", "")])
    ay = 122 + 22 + 20 * len(link_rows) + 50
    p.cell(arl, "<b>Asset register — mirrors each device's NetBox record</b>", kit.TEXT + "fontSize=12;",
           1660, ay, 900, 22)
    p.table(arl, 1660, ay + 26, [("HOSTNAME", 150), ("ROLE", 120), ("STATUS", 70), ("MODEL", 150), ("SERIAL", 100),
                                 ("MGMT IP", 100), ("ROOM", 130), ("RACK/CAB", 100), ("U", 40), ("SW", 220)],
            asset_rows, row_h=20, font=9)
    std_legend(p, lg, 100, 1440, 700)
    p.note(guides, 840, 1440, 600, 110, "How to extend this sheet", [
        "Add a device: copy a card of the same role (Ctrl+D), Edit Data to set name and role.",
        "Add a cable: draw the line, Edit Data to set cable_label; the pill shows speed and VLANs.",
        "Hide mgmt IPs and circuit IDs before sharing outside the company."])
    finish(p, st, border, "Physical", 3)
    return p


# ---------------------------------------------------------------------------- 3b · cabinet and PoE
SLIM = kit.CARD.replace("verticalAlign=top;spacingTop=5;", "verticalAlign=middle;spacingTop=0;").replace(
    "fontSize=11", "fontSize=10").replace("spacingLeft=38", "spacingLeft=30")


def slim(s: Store, p: Page, layer: str, suffix: str, x, y, w, h=30) -> str:
    """A one-line device card (cabinet elevations, lane rows): still a NetBox device, filled on every build."""
    d = s.dev[suffix]
    role = d["role"]["slug"]
    return p.cell(layer, '<b>%name%</b>&nbsp;&nbsp;<span style="font-size:9px;color:#64748B">%device_type%</span>',
                  SLIM + kit.icon_style(ICON.get(role, role), 20), x, y, w, h, device_attrs(s.store, d))


def page_hardware(s: Store) -> Page:
    st = s.store
    W, H = 2300, 960
    p = Page("hardware", "3b · Cabinet & PoE — CAB-01 · counter · power · cable media", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    fl = p.layer("Cabinet & counter")
    dl = p.layer("1 · Devices")
    tl = p.layer("Tables")
    nl = p.layer("5 · Breakouts (notes)")
    border = p.layer("Border & title block")
    p.title(fl, f"{st['code']} · {st['name']} — Cabinet, counter and power",
            "Where each box physically lives, what feeds it power, and how much PoE the switches have left. "
            "Every device here is the NetBox record; the U numbers are its rack position.")

    # CAB-01 elevation: 12U wall cabinet, U12 at the top.
    x0, y0, uh, cw = 120, 150, 40, 420
    p.cell(fl, "<b>CAB-01</b> · 12U wall cabinet · back office", kit.TEXT + "fontSize=13;", x0, y0 - 40, 420, 24)
    p.cell(fl, "", "rounded=0;fillColor=#1E293B;strokeColor=#0F172A;html=1;", x0 - 16, y0 - 8, cw + 32,
           12 * uh + 16)
    rack_link = f"{NETBOX}/dcim/racks/?site={st['slug']}&name={st['code']}-CAB-01"
    units = {12: ("box", "Patch panel 24 × Cat6 (ports 1–24 = SW-01 1/1/1–24)", "patch-panel"),
             11: ("box", "Brush panel · cable management", "patch-panel"),
             10: ("dev", "FW-01"), 9: ("dev", "LTE-01"), 8: ("dev", "SW-01"),
             7: ("box", "Blank", ""), 6: ("dev", "POS-SRV-01"), 5: ("box", "Blank", ""), 4: ("dev", "NVR-01"),
             3: ("box", "Shelf · ISP-A ONT (fiber in) · LTE antenna lead", "cloud")}
    for u in range(12, 0, -1):
        y = y0 + (12 - u) * uh
        p.cell(fl, f"U{u}", kit.TEXT + "fontSize=9;fontColor=#94A3B8;align=right;verticalAlign=middle;" + kit.MONO,
               x0 - 60, y, 36, uh)
        if u in (1, 2):
            continue
        kind, what, *icon = units[u]
        if kind == "dev":
            slim(s, p, dl, what, x0 + 4, y + 4, cw - 8, uh - 8)
        elif what == "Blank":
            p.cell(fl, "", "rounded=0;fillColor=#334155;strokeColor=#475569;html=1;", x0 + 4, y + 4, cw - 8, uh - 8)
        else:
            p.box(fl, x0 + 4, y + 4, cw - 8, uh - 8, what, "", icon[0], 10, fill="#F1F5F9")
    y = y0 + 10 * uh
    p.box(fl, x0 + 4, y + 4, cw - 8, 2 * uh - 8, "UPS 1500 VA (U1–U2)", "feeds everything in the cabinet "
          "· about 20 min at store load", "ups", 10, fill="#F1F5F9")
    p.cell(nl, "Rack positions come from NetBox (Device ▸ Rack, Position). Anything in the cabinet that is not a "
               "NetBox device (patch panel, UPS, shelf) is drawn here and nowhere else.",
           kit.TEXT + "fontSize=10;fontColor=#64748B;", x0 - 16, y0 + 12 * uh + 20, cw + 32, 44)

    # The checkout counter.
    cx, cy = 680, 110
    p.zone(fl, cx, cy, 760, 560, "Checkout counter (CDE)",
           "SW-02 sits under the counter in a locked tray · one lane = one register + one PIN pad", "purple")
    slim(s, p, dl, "SW-02", cx + 30, cy + 70, 330)
    p.cell(nl, "Counter UPS 700 VA: SW-02 and the registers, about 15 min · the PIN pads are PoE from SW-02",
           kit.TEXT + "fontSize=10;fontColor=#475569;", cx + 380, cy + 66, 360, 40)
    p.cell(fl, "<b>REGISTER</b>", kit.TEXT + "fontSize=9;fontColor=#7C3AED;", cx + 30, cy + 130, 300, 16)
    p.cell(fl, "<b>PIN PAD</b>", kit.TEXT + "fontSize=9;fontColor=#7C3AED;", cx + 390, cy + 130, 300, 16)
    for n in range(4):
        if f"POS-0{n + 1}" in s.dev:
            slim(s, p, dl, f"POS-0{n + 1}", cx + 30, cy + 150 + n * 50, 330)
        if f"PED-0{n + 1}" in s.dev:
            slim(s, p, dl, f"PED-0{n + 1}", cx + 390, cy + 150 + n * 50, 330)
    p.table(tl, cx + 30, cy + 360, [("LANE n", 150), ("WIRING STANDARD", 550)], [
        ["Register", "SW-02 port n · access VLAN 20 · counter UPS"],
        ["PIN pad", "SW-02 port n + 4 · access VLAN 21 · PoE class 2 · tamper seal checked at open"],
        ["Spare ports", "every port with no lane device (10, 11; 4 and 8 at three lanes): shut, VLAN 999"]], row_h=24)

    # PoE budget (the standard's numbers: worst case at the PSE, 802.3 class maximums).
    poe = [["Access points", "802.3at · class 4", "4", "30.0", "120.0"],
           ["Cameras", "802.3af · class 3", "4", "15.4", "61.6"],
           ["Signage · refrigeration · counter", "802.3af · class 2", "3", "7.0", "21.0"],
           [("Total SW-01", "", "fontStyle=1;"), "budget 370 W", "11", "", ("202.6 · 55 %", "", "fontStyle=1;")],
           ["PIN pads (on SW-02)", "802.3af · class 2", "4", "7.0", "28.0"],
           [("Total SW-02", "", "fontStyle=1;"), "budget 139 W", "4", "", ("28.0 · 20 %", "", "fontStyle=1;")]]
    tx = 1500
    p.cell(tl, "<b>PoE budget — the store standard</b> (most devices a store may have; watts at the switch, class maximum)",
           kit.TEXT + "fontSize=12;", tx, 110, 760, 22)
    p.table(tl, tx, 138, [("PORTS", 230), ("STANDARD · CLASS", 170), ("UP TO", 80), ("W EACH", 80),
                          ("W TOTAL", 200)], poe, row_h=22)
    p.note(nl, tx, 300, 760, 110, "Why the budget matters", [
        "A refit that adds two cameras and a digital menu board adds about 45 W: still inside 370 W.",
        "Keep each switch under about 80 % of its budget. Past 100 % it refuses or drops power, and port "
        "priority decides who loses: PIN pads and APs high, signage low.",
        "Check the AP datasheet: many Wi-Fi 6E and 7 models need 802.3bt for full function.",
        "Record each PoE device's class on its NetBox interface (PoE mode and type) and this table can be "
        "checked against NetBox."], size=10)

    # Cable media and power standard.
    p.cell(tl, "<b>Cable media and labels</b>", kit.TEXT + "fontSize=12;", tx, 440, 760, 22)
    p.table(tl, tx, 466, [("ITEM", 200), ("STANDARD", 560)], [
        ["Drops", "Cat6 U/UTP, blue; 90 m permanent link max; every drop on the patch panel"],
        ["Counter run", "SW-01 1/1/23 to SW-02 1/1/12 in its own conduit to the counter"],
        ["Fiber", "ISP-A only, ending at the ONT on the shelf (U3); no store-owned fiber"],
        ["Labels", "STORE-DEVICE-PORT of the A side: ST014-SW01-P05, at both ends and in NetBox"],
        ["Spares", "One 24-port PoE switch and one firewall per region, held at HQ1"]], row_h=22)
    # Modules & power register: rebuilt from NetBox modules, module bays and inventory items.
    p.cell(tl, "<b>Modules & power register</b> (from NetBox: modules in bays, power supplies, fans)",
           kit.TEXT + "fontSize=12;", tx, 618, 760, 22)
    p.table(tl, tx, 644, [("DEVICE", 130), ("CHASSIS", 150), ("POWER", 170), ("MODULES", 130), ("OTHER", 180)], [
        [name(st, "FW-01"), "FortiGate 61F", "AC adapter 12 V", "—", "—"],
        [name(st, "LTE-01"), "IX20", "AC adapter 12 V", "—", "—"],
        [name(st, "SW-01"), "CX 6100 24G PoE", "Internal PSU 370 W", "—", "Fan tray"],
        [name(st, "SW-02"), "CX 6000 12G PoE", "Internal PSU 139 W", "—", "—"]], row_h=22)
    p.note(guides, tx, 800, 760, 110, "How to extend this sheet", [
        "A taller cabinet: add U rows above U12 and move the title up; keep U1 at the bottom.",
        "A fifth lane: copy a register and a PIN pad card, then Edit Data to set their names; NetBox fills the rest.",
        "Change the PoE table when the standard changes, not when a store changes."])
    finish(p, st, border, "Cabinet & PoE", "3b")
    return p


# ---------------------------------------------------------------------------- 3d · wireless
def page_wireless(s: Store) -> Page:
    st = s.store
    W, H = 2300, 1160
    p = Page("wireless", "3d · Wireless — store floor · APs · SSIDs", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    fl = p.layer("Floor plan")
    dl = p.layer("1 · Devices")
    tl = p.layer("SSIDs")
    nl = p.layer("5 · Breakouts (notes)")
    lg = p.layer("Legend")
    border = p.layer("Border & title block")
    p.title(fl, f"{st['code']} · {st['name']} — Wireless", "Access points on the store floor plan and the "
            "SSIDs they broadcast. No card data travels over Wi-Fi: registers and PIN pads are wired.",
            "wireless-c10")

    room = ("rounded=0;fillColor={f};strokeColor=#94A3B8;strokeWidth=1.5;align=left;verticalAlign=top;"
            "spacingLeft=10;spacingTop=6;fontSize=12;fontStyle=1;fontColor=#475569;html=1;whiteSpace=wrap;" + FONT)
    x0, y0 = 100, 120
    p.cell(fl, "Sales floor", room.format(f="#FFFFFF"), x0, y0, 760, 520)
    p.cell(fl, "Checkout", room.format(f="#F8F4FE"), x0 + 20, y0 + 380, 380, 120)
    p.cell(fl, "Stockroom", room.format(f="#F8FAFC"), x0 + 760, y0, 320, 300)
    p.cell(fl, "Back office", room.format(f="#F8FAFC"), x0 + 760, y0 + 300, 320, 220)
    p.cell(fl, "Rear yard", room.format(f="#F1F5F9"), x0 + 1080, y0, 160, 520)
    p.cell(fl, "Entrance", "text;html=1;align=center;fontSize=10;fontColor=#64748B;" + FONT, x0 + 310, y0 + 520,
           140, 20)
    p.cell(fl, "Upstairs (mezzanine: staff room and office)", room.format(f="#F8FAFC"), x0, y0 + 600, 760, 200)
    places = {"AP-01": (x0 + 100, y0 + 200), "AP-02": (x0 + 480, y0 + 120), "AP-03": (x0 + 810, y0 + 120),
              "AP-04": (x0 + 300, y0 + 680)}
    for ap, _ in st.get("aps", APS):
        x, y = places[ap]
        s.card(p, dl, "", "", ap, x, y, 220)
    p.cell(nl, "Placement from the last survey: one AP per 300 m² of open floor, one in the stockroom for the "
               "handhelds, one upstairs, each on the ceiling at 3 m. Redraw after a refit, not after a build.",
           kit.TEXT + "fontSize=10;fontColor=#64748B;", x0, y0 + 820, 900, 34)
    p.cell(nl, "Channel plan: 5 GHz at 40 MHz on non-overlapping channels, 2.4 GHz on 1, 6 and 11 only (radio "
               "interfaces in NetBox). Check it against the dated survey, not against this sheet.",
           kit.TEXT + "fontSize=10;fontColor=#64748B;", x0, y0 + 856, 900, 34)

    # SSIDs (filled from NetBox wireless LANs).
    tx = 1400
    # The SSID table sits on its own card: a build that adds an SSID grows this card and moves only this column.
    p.cell(tl, "", "rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;html=1;"
           + FONT, tx - 14, 100, 888, 232)
    p.cell(tl, "<b>SSIDs</b> — the same in every store", kit.TEXT + "fontSize=12;", tx, 110, 600, 22)
    rows = []
    for ssid, vid, auth, zone in WLANS:
        v = next(v for v in VLANS if v[0] == vid)
        fields = WLAN_FIELDS[ssid][0]
        rows.append([(ssid, f"{NETBOX}/wireless/wireless-lans/?ssid={ssid}"), auth,
                     (f"{vid} · {v[3].format(n=st['net'])}", f"{NETBOX}/ipam/vlans/?site={st['slug']}&vid={vid}"),
                     ZONES[zone][0], "2.4 GHz" if zone == "zone-iot" else "2.4 GHz · 5 GHz", "Local switching",
                     "every AP", " · ".join(x for x in ("client isolation" if fields["wlan_client_isolation"] else "",
                                                        "captive portal" if fields["wlan_portal"] == "captive" else "")
                                            if x)])
    # Rows are tall enough for what a build writes (four rooms broadcast each SSID), so a build never grows them.
    p.table(tl, tx, 138, [("SSID", 95), ("SECURITY · AAA", 150), ("VLAN · SUBNET", 115), ("ZONE", 50),
                          ("BANDS", 95), ("SWITCHING", 85), ("BROADCAST ON", 150), ("GUEST CONTROLS", 120)],
            rows, row_h=52)
    p.note(nl, tx, 346, 860, 120, "Rules for every store", [
        "STORE-STAFF: handhelds, tablets and push-to-talk handsets, 802.1X with the staff directory at HQ1; "
        "lands in ZONE STORE.",
        "STORE-GUEST: open with a terms page; client isolation on the AP; internet only, 10 Mb/s per client.",
        "STORE-IOT: shelf-label base stations and scales; a key per device; lands in ZONE IOT, never STORE.",
        "Guest Wi-Fi is switched off when the store is on the 4G line (sheet 5).",
        "No SSID lands in ZONE CDE. A wireless PIN pad would change the CDE: redraw sheets 2, 4 and 7 first."],
        size=10)
    p.note(nl, tx, 880, 860, 70, "How the APs are managed", [
        "Cloud-managed (NetBox: wireless_management on the estate region): the APs take config from the cloud "
        "dashboard over HTTPS (F18). No controller in the store; traffic is switched locally onto the VLANs above."],
        size=10, attrs={"netdiagrams_wireless_mgmt": "1"})
    p.table(tl, tx, 506, [("HOSTNAME", 150), ("STATUS", 70), ("ROOM", 170), ("SWITCH PORT", 120),
                          ("MODE", 140), ("POWER", 210)],
            [[(name(st, ap), f"{NETBOX}/dcim/devices/?name={name(st, ap)}"), ("active", "", "fontColor=#059669;"),
              loc, f"SW-01 1/1/{n}", "Cloud-managed", "802.3at (Type 2)"]
             for n, (ap, loc) in enumerate(st.get("aps", APS), start=1)], row_h=22)
    p.cell(tl, "<b>Access points</b> (room from NetBox Location)", kit.TEXT + "fontSize=12;", tx, 480, 600, 22)
    std_legend(p, lg, tx, 640, 860, lines=False)
    p.note(guides, tx, 960, 860, 60, "How to extend this sheet", [
        "Replace the floor plan with the store's own (Arrange ▸ Insert ▸ Image, then lock the layer).",
        "Add an AP: copy an AP card and Edit Data to set its name; NetBox fills the rest."])
    finish(p, st, border, "Wireless", "3d")
    return p


# ---------------------------------------------------------------------------- 4 · flows
FLOWS = [
    # id, kind, section, source (zone, text), destination (zone or None, text), label
    ("F01", "ok", "card", ("CDE", "PIN pads"), ("OUT", "Payment processor"), "TLS 443 · card data, encrypted at the reader (P2PE)"),
    ("F02", "ok", "card", ("CDE", "Registers"), ("CDE", "PIN pads"), "amount and result · vendor protocol · VLAN 20 → 21"),
    ("F03", "ok", "card", ("CDE", "Registers"), ("CDE", "POS server"), "sales · HTTPS 443 · VLAN 20 → 22"),
    ("F04", "ok", "card", ("CDE", "POS server"), ("HQ", "HQ1 POS central"), "journals · HTTPS 443 over the SD-WAN tunnel"),
    ("F05", "ok", "card", ("HQ", "HQ1 POS central"), ("CDE", "POS server"), "price files and updates · HTTPS 443"),
    ("F16", "cond", "card", ("CDE", "Registers"), ("HQ", "HQ1 POS central"),
     "only while POS-SRV-01 is down · HTTPS 443"),
    ("F17", "cond", "card", ("CDE", "POS server"), ("OUT", "Payment processor"),
     "stored offline sales, when a line returns · TLS 443"),
    ("F06", "ok", "store", ("STORE", "Back office · handhelds"), ("HQ", "HQ1 business apps"), "ERP, stock, email · HTTPS 443"),
    ("F07", "ok", "store", ("STORE", "Back office · handhelds"), ("OUT", "Internet"), "web · through the web filter"),
    ("F15", "ok", "store", ("MGMT", "Access points"), ("HQ", "HQ1 identity (RADIUS)"),
     "802.1X for STORE-STAFF · RADIUS over the tunnel"),
    ("F18", "ok", "store", ("MGMT", "Access points"), ("OUT", "Wi-Fi cloud management (named)"),
     "config, firmware, rogue AP reports · HTTPS 443 out"),
    ("F08", "ok", "devices", ("GUEST", "Customers' phones"), ("OUT", "Internet"), "80 / 443 · 10 Mb/s each · isolated"),
    ("F19", "ok", "devices", ("GUEST", "Customers' phones"), ("OUT", "Guest portal (hosted, named)"),
     "terms page before internet · HTTPS 443"),
    ("F09", "ok", "devices", ("IOT", "Cameras"), ("IOT", "NVR-01"), "RTSP · same VLAN, never leaves the zone"),
    ("F10", "ok", "devices", ("HQ", "HQ1 video management"), ("IOT", "NVR-01"), "clips on request · HTTPS 443"),
    ("F11", "ok", "devices", ("IOT", "Refrigeration monitor"), ("OUT", "Vendor cloud (named)"), "alarms · HTTPS 443 to one FQDN"),
    ("F12", "ok", "devices", ("IOT", "Signage player"), ("OUT", "Signage cloud (named)"), "content · HTTPS 443 to one FQDN"),
    ("F20", "ok", "devices", ("IOT", "Shelf labels · scales (STORE-IOT)"), ("OUT", "Shelf-label cloud (named)"),
     "prices to labels · HTTPS 443 to one FQDN"),
    ("F13", "cond", "support", ("HQ", "HQ1 jump host"), ("MGMT", "Switches · APs · FW"), "SSH / HTTPS · MFA · change ticket"),
    ("F14", "cond", "support", ("OUT", "MSP / vendor"), ("HQ", "HQ1 jump host"), "approved window · recorded session"),
    ("F28", "cond", "support", ("HQ", "HQ1 jump host"), ("CDE", "POS server"),
     "POS vendor support · MFA · approved window · recorded"),
    ("F21", "ok", "plumbing", ("MGMT", "Switches · APs · FW"), ("HQ", "HQ1 SIEM"), "logs · syslog over TLS"),
    ("F27", "ok", "plumbing", ("CDE", "POS server · registers"), ("HQ", "HQ1 SIEM"), "logs · syslog over TLS"),
    ("F22", "ok", "plumbing", ("MGMT", "Switches · APs · FW"), ("HQ", "HQ1 time servers"), "time · NTP"),
    ("F23", "ok", "plumbing", ("STORE", "Store VLANs (not GUEST)"), ("HQ", "HQ1 DNS resolvers"),
     "names · DNS relayed by FW-01"),
    ("F24", "ok", "plumbing", ("HQ", "HQ1 NMS collector"), ("MGMT", "Switches · APs · FW"),
     "SNMPv3 polling, nightly config backup"),
    ("F25", "ok", "plumbing", ("STORE", "Back office PC"), ("HQ", "HQ1 patch and AV servers"), "updates · HTTPS 443"),
    ("F26", "ok", "plumbing", ("CDE", "POS server · registers"), ("HQ", "HQ1 patch and AV servers"),
     "signed updates · HTTPS 443"),
    ("D01", "deny", "denied", ("GUEST", "Guest Wi-Fi"), ("CDE", "Anything in CDE"), "denied · logged"),
    ("D02", "deny", "denied", ("IOT", "Store devices"), ("CDE", "Anything in CDE"), "denied · logged"),
    ("D05", "deny", "denied", ("IOT", "Store devices · STORE-IOT"), ("STORE", "Back office · handhelds"),
     "denied · logged"),
    ("D03", "deny", "denied", ("STORE", "Back office"), ("CDE", "Anything in CDE"), "denied · use HQ1 apps"),
    ("D04", "deny", "denied", ("OUT", "Internet"), ("STORE", "Any store zone"), "no inbound path at all"),
]
ZONE_COLOR = {"CDE": "purple", "STORE": "green", "MGMT": "teal", "GUEST": "amber", "IOT": "amber", "HQ": "blue",
              "OUT": "slate"}
SECTIONS = {"card": "The card's journey", "store": "Store business", "devices": "Guests and store devices",
            "support": "Support (conditional)", "plumbing": "Plumbing: logs, time, names, monitoring, patches",
            "denied": "Denied (the default for everything else)"}


def page_flows(s: Store) -> Page:
    st = s.store
    W, H = 2400, 2620
    p = Page("flows", "4 · Traffic flows — the card's journey · every permitted path", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    bl = p.layer("Lanes", locked=True)
    fl = p.layer("Flows")
    nl = p.layer("Notes & breakouts")
    lg = p.layer("Legend")
    border = p.layer("Border & title block")
    p.title(bl, f"{st['code']} · {st['name']} — Traffic flows",
            "One lane per permitted conversation, initiator on the left. Every lane crosses FW-01 and is a row "
            "in the flow register (sheet 7). Anything not drawn here is denied.")
    gate_x, gate_w = 900, 90
    src_x, dst_x, box_w = 140, 1180, 330
    y = 110
    rows = []
    last = None
    for fid, kind, sec, (sz, stext), (dz, dtext), label in FLOWS:
        if sec != last:
            p.cell(bl, f"<b>{SECTIONS[sec]}</b>", kit.TEXT + "fontSize=12;fontColor=#0F172A;", src_x, y + 6, 600,
                   22)
            y += 34
            last = sec
        rows.append((y, fid, kind, sz, stext, dz, dtext, label))
        y += 62
    top, bottom = 110, y + 4
    p.cell(bl, "<b>FW-01</b><br><span style=\"font-size:9px\">every lane<br>crosses here</span>",
           "rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#FAE3E3;strokeColor=#F5C2C2;fontSize=11;"
           "fontColor=#B91C1C;html=1;verticalAlign=top;spacingTop=8;whiteSpace=wrap;" + FONT, gate_x, top, gate_w,
           bottom - top)
    for y, fid, kind, sz, stext, dz, dtext, label in rows:
        color = PALETTE_INK[ZONE_COLOR[sz]]
        p.pill(fl, src_x - 76, y + 13, 62, 22, fid, "red" if kind == "deny" else "green" if kind == "ok" else
               "amber", 10)
        src = p.box(fl, src_x, y, box_w, 48, stext, f"ZONE {sz}" if sz not in ("HQ", "OUT") else
                    {"HQ": "head office (HQ1)", "OUT": "outside"}[sz], ZONE_ICON[sz], 11,
                    fill=PALETTE_FILL[ZONE_COLOR[sz]], stroke=color)
        style = {"ok": FLOW_OK, "cond": FLOW_COND, "deny": FLOW_DENY}[kind]
        if kind == "deny":
            p.edge(fl, src, None, style + "endArrow=none;exitX=1;exitY=0.5;exitDx=0;exitDy=0;", label,
                   tgt_pt=(gate_x + gate_w / 2, y + 24))
            p.cell(fl, "✕", "ellipse;fillColor=#DC2626;strokeColor=#FFFFFF;strokeWidth=2;fontColor=#FFFFFF;"
                   "fontSize=11;fontStyle=1;html=1;" + FONT, gate_x + gate_w / 2 - 11, y + 13, 22, 22)
            p.box(fl, dst_x, y, box_w, 48, dtext, f"ZONE {dz}" if dz not in ("HQ", "OUT") else "",
                  ZONE_ICON[dz], 11, fill="#F8FAFC", stroke="#E2E8F0")
        else:
            dst = p.box(fl, dst_x, y, box_w, 48, dtext, f"ZONE {dz}" if dz not in ("HQ", "OUT") else
                        {"HQ": "head office (HQ1)", "OUT": "outside"}[dz], ZONE_ICON[dz], 11,
                        fill=PALETTE_FILL[ZONE_COLOR[dz]], stroke=PALETTE_INK[ZONE_COLOR[dz]])
            e = p.edge(fl, src, dst, style + "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;"
                       "entryDy=0;", label)
            if fid == "F09":  # never crosses the firewall: drawn over the gate, dashed through it
                p.root.find(f"mxCell[@id='{e}']").set("style", style.replace("strokeColor=#059669;",
                                                                             "strokeColor=#059669;opacity=60;")
                                                     + "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;"
                                                       "entryY=0.5;entryDx=0;entryDy=0;")
        p.cell(nl, PORTS_OF.get(fid, ""), kit.TEXT + "fontSize=9;fontColor=#64748B;" + kit.MONO,
               dst_x + box_w + 16, y + 14, 300, 20)

    # The card's journey, in words.
    jx = 1880
    p.note(nl, jx, 110, 480, 330, "The card's journey (F01 to F05, F16, F17)", [
        "1. The customer taps or inserts at PED-0n. The PIN pad encrypts the card data inside the reader (P2PE).",
        "2. The register sends the amount to its PIN pad (F02) and gets back approved or declined, never the "
        "card number.",
        "3. The PIN pad sends the encrypted card data to the processor (F01), straight out of the store over "
        "TLS.",
        "4. The register records the sale on the POS server (F03), which sends the journal to HQ1 (F04).",
        "5. Overnight, HQ1 POS central sends price files back (F05).",
        "On a bad day: registers reach HQ1 directly while the POS server is down (F16), and the server drains "
        "sales it stored offline to the processor when a line returns (F17)."], size=11)
    p.note(nl, jx, 460, 480, 150, "Reading the lanes", [
        "Left is who starts the conversation; the reply needs no lane of its own.",
        "Green: always allowed. Amber dashed: allowed only on a condition: approval, MFA and a window "
        "(F13, F14, F28) or a named failure (F16, F17). Red: denied at FW-01 and logged.",
        "F09 stays inside ZONE IOT: it is drawn so nobody adds a rule for it."], size=11)
    p.legend(lg, jx, 630, 480, (), [(FLOW_OK, "Permitted flow"),
                                    (FLOW_COND, "Conditional (approval or failure state)"),
                                    (FLOW_DENY, "Denied at the firewall")],
             [("CDE", "purple"), ("STORE", "green"), ("MGMT", "teal"), ("GUEST · IOT", "amber"), ("HQ1", "blue"),
              ("OUTSIDE", "slate")])
    p.note(guides, jx, 820, 480, 120, "How to extend this sheet", [
        "Add a lane: copy a row (pill, both boxes, the arrow) and give it the next free ID.",
        "Then add the same ID to the flow register on sheet 7, and only then to the firewall.",
        "Removing a lane is the same in reverse: register first, then firewall, then this sheet."])
    finish(p, st, border, "Traffic flows", 4)
    return p


PALETTE_FILL = {k: v[2] for k, v in kit.PALETTE.items()}
PALETTE_INK = {k: v[3] for k, v in kit.PALETTE.items()}
ZONE_ICON = {"CDE": "pos-terminal", "STORE": "workstation", "MGMT": "access-switch", "GUEST": "wifi",
             "IOT": "camera", "HQ": "building", "OUT": "cloud"}
PORTS_OF = {"F01": "tcp/443", "F02": "tcp/vendor", "F03": "tcp/443", "F04": "tcp/443", "F05": "tcp/443",
            "F06": "tcp/443", "F07": "tcp/80,443", "F08": "tcp/80,443", "F09": "tcp/554", "F10": "tcp/443",
            "F11": "tcp/443", "F12": "tcp/443", "F13": "tcp/22,443", "F14": "tcp/443", "F15": "udp/1812,1813", "F16": "tcp/443",
            "F17": "tcp/443", "F18": "tcp/443", "F19": "tcp/443", "F20": "tcp/443", "F21": "tcp/6514", "F22": "udp/123",
            "F23": "udp,tcp/53", "F24": "udp/161, tcp/22", "F25": "tcp/443", "F26": "tcp/443", "F27": "tcp/6514",
            "F28": "tcp/22,443",
            "D01": "any", "D02": "any", "D03": "any", "D04": "any", "D05": "any"}


# ---------------------------------------------------------------------------- 5 · failover
def page_failover(s: Store) -> Page:
    st = s.store
    W, H = 2300, 1440
    p = Page("failover", "5 · Failover — the line, the power, the box", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    wl = p.layer("WAN paths")
    sl = p.layer("Scenarios")
    border = p.layer("Border & title block")
    p.title(wl, f"{st['code']} · {st['name']} — Failover", "What happens when something fails, what the "
            "customer sees, and how long the store can keep trading. Test each row once a quarter.")

    # The two paths out.
    fw = p.box(wl, 140, 140, 260, 60, "FW-01 · store firewall", "SD-WAN edge · wan1 + wan2", "firewall", 12)
    lte = p.box(wl, 420, 280, 240, 56, "LTE-01 · 4G router", "wan2 · VLAN 98", "lte-router", 11)
    isp = p.box(wl, 760, 142, 260, 56, "ISP-A broadband 500M", "primary", "cloud", 11)
    car = p.box(wl, 760, 280, 260, 56, "Carrier-B 4G", "backup · 100 GB a month", "cloud", 11)
    hq = p.box(wl, 1160, 190, 280, 96, "HQ1 · head office", "POS central · apps · jump host", "building", 12)
    p.edge(wl, fw, isp, CIRCUIT_EDGE + "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;"
           "entryDy=0;", "wan1")
    p.edge(wl, fw, lte, LINK_EDGE + "strokeColor=#2196F3;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0;entryY=0.5;"
           "entryDx=0;entryDy=0;", "wan2")
    p.edge(wl, lte, car, CIRCUIT_EDGE, "")
    p.edge(wl, isp, hq, FLOW_OK + "endArrow=none;entryX=0.5;entryY=0;entryDx=0;entryDy=0;", "tunnel 1 (preferred)")
    p.edge(wl, car, hq, FLOW_COND + "endArrow=none;entryX=0.5;entryY=1;entryDx=0;entryDy=0;", "tunnel 2 (on failure)")
    p.cell(wl, "<b>SD-WAN rule</b>", kit.TEXT + "fontSize=12;", 1600, 110, 560, 22)
    p.table(wl, 1600, 136, [("ORDER", 60), ("TRAFFIC", 260), ("PATH", 120), ("ON 4G", 160)], [
        ["1", "Card data (F01, F04, F16, F17)", "wan1, then wan2", "kept"],
        ["2", "Store and Wi-Fi (F06, F07, F15, F18)", "wan1, then wan2", "kept, web filter stricter"],
        ["3", "Plumbing (F21 to F27)", "wan1, then wan2", "kept"],
        ["4", "Store devices (F10 to F12, F20)", "wan1, then wan2", "kept (small)"],
        ["5", "Guest Wi-Fi (F08, F19)", "wan1 only", ("switched off", "", "fontColor=#B45309;fontStyle=1;")]],
        row_h=24)

    scen = [
        ("Broadband down", "x", "SD-WAN moves every tunnel to wan2 within seconds.",
         "Nothing, except guest Wi-Fi is off.", "As long as the 4G data plan lasts (about a week).",
         "Unplug wan1 at open; a test sale must complete."),
        ("Both lines down", "x", "Registers switch to offline mode: card sales are stored on POS-SRV-01 and sent "
         "to the processor when a line returns (F17).", "Card sales still work under the offline limit; above it, cash or another card.",
         "Store policy: 4 hours, then the manager calls head office.", "Unplug both at a quiet hour; check the "
         "stored sales drain within 10 minutes."),
        ("Firewall FW-01 fails", "firewall", "The whole store is cut off: FW-01 is every VLAN's gateway and both "
         "lines end on it.", "As for both lines down (offline mode).", "Spare from HQ1 by courier, same day; "
         "config restored from FortiManager.", "Restore the config to a lab spare twice a year."),
        ("Counter switch SW-02 fails", "access-switch", "Every lane loses its register and PIN pad together.",
         "Checkout closed; the queue moves to handhelds (STAFF) for stock checks only.",
         "Swap in the spare 12-port from the back office: 15 minutes.", "Keep the spare configured and labeled; "
         "check it at every quarterly test."),
        ("Power cut", "ups", "The cabinet UPS carries FW-01, LTE-01, SW-01, POS-SRV-01 and NVR-01; the counter "
         "UPS carries SW-02 and the registers.", "Lights out but the tills work.", "About 15 minutes at the counter, "
         "20 in the cabinet.", "Pull the UPS plug at the quarterly test; time it."),
        ("POS server fails", "pos-server", "Registers send sales straight to HQ1 POS central (F16, "
         "allowed only while the server is down).", "Nothing, as long as a line is up.", "Until the server is replaced.",
         "Stop the POS service at a quiet hour; a test sale must complete."),
        ("Wi-Fi management or RADIUS unreachable", "wifi", "APs keep broadcasting with the config they hold. "
         "New STORE-STAFF logins wait for HQ1 RADIUS (F15); Wi-Fi changes wait for the cloud (F18).",
         "Nothing; staff already signed in stay on.", "Until the tunnel or the cloud is back; tills are wired "
         "and keep trading.", "Block F18 at a quiet hour; a handheld must stay connected and a guest must still "
         "reach the portal."),
    ]
    cw, ch = 680, 250
    for n, (title, icon, what, sees, how_long, test) in enumerate(scen):
        x = 100 + (n % 3) * (cw + 30)
        y = 440 + (n // 3) * (ch + 30)
        p.cell(sl, f"<b style=\"font-size:15px\">{title}</b>", "rounded=1;absoluteArcSize=1;arcSize=16;"
               "fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;align=left;verticalAlign=top;spacingLeft=56;"
               "spacingTop=14;fontSize=12;fontColor=#0F172A;html=1;" + FONT + kit.icon_style(icon, 34).replace(
                   "imageVerticalAlign=middle;", "imageVerticalAlign=top;"), x, y, cw, ch)
        p.table(sl, x + 16, y + 56, [("", 130), ("", cw - 162)], [
            [("What happens", "", "fontStyle=1;"), what], [("Customer sees", "", "fontStyle=1;"), sees],
            [("How long", "", "fontStyle=1;"), how_long], [("Test", "", "fontStyle=1;"), test]], row_h=44,
            head_h=0)
    p.note(guides, 100, 1290, 700, 70, "How to extend this sheet", [
        "One card per failure the store has actually had, or that the business asked about.",
        "Each card's Test row is the quarterly check; date the last one in NetBox (site journal)."])
    finish(p, st, border, "Failover", 5)
    return p


# ---------------------------------------------------------------------------- 6 · estate
def page_multisite() -> Page:
    W, H = 2300, 1300
    p = Page("multisite", "6 · Estate — head office and stores, one standard", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    ml = p.layer("Estate")
    tl = p.layer("Store register")
    nl = p.layer("Standards")
    hl = p.layer("Head office failover")
    border = p.layer("Border & title block")
    p.title(ml, "Retail estate — head office and stores", "Every store is the same drawing with different "
            "numbers. Head office (HQ1) holds the systems stores talk to; each store reaches it over two tunnels.")
    hq = p.cell(ml, "<b style=\"font-size:15px\">HQ1 · head office</b><br><span style=\"font-size:10px;"
                "color:#64748B\">POS central · identity (RADIUS) · business apps · jump host · video "
                "management<br>two internet lines · SD-WAN hub · firewall pair</span>",
                kit.CARD.replace("verticalAlign=top;spacingTop=5;", "verticalAlign=middle;").replace(
                    "spacingLeft=38", "spacingLeft=60") + kit.icon_style("building", 40), 780, 130, 560, 100)
    inet = p.box(ml, 1500, 145, 240, 70, "Internet", "and the payment processor", "cloud", 12)
    p.edge(ml, hq, inet, CIRCUIT_EDGE, "")
    stores = [
        ("ST014", "Store 014", "High Street · 2 floors", "3 lanes · 4 APs · 4 cameras", "", "the template"),
        ("ST027", "Store 027", "Market Square", "4 lanes · 3 APs · 3 cameras", "AP-03 offline", ""),
        ("ST031", "Store 031", "Northfield Mall unit", "2 lanes · 2 APs · mall CCTV", "SW-02 planned", ""),
    ]
    for n, (code, name, where, what, flag, note) in enumerate(stores):
        x = 200 + n * 520
        body = (f"<b style=\"font-size:14px\">{code} · {name}</b><br><span style=\"font-size:10px;color:#64748B\">"
                f"{where}<br>{what}</span>"
                + (f"<br><span style=\"font-size:10px;color:#B45309\">{flag}</span>" if flag else "")
                + (f"<br><span style=\"font-size:10px;color:#2563EB\">{note}</span>" if note else ""))
        c = p.cell(ml, body, kit.CARD.replace("verticalAlign=top;spacingTop=5;", "verticalAlign=middle;").replace(
            "spacingLeft=38", "spacingLeft=56") + kit.icon_style("store", 36), x, 400, 440, 110,
                   {"link": f"{NETBOX}/dcim/sites/?slug={code.lower()}", "linkTarget": "_blank",
                    "placeholders": "1", "tooltip": f"Open {code} in NetBox"})
        for k, style in enumerate((FLOW_OK, FLOW_COND)):
            p.edge(ml, c, hq, style + f"endArrow=none;exitX={0.4 + k * 0.3};exitY=0;exitDx=0;exitDy=0;"
                   f"entryX={0.12 + n * 0.3 + k * 0.12:.2f};entryY=1;entryDx=0;entryDy=0;", "")
    p.cell(ml, "<b>ST0nn · the next store</b><br><span style=\"font-size:10px;color:#64748B\">enter it in NetBox, "
               "then: netdiagrams build --profile retail --site st0nn</span>",
           "rounded=1;absoluteArcSize=1;arcSize=16;fillColor=none;strokeColor=#94A3B8;dashed=1;dashPattern=6 4;"
           "align=left;verticalAlign=middle;spacingLeft=16;fontSize=12;fontColor=#475569;html=1;whiteSpace=wrap;"
           + FONT, 1760, 400, 440, 110)
    p.legend(ml, 1760, 250, 440, (), [(FLOW_OK.replace("endArrow=block", "endArrow=none"), "Tunnel 1 · broadband "
                                       "(preferred)"), (FLOW_COND.replace("endArrow=block", "endArrow=none"),
                                                        "Tunnel 2 · 4G (on failure)")], ())

    rows = [[("ST014", f"{NETBOX}/dcim/sites/?slug=st014"), "Store 014", "high street", "3", "4", "ISP-A 500M",
             "Carrier-B", ("active", "", "fontColor=#059669;"), "ST014.drawio"],
            [("ST027", f"{NETBOX}/dcim/sites/?slug=st027"), "Store 027", "high street", "4", "3", "ISP-A 500M",
             "Carrier-B", ("active · 1 AP offline", "", "fontColor=#B45309;"), "ST027.drawio"],
            [("ST031", f"{NETBOX}/dcim/sites/?slug=st031"), "Store 031", "mall unit", "2", "2", "ISP-A 500M",
             "Carrier-B", ("fit-out · SW-02 planned", "", "fontColor=#B45309;"), "ST031.drawio"]]
    p.cell(tl, "<b>Store register</b>", kit.TEXT + "fontSize=12;", 100, 600, 600, 22)
    p.table(tl, 100, 626, [("SITE", 80), ("NAME", 120), ("FORMAT", 110), ("LANES", 60), ("APS", 50),
                           ("PRIMARY", 120), ("BACKUP", 100), ("STATE", 190), ("DRAWING", 130)], rows, row_h=24)
    p.note(nl, 1100, 600, 540, 150, "What every store has (the standard)", [
        "One firewall that is also the SD-WAN edge, and a 4G router as the second line.",
        "A cabinet switch (SW-01) and a counter switch (SW-02) that carries only the CDE.",
        "The same VLAN IDs and names; 10.nnn.0.0/16 where nnn is the store number.",
        "The same zones: EDGE, STORE, MGMT, CDE, GUEST, IOT.",
        "The same flow register (sheet 7): a store-specific rule is an exception with an owner and an end date."],
        size=11)
    p.note(nl, 1670, 600, 540, 150, "What may differ (and is drawn)", [
        "Number of lanes, APs and cameras.",
        "Mall units: the landlord's CCTV and sometimes the landlord's internet line.",
        "Floors and rooms (the floor plan on sheet 3d).",
        "Fit-outs and remodels: devices planned in NetBox show dashed until they go live."], size=11)
    p.note(guides, 100, 760, 900, 80, "How to extend this sheet", [
        "A new store is a NetBox site plus a build; this sheet is the estate's map, edited when a store opens "
        "or closes.",
        "More than a handful of stores: keep the register, drop the store cards, and group by region."])

    # Head office failover: every store's tunnels, journals and staff logins end here.
    p.cell(hl, "<b>Head office failover</b> — every store's tunnels end at HQ1, so its failures reach every "
               "store", kit.TEXT + "fontSize=12;", 100, 880, 1300, 22)
    isps = [p.box(hl, 100, 930 + k * 120, 240, 56, name_, "HQ1 internet line " + str(k + 1), "cloud", 11)
            for k, name_ in enumerate(("ISP-A fiber 1G", "ISP-C fiber 1G"))]
    p.cell(hl, "<b>HQ1-FW-01 / 02 · firewall pair</b>", "rounded=1;absoluteArcSize=1;arcSize=16;fillColor=none;"
           "strokeColor=#94A3B8;dashed=1;dashPattern=6 4;align=left;verticalAlign=top;spacingLeft=12;spacingTop=6;"
           "fontSize=11;fontColor=#475569;html=1;whiteSpace=wrap;" + FONT, 430, 910, 400, 230)
    fws = [p.box(hl, 450, 950 + k * 100, 260, 56, f"HQ1-FW-0{k + 1}", role, "firewall", 11)
           for k, role in enumerate(("active · carries all traffic", "standby · takes over in seconds"))]
    p.pill(hl, 730, 944, 80, 24, "ACTIVE", "green")
    p.pill(hl, 730, 1044, 80, 24, "STANDBY", "slate")
    for k, dx in enumerate((0.35, 0.65)):
        p.edge(hl, fws[0], fws[1], LINK_EDGE + "strokeColor=#64748B;endArrow=none;"
               f"exitX={dx};exitY=1;exitDx=0;exitDy=0;entryX={dx};entryY=0;entryDx=0;entryDy=0;",
               "HA sync" if k == 0 else "")
    for k, isp in enumerate(isps):
        p.edge(hl, isp, fws[k], CIRCUIT_EDGE + "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;"
               "entryDx=0;entryDy=0;", "")
    hub = p.box(hl, 920, 990, 260, 70, "HQ1 SD-WAN hub", "two tunnels from every store", "router", 11)
    p.edge(hl, fws[0], hub, LINK_EDGE + "strokeColor=#2196F3;endArrow=none;exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
           "entryX=0;entryY=0.5;entryDx=0;entryDy=0;", "")
    for n, (code, *_rest) in enumerate(stores):
        sb = p.box(hl, 1270, 920 + n * 80, 200, 50, code, "", "store", 11)
        for k, style in enumerate((FLOW_OK, FLOW_COND)):
            p.edge(hl, sb, hub, style + f"endArrow=none;exitX=0;exitY={0.35 + k * 0.3};exitDx=0;exitDy=0;"
                   f"entryX=1;entryY={0.3 + n * 0.2 + k * 0.08:.2f};entryDx=0;entryDy=0;", "")
    cx, cw = 1560, 640
    p.cell(hl, "<b style=\"font-size:15px\">HQ1 firewall pair fails over</b>", "rounded=1;absoluteArcSize=1;"
           "arcSize=16;fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;align=left;verticalAlign=top;spacingLeft=56;"
           "spacingTop=14;fontSize=12;fontColor=#0F172A;html=1;" + FONT + kit.icon_style("firewall", 34).replace(
               "imageVerticalAlign=middle;", "imageVerticalAlign=top;"), cx, 880, cw, 250)
    p.table(hl, cx + 16, 936, [("", 130), ("", cw - 162)], [
        [("What happens", "", "fontStyle=1;"), "HQ1-FW-02 takes over; store tunnels re-form to the same hub "
         "address."],
        [("Customer sees", "", "fontStyle=1;"), "Nothing in stores: card data (F01) leaves each store directly; "
         "journals (F04) queue."],
        [("How long", "", "fontStyle=1;"), "Seconds. If both members fail, stores keep trading, but HQ1 apps, "
         "staff Wi-Fi logins and price files wait."],
        [("Test", "", "fontStyle=1;"), "Fail the pair over twice a year, out of hours; every store's tunnels "
         "must come back."]], row_h=44, head_h=0)

    border_w = p
    border_w.title_block(border, "All", "Estate — HQ1 and stores", f"6 of {SHEETS}", DATE, PROJECT)
    return p


# ---------------------------------------------------------------------------- 7 · flow register
def page_register(s: Store) -> Page:
    st = s.store
    W, H = 2500, 1480
    p = Page("register", "7 · Flow register & standards", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    fr = p.layer("Flow register")
    zm = p.layer("Zone matrix")
    sd = p.layer("Standards")
    dc = p.layer("Drawing conventions")
    border = p.layer("Border & title block")
    p.title(fr, "Flow register, zone matrix and store standards", "The rulebase for FW-01 in writing. Every lane "
            "on sheet 4 has one row; a firewall rule with no row here is a finding.", "register-c5")
    card = ("rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;html=1;"
            + FONT)
    rows = []
    for fid, kind, sec, (sz, stext), (dz, dtext), label in FLOWS:
        rows.append([(fid, "", "fontStyle=1;"), {"ok": "permit", "cond": "conditional", "deny": "deny"}[kind],
                     f"{stext} ({sz})", f"{dtext} ({dz})", PORTS_OF[fid], label,
                     {"card": "POS team", "store": "Store IT", "devices": "Facilities", "support": "Network team",
                      "plumbing": "Network team", "denied": "Network team"}[sec],
                     "CDE" if "CDE" in (sz, dz) else "connected" if fid in ("F13", "F21", "F22", "F24") else "out",
                     "2027-01" if kind == "cond" else "2027-04"])
    h = 24 * (len(rows) + 1)
    p.cell(fr, "", card, 40, 86, 1360, h + 60)
    p.cell(fr, "<b>Flow register</b> (one row per lane on sheet 4)", kit.TEXT + "fontSize=12;", 56, 94, 900, 22)
    p.table(fr, 56, 124, [("ID", 50), ("ACTION", 90), ("SOURCE (ZONE)", 210), ("DESTINATION (ZONE)", 210),
                          ("PORTS", 100), ("PURPOSE", 340), ("OWNER", 110), ("PCI", 90), ("REVIEW BY", 100)], rows, row_h=24)

    zones = ["CDE", "STORE", "MGMT", "GUEST", "IOT", "HQ", "OUT"]
    m = {("CDE", "CDE"): "F02 F03", ("CDE", "HQ"): "F04 F16⚠ F26 F27", ("CDE", "OUT"): "F01 F17 ⚠",
         ("HQ", "CDE"): "F05 F28 ⚠", ("STORE", "HQ"): "F06 F23 F25", ("STORE", "OUT"): "F07", ("GUEST", "OUT"): "F08 F19", ("IOT", "IOT"): "F09",
         ("HQ", "IOT"): "F10", ("IOT", "OUT"): "F11 F12 F20", ("HQ", "MGMT"): "F13 ⚠ F24", ("OUT", "HQ"): "F14 ⚠",
         ("MGMT", "HQ"): "F15 F21 F22", ("MGMT", "OUT"): "F18"}
    mrows = []
    for a in zones:
        row = [(a, "", "fontStyle=1;")]
        for b in zones:
            v = m.get((a, b))
            row.append((v, "", "fontColor=#059669;fontStyle=1;") if v else ("✕", "", "fontColor=#DC2626;"))
        mrows.append(row)
    mx = 1440
    mh = 36  # room for two lanes' worth of IDs per cell
    p.cell(zm, "", card, mx, 86, 1020, 24 + mh * 7 + 60)
    p.cell(zm, "<b>Zone matrix</b> (row = from, column = to · ✕ denied · ⚠ conditional)", kit.TEXT + "fontSize=12;",
           mx + 16, 94, 900, 22)
    p.table(zm, mx + 16, 124, [("FROM \\ TO", 110)] + [(z, 126) for z in zones], mrows, row_h=mh)

    zy = 124 + 24 + mh * 7 + 60
    p.cell(sd, "<b>Zones in NetBox</b> (filled on every build)", kit.TEXT + "fontSize=12;", mx + 16, zy, 900, 22)
    p.table(sd, mx + 16, zy + 26, [("ZONE", 230), ("BAND", 70), ("OWNER", 200), ("NOTES", 480)],
            [[f"{c} · {n}", BAND_OF[c], OWNER_OF[c], ""] for z, (c, n, _, _) in ZONES.items()], row_h=24)
    vy = zy + 26 + 24 * 7 + 30
    p.cell(sd, "<b>VLAN and addressing standard</b> (filled on every build)", kit.TEXT + "fontSize=12;", mx + 16,
           vy, 900, 22)
    vrows = []
    for z, (c, n, _, _) in ZONES.items():
        vids = [v for v in VLANS if v[2] == z]
        vrows.append([", ".join(str(v[0]) for v in sorted(vids)), f"{c} · {n}", BAND_OF[c],
                      ", ".join(f"10.{st['net']}.{v[0]}.1" for v in sorted(vids)[:2]),
                      ", ".join(v[1] for v in sorted(vids))])
    p.table(sd, mx + 16, vy + 26, [("VLANS", 110), ("ZONE", 230), ("BAND", 70), ("GATEWAYS", 230),
                                   ("NAMES", 340)], vrows, row_h=24)

    sy = 124 + h + 60
    p.cell(dc, "", card, 40, sy, 1360, 260)
    p.cell(dc, "<b>Store standards</b>", kit.TEXT + "fontSize=12;", 56, sy + 8, 900, 22)
    p.table(dc, 56, sy + 38, [("ITEM", 220), ("STANDARD", 1100)], [
        ["Names", "STORE-ROLE-NN: ST014-POS-01, ST014-SW-02. The store code is the NetBox site facility."],
        ["Zones", "A NetBox tag per zone (zone-cde, zone-store, zone-mgmt, zone-guest, zone-iot, zone-edge) on "
                  "devices and VLANs."],
        ["Cables", "Labeled by the A-side port: ST014-SW01-P05. Same port, same label, every store."],
        ["Changes", "Register row first, then firewall rule, then sheet 4. A rule with no row is removed at the "
                    "next review."],
        ["Review", "Flow register reviewed every six months with the POS team; record the date in the site's "
                   "journal."],
        ["Sharing", "Hide mgmt IPs, circuit IDs and VLAN tables before a drawing leaves the company (Share view)."],
        ["PCI scope", "The PCI column records what the assessor confirmed (compliance_scope in NetBox); "
                      "this sheet never decides it."]], row_h=28)
    p.note(guides, 1456, sy + 120, 900, 90, "How to extend this sheet", [
        "Add the row here before anyone touches the firewall; give it the next free ID and an owner.",
        "The zone tables fill from NetBox on every build: edit zones in NetBox, not here."])
    finish(p, st, border, "Flow register & standards", 7)
    return p


BAND_OF = {"EDGE": "R5", "STORE": "R3", "MGMT": "R3", "CDE": "R2", "GUEST": "R1", "IOT": "R1"}
OWNER_OF = {"EDGE": "Network team", "STORE": "Store IT", "MGMT": "Network team", "CDE": "POS team",
            "GUEST": "Marketing", "IOT": "Facilities"}


# ---------------------------------------------------------------------------- 8 · NetBox
def page_netbox(s: Store) -> Page:
    st = s.store
    W, H = 2300, 960
    p = Page("netbox", "8 · NetBox — data model · import · sync", W, H)
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    ml = p.layer("Mapping")
    fl = p.layer("Workflow")
    border = p.layer("Border & title block")
    p.title(ml, "NetBox is the source, the drawing is the view", "Where each thing on these sheets lives in "
            "NetBox, and the commands that turn a store's NetBox data into its drawing.")
    rows = [
        ["Store", "DCIM ▸ Site", "facility = store code, slug", f"{st['code']} · facility {st['code']} · slug {st['slug']}"],
        ["Room", "DCIM ▸ Location", "name", "Back office, Checkout, Sales floor, Stockroom, Upstairs"],
        ["Cabinet", "DCIM ▸ Rack", "name, height 12U, position on each device", f"{st['code']}-CAB-01 · FW-01 at U10"],
        ["Device", "DCIM ▸ Device", "name, role, type, serial, asset tag, status",
         f"{st['code']}-POS-01 · role pos-terminal"],
        ["Zone", "Extras ▸ Tag on device and VLAN", "slug zone-…, name 'CODE · Name'", "zone-cde · 'CDE · Cardholder "
                                                                                     "data environment'"],
        ["Owner", "Tenancy ▸ Tenant", "on device (optional)", "POS team, Store IT, Facilities"],
        ["VLAN", "IPAM ▸ VLAN (site)", "vid, name, tag", "20 POS · zone-cde"],
        ["Subnet", "IPAM ▸ Prefix", "prefix, VLAN; gateway custom field optional", f"10.{st['net']}.20.0/26"],
        ["Mgmt IP", "IPAM ▸ IP address", "device primary IPv4", f"10.{st['net']}.99.2 on SW-01"],
        ["Cable", "DCIM ▸ Cable", "label, type, both terminations", f"{st['code']}-SW02-P01 · cat6"],
        ["Trunk", "DCIM ▸ Interface", "mode tagged, tagged VLANs, untagged VLAN", "SW-01 1/1/24 · 10,20–22,…"],
        ["Line", "Circuits ▸ Circuit", "cid, provider, description", f"{st['code']}-BB-01 · ISP-A"],
        ["SSID", "Wireless ▸ Wireless LAN", "ssid, auth, cipher, VLAN, group · zone: VLAN tag",
         "STORE-GUEST · VLAN 50 · group R01 estate"],
        ["AP radio", "DCIM ▸ Interface (wireless)", "type, RF role, channel, SSIDs carried",
         f"{st['code']}-AP-01 radio0 · 5 GHz · ch 38"],
        ["Software", "Custom field sw_version", "text, on device", "AOS-CX 10.13"],
        ["End of support", "Custom field end_of_support", "date, on device type", "2033-06-30"],
    ]
    p.cell(ml, "<b>Drawing → NetBox</b>", kit.TEXT + "fontSize=12;", 100, 100, 600, 22)
    p.table(ml, 100, 126, [("ON THE DRAWING", 140), ("NETBOX OBJECT", 230), ("FIELDS", 300), ("EXAMPLE", 420)],
            rows, row_h=26)
    p.note(ml, 100, 126 + 26 * 17 + 20, 1090, 80, "Nothing in NetBox's own schema changes", [
        "Zones are tags, owners are tenants, software and support dates are custom fields: all additive.",
        "'netdiagrams netbox-setup --profile retail' creates the tags, roles and custom fields, and changes "
        "nothing that already exists."], size=11)

    steps = [("Survey the store", "worksheets WS-01 to WS-10 (appendix A)", "clock"),
             ("Set NetBox up once", "netdiagrams netbox-setup --profile retail", "wrench"),
             ("Import the store", "CSV imports from the worksheets (appendix F)", "store"),
             ("Build the drawing", f"netdiagrams build --profile retail --site {st['slug']}", "shield"),
             ("Read the drift report", "what changed, what is missing, sheet 1c", "card")]
    prev = None
    for n, (title, sub, icon) in enumerate(steps):
        y = 126 + n * 110
        c = p.box(fl, 1320, y, 560, 70, f"{n + 1}. {title}", sub, icon, 12)
        if prev:
            p.edge(fl, prev, c, FLOW_OK.replace("strokeColor=#059669;", "strokeColor=#64748B;"), "")
        prev = c
    p.note(fl, 1320, 126 + 5 * 110, 560, 96, "Every store, every night", [
        "One NetBox, one template: run the build for each store site (--site st027, st031 …).",
        "Same data, same drawing: the revision in the title block is a fingerprint of the NetBox data.",
        "A store that changed shows it in the drift report and on its sheets."], size=11)
    p.note(guides, 100, 700, 900, 60, "How to extend this sheet", [
        "Add a row when the standard starts using a new NetBox field; the engine reads only what is listed."])
    finish(p, st, border, "NetBox mapping", 8)
    return p



# ---------------------------------------------------------------------------- stencils
# The retail shape library: one card per store role, as drawn on the R01 sheets.
STENCIL_SHAPES = [  # role, title (from the profile), zone tag, location
    ("firewall", RETAIL.role_shapes["firewall"], "zone-edge", "Back office"),
    ("lte-router", RETAIL.role_shapes["lte-router"], "zone-edge", "Back office"),
    ("access-switch", RETAIL.role_shapes["access-switch"], "zone-mgmt", "Back office"),
    ("access-point", RETAIL.role_shapes["access-point"], "zone-mgmt", "Sales floor"),
    ("pos-terminal", RETAIL.role_shapes["pos-terminal"], "zone-cde", "Checkout"),
    ("pin-pad", RETAIL.role_shapes["pin-pad"], "zone-cde", "Checkout"),
    ("pos-server", RETAIL.role_shapes["pos-server"], "zone-cde", "Back office"),
    ("workstation", RETAIL.role_shapes["workstation"], "zone-store", "Back office"),
    ("printer", RETAIL.role_shapes["printer"], "zone-store", "Back office"),
    ("nvr", RETAIL.role_shapes["nvr"], "zone-iot", "Back office"),
    ("camera", RETAIL.role_shapes["camera"], "zone-iot", "Sales floor"),
    ("signage", RETAIL.role_shapes["signage"], "zone-iot", "Sales floor"),
    ("building-controller", RETAIL.role_shapes["building-controller"], "zone-iot", "Stockroom"),
    ("sensor", RETAIL.role_shapes["sensor"], "zone-iot", "Sales floor"),
]
ROLE_SHAPES = {role: title for role, title, _, _ in STENCIL_SHAPES}


def _compress(xml: str) -> str:
    """draw.io's library encoding: raw deflate of the URI-encoded XML, base64."""
    import base64
    import urllib.parse
    import zlib
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = c.compress(urllib.parse.quote(xml, safe="~()*!.'").encode()) + c.flush()
    return base64.b64encode(raw).decode()


def build_stencils() -> str:
    entries = []
    for role, title, zone, location in STENCIL_SHAPES:
        attrs = {"name": "ST###-ROLE-NN", "role": role, "manufacturer": "", "device_type": "‹model›",
                 "platform": "", "serial": "", "asset_tag": "", "status": "planned", "site": "ST###",
                 "location": location, "rack": "", "position": "", "face": "", "primary_ip4": "‹a.b.c.d/nn›",
                 "virtual_chassis": "", "vc_position": "", "description": "", "tags": zone,
                 "link": f"{NETBOX}/dcim/devices/?name=ST%23%23%23-ROLE-NN", "linkTarget": "_blank",
                 "placeholders": "1",
                 "tooltip": "Edit Data (Ctrl+M) = NetBox device fields: name, role, device_type, location, "
                            "serial, primary_ip4, tags (zone-…)"}
        root = ET.Element("root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", value="Layer 1", style="", parent="0")
        obj = ET.SubElement(root, "object", {"id": "lib-c1", "label": '<b>%name%</b><br><span style="font-size:9px;'
                                             'color:#64748B">%device_type%</span>', **attrs})
        cell = ET.SubElement(obj, "mxCell", style=kit.CARD + kit.icon_style(ICON.get(role, role)), vertex="1",
                             parent="1")
        ET.SubElement(cell, "mxGeometry", x="0", y="0", width="200", height="56", **{"as": "geometry"})
        pill = ET.SubElement(root, "object", {"id": "lib-c2", "label": "%location%", "placeholders": "1"})
        cell = ET.SubElement(pill, "mxCell", style="rounded=1;absoluteArcSize=1;arcSize=8;fillColor=#EEF2F7;"
                             "strokeColor=none;fontSize=7.5;fontColor=#475569;html=1;spacing=0;" + FONT,
                             vertex="1", parent="lib-c1")
        ET.SubElement(cell, "mxGeometry", x="130", y="6", width="64", height="13", **{"as": "geometry"})
        model = ET.Element("mxGraphModel")
        model.append(root)
        entries.append({"xml": _compress(ET.tostring(model, encoding="unicode")), "w": 200, "h": 56,
                        "aspect": "fixed", "title": title})
    return "<mxlibrary>" + json.dumps(entries, ensure_ascii=False) + "</mxlibrary>\n"


def build_template(store: dict = STORE) -> ET.Element:
    s = Store(store)
    pages = [page_overview(), page_logical(s), page_physical(s), page_hardware(s), page_wireless(s),
             page_flows(s), page_failover(s), page_multisite(), page_register(s), page_netbox(s)]
    return kit.mxfile(pages, "netdiagrams make_retail.py")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--estate", help="Also write the ST027 and ST031 exports to this folder.")
    ap.add_argument("--template-out", default=str(TEMPLATE))
    args = ap.parse_args(argv)
    tree = build_template()
    ET.indent(tree, space="  ")
    Path(args.template_out).write_text(ET.tostring(tree, encoding="unicode"), "utf-8")
    SAMPLE.write_text(json.dumps(export(STORE), indent=1) + "\n", "utf-8")
    STENCILS.write_text(build_stencils(), "utf-8")
    print(f"Wrote {args.template_out} and {SAMPLE}")
    if args.estate:
        folder = Path(args.estate)
        folder.mkdir(parents=True, exist_ok=True)
        for st in (ST027, ST031):
            out = folder / f"{st['slug']}-netbox.json"
            out.write_text(json.dumps(export(st), indent=1) + "\n", "utf-8")
            print(f"Wrote {out}")


if __name__ == "__main__":
    main()
