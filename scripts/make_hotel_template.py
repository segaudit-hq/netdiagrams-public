"""Generate src/netdiagrams/data/H01-Hotel-Template.drawio, the hotel standard.

Eight sheets drawn for the fictional Alder Bay Hotel and Conference Center (site
H01): overview, logical, physical, wireless, traffic flows, failover, portfolio
(brand, management company and the sister property) and the flow register.
Every fact comes from scripts/hotel_template/site.py, the same source
scripts/make_hotel_sample.py turns into the sample NetBox export, so
`netdiagrams build --input sample-hotel.json` reproduces the template. The riser
(3e) and audit (3f) sheets are added by the build from NetBox's locations and
evidence, as for every site.

The look is the office standard's (scripts/make_office_template.py): its cards,
tables, links and icons, with icons of its own for the hotel's roles.

    python scripts/make_hotel_template.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hotel_template import site as S  # noqa: E402
from drawkit import (  # noqa: E402
    BAND, EDGE, FONT, NETBOX, NOTE, POINTS, RACK_PILL, SUBTITLE, TITLE, Page, _svg, esc, mxfile, sub, zone_style)
import make_office_template as O  # noqa: E402  (the office look: cards, tables, links, icons)
from make_office_template import (  # noqa: E402
    BODY_CELL, CARD, CID_TAG, HEADING, IP_TAG, KEY_CELL, PORT_LABEL, SMALL, SN_TAG, TEXT, _circle, _line, _rect,
    group_style, link, note, pill_label, resize, table)

SLATE, GREY, BLUE, TEAL, GREEN, VIOLET, PINK, CYAN, ORANGE, SKY, RED, INDIGO, AMBER = (
    "#334155", "#475569", "#2563EB", "#0D9488", "#16A34A", "#7C3AED", "#DB2777", "#0891B2", "#D97706", "#0284C7",
    "#DC2626", "#4F46E5", "#A16207")

# ------------------------------------------------------------------ icons: the office set plus the hotel's roles
ICONS = dict(O.ICONS)
ICONS.update({
    "router": _svg("#E8E8FD", _circle(16, 16, 9, INDIGO) + _line("11,16 21,16", INDIGO) + _line("18.5,13.5 21,16 18.5,18.5", INDIGO)
                   + _line("16,11 16,21", INDIGO) + _line("13.5,13.5 16,11 18.5,13.5", INDIGO)),
    "guest-gateway": _svg("#FCEFE0", _rect(6, 12, 20, 10, ORANGE, rx=2.5) + _line("10,17 13,17", ORANGE)
                          + f'<circle cx="21" cy="17" r="1.1" fill="{ORANGE}"/>' + _line("12.5,9 16,6.5 19.5,9", ORANGE)),
    "pos-server": _svg("#FCE4E4", _rect(9, 7, 14, 7.5, RED) + _rect(9, 17.5, 14, 7.5, RED)
                       + f'<circle cx="12.5" cy="10.75" r="1.1" fill="{RED}"/><circle cx="12.5" cy="21.25" r="1.1" fill="{RED}"/>'),
    "pos-terminal": _svg("#FCE4E4", _rect(7, 7, 18, 11, RED, rx=1.5) + _line("16,18 16,21", RED) + _line("10,24.5 22,24.5", RED)
                         + _line("12,21 20,21", RED)),
    "payment-terminal": _svg("#FCE4E4", _rect(10, 6, 12, 20, RED, rx=2) + _rect(12.5, 8.5, 7, 4, RED, rx=0.5, width=1.3)
                             + _line("13,16.5 19,16.5", RED, 1.4) + _line("13,19.5 19,19.5", RED, 1.4) + _line("13,22.5 19,22.5", RED, 1.4)),
    "call-server": _svg("#E0F0F9", _rect(9, 7, 14, 18, SKY, rx=2) + _line("12,11 20,11", SKY) + _line("12,15 20,15", SKY)
                        + _line("12.5,21 14,19 18,19 19.5,21", SKY)),
    "tv-headend": _svg("#EFE7FD", _rect(6, 8, 20, 13, VIOLET, rx=2) + _line("13,25 16,21 19,25", VIOLET)
                       + _line("10,12 15,12", VIOLET, 1.4)),
    "lock-gateway": _svg("#EFE7FD", _rect(9, 14, 14, 11, VIOLET, rx=2.5) + _line("12,14 12,11 13.2,8.6 16,7.5 18.8,8.6 20,11 20,14", VIOLET)
                         + _line("13,19.5 19,19.5", VIOLET, 1.4) + _line("16,17 16,22", VIOLET, 1.4)),
    "key-encoder": _svg("#EFE7FD", _rect(6, 16, 20, 8, VIOLET, rx=2) + _rect(11, 7, 10, 12, VIOLET, rx=1.5, fill="#EFE7FD")
                        + _line("13.5,10.5 18.5,10.5", VIOLET, 1.3)),
    "room-controls": _svg("#EFE7FD", _rect(8, 7, 16, 18, VIOLET, rx=3) + _circle(16, 14.5, 4.2, VIOLET)
                          + _line("16,14.5 18,12.5", VIOLET, 1.4) + _line("12.5,22 19.5,22", VIOLET, 1.4)),
    "bms-server": _svg("#E3F4E8", _rect(7, 7, 18, 12, GREEN, rx=1.5) + _line("10,15 13,12 16,14 21,10", GREEN, 1.4)
                       + _line("16,19 16,23", GREEN) + _line("11,24.5 21,24.5", GREEN)),
    "building-controller": _svg("#E3F4E8", _rect(8, 7, 16, 18, GREEN, rx=2) + _circle(16, 15, 5, GREEN)
                                + _line("16,15 16,11.5", GREEN, 1.4) + _line("16,15 18.5,16.5", GREEN, 1.4)),
    "elevator-monitor": _svg("#E3F4E8", _rect(9, 6, 14, 20, GREEN, rx=1.5) + _line("16,6 16,26", GREEN, 1.3)
                             + _line("11,12.5 13,10.5 15,12.5", GREEN, 1.3) + _line("17,19.5 19,21.5 21,19.5", GREEN, 1.3)),
    "safety-gateway": _svg("#FBE4EF", _line("10,21 10,15 11.2,11.2 14,9 18,9 20.8,11.2 22,15 22,21", PINK)
                           + _line("8,21 24,21", PINK) + _line("14.5,24 17.5,24", PINK)),
    "bed": _svg("#FCEFE0", _line("6,24 6,9", ORANGE) + _line("6,17 26,17 26,24", ORANGE) + _rect(8, 12.5, 5, 4.5, ORANGE, rx=1.5)
                + _line("14,13 24,13 26,17", ORANGE)),
    "events": _svg("#FEF6DC", _circle(10, 12, 2.8, AMBER, width=1.5) + _circle(16, 10.5, 2.8, AMBER, width=1.5)
                   + _circle(22, 12, 2.8, AMBER, width=1.5) + _line("5.5,22 7.5,18 12.5,18 14.5,22", AMBER, 1.5)
                   + _line("11.5,20 13.5,16 18.5,16 20.5,20", AMBER, 1.5) + _line("17.5,22 19.5,18 24.5,18 26.5,22", AMBER, 1.5)),
    "plate": _svg("#FCE4E4", _circle(16, 16, 7, RED) + _circle(16, 16, 3.5, RED, width=1.3) + _line("6,8 6,24", RED, 1.4)
                  + _line("26,8 26,24", RED, 1.4)),
    "brand": _svg("#E8E8FD", _line("16,6.5 18.6,12.2 24.8,12.6 20,16.6 21.6,22.6 16,19.2 10.4,22.6 12,16.6 7.2,12.6 13.4,12.2 16,6.5", INDIGO)),
})
ICON_FOR_ROLE = {**O.ICON_FOR_ROLE, **{r: r for r in (
    "router", "guest-gateway", "pos-server", "pos-terminal", "payment-terminal", "call-server", "tv-headend",
    "lock-gateway", "key-encoder", "room-controls", "bms-server", "building-controller", "elevator-monitor",
    "safety-gateway")}}


def label_style(icon: str, size: int = 22, left: int = 28, font: int = 10, valign: str = "top", arc: int = 12) -> str:
    return (f"shape=label;rounded=1;absoluteArcSize=1;arcSize={arc};fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;"
            f"shadow=1;align=left;verticalAlign={valign};spacingTop=5;spacingLeft={left};fontSize={font};fontColor=#0F172A;"
            f"whiteSpace=wrap;html=1;{POINTS}{FONT}image=data:image/svg+xml,{ICONS[icon]};imageWidth={size};"
            f"imageHeight={size};imageAlign=left;imageVerticalAlign=middle;")


DEVICE_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 30, 38, 11)
SMALL_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 22, 28, 10)
MEMBER_ROW = lambda role: label_style(ICON_FOR_ROLE.get(role, "access-switch"), 16, 22, 9)

LEGEND_ITEMS = [("firewall", "Firewall (HA pair)"), ("router", "Brand router (the brand's)"),
                ("guest-gateway", "Guest gateway (Wi-Fi vendor's)"), ("core-switch", "Core switch / stack"),
                ("access-switch", "Access switch / stack"), ("access-point", "Wireless AP (cloud managed)"),
                ("hypervisor", "Virtualization host"), ("pos-server", "POS server"),
                ("pos-terminal", "POS workstation"), ("payment-terminal", "Card terminal"),
                ("call-server", "Call server"), ("tv-headend", "TV head-end"), ("room-controls", "Room controls"),
                ("lock-gateway", "Lock gateway"), ("key-encoder", "Key encoder"), ("bms-server", "BMS supervisor"),
                ("building-controller", "Plant controller"), ("elevator-monitor", "Elevator monitor"),
                ("nvr", "Video recorder"), ("camera", "Camera"), ("door-controller", "Door controller"),
                ("safety-gateway", "Safety buttons"), ("printer", "Printer"), ("ups", "UPS"),
                ("console-server", "Out-of-band console"), ("cloud", "Cloud service")]


def legend(p: Page, x: float, y: float, flows: bool = True, width: float = 360) -> float:
    """The hotel legend: icons, line meanings and the zone colors. Returns its height."""
    layer = p.layer("Legend")
    rows = -(-len(LEGEND_ITEMS) // 2)
    lines = [("#64748B", 1.6, "", "Link · pill = Po · speed · media · tag = port"),
             ("#64748B", 2.5, "", "Weight = speed (thicker = 10G and up)")]
    if flows:
        lines += [("#16A34A", 1.6, "endArrow=block;endFill=1;", "Permitted flow (initiator → responder)"),
                  ("#EA580C", 1.6, "dashed=1;endArrow=block;endFill=1;", "Conditional (MFA · window · one destination)"),
                  ("#DC2626", 1.6, "dashed=1;", "Denied path")]
    zone_rows = -(-len(S.ZONES) // 4)
    h = 40 + rows * 24 + 6 + len(lines) * 22 + 10 + zone_rows * 26 + 14
    p.cell(layer, "", CARD, x, y, width, h)
    p.cell(layer, "Legend", HEADING, x + 16, y + 10, 200, 22)
    for n, (icon, text) in enumerate(LEGEND_ITEMS):
        col, row = n % 2, n // 2
        p.cell(layer, esc(text),
               f"shape=label;html=1;fillColor=none;strokeColor=none;align=left;verticalAlign=middle;spacingLeft=24;"
               f"fontSize=10;fontColor=#334155;{FONT}image=data:image/svg+xml,{ICONS[icon]};imageWidth=18;imageHeight=18;"
               "imageAlign=left;imageVerticalAlign=middle;", x + 14 + col * 172, y + 36 + row * 24, 166, 24)
    ly = y + 36 + rows * 24 + 6
    for color, w, extra, text in lines:
        p.edge(layer, None, None, f"endArrow=none;html=1;strokeColor={color};strokeWidth={w};{extra}",
               src_pt=(x + 18, ly + 10), tgt_pt=(x + 58, ly + 10))
        if "Denied" in text:
            p.cell(layer, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
                   "fontSize=10;fontStyle=1;" + FONT, x + 64, ly, 20, 20)
        p.cell(layer, esc(text), "text;html=1;fontSize=10;fontColor=#334155;align=left;"
               "verticalAlign=middle;" + FONT, x + 88, ly, 270, 20)
        ly += 22
    ly += 10
    for n, z in enumerate(S.ZONES):
        col, row = n % 4, n // 4
        fill, stroke, font = z[6]
        p.cell(layer, esc(z[1]),
               f"rounded=1;absoluteArcSize=1;arcSize=12;fillColor={fill};strokeColor={stroke};fontColor={font};"
               "fontSize=9;fontStyle=1;html=1;whiteSpace=wrap;" + FONT, x + 14 + col * 84, ly + row * 26, 80, 22)
    return h


DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"
OUT = DATA / "H01-Hotel-Template.drawio"
DATE = "2026-10-15"
PROJECT = "Hotel network standard"
SHEETS = 8
SITE = S.SITE["code"]

DEV = {d["name"]: d for d in S.DEVICES}
CABLE_OF = {}
for _c in S.CABLES:
    for _end in _c["a"] + _c["b"]:
        CABLE_OF.setdefault(_end.split(":")[0], []).append(_c)
ATTR_ORDER = ["name", "role", "manufacturer", "device_type", "platform", "serial", "asset_tag", "status", "site",
              "location", "rack", "position", "face", "primary_ip4", "virtual_chassis", "vc_position", "description",
              "tags", "cf_sw_version", "cf_support_contract", "cf_lifecycle", "x_modules", "x_power"]
ZONE_LOOK = {z[0]: z[6] for z in S.ZONES}
MGMT_IPS = "3 · Mgmt IPs (hide before sharing)"
LINKS = "2 · Links (Po · speed · VLANs)"


# ------------------------------------------------------------------ objects

def title_block(p, *args) -> None:
    """drawkit's title block, its project row tall enough for two lines: the long hotel name wraps."""
    t = p.title_block(*args)
    row = [el for el in p.root if el.get("parent") == t][1]
    for el in [row, *[c for c in p.root if c.get("parent") == row.get("id")]]:
        (el if el.tag == "mxCell" else el.find("mxCell")).find("mxGeometry").set("height", "31")
    geo = p.find(t).find("mxGeometry")
    geo.set("height", "57")
    geo.set("y", f"{float(geo.get('y')) - 3:g}")

def dev_attrs(name: str) -> dict:
    d = DEV[name]
    a = {k: str(d.get(k, "") or "") for k in ATTR_ORDER}
    a["site"] = SITE
    a["face"] = "front" if d.get("position") else ""
    if d.get("cf_ap_mode"):
        a["cf_ap_mode"] = d["cf_ap_mode"]
    if d.get("cf_criticality"):
        a["cf_criticality"] = d["cf_criticality"]
    tooltip = "\n".join(f"{k}: {v}" for k, v in a.items())
    return {"placeholders": "1", "tooltip": tooltip, **a, "link": f"{NETBOX}/dcim/devices/?name={name}",
            "linkTarget": "_blank"}


def device(p: Page, layer: str, name: str, x, y, w=230, h=56, small=False, label=None, ip=True, serial=True,
           pill=True) -> str:
    d = DEV[name]
    style = (SMALL_CARD if small else DEVICE_CARD)(d["role"])
    text = label or ('<b>%name%</b><br>' + sub("%device_type%"))
    cid = p.cell(layer, text, style, x, y, w, h, dev_attrs(name))
    if pill and d.get("rack"):
        p.cell(cid, "%rack% · U%position%", RACK_PILL, w - 64, 6, 58, 13, {"placeholders": "1"})
    if ip and d.get("primary_ip4"):
        p.cell(p.layer(MGMT_IPS), d["primary_ip4"].split("/")[0], IP_TAG, x + (30 if small else 40), y + h - 18,
               90, 14)
    if serial and d.get("serial"):
        p.cell(p.layer("3b · Serial numbers"), f"SN {d['serial']}", SN_TAG, x + w - 100, y + h - 18, 94, 14)
    return cid


def stack(p: Page, layer: str, vc: str, x, y, w, members: list[str], zone: str, note_text: str) -> str:
    """A virtual chassis: a tinted box with a row per member."""
    fill, stroke, font = ZONE_LOOK[zone]
    first = DEV[members[0]]
    h = 34 + 26 * len(members) + 4
    label = f"%name%<br>{sub(esc(note_text), 9, '#64748B')}"
    sid = p.cell(layer, label, group_style(fill, stroke, font, stack=True), x, y, w, h,
                 {"placeholders": "1", "tooltip": f"NetBox virtual chassis {vc} · {first['location']} {first['rack']}",
                  "object": "dcim.virtualchassis", "name": vc, "location": first["location"], "rack": first["rack"],
                  "link": f"{NETBOX}/dcim/virtual-chassis/?name={vc}", "linkTarget": "_blank"})
    for n, m in enumerate(members):
        d = DEV[m]
        role_word = "conductor" if n == 0 else ("standby" if n == 1 else "member")
        up = " ↑" if any(m in e for c in CABLE_OF.get(m, []) if c["lag"].startswith("Po")
                         for e in c["a"] + c["b"]) else ""
        text = (f"<b>Sw{n + 1}</b> · {role_word}{up} <span style=\"color:#94A3B8;font-family:JetBrains Mono;"
                f"font-size:9px\">&nbsp;U%position% · SN %serial%</span>")
        p.cell(sid, text, MEMBER_ROW(d["role"]), 10, 34 + 26 * n, w - 20, 22, dev_attrs(m))
    if first.get("primary_ip4"):
        p.cell(p.layer(MGMT_IPS), first["primary_ip4"].split("/")[0], IP_TAG, x + w - 80, y + 3, 76, 14)
    return sid


def cable_by_label(label: str) -> dict:
    return next(c for c in S.CABLES if label in c["labels"])


def cable_to(name: str) -> dict:
    """The cable whose B end is this device (its uplink or drop)."""
    return next(c for c in S.CABLES if any(e.split(":")[0] == name for e in c["b"]))


def zone_box(p: Page, layer: str, zone: str, x, y, w, h, title=None, valign="top", size=10) -> str:
    fill, stroke, font = ZONE_LOOK[zone]
    z = S.ZONE[zone]
    text = title if title is not None else f"<b>{z[1]}</b> · {esc(z[2])}"
    return p.cell(layer, text, zone_style(fill, stroke, font, valign, size), x, y, w, h)


def icon_card(p: Page, layer: str, x, y, w, h, icon: str, title: str, text: str, size=28, title_size=12,
              attrs: dict | None = None) -> str:
    style = label_style(icon, size, size + 18, title_size, "middle", 16) + "spacingTop=0;"
    return p.cell(layer, f"<b>{esc(title)}</b><br>{sub(esc(text), 10)}", style, x, y, w, h, attrs=attrs)


def gate_bar(p: Page, layer: str, x, y, w, text: str) -> str:
    style = label_style("shield", 16, 30, 10, "middle", 22).replace("fillColor=#FFFFFF", "fillColor=#F1F5F9")
    return p.cell(layer, text, style.replace("shadow=1;", "shadow=0;") + "spacingTop=0;", x, y, w, 30)


def drop(p: Page, sw: str, sw_box: tuple, card: str, card_box: tuple, cable: dict, lane: float) -> None:
    """An end device's drop: down a lane beside its column from the stack's bottom, then into the card's left side."""
    sx, sy, sw_w, sh = sw_box
    cx, cy, cw, ch = card_box
    link(p, sw, card, cable, "", exit=(round((lane - sx) / sw_w, 4), 1), entry=(0, 0.5),
         points=[(lane, cy + ch / 2)], weight=1.2, color="#94A3B8")


def fan(p: Page, src: str, src_box: tuple, targets: list[tuple[str, tuple, dict, str, str]], top_level: float,
        step: float = 12) -> None:
    """Uplinks from a wide box's bottom to boxes below it, nested so no two cross.

    Each target is (shape, box, cable, port text at the source, port text at the target). A target under the
    source drops straight; the others leave the source's bottom near its nearest corner and turn at a level of
    their own, the farthest out turning highest."""
    sx, sy, sw, sh = src_box
    straight, left, right = [], [], []
    for t in targets:
        tx = t[1][0] + t[1][2] / 2
        (straight if sx + 20 <= tx <= sx + sw - 20 else left if tx < sx else right).append(t)
    for t in straight:
        tx = t[1][0] + t[1][2] / 2
        link(p, src, t[0], t[2], exit=(round((tx - sx) / sw, 4), 1), entry=(0.5, 0), ports=(t[3], t[4]))
    # The farthest target leaves from the outermost exit and turns highest.
    for side, items in (("left", sorted(left, key=lambda t: t[1][0])), ("right", sorted(right, key=lambda t: -t[1][0]))):
        for k, t in enumerate(items):
            tx = t[1][0] + t[1][2] / 2
            ex = sx + 14 + 16 * k if side == "left" else sx + sw - 14 - 16 * k
            level = top_level + step * k
            link(p, src, t[0], t[2], exit=(round((ex - sx) / sw, 4), 1), entry=(0.5, 0),
                 points=[(ex, level), (tx, level)], ports=(None, t[4]))


def row_slots(x0: float, count: int, width: float, gap: float, avoid: list[float], margin: float = 18) -> list[float]:
    """``count`` x positions for cards ``width`` wide from x0, skipping the vertical lines at ``avoid``."""
    out, x = [], x0
    while len(out) < count:
        clash = [a for a in avoid if x - margin < a < x + width + margin]
        if clash:
            x = max(clash) + margin
            continue
        out.append(x)
        x += width + gap
    return out


# ------------------------------------------------------------------ 1 overview
def overview() -> Page:
    p = Page("overview", "1 · Overview — for management", 2000, 1150, prefix="h")
    lay = p.layer("Overview")
    p.cell(lay, "How the hotel network is protected", TITLE, 24, 18, 1000, 32)
    p.cell(lay, "Management overview: no technical detail. What holds card data, what guests touch, and what "
           "stops if the internet goes.", SUBTITLE, 24, 52, 1100, 22)
    x, w = 170, 1010
    rows = [(100, "Outside", "#64748B"), (300, "Payments &amp; operations", "#DC2626"),
            (536, "Guests, events &amp; rooms", "#D97706"), (790, "Building, safety &amp; management", "#16A34A")]
    for y, text, color in rows:
        p.cell(lay, f"<b>{text}</b>", "text;html=1;align=right;verticalAlign=middle;fontSize=10;"
               f"fontColor={color};whiteSpace=wrap;{FONT}", 40, y, 120, 60)
    outside = icon_card(p, lay, x, 92, w, 76, "cloud", "Internet, the brand and the vendors",
                        "The internet lines · the brand's own circuit and router · the cloud PMS and reservations · "
                        "the card processor · Kestrel's VPN and monitoring")
    gate_bar(p, lay, x, 214, w, "<b>Security gate</b> · the firewall: everything between the outside and the "
             "hotel passes through it")
    biz = p.cell(lay, "<b>Payments and operations</b> · the money and the front office",
                 zone_style("#FEF5F5", "#F5B5B5", "#DC2626", "top", 12), x, 270, w, 140)
    for n, (icon, title, text) in enumerate([
            ("payment-terminal", "Card payments", "Front desk, restaurant, bar, spa"),
            ("users", "Front office", "PMS, sales, housekeeping"),
            ("server", "Property servers", "Interfaces to locks, TV, phones"),
            ("phone", "Phones", "Rooms, wake-up calls")]):
        icon_card(p, lay, x + 16 + n * 248, 306, 232, 86, icon, title, text, 24, 11)
    gate_bar(p, lay, x, 440, w, "<b>Same security gate</b> · card systems have their own door: nothing else in the "
             "hotel reaches the terminals or the POS server")
    guests = p.cell(lay, "<b>Guests, events and rooms</b> · used by everyone, trusted by no one",
                    zone_style("#FDF8F3", "#F2CFA8", "#D97706", "top", 12), x, 496, w, 150)
    guest = icon_card(p, lay, x + 16, 532, 316, 92, "bed", "Guest Wi-Fi",
                      "The internet and nothing else; guests can't see each other")
    icon_card(p, lay, x + 346, 532, 316, 92, "events", "Meetings and events",
              "Each booking gets its own network; one event can't see another")
    icon_card(p, lay, x + 676, 532, 318, 92, "tv-headend", "Room technology",
              "TVs, casting, locks and thermostats talk to their own systems")
    gate_bar(p, lay, x, 676, w, "<b>Same security gate</b> · building systems, cameras and network management "
             "are opened only for the people who need them")
    build = p.cell(lay, "<b>Building, safety and management</b> · the systems that keep the hotel running",
                   zone_style("#F4FAF5", "#B4DDBF", "#16A34A", "top", 12), x, 732, w, 150)
    icon_card(p, lay, x + 16, 768, 316, 92, "building-controller", "Plant room",
              "Chillers, boilers, air handlers, kitchen and pool; no internet")
    icon_card(p, lay, x + 346, 768, 316, 92, "camera", "Safety and security",
              "Cameras record on site; staff safety buttons reach their monitoring service")
    mgmt = icon_card(p, lay, x + 676, 768, 318, 92, "wrench", "Network management",
                     "Firewalls, switches, Wi-Fi and power; IT and Kestrel only")
    arrows = p.layer("Arrows")
    p.edge(arrows, outside, mgmt, "endArrow=block;endFill=1;html=1;strokeColor=#7C3AED;strokeWidth=1.6;dashed=1;"
           "fontSize=9;fontColor=#4C1D95;labelBackgroundColor=#FFFFFF;" + FONT, "", exit=(1, 0.7), entry=(1, 0.5),
           points=[(1206, 145.2), (1206, 814)])
    p.cell(arrows, "<b>Kestrel and the BMS contractor</b>: in through the gate, with MFA ↓",
           "text;html=1;align=right;verticalAlign=middle;fontSize=9;fontColor=#6D28D9;" + FONT, 860, 216, 310, 26)
    p.edge(arrows, guest, biz, "endArrow=none;html=1;strokeColor=#DC2626;strokeWidth=1.6;dashed=1;fontSize=9;"
           "fontColor=#991B1B;labelBackgroundColor=#FFFFFF;" + FONT, "No path from guests<br>to card systems",
           exit=(0.5, 0), entry=(0.1717, 1))
    p.cell(arrows, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
           "fontSize=10;fontStyle=1;" + FONT, 334, 414, 20, 20)
    rx = 1240
    promises = p.layer("Business promises (Alder Bay's; rewrite for your hotel)")
    p.cell(promises, "", "rounded=1;arcSize=2;html=1;fillColor=none;strokeColor=none;", rx - 12, 120, 724, 860)
    p.cell(lay, "What this means for the business", HEADING.replace("fontSize=12", "fontSize=14"), rx, 92, 700, 24)
    cards = [
        ("lock", "Guests can't reach card data, the front desk or the plant",
         "Guests and events are on their own networks with the internet only."),
        ("payment-terminal", "Card systems sit behind their own door",
         "Terminals encrypt the card; the POS posts charges to rooms with no card data."),
        ("router", "The brand and the vendors get named doors, not keys to the house",
         "The brand router, the Wi-Fi vendor's gateway and every vendor cloud end on the firewall."),
        ("building-controller", "The plant never talks to the internet",
         "The BMS contractor comes in through the VPN with MFA, in a booked window, and it is logged."),
        ("isp", "One internet line can fail and check-in carries on",
         "Two providers on different technologies; the backup takes over on its own."),
        ("power", "No single box takes the hotel down",
         "A firewall pair, a core stack, two hosts and two UPSs: one failure is a ticket, not an outage."),
        ("key-encoder", "If the cloud PMS goes, keys still get made",
         "The lock server and encoders work on site; the night audit has an offline procedure."),
    ]
    for n, (icon, title, text) in enumerate(cards):
        icon_card(p, promises, rx, 128 + n * 122, 700, 106, icon, title, text, 26, 12)
    title_block(p, p.layer("Border & title block"), "All", "Overview — management", f"1 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 2 logical
def vlan_rows(zone: str) -> list[list]:
    return [[(str(vid), f"{NETBOX}/ipam/vlans/?vid={vid}&site=h01"), name, subnet, gw]
            for vid, name, z, subnet, gw in S.VLANS if z == zone]


VLAN_COLS = [("VLAN", 44), ("NAME", 120), ("SUBNET", 130), ("GATEWAY", 100)]
VLAN_W = sum(w for _, w in VLAN_COLS)


def logical() -> Page:
    layout = {"BUSINESS": ["zone-payments", "zone-ops", "zone-servers", "zone-voice"],
              "GUEST": ["zone-guest", "zone-events", "zone-roomtech"],
              "BUILDING": ["zone-building", "zone-safety", "zone-mgmt"]}
    heights = {code: 78 + 22 * (1 + max(len(vlan_rows(z)) for z in zones)) + 70 for code, zones in layout.items()}
    bands = {"OUT": (96, 170), "EDGE": (282, 250)}
    y = 548
    for code in ("BUSINESS", "GUEST", "BUILDING"):
        bands[code] = (y, heights[code])
        y += heights[code] + 16
    p = Page("logical", "2 · Logical — Zones, VLANs, Subnets", 2400, y + 110, prefix="h")
    lb, lz = p.layer("Bands"), p.layer("Zones")
    lt = p.layer("VLAN tables")
    p.title(lb, f"{SITE} · {S.SITE['name']} — Logical",
            esc("Zones · VLANs · subnets · gateways. Every VLAN lives in one zone. Inside VLANs route on the firewall"
                "; the guest and event VLANs route on the guest gateway, whose outside leg is a firewall port."))
    W = 1880
    for code, label, _ in S.BANDS:
        by, bh = bands[code]
        p.band(lb, by, bh, code, label.split(" · ")[0], W)
    # OUTSIDE: providers, the brand and the management company, no VLANs.
    zone_box(p, lz, "zone-internet", 100, 108, 1060, 146)
    p.cell(lz, esc(S.ZONE["zone-internet"][5]), SMALL, 112, 132, 900, 18)
    for n, (icon, title, text) in enumerate([
            ("isp", "ISP-A", "H01-ISP-A-01 · the main line"), ("isp", "ISP-B", "H01-ISP-B-01 · backup · guests prefer it"),
            ("cloud", "Cloud PMS", "Brand-mandated · reservations"), ("payment-terminal", "Processor", "Card authorization"),
            ("cloud", "Vendor clouds", "POS, TV, locks, Wi-Fi, SIP")]):
        icon_card(p, lz, 112 + n * 208, 160, 198, 80, icon, title, text, 24, 11)
    zone_box(p, lz, "zone-brand", 1170, 108, 720, 146)
    p.cell(lz, esc(S.ZONE["zone-brand"][5]), SMALL, 1182, 132, 700, 18)
    for n, (icon, title, text) in enumerate([
            ("router", "Larkline brand", "Router + its own circuit · brand systems"),
            ("shield", "Kestrel VPN", "IPsec · MFA for people"), ("cloud", "Kestrel SIEM", "Syslog over TLS · NOC")]):
        icon_card(p, lz, 1182 + n * 234, 160, 224, 80, icon, title, text, 24, 11)
    # EDGE: the firewall pair and its interfaces.
    zone_box(p, lz, "zone-edge", 100, 294, 1790, 226)
    p.cell(lz, esc(S.ZONE["zone-edge"][5]), SMALL, 112, 318, 900, 18)
    p.cell(lz, "<b>H01-FW</b> · HA pair (active / passive)",
           zone_style("#FFFFFF", "#94A3B8", "#334155", "top", 10), 112, 346, 300, 150)
    for n, name in enumerate(("H01-FW-01", "H01-FW-02")):
        device(p, p.layer("Devices"), name, 124, 376 + n * 60, 276, 52, ip=False, serial=False, pill=False)
    p.cell(lz, "<b>Firewall interfaces</b>", HEADING.replace("fontSize=12", "fontSize=10"), 440, 346, 300, 20)
    table(p, lt, 440, 370, [("INTERFACE", 140), ("ZONE", 180), ("IP / PREFIX", 200)], [
          ["wan1", "INTERNET", "203.0.113.2/29"], ["wan2", "INTERNET", "DHCP (ISP-B)"],
          ["x1–x2 (Po1 / Po2)", "inside zones", ".1 on VLANs 10–99"],
          ["brand", "BRAND", "10.40.250.1/29"],
          ["dmz-guest", "GUEST", "10.40.251.1/29"]], row_h=22)
    p.cell(lz, "<b>Remote access and the guest side</b>", HEADING.replace("fontSize=12", "fontSize=10"), 1000, 346,
           400, 20)
    table(p, lt, 1000, 370, [("POOL", 70), ("NAME", 120), ("SUBNET", 130), ("WHO", 240)], [
          ["—", "VPN-POOL", "10.40.200.0/24", "Hotel IT, MFA"],
          ["—", "IPSEC-KESTREL", "10.200.0.0/16", "Kestrel IT, NOC and SIEM; MFA for people"],
          ["—", "BMS-VPN", "10.40.201.0/28", "BMS contractor, booked windows"],
          ["—", "GUEST-DMZ", "10.40.251.0/29", "Guest gateway outside leg (NAT to ISP-B)"]], row_h=22)
    for code, zones in layout.items():
        by, bh = bands[code]
        bw = (1790 - 10 * (len(zones) - 1)) / len(zones)
        for n, zone in enumerate(zones):
            zx = 100 + n * (bw + 10)
            z = S.ZONE[zone]
            zone_box(p, lz, zone, zx, by + 12, bw, bh - 24, f"<b>ZONE {z[1]}</b> · {esc(z[2])}")
            p.cell(lz, esc(z[5]), SMALL, zx + 12, by + 36, bw - 24, 40)
            table(p, lt, zx + 12, by + 78, VLAN_COLS, vlan_rows(zone), row_h=22)
            p.cell(lz, sub("Lives here: " + esc(z[4]), 9, "#64748B"), SMALL, zx + 12, by + bh - 62, bw - 24, 36)
    legend(p, 2000, 96, flows=False)
    title_block(p, p.layer("Border & title block"), SITE, "Logical — zones, VLANs", f"2 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 3 physical
CARD_W, CARD_H, PITCH, ROW = 164, 56, 210, 66


def physical() -> Page:
    p = Page("physical", "3 · Physical — Devices, Uplinks, Trunks", 2880, 2600, prefix="h")
    lb = p.layer("Bands")
    lz = p.layer("Zones (groups · stacks)")
    p.layer(LINKS)
    ld = p.layer("1 · Devices")
    for name in (MGMT_IPS, "3b · Serial numbers", "4 · Circuit IDs (hide before sharing)"):
        p.layer(name)
    p.title(lb, f"{SITE} · {S.SITE['name']} — Physical",
            esc("Devices · uplinks · port-channels · trunked VLANs · rack and U on every racked device. One access "
                "stack per closet; end devices hang off their floor's stack. Hover a device or Edit Data (Ctrl+M) "
                "for its NetBox record."))
    W = 2832
    p.band(lb, 96, 130, "ISP", "PROVIDERS", W)
    p.band(lb, 242, 430, "MDF", "MDF-LL · LOWER LEVEL", W)
    p.band(lb, 688, 520, "IDF", "CLOSETS · ONE STACK EACH", W)

    # Providers and circuits: the two ISPs to the firewalls, the brand's circuit to its own router.
    circ_of = {c["cid"]: c for c in S.CIRCUITS}
    isp = {}
    for cid, cx, name in (("H01-BRAND-01", 150, "BRAND"), ("H01-ISP-A-01", 700, "ISP-A"), ("H01-ISP-B-01", 1240, "ISP-B")):
        circ = circ_of[cid]
        isp[cid] = p.cell(ld, f"<b>{name}</b><br>{sub(esc(circ['label']))}",
                          label_style("router" if name == "BRAND" else "isp", 26, 36, 11, "middle", 12)
                          + "spacingTop=0;", cx, 118, 300, 60)
        p.cell(p.layer("4 · Circuit IDs (hide before sharing)"),
               f"CID {cid}<br>{esc(circ['provider'])} · {esc(circ['speed'])}", CID_TAG, cx + 306, 132, 170, 32)
    p.cell(p.layer("4 · Circuit IDs (hide before sharing)"), "CID H01-SIP-01<br>SIP trunk over ISP-A (logical)",
           CID_TAG, 1800, 132, 220, 32)

    # The edge row: the brand router, the firewall pair, the guest gateway.
    zone_box(p, lz, "zone-brand", 120, 262, 360, 104, "<b>BRAND</b> · the brand's box in our rack")
    zone_box(p, lz, "zone-edge", 600, 262, 1120, 104, "<b>H01-FW</b> · HA pair (active / passive) · inspects every zone")
    zone_box(p, lz, "zone-guest", 1800, 262, 400, 104, "<b>GUEST</b> · the Wi-Fi vendor's gateway")
    brand = device(p, ld, "H01-BRAND-RTR-01", 140, 292, 320, 58)
    fw1 = device(p, ld, "H01-FW-01", 640, 292, 260, 58)
    fw2 = device(p, ld, "H01-FW-02", 1380, 292, 260, 58)
    gw = device(p, ld, "H01-GW-01", 1840, 292, 320, 58)
    link(p, fw1, fw2, cable_by_label("H01-CBL-00005"), "HA · 1G · Cat6", exit=(1, 0.5), entry=(0, 0.5),
         ports=("ha", "ha"), weight=1.4)
    link(p, brand, fw1, cable_by_label("H01-CBL-00006"), "1G · Cat6", exit=(1, 0.5), entry=(0, 0.5),
         ports=("lan1", "brand"), weight=1.4, color="#6366F1")
    link(p, gw, fw2, cable_by_label("H01-CBL-00009"), "1G · Cat6", exit=(0, 0.5), entry=(1, 0.5),
         ports=("wan2", "dmz-guest"), weight=1.4, color="#EA580C")
    link(p, brand, fw2, cable_by_label("H01-CBL-00007"), "", exit=(0.5, 1), entry=(0.25, 1),
         points=[(300, 384), (1445, 384)], ports=("lan2", "brand"), weight=1.4, color="#6366F1")
    link(p, gw, fw1, cable_by_label("H01-CBL-00008"), "", exit=(0.7, 1), entry=(0.85, 1),
         points=[(2064, 396), (861, 396)], ports=("wan1", "dmz-guest"), weight=1.4, color="#EA580C")
    lc = p.layer(LINKS)
    edge_style = (EDGE.replace("strokeColor=#64748B", "strokeColor=#94A3B8").replace("strokeWidth=1.6", "strokeWidth=1.4")
                  + "labelBackgroundColor=#DBEAFE;labelBorderColor=#2563EB;")
    fw_x = {0: 640, 1: 1380}
    for n, cid in enumerate(("H01-ISP-A-01", "H01-ISP-B-01")):
        circ = circ_of[cid]
        for m, fw in enumerate((fw1, fw2)):
            attrs = {"object": "circuits.circuit", "cid": cid, "status": "active",
                     "x_handoff": f"H01-FW-0{m + 1}:wan{n + 1}", "x_speed": circ["speed"], "x_media": circ["media"],
                     "x_patch_a": "", "x_patch_b": ""}
            attrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in attrs.items()), **attrs,
                     "link": f"{NETBOX}/circuits/circuits/?cid={cid}", "linkTarget": "_blank"}
            same = n == m
            ex = (0.3 if m == 0 else 0.7, 1)
            en = (0.2 + 0.6 * n, 0)
            src_x = (700, 1240)[n] + 300 * ex[0]
            level = 236 if n == 0 else 250
            pts = [] if same else [(src_x, level), (fw_x[m] + 260 * en[0], level)]
            eid = p.edge(lc, isp[cid], fw, edge_style, esc(f"{circ['speed']} · {circ['media']}") if same else "",
                         attrs, exit=ex, entry=en, points=pts)
            p.edge_label(eid, f"wan{n + 1}", 1, 0, PORT_LABEL)
    battrs = {"object": "circuits.circuit", "cid": "H01-BRAND-01", "status": "active",
              "x_handoff": "H01-BRAND-RTR-01:wan", "x_speed": "200M", "x_media": "Cat6", "x_patch_a": "", "x_patch_b": ""}
    battrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in battrs.items()), **battrs,
              "link": f"{NETBOX}/circuits/circuits/?cid=H01-BRAND-01", "linkTarget": "_blank"}
    eid = p.edge(lc, isp["H01-BRAND-01"], brand, edge_style.replace("#94A3B8", "#6366F1"), "200M · Cat6", battrs,
                 exit=(0.5, 1), entry=(0.5, 0))
    p.edge_label(eid, "wan", 1, 0, PORT_LABEL)

    # Core stack: wide, so the firewalls, the guest gateway, the servers and every closet reach it straight.
    CX, CY, CW = 560, 560, 1720
    core = stack(p, lz, "H01-CORE", CX, CY, CW, ["H01-CORE-1", "H01-CORE-2"], "zone-mgmt",
                 "CX 6300M ×2 · VSF stack · MDF-LL R01 / R02 · every closet, server and edge box lands here")
    core_box = (CX, CY, CW, 90)
    fw1_x, fw2_x, gw_x = 640 + 130, 1380 + 130, 1840 + 60
    for fw, x, label, ports in ((fw1, fw1_x, "H01-CBL-00001", ("x1–x2", "1/1/1 · 2/1/1")),
                                (fw2, fw2_x, "H01-CBL-00003", ("x1–x2", "1/1/2 · 2/1/2"))):
        link(p, fw, core, cable_by_label(label), cable_by_label(label)["lag"], exit=(0.5, 1), entry=(round((x - CX) / CW, 4), 0), ports=ports,
             bundle=(x, 548))
    link(p, gw, core, cable_by_label("H01-CBL-00010"), "Po3", exit=(0.1875, 1), entry=(round((gw_x - CX) / CW, 4), 0),
         ports=("lan1–2", "1/1/3 · 2/1/3"), bundle=(gw_x, 548))

    # The server row between the edge and the core: each card drops straight into the core.
    servers = ["H01-POS-SRV-01", "H01-HV-01", "H01-HV-02", "H01-PBX-01", "H01-IPTV-01", "H01-GRMS-01",
               "H01-UPS-01", "H01-UPS-02", "H01-OOB-01"]
    slots = row_slots(CX + 12, len(servers), 150, 12, [fw1_x, fw2_x, gw_x], margin=22)
    for name, x in zip(servers, slots):
        d = DEV[name]
        z = S.ZONE[d["tags"]]
        zone_box(p, lz, d["tags"], x - 6, 418, 162, 108, f"<b>{z[1]}</b>", valign="top", size=9)
        cid = device(p, ld, name, x, 440, 150, 56, small=True, serial=False, pill=False)
        c = cable_to(name)
        core_port = " · ".join(e.split(":")[1] for e in c["a"])
        link(p, cid, core, c, "", exit=(0.5, 1), entry=(round((x + 75 - CX) / CW, 4), 0), ports=(None, core_port),
             bundle=(x + 75, 548) if len(c["labels"]) > 1 else None, weight=None if "10G" in c["speed"] else 1.2)
    note(p, 2420, 418, 420, 76, "Console lines (not cables in NetBox): OOB-01 serial 1–4 to FW-01, FW-02, CORE-1, "
         "CORE-2 · cellular to Kestrel. UPS runtime: R01 about 25 min, R02 about 30 min.")

    # Closets: one stack each, end devices in columns under it. Each drop runs down a lane on the left of its
    # column and turns into its card, so no two drops cross.
    SY = 740
    lane_gap = 7

    def column(sw, sw_box, x, top, names, zone_of_box=True):
        """Cards in one column from ``top``; returns the column's bottom."""
        lane0 = x - 12
        n_linked = [n for n in names if n and n in CABLE_OF]
        for r, name in enumerate(names):
            if not name:
                continue
            y = top + r * ROW
            cid = device(p, ld, name, x, y, CARD_W, CARD_H, small=True, pill=False, serial=False)
            if name in CABLE_OF:
                k = n_linked.index(name)
                drop(p, sw, sw_box, cid, (x, y, CARD_W, CARD_H), cable_to(name), lane0 - lane_gap * k)
        return top + len(names) * ROW

    def around(zone, x, top, first, last, title):
        """A zone box around rows first..last of the column at x, titled along its bottom."""
        zone_box(p, lz, zone, x - 38, top + first * ROW - 8, CARD_W + 44, (last - first) * ROW + CARD_H + 30,
                 title, valign="bottom")

    # Lower level: ACC-LL in MDF-LL R02, the plant, safety and the back of house.
    LLX, LLW = 90, 1060
    ll_members = ["H01-ACC-LL-1", "H01-ACC-LL-2"]
    ll = stack(p, lz, "H01-ACC-LL", LLX, SY, LLW, ll_members, "zone-mgmt",
               "CX 6200F 48G PoE ×2 · MDF-LL R02 · back of house, plant and safety")
    ll_box = (LLX, SY, LLW, 90)
    cols = [["H01-BMS-01", "H01-CHLR-01", "H01-CHLR-02", "H01-KIT-01"],
            ["H01-BLR-01", "H01-BLR-02", "H01-POOL-01"],
            ["H01-AHU-01", "H01-AHU-02", "H01-AHU-03", "H01-AHU-04"],
            ["H01-NVR-01", "H01-CAM-01", "H01-DOOR-01", "H01-SAFE-01"],
            ["H01-AP-LL-01", "H01-PRN-KIT-01"]]
    top = SY + 90 + 56
    xs = [LLX + 46 + c * PITCH for c in range(5)]
    tall = 3 * ROW + CARD_H + 30
    zone_box(p, lz, "zone-building", xs[0] - 38, top - 8, xs[2] + CARD_W + 6 - (xs[0] - 38), tall,
             "<b>BUILDING</b> · central plant and kitchen · no internet", valign="bottom")
    around("zone-safety", xs[3], top, 0, 3, "<b>SAFETY</b> · security office")
    p.cell(lz, "<b>Back of house</b>", zone_style("#FFFFFF", "#E2E8F0", "#334155", "bottom", 10), xs[4] - 38,
           top - 8, CARD_W + 44, ROW + CARD_H + 30)
    for c, names in enumerate(cols):
        column(ll, ll_box, xs[c], top, names)
    # The elevator monitor: on its own cellular to the elevator company, so no line (F24, a boundary).
    device(p, ld, "H01-ELEV-01", xs[1], top + 3 * ROW, CARD_W, CARD_H, small=True, pill=False, serial=False,
           label="<b>%name%</b><br>" + sub("%device_type%") + "<br>" + sub("own cellular · no link (F24)", 8, "#B45309"))

    # Floor 1: ACC-F1 in IDF-1 with payments, the front desk and the public-area APs.
    F1X, F1W = 1180, 460
    f1 = stack(p, lz, "H01-ACC-F1", F1X, SY, F1W, ["H01-ACC-F1-1", "H01-ACC-F1-2", "H01-ACC-F1-3"], "zone-mgmt",
               "CX 6200F 48G PoE ×3 · IDF-1 CAB-1")
    f1_box = (F1X, SY, F1W, 116)
    f1_top = SY + 116 + 56
    fx = [F1X + 46, F1X + 46 + PITCH]
    around("zone-payments", fx[0], f1_top, 0, 1, "<b>PAYMENTS</b>")
    around("zone-roomtech", fx[1], f1_top, 0, 0, "<b>ROOMTECH</b>")
    around("zone-ops", fx[1], f1_top, 2, 2, "<b>OPS</b>")
    column(f1, f1_box, fx[0], f1_top, ["H01-PT-FD-01", "H01-POS-RST-01", None, "H01-AP-F1-01"])
    column(f1, f1_box, fx[1], f1_top, ["H01-ENC-01", None, "H01-PRN-FD-01"])
    # The guest floors: one wall cabinet each, a lock gateway and the in-room APs.
    GX, GW_, GSTEP = 1680, 226, 234
    targets = [(ll, ll_box, cable_to("H01-ACC-LL-1"), "1/1/11 · 2/1/11", "1/1/49 · 2/1/49"),
               (f1, f1_box, cable_to("H01-ACC-F1-1"), "1/1/12 · 2/1/12", "1/1/49 · 3/1/49")]
    for k, floor in enumerate(range(2, 7)):
        x = GX + k * GSTEP
        sw = stack(p, lz, f"H01-ACC-F{floor}", x, SY, GW_, [f"H01-ACC-F{floor}-1", f"H01-ACC-F{floor}-2"],
                   "zone-mgmt", f"×2 · IDF-{floor} CAB-{floor}")
        box = (x, SY, GW_, 90)
        targets.append((sw, box, cable_to(f"H01-ACC-F{floor}-1"), f"1/1/{11 + floor} · 2/1/{11 + floor}",
                        "1/1/49 · 2/1/49"))
        gtop = SY + 90 + 56
        around("zone-roomtech", x + 46, gtop, 1, 1, "<b>ROOMTECH</b>")
        column(sw, box, x + 46, gtop, [f"H01-AP-F{floor}-01", f"H01-LOCKGW-F{floor}"])
    fan(p, core, core_box, targets, CY + 90 + 16, step=10)
    note(p, 1680, 1056, 1150, 96, "<b>End devices</b> · one card per kind of device on each stack; the build counts "
         "the rest on it (×N). APs trunk VLANs 11, 61, 100 (native 99); floor 1 APs add 22 (AB-PAY) and 110–118 "
         "(events). Terminals "
         "on 20, POS on 21, encoders and lock gateways on 63, plant on 70 and 72, cameras on 80. Room TVs, phones "
         "and the thermostats' mesh are not network devices here: the switch port or the gateway carries the zone.",
         guide=False)

    # Registers and legend, below.
    RY = 1240
    lr = p.layer("6 · Link register")
    link_card = p.cell(lr, "", CARD, 24, RY, 1250, 400)
    p.cell(lr, "<b>Link register</b> — port-channels, members, speed, trunked VLANs", HEADING, 38, RY + 10, 1200, 22)
    rows = []
    names = {"H01-POS-SRV-01": "POS", "H01-PBX-01": "PBX", "H01-GRMS-01": "GRMS", "H01-IPTV-01": "IPTV",
             "H01-UPS-01": "UPS1", "H01-UPS-02": "UPS2", "H01-OOB-01": "OOB"}
    for i, c in enumerate(S.CABLES[:S.INFRA_CABLES]):
        a_dev = sorted({e.split(":")[0].replace("H01-", "") for e in c["a"]})
        b_dev = sorted({e.split(":")[0].replace("H01-", "") for e in c["b"]})
        a_ports = " · ".join(e.split(":")[1] for e in c["a"])
        b_ports = " · ".join(e.split(":")[1] for e in c["b"])
        name = c["lag"] or names.get(c["b"][0].split(":")[0], "")
        speed = c["speed"] + (" LACP" if c["lag"].startswith("Po") else "")
        ids = ", ".join(f"#{S.CABLES.index(c) * 2 + k + 1}" for k in range(len(c["labels"])))
        b0 = c["b"][0].split(":")[0]
        vlans = c["vlans"] or ("heartbeat" if c["lag"] == "HA" else "routed" if c["lag"] else
                               f"access {S.access_vlan(b0, DEV[b0]['role'])}")
        rows.append([name, ids, f"{'/'.join(a_dev)} {a_ports}", f"{'/'.join(b_dev)} {b_ports}", speed, c["media"],
                     "connected", vlans])
    table(p, lr, 38, RY + 38, [("LINK", 56), ("CABLE ID", 66), ("A-SIDE (MEMBERS)", 200), ("B-SIDE (MEMBERS)", 200),
          ("SPEED", 90), ("MEDIA", 70), ("STATUS", 76), ("TRUNKED VLANS", 462)], rows, row_h=22)
    note(p, 38, RY + 38 + p.table_height + 8, 1220, 32, "All trunks: native VLAN 999 (unused) · explicit allowed list "
         "· LACP fast. End-device drops are in NetBox and the AP register, not in this register.")
    resize(p, link_card, 38 + p.table_height + 8 + 32 + 14)
    la = p.layer("7 · Asset register")
    skip = ("access-point", "printer", "camera", "payment-terminal", "pos-terminal")
    reg = [d["name"] for d in S.DEVICES if d["role"] not in skip]
    asset_card = p.cell(la, "", CARD, 1300, RY, 1100, 400)
    p.cell(la, "<b>Asset register</b> — mirrors each device's NetBox record", HEADING, 1314, RY + 10, 1060, 22)
    rows = []
    for name in reg:
        d = DEV[name]
        role = {"ups": "UPS", "nvr": "NVR"}.get(d["role"], d["role"].replace("-", " ").capitalize())
        rows.append([name, role, d["device_type"], d["serial"], d["primary_ip4"].split("/")[0], d["location"],
                     d["rack"], f"U{d['position']}" if d["position"] else "", d["cf_sw_version"]])
    table(p, la, 1314, RY + 36, [("HOSTNAME", 138), ("ROLE", 130), ("MODEL", 186), ("SERIAL", 104), ("MGMT IP", 92),
          ("ROOM", 104), ("RACK/CAB", 62), ("U", 36), ("SW", 120)], rows, row_h=20)
    asset_h = 36 + p.table_height + 16
    resize(p, asset_card, asset_h)
    legend(p, 2440, RY, flows=False)
    height = RY + max(asset_h, 600) + 130
    p.height = height
    p.model.set("pageHeight", str(height))
    title_block(p, p.layer("Border & title block"), SITE, "Physical — devices, links", f"3 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 3d wireless
def wireless() -> Page:
    aps = [d["name"] for d in S.DEVICES if d["role"] == "access-point"]
    height = 470 + 22 * (len(aps) + 1) + 180
    p = Page("wireless", "3d · Wireless — APs and SSIDs", 2400, height, prefix="h")
    lb, ld = p.layer("Floors"), p.layer("1 · Devices")
    p.layer(MGMT_IPS)
    p.layer("3b · Serial numbers")
    p.title(lb, f"{SITE} · {S.SITE['name']} — Wireless",
            esc("Access points per floor · SSIDs and the zone each one lands in. Wall-plate APs in every other "
                "guest room; ceiling APs in the public areas and the back of house."))
    cloud = icon_card(p, lb, 500, 96, 600, 70, "cloud", "Cloud Wi-Fi management",
                      "Configuration, firmware and the guest portal from the vendor's cloud · APs reach it over HTTPS",
                      attrs={"netdiagrams_wireless_mgmt": "1"})
    floors = [("LL", "Lower level", "ceiling APs on H01-ACC-LL: kitchen, laundry, engineering, security"),
              ("F1", "Floor 1", "ceiling APs on H01-ACC-F1: lobby, grill, bar, spa, ballroom, meeting rooms")] + [
        (f"F{f}", f"Floor {f}", f"in-room wall plates on H01-ACC-F{f}, one every other room") for f in range(2, 7)]
    for n, (key, title, what) in enumerate(floors):
        fx, fy = 24 + (n % 4) * 384, 210 + (n // 4) * 124
        p.cell(lb, f"<b>{title}</b> · {esc(what)}", zone_style("#FFFFFF", "#E2E8F0", "#334155", "top", 10), fx, fy,
               374, 112)
        device(p, ld, f"H01-AP-{key}-01", fx + 14, fy + 42, 346, 56, small=True, pill=False,
               label="<b>%name%</b><br>" + sub("%device_type% · one card per floor; the build counts them"))
    p.cell(lb, sub("Each AP's switch port, cable and address are in the AP register below, rebuilt from NetBox on "
                   "every run. Floor 1 APs also carry VLAN 22 for AB-PAY and 110–118 for events.", 10), SMALL,
           24 + 3 * 384 + 14, 334 + 30,
           346, 60)
    la = p.layer("AP register")
    p.cell(la, "", CARD, 24, 470, 1520, 60 + 22 * (len(aps) + 1))
    p.cell(la, "<b>AP register</b> — every access point, its switch port and cable", HEADING, 40, 480, 1480, 22)
    rows = []
    for name in aps:
        d = DEV[name]
        c = CABLE_OF[name][0]
        sw, port = c["a"][0].split(":")
        rows.append([name, d["device_type"], d["serial"], d["primary_ip4"].split("/")[0], d["location"],
                     f"{sw.replace('H01-', '')} {port}", c["labels"][0]])
    table(p, la, 40, 506, [("NAME", 200), ("MODEL", 140), ("SERIAL", 160), ("MGMT IP", 150), ("LOCATION", 150),
          ("SWITCH PORT", 380), ("CABLE", 300)], rows, row_h=22)
    p.edge(p.layer("2 · Management"), cloud, None, "endArrow=none;html=1;strokeColor=#94A3B8;strokeWidth=1.2;"
           "dashed=1;fontSize=9;fontColor=#475569;labelBackgroundColor=#FFFFFF;" + FONT, "AP management",
           exit=(0.5, 1), tgt_pt=(800, 210))
    lt = p.layer("SSID table")
    ssid_card = p.cell(lt, "", CARD, 1580, 210, 796, 420)
    p.cell(lt, "<b>SSIDs</b> — one per zone, never one for everything", HEADING, 1596, 220, 760, 22)
    rows = [[ssid, str(vlan), S.ZONE[zone][1], sec, notes] for ssid, sec, vlan, zone, notes in S.SSIDS]
    table(p, lt, 1596, 250, [("SSID", 130), ("VLAN", 112), ("ZONE", 84), ("SECURITY", 180), ("NOTES", 258)], rows,
          row_h=30)
    p_table = p.table_height
    note(p, 1596, 250 + p_table + 14, 760, 120,
         "<b>Rules</b><br>· ALDERBAY-GUEST: client isolation, portal checks room and last name against the PMS, "
         "bandwidth by room tier; lands in GUEST only.<br>· ALDERBAY-EVENTS: a key per event, a VLAN per booking.<br>"
         "· AB-ROOMTECH: hidden, a key per device type, rotated when a vendor engineer leaves.<br>"
         "· No SSID for cameras, terminals or building systems: they are wired. Management VLAN 99 is never "
         "broadcast.")
    resize(p, ssid_card, 40 + p_table + 14 + 120 + 16)
    legend(p, 1580, 210 + 40 + p_table + 14 + 120 + 16 + 20, flows=False)
    title_block(p, p.layer("Border & title block"), SITE, "Wireless — APs, SSIDs", f"3d of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 4 flows
VERDICT = {"Allow": ("#16A34A", "endArrow=block;endFill=1;", "Permitted"),
           "Conditional": ("#EA580C", "dashed=1;endArrow=block;endFill=1;", "Conditional"),
           "Deny": ("#DC2626", "dashed=1;endArrow=none;", "Denied"),
           "Not on the hotel network": ("#B45309", "dashed=1;dashPattern=3 3;endArrow=block;endFill=1;", "Boundary")}


def flows() -> Page:
    p = Page("flows", "4 · Traffic Flows — who talks to whom", 2400, 60 + 96 + 46 * len(S.FLOWS) + 150, prefix="h")
    lb, lf = p.layer("Lanes"), p.layer("Flows")
    p.title(lb, f"{SITE} · {S.SITE['name']} — Traffic flows",
            esc("Each lane is one conversation: who starts it, who answers, and what the firewall does. Solid green "
                "is permitted, orange dashed is conditional, red ✕ is denied, brown dotted is off the hotel network. "
                "Everything else is denied by default."))
    xa, xb, top = 120, 980, 110
    p.cell(lb, "<b>INITIATOR</b>", SMALL, xa, top - 6, 320, 20)
    p.cell(lb, "<b>RESPONDER</b>", SMALL, xb, top - 6, 320, 20)
    p.cell(lb, "<b>WHAT · CONDITIONS</b>", SMALL, 1340, top - 6, 900, 20)
    for n, (fid, src, dst, what, verdict, cond, owner) in enumerate(S.FLOWS):
        y = top + 20 + n * 46
        color, extra, word = VERDICT[verdict]
        p.cell(lb, "", BAND.replace("fillColor=#FFFFFF", "fillColor=#FFFFFF" if n % 2 else "fillColor=#FBFCFE"),
               24, y, 2350, 40)
        p.cell(lb, f"<b>{fid}</b>", "rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#E9ECEF;"
               "strokeColor=none;fontColor=#475569;fontSize=10;html=1;" + FONT, 36, y + 9, 60, 22)
        box = ("rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#FFFFFF;strokeColor=#CBD5E1;fontSize=10;"
               "fontColor=#0F172A;fontStyle=1;html=1;whiteSpace=wrap;" + FONT)
        a = p.cell(lf, esc(src), box, xa, y + 6, 320, 28)
        b = p.cell(lf, esc(dst), box, xb, y + 6, 320, 28)
        p.edge(lf, a, b, f"html=1;strokeColor={color};strokeWidth=1.8;{extra}fontSize=9;fontColor={color};"
               "labelBackgroundColor=#FFFFFF;fontStyle=1;" + FONT, word, exit=(1, 0.5), entry=(0, 0.5))
        if verdict == "Deny":
            p.cell(lf, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
                   "fontSize=10;fontStyle=1;" + FONT, 760, y + 10, 20, 20)
        p.cell(lf, f"<b>{esc(what)}</b>" + (f" · {sub(esc(cond), 10)}" if cond else "")
               + f" · {sub('owner: ' + esc(owner), 10, '#94A3B8')}",
               TEXT.replace("verticalAlign=top", "verticalAlign=middle"), 1340, y + 4, 1020, 32)
    y = top + 20 + len(S.FLOWS) * 46
    p.cell(lb, "", BAND.replace("fillColor=#FFFFFF", "fillColor=#FEF2F2"), 24, y, 2350, 40)
    p.cell(lb, "<b>—</b>", "rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#FEE2E2;"
           "strokeColor=none;fontColor=#991B1B;fontSize=10;html=1;" + FONT, 36, y + 9, 60, 22)
    p.cell(lf, "<b>Default deny</b> · anything not listed above, between any two zones, is blocked and logged",
           TEXT.replace("verticalAlign=top", "verticalAlign=middle").replace("#334155", "#991B1B"), xa, y + 6, 1220, 28)
    title_block(p, p.layer("Border & title block"), SITE, "Traffic flows", f"4 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 5 failover
def failover() -> Page:
    scenarios = [
        ("isp", "ISP-A goes down", "Fiber cut or provider outage on H01-ISP-A-01.",
         "The firewall pair moves everything to ISP-B (cable 1G/50M) within about 30 seconds; Kestrel's tunnel and "
         "the SIP trunk rebuild over ISP-B. Guest traffic was on ISP-B already.",
         "Calls in progress drop and redial. Uploads are slow until ISP-A is back. Guests notice nothing."),
        ("router", "The brand circuit goes down", "H01-BRAND-01 or the brand's router fails; the brand fixes it.",
         "Brand systems (reservations, loyalty) are reached over the internet lines instead, as the brand allows.",
         "Front office works on; the brand's own help desk owns the ticket, not the hotel."),
        ("firewall", "H01-FW-01 fails", "Power supply, disk or a bad update on the active firewall.",
         "H01-FW-02 takes over every gateway address (.1 on every inside VLAN), both internet lines, the brand port "
         "and the guest gateway's outside leg; sessions carry on.",
         "A few seconds of pause. Card authorizations in flight retry. VPN users reconnect."),
        ("core-switch", "A core stack member fails", "H01-CORE-1 or H01-CORE-2 dies or is rebooted.",
         "Every port-channel (Po1–Po3, Po11–Po17, Po21, Po22) keeps its link on the other member at half speed.",
         "Whatever is on that member's single drops (POS server and room controls on CORE-1, the call server and "
         "TV head-end on CORE-2) stops until it is back."),
        ("cloud", "The cloud PMS is unreachable", "The brand's PMS is down, or both internet lines are.",
         "The interface server queues postings; the lock server and encoders keep making keys on site; terminals "
         "keep taking cards if the processor is reachable.",
         "Check-ins go on paper from the night audit's last report; folios catch up when the PMS is back."),
        ("power", "Power cut", "The utility drops; the generator takes about 10 seconds to pick up the MDF.",
         "Both UPSs carry the MDF (about 25 and 30 minutes) until the generator is on; the IDFs ride on the "
         "generator circuit. The console server reaches the firewall over cellular if both lines are down.",
         "Wi-Fi, room phones and TVs blink. If the generator fails, shut down cleanly before the UPSs run out."),
        ("call-server", "Emergency call with ISP-A down", "A guest dials emergency services from a room phone "
         "while ISP-A is out.",
         "The SIP trunk has to rebuild over ISP-B; no phone line here works without the internet. Whether the call "
         "gets out, and with which room as its location, is the phone provider's answer. Untested.",
         "A room phone may get no outside line, emergency calls included. Book the provider's emergency-call test "
         "with ISP-A pulled, and write who at the front desk is alerted."),
    ]
    p = Page("failover", "5 · Failover scenarios", 2400, 100 + 136 * len(scenarios) + 110, prefix="h")
    lb = p.layer("Scenarios")
    p.title(lb, f"{SITE} · {S.SITE['name']} — Failover",
            esc("What happens at 3 a.m. when one thing breaks: what fails, what takes over, and what the front desk "
                "notices."))
    for n, (icon, title, what, takes, notice) in enumerate(scenarios):
        y = 100 + n * 136
        p.cell(lb, "", CARD, 24, y, 2350, 124)
        icon_card(p, lb, 40, y + 14, 460, 96, icon, title, what, 34, 14)
        for k, (head, text, color) in enumerate([("WHAT TAKES OVER", takes, "#15803D"),
                                                 ("WHAT PEOPLE NOTICE", notice, "#B45309")]):
            x = 540 + k * 900
            p.cell(lb, f"<b>{head}</b>", SMALL.replace("#64748B", color), x, y + 18, 860, 20)
            p.cell(lb, esc(text), TEXT.replace("fontSize=10", "fontSize=12"), x, y + 42, 860, 70)
    title_block(p, p.layer("Border & title block"), SITE, "Failover scenarios", f"5 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 6 portfolio
def multisite() -> Page:
    p = Page("multisite", "6 · Portfolio — brand, management company, sister property", 2400, 1130, prefix="h")
    lb, lc, ll = p.layer("Sites"), p.layer("Cards"), p.layer("Tunnels")
    p.title(lb, "Alder Bay — Owner, operator, brand and the sister property",
            esc(f"{S.OWNER} owns both hotels; {S.OPERATOR} runs them and their IT; {S.BRAND_CO} flags them and "
                "puts its own router and circuit in each MDF. Each property has its own internet lines; Kestrel's "
                "tunnels end on each property's firewall."))
    inet = icon_card(p, lc, 860, 100, 520, 80, "globe", "Internet", "Each property's own lines · cloud PMS, "
                     "processor and vendor clouds reached directly", 30, 13)
    hq = p.cell(lc, "<b>H01 · Alder Bay Hotel and Conference Center</b> · 10.40.0.0/16 · 160 rooms, full service<br>"
                + sub("Firewall HA pair · core stack · 7 closets · 94 APs · POS, PMS interfaces, plant room"),
                zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), 760, 420, 720, 180)
    for n, (icon, title, text) in enumerate([("firewall", "H01-FW HA pair", "Ends Kestrel's tunnel"),
                                             ("router", "Brand router", "The brand's, in rack R01"),
                                             ("guest-gateway", "Guest gateway", "The Wi-Fi vendor's")]):
        icon_card(p, lc, 780 + n * 232, 476, 218, 80, icon, title, text, 24, 11)
    br = p.cell(lc, "<b>H02 · Alder Bay Airport</b> · 10.41.0.0/16 · 120 rooms, select service<br>"
                + sub("One firewall · one switch · market pantry POS · its own brand router and guest gateway"),
                zone_style("#F4FAF5", "#B4DDBF", "#16A34A", "top", 12), 100, 690, 560, 170)
    for n, (icon, title, text) in enumerate([("firewall", "H02-FW-01", "Broadband 500/50 + brand 100M"),
                                             ("pos-terminal", "Market pantry", "One POS, one terminal")]):
        icon_card(p, lc, 120 + n * 264, 756, 250, 80, icon, title, text, 24, 11)
    ke = p.cell(lc, f"<b>{S.OPERATOR}</b> · management company<br>"
                + sub("IT shared services: NOC, SIEM, VPN, the PMS and POS contracts; reaches both hotels"),
                zone_style("#F5F5FF", "#C7C9F9", "#4F46E5", "top", 12), 1580, 690, 560, 170)
    for n, (icon, title, text) in enumerate([("shield", "Kestrel VPN", "IPsec · MFA for people"),
                                             ("cloud", "Kestrel SIEM", "Syslog over TLS · 365 days")]):
        icon_card(p, lc, 1600 + n * 264, 756, 250, 80, icon, title, text, 24, 11)
    brand = icon_card(p, lc, 1580, 240, 560, 80, "brand", f"{S.BRAND_CO} (brand)",
                      "Brand standards · cloud PMS and reservations · loyalty · the brand circuit", 30, 13)
    owner = icon_card(p, lc, 100, 240, 560, 80, "building", S.OWNER, "Owns both properties; the asset manager "
                      "asks for the drawing at every refinancing", 30, 13)
    vend = icon_card(p, lc, 100, 420, 560, 80, "wrench", "Vendors and the BMS contractor",
                     "VPN · MFA · booked window · logged", 30, 13)
    tunnel = ("html=1;strokeColor=#2563EB;strokeWidth=2;dashed=1;dashPattern=8 4;endArrow=none;fontSize=10;"
              "fontColor=#1E3A8A;labelBackgroundColor=#FFFFFF;" + FONT)
    plain_line = "html=1;strokeColor=#94A3B8;strokeWidth=1.4;endArrow=none;fontSize=10;fontColor=#475569;" \
                 "labelBackgroundColor=#FFFFFF;" + FONT
    p.edge(ll, ke, hq, tunnel.replace("#2563EB", "#4F46E5"), "IPsec · F18 · F22", exit=(0, 0.3), entry=(0.9, 1),
           points=[(1408, 741)])
    p.edge(ll, ke, br, tunnel.replace("#2563EB", "#4F46E5"), "IPsec to H02", exit=(0.5, 1), entry=(0.5, 1),
           points=[(1860, 900), (380, 900)])
    p.edge(ll, vend, hq, tunnel.replace("#2563EB", "#EA580C"), "VPN + MFA · F14", exit=(1, 0.5), entry=(0, 0.2222))
    p.edge(ll, brand, hq, tunnel.replace("#2563EB", "#6366F1"), "Brand circuit · F07", exit=(0, 0.5), entry=(1, 0.2),
           points=[(1520, 280), (1520, 456)])
    p.edge(ll, inet, hq, plain_line, "ISP-A + ISP-B", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(ll, owner, hq, plain_line, "Owns", exit=(1, 0.5), entry=(0.3, 0), points=[(976, 280)])
    lt = p.layer("Site table")
    p.cell(lt, "<b>Properties and partners</b>", HEADING, 100, 930, 2040, 22)
    table(p, lt, 100, 956, [("CODE", 90), ("SITE", 300), ("PREFIX", 160), ("INTERNET", 420), ("BRAND", 330),
          ("LINK TO KESTREL", 740)], [
        [(SITE, f"{NETBOX}/dcim/sites/?slug=h01"), S.SITE["name"], "10.40.0.0/16",
         "ISP-A DIA 1G fiber · ISP-B cable 1G/50M", "Larkline router + 200M circuit", "IPsec to the H01 firewall pair"],
        [("H02", f"{NETBOX}/dcim/sites/?slug=h02"), S.BRANCH["name"], "10.41.0.0/16", "Provider C broadband 500/50",
         "Larkline router + 100M circuit", "IPsec to H02-FW-01"],
        ["KESTREL", f"{S.OPERATOR} shared services", "10.200.0.0/16", "Its own data center", "—",
         "Ends both tunnels"]], row_h=26)
    title_block(p, p.layer("Border & title block"), "All", "Portfolio", f"6 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 7 flow register
ZONE_ORDER = ["zone-internet", "zone-brand", "zone-payments", "zone-ops", "zone-servers", "zone-voice", "zone-guest",
              "zone-events", "zone-roomtech", "zone-building", "zone-safety", "zone-mgmt"]
MATRIX = {  # (from, to): (verdict, flows)
    ("zone-payments", "zone-internet"): ("allow", "F01 F03"), ("zone-payments", "zone-servers"): ("cond", "F04"),
    ("zone-servers", "zone-internet"): ("allow", "F05 F13"), ("zone-servers", "zone-roomtech"): ("cond", "F06 F25 F26"),
    ("zone-servers", "zone-voice"): ("cond", "F06"), ("zone-servers", "zone-guest"): ("cond", "F06"),
    ("zone-ops", "zone-internet"): ("allow", "F07"), ("zone-ops", "zone-brand"): ("allow", "F07"),
    ("zone-guest", "zone-internet"): ("allow", "F08"), ("zone-guest", "zone-roomtech"): ("cond", "F10"),
    ("zone-events", "zone-internet"): ("allow", "F11"), ("zone-roomtech", "zone-internet"): ("cond", "F12"),
    ("zone-internet", "zone-building"): ("cond", "F14"), ("zone-building", "zone-internet"): ("deny", "F15"),
    ("zone-safety", "zone-internet"): ("cond", "F17"), ("zone-brand", "zone-mgmt"): ("cond", "F18"),
    ("zone-brand", "zone-servers"): ("cond", "F18"), ("zone-mgmt", "zone-internet"): ("cond", "F21"),
    ("zone-mgmt", "zone-brand"): ("cond", "F22"), ("zone-voice", "zone-internet"): ("allow", "F23"),
    ("zone-ops", "zone-servers"): ("cond", "F28"), ("zone-ops", "zone-building"): ("cond", "F29"),
    ("zone-ops", "zone-safety"): ("cond", "F29"),
}
for _z in ("zone-ops", "zone-servers", "zone-voice", "zone-guest", "zone-events", "zone-roomtech", "zone-building",
           "zone-safety"):
    MATRIX[(_z, "zone-payments")] = ("deny", "F09 F19" if _z in ("zone-guest", "zone-events") else "F19")
for _z in ("zone-ops", "zone-guest", "zone-events", "zone-roomtech", "zone-building", "zone-safety"):
    MATRIX[(_z, "zone-mgmt")] = ("deny", "F09 F27" if _z in ("zone-guest", "zone-events") else "F27")
for _z in ("zone-guest", "zone-events"):
    for _t in ("zone-ops", "zone-servers", "zone-voice", "zone-building", "zone-safety"):
        MATRIX.setdefault((_z, _t), ("deny", "F09"))
MATRIX.setdefault(("zone-events", "zone-roomtech"), ("deny", "F09"))
for _t in ("zone-ops", "zone-servers", "zone-voice", "zone-roomtech", "zone-safety", "zone-mgmt"):
    MATRIX.setdefault(("zone-building", _t), ("deny", "F15"))


def register() -> Page:
    n = len(ZONE_ORDER)
    p = Page("register", "7 · Flow register & standards", 2400, 760 + 26 * len(S.FLOWS) + 30 * n, prefix="h")
    lf, lm, ls = p.layer("Flow register"), p.layer("Zone matrix"), p.layer("Standards")
    p.title(lf, f"{SITE} · {S.SITE['name']} — Flow register and standards",
            esc("The segmentation in writing: every permitted conversation, its conditions and owner, then default "
                "deny. The zone matrix is the same rules as a grid. Naming and drawing standards at the right."))
    look = {"Allow": "#15803D", "Conditional": "#B45309", "Deny": "#B91C1C", "Not on the hotel network": "#92400E"}
    rows = [[fid, src, dst, what, f'<font color="{look[v]}"><b>{v}</b></font>', cond, owner]
            for fid, src, dst, what, v, cond, owner in S.FLOWS]
    rows.append(["—", "Any", "Any", "Everything not listed above", '<font color="#B91C1C"><b>Deny</b></font>',
                 "Default deny, logged", "IT"])
    card = p.cell(lf, "", CARD, 24, 92, 1500, 400)
    p.cell(lf, "<b>Flow register</b>", HEADING, 40, 102, 1460, 22)
    table(p, lf, 40, 128, [("ID", 44), ("FROM", 210), ("TO", 210), ("WHAT", 320), ("VERDICT", 100),
          ("CONDITIONS", 320), ("OWNER", 260)], rows, row_h=26)
    resize(p, card, 36 + p.table_height + 16)
    my = 128 + p.table_height + 40
    p.cell(lm, "", CARD, 24, my, 1500, 60 + 30 * (n + 1))
    p.cell(lm, "<b>Zone matrix</b> — rows start the conversation, columns answer; blank is default deny", HEADING,
           40, my + 10, 1460, 22)
    cols = [("FROM \\ TO", 128)] + [(S.ZONE[z][1], 111) for z in ZONE_ORDER]
    cell = {"allow": '<font color="#15803D"><b>allow</b></font>', "cond": '<font color="#B45309"><b>cond.</b></font>',
            "deny": '<font color="#B91C1C"><b>deny</b></font>'}
    rows = []
    for a in ZONE_ORDER:
        row = [S.ZONE[a][1]]
        for b in ZONE_ORDER:
            if a == b:
                row.append('<font color="#94A3B8">inside</font>')
            elif (a, b) in MATRIX:
                v, f = MATRIX[(a, b)]
                row.append(f"{cell[v]} {f}")
            else:
                row.append("")
        rows.append(row)
    table(p, lm, 40, my + 40, cols, rows, row_h=30, key=KEY_CELL)
    p.height = int(my + 40 + p.table_height + 130)
    p.model.set("pageHeight", str(p.height))
    sx = 1560
    p.cell(ls, "", CARD, sx, 92, 816, 470)
    p.cell(ls, "<b>Naming and drawing standards</b>", HEADING, sx + 16, 102, 780, 22)
    table(p, ls, sx + 16, 128, [("ITEM", 170), ("STANDARD", 610)], [
          ["Site code", "H + two digits: H01 Alder Bay, H02 Alder Bay Airport"],
          ["Device", "SITE-ROLE-NN: H01-FW-01, H01-PT-FD-02, H01-AP-F3-07 (floor, number)"],
          ["Stack", "SITE-ACC-FLOOR: H01-ACC-F2; members -1, -2, -3"],
          ["Closet", "MDF-LL, IDF-1 … IDF-6: one per floor, the same on every floor"],
          ["Cable label", "SITE-CBL-nnnnn on both ends: H01-CBL-00021"],
          ["Zone tag", "zone-&lt;name&gt; on every device, VLAN and prefix"],
          ["VLAN", "Tens per zone: 10s ops, 20s payments, 30 servers, 40 voice, 60s room tech, 70s building, "
                   "80s safety, 99 management, 100s guests and events"],
          ["Subnet", "10.&lt;site&gt;.&lt;vlan&gt;.0 inside; guests and events from 172.20"],
          ["Gateway", "Inside: .1 on the firewall pair. Guests and events: .1 on the guest gateway"],
          ["Third-party boxes", "The brand router and the guest gateway carry their owner as tenant"],
          ["Hide before sharing", "Layers 3 (mgmt IPs) and 4 (circuit IDs)"],
          ["Change", "Edit NetBox, then rebuild; never fix the drawing alone"]], row_h=30)
    title_block(p, p.layer("Border & title block"), SITE, "Flow register and standards", f"7 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ main
def build() -> ET.Element:
    return mxfile((overview(), logical(), physical(), wireless(), flows(), failover(), multisite(), register()),
                  "netdiagrams hotel template")


def main() -> None:
    tree = build()
    ET.indent(tree, space=" ")
    OUT.write_text(ET.tostring(tree, encoding="unicode") + "\n", "utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
