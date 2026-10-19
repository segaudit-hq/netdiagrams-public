"""Typicals and schedules: draw a repeated unit once, list every copy in a table.

A plant with 40 production cells or an office with 20 IDF stacks repeats the
same design. As on electrical and P&ID drawings, the template's drawn cell
(or stack) becomes the TYPICAL, and a schedule under it gives every copy its
own row: switches, management IPs, cabinet, uplinks to the core and what hangs
off it. Copies the template draws already stay drawn; the rest only need a
row. That keeps the page count of the template whatever the site's size, and
every device is still on paper, linked to NetBox.
"""

from __future__ import annotations

import copy
import html
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from . import paper, profiles
from .graph import Graph, cell_of, plain, font_size as graph_font_size, row_height as graph_row_height
from .model import _get

ROW_H = 18
HEADER_H = 20


def _style_of(g: Graph, el_id: str) -> str:
    return cell_of(g.els[el_id]).get("style") or ""


def table_styles(g: Graph, like: str) -> dict[str, str]:
    """The styles of an existing table, to draw new tables that look the same."""
    proto_rows = g.rows(like)
    data_cells = g.row_cells(proto_rows[1]) if len(proto_rows) > 1 else g.row_cells(proto_rows[0])
    plain_cell = next((c for c in reversed(data_cells) if g.els[c].tag == "mxCell"), data_cells[-1])
    return {"head": _style_of(g, g.row_cells(proto_rows[0])[0]),
            "body": re.sub(r"fontStyle=1;", "", _style_of(g, plain_cell)),
            "link": _style_of(g, data_cells[0]), "table": _style_of(g, like), "row": _style_of(g, proto_rows[0])}


def table_card(g: Graph, layer: str, like: str | dict, x: float, y: float, title: str, subtitle: str,
               columns: list[tuple[str, int]], rows: list[list[tuple[str, str]]], prefix: str) -> float:
    """Draw a card with a title and a table styled like the table ``like``; return its height."""
    st = like_styles(g, like)
    head_style, body_style, link_style = st["head"], st["body"], st["link"]
    table_style, row_style = st["table"], st["row"]
    width = sum(w for _, w in columns)
    heights = row_heights(columns, rows, body_style)
    height = HEADER_H + sum(heights)
    card_h = height + 52 + (14 if subtitle else 0)  # 14 px under the table, as at its sides

    def cell(cid, value, style, parent, cx, cy, w, h, link=""):
        el = ET.Element("mxCell", {"id": cid, "value": value, "style": style, "vertex": "1", "parent": parent})
        ET.SubElement(el, "mxGeometry", {"x": f"{cx:g}", "y": f"{cy:g}", "width": f"{w:g}", "height": f"{h:g}",
                                         "as": "geometry"})
        if not link:
            return el
        obj = ET.Element("object", {"id": cid, "label": value, "link": link, "linkTarget": "_blank"})
        el.attrib.pop("id")
        el.attrib.pop("value")
        obj.append(el)
        return obj

    new = [cell(f"{prefix}-card", "", "rounded=1;absoluteArcSize=1;arcSize=24;fillColor=#FFFFFF;strokeColor=#E2E8F0;"
                "shadow=1;html=1;whiteSpace=wrap;fontFamily=Inter;", layer, x, y, width + 28, card_h),
           cell(f"{prefix}-title", f"<b>{html.escape(title)}</b>" + (
               f'<br><span style="font-size:9px;color:#64748B;font-weight:normal">{subtitle}</span>' if subtitle else ""),
                "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=13;fontColor=#0F172A;spacing=2;"
                "fontFamily=Inter;", layer, x + 14, y + 10, width, 22 + (14 if subtitle else 0))]
    ty = y + 38 + (14 if subtitle else 0)
    table = f"{prefix}-t"
    new.append(cell(table, "", table_style, layer, x + 14, ty, width, height))
    ry = 0.0
    for r, values in enumerate([[(c, "") for c, _ in columns]] + rows):
        row_id = f"{table}-r{r}"
        h = HEADER_H if r == 0 else heights[r - 1]
        new.append(cell(row_id, "", row_style, table, 0, ry, width, h))
        ry += h
        cx = 0
        for c, (_, w) in enumerate(columns):
            text, link = values[c] if c < len(values) else ("", "")
            style = head_style if r == 0 else (link_style if link else body_style)
            new.append(cell(f"{row_id}-c{c}", html.escape(text), style, row_id, cx, 0, w, h, link))
            cx += w
    g.root.extend(new)
    g.reindex()
    return card_h


def row_heights(columns, rows, body_style: str = "") -> list[float]:
    """Each row's height: ROW_H, or more when a cell's text wraps at its column width."""
    size = graph_font_size(body_style)
    return [graph_row_height([(v[c][0] if c < len(v) else "", w) for c, (_, w) in enumerate(columns)], size, ROW_H)
            for v in rows]


def table_height(columns, rows, body_style: str = "") -> float:
    return HEADER_H + sum(row_heights(columns, rows, body_style))


def like_styles(g: Graph, like) -> dict[str, str]:
    return like if isinstance(like, dict) else table_styles(g, like)


# --------------------------------------------------------------------- units
def _short(name: str, prefix: str) -> str:
    return name[len(prefix):] if prefix and name.startswith(prefix) else name


def _ips(names, nb) -> str:
    ips = [_get(nb.devices[n], "primary_ip4", "address").split("/")[0] for n in names]
    ips = [i for i in ips if i]
    if len(ips) > 1 and all(i.rsplit(".", 1)[0] == ips[0].rsplit(".", 1)[0] for i in ips):
        return ips[0] + ", " + ", ".join("." + i.rsplit(".", 1)[1] for i in ips[1:])
    return ", ".join(ips)


def _device_ids_link(nb, names) -> str:
    ids = [nb.devices[n].get("id") for n in names]
    return nb.link("dcim/devices", id=ids) if nb.url and all(ids) else ""


class Unit:
    def __init__(self, key: str, kind: str):
        self.key, self.kind = key, kind
        self.switches: list[str] = []
        self.endpoints: list[str] = []
        self.uplinks: list[str] = []
        self.drawn = False


def find_units(nb, drawn: set[str]) -> dict[str, list[Unit]]:
    """Cells (zone-cell* zones) and IDF stacks (access-switch virtual chassis), with what hangs off them."""
    from .sync import _ends, _infrastructure, endpoint_roles, short_if, site_prefix
    ends = endpoint_roles()

    prefix = site_prefix(nb.devices)
    units: dict[str, Unit] = {}
    owner: dict[str, Unit] = {}
    for name, d in sorted(nb.devices.items()):
        role = _get(d, "role", "slug")
        zones = [t.get("slug", "") for t in d.get("tags") or []]
        cell = next((z for z in zones if re.match(r"zone-(cell|line|area)\d", z)), None)
        if cell:
            unit = units.setdefault(cell, Unit(cell, "cell"))
        elif role == "access-switch" and _get(d, "virtual_chassis", "name"):
            vc = _get(d, "virtual_chassis", "name")
            unit = units.setdefault(vc, Unit(vc, "idf"))
        else:
            continue
        (unit.endpoints if role in ends else unit.switches).append(name)
        owner[name] = unit
        unit.drawn |= name in drawn
    # End devices cabled to a unit's switch belong to that unit (office APs on an IDF).
    for label, c in sorted(nb.cables.items()):
        a, b = _ends(c.get("a_terminations"), nb.names), _ends(c.get("b_terminations"), nb.names)
        if not a or not b:
            continue
        for (dev, port), (peer, peer_port) in ((a[0], b[0]), (b[0], a[0])):
            unit = owner.get(dev)
            if unit is None or dev not in unit.switches or peer not in nb.devices:
                continue
            if owner.get(peer) is unit:
                continue
            if _infrastructure(nb, peer):
                unit.uplinks.append(f"{_short(dev, prefix)} {short_if(port)} → {_short(peer, prefix)} {short_if(peer_port)}")
            elif peer not in owner:
                unit.endpoints.append(peer)
                owner[peer] = unit
    out: dict[str, list[Unit]] = defaultdict(list)
    for unit in units.values():
        if unit.switches:
            out[unit.kind].append(unit)
    return out


def _cell_rows(units, nb, prefix):
    rows = []
    for u in units:
        first = nb.devices[u.switches[0]]
        roles = Counter(_get(nb.devices[n], "role", "slug") for n in u.endpoints)
        other = ", ".join(f"{r.replace('-', ' ')} ×{n}" for r, n in sorted(roles.items())
                          if r not in ("plc", "hmi", "io"))
        place = " · ".join(x for x in (_get(first, "location", "name"), _get(first, "rack", "name")) if x)
        rows.append([
            (u.key[5:].upper(), nb.link("dcim/devices", tag=u.key) if nb.url else ""),
            (place, ""),
            (", ".join(_short(n, prefix) for n in u.switches), _device_ids_link(nb, u.switches)),
            (_ips(u.switches, nb), ""),
            ("  ".join(u.uplinks), ""),
            (str(roles.get("plc", 0) or "—"), ""), (str(roles.get("hmi", 0) or "—"), ""),
            (str(roles.get("io", 0) or "—"), ""), (other, ""),
            ("drawn above" if u.drawn else "as typical", ""),
        ])
    return rows


def _idf_rows(units, nb, prefix):
    rows = []
    for u in units:
        first = nb.devices[u.switches[0]]
        aps = len(u.endpoints)
        rows.append([
            (_short(u.key, prefix), _device_ids_link(nb, u.switches)),
            (" · ".join(x for x in (_get(first, "location", "name"), _get(first, "rack", "name")) if x), ""),
            (f"{len(u.switches)} × {_get(first, 'device_type', 'model')}", ""),
            (_ips(u.switches, nb), ""),
            ("  ".join(u.uplinks), ""),
            (str(aps or "—"), _device_ids_link(nb, u.endpoints) if 0 < aps <= 40 else ""),
            ("drawn above" if u.drawn else "as typical", ""),
        ])
    return rows


CELL_COLUMNS = [("CELL", 80), ("LOCATION · CABINET", 170), ("SWITCHES", 220), ("MGMT IP", 200),
                ("UPLINKS TO CORE", 560), ("PLC", 44), ("HMI", 44), ("I/O", 44), ("OTHER", 230), ("DRAWING", 90)]
IDF_COLUMNS = [("IDF STACK", 140), ("LOCATION · RACK", 170), ("STACK", 200), ("MGMT IP", 220),
               ("UPLINKS TO CORE", 700), ("APs", 60), ("DRAWING", 90)]


def _container_of(g: Graph, device: str, layer_name: str) -> str | None:
    """The zone box drawn around a device, e.g. the CELL01 box."""
    from .sync import _is_device
    shape = next((i for i, el in g.els.items() if _is_device(el) and el.get("name") == device), None)
    if shape is None:
        return None
    sx, sy, sw, sh = g.box(shape)
    best = None
    for i, el in g.els.items():
        if g.layer_of(i) != layer_name or i == shape:
            continue
        x, y, w, h = g.box(i)
        if x <= sx and y <= sy and x + w >= sx + sw and y + h >= sy + sh and w * h > 0:
            if best is None or w * h < g.box(best)[2] * g.box(best)[3]:
                best = i
    return best


def typical_tag(count: int, schedule: str) -> str:
    return f' <b style="color:#4338CA">· TYPICAL ×{count}</b> <span style="color:#64748B">see {schedule}</span>'


TYPICAL_TAG = re.compile(r' <b style="color:#4338CA">· TYPICAL ×\d+</b> <span style="color:#64748B">see [^<]*</span>')


def _label_typical(g: Graph, container: str | None, count: int, schedule: str, device: str | None = None) -> None:
    tag = typical_tag(count, html.escape(schedule))
    if container is None and device:
        from .sync import _is_device
        shape = next((el for el in g.els.values() if _is_device(el) and el.get("name") == device), None)
        group = g.els.get(cell_of(shape).get("parent")) if shape is not None else None
        target = group if group is not None and plain(g.value(group)) else shape
        if target is not None:
            g.set_value(target, g.value(target) + tag)
        return
    if container is None:
        return
    for child in [container] + g.children.get(container, []):
        el = g.els[child]
        text = g.value(el)
        if plain(text):
            g.set_value(el, text + tag)
            return
    # The label may be a separate text shape at the box's bottom edge.
    x, y, w, h = g.box(container)
    for i, el in g.els.items():
        bx, by, bw, bh = g.box(i)
        if i != container and x <= bx <= x + w and y + h - 40 <= by <= y + h and plain(g.value(el)):
            g.set_value(el, g.value(el) + tag)
            return


def apply(g: Graph, nb, drawn: set[str]) -> set[str]:
    """Add the cell and IDF schedules to the physical page; return the devices they cover."""
    from .sync import site_prefix

    units = find_units(nb, drawn)
    prefix = site_prefix(nb.devices)
    covered: set[str] = set()
    like = next((t for t in g.tables() if "HOSTNAME" in g.header(t)), None)
    if like is None:
        return covered
    bands = sorted((i for i, el in g.els.items() if g.layer_of(i) == profiles.current().band_layer
                    and cell_of(el).get("vertex") == "1" and g.box(i)[2] > 1000), key=lambda i: g.box(i)[1])
    # Work bottom-up so an inserted schedule doesn't move the next anchor.
    plans = []
    for kind, columns, rows_of, title, unit_name in (
            ("cell", CELL_COLUMNS, _cell_rows, "Cell schedule", "cells"),
            ("idf", IDF_COLUMNS, _idf_rows, "IDF schedule", "IDF stacks")):
        found = sorted(units.get(kind, []), key=lambda u: u.key)
        extra = [u for u in found if not u.drawn]
        if not extra:
            continue
        drawn_units = [u for u in found if u.drawn]
        anchor = next((n for u in drawn_units for n in u.switches if n in drawn), None)
        if anchor is None:
            continue
        container = _container_of(g, anchor, "Zones (cells · SIS)") if kind == "cell" else None
        ay = g.box(container)[1] if container else _shape_y(g, anchor)
        band = next((b for b in bands if g.box(b)[1] <= ay <= g.box(b)[1] + g.box(b)[3]), None)
        if band is None:
            continue
        rows = rows_of(found, nb, prefix)
        typical_unit = next(u for u in drawn_units if anchor in u.switches)
        region_root = container or _parent_box(g, anchor)
        copies = {}
        if region_root is not None:
            region = _region(g, region_root)
            pairs = _cable_pairs(nb)
            groups = {}
            for u in extra:
                made = draw_copy(g, nb, typical_unit, u, region_root, region, pairs)
                if made:
                    copies[u.key], groups[u.key] = made
            _fill_copies(g, nb, copies, groups)
        for u, row in zip(found, rows):
            if u.key in copies:
                others = [l for k, l in copies.items() if k != u.key]
                row[0] = (row[0][0] + " ›", reveal_link(copies[u.key], others))
        plans.append((g.box(band)[1] + g.box(band)[3], kind, columns, rows, title,
                      unit_name, found, band, container, anchor))
        for u in found:
            if not u.drawn:
                covered.update(u.switches + u.endpoints)
    # Schedules go under the last band, so no line between bands crosses them.
    if not plans:
        return covered
    for _, kind, columns, rows, title, unit_name, found, band, container, anchor in sorted(plans, key=lambda p: p[0]):
        n_extra = sum(not u.drawn for u in found)
        typical = container or _container_of(g, anchor, "Zones (cells · SIS)")
        _label_typical(g, typical, n_extra + 1, title, anchor if typical is None else None)
        subtitle = (f"{len(found)} {unit_name}. Those not drawn are built like the TYPICAL; "
                    "each row gives their own names, addresses and uplinks.")
        schedule_card(g, like, title, html.escape(subtitle), columns, rows, f"{g.diagram.get('id')}-{kind}-schedule")
    return covered


def _shape_y(g: Graph, device: str) -> float:
    from .sync import _is_device
    shape = next(i for i, el in g.els.items() if _is_device(el) and el.get("name") == device)
    return g.box(shape)[1]


# ------------------------------------------------------------ register sheets
REGISTER_ROWS = 60          # rows per column on a register sheet
COLUMN_GAP = 24


def _table_rows(g: Graph, table: str) -> tuple[list[tuple[str, int]], list[list[tuple[str, str]]]]:
    rows = g.rows(table)
    header = [(plain(g.value(g.els[c])), int(float(g.geometry(c).get("width", 80)))) for c in g.row_cells(rows[0])]
    data = [[(plain(g.value(g.els[c])), g.els[c].get("link", "")) for c in g.row_cells(r)] for r in rows[1:]]
    return header, data


def _card_parts(g: Graph, table: str) -> list[str]:
    """The table, the card behind it, and the title and notes on that card."""
    tx, ty, tw, th = g.box(table)
    tops = [i for i, el in g.els.items() if cell_of(el) is not None and cell_of(el).get("vertex") == "1"
            and cell_of(el).get("parent") in g.layers and not g.layer_of(i).startswith("Border")]
    cards = [i for i in tops if i != table and g.box(i)[0] <= tx and g.box(i)[1] <= ty
             and g.box(i)[0] + g.box(i)[2] >= tx + tw and g.box(i)[1] + g.box(i)[3] >= ty + th]
    if not cards:
        return [table]
    card = min(cards, key=lambda i: g.box(i)[2] * g.box(i)[3])
    cx, cy, cw, ch = g.box(card)
    return [i for i in tops if cx - 1 <= g.box(i)[0] and cy - 1 <= g.box(i)[1]
            and g.box(i)[0] + g.box(i)[2] <= cx + cw + 1 and g.box(i)[1] + g.box(i)[3] <= cy + ch + 1]


# The tallest paper (A0 landscape) less room for the title block a register sheet gets.
SHEET_LIMIT = paper.SIZES[-1][2] - 140


def _columns(header, data, body_style: str, most: int) -> list[list]:
    """The register's rows cut into columns of at most ``most`` rows, none taller than a sheet holds."""
    tallest = SHEET_LIMIT - 72 - 52 - HEADER_H
    out, height = [], tallest + 1
    for row, h in zip(data, row_heights(header, data, body_style)):
        if height + h > tallest or len(out[-1]) >= most:
            out.append([])
            height = 0.0
        out[-1].append(row)
        height += h
    return out


def move_long_tables(template: ET.Element, g: Graph) -> list[ET.Element]:
    """Tables that run past the drawing's bottom go to register sheets, laid out in columns.

    Paper stays one size: instead of one very tall page, the sheet after this
    one holds the registers side by side, ``REGISTER_ROWS`` rows a column,
    every row still linked to NetBox. The page keeps a card pointing to it.
    A register sheet that would grow taller than A0 continues on the next one.
    """
    bands = [i for i, el in g.els.items() if g.layer_of(i) == profiles.current().band_layer and g.box(i)[2] > 1000
             and not (cell_of(el).get("style") or "").startswith("text")]
    # A page with no bands (the hardware sheet) keeps its tables until they pass the tallest paper.
    right_x = max((g.box(i)[0] + g.box(i)[2] for i in bands), default=0)
    drawing_bottom = max((g.box(i)[1] + g.box(i)[3] for i, el in g.els.items()
                          if cell_of(el) is not None and cell_of(el).get("vertex") == "1"
                          and cell_of(el).get("parent") in g.layers and g.box(i)[0] < right_x
                          and not g.layer_of(i).startswith("Border")), default=SHEET_LIMIT)
    # A register that had its own sheet before (brought back as ``<page>-reg<n>-t`` when the drawing
    # was rebuilt from itself) keeps it, so a rebuild lays the sheets out the same way.
    # A page taller than the tallest paper sends its right-hand registers too.
    page_bottom = max((g.box(i)[1] + g.box(i)[3] for i, el in g.els.items()
                       if cell_of(el) is not None and cell_of(el).get("vertex") == "1"
                       and cell_of(el).get("parent") in g.layers and not g.layer_of(i).startswith("Border")), default=0)
    if page_bottom > SHEET_LIMIT:
        drawing_bottom = -40
    long = [t for t in g.tables() if len(g.rows(t)) > 2
            and ((g.box(t)[0] >= right_x and g.box(t)[1] + g.box(t)[3] > drawing_bottom + 40)
                 or g.box(t)[1] + g.box(t)[3] > SHEET_LIMIT
                 or re.fullmatch(rf"{re.escape(g.diagram.get('id') or '')}-reg\d+-t", t))]
    if not long:
        return []
    page_id = f"{g.diagram.get('id')}-registers"
    number = g.name.split(" ", 1)[0]
    page_w = float(g.model.get("pageWidth", 2880))
    sheets: list[ET.Element] = []

    def new_sheet() -> Graph:
        k = len(sheets) + 1
        sid, code = (page_id, f"{number}r") if k == 1 else (f"{page_id}-{k}", f"{number}r{k}")
        sheet = ET.Element("diagram", {"id": sid, "name": f"{code} · Registers (continued from sheet {number})"})
        model = ET.SubElement(sheet, "mxGraphModel", dict(g.model.attrib))
        root = ET.SubElement(model, "root")
        root.append(ET.Element("mxCell", {"id": "0"}))
        root.append(ET.Element("mxCell", {"id": f"{sid}-L", "value": "Registers", "parent": "0"}))
        title = ET.Element("mxCell", {"id": f"{sid}-title", "parent": f"{sid}-L", "vertex": "1",
                                      "value": html.escape(f"Registers for sheet {number}, every row linked to NetBox"
                                                           + (f" ({k})" if k > 1 else "")),
                                      "style": "text;html=1;align=left;verticalAlign=top;fontSize=22;fontStyle=1;"
                                               "fontColor=#0F172A;fontFamily=Inter;"})
        ET.SubElement(title, "mxGeometry", {"x": "24", "y": "18", "width": "1600", "height": "32", "as": "geometry"})
        root.append(title)
        sheets.append(sheet)
        return Graph(sheet)

    def close(reg: Graph, bottom: float) -> None:
        reg.model.set("pageHeight", f"{bottom + 40:g}")

    reg = new_sheet()
    x, y, row_h = 24.0, 72.0, 0.0
    for n, table in enumerate(sorted(long, key=lambda t: g.box(t)[1])):
        header, data = _table_rows(g, table)
        styles = table_styles(g, table)
        parts = _card_parts(g, table)
        title = next((plain(g.value(g.els[i])) for i in parts if i != table and plain(g.value(g.els[i]))), "Register")
        width = sum(w for _, w in header) + 28 + COLUMN_GAP
        chunks = _columns(header, data, styles["body"], REGISTER_ROWS)
        if len(chunks) > 8:  # a register for a big site: A0-wide sheets of full-height columns
            page_w = max(page_w, paper.SIZES[-1][1] - 24)
            chunks = _columns(header, data, styles["body"], len(data))
        first = None
        for k, chunk in enumerate(chunks):
            if x + width > page_w and x > 24:
                x, y, row_h = 24.0, y + row_h + COLUMN_GAP, 0.0
            if x == 24 and y > 72 and y + table_height(header, chunk, styles["body"]) + 52 > SHEET_LIMIT:
                close(reg, y - COLUMN_GAP)
                reg = new_sheet()
                x, y, row_h = 24.0, 72.0, 0.0
            label = title if len(chunks) == 1 else f"{title} ({k + 1} of {len(chunks)})"
            h = table_card(reg, f"{reg.diagram.get('id')}-L", styles, x, y, label, "", header, chunk,
                           f"{page_id}-t{n}-{k}")
            if first is None:
                first = reg.diagram
            x += width
            row_h = max(row_h, h)
        x = page_w  # each register starts on a new row of columns
        # On the drawing, a short card points to the register sheet.
        old_h = max(g.box(i)[1] + g.box(i)[3] for i in parts) - min(g.box(i)[1] for i in parts)
        top = min(g.box(i)[1] for i in parts)
        left = min(g.box(i)[0] for i in parts)
        card_w = max(g.box(i)[2] for i in parts)
        g.remove(parts)
        layer = next(iter(g.layers))
        pointer = ET.Element("object", {"id": f"{page_id}-ptr{n}", "link": f"data:page/id,{first.get('id')}",
                                        "netdiagrams_from": table,
                                        "label": f"<b>{html.escape(title)}</b><br>{len(data)} rows, on sheet "
                                                 f"{first.get('name').split(' ', 1)[0]} ›"})
        cell = ET.SubElement(pointer, "mxCell", {
            "style": "rounded=1;absoluteArcSize=1;arcSize=24;fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;"
                     "html=1;whiteSpace=wrap;align=left;verticalAlign=middle;spacingLeft=14;fontSize=12;"
                     "fontColor=#1D4ED8;fontFamily=Inter;", "vertex": "1",
            "parent": next(i for i, name in g.layers.items() if "register" in name.lower()) if any(
                "register" in name.lower() for name in g.layers.values()) else layer})
        ET.SubElement(cell, "mxGeometry", {"x": f"{left:g}", "y": f"{top:g}", "width": f"{card_w:g}",
                                           "height": "60", "as": "geometry"})
        g.root.append(pointer)
        g.reindex()
        g.shift_below(left, left + card_w, top + old_h - 0.5, 60 - old_h, {pointer.get("id")})
    close(reg, y + row_h)
    # The drawing's own page shrinks back to the drawing.
    bottom = max(g.box(i)[1] + g.box(i)[3] for i, el in g.els.items()
                 if cell_of(el) is not None and cell_of(el).get("vertex") == "1"
                 and cell_of(el).get("parent") in g.layers and not g.layer_of(i).startswith("Border"))
    g.model.set("pageHeight", f"{bottom + 30:g}")
    border = next((i for i in g.els if g.layer_of(i).startswith("Border") and g.box(i)[2] > 2000), None)
    if border:
        g.geometry(border).set("height", f"{bottom + 10 - g.box(border)[1]:g}")
    at = list(template).index(g.diagram) + 1
    for k, sheet in enumerate(sheets):
        template.insert(at + k, sheet)
    return sheets


# -------------------------------------------------------- copies on screen
COPY_LAYER = "Copy of the typical: {} (click its schedule row)"


def reveal_link(layer: str, others: list[str]) -> str:
    """A draw.io link that shows one copy's layer over the typical and hides the other copies."""
    import json
    actions = [{"hide": {"cells": others}}, {"show": {"cells": [layer]}},
               {"scroll": {"cells": [f"{layer}-back"]}},
               {"highlight": {"cells": [f"{layer}-back"], "color": "#4338CA", "duration": 1500}}]
    return "data:action/json," + json.dumps({"actions": actions}, separators=(",", ":"))


def _parent_box(g: Graph, device: str) -> str | None:
    """The stack box a device row sits in (an IDF stack), else the device's own shape."""
    from .sync import _is_device
    shape = next((i for i, el in g.els.items() if _is_device(el) and el.get("name") == device), None)
    if shape is None:
        return None
    parent = cell_of(g.els[shape]).get("parent")
    return parent if parent in g.els and parent not in g.layers else shape


def _unit_token(key: str) -> tuple[str, str]:
    m = re.search(r"(cell|line|area|idf)(\d+)$", key, re.I)
    return (m.group(1), m.group(2)) if m else ("", "")


def _renamer(a: str, b: str):
    pattern = re.compile(r"(?<![A-Za-z])(C|Cell|CELL|cell|L|Line|LINE|line|Area|AREA|area|IDF|idf)" + a + r"(?!\d)")
    return lambda text: pattern.sub(lambda m: m.group(1) + b, text) if text else text


def _region(g: Graph, root: str) -> set[str]:
    """Everything drawn for a typical: the shapes in its box, their lines, and their tags."""
    rx, ry, rw, rh = g.box(root)
    pad = 24
    skip_layers = (profiles.current().band_layer, "Border", "Legend", "Guides")
    region = {i for i, el in g.els.items()
              if cell_of(el) is not None and cell_of(el).get("vertex") == "1"
              and cell_of(el).get("parent") in g.layers and not g.layer_of(i).startswith(skip_layers)
              and rx - pad <= g.box(i)[0] and ry - pad <= g.box(i)[1]
              and g.box(i)[0] + g.box(i)[2] <= rx + rw + pad and g.box(i)[1] + g.box(i)[3] <= ry + rh + pad}
    inside = set(region)
    for i in region:
        inside.update(g.descendants(i))
    edges = {i for i, el in g.els.items() if cell_of(el) is not None and cell_of(el).get("edge") == "1"
             and (cell_of(el).get("source") in inside or cell_of(el).get("target") in inside)}
    for i in list(edges):
        inside.update(g.descendants(i))
    inside |= edges
    inside |= {i for i, el in g.els.items() if el.get("netdiagrams_ref") in inside}
    return inside


def _cable_pairs(nb) -> dict:
    from .sync import _ends
    pairs = defaultdict(list)
    for label, c in nb.cables.items():
        a, b = _ends(c.get("a_terminations"), nb.names), _ends(c.get("b_terminations"), nb.names)
        if a and b:
            pairs[frozenset((a[0][0], b[0][0]))].append(label)
    return pairs


def draw_copy(g: Graph, nb, typical, unit, root: str, inside: set[str], pairs) -> tuple | None:
    """Draw ``unit`` in a hidden layer exactly over the typical's drawing; NetBox fills it after."""
    from . import sync

    (_, a), (_, b) = _unit_token(typical.key), _unit_token(unit.key)
    if not a or not b:
        return None
    rename = _renamer(a, b)
    rx, ry, rw, rh = g.box(root)
    slug = re.sub(r"[^a-z0-9]+", "-", unit.key.lower()).strip("-")
    layer = f"{g.diagram.get('id')}-copy-{slug}"
    title = rename(plain(g.value(g.els[root])).split(" ")[0])
    if not title or "%" in title:      # a placeholder label, such as an IDF stack's %name%
        title = unit.key
    new = [ET.Element("mxCell", {"id": layer, "value": COPY_LAYER.format(title), "style": "",
                                 "parent": "0", "visible": "0"})]
    back = ET.Element("mxCell", {"id": f"{layer}-back", "value": "", "vertex": "1", "parent": layer,
                                 "style": "rounded=1;absoluteArcSize=1;arcSize=24;fillColor=#FFFFFF;strokeColor=#4338CA;"
                                          "strokeWidth=2;dashed=1;html=1;"})
    ET.SubElement(back, "mxGeometry", {"x": f"{rx - 6:g}", "y": f"{ry - 6:g}", "width": f"{rw + 12:g}",
                                       "height": f"{rh + 12:g}", "as": "geometry"})
    new.append(back)
    new_id = lambda old: f"{layer}-{old}"
    for el in g.root:
        old = el.get("id")
        if old not in inside:
            continue
        c = copy.deepcopy(el)
        c.set("id", new_id(old))
        cell = cell_of(c)
        if cell.get("parent") in g.layers:
            cell.set("parent", layer)
        elif cell.get("parent") in inside:
            cell.set("parent", new_id(cell.get("parent")))
        for key in ("source", "target"):
            if cell.get(key) in inside:
                cell.set(key, new_id(cell.get(key)))
        if c.get("netdiagrams_ref") in inside:
            c.set("netdiagrams_ref", new_id(c.get("netdiagrams_ref")))
        for node in (c, cell):
            for k, v in list(node.attrib.items()):
                if k in ("label", "value", "name", "tooltip", "device", "a_terminations", "b_terminations",
                         "tags", "location", "rack", "description", "virtual_chassis"):
                    node.set(k, rename(v))
        new.append(c)
    by_id = {el.get("id"): el for el in new}
    names = {i: el.get("name") for i, el in by_id.items() if sync._is_device(el)}
    gone = {i for i, n in names.items() if n not in nb.devices}
    # Lines take the copy's own NetBox cable, found by the two devices they join.
    for el in new:
        cell = cell_of(el)
        if cell is None or cell.get("edge") != "1" or el.get("cable_label") is None:
            continue
        ends = frozenset(names.get(cell.get(k)) or (g.els[cell.get(k)].get("name") if cell.get(k) in g.els else None)
                         for k in ("source", "target"))
        el.set("cable_label", ", ".join(sorted(pairs.get(ends, []))))
    # The copy's own place and uplinks replace the typical's notes.
    first = nb.devices.get(unit.switches[0], {})
    place = " · ".join(x for x in (_get(first, "location", "name"), _get(first, "rack", "name")) if x)
    root_copy = by_id.get(new_id(root))
    if root_copy is not None:
        g.set_value(root_copy, f"{html.escape(title)} · {html.escape(place)} "
                               f'<span style="color:#64748B;font-weight:normal">· built like the TYPICAL</span>')
    for el in new:
        if not sync._is_device(el) and "Uplinks" in plain(g.value(el)) and el.get("id") != new_id(root):
            g.set_value(el, "<b>Uplinks</b> " + html.escape(" · ".join(unit.uplinks) or "none in NetBox")
                        + "<br><b>Built like the TYPICAL</b>; ring, trunk and visibility notes as drawn there.")
    g.root.extend(new)
    g.reindex()
    if gone:
        g.remove(gone)
    heads = {n for i, n in names.items() if i not in gone and n in unit.endpoints}
    grouped = defaultdict(list)
    role = lambda n: _get(nb.devices[n], "role", "slug")
    for n in unit.endpoints:
        same = sorted(h for h in heads if role(h) == role(n))
        if n not in heads and same:
            grouped[same[0]].append(n)
    return layer, dict(grouped)


def _fill_copies(g: Graph, nb, copies: dict, groups: dict) -> None:
    """Fill every copy from NetBox in one pass, then label its counted groups."""
    from . import sync

    if not copies:
        return
    layers = set(copies.values())
    ids = {i for i in g.els if g.layer_id(i) in layers}
    view = _Only(g, ids)
    scratch = sync.Report()
    sync._fill_devices(view, nb, scratch)
    sync._fill_interfaces(view, nb, scratch)
    sync._fill_cables(view, nb, lambda n: n, scratch)
    sync._refresh_tags(view, nb, scratch)
    for key, layer in copies.items():
        sync._label_groups(_Only(g, {i for i in ids if g.layer_id(i) == layer}), groups[key], nb)


def _outside_name(g: Graph, el_id: str | None) -> str | None:
    el = g.els.get(el_id) if el_id else None
    return el.get("name") if el is not None else None


class _Only:
    """A view of a page limited to some elements, for helpers that walk every element."""

    def __init__(self, g: Graph, ids: set[str]):
        self._g, self.els = g, {i: g.els[i] for i in ids}

    def __getattr__(self, name):
        return getattr(self._g, name)


# ------------------------------------------------------- logical-page schedule
CELL_ZONE = re.compile(r"^zone-(cell|line|area)\d+$")
VLAN_COLUMNS = [("CELL", 80), ("VLANS", 300), ("SUBNETS", 330), ("GATEWAY · VRF", 200), ("DRAWING", 90)]


def schedule_card(g: Graph, like: str, title: str, subtitle: str, columns, rows, prefix: str) -> bool:
    """Draw a schedule card under the page's last Purdue band, making room for it; False if no band."""
    bands = [i for i, el in g.els.items() if g.layer_of(i) == profiles.current().band_layer
             and cell_of(el).get("vertex") == "1" and g.box(i)[2] > 1000
             and not (cell_of(el).get("style") or "").startswith("text")]
    if not bands:
        return False
    height = table_height(columns, rows, like_styles(g, like)["body"]) + 44 + 14
    last = max(bands, key=lambda b: g.box(b)[1] + g.box(b)[3])
    lx, ly, lw, lh = g.box(last)
    y = ly + lh + 16
    taken = [g.box(i) for i in g.els if g.layer_of(i).startswith("Schedules")
             and cell_of(g.els[i]).get("parent") == g.layer_id(i)]
    if taken:
        y = max(by + bh for _, by, _, bh in taken) + 16
    grow(g, lx, lx + lw, y - 0.5, height + 16)
    table_card(g, _schedule_layer(g), like, lx, y, title, subtitle, columns, rows, prefix)
    # Remembered on the card, so a rebuild from this drawing gives the room back first.
    g.wrap(f"{prefix}-card", netdiagrams_room=f"{height + 16:g}", netdiagrams_at=f"{y - 0.5:g},{lx:g},{lx + lw:g}")
    return True


def grow(g: Graph, x0: float, x1: float, y: float, delta: float) -> None:
    """Move what is below ``y`` in the column down by ``delta`` (up if negative), and the page border with it."""
    g.shift_below(x0, x1, y, delta, set())
    if delta < 0 and float(g.model.get("pageHeight", 0)) > -delta:  # shift_below only ever grows the page
        g.model.set("pageHeight", f"{float(g.model.get('pageHeight')) + delta:g}")
    border = next((i for i in g.els if g.layer_of(i).startswith("Border") and g.box(i)[2] > 2000), None)
    if border:
        geo = g.geometry(border)
        geo.set("height", f"{float(geo.get('height')) + delta:g}")


def _schedule_layer(g: Graph) -> str:
    layer = f"{g.diagram.get('id')}-schedules"
    if layer not in g.els:
        g.root.append(ET.Element("mxCell", {"id": layer, "value": "Schedules (copies of the typicals)",
                                            "style": "", "parent": "0"}))
        g.reindex()
    return layer


def vlan_schedule(g: Graph, nb, natural) -> int:
    """On the logical page: one row per cell zone with its VLANs, subnets and gateway.

    The template draws a VLAN table for the cells it has room for; the first
    becomes the TYPICAL and every cell (drawn or not) gets a row, so every
    routed subnet is still in exactly one zone on paper. Returns the cells added.
    """
    from .ot import vlan_zone
    from .sync import _gateway, _label, _zone_of_table

    tables = [t for t in g.tables() if g.header(t)[:2] == ["VLAN", "NAME"]]
    if not tables:
        return 0
    by_vlan = defaultdict(list)
    for p in nb.prefixes:
        if _get(p, "vlan", "id", default=None) is not None:
            by_vlan[p["vlan"]["id"]].append(p)
    zones = defaultdict(list)
    for v in nb.vlans:
        zone = vlan_zone(v, by_vlan.get(v.get("id")))
        if CELL_ZONE.match(zone):
            zones[zone].append(v)
    drawn = {_zone_of_table(g, t): t for t in tables}
    extra = [z for z in zones if z not in drawn]
    typical = next((drawn[z] for z in sorted(zones, key=natural) if z in drawn), None)
    if not extra or typical is None:
        return 0
    rows = []
    for zone in sorted(zones, key=natural):
        vlans = sorted(zones[zone], key=lambda v: v.get("vid", 0))
        prefixes = [(by_vlan.get(v.get("id")) or [{}])[0] for v in vlans]
        routed = next((p for p in prefixes if p.get("vrf")), prefixes[0])
        gw = _gateway(routed.get("prefix"), nb, _get(routed, "vrf", "id", default=None)) if routed else ""
        name = zone[5:].upper()
        rows.append([(name, nb.link("ipam/vlans", tag=zone)),
                     (" · ".join(f"{v.get('vid')} {v.get('name', '')}" for v in vlans), ""),
                     (" · ".join(p.get("prefix", "") for p in prefixes if p), ""),
                     (" · ".join(x for x in (gw, _label(routed.get("vrf"))) if x), ""),
                     ("drawn above" if zone in drawn else "as typical", "")])
    title = "Cell VLAN schedule"
    subtitle = (f"{len(zones)} cell zones. Each is built like the TYPICAL above, in its own VRF; "
                "every routed VLAN and subnet of every cell has a row.")
    if not schedule_card(g, typical, title, html.escape(subtitle), VLAN_COLUMNS, rows,
                         f"{g.diagram.get('id')}-vlan-schedule"):
        return 0
    zone_title = next((i for i, el in g.els.items()
                       if plain(g.value(el)).upper().startswith("ZONE " + zone_of(typical, g))), None)
    if zone_title is not None:
        g.set_value(g.els[zone_title], g.value(g.els[zone_title]) + typical_tag(len(zones), title))
    return len(extra)


def zone_of(table: str, g: Graph) -> str:
    from .sync import _zone_of_table
    return _zone_of_table(g, table)[5:].upper()
