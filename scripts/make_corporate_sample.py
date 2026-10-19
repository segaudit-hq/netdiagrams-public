"""Regenerate src/netdiagrams/data/sample-corporate.json, the Sable Ridge HQ campus export (C01).

The export is in NetBox REST API shape and comes from the same facts as the
corporate template (scripts/corporate_template/site.py), so
`netdiagrams build --input sample-corporate.json` fills every corporate sheet.
The profile is set where a company would set it: {"profile": "corporate"} and
the naming standard in the netdiagrams field on the Sable Ridge region, which
every site inherits.

    python scripts/make_corporate_sample.py                  # C01, into the package
    python scripts/make_corporate_sample.py --site starter -o corporate-starter.json   # day one, with gaps
    python scripts/make_corporate_sample.py --site c11 -o c11.json   # the Ashcombe branch (BR-M), to draft
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corporate_template import site as S  # noqa: E402
from sample_kit import model_lifecycle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from netdiagrams.audit import FIELD_NAMES as AUDIT_FIELDS  # noqa: E402
from netdiagrams.corporate import ZONE_NAMES  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"
EXPORTED = "2026-10-18T08:00:00Z"
SETTINGS = {"profile": "corporate", "naming": {"pattern": r"^C\d{2}-[A-Z0-9]+(-[A-Z0-9]+)*$"}}
ROLE_NAMES = {"ups": "UPS", "nvr": "NVR", "access-point": "Access point", "sdwan-hub": "SD-WAN hub",
              "dc-leaf": "DC leaf switch", "bms-controller": "BMS controller", "room-system": "Meeting-room system"}
WLAN_AUTH = {"SR-CORP": ("wpa-enterprise", "WPA Enterprise", "aes", "AES"), "SR-GUEST": ("open", "Open", "", ""),
             "SR-IOT": ("wpa-personal", "WPA Personal (PSK)", "aes", "AES")}
# The wlan_* custom fields netbox-setup adds: what NetBox's own auth type can't say. Never a key.
WLAN_FIELDS = {
    "SR-CORP": {"wlan_security": "wpa3-enterprise", "wlan_eap": "EAP-TLS", "wlan_switching": "tunnelled",
                "wlan_bands": ["5ghz", "6ghz"]},
    "SR-GUEST": {"wlan_security": "open-portal", "wlan_switching": "tunnelled", "wlan_bands": ["2.4ghz", "5ghz"],
                 "wlan_client_isolation": True, "wlan_portal": "captive"},
    "SR-IOT": {"wlan_security": "mpsk", "wlan_switching": "tunnelled", "wlan_bands": ["5ghz"]},
}
BRANCH_SWITCHING = "local"   # FlexConnect: branch APs switch SR-CORP and SR-GUEST onto the branch's VLANs
RADIOS = (("radio0", "2.4ghz", "2.4g-6-2437-22", "6 (2437/22)"), ("radio1", "5ghz", "5g-42-5210-80", "42 (5210/80)"),
          ("radio2", "6ghz", "6g-15-6025-160", "15 (6025/160)"))
WIRELESS = {"wireless_management": "controller", "wireless_manager": "C01-WLC-01/02 (SSO pair)"}
# Inventory: an optic in each fiber cable end, by media and speed; PSUs and fans in the core, distribution
# and DC leaf chassis.
OPTICS = {("smf", "100G"): "QSFP-100G-LR4-S", ("smf", "2×10G"): "SFP-10G-LR-S", ("mmf", "2×25G"): "SFP-25G-SR-S",
          ("mmf", "10G"): "SFP-10G-SR-S", ("mmf", "2×10G"): "SFP-10G-SR-S"}
CHASSIS_PARTS = {"core-switch": (("psu", "PWR-C4-950WAC-R", 2), ("fan", "C9K-T1-FANTRAY", 2)),
                 "distribution-switch": (("psu", "PWR-C4-950WAC-R", 2), ("fan", "C9K-T1-FANTRAY", 2)),
                 "dc-leaf": (("psu", "NXA-PAC-650W-PE", 2), ("fan", "NXA-FAN-30CFM-B", 4))}
ITEM_ROLES = {"transceiver": "Transceiver", "psu": "Power supply", "fan": "Fan"}
# Audit evidence. The infrastructure team owns the campus and the network team keeps it; facilities own the
# building systems and their contractor keeps them. The practice management prefixes are SOX scope; the legal
# systems are restricted and tagged client-confidential (no compliance scope says it). A few honest findings:
# the DC console server's backup is stale, the BMS controllers and the IDF UPS cards are unpatched, the
# recorders keep their logs to themselves, and the legal hosts' support ends within the quarter.
ROOM_FACTS = {"DC-N": ("badge-camera", "restricted", "2026-09-30"), "MDF-N": ("badge-camera", "confidential", "2026-09-30"),
              "MDF-S": ("badge-camera", "confidential", "2026-09-30")}
CLOSET_ACCESS = "locked-room"    # every IDF
FLOOR_ACCESS = "badge"           # the floors and buildings: staff badge doors
PREFIX_FACTS = {400: {"compliance_scope": ["sox"], "data_classification": "confidential"},
                410: {"compliance_scope": ["sox"], "data_classification": "confidential"},
                440: {"data_classification": "restricted"},
                199: {"data_classification": "public"}, 700: {"data_classification": "public"}}
BUILDING_ROLES = ("camera", "nvr", "door-controller", "bms-controller")
PATCHED = {"firewall": "2026-09-22", "sdwan-hub": "2026-09-22", "core-switch": "2026-08-25",
           "distribution-switch": "2026-08-25", "access-switch": "2026-08-25", "dc-leaf": "2026-09-08",
           "wireless-controller": "2026-09-08", "console-server": "2026-07-20", "hypervisor": "2026-10-06",
           "storage": "2026-09-15", "backup-appliance": "2026-09-15", "ups": "2025-12-02", "nvr": "2026-08-11",
           "camera": "2026-08-11", "door-controller": "2026-06-30", "bms-controller": "2025-09-18",
           "printer": "2026-09-29", "room-system": "2026-09-14"}
BACKED_UP = {"console-server": "2026-06-30", "ups": "2026-10-01", "nvr": "2026-09-30", "camera": "2026-09-30",
             "door-controller": "2026-09-30", "bms-controller": "2026-09-30", "printer": "2026-10-01",
             "room-system": "2026-10-10"}
INSTALLED = {"firewall": "2024-05-13", "sdwan-hub": "2024-05-13", "core-switch": "2023-09-18",
             "distribution-switch": "2023-09-18", "access-switch": "2023-09-18", "dc-leaf": "2024-02-05",
             "wireless-controller": "2023-09-18", "console-server": "2023-09-18", "hypervisor": "2024-02-05",
             "storage": "2024-02-05", "backup-appliance": "2024-02-05", "ups": "2021-04-12", "access-point": "2023-10-02",
             "nvr": "2022-06-06", "camera": "2022-06-06", "door-controller": "2020-11-16", "bms-controller": "2019-08-05",
             "printer": "2025-02-10", "room-system": "2024-08-19"}
CONTRACT_END = {"Premium support": "2027-05-31", "FortiCare Premium": "2027-05-31", "Smart Net 8x5xNBD": "2027-09-30",
                "Smart Net 24x7x4": "2027-01-31", "ProSupport Plus 4h": "2027-01-31", "SupportEdge 4h": "2027-01-31",
                "ProSupport 4h": "2027-01-31"}
LEGAL_CONTRACT_END = "2026-12-31"   # CL-LEGAL's hosts: bought separately, renewal due this quarter
# Each model's end of sale and end of support, kept once on its device type. Endpoint models carry none.
LIFECYCLE = {"PA-3420": ("2030-06-30", "2035-06-30"), "PA-5420": ("2030-06-30", "2035-06-30"),
             "FortiGate 600F": ("2029-09-30", "2034-09-30"), "Catalyst 9500-48Y4C": ("2028-10-31", "2033-10-31"),
             "Catalyst 9500-24Y4C": ("2028-10-31", "2033-10-31"), "Catalyst 9300-48UXM": ("2028-10-31", "2033-10-31"),
             "Nexus 93180YC-FX3": ("2029-07-31", "2034-07-31"), "Catalyst 9800-40": ("2029-04-30", "2034-04-30"),
             "PowerEdge R760": ("2029-01-31", "2033-01-31"), "PowerEdge R660": ("2029-01-31", "2033-01-31"),
             "AFF A250": ("2027-12-31", "2032-12-31"), "PowerProtect DD6400": ("2028-06-30", "2033-06-30"),
             "OM2248-L": ("2029-12-31", "2032-12-31"), "93PM 100 kW": ("2030-12-31", "2035-12-31"),
             "Smart-UPS SRT 3000": ("2028-12-31", "2031-12-31"), "S1296": ("2029-12-31", "2034-12-31"),
             "C9136I": ("2030-04-30", "2035-04-30"), "FortiGate 120G": ("2030-03-31", "2035-03-31"),
             "Catalyst 9300-48P": ("2028-10-31", "2033-10-31")}
IFACE_TYPE = {("DAC", "100G"): "100gbase-x-qsfp28", ("DAC", "2×100G"): "100gbase-x-qsfp28",
              ("SMF", "100G"): "100gbase-x-qsfp28", ("DAC", "2×25G"): "25gbase-x-sfp28",
              ("MMF OM4", "2×25G"): "25gbase-x-sfp28", ("Cat6A", "2.5G"): "2.5gbase-t", ("Cat6A", "1G"): "1000base-t",
              ("Cat6", "1G"): "1000base-t"}


def ref(value: str, key: str = "name", **extra) -> dict | None:
    return {key: value, "slug": value.lower().replace(" ", "-").replace("&", "and"), **extra} if value else None


def tag(slug: str) -> dict:
    return {"name": ZONE_NAMES.get(slug, slug), "slug": slug}


def group(key: str) -> dict:
    gid, name, slug, parent = S.GROUPS[key]
    custom = {"netdiagrams": None}
    return {"id": gid, "name": name, "slug": slug, "parent": {"id": parent} if parent else None,
            "custom_fields": custom}


class Export:
    def __init__(self, site: dict, n_site: int, site_group: str, wireless: dict):
        self.site = {"id": n_site, "name": site["name"], "slug": site["slug"], "facility": site["code"],
                     "region": {"id": S.REGION["id"], "name": S.REGION["name"]},
                     "group": {"id": S.GROUPS[site_group][0], "name": S.GROUPS[site_group][1]},
                     "custom_fields": dict(wireless)}
        self.site_group = group(site_group)
        self.devices: dict[str, dict] = {}
        self.locations: dict[str, dict] = {}
        self.chassis: dict[str, dict] = {}
        self.interfaces: dict[tuple, dict] = {}
        self.cables, self.vlans, self.prefixes = [], [], []
        self.vrfs: dict[str, dict] = {}

    def location(self, name: str, parent: str | None = None) -> dict:
        if name not in self.locations:
            up = self.locations.get(parent) if parent else None
            self.locations[name] = {"id": len(self.locations) + 1, "name": name, "slug": name.lower().replace(" ", "-"),
                                    "parent": {"id": up["id"], "name": up["name"]} if up else None}
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

    def iface(self, end: str, kind: str, lag: str = "", mode: str = "", untagged=None, tagged=()) -> dict:
        dev, name = end.split(":", 1)
        if (dev, name) not in self.interfaces:
            d = self.devices[dev]
            self.interfaces[(dev, name)] = {
                "id": len(self.interfaces) + 1, "device": {"id": d["id"], "name": dev}, "name": name,
                "type": {"value": kind}, "enabled": True, "lag": {"name": lag} if lag else None,
                "mode": {"value": mode} if mode else None, "untagged_vlan": {"vid": untagged} if untagged else None,
                "tagged_vlans": [{"vid": v} for v in tagged], "description": "", "vrf": None}
        return self.interfaces[(dev, name)]

    def cable(self, c: dict, ap_vlans: tuple = ()) -> None:
        """One NetBox cable per label; port-channel members name their LAG, trunks their VLANs."""
        vids = [int(v) for v in c["vlans"].replace(" ", "").split(",") if v]
        po = c["lag"] if c["lag"].startswith("Po") else ""
        speed = c["speed"].split("×")[-1]
        kind = IFACE_TYPE.get((c["media"], c["speed"])) or IFACE_TYPE.get((c["media"], speed)) or \
            {"10G": "10gbase-x-sfpp", "25G": "25gbase-x-sfp28", "100G": "100gbase-x-qsfp28"}.get(speed, "1000base-t")
        for n, label in enumerate(c["labels"]):
            ends = []
            for side in ("a", "b"):
                end = c[side][n]
                dev = end.split(":", 1)[0]
                role = self.devices[dev]["role"]["slug"]
                peer = self.devices[c["b"][n].split(":", 1)[0]]["role"]["slug"]
                if role == "access-point":
                    iface = self.iface(end, "5gbase-t", mode="tagged" if ap_vlans else "access", untagged=990,
                                       tagged=ap_vlans)
                    iface.update(poe_mode={"value": "pd", "label": "PD"},
                                 poe_type={"value": "type4-ieee802.3bt", "label": "802.3bt (Type 4)"})
                elif side == "a" and peer == "access-point":
                    iface = self.iface(end, "2.5gbase-t", mode="tagged" if ap_vlans else "access", untagged=990,
                                       tagged=ap_vlans)
                elif vids:
                    iface = self.iface(end, kind, lag=po, mode="tagged", tagged=vids)
                elif peer in S.ACCESS_VLAN and not po:
                    vid = S.ACCESS_VLAN[peer]
                    iface = self.iface(end, kind, mode="access", untagged=vid)
                else:
                    iface = self.iface(end, kind, lag=po)
                ends.append([{"object_type": "dcim.interface",
                              "object": {"id": iface["id"], "name": iface["name"],
                                         "device": {"id": self.devices[dev]["id"], "name": dev}}}])
            self.cables.append({"id": len(self.cables) + 1, "label": label, "type": c["type"], "description": c["name"],
                                "status": {"value": "connected"}, "color": c["color"], "length": None,
                                "length_unit": None, "a_terminations": ends[0], "b_terminations": ends[1]})
        # The port-channel interfaces themselves carry the trunk, as NetBox records a LAG.
        if po and vids:
            for side in ("a", "b"):
                for dev in dict.fromkeys(e.split(":", 1)[0] for e in c[side]):
                    self.iface(f"{dev}:{po}", "lag", mode="tagged", tagged=vids)

    def vrf(self, name: str) -> dict | None:
        if not name:
            return None
        if name not in self.vrfs:
            rd = next(v[1] for v in S.VRFS if v[0] == name)
            self.vrfs[name] = {"id": len(self.vrfs) + 1, "name": name, "rd": f"{S.RD_ASN}:{rd}"}
        v = self.vrfs[name]
        return {"id": v["id"], "name": v["name"], "rd": v["rd"]}

    def vlan(self, vid: int | None, name: str, vrf: str, zone: str, subnet: str, gateway: str = "") -> None:
        vlan = None
        if vid is not None:
            self.vlans.append({"id": len(self.vlans) + 1, "vid": vid, "name": name, "role": None,
                               "status": {"value": "active"}, "site": {"id": self.site["id"], "slug": self.site["slug"]},
                               "tags": [tag(zone)]})
            vlan = {"id": len(self.vlans), "vid": vid}
        prefix = {"id": len(self.prefixes) + 1, "prefix": subnet, "vlan": vlan, "vrf": self.vrf(vrf),
                  "tags": [tag(zone)], "status": {"value": "active"}, "description": "" if vlan else name}
        if gateway:
            prefix["custom_fields"] = {"gateway": gateway}
        self.prefixes.append(prefix)

    def wlans(self, ssids, switching: str = "") -> list:
        by_vid = {v["vid"]: v for v in self.vlans}
        out = []
        for n, (ssid, _, vid, zone, desc) in enumerate(ssids):
            a = WLAN_AUTH[ssid]
            fields = dict(WLAN_FIELDS[ssid])
            if switching:
                fields["wlan_switching"] = switching
            out.append({"id": n + 1, "ssid": ssid, "description": desc, "status": {"value": "active"},
                        "vlan": {"id": by_vid[vid]["id"], "vid": vid, "name": by_vid[vid]["name"]},
                        "scope_type": "dcim.site", "scope_id": self.site["id"],
                        "scope": {"id": self.site["id"], "name": self.site["name"], "slug": self.site["slug"]},
                        "tags": [tag(zone)], "custom_fields": fields,
                        "auth_type": {"value": a[0], "label": a[1]},
                        "auth_cipher": {"value": a[2], "label": a[3]} if a[2] else None})
        for name, d in self.devices.items():
            if d["role"]["slug"] != "access-point":
                continue
            for radio, band, channel, label in RADIOS:
                lans = [{"id": w["id"], "ssid": w["ssid"]} for w in out if band in w["custom_fields"]["wlan_bands"]]
                i = self.iface(f"{name}:{radio}", "ieee802.11ax")
                i.update(rf_role={"value": "ap", "label": "Access point"},
                         rf_channel={"value": channel, "label": label}, wireless_lans=lans)
        return out

    def hardware(self, cables) -> list:
        """Inventory items: an optic in each fiber cable end, then each chassis's PSUs and fans."""
        items = []

        def item(dev: str, role: str, part: str, component: dict | None = None) -> None:
            d = self.devices[dev]
            items.append({"id": len(items) + 1, "device": {"id": d["id"], "name": dev}, "name": part, "label": "",
                          "role": {"name": ITEM_ROLES[role], "slug": role}, "manufacturer": ref(S.CISCO),
                          "part_id": part, "serial": f"{d['serial'][:3]}x{1001 + len(items)}",
                          "asset_tag": None, "discovered": False, "description": "",
                          "component_type": "dcim.interface" if component else None, "component": component})

        by_label = {c["label"]: c for c in self.cables}
        for c in cables:
            part = OPTICS.get((c["type"][:3], c["speed"]))
            for label in c["labels"] if part else ():
                for t in by_label[label]["a_terminations"] + by_label[label]["b_terminations"]:
                    o = t["object"]
                    item(o["device"]["name"], "transceiver", part, {"id": o["id"], "name": o["name"]})
        for name, d in self.devices.items():
            for role, part, count in CHASSIS_PARTS.get(d["role"]["slug"], ()):
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
            access, data_class, seen = ROOM_FACTS.get(name, (CLOSET_ACCESS if name.startswith("IDF") else
                                                             FLOOR_ACCESS, None, None))
            loc["custom_fields"] = {k: v for k, v in (("physical_access", access), ("data_classification", data_class),
                                                      ("last_verified", seen)) if v}
        by_vid = {v["id"]: v["vid"] for v in self.vlans}
        for p in self.prefixes:
            p.setdefault("custom_fields", {}).update(PREFIX_FACTS.get(by_vid.get((p.get("vlan") or {}).get("id")), {}))
            if (p.get("vlan") or {}).get("vid") == 440:   # no compliance scope says "client confidential": a tag does
                p["tags"].append({"name": "Client confidential", "slug": "client-confidential"})
        for d in self.devices.values():
            role, cf = d["role"]["slug"], d["custom_fields"]
            if role in BUILDING_ROLES:
                assign("dcim.device", d["id"], "Facilities manager", "asset-owner")
                assign("dcim.device", d["id"], "Building systems contractor", "custodian")
                cf.update(monitoring="polling", log_forwarding="local")
            elif d["name"].startswith("C01-HV-L"):
                assign("dcim.device", d["id"], "Legal IT", "asset-owner")
            if role != "access-point":
                cf["last_config_backup"] = BACKED_UP.get(role, "2026-10-17")
            if d["name"] == "C01-OOB-01":
                cf["last_config_backup"] = "2026-10-12"   # only the DC console server's backup is stale
            if role in PATCHED:
                cf["last_patched"] = PATCHED[role]
            if role == "ups" and d["name"] in ("C01-UPS-A", "C01-UPS-B"):
                cf["last_patched"] = "2026-09-01"         # the DC UPSs are serviced; the IDF cards are not
            if role in INSTALLED:
                cf["install_date"] = INSTALLED[role]
            if cf.get("support_contract") in CONTRACT_END:
                cf["support_contract_end"] = CONTRACT_END[cf["support_contract"]]
            if d["name"].startswith("C01-HV-L"):
                cf["support_contract_end"] = LEGAL_CONTRACT_END
        self.site["custom_fields"].update(monitoring="alerting", monitored_by="Network monitoring (NMS)",
                                          log_forwarding="siem", log_destination="MSSP SIEM (cloud), logs over TLS",
                                          log_retention_days=365, last_verified=verified)
        return contacts

    def data(self, circuits: list, wlans: list, contacts: list = (), inventory: list = ()) -> dict:
        region = {"id": S.REGION["id"], "name": S.REGION["name"], "slug": S.REGION["slug"], "parent": None,
                  "custom_fields": {"netdiagrams": SETTINGS}}
        return {"format": "netdiagrams-export/1", "netbox_version": "sample", "netbox_url": "",
                "exported_at": EXPORTED, "site": self.site, "regions": [region], "site_group": self.site_group,
                "locations": list(self.locations.values()), "devices": list(self.devices.values()),
                "device_types": model_lifecycle(self.devices.values(), LIFECYCLE),
                "virtual_chassis": list(self.chassis.values()), "cables": self.cables, "modules": [],
                "module_bays": [], "inventory_items": list(inventory), "vlans": self.vlans, "prefixes": self.prefixes,
                "circuits": circuits, "interfaces": list(self.interfaces.values()), "wireless_links": [],
                "wireless_lans": wlans, "ip_addresses": [], "contact_assignments": list(contacts)}


def circuits(rows: list) -> list:
    return [{"id": n + 1, "cid": c["cid"], "provider": {"name": c["provider"]}, "type": {"name": c["type"]},
             "commit_rate": c["rate"], "status": {"value": "active"}, "description": c["label"]}
            for n, c in enumerate(rows)]


def hq() -> dict:
    e = Export(S.SITE, 1, "hubs", WIRELESS)
    for name, parent in S.LOCATIONS:
        e.location(name, parent)
    for d in S.DEVICES:
        e.device(d)
    for c in S.CABLES:
        e.cable(c)
    for vid, name, vrf, zone, subnet, gw in S.VLANS:
        e.vlan(vid, name, vrf, zone, subnet, gw)
    for prefix, name, vrf, zone, gw in S.PREFIXES:
        e.vlan(None, name, vrf, zone, prefix, gw)
    wlans = e.wlans(S.SSIDS)
    contacts = e.evidence("Head of Infrastructure", "Network team", "2026-09-30")
    return e.data(circuits(S.CIRCUITS), wlans, contacts, e.hardware(S.CABLES))


def branch() -> dict:
    """C11 Ashcombe, a BR-M branch: a FortiGate HA pair, a two-switch stack, six APs and two printers."""
    e = Export(S.BRANCH, 11, "br-m", {"wireless_management": "controller",
                                      "wireless_manager": "C01-WLC-01/02 (FlexConnect)"})
    e.location("Ground floor")
    e.location("Comms cabinet", "Ground floor")
    devices = [
        S._dev("C11-FW-01", "firewall", S.FORTI, "FortiGate 120G", "fortios", "Comms cabinet", "CAB-1", "20",
               "10.11.240.11/24", "zone-edge", "Branch firewall and SD-WAN spoke (HA primary)", "FG12xxxx1101"),
        S._dev("C11-FW-02", "firewall", S.FORTI, "FortiGate 120G", "fortios", "Comms cabinet", "CAB-1", "19",
               "10.11.240.12/24", "zone-edge", "Branch firewall and SD-WAN spoke (HA secondary)", "FG12xxxx1102"),
        S._dev("C11-ACC-1", "access-switch", S.CISCO, "Catalyst 9300-48P", "ios-xe", "Comms cabinet", "CAB-1", "16",
               "10.11.240.21/24", "zone-corp", "Branch access stack member 1 (active)", "FOCxx1101", vc="C11-ACC",
               vcpos="1"),
        S._dev("C11-ACC-2", "access-switch", S.CISCO, "Catalyst 9300-48P", "ios-xe", "Comms cabinet", "CAB-1", "15",
               "", "zone-corp", "Branch access stack member 2 (standby)", "FOCxx1102", vc="C11-ACC", vcpos="2")]
    devices += [S._dev(f"C11-AP-{n:02d}", "access-point", S.CISCO, "C9136I", "", "Ground floor", "", "",
                       f"10.11.240.{100 + n}/24", "zone-mgmt", f"Ceiling AP {n}", f"FJCxx11{n:02d}") for n in range(1, 7)]
    devices += [S._dev(f"C11-PRN-{n:02d}", "printer", S.CANON, "imageRUNNER ADVANCE DX C5870i", "", "Ground floor",
                       "", "", f"10.11.44.{10 + n}/24", "zone-print", f"Print corner {n}", f"CNxxx11{n}")
                for n in (1, 2)]
    for d in devices:
        d["cf_ap_mode"] = "flexconnect" if d["role"] == "access-point" else ""
        e.device({**d, "cf_ap_mode": d["cf_ap_mode"]})
    trunk = "110, 120, 130, 210, 700, 990"
    cables = [
        S._cable(["C11-CBL-00001", "C11-CBL-00002"], ["C11-FW-01:x1", "C11-FW-02:x1"],
                 ["C11-ACC-1:Te1/1/1", "C11-ACC-2:Te2/1/1"], "dac-passive", "111111", "10G", "DAC", trunk),
        S._cable(["C11-CBL-00003"], ["C11-FW-01:ha"], ["C11-FW-02:ha"], "cat6", "9e9e9e", "1G", "Cat6", "", "HA")]
    cables += [S._cable([f"C11-CBL-{10 + n:05d}"], [f"C11-ACC-{n % 2 + 1}:Gi{n % 2 + 1}/0/{n // 2 + 1}"],
                        [f"C11-AP-{n:02d}:eth0"], "cat6a", "2196f3", "1G", "Cat6A") for n in range(1, 7)]
    cables += [S._cable([f"C11-CBL-{20 + n:05d}"], [f"C11-ACC-{n}:Gi{n}/0/24"], [f"C11-PRN-{n:02d}:eth0"], "cat6",
                        "2196f3", "1G", "Cat6") for n in (1, 2)]
    for c in cables:
        e.cable(c, ap_vlans=(110, 210, 700))
    for vid, name, vrf, zone, subnet in S.BRANCH_VLANS:
        e.vlan(vid, name, vrf, zone, subnet.format(n=11), "C11-FW .1")
    rows = [{"cid": "C11-DIA-0001", "provider": "Provider F", "type": "Dedicated internet", "rate": 500_000,
             "label": "DIA 500M · SD-WAN underlay 1"},
            {"cid": "C11-BB-0001", "provider": "Provider G", "type": "Business broadband", "rate": 300_000,
             "label": "Broadband · SD-WAN underlay 2"},
            {"cid": "C11-5G-0001", "provider": "Provider H", "type": "5G", "rate": 100_000,
             "label": "5G · SD-WAN underlay 3"}]
    wlans = e.wlans(S.BRANCH_SSIDS, BRANCH_SWITCHING)
    return e.data(circuits(rows), wlans, e.evidence("Head of Infrastructure", "Network team", "2026-08-20"))


def starter() -> dict:
    """Sable Ridge HQ on its first day in NetBox: the gaps sample-site.md lists for the starter build.

    Half the prefixes have no VRF, South's access stacks have no rack positions, the Commons cameras have
    no zone tag, P2P-NS-W has no cable label, and the legal cluster's hosts are untagged, so CL-LEGAL looks
    like any other host. (The BR-S site group's missing typical is a branch fact, not in this C01 export.)
    """
    data = hq()
    for n, p in enumerate(data["prefixes"]):
        if n % 2:
            p["vrf"] = None
    for d in data["devices"]:
        name, loc = d["name"], (d.get("location") or {}).get("name", "")
        if name.startswith(("C01-ACC-S1-", "C01-ACC-S2-", "C01-ACC-S3-", "C01-ACC-S4-")):
            d["position"] = d["face"] = None
        if d["role"]["slug"] == "camera" and loc.startswith("C-L"):
            d["tags"] = []
        if name.startswith("C01-HV-L"):
            d["tags"] = []
    west = next(c for c in S.CABLES if c["name"] == "P2P-NS-W")["labels"][0]
    for c in data["cables"]:
        if c["label"] == west:
            c["label"] = ""
    # Day one is 17 days before the HQ export: move the audit dates back with it, so only the HQ's own gaps show.
    for d in data["devices"]:
        cf = d.get("custom_fields") or {}
        for key in ("last_config_backup", "last_patched"):
            if cf.get(key):
                cf[key] = str(date.fromisoformat(cf[key]) - timedelta(days=17))
    data["exported_at"] = "2026-10-01T08:00:00Z"
    return data


SITES = {"c01": hq, "c11": branch, "starter": starter}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", choices=SITES, default="c01")
    ap.add_argument("-o", "--output")
    args = ap.parse_args()
    if args.site != "c01" and not args.output:
        ap.error("--output is needed for a site other than c01")
    data = SITES[args.site]()
    out = Path(args.output) if args.output else DATA / "sample-corporate.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {out}: {len(data['devices'])} devices, {len(data['cables'])} cables, "
          f"{len(data['interfaces'])} interfaces, {len(data['vlans'])} VLANs")


if __name__ == "__main__":
    main()
