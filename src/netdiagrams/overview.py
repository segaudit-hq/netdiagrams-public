"""A one-page summary of a site of any size: one card per zone with device counts.

Detail pages stop being readable past about 50 to 100 shapes, so a big site
starts here. Each zone card counts its network gear and end devices by role
and links to that list in NetBox; lines between cards are the cables that
cross zones, with their count. A band with many zones (40 production cells)
draws one line for the whole band instead of one per zone.
"""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from collections import Counter

from . import drawio, graph, profiles
from .drawio import BAND_COLORS, FONT, GAP, MARGIN, PAGE_W, TEXT, Page
from .model import Site, Zone
from .netbox_setup import ROLE_NAMES

CARD_W, CARD_W_COMPACT = 300, 220
CARD_H, CARD_H_COMPACT = 76, 64
COMPACT_ZONES = 12        # a band with more zones than this gets small cards
BAND_LINE_ZONES = 8       # ... and one line for the whole band past this
ID_LINK_MAX = 40
NETWORK_ORDER = ["firewall", "router", "sdwan-edge", "core-switch", "distribution-switch", "idmz-switch",
                 "access-switch", "industrial-switch", "sis-switch", "oob-switch", "wireless-controller",
                 "ptp-radio"]
CONDUIT_STYLE = ("edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=16;endArrow=none;startArrow=none;"
                 "strokeColor=#94A3B8;strokeWidth=1.5;fontSize=9;fontColor=#475569;"
                 "labelBackgroundColor=#FFFFFF;html=1;" + FONT)


def role_name(slug: str) -> str:
    return profiles.role_name(slug, ROLE_NAMES)


def _is_network(role: str) -> bool:
    from .sync import endpoint_roles
    return role not in endpoint_roles()


def _counts(zone: Zone, compact: bool) -> str:
    roles = Counter(d.role for d in zone.devices)
    rank = lambda r: (NETWORK_ORDER.index(r) if r in NETWORK_ORDER else len(NETWORK_ORDER), r)
    net = [r for r in sorted(roles, key=rank) if _is_network(r)]
    end = sorted((r for r in roles if not _is_network(r)), key=lambda r: (-roles[r], r))
    fmt = lambda rs: " · ".join(f"{html.escape(role_name(r))} ×{roles[r]}" for r in rs)
    if compact:
        return fmt(net + end)
    lines = []
    if net:
        lines.append(f'<span style="color:#64748B">Network</span> {fmt(net)}')
    if end:
        lines.append(f'<span style="color:#64748B">End devices</span> {fmt(end)}')
    return "<br>".join(lines)


def _zone_link(site: Site, zone: Zone) -> str:
    if not site.netbox_url or not zone.devices:
        return ""
    ids = [d.id for d in zone.devices]
    if len(ids) <= ID_LINK_MAX and all(isinstance(i, int) for i in ids):
        return f"{site.netbox_url}/dcim/devices/?" + "&".join(f"id={i}" for i in ids)
    if zone.slug and any(zone.slug in d.attrs.get("tags", "") for d in zone.devices):
        return f"{site.netbox_url}/dcim/devices/?site={site.slug}&tag={zone.slug}"
    return f"{site.netbox_url}/dcim/devices/?site={site.slug}"


def zone_title(zone: Zone) -> str:
    if not zone.slug:
        return "Not zoned in NetBox"
    if zone.name in (zone.slug, zone.slug[5:].upper()):
        return zone.slug[5:].replace("-", " ").upper()
    return zone.name


def _is_gate(zone: Zone) -> bool:
    """A zone of nothing but firewalls is the gate between zones, drawn as a strip."""
    return bool(zone.devices) and all(d.role == "firewall" for d in zone.devices)


def _card(p: Page, layer: str, site: Site, zone: Zone, x, y, w, h, label: str, style: str) -> str:
    card = p.new_id()
    obj = ET.Element("object", {"id": card, "label": label, "zone": zone.slug,
                                "devices": str(len(zone.devices)),
                                "tooltip": f"{zone_title(zone)}: {len(zone.devices)} devices"})
    link = _zone_link(site, zone)
    if link:
        obj.set("link", link)
        obj.set("linkTarget", "_blank")
    cell = ET.SubElement(obj, "mxCell", {"style": style, "vertex": "1", "parent": layer})
    ET.SubElement(cell, "mxGeometry", {"x": f"{x:g}", "y": f"{y:g}", "width": f"{w:g}", "height": f"{h:g}",
                                       "as": "geometry"})
    p.cells.append(obj)
    return card


def page(site: Site, page_id: str = "glance", name: str = "1b · Site at a glance — zones and counts from NetBox",
         sheet: str = "1b", segaudit_note: bool = False, footer: bool = True) -> ET.Element:
    """The page as a <diagram>. Without ``footer`` the caller adds its own title block."""
    p = Page(page_id, name)
    total = len(site.devices)
    zoned = [z for z in site.zones.values() if z.devices]
    drawio._title(p, p.layer("Titles"), f"{site.name} — Site at a glance",
                  f"{total:,} devices in {len(zoned)} zones, {len(site.links):,} cables. One card per zone; "
                  "click a card for its devices in NetBox. Lines are cables between zones, with their count.")
    l_bands, l_zones, l_lines = p.layer(profiles.current().band_layer), p.layer("Zones"), p.layer("Cables between zones")

    zone_of = {d.id: z.slug for z in site.zones.values() for d in z.devices}
    bands = [(band, [z for z in zones if z.devices and not _is_gate(z)]) for band, zones in site.bands()]
    bands = [(band, zones) for band, zones in bands if zones]
    band_index = {z.slug: i for i, (_, zones) in enumerate(bands) for z in zones}
    # Each gate sits under the highest band it has cables to.
    gates_after: dict[int, list[Zone]] = {}
    for gate in sorted((z for z in zoned if _is_gate(z)), key=lambda z: z.slug):
        near = {band_index[zone_of[o]] for l in site.links
                for d, o in ((l.a_device, l.b_device), (l.b_device, l.a_device))
                if zone_of.get(d) == gate.slug and zone_of.get(o) in band_index}
        gates_after.setdefault(min(near) if near else max(len(bands) - 1, 0), []).append(gate)

    inner_x = MARGIN + drawio.BAND_INNER_X
    inner_w = PAGE_W - 2 * MARGIN - drawio.BAND_INNER_X - GAP
    cards: dict[str, str] = {}          # zone slug -> card id
    geo: dict[str, tuple] = {}          # card id -> (x, y, w, h, row in its band, rows in its band)
    band_box: dict[str, str] = {}       # zone slug -> its band's box, for bands drawn with one line
    band_of_card: dict[str, int] = {}

    def draw_gates(b: int, y: int) -> int:
        for gate in gates_after.get(b, []):
            roles = Counter(d.role for d in gate.devices)
            label = (f'<b>Security gate · {html.escape(zone_title(gate))}</b> · '
                     + " · ".join(f"{html.escape(role_name(r))} ×{n}" for r, n in roles.items()))
            card = _card(p, l_zones, site, gate, inner_x, y, inner_w, 30, label,
                         "rounded=1;absoluteArcSize=1;arcSize=30;fillColor=#F1F5F9;strokeColor=#CBD5E1;"
                         "strokeWidth=1;align=left;verticalAlign=middle;spacingLeft=12;fontSize=11;"
                         "fontColor=#334155;whiteSpace=wrap;html=1;" + FONT)
            cards[gate.slug] = card
            geo[card] = (inner_x, y, inner_w, 30, 0, 1)
            band_of_card[card] = b + 0.5
            y += 30 + GAP
        return y

    y = 100
    for b, ((level, band_name, _), zones) in enumerate(bands):
        compact = len(zones) > COMPACT_ZONES
        w, h = (CARD_W_COMPACT, CARD_H_COMPACT) if compact else (CARD_W, CARD_H)
        heads = [f"{zone_title(z)} · {len(z.devices):,} devices" for z in zones]
        counts = [_counts(z, compact) for z in zones]
        # Busy zones list many roles: every card in the band grows to the tallest one's text.
        h = max([h] + [16 + 14 * graph.text_lines(t, w, 11, spacing=16, bold=True)
                       + 12 * graph.text_lines(c, w, 9, spacing=16) for t, c in zip(heads, counts)])
        per_row = max(1, (inner_w + GAP) // (w + GAP))
        rows = -(-len(zones) // per_row)
        head = 20 if compact else 0
        band_h = max(rows * (h + GAP) + GAP + head, 110)
        pill_fill, pill_text = BAND_COLORS[profiles.palette(level)][:2]
        box = p.box(l_bands, MARGIN, y, PAGE_W - 2 * MARGIN, band_h, "",
                    "rounded=1;absoluteArcSize=1;arcSize=28;fillColor=#FFFFFF;strokeColor=#E2E8F0;"
                    "strokeWidth=1;html=1;" + FONT)
        geo[box] = (MARGIN, y, PAGE_W - 2 * MARGIN, band_h, 0, 1)
        band_of_card[box] = b
        p.box(l_bands, MARGIN + 10, y + 10, 40, 22, f"<b>{html.escape(level)}</b>",
              f"rounded=1;absoluteArcSize=1;arcSize=22;fillColor={pill_fill};strokeColor=none;"
              f"fontColor={pill_text};fontSize=10;html=1;" + FONT)
        p.box(l_bands, MARGIN + 8, y + 40, 44, max(band_h - 52, 40), html.escape(band_name),
              "text;html=1;horizontal=0;fontSize=10;fontStyle=1;fontColor=#94A3B8;align=right;"
              "verticalAlign=middle;whiteSpace=wrap;" + FONT)
        if compact:
            n = sum(len(z.devices) for z in zones)
            p.box(l_bands, inner_x, y + 6, 900, 18, f"{len(zones)} zones · {n:,} devices",
                  TEXT + "fontSize=10;fontColor=#64748B;")
        for i, zone in enumerate(zones):
            fill, stroke, text = drawio._zone_colors(zone)
            zx = inner_x + (i % per_row) * (w + GAP)
            zy = y + GAP + head + (i // per_row) * (h + GAP)
            label = (f'<b style="color:{text}">{html.escape(zone_title(zone))}</b>'
                     f'<span style="color:#64748B"> · {len(zone.devices):,} devices</span><br>'
                     f'<span style="font-size:9px;color:#334155">{counts[i]}</span>')
            card = _card(p, l_zones, site, zone, zx, zy, w, h, label,
                         f"rounded=1;absoluteArcSize=1;arcSize=16;fillColor={fill};strokeColor={stroke};"
                         "strokeWidth=1;shadow=1;align=left;verticalAlign=top;spacing=8;fontSize=11;"
                         "whiteSpace=wrap;html=1;overflow=hidden;" + FONT)
            cards[zone.slug] = card
            geo[card] = (zx, zy, w, h, i // per_row, rows)
            band_of_card[card] = b
            if len(zones) > BAND_LINE_ZONES:
                band_box[zone.slug] = box
        y = draw_gates(b, y + band_h + GAP)
    if not bands:  # a site of firewalls only still shows them
        y = draw_gates(0, y)
    p.height = y

    # Cables between zones, counted per pair of cards (or band, for crowded bands).
    pairs: Counter = Counter()
    members: dict[tuple, set] = {}
    for link in site.links:
        a, b = zone_of.get(link.a_device), zone_of.get(link.b_device)
        if a is None or b is None or a == b or a not in cards or b not in cards:
            continue
        ends = [band_box[z] if z in band_box and band_box.get(o) != band_box[z] else cards[z]
                for z, o in ((a, b), (b, a))]
        if ends[0] == ends[1]:
            continue
        key = tuple(sorted(ends, key=lambda c: (band_of_card[c], geo[c][0])))
        pairs[key] += 1
        members.setdefault(key, set()).update({a, b})
    _draw_lines(p, l_lines, pairs, members, geo, band_of_card, set(band_box.values()), inner_x)

    if footer:
        drawio._footer(p, site, "Site at a glance", sheet, segaudit_note)
    return p.element()


def _draw_lines(p, layer, pairs, members, geo, band_of_card, band_boxes, inner_x) -> None:
    """A line straight down when nothing is in the way, else down the gutter left of the cards."""
    exits: dict[str, list] = {}
    plans = []
    lane = 0
    for (top, bottom), count in sorted(pairs.items(), key=lambda kv: (band_of_card[kv[0][0]], geo[kv[0][1]][0])):
        tx, ty, tw, th, trow, trows = geo[top]
        bx, by, bw, bh, brow, _ = geo[bottom]
        gap = band_of_card[bottom] - band_of_card[top]
        if gap == 0 and trow == brow:
            # Neighbours share a narrow gutter: the count alone fits on the line; the tooltip says the rest.
            # Cards further apart in one row are joined over the top, clear of the cards between them.
            side = abs(tx - bx) == tw + GAP
            plans.append((top, bottom, str(count), "side" if side else "over", lane))
            lane += not side
            continue
        direct = (0 < gap <= 1 and trow == trows - 1 and brow == 0) or bottom in band_boxes or tw > 1000 or bw > 1000
        label = f"{count} cable{'s' if count != 1 else ''}"
        if top in band_boxes or bottom in band_boxes:
            label = f"{len(members[(top, bottom)]) - 1} zones · {label}"
        plans.append((top, bottom, label, direct, lane))
        if direct:
            exits.setdefault(top, []).append(bx + bw / 2)
            exits.setdefault(bottom, []).append(tx + tw / 2)
        else:
            lane += 1
    for card in exits:
        exits[card].sort()
    for top, bottom, label, direct, lane_n in plans:
        count = pairs[(top, bottom)]
        holder = ET.Element("object", {"id": p.new_id(), "label": label,
                                       "tooltip": f"{count} cable{'s' if count != 1 else ''} between these zones"})
        edge = ET.SubElement(holder, "mxCell", {"edge": "1", "parent": layer, "source": top, "target": bottom})
        g = ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})
        tx, ty, tw, th, _, _ = geo[top]
        bx, by, bw, bh, _, _ = geo[bottom]
        if direct == "side":
            left, right = (top, bottom) if tx < bx else (bottom, top)
            edge.set("source", left)
            edge.set("target", right)
            style = "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
        elif direct == "over":
            y = ty - GAP / 2 + 3 * (lane_n % 2)
            pts = ET.SubElement(g, "Array", {"as": "points"})
            ET.SubElement(pts, "mxPoint", {"x": f"{tx + tw / 2:g}", "y": f"{y:g}"})
            ET.SubElement(pts, "mxPoint", {"x": f"{bx + bw / 2:g}", "y": f"{y:g}"})
            style = "exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
        elif direct:
            # Where both cards overlap sideways, drop straight down; else spread along each edge.
            lo, hi = max(tx, bx), min(tx + tw, bx + bw)
            if hi - lo > 24:
                x = (lo + hi) / 2
                fx, fy = (x - tx) / tw, (x - bx) / bw
            else:
                ex = exits[top].index(bx + bw / 2) + 1
                fx = ex / (len(exits[top]) + 1)
                fy = (exits[bottom].index(tx + tw / 2) + 1) / (len(exits[bottom]) + 1)
            style = f"exitX={fx:.3f};exitY=1;exitDx=0;exitDy=0;entryX={fy:.3f};entryY=0;entryDx=0;entryDy=0;"
        else:
            x = inner_x - 8 - 6 * (lane_n % 5)
            pts = ET.SubElement(g, "Array", {"as": "points"})
            ET.SubElement(pts, "mxPoint", {"x": f"{x:g}", "y": f"{ty + th / 2:g}"})
            ET.SubElement(pts, "mxPoint", {"x": f"{x:g}", "y": f"{by + bh / 2:g}"})
            # The label reads down the gutter, beside the vertical run, clear of the cards.
            style = ("exitX=0;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
                     "horizontal=0;")
        edge.set("style", CONDUIT_STYLE + style)
        p.cells.append(holder)
