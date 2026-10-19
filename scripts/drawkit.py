"""Drawing kit for the bundled industry templates: the S01 standard's look, as functions.

One Page class writes a draw.io page with S01's id scheme ('<page>-c<n>'), its
cards, tables, bands and title block, so a template drawn with it reads as the
same standard and fills from NetBox through the same engine. The retail, office
and school generators all draw with it. ICONS is the retail set; the office and
school generators keep their own icon sets and device cards. Where the
generators' copies of this kit disagreed, the value here is the one the S01
template itself carries.
"""

from __future__ import annotations

import base64
import html
import xml.etree.ElementTree as ET

FONT = "fontFamily=Inter;"
MONO = "fontFamily=JetBrains Mono;"
NETBOX = "https://netbox.example.com"
LINE = "#E2E8F0"
BLUE_LINK = "#1D4ED8"

# Band colors: (pill fill, pill text, card fill, card stroke, title), the S01 palette.
PALETTE = {
    "slate": ("#E2E8F0", "#475569", "#F8FAFC", "#CBD5E1", "#475569"),
    "blue": ("#E0E9FC", "#2563EB", "#F4F7FE", "#B3C8F8", "#2563EB"),
    "amber": ("#FAECDC", "#D97706", "#FFF9F0", "#F2D3A6", "#B45309"),
    "green": ("#DCF0EA", "#059669", "#F2FAF8", "#A8DACA", "#059669"),
    "purple": ("#EDE3FC", "#7C3AED", "#F8F4FE", "#D4C2F7", "#7C3AED"),
    "red": ("#FDE2E2", "#DC2626", "#FEF6F6", "#F5C2C2", "#B91C1C"),
    "teal": ("#D9F2F4", "#0E7490", "#F1FAFB", "#A5DCE2", "#0E7490"),
}

POINTS = ("points=[[0,0.25,0],[0,0.5,0],[0,0.75,0],[1,0.25,0],[1,0.5,0],[1,0.75,0],"
          "[0.25,0,0],[0.5,0,0],[0.75,0,0],[0.25,1,0],[0.5,1,0],[0.75,1,0]];")
CARD = ("shape=label;rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;"
        "shadow=1;align=left;verticalAlign=top;spacingTop=5;spacingLeft=38;fontSize=11;fontColor=#0F172A;"
        "whiteSpace=wrap;html=1;" + POINTS + FONT)
TEXT = "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;spacing=2;" + FONT
TITLE = "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=22;fontColor=#0F172A;fontStyle=1;spacing=2;" + FONT
SUBTITLE = "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=12;fontColor=#64748B;spacing=2;" + FONT
NOTE = ("rounded=1;absoluteArcSize=1;arcSize=20;fillColor=#F7FAFD;strokeColor=#E8EEF6;fontSize=10;align=left;"
        "verticalAlign=top;spacingLeft=12;spacingTop=8;spacingRight=10;whiteSpace=wrap;html=1;fontColor=#334155;" + FONT)
BAND = "rounded=1;absoluteArcSize=1;arcSize=28;fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;html=1;" + FONT
RACK_PILL = ("rounded=1;absoluteArcSize=1;arcSize=8;fillColor=#EEF2F7;strokeColor=none;fontSize=7.5;fontColor=#475569;"
             "html=1;spacing=0;" + MONO)
TABLE = ("shape=table;startSize=0;container=1;collapsible=0;childLayout=tableLayout;fixedRows=1;rowLines=1;"
         "columnLines=0;fontSize=10;strokeColor=#E2E8F0;fillColor=#FFFFFF;html=1;" + FONT)
ROW = ("shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;strokeColor=inherit;top=0;left=0;"
       "bottom=0;right=0;collapsible=0;dropTarget=0;fillColor=none;points=[[0,0.5],[1,0.5]];"
       "portConstraint=eastwest;fontSize=10;html=1;" + FONT)
TCELL = ("shape=partialRectangle;html=1;whiteSpace=wrap;connectable=0;strokeColor=inherit;overflow=hidden;"
         "fillColor=none;top=0;left=0;bottom=0;right=0;pointerEvents=1;align=left;spacingLeft=6;" + FONT)
THEAD = TCELL.replace("fillColor=none;", "fillColor=#F8FAFC;") + "fontSize=9;fontColor=#64748B;fontStyle=1;"
EDGE = ("edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=16;orthogonalLoop=1;jumpStyle=arc;jumpSize=8;"
        "endArrow=none;startArrow=none;fontSize=9;fontColor=#334155;"
        "labelBackgroundColor=#FFFFFF;labelBorderColor=#E2E8F0;spacing=3;html=1;" + FONT)
LINK_EDGE = EDGE.replace("startArrow=none;", "startArrow=none;strokeWidth=1.6;")
PORT = ("edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;points=[];fontSize=7;fontColor=#334155;"
        "labelBackgroundColor=#F8FAFC;labelBorderColor=#CBD5E1;spacing=1;spacingLeft=3;spacingRight=3;" + MONO)


# --------------------------------------------------------------------- icons
def _svg(bg: str, body: str) -> str:
    """A 32x32 icon tile, base64 for a style's image=data:image/svg+xml,<this>."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'
           f'<rect x="0" y="0" width="32" height="32" rx="8" fill="{bg}"/>{body}</svg>')
    return base64.b64encode(svg.encode()).decode()


def _icon(bg: str, body: str, stroke: str = "#334155") -> str:
    return _svg(bg, f'<g fill="none" stroke="{stroke}" stroke-width="1.7" stroke-linecap="round" '
                    f'stroke-linejoin="round">{body}</g>')


ICONS = {
    "firewall": _icon("#FAE3E3", '<rect x="7" y="8" width="18" height="16" rx="2"/><path d="M7 13.3H25M7 18.6H25'
                                 'M13 8V13.3M19 8V13.3M16 13.3V18.6M11 18.6V24M21 18.6V24"/>'),
    "router": _icon("#E9E3FC", '<circle cx="16" cy="16" r="8"/><path d="M12 12l8 8M20 12l-8 8"/>'),
    "lte-router": _icon("#E9E3FC", '<rect x="8" y="15" width="16" height="9" rx="2"/><path d="M12 15V9M20 15V9'
                                   'M11.5 19.5h.01M15.5 19.5h.01"/><path d="M9 7.5c2-1.6 4.8-1.6 6.8 0" />'),
    "access-switch": _icon("#E0E9FC", '<rect x="6" y="11" width="20" height="10" rx="2"/><path d="M9.5 16h.01M13 16h.01'
                                      'M16.5 16h.01M20 16h.01M23 16h.01"/>'),
    "core-switch": _icon("#E0E9FC", '<rect x="6" y="9" width="20" height="14" rx="2"/><path d="M10 14h12M10 18h12'
                                    'M19 12l3 2-3 2M13 16l-3 2 3 2"/>'),
    "access-point": _icon("#DCF0EA", '<circle cx="16" cy="20" r="2"/><path d="M11 15.5a7 7 0 0 1 10 0M8 12.5a11 11 0 0 1 16 0"/>'),
    "pos-terminal": _icon("#EDE3FC", '<rect x="7" y="7" width="18" height="11" rx="1.5"/><path d="M16 18v3M10 25h12'
                                     'M12 21h8"/>'),
    "pin-pad": _icon("#EDE3FC", '<rect x="10" y="6" width="12" height="20" rx="2"/><rect x="12.5" y="8.5" width="7" '
                                'height="4" rx=".5"/><path d="M13 16h.01M16 16h.01M19 16h.01M13 19h.01M16 19h.01M19 19h.01'
                                'M13 22h.01M16 22h.01M19 22h.01"/>'),
    "pos-server": _icon("#EDE3FC", '<rect x="8" y="7" width="16" height="8" rx="1.5"/><rect x="8" y="17" width="16" '
                                   'height="8" rx="1.5"/><path d="M11 11h.01M11 21h.01M15 11h6M15 21h6"/>'),
    "server": _icon("#E9ECEF", '<rect x="8" y="7" width="16" height="8" rx="1.5"/><rect x="8" y="17" width="16" '
                               'height="8" rx="1.5"/><path d="M11 11h.01M11 21h.01M15 11h6M15 21h6"/>'),
    "workstation": _icon("#E0E9FC", '<rect x="7" y="8" width="18" height="12" rx="1.5"/><path d="M13 24h6M16 20v4"/>'),
    "printer": _icon("#E0E9FC", '<path d="M11 12V7h10v5"/><rect x="7" y="12" width="18" height="8" rx="1.5"/>'
                                '<path d="M11 18h10v6H11z"/>'),
    "nvr": _icon("#FAECDC", '<rect x="6" y="11" width="20" height="10" rx="2"/><circle cx="11" cy="16" r="1.6"/>'
                            '<path d="M16 16h7"/>'),
    "camera": _icon("#FAECDC", '<rect x="6" y="11" width="13" height="10" rx="2"/><path d="M19 14l6-3v10l-6-3"/>'),
    "signage": _icon("#FAECDC", '<rect x="6" y="8" width="20" height="13" rx="1.5"/><path d="M16 21v4M12 25h8M10 12h7'
                                'M10 16h12"/>'),
    "building-controller": _icon("#FAECDC", '<rect x="8" y="7" width="16" height="18" rx="2"/><path d="M16 11v5l3 2"/>'
                                            '<circle cx="16" cy="16" r="5.5"/>'),
    "sensor": _icon("#FAECDC", '<circle cx="16" cy="16" r="3"/><path d="M10 10a8.5 8.5 0 0 0 0 12M22 10a8.5 8.5 0 0 1 0 12"/>'),
    "cloud": _icon("#EBEDF0", '<path d="M11 22h11a4.5 4.5 0 0 0 .6-9 6.5 6.5 0 0 0-12.4 1.6A3.8 3.8 0 0 0 11 22z"/>',
                   "#64748B"),
    "card": _icon("#EDE3FC", '<rect x="6" y="9" width="20" height="14" rx="2"/><path d="M6 13.5h20M10 19h5"/>'),
    "building": _icon("#E0E9FC", '<path d="M8 25V9l8-3 8 3v16M8 25h16M12 12h2M18 12h2M12 16h2M18 16h2M14 25v-4h4v4"/>'),
    "store": _icon("#DCF0EA", '<path d="M7 13l2-6h14l2 6M7 13h18M7 13v12h18V13M13 25v-6h6v6"/>'),
    "people": _icon("#E9E3FC", '<circle cx="13" cy="12" r="3"/><circle cx="21" cy="13" r="2.4"/>'
                               '<path d="M7.5 24a5.5 5.5 0 0 1 11 0M18 24a4 4 0 0 1 7 -2.5"/>'),
    "lock": _icon("#EDE3FC", '<rect x="9" y="14" width="14" height="11" rx="2"/><path d="M12 14v-3a4 4 0 0 1 8 0v3'
                             'M16 18.5v2.5"/>'),
    "wifi": _icon("#DCF0EA", '<path d="M16 23h.01M12.5 19.5a5 5 0 0 1 7 0M9.5 16.5a9 9 0 0 1 13 0M6.5 13.5a13 13 0 0 1 19 0"/>'),
    "shield": _icon("#FAE3E3", '<path d="M16 6l8 3v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V9z"/><path d="M12.5 16l2.5 2.5 4.5-5"/>'),
    "wrench": _icon("#E9ECEF", '<path d="M19.5 7.5a5 5 0 0 0-5.7 6.6L7.5 20.4a2 2 0 0 0 2.8 2.8l6.3-6.3a5 5 0 0 0 6.6-5.7'
                               'l-3 3-2.8-.6-.6-2.8z"/>'),
    "ups": _icon("#E9ECEF", '<rect x="9" y="7" width="14" height="18" rx="2"/><path d="M17 10l-3 6h4l-3 6"/>'),
    "patch-panel": _icon("#E9ECEF", '<rect x="6" y="12" width="20" height="8" rx="1.5"/><path d="M9.5 16h.01M12.5 16h.01'
                                    'M15.5 16h.01M18.5 16h.01M21.5 16h.01"/>'),
    "clock": _icon("#E9ECEF", '<circle cx="16" cy="16" r="9"/><path d="M16 11v5l3.5 2"/>'),
    "x": _icon("#FDE2E2", '<path d="M11 11l10 10M21 11l-10 10"/>', "#DC2626"),
}


def icon_style(name: str, size: int = 30) -> str:
    return (f"image=data:image/svg+xml,{ICONS[name]};imageWidth={size};imageHeight={size};imageAlign=left;"
            "imageVerticalAlign=middle;")


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def sub(text: str, size: int = 9, color: str = "#64748B") -> str:
    """A card's second line, smaller and muted."""
    return f'<span style="font-size:{size}px;color:{color}">{text}</span>'


def zone_style(fill: str, stroke: str, ink: str, valign: str = "top", size: int = 12) -> str:
    """A zone box: a tinted container titled in the zone's color."""
    return (f"rounded=1;absoluteArcSize=1;arcSize=24;fillColor={fill};strokeColor={stroke};strokeWidth=1;"
            f"verticalAlign={valign};align=left;spacingLeft=12;spacingTop=6;fontSize={size};fontStyle=1;"
            f"fontColor={ink};whiteSpace=wrap;html=1;container=1;collapsible=0;" + FONT)


def link_attrs(link: str) -> dict:
    """A shape that opens its NetBox object, as S01's linked cells do."""
    return {"placeholders": "1", "tooltip": f"Open in NetBox: {link}", "link": link, "linkTarget": "_blank"}


# --------------------------------------------------------------------- pages
class Page:
    """One <diagram>: layers, cells and edges, ids '<page>-<prefix><kind><n>' (S01's are '<page>-c<n>').

    A generator whose page ids repeat S01's gives a ``prefix`` so its ids never collide with the S01 ids
    the engine's rules name."""

    def __init__(self, page_id: str, name: str, width: int, height: int, prefix: str = ""):
        self.id, self.name, self.width, self.height, self.prefix = page_id, name, width, height, prefix
        self.diagram = ET.Element("diagram", {"id": page_id, "name": name})
        self.model = ET.SubElement(self.diagram, "mxGraphModel", {
            "dx": "1600", "dy": "1000", "grid": "1", "gridSize": "10", "guides": "1", "tooltips": "1",
            "connect": "1", "arrows": "1", "fold": "1", "page": "1", "pageScale": "1",
            "pageWidth": str(width), "pageHeight": str(height), "background": "#F4F6FA", "math": "0",
            "shadow": "0"})
        self.root = ET.SubElement(self.model, "root")
        ET.SubElement(self.root, "mxCell", {"id": "0"})
        self.n = 0
        self.layers: dict[str, str] = {}
        self.reserved: set[str] = set()
        self.table_height = 0.0

    def element(self) -> ET.Element:
        return self.diagram

    def find(self, cid: str) -> ET.Element:
        """The <object> or <mxCell> with this id."""
        return next(el for el in self.root if el.get("id") == cid)

    def shift_below(self, y0: float, dy: float) -> None:
        """Move every top-level shape and edge point at or below y0 down by dy (to open a band up)."""
        layers = {c.get("id") for c in self.root if c.get("parent") == "0"}
        for el in self.root:
            cell = el if el.tag == "mxCell" else el.find("mxCell")
            if cell is None or cell.get("parent") not in layers:
                continue
            geo = cell.find("mxGeometry")
            if geo is None:
                continue
            if cell.get("vertex") == "1" and float(geo.get("y", 0)) >= y0:
                geo.set("y", f"{float(geo.get('y', 0)) + dy:g}")
            for pt in geo.iter("mxPoint"):
                if pt.get("y") is not None and float(pt.get("y")) >= y0:
                    pt.set("y", f"{float(pt.get('y')) + dy:g}")

    def _next(self, kind: str = "c") -> str:
        self.n += 1
        while f"{self.id}-{self.prefix}{kind}{self.n}" in self.reserved:
            self.n += 1
        return f"{self.id}-{self.prefix}{kind}{self.n}"

    def layer(self, name: str, visible: bool = True, locked: bool = False) -> str:
        """The layer of that name, made on first use."""
        if name not in self.layers:
            lid = self.layers[name] = f"{self.id}-L{len(self.layers)}"
            attrs = {"id": lid, "value": name, "style": "locked=1;" if locked else "", "parent": "0"}
            if not visible:
                attrs["visible"] = "0"
            ET.SubElement(self.root, "mxCell", attrs)
        return self.layers[name]

    def cell(self, parent: str, value: str, style: str, x: float, y: float, w: float, h: float,
             attrs: dict | None = None, cid: str | None = None) -> str:
        """A vertex; with ``attrs`` it is an <object> carrying them as shape data."""
        cid = cid or self._next()
        if attrs is not None:
            obj = ET.SubElement(self.root, "object", {"id": cid, "label": value, **{k: str(v) for k, v in attrs.items()}})
            cell = ET.SubElement(obj, "mxCell", {"style": style, "vertex": "1", "parent": parent})
        else:
            cell = ET.SubElement(self.root, "mxCell", {"id": cid, "value": value, "style": style, "vertex": "1",
                                                       "parent": parent})
        ET.SubElement(cell, "mxGeometry", {"x": f"{x:g}", "y": f"{y:g}", "width": f"{w:g}", "height": f"{h:g}",
                                           "as": "geometry"})
        return cid

    def edge(self, parent: str, source: str | None, target: str | None, style: str, value: str = "",
             attrs: dict | None = None, points=None, src_pt=None, tgt_pt=None, exit=None, entry=None,
             pos: float | None = None, cid: str | None = None) -> str:
        """An edge; ``exit``/``entry`` pin its ends, ``pos`` places its label (-1 source .. 1 target)."""
        cid = cid or self._next("e")
        if exit:
            style += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;exitPerimeter=0;"
        if entry:
            style += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;entryPerimeter=0;"
        a = {"style": style, "edge": "1", "parent": parent}
        if source:
            a["source"] = source
        if target:
            a["target"] = target
        if attrs is not None:
            obj = ET.SubElement(self.root, "object", {"id": cid, "label": value, **{k: str(v) for k, v in attrs.items()}})
            cell = ET.SubElement(obj, "mxCell", a)
        else:
            cell = ET.SubElement(self.root, "mxCell", {"id": cid, "value": value, **a})
        geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        if pos is not None:
            geo.set("x", f"{pos:g}")
        if src_pt:
            ET.SubElement(geo, "mxPoint", {"x": f"{src_pt[0]:g}", "y": f"{src_pt[1]:g}", "as": "sourcePoint"})
        if tgt_pt:
            ET.SubElement(geo, "mxPoint", {"x": f"{tgt_pt[0]:g}", "y": f"{tgt_pt[1]:g}", "as": "targetPoint"})
        if points:
            arr = ET.SubElement(geo, "Array", {"as": "points"})
            for px, py in points:
                ET.SubElement(arr, "mxPoint", {"x": f"{px:g}", "y": f"{py:g}"})
        return cid

    def edge_label(self, edge: str, value: str, pos: float, dy: float = -10.5, style: str = PORT,
                   dx: float = 0) -> str:
        """A label riding an edge, such as a port name at one end (pos -1 at the source, 1 at the target)."""
        cid = self._next("l")
        cell = ET.SubElement(self.root, "mxCell", {"id": cid, "value": value, "style": style, "vertex": "1",
                                                   "connectable": "0", "parent": edge})
        geo = ET.SubElement(cell, "mxGeometry", {"x": f"{pos:.4f}", "relative": "1", "as": "geometry"})
        ET.SubElement(geo, "mxPoint", {"x": f"{dx:g}", "y": f"{dy:g}", "as": "offset"})
        return cid

    def table(self, layer: str, x, y, columns: list[tuple[str, float]], rows: list[list], row_h: float = 22,
              head_h: float = 22, font: int = 10, style: str = TABLE, row: str = ROW, head: str = THEAD,
              body=None, heights: list[float] | None = None) -> str:
        """A draw.io table: a header row, then body rows. A body value may be (text, link) or
        (text, link, extra style); a linked cell opens its NetBox object.

        ``body`` is the body cells' style, or ``body(column, link)`` returning it; by default
        slate text, linked cells blue and bold. ``heights`` gives each row's height, header first.
        ``self.table_height`` is the height drawn."""
        width = sum(w for _, w in columns)
        heights = heights or [head_h] + [row_h] * len(rows)
        self.table_height = sum(heights)
        t = self.cell(layer, "", style, x, y, width, self.table_height)
        top = 0
        for r, values in enumerate([[title for title, _ in columns]] + rows):
            rid = self.cell(t, "", row, 0, top, width, heights[r])
            left = 0
            for c, ((_, w), value) in enumerate(zip(columns, values)):
                link, extra = "", ""
                if isinstance(value, tuple):
                    value, link, extra = (*value, "")[:3]
                if r == 0:
                    st = head
                elif body is None:
                    st = TCELL + (f"fontSize={font};fontColor={BLUE_LINK};fontStyle=1;" if link
                                  else f"fontSize={font};fontColor=#334155;")
                else:
                    st = body(c, link) if callable(body) else body
                self.cell(rid, value, st + extra, left, 0, w, heights[r], link_attrs(link) if link else None)
                left += w
            top += heights[r]
        return t

    # ------------------------------------------------------------ components
    def title(self, layer: str, title: str, subtitle: str, sub_id: str | None = None) -> tuple[str, str]:
        """The page title and subtitle (HTML); ``sub_id`` gives the subtitle the id the engine rewrites."""
        tid = self.cell(layer, esc(title), TITLE, 24, 18, 1600, 32)
        if sub_id:
            self.reserved.add(sub_id)
        return tid, self.cell(layer, subtitle, SUBTITLE, 24, 52, 1800, 22, cid=sub_id)

    def band(self, layer: str, y: float, h: float, code: str, label: str, width: float | None = None) -> str:
        """A full-width band with its code pill and its name up the left edge."""
        bid = self.cell(layer, "", BAND, 24, y, width or self.width - 48, h)
        self.cell(layer, f"<b>{html.escape(code)}</b>", "rounded=1;absoluteArcSize=1;arcSize=22;fillColor=#E9ECEF;"
                  "strokeColor=none;fontColor=#64748B;fontSize=10;html=1;" + FONT, 34, y + 10, 36, 22)
        self.cell(layer, html.escape(label), "text;html=1;horizontal=0;fontSize=10;fontStyle=1;fontColor=#94A3B8;"
                  "align=right;verticalAlign=middle;whiteSpace=wrap;" + FONT, 32, y + 38, 40, h - 48)
        return bid

    def zone(self, layer: str, x, y, w, h, title: str, subtitle: str, color: str) -> str:
        _, _, fill, stroke, ink = PALETTE[color]
        return self.cell(layer, f"{html.escape(title)}<br><span style=\"font-size:10px;font-weight:normal;"
                                f"color:#64748B\">{subtitle}</span>", zone_style(fill, stroke, ink), x, y, w, h)

    def note(self, layer: str, x, y, w, h, title: str, lines: list[str], fill="#FFFFFF", stroke=LINE,
             size: int = 10, attrs: dict | None = None) -> str:
        body = "<br>".join(f"• {line}" for line in lines)
        return self.cell(layer, f"<b>{html.escape(title)}</b><br>{body}",
                         f"rounded=1;absoluteArcSize=1;arcSize=16;fillColor={fill};strokeColor={stroke};"
                         f"strokeWidth=1;align=left;verticalAlign=top;spacing=10;fontSize={size};fontColor=#334155;"
                         "whiteSpace=wrap;html=1;" + FONT, x, y, w, h, attrs=attrs)

    def pill(self, layer: str, x, y, w, h, text: str, color: str, size: int = 10) -> str:
        fill, ink = PALETTE[color][0], PALETTE[color][1]
        return self.cell(layer, f"<b>{text}</b>", f"rounded=1;absoluteArcSize=1;arcSize=22;fillColor={fill};"
                         f"strokeColor=none;fontColor={ink};fontSize={size};html=1;whiteSpace=wrap;" + FONT, x, y, w, h)

    def box(self, layer: str, x, y, w, h, title: str, sub: str, icon: str, size: int = 12, link: str = "",
            stroke: str = LINE, fill: str = "#FFFFFF") -> str:
        attrs = {"link": link, "linkTarget": "_blank", "placeholders": "1",
                 "tooltip": f"Open in NetBox: {link}"} if link else None
        return self.cell(layer, f"<b>{title}</b>" + (f"<br><span style=\"font-size:9px;color:#64748B\">{sub}</span>"
                                                     if sub else ""),
                         CARD.replace("strokeColor=#E2E8F0", f"strokeColor={stroke}")
                         .replace("fillColor=#FFFFFF", f"fillColor={fill}")
                         .replace("fontSize=11", f"fontSize={size}").replace("verticalAlign=top;spacingTop=5;",
                                                                           "verticalAlign=middle;")
                         + icon_style(icon), x, y, w, h, attrs)

    def title_block(self, layer: str, site_code: str, drawing: str, sheet: str, date: str, project: str) -> str:
        """The page border, logo box and title block; a site code (not "All") links to its NetBox site."""
        W, H = self.width, self.height
        self.cell(layer, "", "rounded=1;absoluteArcSize=1;arcSize=36;fillColor=none;strokeColor=#E2E8F0;strokeWidth=1;"
                             "html=1;" + FONT, 10, 10, W - 20, H - 20)
        self.cell(layer, "", "rounded=1;absoluteArcSize=1;arcSize=24;fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;"
                             "html=1;whiteSpace=wrap;" + FONT, W - 904, H - 86, 880, 64)
        self.cell(layer, "<b>LOGO</b>", "rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#E8EBF3;strokeColor=none;"
                                        "fontColor=#1E3A8A;fontSize=11;html=1;" + FONT, W - 894, H - 76, 108, 44)
        site = site_code if site_code == "All" else (site_code, f"{NETBOX}/dcim/sites/?slug={site_code.lower()}")
        body = TCELL + "fontSize=10;fontColor=#334155;"
        return self.table(layer, W - 772, H - 80, [("PROJECT", 240), ("DRAWING", 200), ("SITE", 60), ("REV", 54),
                                                    ("DATE", 90), ("SHEET", 80)],
                          [[project, drawing, site, "A", date, sheet]], row_h=26, head_h=26,
                          style=TABLE.replace("strokeColor=#E2E8F0", "strokeColor=none"),
                          head=TCELL + "fontSize=9;fontColor=#94A3B8;fontStyle=1;",
                          body=lambda c, link: TCELL + "fontSize=10;fontColor=#0F172A;fontStyle=1;" if c == 0 else body)

    def legend(self, layer: str, x, y, w: float = 480, roles=(), lines=(), chips=()) -> None:
        """Roles (icon, text), line samples (style, text) and zone chips (text, color)."""
        rows = -(-len(roles) // 2)
        h = 40 + rows * 24 + len(lines) * 22 + (36 if chips else 0) + 10
        self.cell(layer, "<b>Legend</b>", "rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#FFFFFF;"
                  "strokeColor=#E2E8F0;shadow=1;align=left;verticalAlign=top;spacing=10;fontSize=12;"
                  "fontColor=#0F172A;html=1;" + FONT, x, y, w, h)
        for n, (ic, text) in enumerate(roles):
            cx = x + 14 + (n % 2) * (w / 2)
            cy = y + 38 + (n // 2) * 24
            self.cell(layer, html.escape(text), "shape=label;fillColor=none;strokeColor=none;align=left;"
                      "verticalAlign=middle;spacingLeft=24;fontSize=10;fontColor=#334155;html=1;"
                      + FONT + icon_style(ic, 18), cx, cy, w / 2 - 20, 20)
        ly = y + 40 + rows * 24
        for style, text in lines:
            self.edge(layer, None, None, style, src_pt=(x + 16, ly + 10), tgt_pt=(x + 86, ly + 10))
            self.cell(layer, html.escape(text), TEXT + "fontSize=10;fontColor=#334155;verticalAlign=middle;",
                      x + 96, ly, w - 110, 20)
            ly += 22
        cx = x + 14
        for text, color in chips:
            width = 14 + 6.2 * len(text)
            if cx + width > x + w - 10:
                break
            self.pill(layer, cx, ly + 6, width, 20, text, color, 9)
            cx += width + 6


def tooltip(attrs: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in attrs.items() if k not in ("link", "linkTarget", "placeholders"))


def mxfile(pages, agent: str, **attrs) -> ET.Element:
    """The <mxfile> holding these pages (anything with element()); extra attributes go on the root."""
    root = ET.Element("mxfile", {"host": "drawio", "agent": agent, "version": "24.7.0", "type": "device", **attrs})
    for p in pages:
        root.append(p.element())
    return root
