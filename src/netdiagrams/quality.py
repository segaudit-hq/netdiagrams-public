"""Data quality: how complete NetBox is for this site, scored, per zone, with what to fix first.

The "Plan to improve" cards say what each sheet is missing. This module adds the view
an operations team works from day to day: one score for the site, one line per check
with how many of how many are missing, the same per zone, the ten objects with the
most gaps, and the trend since the last build. It is drawn as sheet 1c, printed by
``netdiagrams doctor``, and saved next to the drawing as ``<site>.quality.json`` so
the next build can show what moved.
"""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from . import graph as graph_mod
from . import audit, hardware, drawio, gaps, intake, overview, wireless
from .drawio import FONT, MARGIN, PAGE_W, TEXT, Page
from .model import Site, _get

PAGE_ID = "quality"
PAGE_NAME = "1c · Data quality — what NetBox is missing, and the trend"
FORMAT = "netdiagrams-quality/1"

# check key -> (group, unit, what the total counts)
GROUPS = {"draw": "Needed to draw the site", "evidence": "Needed as evidence", "audit": "Needed for an audit",
          "ops": "Good to have"}
WEIGHT = {"draw": 3, "evidence": 2, "audit": 2, "ops": 1}
CHECKS = {
    "no_name": ("draw", "devices", "devices"),
    "no_zone": ("draw", "devices", "devices"),
    "no_cables": ("draw", "devices", "network devices"),
    "no_vlans": ("draw", "VLANs", "the site"),
    "no_serial": ("evidence", "devices", "devices"),
    "no_criticality": ("evidence", "devices", "devices"),
    "no_ip": ("evidence", "devices", "network devices"),
    "no_location": ("evidence", "devices", "network devices"),
    "dup_serial": ("evidence", "serials", "serial numbers"),
    "dup_ip": ("evidence", "addresses", "management IPs"),
    "dup_asset_tag": ("evidence", "asset tags", "asset tags"),
    "cable_no_label": ("evidence", "cables", "cables"),
    "cable_label_twice": ("evidence", "labels", "cable labels"),
    "trunk_no_vlans": ("evidence", "trunks", "cabled trunk ports"),
    "past_support": ("evidence", "devices", "devices with an end-of-support date"),
    "model_no_eos": ("ops", "models", "network models"),
    "bad_name": ("ops", "names", "devices"),
    "cable_no_type": ("ops", "cables", "cables"),
    "vlan_no_prefix": ("ops", "VLANs", "VLANs"),
    "prefix_no_zone": ("ops", "subnets", "subnets"),
    "ap_no_cable": ("ops", "APs", "access points"),
    "no_wireless_links": ("ops", "radios", "point-to-point radios"),
    "no_wlans": ("draw", "sites", "sites with access points"),
    "wlan_no_vlan": ("draw", "SSIDs", "SSIDs"),
    "wlan_no_manager": ("evidence", "APs", "access points"),
    "ap_no_location": ("evidence", "APs", "access points"),
    "wlink_bad_ends": ("evidence", "links", "wireless links"),
    "wgb_no_link": ("evidence", "bridges", "workgroup bridges"),
    "wlan_no_fields": ("ops", "SSIDs", "SSIDs"),
    "wlan_review_open": ("ops", "SSIDs", "SSIDs"),
    "wlan_review_psk": ("ops", "SSIDs", "SSIDs"),
    "wlan_guest_controls": ("ops", "SSIDs", "guest SSIDs"),
    "module_no_serial": ("evidence", "modules", "modules"),
    "item_no_serial": ("ops", "items", "power supplies, fans and optics"),
    "fibre_no_optic": ("ops", "ends", "fiber cable ends"),
    "template_examples": ("ops", "names", "template names on the drawing"),
    # Scored once the site records the field (see audit.Evidence.checks); until then listed, not scored.
    "no_owner": ("audit", "devices", "devices"),
    "stale_backup": ("audit", "devices", "devices that keep a configuration"),
    "stale_patch": ("audit", "devices", "devices that take patches"),
    "stale_verified": ("audit", "devices", "devices"),
    "support_ended": ("audit", "contracts", "devices with a contract end date"),
    "not_monitored": ("audit", "devices", "devices"),
    "no_log_forwarding": ("audit", "devices", "devices"),
    "no_physical_access": ("audit", "devices", "devices with a room or rack"),
    "audit_bad_values": ("ops", "values", "audit values recorded"),
}
# Per-device fields a zone's completeness and the "fix first" list count.
DEVICE_FIELDS = (("no_zone", "zone"), ("no_serial", "serial"), ("no_ip", "mgmt IP"), ("no_location", "room/rack"),
                 ("no_cables", "cables"), ("bad_name", "name"))
GREEN, AMBER, RED, SLATE = "#059669", "#D97706", "#DC2626", "#64748B"


@dataclass
class Check:
    key: str
    what: str
    group: str
    missing: int
    total: int
    where: str
    worksheet: str
    names: list[str] = field(default_factory=list)

    @property
    def complete(self) -> float:
        """0..1; a check with nothing to count is complete."""
        if self.total <= 0:
            return 1.0
        return max(0.0, 1.0 - self.missing / self.total)


@dataclass
class ZoneRow:
    zone: str
    devices: int
    complete: int                       # devices with none of DEVICE_FIELDS missing
    missing: dict = field(default_factory=dict)  # field -> count


@dataclass
class Scorecard:
    site: str
    data_date: str
    revision: str
    score: int
    checks: list[Check]
    zones: list[ZoneRow]
    worst: list[tuple[str, list[str], str]]  # (device, missing fields, NetBox link)
    counts: dict = field(default_factory=dict)  # devices, cables, vlans, prefixes

    def check(self, key: str) -> Check | None:
        return next((c for c in self.checks if c.key == key), None)

    def to_json(self) -> dict:
        return {"format": FORMAT, "site": self.site, "data_date": self.data_date, "revision": self.revision,
                "score": self.score, "counts": self.counts,
                "checks": {c.key: {"missing": c.missing, "total": c.total} for c in self.checks},
                "zones": {z.zone: {"devices": z.devices, "complete": z.complete, "missing": z.missing}
                          for z in self.zones}}


def _totals(export: dict, endpoint_roles: set[str]) -> dict[str, int]:
    devices = [d for d in export.get("devices", []) if d.get("name")]
    infra = [d for d in devices if _get(d, "role", "slug") not in endpoint_roles]
    cables = export.get("cables", [])
    infra_names = {d["name"] for d in infra}
    cabled = set()
    for c in cables:
        for t in (c.get("a_terminations") or []) + (c.get("b_terminations") or []):
            obj = t.get("object") or {}
            if (obj.get("device") or {}).get("name"):
                cabled.add((obj["device"]["name"], obj.get("name")))
    trunks = sum(1 for i in export.get("interfaces", []) if _get(i, "mode", "value") == "tagged"
                 and _get(i, "device", "name") in infra_names and (_get(i, "device", "name"), i.get("name")) in cabled)
    distinct = lambda key: len({key(d) for d in devices if key(d)})
    wx = wireless.Index(export, endpoint_roles)
    aps = len(wx.aps)
    wlans = export.get("wireless_lans") or []
    eos = sum(1 for d in devices if (d.get("custom_fields") or {}).get("end_of_support"))
    hw = hardware.Hardware(export).counts()
    evidence = audit.Evidence(export, intake.intake(export).settings, endpoint_roles).checks("")
    return {**{key: total for key, (_, total) in evidence.items()},
        "no_name": len(export.get("devices", [])), "no_zone": len(devices), "no_cables": len(infra),
        "no_vlans": 1, "no_serial": len(devices), "no_criticality": len(devices), "no_ip": len(infra), "no_location": len(infra),
        "dup_serial": distinct(lambda d: d.get("serial")),
        "dup_ip": distinct(lambda d: _get(d, "primary_ip4", "address")),
        "dup_asset_tag": distinct(lambda d: d.get("asset_tag")),
        "cable_no_label": len(cables), "cable_label_twice": len({c.get("label") for c in cables if c.get("label")}),
        "trunk_no_vlans": trunks, "past_support": eos, "model_no_eos": len({_get(d, "device_type", "model") for d in infra
                                                            if _get(d, "device_type", "model")}), "bad_name": len(devices), "cable_no_type": len(cables),
        "vlan_no_prefix": len(export.get("vlans", [])), "prefix_no_zone": len(export.get("prefixes", [])),
        "ap_no_cable": sum(1 for d in devices if _get(d, "role", "slug") == "access-point" and not wx.is_radio_fed(d["name"])),
        "no_wireless_links": sum(1 for d in devices if _get(d, "role", "slug") == "ptp-radio"),
        "no_wlans": 1 if aps else 0, "wlan_no_vlan": len(wlans), "wlan_no_fields": len(wlans),
        "wlan_no_manager": aps if not wx.mode else 0, "ap_no_location": aps,
        "wlink_bad_ends": len(export.get("wireless_links") or []), "wgb_no_link": len(wx.wgbs),
        "wlan_review_open": len(wlans), "wlan_review_psk": len(wlans),
        "wlan_guest_controls": len(wlans), "template_examples": 0,
        "module_no_serial": hw["modules"], "item_no_serial": hw["items"],
        "fibre_no_optic": hardware.fibre_ends(cables),
    }


def assess(export: dict, found: dict[str, gaps.Gap], site: Site, endpoint_roles: set[str],
           data_date: str = "", revision: str = "") -> Scorecard:
    """Score the export from the gaps already found."""
    totals = _totals(export, endpoint_roles)
    checks = []
    for key, (group, unit, _) in CHECKS.items():
        gap = found.get(key)
        if gap is None:
            continue
        missing = (1 if gap.always else 0) if key == "no_vlans" else len(gap.names)
        total = totals.get(key, 0)   # template leftovers are listed (total 0), not weighted: doctor sees no drawing
        checks.append(Check(key, gap.what, group, missing, total, gap.where, gap.worksheet, list(gap.names)))
    weight = sum(WEIGHT[c.group] for c in checks if c.total > 0)
    score = round(100 * sum(WEIGHT[c.group] * c.complete for c in checks if c.total > 0) / weight) if weight else 100
    if score == 100 and any(c.missing for c in checks if c.total > 0):
        score = 99   # rounding must not hide a gap: 100 means nothing scored is missing

    flagged = {key: set(found[key].names) if key in found else set() for key, _ in DEVICE_FIELDS}
    rows = []
    for zone in sorted(site.zones.values(), key=lambda z: (z.band != drawio.bands()[0], z.slug)):
        if not zone.devices:
            continue
        missing: dict[str, int] = {}
        complete = 0
        for d in zone.devices:
            gone = [label for key, label in DEVICE_FIELDS if d.name in flagged[key]]
            for label in gone:
                missing[label] = missing.get(label, 0) + 1
            complete += not gone
        rows.append(ZoneRow(overview.zone_title(zone), len(zone.devices), complete, missing))

    worst = []
    for d in site.devices.values():
        gone = [label for key, label in DEVICE_FIELDS if d.name in flagged[key]]
        if gone:
            worst.append((d.name, gone, d.attrs.get("link", "")))
    worst.sort(key=lambda w: (-len(w[1]), w[0]))
    counts = {"devices": len(site.devices), "cables": len(export.get("cables", [])),
              "vlans": len(export.get("vlans", [])), "prefixes": len(export.get("prefixes", []))}
    return Scorecard(site.name, data_date, revision, score, checks, rows, worst[:10], counts)


def delta(card: Scorecard, previous: dict | None, key: str | None = None) -> int | None:
    """Change since the previous build's quality.json: the score, or one check's missing count."""
    if not isinstance(previous, dict) or previous.get("format") != FORMAT:
        return None
    try:  # a hand-edited or damaged quality.json gives no trend rather than a crash
        if key is None:
            return card.score - int(previous.get("score", 0))
        before = (previous.get("checks") or {}).get(key)
        check = card.check(key)
        if not isinstance(before, dict) or check is None:
            return None
        return check.missing - int(before.get("missing", 0))
    except (AttributeError, TypeError, ValueError):
        return None


def lines(card: Scorecard, previous: dict | None = None) -> list[str]:
    """The scorecard as text, for doctor and the build summary."""
    change = delta(card, previous)
    head = f"Data quality: {card.score}/100"
    if change is not None:
        head += f" ({'+' if change >= 0 else ''}{change} since Rev {previous.get('revision', '?')})"
    out = [head]
    for group, title in GROUPS.items():
        rows = [c for c in card.checks if c.group == group and (c.total > 0 or c.missing)]
        if not rows:
            continue
        out.append(f"  {title}")
        for c in rows:
            moved = delta(card, previous, c.key)
            trend = "" if not moved else f"  ({'+' if moved > 0 else ''}{moved})"
            state = "ok" if not c.missing else f"{c.missing} of {c.total} missing" if c.total else f"{c.missing} listed"
            out.append(f"    {c.what:<44} {state}{trend}")
    if card.worst:
        out.append("  Fix first: " + "; ".join(f"{n} ({', '.join(f)})" for n, f, _ in card.worst[:5]))
    return out


# ----------------------------------------------------------------------- sheet
TILE = ("rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;shadow=1;"
        "align=left;verticalAlign=top;spacing=12;whiteSpace=wrap;html=1;overflow=hidden;" + FONT)
CARD = ("rounded=1;absoluteArcSize=1;arcSize=20;fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;shadow=1;"
        "html=1;" + FONT)
HEAD = ("text;html=1;whiteSpace=wrap;align=left;verticalAlign=middle;spacingLeft=8;fontSize=9;fontStyle=1;"
        "fontColor=#64748B;fillColor=#F8FAFC;strokeColor=none;" + FONT)
CELL = ("text;html=1;whiteSpace=wrap;align=left;verticalAlign=middle;spacingLeft=8;fontSize=10;"
        "fontColor=#0F172A;fillColor=none;strokeColor=none;" + FONT)
RULE = "line;strokeColor=#EEF2F7;strokeWidth=1;html=1;"


def _color(fraction: float, missing: int = 0) -> str:
    """Green only when nothing is missing: 3 gaps in 200 rows still want fixing."""
    return GREEN if fraction >= 0.95 and not missing else AMBER if fraction >= 0.7 else RED


def pct(fraction: float) -> int:
    """A share as a whole percent that never reads 100 while something is missing."""
    shown = round(fraction * 100)
    return 99 if shown == 100 and fraction < 1 else shown


def _bar(fraction: float, width: int = 110, missing: int = 0) -> str:
    fill = max(2, round(width * fraction))
    color = _color(fraction, missing)
    return (f'<div style="display:inline-block;width:{width}px;height:7px;background:#E2E8F0;border-radius:4px">'
            f'<div style="width:{fill}px;height:7px;background:{color};border-radius:4px"></div></div>'
            f' <span style="color:{color};font-weight:bold">{pct(fraction)}%</span>')


def _trend_text(moved: int | None, fewer_is_better: bool = True) -> str:
    if moved is None or moved == 0:  # None: a first build, or a check the last build didn't have
        return '<span style="color:#94A3B8">·</span>' if moved == 0 else '<span style="color:#94A3B8">new</span>'
    good = (moved < 0) == fewer_is_better
    arrow = "▼" if moved < 0 else "▲"
    return f'<span style="color:{GREEN if good else RED}">{arrow} {abs(moved)}</span>'


def _table(p: Page, layer: str, x: float, y: float, columns: list[tuple[str, int]], rows: list[list[str]],
           row_h: int = 22) -> float:
    """A light table drawn as boxes; returns the y under it. A row grows when a cell's text wraps."""
    cx = x
    for title, w in columns:
        p.box(layer, cx, y, w, 20, html.escape(title), HEAD)
        cx += w
    y += 20
    for row in rows:
        cx = x
        need = graph_mod.row_height([(value, w - 4) for (_, w), value in zip(columns, row)], size=10, base=row_h)
        for (title, w), value in zip(columns, row):
            p.box(layer, cx, y, w, need, value, CELL)
            cx += w
        y += need
        p.box(layer, x, y - 1, sum(w for _, w in columns), 1, "", RULE)
    return y


def page(card: Scorecard, previous: dict | None = None) -> ET.Element:
    """Sheet 1c as a <diagram>; the caller adds the title block."""
    p = Page(PAGE_ID, PAGE_NAME)
    l_title, l_score, l_checks, l_zones = (p.layer("Titles"), p.layer("Score"), p.layer("Checks"),
                                           p.layer("By zone · fix first"))
    when = f"NetBox as of {card.data_date}" if card.data_date else "NetBox"
    drawio._title(p, l_title, f"{card.site} — Data quality",
                  f"What {when} is missing for this drawing, scored, per zone, and what to fix first. "
                  f"Rev {card.revision}. Scores: needed to draw ×3, evidence and audit ×2, good to have ×1.")

    # Tiles: overall, then one per group, then devices complete.
    moved = delta(card, previous)
    tiles = [("Overall", card.score / 100, moved,
              "points since last build" if moved is not None else "first build: the next one shows the trend", 0)]
    for group, title in GROUPS.items():
        rows = [c for c in card.checks if c.group == group and c.total > 0]
        if rows:
            fraction = sum(c.complete for c in rows) / len(rows)
            missing = sum(c.missing for c in rows)
            tiles.append((title, fraction, None, f"{missing:,} missing across {len(rows)} checks", missing))
    complete = sum(z.complete for z in card.zones)
    total = sum(z.devices for z in card.zones)
    tiles.append(("Devices complete", complete / total if total else 1.0, None,
                  f"{complete:,} of {total:,} with zone, serial, IP, room, cables and a standard name",
                  total - complete))
    tile_w = (PAGE_W - 2 * MARGIN - 16 * (len(tiles) - 1)) / len(tiles)
    y = 100
    for i, (title, fraction, moved, note, missing) in enumerate(tiles):
        x = MARGIN + i * (tile_w + 16)
        color = _color(fraction, missing)
        trend = ""
        if moved is not None:
            trend = (f' <span style="font-size:14px;color:{GREEN if moved >= 0 else RED}">'
                     f'{"▲" if moved > 0 else "▼" if moved < 0 else "="} {abs(moved)}</span>')
        p.box(l_score, x, y, tile_w, 92,
              f'<span style="font-size:11px;color:#64748B">{html.escape(title)}</span><br>'
              f'<span style="font-size:30px;font-weight:bold;color:{color}">{pct(fraction)}'
              f'<span style="font-size:14px;color:#94A3B8">{"/100" if i == 0 else "%"}</span></span>{trend}<br>'
              f'<span style="font-size:9px;color:#64748B">{html.escape(note)}</span>',
              TILE)
    y += 92 + 24

    # Left: every check.
    left_w, right_x = 1060, MARGIN + 1060 + 24
    right_w = PAGE_W - MARGIN - right_x
    p.box(l_checks, MARGIN, y, left_w, 22, "<b>Checks</b> · missing of total · complete · since last build · "
          "where it goes in NetBox · worksheet", TEXT + "fontSize=11;fontColor=#0F172A;")
    columns = [("WHAT", 250), ("MISSING", 70), ("OF", 60), ("COMPLETE", 170), ("TREND", 60),
               ("NETBOX", 250), ("WORKSHEET", 200)]
    rows = []
    for group, title in GROUPS.items():
        checks = [c for c in card.checks if c.group == group]
        if not checks:
            continue
        rows.append([f'<b style="color:#4338CA">{html.escape(title)}</b>', "", "", "", "", "", ""])
        for c in checks:
            if c.total <= 0:
                if c.missing:   # listed, not scored (template words left on the drawing)
                    rows.append([html.escape(c.what), f'<b style="color:{AMBER}">{c.missing:,}</b>', "—",
                                 '<span style="color:#94A3B8">listed, not scored</span>', "",
                                 html.escape(c.where), html.escape(c.worksheet)])
                else:
                    rows.append([html.escape(c.what), "—", "0", '<span style="color:#94A3B8">nothing to check</span>',
                                 "", html.escape(c.where), html.escape(c.worksheet)])
                continue
            rows.append([html.escape(c.what),
                         f'<b style="color:{_color(c.complete, c.missing) if c.missing else SLATE}">{c.missing:,}</b>',
                         f"{c.total:,}", _bar(c.complete, missing=c.missing), _trend_text(delta(card, previous, c.key)),
                         html.escape(c.where), html.escape(c.worksheet)])
    y_left = _table(p, l_checks, MARGIN, y + 28, columns, rows)

    # Right: per zone, then fix first.
    yr = y
    p.box(l_zones, right_x, yr, right_w, 22, "<b>By zone</b> · devices complete · what is missing",
          TEXT + "fontSize=11;fontColor=#0F172A;")
    zcols = [("ZONE", 150), ("DEVICES", 70), ("COMPLETE", 170), ("MISSING", right_w - 390)]
    zrows = []
    for z in card.zones:
        fraction = z.complete / z.devices if z.devices else 1.0
        gone = " · ".join(f"{label} {n}" for label, n in sorted(z.missing.items(), key=lambda kv: -kv[1]))
        zrows.append([html.escape(z.zone), f"{z.devices:,}", _bar(fraction, 90, z.devices - z.complete),
                      f'<span style="font-size:9px;color:#475569">{html.escape(gone) or "—"}</span>'])
    yr = _table(p, l_zones, right_x, yr + 28, zcols, zrows) + 24
    p.box(l_zones, right_x, yr, right_w, 22, "<b>Fix these first</b> · the devices with the most gaps",
          TEXT + "fontSize=11;fontColor=#0F172A;")
    fcols = [("DEVICE", 220), ("MISSING", right_w - 220)]
    frows = []
    for name, missing, link in card.worst:
        label = html.escape(name)
        if link:
            label = f'<a href="{html.escape(link)}">{label}</a>'
        frows.append([label, html.escape(", ".join(missing))])
    if not frows:
        frows.append(['<span style="color:#059669">Nothing: every device has its zone, serial, IP, room, '
                      'cables and a standard name.</span>', ""])
    yr = _table(p, l_zones, right_x, yr + 28, fcols, frows)

    y = max(y_left, yr) + 24
    p.box(l_title, MARGIN, y, PAGE_W - 2 * MARGIN, 40,
          "<b>How to read this sheet.</b> Each check counts objects NetBox is missing something for, out of the "
          "objects it applies to. The site score weights the checks: needed to draw ×3, evidence and audit ×2, good "
          "to have ×1; an audit check counts once the site records its field (until then it is listed, not scored). "
          "<i>netdiagrams gaps</i> writes import files that close the gaps by id; the trend column compares with the "
          "quality.json the previous build left next to the drawing.",
          TEXT + "fontSize=10;fontColor=#475569;")
    p.height = y + 40 + 24
    return p.element()
