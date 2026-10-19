"""Turn raw NetBox objects into the zones, devices and links a drawing needs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import profiles

# Purdue bands, top to bottom (the manufacturing profile's). A zone tag lands in the
# first band whose prefixes match its slug (after "zone-"). Other industries band
# their zones their own way: see profiles.py and bands().
BANDS = list(profiles.MANUFACTURING.bands)
OTHER_BAND = ("—", "OTHER ZONES", ())
UNZONED_BAND = ("?", "NOT ZONED IN NETBOX", ())
ZONE_PREFIX = "zone-"


def _natural(name: str) -> list:
    """Sort IDF2 before IDF10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def _get(obj, *path, default=""):
    for key in path:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
    return default if obj is None else obj


def _label(obj) -> str:
    """NetBox nested objects carry 'name' (or 'model', 'label', 'value')."""
    if isinstance(obj, dict):
        for key in ("name", "model", "label", "value", "display"):
            if obj.get(key):
                return str(obj[key])
        return ""
    return "" if obj is None else str(obj)


def _number(value) -> str:
    if value is None:
        return ""
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def zone_slug(slug: str) -> str:
    slug = (slug or "").strip().lower()
    return slug if slug.startswith(ZONE_PREFIX) else ZONE_PREFIX + slug


def bands() -> list[tuple]:
    """The bands of the profile in force, top to bottom."""
    return list(profiles.current().bands)


def band_for_zone(zone: str | None) -> tuple:
    if not zone:
        return UNZONED_BAND
    name = zone[len(ZONE_PREFIX):]
    for band in bands():
        # "cell01" and "line2" count as cells; other prefixes need "-" ("it-ent", "ot-ops").
        if any(name == p or name.startswith(p + "-") or (p in ("cell", "line") and name.startswith(p))
               for p in band[2]):
            return band
    return OTHER_BAND


@dataclass
class Device:
    id: int
    name: str
    role: str
    zones: list[str]
    attrs: dict[str, str]

    @property
    def zone(self) -> str | None:
        return self.zones[0] if self.zones else None


@dataclass
class Link:
    label: str
    type: str
    color: str
    a_device: int
    b_device: int
    a_port: str
    b_port: str
    attrs: dict[str, str]


@dataclass
class Vlan:
    vid: int
    name: str
    zone: str | None
    prefixes: list[str] = field(default_factory=list)
    vrf: str = ""
    tenant: str = ""     # the VLAN's tenant, else its first prefix's: who owns a zone with no device


@dataclass
class Zone:
    slug: str
    name: str
    band: tuple
    devices: list[Device] = field(default_factory=list)
    vlans: list[Vlan] = field(default_factory=list)


@dataclass
class Site:
    name: str
    slug: str
    netbox_url: str
    zones: dict[str, Zone]
    devices: dict[int, Device]
    links: list[Link]

    def bands(self) -> list[tuple[tuple, list[Zone]]]:
        order = bands() + [OTHER_BAND, UNZONED_BAND]
        grouped = []
        for band in order:
            zones = [z for z in self.zones.values() if z.band == band]
            if zones:
                grouped.append((band, sorted(zones, key=lambda z: z.slug)))
        return grouped


def _device_attrs(d: dict, netbox_url: str) -> dict[str, str]:
    attrs = {
        "name": d.get("name") or f"device-{d.get('id')}",
        "role": _get(d, "role", "slug") or _get(d, "device_role", "slug"),
        "manufacturer": _label(_get(d, "device_type", "manufacturer", default=None)),
        "device_type": _label(d.get("device_type")),
        "platform": _get(d, "platform", "slug"),
        "serial": d.get("serial") or "",
        "asset_tag": d.get("asset_tag") or "",
        "status": _get(d, "status", "value") or str(d.get("status") or ""),
        "site": _get(d, "site", "slug"),
        "location": _label(d.get("location")),
        "rack": _label(d.get("rack")),
        "position": _number(d.get("position")),
        "face": _get(d, "face", "value"),
        "primary_ip4": _get(d, "primary_ip4", "address"),
        "virtual_chassis": _label(d.get("virtual_chassis")),
        "vc_position": "" if d.get("vc_position") is None else str(d["vc_position"]),
        "description": d.get("description") or "",
        "tags": ",".join(t.get("slug", "") for t in d.get("tags") or []),
    }
    if _get(d, "role", "netbox_slug"):  # the site's own role, when settings mapped it to the template's
        attrs["netbox_role"] = _get(d, "role", "netbox_slug")
    for key in ("primary_ip6", "oob_ip"):  # NetBox 4.1+ out-of-band address, and IPv6
        if _get(d, key, "address"):
            attrs[key] = _get(d, key, "address")
    for key, value in (d.get("custom_fields") or {}).items():
        if value not in (None, "", [], {}):
            if isinstance(value, list):   # a multiple selection (compliance scope): its values, comma-separated
                attrs[f"cf_{key}"] = ", ".join(_label(v) for v in value if v not in (None, ""))
            else:
                attrs[f"cf_{key}"] = _label(value) if isinstance(value, dict) else str(value)
    if netbox_url and d.get("id") is not None:
        attrs["link"] = f"{netbox_url}/dcim/devices/{d['id']}/"
    return attrs


def _termination_device(terms: list) -> tuple[int | None, str]:
    for t in terms or []:
        obj = t.get("object") or {}
        device = obj.get("device") or {}
        if device.get("id") is not None:
            return device["id"], obj.get("name", "")
    return None, ""


def build_site(export: dict) -> Site:
    from . import intake, ot

    export = intake.prepare(export)
    site = export.get("site") or {}
    locations = ot.Locations(export.get("locations"))
    netbox_url = (export.get("netbox_url") or "").rstrip("/")
    zones: dict[str, Zone] = {}

    def zone(slug: str | None, name: str = "") -> Zone:
        key = slug or ""
        if key not in zones:
            label = name or (slug[len(ZONE_PREFIX):].upper() if slug else "Not zoned")
            zones[key] = Zone(slug=key, name=label, band=band_for_zone(slug))
        elif name and zones[key].name == key[len(ZONE_PREFIX):].upper():
            zones[key].name = name
        return zones[key]

    devices: dict[int, Device] = {}
    for d in export.get("devices", []):
        tag_names = {t.get("slug"): t.get("name", "") for t in d.get("tags") or []}
        zones_of = ot.device_zones(d, locations)
        device = Device(
            id=d.get("id"),
            name=d.get("name") or f"device-{d.get('id')}",
            role=_get(d, "role", "slug") or _get(d, "device_role", "slug"),
            zones=zones_of,
            attrs=_device_attrs(d, netbox_url),
        )
        devices[device.id] = device
        for slug in zones_of:
            zone(slug, tag_names.get(slug, ""))
        home = zone(device.zone)
        home.devices.append(device)
        # A Purdue level set in NetBox (custom field on the device or its location) wins.
        band = ot.band_for_level(ot.normalize_level(ot._cf(d, ot.LEVEL_FIELDS)) or locations.level(d.get("location")))
        if band and home.slug:
            home.band = band

    for z in zones.values():
        z.devices.sort(key=lambda dev: dev.name)

    prefixes_by_vlan: dict[int, list[dict]] = {}
    for p in export.get("prefixes", []):
        vlan_id = _get(p, "vlan", "id", default=None)
        if vlan_id is not None:
            prefixes_by_vlan.setdefault(vlan_id, []).append(p)

    for v in sorted(export.get("vlans", []), key=lambda v: v.get("vid", 0)):
        zone_tags = [t["slug"] for t in v.get("tags") or [] if t.get("slug", "").startswith(ZONE_PREFIX)]
        role = _get(v, "role", "slug")
        prefixes = prefixes_by_vlan.get(v.get("id"), [])
        slug = ot.vlan_zone(v, prefixes) or None
        vlan = Vlan(
            vid=v.get("vid", 0),
            name=v.get("name", ""),
            zone=slug,
            prefixes=[p.get("prefix", "") for p in prefixes],
            vrf=next((_label(p.get("vrf")) for p in prefixes if p.get("vrf")), ""),
            tenant=_label(v.get("tenant")) or next((_label(p.get("tenant")) for p in prefixes if p.get("tenant")), ""),
        )
        tag_name = next((t.get("name", "") for t in v.get("tags") or [] if t.get("slug") == slug != t.get("name")), "")
        zone(slug, tag_name or (_label(v.get("role")) if role and not zone_tags else "")).vlans.append(vlan)

    links = []
    for c in export.get("cables", []):
        a_dev, a_port = _termination_device(c.get("a_terminations"))
        b_dev, b_port = _termination_device(c.get("b_terminations"))
        if a_dev not in devices or b_dev not in devices:
            continue
        cable_type = c.get("type") or ""
        links.append(Link(
            label=c.get("label") or "",
            type=cable_type,
            color=(c.get("color") or "").lstrip("#"),
            a_device=a_dev, b_device=b_dev, a_port=a_port, b_port=b_port,
            attrs={
                "cable_label": c.get("label") or "",
                "type": cable_type,
                "status": _get(c, "status", "value"),
                "color": c.get("color") or "",
                "length": _number(c.get("length")),
                "length_unit": _get(c, "length_unit", "value"),
                "a_terminations": f"{devices[a_dev].name}:{a_port}",
                "b_terminations": f"{devices[b_dev].name}:{b_port}",
            },
        ))

    return Site(
        name=site.get("name") or site.get("slug") or "Site",
        slug=site.get("slug") or "",
        netbox_url=netbox_url,
        zones=zones,
        devices=devices,
        links=links,
    )
