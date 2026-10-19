"""Small helpers for reading and editing one draw.io page."""

from __future__ import annotations

import copy
import html
import itertools
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict


def cell_of(el: ET.Element) -> ET.Element | None:
    return el if el.tag == "mxCell" else el.find("mxCell")


def plain(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def font_size(style: str, default: float = 9) -> float:
    m = re.search(r"fontSize=([\d.]+)", style or "")
    return float(m.group(1)) if m else default


# Advance widths of Inter Regular per em, measured from the font, so a cell's text wraps on the
# drawing where the estimate says it does (a class-average guess under-measured capitals by 15%).
INTER_WIDTHS = {
    ' ': 0.281, '!': 0.288, '"': 0.466, '#': 0.633, '$': 0.642, '%': 0.982, '&': 0.644, "'": 0.3, '(': 0.365,
    ')': 0.365, '*': 0.501, '+': 0.662, ',': 0.288, '-': 0.46, '.': 0.288, '/': 0.36, '0': 0.631, '1': 0.407,
    '2': 0.61, '3': 0.618, '4': 0.646, '5': 0.608, '6': 0.62, '7': 0.566, '8': 0.619, '9': 0.62, ':': 0.288,
    ';': 0.302, '<': 0.662, '=': 0.662, '>': 0.662, '?': 0.511, '@': 0.966, 'A': 0.69, 'B': 0.654, 'C': 0.73,
    'D': 0.722, 'E': 0.601, 'F': 0.59, 'G': 0.746, 'H': 0.743, 'I': 0.269, 'J': 0.571, 'K': 0.672, 'L': 0.565,
    'M': 0.903, 'N': 0.753, 'O': 0.765, 'P': 0.639, 'Q': 0.765, 'R': 0.644, 'S': 0.642, 'T': 0.646, 'U': 0.744,
    'V': 0.69, 'W': 0.985, 'X': 0.682, 'Y': 0.679, 'Z': 0.629, '[': 0.365, '\\': 0.36, ']': 0.365, '^': 0.471,
    '_': 0.456, '`': 0.323, 'a': 0.562, 'b': 0.612, 'c': 0.571, 'd': 0.612, 'e': 0.583, 'f': 0.37, 'g': 0.613,
    'h': 0.591, 'i': 0.242, 'j': 0.242, 'k': 0.549, 'l': 0.242, 'm': 0.876, 'n': 0.591, 'o': 0.6, 'p': 0.612,
    'q': 0.612, 'r': 0.376, 's': 0.528, 't': 0.327, 'u': 0.591, 'v': 0.562, 'w': 0.818, 'x': 0.546, 'y': 0.562,
    'z': 0.552, '{': 0.426, '|': 0.333, '}': 0.426, '~': 0.662, '·': 0.288, '–': 0.5, '—': 1.0, '×': 0.662, '→':
    0.954, '↑': 0.834, '↓': 0.834, '⇄': 0.656, '‹': 0.384, '›': 0.384, '°': 0.456, '€': 0.666, '£': 0.611, '…':
    0.864
}


BOLD_FACTOR = 1.04  # Inter Bold runs about 4% wider than Regular


def text_width(text: str, size: float = 9, bold: bool = False) -> float:
    """How wide a run of text draws in Inter at this size."""
    width = sum(INTER_WIDTHS.get(ch, 0.68 if ch.isupper() else 0.6 if ch.isdigit() else 0.54) for ch in text) * size
    return width * BOLD_FACTOR if bold else width


def text_lines(text: str, width: float, size: float = 9, spacing: float = 6, bold: bool = False) -> int:
    """How many lines a cell's text takes at this width, wrapping where draw.io does: at a space, or
    after a hyphen (a hostname such as W01-IT-ACC-IDF2-2 breaks after its last hyphen)."""
    usable = max(12.0, width - spacing - 2)
    lines = 0
    for part in re.split(r"<br\s*/?>", text or ""):
        words = re.split(r" |(?<=-)(?=[^\s-])", plain(part))
        line_w, count, prev_hyphen = 0.0, 1, False
        for w in words:
            ww = text_width(w, size, bold)
            space = text_width(" ", size) if line_w and not prev_hyphen else 0
            if line_w and line_w + space + ww > usable:
                count += 1
                line_w = ww
            else:
                line_w += space + ww
            while line_w > usable:  # a word longer than the cell breaks mid-word
                count += 1
                line_w -= usable
            prev_hyphen = w.endswith("-")
        lines += count
    return max(1, lines)


def row_height(cells: list[tuple], size: float = 9, base: float = 18) -> float:
    """The height a table row needs: its base height, or more when a cell wraps.

    Each cell is (text, width) or (text, width, bold)."""
    lines = max((text_lines(c[0], c[1], size, bold=bool(c[2:] and c[2])) for c in cells), default=1)
    return max(base, 5 + lines * round(size * 1.3))


class Graph:
    def __init__(self, diagram: ET.Element):
        self.diagram = diagram
        self.name = diagram.get("name", "")
        self.model = diagram.find("mxGraphModel")
        self.root = self.model.find("root")
        self.reindex()

    def reindex(self) -> None:
        self.cache: dict = {}  # per-page lookups that any structural change invalidates
        self.els: dict[str, ET.Element] = {}
        self.children: dict[str, list[str]] = defaultdict(list)
        for el in self.root:
            if el.get("id"):
                self.els[el.get("id")] = el
        for el_id, el in self.els.items():
            cell = cell_of(el)
            if cell is not None and cell.get("parent"):
                self.children[cell.get("parent")].append(el_id)
        self.layers = {i: e.get("value", "") for i, e in self.els.items()
                       if e.tag == "mxCell" and e.get("parent") == "0"}

    # values -------------------------------------------------------------
    @staticmethod
    def value(el: ET.Element) -> str:
        return (el.get("label") if el.tag in ("object", "UserObject") else el.get("value")) or ""

    @staticmethod
    def set_value(el: ET.Element, value: str) -> None:
        el.set("label" if el.tag in ("object", "UserObject") else "value", value)

    def wrap(self, el_id: str, **attrs: str) -> ET.Element:
        """Turn a plain mxCell into an <object> so it can carry data and a link."""
        el = self.els[el_id]
        if el.tag != "mxCell":
            for k, v in attrs.items():
                el.set(k, v)
            return el
        obj = ET.Element("object", {"id": el_id, "label": el.get("value", ""), **attrs})
        index = list(self.root).index(el)
        cell = copy.deepcopy(el)
        cell.attrib.pop("id", None)
        cell.attrib.pop("value", None)
        obj.append(cell)
        self.root.remove(el)
        self.root.insert(index, obj)
        self.els[el_id] = obj
        return obj

    # structure ------------------------------------------------------------
    def layer_of(self, el_id: str) -> str:
        for _ in range(50):
            el = self.els.get(el_id)
            cell = cell_of(el) if el is not None else None
            if cell is None:
                return ""
            parent = cell.get("parent")
            if parent in self.layers:
                return self.layers[parent]
            el_id = parent
        return ""

    def layer_id(self, el_id: str) -> str:
        for _ in range(50):
            el = self.els.get(el_id)
            cell = cell_of(el) if el is not None else None
            if cell is None:
                return ""
            if cell.get("parent") in self.layers:
                return cell.get("parent")
            el_id = cell.get("parent")
        return ""

    def hidden(self, el_id: str) -> bool:
        """On a layer that is switched off."""
        layer = self.els.get(self.layer_id(el_id))
        return layer is not None and layer.get("visible") == "0"

    def geometry(self, el_id: str) -> ET.Element | None:
        cell = cell_of(self.els[el_id])
        return cell.find("mxGeometry") if cell is not None else None

    def box(self, el_id: str) -> tuple[float, float, float, float]:
        """Absolute x, y, width, height of a vertex."""
        geo = self.geometry(el_id)
        if geo is None:
            return 0, 0, 0, 0
        x, y = float(geo.get("x", 0)), float(geo.get("y", 0))
        w, h = float(geo.get("width", 0)), float(geo.get("height", 0))
        parent = cell_of(self.els[el_id]).get("parent")
        if parent in self.els and parent not in self.layers and cell_of(self.els[parent]).get("vertex") == "1":
            px, py, _, _ = self.box(parent)
            x, y = x + px, y + py
        return x, y, w, h

    def descendants(self, el_id: str) -> list[str]:
        out, stack = [], list(self.children.get(el_id, []))
        while stack:
            child = stack.pop()
            out.append(child)
            stack.extend(self.children.get(child, []))
        return out

    def remove(self, el_ids) -> set[str]:
        """Remove elements, their children, and any edge attached to them."""
        doomed: set[str] = set()
        for el_id in el_ids:
            if el_id in self.els:
                doomed.add(el_id)
                doomed.update(self.descendants(el_id))
        for el_id, el in self.els.items():
            cell = cell_of(el)
            if cell is not None and cell.get("edge") == "1" and (
                    cell.get("source") in doomed or cell.get("target") in doomed):
                doomed.add(el_id)
                doomed.update(self.descendants(el_id))
        for el_id in doomed:
            el = self.els.get(el_id)
            if el is not None and el in list(self.root):
                self.root.remove(el)
        self.reindex()
        return doomed

    def shift_below(self, x0: float, x1: float, y_from: float, delta: float, skip: set[str]) -> None:
        """Move top-level shapes in a column down (or up) to make room for a taller table.

        Lines move with them: every bend point and free line end in the column below
        ``y_from`` moves too.
        """
        if not delta:
            return
        edges, shapes = [], []
        for el_id, el in self.els.items():
            cell = cell_of(el)
            if el_id in skip or cell is None or cell.get("parent") not in self.layers:
                continue
            geo = cell.find("mxGeometry")
            if geo is None:
                continue
            if cell.get("edge") == "1":
                edges.append((cell, geo))
                continue
            x, y = float(geo.get("x", 0)), float(geo.get("y", 0))
            w, h = float(geo.get("width", 0)), float(geo.get("height", 0))
            if x < x0 - 40 and x + w > x1 + 40:
                continue   # a band or frame across the page is not in this column; it must keep its place
            if y >= y_from - 0.5:
                shapes.append((geo, x, y, w, h, x < x1 and x + w > x0))
        moved = [(x, y, w, h) for geo, x, y, w, h, hit in shapes if hit]
        # A shape drawn inside a moved card (an L0 card at the far side of a zone card whose VLAN table
        # grew) moves with the card, even when it stands beside the column rather than in it.
        pending = [s for s in shapes if not s[5]]
        while pending:
            # (a pill on the card's top edge, 7 px above it, is inside too)
            inside = [s for s in pending if any(mx <= s[1] and s[1] + s[3] <= mx + mw and my - 8 <= s[2]
                                                and s[2] + s[4] <= my + mh for mx, my, mw, mh in moved)]
            if not inside:
                break
            moved += [(x, y, w, h) for _, x, y, w, h, _ in inside]
            pending = [s for s in pending if s not in inside]
        for geo, x, y, w, h, hit in shapes:
            if hit or (x, y, w, h) in moved:
                geo.set("y", f"{y + delta:g}")
        for cell, geo in edges:
            # Bend points, and the free ends of unconnected lines (legend samples), move when
            # they sit in the column below the line; a line between a moved and an unmoved
            # shape keeps the bends above it.
            for p in geo.iter("mxPoint"):
                if p.get("as") == "offset" or p.get("y") is None:
                    continue
                if float(p.get("y")) >= y_from - 0.5 and x0 <= float(p.get("x", 0)) <= x1:
                    p.set("y", f"{float(p.get('y')) + delta:g}")
        height = float(self.model.get("pageHeight", 0))
        if delta > 0 and height:
            self.model.set("pageHeight", f"{height + delta:g}")

    def tables(self) -> list[str]:
        return [i for i, e in self.els.items()
                if "shape=table;" in ((cell_of(e).get("style") or "") if cell_of(e) is not None else "")]

    def rows(self, table_id: str) -> list[str]:
        rows = [c for c in self.children.get(table_id, [])
                if "shape=tableRow" in (cell_of(self.els[c]).get("style") or "")]
        return sorted(rows, key=lambda r: float(self.geometry(r).get("y", 0)))

    def row_cells(self, row_id: str) -> list[str]:
        return sorted(self.children.get(row_id, []), key=lambda c: float(self.geometry(c).get("x", 0)))

    def header(self, table_id: str) -> list[str]:
        rows = self.rows(table_id)
        return [plain(self.value(self.els[c])).upper() for c in self.row_cells(rows[0])] if rows else []

    def add_column(self, table_id: str, title: str, width: float, after: str, donors: list[str]) -> bool:
        """Add a column after the one titled ``after``, taking its width from the ``donors`` (widest first).

        Every row gets a cell copied from its neighbour. Returns False when the table has no
        such column or already has the new one.
        """
        header = self.header(table_id)
        if title.upper() in header or after.upper() not in header:
            return False
        at = header.index(after.upper())
        rows = self.rows(table_id)
        if not rows:
            return False
        cells = [self.row_cells(r) for r in rows]
        widths = [float(self.geometry(c).get("width", 0)) for c in cells[0]]
        # The donors pay evenly, none below 60 px; what they cannot pay comes from every wide column.
        pool = [header.index(d.upper()) for d in donors if d.upper() in header]
        need, taken, floor = width, {}, 60.0
        for _ in range(8):
            payers = [i for i in pool if widths[i] - taken.get(i, 0) > floor + 1]
            if need <= 0.5 or not payers:
                break
            share = need / len(payers)
            for i in payers:
                give = min(share, widths[i] - taken.get(i, 0) - floor)
                taken[i] = taken.get(i, 0) + give
                need -= give
        if need > 0.5:
            others = [i for i in range(len(header)) if widths[i] - taken.get(i, 0) > 80]
            for i in others:
                taken[i] = taken.get(i, 0) + need / len(others)
            need = 0
        for n, row in enumerate(rows):
            proto = cells[n][at]
            new = copy.deepcopy(self.els[proto])
            new_id = f"{proto}-{re.sub(r'[^a-z0-9]+', '', title.lower())}-col"
            new.set("id", new_id)
            cell = cell_of(new)
            # The new column takes its neighbour's layout, not its colour (a STATUS cell may be green);
            # the header keeps the header colour.
            if n:
                cell.set("style", re.sub(r"fontColor=[^;]*;?", "", cell.get("style") or ""))
            if new.tag != "mxCell":
                for k in list(new.attrib):
                    if k not in ("id", "label"):
                        del new.attrib[k]
                new.set("label", title if n == 0 else "")
            else:
                cell.set("value", title if n == 0 else "")
            # Shift and shrink: cells left of the new one shrink where they donate; the new cell follows.
            x = 0.0
            geos = [self.geometry(c) for c in cells[n]]
            for i, geo in enumerate(geos):
                w = widths[i] - taken.get(i, 0)
                geo.set("x", f"{x:g}")
                geo.set("width", f"{w:g}")
                x += w
                if i == at:
                    cell.find("mxGeometry").set("x", f"{x:g}")
                    cell.find("mxGeometry").set("width", f"{width:g}")
                    x += width
            self.root.insert(list(self.root).index(self.els[proto]) + 1, new)
        self.reindex()
        return True

    def balance_columns(self, table_id: str, rows: list[list[tuple]], width: float | None = None) -> None:
        """Before ``fill_table``: move width from columns whose text has room to spare to columns
        whose text would wrap, so the table keeps its width (or narrows to ``width``, to sit inside
        its card) and as many rows as possible stay one line."""
        row_ids = self.rows(table_id)
        if len(row_ids) < 2:
            return
        head, body = self.row_cells(row_ids[0]), self.row_cells(row_ids[1])
        if len(head) != len(body):
            return
        widths = [float(self.geometry(c).get("width", 0)) for c in head]
        size = font_size(cell_of(self.els[body[0]]).get("style") or "")

        def need(text: str, bold: bool) -> float:
            w = max((text_width(plain(part), size, bold) for part in re.split(r"<br\s*/?>", text or "")), default=0)
            w = float(int(w) + 9)
            while text_lines(text, w, size, bold=bold) > 1 and w < 600:
                w += 1
            return w

        bold = ["fontStyle=1" in (cell_of(self.els[c]).get("style") or "") for c in body]
        per_row = [[need(plain(self.value(self.els[head[i]])), True)]
                   + [need(text, bold[i] or "<b>" in text) for r in rows for text in [r[i][0] if i < len(r) else ""]]
                   for i in range(len(widths))]
        needs = [max(col) for col in per_row]
        total = round(min(width, sum(widths)) if width else sum(widths))

        def longest_word(text: str, bold: bool, at_hyphens: bool) -> float:
            split = r" |(?<=-)(?=[^\s-])" if at_hyphens else r" "
            words = re.split(split, " ".join(plain(part) for part in re.split(r"<br\s*/?>", text or "")))
            return float(int(max((text_width(w, size, bold) for w in words), default=0)) + 9)

        # A column never gets narrower than its longest unbroken word (a serial, an address, a date):
        # draw.io does not break inside a word, so it would be cut off rather than wrap. A date or a
        # hostname stays whole too, unless the table has no room for that; then it may break at a hyphen.
        def word_floor(at_hyphens: bool) -> list[list[float]]:
            return [[longest_word(plain(self.value(self.els[head[i]])), True, at_hyphens)]
                    + [longest_word(text, bold[i] or "<b>" in text, at_hyphens)
                       for r in rows for text in [r[i][0] if i < len(r) else ""]] for i in range(len(widths))]

        whole, broken = word_floor(False), word_floor(True)
        floor = [max(col) for col in broken]
        shrink = sum(widths) - total
        if shrink < 0.5 and all(n <= w + 0.5 for w, n in zip(widths, needs)):
            return
        if sum(needs) <= total:
            # Every column fits on one line: the room left over stays where the template had it.
            extra = [max(0.0, w - n) for w, n in zip(widths, needs)]
            weights = extra if sum(extra) else widths
            new = [n + (total - sum(needs)) * e / sum(weights) for n, e in zip(needs, weights)]
        else:
            # Not enough room: let as few rows as possible wrap. Try leaving out one, two, then three of the
            # rows that set a column's width; past that, take pixels where the fewest rows start to wrap.
            n_rows = len(per_row[0])
            widest = {r for col in per_row for r in sorted(range(n_rows), key=lambda r: -col[r])[:4] if r}
            fit = None
            for words in (whole, broken):   # dates and names whole if that fits, else broken at a hyphen
                for size in (1, 2, 3):
                    for out in itertools.combinations(sorted(widest), size):
                        ws = [max([n for r, n in enumerate(col) if r not in out] + [words[i][r] for r in out])
                              for i, col in enumerate(per_row)]
                        if sum(ws) <= total and (fit is None or sum(ws) < sum(fit)):
                            fit = ws
                    if fit:
                        break
                if fit:
                    break
            if fit:
                weights = [max(0.0, w - f) for w, f in zip(widths, fit)]
                weights = weights if sum(weights) else widths
                new = [f + (total - sum(fit)) * e / sum(weights) for f, e in zip(fit, weights)]
            else:
                new = list(needs)
                for _ in range(int(round(sum(needs) - total))):
                    cost = lambda i: (sum(1 for n in per_row[i] if n > new[i] - 1), -new[i])
                    i = min((i for i in range(len(new)) if new[i] - 1 >= max(24, floor[i])), key=cost, default=None)
                    if i is None:
                        break
                    new[i] -= 1
        # Whole pixels, the total asked for: round down (every need is a whole pixel, so none is cut),
        # then hand the pixels left to the columns with the largest fractions.
        exact, new = new, [math.floor(w + 1e-6) for w in new]
        if 0 < total - sum(new) < len(new):
            for i in sorted(range(len(new)), key=lambda i: new[i] - exact[i])[:int(total - sum(new))]:
                new[i] += 1
        if abs(sum(new) - sum(widths)) >= 0.5:   # narrowed to its card (or, at worst, as wide as its words)
            self.geometry(table_id).set("width", f"{sum(new):g}")
        for r in row_ids:
            x = 0.0
            for c, w in zip(self.row_cells(r), new):
                geo = self.geometry(c)
                geo.set("x", f"{x:g}")
                geo.set("width", f"{w:g}")
                x += w

    def tighten_card(self, table_id: str) -> None:
        """Shrink the card around a table that ended up shorter, when nothing shown sits under the table."""
        tx, ty, tw, th = self.box(table_id)
        page_w = float(self.model.get("pageWidth", 0) or 0) if self.model is not None else 0
        cards = [i for i, e in self.els.items() if i != table_id and cell_of(e) is not None
                 and cell_of(e).get("vertex") == "1" and cell_of(e).get("parent") in self.layers
                 and "rounded=1" in (cell_of(e).get("style") or "") and not self.hidden(i)
                 and _inside((tx, ty, tw, th), self.box(i)) and self.box(i)[2] < 0.8 * (page_w or 1250)]
        if not cards:
            return
        card = min(cards, key=lambda i: self.box(i)[2] * self.box(i)[3])
        cx, cy, cw, ch = self.box(card)
        skip = {table_id, card, *self.descendants(table_id)}
        if any(i not in skip and not self.hidden(i) and self.box(i)[1] + self.box(i)[3] > ty + th
               and _inside(self.box(i), (cx, cy, cw, ch)) for i, e in self.els.items()
               if cell_of(e) is not None and cell_of(e).get("vertex") == "1"):
            return
        fit = ty + th + (tx - cx) - cy  # the card's side margin under the last row
        if ch - fit > 40:  # a template's own padding stays; only room left by fewer or shorter rows goes
            self.geometry(card).set("height", f"{fit:g}")

    def fill_table(self, table_id: str, rows: list[list[tuple[str, str]]]) -> None:
        """Replace a table's data rows, keeping its header and the first data row's style.

        Each row is a list of (text, link) pairs; link may be "", a third item True
        marks text that is HTML already, and a fourth is a tooltip. A longer table grows
        the card behind it and moves the shapes below it in the same column; a shorter one keeps its space.
        """
        row_ids = self.rows(table_id)
        if len(row_ids) < 2:
            return
        header_h = float(self.geometry(row_ids[0]).get("height", 22))
        proto_row = copy.deepcopy(self.els[row_ids[1]])
        proto_cells = [copy.deepcopy(self.els[c]) for c in self.row_cells(row_ids[1])]
        # The base row height is the shortest data row: a wrapped first row (from an earlier
        # build of this same drawing) must not make every row that tall.
        row_h = min(float(cell_of(self.els[r]).find("mxGeometry").get("height", 18)) for r in row_ids[1:])
        tx, ty, tw, th = self.box(table_id)
        old_bottom = ty + th

        for row in row_ids[1:]:
            for c in self.descendants(row):
                if self.els.get(c) is not None and self.els[c] in list(self.root):
                    self.root.remove(self.els[c])
            self.root.remove(self.els[row])

        insert_at = list(self.root).index(self.els[row_ids[0]]) + 1 + len(self.descendants(row_ids[0]))
        col_widths = [float(cell_of(c).find("mxGeometry").get("width", 0)) for c in proto_cells]
        col_bold = ["fontStyle=1" in (cell_of(c).get("style") or "") for c in proto_cells]
        size = font_size(cell_of(proto_cells[0]).get("style") or "")
        new = []
        y = header_h
        for n, values in enumerate(rows):
            row_id = f"{table_id}-r{n}"
            row = copy.deepcopy(proto_row)
            row_cell = cell_of(row)
            row.set("id", row_id) if row.tag != "mxCell" else row_cell.set("id", row_id)
            # A row is as tall as its longest cell needs: a second prefix or a long name wraps instead of clipping.
            texts = [(values[c][0] if c < len(values) else "", w, col_bold[c]) for c, w in enumerate(col_widths)]
            this_h = row_height(texts, size, row_h)
            row_cell.find("mxGeometry").set("y", f"{y:g}")
            row_cell.find("mxGeometry").set("height", f"{this_h:g}")
            y += this_h
            new.append(row)
            for col, proto in enumerate(proto_cells):
                text, link, *rest = values[col] if col < len(values) else ("", "")
                shown = text if rest and rest[0] else html.escape(text)  # (text, link, True) is HTML already
                tooltip = rest[1] if len(rest) > 1 else ""
                pc = copy.deepcopy(cell_of(proto))
                pc.set("parent", row_id)
                pc.attrib.pop("id", None)
                if pc.find("mxGeometry") is not None:
                    pc.find("mxGeometry").set("height", f"{this_h:g}")
                cell_id = f"{row_id}-c{col}"
                if link or tooltip:
                    attrs = {"id": cell_id, "label": shown}
                    if link:
                        attrs.update(link=link, linkTarget="_blank")
                    if tooltip:
                        attrs["tooltip"] = tooltip
                    obj = ET.Element("object", attrs)
                    pc.attrib.pop("value", None)
                    obj.append(pc)
                    new.append(obj)
                else:
                    pc.set("id", cell_id)
                    pc.set("value", shown)
                    new.append(pc)
        for offset, el in enumerate(new):
            self.root.insert(insert_at + offset, el)

        new_h = y
        geo = self.geometry(table_id)
        geo.set("height", f"{new_h:g}")
        delta = new_h - th
        self.reindex()
        if delta > 0:
            # A longer table grows its card and pushes everything below it in that column down.
            # A shorter one leaves its space empty, so the rest of the template keeps its layout.
            cards = [i for i, e in self.els.items()
                     if i != table_id and cell_of(e) is not None and cell_of(e).get("vertex") == "1"
                     and cell_of(e).get("parent") in self.layers and "rounded=1" in (cell_of(e).get("style") or "")]
            card = None
            # The page frame is rounded too: a table with no card of its own must not grow the frame
            # and shift the whole page width under it (that would move the floor plan beside it).
            page_w = float(self.model.get("pageWidth", 0) or 0) if self.model is not None else 0
            frame_w = 0.8 * page_w if page_w else 1000
            for i in cards:
                x, y, w, h = self.box(i)
                if w >= frame_w:
                    continue
                if x <= tx and y <= ty and x + w >= tx + tw and y + h >= old_bottom - 1:
                    if card is None or w * h < self.box(card)[2] * self.box(card)[3]:
                        card = i
            skip = {table_id} | set(self.descendants(table_id))
            if card:
                cx, cy, cw, ch = self.box(card)
                self.geometry(card).set("height", f"{ch + delta:g}")
                skip.add(card)
                # Everything below the table in the card's column moves: on the card and under it.
                self.shift_below(cx, cx + cw, old_bottom, delta, skip)
            else:
                self.shift_below(tx, tx + tw, old_bottom, delta, skip)


def _inside(inner, outer) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[0] + inner[2] <= outer[0] + outer[2] \
        and inner[1] + inner[3] <= outer[1] + outer[3]
