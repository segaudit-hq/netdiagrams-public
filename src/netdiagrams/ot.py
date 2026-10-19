"""OT structure in NetBox: security zones, Purdue levels and the location tree.

NetBox has no built-in zone or Purdue model, so OT teams record them in a few
common ways. NetDiagrams reads all of them, first match wins:

1. a custom field on the object: ``security_zone`` (or ``iec62443_zone``, ``ot_zone``,
   or the field the site's settings name) and ``purdue_level`` (or ``purdue``);
2. a ``zone-*`` tag on the object;
3. the location tree: the nearest location (cell, line, area, building) that
   carries a zone custom field or tag, or whose slug names a cell or line;
4. for VLANs and prefixes: the VLAN role, VLAN group or VRF named after a zone.

``netdiagrams netbox-setup`` writes import files for the custom fields, tags and
roles, so a NetBox without them can take them in one import.
"""

from __future__ import annotations

import re

from .model import ZONE_PREFIX, _get, _label, band_for_zone, bands, zone_slug

# The site's own field names are copied to these by intake.prepare (see settings.py).
ZONE_FIELDS = ("security_zone",)
LEVEL_FIELDS = ("purdue_level",)
SL_FIELDS = ("security_level_target",)
CELL_SLUG = re.compile(r"^(cell|line|area)[-_]?\d+", re.I)


def _cf(obj: dict, names) -> str:
    fields = obj.get("custom_fields") or {}
    for name in names:
        value = fields.get(name)
        if isinstance(value, dict):  # a selection ({value, label}) or an object reference
            value = value.get("value") or value.get("slug") or value.get("name") or value.get("label")
        if isinstance(value, list):
            value = value[0] if value else None
            if isinstance(value, dict):
                value = value.get("value") or value.get("slug") or value.get("name")
        if value not in (None, ""):
            return str(value)
    return ""


def _tag_zones(obj: dict) -> list[str]:
    return [t.get("slug", "") for t in obj.get("tags") or [] if t.get("slug", "").startswith(ZONE_PREFIX)]


def _norm_zone(value: str) -> str:
    return zone_slug(re.sub(r"[\s_]+", "-", value.strip().lower())) if value else ""


class Locations:
    """The site's location tree, so a device can inherit its cell's zone."""

    def __init__(self, locations: list[dict] | None):
        self.by_id = {loc.get("id"): loc for loc in locations or [] if loc.get("id") is not None}
        roots = [i for i, loc in self.by_id.items() if (loc.get("parent") or {}).get("id") not in self.by_id]
        # A sole top-level location holding everything (the campus): left off card paths, as the
        # site name already says it.
        self.campus = roots[0] if len(roots) == 1 and len(self.by_id) > 1 else None

    def chain(self, location: dict | None) -> list[dict]:
        out, seen = [], set()
        loc = self.by_id.get((location or {}).get("id"), location)
        while loc and loc.get("id") not in seen:
            seen.add(loc.get("id"))
            out.append(loc)
            parent = loc.get("parent") or {}
            loc = self.by_id.get(parent.get("id"), parent if parent.get("id") else None)
        return out

    def path(self, location: dict | None) -> str:
        """'Building 1 › Hall A › Cell 01', outermost first."""
        return " › ".join(_label(loc) for loc in reversed(self.chain(location)) if _label(loc))

    def card_chain(self, location: dict | None) -> list[dict]:
        """The chain outermost first, without the campus root."""
        return [loc for loc in reversed(self.chain(location)) if loc.get("id") != self.campus or self.campus is None]

    def card_path(self, location: dict | None) -> str:
        """'Building 1 › Hall A › Cell 01' for a card: the path without the campus root."""
        return " › ".join(_label(loc) for loc in self.card_chain(location) if _label(loc))

    def zone(self, location: dict | None) -> str:
        for loc in self.chain(location):
            zone = _norm_zone(_cf(loc, ZONE_FIELDS))
            if zone:
                return zone
            tags = _tag_zones(loc)
            if tags:
                return tags[0]
            if CELL_SLUG.match(loc.get("slug") or ""):
                return _norm_zone(re.sub(r"[-_]", "", CELL_SLUG.match(loc["slug"]).group(0)))
        return ""

    def level(self, location: dict | None) -> str:
        for loc in self.chain(location):
            level = _cf(loc, LEVEL_FIELDS)
            if level:
                return normalize_level(level)
        return ""


def device_zones(d: dict, locations: Locations | None = None) -> list[str]:
    """Every zone a device belongs to, most specific first."""
    zones = []
    field = _norm_zone(_cf(d, ZONE_FIELDS))
    if field:
        zones.append(field)
    zones += [z for z in _tag_zones(d) if z not in zones]
    if not zones and locations is not None:
        loc_zone = locations.zone(d.get("location"))
        if loc_zone:
            zones.append(loc_zone)
    return zones


def normalize_level(value: str) -> str:
    """'3', 'L3', 'Level 3', 'level-3-5', '3.5' -> 'L3' or 'L3.5'; '0-2', 'L2' -> 'L2–0'."""
    text = str(value).strip().lower().replace("level", "").replace("_", "-").strip(" -l")
    m = re.match(r"(\d)(?:[.-](5))?", text)
    if not m:
        return ""
    major = int(m.group(1))
    if major <= 2:
        return "L2–0"
    return f"L{major}.5" if m.group(2) else f"L{min(major, 5)}"


def device_level(d: dict, zones: list[str], locations: Locations | None = None) -> str:
    level = normalize_level(_cf(d, LEVEL_FIELDS))
    if not level and locations is not None:
        level = locations.level(d.get("location"))
    return level or band_for_zone(zones[0] if zones else None)[0]


def band_for_level(level: str) -> tuple | None:
    return next((b for b in bands() if b[0] == level), None)


def security_level(d: dict) -> str:
    value = _cf(d, SL_FIELDS)
    m = re.search(r"\d", value)
    return f"SL-T {m.group(0)}" if m else value


def vlan_zone(v: dict, prefixes: list[dict] | None = None) -> str:
    """A VLAN's zone: custom field, tag, role, VLAN group, then its prefixes' VRF or zone."""
    zone = _norm_zone(_cf(v, ZONE_FIELDS))
    if zone:
        return zone
    tags = _tag_zones(v)
    if tags:
        return tags[0]
    role = _get(v, "role", "slug")
    if role:
        return zone_slug(role)
    group = _get(v, "group", "slug")
    if group and group.startswith(ZONE_PREFIX):
        return group
    for p in prefixes or []:
        zone = _norm_zone(_cf(p, ZONE_FIELDS)) or next(iter(_tag_zones(p)), "")
        if zone:
            return zone
        vrf = _get(p, "vrf", "name")
        if vrf and band_for_zone(_norm_zone(vrf))[0] not in ("—", "?"):
            return _norm_zone(vrf)
    return ""
