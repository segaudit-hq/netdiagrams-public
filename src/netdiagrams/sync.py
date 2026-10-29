"""Fill the drawing template with NetBox data, keeping its layout.

The template's shapes carry NetBox field names (see its NetBox page). NetDiagrams:

1. matches devices by name (after swapping the template's site prefix for the
   site's own) and gives leftover NetBox devices the template slot of the same
   role, so a standard-shaped site needs no hand placing;
2. updates every NetBox-owned fact on devices, cables, interfaces, circuits and
   wireless links, and points every shape and table row at its NetBox object;
3. rewrites the typed parts from NetBox too: management IP, serial and circuit
   tags, the asset and link registers, the VLAN tables and the title blocks;
4. removes template devices the site doesn't have, shows drawn links missing
   from NetBox as dashed, and draws NetBox cables the template lacks;
5. folds end devices with no slot (more PLCs, APs, HMIs) into a drawn shape of
   the same role on the same switch, location or zone, which then reads as a
   counted group such as "PLC ×12", and puts any other device without a slot
   in a tray below the physical page.

Drawing-only facts (``x_*`` fields) and the layout are never changed.
"""

from __future__ import annotations

import copy
import datetime as dt
import html
import ipaddress
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from importlib import resources

from . import audit as audit_mod, changes as changes_mod, gaps, hardware, intake, interactive, model, ot, overview, pages as page_list, paper, profiles, provenance, quality, riser as riser_mod, stencils, truth, typicals, wireless, wireless_page
from .graph import Graph, _inside, cell_of, font_size, plain, text_lines
from .model import _device_attrs, _get, _label, _natural, _number, build_site

# The manufacturing template's; a build uses the profile in force (profiles.py).
TEMPLATE_FILE = profiles.MANUFACTURING.template
TEMPLATE_SITE_CODE = profiles.MANUFACTURING.site_code
TEMPLATE_SITE_NAME = profiles.MANUFACTURING.site_name
TEMPLATE_NETBOX = "https://netbox.example.com"
DEVICE_KEYS = ("role", "device_type")
SKIP_IN_TOOLTIP = {"id", "label", "placeholders", "tooltip", "link", "linkTarget"}
UNPLACED_LAYER = "Unplaced from NetBox (drag into place)"
# Criticality pills get a layer of their own: hide it, or let `share` strip it, before a copy leaves the site.
CRITICALITY_LAYER = "Asset criticality (hide before sharing)"
# Devices in a compliance scope (PCI CDE, safety, NERC CIP...) wear a purple stripe on their right edge.
SCOPE_LAYER = "Compliance scope (hide before sharing)"
ADDED_LINKS_LAYER = "Links from NetBox (not in the template)"
MISSING_LINK_STYLE = "dashed=1;dashPattern=4 4;strokeColor=#94A3B8;opacity=60;"

SHORT_IF = [
    ("TwentyFiveGigE", "Twe"), ("HundredGigE", "Hu"), ("FortyGigabitEthernet", "Fo"),
    ("TenGigabitEthernet", "Te"), ("GigabitEthernet", "Gi"), ("FastEthernet", "Fa"),
    ("Port-channel", "Po"), ("Ethernet", "Eth"), ("ethernet", "eth"), ("Redundancy Port", "RP"),
    ("StackPort", "SP"),
]
MEDIA = {
    "smf-os2": "SMF OS2", "smf-os1": "SMF OS1", "smf": "SMF", "mmf-om1": "MMF OM1", "mmf-om2": "MMF OM2",
    "mmf-om3": "MMF OM3", "mmf-om4": "MMF OM4", "mmf-om5": "MMF OM5", "mmf": "MMF",
    "cat5e": "Cat5e", "cat6": "Cat6", "cat6a": "Cat6A", "cat7": "Cat7", "cat8": "Cat8",
    "dac-passive": "DAC", "dac-active": "DAC", "aoc": "AOC", "power": "Power",
}

# Asset register column header -> how to fill it from a NetBox device.
ASSET_COLUMNS = {
    "HOSTNAME": lambda d, a: a["name"], "NAME": lambda d, a: a["name"],
    "ROLE": lambda d, a: _role_name(d, a),
    "MODEL": lambda d, a: a.get("device_type", ""), "SERIAL": lambda d, a: a.get("serial", ""),
    "MGMT IP": lambda d, a: (a.get("primary_ip4", "").split("/")[0]
                             or (f"OOB {a['oob_ip'].split('/')[0]}" if a.get("oob_ip") else "")),
    "OOB IP": lambda d, a: a.get("oob_ip", "").split("/")[0],
    "EOS": lambda d, a: (a.get("cf_end_of_support") or "")[:10],
    "CRIT": lambda d, a: (a.get("cf_criticality") or "").capitalize(),
    "ROOM": lambda d, a: a.get("location", ""),
    "LOCATION": lambda d, a: a.get("location_path") or a.get("location", ""),
    "AREA": lambda d, a: a.get("location_path") or a.get("location", ""),
    "RACK/CAB": lambda d, a: a.get("rack", ""), "RACK": lambda d, a: a.get("rack", ""),
    "U": lambda d, a: f"U{a['position']}" if a.get("position") else "",
    "SW": lambda d, a: a.get("cf_sw_version") or a.get("platform", ""),
    "STATUS": lambda d, a: a.get("status", ""), "ASSET TAG": lambda d, a: a.get("asset_tag", ""),
}
STATUS_COLORS = {"active": "#15803D", "connected": "#15803D", "planned": "#B45309", "staged": "#B45309",
                 "offline": "#B91C1C", "failed": "#B91C1C", "inventory": "#64748B", "decommissioning": "#64748B"}
ASSET_EXTRA_COLUMNS = (  # (title, width, after, donors that pay evenly)
    ("STATUS", 48, "ROLE", ["ROLE", "HOSTNAME", "NAME"]),
    ("CRIT", 50, "STATUS", ["ROOM", "LOCATION", "SW", "MODEL"]),   # "Medium" needs 50
    ("EOS", 60, "SW", ["SW", "MODEL", "ROOM", "LOCATION"]),   # a date needs 58; SERIAL keeps its width
)
LINK_EXTRA_COLUMNS = (
    ("CABLE ID", 64, "LINK", ["TRUNKED VLANS"]),
    ("STATUS", 54, "MEDIA", ["A-SIDE (MEMBERS)", "B-SIDE (MEMBERS)"]),
)


def _role_name(d: dict, a: dict) -> str:
    """The NetBox role's name; a slug-shaped name reads as words ('OOB switch', 'Core switch')."""
    from .netbox_setup import ROLE_NAMES
    name, slug = _label(d.get("role")), a.get("role", "")
    if not name or name == slug:
        return profiles.role_name(slug, ROLE_NAMES)
    return name


def _status_pill(status: str) -> tuple[str, str, bool]:
    status = (status or "active").lower()
    return (f'<font color="{STATUS_COLORS.get(status, "#334155")}"><b>{html.escape(status)}</b></font>', "", True)


def default_template(profile: "profiles.Profile | str | None" = None) -> ET.Element:
    """The bundled template of ``profile`` (the profile in force when not given)."""
    profile = profiles.get(profile) if isinstance(profile, str) else (profile or profiles.current())
    text = resources.files("netdiagrams").joinpath("data", profile.template).read_text("utf-8")
    return ET.fromstring(text)


# --------------------------------------------------------------------- report
@dataclass
class Report:
    site_code: str = ""
    profile: str = profiles.DEFAULT
    renamed_prefix: str = ""
    matched_devices: set = field(default_factory=set)
    slotted: dict = field(default_factory=dict)          # template name -> NetBox name
    removed_devices: list = field(default_factory=list)
    matched_cables: set = field(default_factory=set)
    added_cables: list = field(default_factory=list)
    missing_cables: set = field(default_factory=set)
    changes: list = field(default_factory=list)          # (page, kind, name, key, old, new)
    netbox_only_devices: list = field(default_factory=list)
    wireless_tray: list = field(default_factory=list)       # the netbox-only devices waiting under the wireless sheet
    grouped: dict = field(default_factory=dict)          # drawn device -> NetBox devices folded into it
    glance: bool = False                                 # a "Site at a glance" page was added
    riser: bool = False                                  # a "Riser" sheet (buildings and floors) was added
    audit: bool = False                                  # the audit evidence sheet (3f) was added
    scheduled: list = field(default_factory=list)        # devices listed in a cell or IDF schedule
    register_sheets: list = field(default_factory=list)  # pages added for registers too long for their page
    oversize: list = field(default_factory=list)  # sheets still larger than A0
    skipped_pages: list = field(default_factory=list)    # (page, why) left out of this site's file
    vlan_scheduled: int = 0  # cells listed only in the logical page's Cell VLAN schedule
    netbox_only_cables: list = field(default_factory=list)
    tables: list = field(default_factory=list)           # (page, title, rows)
    tags: int = 0
    interfaces: int = 0
    intake: intake.Intake = field(default_factory=intake.Intake)
    provenance: provenance.Provenance = field(default_factory=provenance.Provenance)
    examples_marked: list = field(default_factory=list)  # sheets and cards watermarked as the template's example
    examples_kept: list = field(default_factory=list)  # example sheets and cards the site rewrote: not stamped
    edited_examples: set = field(default_factory=set)
    guide_notes: int = 0                                 # template notes moved to the hidden guide layer
    label_changes: list = field(default_factory=list)    # (page, was, now) group labels derived from member counts
    residue: list = field(default_factory=list)          # (page, count) leftovers removed with their devices
    zone_tables: list = field(default_factory=list)      # sheet 7 tables filled from NetBox
    duplicates: list = field(default_factory=list)       # 'serial X: dev-a, dev-b' and the like
    quality: "quality.Scorecard | None" = None           # the data quality scorecard (sheet 1c)
    state: dict = field(default_factory=dict)            # this build's fingerprint (state.json)
    changes_since: "changes_mod.Changes | None" = None   # against the previous state.json, when there was one
    marked_changes: int = 0                              # NEW / CHANGED pills drawn
    removed_cards: list = field(default_factory=list)    # wireless-sheet cards (controllers, radios) NetBox lacks
    template_leftovers: dict = field(default_factory=dict)  # page -> template names a caption lost to '?'
    wireless_management: str = ""                        # the management card drawn when there is no controller
    matched_wireless: set = field(default_factory=set)   # id() of the NetBox wireless links a drawn line matched
    added_wireless_links: list = field(default_factory=list)

    @property
    def drawing_only_devices(self) -> list:
        return self.removed_devices

    def markdown(self, site_name: str) -> str:
        lines = [f"# NetDiagrams drift report: {site_name}", ""]
        lines += self.provenance.markdown()
        if self.quality is not None:
            lines.append(f"- Data quality: {self.quality.score}/100 (sheet 1c; quality.json next to the drawing)")
        if self.intake.roles_mapped:
            lines.append("- Roles mapped to the template's: " + ", ".join(
                f"{k} → {v}" for k, v in sorted(self.intake.roles_mapped.items())))
        if self.renamed_prefix:
            lines.append(f"- Template names renamed: {self.renamed_prefix}")
        lines += [
            f"- Devices matched by name: {len(self.matched_devices) - len(self.slotted)}",
            f"- Devices placed in a template slot of the same role: {len(self.slotted)}",
            f"- Template devices removed (not in NetBox): {len(self.removed_devices)}",
            f"- Cables matched: {len(self.matched_cables)} · drawn from NetBox: {len(self.added_cables)} · "
            f"drawn but not in NetBox (shown dashed): {len(self.missing_cables)}",
            f"- Interfaces updated: {self.interfaces} · tags rewritten: {self.tags}",
            f"- Tables rebuilt from NetBox: {len(self.tables)}",
            f"- Fields updated: {len(self.changes)}",
            "",
        ]
        sections = [
            ("Placed in a template slot", [f"{n} (in place of {t})" for t, n in sorted(self.slotted.items())]),
            ("End devices shown as a counted group on a drawn shape",
             [f"{head} ×{len(m) + 1}: adds {', '.join(m)}" for head, m in sorted(self.grouped.items())]),
            ("In NetBox, no slot on the drawing (in the tray below the physical page)",
             [n for n in self.netbox_only_devices if n not in self.wireless_tray]),
            ("In NetBox, no slot on the wireless sheet (in the tray below it)", self.wireless_tray),
            ("Template devices removed because the site doesn't have them", self.removed_devices),
            ("Cables in NetBox drawn as new links", self.added_cables),
            ("Cables in NetBox with an end not on the drawing", self.netbox_only_cables),
            ("Links on the drawing with no NetBox cable (dashed)", sorted(self.missing_cables)),
            ("Not drawn because of their NetBox status (listed in the registers)",
             [f"{d.get('name')} ({intake.status(d)})" for d in self.intake.register_only]),
            ("Planned in NetBox (drawn dashed)", self.intake.planned),
            ("Offline or failed in NetBox (amber marker)", [f"{n} ({s})" for n, s in self.intake.flagged]),
            ("Patch panels (not drawn as devices)", self.intake.panels),
            ("Links traced through patch panels", self.intake.traced),
            ("Devices with no name in NetBox (named role-id here)", self.intake.unnamed),
            ("Devices sharing a name in NetBox (the others get -id here)", self.intake.shared_names),
            ("Cable labels used on more than one cable",
             [f"{label} ×{n}" for label, n in self.intake.duplicate_labels.items()]),
            ("VLANs from a wider group left out (the site has its own with that number)",
             self.intake.shadowed_vlans),
            ("Wireless LANs left out (their VLAN isn't one of this site's, and they aren't scoped to it)",
             self.intake.left_out_wlans),
            ("Tables rebuilt", [f"{p}: {t} ({n} rows)" for p, t, n in self.tables]),
            ("Duplicate serial numbers, management IPs or asset tags", self.duplicates),
            ("Marked as the template's example (watermarked, not this site's data)", self.examples_marked),
            ("Example sheets and cards this site rewrote (not marked)", self.examples_kept),
            ("Group labels reduced to what NetBox has (one member: no HA or stack wording)",
             [f"{p}: '{was}' → '{now}'" for p, was, now in self.label_changes]),
            ("Leftovers removed with their devices (labels, pills, free lines)",
             [f"{p}: {n}" for p, n in self.residue]),
            ("Pages left out", [f"{p}: {why}" for p, why in self.skipped_pages]),
            ("Sheets larger than A0 (they print tiled; leave pages out or split the site)", self.oversize),
        ]
        for title, items in sections:
            lines += [f"## {title}", ""] + ([f"- {i}" for i in items] or ["None."]) + [""]
        lines += changes_mod.markdown(self.changes_since)
        lines += ["## Fields updated from NetBox", ""]
        if self.changes:
            lines += ["| Page | Object | Field | Was | Now |", "| --- | --- | --- | --- | --- |"]
            lines += [f"| {_md(p)} | {_md(n)} | {_md(k)} | {_md(o) or '—'} | {_md(v) or '—'} |"
                      for p, _, n, k, o, v in self.changes]
        else:
            lines.append("None.")
        lines += ["", "Closing the gaps? `netdiagrams gaps` writes NetBox import files (one row per object with a "
                      "gap, its id and current values; fill the blanks and import).",
                  _rot_line(profiles.get(self.profile))]
        return "\n".join(lines) + "\n"


# -------------------------------------------------------------------- helpers
def _md(value) -> str:
    """A value as one Markdown table cell: no column break, no line break."""
    return re.sub(r"\s*[\r\n]+\s*", " ", str(value or "")).replace("|", "\\|")


def _same(a: str, b: str) -> bool:
    return (a or "").strip().casefold() == (b or "").strip().casefold()


def _tooltip(el: ET.Element) -> str:
    return "\n".join(f"{k}: {v}" for k, v in el.attrib.items()
                     if k not in SKIP_IN_TOOLTIP and not k.startswith("netdiagrams_"))


def short_if(name: str) -> str:
    for long, short in SHORT_IF:
        if name.startswith(long):
            return short + name[len(long):]
    return name


def _speed(iface: dict) -> str:
    kbps = iface.get("speed")
    if kbps:
        g = kbps / 1_000_000
        return f"{g:g}G" if g >= 1 else f"{kbps / 1000:g}M"
    t = _get(iface, "type", "value") or ""
    m = re.match(r"(\d+)(g|base)", t)
    if not m:
        return ""
    return f"{m.group(1)}G" if m.group(2) == "g" else ("1G" if m.group(1) == "1000" else f"{int(m.group(1))}M")


def _vlans(iface: dict) -> str:
    mode = _get(iface, "mode", "value")
    if mode == "access":
        return f"access {_get(iface, 'untagged_vlan', 'vid')}"
    if mode in ("tagged", "tagged-all"):
        tagged = ", ".join(str(v.get("vid")) for v in iface.get("tagged_vlans") or [])
        return tagged or ("all" if mode == "tagged-all" else "")
    return ""


def site_prefix(names) -> str:
    """The shared first token of device names, e.g. 'S07-' for S07-IT-CORE-1."""
    firsts = Counter(n.split("-", 1)[0] + "-" for n in names if "-" in n)
    if not firsts:
        return ""
    prefix, count = firsts.most_common(1)[0]
    return prefix if count >= max(2, len(names) // 2) else ""


class NetBoxIndex:
    def __init__(self, export: dict):
        self.url = (export.get("netbox_url") or "").rstrip("/")
        self.site = export.get("site") or {}
        self.devices = {d["name"]: d for d in export.get("devices", []) if d.get("name")}
        self.names = {d.get("id"): d.get("name") for d in export.get("devices", [])}
        self.register_only = {d["name"]: d for d in intake.intake(export).register_only if d.get("name")}
        # Cables by label. A label used on several cables (cabinet-local '1', '2'...) gets the
        # A-side device added, so no cable silently replaces another.
        self.cables: dict[str, dict] = {}
        self.duplicates: dict[str, list[str]] = defaultdict(list)
        counts = Counter(c.get("label") for c in export.get("cables", []) if c.get("label"))
        for c in export.get("cables", []):
            label = c.get("label")
            if not label:
                continue
            key = label
            if counts[label] > 1:
                a = _ends(c.get("a_terminations"), self.names)
                key = f"{label} ({a[0][0] if a else c.get('id')})"
                if key in self.cables:
                    key = f"{label} (#{c.get('id')})"
                self.duplicates[label].append(key)
            self.cables[key] = c
        self.interfaces = {}
        for i in export.get("interfaces", []):
            dev = (i.get("device") or {}).get("name") or self.names.get((i.get("device") or {}).get("id"))
            self.interfaces[(dev, i.get("name"))] = i
        self.circuits = {c["cid"]: c for c in export.get("circuits", []) if c.get("cid")}
        self.wireless: dict[str, list[dict]] = defaultdict(list)
        for w in export.get("wireless_links", []):
            if w.get("ssid"):
                self.wireless[w["ssid"]].append(w)
        self.wlans = export.get("wireless_lans") or []
        self.vlans = export.get("vlans", [])
        self.prefixes = export.get("prefixes", [])
        self.ip_addresses = export.get("ip_addresses", [])
        self.parsed_ips = []  # (address, the IP record), parsed once: _gateway looks through them per prefix
        for ip in self.ip_addresses:
            try:
                self.parsed_ips.append((ipaddress.ip_interface(ip.get("address", "")).ip, ip))
            except ValueError:
                continue
        self.locations = ot.Locations(export.get("locations"))
        self.wx = wireless.Index(export, endpoint_roles())
        self.hw = hardware.Hardware(export)
        self.audit = audit_mod.Evidence(export, intake.intake(export).settings, endpoint_roles())

    def link(self, path: str, obj: dict | None = None, **query) -> str:
        if not self.url:
            return ""
        if obj and obj.get("id") is not None:
            return f"{self.url}/{path}/{obj['id']}/"
        return f"{self.url}/{path}/?{urllib.parse.urlencode(query, doseq=True)}"

    def device_attrs(self, name: str) -> dict[str, str]:
        attrs = _device_attrs(self.devices[name], self.url)
        attrs.pop("link", None)
        if self.location_path(self.devices[name]):
            attrs["location_path"] = self.location_path(self.devices[name])
        return attrs

    def location_path(self, d: dict) -> str:
        """'Main building › floor 2 › IDF-B214' when NetBox nests the device's location; else its name."""
        path = self.locations.card_path(d.get("location")) if d.get("location") else ""
        return path if " › " in path else ""   # a flat site's cards keep %location% as before


PLACEHOLDER = re.compile(r"‹[^›]*›")


QUIET = audit_mod.QUIET | {f"cf_{n}" for n in intake.MODEL_FIELDS}


def _update(el, updates: dict[str, str], report: Report, page: str, kind: str, name: str) -> None:
    for key, new in updates.items():
        old = el.get(key, "")
        if (key in el.attrib and old == new) or (not new and not old):
            continue
        if key in el.attrib and _same(old, new):  # a case or spacing fix in NetBox: written, not reported
            el.set(key, new)
            continue
        if key in QUIET:   # evidence dates move nightly, model dates come from the type: not the drawing disagreeing
            el.set(key, new)
            continue
        if not PLACEHOLDER.fullmatch(old.strip()):   # filling a '‹serial›' blank is not the drawing disagreeing
            report.changes.append((page, kind, name, key, old, new))
        el.set(key, new)


def _is_device(el: ET.Element) -> bool:
    return el.tag in ("object", "UserObject") and bool(el.get("name")) and any(
        el.get(k) is not None for k in DEVICE_KEYS)


def _ends(terms, names) -> list[tuple[str, str]]:
    out = []
    for t in terms or []:
        obj = t.get("object") or {}
        dev = obj.get("device") or {}
        out.append((names.get(dev.get("id")) or dev.get("name", "?"), obj.get("name", "")))
    return out


def _cable_attrs(cables: list[dict], names: dict) -> dict[str, str]:
    """One drawn line may carry several cables (a port-channel): join their facts."""
    merged: dict[str, list[str]] = defaultdict(list)
    for c in cables:
        values = {
            "x_patch_a": c.get("x_patch_a") or "", "x_patch_b": c.get("x_patch_b") or "",
            "type": c.get("type") or "", "status": _get(c, "status", "value"),
            "color": c.get("color") or "", "length": _number(c.get("length")),
            "length_unit": _get(c, "length_unit", "value"),
            "a_terminations": ", ".join(f"{d}:{p}" for d, p in _ends(c.get("a_terminations"), names)),
            "b_terminations": ", ".join(f"{d}:{p}" for d, p in _ends(c.get("b_terminations"), names)),
        }
        for k, v in values.items():
            if v and v not in merged[k]:
                merged[k].append(v)
    joined = {k: ", ".join(merged.get(k, [])) for k in
              ("type", "status", "color", "length", "length_unit", "a_terminations", "b_terminations",
               "x_patch_a", "x_patch_b")}
    for key in ("x_patch_a", "x_patch_b"):  # the template's own patch text stays unless NetBox has one
        if not joined[key]:
            del joined[key]
    for key in ("type", "status", "color", "length_unit"):
        joined[key] = merged[key][0] if merged.get(key) else ""
    return joined


# ------------------------------------------------------------------ main fill
def _rot_line(profile: "profiles.Profile") -> str:
    number, title, _ = profile.chapters.get("quality", (13, "Diagrams rot. Measure the rot.", ""))
    return (f"Fixing these for good? Chapter {number}, \"{title}\", sets up a routine to keep "
            f"the drawing and NetBox in step: {profile.book_url}")


def fill(template: ET.Element, export: dict, *args, **kwargs) -> Report:
    """Fill ``template`` from ``export`` under the site's industry profile (see ``_fill``)."""
    stencils.inflate(template)
    export = intake.prepare(export, kwargs.get("settings"), kwargs.get("settings_name", ""))
    with profiles.use(profiles.from_settings(intake.intake(export).settings)) as profile:
        report = _fill(template, export, *args, **kwargs)
        report.profile = profile.name
        return report


def _fill(template: ET.Element, export: dict, prefix_map: dict[str, str] | None = None,
         tray: bool = True, keep_unmatched: bool = False, slots: bool = True,
         today: str | None = None, glance: bool | None = None, riser: bool | None = None, controls: bool = True,
         audit: bool | None = None,
         data_gaps: bool = True, pages: str = "", settings: dict | None = None,
         settings_name: str = "", book_note: bool = True, source_name: str = "", revision: str = "",
         guide: bool = True, quality_sheet: bool = True, previous_quality: dict | None = None,
         previous_state: dict | None = None) -> Report:
    """Update ``template`` in place from a NetBox export and return what changed.

    ``glance`` adds a "Site at a glance" page after the first one: one card per
    zone with device counts. By default it is added when the site doesn't fit
    the template (devices grouped or left in the tray), so a site shaped like
    the template still comes out page for page.

    ``riser`` adds the buildings-and-floors sheet drawn from NetBox's location tree;
    by default it comes when the site's locations nest and more than one holds
    network gear.

    ``audit`` adds sheet 3f, the audit evidence register (owners, compliance scope, backups,
    patching, verification, support, monitoring and logging per asset); by default it comes
    when NetBox records any of that evidence for the site.

    ``source_name`` names the export file for the provenance note; ``revision``
    overrides the content-based revision written in every title block. ``guide``
    False removes the hidden guide layer (template how-to notes) from every page.
    ``quality_sheet`` adds sheet 1c (the data quality scorecard); ``previous_quality``
    is the quality.json of the last build, for the trend column. ``previous_state`` is
    the last build's state.json; devices new or changed since it get a pill.
    """
    export = intake.prepare(export, settings, settings_name)
    info = intake.intake(export)
    cfg = info.settings
    skip = page_list.skipped(template, export, " ".join(x for x in (cfg.get("pages", ""), pages) if x))
    nb = NetBoxIndex(export)
    report = Report(intake=info, provenance=provenance.Provenance.build(
        export, cfg, info.sources, info.data_date, source=source_name, today=today, revision=revision))
    _strip_generated(template)
    pages = [Graph(d) for d in template.findall("diagram")]
    template_names = {el.get("name") for g in pages for el in g.els.values() if _is_device(el)}
    site = model.build_site(export)
    devices_with_names = [d for d in export.get("devices", []) if d.get("name")]
    for what, key in (("serial", lambda d: d.get("serial")), ("mgmt IP", lambda d: _get(d, "primary_ip4", "address")),
                      ("asset tag", lambda d: d.get("asset_tag"))):
        report.duplicates += [f"{what} {line}" for line in gaps.duplicates(devices_with_names, key)]

    # 1. Site prefix: S01- on the template becomes the site's own prefix.
    prefix_map = dict(prefix_map or {})
    if not prefix_map:
        old, new = site_prefix(template_names), (cfg.get("naming") or {}).get("prefix") or site_prefix(nb.devices)
        if old and new and old != new:
            prefix_map[old] = new
    if prefix_map:
        report.renamed_prefix = ", ".join(f"{o}* → {n}*" for o, n in prefix_map.items())
    rename = _renamer(prefix_map)
    old_code = profiles.current().site_code
    # Names with no shared prefix (CORE, NEWCORE) fall back to the site's facility, then its slug.
    report.site_code = (next(iter(prefix_map.values()), "") or site_prefix(nb.devices)).rstrip("-") \
        or (nb.site.get("facility") or "").upper() or (nb.site.get("slug") or "").upper() or old_code

    # Example sheets and cards the site rewrote in its own template are not stamped as the template's.
    report.edited_examples = truth.edited_examples(
        pages, default_template(), (old_code, report.site_code, profiles.current().site_name, nb.site.get("name")))

    # 2. Tags (mgmt IP, serial, circuit ID) get bound to their shape before anything moves.
    for g in pages:
        _bind_tags(g)
        _lift_inline_serials(g)

    # 3. Match devices; give unmatched NetBox devices the slot of the same role.
    names_after = {t: rename(t) for t in template_names}
    matched = {t for t, n in names_after.items() if n in nb.devices}
    if slots:
        report.slotted = _assign_slots(pages, names_after, matched, nb)
        for t, n in report.slotted.items():
            names_after[t] = n
    final = {t: n for t, n in names_after.items() if n in nb.devices}
    report.matched_devices = set(final.values())
    report.grouped = _group_endpoints(set(final.values()), nb)
    removed_templates = sorted(t for t in template_names if t not in final)
    report.removed_devices = removed_templates if not keep_unmatched else []

    for g in pages:
        if prefix_map and g.diagram.get("id") not in truth.example_sheets():
            _rename_labels(g, names_after, prefix_map)  # before registers are read back as "before" rows
        before = {t: [(names_after.get(r[0], rename(r[0])) if r else "", r) for r in _table_text(g, t)]
                  for t in g.tables()}
        _rename_everywhere(g, names_after, rename)
        _fill_devices(g, nb, report)
        _label_groups(g, report.grouped, nb)
        _fill_interfaces(g, nb, report)
        if g.diagram.get("id") == "hardware":
            _fill_hardware_cards(g, nb)
        _fill_circuits_and_wireless(g, nb, rename, report)
        if not keep_unmatched:
            _remove_devices(g, {names_after[t] for t in removed_templates}, report)
        if g.diagram.get("id") == "wireless":
            wireless_page.fill(g, nb, report, _is_device, keep_unmatched, rename(site_prefix(template_names)))
        _fill_cables(g, nb, rename, report)
        _refresh_tags(g, nb, report)
        if g.diagram.get("id") == "physical" and not report.scheduled:
            report.scheduled = sorted(typicals.apply(g, nb, set(_drawn_devices(g))), key=_natural)
        g.scheduled = report.scheduled
        _fill_tables(g, nb, report, before)
        _fill_interface_tables(g, nb, site)
        report.vlan_scheduled += typicals.vlan_schedule(g, nb, _natural)
        _cell_ranges(g, nb)
        _fill_title(g, nb, report, old_code, today)
        _fill_ssids(g, nb, report)
        _repoint_links(g, nb, rename)
        _separate_example(g, nb, export, report, site, guide)
        _tidy_placeholders(g)
        _label_closets(g, nb)

    placed = set().union(*[{el.get("name") for el in g.els.values() if _is_device(el)} for g in pages])
    placed |= {m for head, members in report.grouped.items() if head in placed for m in members}
    placed |= set(report.scheduled)
    report.netbox_only_devices = sorted(set(nb.devices) - placed)
    # Wireless gear with no place goes under the wireless sheet, beside its links; the rest under the physical page.
    wireless_g = next((g for g in pages if g.diagram.get("id") == "wireless"), None)
    on_wireless = wireless_page.wireless_only(nb, report.netbox_only_devices) \
        if wireless_g is not None and "wireless" not in skip else []
    for g in pages:
        if g.diagram.get("id") == "physical":
            _add_netbox_cables(g, nb, report)
            rest = [n for n in report.netbox_only_devices if n not in on_wireless]
            if tray and rest:
                _add_tray(g, [nb.devices[n] for n in rest], nb)
            break
    if wireless_g is not None:
        if tray and on_wireless:
            _add_tray(wireless_g, [nb.devices[n] for n in on_wireless], nb)
            report.wireless_tray = list(on_wireless)
        wireless_page.add_links(wireless_g, nb, report, _is_device)
    for g in pages:
        _add_missing_tags(g, nb)
    # A counted group's own cables are on the drawing too: the group card stands for every member.
    members = {m for group in report.grouped.values() for m in group}
    counted = {k for k, c in nb.cables.items()
               if any(d in members for d, _ in _ends(c.get("a_terminations"), nb.names)
                      + _ends(c.get("b_terminations"), nb.names))}
    report.netbox_only_cables = sorted(set(nb.cables) - report.matched_cables - set(report.added_cables) - counted)
    for g in pages:
        for sheet in typicals.move_long_tables(template, g):
            report.register_sheets.append(sheet.get("name"))
            reg = Graph(sheet)
            top = float(reg.model.get("pageHeight", 1000))
            if _copy_title_block(g, reg, 24, top, "Registers", sheet.get("name").split(" ", 1)[0]):
                reg.model.set("pageHeight", f"{top + 100:g}")
    grew = report.grouped and profiles.current().glance_on_groups
    if glance or (glance is None and (grew or report.netbox_only_devices)):
        _add_glance(template, pages, export, report)
        report.glance = True
    if riser or (riser is None and riser_mod.wanted(export, endpoint_roles())):
        _add_riser(template, pages, export, report, nb)
        report.riser = True
    if audit or (audit is None and nb.audit.any):
        _add_audit(template, pages, export, report, nb, today)
        report.audit = True
    checked = report.intake.data_date or today or dt.date.today().isoformat()
    found = gaps.find(export, endpoint_roles(), lambda d: ot.device_zones(d, nb.locations), checked)
    report.template_leftovers = wireless_page.leftovers(template)  # captions the build kept, not ones it later removed
    report.quality = _assess_quality(export, nb, report, today, found, template, {rename(t) for t in template_names})
    if quality_sheet:
        _add_quality(template, pages, report, previous_quality)
    report.state = changes_mod.fingerprint(export, lambda d: ot.device_zones(d, nb.locations),
                                           report.provenance.revision, report.provenance.built)
    report.changes_since = changes_mod.compare(report.state, previous_state)
    report.marked_changes = changes_mod.mark(template, report.changes_since, _is_device)
    for diagram in template.findall("diagram"):
        if diagram.get("id") == "wireless" and diagram.find("mxGraphModel") is not None:
            report.examples_marked += wireless_page.mark_example_regions(
                Graph(diagram), {rename(t) for t in template_names}, nb)
            wireless_page.add_area_register(Graph(diagram), nb)  # before the plan card, which goes under it
    if data_gaps:
        _add_gap_cards(template, nb, found, checked, {rename(t) for t in template_names}, report.template_leftovers)
    if book_note:
        for diagram in template.findall("diagram"):
            _add_book_note(Graph(diagram))
    for g in [Graph(d) for d in template.findall("diagram")]:
        _big_site_legend(g)
        for table in g.tables():
            g.tighten_card(table)
        _fit_border(g)
    if controls:
        interactive.add_to_all(template)
    report.skipped_pages = page_list.remove(template, skip)
    _number_sheets(template)
    big = paper.SIZES[-1]
    report.oversize = [f"{d.get('name')}: {w:g} × {h:g}" for d in template.findall("diagram")
                       if d.find("mxGraphModel") is not None
                       for w, h in [paper.content_size(d.find("mxGraphModel"))] if w > big[1] or h > big[2]]
    return report


def _number_sheets(template: ET.Element) -> None:
    """'3b of 13': each sheet's number out of the sheets this file really has, after pages came and went."""
    diagrams = template.findall("diagram")
    for diagram in diagrams:
        if diagram.find("mxGraphModel") is None:
            continue
        g = Graph(diagram)
        sheet = (diagram.get("name") or "").split(" ", 1)[0]
        for table in g.tables():
            header = g.header(table)
            rows = g.rows(table)
            if "SHEET" not in header or "DATE" not in header or len(rows) < 2:
                continue
            cell = g.els[g.row_cells(rows[1])[header.index("SHEET")]]
            g.set_value(cell, f"{sheet} of {len(diagrams)}")


CELL_RANGE = re.compile(r"CELL0?1(\s*)[–-](\s*)0?3\b")


def _cell_ranges(g: Graph, nb: NetBoxIndex) -> None:
    """Template text naming the template's cells ('CELL01–03') names the site's cells instead."""
    numbers = {int(m.group(1)) for d in nb.devices.values() for t in d.get("tags") or []
               for m in [re.match(r"zone-cell(\d+)$", t.get("slug") or "")] if m}
    if not numbers or max(numbers) == 3:
        return
    last = f"CELL01–{max(numbers):02d}" if max(numbers) > 1 else "CELL01"
    for el in g.els.values():
        value = g.value(el)
        if value and CELL_RANGE.search(value):
            g.set_value(el, CELL_RANGE.sub(last, value))


BIG_SITE_SYMBOLS = (
    ("typical", '<b style="color:#4338CA">TYPICAL ×N</b> drawn once; every copy has a row in its schedule'),
    ("copy", '<b>CELL27 ›</b> click a schedule row to show that copy over the typical '
             '(<span style="color:#4338CA">indigo dashed outline</span>)'),
    ("group", "<b>PLC ×20</b> devices of one role on one switch, drawn once and counted; click for the list"),
    ("pointer", "<b>On sheet 3r</b> a register too long for this page continues on its own sheet"),
)


def _add_gap_cards(template: ET.Element, nb: NetBoxIndex, found: dict, checked: str, template_devices: set[str],
                   leftovers: dict | None = None) -> None:
    """Give each data page a 'Plan to improve this page' card: what NetBox is missing for it (``found``)."""
    real, prefix = set(nb.devices), site_prefix(nb.devices)

    def link(gap):
        devices = [n for n in gap.names if n in nb.devices]
        if devices and len(devices) == len(gap.names) and len(devices) <= 40:
            return nb.link("dcim/devices", id=[nb.devices[n].get("id") for n in devices])
        return ""

    for diagram in template.findall("diagram"):
        keys = gaps.PAGES.get(diagram.get("id") or "")
        if keys is None or diagram.find("mxGraphModel") is None:
            continue
        g = Graph(diagram)
        items = []
        if diagram.get("id") in truth.example_sheets():
            items.append(gaps.example_sheet(*truth.example_sheets()[diagram.get("id")]))
        for key in keys:
            if key == "template_examples":
                names = gaps.template_examples(g, real, prefix, template_devices, wireless_page.backed_names(nb))
                names = sorted(set(names) | (leftovers or {}).get(diagram.get("id") or "", set()))
                shown = ", ".join(_short_dev(n) for n in names[:4]) + (f" +{len(names) - 4} more" if len(names) > 4 else "")
                items.append(gaps.Gap(**{**gaps.EXAMPLES.__dict__, "names": names,
                                         "how": f"Replace with the site's own, or delete: {shown}"}))
            else:
                items.append(found[key])
        gaps.add_card(g, items, checked, link)
        if diagram.get("id") in ("physical", "wireless"):
            gaps.mark_empty(g, _is_device, template_devices, real, prefix)


# The book and chapter that explain each sheet come from the profile (profiles.py);
# these are the manufacturing standard's.
BOOK = profiles.MANUFACTURING.book
BOOK_URL = profiles.MANUFACTURING.book_url
# Page id -> (chapter, title, link): the chapter that explains how to draw that sheet.
CHAPTERS = profiles.MANUFACTURING.chapters
BOOK_LAYER = "How to draw this page"


def _add_book_note(g: Graph) -> None:
    """One small line under the sheet: the book chapter that explains how to draw it."""
    chapter = profiles.current().chapters.get(g.diagram.get("id") or "")
    layer = f"{g.diagram.get('id')}-book"
    if not chapter or layer in g.els or g.model is None:
        return
    number, title, link = chapter
    skip = ("Border", "Controls", "Guides", "Copy of the typical")
    bottom = max((g.box(i)[1] + g.box(i)[3] for i, el in g.els.items() if cell_of(el) is not None
                  and cell_of(el).get("vertex") == "1" and cell_of(el).get("parent") in g.layers
                  and not g.layer_of(i).startswith(skip)), default=0)
    # The line never runs through the title block: on a page where that block sits low on the left
    # (register and glance sheets), the line goes under it.
    for i, el in g.els.items():
        cell = cell_of(el)
        if cell is None or cell.get("vertex") != "1" or cell.get("parent") not in g.layers:
            continue
        if not g.layer_of(i).startswith("Border") or g.box(i)[2] > 1000:
            continue
        x, y, w, h = g.box(i)
        if x < 924 and x + w > 24 and y < bottom + 28 and y + h > bottom:
            bottom = max(bottom, y + h)
    g.root.append(ET.Element("mxCell", {"id": layer, "value": BOOK_LAYER, "style": "", "parent": "0"}))
    note = ET.SubElement(g.root, "object", {
        "id": f"{layer}-note", "link": link, "linkTarget": "_blank",
        "label": f"How to draw this page: <b>Chapter {number}, {title}</b> · <i>{profiles.current().book}</i> · "
                 f"{link.split('//', 1)[1].rstrip('/')}"})
    cell = ET.SubElement(note, "mxCell", {
        "vertex": "1", "parent": layer,
        "style": "text;html=1;align=left;verticalAlign=middle;fontSize=10;fontFamily=Inter;fontColor=#64748B;"
                 "spacing=0;whiteSpace=nowrap;"})
    ET.SubElement(cell, "mxGeometry", {"x": "24", "y": f"{bottom + 10:g}", "width": "900", "height": "18",
                                       "as": "geometry"})
    g.reindex()


def _fit_border(g: Graph) -> None:
    """Grow the page border (and page) to hold everything, after tables and schedules grew."""
    border = next((i for i in g.els if g.layer_of(i).startswith("Border") and g.box(i)[2] > 1000
                   and cell_of(g.els[i]).get("parent") in g.layers), None)
    if border is None:
        return
    bx, by, bw, bh = g.box(border)
    bottom = max((g.box(i)[1] + g.box(i)[3] for i, el in g.els.items() if i != border
                  and cell_of(el).get("vertex") == "1" and cell_of(el).get("parent") in g.layers), default=0)
    if bottom > by + bh:
        g.geometry(border).set("height", f"{bottom + 16 - by:g}")
        if float(g.model.get("pageHeight", 0)) < bottom + 26:
            g.model.set("pageHeight", f"{bottom + 26:g}")


def _overlaps(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _big_site_legend(g: Graph) -> None:
    """Add the symbols a big site brings (typicals, copies, counted groups) to the page's legend."""
    texts = " ".join(plain(g.value(el)) for el in g.els.values())
    found = {"typical": "TYPICAL ×" in texts,
             "copy": any(name.startswith("Copy of the typical") for name in g.layers.values()),
             "group": any(el.get("netdiagrams_group") for el in g.els.values()),
             "pointer": bool(re.search(r"rows, on sheet \w+", texts))}
    lines = [text.replace("PLC ×20", profiles.word("group_example")) for key, text in BIG_SITE_SYMBOLS if found[key]]
    legend = [i for i in g.els if g.layer_of(i) == "Legend" and cell_of(g.els[i]).get("vertex") == "1"]
    if not lines or not legend:
        return
    title = next((i for i in legend if plain(g.value(g.els[i])).strip() == "Legend"), None)
    if title is None:
        return
    note_id = f"{g.diagram.get('id')}-legend-big-site"
    if note_id in g.els:  # rebuilt from a drawing that has the note: the card made room for it before
        g.els[note_id].set("value", '<b style="color:#334155">Big sites</b><br>' + "<br>".join(lines))
        return
    tx, ty = g.box(title)[:2]
    around = [i for i in legend if i != title and _overlaps(g.box(i), (tx, ty, 1, 1))]
    if not around:
        return
    card = min(around, key=lambda i: g.box(i)[2] * g.box(i)[3])
    x, y, w, h = g.box(card)
    per_line = max(20, (w - 28) / 4.6)
    extra = 26 + 13 * sum(-(-len(plain(text)) // per_line) for text in lines)
    # Grow the legend upward when the space above it is free, so nothing else on the page moves.
    background = (profiles.current().band_layer, "Border", "Guides", "Controls", "Legend", "Zones")
    above_free = y - extra > 60 and not any(
        cell_of(el).get("vertex") == "1" and not g.layer_of(i).startswith(background)
        and _overlaps(g.box(i), (x, y - extra - 8, w, extra + 8)) for i, el in g.els.items())
    if above_free:
        for i in legend:
            if cell_of(g.els[i]).get("parent") == g.layer_id(i):
                geo = g.geometry(i)
                geo.set("y", f"{float(geo.get('y', 0)) - extra:g}")
        for i, el in g.els.items():
            if g.layer_of(i) == "Legend" and cell_of(el).get("edge") == "1":
                for pt in cell_of(el).iter("mxPoint"):
                    if pt.get("as") != "offset" and pt.get("y") is not None:
                        pt.set("y", f"{float(pt.get('y')) - extra:g}")
        y -= extra
    else:
        # Move everything under the legend, widening the column to whole shapes (a title block).
        x0, x1 = x, x + w
        below = [g.box(i) for i, el in g.els.items() if cell_of(el).get("vertex") == "1"
                 and cell_of(el).get("parent") in g.layers and g.box(i)[1] >= y + h - 0.5]
        while True:
            hit = [b for b in below if b[0] < x1 and b[0] + b[2] > x0]
            nx0, nx1 = min([x0] + [b[0] for b in hit]), max([x1] + [b[0] + b[2] for b in hit])
            if (nx0, nx1) == (x0, x1):
                break
            x0, x1 = nx0, nx1
        g.shift_below(x0, x1, y + h - 0.5, extra, {card})
        for i in g.els:
            if g.layer_of(i).startswith("Border") and g.box(i)[1] < y and g.box(i)[1] + g.box(i)[3] > y + h:
                border = g.geometry(i)
                border.set("height", f"{float(border.get('height')) + extra:g}")
    geo = g.geometry(card)
    geo.set("height", f"{float(geo.get('height')) + extra:g}")
    el = ET.SubElement(g.root, "mxCell", {
        "id": note_id, "vertex": "1", "parent": g.layer_id(card),
        "value": '<b style="color:#334155">Big sites</b><br>' + "<br>".join(lines),
        "style": "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=9;fontFamily=Inter;"
                 "fontColor=#334155;spacing=0;"})
    ET.SubElement(el, "mxGeometry", {"x": f"{x + 14:g}", "y": f"{y + h - 4:g}", "width": f"{w - 28:g}",
                                     "height": f"{extra:g}", "as": "geometry"})
    g.reindex()


GLANCE_NAME = "1b · Site at a glance — zones and counts from NetBox"


def _after(template: ET.Element, ids: tuple[str, ...]) -> ET.Element | None:
    """The first of these sheets the drawing has."""
    return next((d for pid in ids for d in template.findall("diagram") if d.get("id") == pid), None)


def _insert_sheet(template: ET.Element, pages: list[Graph], diagram: ET.Element, report: Report, drawing: str,
                  sheet: str, after: ET.Element | None) -> None:
    """Put a generated sheet after ``after``, with the physical page's title block and the site code in its title."""
    g = Graph(diagram)
    source = next((p for p in pages if p.diagram.get("id") == "physical"), pages[0] if pages else None)
    top = float(g.model.get("pageHeight", 1000)) + 16
    if source is not None and _copy_title_block(source, g, 24, top, drawing, sheet):
        g.model.set("pageHeight", f"{top + 90:g}")
    title = g.els.get(f"{diagram.get('id')}-c1")
    if title is not None and report.site_code:
        g.set_value(title, f"{report.site_code} · {g.value(title)}")
    children = list(template)
    index = children.index(after) + 1 if after is not None else len(children)
    while after is not None and index < len(children) and \
            (children[index].get("id") or "").startswith(f"{after.get('id')}-registers"):
        index += 1  # a sheet's register sheets stay with it
    template.insert(index, diagram)


def _add_glance(template: ET.Element, pages: list[Graph], export: dict, report: Report) -> None:
    """Insert the zone overview after the first page, with the template's own title block."""
    site = build_site(export)
    if report.site_code and not site.slug:
        site.slug = report.site_code
    diagram = overview.page(site, name=GLANCE_NAME, footer=False)
    _insert_sheet(template, pages, diagram, report, "Site at a glance", "1b", pages[0].diagram if pages else None)


AUDIT_AFTER = ("riser", "wireless-registers", "wireless", "platforms", "hardware", "physical-registers", "physical")


def _add_audit(template: ET.Element, pages: list[Graph], export: dict, report: Report, nb: NetBoxIndex,
               today: str | None) -> None:
    """Insert the audit evidence sheet (3f) after the physical sheets (and the riser), with the title block."""
    as_of = report.intake.data_date or today or dt.date.today().isoformat()
    link = (lambda f: nb.link("dcim/devices", nb.devices[f.name]) if f.name in nb.devices else "") if nb.url else None
    diagram = audit_mod.page(nb.audit, export, as_of, lambda d: ot.device_zones(d, nb.locations), link,
                             report.provenance.revision)
    _insert_sheet(template, pages, diagram, report, "Audit evidence", audit_mod.SHEET, _after(template, AUDIT_AFTER))


RISER_AFTER = ("wireless-registers", "wireless", "platforms", "hardware", "physical-registers", "physical")


def _add_riser(template: ET.Element, pages: list[Graph], export: dict, report: Report, nb: NetBoxIndex) -> None:
    """Insert the riser sheet (3e) after the last of the physical sheets, with the template's title block."""
    diagram = riser_mod.page(export, endpoint_roles(), nb.url, report.site_code)
    _insert_sheet(template, pages, diagram, report, "Riser", riser_mod.SHEET, _after(template, RISER_AFTER))


def _assess_quality(export: dict, nb: NetBoxIndex, report: Report, today: str | None, found: dict,
                    template: ET.Element | None = None, template_devices: set[str] | None = None) -> "quality.Scorecard":
    checked = report.intake.data_date or today or dt.date.today().isoformat()
    found = dict(found)  # the template's leftovers count here, not on the gap cards
    if template is not None:
        # Template words left on the drawing count against the score: they read as this site's facts.
        names = {n for leftovers in report.template_leftovers.values() for n in leftovers}
        backed = wireless_page.backed_names(nb)
        for diagram in template.findall("diagram"):
            if diagram.find("mxGraphModel") is not None and diagram.get("id") in gaps.PAGES:
                names.update(gaps.template_examples(Graph(diagram), set(nb.devices), site_prefix(nb.devices),
                                                    template_devices or set(), backed))
        found["template_examples"] = gaps.Gap(**{**gaps.EXAMPLES.__dict__, "names": sorted(names)})
    site = model.build_site(export)
    return quality.assess(export, found, site, endpoint_roles(), report.intake.data_date, report.provenance.revision)


def _add_quality(template: ET.Element, pages: list[Graph], report: Report, previous: dict | None) -> None:
    """Insert the data quality sheet after the glance page (or the first page), with the title block."""
    diagram = quality.page(report.quality, previous)
    after = _after(template, ("glance",))
    if after is None and pages:
        after = pages[0].diagram
    _insert_sheet(template, pages, diagram, report, "Data quality", "1c", after)


def _copy_title_block(src: Graph, dst: Graph, x: float, y: float, drawing: str, sheet: str) -> bool:
    """Copy the title block (the card holding the SITE / DATE table) from one page to another."""
    table = next((t for t in src.tables() if {"SITE", "DATE"} <= set(src.header(t))), None)
    if table is None:
        return False
    tx, ty, tw, th = src.box(table)
    card = None
    for i, el in src.els.items():
        cell = cell_of(el)
        if i == table or cell is None or cell.get("vertex") != "1" or cell.get("parent") not in src.layers:
            continue
        cx, cy, cw, ch = src.box(i)
        if cx <= tx and cy <= ty and cx + cw >= tx + tw and cy + ch >= ty + th:
            if card is None or cw * ch < src.box(card)[2] * src.box(card)[3]:
                card = i
    cx, cy, cw, ch = src.box(card) if card else (tx, ty, tw, th)
    tops = [i for i, el in src.els.items()
            if cell_of(el) is not None and cell_of(el).get("vertex") == "1"
            and cell_of(el).get("parent") in src.layers
            and cx - 1 <= src.box(i)[0] and cy - 1 <= src.box(i)[1]
            and src.box(i)[0] + src.box(i)[2] <= cx + cw + 1 and src.box(i)[1] + src.box(i)[3] <= cy + ch + 1]
    layer = f"{dst.diagram.get('id')}-title-block"
    dst.root.append(ET.Element("mxCell", {"id": layer, "value": "Border & title block", "style": "", "parent": "0"}))
    ids = set(tops)
    for i in tops:
        ids.update(src.descendants(i))
    prefix = f"{dst.diagram.get('id')}-tb-"
    for el in src.root:
        if el.get("id") not in ids:
            continue
        new = copy.deepcopy(el)
        new.set("id", prefix + el.get("id"))
        cell = cell_of(new)
        if cell.get("parent") in src.layers:
            cell.set("parent", layer)
            geo = cell.find("mxGeometry")
            geo.set("x", f"{float(geo.get('x', 0)) - cx + x:g}")
            geo.set("y", f"{float(geo.get('y', 0)) - cy + y:g}")
        else:
            cell.set("parent", prefix + cell.get("parent"))
        dst.root.append(new)
    dst.reindex()
    copied = prefix + table
    header = dst.header(copied)
    rows = dst.rows(copied)
    if len(rows) > 1:
        for col, cell_id in zip(header, dst.row_cells(rows[1])):
            if col == "DRAWING":
                dst.set_value(dst.els[cell_id], drawing)
            elif col == "SHEET":
                dst.set_value(dst.els[cell_id], sheet)
    return True


def _renamer(prefix_map):
    def rename(name: str) -> str:
        for old, new in prefix_map.items():
            if name.startswith(old):
                return new + name[len(old):]
        return name
    return rename


def _device_zones(d: dict, nb: "NetBoxIndex | None" = None) -> set[str]:
    return set(ot.device_zones(d, nb.locations if nb else None))


def _zone_tags(tags: str) -> set[str]:
    return {t.strip() for t in (tags or "").split(",") if t.strip().startswith("zone-")}


def _assign_slots(pages, names_after, matched, nb: NetBoxIndex) -> dict[str, str]:
    """Pair each unmatched template device with an unmatched NetBox device of the same role."""
    info = {}
    for g in pages:
        for el in g.els.values():
            if _is_device(el) and el.get("name") not in info:
                info[el.get("name")] = (el.get("role", ""), _zone_tags(el.get("tags", "")))
    free_nb = sorted(set(nb.devices) - {names_after[t] for t in matched})
    out = {}
    # Slots in the device's own zone first, for every slot, then any slot of the same role.
    for same_zone_only in (True, False):
        for t in sorted(t for t in names_after if t not in matched and t not in out):
            role, zones = info.get(t, ("", set()))
            if not role:
                continue
            candidates = [n for n in free_nb if (_get(nb.devices[n], "role", "slug")) == role]
            if same_zone_only:
                candidates = [n for n in candidates if zones & _device_zones(nb.devices[n], nb)]
            if candidates:
                out[t] = candidates[0]
                free_nb.remove(candidates[0])
    return out


def _group_endpoints(placed: set[str], nb: NetBoxIndex) -> dict[str, list[str]]:
    """Fold each end device with no shape of its own into a drawn device of the same role.

    It joins the drawn device on the same switch, else in the same location,
    else in the same zone. A device whose switch isn't drawn stays with that
    switch, and network gear is never folded: both go to the tray.
    """
    uplinks = _uplinks(nb)
    role = lambda n: _get(nb.devices[n], "role", "slug")
    peer = lambda n: _group(nb, uplinks[n][0]) if n in uplinks else ""
    location = lambda n: _get(nb.devices[n], "location", "name")
    ends = endpoint_roles()
    heads = sorted(n for n in placed if n in nb.devices and role(n) in ends)
    out: dict[str, list[str]] = defaultdict(list)
    for name in sorted(set(nb.devices) - placed):
        if role(name) not in ends or (name in uplinks and uplinks[name][0] not in placed):
            continue
        if nb.wx.is_radio_fed(name):
            continue  # a mesh AP or bridge hangs off a radio: drawn beside its root, never counted into a group
        same = [h for h in heads if role(h) == role(name)]
        zones = _device_zones(nb.devices[name], nb)
        tests = [lambda h: peer(name) and peer(h) == peer(name),
                 lambda h: location(name) and location(h) == location(name)]
        if role(name) not in wireless.WIRELESS_ROLES:
            # The zone alone is too loose for radios: an AP on its own switch in another room is its
            # own coverage, not one more of a drawn AP's; it waits in the wireless tray instead.
            tests.append(lambda h: zones and zones & _device_zones(nb.devices[h], nb))
        for test in tests:
            hits = [h for h in same if test(h)]
            if hits:
                out[hits[-1]].append(name)
                break
    return dict(out)


GROUP_LIST_MAX = 40


def _label_groups(g: Graph, grouped: dict[str, list[str]], nb: NetBoxIndex) -> None:
    """Show a drawn device that stands for several as a group: 'PLC ×12' or 'AP-OF-05 +10 more'."""
    for el in g.els.values():
        members = grouped.get(el.get("name")) if _is_device(el) else None
        if not members:
            continue
        everyone = [el.get("name")] + members
        el.set("netdiagrams_group", ",".join(members))
        label = re.sub(r" (×\d+|\+\d+ more)(?=[\s<·]|$)", "", g.value(el), count=1)
        m = re.match(r"(\s*(?:<b>)?)([^<·]*?)(\s*(?:·|</b>|<br|$))", label)
        if m and _short_dev(el.get("name")) in m.group(2):
            label = f"{m.group(1)}{m.group(2)} +{len(members)} more{label[m.end(2):]}"
        elif m:
            label = f"{m.group(1)}{m.group(2)} ×{len(everyone)}{label[m.end(2):]}"
        g.set_value(el, label)
        if nb.url:
            ids = [nb.devices[n].get("id") for n in everyone]
            if all(ids) and len(ids) <= GROUP_LIST_MAX:
                el.set("link", nb.link("dcim/devices", id=ids))
            else:
                d = nb.devices[el.get("name")]
                query = {"site_id": _get(d, "site", "id"), "role": _get(d, "role", "slug"),
                         "location_id": _get(d, "location", "id")}
                el.set("link", nb.link("dcim/devices", **{k: v for k, v in query.items() if v}))
        shown = everyone[:GROUP_LIST_MAX]
        more = f"\n… and {len(everyone) - len(shown)} more" if len(everyone) > len(shown) else ""
        el.set("tooltip", f"Group of {len(everyone)} devices: " + ", ".join(shown) + more + "\n" + _tooltip(el))


CLOSET_STYLE = ("text;html=1;align=right;verticalAlign=top;fontSize=9;fontFamily=Inter;fontColor=#64748B;"
                "spacing=0;whiteSpace=nowrap;fillColor=#FFFFFF;strokeColor=none;")


def _label_closets(g: Graph, nb: NetBoxIndex) -> None:
    """A box holding devices NetBox places under a building and floor says where it is.

    The template's closet and area boxes carry their own titles; a small line at the top
    right of each adds the NetBox location the devices inside share ('Main building › floor 2
    › IDF-B214'), linked to that location. Nothing is added where NetBox's locations do not
    nest, so a flat site's drawing is unchanged.
    """
    devices = [(i, el) for i, el in g.els.items() if _is_device(el) and el.get("name") in nb.devices and not g.hidden(i)]
    if not devices or not nb.locations.by_id:
        return
    boxes = []
    for i, el in g.els.items():
        cell = cell_of(el)
        if cell is None or cell.get("vertex") != "1" or cell.get("parent") not in g.layers or _is_device(el):
            continue
        style = cell.get("style") or ""
        layer = g.layer_of(i)
        if "rounded=1" not in style or style.startswith("text") or layer.startswith(("Border", "Legend", "Controls")) \
                or layer == profiles.current().band_layer:
            continue
        x, y, w, h = g.box(i)
        if w < 240 or h < 100:
            continue
        boxes.append((i, (x, y, w, h)))
    for box_id, (x, y, w, h) in boxes:
        inside = [el for i, el in devices if _overlaps(g.box(i), (x, y, w, h))
                  and x <= g.box(i)[0] and g.box(i)[0] + g.box(i)[2] <= x + w + 1]
        chains = [nb.locations.card_chain(nb.devices[el.get("name")].get("location")) for el in inside]
        chains = [c for c in chains if c]
        if not chains:
            continue
        common = []
        for step in zip(*chains):
            if len({loc.get("id") for loc in step}) == 1:
                common.append(step[0])
            else:
                break
        if len(common) < 2:
            continue  # no building-and-floor context to add
        path = " › ".join(_label(loc) for loc in common if _label(loc))
        width = min(w - 24, max(80, len(path) * 4.8 + 6))  # Inter 9 px; a wider white box hides the border
        # The note shares the box's top strip only when the box's own title leaves room for it;
        # otherwise it sits just above the box, so the two never print over each other.
        taken = x
        title = html.unescape(re.sub(r"<[^>]+>", "", re.split(r"<br\s*/?>", g.value(g.els[box_id]) or "",
                                                              maxsplit=1)[0])).split("\n")[0]
        if title.strip():
            taken = max(taken, x + 12 + len(title.strip()) * 6.4)
        for j, other in g.els.items():
            oc = cell_of(other)
            if j == box_id or oc is None or oc.get("vertex") != "1" or oc.get("parent") not in g.layers:
                continue
            ox, oy, ow, oh = g.box(j)
            if x <= ox < x + w and y - 2 <= oy < y + 22 and (g.value(other) or "").strip():
                taken = max(taken, ox + ow)
        fits = taken + 8 <= x + w - 12 - width
        nx, ny = x + w - 12 - width, y + 4
        if not fits:
            # just above the box, unless that prints over a band subtitle or another note; then along its bottom
            spots = [(y - 16, False), (y + h - 18, True), (y + h + 2, False)]
            ny = next((sy for sy, inner in spots if not any(
                _overlaps(g.box(j), (nx, sy, width, 14)) and not _inside((nx, sy, width, 14), g.box(j))
                for j, other in g.els.items()
                if j != box_id and (cell_of(other) is not None and cell_of(other).get("vertex") == "1")
                and not g.hidden(j) and (inner or plain(g.value(other)).strip()))), y - 16)
        note = ET.SubElement(g.root, "object", {
            "id": f"{box_id}-closet", "label": html.escape(path), "netdiagrams_closet": "1",
            "tooltip": f"NetBox location of the {len(inside)} device{'s' if len(inside) != 1 else ''} in this box: {path}"})
        if nb.url and common[-1].get("id") is not None:
            note.set("link", f"{nb.url}/dcim/locations/{common[-1]['id']}/")
            note.set("linkTarget", "_blank")
        cell = ET.SubElement(note, "mxCell", {"style": CLOSET_STYLE, "vertex": "1", "parent": g.layer_id(box_id)})
        ET.SubElement(cell, "mxGeometry", {"x": f"{nx:g}", "y": f"{ny:g}",
                                           "width": f"{width:g}", "height": "14", "as": "geometry"})
    g.reindex()


def _rename_everywhere(g: Graph, names_after: dict[str, str], rename) -> None:
    for el in g.els.values():
        if _is_device(el) and el.get("name") in names_after:
            el.set("name", names_after[el.get("name")])
        if el.get("device") and el.get("name") is not None and not _is_device(el):
            el.set("device", names_after.get(el.get("device"), rename(el.get("device"))))
        for key in ("a_terminations", "b_terminations", "x_handoff", "interface_a", "interface_b"):
            if el.get(key):
                parts = []
                for end in el.get(key).split(","):
                    dev, _, port = end.strip().partition(":")
                    parts.append(f"{names_after.get(dev, rename(dev))}:{port}" if port else end.strip())
                el.set(key, ", ".join(parts))
        for key in ("x_cable", "ssid"):  # a cable label or SSID named after the template's site
            if el.get(key):
                el.set(key, rename(el.get(key)))


GENERATED_PAGES = ("glance", quality.PAGE_ID, riser_mod.PAGE_ID, audit_mod.PAGE_ID)
GENERATED_LAYERS = ("Example watermark", "Schedules (copies of the typicals)", "Links from NetBox (not in the template)", CRITICALITY_LAYER,
                    SCOPE_LAYER,
                    changes_mod.LAYER, gaps.LAYER, interactive.CONTROLS_LAYER, UNPLACED_LAYER, "How to draw this page",
                    wireless_page.AREA_LAYER)


def _strip_generated(template: ET.Element) -> None:
    """A drawing built before carries sheets, layers and marks the build makes again.

    Rebuilding from your own last drawing (``--template last.drawio``) is the day-to-day
    path, so those go first: the glance and data quality sheets, the example watermarks,
    the change pills, the tray and the provenance lines. Everything else the build adds
    replaces itself.
    """
    _restore_registers(template)
    for diagram in list(template.findall("diagram")):
        if diagram.get("id") in GENERATED_PAGES:
            template.remove(diagram)
            continue
        if diagram.find("mxGraphModel") is None:
            continue
        g = Graph(diagram)
        doomed = [i for i, name in g.layers.items()
                  if name in GENERATED_LAYERS or name.startswith(typicals.COPY_LAYER.split("{")[0])]
        rooms = [el for el in g.els.values() if el.get("netdiagrams_room") and el.get("netdiagrams_at")]
        for el in sorted(rooms, key=lambda el: -float(el.get("netdiagrams_at").split(",")[0])):
            y, x0, x1 = map(float, el.get("netdiagrams_at").split(","))  # a schedule pushed the page down
            typicals.grow(g, x0, x1, y, -float(el.get("netdiagrams_room")))
        for el in g.els.values():
            if typicals.TYPICAL_TAG.search(g.value(el)):
                g.set_value(el, typicals.TYPICAL_TAG.sub("", g.value(el)))
        doomed += [i for i, el in g.els.items() if el.get("netdiagrams_provenance") == "1"
                   or el.get("netdiagrams_change") or el.get("netdiagrams_closet")]
        for i in doomed:
            if g.els[i].get("netdiagrams_provenance") == "1":  # the title-block card made room for the line
                card = _card_at(g, g.box(i)[0] + 1, g.box(i)[1] + 1, {i})
                if card is not None:
                    g.geometry(card).set("height", f"{g.box(card)[3] - PROVENANCE_EXTRA:g}")
        if doomed:
            g.remove(doomed)


def _card_at(g: Graph, x: float, y: float, skip: set[str]) -> str | None:
    """The smallest top-level vertex under the point (x, y), other than ``skip``."""
    hits = [i for i, el in g.els.items() if cell_of(el) is not None and cell_of(el).get("vertex") == "1"
            and cell_of(el).get("parent") in g.layers and i not in skip
            and g.box(i)[0] <= x <= g.box(i)[0] + g.box(i)[2] and g.box(i)[1] <= y <= g.box(i)[1] + g.box(i)[3]]
    return min(hits, key=lambda i: g.box(i)[2] * g.box(i)[3], default=None)


def _restore_registers(template: ET.Element) -> None:
    """Put a register that spilled onto its own sheet back on the drawing, so the build fills it again.

    A long register moves to a ``…r`` sheet and leaves a pointer card on the drawing. Rebuilding
    from that drawing needs the table itself, so the first column of each spilled register comes
    back where the pointer stands, the sheet goes, and the build spills it afresh.
    """
    by_id = {d.get("id"): d for d in template.findall("diagram")}
    for page_id, sheet in list(by_id.items()):
        if not page_id or not page_id.endswith("-registers") or sheet.find("mxGraphModel") is None:
            continue
        base = by_id.get(page_id[:-len("-registers")])
        if base is None or base.find("mxGraphModel") is None:
            continue
        g = Graph(base)
        more = [d for i, d in by_id.items() if re.fullmatch(rf"{re.escape(page_id)}-\d+", i or "")]
        regs = [Graph(sheet)] + [Graph(d) for d in more]
        for ptr in [i for i in g.els if i.startswith(f"{page_id}-ptr")]:
            n = ptr[len(f"{page_id}-ptr"):]
            old_prefix, new_prefix = f"{page_id}-t{n}-0", f"{base.get('id')}-reg{n}"
            card = f"{old_prefix}-card"
            reg = next((r for r in regs if card in r.els), None)
            if reg is None or (g.els[ptr].get("netdiagrams_from") or "").endswith("-schedule-t"):  # drawn afresh
                g.remove([ptr])
                continue
            left, top, card_w, ptr_h = g.box(ptr)
            cx, cy, _, card_h = reg.box(card)
            layer = g.layer_id(ptr)
            parts = [card, f"{old_prefix}-title", f"{old_prefix}-t"] + reg.descendants(f"{old_prefix}-t")
            moved = []
            for i in parts:
                el = reg.els.get(i)
                if el is None:
                    continue
                cell = cell_of(el)
                # The header row is numbered apart, so the rows the build fills in never share its id.
                el.set("id", new_prefix + i[len(old_prefix):].replace("-t-r0", "-t-head"))
                if cell.get("parent", "").startswith(old_prefix):
                    cell.set("parent", new_prefix + cell.get("parent")[len(old_prefix):].replace("-t-r0", "-t-head"))
                else:
                    cell.set("parent", layer)
                    geo = cell.find("mxGeometry")
                    geo.set("x", f"{float(geo.get('x', 0)) + left - cx:g}")
                    geo.set("y", f"{float(geo.get('y', 0)) + top - cy:g}")
                if i == f"{old_prefix}-title":
                    el.set("value", re.sub(r" \(1 of \d+\)(?=</b>)", "", el.get("value", "")))
                reg.root.remove(el)
                g.root.append(el)
                moved.append(el.get("id"))
            g.remove([ptr])
            g.reindex()
            page_h = g.model.get("pageHeight")
            g.shift_below(left, left + card_w, top + ptr_h - 0.5, card_h - ptr_h, set(moved))
            if page_h:  # the border fit at the end of the build grows the page again if it must
                g.model.set("pageHeight", page_h)
        for d in [sheet] + more:
            template.remove(d)


TAG_STYLE = ("text;html=1;align=left;verticalAlign=middle;spacing=0;fontSize=9;fontFamily=Inter;"
             "fontColor=#475569;whiteSpace=nowrap;")


def _add_missing_tags(g: Graph, nb: NetBoxIndex) -> None:
    """A drawn network device with no IP or serial tag of its own gets one on the tag layers.

    Template devices bring their tags; a card from the tray, or one someone drew by hand
    and matched by name, had none, so its address and serial never showed and never
    followed NetBox. End devices stay as the template draws them, without tags.
    """
    layers = {}
    for lid, name in g.layers.items():
        for key, fld in TAG_LAYERS:
            if key in name.lower() and fld != "cid":
                layers.setdefault(fld, lid)
    if not layers:
        return
    tagged = {(el.get("netdiagrams_ref"), el.get("netdiagrams_field")) for el in g.els.values()
              if el.get("netdiagrams_ref")}
    styles = {}
    for fld, lid in layers.items():
        proto = next((el for i, el in g.els.items() if el.get("netdiagrams_field") == fld
                      and g.layer_of(i) == g.layers[lid] and cell_of(el) is not None
                      and (cell_of(el).get("style") or "").startswith("text")), None)
        styles[fld] = cell_of(proto).get("style") if proto is not None else TAG_STYLE
    ends = endpoint_roles()
    new = []
    for i, el in list(g.els.items()):
        d = nb.devices.get(el.get("name") or "")
        if not _is_device(el) or d is None or g.hidden(i) or _get(d, "role", "slug") in ends:
            continue
        x, y, w, h = g.box(i)
        if w < 80:
            continue
        slot = 0
        for fld, lid in layers.items():
            if (i, fld) in tagged:
                continue
            value = (el.get(fld) or "").split("/")[0]
            if not value:
                continue
            fmt = "SN {}" if fld == "serial" else "{}"
            text = fmt.replace("{}", html.escape(value, quote=False))
            tag = ET.Element("object", {"id": f"{i}-tag-{fld}", "label": text, "netdiagrams_ref": i,
                                        "netdiagrams_field": fld, "netdiagrams_format": fmt})
            if el.get("link"):
                tag.set("link", el.get("link"))
                tag.set("linkTarget", "_blank")
            cell = ET.SubElement(tag, "mxCell", {"vertex": "1", "parent": lid, "style": styles[fld]})
            width = round(len(plain(text)) * 5.6 + 8)
            # a stack member row is one line in its stack card: the tag goes at the row's right end, not under it
            tx, ty = (x + w - 6 - slot - width, y + (h - 14) / 2) if h <= 30 else (x + slot, y + h + 2)
            ET.SubElement(cell, "mxGeometry", {"x": f"{tx:g}", "y": f"{ty:g}", "width": f"{width}",
                                               "height": "14", "as": "geometry"})
            new.append(tag)
            slot += width + 6
    if new:
        g.root.extend(new)
        g.reindex()


IP_TEXT = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def _fill_interface_tables(g: Graph, nb: NetBoxIndex, site) -> None:
    """An INTERFACE / ZONE / VLAN / IP table (a firewall's sub-interfaces) follows NetBox's IP addresses.

    The interface names are the template's; the addresses, VLANs and zones are the site's,
    read from the IP addresses NetBox assigns to interfaces of that name. An interface
    NetBox has no address for shows ? rather than the template's address, and an
    addressed interface the template does not list gets a row.
    """
    if not nb.devices:
        return
    for table in g.tables():
        header = [h.upper() for h in g.header(table)]
        if header[:1] != ["INTERFACE"] or not any(h.startswith("IP") for h in header):
            continue
        ip_col = next(k for k, h in enumerate(header) if h.startswith("IP"))
        vlan_col = header.index("VLAN") if "VLAN" in header else None
        zone_col = header.index("ZONE") if "ZONE" in header else None
        rows_text = _table_text(g, table)
        names = {r[0].strip().lower() for r in rows_text if r}
        addressed = [(a, (a.get("assigned_object") or {}).get("name") or "",
                      ((a.get("assigned_object") or {}).get("device") or {}).get("name") or "")
                     for a in nb.ip_addresses if a.get("address")]
        owners = {dev for _, name, dev in addressed if dev in nb.devices and name.lower() in names}
        if not owners:
            owners = {n for n, d in nb.devices.items() if _get(d, "role", "slug") == "firewall"}
        by_name: dict[str, list] = {}
        for a, name, dev in addressed:
            if dev in owners:
                by_name.setdefault(name.lower(), []).append((dev, a))
        rows, seen = [], set()
        for r in rows_text:
            cells = [(c, "") for c in r]
            key = r[0].strip().lower() if r else ""
            if key in by_name:
                seen.add(key)
                cells = _interface_row(r, by_name[key], ip_col, vlan_col, zone_col, nb, site)
            elif IP_TEXT.search(r[ip_col] if len(r) > ip_col else ""):
                # The template's address, VLAN and zone would read as this site's: all three go.
                for col in (ip_col, vlan_col, zone_col):
                    if col is not None and col < len(cells):
                        cells[col] = (truth.MISSING, "", True, "No IP address on this interface in NetBox")
            rows.append(cells)
        for key in sorted(set(by_name) - seen, key=_natural):
            blank = [""] * len(header)
            blank[0] = by_name[key][0][1]["assigned_object"]["name"]
            rows.append(_interface_row(blank, by_name[key], ip_col, vlan_col, zone_col, nb, site))
        if rows != [[(c, "") for c in r] for r in rows_text]:
            g.fill_table(table, rows)


def _interface_row(r: list[str], found: list, ip_col: int, vlan_col, zone_col, nb: NetBoxIndex, site) -> list:
    cells = [(c, "") for c in r]
    found = sorted(found, key=lambda pair: _natural(pair[0]))
    shown = [a["address"] for _, a in found]  # each address in full: an HA pair's two, side by side
    link = nb.link("ipam/ip-addresses", found[0][1]) if found[0][1].get("id") else ""
    cells[ip_col] = (" · ".join(shown), link)
    # VLAN and zone come from the prefix NetBox holds the address in, never from the template's row.
    prefix = _prefix_of(found[0][1]["address"], nb) or {}
    vid = _get(prefix, "vlan", "vid", default=None)
    if vlan_col is not None:
        cells[vlan_col] = (str(vid), "") if vid is not None else \
            (truth.MISSING, "", True, "No prefix with a VLAN holds this address in NetBox")
    if zone_col is not None:
        vlan = next((v for v in nb.vlans if v.get("id") == _get(prefix, "vlan", "id", default=None)), {})
        slug = ot.vlan_zone(vlan, [prefix]) if vlan else ""
        if not slug:
            slug = next((t.get("slug") for t in prefix.get("tags") or [] if (t.get("slug") or "").startswith("zone-")), "")
        if slug:
            zone = site.zones.get(slug)
            cells[zone_col] = (overview.zone_title(zone) if zone else slug[5:].replace("-", " ").upper(), "")
        else:
            cells[zone_col] = (truth.MISSING, "", True, "No zone tag on this address's VLAN or prefix in NetBox")
    return cells


def _prefix_of(address: str, nb: NetBoxIndex) -> dict | None:
    try:
        ip = ipaddress.ip_interface(address).ip
    except ValueError:
        return None
    best = None
    for p in nb.prefixes:
        try:
            net = ipaddress.ip_network(p.get("prefix", ""), strict=False)
        except ValueError:
            continue
        if ip in net and (best is None or net.prefixlen > best[0]):
            best = (net.prefixlen, p)
    return best[1] if best else None


def _rename_labels(g: Graph, names_after: dict[str, str], prefix_map: dict[str, str]) -> None:
    """Free text that names a template device or carries the template's prefix follows the rename.

    Group titles ("S01-FW-EDGE · Internet edge"), zone notes ("Gateways on S01-IT-CORE") and
    flow rows name devices in plain text, not through an attribute. Example sheets are left
    alone: they describe the template's own estate and are watermarked as such.
    """
    heads = "|".join(re.escape(old) for old in prefix_map)
    token = re.compile(rf"(?<![A-Za-z0-9])(?:{heads})[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?")
    rename = _renamer(prefix_map)

    def swap(m: re.Match) -> str:
        name = m.group(0)
        return names_after.get(name) or rename(name)

    for el in g.els.values():
        attrs = ["label" if el.tag in ("object", "UserObject") else "value", "tooltip", "link"]
        if not _is_device(el):
            attrs.append("name")  # a stack or virtual chassis title, resolved into its label by draw.io
        for attr in attrs:
            text = el.get(attr)
            if text and token.search(text):
                el.set(attr, token.sub(swap, text))


def _fill_devices(g: Graph, nb: NetBoxIndex, report: Report) -> None:
    for el in g.els.values():
        if not _is_device(el) or el.get("name") not in nb.devices:
            continue
        name = el.get("name")
        _update(el, nb.device_attrs(name), report, g.name, "device", name)
        if " › " in (el.get("location_path") or "") and "%location%" in (el.get("label") or ""):
            # The card names the room: with buildings and floors in NetBox it names the whole path.
            el.set("label", el.get("label").replace("%location%", "%location_path%"))
        if nb.url:
            el.set("link", nb.link("dcim/devices", nb.devices[name]))
            el.set("linkTarget", "_blank")
    marks: dict[str, list] = {CRITICALITY_LAYER: [], SCOPE_LAYER: []}
    for i in [i for i, el in g.els.items() if _is_device(el) and el.get("name") in nb.devices]:
        name = g.els[i].get("name")
        g.root.extend(status_marks(g.els[i], i, intake.status(nb.devices[name]), g.box(i)[2]))
        for suffix in ("crit", "scope"):
            old = g.els.get(f"{i}-{suffix}")
            if old is not None:
                g.root.remove(old)
        facts = nb.audit.devices.get(name)
        for key, value in (("owner", facts.owner if facts else None), ("custodian", facts.custodian if facts else None)):
            text = "" if value is None else str(value.value) + (" (tenant)" if value.where == "tenant" else "")
            if text or g.els[i].get(key):
                _update(g.els[i], {key: text}, report, g.name, "device", name)
        g.els[i].set("tooltip", _tooltip(g.els[i]))  # after the owner and custodian, so it shows this build's
        level = nb.device_attrs(name).get("cf_criticality") or ""   # NetBox's rating, not the drawing's
        if not g.hidden(i):
            marks[CRITICALITY_LAYER] += criticality_marks(g.els[i], i, g.box(i), level)
            marks[SCOPE_LAYER] += scope_marks(g.els[i], i, g.box(i), facts.scope if facts else [])
    for layer_name, shapes in marks.items():
        layer = next((lid for lid, n in g.layers.items() if n == layer_name), None)
        if shapes and layer is None:
            layer = f"{g.diagram.get('id', 'p')}-{'crit' if layer_name == CRITICALITY_LAYER else 'scope'}-layer"
            g.root.append(ET.Element("mxCell", {"id": layer, "value": layer_name, "style": "", "parent": "0"}))
        for shape in shapes:
            cell_of(shape).set("parent", layer)
            g.root.append(shape)
    g.reindex()
    _name_generated_layers(g)


LAYERS_CARD = "<b>Layers on this sheet</b>"
# Layers the build adds to a page: the line the page's layer card gives each, and its name in the sentence
# about hiding layers by hand before an export.
LAYER_LEGEND = ((CRITICALITY_LAYER, "Asset criticality — <i>hide before sharing</i>", "Asset criticality"),
                (SCOPE_LAYER, "Compliance scope — <i>hide before sharing</i>", "Compliance scope"))
CRITICALITY_LEGEND = LAYER_LEGEND[0][1]
HIDE_BY_HAND = re.compile(r"hide layers ([^.<>]*?) by hand")


def _name_generated_layers(g: Graph) -> None:
    """The page's layer card names the layers the build added, in the list and in the 'hide layers … by hand'
    sentence, so someone who exports by hand instead of running `share` hides them too; a layer the page
    no longer has comes off the card again."""
    present = set(g.layers.values())
    ours = {line for _, line, _ in LAYER_LEGEND}
    shorts = {short for *_, short in LAYER_LEGEND}
    for el in g.els.values():
        text = g.value(el)
        if not text.startswith(LAYERS_CARD):
            continue
        lines = [line for line in text.split("<br>") if line not in ours]
        last = max((k for k, line in enumerate(lines) if re.match(r"\d+[a-z]? · ", line)), default=None)
        if last is None:
            continue
        lines[last + 1:last + 1] = [line for layer, line, _ in LAYER_LEGEND if layer in present]

        def sentence(m: re.Match) -> str:
            names = [n for n in re.split(r", | and ", m.group(1)) if n not in shorts]
            names += [short for layer, _, short in LAYER_LEGEND if layer in present]
            joined = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
            return f"hide layers {joined} by hand"

        new = HIDE_BY_HAND.sub(sentence, "<br>".join(lines))
        if new != text:
            g.set_value(el, new)


# Planned devices are drawn dashed; offline and failed ones get an amber outline. Each gets a pill.
STATUS_LOOK = {
    "planned": ("dashed=1;dashPattern=6 4;strokeColor=#64748B;opacity=80;", "#F1F5F9", "#475569", "Planned"),
    "offline": ("strokeColor=#D97706;strokeWidth=2;", "#FEF3C7", "#92400E", "Offline"),
    "failed": ("strokeColor=#D97706;strokeWidth=2;", "#FEF3C7", "#92400E", "Failed"),
}


# A critical asset wears a red stripe down the left edge of its card (a stack member row too), so an
# auditor finds them on the drawing; it sits inside the shape, so it never covers a title, a subtitle or a
# tag. The other levels stay quiet on the cards (the asset register's CRIT column has every device's).
CRITICALITY_LOOK = {"critical": ("#B91C1C", "Critical asset")}


def criticality_marks(el: ET.Element, el_id: str, box: tuple, level: str) -> list[ET.Element]:
    """The stripe a critical asset wears, drawn on the criticality layer (the caller sets the parent of
    its cell) so hiding or stripping that layer takes every mark off the page."""
    look = CRITICALITY_LOOK.get(level.strip().lower())
    if not look or cell_of(el) is None or box is None:
        return []
    x, y, w, h = box
    inset = 5 if h >= 24 else 2
    mark = ET.Element("object", {"id": f"{el_id}-crit", "label": "", "tooltip": f"{look[1]} (NetBox criticality: {level})",
                                 "netdiagrams_ref": el_id, "netdiagrams_field": "cf_criticality"})
    cell = ET.SubElement(mark, "mxCell", {"vertex": "1", "parent": "1",
                                          "style": f"rounded=1;arcSize=50;fillColor={look[0]};strokeColor=none;"
                                                   "connectable=0;movable=0;resizable=0;"})
    ET.SubElement(cell, "mxGeometry", {"x": f"{x + 2:g}", "y": f"{y + inset:g}", "width": "4",
                                       "height": f"{max(h - 2 * inset, 6):g}", "as": "geometry"})
    return [mark]


SCOPE_COLOR = "#7C3AED"


def scope_marks(el: ET.Element, el_id: str, box: tuple, scope: list[str]) -> list[ET.Element]:
    """The purple stripe down the right edge of a card in a compliance scope, on the scope layer (the caller
    sets the parent of its cell)."""
    if not scope or cell_of(el) is None or box is None:
        return []
    x, y, w, h = box
    inset = 5 if h >= 24 else 2
    names = ", ".join(audit_mod.scope_title(s) for s in scope)
    mark = ET.Element("object", {"id": f"{el_id}-scope", "label": "", "tooltip": f"In compliance scope: {names}",
                                 "netdiagrams_ref": el_id, "netdiagrams_field": "cf_compliance_scope"})
    cell = ET.SubElement(mark, "mxCell", {"vertex": "1", "parent": "1",
                                          "style": f"rounded=1;arcSize=50;fillColor={SCOPE_COLOR};strokeColor=none;"
                                                   "connectable=0;movable=0;resizable=0;"})
    ET.SubElement(cell, "mxGeometry", {"x": f"{x + w - 6:g}", "y": f"{y + inset:g}", "width": "4",
                                       "height": f"{max(h - 2 * inset, 6):g}", "as": "geometry"})
    return [mark]


def status_marks(el: ET.Element, el_id: str, status: str, width: float) -> list[ET.Element]:
    """Restyle a device shape for its NetBox status and return the pill to add on its corner."""
    look = STATUS_LOOK.get(status)
    cell = cell_of(el)
    if not look or cell is None or el.get("netdiagrams_status") == status:
        return []
    el.set("netdiagrams_status", status)
    cell.set("style", (cell.get("style") or "") + look[0])
    pill = ET.Element("mxCell", {
        "id": f"{el_id}-status", "vertex": "1", "parent": el_id, "value": look[3],
        "style": f"rounded=1;arcSize=50;html=1;fillColor={look[1]};strokeColor={look[2]};fontColor={look[2]};"
                 "fontSize=9;fontStyle=1;fontFamily=Inter;align=center;verticalAlign=middle;spacing=0;"
                 "connectable=0;movable=0;resizable=0;"})
    ET.SubElement(pill, "mxGeometry", {"x": f"{max(width - 50, 0):g}", "y": "-7", "width": "46", "height": "13",
                                       "as": "geometry"})
    return [pill]


def _fill_interfaces(g: Graph, nb: NetBoxIndex, report: Report) -> None:
    for el in g.els.values():
        if _is_device(el) or not el.get("device") or el.get("name") is None:
            continue
        iface = nb.interfaces.get((el.get("device"), el.get("name")))
        if not iface:
            continue
        updates = {
            "type": _get(iface, "type", "value"),
            "enabled": "true" if iface.get("enabled", True) else "false",
            "lag": _get(iface, "lag", "name"),
            "mode": _get(iface, "mode", "value"),
            "untagged_vlan": str(_get(iface, "untagged_vlan", "vid") or ""),
            "tagged_vlans": ",".join(str(v.get("vid")) for v in iface.get("tagged_vlans") or []),
            "description": iface.get("description") or "",
            "vrf": _label(iface.get("vrf")),
        }
        optic = nb.hw.optics.get((el.get("device"), el.get("name")))
        if optic is not None:   # the transceiver NetBox records in this port, over the drawing's x_optic
            updates["x_optic"] = hardware.part(optic)
            updates["x_optic_serial"] = optic.get("serial") or ""
            label = el.get("label") or ""
            m = re.search(r"(<span[^>]*>)([^<]*)(</span>)\s*$", label)
            short = html.escape(hardware.short_optic(updates["x_optic"]), quote=False)  # NetBox text in an HTML label
            if m and m.group(2).strip() and m.group(2).strip() != short:
                el.set("label", label[:m.start(2)] + short + label[m.end(2):])
        _update(el, {k: v for k, v in updates.items() if k in el.attrib or v}, report, g.name,
                "interface", f"{el.get('device')}:{el.get('name')}")
        report.interfaces += 1
        if nb.url:
            el.set("link", nb.link("dcim/interfaces", iface))
        el.set("tooltip", _tooltip(el))


def _fill_circuits_and_wireless(g: Graph, nb: NetBoxIndex, rename, report: Report) -> None:
    for el in g.els.values():
        if el.get("cid") is not None:
            el.set("cid", rename(el.get("cid")))
            c = nb.circuits.get(el.get("cid"))
            if c:
                _update(el, {"status": _get(c, "status", "value")}, report, g.name, "circuit", el.get("cid"))
                el.set("link", nb.link("circuits/circuits", c))
                el.set("tooltip", _tooltip(el))
        elif el.get("object") == "wireless.wirelesslink":
            # The radio pair names the link (bridges often share an SSID, a backhaul may have none); SSID is the fallback.
            drawn = {rename(el.get(k) or "") for k in ("interface_a", "interface_b")}
            w = nb.wx.link_for(drawn, rename(el.get("ssid") or ""))
            cell = cell_of(el)
            if w is None:
                if cell is not None and cell.get("edge") == "1" and MISSING_LINK_STYLE not in (cell.get("style") or ""):
                    cell.set("style", (cell.get("style") or "") + MISSING_LINK_STYLE)
                el.set("tooltip", "Not in NetBox: no wireless link between these radios\n" + _tooltip(el))
                continue
            report.matched_wireless.add(id(w))
            (da, ia), (db, ib) = nb.wx.link_ends[id(w)]
            _update(el, {"ssid": w.get("ssid") or "", "status": _get(w, "status", "value"),
                         "auth_type": _get(w, "auth_type", "value"), "auth_cipher": _get(w, "auth_cipher", "value"),
                         "distance": _number(w.get("distance")), "distance_unit": _get(w, "distance_unit", "value"),
                         "interface_a": f"{da}:{ia}", "interface_b": f"{db}:{ib}"},
                    report, g.name, "wireless link", w.get("ssid") or f"{da} ⇄ {db}")
            if cell is not None and MISSING_LINK_STYLE in (cell.get("style") or ""):
                cell.set("style", cell.get("style").replace(MISSING_LINK_STYLE, ""))
            el.set("link", nb.link("wireless/wireless-links", w))
            el.set("tooltip", _tooltip(el))


def _remove_devices(g: Graph, names: set[str], report: Report | None = None) -> None:
    doomed = [i for i, el in g.els.items() if _is_device(el) and el.get("name") in names]
    doomed += [i for i, el in g.els.items() if el.get("netdiagrams_ref") in doomed]
    if doomed:
        boxes = [g.box(i) for i in doomed if cell_of(g.els[i]) is not None and cell_of(g.els[i]).get("vertex") == "1"]
        edges = [i for i, el in g.els.items() if cell_of(el) is not None and cell_of(el).get("edge") == "1"]
        before = truth.edge_endpoints(g, edges)
        g.remove(doomed)
        after = truth.edge_endpoints(g, [i for i in edges if i in g.els])
        swept = truth.sweep_residue(g, boxes, _is_device, ends_before=before, ends_after=after)
        if swept and report is not None:
            report.residue.append((g.name, len(swept)))


def _fill_cables(g: Graph, nb: NetBoxIndex, rename, report: Report) -> None:
    for el in list(g.els.values()):
        if el.get("cable_label") is None:
            continue
        labels = [rename(l.strip()) for l in el.get("cable_label").split(",") if l.strip()]
        el.set("cable_label", ", ".join(labels))
        keys = [k for k in (_cable_key(el, l, nb) for l in labels) if k]
        found = [nb.cables[k] for k in keys]
        report.matched_cables.update(keys)
        if found:
            _update(el, _cable_attrs(found, nb.names), report, g.name, "cable", ", ".join(labels))
            if el.get("label"):
                _update(el, {"label": _line_label(el.get("label"), found, nb)}, report, g.name, "cable",
                        ", ".join(labels))
            if nb.url:
                el.set("link", nb.link("dcim/cables", **({"id": [c["id"] for c in found]}
                                                           if all(c.get("id") for c in found) else {"label": labels})))
            el.set("tooltip", _tooltip(el))
        elif cell_of(el) is not None and cell_of(el).get("edge") == "1":
            # No NetBox cable for this line, or no cables in NetBox at all: the template's
            # cabling is drawn as unverified, never as this site's.
            report.missing_cables.update(labels)
            cell = cell_of(el)
            if MISSING_LINK_STYLE not in (cell.get("style") or ""):
                cell.set("style", (cell.get("style") or "") + MISSING_LINK_STYLE)
            el.set("tooltip", "Not in NetBox: " + ", ".join(labels) + "\n" + _tooltip(el))


SPEED_SEG = re.compile(r"^(\d+×)?\d+(\.\d+)?[GM]$")
VLAN_SEG = re.compile(r"^(access \d+|all|same VLANs|\d+(\s*[,–-]\s*\d+)*)$")
MEDIA_SEG = re.compile(r"^(Cat\d|SMF|MMF|DAC|AOC|Stack cable|Power)", re.I)


def _line_label(label: str, found: list[dict], nb: NetBoxIndex) -> str:
    """A link pill restated from NetBox: 'Po1 · 2×10G · 181,189 · MMF OM4' keeps its name, and the
    speed, VLAN list and media it already shows follow the cable and its interfaces.

    A VLAN list stays only when NetBox has it: a trunk NetBox records no VLANs for, or a
    routed link, loses the template's numbers rather than showing a list nobody verified.
    """
    if "<" in label or "%" in label:
        return label
    segs = [s.strip() for s in label.split("·")]
    kinds = ["speed" if SPEED_SEG.match(s) else "media" if MEDIA_SEG.match(s) else "vlans" if VLAN_SEG.match(s)
             else "name" for s in segs]
    if set(kinds) <= {"name"}:
        return label
    ends = [(_ends(c.get("a_terminations"), nb.names), _ends(c.get("b_terminations"), nb.names)) for c in found]
    ia = next((nb.interfaces[a[0]] for a, _ in ends if a and a[0] in nb.interfaces), {})
    ib = next((nb.interfaces[b[0]] for _, b in ends if b and b[0] in nb.interfaces), {})
    new = {}
    if "speed" in kinds:
        one = _speed(ia) or _speed(ib)
        bundled = len(found) > 1 and bool(_get(ia, "lag", "name") or _get(ib, "lag", "name"))
        if one:  # two ring uplinks drawn as one line are 1G each, not a 2×1G bundle
            new["speed"] = f"{len(found)}×{one}" if bundled else one
    if "vlans" in kinds and (ia or ib):
        vlans = _trunk_vlans(_lag_interface(nb, ends, ia, ib), ia, ib, sep=",")
        new["vlans"] = "" if vlans in ("—", MISSING_TRUNK) else vlans
    if "media" in kinds:
        types = dict.fromkeys(MEDIA.get(c.get("type") or "", c.get("type") or "") for c in found)
        if any(types):
            new["media"] = " · ".join(t for t in types if t)
    return " · ".join(p for p in (new.get(kind, seg) for kind, seg in zip(kinds, segs)) if p)


def _lag_interface(nb: NetBoxIndex, ends: list, ia: dict, ib: dict) -> dict:
    """The port-channel a link's members belong to, whichever end NetBox records it on."""
    for side, iface in ((0, ia), (1, ib)):
        lag = _get(iface, "lag", "name")
        dev = next((e[side][0][0] for e in ends if e[side]), "")
        if lag and (dev, lag) in nb.interfaces:
            return nb.interfaces[(dev, lag)]
    return ia


def _cable_key(el: ET.Element, label: str, nb: NetBoxIndex) -> str:
    """The NetBox cable a drawn line names. A label on several cables is told apart by the line's ends."""
    if label in nb.cables and label not in nb.duplicates:
        return label
    ends = {e.strip().partition(":")[0] for key in ("a_terminations", "b_terminations")
            for e in (el.get(key) or "").split(",") if e.strip()}
    for key in nb.duplicates.get(label, []):
        c = nb.cables[key]
        devices = {d for d, _ in _ends(c.get("a_terminations"), nb.names) + _ends(c.get("b_terminations"), nb.names)}
        if devices and devices <= ends:
            return key
    return ""


# ----------------------------------------------------------------------- tags
TAG_LAYERS = (("mgmt ip", "primary_ip4"), ("serial", "serial"), ("circuit", "cid"))
INLINE_SERIAL = re.compile(r"(?:(?:\s|&nbsp;)*·)?\s*SN %serial%")
SERIAL_TAG_STYLE = ("text;html=1;fontSize=9;fontColor=#64748B;align=right;verticalAlign=middle;spacing=0;"
                    "spacingLeft=2;fontFamily=JetBrains Mono;")


def _lift_inline_serials(g: Graph) -> None:
    """A serial written into a shape's own label (a stack member row's 'U42 · SN FOC…') becomes a tag on
    the serial layer, so hiding layer 3b before sharing hides every serial on the page."""
    layer = next((lid for lid, name in g.layers.items() if "serial" in name.lower()), None)
    if layer is None:
        return
    new = []
    for i, el in list(g.els.items()):
        label = el.get("label") or ""
        if "SN %serial%" not in label or el.get("placeholders") != "1" or not _is_device(el) or g.hidden(i):
            continue
        el.set("label", INLINE_SERIAL.sub("", label, count=1))
        x, y, w, h = g.box(i)
        width = 98
        tag = ET.Element("object", {"id": f"{i}-tag-serial", "label": f"SN {html.escape(el.get('serial'), quote=False)}"
                                    if el.get("serial")
                                    else "", "netdiagrams_ref": i, "netdiagrams_field": "serial",
                                    "netdiagrams_format": "SN {}"})
        cell = ET.SubElement(tag, "mxCell", {"vertex": "1", "parent": layer, "style": SERIAL_TAG_STYLE})
        ET.SubElement(cell, "mxGeometry", {"x": f"{x + w - width - 6:g}", "y": f"{y + (h - 14) / 2:g}",
                                           "width": f"{width}", "height": "14", "as": "geometry"})
        new.append(tag)
    if new:
        g.root.extend(new)
        g.reindex()


def _bind_tags(g: Graph) -> None:
    """Link each free-floating IP / serial / circuit tag to the shape it describes.

    The tag keeps its wording: '10.1.99.2 (SVL)' becomes format '{} (SVL)' on
    the device whose IP it shows, so later fills rewrite only the value.
    """
    shapes = {"primary_ip4": [], "serial": [], "cid": []}
    for i, el in g.els.items():
        if _is_device(el):
            shapes["primary_ip4"].append(i)
            shapes["serial"].append(i)
        elif el.get("cid") is not None:
            shapes["cid"].append(i)
    for i in list(g.els):
        el = g.els[i]
        if el.get("netdiagrams_ref") or _is_device(el) or el.get("cid") is not None:
            continue
        layer = g.layer_of(i).lower()
        fld = next((f for key, f in TAG_LAYERS if key in layer), None)
        cell = cell_of(el)
        if not fld or cell is None or cell.get("vertex") != "1":
            continue
        raw = g.value(el)
        best = None
        for cand in shapes[fld]:
            current = g.els[cand].get(fld, "")
            if fld == "primary_ip4":
                current = current.split("/")[0]
            if not current or current not in raw:
                continue
            dist = _distance(g, i, cand) if fld != "cid" else _edge_distance(g, i, cand)
            if best is None or dist < best[0]:
                best = (dist, cand, current)
        if fld == "cid" and best is None and shapes["cid"]:
            # Circuit tags start as '‹circuit id›': take the nearest circuit line.
            d, cand = min((_edge_distance(g, i, c), c) for c in shapes["cid"])
            if d < 200:
                fmt = re.sub(r"‹[^›]*›", "{}", raw) if "‹" in raw else raw + " {}"
                g.wrap(i, netdiagrams_ref=cand, netdiagrams_field=fld, netdiagrams_format=fmt)
            continue
        if best:
            g.wrap(i, netdiagrams_ref=best[1], netdiagrams_field=fld, netdiagrams_format=raw.replace(best[2], "{}", 1))
    g.reindex()


def _centre(g: Graph, el_id: str) -> tuple[float, float]:
    x, y, w, h = g.box(el_id)
    return x + w / 2, y + h / 2


def _distance(g, a, b) -> float:
    (ax, ay), (bx, by) = _centre(g, a), _centre(g, b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _edge_distance(g, tag, edge) -> float:
    cell = cell_of(g.els[edge])
    ends = [e for e in (cell.get("source"), cell.get("target")) if e in g.els]
    return min((_distance(g, tag, e) for e in ends), default=1e9)


def _refresh_tags(g: Graph, nb: NetBoxIndex, report: Report) -> None:
    for el in g.els.values():
        ref, fld, fmt = el.get("netdiagrams_ref"), el.get("netdiagrams_field"), el.get("netdiagrams_format")
        if not ref or ref not in g.els or not fmt:
            continue
        target = g.els[ref]
        value = target.get(fld, "")
        if fld == "primary_ip4":
            value = value.split("/")[0] if value else (
                f"OOB {target.get('oob_ip', '').split('/')[0]}" if target.get("oob_ip") else "")
        if fld == "cid" and target.get("cid") not in nb.circuits:
            continue
        if not value:
            if target.get("name") in nb.devices and fld in ("primary_ip4", "serial"):
                g.set_value(el, gaps.mark_missing(fmt, fld))
            continue
        text = fmt.replace("{}", html.escape(value, quote=False))
        report.tags += 1
        if g.value(el) != text:
            g.set_value(el, text)
        link = target.get("link")
        if link:
            el.set("link", link)
            el.set("linkTarget", "_blank")


# --------------------------------------------------------------------- tables
def _inside_card(g: Graph, table: str) -> float | None:
    """The width that keeps a table 14 px inside the right edge of the card behind it, when it pokes out."""
    tx, ty, tw, th = g.box(table)
    cards = [g.box(i) for i, el in g.els.items() if i != table and cell_of(el) is not None
             and cell_of(el).get("vertex") == "1" and cell_of(el).get("parent") in g.layers
             and "rounded=1" in (cell_of(el).get("style") or "") and g.box(i)[0] < tx and g.box(i)[1] < ty
             and g.box(i)[1] + g.box(i)[3] > ty + 20 and abs(g.box(i)[0] + g.box(i)[2] - (tx + tw)) < 40
             and g.box(i)[2] < 1.5 * tw]
    if not cards:
        return None
    right = min(x + w for x, _, w, _ in cards) - 14
    return right - tx if right < tx + tw - 0.5 else None


def _fill_tables(g: Graph, nb: NetBoxIndex, report: Report, before: dict[str, list]) -> None:
    today = report.intake.data_date or report.provenance.built
    for table in g.tables():
        header = g.header(table)
        if "HOSTNAME" in header or ("NAME" in header and "SERIAL" in header):
            old_header = header
            if nb.devices and "HOSTNAME" in header and "SW" in header:  # the physical register, not the AP one
                has_eos = any(_device_attrs(d, "").get("cf_end_of_support") for d in nb.devices.values())
                has_crit = any(_device_attrs(d, "").get("cf_criticality") for d in nb.devices.values())
                for title, width, after, donors in ASSET_EXTRA_COLUMNS:
                    if (title == "EOS" and not has_eos) or (title == "CRIT" and not has_crit):
                        continue  # the column appears once NetBox has the field to show
                    g.add_column(table, title, width, after, donors)
                header = g.header(table)
            rows = _asset_rows(g, table, header, nb, before.get(table, []), today, old_header)
            g.balance_columns(table, rows, _inside_card(g, table))   # added columns take room where text has some
            title = "Asset register"
        elif header[:1] == ["LINK"] and any("A-SIDE" in h for h in header):
            if nb.cables:
                for title, width, after, donors in LINK_EXTRA_COLUMNS:
                    g.add_column(table, title, width, after, donors)
                header = g.header(table)
            rows = _link_rows(g, header, nb, [name for name, _ in before.get(table, [])])
            g.balance_columns(table, rows, _inside_card(g, table))
            title = "Link register"
            if not rows and not nb.cables:
                # The template's example links would read as this site's: say NetBox has none yet.
                rows = [[("?", "") if i == 0 else ("No cables in NetBox yet", "") if i == 1 else ("", "")
                         for i in range(len(header))]]
        elif header[:1] == ["LINK"] and any(h.startswith("RADIO A") for h in header):
            rows = wireless_page.ptp_rows(g, table, header, nb)
            title = "Point-to-point register"
        elif header[:1] == ["AREA"] and any(h.startswith("POLICY TAG") for h in header):
            rows = wireless_page.tag_rows(g, table, header, nb)
            title = "Tag table"
            if not rows and nb.wx.aps:
                wireless_page.hide_tag_table(g, table)   # no AP carries a tag model: reference only
                continue
        elif header[:2] == ["ID", "FLOW"] and g.diagram.get("id") == "wireless":
            rows = wireless_page.flow_rows(g, table, header, nb, [r for _, r in before.get(table, [])])
            title = "Wireless flows"
        elif header[:1] == ["CABLE ID"] and any(h.startswith("A OPTIC") for h in header):
            rows = _optics_rows(header, nb, before.get(table, []), g.els[table].get("netdiagrams_rows") or "")
            title = "Cable & optics register"
            if not rows and nb.devices:
                rows = [[("?", "") if i == 0 else ("No cables in NetBox yet", "") if i == 1 else ("", "")
                         for i in range(len(header))]]
        elif header[:2] == ["DEVICE", "CHASSIS"] and "MODULES" in header:
            rows = _module_rows(g, table, header, nb)
            title = "Modules & power register"
        elif header[:2] == ["VLAN", "NAME"] and any("SUBNET" in h for h in header):
            rows = _vlan_rows(g, table, header, nb)
            title = "VLAN table " + (_zone_of_table(g, table) or "")
            if not rows and nb.vlans and _zone_of_table(g, table):
                # The template's example VLANs would read as this site's: say NetBox has none yet.
                rows = [[("?", "") if i == 0 else ("Not in NetBox yet" if i == 1 else "", "")
                         for i in range(len(header))]]
        else:
            continue
        if rows:
            g.fill_table(table, rows)
            report.tables.append((g.name, title.strip(), len(rows)))


def _table_text(g: Graph, table: str) -> list[list[str]]:
    """A table's data rows as drawn, one list of cell texts per row."""
    return [[plain(g.value(g.els[c])) for c in g.row_cells(row)] for row in g.rows(table)[1:]]


def _drawn_devices(g: Graph) -> list[str]:
    """Devices drawn on the page, with the members of a counted group after its shape."""
    seen = []
    for el in g.els.values():
        if _is_device(el):
            for name in [el.get("name")] + [m for m in (el.get("netdiagrams_group") or "").split(",") if m]:
                if name not in seen:
                    seen.append(name)
    return seen


def _uplinks(nb: NetBoxIndex) -> dict[str, tuple[str, str, str]]:
    """Device -> (peer device, peer port, cable label) for its first cabled port."""
    out = {}
    for label, c in sorted(nb.cables.items()):
        a = _ends(c.get("a_terminations"), nb.names)
        b = _ends(c.get("b_terminations"), nb.names)
        if a and b:
            out.setdefault(a[0][0], (b[0][0], b[0][1], label))
            out.setdefault(b[0][0], (a[0][0], a[0][1], label))
    return out


def _asset_rows(g, table, header, nb: NetBoxIndex, before_rows: list, today: str = "", old_header=None):
    """One row per device drawn on this page, for the roles the register lists.

    The template decides the scope: the physical register lists the network
    gear but not the PLCs and HMIs, the wireless register only the radios.
    ``before`` is the register as drawn in the template, under template names.
    """
    if not nb.devices:
        return []
    before = [name for name, _ in before_rows]
    uplinks = _uplinks(nb)
    drawn = [n for n in _drawn_devices(g) + list(getattr(g, "scheduled", ())) if n in nb.devices]
    roles = {_get(nb.devices.get(n) or nb.register_only[n], "role", "slug") for n in before
             if n in nb.devices or n in nb.register_only}
    if roles:
        drawn = [n for n in drawn if _get(nb.devices[n], "role", "slug") in roles]
        if g.diagram.get("id") == "wireless":
            # The wireless register is the AP inventory: a mesh AP or WGB waiting in the tray is listed too.
            drawn += [n for n in nb.devices if n not in drawn and _get(nb.devices[n], "role", "slug") in roles]
    order = [n for n in before if n in drawn] + sorted((n for n in drawn if n not in before), key=_natural)
    rows = []
    for name in order:
        d = nb.devices[name]
        attrs = _device_attrs(d, nb.url)
        row = []
        peer = uplinks.get(name)
        for col in header:
            fill = ASSET_COLUMNS.get(col)
            text = fill(d, attrs) if fill else ""
            link = nb.link("dcim/devices", d) if col in ("HOSTNAME", "NAME") else ""
            if col == "STATUS":
                row.append(_status_pill(attrs.get("status")))
                continue
            if col == "ROLE" and attrs.get("description"):
                row.append((text, "", False, attrs["description"]))
                continue
            if col == "CRIT" and text.lower() == "critical":
                row.append((f'<font color="#B91C1C"><b>{html.escape(text)}</b></font>', "", True))
                continue
            if col == "EOS" and text and today and text < today:
                row.append((f'<font color="#B91C1C"><b>{html.escape(text)}</b></font>', "", True, "Past end of support"))
                continue
            # Mode, power, controller and a radio uplink come from NetBox's wireless records, never the template.
            own = wireless_page.ap_columns(nb, d, col)
            if own is not None and (not peer or not (col.startswith("SWITCH") or col == "CABLE")):
                row.append(own)
                continue
            if peer and col.startswith("SWITCH"):
                text = f"{_short_dev(peer[0])} {short_if(peer[1])}"
                link = nb.link("dcim/devices", nb.devices[peer[0]]) if peer[0] in nb.devices else ""
            elif peer and col == "CABLE":
                text = _short_dev(nb.cables[peer[2]].get("label") or peer[2])
                cable = nb.cables[peer[2]]
                link = nb.link("dcim/cables", cable) if cable.get("id") else nb.link("dcim/cables", label=peer[2])
            row.append((text, link))
        rows.append(row)
    # Spares and devices being taken out are listed, not drawn: the register says which.
    for name, d in sorted(nb.register_only.items(), key=lambda kv: _natural(kv[0])):
        if roles and _get(d, "role", "slug") not in roles:
            continue
        attrs = _device_attrs(d, nb.url)
        state = intake.status(d)
        row = []
        for col in header:
            fill = ASSET_COLUMNS.get(col)
            text = fill(d, attrs) if fill else ""
            if col == "STATUS":
                row.append(_status_pill(state))
                continue
            if col == "ROLE" and "STATUS" not in header:
                text = f"{text} · {state}" if text else state
            row.append((text, nb.link("dcim/devices", d) if col in ("HOSTNAME", "NAME") else ""))
        rows.append(row)
    return rows


def _short_dev(name: str) -> str:
    prefix = site_prefix([name, name])
    return name[len(prefix):] if prefix else name


# The link register lists the network's own links, not every endpoint drop.
ENDPOINT_ROLES = {"access-point", "plc", "hmi", "io", "sis-controller", "workgroup-bridge", "sensor",
                  "camera", "printer", "phone", "workstation", "engineering-workstation", "drive",
                  "server", "ews", "safety-plc"}


def endpoint_roles() -> set[str]:
    """The end-device roles of the profile in force, on top of the common ones."""
    return profiles.endpoint_roles(ENDPOINT_ROLES)


# Which end of a link is the A side: the more central device.
ROLE_RANK = ["core-switch", "distribution-switch", "idmz-switch", "access-switch", "industrial-switch",
             "sis-switch", "oob-switch", "wireless-controller", "firewall", "sdwan-edge", "router"]


def _infrastructure(nb: NetBoxIndex, device: str) -> bool:
    d = nb.devices.get(device)
    return bool(d) and _get(d, "role", "slug") not in endpoint_roles()   # the profile's end devices too


def _group(nb: NetBoxIndex, device: str) -> str:
    """A virtual chassis or stack reads as one device in the register."""
    return _get(nb.devices.get(device) or {}, "virtual_chassis", "name") or device


def _rank(nb: NetBoxIndex, device: str) -> int:
    role = _get(nb.devices.get(device) or {}, "role", "slug")
    return ROLE_RANK.index(role) if role in ROLE_RANK else len(ROLE_RANK)


def _drawn_link_names(g: Graph) -> dict[str, str]:
    """Cable label -> the link name written on its line, e.g. 'Po1' from 'Po1 · 2×10G'."""
    names = {}
    for el in g.els.values():
        labels = el.get("cable_label")
        text = plain(g.value(el)).split(" · ")[0].strip()
        if not labels or not text or text[0].isdigit() or text.startswith("access "):
            continue
        for label in (part.strip() for part in labels.split(",")):  # as _fill_cables: a label may hold spaces
            if label:
                names.setdefault(label, text.removesuffix(" feed"))
    return names


def _link_kind(aport: str, bport: str) -> str:
    """A name for well-known peer links that NetBox doesn't name."""
    ports = (aport.lower(), bport.lower())
    if all(p.startswith("stackport") for p in ports):
        return "STK"
    if all(p.startswith("redundancy") for p in ports):
        return "RP"
    if all(p.startswith("ha") for p in ports):
        return "HA"
    return ""


def _link_rows(g: Graph, header, nb: NetBoxIndex, before: list[str]):
    """One row per logical link between network devices.

    Member cables of a port-channel, or several cables between the same pair
    of devices (stack, HA, SVL), share a row; a virtual chassis reads as one
    device. Endpoint drops and links inside a cell ring are left out, as in
    the template.
    """
    if not nb.cables:
        return []
    drawn_names = _drawn_link_names(g)
    groups: dict[tuple, list] = defaultdict(list)
    for c in nb.cables.values():
        a = _ends(c.get("a_terminations"), nb.names)
        b = _ends(c.get("b_terminations"), nb.names)
        if not a or not b or not (_infrastructure(nb, a[0][0]) and _infrastructure(nb, b[0][0])):
            continue
        ra, rb = nb.devices[a[0][0]], nb.devices[b[0][0]]
        if _get(ra, "role", "slug") == _get(rb, "role", "slug") == "industrial-switch" and \
                _device_zones(ra, nb) == _device_zones(rb, nb):
            continue
        if (_rank(nb, b[0][0]), _group(nb, b[0][0])) < (_rank(nb, a[0][0]), _group(nb, a[0][0])):
            a, b = b, a
        ia, ib = nb.interfaces.get(a[0], {}), nb.interfaces.get(b[0], {})
        ga, gb = _group(nb, a[0][0]), _group(nb, b[0][0])
        if ga == gb:  # between members of one chassis: keep the members apart
            ga, gb = a[0][0], b[0][0]
        bundle = _get(ia, "lag", "name") or _get(ib, "lag", "name") or c.get("type") or ""
        groups[(ga, gb, bundle)].append((c, a[0], b[0], ia, ib, a, b))

    # Plain links drawn as one line (a REP ring's two uplinks) share a row.
    merged: dict[tuple, list] = {}
    for (ga, gb, bundle), members in groups.items():
        ia, ib = members[0][3], members[0][4]
        drawn = next((drawn_names[m[0]["label"]] for m in members if m[0].get("label") in drawn_names), "")
        lag = _get(ia, "lag", "name") or _get(ib, "lag", "name")
        key = (ga, "drawn", drawn) if drawn and not lag else (ga, gb, bundle)
        merged.setdefault(key, []).extend(members)

    rows = []
    for members in merged.values():
        c0, (adev, aport), (bdev, bport), ia, ib, _, _ = members[0]
        ga = _group(nb, adev) if len({_group(nb, m[1][0]) for m in members}) == 1 else adev
        gb = _group(nb, bdev) if len({_group(nb, m[2][0]) for m in members}) == 1 else ""
        if ga == gb:
            ga, gb = adev, bdev
        lag = _get(ia, "lag", "name") or _get(ib, "lag", "name")
        drawn = [drawn_names[m[0]["label"]] for m in members if m[0].get("label") in drawn_names]
        if _get(ia, "lag", "name"):
            name = short_if(_get(ia, "lag", "name"))
        elif drawn:
            name = "/".join(dict.fromkeys(drawn))
        elif lag:
            name = short_if(lag)
        else:
            label = c0.get("label") or ""
            name = c0.get("description") or _link_kind(aport, bport) or \
                (f"cable {label}" if label.isdigit() else _short_dev(label))
        lag_if = nb.interfaces.get((adev, _get(ia, "lag", "name"))) \
            or nb.interfaces.get((bdev, _get(ib, "lag", "name"))) or ia
        speed = _speed(ia) or _speed(ib)
        types = list(dict.fromkeys(MEDIA.get(m[0].get("type") or "", m[0].get("type") or "") for m in members))
        values = {
            "LINK": name,
            "A-SIDE": f"{_short_dev(ga)} " + " · ".join(_ports(m[5]) for m in members),
            "B-SIDE": (f"{_short_dev(gb)} " + " · ".join(_ports(m[6]) for m in members)) if gb else
                      " · ".join(f"{_short_dev(m[2][0])} {_ports(m[6])}" for m in members),
            "SPEED": (f"{len(members)}×{speed}" if len(members) > 1 and speed else speed) + (" LACP" if lag else ""),
            "MEDIA": " · ".join(t for t in types if t),
            "TRUNKED VLANS": _trunk_vlans(lag_if, ia, ib),
            "CABLE ID": _cable_ids([m[0] for m in members]),
            "STATUS": _status_pill(_get(c0, "status", "value") or "connected"),
        }
        ids = [m[0].get("id") for m in members]
        link = nb.link("dcim/cables", id=ids) if all(ids) else \
            nb.link("dcim/cables", label=[m[0].get("label") for m in members])
        row = []
        for col in header:
            key = next((k for k in values if col.startswith(k)), None)
            value = values.get(key, "")
            if isinstance(value, tuple):
                row.append(value)
            elif key == "TRUNKED VLANS" and value == MISSING_TRUNK:
                row.append((value, "", True, "Trunk with no tagged VLANs in NetBox"))
            else:
                row.append((value, link if key in ("LINK", "CABLE ID") else ""))
        rows.append((name, ga, gb, row))
    # The template's order first, then new links grouped by their A side.
    pos = {n: i for i, n in enumerate(before)}
    rows.sort(key=lambda r: (pos.get(r[0], len(pos)), _rank(nb, r[1]), r[1], r[2], r[0]))
    return [r[3] for r in rows]


FIBRE_MEDIA = re.compile(r"\b(SMF|MMF|OS\d|OM\d|fib(re|er))", re.I)


def _optics_rows(header, nb: NetBoxIndex, before_rows: list, scope: str = ""):
    """One row per NetBox cable: its ends, the transceiver in each end's port, media, speed, length, patch.

    The optic comes from the inventory item NetBox binds to the interface (role transceiver);
    a fiber end with none shows ? so the gap is on the sheet, not hidden by a template value.

    Which cables: all of them, or the fiber ones only when the table carries
    ``netdiagrams_rows="fiber"`` or every row the template itself drew is fiber (a register
    of fiber uplinks stays one). ``netdiagrams_rows="all"`` forces the full list.
    PATCH columns come from the panel ports NetBox traces (front/rear-port paths, intake's
    x_patch_a/b); a cable with no path keeps the text the template or the previous build had
    for it, matched by cable label, the way LINK does.
    """
    if not nb.cables:
        return []
    # The template labels cables without the site code (CBL-018 for S01-CBL-018): match either form.
    bare = lambda label: re.sub(r"^[A-Za-z]{1,4}\d{1,3}-", "", label or "")
    old_links = {name: row for name, row in before_rows}
    old_links.update({bare(name): row for name, row in before_rows if bare(name) not in old_links})
    link_col = next((i for i, h in enumerate(header) if h == "LINK"), None)
    media_col = next((i for i, h in enumerate(header) if h.startswith("MEDIA")), None)
    patch_cols = [i for i, h in enumerate(header) if h.startswith("PATCH")]
    scope = scope.strip().lower()
    if not scope and media_col is not None:
        drawn = [row[media_col] for _, row in before_rows if len(row) > media_col and row[media_col].strip() not in ("", "—")]
        if drawn and all(FIBRE_MEDIA.search(m) for m in drawn):
            scope = "fiber"
    rows = []
    for key, c in sorted(nb.cables.items(), key=lambda kv: _natural(kv[0])):
        a = _ends(c.get("a_terminations"), nb.names)
        b = _ends(c.get("b_terminations"), nb.names)
        if not a or not b:
            continue
        if scope in ("fibre", "fiber") and not str(c.get("type") or "").startswith(hardware.FIBRE):
            continue
        ia, ib = nb.interfaces.get(a[0], {}), nb.interfaces.get(b[0], {})
        lag = _get(ia, "lag", "name") or _get(ib, "lag", "name")
        old = old_links.get(c.get("label") or key) or old_links.get(bare(c.get("label") or key))
        link = short_if(lag) if lag else (old[link_col] if old and link_col is not None and len(old) > link_col
                                            else "") or c.get("description") or _link_kind(a[0][1], b[0][1]) or "—"
        fiber = str(c.get("type") or "").startswith(hardware.FIBRE)
        link_url = nb.link("dcim/cables", c) if c.get("id") is not None else ""

        def optic(end):
            item = nb.hw.optics.get(end)
            if item is not None:
                tip = f"Inventory item {item.get('name') or ''} · SN {item.get('serial') or '?'}".strip()
                return (hardware.part(item), nb.link("dcim/inventory-items", item) if item.get("id") else "", False, tip)
            if fiber:
                return (gaps.MISSING, "", True, "No transceiver recorded on this interface (inventory item, role transceiver)")
            return ("—", "")

        length = f"{_number(c.get('length'))} {_get(c, 'length_unit', 'value')}".strip() if c.get("length") else "—"
        speed = _speed(ia) or _speed(ib) or "—"
        patch = [c.get("x_patch_a") or "", c.get("x_patch_b") or ""]   # the panel ports NetBox traced
        if len(patch_cols) == 1:
            patch = [" · ".join(p for p in patch if p)]
        patch_text = {}
        for n, col in enumerate(patch_cols):
            text = patch[n] if n < len(patch) else ""
            if not text and old and len(old) > col and not PLACEHOLDER.search(old[col]):
                text = old[col].strip()   # no path in NetBox: what the template or the last build said
            patch_text[col] = text or "—"
        values = {
            "CABLE ID": (c.get("label") or f"#{c.get('id')}", link_url),
            "LINK": (link, link_url),
            "A END": (f"{_short_dev(a[0][0])} {_ports(a)}", nb.link("dcim/interfaces", ia) if ia.get("id") else ""),
            "A OPTIC": optic(a[0]),
            "B END": (f"{_short_dev(b[0][0])} {_ports(b)}", nb.link("dcim/interfaces", ib) if ib.get("id") else ""),
            "B OPTIC": optic(b[0]),
            "MEDIA": (MEDIA.get(c.get("type") or "", c.get("type") or "") or "—", ""),
            "SPEED": (speed, ""),
            "LENGTH": (length, ""),
        }
        rows.append([(patch_text[n], "") if n in patch_text else
                     values.get(next((k for k in values if col.startswith(k)), ""), ("", ""))
                     for n, col in enumerate(header)])
    return rows


def _module_rows(g: Graph, table: str, header, nb: NetBoxIndex):
    """One row per chassis: a stack as one, and identical boxes (same role, model and fittings) as one.

    All of it is NetBox's: modules in their bays, inventory items by role (or part number when
    the item has no role). An empty bay is amber so a missing blank or an unrecorded module
    shows, and the network devices NetBox records nothing for close the register in one amber row.
    """
    if not nb.devices:
        return []
    if not nb.hw.recorded:
        return [[("?", "") if i == 0 else ("No modules or inventory items in NetBox yet", "") if i == 1 else ("", "")
                 for i in range(len(header))]]
    hw = nb.hw
    groups: dict[tuple, list[str]] = {}
    unrecorded = []
    for name in sorted(nb.devices, key=_natural):
        if not _infrastructure(nb, name):
            continue
        d = nb.devices[name]
        if not (hw.modules.get(name) or hw.bays.get(name) or hw.items.get(name)):
            if not _get(d, "virtual_chassis", "name"):
                unrecorded.append(name)
                continue
        vc = _get(d, "virtual_chassis", "name")
        if vc:
            key = ("vc", vc)
        else:
            parts = tuple(sorted(hardware.part(i) for i in hw.items.get(name, []) if hardware.kind_of(i) != "optic")) + \
                tuple(hw.fitted([name])) + tuple(sorted(hw.empty_bays([name])))   # optics differ per box; the rest is the chassis
            key = ("same", _get(d, "role", "slug"), _label(d.get("device_type")), parts)
        groups.setdefault(key, []).append(name)
    rows = []
    for key, members in sorted(groups.items(), key=lambda kv: (_rank(nb, kv[1][0]), _natural(kv[1][0]))):
        d = nb.devices[members[0]]
        each = members if key[0] == "vc" else members[:1]   # fittings per chassis: a stack sums its members
        models = " · ".join(dict.fromkeys(_label(nb.devices[m].get("device_type")) for m in members))
        fitted = hw.fitted(each)
        counts = Counter(fitted)
        modules = [f"{counts[(bay, model)]}× {bay} {model}" if counts[(bay, model)] > 1 else f"{bay} {model}"
                   for bay, model in dict.fromkeys(fitted)]
        empty = Counter(hw.empty_bays(each))
        empty_text = " · ".join(f'<font color="#B45309">{n}× {html.escape(bay)} empty</font>' if n > 1
                                else f'<font color="#B45309">{html.escape(bay)} empty</font>' for bay, n in empty.items())
        modules_html = " · ".join([html.escape(m) for m in modules] + ([empty_text] if empty_text else [])) or "—"
        tip = "A bay with no module: fit one or record what covers it" if empty else ""
        link = nb.link("dcim/virtual-chassis", d.get("virtual_chassis")) if key[0] == "vc" else \
            nb.link("dcim/devices", d)
        label = key[1] if key[0] == "vc" else _joined_names(members)
        if key[0] == "same" and len(members) > 1:
            tip = (tip + " · " if tip else "") + f"Each of {', '.join(members)}"
        def per_member(fn):
            """'2× PWR-C1-1100WAC-P per member' when every member of a stack carries the same, else the sum."""
            texts = [fn([m]) for m in each]
            if len(each) > 1 and len(set(texts)) == 1 and texts[0]:
                return texts[0] + " per member"
            return fn(each)

        values = {
            "DEVICE": (label, link, False, tip) if key[0] == "same" and len(members) > 1 else (label, link),
            "CHASSIS": (models or "—", ""),
            "POWER": (per_member(hw.power) or "—", ""),
            "MODULES": (modules_html, "", True, tip),
            "OTHER": (" · ".join(x for x in (per_member(hw.fans), per_member(hw.other)) if x) or "—", ""),
        }
        rows.append([values.get(next((k for k in values if col.startswith(k)), ""), ("", "")) for col in header])
    if unrecorded:
        # As many names as fit the CHASSIS cell in two lines; the tooltip carries the whole list.
        col = header.index("CHASSIS")
        first = g.rows(table)[1:2]
        cell = g.row_cells(first[0])[col] if first else None
        width = float(g.geometry(cell).get("width", 150)) if cell is not None and g.geometry(cell) is not None else 150
        size = font_size(cell_of(g.els[cell]).get("style") or "") if cell is not None else 9
        shown = list(unrecorded)
        while True:
            more = f" … +{len(unrecorded) - len(shown)} more" if len(shown) < len(unrecorded) else ""
            text = f"Not recorded in NetBox: {', '.join(shown)}{more}"
            if len(shown) <= 1 or text_lines(text, width, size) <= 2:
                break
            shown.pop()
        tip = "No modules or inventory items recorded in NetBox for: " + ", ".join(unrecorded)
        values = {"DEVICE": (gaps.MISSING, "", True, tip), "CHASSIS": (text, "", False, tip)}
        rows.append([values.get(next((k for k in values if col.startswith(k)), ""), ("—", "")) for col in header])
    return rows


def _joined_names(names: list[str]) -> str:
    """'S01-FW-EDGE-01/02' for a pair, 'S01-C01-IE01 … S01-C03-IE03 (9)' for a run of identical boxes."""
    if len(names) == 1:
        return names[0]
    prefix = os.path.commonprefix(names).rstrip("-0123456789") if len(names) <= 3 else ""
    if prefix and len(prefix) >= 4 and all(len(n) > len(prefix) for n in names):
        cut = len(prefix)
        tails = [n[cut:] for n in names]
        if all(re.fullmatch(r"[-]?\w{1,4}", t) for t in tails):
            return prefix.rstrip("-") + "-" + "/".join(t.lstrip("-") for t in tails)
    return f"{names[0]} … {names[-1]} ({len(names)})"


def _fill_hardware_cards(g: Graph, nb: NetBoxIndex) -> None:
    """The 'Power … · Fans …' line under each port map follows NetBox's inventory items.

    The line keeps its other notes (SVL ports, stack cables); only the power and fan
    segments are restated, and only when NetBox records those items for the device.
    """
    heads = []
    for i, el in g.els.items():
        m = re.match(r"\s*<b>([^<]+)</b>", el.get("value") or el.get("label") or "")
        if m and cell_of(el) is not None and cell_of(el).get("vertex") == "1":
            name = m.group(1).strip()
            members = [name] if name in nb.devices else \
                [n for n, d in nb.devices.items() if _get(d, "virtual_chassis", "name") == name]
            if members:
                heads.append((g.box(i), members))
    for i, el in g.els.items():
        value = el.get("value") or el.get("label") or ""
        if not value.startswith("<b>Power</b>") or cell_of(el) is None:
            continue
        x, y, w, h = g.box(i)
        above = [(y - hy, members) for (hx, hy, hw_, hh), members in heads if abs(hx - x) < 2 and 0 < y - hy < 400]
        if not above:
            continue
        members = min(above)[1]
        power, fans = nb.hw.power(members), nb.hw.fans(members)
        per = " per member" if len(members) > 1 else ""
        segments = [seg.strip() for seg in value.split(" · ")]
        if power:
            text = f"<b>Power</b> {html.escape(nb.hw.power([members[0]]) or power)}{per}"
            segments = [text if seg.startswith("<b>Power</b>") else seg for seg in segments]
        if fans:
            text = f"<b>Fans</b> {html.escape(nb.hw.fans([members[0]]) or fans)}{per}"
            if any(seg.startswith("<b>Fans</b>") for seg in segments):
                segments = [text if seg.startswith("<b>Fans</b>") else seg for seg in segments]
            else:
                segments.insert(1, text)
        g.set_value(el, " · ".join(segments))


def _cable_ids(cables: list[dict]) -> str:
    """The NetBox ids of a row's cables, '#7, #8' or '#101–104', so a row names its records even when
    the labels are cabinet-local numbers."""
    ids = sorted({c.get("id") for c in cables if isinstance(c.get("id"), int)})
    if not ids:
        return ", ".join(dict.fromkeys(_short_dev(c.get("label") or "") for c in cables if c.get("label")))
    runs, run = [], [ids[0]]
    for i in ids[1:]:
        if i == run[-1] + 1:
            run.append(i)
        else:
            runs.append(run)
            run = [i]
    runs.append(run)
    return ", ".join(f"#{r[0]}–{r[-1]}" if len(r) > 2 else ", ".join(f"#{i}" for i in r) for r in runs)


MISSING_TRUNK = gaps.MISSING


def _trunk_vlans(lag_if: dict, ia: dict, ib: dict, sep: str = ", ") -> str:
    """The allowed list on a trunk; '—' on an access or routed port; '?' on a trunk NetBox has no list for.

    The register joins with ", " so a long list wraps inside its cell; a pill joins with ","
    to stay one short run on the line.
    """
    for iface in (lag_if, ia, ib):
        mode = _get(iface, "mode", "value")
        if mode == "access":
            vid = _get(iface, "untagged_vlan", "vid")
            return f"access {vid}" if vid else MISSING_TRUNK
        if mode == "tagged-all":
            return "all"
        if mode == "tagged":
            return compact_vids([v.get("vid") for v in iface.get("tagged_vlans") or []], sep) or MISSING_TRUNK
    return "—"


def compact_vids(vids, sep: str = ",") -> str:
    """'181,189' for two VLANs, '210–249' for a run: the form the drawing uses on its link pills."""
    ids = sorted({int(v) for v in vids if str(v).isdigit()})
    runs: list[list[int]] = []
    for v in ids:
        if runs and v == runs[-1][-1] + 1:
            runs[-1].append(v)
        else:
            runs.append([v])
    return sep.join(f"{r[0]}–{r[-1]}" if len(r) > 2 else sep.join(map(str, r)) for r in runs)


def _ports(ends: list[tuple[str, str]]) -> str:
    """Every port on one side of a cable: a breakout or MPO trunk lands on several."""
    return "+".join(short_if(port) for _, port in ends)


def _zone_of_table(g: Graph, table: str) -> str:
    """The zone a VLAN table belongs to: the 'ZONE XXX' title on the card around it."""
    tx, ty, tw, th = g.box(table)
    best = None
    titles = g.cache.get("zone_titles")
    if titles is None:  # one scan per page, not one per table
        titles = []
        for i, el in g.els.items():
            text = plain(g.value(el))
            if text.upper().startswith("ZONE "):
                titles.append((i, text, g.box(i)))
        g.cache["zone_titles"] = titles
    for i, text, (x, y, w, h) in titles:
        if x - 30 <= tx <= x + max(w, 40) + 30 and y - 10 <= ty and ty - y < 160:
            # A title whose column the table sits in beats a neighbor's title that is merely close.
            key = (not x - 1 <= tx <= x + w, ty - y)
            if best is None or key < best[0]:
                best = (key, text)
    if not best:
        return ""
    return "zone-" + best[1][5:].split("·")[0].strip().lower().replace(" ", "-")


def _vlan_rows(g, table, header, nb: NetBoxIndex):
    zone = _zone_of_table(g, table)
    if not zone or not nb.vlans:
        return []
    by_vlan = defaultdict(list)
    for p in nb.prefixes:
        if _get(p, "vlan", "id", default=None) is not None:
            by_vlan[p["vlan"]["id"]].append(p)
    vlans = [v for v in nb.vlans if ot.vlan_zone(v, by_vlan.get(v.get("id"))) == zone]
    if not vlans:
        return []
    ssids = defaultdict(list)
    for w in nb.wlans:
        if _get(w, "vlan", "id", default=None) is not None and w.get("ssid"):
            ssids[w["vlan"]["id"]].append(w["ssid"])
    rows = []
    for v in sorted(vlans, key=lambda v: v.get("vid", 0)):
        # Every subnet on the VLAN, IPv4 first: secondary and IPv6 prefixes count too.
        prefixes = sorted(by_vlan.get(v.get("id"), []), key=_prefix_order)
        # A gateway recorded on the prefix (custom field) wins over the one worked out from addresses.
        gws = [str((p.get("custom_fields") or {}).get("gateway") or "")
               or _gateway(p.get("prefix"), nb, _get(p, "vrf", "id", default=None)) for p in prefixes]
        vrf = next((_label(p.get("vrf")) for p in prefixes if p.get("vrf")), "")
        if len(prefixes) > 1 and v.get("id") is not None:
            subnet_link = nb.link("ipam/prefixes", vlan_id=v["id"])
        else:
            subnet_link = nb.link("ipam/prefixes", prefixes[0]) if prefixes else ""
        values = {
            "VLAN": (str(v.get("vid", "")), nb.link("ipam/vlans", v)),
            "NAME": (" · ".join([v.get("name", "")] + [f"SSID {s}" for s in ssids.get(v.get("id"), [])]).strip(" ·"),
                     "", False, "The wireless LAN on this VLAN" if ssids.get(v.get("id")) else ""),
            "SUBNET": (" · ".join(p.get("prefix", "") for p in prefixes), subnet_link),
            # A table with its own VRF column keeps the VRF out of the gateway cell.
            "GATEWAY": (" · ".join(x for x in (" / ".join(g for g in gws if g), "" if "VRF" in header else vrf) if x), ""),
            "VRF": (vrf, ""),
        }
        rows.append([values.get(next((k for k in values if col.startswith(k)), ""), ("", "")) for col in header])
    return rows


def _prefix_order(p: dict) -> tuple:
    try:
        net = ipaddress.ip_network(p.get("prefix", ""), strict=False)
        return net.version, net
    except ValueError:
        return 9, p.get("prefix", "")


FHRP_ROLES = ("vip", "hsrp", "vrrp", "glbp", "carp", "anycast")


def _host_part(addr, net) -> str:
    """'.1' for 10.1.10.1 in a /24; '::1' for 2001:db8:10::1 in a /64."""
    if addr.version == 4:
        return f".{str(addr).split('.')[-1]}"
    return f"::{int(addr) - int(net.network_address):x}"


def _gateway(prefix: str | None, nb: NetBoxIndex, vrf=None) -> str:
    """The address in a prefix that sits on a device interface (an SVI or subinterface).

    OT sites often reuse address space per zone VRF, so only addresses in the
    prefix's own VRF count.
    """
    if not prefix:
        return ""
    try:
        net = ipaddress.ip_network(prefix, strict=False)
    except ValueError:
        return ""
    best = None
    for addr, ip in nb.parsed_ips:
        if addr not in net or _get(ip, "vrf", "id", default=None) != vrf:
            continue
        obj = ip.get("assigned_object") or {}
        dev = _get(obj, "device", "name") or _get(obj, "virtual_machine", "name")
        role = _get(ip, "role", "value")
        # An HSRP/VRRP address is assigned to its FHRP group, which names the protocol.
        fhrp = _get(obj, "protocol", "value") or (obj.get("protocol") if isinstance(obj.get("protocol"), str) else "")
        rank = 0 if role in FHRP_ROLES or fhrp else 1 if dev else 2
        if dev:
            label = f"{_short_dev(dev)} {_host_part(addr, net)}"
        elif role in FHRP_ROLES or fhrp:
            label = f"{(fhrp or role).upper()} {_host_part(addr, net)}"
        else:
            label = str(addr)
        if best is None or rank < best[0]:
            best = (rank, label)
    return best[1] if best else ""


# ---------------------------------------------------------------- title block
PROVENANCE_STYLE = ("text;html=1;align=right;verticalAlign=middle;fontSize=9;fontFamily=Inter;fontColor=#64748B;"
                    "spacing=0;whiteSpace=nowrap;")


def _fill_title(g: Graph, nb: NetBoxIndex, report: Report, old_code: str, today: str | None) -> None:
    """The title block: project, drawing, site, revision, build date, plus the provenance line under it.

    Every sheet of a site's set says the same site, the same revision and the
    same date, and the line under the table says what the sheet was built from.
    """
    code = report.site_code
    site_name = nb.site.get("name") or ""
    prov = report.provenance
    project = (report.intake.settings.get("project") or "").strip() or \
        (f"{site_name} · network standard" if site_name else "Network standard")
    place_logo(g, report.intake.settings.get("logo") or "")
    for table in g.tables():
        header = g.header(table)
        if "SITE" not in header or "DATE" not in header:
            continue
        rows = g.rows(table)
        if len(rows) < 2:
            continue
        cells = g.row_cells(rows[1])
        for col, cell_id in zip(header, cells):
            el = g.els[cell_id]
            if col == "SITE":
                g.set_value(el, code)
                if nb.url and nb.site.get("id") is not None:
                    g.wrap(cell_id, link=nb.link("dcim/sites", nb.site), linkTarget="_blank")
            elif col == "DATE":
                g.set_value(el, prov.built)
            elif col == "REV":
                g.set_value(el, prov.revision)
            elif col == "PROJECT":
                g.set_value(el, html.escape(project, quote=False))
            elif col == "DRAWING" and old_code != code:
                g.set_value(el, re.sub(rf"\b{re.escape(old_code)}\b", code, g.value(el)))
        _add_provenance_line(g, table, prov)
    if old_code == code and not site_name:
        return
    # Page titles name the site: 'S01 · Plant A — Physical Architecture'.
    for el in g.els.values():
        cell = cell_of(el)
        if cell is None or "fontSize=22" not in (cell.get("style") or ""):
            continue
        text = g.value(el)
        text = re.sub(rf"\b{re.escape(old_code)}\b", code, text)
        new_name = html.escape(site_name, quote=False)
        if site_name and new_name not in text:  # not again on a rebuild, where 'Plant A' may be part of 'Plant AB'
            old_name = re.escape(html.escape(profiles.current().site_name, quote=False))
            text = re.sub(rf"(?<!\w){old_name}(?!\w)", lambda m: new_name, text)
        g.set_value(el, text)


def _card_around(g: Graph, el_id: str) -> str | None:
    """The smallest rounded card (top-level vertex) that holds the whole of ``el_id``."""
    tx, ty, tw, th = g.box(el_id)
    card = None
    for i, el in g.els.items():
        cell = cell_of(el)
        if i == el_id or cell is None or cell.get("vertex") != "1" or cell.get("parent") not in g.layers:
            continue
        cx, cy, cw, ch = g.box(i)
        if cx <= tx and cy <= ty and cx + cw >= tx + tw and cy + ch >= ty + th:
            if card is None or cw * ch < g.box(card)[2] * g.box(card)[3]:
                card = i
    return card


PROVENANCE_EXTRA = 16


def _add_provenance_line(g: Graph, table: str, prov: "provenance.Provenance") -> None:
    """One grey line inside the title-block card, under the table: revision, dates, source, settings."""
    note_id = f"{g.diagram.get('id')}-provenance"
    card = _card_around(g, table)
    tx, ty, tw, th = g.box(table)
    if note_id in g.els or card is None:
        return
    cx, cy, cw, ch = g.box(card)
    g.geometry(card).set("height", f"{ch + PROVENANCE_EXTRA:g}")
    el = ET.SubElement(g.root, "object", {"id": note_id, "label": prov.line(), "netdiagrams_provenance": "1",
                                          "tooltip": "\n".join(l.lstrip("- ") for l in prov.markdown())})
    cell = ET.SubElement(el, "mxCell", {"vertex": "1", "parent": g.layer_id(card), "style": PROVENANCE_STYLE})
    ET.SubElement(cell, "mxGeometry", {"x": f"{tx:g}", "y": f"{cy + ch - 2:g}", "width": f"{tw:g}", "height": "14",
                                       "as": "geometry"})
    g.reindex()


def _separate_example(g: Graph, nb: NetBoxIndex, export: dict, report: Report, site: model.Site,
                      guide: bool) -> None:
    """Rule set from :mod:`truth`: watermark examples, hide prose, derive labels, fill zone tables."""
    page = g.diagram.get("id") or ""
    data_date = report.intake.data_date or report.provenance.built
    report.guide_notes += truth.move_guides(g)
    marked, kept = truth.mark_examples(g, report.edited_examples)
    report.examples_marked += marked
    report.examples_kept += kept
    if not guide:
        truth.remove_guides(g)
    for _, was, now in truth.derive_group_labels(g, nb.devices, nb.register_only, _is_device):
        report.label_changes.append((g.name, was, now))
    if page == "overview":
        truth.derive_overview(g, site, nb.devices, nb.register_only, data_date, report.provenance.revision,
                              len(export.get("cables", [])), len(nb.vlans))
    roles = Counter((d.get("role") or {}).get("slug") for d in nb.devices.values())
    truth.derive_subtitles(g, {
        "zones": len([z for z in site.zones.values() if z.slug]), "vlans": len(nb.vlans),
        "prefixes": len(nb.prefixes), "devices": len(nb.devices), "cables": len(export.get("cables", [])),
        "wlc": roles["wireless-controller"], "ap": roles["access-point"], "ptp": roles["ptp-radio"],
        "ssid": len(nb.wlans)}, data_date)
    if page == "physical":
        truth.derive_cell_notes(g, nb.devices, nb.names, nb.interfaces, export.get("cables", []), _is_device,
                                _short_dev)
    if page == "register":
        by_prefix = {p.get("prefix"): p for p in nb.prefixes}

        def gateway(prefix: str, vrf_name: str) -> str:
            p = by_prefix.get(prefix) or {}
            return (str((p.get("custom_fields") or {}).get("gateway") or "")
                    or _gateway(prefix, nb, _get(p, "vrf", "id", default=None)))

        for title in truth.fill_zone_tables(g, site, nb.devices, gateway):
            report.tables.append((g.name, title, len([z for z in site.zones.values() if z.slug])))


SSID_EXTRA_COLUMNS = (  # (title, width, after, donors that pay evenly)
    ("GUEST CONTROLS", 110, "BROADCAST ON", ["SECURITY · AAA", "BROADCAST ON", "VLAN · SUBNET"]),
)


def _fill_ssids(g: Graph, nb: NetBoxIndex, report: Report) -> None:
    """The SSID table from NetBox wireless LANs and their custom fields; never the template's rows."""
    for table in g.tables():
        header = g.header(table)
        if header[:1] != ["SSID"]:
            continue
        if nb.wlans:
            for title, width, after, donors in SSID_EXTRA_COLUMNS:
                g.add_column(table, title, width, after, donors)
            header = g.header(table)
        rows = wireless_page.ssid_rows(g, table, header, nb)
        if rows:
            g.fill_table(table, rows)
            report.tables.append((g.name, "SSID table", len(rows)))


def place_logo(g: Graph, logo: str = "") -> None:
    """The template's LOGO placeholder never prints: it shows the settings' logo, or stays blank."""
    style = _logo_style(logo)
    for el in g.els.values():
        cell = cell_of(el)
        if plain(g.value(el)) == "LOGO" and cell is not None:
            g.set_value(el, "")
            cell.set("style", style or (cell.get("style") or "") + "fillColor=none;strokeColor=none;")


def finish_sample(template: ET.Element) -> ET.Element:
    """The bundled Plant A as printed by ``netdiagrams sample``: no LOGO box, sheets numbered, chapter notes."""
    for diagram in template.findall("diagram"):
        g = Graph(diagram)
        place_logo(g)
        _add_book_note(g)
    _number_sheets(template)
    return template


def _logo_style(logo: str) -> str:
    """A draw.io image style for the company logo: a URL, or a PNG, JPEG or SVG file embedded."""
    if not logo:
        return ""
    if logo.startswith(("http://", "https://")):
        return f"shape=image;imageAspect=1;aspect=fixed;image={logo};"
    import base64
    from pathlib import Path

    from .settings import SettingsError

    kind = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".svg": "svg+xml"}.get(Path(logo).suffix.lower())
    if not kind:
        raise SettingsError(f"logo {logo}: use a PNG, JPEG or SVG file, or an http(s) URL")
    try:
        data = base64.b64encode(Path(logo).read_bytes()).decode()
    except OSError as err:
        raise SettingsError(f"logo {logo}: can't read it ({err.strerror or err})") from err
    return f"shape=image;imageAspect=1;aspect=fixed;image=data:image/{kind},{data};"


PLACEHOLDER_FRAGMENTS = (
    # (fragment in a label, keys it needs, what to show when the first key is empty, when the second is empty)
    ("%rack% · U%position%", ("rack", "position"), "U%position%", "%rack%"),
    ("U%position% · SN %serial%", ("position", "serial"), "SN %serial%", "U%position%"),
    ("U%position%", ("position", "position"), "", ""),
    ("%location% %rack%", ("location", "rack"), "%rack%", "%location%"),
    ("%location_path% %rack%", ("location_path", "rack"), "%rack%", "%location_path%"),
)


def _inherited(g: Graph, el: ET.Element, key: str) -> str | None:
    """A placeholder's value as draw.io resolves it: the shape's own data, else its parent shape's.

    A rack pill drawn inside a device card reads %rack% from the device, so it must not get an
    empty attribute of its own (that would hide the device's value).
    """
    seen = set()
    while el is not None and id(el) not in seen:
        seen.add(id(el))
        if key in el.attrib:
            return el.get(key)
        cell = cell_of(el)
        parent = cell.get("parent") if cell is not None else None
        el = g.els.get(parent) if parent and parent not in g.layers else None
        if el is not None and el.tag not in ("object", "UserObject"):
            el = None
    return None


def _tidy_placeholders(g: Graph) -> None:
    """A %key% draw.io cannot resolve stays on screen as literal text.

    Every key a label names gets an attribute (empty when NetBox has nothing), and the
    template's "rack · U" and "U · SN" fragments lose their separators when a half is empty.
    """
    empty = []
    for el_id, el in g.els.items():
        if el.tag not in ("object", "UserObject") or el.get("placeholders") != "1":
            continue
        label = el.get("label") or ""
        if "%" not in label:
            continue
        for fragment, (first, second), no_first, no_second in PLACEHOLDER_FRAGMENTS:
            if fragment in label:
                has_first, has_second = bool(_inherited(g, el, first)), bool(_inherited(g, el, second))
                if not has_first and not has_second:
                    label = label.replace(fragment, "")
                elif not has_first:
                    label = label.replace(fragment, no_first)
                elif not has_second:
                    label = label.replace(fragment, no_second)
        for key in set(re.findall(r"%(\w+)%", label)):
            if _inherited(g, el, key) is None:
                el.set(key, "")
        el.set("label", label)
        if not plain(label).strip() and not _is_device(el):
            empty.append(el_id)  # a badge with nothing left to say would print as an empty pill
    if empty:
        g.remove(empty)


def _repoint_links(g: Graph, nb: NetBoxIndex, rename) -> None:
    """Template links point at netbox.example.com by name; point them at this NetBox's objects."""
    if not nb.url:
        return
    for el in g.els.values():
        link = el.get("link") or ""
        if link.startswith(TEMPLATE_NETBOX):
            link = _resolve(link[len(TEMPLATE_NETBOX):], nb, rename)
            el.set("link", link)
        tip = el.get("tooltip") or ""
        if TEMPLATE_NETBOX in tip:
            el.set("tooltip", re.sub(re.escape(TEMPLATE_NETBOX) + r"\S*", link or nb.url, tip))


def _resolve(path: str, nb: NetBoxIndex, rename) -> str:
    parsed = urllib.parse.urlsplit(path)
    query = dict(urllib.parse.parse_qsl(parsed.query))
    route = parsed.path.strip("/")
    if route == "dcim/devices" and rename(query.get("name", "")) in nb.devices:
        return nb.link("dcim/devices", nb.devices[rename(query["name"])])
    if route == "circuits/circuits" and rename(query.get("cid", "")) in nb.circuits:
        return nb.link("circuits/circuits", nb.circuits[rename(query["cid"])])
    if route == "dcim/sites" and nb.site.get("slug"):
        return nb.link("dcim/sites", nb.site) if nb.site.get("id") is not None else \
            nb.link("dcim/sites", slug=nb.site["slug"])
    if query:
        query = {k: rename(v) for k, v in query.items()}
        return f"{nb.url}/{route}/?{urllib.parse.urlencode(query)}"
    return nb.url + path


# --------------------------------------------------- new links and the tray
def _add_netbox_cables(g: Graph, nb: NetBoxIndex, report: Report) -> None:
    """Draw NetBox cables the template has no line for, when both ends are on the page."""
    cards = {el.get("name"): i for i, el in g.els.items() if _is_device(el) and not g.hidden(i)}
    drawn = set(report.matched_cables)
    new = []
    for label, c in sorted(nb.cables.items()):
        if label in drawn:
            continue
        a = _ends(c.get("a_terminations"), nb.names)
        b = _ends(c.get("b_terminations"), nb.names)
        if not a or not b or a[0][0] not in cards or b[0][0] not in cards:
            continue
        new.append((label, c, a[0], b[0]))
    if not new:
        return
    layer = f"{g.diagram.get('id', 'p')}-nblinks"
    g.root.append(ET.Element("mxCell", {"id": layer, "value": ADDED_LINKS_LAYER, "style": "", "parent": "0"}))
    for n, (label, c, (adev, aport), (bdev, bport)) in enumerate(new):
        media = MEDIA.get(c.get("type") or "", c.get("type") or "")
        attrs = {"object": "dcim.cable", "cable_label": c.get("label") or label, **_cable_attrs([c], nb.names)}
        obj = ET.Element("object", {"id": f"{layer}-{n}", "label": html.escape(f"{short_if(aport)} – {short_if(bport)} · {media}", quote=False),
                                    **attrs})
        if nb.url:
            obj.set("link", nb.link("dcim/cables", c))
            obj.set("linkTarget", "_blank")
        obj.set("tooltip", _tooltip(obj))
        cell = ET.SubElement(obj, "mxCell", {
            "style": "edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=none;strokeColor=#2563EB;strokeWidth=1.5;"
                     "fontSize=9;fontColor=#1E3A8A;labelBackgroundColor=#FFFFFF;html=1;fontFamily=Inter;",
            "edge": "1", "parent": layer, "source": cards[adev], "target": cards[bdev]})
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        g.root.append(obj)
        report.added_cables.append(label)
    g.reindex()


def _add_tray(g: Graph, devices: list[dict], nb: NetBoxIndex) -> None:
    """Put NetBox devices with no slot below the physical page, ready to drag in."""
    page_w = float(g.model.get("pageWidth", 2000))
    # Under the drawn content, not under the page: a rebuild from the last drawing keeps the page and
    # border the previous tray grew, and a tray placed under those would walk down the page each build.
    skip = ("Controls", "Guides", "Copy of the typical")
    bottom = max((g.box(i)[1] + g.box(i)[3] for i, el in g.els.items() if cell_of(el) is not None
                  and cell_of(el).get("vertex") == "1" and cell_of(el).get("parent") in g.layers
                  and not g.layer_of(i).startswith(skip)
                  and not (g.layer_of(i).startswith("Border") and g.box(i)[2] > 1000)), default=0)
    top = bottom + 40
    layer_id = f"{g.diagram.get('id', 'p')}-unplaced"
    g.root.append(ET.Element("mxCell", {"id": layer_id, "value": UNPLACED_LAYER, "style": "", "parent": "0"}))
    heading = ET.Element("mxCell", {
        "id": f"{layer_id}-title", "parent": layer_id, "vertex": "1",
        "value": f"<b>In NetBox, no place on this drawing yet</b> · "
                 + (f"{len(devices)} devices · drag each one into place" if len(devices) != 1
                    else "1 device · drag it into place"),
        "style": "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=14;"
                 "fontColor=#B45309;spacing=2;fontFamily=Inter;"})
    ET.SubElement(heading, "mxGeometry", {"x": "24", "y": f"{top:g}", "width": "900", "height": "24",
                                          "as": "geometry"})
    g.root.append(heading)
    x, y, row_h = 24.0, top + 36, 0.0
    for n, d in enumerate(devices):
        attrs = _device_attrs(d, nb.url)
        shape = stencils.shape_for_role(attrs.get("role"))
        w = stencils.library()[shape]["w"]
        if x + w > page_w - 24:
            x, y, row_h = 24.0, y + row_h + 24, 0.0
        cells, w, h = stencils.device_cells(shape, f"{layer_id}-d{n}", layer_id, x, y, attrs)
        cells[0].set("tooltip", _tooltip(cells[0]))
        g.root.extend(cells)
        g.root.extend(status_marks(cells[0], f"{layer_id}-d{n}", intake.status(d), w))
        x += w + 24
        row_h = max(row_h, h)
    g.model.set("pageHeight", f"{y + row_h + 40:g}")
    g.reindex()
    _tidy_placeholders(g)  # a card with no rack keeps no empty "U" pill


def write(template: ET.Element, path) -> None:
    paper.fit(template)
    ET.ElementTree(template).write(path, encoding="utf-8", xml_declaration=False)
