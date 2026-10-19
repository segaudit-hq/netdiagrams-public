"""Regenerate src/netdiagrams/data/sample-bank.json, the Ninebark Community Bank export (B01 main office).

The export is in NetBox REST API shape and comes from the same facts as the
bank template (scripts/bank_template/site.py), so
`netdiagrams build --input sample-bank.json` fills every bank sheet. The
site carries {"profile": "bank"} in its netdiagrams field, the way a real
NetBox would pick the bank standard. A fork of make_office_sample.py.

    python scripts/make_bank_sample.py              # B01, into the package
    python scripts/make_bank_sample.py --site b02 -o tests/fixtures/bank-b02.json
    python scripts/make_bank_sample.py --site starter -o bank-starter.json   # day one, with gaps
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bank_template import site as S  # noqa: E402
from sample_kit import model_lifecycle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from netdiagrams.banking import ZONE_NAMES  # noqa: E402
from netdiagrams.audit import FIELD_NAMES as AUDIT_FIELDS  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"
EXPORTED = "2026-10-15T08:00:00Z"
ROLE_NAMES = {"ups": "UPS", "nvr": "NVR", "access-point": "Access point", "atm": "ATM"}
WLAN_AUTH = {"NB-STAFF": ("wpa-enterprise", "WPA Enterprise", "aes", "AES"),
             "NB-GUEST": ("open", "Open", "", "")}
# The wlan_* custom fields netbox-setup adds: what NetBox's own auth type can't say. Never a PSK.
WLAN_FIELDS = {
    "NB-STAFF": {"wlan_security": "wpa3-enterprise", "wlan_eap": "EAP-TLS", "wlan_switching": "local",
                 "wlan_bands": ["5ghz", "6ghz"]},
    "NB-GUEST": {"wlan_security": "open-portal", "wlan_switching": "local", "wlan_bands": ["2.4ghz", "5ghz"],
                 "wlan_client_isolation": True, "wlan_portal": "captive"},
}
# Every bank AP is tri-band; each radio broadcasts the SSIDs set to its band.
RADIOS = (("radio0", "2.4ghz", "2.4g-6-2437-22", "6 (2437/22)"), ("radio1", "5ghz", "5g-42-5210-80", "42 (5210/80)"),
          ("radio2", "6ghz", "6g-15-6025-160", "15 (6025/160)"))  # NetBox's channel choice values
# Both sites' APs are run from the same cloud dashboard: no controller on site.
WIRELESS = {"wireless_management": "cloud", "wireless_manager": "Cloud Wi-Fi dashboard"}
# What NetBox holds inside the boxes: the field-replaceable parts 'show inventory' lists. Optics sit in
# every fibre port (bound to the interface), the core switches carry two PSUs and two fan trays each;
# the access switches, firewalls and servers have fixed power and no module bays.
OPTIC = {"mmf": "J9150D"}  # Aruba 10G SFP+ LC SR
CHASSIS_PARTS = {"core-switch": (("psu", "Power supply", "JL086A", 2), ("fan", "Fan", "JL669A", 2))}
ITEM_ROLES = {"transceiver": "Transceiver", "psu": "Power supply", "fan": "Fan"}
# Audit evidence (the fields netbox-setup adds, and NetBox contacts as owners and custodians). The information
# security officer (ISO) owns the network and the MSP runs it and backs it up nightly; the head of operations
# owns the teller, wire, card and ATM gear; the security officer owns the alarm, cameras and doors, which the
# alarm company services. Customer information (GLBA) lives in the teller, staff, wire and server subnets; card
# data in the card room's VLAN 26 and the ATM VLAN 60. A few honest findings: the alarm panel and the NVR are unpatched, the
# console server's backup is stale, the NVR keeps its logs to itself, and the core processor's router has no
# patch date at all, because the provider owns it and tells the bank nothing.
ROOM_FACTS = {  # location -> (physical access, data classification, last verified)
    "COMMS-1": ("badge-camera", "confidential", "2026-09-12"), "IDF-2": ("locked-room", "internal", "2026-09-12"),
    "Wire room": ("badge-camera", "confidential", "2026-09-12"),
    "Card room": ("badge-camera", "restricted", "2026-09-12"), "Vault": ("badge-camera", "restricted", "2026-09-12"),
    "CAB-1": ("locked-cabinet", "confidential", "2026-08-20")}
ROOM_ACCESS = "badge"   # every other room: staff areas are behind badge doors
# Rooms on each floor, for the NetBox location tree (a location not listed here is a top-level one).
PARENT = {"COMMS-1": "Floor 1", "Teller line": "Floor 1", "Drive-up": "Floor 1", "Lobby": "Floor 1",
          "Vault": "Floor 1", "IDF-2": "Floor 2", "Wire room": "Floor 2", "Card room": "Floor 2",
          "CAB-1": "Ground floor"}
GLBA = {"compliance_scope": ["glba"], "data_classification": "confidential"}
PCI = {"compliance_scope": ["pci-cde"], "data_classification": "restricted"}   # the card room and the ATMs
PREFIX_FACTS = {10: GLBA, 20: GLBA, 21: GLBA, 25: GLBA, 40: GLBA, 45: GLBA,
                26: PCI, 60: PCI,
                70: {"data_classification": "public"}}
SECURITY_ROLES = ("camera", "nvr", "door-controller", "alarm-panel")
OPERATIONS_ROLES = ("atm", "cash-recycler", "wire-workstation", "card-printer")
PATCHED = {"firewall": "2026-09-24", "core-switch": "2026-08-19", "access-switch": "2026-08-19",
           "console-server": "2026-09-15", "hypervisor": "2026-10-08", "storage": "2026-09-02", "ups": "2026-08-20",
           "nvr": "2026-05-12", "camera": "2026-08-12", "door-controller": "2026-08-12", "alarm-panel": "2025-12-03",
           "printer": "2026-09-30", "atm": "2026-09-10", "cash-recycler": "2026-08-27",
           "wire-workstation": "2026-10-13", "card-printer": "2026-09-22", "router": "2026-09-24"}
BACKED_UP = {"console-server": "2026-06-30", "ups": "2026-10-01", "nvr": "2026-09-30", "camera": "2026-09-30",
             "door-controller": "2026-09-30", "alarm-panel": "2026-10-02", "printer": "2026-10-01",
             "atm": "2026-10-01", "cash-recycler": "2026-10-01", "wire-workstation": "2026-10-13",
             "card-printer": "2026-10-01"}
INSTALLED = {"firewall": "2024-06-10", "core-switch": "2024-06-10", "access-switch": "2024-06-10",
             "console-server": "2024-06-10", "hypervisor": "2023-11-06", "storage": "2023-11-06", "ups": "2022-03-14",
             "access-point": "2024-06-24", "nvr": "2021-09-20", "camera": "2021-09-20", "door-controller": "2021-09-20",
             "alarm-panel": "2019-05-06", "printer": "2025-01-20", "atm": "2022-11-07", "cash-recycler": "2023-04-17",
             "wire-workstation": "2025-02-03", "card-printer": "2024-01-15", "provider-router": "2023-08-01",
             "router": "2024-06-10"}
CONTRACT_END = {"FortiCare 24x7": "2027-06-30", "Foundation Care NBD": "2027-06-30", "ProSupport NBD": "2027-11-30"}
# Each model's end of sale and end of support, kept once on its device type. Endpoint models carry none,
# except the bank's own kit, whose end of support the vendors publish.
LIFECYCLE = {"FortiGate 120G": ("2030-03-31", "2035-03-31"), "CX 6300M 24SFP+": ("2029-10-31", "2034-10-31"),
             "CX 6200F 48G Class4 PoE": ("2029-10-31", "2034-10-31"), "AP-635": ("2030-06-30", "2035-06-30"),
             "OM1204-4E-L": ("2028-12-31", "2031-12-31"), "PowerEdge R660xs": ("2029-05-31", "2033-05-31"),
             "RS2423RP+": ("2028-06-30", "2031-06-30"), "Smart-UPS SRT 3000": ("2028-12-31", "2031-12-31"),
             "FortiGate 60F": ("2027-09-30", "2032-09-30"), "FortiExtender 211F": ("2028-06-30", "2033-06-30"),
             "CX 6100 24G Class4 PoE": ("2029-10-31", "2034-10-31"), "AP-615": ("2030-06-30", "2035-06-30"),
             "S3016": ("2029-12-31", "2034-12-31"), "S3008": ("2028-12-31", "2033-12-31"),
             "ISR 1111-4P": ("2026-11-30", "2031-11-30"), "SelfServ 84": ("2029-12-31", "2034-12-31"),
             "SelfServ 82": ("2027-12-31", "2032-12-31"), "RBG-200": ("2028-03-31", "2033-03-31"),
             "B6512": ("2027-06-30", "2030-06-30"), "Sigma DS3": ("2029-06-30", "2032-06-30")}
IFACE_TYPE = {"DAC": "10gbase-x-sfpp", "MMF OM4": "10gbase-x-sfpp", "Cat6A": "10gbase-t", "Cat6": "1000base-t"}


def ref(value: str, key: str = "name", **extra) -> dict | None:
    return {key: value, "slug": value.lower().replace(" ", "-").replace("&", "and"), **extra} if value else None


def tag(slug: str) -> dict:
    return {"name": ZONE_NAMES.get(slug, slug), "slug": slug}


class Export:
    def __init__(self, site: dict, n_site: int, ap_vlans: tuple = S.AP_VLANS, access: dict = S.ACCESS_VLAN):
        self.site = {"id": n_site, "name": site["name"], "slug": site["slug"], "facility": site["code"],
                     "custom_fields": {"netdiagrams": {"profile": "bank"}, **WIRELESS}}
        self.devices: dict[str, dict] = {}
        self.locations: dict[str, dict] = {}
        self.chassis: dict[str, dict] = {}
        self.interfaces: dict[tuple, dict] = {}
        self.cables, self.vlans, self.prefixes, self.ips = [], [], [], []
        self.ap_vlans = ap_vlans  # what an AP trunks, native 99: only VLANs this site has
        self.access = access      # each end device role's access VLAN at this site

    def location(self, name: str) -> dict:
        if name not in self.locations:
            parent = self.location(PARENT[name]) if name in PARENT else None
            loc = {"id": len(self.locations) + 1, "name": name, "slug": name.lower().replace(" ", "-"),
                   "parent": {"id": parent["id"], "name": parent["name"]} if parent else None}
            self.locations[name] = loc
        return self.locations[name]

    def device(self, d: dict) -> None:
        loc = self.location(d["location"]) if d["location"] else None
        vc = None
        if d["virtual_chassis"]:
            vc = self.chassis.setdefault(d["virtual_chassis"], {"id": len(self.chassis) + 1,
                                                                "name": d["virtual_chassis"]})
        self.devices[d["name"]] = {
            "id": len(self.devices) + 1, "name": d["name"],
            "role": {"name": ROLE_NAMES.get(d["role"], d["role"].replace("-", " ").capitalize()), "slug": d["role"]},
            "device_type": {"model": d["device_type"], "manufacturer": ref(d["manufacturer"])},
            "platform": ref(d["platform"]), "serial": d["serial"], "asset_tag": d["asset_tag"] or None,
            "status": {"value": d["status"]}, "site": {"id": self.site["id"], "name": self.site["name"],
                                                       "slug": self.site["slug"]},
            "location": {"id": loc["id"], "name": loc["name"], "slug": loc["slug"]} if loc else None,
            "rack": ref(d["rack"]), "position": float(d["position"]) if d["position"] else None,
            "face": {"value": "front"} if d["position"] else None,
            "primary_ip4": {"address": d["primary_ip4"]} if d["primary_ip4"] else None,
            "virtual_chassis": {"id": vc["id"], "name": vc["name"]} if vc else None,
            "vc_position": int(d["vc_position"]) if d["vc_position"] else None,
            "description": d["description"], "tags": [tag(d["tags"])],
            "custom_fields": {k[3:]: v for k, v in d.items() if k.startswith("cf_") and v},
        }

    def iface(self, end: str, media: str, lag: str = "", mode: str = "", untagged=None, tagged=(),
              kind: str = "") -> dict:
        dev, name = end.split(":", 1)
        key = (dev, name)
        if key not in self.interfaces:
            d = self.devices[dev]
            self.interfaces[key] = {
                "id": len(self.interfaces) + 1, "device": {"id": d["id"], "name": dev}, "name": name,
                "type": {"value": kind or IFACE_TYPE.get(media, "1000base-t")}, "enabled": True,
                "lag": {"name": lag} if lag else None, "mode": {"value": mode} if mode else None,
                "untagged_vlan": {"vid": untagged} if untagged else None,
                "tagged_vlans": [{"vid": v} for v in tagged], "description": "", "vrf": None}
        return self.interfaces[key]

    def cable(self, c: dict) -> None:
        vids = [int(v) for v in c["vlans"].replace(" ", "").split(",") if v]
        po = c["lag"] if c["lag"].startswith("Po") else ""
        for n, label in enumerate(c["labels"]):
            ends = []
            for side in ("a", "b"):
                end = c[side][n]
                dev, port = end.split(":", 1)
                role = self.devices[dev]["role"]["slug"]
                access = self.access.get(role) if side == "b" else None
                if role == "access-point" and side == "b":  # the AP's 2.5G port, on a 1G switch port
                    iface = self.iface(end, c["media"], mode="tagged", untagged=99, tagged=self.ap_vlans,
                                       kind="2.5gbase-t")
                    iface.update(poe_mode={"value": "pd", "label": "PD"},
                                 poe_type={"value": "type2-ieee802.3at", "label": "802.3at (Type 2)"})
                elif side == "a" and self.devices[c["b"][n].split(":")[0]]["role"]["slug"] == "access-point":
                    iface = self.iface(end, c["media"], mode="tagged", untagged=99, tagged=self.ap_vlans,
                                       kind="1000base-t")
                elif vids:
                    iface = self.iface(end, c["media"], lag=po, mode="tagged", tagged=vids)
                elif not po and side == "a":
                    b_role = self.devices[c["b"][n].split(":")[0]]["role"]["slug"]
                    vid = self.access.get(b_role)
                    iface = self.iface(end, c["media"], mode="access" if vid else "", untagged=vid)
                else:
                    iface = self.iface(end, c["media"], mode="access" if access else "", untagged=access)
                ends.append([{"object_type": "dcim.interface",
                              "object": {"id": iface["id"], "name": port,
                                         "device": {"id": self.devices[dev]["id"], "name": dev}}}])
            self.cables.append({"id": len(self.cables) + 1, "label": label, "type": c["type"],
                                "status": {"value": "connected"}, "color": c["color"], "length": None,
                                "length_unit": None, "a_terminations": ends[0], "b_terminations": ends[1]})

    def vlan(self, vid: int, name: str, zone: str, subnet: str, gateway: str = "") -> None:
        vlan_id = len(self.vlans) + 1
        self.vlans.append({"id": vlan_id, "vid": vid, "name": name, "role": None, "status": {"value": "active"},
                           "site": {"id": self.site["id"], "slug": self.site["slug"]},
                           "tags": [tag(zone)]})
        prefix = {"id": len(self.prefixes) + 1, "prefix": subnet, "vlan": {"id": vlan_id, "vid": vid},
                  "vrf": None, "tags": [tag(zone)], "status": {"value": "active"}}
        if gateway:
            prefix["custom_fields"] = {"gateway": gateway}
        self.prefixes.append(prefix)

    def wlans(self, ssids) -> list:
        """The site's wireless LANs, scoped to the site and tagged with their VLAN's zone."""
        by_vid = {v["vid"]: v for v in self.vlans}
        out = []
        for n, (ssid, _, vid, zone, desc) in enumerate(ssids):
            a = WLAN_AUTH[ssid]
            out.append({"id": n + 1, "ssid": ssid, "description": desc, "status": {"value": "active"},
                        "vlan": {"id": by_vid[vid]["id"], "vid": vid, "name": by_vid[vid]["name"]},
                        "scope_type": "dcim.site", "scope_id": self.site["id"],
                        "scope": {"id": self.site["id"], "name": self.site["name"], "slug": self.site["slug"]},
                        "tags": [tag(zone)], "custom_fields": dict(WLAN_FIELDS[ssid]),
                        "auth_type": {"value": a[0], "label": a[1]},
                        "auth_cipher": {"value": a[2], "label": a[3]} if a[2] else None})
        # Each AP's radios, with the SSIDs set to that band (interface Wireless LANs in NetBox).
        for name, d in self.devices.items():
            if d["role"]["slug"] != "access-point":
                continue
            for radio, band, channel, label in RADIOS:
                lans = [{"id": w["id"], "ssid": w["ssid"]} for w in out
                        if band in w["custom_fields"]["wlan_bands"]]
                i = self.iface(f"{name}:{radio}", "", kind="ieee802.11ax")
                i.update(rf_role={"value": "ap", "label": "Access point"},
                         rf_channel={"value": channel, "label": label}, wireless_lans=lans)
        return out

    def hardware(self) -> list:
        """Inventory items: an optic in each fibre cable end, then each chassis's PSUs and fan trays."""
        items = []

        def item(dev: str, role: str, part: str, component: dict | None = None) -> None:
            d = self.devices[dev]
            items.append({"id": len(items) + 1, "device": {"id": d["id"], "name": dev}, "name": part, "label": "",
                          "role": {"name": ITEM_ROLES[role], "slug": role}, "manufacturer": ref(S.ARUBA),
                          "part_id": part, "serial": f"{d['serial'][:2] or 'CN'}xxxxx{51 + len(items)}",
                          "asset_tag": None, "discovered": False, "description": "",
                          "component_type": "dcim.interface" if component else None, "component": component})

        for c in self.cables:
            part = OPTIC.get(c["type"][:3])
            for t in (c["a_terminations"] + c["b_terminations"]) if part else ():
                o = t["object"]
                item(o["device"]["name"], "transceiver", part, {"id": o["id"], "name": o["name"]})
        for name, d in self.devices.items():
            for role, _, part, count in CHASSIS_PARTS.get(d["role"]["slug"], ()):
                for _ in range(count):
                    item(name, role, part)
        return items

    def evidence(self, owner: str, custodian: str, verified: str) -> list:
        """The audit fields on rooms, subnets, devices and the site; returns the contact assignments."""
        people, contacts = {}, []

        def assign(kind: str, ident: int, person: str, role: str) -> None:
            people.setdefault(person, len(people) + 1 + 10 * (self.site["id"] - 1))
            contacts.append({"id": len(contacts) + 1, "object_type": kind, "object_id": ident,
                             "contact": {"id": people[person], "name": person},
                             "role": {"slug": role, "name": role.replace("-", " ").capitalize()},
                             "priority": {"value": "primary"}})

        assign("dcim.site", self.site["id"], owner, "asset-owner")
        assign("dcim.site", self.site["id"], custodian, "custodian")
        for name, loc in self.locations.items():
            access, data_class, seen = ROOM_FACTS.get(name, (ROOM_ACCESS, None, None))
            loc["custom_fields"] = {k: v for k, v in (("physical_access", access), ("data_classification", data_class),
                                                      ("last_verified", seen)) if v}
        by_vid = {v["id"]: v["vid"] for v in self.vlans}
        for p in self.prefixes:
            p.setdefault("custom_fields", {}).update(PREFIX_FACTS.get(by_vid.get((p.get("vlan") or {}).get("id")), {}))
        for d in self.devices.values():
            role, cf = d["role"]["slug"], d["custom_fields"]
            if role in SECURITY_ROLES:   # the alarm company's kit: the security officer owns it, and it logs locally
                assign("dcim.device", d["id"], "Security officer", "asset-owner")
                assign("dcim.device", d["id"], "Alarm company", "custodian")
                cf.update(monitoring="polling", log_forwarding="local")
            elif role in OPERATIONS_ROLES:
                assign("dcim.device", d["id"], "Head of operations", "asset-owner")
            elif role == "provider-router":   # their box in our rack: we own the risk, they run it
                assign("dcim.device", d["id"], "Head of operations", "asset-owner")
                assign("dcim.device", d["id"], "Core processor", "custodian")
            if role not in ("access-point", "provider-router"):   # the MSP's nightly backup; APs follow the cloud
                cf["last_config_backup"] = BACKED_UP.get(role, "2026-10-14")
            if role in PATCHED:
                cf["last_patched"] = PATCHED[role]
            if role in INSTALLED:
                cf["install_date"] = INSTALLED[role]
            if cf.get("support_contract") in CONTRACT_END:
                cf["support_contract_end"] = CONTRACT_END[cf["support_contract"]]
        self.site["custom_fields"].update(monitoring="alerting", monitored_by="MSP monitoring (RMM)",
                                          log_forwarding="siem", log_destination="MSSP SIEM, syslog over TLS",
                                          log_retention_days=365, last_verified=verified)
        return contacts

    def device_types(self) -> list:
        return model_lifecycle(self.devices.values(), LIFECYCLE)

    def data(self, circuits: list, wlans: list, contacts: list = ()) -> dict:
        return {"format": "netdiagrams-export/1", "netbox_version": "sample", "netbox_url": "",
                "exported_at": EXPORTED, "site": self.site, "locations": list(self.locations.values()),
                "devices": list(self.devices.values()), "device_types": self.device_types(), "virtual_chassis": list(self.chassis.values()),
                "cables": self.cables, "modules": [], "module_bays": [], "inventory_items": self.hardware(),
                "vlans": self.vlans, "prefixes": self.prefixes, "circuits": circuits,
                "interfaces": list(self.interfaces.values()), "wireless_links": [], "wireless_lans": wlans,
                "ip_addresses": self.ips, "contact_assignments": list(contacts)}


def hq() -> dict:
    e = Export(S.SITE, 1)
    for d in S.DEVICES:
        e.device(d)
    for c in S.CABLES:
        e.cable(c)
    for vid, name, zone, subnet, gw in S.VLANS:
        e.vlan(vid, name, zone, subnet, gw)
    rate = {"1G": 1_000_000, "500/50M": 500_000, "100M": 100_000}
    circuits = [{"id": n + 1, "cid": c["cid"], "provider": {"name": c["provider"]}, "type": {"name": c["type"]},
                 "commit_rate": rate[c["speed"]], "status": {"value": "active"},
                 "description": c["label"]} for n, c in enumerate(S.CIRCUITS)]
    wlans = e.wlans(S.SSIDS)
    return e.data(circuits, wlans, e.evidence("Information security officer", "MSP service desk", "2026-09-12"))


def branch() -> dict:
    # B02 has no VLAN 81: its alarm panel shares the SECURITY VLAN 80 with the NVR.
    e = Export(S.BRANCH, 2, ap_vlans=(20, 70), access={**S.ACCESS_VLAN, "alarm-panel": 80})
    for d in S.BRANCH_DEVICES:
        e.device(d)
    trunk = ", ".join(str(v[0]) for v in S.BRANCH_VLANS)
    drop = lambda n, port, dev, vlans="": {
        "labels": [f"B02-CBL-{n:05d}"], "a": [f"B02-ACC-1:1/1/{port}"], "b": [f"{dev}:eth0"],
        "type": "cat6a" if vlans else "cat6", "color": "2196f3", "speed": "1G", "media": "Cat6A" if vlans else "Cat6",
        "vlans": vlans, "lag": ""}
    cables = [
        {"labels": ["B02-CBL-00001"], "a": ["B02-FW-01:internal1"], "b": ["B02-ACC-1:1/1/24"], "type": "cat6",
         "color": "2196f3", "speed": "1G", "media": "Cat6", "vlans": trunk, "lag": ""},
        {"labels": ["B02-CBL-00002"], "a": ["B02-FW-01:wan2"], "b": ["B02-LTE-01:lan"], "type": "cat6",
         "color": "9e9e9e", "speed": "1G", "media": "Cat6", "vlans": "", "lag": ""},
        drop(11, 1, "B02-AP-01", "20, 70, 99"), drop(12, 2, "B02-AP-02", "20, 70, 99"),
        drop(13, 3, "B02-ATM-01"), drop(14, 4, "B02-TCR-01"), drop(15, 5, "B02-ALARM-01"), drop(16, 6, "B02-NVR-01"),
    ]
    for c in cables:
        e.cable(c)
    for vid, name, zone, subnet in S.BRANCH_VLANS:
        e.vlan(vid, name, zone, subnet, "FW-01 .1")
    circuits = [{"id": 1, "cid": "B02-ISP-C-01", "provider": {"name": "Provider C"},
                 "type": {"name": "Business broadband"}, "commit_rate": 300_000, "status": {"value": "active"},
                 "description": "Broadband 300/30 · LTE backup on B02-LTE-01"}]
    wlans = e.wlans(S.BRANCH_SSIDS)
    return e.data(circuits, wlans, e.evidence("Information security officer", "MSP service desk", "2026-08-20"))


def starter() -> dict:
    """Ninebark's main office on its first day in NetBox: the gaps a real import has.

    Half the serials and the printers' and UPSes' IPs are missing, nothing in IDF-2
    has a rack position, the cameras have no zone tag, the floor 2 uplink cables
    have no label, and VLAN 81 (the alarm panel and door controller) has no prefix. The wireless LANs
    went in before netbox-setup's wireless fields: no switching, bands, isolation or
    portal on any SSID, and nothing yet says the APs are run from the cloud. No device has
    an asset criticality yet either: that field comes with netbox-setup too. Nobody has
    entered the optics yet, and the PSUs and fans in a box with no serial have none either.
    No owners or audit evidence are recorded yet, so the build draws no sheet 3f, and no
    model has its end-of-support date.
    """
    data = hq()
    for n, d in enumerate(data["devices"]):
        if n % 2:
            d["serial"] = ""
        if d["role"]["slug"] in ("printer", "ups"):
            d["primary_ip4"] = None
        if (d.get("location") or {}).get("name", "").startswith("IDF-2"):
            d["position"] = d["face"] = None
        if d["role"]["slug"] == "camera":
            d["tags"] = []
    uplink = set(next(c for c in S.CABLES if c["lag"] == "Po12")["labels"])
    for c in data["cables"]:
        if c["label"] in uplink:
            c["label"] = ""
    vlan81 = next(v["id"] for v in data["vlans"] if v["vid"] == 81)
    data["prefixes"] = [p for p in data["prefixes"] if (p.get("vlan") or {}).get("id") != vlan81]
    for key in WIRELESS:
        data["site"]["custom_fields"].pop(key, None)
    for w in data["wireless_lans"]:
        w["custom_fields"] = {}
    for d in data["devices"]:
        d["custom_fields"].pop("ap_mode", None)
        d["custom_fields"].pop("criticality", None)
    # The optics were never entered, and the parts in a box with no serial have none either.
    no_serial = {d["name"] for d in data["devices"] if not d["serial"]}
    data["inventory_items"] = [i for i in data["inventory_items"] if i["role"]["slug"] != "transceiver"]
    # Nobody has looked up the models' end-of-life notices yet.
    for t in data["device_types"]:
        t["custom_fields"] = {"end_of_sale": None, "end_of_support": None}
    for i in data["inventory_items"]:
        if i["device"]["name"] in no_serial:
            i["serial"] = ""
    # The audit evidence fields and the owner contacts come with netbox-setup too: none of it yet.
    evidence = set(AUDIT_FIELDS) - {"support_contract"}
    for obj in [data["site"], *data["locations"], *data["prefixes"], *data["devices"]]:
        for key in evidence & set(obj.get("custom_fields") or {}):
            del obj["custom_fields"][key]
    data["contact_assignments"] = []
    data["exported_at"] = "2026-10-01T08:00:00Z"
    return data


SITES = {"b01": hq, "b02": branch, "starter": starter}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", choices=SITES, default="b01")
    ap.add_argument("-o", "--output")
    args = ap.parse_args()
    data = SITES[args.site]()
    if args.site != "b01" and not args.output:
        ap.error("--output is needed for a site other than b01")
    out = Path(args.output) if args.output else DATA / "sample-bank.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {out}: {len(data['devices'])} devices, {len(data['cables'])} cables, "
          f"{len(data['interfaces'])} interfaces, {len(data['vlans'])} VLANs")


if __name__ == "__main__":
    main()
