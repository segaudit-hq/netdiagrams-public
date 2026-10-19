"""Tidy a NetBox export before it is drawn, so the drawing states only true facts.

First the site's settings (see ``settings.py``) translate its own names into the
template's: mapped device roles take the template's role slug (the NetBox slug
is kept as ``netbox_role``), and the custom fields named for zone, Purdue level,
SL-T, software version, gateway and end of support are copied to the names the
rest of NetDiagrams reads (``security_zone``, ``purdue_level``,
``security_level_target``, ``sw_version``, ``gateway``, ``end_of_support``).

NetBox holds things a drawing must not show as running network: spares on the
shelf, devices being taken out, patch panels in the middle of a link, objects
nobody named. ``prepare`` returns a copy of the export where:

- devices in ``inventory`` or ``decommissioning`` are taken off the drawing and
  kept for the registers, with their status; ``planned`` devices stay and are
  drawn dashed, ``offline`` and ``failed`` ones stay with an amber marker;
- a cable that ends on a patch panel is replaced by the link it really makes,
  switch port to far port, using the cable path NetBox computes
  (``connected_endpoints``), with the panel ports kept as ``x_patch_a/b``;
  patch panels never take a device slot;
- unnamed devices get a name (``‹role›-‹id›``) and are reported;
- a VLAN from a region or global group is dropped when the site has its own
  VLAN with the same number;
- wireless LANs are kept when they belong to the site (scoped to it or one of
  its locations, or on one of its VLANs); the others are reported;
- a device takes the facts of its model (end of sale, end of support, the
  vendor's notice) from its NetBox device type, unless the device has its own;
- the date the data is true for is worked out (the export time, else the
  newest change in the export).

What was done is kept in ``export["_intake"]`` for the drift report.
"""

from __future__ import annotations

import datetime as dt
import copy
from dataclasses import dataclass, field

from . import settings as config
from .model import _get

PANEL_ROLES = {"patch-panel", "patch-panels", "fiber-panel", "fibre-panel", "panel", "odf", "patch-field"}
PASS_THROUGH = {"dcim.frontport", "dcim.rearport"}
KEY = "_intake"


@dataclass
class Intake:
    register_only: list = field(default_factory=list)     # NetBox device dicts kept off the drawing
    planned: list = field(default_factory=list)
    flagged: list = field(default_factory=list)           # (name, status)
    panels: list = field(default_factory=list)
    traced: list = field(default_factory=list)            # "A:port ⇄ B:port via PANEL:port"
    unnamed: list = field(default_factory=list)
    duplicate_labels: dict = field(default_factory=dict)  # label -> how many cables carry it
    shadowed_vlans: list = field(default_factory=list)    # "VID name (group)" dropped for the site's own
    left_out_wlans: list = field(default_factory=list)    # "SSID (VLAN VID)" not this site's
    data_date: str = ""
    settings: dict = field(default_factory=lambda: copy.deepcopy(config.DEFAULTS))
    sources: list = field(default_factory=lambda: ["defaults"])
    roles_mapped: dict = field(default_factory=dict)  # NetBox role slug -> template role
    from_type: dict = field(default_factory=dict)     # model field -> devices that took it from their type


def status(d: dict) -> str:
    return (_get(d, "status", "value") or (d.get("status") if isinstance(d.get("status"), str) else "")
            or "active").lower()


# Canonical custom field name -> the setting that names the site's own field.
CANONICAL = {"security_zone": "zone_field", "purdue_level": "level_field", "security_level_target": "sl_field",
             "sw_version": "sw_field", "gateway": "gateway_field", "end_of_support": "end_of_support_field",
             "criticality": "criticality_field"}
# Facts true of every device of a model: kept once on the NetBox device type; a device's own value wins.
MODEL_FIELDS = ("end_of_sale", "end_of_support", "eol_notice")


def prepare(export: dict, file_settings: dict | None = None, file_name: str = "") -> dict:
    """A tidied copy of ``export`` (or ``export`` itself when already tidied)."""
    if KEY in export:
        return export
    export = copy.deepcopy(export)
    cfg, sources = config.resolve(export, file_settings, file_name)
    info = Intake(settings=cfg, sources=sources)
    _apply_fields(export, cfg)
    _map_roles(export, cfg, info)
    _name_unnamed(export, info)
    _inherit_from_type(export, info)
    _split_by_status(export, info)
    _trace_patch_panels(export, info)
    _drop_shadowed_vlans(export, info)
    _site_wlans(export, info)
    _site_wireless_links(export)
    labels: dict[str, int] = {}
    for c in export.get("cables", []):
        if c.get("label"):
            labels[c["label"]] = labels.get(c["label"], 0) + 1
    info.duplicate_labels = {k: n for k, n in sorted(labels.items()) if n > 1}
    info.data_date = data_date(export)
    export[KEY] = info
    return export


def intake(export: dict) -> Intake:
    return export.get(KEY) or Intake()


# ------------------------------------------------------------------- devices
def _terms(c: dict) -> list[dict]:
    return (c.get("a_terminations") or []) + (c.get("b_terminations") or [])


def _name_unnamed(export: dict, info: Intake) -> None:
    named = {}
    for d in export.get("devices", []):
        if not d.get("name") and d.get("id") is not None:
            d["name"] = f"{_get(d, 'role', 'slug') or 'device'}-{d['id']}"
            named[d["id"]] = d["name"]
            info.unnamed.append(d["name"])
    if not named:
        return
    for c in export.get("cables", []):
        for t in _terms(c):
            dev = (t.get("object") or {}).get("device") or {}
            if dev.get("id") in named:
                dev["name"] = named[dev["id"]]
    for i in export.get("interfaces", []):
        dev = i.get("device") or {}
        if dev.get("id") in named:
            dev["name"] = named[dev["id"]]


def _apply_fields(export: dict, cfg: dict) -> None:
    """Copy each fact from the field the site keeps it in to the name NetDiagrams reads."""
    for key in ("devices", "device_types", "locations", "vlans", "prefixes"):
        for obj in export.get(key) or []:
            fields = obj.get("custom_fields")
            if not isinstance(fields, dict):
                continue
            for canonical, setting in CANONICAL.items():
                names = cfg.get(setting) or []
                value = next((fields[n] for n in names if fields.get(n) not in (None, "", [], {})), None)
                if value is None:
                    fields.pop(canonical, None)  # a field the site doesn't use for this (e.g. a fire 'zone')
                else:
                    fields[canonical] = value


def _type_key(t: dict) -> tuple:
    return ((_get(t, "manufacturer", "slug") or _get(t, "manufacturer", "name") or "").lower(),
            (t.get("model") or "").lower())


def type_of(device: dict, types: list[dict]) -> dict | None:
    """The device's NetBox device type from the export: by id, else by manufacturer and model."""
    ref = device.get("device_type") or {}
    if not isinstance(ref, dict):
        return None
    by_id = {t["id"]: t for t in types if t.get("id") is not None}
    if ref.get("id") in by_id:
        return by_id[ref["id"]]
    return next((t for t in types if _type_key(t) == _type_key(ref) and _type_key(ref)[1]), None)


def _inherit_from_type(export: dict, info: Intake) -> None:
    """Give each device its model's end of sale, end of support and notice, unless it has its own."""
    types = [t for t in export.get("device_types") or [] if isinstance(t, dict)]
    if not types:
        return
    for d in export.get("devices", []):
        t = type_of(d, types)
        own = d.get("custom_fields") if isinstance(d.get("custom_fields"), dict) else {}
        theirs = (t or {}).get("custom_fields") or {}
        for name in MODEL_FIELDS:
            if own.get(name) in (None, "") and theirs.get(name) not in (None, ""):
                own[name] = theirs[name]
                info.from_type.setdefault(name, []).append(d.get("name") or "")
        d["custom_fields"] = own


def _map_roles(export: dict, cfg: dict, info: Intake) -> None:
    lookup = config.role_lookup(cfg)
    if not lookup:
        return
    for d in export.get("devices", []):
        role = d.get("role") or d.get("device_role") or {}
        if not isinstance(role, dict):
            continue
        slug, name = (role.get("slug") or "").lower(), (role.get("name") or "").lower()
        target = lookup.get(slug) or lookup.get(name)
        if target and target != role.get("slug"):
            info.roles_mapped[role.get("slug") or name] = target
            d["role"] = {**role, "slug": target, "netbox_slug": role.get("slug") or ""}


def _split_by_status(export: dict, info: Intake) -> None:
    states = info.settings.get("status") or {}
    dashed, flagged = set(states.get("dashed") or ()), set(states.get("flagged") or ())
    register_only, draw = set(states.get("register_only") or ()), set(states.get("draw") or ())
    keep, hidden = [], set()
    for d in export.get("devices", []):
        s = status(d)
        if s in register_only or (draw and s not in draw | dashed | flagged):
            info.register_only.append(d)
            hidden.add(d.get("id"))
            continue
        if s in dashed:
            info.planned.append(d["name"])
        elif s in flagged:
            info.flagged.append((d["name"], s))
        keep.append(d)
    if hidden:
        export["devices"] = keep
        _drop_cables_to(export, hidden)


def _drop_cables_to(export: dict, device_ids: set) -> None:
    export["cables"] = [c for c in export.get("cables", []) if not any(
        ((t.get("object") or {}).get("device") or {}).get("id") in device_ids for t in _terms(c))]


# --------------------------------------------------------------- patch panels
def _end(obj: dict) -> tuple[str, str]:
    return _get(obj, "device", "name"), obj.get("name", "")


def _trace_patch_panels(export: dict, info: Intake) -> None:
    """Replace switch ↔ panel cables with the end-to-end link NetBox traced through the panels."""
    devices = export.get("devices", [])
    through: dict = {}  # device id -> only ever seen on front/rear ports
    for c in export.get("cables", []):
        for t in _terms(c):
            dev_id = _get(t, "object", "device", "id", default=None)
            if dev_id is not None:
                passive = t.get("object_type") in PASS_THROUGH
                through[dev_id] = through.get(dev_id, True) and passive
    panels = {d.get("id") for d in devices
              if _get(d, "role", "slug") in PANEL_ROLES or through.get(d.get("id"))}
    if not panels:
        return
    by_id = {d.get("id"): d for d in devices}
    info.panels = sorted(by_id[i]["name"] for i in panels if i in by_id)
    ids = {d.get("name"): d.get("id") for d in devices if d.get("id") not in panels}
    interfaces = {_end(i): i for i in export.get("interfaces", [])}
    cables = {c.get("id"): c for c in export.get("cables", [])}
    patch = lambda iface: ", ".join(f"{_get(p, 'device', 'name')}:{p.get('name', '')}"
                                    for p in iface.get("link_peers") or [])
    term = lambda end: [{"object_type": "dcim.interface", "object": {
        "name": end[1], "device": {"id": ids.get(end[0]), "name": end[0]}}}]
    links, replaced = {}, set()
    for i in export.get("interfaces", []):
        peers = i.get("link_peers") or []
        if i.get("link_peers_type") not in PASS_THROUGH and not any(
                _get(p, "device", "id", default=None) in panels for p in peers):
            continue
        if i.get("connected_endpoints_type") not in (None, "dcim.interface"):
            continue
        a = _end(i)
        for e in i.get("connected_endpoints") or []:
            b = _end(e)
            if a[0] not in ids or b[0] not in ids:
                continue
            key = tuple(sorted((a, b)))
            if key in links:
                continue
            first, second = (i, interfaces.get(b, {})) if key[0] == a else (interfaces.get(b, {}), i)
            segments = [x for x in (_get(first, "cable", "id", default=None),
                                    _get(second, "cable", "id", default=None)) if x is not None]
            replaced.update(segments)
            cable = next((cables[x] for x in segments if x in cables), {})
            links[key] = {
                **{k: v for k, v in cable.items() if k not in ("a_terminations", "b_terminations")},
                "label": cable.get("label") or _get(first, "cable", "label") or _get(second, "cable", "label") or "",
                "a_terminations": term(key[0]),
                "b_terminations": term(key[1]),
                "x_patch_a": patch(first),
                "x_patch_b": patch(second),
                "netdiagrams_segments": segments,
            }
            via = " · ".join(x for x in (links[key]["x_patch_a"], links[key]["x_patch_b"]) if x)
            info.traced.append(f"{key[0][0]}:{key[0][1]} ⇄ {key[1][0]}:{key[1][1]}" + (f" via {via}" if via else ""))
    # Cables between panels (trunks) and the traced switch-to-panel segments give way to the links.
    # Each link takes the place of its first segment, so cable order (and register order) holds.
    at = {}
    for link in links.values():
        for seg in link["netdiagrams_segments"]:
            at.setdefault(seg, []).append(link)
    kept, placed = [], set()
    for c in export.get("cables", []):
        ends = [_get(t, "object", "device", "id", default=None) for t in _terms(c)]
        for link in at.get(c.get("id"), []):
            if id(link) not in placed:
                placed.add(id(link))
                kept.append(link)
        if c.get("id") in replaced or (ends and all(e in panels for e in ends)):
            continue
        kept.append(c)
    export["cables"] = kept + [link for link in links.values() if id(link) not in placed]
    export["devices"] = [d for d in devices if d.get("id") not in panels]
    export["patch_panels"] = [by_id[i] for i in panels if i in by_id]


# ---------------------------------------------------------------- VLANs, WLANs
def _vlan_rank(v: dict) -> int:
    """0 for a VLAN assigned to the site itself, 1 for one from a group or the global table."""
    return 0 if v.get("site") else 1


def _drop_shadowed_vlans(export: dict, info: Intake) -> None:
    best: dict = {}
    for v in export.get("vlans", []):
        best[v.get("vid")] = min(best.get(v.get("vid"), 9), _vlan_rank(v))
    kept = []
    for v in export.get("vlans", []):
        if _vlan_rank(v) > best[v.get("vid")]:
            group = _get(v, "group", "name")
            info.shadowed_vlans.append(f"{v.get('vid')} {v.get('name', '')}" + (f" ({group})" if group else ""))
            continue
        kept.append(v)
    export["vlans"] = kept


def _site_wlans(export: dict, info: Intake) -> None:
    """Wireless LANs scoped to the site or its locations, or on one of its VLANs, or global.

    A scope says whose the SSID is even when its VLAN lives in a VLAN group rather
    than on the site, so the scope is read first. What is left out is reported:
    an SSID imported before its VLAN must not vanish without a word.
    """
    wlans = export.get("wireless_lans") or []
    if not wlans:
        return
    site_id = (export.get("site") or {}).get("id")
    vlans = {v.get("id") for v in export.get("vlans", [])}
    locations = {loc.get("id") for loc in export.get("locations") or []}
    # A corporate SSID scoped to the site's region or site group is this site's too (NetBox 4.2+).
    scopes = {("dcim.site", site_id)} | {("dcim.location", i) for i in locations} | \
        {("dcim.region", r.get("id")) for r in export.get("regions") or []} | \
        {("dcim.sitegroup", (export.get("site_group") or {}).get("id"))}

    def ours(w):
        vlan = _get(w, "vlan", "id", default=None)
        scope_type, scope_id = w.get("scope_type"), w.get("scope_id")
        if scope_id is not None and (scope_type, scope_id) in scopes:
            return True
        if vlan is not None:
            return vlan in vlans
        return not scope_type
    kept = [w for w in wlans if ours(w)]
    info.left_out_wlans = [f"{w.get('ssid') or w.get('id')} (VLAN {_get(w, 'vlan', 'vid', default='?')})"
                           for w in wlans if w not in kept]
    export["wireless_lans"] = kept


def _site_wireless_links(export: dict) -> None:
    """Wireless links with an end on one of this site's devices (the endpoint has no reliable site filter)."""
    links = export.get("wireless_links") or []
    if not links:
        return
    names = {d.get("name") for d in export.get("devices", []) if d.get("name")}
    ids = {d.get("id") for d in export.get("devices", []) if d.get("id") is not None}

    def ours(w):
        for side in ("interface_a", "interface_b"):
            dev = (w.get(side) or {}).get("device") or {}
            if dev.get("name") in names or dev.get("id") in ids:
                return True
        return False
    export["wireless_links"] = [w for w in links if ours(w)]


# ------------------------------------------------------------------- the date
def data_date(export: dict) -> str:
    """The day the export's data is true for: when it was exported, else its newest change."""
    if export.get("exported_at"):
        stamp = str(export["exported_at"])
        try:  # the day where the build runs: a UTC stamp of 00:30 is still yesterday evening in New York
            return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().date().isoformat()
        except ValueError:
            return stamp[:10]
    newest = ""
    for key, objs in export.items():
        if isinstance(objs, list):
            for o in objs:
                stamp = (o.get("last_updated") or "") if isinstance(o, dict) else ""
                newest = max(newest, str(stamp)[:10])
    return newest
