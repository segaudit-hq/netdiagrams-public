"""Keep the template's example apart from this site's data, on every sheet.

Three rules, applied at build time:

1. What the tool rebuilt from NetBox keeps its normal look. A sheet or card the
   template brought along as an example (Plant A's flows, failover scenarios,
   the multi-site picture, the platform catalogue) gets an EXAMPLE watermark
   until a data source fills it, and a plan-card row naming that source.
2. Prose that can never come from NetBox (zone rules, routing policy, design
   rules, how-to notes) moves to the page's "Guides (hidden)" layer, which the
   Print and Share views hide. ``--no-guide`` removes it.
3. Labels that assert a fact are derived: an "HA pair" group reads as a pair
   only when NetBox has two members; the management overview's cards count
   this site's zones, firewalls and lines; a cell's note lists its NetBox
   uplinks and trunks.
"""

from __future__ import annotations

import html
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter

from . import ot
from .graph import Graph, cell_of, plain
from . import profiles
from .model import Site, Zone, bands

MISSING = '<font color="#B45309"><b>?</b></font>'
AMBER = "#B45309"
GUIDE_LAYER = "Guides (hidden)"
WATERMARK_LAYER = "Example watermark"

# Sheets that are the template's example, not this site's data: (word, why, source that fills it).
# Each profile names its own (profiles.py); these are the manufacturing template's.
EXAMPLE_SHEETS = profiles.MANUFACTURING.example_sheets
# On the flow register sheet the zone tables fill from NetBox; these cards stay the example.
EXAMPLE_CARDS = profiles.MANUFACTURING.example_cards
EXAMPLE_TABLE_HEADERS = profiles.MANUFACTURING.example_table_headers
# Template prose that can never come from NetBox, by page: it goes to the guide layer.
GUIDE_IDS = profiles.MANUFACTURING.guide_ids


def example_sheets() -> dict:
    """The example and reference sheets of the profile in force."""
    return profiles.current().example_sheets


HA_WORDS = re.compile(r"\b(HA|SSO|SVL|VSX|VSF|IRF|StackWise|pair|stack|active|standby|A/P|A/A)\b")
HA_PHRASE = re.compile(r"\s*\b(?:[A-Z]{1,2}[A-Z0-9]*-?\d{3,4}[A-Z0-9-]* )?"
                       r"(HA pair(?: \([^)]*\))?|HA SSO(?: RP(?: back-to-back)?)?|HA|SVL pair|SVL(?: \d×\d+G)?|"
                       r"edge pair|pair|stack(?: \(\d+\))?)\b")
NAME = re.compile(r"[A-Z][A-Z0-9]*\d[A-Z0-9]*-[A-Z0-9]+(?:-[A-Z0-9]+)*")


# ------------------------------------------------------------------ helpers
def _top_vertices(g: Graph):
    for i, el in g.els.items():
        cell = cell_of(el)
        if cell is not None and cell.get("vertex") == "1" and cell.get("parent") in g.layers:
            yield i, el


def _layer(g: Graph, name: str, hidden: bool = False, after: str | None = None) -> str:
    """The id of the layer called ``name`` on this page, made if missing."""
    for i, layer_name in g.layers.items():
        if layer_name == name:
            return i
    layer_id = f"{g.diagram.get('id')}-{re.sub(r'[^a-z]+', '-', name.lower()).strip('-')}"
    attrs = {"id": layer_id, "value": name, "style": "", "parent": "0"}
    if hidden:
        attrs["visible"] = "0"
    layer = ET.Element("mxCell", attrs)
    if after and after in g.els:
        g.root.insert(list(g.root).index(g.els[after]) + 1, layer)
    else:
        g.root.append(layer)
    g.reindex()
    return layer_id


def _move_to_layer(g: Graph, el_id: str, layer_id: str) -> None:
    cell = cell_of(g.els[el_id])
    if cell is not None and cell.get("parent") in g.layers:
        cell.set("parent", layer_id)


def _text(g: Graph, el_id: str, value: str) -> None:
    g.set_value(g.els[el_id], value)


def _page_size(g: Graph) -> tuple[float, float]:
    """The drawn extent of the sheet (the page, when the drawing is smaller).

    The band is laid across the drawing itself, not across the paper, so that it sits the same
    on a first build and on a rebuild from that drawing (whose page is already its paper size)
    and never pushes the cards the build adds under the drawing further down.
    """
    pw, ph = float(g.model.get("pageWidth", 2000)), float(g.model.get("pageHeight", 1200))
    boxes = [g.box(i) for i, _ in _top_vertices(g) if not g.layer_of(i).startswith(("Border", WATERMARK_LAYER))]
    if boxes:
        pw = min(pw, max(x + w for x, _, w, _ in boxes))
        ph = min(ph, max(y + h for _, y, _, h in boxes))
    return pw, ph


# ------------------------------------------------------------------ 1. example
def possessive(name: str) -> str:
    """"Plant A's", but "Kestrel Valley Motors'"."""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def watermark(g: Graph, word: str, why: str, box: tuple[float, float, float, float] | None = None) -> str:
    """A diagonal grey band saying this is an example: across the page, or across one card."""
    layer = _layer(g, WATERMARK_LAYER)
    whole = box is None
    if box is None:
        pw, ph = _page_size(g)
        box = (pw * 0.08, ph * 0.10, pw * 0.84, ph * 0.80)
    # tilted 18°, the band must stay inside the box, or it reaches past a wide card or the page's top edge
    bx, by, bw, bh = box
    h = bh * 0.4
    w = min(bw * 0.92, (bh - h * math.cos(math.radians(18))) / math.sin(math.radians(18)))
    x, y = bx + (bw - w) / 2, by + (bh - h) / 2
    size = max(28, min(110, w / 9))
    sub = max(11, min(24, size / 4))
    n = sum(1 for i in g.els if i.startswith(f"{g.diagram.get('id')}-example-"))
    el_id = f"{g.diagram.get('id')}-example-{n}"
    label = (f'<span style="font-size:{size:g}px;letter-spacing:6px">{word}</span><br>'
             f'<span style="font-size:{sub:g}px;letter-spacing:1px">{html.escape(why)}</span>')
    # "page" marks a whole sheet as an example: share leaves such sheets out, whatever the profile.
    el = ET.SubElement(g.root, "object", {"id": el_id, "label": label,
                                          "netdiagrams_example": "page" if whole else "1",
                                          "tooltip": f"{word}: {why}"})
    cell = ET.SubElement(el, "mxCell", {
        "vertex": "1", "parent": layer,
        "style": "text;html=1;align=center;verticalAlign=middle;fontStyle=1;fontFamily=Inter;fontColor=#94A3B8;"
                 "textOpacity=35;rotation=-18;whiteSpace=wrap;spacing=0;"})
    ET.SubElement(cell, "mxGeometry", {"x": f"{x:g}", "y": f"{y:g}", "width": f"{w:g}", "height": f"{h:g}",
                                       "as": "geometry"})
    g.reindex()
    return el_id


UNCOMPARED = ("Border", WATERMARK_LAYER, "Controls", "How to draw this page")


def _texts_by_id(g: Graph, names: tuple[str, ...]) -> dict[str, str]:
    """id -> the text a reader sees, with the template's and the site's code and name taken out."""
    out = {}
    for i, el in g.els.items():
        if cell_of(el) is None or g.layer_of(i).startswith(UNCOMPARED) or i in SUBTITLE_IDS.values():
            continue
        text = " ".join(plain(g.value(el)).split())
        for name in names:
            text = text.replace(name, "§")
        if text:
            out[i] = text
    return out


def edited_examples(pages: list[Graph], bundled: ET.Element, names: tuple[str, ...]) -> set[tuple[str, str]]:
    """The example sheets and example cards a site rewrote in its own template: (page id, "" or layer name).

    They are compared with the profile's bundled template by shape id and text; the codes and names in
    ``names`` don't count, since every build renames those. A rewritten one is the site's own and is not
    stamped EXAMPLE again.
    """
    names = tuple(sorted({n for n in names if n}, key=len, reverse=True))
    theirs = {d.get("id"): Graph(d) for d in bundled.findall("diagram") if d.find("mxGraphModel") is not None}
    out = set()
    for g in pages:
        page = g.diagram.get("id") or ""
        wanted = ([""] if page in example_sheets() else []) + list(profiles.current().example_cards.get(page, ()))
        if not wanted:
            continue
        if page not in theirs:
            out.update((page, layer) for layer in wanted)
            continue
        mine, base = _texts_by_id(g, names), _texts_by_id(theirs[page], names)
        for layer in wanted:
            # A guide note moves to the hidden guide layer on the first build; it is compared by id all the same.
            ids = set(mine) | set(base) if not layer else \
                {i for i in base if theirs[page].layer_of(i) == layer} | {i for i in mine if g.layer_of(i) == layer}
            if any(mine.get(i) != base.get(i) for i in ids):
                out.add((page, layer))
    return out


def mark_examples(g: Graph, edited: set[tuple[str, str]] = frozenset()) -> tuple[list[str], list[str]]:
    """Watermark the example sheets and cards; return (what was marked, what was left as the site rewrote it)."""
    page = g.diagram.get("id") or ""
    marked, kept = [], []
    if page in example_sheets() and (page, "") in edited:
        kept.append(f"{g.name}: not marked EXAMPLE, it differs from the bundled template")
    elif page in example_sheets():
        word, why, _ = example_sheets()[page]
        watermark(g, word, why)
        marked.append(f"{g.name}: whole sheet")
    for layer_name in profiles.current().example_cards.get(page, ()):
        if (page, layer_name) in edited:
            kept.append(f"{g.name}: {layer_name} not marked EXAMPLE, it differs from the bundled template")
            continue
        cards = [i for i, el in _top_vertices(g) if g.layer_of(i) == layer_name
                 and "rounded=1" in (cell_of(el).get("style") or "") and g.box(i)[2] > 300 and g.box(i)[3] > 120]
        cards = [c for c in cards if card_around(g, c) not in cards]  # one band per card, not per nested card
        for card in cards:
            watermark(g, "EXAMPLE", f"{possessive(profiles.current().site_name)}, not from this site's NetBox", g.box(card))
            marked.append(f"{g.name}: {layer_name}")
    for header in profiles.current().example_table_headers.get(page, ()):
        for table in g.tables():
            if g.header(table)[:len(header)] == header:
                card = card_around(g, table)
                if card:
                    watermark(g, "EXAMPLE", f"{possessive(profiles.current().site_name)} standards, not this site's",
                              g.box(card))
                    marked.append(f"{g.name}: {' / '.join(header)} table")
    return marked, kept


def card_around(g: Graph, el_id: str) -> str | None:
    tx, ty, tw, th = g.box(el_id)
    card = None
    for i, el in _top_vertices(g):
        if i == el_id:
            continue
        cx, cy, cw, ch = g.box(i)
        if cx <= tx and cy <= ty and cx + cw >= tx + tw and cy + ch >= ty + th:
            if card is None or cw * ch < g.box(card)[2] * g.box(card)[3]:
                card = i
    return card


# ------------------------------------------------------------------ 2. guide
def move_guides(g: Graph) -> int:
    """Template prose goes to the hidden guide layer. Returns how many notes moved."""
    page = g.diagram.get("id") or ""
    ids = [i for i in profiles.current().guide_ids.get(page, []) if i in g.els]
    if not ids:
        return 0
    layer = _layer(g, GUIDE_LAYER, hidden=True, after=None)
    g.els[layer].set("visible", "0")
    for i in ids:
        _move_to_layer(g, i, layer)
    g.reindex()
    return len(ids)


def remove_guides(g: Graph) -> None:
    """``--no-guide``: the guide layer and everything on it leave the file."""
    for layer_id, name in list(g.layers.items()):
        if name.startswith("Guides"):
            g.remove(list(g.children.get(layer_id, [])))
            g.root.remove(g.els[layer_id])
            g.reindex()


# ------------------------------------------------------------------ 3. derived labels
def _members(name: str, devices: dict, register_only: dict) -> list[str]:
    return sorted(d for d in devices if (d == name or d.startswith(name + "-")) and d not in register_only)


def derive_group_labels(g: Graph, devices: dict, register_only: dict, is_device) -> list[tuple[str, str, str]]:
    """A group label says 'HA pair', 'SSO' or 'stack' only when NetBox has at least two members.

    Returns (element id, old text, new text) for the drift report.
    """
    changed = []
    for i, el in list(g.els.items()):
        cell = cell_of(el)
        if cell is None or cell.get("vertex") != "1" or is_device(el) or cell.get("parent") not in g.layers:
            continue
        value = g.value(el)
        text = plain(value)
        m = NAME.match(text)
        name = el.get("name") if text.startswith("%name%") else m.group(0) if m else ""
        if not name or name in devices:  # a device's own label is the device's business, not a group claim
            continue
        members = _members(name, devices, register_only)
        drawn = [g.els[d].get("name") for d in g.descendants(i) if is_device(g.els[d])
                 and g.els[d].get("name") in devices]
        if drawn and not members and text.startswith("%name%"):
            # the template's stack holds a NetBox device of another name: the stack is that device's
            members = drawn
            if len(drawn) == 1:
                el.set("name", drawn[0])
        if not members:
            continue  # the template's example; the plan card lists it
        new = value
        if HA_WORDS.search(text):
            if len(members) >= 2:
                new = re.sub(r"stack \(\d+\)", f"stack ({len(members)})", value)
            elif m:
                new = _without_ha(value, name)
        new = _model_count(new, [devices[d] for d in members])
        if new != value:
            g.set_value(el, new)
            changed.append((i, text, plain(new)))
    return changed


MODEL_COUNT = re.compile(r"(?<=[\s>])(?P<model>[^<>·%]*?\S) ×(?P<n>\d+)(?![\w.])")  # "C9300 ×3", not "2×100G"


def _model_count(value: str, members: list[dict]) -> str:
    """'CX 6200F 48G PoE ×3' on a stack's label says what NetBox has: its members' model and count."""
    found = MODEL_COUNT.search(value)
    if not found or found.group("n") == str(len(members)):
        return value  # a count that matches NetBox keeps the template's wording
    models = {((d.get("device_type") or {}).get("model") or "") for d in members}
    model = found.group("model")
    if len(models) == 1 and "" not in models and re.search(r"\d", model):  # a model name, not "Core switch"
        model = html.escape(models.pop())
    n = len(members)
    return value[:found.start()] + model + (f" ×{n}" if n > 1 else "") + value[found.end():]


def _without_ha(value: str, name: str) -> str:
    """Drop the segments of an HTML label that claim redundancy; keep the name and the rest."""
    parts = re.split(r"(<br\s*/?>|\s[·•]\s)", value)
    out = []
    for n, part in enumerate(parts):
        if n % 2 == 1:
            out.append(part)
            continue
        text = plain(part)
        if not HA_WORDS.search(text):
            out.append(part)
            continue
        # The segment loses its HA words; what is left stays when it still says something
        # (the name, or a sentence), and goes when it was only the claim.
        cleaned = re.sub(r"\(\s*\)", "", HA_PHRASE.sub("", part))
        left = plain(cleaned)
        if name in left or (len(left) > 24 and not HA_WORDS.search(left)):
            out.append(cleaned)
        else:
            out.append("")
    # Tidy separators left around removed segments.
    text = "".join(out)
    for _ in range(3):
        text = re.sub(r"(\s[·•]\s)(\s[·•]\s)", r"\1", text)
        text = re.sub(r"(<br\s*/?>)(\s*<br\s*/?>)", r"\1", text)
        text = re.sub(r"(\s[·•]\s)(<br\s*/?>|</b>|$)", r"\2", text)
        text = re.sub(r"(<br\s*/?>|<b>|^)(\s[·•]\s)", r"\1", text)
        text = re.sub(r"(<br\s*/?>)\s*$", "", text)
    return text.strip()


# ------------------------------------------------------------------ overview sheet
def _status_counts(devices: dict, register_only: dict) -> Counter:
    counts = Counter()
    for name, d in devices.items():
        status = (d.get("status") or {}).get("value") if isinstance(d.get("status"), dict) else d.get("status")
        counts[status or "active"] += 1
    return counts


def _zones_by_band(site: Site) -> dict[str, list[Zone]]:
    out: dict[str, list[Zone]] = {}
    for band, zones in site.bands():
        out[band[0]] = zones
    return out


def _is_safety(zone: Zone) -> bool:
    return bool(re.match(profiles.word("safety_zones"), zone.slug or ""))


def _line_card(style: str, parent: str, el_id: str, x: float, y: float, w: float, h: float, label: str) -> ET.Element:
    cell = ET.Element("mxCell", {"id": el_id, "value": label, "style": style, "vertex": "1", "parent": parent})
    ET.SubElement(cell, "mxGeometry", {"x": f"{x:g}", "y": f"{y:g}", "width": f"{w:g}", "height": f"{h:g}",
                                       "as": "geometry"})
    return cell


def _plural(n: int, word: str, plural: str = "") -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def derive_overview(g: Graph, site: Site, devices: dict, register_only: dict, data_date: str, revision: str,
                    cables: int, vlans: int) -> None:
    """The management overview says what NetBox says about this plant, nothing more.

    Gate strips count the firewalls, the production-line cards are the cell zones,
    and the right-hand column carries six statements that are true by construction.
    """
    if "overview-c26" not in g.els or "overview-c17" not in g.els:
        return
    bands = _zones_by_band(site)
    live = {n: d for n, d in devices.items() if n not in register_only}
    firewalls = [n for n, d in live.items() if (d.get("role") or {}).get("slug") == "firewall"]
    status = _status_counts(live, register_only)
    say = profiles.word
    cells = [z for z in bands.get(say("areas_band"), []) if not _is_safety(z)]
    safety = [z for z in bands.get(say("safety_band"), []) if _is_safety(z)]
    n_devices = len(live)

    def none_yet(what: str) -> str:
        return f'<br><font color="{AMBER}"><i>{what} in NetBox yet</i></font>'

    # Subtitle and section cards.
    _text(g, "overview-c2", html.escape(
        f"Management overview — no technical detail. What follows is read from NetBox as of {data_date}: "
        f"{_plural(len([z for z in site.zones.values() if z.slug]), 'zone')}, {_plural(n_devices, 'device')}."))
    if len(firewalls) >= 2:
        gate = f"<b>Security gate</b> — {_plural(len(firewalls), 'firewall')} in NetBox (a pair takes over if one fails)"
        same = "<b>Same security gate</b>"
    elif len(firewalls) == 1:
        gate = (f"<b>Security gate</b> — one firewall in NetBox "
                f'<font color="{AMBER}">(no standby firewall recorded)</font>')
        same = "<b>Same firewall</b>"
    else:
        gate = f'<b>Security gate</b> — <font color="{AMBER}">no firewall in NetBox yet</font>'
        same = "<b>Same gate</b>"
    _text(g, "overview-c7", gate)
    _text(g, "overview-c10", f"{same} — {say('outer_gate')}")
    _text(g, "overview-c13", f"{same} — {say('inner_gate')}")
    for el_id, key, what in say("missing_band"):
        if not bands.get(key) and el_id in g.els:
            _text(g, el_id, g.value(g.els[el_id]) + none_yet(what))

    # Production-line cards: one per cell zone, plus the safety zones.
    style = cell_of(g.els["overview-c17"]).get("style") or ""
    safe_style = cell_of(g.els["overview-c20"]).get("style") or style
    parent = cell_of(g.els["overview-c17"]).get("parent")
    index = list(g.root).index(g.els["overview-c17"])
    g.remove([i for i in ("overview-c17", "overview-c18", "overview-c19", "overview-c20") if i in g.els])
    lines = [(z, style) for z in sorted(cells, key=lambda z: z.slug)] + [(z, safe_style) for z in safety]
    cards = []
    if not lines:
        cards.append(_line_card(style, parent, "overview-line-0", 190, 870, 500, 100,
                                f'<b>{say("areas_title")}</b><br><span style="font-size:11px;color:{AMBER}">'
                                f"{say('no_areas_card')}</span>"))
    for n, (zone, card_style) in enumerate(lines):
        col, row = n % 4, n // 4
        counts = _plural(len(zone.devices), "device")
        bad = Counter((d.attrs.get("status") or "active") for d in zone.devices)
        notes = [f'<font color="{AMBER}">{bad[s]} {s}</font>' for s in ("offline", "failed", "planned") if bad[s]]
        if _is_safety(zone):
            notes.insert(0, "its own zone")
        sub = " · ".join([counts] + notes)
        cards.append(_line_card(card_style, parent, f"overview-line-{n}", 190 + col * 258, 870 + row * 110, 240, 100,
                                f'<b>{html.escape(plain(_zone_name(zone)))}</b>'
                                f'<br><span style="font-size:11px;color:#64748B">{sub}</span>'))
    for offset, card in enumerate(cards):
        g.root.insert(index + offset, card)
    g.reindex()
    rows = max(1, -(-len(lines) // 4))
    extra = (rows - 1) * 110
    if extra and "overview-c14" in g.els:
        x, y, w, h = g.box("overview-c14")
        g.geometry("overview-c14").set("height", f"{h + extra:g}")
        g.shift_below(0, 10000, y + h, extra, {"overview-c14"} | {c.get("id") for c in cards})
        if "overview-c15" in g.els:
            g.geometry("overview-c15").set("height", f"{h + extra:g}")

    # Right-hand column: statements that NetBox backs.
    if "overview-c25" in g.els:
        _text(g, "overview-c25", f"What NetBox says about this {say('site')}")
    by_band = {k: len(v) for k, v in bands.items()}
    zone_words = [f"{by_band[k]} {what}" for k, what in say("zone_words") if by_band.get(k)]
    unzoned = len(site.zones.get("", Zone("", "", ())).devices) if "" in site.zones else 0
    statements = [
        ("Zones", f"{_plural(len([z for z in site.zones.values() if z.slug]), 'security zone')} in NetBox"
                  + (f": {', '.join(zone_words)}." if zone_words else ".")
                  + (f' <font color="{AMBER}">{_plural(unzoned, "device")} not zoned yet.</font>' if unzoned else "")),
        ("Boundary", {0: f'<font color="{AMBER}">No firewall in NetBox yet.</font>',
                      1: f"One firewall {say('boundary')}. "
                         f'<font color="{AMBER}">NetBox records no standby firewall for it.</font>'}.get(
            len(firewalls), f"{_plural(len(firewalls), 'firewall')} {say('boundary')}, so one can fail.")),
        (say("areas_title"), f"{_plural(len(cells), say('area'))}, each its own zone, "
                             f"{_plural(sum(len(z.devices) for z in cells), 'device')} in them."
                             if cells else f'<font color="{AMBER}">{say("no_areas")}</font>'),
        (say("safety_title"), f"{_plural(sum(len(z.devices) for z in safety), 'device')} {say('safety')}"
                            if safety else f'<font color="{AMBER}">{say("no_safety")}</font>'),
        ("Health", _health(status, len(register_only))),
        ("Where this comes from", f"NetBox as of {data_date}: {_plural(n_devices, 'device')}, "
                                  f"{_plural(cables, 'cable')}, {_plural(vlans, 'VLAN')}. Revision {revision}."),
    ]
    ids = ["overview-c26", "overview-c27", "overview-c28", "overview-c29", "overview-c30", "overview-c31"]
    for el_id, (title, body) in zip(ids, statements):
        if el_id in g.els:
            _text(g, el_id, f'<b><span style="font-size:15px">{title}</span></b><br>{body}')
    for el_id in ids[len(statements):]:
        if el_id in g.els:
            g.remove([el_id])


def _health(status: Counter, spares: int) -> str:
    trouble = [(status[s], s) for s in ("offline", "failed", "planned", "staged", "decommissioning") if status[s]]
    if not trouble and not spares:
        return f"Every device NetBox lists for this {profiles.word('site')} is active."
    parts = [f'<font color="{AMBER}">{n} {s}</font>' for n, s in trouble]
    if spares:
        parts.append(f"{_plural(spares, 'spare or retiring device')} listed, not drawn")
    return f"{status['active']} active · " + " · ".join(parts) + "."


def _zone_name(zone: Zone) -> str:
    from .overview import zone_title
    return zone_title(zone)


# ------------------------------------------------------------------ subtitles
SUBTITLE_IDS = {"logical": "logical-c14", "physical": "physical-c12", "wireless": "wireless-c10",
                "register": "register-c5"}


def derive_subtitles(g: Graph, nb_counts: dict[str, int], data_date: str) -> None:
    page = g.diagram.get("id") or ""
    texts = {
        "logical": ("Zones · VLANs · subnets · VRFs, from NetBox as of {date}: {zones} zones, {vlans} VLANs, "
                    "{prefixes} prefixes. Tables are rebuilt on every run; design notes are on the hidden Guides layer."),
        "physical": ("Devices · uplinks · port-channels · trunked VLANs · rack / cabinet on every device, from NetBox "
                     "as of {date}: {devices} devices, {cables} cables. Hover a device or Edit Data (Ctrl+M) for its "
                     "NetBox record."),
        "wireless": ("Controllers · access points · point-to-point radios · SSIDs, from NetBox as of {date}: "
                     "{wlc} controllers, {ap} access points, {ptp} radios, {ssid} SSIDs. Design notes are on the "
                     "hidden Guides layer."),
        "register": ("The flow register, zone matrix and standards are the template's example until a flow source "
                     "is read (watermarked). The zone and VLAN tables come from NetBox as of {date}: {zones} zones, "
                     "{vlans} VLANs."),
    }
    el_id = SUBTITLE_IDS.get(page)
    if page in texts and el_id in g.els:
        _text(g, el_id, html.escape(texts[page].format(date=data_date, **nb_counts)))


# ------------------------------------------------------------------ cell notes
def derive_cell_notes(g: Graph, devices: dict, names: dict, interfaces: dict, cables: list, is_device,
                      short) -> list[str]:
    """Each cell's note lists the uplinks and trunk VLANs NetBox has for it; a note with no devices under it goes."""
    notes = [i for i, el in _top_vertices(g) if g.layer_of(i).startswith("5 ·")]
    if not notes:
        return []
    zones = [i for i, el in _top_vertices(g) if g.layer_of(i).startswith("Zones")]
    placed = {el.get("name"): g.box(i) for i, el in g.els.items() if is_device(el) and not g.hidden(i)}
    removed = []
    for note in notes:
        nx, ny, nw, nh = g.box(note)
        zone = None
        for z in zones:
            zx, zy, zw, zh = g.box(z)
            if zx <= nx and zy <= ny and zx + zw >= nx + nw and zy + zh >= ny + nh:
                if zone is None or zw * zh < g.box(zone)[2] * g.box(zone)[3]:
                    zone = z
        if zone is None:
            continue
        zx, zy, zw, zh = g.box(zone)
        inside = {n for n, (x, y, w, h) in placed.items() if zx <= x and x + w <= zx + zw and zy <= y and y + h <= zy + zh}
        if not inside:
            g.remove([note])
            removed.append(note)
            continue
        uplinks, trunks, untagged = [], [], 0
        for c in cables:
            a = _end(c.get("a_terminations"), names)
            b = _end(c.get("b_terminations"), names)
            if not a or not b:
                continue
            if (a[0] in inside) == (b[0] in inside):
                continue
            near, far = (a, b) if a[0] in inside else (b, a)
            uplinks.append(f"{html.escape(short(near[0]))} {html.escape(near[1])} → "
                           f"{html.escape(short(far[0]))} {html.escape(far[1])}")
            iface = interfaces.get((near[0], near[1])) or {}
            tagged = [str(v.get("vid")) for v in iface.get("tagged_vlans") or [] if v.get("vid") is not None]
            if tagged:
                trunks.extend(t for t in tagged if t not in trunks)
            elif (iface.get("mode") or {}).get("value", iface.get("mode")) in ("tagged", "tagged-all"):
                untagged += 1
        lines = []
        if uplinks:
            shown = uplinks[:3] + ([f"+{len(uplinks) - 3} more"] if len(uplinks) > 3 else [])
            lines.append("<b>Uplinks</b> " + " · ".join(shown))
        else:
            lines.append(f"<b>Uplinks</b> {MISSING} <i>no cable out of this cell in NetBox</i>")
        if trunks:
            lines.append("<b>Trunk VLANs</b> " + ", ".join(sorted(trunks, key=lambda v: int(v) if v.isdigit() else 0)))
        elif untagged:
            lines.append(f"<b>Trunk VLANs</b> {MISSING} <i>trunk with no tagged VLANs in NetBox</i>")
        elif uplinks:
            lines.append("<b>Trunk VLANs</b> — <i>access ports</i>")
        status = Counter((devices.get(n, {}).get("status") or {}).get("value", "active") for n in inside)
        health = " · ".join(f'<font color="{AMBER}">{status[s]} {s}</font>' for s in ("offline", "failed", "planned")
                            if status[s])
        lines.append(f"<b>In NetBox</b> {_plural(len(inside), 'device')}" + (f" · {health}" if health else ""))
        g.set_value(g.els[note], "<br>".join(lines))
    return removed


def _end(terms, names) -> tuple[str, str] | None:
    for t in terms or []:
        obj = t.get("object") or {}
        dev = obj.get("device") or {}
        name = names.get(dev.get("id")) or dev.get("name")
        if name:
            return name, obj.get("name", "")
    return None


# ------------------------------------------------------------------ residue
RESIDUE_SKIP = ("Zones", "Border", "Legend", "Guides", "Purdue", "Controls", "6 ·", "7 ·", "Plan", "Registers",
                "Optics", "Port maps")


def edge_endpoints(g: Graph, el_ids) -> list[tuple[float, float]]:
    """Where each edge meets its shapes: the exit/entry fraction of the source and target box."""
    ends = []
    for i in el_ids:
        cell = cell_of(g.els[i])
        if cell is None or cell.get("edge") != "1":
            continue
        style, geo = cell.get("style") or "", cell.find("mxGeometry")
        for end, kx, ky, as_ in ((cell.get("source"), "exitX", "exitY", "sourcePoint"),
                                 (cell.get("target"), "entryX", "entryY", "targetPoint")):
            fx, fy = re.search(kx + r"=([\d.]+)", style), re.search(ky + r"=([\d.]+)", style)
            if end in g.els:
                x, y, w, h = g.box(end)
                if fx and fy:
                    ends.append((x + float(fx.group(1)) * w, y + float(fy.group(1)) * h))
                else:
                    ends.append((x + w / 2, y + h / 2))
            elif geo is not None:
                p = next((p for p in geo.iter("mxPoint") if p.get("as") == as_), None)
                if p is not None:
                    ends.append((float(p.get("x", 0)), float(p.get("y", 0))))
    return ends


def _near(px: float, py: float, points, tol: float) -> bool:
    return any(abs(px - x) <= tol and abs(py - y) <= tol and ((px - x) ** 2 + (py - y) ** 2) ** 0.5 <= tol
               for x, y in points)


def sweep_residue(g: Graph, boxes: list[tuple[float, float, float, float]], is_device, margin: float = 28,
                  ends_before: list | None = None, ends_after: list | None = None) -> list[str]:
    """After devices leave a page, the small labels, pills and free lines that sat on them leave too.

    A port-channel oval that sat on the end of a link (within 24 px of where a link met
    its shape) and has no link end there any more goes with the link.
    """
    if not boxes:
        return []
    grown = [(x - margin, y - margin, w + 2 * margin, h + 2 * margin) for x, y, w, h in boxes]
    ends_before, ends_after = ends_before or [], ends_after or []

    def inside(px: float, py: float) -> bool:
        return any(x <= px <= x + w and y <= py <= y + h for x, y, w, h in grown)

    def orphan_pill(el, box) -> bool:
        cell = cell_of(el)
        if g.value(el) or "ellipse" not in (cell.get("style") or ""):
            return False
        x, y, w, h = box
        px, py = x + w / 2, y + h / 2
        if max(w, h) >= 50:
            # A long oval rings a bundle of parallel links; fewer than two left means no bundle.
            def links(points):
                if w >= h:
                    return sum(1 for ex, ey in points if x - 4 <= ex <= x + w + 4 and abs(ey - py) <= 160)
                return sum(1 for ex, ey in points if y - 4 <= ey <= y + h + 4 and abs(ex - px) <= 160)
            return links(ends_before) >= 2 and links(ends_after) < 2
        return _near(px, py, ends_before, 24) and not _near(px, py, ends_after, 24)

    doomed = []
    for i, el in g.els.items():
        cell = cell_of(el)
        if cell is None or cell.get("parent") not in g.layers or is_device(el):
            continue
        if g.layer_of(i).startswith(RESIDUE_SKIP + (profiles.current().band_layer,)):
            continue
        geo = cell.find("mxGeometry")
        if geo is None:
            continue
        if cell.get("edge") == "1":
            if cell.get("source") or cell.get("target"):
                continue
            points = [(float(p.get("x", 0)), float(p.get("y", 0))) for p in geo.iter("mxPoint")
                      if p.get("as") in ("sourcePoint", "targetPoint") or p.get("as") is None]
            if points and all(inside(px, py) for px, py in points):
                doomed.append(i)
            continue
        x, y, w, h = g.box(i)
        if w * h > 220 * 90:
            continue
        if inside(x + w / 2, y + h / 2):
            doomed.append(i)
        elif w * h <= 100 * 100 and orphan_pill(el, (x, y, w, h)):
            doomed.append(i)
    if doomed:
        g.remove(doomed)
    return doomed


# ------------------------------------------------------------------ zone tables (sheet 7)
def _vid_ranges(vids: list[int]) -> str:
    out, run = [], []
    for v in sorted(set(vids)):
        if run and v == run[-1] + 1:
            run.append(v)
        else:
            if run:
                out.append(f"{run[0]}–{run[-1]}" if len(run) > 2 else ", ".join(map(str, run)))
            run = [v]
    if run:
        out.append(f"{run[0]}–{run[-1]}" if len(run) > 2 else ", ".join(map(str, run)))
    return ", ".join(out)


def _owner(z: Zone, devices: dict) -> str:
    """Who owns a zone: the tenant most of its devices carry, else its VLANs' or prefixes' tenant."""
    owners = Counter(_label(devices[d.name].get("tenant")) for d in z.devices if d.name in devices)
    owners.pop("", None)
    if not owners:
        owners = Counter(v.tenant for v in z.vlans if v.tenant)
    return owners.most_common(1)[0][0] if owners else MISSING


def fill_zone_tables(g: Graph, site: Site, devices: dict, gateway) -> list[str]:
    """The ZONE / PURDUE / SL-T (or ZONE / BAND / OWNER) and VLANS / ZONE / LEVEL (or BAND) tables fill from
    this site's zones."""
    filled = []
    zones = [z for z in site.zones.values() if z.slug]
    if not zones:
        return filled
    order = {b[0]: n for n, b in enumerate(bands())}
    zones.sort(key=lambda z: (order.get(z.band[0], 9), z.slug))
    for table in g.tables():
        header = g.header(table)
        if header[:3] == ["ZONE", "PURDUE", "SL-T"]:
            rows = []
            for z in zones:
                levels = Counter(ot.security_level(devices[d.name]) for d in z.devices if d.name in devices)
                levels.pop("", None)
                sl = levels.most_common(1)[0][0] if levels else MISSING
                owner = _owner(z, devices)
                notes = f"{_plural(len(z.devices), 'device')} · {_plural(len(z.vlans), 'VLAN')}"
                rows.append([(plain(_zone_name(z)), ""), (z.band[0], ""), (sl, "", sl == MISSING),
                             (owner, "", owner == MISSING), (notes, "")])
            g.fill_table(table, rows)
            filled.append("ZONE / PURDUE / SL-T")
        elif header[:3] == ["ZONE", "BAND", "OWNER"]:  # a profile without Purdue levels (retail)
            rows = []
            for z in zones:
                owner = _owner(z, devices)
                notes = f"{_plural(len(z.devices), 'device')} · {_plural(len(z.vlans), 'VLAN')}"
                rows.append([(plain(_zone_name(z)), ""), (z.band[0], ""), (owner, "", owner == MISSING),
                             (notes, "")])
            g.fill_table(table, rows)
            filled.append("ZONE / BAND / OWNER")
        elif header[:3] in (["VLANS", "ZONE", "LEVEL"], ["VLANS", "ZONE", "BAND"]):
            rows = []
            for z in zones:
                if not z.vlans:
                    continue
                gws = []
                for v in z.vlans:
                    for p in v.prefixes:
                        gw = gateway(p, v.vrf)
                        if gw and gw not in gws:
                            gws.append(gw)
                names = ", ".join(v.name for v in z.vlans[:3]) + (f" +{len(z.vlans) - 3} more" if len(z.vlans) > 3 else "")
                rows.append([(_vid_ranges([v.vid for v in z.vlans]), ""), (plain(_zone_name(z)), ""), (z.band[0], ""),
                             (", ".join(gws[:2]), "") if gws else (MISSING, "", True), (names, "")])
            g.fill_table(table, rows)
            filled.append(" / ".join(header[:3]))
    return filled


def _label(obj) -> str:
    if isinstance(obj, dict):
        return str(obj.get("name") or obj.get("display") or "")
    return "" if obj is None else str(obj)
