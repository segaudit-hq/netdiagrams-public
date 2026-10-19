"""Click-to-show controls for the draw.io file, which still prints cleanly.

Every page gets a small bar of buttons at its top right, on its own layer.
Each button switches one of the page's layers on or off (mgmt IPs, serials,
registers, schedules ...), and three presets set the whole page at once:

- **Print view** hides the bar and every on-screen-only layer, so what's left
  is the drawing as printed;
- **Share view** also hides the layers marked "hide before sharing";
- **Everything** switches the page's layers back on.

The buttons are draw.io custom links: they work when the file is opened in
draw.io's viewer (and in Confluence, Jira or an exported HTML page), and in
the editor from the link pop-up. View ▸ Layers (Ctrl+Shift+L) does the same by hand.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET

from .graph import Graph, cell_of

CONTROLS_LAYER = "Controls (screen only · Print view hides this bar)"
SKIP = ("Guides", "Border", "Controls", "Copy of the typical")
BUTTON = ("rounded=1;absoluteArcSize=1;arcSize=20;html=1;whiteSpace=nowrap;fontSize=9;fontFamily=Inter;"
          "fillColor=#FFFFFF;strokeColor=#CBD5E1;fontColor=#334155;spacing=2;")
PRESET = ("rounded=1;absoluteArcSize=1;arcSize=20;html=1;whiteSpace=nowrap;fontSize=9;fontFamily=Inter;"
          "fillColor=#1D4ED8;strokeColor=#1D4ED8;fontColor=#FFFFFF;fontStyle=1;spacing=2;")


def _link(*actions: dict) -> str:
    return "data:action/json," + json.dumps({"actions": list(actions)}, separators=(",", ":"))


def _short(name: str) -> str:
    name = re.sub(r"^\d+[a-z]? · ", "", name)
    name = re.sub(r"\s*\((hide before sharing|hidden)\)", "", name)
    name = name.split(" (")[0]
    return name if len(name) <= 28 else name[:26] + "…"


def add_controls(diagram: ET.Element) -> None:
    g = Graph(diagram)
    if any(name == CONTROLS_LAYER for name in g.layers.values()):
        return
    layers = [(i, name) for i, name in g.layers.items()]
    toggles = [(i, name) for i, name in layers if name and not name.startswith(SKIP)]
    copies = [i for i, name in layers if name.startswith("Copy of the typical")]
    if len(toggles) < 2:
        return
    page_id = diagram.get("id", "page")
    bar = f"{page_id}-controls"
    guides = [i for i, name in layers if name.startswith("Guides")]
    hide_for_print = [bar] + copies + guides
    hide_for_share = hide_for_print + [i for i, name in toggles if "hide before sharing" in name.lower()]
    everything = [i for i, _ in toggles] + [bar] + guides

    buttons = [("Print view", PRESET, _link({"hide": {"cells": hide_for_print}}),
                "Hide this bar, the guide notes and the on-screen copies; print what's left (bring the bar back from View ▸ Layers)"),
               ("Share view", PRESET, _link({"hide": {"cells": hide_for_share}}),
                "Print view without the layers marked 'hide before sharing' (IPs, serials, circuit IDs). For a file to send "
                "out, run: netdiagrams share <this file> (it strips the hidden data too)"),
               ("Everything", PRESET, _link({"show": {"cells": everything}}, {"hide": {"cells": copies}}),
                "Switch every layer of this page back on")]
    buttons += [(f"{_short(name)}", BUTTON, _link({"toggle": {"cells": [i]}}), f"Show or hide: {name}")
                for i, name in toggles]

    widths = [len(label) * 5.4 + 18 for label, *_ in buttons]
    page_w = _right_edge(g)  # the drawing's own frame, so the bar sits inside it on paper wider than the sheet
    gap, max_w = 6, page_w * 0.55
    rows, row = [], []
    for item in zip(buttons, widths):
        if row and sum(w for _, w in row) + gap * len(row) + item[1] > max_w:
            rows.append(row)
            row = []
        row.append(item)
    rows.append(row)
    cells = [ET.Element("mxCell", {"id": bar, "value": CONTROLS_LAYER, "style": "", "parent": "0"})]
    n = 0
    for r, row in enumerate(rows):
        x = page_w - 30 - sum(w for _, w in row) - gap * (len(row) - 1)
        y = (16 if len(rows) == 1 else 6) + r * 24
        for (label, style, link, tip), w in row:
            obj = ET.Element("object", {"id": f"{bar}-{n}", "label": html.escape(label), "link": link,
                                        "tooltip": tip})
            cell = ET.SubElement(obj, "mxCell", {"style": style, "vertex": "1", "parent": bar})
            ET.SubElement(cell, "mxGeometry", {"x": f"{x:g}", "y": f"{y:g}", "width": f"{w:g}", "height": "20",
                                               "as": "geometry"})
            cells.append(obj)
            x += w + gap
            n += 1
    g.root.extend(cells)


def _right_edge(g: Graph) -> float:
    """The right edge of the sheet's frame (the border cell), else of its drawn content.

    Anchored to the drawing rather than the page: a sheet narrower than its paper would
    otherwise leave the bar floating outside the frame, and a rebuild from the drawing
    (whose page is already its paper size) puts the bar in the same place.
    """
    tops = [(i, g.box(i)) for i, el in g.els.items() if cell_of(el) is not None
            and cell_of(el).get("vertex") == "1" and cell_of(el).get("parent") in g.layers
            and not g.layer_of(i).startswith(("Controls", "Example watermark"))]
    frame = [b for i, b in tops if g.layer_of(i).startswith("Border") and b[2] > 1000]
    boxes = frame or [b for _, b in tops]
    if not boxes:
        return float(g.model.get("pageWidth", 2400))
    return max(x + w for x, _, w, _ in boxes)


def add_to_all(template: ET.Element) -> None:
    for diagram in template.findall("diagram"):
        if diagram.find("mxGraphModel") is not None:
            add_controls(diagram)
