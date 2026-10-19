"""Regenerate src/netdiagrams/data/sample-plant-a.json from the bundled template.

    python scripts/make_sample.py                     # Plant A, from the S01 template
    python scripts/make_sample.py --template T --site-name NAME -o OUT.json

The export is in NetBox REST API shape and holds the same facts the template's
shapes carry, so `netdiagrams build --input` on it reproduces the template. Tests
use it as a stand-in for a real NetBox.
"""

import argparse
import ipaddress
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from netdiagrams.graph import Graph, plain  # noqa: E402
from netdiagrams import hardware  # noqa: E402
from netdiagrams.sync import _zone_of_table  # noqa: E402
from sample_kit import model_lifecycle, slug  # noqa: E402  (the scripts folder is on sys.path)

DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"


def ref(value, key="name"):
    return {key: value, "slug": slug(value)} if value else None


def channel_label(value: str) -> str:
    """NetBox's label for a channel choice: '5g-151-5755-40' -> '151 (5755/40 MHz)', 60 GHz in GHz."""
    band, channel, freq, width = value.split("-")
    if band == "60g":
        return f"{channel} ({int(freq) / 1000:g}/{width} GHz)"
    return f"{channel} ({freq} MHz)" if band == "2.4g" else f"{channel} ({freq}/{width} MHz)"


def main():
    ap = argparse.ArgumentParser(description="Write a template's example site as a NetBox export.")
    ap.add_argument("--template", default=str(DATA / "S01-Network-Architecture-Template.drawio"))
    ap.add_argument("--site-name", default="Plant A")
    ap.add_argument("--site-slug", default="s01")
    ap.add_argument("-o", "--output", default=str(DATA / "sample-plant-a.json"))
    args = ap.parse_args()
    root = ET.parse(args.template).getroot()
    devices, cables, ids = {}, {}, {}
    for obj in root.iter("object"):
        a = obj.attrib
        if a.get("name") and (a.get("role") is not None or a.get("device_type") is not None):
            if a["name"] in devices:
                continue
            ids[a["name"]] = len(ids) + 1
            devices[a["name"]] = {
                "id": ids[a["name"]], "name": a["name"],
                "role": {"name": a.get("role", ""), "slug": a.get("role", "")},
                "device_type": {"model": a.get("device_type", ""),
                                "manufacturer": ref(a.get("manufacturer", ""))},
                "platform": ref(a.get("platform", "")),
                "serial": a.get("serial", ""), "asset_tag": a.get("asset_tag") or None,
                "status": {"value": a.get("status", "active")},
                "site": {"name": args.site_name, "slug": a.get("site", args.site_slug.upper())},
                "location": ref(a.get("location", "")), "rack": ref(a.get("rack", "")),
                "position": float(a["position"]) if a.get("position", "").replace(".", "").isdigit() else None,
                "face": {"value": a["face"]} if a.get("face") else None,
                "primary_ip4": {"address": a["primary_ip4"]} if a.get("primary_ip4") else None,
                "virtual_chassis": ref(a.get("virtual_chassis", "")),
                "vc_position": int(a["vc_position"]) if a.get("vc_position", "").isdigit() else None,
                "description": a.get("description", ""),
                "tags": [{"name": t, "slug": t} for t in a.get("tags", "").split(",") if t],
                "custom_fields": {k[3:]: v for k, v in a.items() if k.startswith("cf_") and v},
            }
    for obj in root.iter("object"):
        a = obj.attrib
        if a.get("cable_label") is None:
            continue
        labels = [l.strip() for l in a["cable_label"].split(",")]
        a_ends = [e.strip() for e in a.get("a_terminations", "").split(",")]
        b_ends = [e.strip() for e in a.get("b_terminations", "").split(",")]
        for i, label in enumerate(labels):
            if label in cables or not label or "‹" in label:
                continue

            def term(ends):
                if i >= len(ends) or ":" not in ends[i]:
                    return []
                dev, port = ends[i].split(":", 1)
                dev_ref = {"id": ids.get(dev), "name": dev}
                return [{"object_type": "dcim.interface", "object": {"name": port, "device": dev_ref}}]

            cables[label] = {
                "id": len(cables) + 1, "label": label, "type": a.get("type", ""),
                "status": {"value": a.get("status", "connected")}, "color": a.get("color", ""),
                "length": None, "length_unit": None,
                "a_terminations": term(a_ends), "b_terminations": term(b_ends),
            }
    # Interfaces from the hardware page's port cells.
    interfaces, seen = [], set()
    for obj in root.iter("object"):
        a = obj.attrib
        if not a.get("device") or a.get("name") is None or a.get("role") is not None:
            continue
        key = (a["device"], a["name"])
        if key in seen or a["device"] not in ids:
            continue
        seen.add(key)
        tagged = [v for v in re.split(r"[,\s]+", a.get("tagged_vlans", "")) if v.isdigit()]
        interfaces.append({
            "id": len(interfaces) + 1, "device": {"id": ids[a["device"]], "name": a["device"]},
            "name": a["name"], "type": {"value": a.get("type", "")},
            "enabled": a.get("enabled", "true") != "false",
            "lag": {"name": a["lag"]} if a.get("lag") else None,
            "mode": {"value": a["mode"]} if a.get("mode") else None,
            "untagged_vlan": {"vid": int(a["untagged_vlan"])} if a.get("untagged_vlan", "").isdigit() else None,
            "tagged_vlans": [{"vid": int(v)} for v in tagged],
            "description": a.get("description", ""), "vrf": {"name": a["vrf"]} if a.get("vrf") else None,
        })
    # The VLANs a link pill names ("Po1 · 2×10G · 181,189 · MMF OM4") go on the LAG interface at each
    # end (on the port itself when there is none), so the drawing's trunks are NetBox's trunks.
    by_port = {(i["device"]["name"], i["name"]): i for i in interfaces}
    last: list[int] = []
    for obj in root.iter("object"):
        a = obj.attrib
        if a.get("cable_label") is None or "‹" in a.get("cable_label", "") or not a.get("label"):
            continue
        segs = [x.strip() for x in a["label"].split("·")]
        speed = next((re.match(r"(?:\d+×)?(\d+(?:\.\d+)?)([GM])$", x) for x in segs
                      if re.match(r"(?:\d+×)?\d+(?:\.\d+)?[GM]$", x)), None)
        if speed:  # the pill's speed is the port's: a 10G optic in a 25G port runs at 10G
            kbps = int(float(speed.group(1)) * (1_000_000 if speed.group(2) == "G" else 1000))
            for end in a.get("a_terminations", "").split(",") + a.get("b_terminations", "").split(","):
                dev, _, port_name = end.strip().partition(":")
                if (dev, port_name) in by_port:
                    by_port[(dev, port_name)]["speed"] = kbps
        seg = next((x for x in segs if re.fullmatch(r"access \d+|same VLANs|\d+(\s*[,–-]\s*\d+)*", x)), "")
        if not seg:
            continue
        access = seg.startswith("access")
        if seg == "same VLANs":
            vids = last
        else:
            vids = []
            for part in re.split(r"[,\s]+", seg.removeprefix("access ")):
                lo, _, hi = part.replace("-", "–").partition("–")
                if lo.isdigit():
                    vids.extend(range(int(lo), int(hi or lo) + 1))
        last = vids
        for end in a.get("a_terminations", "").split(",") + a.get("b_terminations", "").split(","):
            dev, _, port_name = end.strip().partition(":")
            port = by_port.get((dev, port_name))
            if port is None:
                continue
            lag = (port.get("lag") or {}).get("name")
            target = port
            if lag:
                target = by_port.get((dev, lag))
                if target is None:
                    target = by_port[(dev, lag)] = {
                        "id": len(interfaces) + 1, "device": port["device"], "name": lag, "type": {"value": "lag"},
                        "enabled": True, "lag": None, "mode": None, "untagged_vlan": None, "tagged_vlans": [],
                        "description": "", "vrf": None}
                    interfaces.append(target)
            if access:
                target["mode"], target["untagged_vlan"] = {"value": "access"}, {"vid": vids[0]} if vids else None
            else:
                target["mode"], target["tagged_vlans"] = {"value": "tagged"}, [{"vid": v} for v in vids]
    # VLANs, prefixes and gateway addresses from the logical page's zone tables.
    vlans, prefixes, ips = [], [], []
    logical = next(d for d in root.findall("diagram") if d.get("id") == "logical")
    g = Graph(logical)
    for table in g.tables():
        if g.header(table)[:2] != ["VLAN", "NAME"]:
            continue
        zone = _zone_of_table(g, table)
        for row in g.rows(table)[1:]:
            vid, name, subnet, gateway = (plain(g.value(g.els[c])) for c in g.row_cells(row)[:4])
            if not vid.isdigit():
                continue
            vlan_id = len(vlans) + 1
            vlans.append({"id": vlan_id, "vid": int(vid), "name": name, "role": None,
                          "tags": [{"slug": zone, "name": zone}] if zone else []})
            vrf = gateway.split("·")[-1].strip() if "·" in gateway else ""
            prefixes.append({"id": len(prefixes) + 1, "prefix": subnet, "vlan": {"id": vlan_id, "vid": int(vid)},
                             "vrf": {"name": vrf} if vrf and vrf != "—" else None})
            m = re.match(r"([A-Za-z0-9-]+)\s+\.(\d+)", gateway)
            if m and "/" in subnet:
                want = m.group(1)
                if want == "CORE":  # the zone's own core: IT zones on the IT core, OT zones on the OT core
                    want = "IT-CORE" if not zone or zone.startswith(("zone-it", "zone-idmz")) else "OT-CORE"
                dev = next((n for n in ids if n.endswith(want) or n.endswith(want + "-1")), None)
                try:
                    net = ipaddress.ip_network(subnet, strict=False)
                    # ".33" is the gateway's last octet inside the subnet, not an offset from its start
                    addr = ipaddress.ip_address(f"{net.network_address}".rsplit(".", 1)[0] + "." + m.group(2))
                    if addr not in net:
                        raise ValueError(subnet)
                except ValueError:
                    continue
                if dev:
                    ips.append({"id": len(ips) + 1, "address": f"{addr}/{net.prefixlen}",
                                "assigned_object": {"name": f"Vlan{vid}", "device": {"id": ids[dev], "name": dev}}})
    # The firewall's sub-interface addresses, from the INTERFACE / ZONE / VLAN / IP table.
    fw = [n for n in ids if n.endswith("FW-ITOT-01")] + [n for n in ids if n.endswith("FW-ITOT-02")]
    for table in g.tables():
        if g.header(table)[:1] != ["INTERFACE"] or not fw:
            continue
        for row in g.rows(table)[1:]:
            name, _zone, _vid, ip = (plain(g.value(g.els[c])) for c in g.row_cells(row)[:4])
            addresses = re.findall(r"\d+\.\d+\.\d+\.\d+/\d+", ip)
            pair = re.match(r"(\d+\.\d+\.\d+)\.(\d+) / \.(\d+)$", ip)
            if pair:  # one address per firewall of the pair
                addresses = [f"{pair.group(1)}.{pair.group(2)}/27", f"{pair.group(1)}.{pair.group(3)}/27"]
            for dev, address in zip(fw, addresses):
                ips.append({"id": len(ips) + 1, "address": address,
                            "assigned_object": {"name": name, "device": {"id": ids[dev], "name": dev}}})
    modules, module_bays, inventory_items = hardware_items(root, devices, ids, interfaces, cables)
    circuits = [{"id": i + 1, "cid": o.get("cid"), "status": {"value": o.get("status", "active")}}
                for i, o in enumerate(o for o in root.iter("object") if o.get("cid"))]
    wireless_links, wireless_lans = wireless(root, devices, ids, interfaces, vlans, prefixes)
    locations, contacts, site_fields = audit_evidence(devices)
    device_types = model_lifecycle(devices.values(), LIFECYCLE)
    data = {"format": "netdiagrams-export/1", "netbox_version": "sample", "netbox_url": "",
            "exported_at": EXPORTED_AT,
            "site": {"id": 1, "name": args.site_name, "slug": args.site_slug, "custom_fields": site_fields},
            "locations": locations, "contact_assignments": contacts,
            "device_types": device_types,
            "devices": list(devices.values()), "virtual_chassis": [], "cables": list(cables.values()),
            "modules": modules, "module_bays": module_bays, "inventory_items": inventory_items,
            "vlans": vlans, "prefixes": prefixes, "circuits": circuits, "interfaces": interfaces,
            "wireless_links": wireless_links, "wireless_lans": wireless_lans, "ip_addresses": ips}
    # An AP's controller is an object field in NetBox: the shape names it, the export carries the reference.
    for d in devices.values():
        ctrl = d["custom_fields"].get("wireless_controller")
        if ctrl and ctrl in ids:
            d["custom_fields"]["wireless_controller"] = {"id": ids[ctrl], "name": ctrl}
    out = Path(args.output)
    out.write_text(json.dumps(data, indent=1) + "\n", "utf-8")
    print(f"wrote {out}: {len(devices)} devices, {len(cables)} cables, {len(interfaces)} interfaces, "
          f"{len(vlans)} VLANs, {len(ips)} gateway IPs")


# Audit evidence as Plant A keeps it: owners and room facts set once per room, site-wide monitoring and
# logging, and per-device dates. A few findings are left in on purpose, as a real plant would have them:
# one HMI's backup job stopped in July, one cell switch missed the summer patch window, and the three
# end-of-support ProCurve switches are out of contract and unpatched (sheet 3b says replace them).
EXPORTED_AT = "2026-10-17T06:00:00+00:00"
IT_ROOMS = ["MDF-01", "IDF-1", "IDF-2", "Office", "WH-01", "WH-01 ship office", "Mast M1", "Mast M2"]
OT_ROOMS = ["Control room", "Cell01 floor", "Cell02 floor", "Cell03 floor", "Production hall", "PH-01",
            "Mast M3", "Mast M4"]
ROOM_FACTS = {  # room -> (physical access, data classification, last verified)
    "MDF-01": ("badge-camera", "internal", "2026-09-12"), "IDF-1": ("locked-room", "internal", "2026-09-12"),
    "IDF-2": ("locked-room", "internal", "2026-09-12"), "Office": ("locked-cabinet", "internal", None),
    "WH-01": ("locked-cabinet", "internal", None), "WH-01 ship office": (None, "internal", None),
    "Mast M1": ("locked-cabinet", None, None), "Mast M2": ("locked-cabinet", None, None),
    "Mast M3": ("locked-cabinet", None, None), "Mast M4": ("locked-cabinet", None, None),
    "Control room": ("badge", "confidential", "2026-06-18"),
    "Cell01 floor": ("locked-cabinet", "confidential", "2026-06-18"),
    "Cell02 floor": ("locked-cabinet", "confidential", "2026-06-18"),
    "Cell03 floor": ("locked-cabinet", "confidential", "2026-06-18"),
    "Production hall": ("locked-cabinet", "confidential", "2026-06-18"),
    "PH-01": ("locked-room", "confidential", "2026-06-18"), "SIS room": ("badge-camera", "restricted", "2026-08-27"),
}
OT_IN_MDF = {"S01-FW-ITOT-01", "S01-FW-ITOT-02", "S01-IDMZ-SW-01", "S01-IDMZ-HV-01", "S01-OT-CORE-1",
             "S01-OT-CORE-2", "S01-OT-HCI-01", "S01-OT-WLC-01", "S01-OT-WLC-02"}
PATCHED = {"firewall": "2026-09-24", "sdwan-edge": "2026-08-19", "core-switch": "2026-08-19",
           "access-switch": "2026-08-19", "wireless-controller": "2026-08-19", "oob-switch": "2026-08-19",
           "industrial-switch": "2026-07-29", "hypervisor": "2026-09-10", "ptp-radio": "2026-09-02",
           "workgroup-bridge": "2026-08-19", "sis-switch": "2026-08-27", "sis-controller": "2026-08-27"}
INSTALLED = {"access-point": "2024-02-20", "ptp-radio": "2023-08-01", "industrial-switch": "2022-09-12",
             "plc": "2021-11-08", "hmi": "2022-09-12", "io": "2021-11-08", "sis-switch": "2021-11-08",
             "sis-controller": "2021-11-08", "workgroup-bridge": "2024-02-20"}


# Each model's end of sale and end of support, kept once on its device type (what the vendor published).
# The three ProCurves are long past support; the rest are current. Endpoint models carry none.
LIFECYCLE = {
    "ProCurve 2610-24": ("2013-10-31", "2018-10-31"), "ProCurve 2910al-24G-PoE+": ("2016-04-30", "2021-04-30"),
    "ProCurve E2510-24G": ("2017-07-31", "2022-07-31"),
    "Catalyst 9300-48P": ("2028-10-30", "2033-10-31"), "Catalyst 9300-48UXM": ("2028-10-30", "2033-10-31"),
    "Catalyst 9300-24T": ("2028-10-30", "2033-10-31"), "Catalyst 9300-24S": ("2028-10-30", "2033-10-31"),
    "Catalyst 9500-24Y4C": ("2028-10-30", "2033-10-31"), "Catalyst 9200L-24T-4G": ("2027-10-30", "2032-10-31"),
    "Catalyst 9800-L-F": ("2029-04-30", "2034-04-30"), "Catalyst 8300-1N1S-6T": ("2029-04-30", "2034-04-30"),
    "IE-3400-8T2S": ("2029-07-31", "2034-07-31"), "IE-3300-8T2S-E": ("2029-07-31", "2034-07-31"),
    "CW9166I": ("2030-01-31", "2035-01-31"), "CW9166D1": ("2030-01-31", "2035-01-31"),
    "IW9167EH": ("2030-01-31", "2035-01-31"), "PA-1410": ("2030-06-30", "2035-06-30"),
    "PA-450": ("2028-06-30", "2033-06-30"), "PowerBeam 5AC Gen2": ("2027-12-31", "2030-12-31"),
    "airFiber 60 LR": ("2028-12-31", "2031-12-31"), "PowerEdge R660": ("2029-05-31", "2033-05-31"),
    "HCI node": ("2029-05-31", "2033-05-31"),
}


def audit_evidence(devices):
    """Locations with their audit facts, contact assignments (owners, custodians) and the site's own fields."""
    rooms = sorted({(d.get("location") or {}).get("name") for d in devices.values() if d.get("location")})
    locations = []
    for i, name in enumerate(rooms, start=1):
        access, data_class, verified = ROOM_FACTS.get(name, (None, None, None))
        cf = {k: v for k, v in (("physical_access", access), ("data_classification", data_class),
                                ("last_verified", verified)) if v}
        if name == "SIS room":
            cf["compliance_scope"] = ["safety"]
        locations.append({"id": i, "name": name, "slug": slug(name), "parent": None, "custom_fields": cf})
    loc_id = {loc["name"]: loc["id"] for loc in locations}
    people = {"Dana Ortiz": 1, "Maya Chen": 2, "Ravi Okafor": 3, "Lee Novak": 4, "Plant IT team": 5,
              "OT controls team": 6, "Safety systems team": 7}
    owner = {"slug": "asset-owner", "name": "Asset owner"}
    custodian = {"slug": "custodian", "name": "Custodian"}
    contacts = []

    def assign(kind, ident, person, role):
        contacts.append({"id": len(contacts) + 1, "object_type": kind, "object_id": ident,
                         "contact": {"id": people[person], "name": person}, "role": role,
                         "priority": {"value": "primary"}})

    assign("dcim.site", 1, "Dana Ortiz", owner)
    assign("dcim.site", 1, "Plant IT team", custodian)
    for name in rooms:
        if name in IT_ROOMS:
            assign("dcim.location", loc_id[name], "Maya Chen", owner)
        elif name in OT_ROOMS:
            assign("dcim.location", loc_id[name], "Ravi Okafor", owner)
            assign("dcim.location", loc_id[name], "OT controls team", custodian)
        elif name == "SIS room":
            assign("dcim.location", loc_id[name], "Lee Novak", owner)
            assign("dcim.location", loc_id[name], "Safety systems team", custodian)
    for name in sorted(OT_IN_MDF):   # OT gear in the IT room belongs to OT engineering
        assign("dcim.device", devices[name]["id"], "Ravi Okafor", owner)
        assign("dcim.device", devices[name]["id"], "OT controls team", custodian)
    for d in devices.values():
        role, cf, name = d["role"]["slug"], d["custom_fields"], d["name"]
        procurve = "ProCurve" in d["device_type"]["model"]
        if role != "access-point":
            cf["last_config_backup"] = "2026-07-02" if name == "S01-C02-HMI01" else \
                "2026-10-01" if role in ("plc", "hmi", "io", "sis-controller") else "2026-10-16"
            cf["last_patched"] = "2026-02-04" if procurve else "2026-03-11" if name == "S01-C03-IE03" else \
                PATCHED.get(role, "2026-08-05")
        cf["install_date"] = "2014-06-03" if procurve else INSTALLED.get(role, "2023-05-15")
        if cf.get("support_contract"):
            cf["support_contract_end"] = "2025-12-31" if procurve else \
                "2026-12-31" if role == "ptp-radio" else "2027-06-30"
        if role in ("plc", "hmi", "io", "sis-controller"):
            cf["monitoring"], cf["monitored_by"] = "passive", "OT sensor on cell SPAN"
            cf["log_forwarding"] = "local"
        if procurve:
            cf["monitoring"] = "polling"
    site_fields = {"monitoring": "alerting", "monitored_by": "LibreNMS", "log_forwarding": "siem",
                   "log_destination": "Splunk, syslog over TLS", "log_retention_days": 400,
                   "last_verified": "2026-03-20"}
    return locations, contacts, site_fields


# Wireless LANs as Plant A's SSID table shows them: group, VLAN, auth and the wlan_* custom fields.
# NetBox holds no PSK here: OT-IOT's key lives in the controller, and the export never carries one.
WLANS = [
    ("CORP", 130, "wpa-enterprise", "aes", "wpa3-enterprise", "EAP-TLS", "tunnelled", ["5ghz", "6ghz"], None, "",
     "Corporate 802.1X, Corp ISE", None),
    ("GUEST", 190, "open", None, "owe", "", "tunnelled", ["2.4ghz", "5ghz"], True, "captive",
     "Internet only, rate-limited", None),
    ("OT-MOBILE", 350, "wpa-enterprise", "aes", "wpa3-enterprise", "EAP-TLS", "tunnelled", ["5ghz"], None, "",
     "Plant tablets and scanners, OT NPS", None),
    ("C02-AGV", 520, "wpa-enterprise", "aes", "wpa3-enterprise", "EAP-TLS", "local", ["5ghz"], None, "",
     "AGV workgroup bridges, 802.11r, FlexConnect local switching", "Cell02 floor"),
    ("OT-IOT", 365, "wpa-personal", "aes", "wpa2-psk", "", "tunnelled", ["2.4ghz"], None, "",
     "OEM machine sensors and condition-monitoring gateways; key held by OT, rotated yearly", None),
    ("WH-SCAN", 131, "wpa-enterprise", "aes", "wpa2-enterprise", "PEAP-MSCHAPv2", "tunnelled", ["5ghz"], None, "",
     "Warehouse forklift tablets and scanners", None),
]
# SSIDs each AP group's radios carry (interface.wireless_lans).
CARRIES = {"S01-AP-OF": ["CORP", "GUEST"], "S01-AP-WH": ["CORP", "WH-SCAN"], "S01-AP-OT": ["OT-MOBILE", "OT-IOT"],
           "S01-AP-C02": ["C02-AGV"]}
RADIOS = {  # radio interface -> RF fields of the point-to-point and bridge radios drawn on 3d
    ("S01-PTP-WH-A", "ath0"): dict(rf_role="ap", rf_channel="60g-2-60480-2160", rf_channel_frequency=60480,
                                    rf_channel_width=2160, tx_power=11),
    ("S01-PTP-WH-B", "ath0"): dict(rf_role="station", rf_channel="60g-2-60480-2160", rf_channel_frequency=60480,
                                    rf_channel_width=2160, tx_power=11),
    ("S01-PTP-PH-A", "wlan0"): dict(rf_role="ap", rf_channel="5g-151-5755-40", rf_channel_frequency=5755,
                                    rf_channel_width=40, tx_power=20),
    ("S01-PTP-PH-B", "wlan0"): dict(rf_role="station", rf_channel="5g-151-5755-40", rf_channel_frequency=5755,
                                    rf_channel_width=40, tx_power=20),
    ("S01-WGB-AGV-01", "radio0"): dict(rf_role="station", rf_channel="5g-36-5180-20", rf_channel_frequency=5180,
                                       rf_channel_width=20, tx_power=14),
}


ITEM_ROLES = {"optic": {"id": 1, "name": "Transceiver", "slug": "transceiver"},
              "power": {"id": 2, "name": "Power supply", "slug": "psu"}, "fan": {"id": 3, "name": "Fan", "slug": "fan"},
              "other": None}
PART_NUMBER = re.compile(r"^[A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+$")


def register_devices(label, devices):
    """The devices a modules-register row names: 'S01-FW-EDGE-01/02', 'S01-IT-ACC-IDF1/2', 'S01-Cnn-IE01..03',
    'S01-WLC-01/02 · OT-WLC-01/02' (a bare second name keeps the first one's site prefix)."""
    names = []
    for part in label.split(" · "):
        part = part.strip()
        if "-" in part and not part.startswith(label.split("-")[0] + "-"):
            part = label.split("-")[0] + "-" + part
        m = re.match(r"^(.*?)(\w+)((?:/\w+)+)$", part)
        variants = [part]
        if m:
            token = m.group(2)
            alts = [token] + m.group(3).split("/")[1:]
            variants = [m.group(1) + (token[:-len(a)] + a if len(a) < len(token) else a) for a in alts]
        for v in variants:
            pattern = re.escape(v).replace("nn", r"\d\d")
            r = re.search(r"(\d+)\\\.\\\.(\d+)$", pattern)
            if r:
                lo, hi = int(r.group(1)), int(r.group(2))
                pattern = pattern[:r.start()] + "(" + "|".join(f"{n:0{len(r.group(1))}d}" for n in range(lo, hi + 1)) + ")"
            names += [d for d in devices if d not in names and (re.fullmatch(pattern, d) or re.fullmatch(
                pattern, (devices[d].get("virtual_chassis") or {}).get("name") or ""))]
    return names


def hardware_items(root, devices, ids, interfaces, cables):
    """Modules, module bays and inventory items as NetBox would hold them for Plant A.

    Optics come from the hardware sheet's port cells (x_optic), power supplies and fans from the
    line under each port map ("Power 2× PWR-C1-350WAC-P · Fans 3× FAN-T1"), and every C9300 gets
    its network-module bay: filled on the members that carry uplink ports, empty on the others.
    A fibre cable end on a device with no port map (the firewalls, the ring switches) gets the
    transceiver its speed implies, so every fibre end in the sample has one.
    """
    modules, bays, items = [], [], []
    serial = lambda prefix: f"{prefix}xxxxx{len(items) + len(modules) + 1:02d}"

    def item(dev, kind, part_id, component=None):
        it = {"id": len(items) + 1, "device": {"id": ids[dev], "name": dev}, "name": part_id, "label": "",
              "role": ITEM_ROLES[kind], "manufacturer": None, "part_id": part_id if PART_NUMBER.match(part_id) else "",
              "serial": serial("AV" if kind == "optic" else "ART"),
              "asset_tag": None, "discovered": False, "description": "",
              "component_type": "dcim.interface" if component else None, "component": component}
        items.append(it)

    # Transceivers: the port cells name them (x_optic); a fibre cable end with no port cell gets the
    # optic its other end carries, else the one the cable's media and speed imply.
    ports = {(i["device"]["name"], i["name"]): i for i in interfaces}
    cell_optic = {}
    for obj in root.iter("object"):
        a = obj.attrib
        if a.get("device") in ids and a.get("name") and a.get("role") is None and a.get("x_optic") \
                and "‹" not in a["x_optic"] and hardware.kind_of({"part_id": a["x_optic"]}) == "optic":
            cell_optic.setdefault((a["device"], a["name"]), a["x_optic"])

    def optic(dev, name, part_id):
        if any(i["device"]["name"] == dev and (i.get("component") or {}).get("name") == name for i in items):
            return
        port = ports.get((dev, name))
        item(dev, "optic", part_id, {"id": port["id"] if port else None, "name": name})

    for (dev, name), part_id in cell_optic.items():
        optic(dev, name, part_id)
    # NetBox interface speeds are in kbps.
    by_speed = {1000000: "GLC-SX-MMD", 10000000: "SFP-10G-SR-S", 25000000: "SFP-25G-SR-S", 40000000: "QSFP-40G-SR4",
                100000000: "QSFP-100G-SR4-S"}
    for c in cables.values():
        if not str(c.get("type") or "").startswith(("smf", "mmf")):
            continue
        ends = [(t["object"]["device"]["name"], t["object"]["name"])
                for side in ("a_terminations", "b_terminations") for t in c.get(side) or []]
        known = next((cell_optic[e] for e in ends if e in cell_optic), None)
        for dev, name in ends:
            if dev not in ids:
                continue
            speed = next((ports[e].get("speed") for e in ends if e in ports and ports[e].get("speed")), 0) or \
                {"Gi": 1000000, "Te": 10000000, "Tw": 25000000, "Fo": 40000000, "Hu": 100000000}.get(name[:2], 0)
            part_id = cell_optic.get((dev, name)) or known or by_speed.get(speed) or "SFP-10G-SR-S"
            if devices[dev]["device_type"]["model"].startswith("IE-") and speed <= 1000000 and not cell_optic.get((dev, name)):
                part_id = "GLC-LX-SM-RGD" if str(c["type"]).startswith("smf") else "GLC-SX-MM-RGD"   # rugged optics in the cells
            if str(c["type"]).startswith("smf") and part_id in by_speed.values():
                part_id = part_id.replace("SX-MMD", "LH-SMD").replace("SR-S", "LR-S").replace("SR4", "LR4")
            optic(dev, name, part_id)
    # Power supplies and fans from the line under each port map, for the device (or every stack member) above it.
    hardware_page = next(d for d in root.findall("diagram") if d.get("id") == "hardware")
    g = Graph(hardware_page)
    heads = []
    for i, el in g.els.items():
        m = re.match(r"\s*<b>([^<]+)</b>", g.value(el))
        if m:
            name = m.group(1).strip()
            members = [name] if name in ids else [n for n, d in devices.items()
                                                   if (d.get("virtual_chassis") or {}).get("name") == name]
            if members:
                heads.append((g.box(i), members))
    for i, el in g.els.items():
        value = g.value(el)
        if not value.startswith("<b>Power</b>"):
            continue
        x, y, _, _ = g.box(i)
        above = [(y - hy, members) for (hx, hy, _, _), members in heads if abs(hx - x) < 2 and 0 < y - hy < 400]
        if not above:
            continue
        for seg in plain(value).split(" · "):
            kind = "power" if seg.startswith("Power ") else "fan" if seg.startswith("Fans ") else ""
            m = re.match(r"(?:Power|Fans) (?:(\d+)× )?((?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]+)", seg)
            if not kind or not m:
                continue
            for dev in min(above)[1]:
                for _ in range(int(m.group(1) or 1)):
                    item(dev, kind, m.group(2))
    # The modules register the template was drawn with covers the devices with no port map here:
    # their power supplies, empty slots and the odd item (an SD card), as the row words them.
    has = lambda dev, kind: any(i["device"]["name"] == dev and i["role"] == ITEM_ROLES[kind] for i in items)
    for table in g.tables():
        if g.header(table)[:2] != ["DEVICE", "CHASSIS"]:
            continue
        for row in g.rows(table)[1:]:
            cells = [plain(g.value(g.els[c])) for c in g.row_cells(row)]
            cols = dict(zip(g.header(table), cells))
            for dev in register_devices(cells[0], devices):
                power = cols.get("POWER", "")
                m = re.match(r"(?:PSU )?(?:(\d+)× )?(.+)$", power)
                if power and power != "—" and not has(dev, "power"):
                    for _ in range(int(m.group(1) or 1) if m else 1):
                        item(dev, "power", m.group(2) if m else power)
                slots = re.match(r"Slots? ([A-Z0-9]+(?:/[A-Z0-9]+)*) empty", cols.get("MODULES", "")) or \
                    re.match(r"([A-Z]+) / ([A-Z]+) slots empty", cols.get("MODULES", ""))
                if slots and not any(b["device"]["name"] == dev for b in bays):
                    for slot in slots.group(1).split("/") if slots.re.pattern.startswith("Slots") else slots.groups():
                        bays.append({"id": len(bays) + 1, "device": {"id": ids[dev], "name": dev},
                                     "name": f"Slot {slot}" if len(slot) == 1 else slot, "position": slot,
                                     "installed_module": None})
                for word in cols.get("OTHER", "").split(" · "):
                    if PART_NUMBER.match(word) and not any(i["device"]["name"] == dev and i["name"] == word for i in items):
                        item(dev, "other", word)
    # Network-module bays on the C9300s.
    for name, d in devices.items():
        if "9300" not in d["device_type"]["model"]:
            continue
        bay = {"id": len(bays) + 1, "device": {"id": ids[name], "name": name}, "name": "Network Module",
               "position": "1", "installed_module": None}
        bays.append(bay)
        uplink_ports = {p for d, p in ports if d == name} | {t["object"]["name"] for c in cables.values()
                        for side in ("a_terminations", "b_terminations") for t in c.get(side) or []
                        if t["object"]["device"]["name"] == name}
        # An uplink module where the member has uplink ports, the blank cover everywhere else (NetBox
        # records a blank as a module too, so an empty bay means "nobody looked").
        model = "C9300-NM-8X" if any(re.search(r"/1/\d+$", p) for p in uplink_ports) else "C9300-NM-BLANK"
        module = {"id": len(modules) + 1, "device": {"id": ids[name], "name": name},
                  "module_bay": {"id": bay["id"], "name": bay["name"]},
                  "module_type": {"model": model, "part_number": model, "manufacturer": {"name": "Cisco"}},
                  "status": {"value": "active"}, "serial": serial("FOC") if model != "C9300-NM-BLANK" else "",
                  "asset_tag": None, "description": ""}
        modules.append(module)
        bay["installed_module"] = {"id": module["id"]}
    return modules, bays, items


def wireless(root, devices, ids, interfaces, vlans, prefixes):
    """Wireless LANs, radio interfaces, AP uplinks and the wireless links the template's lines name."""
    by_vid = {v["vid"]: v for v in vlans}
    # Two VLANs the SSIDs need that the zone tables do not list yet.
    for vid, name, zone, subnet in ((365, "OT-IOT", "zone-ot-ops", "10.101.65.0/24"),
                                    (131, "WH-SCAN", "zone-it-ent", "10.1.32.0/24")):
        if vid not in by_vid:
            v = {"id": len(vlans) + 1, "vid": vid, "name": name, "role": None, "tags": [{"slug": zone, "name": zone}]}
            vlans.append(v)
            by_vid[vid] = v
            prefixes.append({"id": len(prefixes) + 1, "prefix": subnet, "vlan": {"id": v["id"], "vid": vid},
                             "vrf": {"name": "OT-OPS"} if zone == "zone-ot-ops" else None})
    group = {"id": 1, "name": "S01-WLAN", "slug": "s01-wlan"}
    wlans = []
    for n, (ssid, vid, auth, cipher, security, eap, switching, bands, isolation, portal, note, scope) in enumerate(WLANS):
        v = by_vid[vid]
        cf = {"wlan_security": security, "wlan_switching": switching, "wlan_bands": bands}
        if eap:
            cf["wlan_eap"] = eap
        if isolation is not None:
            cf["wlan_client_isolation"] = isolation
        if portal:
            cf["wlan_portal"] = portal
        w = {"id": n + 1, "ssid": ssid, "group": group, "vlan": {"id": v["id"], "vid": vid, "name": v["name"]},
             "auth_type": {"value": auth, "label": {"open": "Open", "wpa-personal": "WPA Personal",
                                                    "wpa-enterprise": "WPA Enterprise"}[auth]},
             "auth_cipher": {"value": cipher, "label": cipher.upper()} if cipher else None,
             "status": {"value": "active", "label": "Active"}, "description": note, "custom_fields": cf,
             "tags": []}
        if scope:
            w.update(scope_type="dcim.location", scope={"name": scope, "slug": slug(scope)})
        wlans.append(w)
    wlan_id = {w["ssid"]: w["id"] for w in wlans}

    seen = {(i["device"]["name"], i["name"]): i for i in interfaces}

    def iface(dev, name, kind, **extra):
        key = (dev, name)
        if key in seen:
            seen[key].update(extra)
            return seen[key]
        i = {"id": len(interfaces) + 1, "device": {"id": ids[dev], "name": dev}, "name": name,
             "type": {"value": kind}, "enabled": True, "lag": None, "mode": None, "untagged_vlan": None,
             "tagged_vlans": [], "description": "", "vrf": None, **extra}
        interfaces.append(i)
        seen[key] = i
        return i

    for name, d in devices.items():
        role = d["role"]["slug"]
        if role == "access-point":
            model = d["device_type"]["model"]
            iface(name, "GigabitEthernet0", "2.5gbase-t" if model.startswith("CW") else "1000base-t",
                  poe_mode={"value": "pd", "label": "PD"},
                  poe_type={"value": "type3-ieee802.3bt", "label": "802.3bt (Type 3)"} if model.startswith("CW")
                  else {"value": "type2-ieee802.3at", "label": "802.3at (Type 2)"})
            carried = next((v for k, v in CARRIES.items() if name.startswith(k)), [])
            lans = [{"id": wlan_id[s], "ssid": s} for s in carried]
            iface(name, "radio0", "ieee802.11ax", rf_role={"value": "ap"}, wireless_lans=lans,
                  rf_channel={"value": "2.4g-1-2412-22", "label": "1 (2412 MHz)"})
            iface(name, "radio1", "ieee802.11ax", rf_role={"value": "ap"}, wireless_lans=lans,
                  rf_channel={"value": "5g-36-5180-20", "label": "36 (5180/20 MHz)"})
        elif role == "workgroup-bridge":
            iface(name, "GigabitEthernet0", "1000base-t")
    for (dev, port), rf in RADIOS.items():
        kind = ("ieee802.11ad" if rf["rf_channel"].startswith("60g")      # NetBox's type for 60 GHz
                else "ieee802.11ax" if "radio" in port else "ieee802.11ac")
        fields = {k: ({"value": v, "label": channel_label(v)} if k == "rf_channel"
                      else {"value": v} if k == "rf_role" else v) for k, v in rf.items()}
        iface(dev, port, kind, **fields)["type"] = {"value": kind}   # also when drawn on an earlier sheet

    links = []
    for obj in root.iter("object"):
        a = obj.attrib
        if a.get("object") != "wireless.wirelesslink" or "‹" in a.get("ssid", "") or ":" not in a.get("interface_a", ""):
            continue
        if any(l["ssid"] == a["ssid"] for l in links):
            continue

        def end(text):
            dev, port = text.split(":", 1)
            i = iface(dev, port, "ieee802.11ax")
            return {"id": i["id"], "name": port, "device": {"id": ids[dev], "name": dev}}

        links.append({"id": len(links) + 1, "ssid": a["ssid"], "status": {"value": a.get("status", "connected")},
                      "interface_a": end(a["interface_a"]), "interface_b": end(a["interface_b"]),
                      "auth_type": {"value": a.get("auth_type", "")} if a.get("auth_type") else None,
                      "auth_cipher": {"value": a.get("auth_cipher", "")} if a.get("auth_cipher") else None,
                      "distance": float(a["distance"]) if a.get("distance", "").replace(".", "").isdigit() else None,
                      "distance_unit": {"value": a.get("distance_unit") or "m"}, "description": ""})
    return links, wlans


if __name__ == "__main__":
    main()
