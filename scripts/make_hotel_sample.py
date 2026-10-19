"""Regenerate src/netdiagrams/data/sample-hotel.json, the Alder Bay Hotel and Conference Center export.

The export is in NetBox REST API shape and comes from the same facts as the
hotel template (scripts/hotel_template/site.py), so
`netdiagrams build --input sample-hotel.json` fills every hotel sheet. The
site carries {"profile": "hotel"} in its netdiagrams field, the way a real
NetBox would pick the hotel standard.

    python scripts/make_hotel_sample.py              # H01, into the package
    python scripts/make_hotel_sample.py --site h02 -o tests/fixtures/hotel-h02.json
    python scripts/make_hotel_sample.py --site starter -o hotel-starter.json   # day one, with gaps
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hotel_template import site as S  # noqa: E402
from sample_kit import model_lifecycle  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from netdiagrams.hotels import ZONE_NAMES  # noqa: E402
from netdiagrams.audit import FIELD_NAMES as AUDIT_FIELDS  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"
EXPORTED = "2026-10-15T08:00:00Z"
ROLE_NAMES = {"ups": "UPS", "nvr": "NVR", "access-point": "Access point", "pos-server": "POS server",
              "pos-terminal": "POS workstation", "payment-terminal": "Card terminal", "tv-headend": "TV head-end",
              "bms-server": "BMS supervisor", "room-controls": "Room-controls gateway",
              "safety-gateway": "Safety-button gateway"}
WLAN_AUTH = {"ALDERBAY-GUEST": ("open", "Open", "", ""),
             "ALDERBAY-EVENTS": ("wpa-personal", "WPA Personal (PSK)", "aes", "AES"),
             "AB-STAFF": ("wpa-enterprise", "WPA Enterprise", "aes", "AES"),
             "AB-PAY": ("wpa-enterprise", "WPA Enterprise", "aes", "AES"),
             "AB-ROOMTECH": ("wpa-personal", "WPA Personal (PSK)", "aes", "AES")}
# The wlan_* custom fields netbox-setup adds: what NetBox's own auth type can't say. Never a PSK.
WLAN_FIELDS = {
    "ALDERBAY-GUEST": {"wlan_security": "open-portal", "wlan_switching": "local", "wlan_bands": ["2.4ghz", "5ghz"],
                       "wlan_client_isolation": True, "wlan_portal": "captive"},
    "ALDERBAY-EVENTS": {"wlan_security": "wpa2-wpa3", "wlan_switching": "local", "wlan_bands": ["5ghz", "6ghz"],
                        "wlan_client_isolation": True},
    "AB-STAFF": {"wlan_security": "wpa3-enterprise", "wlan_eap": "EAP-TLS", "wlan_switching": "local",
                 "wlan_bands": ["5ghz", "6ghz"]},
    "AB-PAY": {"wlan_security": "wpa3-enterprise", "wlan_eap": "EAP-TLS", "wlan_switching": "local",
               "wlan_bands": ["5ghz"]},
    "AB-ROOMTECH": {"wlan_security": "mpsk", "wlan_switching": "local", "wlan_bands": ["2.4ghz", "5ghz"]},
}
# The public-area APs are tri-band; the in-room wall plates are dual-band. Each radio broadcasts the SSIDs set
# to its band, on the APs that SSID is meant for (S.SSID_ON).
TRI = (("radio0", "2.4ghz", "2.4g-6-2437-22", "6 (2437/22)"), ("radio1", "5ghz", "5g-42-5210-80", "42 (5210/80)"),
       ("radio2", "6ghz", "6g-15-6025-160", "15 (6025/160)"))  # NetBox's channel choice values
DUAL = TRI[:2]
RADIOS = {"AP-635": TRI, "AP-503H": DUAL}
WIRELESS = {"wireless_management": "cloud", "wireless_manager": "Cloud Wi-Fi dashboard"}
# Inventory: an SR optic in every fibre port (floor 1 and the guest floors' riser uplinks, both ends), and two
# PSUs and two fan trays in each core member.
OPTIC = {"mmf": "J9150D"}  # Aruba 10G SFP+ LC SR
CHASSIS_PARTS = {"core-switch": (("psu", "Power supply", "JL086A", 2), ("fan", "Fan", "JL669A", 2))}
ITEM_ROLES = {"transceiver": "Transceiver", "psu": "Power supply", "fan": "Fan"}

# Nested locations: Main building › floor › closet or room.
PARENT = {"Lower level": "Main building", **{f"Floor {f}": "Main building" for f in range(1, 7)},
          **{room: "Lower level" for room in ("MDF-LL", "Central plant", "Kitchen", "Security office")},
          **{room: "Floor 1" for room in ("IDF-1", "Front desk", "Restaurant", "Bar", "Spa", "Ballroom",
                                          "Meeting rooms")},
          **{f"IDF-{f}": f"Floor {f}" for f in range(2, 7)}}
BRANCH_PARENT = {**{f"Floor {f}": "Main building" for f in range(1, 5)},
                 **{room: "Floor 1" for room in ("MDF", "Front desk", "Market pantry")}}

# Audit evidence (the fields netbox-setup adds, and NetBox contacts as owners and custodians). Kestrel Hospitality
# runs IT for the owner and is every system's custodian unless a vendor is; the hotel IT manager owns the network.
# The director of engineering owns the building systems, the F&B director and the front office own payments, and
# the security director owns safety. The brand's router and the Wi-Fi vendor's gateway are theirs (tenant too).
# Payments subnets are in the PCI CDE; the servers subnet (the PMS interface server takes post-to-room), the
# firewalls and the core are PCI connected. A few honest findings: nobody holds a config backup of the two
# third-party boxes, the BMS supervisor and the door controller are unpatched, the NVR keeps its logs to itself,
# and the hypervisors' support contract runs out within the quarter.
ROOM_FACTS = {  # location -> (physical access, data classification, last verified)
    "MDF-LL": ("badge-camera", "confidential", "2026-09-18"), "IDF-1": ("locked-room", "internal", "2026-09-18"),
    "Central plant": ("locked-room", "internal", "2026-09-18"),
    **{f"IDF-{f}": ("locked-cabinet", "internal", "2026-09-18") for f in range(2, 7)},
    "MDF": ("locked-room", "internal", "2026-08-27")}
OPEN_AREAS = {"Floor 1", "Restaurant", "Bar", "Spa", "Ballroom", "Meeting rooms",
              *(f"Floor {f}" for f in range(2, 7))}   # guests walk here: the AP and drops are in reach
ROOM_ACCESS = "badge"   # back of house, the front desk and the lower level are staff-only
PREFIX_FACTS = {**{v: {"compliance_scope": ["pci-cde"], "data_classification": "restricted"} for v in (20, 21, 22)},
                30: {"compliance_scope": ["pci-connected"], "data_classification": "confidential"},
                100: {"data_classification": "public"}, 101: {"data_classification": "public"},
                110: {"data_classification": "public"}}
CONNECTED_ROLES = ("firewall", "core-switch")   # carry card traffic between the payments VLANs and the processor
CUSTODIAN = "Kestrel Hospitality IT"
OWNERS = {  # role -> (asset owner, custodian)
    "bms-server": ("Director of engineering", "BMS contractor"),
    "building-controller": ("Director of engineering", "BMS contractor"),
    "elevator-monitor": ("Director of engineering", "Elevator company"),
    "pos-server": ("F&B director", "POS vendor support"), "pos-terminal": ("F&B director", "POS vendor support"),
    "camera": ("Security director", "Security integrator"), "nvr": ("Security director", "Security integrator"),
    "door-controller": ("Security director", "Security integrator"),
    "safety-gateway": ("Security director", "Security integrator"),
    "router": (f"{S.BRAND_CO} (brand IT)", f"{S.BRAND_CO} (brand IT)"),
    "guest-gateway": (S.HSIA, S.HSIA),
}
OWNERS_BY_NAME = {"PT-FD": ("Front office manager", CUSTODIAN), "PT-RST": ("F&B director", CUSTODIAN),
                  "PT-SPA": ("F&B director", CUSTODIAN), "PRN-KIT": ("F&B director", CUSTODIAN)}
LOGS_LOCAL = ("camera", "nvr", "door-controller", "building-controller", "elevator-monitor")
NO_BACKUP = ("router", "guest-gateway", "elevator-monitor")   # third parties' boxes: the hotel holds no backup
PATCHED = {"firewall": "2026-09-24", "core-switch": "2026-08-19", "access-switch": "2026-08-19",
           "console-server": "2026-07-15", "hypervisor": "2026-10-08", "ups": "2026-09-02", "nvr": "2026-08-12",
           "camera": "2026-08-12", "door-controller": "2026-03-04", "printer": "2026-09-30",
           "pos-server": "2026-09-29", "pos-terminal": "2026-09-29", "payment-terminal": "2026-09-29",
           "call-server": "2026-08-05", "tv-headend": "2026-07-28", "room-controls": "2026-07-28",
           "lock-gateway": "2026-08-26", "key-encoder": "2026-08-26", "bms-server": "2025-12-10",
           "building-controller": "2026-07-20", "safety-gateway": "2026-09-10", "guest-gateway": "2026-09-15",
           "router": "2026-09-01"}
INSTALLED = {"firewall": "2024-05-06", "core-switch": "2024-05-06", "access-switch": "2024-05-06",
             "console-server": "2024-05-06", "hypervisor": "2023-11-06", "ups": "2022-03-14",
             "access-point": "2024-05-20", "nvr": "2022-06-01", "camera": "2022-06-01", "door-controller": "2022-06-01",
             "printer": "2025-01-20", "pos-server": "2023-04-17", "pos-terminal": "2023-04-17",
             "payment-terminal": "2025-02-03", "call-server": "2021-09-13", "tv-headend": "2022-11-07",
             "room-controls": "2022-11-07", "lock-gateway": "2023-02-20", "key-encoder": "2023-02-20",
             "bms-server": "2019-08-26", "building-controller": "2019-08-26", "safety-gateway": "2024-01-15",
             "guest-gateway": "2024-05-20", "router": "2024-05-06", "elevator-monitor": "2020-04-01"}
CONTRACT_END = {"FortiCare 24x7": "2027-05-31", "Foundation Care NBD": "2027-06-30", "ProSupport NBD": "2026-12-15",
                "POS vendor support": "2027-03-31", "Voice vendor support": "2027-01-31",
                "TV vendor support": "2027-10-31", "BMS contractor service": "2027-06-30",
                "Wi-Fi vendor managed service": "2028-05-31"}
# Each model's end of sale and end of support, kept once on its device type. Endpoint models carry none.
LIFECYCLE = {"FortiGate 200G": ("2030-03-31", "2035-03-31"), "FortiGate 120G": ("2030-03-31", "2035-03-31"),
             "CX 6300M 24SFP+": ("2029-10-31", "2034-10-31"), "CX 6300F 48G Class4 PoE": ("2029-10-31", "2034-10-31"),
             "CX 6200F 48G Class4 PoE": ("2029-10-31", "2034-10-31"), "AP-635": ("2030-06-30", "2035-06-30"),
             "AP-503H": ("2029-06-30", "2034-06-30"), "OM1204-4E-L": ("2028-12-31", "2031-12-31"),
             "PowerEdge R660xs": ("2029-05-31", "2033-05-31"), "Smart-UPS SRT 5000": ("2028-12-31", "2031-12-31"),
             "S3016": ("2029-12-31", "2034-12-31"), "Hospitality call server": ("2026-06-30", "2028-06-30"),
             "BMS supervisor": ("2024-12-31", "2027-12-31")}
IFACE_TYPE = {"DAC": "10gbase-x-sfpp", "MMF OM4": "10gbase-x-sfpp", "Cat6A": "10gbase-t", "Cat6": "1000base-t"}


def ref(value: str, key: str = "name", **extra) -> dict | None:
    return {key: value, "slug": value.lower().replace(" ", "-").replace("&", "and"), **extra} if value else None


def tag(slug: str) -> dict:
    return {"name": ZONE_NAMES.get(slug, slug), "slug": slug}


OUTSIDE_VRF = {"id": 1, "name": "OUTSIDE"}


class Export:
    def __init__(self, site: dict, n_site: int, parents: dict, ap_vlans=S.AP_VLANS, ssid_on: dict | None = None):
        self.site = {"id": n_site, "name": site["name"], "slug": site["slug"], "facility": site["code"],
                     "custom_fields": {"netdiagrams": {"profile": "hotel"}, **WIRELESS}}
        self.devices: dict[str, dict] = {}
        self.locations: dict[str, dict] = {}
        self.chassis: dict[str, dict] = {}
        self.interfaces: dict[tuple, dict] = {}
        self.cables, self.vlans, self.prefixes, self.ips = [], [], [], []
        self.parents = parents
        self.ap_vlans = ap_vlans  # what an AP trunks, native 99: only VLANs this site has
        self.ssid_on = ssid_on or {}
        for name in parents:   # every floor, closet and room, used or not
            self.location(name)

    def location(self, name: str) -> dict:
        if name not in self.locations:
            parent = self.location(self.parents[name]) if self.parents.get(name) else None
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
            "tenant": ref(d["tenant"]),
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
                b_dev = c["b"][n].split(":")[0]
                b_role = self.devices[b_dev]["role"]["slug"]
                if role == "access-point" and side == "b":  # the AP's uplink, on a 1G PoE switch port
                    iface = self.iface(end, c["media"], mode="tagged", untagged=99, tagged=vids and
                                       [v for v in vids if v != 99] or self.ap_vlans, kind="2.5gbase-t")
                    iface.update(poe_mode={"value": "pd", "label": "PD"},
                                 poe_type={"value": "type2-ieee802.3at", "label": "802.3at (Type 2)"})
                elif side == "a" and b_role == "access-point":
                    iface = self.iface(end, c["media"], mode="tagged", untagged=99, tagged=vids and
                                       [v for v in vids if v != 99] or self.ap_vlans, kind="1000base-t")
                elif vids:
                    iface = self.iface(end, c["media"], lag=po, mode="tagged", tagged=vids)
                else:
                    vid = S.access_vlan(b_dev, b_role) if not po and c["lag"] == "" else None
                    iface = self.iface(end, c["media"], mode="access" if vid else "", untagged=vid)
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

    def address(self, dev: str, port: str, address: str, zone: str) -> None:
        """An address on a firewall port with no VLAN behind it (wan, brand, guest DMZ): its own zone-tagged prefix,
        in the OUTSIDE VRF, which is how NetBox says a routed subnet with no VLAN is owned."""
        self.iface(f"{dev}:{port}", "Cat6")
        net = ipaddress.ip_interface(address).network
        self.prefixes.append({"id": len(self.prefixes) + 1, "prefix": str(net), "vlan": None, "vrf": OUTSIDE_VRF,
                              "tags": [tag(zone)], "status": {"value": "active"}})
        self.ips.append({"id": len(self.ips) + 1, "address": address, "vrf": OUTSIDE_VRF,
                         "assigned_object": {"name": port, "device": {"id": self.devices[dev]["id"], "name": dev}}})

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
        # Each AP's radios, with the SSIDs set to that band and meant for that AP (interface Wireless LANs).
        for name, d in self.devices.items():
            if d["role"]["slug"] != "access-point":
                continue
            for radio, band, channel, label in RADIOS[d["device_type"]["model"]]:
                lans = [{"id": w["id"], "ssid": w["ssid"]} for w in out
                        if band in w["custom_fields"]["wlan_bands"]
                        and name.startswith(self.ssid_on.get(w["ssid"], ("",)))]
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
            people.setdefault(person, len(people) + 1 + 20 * (self.site["id"] - 1))
            contacts.append({"id": len(contacts) + 1, "object_type": kind, "object_id": ident,
                             "contact": {"id": people[person], "name": person},
                             "role": {"slug": role, "name": role.replace("-", " ").capitalize()},
                             "priority": {"value": "primary"}})

        assign("dcim.site", self.site["id"], owner, "asset-owner")
        assign("dcim.site", self.site["id"], custodian, "custodian")
        for name, loc in self.locations.items():
            access, data_class, seen = ROOM_FACTS.get(name, ("open" if name in OPEN_AREAS else ROOM_ACCESS,
                                                             None, None))
            if name == "Main building":
                access = ROOM_ACCESS
            loc["custom_fields"] = {k: v for k, v in (("physical_access", access), ("data_classification", data_class),
                                                      ("last_verified", seen)) if v}
        by_vid = {v["id"]: v["vid"] for v in self.vlans}
        for p in self.prefixes:
            p.setdefault("custom_fields", {}).update(PREFIX_FACTS.get(by_vid.get((p.get("vlan") or {}).get("id")), {}))
        for d in self.devices.values():
            role, cf = d["role"]["slug"], d["custom_fields"]
            who = next((v for k, v in OWNERS_BY_NAME.items() if f"-{k}-" in d["name"]), OWNERS.get(role))
            if who:
                assign("dcim.device", d["id"], who[0], "asset-owner")
                assign("dcim.device", d["id"], who[1], "custodian")
            if role in LOGS_LOCAL:
                cf.update(monitoring="polling", log_forwarding="local")
            if role in CONNECTED_ROLES:
                cf["compliance_scope"] = ["pci-connected"]
            if role not in ("access-point",) + NO_BACKUP:   # APs follow the cloud; nobody backs up a vendor's box
                cf["last_config_backup"] = "2026-10-14" if role != "console-server" else "2026-10-01"
            if role in PATCHED:
                cf["last_patched"] = PATCHED[role]
            if role in INSTALLED:
                cf["install_date"] = INSTALLED[role]
            if cf.get("support_contract") in CONTRACT_END:
                cf["support_contract_end"] = CONTRACT_END[cf["support_contract"]]
        self.site["custom_fields"].update(monitoring="alerting", monitored_by="Kestrel monitoring (NOC)",
                                          log_forwarding="siem", log_destination="Kestrel SIEM, syslog over TLS",
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


def circuit(n: int, c: dict, rate: int) -> dict:
    return {"id": n, "cid": c["cid"], "provider": {"name": c["provider"]}, "type": {"name": c["type"]},
            "commit_rate": rate or None, "status": {"value": "active"}, "description": c["label"]}


RATES = {"1G": 1_000_000, "1G/50M": 1_000_000, "200M": 200_000}


def hq() -> dict:
    e = Export(S.SITE, 1, PARENT, ssid_on=S.SSID_ON)
    for d in S.DEVICES:
        e.device(d)
    for c in S.CABLES:
        e.cable(c)
    for vid, name, zone, subnet, gw in S.VLANS:
        e.vlan(vid, name, zone, subnet, gw)
    for dev, port, address, zone in S.FW_ADDRESSES:
        e.address(dev, port, address, zone)
    circuits = [circuit(n + 1, c, RATES.get(c["speed"], 0)) for n, c in enumerate(S.CIRCUITS)]
    wlans = e.wlans(S.SSIDS)
    return e.data(circuits, wlans, e.evidence("Hotel IT manager", CUSTODIAN, "2026-09-18"))


def branch() -> dict:
    e = Export(S.BRANCH, 2, BRANCH_PARENT, ap_vlans=(10, 100))
    for d in S.BRANCH_DEVICES:
        e.device(d)
    cat6 = lambda n, a, b, vlans="", lag="": {"labels": [f"H02-CBL-{n:05d}"], "a": [a], "b": [b], "type": "cat6",
                                              "color": "2196f3", "speed": "1G", "media": "Cat6", "vlans": vlans,
                                              "lag": lag}
    inside = ", ".join(str(v[0]) for v in S.BRANCH_VLANS if v[0] != 100)
    cables = [cat6(1, "H02-FW-01:internal1", "H02-CORE-1:1/1/1", inside),
              cat6(2, "H02-BRAND-RTR-01:lan1", "H02-FW-01:brand", lag="BRAND"),
              cat6(3, "H02-FW-01:dmz-guest", "H02-GW-01:wan1", lag="DMZ"),
              cat6(4, "H02-CORE-1:1/1/3", "H02-GW-01:lan1", "100"),
              cat6(11, "H02-CORE-1:1/1/11", "H02-POS-01:eth0"), cat6(12, "H02-CORE-1:1/1/12", "H02-PT-FD-01:eth0"),
              cat6(13, "H02-CORE-1:1/1/13", "H02-PBX-01:eth0"), cat6(14, "H02-CORE-1:1/1/14", "H02-LOCKGW-01:eth0")]
    cables += [cat6(20 + n, f"H02-CORE-1:1/1/{20 + n}", f"H02-AP-{n:02d}:eth0", "10, 99, 100") for n in (1, 2)]
    for c in cables:
        c["type"] = "cat6a" if "-AP-" in c["b"][0] else c["type"]
        e.cable(c)
    for vid, name, zone, subnet, gw in S.BRANCH_VLANS:
        e.vlan(vid, name, zone, subnet, gw)
    circuits = [{"id": 1, "cid": "H02-ISP-A-01", "provider": {"name": "Provider C"},
                 "type": {"name": "Business broadband"}, "commit_rate": 500_000, "status": {"value": "active"},
                 "description": "Broadband 500/50"},
                {"id": 2, "cid": "H02-BRAND-01", "provider": {"name": S.BRAND_CO},
                 "type": {"name": "Brand-managed broadband"}, "commit_rate": 100_000, "status": {"value": "active"},
                 "description": "Brand broadband 100M · the brand's, not the hotel's"}]
    wlans = e.wlans(S.BRANCH_SSIDS)
    return e.data(circuits, wlans, e.evidence("Hotel IT manager", CUSTODIAN, "2026-08-27"))


def starter() -> dict:
    """Alder Bay on its first day in NetBox: the gaps a real import has.

    Half the serials and the printers' and UPSes' IPs are missing, nothing in
    IDF-1 has a rack position, the cameras have no zone tag, the floor 2 riser
    uplink cables have no label, and VLAN 81 (door access) has no prefix. The
    wireless LANs went in before netbox-setup's wireless fields: no switching,
    bands, isolation or portal on any SSID, and nothing yet says the APs are run
    from the cloud. No device has an asset criticality yet, nobody has entered
    the optics, and the PSUs and fans in a box with no serial have none either.
    No owners (not even the brand's and the Wi-Fi vendor's tenants) or audit evidence are recorded yet, so the build draws no sheet
    3f, and no model has its end-of-support date.
    """
    data = hq()
    for n, d in enumerate(data["devices"]):
        if n % 2:
            d["serial"] = ""
        if d["role"]["slug"] in ("printer", "ups"):
            d["primary_ip4"] = None
        if (d.get("location") or {}).get("name", "") == "IDF-1":
            d["position"] = d["face"] = None
        if d["role"]["slug"] == "camera":
            d["tags"] = []
    uplink = set(next(c for c in S.CABLES if c["lag"] == "Po13")["labels"])
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
        d["tenant"] = None  # a tenant is an owner to the audit checks; day one has none (descriptions still say whose)
    no_serial = {d["name"] for d in data["devices"] if not d["serial"]}
    data["inventory_items"] = [i for i in data["inventory_items"] if i["role"]["slug"] != "transceiver"]
    for t in data["device_types"]:
        t["custom_fields"] = {"end_of_sale": None, "end_of_support": None}
    for i in data["inventory_items"]:
        if i["device"]["name"] in no_serial:
            i["serial"] = ""
    evidence = set(AUDIT_FIELDS) - {"support_contract"}
    for obj in [data["site"], *data["locations"], *data["prefixes"], *data["devices"]]:
        for key in evidence & set(obj.get("custom_fields") or {}):
            del obj["custom_fields"][key]
    data["contact_assignments"] = []
    data["exported_at"] = "2026-10-01T08:00:00Z"
    return data


SITES = {"h01": hq, "h02": branch, "starter": starter}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", choices=SITES, default="h01")
    ap.add_argument("-o", "--output")
    args = ap.parse_args()
    data = SITES[args.site]()
    if args.site != "h01" and not args.output:
        ap.error("--output is needed for a site other than h01")
    out = Path(args.output) if args.output else DATA / "sample-hotel.json"
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {out}: {len(data['devices'])} devices, {len(data['cables'])} cables, "
          f"{len(data['interfaces'])} interfaces, {len(data['vlans'])} VLANs")


if __name__ == "__main__":
    main()
