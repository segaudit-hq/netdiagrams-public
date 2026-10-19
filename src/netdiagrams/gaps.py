"""Data gaps: draw what NetBox has, and say on the page what is missing and how to get it.

Few sites have every serial, cable label and subnet in NetBox on day one. The
drawing still gets made from what is there; a missing field shows as an amber
"?" on the shape, and each page gets a "Plan to improve this page" card listing
what is missing for that page, how many, how to collect it, where it goes in
NetBox and which collection worksheet to use. When nothing is missing, the
card says so in one line, so the reader knows it was checked.
"""

from __future__ import annotations

import html
import ipaddress
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .graph import Graph, cell_of, plain
from . import audit, hardware, intake, profiles, wireless
from .model import _get

LAYER = "Plan to improve (data gaps)"
MISSING = '<font color="#B45309"><b>?</b></font>'

# The free data collection worksheets (netdiagrams.com/worksheets), by their IDs.
WORKSHEETS = {
    "zones": "WS-01 Site, areas, zones",
    "devices": "WS-02 Network devices",
    "vlans": "WS-03 VLANs, subnets",
    "cables": "WS-04 Links, cables, optics",
    "wireless": "WS-06 Wireless",
    "sites": "WS-07 Outside connections",
    "flows": "WS-08 Flows",
    "naming": "WS-10 Name crosswalk",
    "audit": "WS-12 Audit evidence",
    "models": "WS-02 Network devices (models)",
}
GAPS_REGISTER = "WS-11 gaps register"


@dataclass
class Gap:
    key: str
    what: str
    how: str
    where: str
    worksheet: str
    names: list[str] = field(default_factory=list)
    always: bool = False          # a standing reminder, not a count

    @property
    def count(self) -> str:
        return "—" if self.always else str(len(self.names))


def model_names(devices: list[dict], eos) -> list[str]:
    """The models (manufacturer and model) of these devices that none of them has an end-of-support date for."""
    models: dict[str, bool] = {}
    for d in devices:
        model = _get(d, "device_type", "model")
        if model:
            key = " ".join(x for x in (_get(d, "device_type", "manufacturer", "name"), model) if x)
            models[key] = models.get(key, False) or bool(eos(d))
    return sorted(k for k, dated in models.items() if not dated)


# Which gaps each page lists, by page id.
PAGES = {
    "glance": ["no_zone", "no_location", "dup_serial", "dup_ip", "past_support", "no_criticality", "template_examples"],
    "logical": ["no_vlans", "vlan_no_prefix", "prefix_no_zone", "svi_outside_prefix", "template_examples"],
    "physical": ["no_zone", "bad_name", "no_name", "no_ip", "no_serial", "dup_serial", "dup_ip", "dup_asset_tag",
                 "no_location", "no_cables", "cable_no_label", "cable_label_twice", "cable_no_type",
                 "trunk_no_vlans", "past_support", "no_criticality", "template_examples"],
    "physical-registers": ["no_serial", "dup_serial", "dup_ip", "no_location", "trunk_no_vlans"],
    "hardware": ["past_support", "model_no_eos", "no_serial", "module_no_serial", "item_no_serial", "fibre_no_optic",
                 "cable_no_type", "cable_no_label", "cable_label_twice", "template_examples"],
    "wireless": ["no_wlans", "wlan_no_vlan", "wlan_no_fields", "wlan_no_manager", "ap_no_cable", "ap_no_location",
                 "no_wireless_links", "wlink_bad_ends", "wgb_no_link", "wlan_review_open", "wlan_review_psk",
                 "wlan_guest_controls", "template_examples"],
    "wireless-registers": ["ap_no_cable", "ap_no_location", "wlan_no_fields"],
    "audit": ["no_owner", "stale_backup", "stale_patch", "stale_verified", "support_ended", "not_monitored",
              "no_log_forwarding", "no_physical_access", "past_support", "model_no_eos", "audit_bad_values",
              "no_criticality"],
    "flows": ["flows_not_in_netbox"],
    "register": ["flows_not_in_netbox", "bad_name"],
    "multisite": ["one_site"],
    "failover": [],
    "platforms": [],
    "netbox": [],
}

NAME = re.compile(r"^[A-Z]\d{2}-[A-Z0-9]+(-[A-Z0-9]+)*$")


def naming_pattern(naming: dict) -> str:
    """The naming standard in force: the site's own, else the profile's, else S01's."""
    pattern = naming.get("pattern") or NAME.pattern
    return profiles.current().naming or pattern if pattern == NAME.pattern else pattern


def no_zone_fix() -> str:
    """What closes the zone gap, in the profile's words (Purdue levels only where they apply)."""
    words = profiles.current().words
    if "no_zone_fix" in words:
        return words["no_zone_fix"]
    return profiles.word("no_zone_fix") if profiles.current().levels else "Agree each area's zone with whoever owns it"


def svis_outside_prefix(export: dict) -> list[str]:
    """``device Vlan399 10.0.0.65/29 (VLAN 399 is 10.0.0.32/29)`` for each SVI whose address no prefix of its VLAN holds.

    An SVI is an interface named ``Vlan<N>`` (or ``vlan<N>``, ``irb.<N>``, ``bdi<N>``). A VLAN with no prefix
    in NetBox is the ``vlan_no_prefix`` gap, not this one.
    """
    by_vid: dict[int, list] = {}
    for p in export.get("prefixes", []):
        vid = _get(p, "vlan", "vid", default=None)
        try:
            if vid is not None:
                by_vid.setdefault(int(vid), []).append(ipaddress.ip_network(p.get("prefix", ""), strict=False))
        except ValueError:
            continue
    out = []
    for a in export.get("ip_addresses", []):
        assigned = a.get("assigned_object") or {}
        m = re.fullmatch(r"(?:vlan|irb\.|bdi)(\d+)", (assigned.get("name") or "").lower())
        if not m or int(m.group(1)) not in by_vid:
            continue
        try:
            ip = ipaddress.ip_interface(a.get("address", "")).ip
        except ValueError:
            continue
        nets = by_vid[int(m.group(1))]
        if not any(ip in n for n in nets):
            device = (assigned.get("device") or {}).get("name") or "?"
            out.append(f"{device} {assigned.get('name')} {a.get('address')} "
                       f"(VLAN {m.group(1)} is {' · '.join(str(n) for n in nets)})")
    return out


def find(export: dict, endpoint_roles: set[str], zone_of, today: str = "") -> dict[str, Gap]:
    """Every gap in the export, keyed by check."""
    devices = [d for d in export.get("devices", []) if d.get("name")]
    infra = [d for d in devices if _get(d, "role", "slug") not in endpoint_roles]
    cables = export.get("cables", [])
    cabled = {t["object"]["device"].get("name") for c in cables
              for t in (c.get("a_terminations") or []) + (c.get("b_terminations") or [])
              if (t.get("object") or {}).get("device")}
    vlans, prefixes = export.get("vlans", []), export.get("prefixes", [])
    with_prefix = {_get(p, "vlan", "id", default=None) for p in prefixes}
    aps = [d for d in devices if _get(d, "role", "slug") == "access-point"]
    wx = wireless.Index(export, endpoint_roles)
    wgaps = wireless.gaps_for(wx, endpoint_roles)
    sites = {_get(d, "site", "slug") for d in devices}
    chassis = {d["name"]: _get(d, "virtual_chassis", "name") for d in devices if d.get("virtual_chassis")}
    radios = {d["name"] for d in devices if _get(d, "role", "slug") == "ptp-radio"}
    linked = {n for w in export.get("wireless_links") or [] for side in ("interface_a", "interface_b")
              for n in [_get(w, side, "device", "name")] if n}
    linked |= {a for c in cables for a, b in [_ends(c)] if a in radios and b in radios}
    linked |= {b for c in cables for a, b in [_ends(c)] if a in radios and b in radios}
    dev = WORKSHEETS["devices"]
    hw = hardware.Hardware(export)
    info = intake.intake(export)
    naming = info.settings.get("naming") or {}
    pattern = re.compile(naming_pattern(naming))
    example = "SITE-ROLE-NN, e.g. S01-OT-CORE-1" if pattern.pattern == NAME.pattern else f"the site's standard ({pattern.pattern})"
    eos = lambda d: str((d.get("custom_fields") or {}).get("end_of_support") or "")[:10]
    gaps = [
        Gap("no_zone", "Devices without a zone", no_zone_fix(),
            "Device ▸ Tags (zone-…)", WORKSHEETS["zones"], [d["name"] for d in devices if not zone_of(d)]),
        Gap("bad_name", "Names off the naming standard", f"Rename to {example}",
            "Device ▸ Name", WORKSHEETS["naming"],
            [d["name"] for d in devices if not pattern.match(d["name"]) and d["name"] not in info.unnamed]),
        Gap("past_support", "Devices past end of support", "Plan the replacement, or record the extended contract",
            "Device type ▸ End of support (custom field; a device's own date overrides it)", dev,
            [d["name"] for d in devices if today and eos(d) and eos(d) < today]),
        Gap("model_no_eos", "Network models with no end-of-support date",
            "From the vendor's end-of-life notice; one entry on the device type covers every device of that model",
            "Device type ▸ End of support (custom field)", WORKSHEETS["models"], model_names(infra, eos)),
        Gap("no_ip", "Network gear without a mgmt IP", "From the device's management interface or the IPAM list",
            "Device ▸ Primary IPv4 (or OOB IP)", dev,
            [d["name"] for d in infra if not _get(d, "primary_ip4", "address") and not _get(d, "oob_ip", "address")
             and not d.get("virtual_chassis")]),
        Gap("no_name", "Devices with no name in NetBox", "Read the hostname or the asset label; name it to the standard",
            "Device ▸ Name", WORKSHEETS["naming"], list(info.unnamed)),
        Gap("no_serial", "Devices without a serial number", "Chassis label, or 'show inventory' on the device",
            "Device ▸ Serial number", dev, [d["name"] for d in devices if not d.get("serial")]),
        Gap("no_criticality", "Devices without an asset criticality",
            "Rate it with the asset owner: critical, high, medium or low (what stops when it fails)",
            "Device ▸ Asset criticality (custom field)", dev,
            [d["name"] for d in devices if not (d.get("custom_fields") or {}).get("criticality")]),
        Gap("no_location", "Devices without a room or rack", "Walk the room: building, room, rack and U",
            "Device ▸ Location, Rack", dev,
            [d["name"] for d in infra if not _get(d, "location", "name") and not _get(d, "rack", "name")]),
        Gap("no_cables", "Network gear with no cable recorded", "Trace uplinks: LLDP/CDP neighbors, then follow the cable",
            "Cables ▸ Add", WORKSHEETS["cables"], [d["name"] for d in infra if d["name"] not in cabled]),
        Gap("cable_no_label", "Cables without a label", "Read both ends; label unlabeled cables with the next number",
            "Cable ▸ Label", WORKSHEETS["cables"], [_cable_name(c) for c in cables if not c.get("label")]),
        Gap("cable_label_twice", "Cable labels used on more than one cable",
            "Relabel so every cable on the site has its own number (prefix with the cabinet)",
            "Cable ▸ Label", WORKSHEETS["cables"], [f"{label} ×{n}" for label, n in info.duplicate_labels.items()]),
        Gap("cable_no_type", "Cables without a media type", "Jacket print and optic part number at each end",
            "Cable ▸ Type", WORKSHEETS["cables"], [_cable_name(c) for c in cables if not c.get("type") and not _stack_cable(c, chassis)]),
        Gap("no_vlans", "No VLANs in NetBox", "Export the VLAN list from each core and routed switch",
            "IPAM ▸ VLANs", WORKSHEETS["vlans"], always=not vlans),
        Gap("vlan_no_prefix", "VLANs without a subnet", "SVI or firewall subinterface address on the gateway",
            "Prefix ▸ VLAN", WORKSHEETS["vlans"],
            [f"{v.get('vid')} {v.get('name', '')}" for v in vlans if v.get("id") not in with_prefix]),
        Gap("prefix_no_zone", "Subnets without a zone", "Name the zone that owns each routed subnet",
            "Prefix ▸ VRF, or VLAN ▸ Tags", WORKSHEETS["zones"],
            [p.get("prefix", "") for p in prefixes if not p.get("vrf") and not _get(p, "vlan", "id", default=None)]),
        Gap("ap_no_cable", "Access points without a switch port", "Switch MAC/LLDP table, or the controller's AP list",
            "Cable from AP to switch port", WORKSHEETS["wireless"],
            [d["name"] for d in aps if d["name"] not in cabled and not wx.is_radio_fed(d["name"])]),
        Gap("no_wlans", "Access points but no SSIDs in NetBox", "One wireless LAN per SSID: name, auth, VLAN, scope",
            "Wireless ▸ Wireless LANs", WORKSHEETS["wireless"], wgaps["no_wlans"]),
        Gap("wlan_no_vlan", "SSIDs without a VLAN (no zone, no subnet)", "The VLAN the SSID's clients land in",
            "Wireless LAN ▸ VLAN", WORKSHEETS["wireless"], wgaps["wlan_no_vlan"]),
        Gap("wlan_no_fields", "SSIDs without switching, bands or broadcast area recorded",
            "Controller or dashboard: where traffic is switched, which bands, which APs carry it",
            "Wireless LAN ▸ Switching, Bands (custom fields); AP radio ▸ Wireless LANs", WORKSHEETS["wireless"],
            wgaps["wlan_no_fields"]),
        Gap("ap_no_location", "Access points without a room or floor", "The controller's AP list or the survey map",
            "Device ▸ Location", WORKSHEETS["wireless"], wgaps["ap_no_location"]),
        Gap("wlan_no_manager", "APs with no controller or cloud manager recorded",
            "How are the APs managed? Controller, cloud dashboard, firewall or embedded",
            "Site ▸ Wireless management, or AP ▸ Wireless controller", WORKSHEETS["wireless"],
            wgaps["wlan_no_manager"]),
        Gap("wlan_review_open", "Open or OWE SSIDs outside a guest zone (check)",
            "Confirm the SSID is meant to be open, and that its VLAN is the guest zone",
            "Wireless LAN ▸ VLAN, or Auth type", WORKSHEETS["wireless"], wgaps["wlan_review_open"]),
        Gap("wlan_review_psk", "Shared-key SSIDs on staff or management zones (check)",
            "Confirm who holds the key and when it rotates; move staff devices to 802.1X where possible",
            "Wireless LAN ▸ Auth type", WORKSHEETS["wireless"], wgaps["wlan_review_psk"]),
        Gap("wlink_bad_ends", "Wireless links to interfaces that aren't in NetBox",
            "Add the radio interface on each device, then point the link at it",
            "Device ▸ Interfaces (radio)", WORKSHEETS["wireless"], wgaps["wlink_bad_ends"]),
        Gap("wgb_no_link", "Workgroup bridges with no association recorded",
            "The AP and SSID the bridge joins: a wireless link from its radio to the AP's",
            "Wireless ▸ Wireless links", WORKSHEETS["wireless"], wgaps["wgb_no_link"]),
        Gap("wlan_guest_controls", "Guest SSIDs without client isolation or a portal recorded",
            "Dashboard or controller: client isolation on, and the portal type",
            "Wireless LAN ▸ Client isolation, Portal (custom fields)", WORKSHEETS["wireless"],
            wgaps["wlan_guest_controls"]),
        Gap("no_wireless_links", "Radios without their link", "Pair each bridge: both radios, band, channel, SSID",
            "Wireless ▸ Wireless links", WORKSHEETS["wireless"], sorted(radios - linked)),
        Gap("flows_not_in_netbox", "Flows are not kept in NetBox",
            "Check every row against the firewall rulebase each quarter", "Flow register (sheet 7)",
            WORKSHEETS["flows"], always=True),
        Gap("one_site", "Other sites not in NetBox yet", "One row per site: name, address plan, platform",
            "Sites, then each site's devices", WORKSHEETS["sites"], always=len(sites) < 2),
        Gap("dup_serial", "One serial number on several devices", "Read the chassis label; a spare keeps its own serial",
            "Device ▸ Serial number", dev, duplicates(devices, lambda d: d.get("serial"))),
        Gap("dup_ip", "One management IP on several devices", "Give each device its own address (a stack has one)",
            "Device ▸ Primary IPv4", dev, duplicates(devices, lambda d: _get(d, "primary_ip4", "address"))),
        Gap("dup_asset_tag", "One asset tag on several devices", "Read the asset label on each unit",
            "Device ▸ Asset tag", dev, duplicates(devices, lambda d: d.get("asset_tag"))),
        Gap("trunk_no_vlans", "Trunks with no tagged VLANs in NetBox", "Allowed-VLAN list from the switch config",
            "Interface ▸ Tagged VLANs", WORKSHEETS["vlans"], trunks_without_vlans(export, endpoint_roles)),
        Gap("svi_outside_prefix", "SVI addresses outside their VLAN's prefix",
            "Check 'show ip interface brief' against the VLAN's prefix; fix the address or the prefix",
            "IP address ▸ Address · Prefix ▸ VLAN", WORKSHEETS["vlans"], svis_outside_prefix(export)),
        Gap("module_no_serial", "Modules without a serial number", "'show inventory' lists each module's serial",
            "Module ▸ Serial number", dev, hw.modules_without_serial()),
        Gap("item_no_serial", "Power supplies, fans and optics without a serial number",
            "'show inventory' on the device, or the part's own label",
            "Inventory item ▸ Serial number", dev, hw.items_without_serial()),
        Gap("fibre_no_optic", "Fiber cable ends with no transceiver recorded",
            "'show inventory' or the optic's label; add it as an inventory item on the interface (role transceiver)",
            "Device ▸ Inventory items ▸ Component", WORKSHEETS["cables"],
            hw.fibre_without_optic(cables, {d.get("id"): d.get("name") for d in devices})),
    ]
    evidence = audit.Evidence(export, info.settings, endpoint_roles)
    texts = audit.gap_texts(evidence.days)
    for key, (names, _) in evidence.checks(today).items():
        what, how, where = texts[key]
        gaps.append(Gap(key, what, how, where, WORKSHEETS["audit"], names))
    return {g.key: g for g in gaps}


def duplicates(devices: list[dict], key) -> list[str]:
    """'value: dev-a, dev-b' for every value two or more devices share."""
    by_value: dict[str, list[str]] = {}
    for d in devices:
        value = key(d)
        if value and not _is_vc_member_sharing_ip(d):
            by_value.setdefault(str(value), []).append(d["name"])
    return [f"{v}: {', '.join(sorted(names))}" for v, names in sorted(by_value.items()) if len(names) > 1]


def _is_vc_member_sharing_ip(d: dict) -> bool:
    return False


def trunks_without_vlans(export: dict, endpoint_roles: set[str]) -> list[str]:
    """Cabled interfaces in tagged mode with no tagged VLAN list, on network gear."""
    infra = {d["name"] for d in export.get("devices", []) if d.get("name")
             and _get(d, "role", "slug") not in endpoint_roles}
    cabled = set()
    for c in export.get("cables", []):
        for t in (c.get("a_terminations") or []) + (c.get("b_terminations") or []):
            obj = t.get("object") or {}
            if (obj.get("device") or {}).get("name"):
                cabled.add((obj["device"]["name"], obj.get("name")))
    out = []
    for i in export.get("interfaces", []):
        dev = _get(i, "device", "name")
        if dev not in infra or (dev, i.get("name")) not in cabled:
            continue
        if _get(i, "mode", "value") == "tagged" and not i.get("tagged_vlans"):
            out.append(f"{dev} {i.get('name')}")
    return sorted(out)


def _ends(c: dict) -> tuple[str, str]:
    name = lambda terms: next((t["object"]["device"].get("name", "") for t in terms or []
                               if (t.get("object") or {}).get("device")), "")
    return name(c.get("a_terminations")), name(c.get("b_terminations"))


def _stack_cable(c: dict, chassis: dict[str, str]) -> bool:
    """A cable between two members of one stack or virtual chassis (NetBox has no cable type for it)."""
    a, b = _ends(c)
    return bool(chassis.get(a)) and chassis.get(a) == chassis.get(b)


def _cable_name(c: dict) -> str:
    ends = [t["object"]["device"].get("name", "?") for t in (c.get("a_terminations") or [])[:1]
            + (c.get("b_terminations") or [])[:1] if (t.get("object") or {}).get("device")]
    return " ⇄ ".join(ends) or f"cable {c.get('id')}"


def template_examples(g: Graph, real: set[str], prefix: str, template: set[str],
                      backed: set[str] | None = None, within: tuple | None = None) -> list[str]:
    """The template's example devices (or their pairs and stacks) still written on this page.

    With ``backed`` (every name NetBox has an object for: devices, cables, circuits, SSIDs), any
    prefixed name on the page that NetBox doesn't back counts, device or not: a controller card,
    a cable label or an SSID the template brought along. With ``within`` (x, y, w, h), only shapes
    inside that box are read.
    """
    if not prefix:
        return []
    pattern = re.compile(r"(?<![A-Z0-9-])" + re.escape(prefix) + r"[A-Z0-9]+(?:-[A-Z0-9]+)*(?![A-Za-z0-9])")
    found = set()
    for el in g.els.values():
        if g.hidden(el.get("id") or ""):
            continue
        if within is not None and not _within(g, el, within):
            continue
        for name in pattern.findall(plain(g.value(el))):
            ours = name in template or any(t.startswith(name + "-") for t in template)
            if ours and name not in real and not any(r.startswith(name + "-") for r in real):
                found.add(name)
            elif backed is not None and not ours and name not in backed \
                    and not any(b.startswith(name + "-") for b in backed):
                found.add(name)
    return sorted(found)


def _within(g: Graph, el, box: tuple) -> bool:
    cell = cell_of(el)
    if cell is None or cell.get("vertex") != "1":
        return False
    x, y, w, h = g.box(el.get("id") or "")
    bx, by, bw, bh = box
    return bx <= x and by <= y and x + w <= bx + bw and y + h <= by + bh


EMPTY_NOTE = '<br><font color="#B45309"><i>Nothing in NetBox here yet</i></font>'


def mark_empty(g: Graph, is_device, template: set[str], real: set[str], prefix: str) -> int:
    """Say so on a zone or group box the template drew but NetBox has nothing in."""
    devices = [g.box(i) for i, el in g.els.items() if is_device(el) and not g.hidden(i)]
    # A plain shape whose label starts with a NetBox device's name (the wireless sheet's controllers) is a device too.
    for i, el in g.els.items():
        cell = cell_of(el)
        if cell is None or cell.get("vertex") != "1" or is_device(el) or g.hidden(i):
            continue
        first = plain(g.value(el)).split(" ")[0] if plain(g.value(el)) else ""
        if first in real:
            devices.append(g.box(i))
    pattern = re.compile(re.escape(prefix) + r"[A-Z0-9]+(?:-[A-Z0-9]+)*") if prefix else None
    marked = 0
    for i, el in list(g.els.items()):
        cell = cell_of(el)
        if (cell is None or cell.get("vertex") != "1" or g.hidden(i) or is_device(el)
                or (cell.get("style") or "").startswith("text")):
            continue
        x, y, w, h = g.box(i)
        if w < 150 or h < 60:
            continue
        text = plain(g.value(el))
        zone_box = g.layer_of(i).startswith("Zones") and text
        example = pattern and any(n not in real and (n in template or any(t.startswith(n + "-") for t in template))
                                  for n in pattern.findall(text) + [el.get("name") or ""])
        if not (zone_box or example) or "Nothing in NetBox" in text or el.get("netdiagrams_wireless_mgmt"):
            continue
        if any(x <= dx and dx + dw <= x + w and y <= dy and dy + dh <= y + h for dx, dy, dw, dh in devices):
            continue
        g.set_value(el, g.value(el) + EMPTY_NOTE)
        marked += 1
        if example and (not zone_box or el.get("name")):
            # the template's gear with no NetBox match: a dashed outline and faded links, so it reads as
            # a slot to fill rather than a switch the site has
            cell.set("style", _faded(cell.get("style") or "") + "dashed=1;dashPattern=4 3;fillColor=none;")
            inside = {i, *g.descendants(i)}
            for edge in g.els.values():
                ec = cell_of(edge)
                if ec is not None and ec.get("edge") == "1" and {ec.get("source"), ec.get("target")} & inside:
                    ec.set("style", _faded(ec.get("style") or "") + "dashed=1;")
    return marked


def _faded(style: str) -> str:
    style = re.sub(r"(^|;)(opacity|textOpacity|dashed|dashPattern)=[^;]*", r"\1", style).replace(";;", ";")
    return (style if style.endswith(";") or not style else style + ";") + "opacity=40;textOpacity=60;"


EXAMPLES = Gap("template_examples", "Template examples still on this page",
               "Replace with the site's own, or delete them", "—", "—")


def example_sheet(word: str, why: str, source: str) -> Gap:
    """The standing row on a sheet that is the template's example, not this site's data."""
    what = f"This sheet is {word.lower()} content: {why}"
    how = f"Filled by {source}" if source else "Keep as reference, or leave the sheet out (--leave-out)"
    return Gap("example_sheet", what, how, "—", WORKSHEETS["flows"] if "flow" in source else "—", always=True)

COLUMNS = [("WHAT'S MISSING", 220), ("COUNT", 50), ("HOW TO COLLECT IT", 440), ("WHERE IT GOES IN NETBOX", 190),
           ("WORKSHEET", 170)]
STYLES = {
    "table": "shape=table;startSize=0;container=1;collapsible=0;childLayout=tableLayout;fixedRows=1;rowLines=0;"
             "fontStyle=0;strokeColor=none;fillColor=none;html=1;",
    "row": "shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;strokeColor=inherit;top=0;left=0;"
           "bottom=0;right=0;collapsible=0;dropTarget=0;fillColor=none;points=[[0,0.5],[1,0.5]];"
           "portConstraint=eastwest;html=1;",
    "head": "shape=partialRectangle;html=1;whiteSpace=wrap;connectable=0;strokeColor=#E2E8F0;fillColor=#FFF7ED;top=0;"
            "left=0;right=0;bottom=1;fontSize=9;fontStyle=1;fontColor=#9A3412;align=left;spacingLeft=4;"
            "fontFamily=Inter;",
    "body": "shape=partialRectangle;html=1;whiteSpace=wrap;connectable=0;strokeColor=#F1F5F9;fillColor=none;top=0;"
            "left=0;right=0;bottom=1;fontSize=9;fontColor=#0F172A;align=left;spacingLeft=4;fontFamily=Inter;",
    "link": "shape=partialRectangle;html=1;whiteSpace=wrap;connectable=0;strokeColor=#F1F5F9;fillColor=none;top=0;"
            "left=0;right=0;bottom=1;fontSize=9;fontColor=#1D4ED8;align=left;spacingLeft=4;fontFamily=Inter;",
}


def add_card(g: Graph, items: list[Gap], checked: str, link=None) -> None:
    """The 'Plan to improve this page' card, beside the title block (or under it when there is no room)."""
    from .typicals import table_card, table_height

    layer = f"{g.diagram.get('id')}-gaps"
    if layer in g.els:
        return
    g.root.append(ET.Element("mxCell", {"id": layer, "value": LAYER, "style": "", "parent": "0"}))
    g.reindex()
    open_items = [i for i in items if i.names or i.always]
    width = sum(w for _, w in COLUMNS) + 28
    if open_items:
        rows = [[(i.what, link(i) if link else ""), (i.count, ""), (i.how, ""), (i.where, ""), (i.worksheet, "")]
                for i in open_items]
        height = table_height(COLUMNS, rows, STYLES["body"]) + 66  # rows grow when their text wraps
    else:
        height = 44
    x, y = _place(g, width, height)
    if open_items:
        subtitle = (f"Checked against NetBox on {html.escape(checked)}. The drawing shows what NetBox has; a "
                    f'<font color="#B45309"><b>?</b></font> on a shape marks a missing field. Track owners and '
                    f"dates in the {GAPS_REGISTER}; free worksheets at netdiagrams.com/worksheets.")
        height = table_card(g, layer, STYLES, x, y, "Plan to improve this page", subtitle, COLUMNS, rows,
                            f"{g.diagram.get('id')}-gaps-card")
    else:
        el = ET.SubElement(g.root, "mxCell", {
            "id": f"{g.diagram.get('id')}-gaps-card", "vertex": "1", "parent": layer,
            "value": f'<b>Plan to improve this page</b> · <font color="#15803D">nothing missing in NetBox for '
                     f"this page</font> (checked {html.escape(checked)})",
            "style": "rounded=1;absoluteArcSize=1;arcSize=24;fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;html=1;"
                     "whiteSpace=wrap;align=left;spacingLeft=14;fontSize=11;fontFamily=Inter;fontColor=#0F172A;"})
        ET.SubElement(el, "mxGeometry", {"x": f"{x:g}", "y": f"{y:g}", "width": f"{width:g}", "height": "44",
                                         "as": "geometry"})
        g.reindex()
    if float(g.model.get("pageHeight", 0) or 0) < y + height + 26:  # the page always holds the card
        g.model.set("pageHeight", f"{y + height + 26:g}")


BACKGROUND = ("Purdue levels", "Border", "Guides", "Controls")


def _place(g: Graph, width: float, height: float) -> tuple[float, float]:
    """Under everything on the page, beside the title block when it sits at the bottom."""
    border_parts = [i for i in g.els if g.layer_of(i).startswith("Border") and cell_of(g.els[i]).get("vertex") == "1"
                    and cell_of(g.els[i]).get("parent") in g.layers]
    frame = max(border_parts, key=lambda i: g.box(i)[2] * g.box(i)[3], default=None)
    block = [g.box(i) for i in border_parts if i != frame]
    skip = ("Border", "Controls", "Guides", "Copy of the typical", LAYER)
    bottom = max((g.box(i)[1] + g.box(i)[3] for i, el in g.els.items() if cell_of(el).get("vertex") == "1"
                  and cell_of(el).get("parent") in g.layers and not g.layer_of(i).startswith(skip)), default=0)
    if block:
        tx, ty = min(b[0] for b in block), min(b[1] for b in block)
        tb = max(b[1] + b[3] for b in block)
        if ty >= bottom - 1 and tx - 48 >= width:
            return 24, max(bottom + 16, tb - height)
        if ty >= bottom - 1 and tx < 24 + width:  # no room beside the title block: the card goes above it
            move = bottom + 16 + height + 16 - ty
            for i in border_parts:
                if i != frame and move > 0:
                    geo = g.geometry(i)
                    geo.set("y", f"{float(geo.get('y', 0)) + move:g}")
            return 24, bottom + 16
        if tx < 24 + width and tb > bottom:  # the title block is in the way: go under it
            bottom = tb
    return 24, bottom + 16


def mark_missing(fmt: str, field_name: str) -> str:
    """A tag's text for a field NetBox doesn't have yet: the label and an amber '?'."""
    label = {"primary_ip4": "IP", "serial": "SN", "cid": "CID"}.get(field_name, field_name)
    text = plain(fmt).replace("{}", "").strip()
    return (html.escape(text) + " " if text else label + " ") + MISSING
