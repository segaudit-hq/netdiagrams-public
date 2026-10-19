"""The riser sheet: the site's buildings, floors and closets, drawn from NetBox's location tree.

NetBox locations nest (campus › building › floor › closet or room). This sheet lays
each building out as a column of floors, top floor first as you would read a riser
diagram, with a card per closet or room on each floor, and draws the cables NetBox
records between closets, inside a building and between buildings. Nothing here is
template text: a card is a NetBox location, its counts are the devices NetBox puts
there, and a line is a count of NetBox cables.

The sheet is optional, like the "Site at a glance" page: it is added when the
site's locations nest and more than one of them holds network gear, and
``--riser`` / ``--no-riser`` force it either way.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import drawio, graph, ot, profiles
from .drawio import FONT, GAP, MARGIN, TEXT, Page
from .model import _get, _label
from .netbox_setup import ROLE_NAMES

PAGE_ID = "riser"
SHEET = "3e"
NAME = f"{SHEET} · Riser — buildings, floors and closets from NetBox"

CARD_W, CARD_H = 196, 56          # one closet or room (taller when its device list needs it)
FLOOR_LABEL_W = 72                # the floor's name, down the left of its band
BUILDING_HEAD = 34                # the building's title bar
FLOOR_PAD = 12
RUN = 7                           # between parallel cable runs
LIFT = 12                         # a run leaves a card this far above its top edge
ASPECT = 1.5                      # the buildings are packed into columns to about this width : height

CLOSET_STYLE = ("rounded=1;absoluteArcSize=1;arcSize=14;fillColor=#FFFFFF;strokeColor=#2563EB;strokeWidth=1.2;"
                "shadow=1;align=left;verticalAlign=top;spacing=7;fontSize=10;whiteSpace=wrap;html=1;"
                "overflow=hidden;" + FONT)
ROOM_STYLE = ("rounded=1;absoluteArcSize=1;arcSize=14;fillColor=#F8FAFC;strokeColor=#CBD5E1;strokeWidth=1;"
              "align=left;verticalAlign=top;spacing=7;fontSize=10;whiteSpace=wrap;html=1;overflow=hidden;" + FONT)
EMPTY_STYLE = ("rounded=1;absoluteArcSize=1;arcSize=14;fillColor=none;strokeColor=#CBD5E1;strokeWidth=1;dashed=1;"
               "dashPattern=4 3;align=left;verticalAlign=top;spacing=7;fontSize=10;fontColor=#94A3B8;"
               "whiteSpace=wrap;html=1;overflow=hidden;" + FONT)
FLOOR_STYLE = ("rounded=0;fillColor=#F8FAFC;strokeColor=#E2E8F0;strokeWidth=1;html=1;" + FONT)
BUILDING_STYLE = ("rounded=1;absoluteArcSize=1;arcSize=20;fillColor=#FFFFFF;strokeColor=#CBD5E1;strokeWidth=1.2;"
                  "html=1;" + FONT)
CABLE_STYLE = ("edgeStyle=none;rounded=1;arcSize=10;endArrow=none;"
               "startArrow=none;strokeColor=#64748B;strokeWidth=1.5;fontSize=9;fontColor=#334155;"
               "labelBackgroundColor=#FFFFFF;labelBorderColor=#E2E8F0;html=1;" + FONT)
BETWEEN_BUILDINGS = "strokeColor=#2563EB;strokeWidth=2;"
RADIO = "dashed=1;dashPattern=6 4;strokeColor=#7C3AED;strokeWidth=1.5;"

ROOF = re.compile(r"\b(roof|rooftop|penthouse)\b", re.I)
BELOW = re.compile(r"\b(lower level|basement|cellar|sub-?level|underground|b1|ll)\b", re.I)
FLOOR_NUMBER = re.compile(r"(?:floor|level|fl|storey|story)\s*(-?\d+)|(-?\d+)(?:st|nd|rd|th)?\s*(?:floor|level)",
                          re.I)


@dataclass
class Node:
    """A location on the sheet: a closet or room card, or the floor or building it sits on."""
    loc: dict
    children: list = field(default_factory=list)
    devices: list = field(default_factory=list)
    inside: list = field(default_factory=list)   # ids of the rooms within this card's room, drawn as part of it

    @property
    def id(self):
        return self.loc.get("id")

    @property
    def name(self) -> str:
        return _label(self.loc) or str(self.id)


def wanted(export: dict, endpoint_roles: set[str]) -> bool:
    """Nested locations, with network gear in more than one of them."""
    locations = export.get("locations") or []
    if not any((loc.get("parent") or {}).get("id") is not None for loc in locations):
        return False
    with_gear = {_get(d, "location", "id", default=None) for d in export.get("devices", [])
                 if d.get("location") and _get(d, "role", "slug") not in endpoint_roles}
    return len(with_gear - {None}) >= 2


def floor_key(name: str, fallback: int) -> float:
    """Higher floors sort first: roof above numbered floors, below-ground floors last."""
    if ROOF.search(name):
        return 1000
    if BELOW.search(name):
        return -1
    m = FLOOR_NUMBER.search(name)
    if m:
        return float(m.group(1) or m.group(2))
    return -100 - fallback   # no floor number: keep NetBox's order, under the numbered floors


def tree(export: dict) -> list[Node]:
    """Buildings (top-level locations, or a sole campus root's children), each with its locations."""
    locations = [loc for loc in export.get("locations") or [] if loc.get("id") is not None]
    nodes = {loc["id"]: Node(loc) for loc in locations}
    roots = []
    for loc in locations:
        parent = nodes.get((loc.get("parent") or {}).get("id"))
        (parent.children if parent else roots).append(nodes[loc["id"]])
    for d in export.get("devices", []):
        node = nodes.get(_get(d, "location", "id", default=None))
        if node is not None:
            node.devices.append(d)
    # Floors straight under the site (Floor 2 › COMMS-2, Floor 3 › IDF-3) are one building's, not
    # one building each; and a sole root whose children are floors is that building, not a campus.
    if roots and all(is_floor(r.name) for r in roots):
        site = export.get("site") or {}
        return [Node({"id": None, "name": _label(site) or site.get("slug") or "Building"}, children=roots)]
    if len(roots) == 1 and roots[0].children and not all(is_floor(c.name) for c in roots[0].children) \
            and any(c.children for c in roots[0].children):
        roots = roots[0].children  # a campus root over the buildings
    return roots


def is_floor(name: str) -> bool:
    """A location named like a floor: 'Floor 2', 'Level -1', 'Roof', 'Basement'."""
    return bool(ROOF.search(name) or BELOW.search(name) or FLOOR_NUMBER.search(name))


def _folded(closet: Node) -> Node:
    """A closet with rooms inside it (IDF-1 › Rack room 1) is one card holding their devices too."""
    if not closet.children:
        return closet
    devices, inside, todo, seen = list(closet.devices), [], list(closet.children), set()
    while todo:
        node = todo.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        devices += node.devices
        inside.append(node.id)
        todo += node.children
    return Node(closet.loc, devices=devices, inside=inside)


def _floors(building: Node) -> list[tuple[Node | None, list[Node]]]:
    """(floor, closets) from the top floor down; closets with no floor sit on the building's own row."""
    floors = [(c, [_folded(k) for k in c.children]) for c in building.children if c.children]
    loose = [c for c in building.children if not c.children]
    for floor, closets in floors:
        if floor.devices:  # gear at the floor itself, not in a named closet
            closets.insert(0, Node(dict(floor.loc, name=f"{floor.name} (floor)"), devices=floor.devices))
    if loose or building.devices or not floors:
        closets = list(loose)
        if building.devices:
            closets.insert(0, Node(dict(building.loc, name=f"{building.name} (building)"), devices=building.devices))
        floors.append((None, closets))
    order = {id(f): n for n, (f, _) in enumerate(floors)}
    floors.sort(key=lambda fc: -(floor_key(fc[0].name, order[id(fc[0])]) if fc[0] else -10_000))
    return floors


def _floor_count(floors: list) -> str:
    """The floor locations NetBox has; rooms straight under the building are not a floor."""
    n = sum(1 for floor, _ in floors if floor is not None)
    return f"{n} floor{'s' if n != 1 else ''}" if n else "no floor locations"


def _counts(devices: list[dict], endpoint_roles: set[str]) -> str:
    roles = Counter(_get(d, "role", "slug") for d in devices)
    net = sorted((r for r in roles if r not in endpoint_roles), key=lambda r: (-roles[r], r))
    end = sorted((r for r in roles if r in endpoint_roles), key=lambda r: (-roles[r], r))
    name = lambda r: html.escape(profiles.role_name(r, ROLE_NAMES))
    parts = [f"{name(r)} ×{roles[r]}" for r in net + end]
    return " · ".join(parts)


def _card_lines(closet: Node, endpoint_roles: set[str], racks: set[str]) -> tuple[list[str], float]:
    """A card's label lines and the height they need."""
    gear = [d for d in closet.devices if _get(d, "role", "slug") not in endpoint_roles]
    lines = [f'<b style="color:{"#1D4ED8" if gear else "#334155"}">{html.escape(closet.name)}</b>']
    lines_of = lambda text, size, bold=False: graph.text_lines(text, CARD_W, size, spacing=14, bold=bold)
    head = lines_of(closet.name, 10, True)   # a long room name wraps
    rows = 0
    if closet.devices:
        counts = _counts(closet.devices, endpoint_roles)
        lines.append(f'<span style="font-size:9px;color:#334155">{counts}</span>')
        rows += lines_of(html.unescape(counts), 9)
    if racks:
        text = "Rack " + ", ".join(sorted(racks))
        lines.append(f'<span style="font-size:9px;color:#64748B">{html.escape(text)}</span>')
        rows += lines_of(text, 9)
    if not closet.devices:
        lines.append('<span style="font-size:9px">no devices in NetBox</span>')
        rows += 1
    return lines, max(CARD_H, 14 + 16 + 13 * (head - 1) + 12 * rows + 10)


def _runs(export: dict) -> dict:
    """(location id a, location id b, kind) -> the NetBox cables or wireless links between them."""
    loc_of = {d.get("id"): _get(d, "location", "id", default=None) for d in export.get("devices", [])}
    loc_by_name = {d.get("name"): _get(d, "location", "id", default=None) for d in export.get("devices", [])}
    runs: dict = defaultdict(list)

    def add(kind, a, b, item):
        if a is not None and b is not None and a != b:
            runs[(min(a, b), max(a, b), kind)].append(item)

    for c in export.get("cables", []):
        ends = []
        for side in ("a_terminations", "b_terminations"):
            for t in c.get(side) or []:
                dev = ((t.get("object") or {}).get("device") or {}).get("id")
                if dev in loc_of:
                    ends.append(loc_of[dev])
                    break
        if len(ends) == 2:
            add("cable", ends[0], ends[1], c)
    for w in export.get("wireless_links") or []:
        ends = []
        for side in ("interface_a", "interface_b"):
            dev = (w.get(side) or {}).get("device") or {}
            ends.append(loc_of.get(dev.get("id"), loc_by_name.get(dev.get("name"))))
        add("radio", ends[0], ends[1], w)
    return runs


def _run_label(kind: str, items: list[dict]) -> tuple[str, str]:
    """The label on a run and the tooltip behind it."""
    n = len(items)
    if kind == "radio":
        ssids = sorted({w.get("ssid") for w in items if w.get("ssid")})
        label = f"{n} × radio link" + (f" · {', '.join(ssids[:2])}" if ssids else "")
        tip = f"{n} wireless link{'s' if n != 1 else ''} between these locations in NetBox"
        for w in items[:10]:
            a, b = (((w.get(side) or {}).get("device") or {}).get("name", "?") for side in ("interface_a", "interface_b"))
            tip += f"\n{a} ↔ {b}" + (f" · {w['ssid']}" if w.get("ssid") else "")
        return label, tip
    media = Counter(drawio.CABLE_MEDIA.get(c.get("type") or "", ("", c.get("type") or ""))[1] for c in items)
    kinds = " · ".join(f"{k} × {m}" if m else f"{k}" for m, k in media.most_common())
    label = kinds if len(media) == 1 and list(media)[0] else f"{n} cables" + (f" · {kinds}" if list(media)[0] else "")
    names = ", ".join(c.get("label") or f"cable {c.get('id')}" for c in items[:10])
    tip = (f"{n} cable{'s' if n != 1 else ''} between these locations in NetBox\n{names}"
           + (f"\n… and {n - 10} more" if n > 10 else ""))
    return label, tip


def _overlaps(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _pack(sizes: list[tuple[float, float]]) -> list[list[int]]:
    """Buildings into columns of about ASPECT width : height; short buildings share a column."""
    if not sizes:
        return []
    area = sum(w * h for w, h in sizes)
    target = max(max(h for _, h in sizes), (area / ASPECT) ** 0.5)
    columns: list[list[int]] = []
    heights: list[float] = []
    for i in sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], i)):
        for c, h in enumerate(heights):
            if h + 2 * GAP + sizes[i][1] <= target:
                columns[c].append(i)
                heights[c] = h + 2 * GAP + sizes[i][1]
                break
        else:
            columns.append([i])
            heights.append(sizes[i][1])
    return columns


def page(export: dict, endpoint_roles: set[str], netbox_url: str = "", site_code: str = "") -> ET.Element:
    """The riser sheet as a <diagram>; the caller adds the title block.

    Each building is a box of floor bands with a card per closet or room. Runs between
    cards never cross a card: a run leaves the top of its card into the gap above the
    row, reaches the building's shaft (the strip between the floor names and the cards)
    to change floors, and, to reach another building, drops down the gutter beside its
    column to a ground line under the buildings and climbs the other building the same
    way. Every parallel run gets its own offset so the labels stay apart.
    """
    p = Page(PAGE_ID, NAME)
    titles, l_buildings, l_floors, l_closets, l_cables = (p.layer(n) for n in (
        "Titles", "Buildings", "Floors", "Closets & rooms", "Cables between closets"))
    buildings = tree(export)
    locations = ot.Locations(export.get("locations"))
    site_name = _label(export.get("site")) or site_code or "Site"
    drawio._title(p, titles, f"{site_name} — Riser", "")   # the first cell: the title, for the site code prefix
    subtitle_cell = p.cells[-1]
    racks: dict = defaultdict(set)
    for d in export.get("devices", []):
        if d.get("rack"):
            racks[_get(d, "location", "id", default=None)].add(_label(d["rack"]))
    # A run to a room inside a closet is a run to the closet's card.
    card_of = {i: c.id for b in buildings for _, closets in _floors(b) for c in closets for i in c.inside}
    runs: dict = defaultdict(list)
    for (a, b, kind), items in _runs(export).items():
        a, b = card_of.get(a, a), card_of.get(b, b)
        if a != b:
            runs[(min(a, b), max(a, b), kind)] += items
    touching: Counter = Counter()          # location id -> runs that start or end there
    for a, b, _ in runs:
        touching[a] += 1
        touching[b] += 1

    # Measure each building: its floors, the rows of cards on each, and the room the runs need.
    plans = []
    for building in buildings:
        floors = _floors(building)
        per_row = min(4, max(1, max((len(c) for _, c in floors), default=1)))
        bands = []
        for floor, closets in floors:
            rows = []
            for r in range(0, len(closets), per_row):
                chunk = closets[r:r + per_row]
                cards = [(c,) + _card_lines(c, endpoint_roles, racks.get(c.id) or set()) for c in chunk]
                gap = LIFT + RUN * max(1, sum(touching[c.id] for c in chunk)) + 4 + 18 * bool(r)  # room for labels
                rows.append((cards, max(h for _, _, h in cards), gap))
            if not rows:
                rows.append(([], CARD_H, GAP))
            band_h = sum(h + gap for _, h, gap in rows) + GAP
            bands.append((floor, rows, band_h))
        shafts = sum(1 for a, b, _ in runs if any(c.id in (a, b) for _, cs in floors for c in cs))
        shaft_w = 20 + RUN * shafts  # the last shaft run keeps clear of the first card
        bw = FLOOR_LABEL_W + shaft_w + per_row * (CARD_W + GAP) + GAP
        bh = BUILDING_HEAD + sum(b for _, _, b in bands) + FLOOR_PAD * (len(bands) + 1)
        plans.append((building, floors, bands, per_row, shaft_w, bw, bh))

    # Pack the buildings into columns, with a gutter beside each column for the runs between buildings.
    columns = _pack([(bw, bh) for *_, bw, bh in plans])
    column_of = {i: c for c, col in enumerate(columns) for i in col}
    gutter_runs = Counter()
    loc_building = {c.id: i for i, (_, floors, *_) in enumerate(plans) for _, cs in floors for c in cs}
    for a, b, _ in runs:
        ba, bb = loc_building.get(a), loc_building.get(b)
        if ba is not None and bb is not None and ba != bb and column_of[ba] != column_of[bb]:
            ca, cb = sorted((column_of[ba], column_of[bb]))
            for col in ({cb} if cb == ca + 1 else {ca, cb}):
                gutter_runs[col] += 1
    x = MARGIN
    origin: dict = {}   # building index -> (x, y)
    col_x: dict = {}
    for c, col in enumerate(columns):
        gutter = 16 + RUN * gutter_runs[c]
        x += gutter
        col_x[c] = x
        y = 96
        for i in col:
            origin[i] = (x, y)
            y += plans[i][6] + 2 * GAP
        x += max(plans[i][5] for i in col) + GAP
    bottom = max((origin[i][1] + plans[i][6] for i in origin), default=96)

    # Draw the buildings.
    cards: dict = {}        # location id -> card id
    geo: dict = {}          # card id -> (x, y, w, h)
    row_of: dict = {}       # card id -> row key, for the lift levels
    building_of: dict = {}  # card id -> building index
    shaft_x: dict = {}      # building index -> x of its first shaft run
    n_floors = n_cards = 0
    for i, (building, floors, bands, per_row, shaft_w, bw, bh) in enumerate(plans):
        x, y = origin[i]
        box = ET.Element("object", {"id": p.new_id(), "label": "",
                                    "netdiagrams_building": "" if building.id is None else str(building.id),
                                    "tooltip": (f"NetBox location {building.name}" if building.id is not None
                                                else f"{building.name}: floors straight under the site")
                                    + f": {_floor_count(floors)}"})
        if netbox_url and building.id is not None:
            box.set("link", f"{netbox_url}/dcim/locations/{building.id}/")
            box.set("linkTarget", "_blank")
        cell = ET.SubElement(box, "mxCell", {"style": BUILDING_STYLE, "vertex": "1", "parent": l_buildings})
        ET.SubElement(cell, "mxGeometry", {"x": f"{x:g}", "y": f"{y:g}", "width": f"{bw:g}", "height": f"{bh:g}",
                                           "as": "geometry"})
        p.cells.append(box)
        total = sum(len(c.devices) for _, cs in floors for c in cs)
        p.box(l_buildings, x + 14, y + 7, bw - 28, 22,
              f'<b style="color:#0F172A">{html.escape(building.name)}</b>'
              f'<span style="color:#64748B"> · {_floor_count(floors)} · '
              f'{total} device{"s" if total != 1 else ""}</span>',
              TEXT + "fontSize=12;verticalAlign=middle;")
        shaft_x[i] = x + 8 + FLOOR_LABEL_W + 6
        fy = y + BUILDING_HEAD + FLOOR_PAD
        for floor, rows, band_h in bands:
            n_floors += floor is not None
            p.box(l_floors, x + 8, fy, bw - 16, band_h, "", FLOOR_STYLE)
            p.box(l_floors, x + 8, fy + 6, FLOOR_LABEL_W - 8, band_h - 12,
                  html.escape(floor.name if floor else "—"),
                  "text;html=1;fontSize=10;fontStyle=1;fontColor=#475569;align=center;verticalAlign=middle;"
                  "whiteSpace=wrap;" + FONT)
            ry = fy
            for r, (row_cards, row_h, gap) in enumerate(rows):
                ry += gap
                for k, (closet, lines, h) in enumerate(row_cards):
                    cx = x + 8 + FLOOR_LABEL_W + shaft_w + k * (CARD_W + GAP)
                    gear = any(_get(d, "role", "slug") not in endpoint_roles for d in closet.devices)
                    style = CLOSET_STYLE if gear else ROOM_STYLE if closet.devices else EMPTY_STYLE
                    names = sorted(d.get("name", "?") for d in closet.devices)
                    shown = ", ".join(names[:12]) + (f" … and {len(names) - 12} more" if len(names) > 12 else "")
                    card = ET.Element("object", {
                        "id": p.new_id(), "label": "<br>".join(lines), "netdiagrams_location": str(closet.id),
                        "devices": str(len(closet.devices)),
                        "tooltip": f"{locations.path(closet.loc)}: "
                                   f"{len(closet.devices)} devices" + (f"\n{shown}" if shown else "")})
                    if netbox_url and closet.devices:
                        card.set("link", f"{netbox_url}/dcim/devices/?location_id={closet.id}")
                        card.set("linkTarget", "_blank")
                    elif netbox_url:
                        card.set("link", f"{netbox_url}/dcim/locations/{closet.id}/")
                        card.set("linkTarget", "_blank")
                    cell = ET.SubElement(card, "mxCell", {"style": style, "vertex": "1", "parent": l_closets})
                    ET.SubElement(cell, "mxGeometry", {"x": f"{cx:g}", "y": f"{ry:g}", "width": f"{CARD_W:g}",
                                                       "height": f"{row_h:g}", "as": "geometry"})
                    p.cells.append(card)
                    n_cards += 1
                    cards.setdefault(closet.id, card.get("id"))
                    geo[card.get("id")] = (cx, ry, CARD_W, row_h)
                    row_of[card.get("id")] = (i, ry)
                    building_of[card.get("id")] = i
                ry += row_h
            fy += band_h + FLOOR_PAD

    # The runs: cables and radio links between cards, counted per pair.
    lifts: Counter = Counter()      # row key -> levels used above that row
    shafts: Counter = Counter()     # building -> shaft runs used
    gutters: Counter = Counter()    # column -> gutter runs used
    grounds = 0                     # runs along the ground line
    below: Counter = Counter()      # building -> runs leaving under it
    exits: Counter = Counter()      # card -> runs leaving its top, each at its own x
    labels: Counter = Counter()     # card -> run labels stacked above it
    placed: list = []               # run labels drawn so far, as (x, y, w, h)
    n_runs = n_cables = between_buildings = radio_runs = 0

    def lift(card):
        key = row_of[card]
        level = lifts[key]
        lifts[key] += 1
        return geo[card][1] - LIFT - RUN * level

    ordered = sorted(((cards.get(a), cards.get(b), kind, items) for (a, b, kind), items in runs.items()
                      if cards.get(a) and cards.get(b)),
                     key=lambda r: (geo[r[0]][1], geo[r[0]][0], geo[r[1]][1], geo[r[1]][0], r[2]))
    per_card = Counter(c for a, b, _, _ in ordered for c in (a, b))   # runs at each card: its labels clear their lines
    rooms = {id(items): (a, b) for (a, b, _), items in runs.items()}
    for a, b, kind, items in ordered:
        a_loc, b_loc = rooms[id(items)]
        if geo[a][1:2] + (building_of[a],) > geo[b][1:2] + (building_of[b],) or (
                geo[a][1] == geo[b][1] and geo[a][0] > geo[b][0]):
            a, b = b, a
        label, tip = _run_label(kind, items)
        holder = ET.Element("object", {"id": p.new_id(), "label": html.escape(label), "tooltip": tip,
                                       "netdiagrams_cables" if kind == "cable" else "netdiagrams_radio": str(len(items))})
        if netbox_url and all(it.get("id") for it in items):
            path = "dcim/cables" if kind == "cable" else "wireless/wireless-links"
            # Past 50 ids the link would be too long for some proxies: the two rooms' cables instead.
            query = "&".join(f"id={it['id']}" for it in items) if len(items) <= 50 or kind != "cable" else \
                "&".join(f"location_id={i}" for i in sorted({a_loc, b_loc}, key=str))
            holder.set("link", f"{netbox_url}/{path}/?{query}")
            holder.set("linkTarget", "_blank")
        ba, bb = building_of[a], building_of[b]
        style = CABLE_STYLE + (BETWEEN_BUILDINGS if ba != bb else "") + (RADIO if kind == "radio" else "")
        (ax, ay, aw, _), (bx, by, bw_, _) = geo[a], geo[b]
        acx = ax + aw / 2 - 12 + RUN * exits[a]
        bcx = bx + bw_ / 2 - 12 + RUN * exits[b]
        exits[a] += 1
        exits[b] += 1
        style += f"exitX={(acx - ax) / aw:.3f};exitY=0;entryX={(bcx - bx) / bw_:.3f};entryY=0;"
        if row_of[a] == row_of[b]:
            la = lift(a)
            points = [(acx, la), (bcx, la)]
        elif ba == bb:
            la, lb = lift(a), lift(b)
            sx = shaft_x[ba] + RUN * shafts[ba]
            shafts[ba] += 1
            points = [(acx, la), (sx, la), (sx, lb), (bcx, lb)]
        else:
            la, lb = lift(a), lift(b)
            sa = shaft_x[ba] + RUN * shafts[ba]
            sb = shaft_x[bb] + RUN * shafts[bb]
            shafts[ba] += 1
            shafts[bb] += 1
            ya = origin[ba][1] + plans[ba][6] + 6 + RUN * below[ba]
            yb = origin[bb][1] + plans[bb][6] + 6 + RUN * below[bb]
            below[ba] += 1
            below[bb] += 1
            ca, cb = column_of[ba], column_of[bb]
            points = [(acx, la), (sa, la), (sa, ya)]
            if ca == cb:
                # one above the other: across the gap between them, then down the lower one's shaft
                top = ba if origin[ba][1] < origin[bb][1] else bb
                yc = origin[top][1] + plans[top][6] + 6 + RUN * (below[top] - 1)
                points = [(acx, la), (sa, la), (sa, yc), (sb, yc), (sb, lb), (bcx, lb)]
            elif abs(ca - cb) == 1:
                # side by side: under each building to the gutter between their columns
                right = max(ca, cb)
                gx = col_x[right] - 10 - RUN * gutters[right]
                gutters[right] += 1
                points += [(gx, ya), (gx, yb)]
            else:
                ga = col_x[ca] - 10 - RUN * gutters[ca]
                gutters[ca] += 1
                points += [(ga, ya)]
                gb = col_x[cb] - 10 - RUN * gutters[cb]
                gutters[cb] += 1
                yg = bottom + 2 * GAP + 10 + 2 * RUN * grounds
                grounds += 1
                points += [(ga, yg), (gb, yg), (gb, yb)]
            if ca != cb:
                points += [(sb, yb), (sb, lb), (bcx, lb)]
            between_buildings += 1
        edge = ET.SubElement(holder, "mxCell", {"style": style, "edge": "1", "parent": l_cables, "source": a, "target": b})
        geometry = ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})
        # The label sits above a horizontal stretch next to one of the two cards, never at the path's
        # middle (the vertical shaft, where it would lie across the floor card beside it). Each card
        # takes the labels of the runs leaving it in a stack, and a run labels the end with fewer so far.
        path = [(acx, ay)] + points + [(bcx, by)]
        lengths = [abs(x2 - x1) + abs(y2 - y1) for (x1, y1), (x2, y2) in zip(path, path[1:])]
        total = sum(lengths) or 1
        end = a if labels[a] <= labels[b] else b
        if end == a:
            along, stretch = lengths[0] + lengths[1] / 2, (path[1], path[2])
        else:
            along, stretch = total - lengths[-1] - lengths[-2] / 2, (path[-3], path[-2])
        slot = labels[end]
        labels[end] += 1
        lift_px = 8 + RUN * per_card[end] + 16 * slot  # a label is about 14 px tall
        # labels of other cards' runs can share this height: lift this one clear of them
        lx, ly = (stretch[0][0] + stretch[1][0]) / 2, stretch[0][1]
        lw = len(label) * 4.9 + 10
        tries = [lift_px + d for k in range(1, 6) for d in (16 * (k - 1), -16 * k)]
        lift_px = next((t for t in tries if not any(_overlaps((lx - lw / 2, ly - t - 7, lw, 14), r)
                                                    for r in placed + list(geo.values()))), lift_px)
        placed.append((lx - lw / 2, ly - lift_px - 7, lw, 14))
        rightward = stretch[1][0] >= stretch[0][0]   # draw.io offsets a label across the line's direction
        geometry.set("x", f"{max(-1.0, min(1.0, 2 * along / total - 1)):.3f}")
        geometry.set("y", f"{lift_px if rightward else -lift_px:g}")
        array = ET.SubElement(geometry, "Array", {"as": "points"})
        for px, py in points:
            ET.SubElement(array, "mxPoint", {"x": f"{px:g}", "y": f"{py:g}"})
        p.cells.append(holder)
        n_runs += 1
        n_cables += len(items) if kind == "cable" else 0
        radio_runs += kind == "radio"

    if buildings:
        subtitle = (f"{len(buildings)} building{'s' if len(buildings) != 1 else ''} · "
                    + (f"{n_floors} floor{'s' if n_floors != 1 else ''}" if n_floors else "no floor locations")
                    + f" · "
                    f"{n_cards} closets and rooms · {n_cables} cables between them"
                    + (f", {radio_runs} radio link{'s' if radio_runs != 1 else ''}" if radio_runs else "")
                    + (f", {between_buildings} runs between buildings" if between_buildings else "")
                    + ". Floors read top to bottom as in the building. Blue cards hold network gear; "
                      "click a card for its devices in NetBox, a line for its cables.")
    else:
        subtitle = ("NetBox has no locations for this site. Add buildings, floors and closets under "
                    "Organization ▸ Locations (parent = the floor or building) and put each device in its room.")
    subtitle_cell.set("value", html.escape(subtitle))
    page_w = max(drawio.PAGE_W, int(max((gx + gw for gx, _, gw, _ in geo.values()), default=0) + 2 * MARGIN + 40))
    if grounds:  # the ground band, so the runs between buildings read as one thing and nothing lands on them
        p.box(l_cables, MARGIN, bottom + 2 * GAP, page_w - 2 * MARGIN, 2 * RUN * grounds + 16,
              "ground · runs between buildings",
              "text;html=1;fontSize=9;fontColor=#94A3B8;align=right;verticalAlign=bottom;spacingRight=4;" + FONT)
    p.height = bottom + 2 * GAP + 2 * RUN * grounds + 28
    diagram = p.element()
    diagram.find("mxGraphModel").set("pageWidth", str(page_w))
    return diagram
