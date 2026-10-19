"""What changed in NetBox since the last build, on the drawing and in the drift report.

Each build leaves ``<site>.state.json`` next to the drawing: a fingerprint of every
device and cable (the fields the drawing shows). The next build compares against it
and marks devices that are new or changed with a small pill on their shape, on a
layer of their own, so the day-to-day reader sees at a glance what moved since the
revision they last printed. The drift report lists the same with the old and new
values. Removed devices are listed, since there is no shape left to mark.
"""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .graph import Graph, cell_of
from .model import _get

FORMAT = "netdiagrams-state/1"
LAYER = "Changed since last build"
PILL = ("rounded=1;absoluteArcSize=1;arcSize=14;strokeColor=none;fontSize=8;fontStyle=1;html=1;spacing=0;"
        "whiteSpace=nowrap;fontFamily=Inter;")
NEW_STYLE = PILL + "fillColor=#DCFCE7;fontColor=#15803D;"
CHANGED_STYLE = PILL + "fillColor=#FEF3C7;fontColor=#B45309;"

DEVICE_FIELDS = ("role", "device_type", "serial", "asset_tag", "status", "location", "rack", "position",
                 "primary_ip4", "oob_ip", "platform", "sw_version", "zone")


def _device_fingerprint(d: dict, zone: str) -> dict[str, str]:
    cf = d.get("custom_fields") or {}
    return {
        "role": _get(d, "role", "slug"), "device_type": _get(d, "device_type", "model"),
        "serial": d.get("serial") or "", "asset_tag": d.get("asset_tag") or "",
        "status": _get(d, "status", "value"), "location": _get(d, "location", "name"),
        "rack": _get(d, "rack", "name"), "position": "" if d.get("position") is None else f"{d['position']:g}",
        "primary_ip4": _get(d, "primary_ip4", "address"), "oob_ip": _get(d, "oob_ip", "address"),
        "platform": _get(d, "platform", "slug"), "sw_version": str(cf.get("sw_version") or ""), "zone": zone,
    }


def _cable_key(c: dict) -> str:
    ends = []
    for side in ("a_terminations", "b_terminations"):
        terms = c.get(side) or []
        obj = (terms[0].get("object") or {}) if terms else {}
        ends.append(f"{(obj.get('device') or {}).get('name', '?')}:{obj.get('name', '?')}")
    return " ⇄ ".join(sorted(ends))


def fingerprint(export: dict, zone_of, revision: str = "", built: str = "") -> dict:
    """The state this build saw: one entry per device and cable, keyed by name."""
    devices = {}
    for d in export.get("devices", []):
        if d.get("name"):
            zones = zone_of(d)
            devices[d["name"]] = _device_fingerprint(d, zones[0] if zones else "")
    cables = {}
    for c in export.get("cables", []):
        cables[_cable_key(c)] = {"label": c.get("label") or "", "type": c.get("type") or "",
                                 "status": _get(c, "status", "value")}
    return {"format": FORMAT, "revision": revision, "built": built, "devices": devices, "cables": cables}


@dataclass
class Changes:
    since_revision: str = ""
    since_built: str = ""
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[tuple[str, str, str, str]] = field(default_factory=list)   # device, field, was, now
    cables_added: list[str] = field(default_factory=list)
    cables_removed: list[str] = field(default_factory=list)
    cables_changed: list[tuple[str, str, str, str]] = field(default_factory=list)

    @property
    def any(self) -> bool:
        return bool(self.added or self.removed or self.changed or self.cables_added or self.cables_removed
                    or self.cables_changed)

    @property
    def changed_devices(self) -> list[str]:
        return sorted({name for name, *_ in self.changed})

    def summary(self) -> str:
        parts = []
        n = lambda count, word: f"{count} {word}" + ("" if count == 1 else "s")
        if self.added:
            parts.append(n(len(self.added), "new device"))
        if self.removed:
            parts.append(f"{len(self.removed)} removed")
        if self.changed:
            parts.append(f"{n(len(self.changed), 'field')} changed on {n(len(self.changed_devices), 'device')}")
        cables = len(self.cables_added) + len(self.cables_removed) + len(self.cables_changed)
        if cables:
            parts.append(n(cables, "cable change"))
        return ", ".join(parts) if parts else "nothing"


def compare(now: dict, previous: dict | None) -> Changes | None:
    """None when there is no previous state to compare with."""
    if not previous or previous.get("format") != FORMAT:
        return None
    out = Changes(previous.get("revision", ""), previous.get("built", ""))
    before, after = previous.get("devices") or {}, now.get("devices") or {}
    out.added = sorted(set(after) - set(before))
    out.removed = sorted(set(before) - set(after))
    for name in sorted(set(after) & set(before)):
        for key in DEVICE_FIELDS:
            was, is_now = before[name].get(key, ""), after[name].get(key, "")
            if was != is_now:
                out.changed.append((name, key, was, is_now))
    before, after = previous.get("cables") or {}, now.get("cables") or {}
    out.cables_added = sorted(set(after) - set(before))
    out.cables_removed = sorted(set(before) - set(after))
    for key in sorted(set(after) & set(before)):
        for fld in ("label", "type", "status"):
            if before[key].get(fld, "") != after[key].get(fld, ""):
                out.cables_changed.append((key, fld, before[key].get(fld, ""), after[key].get(fld, "")))
    return out


def markdown(changes: Changes | None) -> list[str]:
    if changes is None:
        return ["## Changes since the last build", "", "First build here: nothing to compare with. The next build "
                "will list what changed in NetBox since this one.", ""]
    head = f"## Changes since Rev {changes.since_revision or '?'}" + (f" ({changes.since_built})" if changes.since_built else "")
    lines = [head, "", f"{changes.summary().capitalize()}.", ""]
    if changes.added:
        lines += ["New devices: " + ", ".join(changes.added), ""]
    if changes.removed:
        lines += ["Removed from NetBox (or this site): " + ", ".join(changes.removed), ""]
    if changes.changed:
        lines += ["| Device | Field | Was | Now |", "| --- | --- | --- | --- |"]
        lines += [f"| {n} | {k} | {w or '—'} | {v or '—'} |" for n, k, w, v in changes.changed]
        lines.append("")
    if changes.cables_added:
        lines += ["New cables: " + ", ".join(changes.cables_added), ""]
    if changes.cables_removed:
        lines += ["Cables gone: " + ", ".join(changes.cables_removed), ""]
    if changes.cables_changed:
        lines += ["| Cable | Field | Was | Now |", "| --- | --- | --- | --- |"]
        lines += [f"| {c} | {k} | {w or '—'} | {v or '—'} |" for c, k, w, v in changes.cables_changed]
        lines.append("")
    return lines


def mark(template: ET.Element, changes: Changes | None, is_device) -> int:
    """A NEW or CHANGED pill on every drawn device the comparison names; returns how many."""
    if changes is None or not (changes.added or changes.changed):
        return 0
    added = set(changes.added)
    fields = {}
    for name, key, was, now in changes.changed:
        fields.setdefault(name, []).append(f"{key}: {was or '—'} → {now or '—'}")
    marked = 0
    for diagram in template.findall("diagram"):
        if diagram.find("mxGraphModel") is None:
            continue
        g = Graph(diagram)
        page = diagram.get("id") or "page"
        layer = f"{page}-changes"
        pills = []
        for el_id, el in list(g.els.items()):
            if not is_device(el) or g.hidden(el_id):
                continue
            name = el.get("name") or ""
            if name not in added and name not in fields:
                continue
            x, y, w, h = g.box(el_id)
            if w < 40 or h < 16:
                continue
            new = name in added
            label = "NEW" if new else "CHANGED"
            tip = (f"{name} is new in NetBox since Rev {changes.since_revision}" if new
                   else f"{name} changed since Rev {changes.since_revision}:\n" + "\n".join(fields[name]))
            pill_w = 30 if new else 50
            obj = ET.Element("object", {"id": f"{el_id}-changed", "label": label, "tooltip": tip,
                                        "netdiagrams_change": "new" if new else "changed"})
            cell = ET.SubElement(obj, "mxCell", {"vertex": "1", "parent": layer,
                                                 "style": NEW_STYLE if new else CHANGED_STYLE})
            ET.SubElement(cell, "mxGeometry", {"x": f"{x + w - pill_w - 4:g}", "y": f"{y - 7:g}",
                                               "width": f"{pill_w}", "height": "13", "as": "geometry"})
            pills.append(obj)
        if pills:
            g.root.append(ET.Element("mxCell", {"id": layer, "value": LAYER, "style": "", "parent": "0"}))
            for pill in pills:
                g.root.append(pill)
            marked += len(pills)
    return marked
