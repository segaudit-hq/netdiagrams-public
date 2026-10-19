"""Grow the fictional Plant A export into a site of any size, for testing layouts.

    python scripts/make_site.py starter -o starter.json # day one: 10 devices, gaps in the data
    python scripts/make_site.py small  -o small.json    # about 10 devices
    python scripts/make_site.py medium -o medium.json   # about 300
    python scripts/make_site.py large  -o large.json    # about 3,000
    python scripts/make_site.py edges  -o edges.json    # Plant A with the NetBox data that trips drawings up

Every added device is a copy of a Plant A device of the same kind, with its
own name, serial, location, zone tag and a cable to the switch above it.
"""

from __future__ import annotations

import argparse
import copy
import json
from importlib import resources

PROFILES = {
    #         IDFs, stack, office APs, cells, IE/cell, PLC, HMI, IO, OT APs
    "small": None,
    "starter": None,
    "edges": None,
    "medium": dict(idfs=6, stack=3, aps=60, cells=8, ie=3, plc=8, hmi=4, io=12, ot_aps=12),
    "large": dict(idfs=20, stack=3, aps=300, cells=40, ie=3, plc=20, hmi=10, io=30, ot_aps=50),
}
SMALL = {"S01-FW-EDGE-01", "S01-IT-CORE-1", "S01-IT-ACC-IDF1-1", "S01-FW-ITOT-01", "S01-OT-CORE-1",
         "S01-C01-IE01", "S01-C01-PLC01", "S01-C01-HMI01", "S01-SIS-SW01", "S01-AP-OF-01"}


def _sample() -> dict:
    return json.loads(resources.files("netdiagrams").joinpath("data/sample-plant-a.json").read_text())


def _subset(export: dict, names: set[str]) -> dict:
    out = copy.deepcopy(export)
    out["devices"] = [d for d in export["devices"] if d["name"] in names]
    ids = {d["id"] for d in out["devices"]}
    ends = lambda c: c.get("a_terminations", []) + c.get("b_terminations", [])
    out["cables"] = [c for c in export["cables"]
                     if ends(c) and all(t["object"]["device"]["id"] in ids for t in ends(c))]
    out["interfaces"] = [i for i in export["interfaces"] if i["device"]["name"] in names]
    out["ip_addresses"] = [i for i in export["ip_addresses"]
                           if ((i.get("assigned_object") or {}).get("device") or {}).get("name") in names]
    return out


class Grower:
    def __init__(self, export: dict):
        self.e = export
        self.by_name = {d["name"]: d for d in export["devices"]}
        self.next_id = max(d["id"] for d in export["devices"]) + 1
        self.next_cable = max(c["id"] for c in export["cables"]) + 1

    def device(self, like: str, name: str, location: str | None = None, zone: str | None = None,
               chassis: str | None = None) -> dict:
        if name in self.by_name:
            return self.by_name[name]
        d = copy.deepcopy(self.by_name[like])
        d.update(id=self.next_id, name=name, serial=f"SN{self.next_id:06d}")
        if d.get("primary_ip4"):
            d["primary_ip4"] = {"address": f"10.{100 + self.next_id // 62500}.{self.next_id // 250 % 250}."
                                           f"{self.next_id % 250 + 2}/24"}
        if location:
            d["location"] = {"name": location, "slug": location.lower().replace(" ", "-")}
        if zone:
            d["tags"] = [{"name": zone, "slug": zone}]
        if chassis:
            d["virtual_chassis"] = {"name": chassis}
        self.next_id += 1
        self.e["devices"].append(d)
        self.by_name[name] = d
        return d

    def cable(self, a: dict, aport: str, b: dict, bport: str, kind: str = "cat6") -> None:
        term = lambda d, p: [{"object_type": "dcim.interface", "object": {"name": p, "device": {
            "id": d["id"], "name": d["name"]}}}]
        self.e["cables"].append({"id": self.next_cable, "label": f"S01-CBL-{self.next_cable:05d}",
                                 "type": kind, "status": {"value": "connected"},
                                 "a_terminations": term(a, aport), "b_terminations": term(b, bport)})
        self.next_cable += 1

    def cell_vlans(self, cell: int, gateway: dict) -> None:
        """Control, I/O and transit VLANs of a new cell, with their prefixes and gateways.

        Cells 1-8 follow the template's standard (VLAN 5n0 / 5n1 / 5n9). The
        standard stops at 8 cells, so larger sites use 1nn0 / 1nn1 / 1nn9 and
        10.102.0.0/16 here, which is only a proposal.
        """
        c, zone = f"C{cell:02d}", f"zone-cell{cell:02d}"
        base = 500 + cell * 10 if cell <= 8 else 1000 + cell * 10
        if cell <= 8:
            ctrl, io = f"10.101.{100 + cell * 10}.0/24", f"10.101.{101 + cell * 10}.0/24"
            transit = f"10.101.252.{64 + 8 * (cell - 1)}/29"
        else:
            ctrl, io = f"10.102.{cell * 2}.0/24", f"10.102.{cell * 2 + 1}.0/24"
            transit = f"10.101.253.{8 * (cell - 9)}/29"
        next_id = max(v["id"] for v in self.e["vlans"]) + 1
        next_prefix = max(p["id"] for p in self.e["prefixes"]) + 1
        next_ip = max(i["id"] for i in self.e["ip_addresses"]) + 1
        for k, (vid, name, prefix, vrf) in enumerate(((base, f"{c}-CTRL", ctrl, f"CELL{cell:02d}"),
                                                      (base + 1, f"{c}-IO", io, f"CELL{cell:02d}"),
                                                      (base + 9, f"TR-{c}", transit, None))):
            vid_id = next_id + k
            self.e["vlans"].append({"id": vid_id, "vid": vid, "name": name, "role": None,
                                    "tags": [{"slug": zone, "name": zone}]})
            self.e["prefixes"].append({"id": next_prefix + k, "prefix": prefix, "vlan": {"id": vid_id, "vid": vid},
                                       "vrf": {"name": vrf} if vrf else None})
            if vrf:
                self.e["ip_addresses"].append({"id": next_ip + k, "address": prefix.replace(".0/24", ".1/24"),
                                               "assigned_object": {"name": f"Vlan{vid}", "device": {
                                                   "id": gateway["id"], "name": gateway["name"]}}})


def _starter(export: dict) -> dict:
    """A site on day one: some serials, addresses, racks and cable labels not collected yet,
    a few names off the standard, and only the core's VLANs entered."""
    by_name = {d["name"]: d for d in export["devices"]}
    for name in ("S01-C01-PLC01", "S01-C01-HMI01", "S01-AP-OF-01", "S01-SIS-SW01"):
        by_name[name]["serial"] = ""
    for name in ("S01-C01-IE01", "S01-SIS-SW01"):
        by_name[name]["primary_ip4"] = None
    for name in ("S01-C01-IE01", "S01-AP-OF-01"):
        by_name[name]["location"] = by_name[name]["rack"] = None
    renames = {"S01-IT-ACC-IDF1-1": "idf1-sw1", "S01-C01-PLC01": "Line1_PLC"}
    for old, new in renames.items():
        by_name[old]["name"] = new
    for c in export["cables"]:
        for t in c.get("a_terminations", []) + c.get("b_terminations", []):
            dev = t["object"]["device"]
            dev["name"] = renames.get(dev["name"], dev["name"])
    for i in export["interfaces"]:
        i["device"]["name"] = renames.get(i["device"]["name"], i["device"]["name"])
    for c in export["cables"][:3]:
        c["label"] = ""
    for c in export["cables"][3:5]:
        c["type"] = ""
    keep = {v["id"] for v in export["vlans"] if v["vid"] in (110, 150, 310, 510, 511, 519)}
    export["vlans"] = [v for v in export["vlans"] if v["id"] in keep]
    export["prefixes"] = [p for p in export["prefixes"] if _get_vid(p) in (110, 310, 510)]
    export["wireless_links"] = []
    return export


def _get_vid(prefix: dict):
    return (prefix.get("vlan") or {}).get("vid")


def _iface(export: dict, device: str, name: str) -> dict:
    for i in export["interfaces"]:
        if i["device"]["name"] == device and i["name"] == name:
            return i
    by_name = {d["name"]: d for d in export["devices"]}
    i = {"id": max(x["id"] for x in export["interfaces"]) + 1, "name": name, "type": {"value": "10gbase-x-sfpp"},
         "device": {"id": by_name[device]["id"], "name": device}, "enabled": True}
    export["interfaces"].append(i)
    return i


def _edges(export: dict) -> dict:
    """Plant A with the NetBox data real plants have and the template doesn't expect.

    A spare on the shelf and a planned and an offline switch; a core uplink
    patched through a panel; an HSRP gateway; a dual-stack VLAN; a VLAN from a
    region group, and a group copy of a VLAN the site has itself; two cables
    both labelled "1"; a 4-way breakout; an unnamed PLC; a switch known only by
    its out-of-band address; a wireless LAN; and data exported months ago.
    """
    e = export
    by_name = {d["name"]: d for d in e["devices"]}
    dev = lambda n: {"id": by_name[n]["id"], "name": n}
    term = lambda n, port, kind="dcim.interface": [{"object_type": kind, "object": {"name": port, "device": dev(n)}}]
    next_id = max(d["id"] for d in e["devices"]) + 1
    next_cable = max(c["id"] for c in e["cables"]) + 1
    e["exported_at"] = "2026-04-01T08:00:00+00:00"

    # Status: a spare core switch, the OOB switch back on the shelf, a planned and an offline switch.
    spare = copy.deepcopy(by_name["S01-OT-CORE-1"])
    spare.update(id=next_id, name="S01-OT-CORE-SPARE", status={"value": "inventory"}, virtual_chassis=None)
    e["devices"].append(spare)
    by_name["S01-OOB-SW-01"]["status"] = {"value": "inventory"}
    by_name["S01-IT-ACC-IDF1-2"]["status"] = {"value": "planned"}
    by_name["S01-SIS-SW01"]["status"] = {"value": "offline"}
    e["cables"] = [c for c in e["cables"] if "S01-OOB-SW-01" not in json.dumps(c)]

    # Patch panel: IDF1-1 Te1/1/1 → panel front 1 → rear 1 → IT-CORE-1 Twe1/0/13.
    panel = {"id": next_id + 1, "name": "S01-PP-MDF-01", "role": {"name": "Patch panel", "slug": "patch-panel"},
             "device_type": {"model": "24-port LC panel"}, "status": {"value": "active"}, "tags": []}
    e["devices"].append(panel)
    by_name[panel["name"]] = panel
    old = next(c for c in e["cables"] if c["label"] == "S01-CBL-018")
    at = e["cables"].index(old)
    front = {"object_type": "dcim.frontport", "object": {"name": "1", "device": dev(panel["name"])}}
    rear = {"object_type": "dcim.rearport", "object": {"name": "R1", "device": dev(panel["name"])}}
    e["cables"][at:at + 1] = [
        {**old, "a_terminations": term("S01-IT-ACC-IDF1-1", "TenGigabitEthernet1/1/1"), "b_terminations": [front]},
        {**old, "id": next_cable, "label": "S01-CBL-018B", "a_terminations": [rear],
         "b_terminations": term("S01-IT-CORE-1", "TwentyFiveGigE1/0/13")},
    ]
    for (a, aport, b, bport, cable, peer) in (
            ("S01-IT-ACC-IDF1-1", "TenGigabitEthernet1/1/1", "S01-IT-CORE-1", "TwentyFiveGigE1/0/13", old, front),
            ("S01-IT-CORE-1", "TwentyFiveGigE1/0/13", "S01-IT-ACC-IDF1-1", "TenGigabitEthernet1/1/1",
             {"id": next_cable, "label": "S01-CBL-018B"}, rear)):
        i = _iface(e, a, aport)
        i.update(cable={"id": cable["id"], "label": cable["label"]}, link_peers_type=peer["object_type"],
                 link_peers=[peer["object"]], connected_endpoints_type="dcim.interface",
                 connected_endpoints=[{"name": bport, "device": dev(b)}])

    # Gateways: an HSRP address for VLAN 110, and the VLAN dual-stacked.
    vlan110 = next(v for v in e["vlans"] if v["vid"] == 110)
    e["ip_addresses"] += [
        {"id": 9001, "address": "10.1.10.254/24", "role": {"value": "hsrp"},
         "assigned_object": {"id": 1, "protocol": "hsrp", "group_id": 10}},
        {"id": 9002, "address": "2001:db8:110::1/64",
         "assigned_object": {"name": "Vlan110", "device": dev("S01-IT-CORE-1")}},
    ]
    e["prefixes"].append({"id": 9001, "prefix": "2001:db8:110::/64", "vlan": {"id": vlan110["id"], "vid": 110},
                          "vrf": {"name": "CORP"}})

    # VLANs from wider groups: a new OT VLAN only in the region's group, and a copy of 120.
    for v in e["vlans"]:
        v["site"] = {"id": 1, "slug": "S01"}
    e["vlans"] += [
        {"id": 9001, "vid": 360, "name": "OT-HISTORIAN", "group": {"name": "Region OT", "slug": "region-ot"},
         "tags": [{"slug": "zone-ot-ops", "name": "zone-ot-ops"}]},
        {"id": 9002, "vid": 120, "name": "VOICE-GLOBAL", "group": {"name": "Region IT", "slug": "region-it"},
         "tags": [{"slug": "zone-it-ent", "name": "zone-it-ent"}]},
    ]
    e["prefixes"].append({"id": 9002, "prefix": "10.101.60.0/24", "vlan": {"id": 9001, "vid": 360},
                          "vrf": {"name": "OT-OPS"}})

    # Two cables labelled "1" (cabinet-local numbering) and a 4-way breakout.
    e["cables"] += [
        {"id": next_cable + 1, "label": "1", "type": "cat6", "status": {"value": "connected"},
         "a_terminations": term("S01-WLC-01", "GigabitEthernet0/0/1"),
         "b_terminations": term("S01-OT-CORE-1", "GigabitEthernet1/0/40")},
        {"id": next_cable + 2, "label": "1", "type": "cat6", "status": {"value": "connected"},
         "a_terminations": term("S01-WLC-01", "GigabitEthernet0/0/2"),
         "b_terminations": term("S01-OT-CORE-2", "GigabitEthernet2/0/40")},
        {"id": next_cable + 3, "label": "S01-CBL-BRK", "type": "dac-passive", "status": {"value": "connected"},
         "a_terminations": term("S01-IT-CORE-1", "HundredGigE1/0/49"),
         "b_terminations": term("S01-FW-EDGE-01", "ethernet1/21") + term("S01-FW-EDGE-01", "ethernet1/22")
         + term("S01-FW-EDGE-01", "ethernet1/23") + term("S01-FW-EDGE-01", "ethernet1/24")},
    ]

    # An unnamed PLC in cell 1, and a cell switch known only by its OOB address.
    plc = copy.deepcopy(by_name["S01-C01-PLC01"])
    plc.update(id=next_id + 2, name=None, serial="")
    e["devices"].append(plc)
    by_name["S01-C01-IE01"].update(primary_ip4=None, oob_ip={"address": "10.1.99.77/24"})

    # The OT wireless LAN on VLAN 350.
    vlan350 = next(v for v in e["vlans"] if v["vid"] == 350)
    e["wireless_lans"] = [{"id": 1, "ssid": "PLANT-OT", "vlan": {"id": vlan350["id"], "vid": 350},
                           "auth_type": {"value": "wpa-enterprise", "label": "WPA Enterprise"},
                           "auth_cipher": {"value": "aes", "label": "AES"}}]
    return e


def grow(profile: str) -> dict:
    export = _sample()
    if profile == "edges":
        return _edges(export)
    if profile == "starter":
        return _starter(_subset(export, SMALL))
    if PROFILES[profile] is None:
        return _subset(export, SMALL)
    p = PROFILES[profile]
    g = Grower(export)
    it_core = [g.by_name["S01-IT-CORE-1"], g.by_name["S01-IT-CORE-2"]]
    ot_core = [g.by_name["S01-OT-CORE-1"], g.by_name["S01-OT-CORE-2"]]

    # Office: more IDF stacks, each with APs spread over them.
    access = []
    for idf in range(1, p["idfs"] + 1):
        members = [g.device("S01-IT-ACC-IDF1-1", f"S01-IT-ACC-IDF{idf}-{m}", f"IDF-{idf}", "zone-it-ent",
                            f"S01-IT-ACC-IDF{idf}") for m in range(1, p["stack"] + 1)]
        if idf > 2:
            g.cable(members[0], "TenGigabitEthernet1/1/1", it_core[0], f"TwentyFiveGigE1/0/{16 + idf}", "smf-os2")
            g.cable(members[-1], f"TenGigabitEthernet{p['stack']}/1/1", it_core[1],
                    f"TwentyFiveGigE2/0/{16 + idf}", "smf-os2")
        access += members
    for n in range(1, p["aps"] + 1):
        sw = access[(n - 1) % len(access)]
        ap = g.device("S01-AP-OF-01", f"S01-AP-OF-{n:03d}" if n > 5 else f"S01-AP-OF-{n:02d}",
                      sw["location"]["name"], "zone-it-ent")
        if n > 5:
            g.cable(ap, "GigabitEthernet0", sw, f"GigabitEthernet1/0/{(n - 1) // len(access) + 1}")

    # Plant floor: more cells, each a ring of industrial switches with PLCs, HMIs and I/O.
    for cell in range(1, p["cells"] + 1):
        c = f"C{cell:02d}"
        loc, zone = f"Cell{cell:02d} floor", f"zone-cell{cell:02d}"
        ies = [g.device("S01-C01-IE01", f"S01-{c}-IE{k:02d}", loc, zone) for k in range(1, p["ie"] + 1)]
        if cell > 3:
            g.cable(ies[0], "GigabitEthernet1/1", ot_core[0], f"GigabitEthernet1/0/{10 + cell}", "smf-os2")
            g.cable(ies[-1], "GigabitEthernet1/2", ot_core[1], f"GigabitEthernet2/0/{10 + cell}", "smf-os2")
            for a, b in zip(ies, ies[1:]):
                g.cable(a, "GigabitEthernet1/2", b, "GigabitEthernet1/1")
        for kind, like, count in (("PLC", "S01-C01-PLC01", p["plc"]), ("HMI", "S01-C01-HMI01", p["hmi"]),
                                  ("IO", "S01-C01-IO01", p["io"])):
            for n in range(1, count + 1):
                name = f"S01-{c}-{kind}{n:02d}"
                if name in g.by_name:
                    continue
                d = g.device(like, name, loc, zone)
                sw = ies[(n - 1) % len(ies)]
                g.cable(d, "eth0", sw, f"GigabitEthernet1/{4 + (n - 1) // len(ies)}")
        if cell > 3:
            g.cell_vlans(cell, ot_core[0])
    for n in range(1, p["ot_aps"] + 1):
        name = f"S01-AP-OT-{n:02d}"
        if name not in g.by_name:
            g.device("S01-AP-OT-01", name, "Production hall", "zone-ot-mgmt")
    return export


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("profile", choices=PROFILES)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    export = grow(args.profile)
    with open(args.output, "w") as f:
        json.dump(export, f)
    print(f"{args.output}: {len(export['devices'])} devices, {len(export['cables'])} cables")


if __name__ == "__main__":
    main()
