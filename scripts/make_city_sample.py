"""Regenerate src/netdiagrams/data/sample-municipal.json, the Halvern Civic Center export.

The export is in NetBox REST API shape and comes from the same facts as the
municipal template (scripts/city_template/site.py), so
`netdiagrams build --input sample-municipal.json` fills every municipal sheet.
The site carries {"profile": "municipal"} in its netdiagrams field, the way a
real NetBox would pick the local government standard.

    python scripts/make_city_sample.py              # CH1, into the package
    python scripts/make_city_sample.py --site lb1 -o tests/fixtures/municipal-lb1.json
    python scripts/make_city_sample.py --site starter -o municipal-starter.json   # day one, with gaps
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from city_template import site as S  # noqa: E402
from sample_kit import model_lifecycle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from netdiagrams.municipal import ZONE_NAMES  # noqa: E402
from netdiagrams.audit import FIELD_NAMES as AUDIT_FIELDS  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"
EXPORTED = "2026-10-18T08:00:00Z"
ROLE_NAMES = {"ups": "UPS", "nvr": "NVR", "access-point": "Access point", "hvac-controller": "HVAC controller",
              "payment-terminal": "Payment terminal", "signal-system": "Signal system", "public-pc": "Public PC"}
WLAN_AUTH = {"HALVERN-STAFF": ("wpa-enterprise", "WPA Enterprise", "aes", "AES"),
             "HALVERN-PUBLIC": ("open", "Open", "", ""),
             "HALVERN-LIBRARY": ("open", "Open", "", ""),
             "PD-SECURE": ("wpa-enterprise", "WPA Enterprise", "aes", "AES")}
# The wlan_* custom fields netbox-setup adds: what NetBox's own auth type can't say. Never a PSK.
WLAN_FIELDS = {
    "HALVERN-STAFF": {"wlan_security": "wpa3-enterprise", "wlan_eap": "EAP-TLS", "wlan_switching": "local",
                      "wlan_bands": ["5ghz"]},
    "HALVERN-PUBLIC": {"wlan_security": "open-portal", "wlan_switching": "local", "wlan_bands": ["2.4ghz", "5ghz"],
                       "wlan_client_isolation": True, "wlan_portal": "captive"},
    "HALVERN-LIBRARY": {"wlan_security": "open-portal", "wlan_switching": "local", "wlan_bands": ["2.4ghz", "5ghz"],
                        "wlan_client_isolation": True, "wlan_portal": "captive"},
    "PD-SECURE": {"wlan_security": "wpa3-enterprise", "wlan_eap": "EAP-TLS", "wlan_switching": "local",
                  "wlan_bands": ["5ghz"]},
}
# The MR46 is dual-band; each radio broadcasts the SSIDs set to its band that the AP's own VLANs carry.
RADIOS = (("radio0", "2.4ghz", "2.4g-6-2437-22", "6 (2437/22)"), ("radio1", "5ghz", "5g-42-5210-80", "42 (5210/80)"))
# Both sites' APs are run from the same cloud dashboard: no controller on site.
WIRELESS = {"wireless_management": "cloud", "wireless_manager": "Cloud Wi-Fi dashboard"}
# What NetBox holds inside the boxes: an SR optic in every fibre port (bound to the interface), and the core
# pair's two PSUs and two fan trays each; the rest have fixed power and no module bays recorded.
OPTIC = {"mmf": "SFP-10G-SR"}
CHASSIS_PARTS = {"core-switch": (("psu", "Power supply", "C9K-PWR-950WAC-R", 2), ("fan", "Fan", "C9K-T1-FANTRAY", 2))}
ITEM_ROLES = {"transceiver": "Transceiver", "psu": "Power supply", "fan": "Fan"}
# Rooms under the two wings (the shared basement data room sits under City Hall's); the library's rooms stand alone.
PARENT = {"City Hall Floor 1": "City Hall wing", "City Hall Floor 2": "City Hall wing", "IDF-C2": "City Hall Floor 2",
          "Council chamber": "City Hall Floor 1", "IDF-PD": "Police wing", "DATA-B": "Basement",
          "Basement": "City Hall wing"}
# Audit evidence (the fields netbox-setup adds, and NetBox contacts as owners and custodians). City IT runs the
# network; the police department owns its cage, its closet and everything on its VLANs; finance owns the card
# terminals; facilities own the building systems; public works owns the signal system. Police subnets carry the
# CJIS scope and the payment counters the PCI one. A few honest findings: the console server's backup is stale,
# the UPS cards and the door controller are unpatched, the NVR and the HVAC controller keep their logs to
# themselves, and the city hosts' support contract runs out within the quarter.
ROOM_FACTS = {  # location -> (physical access, data classification, last verified)
    "DATA-B": ("badge-camera", "confidential", "2026-09-15"), "IDF-C2": ("locked-room", "internal", "2026-09-15"),
    "IDF-PD": ("badge-camera", "restricted", "2026-09-15"), "Police wing": ("badge", "restricted", "2026-09-15"),
    "LB1-MDF": ("locked-room", "internal", "2026-08-28"), "Reading room": ("open", "public", None)}
ROOM_ACCESS = "badge"   # every other room: staff areas are behind the civic center's badge doors
PREFIX_FACTS = {25: {"compliance_scope": ["pci-cde"], "data_classification": "confidential"},
                60: {"compliance_scope": ["cjis"], "data_classification": "restricted"},
                61: {"compliance_scope": ["cjis"], "data_classification": "restricted"},
                62: {"compliance_scope": ["cjis"], "data_classification": "restricted"},
                70: {"data_classification": "public"}, 71: {"data_classification": "public"}}
OWNERS = {  # role -> (asset owner, custodian), where it isn't the site's
    "camera": ("Facilities manager", "Security installer"), "nvr": ("Facilities manager", "Security installer"),
    "door-controller": ("Facilities manager", "Security installer"),
    "hvac-controller": ("Facilities manager", "HVAC contractor"),
    "payment-terminal": ("Finance director", "IT manager"),
    "signal-system": ("Public works director", "Signal vendor")}
POLICE = ("Police department", "Police IT liaison")
LOCAL_LOGS = ("nvr", "camera", "door-controller", "hvac-controller")
PATCHED = {"firewall": "2026-09-24", "core-switch": "2026-08-19", "access-switch": "2026-08-19",
           "console-server": "2026-07-15", "hypervisor": "2026-10-08", "storage": "2026-09-02", "ups": "2025-11-20",
           "nvr": "2026-08-12", "camera": "2026-08-12", "door-controller": "2026-05-04", "printer": "2026-09-30",
           "hvac-controller": "2026-08-05", "signal-system": "2026-09-10", "payment-terminal": "2026-09-18",
           "public-pc": "2026-10-12"}
BACKED_UP = {"console-server": "2026-06-30", "ups": "2026-10-01", "nvr": "2026-09-30", "camera": "2026-09-30",
             "door-controller": "2026-09-30", "printer": "2026-10-01", "hvac-controller": "2026-10-01",
             "payment-terminal": "2026-10-01", "public-pc": "2026-10-12"}
INSTALLED = {"firewall": "2024-06-10", "core-switch": "2024-06-10", "access-switch": "2024-06-10",
             "console-server": "2024-06-10", "hypervisor": "2023-09-18", "storage": "2023-09-18", "ups": "2021-04-26",
             "access-point": "2024-07-01", "nvr": "2022-03-14", "camera": "2022-03-14", "door-controller": "2022-03-14",
             "printer": "2025-02-03", "hvac-controller": "2019-10-07", "signal-system": "2021-08-30",
             "payment-terminal": "2024-01-15", "router": "2023-05-22", "public-pc": "2025-06-30"}
CONTRACT_END = {"Premium support": "2027-06-30", "Smart Net NBD": "2027-06-30", "ProSupport NBD": "2026-12-15",
                "Foundation Care NBD": "2027-03-31", "Vendor support annual": "2027-01-31"}
# Each model's end of sale and end of support, kept once on its device type. Endpoint models carry none.
LIFECYCLE = {"PA-1410": ("2030-06-30", "2035-06-30"), "PA-445": ("2030-06-30", "2035-06-30"),
             "C9500-24Y4C": ("2029-10-31", "2034-10-31"), "C9300-48P": ("2028-10-31", "2033-10-31"),
             "MR46": ("2027-07-31", "2032-07-31"), "OM1204-4E-L": ("2028-12-31", "2031-12-31"),
             "PowerEdge R660": ("2029-05-31", "2033-05-31"), "StoreOnce 3720": ("2028-06-30", "2031-06-30"),
             "PowerVault ME5012": ("2029-03-31", "2032-03-31"), "ISR 1121": ("2027-04-30", "2032-04-30"),
             "9PX 3000": ("2028-12-31", "2031-12-31"), "9PX 2000": ("2028-12-31", "2031-12-31")}
IFACE_TYPE = {"DAC": "10gbase-x-sfpp", "MMF OM4": "10gbase-x-sfpp", "Cat6A": "10gbase-t", "Cat6": "1000base-t"}


def ref(value: str, key: str = "name", **extra) -> dict | None:
    return {key: value, "slug": value.lower().replace(" ", "-").replace("&", "and"), **extra} if value else None


def tag(slug: str) -> dict:
    return {"name": ZONE_NAMES.get(slug, slug), "slug": slug}


class Export:
    def __init__(self, site: dict, n_site: int):
        self.site = {"id": n_site, "name": site["name"], "slug": site["slug"], "facility": site["code"],
                     "custom_fields": {"netdiagrams": {"profile": "municipal"}, **WIRELESS}}
        self.devices: dict[str, dict] = {}
        self.locations: dict[str, dict] = {}
        self.chassis: dict[str, dict] = {}
        self.interfaces: dict[tuple, dict] = {}
        self.cables, self.vlans, self.prefixes, self.ips = [], [], [], []

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

    def access(self, dev: str):
        d = self.devices[dev]
        return S.access_vlan(d["role"]["slug"], (d["tags"] or [{}])[0].get("slug", ""))

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
        kind = "25gbase-x-sfp28" if "25G" in c["speed"] else ""
        for n, label in enumerate(c["labels"]):
            ends = []
            b_dev = c["b"][n].split(":")[0]
            to_ap = self.devices[b_dev]["role"]["slug"] == "access-point"
            ap_vlans = [v for v in vids if v != 99]   # an AP trunks its area's SSID VLANs, native 99
            for side in ("a", "b"):
                end = c[side][n]
                dev, port = end.split(":", 1)
                if to_ap and side == "b":  # the AP's 2.5G port, on a 1G switch port
                    iface = self.iface(end, c["media"], mode="tagged", untagged=99, tagged=ap_vlans,
                                       kind="2.5gbase-t")
                    iface.update(poe_mode={"value": "pd", "label": "PD"},
                                 poe_type={"value": "type2-ieee802.3at", "label": "802.3at (Type 2)"})
                elif to_ap:
                    iface = self.iface(end, c["media"], mode="tagged", untagged=99, tagged=ap_vlans,
                                       kind="1000base-t")
                elif vids:
                    iface = self.iface(end, c["media"], lag=po, mode="tagged", tagged=vids, kind=kind)
                elif not po and side == "a":
                    vid = self.access(b_dev)
                    iface = self.iface(end, c["media"], mode="access" if vid else "", untagged=vid, kind=kind)
                else:
                    vid = self.access(dev) if side == "b" else None
                    iface = self.iface(end, c["media"], mode="access" if vid else "", untagged=vid, kind=kind)
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
        # Each AP's radios, with the SSIDs set to that band on the VLANs its port carries: PD-SECURE is
        # broadcast in the police wing only, the staff and public SSIDs everywhere else (interface Wireless LANs).
        for name, d in self.devices.items():
            if d["role"]["slug"] != "access-point":
                continue
            carried = {v["vid"] for v in self.interfaces[(name, "eth0")]["tagged_vlans"]}
            for radio, band, channel, label in RADIOS:
                lans = [{"id": w["id"], "ssid": w["ssid"]} for w in out
                        if band in w["custom_fields"]["wlan_bands"] and w["vlan"]["vid"] in carried]
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
                          "role": {"name": ITEM_ROLES[role], "slug": role}, "manufacturer": ref(S.CISCO),
                          "part_id": part, "serial": f"{d['serial'][:2] or 'FN'}xxxxx{51 + len(items)}",
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
            people.setdefault(person, len(people) + 1 + 20 * (self.site["id"] - 1))
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
            if name in ("IDF-PD", "Police wing"):   # the police closet and wing are the department's
                assign("dcim.location", loc["id"], POLICE[0], "asset-owner")
        by_vid = {v["id"]: v["vid"] for v in self.vlans}
        for p in self.prefixes:
            p.setdefault("custom_fields", {}).update(PREFIX_FACTS.get(by_vid.get((p.get("vlan") or {}).get("id")), {}))
        for d in self.devices.values():
            role, cf = d["role"]["slug"], d["custom_fields"]
            police = (d["tags"] and d["tags"][0]["slug"] == "zone-cjis") or (d.get("rack") or {}).get("name") == "R03"
            if role == "router" and police:   # the state's router: the state owns and runs it
                assign("dcim.device", d["id"], "State CJIS agency", "asset-owner")
                assign("dcim.device", d["id"], "State network operations", "custodian")
                cf.update(monitoring="none", log_forwarding="none")
                if role in INSTALLED:
                    cf["install_date"] = INSTALLED[role]
                continue
            if police:
                assign("dcim.device", d["id"], POLICE[0], "asset-owner")
                assign("dcim.device", d["id"], POLICE[1], "custodian")
            elif role in OWNERS:
                assign("dcim.device", d["id"], OWNERS[role][0], "asset-owner")
                assign("dcim.device", d["id"], OWNERS[role][1], "custodian")
            if role in LOCAL_LOGS:
                cf.update(monitoring="polling", log_forwarding="local")
            if role == "payment-terminal":   # the processor's terminals: in the card audit's scope
                cf["compliance_scope"] = ["pci-cde"]
            if police:
                cf["compliance_scope"] = ["cjis"]
            if role != "access-point":   # IT's nightly backup, or the vendor tool's export; APs follow the cloud
                cf["last_config_backup"] = BACKED_UP.get(role, "2026-10-17")
            if role in PATCHED:
                cf["last_patched"] = PATCHED[role]
            if role in INSTALLED:
                cf["install_date"] = INSTALLED[role]
            if cf.get("support_contract") in CONTRACT_END:
                cf["support_contract_end"] = CONTRACT_END[cf["support_contract"]]
        self.site["custom_fields"].update(monitoring="alerting", monitored_by="City IT monitoring",
                                          log_forwarding="siem", log_destination="City SIEM service, syslog over TLS",
                                          log_retention_days=365, last_verified=verified)
        return contacts

    def device_types(self) -> list:
        return model_lifecycle(self.devices.values(), LIFECYCLE)

    def data(self, circuits: list, wlans: list, contacts: list = ()) -> dict:
        return {"format": "netdiagrams-export/1", "netbox_version": "sample", "netbox_url": "",
                "exported_at": EXPORTED, "site": self.site, "locations": list(self.locations.values()),
                "devices": list(self.devices.values()), "device_types": self.device_types(),
                "virtual_chassis": list(self.chassis.values()),
                "cables": self.cables, "modules": [], "module_bays": [], "inventory_items": self.hardware(),
                "vlans": self.vlans, "prefixes": self.prefixes, "circuits": circuits,
                "interfaces": list(self.interfaces.values()), "wireless_links": [], "wireless_lans": wlans,
                "ip_addresses": self.ips, "contact_assignments": list(contacts)}


RATE = {"1G": 1_000_000, "500/50M": 500_000, "100M": 100_000}


def circuits_of(circuits: list) -> list:
    return [{"id": n + 1, "cid": c["cid"], "provider": {"name": c["provider"]}, "type": {"name": c["type"]},
             "commit_rate": RATE.get(c["speed"]), "status": {"value": "active"}, "description": c["label"]}
            for n, c in enumerate(circuits)]


def ch1() -> dict:
    e = Export(S.SITE, 1)
    for d in S.DEVICES:
        e.device(d)
    for c in S.CABLES:
        e.cable(c)
    for vid, name, zone, subnet, gw in S.VLANS:
        e.vlan(vid, name, zone, subnet, gw)
    wlans = e.wlans(S.SSIDS)
    return e.data(circuits_of(S.CIRCUITS), wlans, e.evidence("IT manager", "City IT", "2026-09-15"))


LB1_CABLES = [
    {"labels": ["LB1-CBL-00001"], "a": ["LB1-FW-01:ethernet1/2"], "b": ["LB1-ACC-1:Te1/1/1"], "type": "cat6a",
     "color": "2196f3", "speed": "10G", "media": "Cat6A", "vlans": "10, 20, 70, 71, 99", "lag": ""},
] + [
    {"labels": [f"LB1-CBL-{10 + n:05d}"], "a": [f"LB1-ACC-1:Gi1/0/{n}"], "b": [f"LB1-AP-{n:02d}:eth0"],
     "type": "cat6a", "color": "2196f3", "speed": "1G", "media": "Cat6A", "vlans": "10, 70, 99", "lag": ""}
    for n in (1, 2, 3)
] + [
    {"labels": [f"LB1-CBL-{20 + n:05d}"], "a": [f"LB1-ACC-1:Gi1/0/{10 + n}"], "b": [f"LB1-PC-{n:02d}:eth0"],
     "type": "cat6", "color": "ff9800", "speed": "1G", "media": "Cat6", "vlans": "", "lag": ""}
    for n in (1, 2, 3, 4)
] + [
    {"labels": ["LB1-CBL-00031"], "a": ["LB1-ACC-1:Gi1/0/20"], "b": ["LB1-PRN-01:eth0"], "type": "cat6",
     "color": "ff9800", "speed": "1G", "media": "Cat6", "vlans": "", "lag": ""},
]
LB1_CIRCUITS = [
    {"cid": "LB1-ISP-01", "provider": "Provider C", "type": "Filtered internet (E-rate)", "speed": "1G",
     "label": "Patron internet · content filtered"},
    {"cid": "LB1-FIBER-01", "provider": "City of Halvern", "type": "City-owned dark fiber", "speed": "1G",
     "label": "City fiber to CH1 · staff only"},
]


def lb1() -> dict:
    e = Export(S.BRANCH, 2)
    for d in S.BRANCH_DEVICES:
        e.device(d)
    for c in LB1_CABLES:
        e.cable(c)
    for vid, name, zone, subnet in S.BRANCH_VLANS:
        e.vlan(vid, name, zone, subnet, "FW-01 .1")
    wlans = e.wlans(S.BRANCH_SSIDS)
    return e.data(circuits_of(LB1_CIRCUITS), wlans, e.evidence("Library director", "City IT", "2026-08-28"))


def starter() -> dict:
    """The civic center on its first day in NetBox: the gaps a real import has.

    Half the serials and the printers' and UPSes' IPs are missing, nothing in IDF-C2
    has a rack position, the cameras have no zone tag, the floor 2 uplink cables
    have no label, and VLAN 81 (door access) has no prefix. The wireless LANs
    went in before netbox-setup's wireless fields: no switching, bands, isolation or
    portal on any SSID, and nothing yet says the APs are run from the cloud. No device has
    an asset criticality yet either: that field comes with netbox-setup too. Nobody has
    entered the optics yet, and the PSUs and fans in a box with no serial have none either.
    No owners or audit evidence are recorded yet, so the build draws no sheet 3f, and no
    model has its end-of-support date.
    """
    data = ch1()
    for n, d in enumerate(data["devices"]):
        if n % 2:
            d["serial"] = ""
        if d["role"]["slug"] in ("printer", "ups"):
            d["primary_ip4"] = None
        if (d.get("location") or {}).get("name", "") == "IDF-C2":
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
    for i in data["inventory_items"]:
        if i["device"]["name"] in no_serial:
            i["serial"] = ""
    # Nobody has looked up the models' end-of-life notices yet.
    for t in data["device_types"]:
        t["custom_fields"] = {"end_of_sale": None, "end_of_support": None}
    # The audit evidence fields and the owner contacts come with netbox-setup too: none of it yet.
    evidence = set(AUDIT_FIELDS) - {"support_contract"}
    for obj in [data["site"], *data["locations"], *data["prefixes"], *data["devices"]]:
        for key in evidence & set(obj.get("custom_fields") or {}):
            del obj["custom_fields"][key]
    data["contact_assignments"] = []
    data["exported_at"] = "2026-10-01T08:00:00Z"
    return data


SITES = {"ch1": ch1, "lb1": lb1, "starter": starter}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", choices=SITES, default="ch1")
    ap.add_argument("-o", "--output")
    args = ap.parse_args()
    data = SITES[args.site]()
    if args.site != "ch1" and not args.output:
        ap.error("--output is needed for a site other than ch1")
    out = Path(args.output) if args.output else DATA / "sample-municipal.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {out}: {len(data['devices'])} devices, {len(data['cables'])} cables, "
          f"{len(data['interfaces'])} interfaces, {len(data['vlans'])} VLANs")


if __name__ == "__main__":
    main()
