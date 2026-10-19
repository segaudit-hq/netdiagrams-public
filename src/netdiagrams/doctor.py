"""``netdiagrams doctor``: say what a build would infer, before anything is drawn.

Read-only. For each site it prints the prefix, role map and zone source it
would use, how the site's roles fill the template's slots, the NetBox data
that needs care (spares, patch panels, repeated labels...), and the next three
things to fix, each with its worksheet. Roles the template doesn't know get a
proposed mapping, printed as a settings file to accept.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter

from . import gaps, intake, netbox_setup, ot, settings as config
from .model import _get

# Words in a NetBox role (slug, name) or device type that suggest a template role, most specific first.
HINTS = [
    (r"sd-?wan", "sdwan-edge"), (r"wlc|wireless[- ]?controller", "wireless-controller"),
    (r"\bap\b|wap|access[- ]?point|^ap-|-ap$", "access-point"), (r"ptp|radio|bridge|backhaul", "ptp-radio"),
    (r"wgb|workgroup", "workgroup-bridge"), (r"oob|console|out[- ]?of[- ]?band", "oob-switch"),
    (r"sis|safety", "sis-switch"), (r"fw|firewall|asa|palo|fortigate|ngfw", "firewall"),
    (r"core|l3|backbone|collapsed", "core-switch"), (r"dist", "distribution-switch"),
    (r"\bie\b|^ie-|industrial|cell|ring|din|ruggedi", "industrial-switch"),
    (r"access|acc|edge[- ]?switch|idf|closet", "access-switch"),
    (r"plc|controller|logix|s7", "plc"), (r"hmi|panel[- ]?pc|operator", "hmi"),
    (r"\bi/?o\b|^io-|remote[- ]?io|adapter", "io"), (r"hyper|esx|hci|vmware|proxmox|nutanix", "hypervisor"),
    (r"server|historian|scada|srv", "server"), (r"router|wan|isr|edge", "router"),
    (r"drive|vfd|inverter", "drive"), (r"camera|cctv", "camera"), (r"printer", "printer"),
]


def template_slots(template: ET.Element) -> Counter:
    """How many device shapes of each role the template draws (each device once)."""
    from .sync import _is_device

    seen = {}
    for el in template.iter("object"):
        if _is_device(el) and el.get("role"):
            seen.setdefault(el.get("name"), el.get("role"))
    return Counter(seen.values())


def propose(role: dict, device_types: list[str], known: set[str]) -> str:
    text = " ".join([role.get("slug") or "", role.get("name") or ""] + device_types).lower()
    for pattern, target in HINTS:
        if target in known and re.search(pattern, text):
            return target
    return ""


def _zone_source(d: dict, locations: ot.Locations) -> str:
    if ot._cf(d, ot.ZONE_FIELDS):
        return "field"
    if ot._tag_zones(d):
        return "tag"
    if locations.zone(d.get("location")):
        return "location"
    return "none"


def quality(export: dict, file_settings: dict | None = None, file_name: str = ""):
    """The data quality scorecard for one export (sheet 1c, without drawing anything)."""
    from . import quality as quality_mod
    from .model import build_site
    from .sync import endpoint_roles
    ENDPOINT_ROLES = endpoint_roles()

    export = intake.prepare(export, file_settings, file_name)
    info = intake.intake(export)
    locations = ot.Locations(export.get("locations"))
    as_of = info.data_date or dt.date.today().isoformat()  # as build and gaps age evidence
    found = gaps.find(export, ENDPOINT_ROLES, lambda d: ot.device_zones(d, locations), as_of)
    return quality_mod.assess(export, found, build_site(export), ENDPOINT_ROLES, as_of)


def check(export: dict, template: ET.Element, file_settings: dict | None = None,
          file_name: str = "") -> tuple[str, dict]:
    """The doctor's report for one site, and the settings it proposes (empty when nothing to add)."""
    from .sync import endpoint_roles, site_prefix
    ENDPOINT_ROLES = endpoint_roles()

    raw_roles = {d.get("id"): d.get("role") or {} for d in export.get("devices", [])}
    export = intake.prepare(export, file_settings, file_name)
    info = intake.intake(export)
    cfg = info.settings
    site = export.get("site") or {}
    devices = export.get("devices", [])
    slots = template_slots(template)
    known = set(slots) | ENDPOINT_ROLES | {"server", "router", "distribution-switch", "drive", "camera"}
    out = [f"NetDiagrams doctor: {site.get('name') or site.get('slug') or 'site'} ({site.get('slug', '')})", ""]
    if info.data_date:
        out.append(f"NetBox data as of {info.data_date}.")
    out.append("Settings from: " + ", ".join(info.sources) + ".")
    out.append("")

    # Names
    names = [d["name"] for d in devices]
    configured = (cfg.get("naming") or {}).get("prefix") or ""
    shared = site_prefix(names)
    out.append("Names")
    if configured:
        out.append(f"  Site prefix: {configured} (from settings)")
    elif shared:
        count = sum(1 for n in names if n.startswith(shared))
        out.append(f"  Site prefix: {shared} (shared by {count} of {len(names)} device names)")
    else:
        code = (site.get("facility") or site.get("slug") or "").upper()
        out.append(f"  Site prefix: none shared by the device names; the drawing's site code will be {code or '?'}."
                   ' Set "naming": {"prefix": ...} if the names do share one.')
    locations = ot.Locations(export.get("locations"))
    found = gaps.find(export, ENDPOINT_ROLES, lambda d: ot.device_zones(d, locations),
                      info.data_date or dt.date.today().isoformat())
    pattern = gaps.naming_pattern(cfg.get("naming") or {})
    out.append(f"  Naming standard: {pattern} · {len(found['bad_name'].names)} names off it")
    out.append("")

    # Roles
    by_role = Counter(_get(d, "role", "slug") for d in devices)
    netbox_names: dict[str, set] = {}
    for d in devices:
        netbox_names.setdefault(_get(d, "role", "slug"), set()).add(
            _get(d, "role", "netbox_slug") or _get(d, "role", "slug"))
    out.append("Roles")
    width = max([len(r) for r in set(slots) | set(by_role)] + [12])
    out.append(f"  {'template role':<{width}}  slots  NetBox")
    for role in sorted(set(slots) | set(by_role), key=lambda r: (r not in slots, r)):
        source = sorted(netbox_names.get(role, set()) - {role})
        note = ""
        if role in slots and not by_role.get(role):
            note = "no devices: these slots are removed"
        elif role not in slots and role in ENDPOINT_ROLES:
            note = "end devices: folded into a drawn shape of the same role"
        elif role not in slots and role in known:
            note = "no slot: goes to the tray"
        elif role not in slots:
            note = "not a template role: goes to the tray"
        if source:
            note = ("mapped from " + ", ".join(source) + ("; " + note if note else "")).strip()
        out.append(f"  {role or '(no role)':<{width}}  {slots.get(role, 0):>4}  {by_role.get(role, 0):>5}  {note}")
    proposal: dict[str, list[str]] = {}
    types_by_role: dict[str, list] = {}
    for d in devices:
        types_by_role.setdefault(_get(d, "role", "slug"), []).append(_get(d, "device_type", "model"))
    asked = {}  # (role, the role as NetBox has it) -> one device's raw role: propose once per pair, not per device
    for d in devices:
        role = _get(d, "role", "slug")
        if role in known or not role:
            continue
        raw = raw_roles.get(d.get("id")) or {"slug": role}
        asked.setdefault((role, raw.get("slug")), raw)
    for (role, _), raw in asked.items():
        target = propose(raw, types_by_role[role], known)
        if target:
            proposal.setdefault(target, [])
            if role not in proposal[target]:
                proposal[target].append(role)
    if proposal:
        out.append("  Proposed role mapping (not applied until saved in settings): " + ", ".join(
            f"{', '.join(v)} → {k}" for k, v in sorted(proposal.items())))
    out.append("")

    # Zones
    locations = ot.Locations(export.get("locations"))
    sources = Counter(_zone_source(d, locations) for d in devices)
    fields = ", ".join(cfg.get("zone_field") or [])
    out.append("Zones")
    out.append(f"  Read from: field {fields or '(none)'} on {sources['field']} devices, zone-* tags on "
               f"{sources['tag']}, the location tree on {sources['location']}, nothing on {sources['none']}.")
    template_zones, _, _ = netbox_setup._template_facts(template)
    prefixes: dict = {}
    for p in export.get("prefixes", []):
        if _get(p, "vlan", "id", default=None) is not None:
            prefixes.setdefault(p["vlan"]["id"], []).append(p)
    vlan_zones = {ot.vlan_zone(v, prefixes.get(v.get("id"))) for v in export.get("vlans", [])}
    device_zones = {z for d in devices for z in ot.device_zones(d, locations)}
    empty = sorted(z for z in template_zones if z in device_zones and z not in vlan_zones)
    if empty:
        out.append("  Zones with devices but no VLANs in NetBox: " + ", ".join(empty))
    unknown = sorted(device_zones - set(template_zones))
    if unknown:
        out.append("  Zones the template doesn't draw (shown on the glance page): " + ", ".join(unknown))
    out.append("")

    # Data that needs care
    care = [
        ("Spares and devices being taken out (listed, not drawn)", [d.get("name") for d in info.register_only]),
        ("Planned (drawn dashed)", info.planned),
        ("Offline or failed (amber marker)", [n for n, _ in info.flagged]),
        ("Patch panels (links traced through them)", info.panels),
        ("Devices with no name", info.unnamed),
        ("Cable labels used more than once", [f"{k} ×{n}" for k, n in info.duplicate_labels.items()]),
        ("Group VLANs left out for the site's own", info.shadowed_vlans),
        ("Wireless LANs left out (VLAN not this site's, not scoped to it)", info.left_out_wlans),
    ]
    care = [(title, items) for title, items in care if items]
    out.append("Data that needs care")
    if not care:
        out.append("  None found.")
    for title, items in care:
        shown = ", ".join(items[:6]) + (f" +{len(items) - 6} more" if len(items) > 6 else "")
        out.append(f"  {title}: {len(items)} · {shown}")
    out.append("")

    # Next three things to fix
    ranked = sorted((g for g in found.values() if g.names and not g.always), key=lambda g: -len(g.names))[:3]
    out.append("Next three things to fix")
    if not ranked:
        out.append("  Nothing missing that NetDiagrams checks for.")
    for n, g in enumerate(ranked, 1):
        out.append(f"  {n}. {g.what}: {len(g.names)} · {g.how} · {g.where} · {g.worksheet}")
    suggested = {"roles": proposal} if proposal else {}
    if suggested:
        out += ["", f"To accept the proposed mapping, save this as {config.FILE_NAME} next to your drawings "
                f"(or put it in the '{config.FIELD}' JSON custom field on the NetBox site or region):", "",
                json.dumps(suggested, indent=2)]
    return "\n".join(out) + "\n", suggested
