"""Render a Site as a multi-page draw.io file in the S01 drawing standard."""

from __future__ import annotations

import datetime as dt
import html
import math
import xml.etree.ElementTree as ET

from . import paper, profiles, stencils
from .model import BANDS, Site, Zone, bands

PAGE_W = 1800
MARGIN = 24
BAND_INNER_X = 84
GAP = 16
FONT = "fontFamily=Inter;"

# Purdue band level -> (pill fill, pill text, zone fill, zone stroke, zone text).
BAND_COLORS = {
    "L5": ("#E2E8F0", "#475569", "#F8FAFC", "#CBD5E1", "#475569"),
    "L4": ("#E0E9FC", "#2563EB", "#F3F7FE", "#BFD0F7", "#2563EB"),
    "L3.5": ("#FAECDC", "#D97706", "#FFF9F0", "#F2D3A6", "#B45309"),
    "L3": ("#DCF0EA", "#059669", "#F2FAF8", "#A8DACA", "#059669"),
    "L2–0": ("#EDE3FC", "#7C3AED", "#F8F4FE", "#D4C2F7", "#7C3AED"),
    "—": ("#E2E8F0", "#475569", "#F8FAFC", "#CBD5E1", "#475569"),
    "?": ("#FEF3C7", "#B45309", "#FFFBEB", "#FCD34D", "#B45309"),  # a gap to fix, in the gaps' amber
}
SIS_COLORS = ("#FEF2F2", "#FCA5A5", "#DC2626")

# NetBox cable type -> (pill color, pill text), from the template's NetBox page.
CABLE_MEDIA = {
    "smf-os2": ("#FFEB3B", "SMF OS2"), "smf-os1": ("#FFEB3B", "SMF OS1"), "smf": ("#FFEB3B", "SMF"),
    "mmf-om1": ("#FF9800", "MMF OM1"), "mmf-om2": ("#FF9800", "MMF OM2"),
    "mmf-om3": ("#00BCD4", "MMF OM3"), "mmf-om4": ("#00BCD4", "MMF OM4"),
    "mmf-om5": ("#8BC34A", "MMF OM5"), "mmf": ("#00BCD4", "MMF"),
    "cat5e": ("#2196F3", "Cat5e"), "cat6": ("#2196F3", "Cat6"), "cat6a": ("#2196F3", "Cat6A"),
    "cat7": ("#2196F3", "Cat7"), "cat8": ("#2196F3", "Cat8"),
    "dac-passive": ("#9E9E9E", "DAC"), "dac-active": ("#9E9E9E", "DAC"), "aoc": ("#9E9E9E", "AOC"),
}
LIGHT_PILLS = {"#FFEB3B", "#FF9800", "#00BCD4", "#8BC34A"}

LINK_STYLE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=16;orthogonalLoop=1;jumpStyle=arc;jumpSize=8;"
    "endArrow=none;startArrow=none;strokeColor=#64748B;strokeWidth=1.6;fontSize=9;html=1;" + FONT
)
PORT_TAG_STYLE = (
    "edgeLabel;html=1;fontSize=9;fontColor=#334155;labelBackgroundColor=#FFFFFF;"
    "fontFamily=JetBrains Mono;"
)
TEXT = "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;spacing=2;" + FONT

SEGAUDIT_NOTE = (
    "<b>Is this segmentation really enforced?</b><br>"
    "The zones on this drawing are the design. SegAudit reads your firewall configuration "
    "and shows where real traffic paths differ from it.<br>"
    '<a href="https://segaudit.com">segaudit.com</a>'
)


class Page:
    def __init__(self, page_id: str, name: str):
        self.id = page_id
        self.name = name
        self.layers: dict[str, str] = {}
        self.cells: list[ET.Element] = []
        self.height = 1000
        self._n = 0

    def layer(self, name: str, visible: bool = True) -> str:
        if name not in self.layers:
            layer_id = f"{self.id}-L{len(self.layers)}"
            self.layers[name] = layer_id
            attrs = {"id": layer_id, "value": name, "style": "", "parent": "0"}
            if not visible:
                attrs["visible"] = "0"
            self.cells.append(ET.Element("mxCell", attrs))
        return self.layers[name]

    def new_id(self) -> str:
        self._n += 1
        return f"{self.id}-c{self._n}"

    def box(self, parent: str, x, y, w, h, value: str = "", style: str = "", cell_id: str | None = None) -> str:
        cell_id = cell_id or self.new_id()
        cell = ET.Element("mxCell", {
            "id": cell_id, "value": value, "style": style, "vertex": "1", "parent": parent,
        })
        ET.SubElement(cell, "mxGeometry", {
            "x": f"{x:g}", "y": f"{y:g}", "width": f"{w:g}", "height": f"{h:g}", "as": "geometry",
        })
        self.cells.append(cell)
        return cell_id

    def element(self) -> ET.Element:
        diagram = ET.Element("diagram", {"id": self.id, "name": self.name})
        model = ET.SubElement(diagram, "mxGraphModel", {
            "dx": "1600", "dy": "1000", "grid": "1", "gridSize": "10", "guides": "1",
            "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1",
            "pageScale": "1", "pageWidth": str(PAGE_W), "pageHeight": str(int(self.height)),
            "background": "#F4F6FA", "math": "0", "shadow": "0",
        })
        root = ET.SubElement(model, "root")
        root.append(ET.Element("mxCell", {"id": "0"}))
        for cell in self.cells:
            root.append(cell)
        return diagram


def _zone_colors(zone: Zone) -> tuple[str, str, str]:
    if any(k in zone.slug for k in ("sis", "safety")):
        return SIS_COLORS
    return BAND_COLORS[profiles.palette(zone.band[0])][2:]


def _vlan_table(zone: Zone) -> str:
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            v.vid, html.escape(v.name), html.escape(", ".join(v.prefixes) or "—"), html.escape(v.vrf or "—"))
        for v in zone.vlans
    )
    return (
        '<table style="width:100%;border-collapse:collapse;font-size:9px;color:#334155">'
        '<tr style="color:#64748B;font-weight:bold"><td>VLAN</td><td>NAME</td><td>SUBNET</td><td>VRF</td></tr>'
        f"{rows}</table>"
    )


def _layout_zone(zone: Zone, logical: bool) -> dict:
    shapes = [stencils.shape_for_role(d.role) for d in zone.devices]
    sizes = [(stencils.library()[s]["w"], stencils.library()[s]["h"]) for s in shapes]
    card_w = max([w for w, _ in sizes] or [160])
    card_h = max([h for _, h in sizes] or [50])
    n = len(zone.devices)
    cols = 1 if n <= 1 else 2 if n <= 4 else 3 if n <= 9 else 4
    rows = math.ceil(n / cols) if n else 0
    # The physical page leaves room between cards for links, port tags and mgmt IPs.
    col_gap = GAP if logical else 56
    row_gap = GAP if logical else 64
    vlan_h = (22 + 15 * len(zone.vlans)) if (logical and zone.vlans) else 0
    width = max(cols * (card_w + col_gap) - col_gap + 2 * GAP, 300 if vlan_h else 260)
    height = 40 + rows * (card_h + row_gap) + vlan_h + (GAP if vlan_h else 0) + 8
    return {"shapes": shapes, "card_w": card_w, "card_h": card_h, "cols": cols,
            "col_gap": col_gap, "row_gap": row_gap, "vlan_h": vlan_h, "w": width, "h": max(height, 90)}


def _title(page: Page, layer: str, title: str, subtitle: str) -> None:
    page.box(layer, MARGIN, 18, 1600, 32, html.escape(title),
             TEXT + "fontSize=22;fontColor=#0F172A;fontStyle=1;")
    page.box(layer, MARGIN, 52, 1700, 22, html.escape(subtitle), TEXT + "fontSize=12;fontColor=#64748B;")


def _bands_page(page: Page, site: Site, logical: bool) -> dict[int, tuple]:
    """Draw Purdue bands, zones and device cards.

    Returns {device id: (card cell id, x, y, w, h)}.
    """
    l_bands = page.layer(profiles.current().band_layer)
    l_zones = page.layer("Zones")
    l_devices = page.layer("Devices")
    l_ips = page.layer("Mgmt IPs (hide before sharing)")
    l_vlans = page.layer("VLAN & subnet tables (hide before sharing)") if logical else None

    cards: dict[int, str] = {}
    inner_w = PAGE_W - 2 * MARGIN - BAND_INNER_X - GAP
    y = 100
    for (level, band_name, _), zones in site.bands():
        pill_fill, pill_text = BAND_COLORS[profiles.palette(level)][:2]
        placed, cx, row_y, row_h = [], 0, 0, 0
        for zone in zones:
            box = _layout_zone(zone, logical)
            if cx and cx + box["w"] > inner_w:
                cx, row_y, row_h = 0, row_y + row_h + GAP, 0
            placed.append((zone, box, cx, row_y))
            cx += box["w"] + GAP
            row_h = max(row_h, box["h"])
        band_h = max(row_y + row_h + 2 * GAP, 150)  # tall enough for the vertical band name

        page.box(l_bands, MARGIN, y, PAGE_W - 2 * MARGIN, band_h, "",
                 "rounded=1;absoluteArcSize=1;arcSize=28;fillColor=#FFFFFF;strokeColor=#E2E8F0;"
                 "strokeWidth=1;html=1;" + FONT)
        page.box(l_bands, MARGIN + 10, y + 10, 40, 22, f"<b>{html.escape(level)}</b>",
                 f"rounded=1;absoluteArcSize=1;arcSize=22;fillColor={pill_fill};strokeColor=none;"
                 f"fontColor={pill_text};fontSize=10;html=1;" + FONT)
        page.box(l_bands, MARGIN + 8, y + 40, 44, max(band_h - 52, 40), html.escape(band_name),
                 "text;html=1;horizontal=0;fontSize=10;fontStyle=1;fontColor=#94A3B8;align=right;"
                 "verticalAlign=middle;whiteSpace=wrap;" + FONT)

        for zone, box, zx, zy in placed:
            fill, stroke, text = _zone_colors(zone)
            ax, ay = MARGIN + BAND_INNER_X + zx, y + GAP + zy
            label = f"ZONE {html.escape(zone.name)}" if zone.slug else "Devices without a zone-* tag"
            zone_id = page.box(
                l_zones, ax, ay, box["w"], box["h"], label,
                f"rounded=1;absoluteArcSize=1;arcSize=24;fillColor={fill};strokeColor={stroke};"
                f"strokeWidth=1;verticalAlign=top;align=left;spacingLeft=12;spacingTop=6;fontSize=12;"
                f"fontStyle=1;fontColor={text};whiteSpace=wrap;html=1;" + FONT)
            del zone_id  # zones stay on their own layer; cards use absolute positions
            for i, device in enumerate(zone.devices):
                col, row = i % box["cols"], i // box["cols"]
                dx = ax + GAP + col * (box["card_w"] + box["col_gap"])
                dy = ay + 36 + row * (box["card_h"] + box["row_gap"])
                card_id = page.new_id()
                cells, w, h = stencils.device_cells(box["shapes"][i], card_id, l_devices, dx, dy, device.attrs)
                page.cells.extend(cells)
                cards[device.id] = (card_id, dx, dy, w, h)
                ip = device.attrs.get("primary_ip4", "")
                if ip and not logical:
                    page.box(l_ips, dx, dy + h + 2, 120, 12, html.escape(ip.split("/")[0]),
                             "text;html=1;fontSize=9;fontColor=#64748B;align=left;verticalAlign=middle;"
                             "spacing=0;fontFamily=JetBrains Mono;")
            if l_vlans and zone.vlans:
                rows = math.ceil(len(zone.devices) / box["cols"]) if zone.devices else 0
                vy = ay + 36 + rows * (box["card_h"] + box["row_gap"])
                page.box(l_vlans, ax + GAP, vy, box["w"] - 2 * GAP, box["vlan_h"], _vlan_table(zone),
                         "rounded=1;absoluteArcSize=1;arcSize=8;fillColor=#FFFFFF;strokeColor=#E2E8F0;"
                         "html=1;whiteSpace=wrap;align=left;verticalAlign=top;spacing=4;overflow=hidden;" + FONT)
        y += band_h + GAP
    page.height = y
    return cards


def _sides(a: tuple, b: tuple) -> tuple[str, str]:
    """Which side of each card a link leaves from: below/above first, else beside."""
    _, ax, ay, aw, ah = a
    _, bx, by, bw, bh = b
    if by >= ay + ah:
        return "bottom", "top"
    if by + bh <= ay:
        return "top", "bottom"
    return ("right", "left") if bx >= ax else ("left", "right")


def _anchor(side: str, frac: float) -> tuple[float, float]:
    return {"top": (frac, 0), "bottom": (frac, 1), "left": (0, frac), "right": (1, frac)}[side]


def _links(page: Page, site: Site, cards: dict[int, tuple]) -> None:
    layer = page.layer("Links (cable · media · ports)")
    links = [l for l in site.links if l.a_device in cards and l.b_device in cards]

    # Spread the links that share a card side so they don't stack on one point,
    # ordered by where the far end sits to avoid crossings.
    ends: dict[tuple, list] = {}
    for n, link in enumerate(links):
        a, b = cards[link.a_device], cards[link.b_device]
        sa, sb = _sides(a, b)
        for card, other, side, end in ((a, b, sa, "a"), (b, a, sb, "b")):
            key = other[1] + other[3] / 2 if side in ("top", "bottom") else other[2] + other[4] / 2
            ends.setdefault((card[0], side), []).append((key, n, end))
    anchors: dict[tuple, tuple] = {}
    for (_, side), items in ends.items():
        items.sort()
        for i, (_, n, end) in enumerate(items):
            anchors[(n, end)] = (side, _anchor(side, (i + 1) / (len(items) + 1)))

    for n, link in enumerate(links):
        color, pill = CABLE_MEDIA.get(link.type, (f"#{link.color}" if link.color else "#E2E8F0",
                                                  link.type or "cable"))
        font = "#0F172A" if color.upper() in LIGHT_PILLS or color == "#E2E8F0" else "#FFFFFF"
        (_, (ex, ey)), (_, (nx, ny)) = anchors[(n, "a")], anchors[(n, "b")]
        edge_id = page.new_id()
        attrs = dict(link.attrs, tooltip=f"{link.label} · {pill}" if link.label else pill)
        obj = ET.Element("object", {"id": edge_id, "label": html.escape(pill), **attrs})
        cell = ET.SubElement(obj, "mxCell", {
            "style": LINK_STYLE + f"labelBackgroundColor={color};fontColor={font};"
                     f"exitX={ex:.3g};exitY={ey:.3g};exitDx=0;exitDy=0;exitPerimeter=0;"
                     f"entryX={nx:.3g};entryY={ny:.3g};entryDx=0;entryDy=0;entryPerimeter=0;",
            "edge": "1", "parent": layer,
            "source": cards[link.a_device][0], "target": cards[link.b_device][0],
        })
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        page.cells.append(obj)
        for port, pos in ((link.a_port, "-0.8"), (link.b_port, "0.8")):
            if not port:
                continue
            tag = ET.Element("mxCell", {"id": page.new_id(), "value": html.escape(port),
                                        "style": PORT_TAG_STYLE, "vertex": "1", "connectable": "0",
                                        "parent": edge_id})
            geo = ET.SubElement(tag, "mxGeometry", {"x": pos, "relative": "1", "as": "geometry"})
            ET.SubElement(geo, "mxPoint", {"as": "offset"})
            page.cells.append(tag)


def _footer(page: Page, site: Site, drawing: str, sheet: str, segaudit_note: bool) -> None:
    layer = page.layer("Border & title block")
    y = page.height + GAP
    if segaudit_note:
        note_layer = page.layer("About this drawing")
        page.box(note_layer, PAGE_W - 2 * MARGIN - 360, y, 360, 72, SEGAUDIT_NOTE,  # four lines of text
                 "rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;"
                 "html=1;whiteSpace=wrap;align=left;verticalAlign=top;spacing=10;fontSize=10;"
                 "fontColor=#334155;" + FONT)
    page.cells.extend(stencils.copy_shape("Title block", page.new_id(), layer, MARGIN, y, {
        "Network standard — multi-site": html.escape(site.name),
        "‹drawing›": html.escape(drawing),
        "S##": html.escape(site.slug.upper() or "—"),
        "YYYY-MM-DD": dt.date.today().isoformat(),
        "n of N": sheet,
    }))
    page.height = y + 120


def render(site: Site, segaudit_note: bool = True) -> ET.Element:
    """Build the <mxfile> for a site."""
    source = f"Generated from NetBox ({site.netbox_url})" if site.netbox_url else "Generated by NetDiagrams"
    pages = []

    logical = Page("logical", "1 · Logical — zones, VLANs, subnets")
    _title(logical, logical.layer("Titles"), f"{site.name} — Logical architecture",
           f"Zones, VLANs and subnets by {profiles.current().band_word}. {source}. Zones come from zone-* tags; "
           "VLANs from their zone role or tag.")
    _bands_page(logical, site, logical=True)
    pages.append((logical, "Logical"))

    physical = Page("physical", "2 · Physical — devices and links")
    _title(physical, physical.layer("Titles"), f"{site.name} — Physical architecture",
           f"Devices and cables. Pill color = cable media; tags = interface names. {source}.")
    cards = _bands_page(physical, site, logical=False)
    _links(physical, site, cards)
    pages.append((physical, "Physical"))

    mxfile = ET.Element("mxfile", {"host": "netdiagrams", "agent": "netdiagrams", "type": "device"})
    for n, (page, drawing) in enumerate(pages, start=1):
        _footer(page, site, drawing, f"{n} of {len(pages)}", segaudit_note)
        mxfile.append(page.element())
    return mxfile


def blank_site() -> Site:
    """One empty example zone per band (Purdue levels for a plant), for drawing by hand."""
    from .model import Zone as Z
    names = profiles.current().blank_zones or [b[1].capitalize() for b in bands()]
    zones = {}
    for band, name in zip(bands(), names):
        slug = f"zone-example-{band[0].lower()}"
        zones[slug] = Z(slug=slug, name=f"{name} (rename me)", band=band)
    return Site(name="New site", slug="", netbox_url="", zones=zones, devices={}, links=[])


def write(mxfile: ET.Element, path) -> None:
    paper.fit(mxfile)
    ET.indent(mxfile)
    ET.ElementTree(mxfile).write(path, encoding="utf-8", xml_declaration=False)
