"""Generate src/netdiagrams/data/D01-Dealership-Template.drawio, the dealership standard.

Eight sheets drawn for the fictional Kestrel Valley Motors (site D01): overview,
logical, physical, wireless, traffic flows, failover, rooftops and cloud, and the
flow register. Every fact comes from scripts/dealer_template/site.py, the same
source scripts/make_dealer_sample.py turns into the sample NetBox export, so
`netdiagrams build --input sample-dealership.json` reproduces the template.
The look and the kit are the office standard's (scripts/make_office_template.py).

    python scripts/make_dealer_template.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dealer_template import site as S  # noqa: E402
from drawkit import (  # noqa: E402
    BAND, EDGE, FONT, NETBOX, NOTE, POINTS, RACK_PILL, SUBTITLE, TITLE, Page, _svg, esc, mxfile, sub, zone_style)
from make_office_template import (  # noqa: E402  (the office kit: styles, tables, the common icons)
    BUNDLE, CARD, CID_TAG, GREY, HEADING, ICONS as OFFICE_ICONS, IP_TAG, KEY_CELL, MEDIA_LOOK, PORT_LABEL, SLATE,
    SMALL, SN_TAG, TEXT, _circle, _line, _rect, group_style, table)

ORANGE, OLIVE, PLUM, PINK = "#EA580C", "#A16207", "#6B5B95", "#DB2777"
ICONS = {
    **OFFICE_ICONS,
    "card-terminal": _svg("#FCEBE0", _rect(9.5, 5.5, 13, 21, ORANGE, rx=2.5) + _rect(12, 8.5, 8, 5, ORANGE, rx=1)
                          + _line("12.5,17 13.5,17", ORANGE) + _line("15.5,17 16.5,17", ORANGE)
                          + _line("18.5,17 19.5,17", ORANGE) + _line("12.5,20.5 13.5,20.5", ORANGE)
                          + _line("15.5,20.5 16.5,20.5", ORANGE) + _line("18.5,20.5 19.5,20.5", ORANGE)),
    "diag-tool": _svg("#F6F1D9", _rect(7, 8, 18, 12, OLIVE) + _line("9.5,14.5 12,14.5 13.5,11 15.5,18 17,14.5 22.5,14.5", OLIVE)
                      + _line("16,20 16,24", OLIVE) + _line("12,24.5 20,24.5", OLIVE)),
    "key-cabinet": _svg("#FBE4EF", _circle(12, 12.5, 4, PINK) + _line("14.8,15.3 24,24.5", PINK)
                        + _line("21,21.5 23,19.5", PINK) + _line("18.5,19 20.5,17", PINK)),
    "router": _svg("#ECEAF3", _rect(6, 13, 20, 9, PLUM, rx=3) + _line("10,17.5 10.5,17.5", PLUM, 2.2)
                   + _line("13.5,17.5 14,17.5", PLUM, 2.2) + _line("11,13 9,8", PLUM, 1.4) + _line("21,13 23,8", PLUM, 1.4)),
    "car": _svg("#E2E8F0", _line("6,20 6,16.5 9.5,15.5 12.5,11.5 19.5,11.5 22.5,15.5 26,16.5 26,20 6,20", SLATE)
                + _circle(11, 20.5, 2.2, SLATE, fill="#E2E8F0") + _circle(21, 20.5, 2.2, SLATE, fill="#E2E8F0")),
    "dms": _svg("#E7E9EC", _rect(8, 6.5, 16, 19, GREY, rx=2) + _line("11,11 21,11", GREY) + _line("11,15 21,15", GREY)
                + _line("11,19 17,19", GREY)),
}
ICON_FOR_ROLE = {"firewall": "firewall", "core-switch": "core-switch", "access-switch": "access-switch",
                 "access-point": "access-point", "storage": "storage", "ups": "ups", "console-server": "console-server",
                 "printer": "printer", "nvr": "nvr", "camera": "camera", "router": "router",
                 "card-terminal": "card-terminal", "diag-tool": "diag-tool", "key-cabinet": "key-cabinet"}


def label_style(icon: str, size: int = 22, left: int = 28, font: int = 10, valign: str = "top", arc: int = 12) -> str:
    return (f"shape=label;rounded=1;absoluteArcSize=1;arcSize={arc};fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;"
            f"shadow=1;align=left;verticalAlign={valign};spacingTop=5;spacingLeft={left};fontSize={font};fontColor=#0F172A;"
            f"whiteSpace=wrap;html=1;{POINTS}{FONT}image=data:image/svg+xml,{ICONS[icon]};imageWidth={size};"
            f"imageHeight={size};imageAlign=left;imageVerticalAlign=middle;")


DEVICE_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 30, 38, 11)
SMALL_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 22, 28, 10)
MEMBER_ROW = lambda role: label_style(ICON_FOR_ROLE.get(role, "access-switch"), 16, 22, 9)

LEGEND_ITEMS = [("firewall", "Firewall (HA pair)"), ("core-switch", "Core switch / stack"),
                ("access-switch", "Access switch / stack"), ("access-point", "Wireless AP (cloud managed)"),
                ("router", "Manufacturer's router"), ("storage", "Storage / NAS"), ("ups", "UPS"),
                ("console-server", "Out-of-band console"), ("card-terminal", "Card terminal"),
                ("diag-tool", "Diagnostic PC"), ("printer", "Printer"), ("nvr", "Video recorder"),
                ("camera", "Camera"), ("key-cabinet", "Key cabinet"), ("dms", "Hosted DMS"), ("cloud", "Cloud / SaaS")]


def legend(p: Page, x: float, y: float, zones: list[tuple[str, str, str, str]], flows: bool = True) -> float:
    """The dealership legend: icons, line meanings and the zone colors. Returns its height."""
    layer = p.layer("Legend")
    rows = -(-len(LEGEND_ITEMS) // 2)
    lines = [("#64748B", 1.6, "", "Link · pill = Po · speed · media · tag = port"),
             ("#64748B", 2.5, "", "Weight = speed (thicker = 10G and up)")]
    if flows:
        lines += [("#16A34A", 1.6, "endArrow=block;endFill=1;", "Permitted flow (initiator → responder)"),
                  ("#EA580C", 1.6, "dashed=1;endArrow=block;endFill=1;", "Conditional (MFA · window · one destination)"),
                  ("#DC2626", 1.6, "dashed=1;", "Denied path")]
    zone_rows = -(-len(zones) // 5)
    h = 40 + rows * 24 + 6 + len(lines) * 22 + 10 + zone_rows * 26 + 14
    p.cell(layer, "", CARD, x, y, 360, h)
    p.cell(layer, "Legend", HEADING, x + 16, y + 10, 200, 22)
    for n, (icon, text) in enumerate(LEGEND_ITEMS):
        col, row = n % 2, n // 2
        p.cell(layer, esc(text),
               f"shape=label;html=1;fillColor=none;strokeColor=none;align=left;verticalAlign=middle;spacingLeft=24;"
               f"fontSize=10;fontColor=#334155;{FONT}image=data:image/svg+xml,{ICONS[icon]};imageWidth=18;imageHeight=18;"
               "imageAlign=left;imageVerticalAlign=middle;", x + 14 + col * 172, y + 36 + row * 24, 166, 24)
    ly = y + 36 + rows * 24 + 6
    for color, width, extra, text in lines:
        p.edge(layer, None, None, f"endArrow=none;html=1;strokeColor={color};strokeWidth={width};{extra}",
               src_pt=(x + 18, ly + 10), tgt_pt=(x + 58, ly + 10))
        if "Denied" in text:
            p.cell(layer, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
                   "fontSize=10;fontStyle=1;" + FONT, x + 64, ly, 20, 20)
        p.cell(layer, esc(text), "text;html=1;fontSize=10;fontColor=#334155;align=left;"
               "verticalAlign=middle;" + FONT, x + 88, ly, 270, 20)
        ly += 22
    ly += 10
    for n, (label, fill, stroke, font) in enumerate(zones):
        col, row = n % 5, n // 5
        p.cell(layer, esc(label),
               f"rounded=1;absoluteArcSize=1;arcSize=12;fillColor={fill};strokeColor={stroke};fontColor={font};"
               "fontSize=9;fontStyle=1;html=1;whiteSpace=wrap;" + FONT, x + 14 + col * 68, ly + row * 26, 64, 22)
    return h


DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"
OUT = DATA / "D01-Dealership-Template.drawio"
DATE = "2026-10-18"
PROJECT = "Dealership network standard"
SHEETS = 8
CODE = S.SITE["code"]

DEV = {d["name"]: d for d in S.DEVICES}
CABLE_OF = {}
for _c in S.CABLES:
    for _end in _c["a"] + _c["b"]:
        CABLE_OF.setdefault(_end.split(":")[0], []).append(_c)
ATTR_ORDER = ["name", "role", "manufacturer", "device_type", "platform", "serial", "asset_tag", "status", "site",
              "location", "rack", "position", "face", "primary_ip4", "virtual_chassis", "vc_position", "description",
              "tags", "cf_sw_version", "cf_support_contract", "cf_lifecycle", "x_modules", "x_power"]
ZONE_LOOK = {z[0]: z[6] for z in S.ZONES}
ZONE_KEYS = [(z[1], *z[6]) for z in S.ZONES]


# ------------------------------------------------------------------ objects
def resize(p, cid: str, height: float) -> None:
    """Set a drawn box's height once what it holds is measured."""
    p.find(cid).find(".//mxGeometry").set("height", f"{height:g}")


def dev_attrs(name: str) -> dict:
    d = DEV[name]
    a = {k: str(d.get(k, "") or "") for k in ATTR_ORDER}
    a["site"] = CODE
    a["face"] = "front" if d.get("position") else ""
    if d.get("cf_ap_mode"):  # access points only: how NetBox says the AP is run
        a["cf_ap_mode"] = d["cf_ap_mode"]
    if d.get("cf_criticality"):  # the asset criticality NetBox rates it with
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
        p.cell(p.layer("3 · Mgmt IPs (hide before sharing)"), d["primary_ip4"].split("/")[0], IP_TAG,
               x + (30 if small else 40), y + h - 18, 110, 14)
    if serial and d.get("serial"):
        p.cell(p.layer("3b · Serial numbers"), f"SN {d['serial']}", SN_TAG, x + w - 122, y + h - 18, 110, 14)
    return cid


def stack(p: Page, layer: str, vc: str, x, y, w, members: list[str], zone: str, note: str) -> str:
    fill, stroke, font = ZONE_LOOK[zone]
    first = DEV[members[0]]
    h = 34 + 26 * len(members) + 4
    label = f"%name%<br>{sub(esc(note), 9, '#64748B')}"
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
        p.cell(p.layer("3 · Mgmt IPs (hide before sharing)"), first["primary_ip4"].split("/")[0], IP_TAG, x + w - 92,
               y + 3, 86, 14)
    return sid


def cable_by_label(label: str) -> dict:
    return next(c for c in S.CABLES if label in c["labels"])


def link(p: Page, src: str, dst: str, cable: dict, text=None, points=(), exit=None, entry=None,
         ports=None, bundle=None, weight=None, color="#64748B", pos=None) -> str:
    labels = ", ".join(cable["labels"])
    attrs = {"object": "dcim.cable", "cable_label": labels, "type": cable["type"], "status": "connected",
             "color": cable["color"], "length": "", "length_unit": "", "a_terminations": ", ".join(cable["a"]),
             "b_terminations": ", ".join(cable["b"]), "x_speed": cable["speed"], "x_media": cable["media"],
             "x_patch_a": "", "x_patch_b": ""}
    attrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in attrs.items()), **attrs,
             "link": f"{NETBOX}/dcim/cables/?" + "&".join(f"label={l}" for l in cable["labels"]),
             "linkTarget": "_blank"}
    bg, border = MEDIA_LOOK.get(cable["media"], ("#FFFFFF", "#E2E8F0"))
    width = weight or (2.5 if "10G" in cable["speed"] else 1.4)
    style = (EDGE.replace("strokeColor=#64748B", f"strokeColor={color}").replace("strokeWidth=1.6", f"strokeWidth={width}")
             + f"labelBackgroundColor={bg};labelBorderColor={border};")
    if text is None:
        text = " · ".join(x for x in (cable["lag"] if cable["lag"].startswith("Po") else "", cable["speed"],
                                       cable["media"]) if x)
    eid = p.edge(p.layer("2 · Links (Po · speed · VLANs)"), src, dst, style, esc(text), attrs, points=points,
                 exit=exit, entry=entry, pos=pos)
    if ports:
        a, b = ports[:2]
        if a:
            dx, dy = ports[2] if len(ports) > 2 else (0, 0)
            p.edge_label(eid, a, -1, dy, PORT_LABEL, dx)
        if b:
            dx, dy = ports[3] if len(ports) > 3 else (0, 0)
            p.edge_label(eid, b, 1, dy, PORT_LABEL, dx)
    if bundle:
        p.cell(p.layer("2 · Links (Po · speed · VLANs)"), "", BUNDLE, bundle[0] - 10, bundle[1] - 4.5, 20, 9)
    return eid


def zone_box(p: Page, layer: str, zone: str, x, y, w, h, title=None, valign="top") -> str:
    fill, stroke, font = ZONE_LOOK[zone]
    z = S.ZONE[zone]
    text = title if title is not None else f"<b>{esc(z[1])}</b> · {esc(z[2])}"
    return p.cell(layer, text, zone_style(fill, stroke, font, valign, 10), x, y, w, h)


def note(p: Page, x, y, w, h, text, guide=True) -> str:
    """Design prose: on the hidden guide layer, since NetBox can never fill it."""
    layer = p.layer("Guides (hidden)", visible=False) if guide else p.layer("Notes")
    return p.cell(layer, text, NOTE, x, y, w, h, {"netdiagrams_guide": "1"} if guide else None)


def icon_card(p: Page, layer: str, x, y, w, h, icon: str, title: str, text: str, size=28, title_size=12,
              attrs: dict | None = None) -> str:
    style = label_style(icon, size, size + 18, title_size, "middle", 16) + "spacingTop=0;"
    return p.cell(layer, f"<b>{esc(title)}</b><br>{sub(esc(text), 10)}", style, x, y, w, h, attrs=attrs)


def gate_bar(p: Page, layer: str, x, y, w, text: str) -> str:
    style = label_style("shield", 16, 30, 10, "middle", 22).replace("fillColor=#FFFFFF", "fillColor=#F1F5F9")
    return p.cell(layer, text, style.replace("shadow=1;", "shadow=0;") + "spacingTop=0;", x, y, w, 30)


# ------------------------------------------------------------------ 1 overview
def overview() -> Page:
    p = Page("overview", "1 · Overview — for management", 2000, 990, prefix="d")
    lay = p.layer("Overview")
    p.cell(lay, "How the dealership network is protected", TITLE, 24, 18, 1000, 32)
    p.cell(lay, "Management overview: no technical detail. Every rooftop in the group follows the same "
           "design.", SUBTITLE, 24, 52, 1000, 22)
    x, w = 170, 1010
    rows = [  # y, side label, color
        (100, "Outside", "#64748B"), (305, "Sales, F&amp;I &amp; office", "#4F46E5"),
        (521, "Service, shop &amp; parts", "#16A34A"), (737, "Guests, building &amp; management", "#DB2777")]
    for y, text, color in rows:
        p.cell(lay, f"<b>{text}</b>", "text;html=1;align=right;verticalAlign=middle;fontSize=10;"
               f"fontColor={color};whiteSpace=wrap;{FONT}", 40, y, 120, 60)
    outside = icon_card(p, lay, x, 92, w, 76, "cloud", "Internet, the DMS, lenders and the manufacturer",
                        "The hosted DMS · lender portals and credit bureaus · the manufacturer's systems · the CRM "
                        "and email · the managed service provider (MSP)")
    gate_bar(p, lay, x, 214, w, "<b>Security gate</b> · the firewall: everything between the internet and the "
             "dealership passes through it, and the DMS has its own encrypted tunnel")
    deals = p.cell(lay, "<b>Sales, F&amp;I and office</b> · where customers' financial information lives",
                   zone_style("#F5F5FE", "#C2C4F6", "#4F46E5", "top", 12), x, 270, w, 130)
    for n, (icon, title, text) in enumerate([
            ("lock", "F&I", "Credit applications, deal jackets"), ("users", "Sales floor", "Desks, tablets, the CRM"),
            ("dms", "Back office", "Accounting, titles, payroll"),
            ("card-terminal", "Card terminals", "Cashier, parts, F&I")]):
        icon_card(p, lay, x + 16 + n * 248, 306, 232, 76, icon, title, text, 24, 11)
    gate_bar(p, lay, x, 430, w, "<b>Same security gate</b> · between every department and the manufacturer's box")
    fixed = p.cell(lay, "<b>Service, shop and parts</b> · fixed operations and the manufacturer's link",
                   zone_style("#F4FAF5", "#B4DDBF", "#16A34A", "top", 12), x, 486, w, 130)
    cards = {}
    for n, (key, icon, title, text) in enumerate([
            ("service", "car", "Service drive", "Advisors, write-up tablets"),
            ("shop", "diag-tool", "Shop", "Diagnostic PCs, shop tablets"),
            ("parts", "storage", "Parts", "Counter and warehouse"),
            ("oem", "router", "Manufacturer's router", "Their box, one port")]):
        cards[key] = icon_card(p, lay, x + 16 + n * 248, 522, 232, 76, icon, title, text, 24, 11)
    gate_bar(p, lay, x, 646, w, "<b>Same security gate</b> · customers' Wi-Fi, the building systems and network "
             "management have their own doors, opened only for the people who need them")
    p.cell(lay, "<b>Guests, building and management</b> · the lounge, the lot and the closet",
           zone_style("#FDF4F9", "#F3B8D6", "#DB2777", "top", 12), x, 702, w, 150)
    icon_card(p, lay, x + 16, 738, 316, 92, "guest", "Customer Wi-Fi",
              "The lounge and showroom get the internet and nothing else")
    icon_card(p, lay, x + 346, 738, 316, 92, "camera", "Cameras and keys",
              "The lot cameras record on site; the key cabinet reports to its vendor only")
    mgmt = icon_card(p, lay, x + 676, 738, 318, 92, "wrench", "Network management",
                     "Firewalls, switches, Wi-Fi and power; the MSP only")
    arrows = p.layer("Arrows")
    # The MSP and vendors: in through the gate, with MFA.
    p.edge(arrows, outside, mgmt, "endArrow=block;endFill=1;html=1;strokeColor=#7C3AED;strokeWidth=1.6;dashed=1;"
           "fontSize=9;fontColor=#4C1D95;labelBackgroundColor=#FFFFFF;" + FONT, "", exit=(1, 0.7), entry=(1, 0.5),
           points=[(1206, 145.2), (1206, 784)])
    p.cell(arrows, "<b>The MSP and vendors</b>: in through the gate, with MFA, per ticket ↓",
           "text;html=1;align=right;verticalAlign=middle;fontSize=9;fontColor=#6D28D9;" + FONT, 860, 216, 310, 26)
    # The shop: no direct path to F&I.
    p.edge(arrows, cards["shop"], deals, "endArrow=none;html=1;strokeColor=#DC2626;strokeWidth=1.6;dashed=1;fontSize=9;"
           "fontColor=#991B1B;labelBackgroundColor=#FFFFFF;" + FONT, "No direct path<br>from the shop to F&amp;I",
           exit=(0.9, 0), entry=(0.4686, 1))  # x 643: clear of the gate text and the band title
    p.cell(arrows, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
           "fontSize=10;fontStyle=1;" + FONT, 633, 405, 20, 20)
    # What this means for the business: Kestrel Valley's promises, on their own layer so a build marks them EXAMPLE
    rx = 1240
    promises = p.layer("Business promises (Kestrel Valley's; rewrite for your dealership)")
    p.cell(promises, "", "rounded=1;arcSize=2;html=1;fillColor=none;strokeColor=none;", rx - 12, 120, 724, 736)
    p.cell(lay, "What this means for the business", HEADING.replace("fontSize=12", "fontSize=14"), rx, 92, 700, 24)
    cards = [
        ("lock", "Credit files stay in F&I and the DMS",
         "F&I desks are wired, on their own network, and reach only the DMS, the lenders and the credit bureaus."),
        ("shield", "Vendors get in through one logged door",
         "The MSP, the DMS vendor and the manufacturer's support use the VPN with MFA, per ticket, and every "
         "session is recorded."),
        ("card-terminal", "Card terminals talk to the processor and nothing else",
         "Card data is encrypted at the terminal, and nothing else in the store can reach the terminals."),
        ("router", "The manufacturer's box gets one port",
         "Their router answers our shop and service desks; nothing it starts reaches our network."),
        ("isp", "One internet line can fail and the DMS stays up",
         "Two providers on different technologies; the DMS tunnel rebuilds on the backup line on its own."),
        ("backup", "Deal jackets leave the building every night",
         "The scans on the NAS copy overnight to a cloud vault that can't be altered for 30 days, so a fire or "
         "ransomware is not the end."),
    ]
    for n, (icon, title, text) in enumerate(cards):
        icon_card(p, promises, rx, 128 + n * 122, 700, 106, icon, title, text, 26, 12)
    p.title_block(p.layer("Border & title block"), "All", "Overview — management", f"1 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 2 logical
def vlan_rows(zone: str) -> list[list]:
    return [[(str(vid), f"{NETBOX}/ipam/vlans/?vid={vid}&site={S.SITE['slug']}"), name, subnet, gw]
            for vid, name, z, subnet, gw in S.VLANS if z == zone]


VLAN_COLS = [("VLAN", 44), ("NAME", 130), ("SUBNET", 132), ("GATEWAY", 110)]


def logical() -> Page:
    p = Page("logical", "2 · Logical — Zones, VLANs, Subnets", 2400, 1260, prefix="d")
    lb, lz = p.layer("Bands"), p.layer("Zones")
    lt = p.layer("VLAN tables")
    p.title(lb, f"{CODE} · {S.SITE['name']} — Logical",
            esc("Zones · VLANs · subnets · gateways. Every VLAN lives in one zone and every gateway is on the firewall, "
            "so every packet between zones is inspected. One-line rule per zone."))
    W = 1880
    bands = {"OUT": (96, 170), "EDGE": (282, 270), "DEALS": (568, 184), "FIXED": (768, 184), "SHARED": (968, 184)}
    for code, label, _ in S.BANDS:
        y, h = bands[code]
        p.band(lb, y, h, code, label.split(" · ")[0], W)
    # OUTSIDE: providers, the DMS, lenders and the cloud, no VLANs.
    zone_box(p, lz, "zone-internet", 100, 108, 1790, 146)
    p.cell(lz, esc(S.ZONE["zone-internet"][5]), SMALL, 112, 132, 900, 18)
    for n, (icon, title, text) in enumerate([
            ("isp", "ISP-A", "DIA 1G · fiber · static 203.0.113.0/29"), ("isp", "ISP-B", "Cable 500/50 · DHCP"),
            ("dms", "DMS (hosted)", "Vendor's data center · IPsec from D01"),
            ("lock", "Lenders and bureaus", "Credit apps and pulls · HTTPS from F&I"),
            ("cloud", "SaaS", "CRM, email, phones, the manufacturer's portals"),
            ("wrench", "MSP and vendors", "VPN · MFA · per ticket"),
            ("building", "D02 Pre-Owned", "10.31.0.0/16 · IPsec to D01")]):
        icon_card(p, lz, 112 + n * 252, 160, 240, 80, icon, title, text, 24, 11)
    # EDGE: the firewall pair and its interfaces.
    zone_box(p, lz, "zone-edge", 100, 294, 1790, 246)
    p.cell(lz, esc(S.ZONE["zone-edge"][5]), SMALL, 112, 318, 900, 18)
    p.cell(lz, f"<b>{CODE}-FW</b> · HA pair (active / passive)",
           zone_style("#FFFFFF", "#94A3B8", "#334155", "top", 10), 112, 346, 300, 150)
    for n, name in enumerate((f"{CODE}-FW-01", f"{CODE}-FW-02")):
        device(p, p.layer("Devices"), name, 124, 376 + n * 60, 276, 52, ip=False, serial=False, pill=False)
    p.cell(lz, "<b>Firewall interfaces</b>", HEADING.replace("fontSize=12", "fontSize=10"), 440, 346, 300, 20)
    table(p, lt, 440, 370, [("INTERFACE", 150), ("ZONE", 120), ("VLAN", 120), ("IP / PREFIX", 200)], [
          ["wan1", "INTERNET", "—", "static (ISP-A)"], ["wan2", "INTERNET", "—", "DHCP (ISP-B)"],
          ["x1–x2 (Po1 / Po2)", "all inside zones", "10–99 tagged", ".1 on every VLAN"],
          ["ssl-vpn", "EDGE", "—", "the VPN pool"], ["ipsec-dms", "EDGE", "—", "to the DMS vendor"],
          ["ipsec-d02", "EDGE", "—", "to D02 Pre-Owned"]], row_h=22)  # no addresses: a build would ? them
    p.cell(lz, "<b>Remote access and tunnels</b>", HEADING.replace("fontSize=12", "fontSize=10"), 1060, 346, 300, 20)
    table(p, lt, 1060, 370, [("POOL", 110), ("NAME", 120), ("SUBNET", 116), ("WHO", 150)], [
          ["—", "VPN-POOL", "10.30.200.0/24", "The MSP and vendors, MFA"],
          ["—", "IPSEC-DMS", "vendor's ranges", "The hosted DMS"],
          ["—", "IPSEC-D02", "10.31.0.0/16", "Pre-owned store"]], row_h=22)
    # Inside zones with VLAN tables, four to a band.
    layout = {"DEALS": ["zone-fi", "zone-sales", "zone-office", "zone-cde"],
              "FIXED": ["zone-service", "zone-shop", "zone-parts", "zone-oem"],
              "SHARED": ["zone-guest", "zone-voice", "zone-building", "zone-mgmt"]}
    for code, zones in layout.items():
        y, h = bands[code]
        bw = (1790 - 10 * (len(zones) - 1)) / len(zones)
        for n, zone in enumerate(zones):
            zx = 100 + n * (bw + 10)
            z = S.ZONE[zone]
            zone_box(p, lz, zone, zx, y + 12, bw, h - 24, f"<b>ZONE {esc(z[1])}</b> · {esc(z[2])}")
            p.cell(lz, esc(z[5]), SMALL, zx + 12, y + 36, bw - 24, 20)
            table(p, lt, zx + 12, y + 62, VLAN_COLS, vlan_rows(zone), row_h=22)
            p.cell(lz, sub("Lives here: " + esc(z[4]), 9, "#64748B"), SMALL, zx + 12, y + h - 38, bw - 24, 20)
    legend(p, 2000, 96, ZONE_KEYS, flows=False)
    p.title_block(p.layer("Border & title block"), CODE, "Logical — zones, VLANs", f"2 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 3 physical
def physical(p: Page | None = None) -> Page:
    p = Page("physical", "3 · Physical — Devices, Uplinks, Trunks", 2880, 1540, prefix="d")
    lb = p.layer("Bands")
    lz = p.layer("Zones (groups · stacks)")
    p.layer("2 · Links (Po · speed · VLANs)")
    ld = p.layer("1 · Devices")
    for name in ("3 · Mgmt IPs (hide before sharing)", "3b · Serial numbers", "4 · Circuit IDs (hide before sharing)"):
        p.layer(name)
    p.title(lb, f"{CODE} · {S.SITE['name']} — Physical",
            esc("Devices · uplinks · port-channels · trunked VLANs · rack and U on every device. Hover a device or Edit "
            "Data (Ctrl+M) for its NetBox record."))
    W = 1920
    p.band(lb, 96, 130, "ISP", "PROVIDERS", W)
    p.band(lb, 242, 760, "MDF", "MDF · MAIN BUILDING", W)
    p.band(lb, 1018, 170, "IDF", "IDF-SHOP · SERVICE BUILDING", W)
    p.band(lb, 1204, 230, "ROOMS", "IN THE ROOMS AND BAYS", W)

    # Providers and circuits
    isp = {}
    for n, circ in enumerate(S.CIRCUITS):
        cx = 560 + n * 470
        isp[circ["cid"]] = p.cell(ld, f"<b>ISP-{'AB'[n]}</b><br>{sub(esc(circ['label']))}",
                                  label_style("isp", 26, 36, 11, "middle", 12) + "spacingTop=0;", cx, 118, 230, 60)
        p.cell(p.layer("4 · Circuit IDs (hide before sharing)"),
               f"CID {circ['cid']}<br>{esc(circ['provider'])} · {esc(circ['speed'])}", CID_TAG, cx + 236, 132, 170,
               32)

    # Firewall pair
    zone_box(p, lz, "zone-edge", 180, 262, 1100, 104, f"<b>{CODE}-FW</b> · HA pair (active / passive) · inspects "
             "every zone")
    fw1 = device(p, ld, f"{CODE}-FW-01", 560, 290, 250, 58)
    fw2 = device(p, ld, f"{CODE}-FW-02", 990, 290, 250, 58)
    link(p, fw1, fw2, cable_by_label("D01-CBL-00005"), "HA · 1G · Cat6", exit=(1, 0.5), entry=(0, 0.5),
         ports=("ha", "ha"), weight=1.4)
    # Circuits: each provider hands off to both firewalls.
    lc = p.layer("2 · Links (Po · speed · VLANs)")
    for n, circ in enumerate(S.CIRCUITS):
        for m, fw in enumerate((fw1, fw2)):
            port = f"wan{n + 1}"
            style = (EDGE.replace("strokeColor=#64748B", "strokeColor=#94A3B8").replace("strokeWidth=1.6", "strokeWidth=1.4")
                     + "labelBackgroundColor=#DBEAFE;labelBorderColor=#2563EB;")
            attrs = {"object": "circuits.circuit", "cid": circ["cid"], "status": "active",
                     "x_handoff": f"{CODE}-FW-0{m + 1}:{port}", "x_speed": circ["speed"],
                     "x_media": circ["media"], "x_patch_a": "", "x_patch_b": ""}
            attrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in attrs.items()), **attrs,
                     "link": f"{NETBOX}/circuits/circuits/?cid={circ['cid']}", "linkTarget": "_blank"}
            same = n == m
            ex = (0.3 if m == 0 else 0.7, 1)
            en = (0.2 + 0.6 * n, 0)
            pts = [] if same else [((560 + n * 470) + 230 * ex[0], 238), (560 + m * 430 + 250 * en[0], 238)]
            eid = p.edge(lc, isp[circ["cid"]], fw, style, esc(f"{circ['speed']} · {circ['media']}") if same else "",
                         attrs, exit=ex, entry=en, points=pts)
            p.edge_label(eid, port, 1, 0, PORT_LABEL)

    # Core stack
    core = stack(p, lz, f"{CODE}-CORE", 600, 462, 640, [f"{CODE}-CORE-1", f"{CODE}-CORE-2"], "zone-mgmt",
                 "CX 6300M ×2 · VSF stack · MDF R01 / R02")
    link(p, fw1, core, cable_by_label("D01-CBL-00001"), exit=(0.5, 1), entry=(0.2, 0),
         points=[(685, 420), (728, 420)], ports=("x1–x2", "1/1/1 · 2/1/1"), bundle=(728, 448))
    link(p, fw2, core, cable_by_label("D01-CBL-00003"), exit=(0.5, 1), entry=(0.8, 0),
         points=[(1115, 420), (1112, 420)], ports=("x1–x2", "1/1/2 · 2/1/2"), bundle=(1112, 448))

    # Main building access stack, left
    main = stack(p, lz, f"{CODE}-ACC-MAIN", 90, 640, 330, [f"{CODE}-ACC-MAIN-{n}" for n in (1, 2, 3)], "zone-sales",
                 "CX 6200F 48G PoE ×3 · MDF R02")
    link(p, core, main, cable_by_label("D01-CBL-00011"), exit=(0, 0.5), entry=(0.5, 0),
         points=[(255, 508)], ports=("1/1/11 · 2/1/11", "1/1/49 · 3/1/49", (-34, 0)), bundle=(255, 600))
    # Building systems beside it
    zone_box(p, lz, "zone-building", 530, 630, 460, 120, "<b>BUILDING</b> · cameras record here; keys report out")
    nvr = device(p, ld, f"{CODE}-NVR-01", 546, 666, 208, 58)
    key = device(p, ld, f"{CODE}-KEY-01", 766, 666, 208, 58)
    link(p, main, nvr, cable_by_label("D01-CBL-00031"), "NVR · 1G · Cat6", exit=(1, 0.48), entry=(0, 0.5),
         ports=("2/1/45", "eth0"))
    link(p, main, key, cable_by_label("D01-CBL-00032"), "KEY · 1G · Cat6", exit=(1, 0.85), entry=(0.5, 1),
         points=[(870, 739)], ports=("2/1/46", "eth0"))

    # The office NAS and the manufacturer's router, right: nested elbows off the core's right side.
    zone_box(p, lz, "zone-office", 1250, 630, 330, 120, "<b>OFFICE</b> · the deal-jacket NAS")
    nas = device(p, ld, f"{CODE}-NAS-01", 1266, 666, 216, 58)
    zone_box(p, lz, "zone-oem", 1600, 630, 340, 120, "<b>OEM</b> · the manufacturer's router")
    oem = device(p, ld, f"{CODE}-OEM-RTR-01", 1616, 666, 216, 58)
    p.cell(p.layer("4 · Circuit IDs (hide before sharing)"),
           f"CID {S.OEM_CIRCUIT['cid']}<br>{esc(S.OEM_CIRCUIT['label'])}", CID_TAG, 1770, 574, 170, 32)
    link(p, core, oem, cable_by_label("D01-CBL-00026"), "OEM · 1G · Cat6 · 65", exit=(1, 0.15), entry=(0.5, 0),
         points=[(1724, 475.5)], ports=("2/1/19", "gi0/1/0", (18, 0)))
    link(p, core, nas, cable_by_label("D01-CBL-00025"), "NAS · 10G · Cat6A", exit=(1, 0.45), entry=(0.5, 0),
         points=[(1374, 502.5)], ports=("1/1/23", "lan1", (18, 0)))

    # Management and power, below: down the gap beside them, then up into each card.
    zone_box(p, lz, "zone-mgmt", 1250, 790, 690, 120, "<b>MGMT &amp; POWER</b> · on the core, in the racks")
    ups1 = device(p, ld, f"{CODE}-UPS-01", 1266, 826, 216, 58)
    ups2 = device(p, ld, f"{CODE}-UPS-02", 1494, 826, 216, 58)
    oob = device(p, ld, f"{CODE}-OOB-01", 1722, 826, 206, 58)
    for n, (dev, label, ports, name) in enumerate([(ups1, "D01-CBL-00033", ("1/1/24", "nmc"), "UPS1"),
                                                   (ups2, "D01-CBL-00034", ("2/1/24", "nmc"), "UPS2"),
                                                   (oob, "D01-CBL-00035", ("1/1/20", "net1"), "OOB")]):
        x = 1225 - n * 35  # far enough apart for the port tags
        y = 930 + n * 18
        target = (1374, 1602, 1825)[n]
        down, across, up = y - 552, target - x, y - 884  # the core's bottom, then the card's
        # The pill sits in the middle of the run under the group, not on the group's border.
        link(p, core, dev, cable_by_label(label), f"{name} · 1G · Cat6", exit=((x - 600) / 640, 1), entry=(0.5, 1),
             points=[(x, y), (target, y)], ports=ports, pos=2 * (down + across / 2) / (down + across + up) - 1)
    note(p, 1250, 984, 690, 30, "Console lines (not cables in NetBox): OOB-01 serial 1–4 to FW-01, FW-02, "
         "CORE-1, CORE-2 · cellular to the MSP. UPS runtime: R01 about 20 min, R02 about 25 min. IDF-SHOP has no UPS.")

    # Service building access stack, straight under the core, on fiber
    shop = stack(p, lz, f"{CODE}-ACC-SHOP", 1000, 1046, 330, [f"{CODE}-ACC-SHOP-1", f"{CODE}-ACC-SHOP-2"], "zone-shop",
                 "CX 6200F 48G PoE ×2 · IDF-SHOP R01")
    link(p, core, shop, cable_by_label("D01-CBL-00013"), exit=(0.78125, 1), entry=(0.3, 0),
         ports=("1/1/12 · 2/1/12", "1/1/49 · 2/1/49"), bundle=(1100, 1034))

    # Rooms and bays: one card per kind of end device, the build counts the rest. Drops leave the stack
    # left to right and drop to nested levels, so none cross.
    ends = [("Main building", 90, 90, 330, main, 756, 880,
             [f"{CODE}-AP-MAIN-01", f"{CODE}-PRN-01", f"{CODE}-PAY-01", f"{CODE}-CAM-01"]),
            ("Service building and lot", 1000, 1000, 330, shop, 1136, 680,
             [f"{CODE}-AP-SHOP-01", f"{CODE}-DIAG-01", f"{CODE}-CAM-03"])]
    for place, fx, sx, sw_w, sw, sw_bottom, box_w, names in ends:
        p.cell(lz, f"<b>{place}</b> · one card per kind of end device; the build shows how many",
               zone_style("#FFFFFF", "#E2E8F0", "#334155", "bottom", 10), fx, 1222, box_w, 210)
        for n, name in enumerate(names):
            d = DEV[name]
            x = fx + 14 + n * 212
            cid = device(p, ld, name, x, 1316, 200, 52, small=True, pill=False,
                         label='<b>%name%</b><br>' + sub("%device_type%"))
            c = CABLE_OF[name][0]
            sw_port = c["a"][0].split(":")[1]
            member = int(c["a"][0].split(":")[0].rsplit("-", 1)[1])
            iface = f"{member}/1/{sw_port.split('/')[-1]}"
            vlan = S.access_vlan(d)
            text = f"{c['speed']} · {c['media']}" + (f" · {vlan}" if vlan else " · trunk")
            ex_x = sx + 30 + n * 70
            level = 1290 - n * 14
            pts = [(ex_x, level), (x + 100, level)]
            down, across = level - sw_bottom, x + 100 - ex_x
            # The pill rides the drop just above its bend, inside the rooms band, not in the IDF band it crosses.
            link(p, sw, cid, c, text, exit=((ex_x - sx) / sw_w, 1), entry=(0.5, 0), points=pts,
                 ports=(iface, "eth0"), weight=1.2, color="#94A3B8",
                 pos=2 * (down - 12) / (down + across + 1316 - level) - 1)
    note(p, 1720, 1222, 220, 210, "<b>End devices</b><br>APs trunk VLANs 11, 41, 70 in the main building and 51, 70 "
         "in the shop, plus management 99, all tagged. Printers and card terminals sit in the zone of the desk "
         "they serve. Desk PCs and phones are not drawn: the switch port carries the zone.", guide=False)

    # Registers and legend, right
    lr = p.layer("6 · Link register")
    link_card = p.cell(lr, "", CARD, 1976, 96, 880, 400)
    p.cell(lr, "<b>Link register</b> — port-channels, members, speed, trunked VLANs", HEADING, 1990, 106, 840, 22)
    names = {f"{CODE}-NAS-01": "NAS", f"{CODE}-OEM-RTR-01": "OEM", f"{CODE}-NVR-01": "NVR", f"{CODE}-KEY-01": "KEY",
             f"{CODE}-UPS-01": "UPS1", f"{CODE}-UPS-02": "UPS2", f"{CODE}-OOB-01": "OOB"}
    rows = []
    for c in S.CABLES[:S.NETWORK_CABLES]:
        a_dev = sorted({e.split(":")[0].replace(f"{CODE}-", "") for e in c["a"]})
        b_dev = sorted({e.split(":")[0].replace(f"{CODE}-", "") for e in c["b"]})
        a_ports = " · ".join(e.split(":")[1] for e in c["a"])
        b_ports = " · ".join(e.split(":")[1] for e in c["b"])
        name = c["lag"] or names.get(c["b"][0].split(":")[0], "")
        speed = c["speed"] + (" LACP" if c["lag"].startswith("Po") else "")
        ids = ", ".join(f"#{S.CABLES.index(c) * 2 + k + 1}" for k in range(len(c["labels"])))
        rows.append([name, ids, f"{'/'.join(a_dev)} {a_ports}", f"{'/'.join(b_dev)} {b_ports}", speed, c["media"],
                     "connected",
                     c["vlans"] or ("access " + str(S.access_vlan(DEV[c["b"][0].split(':')[0]]) or '')
                                    if c["lag"] != "HA" else "heartbeat")])
    # CABLE ID and STATUS are drawn here, wide enough for "connected", so the build doesn't squeeze them in.
    table(p, lr, 1990, 134, [("LINK", 46), ("CABLE ID", 60), ("A-SIDE (MEMBERS)", 176), ("B-SIDE (MEMBERS)", 176),
          ("SPEED", 84), ("MEDIA", 66), ("STATUS", 70), ("TRUNKED VLANS", 162)], rows, row_h=22)
    note(p, 1990, 134 + p.table_height + 8, 840, 32, "All trunks: native VLAN 999 (unused) · explicit allowed list · LACP "
         "fast. End-device drops are in NetBox, not in this register.")
    bottom = 134 + p.table_height + 8 + 32 + 14   # the card fits its table, two-line trunk rows included
    resize(p, link_card, bottom - 96)
    la = p.layer("7 · Asset register")
    ends_roles = ("access-point", "printer", "camera", "card-terminal", "diag-tool")
    reg = [d["name"] for d in S.DEVICES if d["role"] not in ends_roles]  # end devices are counted on their cards
    top = bottom + 14
    asset_card = p.cell(la, "", CARD, 1976, top, 880, 400)
    p.cell(la, "<b>Asset register</b> — mirrors each device's NetBox record", HEADING, 1990, top + 10, 840, 22)
    rows = []
    for name in reg:
        d = DEV[name]
        role = {"ups": "UPS", "nvr": "NVR"}.get(d["role"], d["role"].replace("-", " ").capitalize())
        rows.append([name, role, d["device_type"], d["serial"],
                     d["primary_ip4"].split("/")[0], d["location"], d["rack"],
                     f"U{d['position']}" if d["position"] else "", d["cf_sw_version"]])
    # Wide enough that the STATUS and CRIT columns a build adds leave every cell on one line.
    table(p, la, 1990, top + 36, [("HOSTNAME", 112), ("ROLE", 104), ("MODEL", 166), ("SERIAL", 96), ("MGMT IP", 78),
          ("ROOM", 76), ("RACK/CAB", 58), ("U", 36), ("SW", 114)], rows, row_h=20)
    resize(p, asset_card, 36 + p.table_height + 16)
    legend(p, 1976, top + 36 + p.table_height + 16 + 14, ZONE_KEYS, flows=False)
    p.title_block(p.layer("Border & title block"), CODE, "Physical — devices, links", f"3 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ 3d wireless
def wireless() -> Page:
    p = Page("wireless", "3d · Wireless — APs and SSIDs", 2400, 1060, prefix="d")
    lb, ld = p.layer("Floors"), p.layer("1 · Devices")
    p.layer("Zones")
    p.layer("3 · Mgmt IPs (hide before sharing)")
    p.layer("3b · Serial numbers")
    p.title(lb, f"{CODE} · {S.SITE['name']} — Wireless",
            esc("Access points per building · SSIDs and the zone each one lands in."))
    # A build rewrites this card from the site's wireless_management / wireless_manager fields.
    cloud = icon_card(p, lb, 600, 96, 600, 70, "cloud", "Cloud Wi-Fi management",
                      "Configuration, firmware and guest portal from the vendor's cloud · APs reach it over HTTPS",
                      attrs={"netdiagrams_wireless_mgmt": "1"})
    for n, (bld, place) in enumerate((("MAIN", "Main building"), ("SHOP", "Service building"))):
        fx = 24 + n * 760
        trunk = ", ".join(map(str, S.AP_VLANS[bld]))
        p.cell(lb, f"<b>{place}</b> · ceiling APs on {CODE}-ACC-{bld}: PoE, trunk {trunk}, 99 (all tagged)",
               zone_style("#FFFFFF", "#E2E8F0", "#334155", "top", 11), fx, 210, 740, 130)
        device(p, ld, f"{CODE}-AP-{bld}-01", fx + 20, 250, 360, 60, small=True, pill=False,
               label="<b>%name%</b><br>" + sub("%device_type% · one card per building; the build counts them"))
        p.cell(lb, sub("Each AP's switch port, cable and address are in the AP register "
               "below, rebuilt from NetBox on every run.", 10), SMALL, fx + 400, 250, 320, 60)
    la = p.layer("AP register")
    aps = [d["name"] for d in S.DEVICES if d["role"] == "access-point"]
    p.cell(la, "", CARD, 24, 364, 1520, 60 + 22 * (len(aps) + 1))
    p.cell(la, "<b>AP register</b> — every access point, its switch port and cable", HEADING, 40, 374, 1480, 22)
    rows = []
    for name in aps:
        d = DEV[name]
        c = CABLE_OF[name][0]
        sw, port = c["a"][0].split(":")
        rows.append([name, d["device_type"], d["serial"], d["primary_ip4"].split("/")[0], d["location"],
                     f"{sw.replace(f'{CODE}-', '')} {port}", c["labels"][0]])
    table(p, la, 40, 400, [("NAME", 200), ("MODEL", 140), ("SERIAL", 160), ("MGMT IP", 150), ("LOCATION", 150),
          ("SWITCH PORT", 380), ("CABLE", 300)], rows, row_h=22)
    p.edge(p.layer("2 · Management"), cloud, None, "endArrow=none;html=1;strokeColor=#94A3B8;strokeWidth=1.2;"
           "dashed=1;fontSize=9;fontColor=#475569;labelBackgroundColor=#FFFFFF;" + FONT, "AP management",
           exit=(0.5, 1), tgt_pt=(900, 210))
    lt = p.layer("SSID table")
    p.cell(lt, "", CARD, 1580, 210, 796, 214)
    p.cell(lt, "<b>SSIDs</b> — one per zone, never one for everything", HEADING, 1596, 220, 760, 22)
    rows = [[ssid, str(vlan), S.ZONE[zone][1], sec, notes] for ssid, sec, vlan, zone, notes in S.SSIDS]
    table(p, lt, 1596, 250, [("SSID", 110), ("VLAN", 120), ("ZONE", 80), ("SECURITY", 200), ("NOTES", 250)], rows,
          row_h=30)
    note(p, 1596, 432, 760, 120, "<b>Rules</b><br>· KV-GUEST: client isolation, captive portal, rate limit, DNS "
         "filter; lands in GUEST only.<br>· KV-SHOP: shop tools that can't do 802.1X only; key rotated quarterly and "
         "whenever a technician who knew it leaves.<br>· No SSID for F&amp;I, card terminals, cameras or the key "
         "cabinet: they are wired.<br>· Rogue AP detection on; management VLAN 99 is never broadcast.")
    legend(p, 1580, 580, ZONE_KEYS, flows=False)
    p.title_block(p.layer("Border & title block"), CODE, "Wireless — APs, SSIDs", f"3d of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 4 flows
VERDICT = {"Allow": ("#16A34A", "endArrow=block;endFill=1;", "Permitted"),
           "Conditional": ("#EA580C", "dashed=1;endArrow=block;endFill=1;", "Conditional"),
           "Deny": ("#DC2626", "dashed=1;endArrow=none;", "Denied")}


def flows() -> Page:
    p = Page("flows", "4 · Traffic Flows — who talks to whom", 2400, 60 + 96 + 46 * len(S.FLOWS) + 150, prefix="d")
    lb, lf = p.layer("Lanes"), p.layer("Flows")
    p.title(lb, f"{CODE} · {S.SITE['name']} — Traffic flows",
            esc("Each lane is one conversation: who starts it, who answers, and what the firewall does. Solid green "
            "is permitted, orange dashed is conditional, red ✕ is denied. Everything else is denied by default."))
    xa, xb, top = 120, 980, 110
    p.cell(lb, "<b>INITIATOR</b>", SMALL, xa, top - 6, 320, 20)
    p.cell(lb, "<b>RESPONDER</b>", SMALL, xb, top - 6, 320, 20)
    p.cell(lb, "<b>WHAT · CONDITIONS</b>", SMALL, 1340, top - 6, 900, 20)
    for n, (fid, src, dst, what, verdict, cond, owner) in enumerate(S.FLOWS):
        y = top + 20 + n * 46
        color, extra, word = VERDICT[verdict]
        p.cell(lb, "", BAND.replace("fillColor=#FFFFFF", "fillColor=#FFFFFF" if n % 2 else
               "fillColor=#FBFCFE"), 24, y, 2350, 40)
        p.cell(lb, f"<b>{fid}</b>", "rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#E9ECEF;"
               "strokeColor=none;fontColor=#475569;fontSize=10;html=1;" + FONT, 36, y + 9, 60, 22)
        a = p.cell(lf, esc(src), "rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#FFFFFF;"
                   "strokeColor=#CBD5E1;fontSize=10;fontColor=#0F172A;fontStyle=1;html=1;whiteSpace=wrap;" + FONT, xa,
                   y + 6, 320, 28)
        b = p.cell(lf, esc(dst), "rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#FFFFFF;"
                   "strokeColor=#CBD5E1;fontSize=10;fontColor=#0F172A;fontStyle=1;html=1;whiteSpace=wrap;" + FONT, xb,
                   y + 6, 320, 28)
        # verticalAlign=bottom: the verdict sits above its line, not on it.
        p.edge(lf, a, b, f"html=1;strokeColor={color};strokeWidth=1.8;{extra}fontSize=9;fontColor={color};"
               "labelBackgroundColor=#FFFFFF;fontStyle=1;verticalAlign=bottom;" + FONT, word, exit=(1, 0.5),
               entry=(0, 0.5))
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
    p.cell(lf, "<b>Default deny</b> · anything not listed above, between any two zones, is "
           "blocked and logged",
           TEXT.replace("verticalAlign=top", "verticalAlign=middle").replace("#334155", "#991B1B"), xa, y + 6, 1220,
           28)
    p.title_block(p.layer("Border & title block"), CODE, "Traffic flows", f"4 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 5 failover
def failover() -> Page:
    p = Page("failover", "5 · Failover scenarios", 2400, 900, prefix="d")
    lb = p.layer("Scenarios")
    p.title(lb, f"{CODE} · {S.SITE['name']} — Failover",
            esc("What happens when one thing breaks on a Saturday morning: what fails, what takes over, and what "
                "people notice."))
    scenarios = [
        ("isp", "ISP-A goes down", "Fiber cut or provider outage on D01-ISP-A-01.",
         "The firewall pair moves internet traffic to ISP-B (cable 500/50) within about 30 seconds; the DMS tunnel "
         "and the D02 tunnel rebuild over ISP-B on their own.",
         "DMS screens pause and reconnect. Calls in progress drop and redial."),
        ("dms", "The DMS goes dark", "The DMS vendor's data center or network is down, for every dealer at once.",
         "Nothing on our side can take over: the DMS is theirs. The downtime kit does: paper repair orders and deal "
         "forms, card terminals (they don't need the DMS), and this week's customer list exported to the NAS.",
         "Everything slows to paper. Deals still close and cars still get fixed; it is all keyed in when the DMS "
         "returns."),
        ("firewall", "D01-FW-01 fails", "Power supply, disk or a bad update on the active firewall.",
         "D01-FW-02 takes over the gateway addresses (.1 on every VLAN), both WAN lines and the tunnels; sessions "
         "carry on.", "A few seconds of pause. VPN users may need to reconnect."),
        ("access-switch", "The conduit to the service building is cut",
         "A trencher on the lot cuts the conduit. Both Po12 fibers run in it.",
         "Nothing: the two fibers protect against a bad optic, not a cut conduit. The shop's APs, diagnostic PCs "
         "and cameras are offline until the fiber is spliced.",
         "The shop stops: no repair orders, no diagnostics, no time punches. The plan card asks for a second path."),
        ("power", "Power cut", "The utility drops; the dealership has no generator.",
         "Both UPSs carry the MDF (about 20 and 25 minutes at today's load). IDF-SHOP has no UPS: the shop "
         "switches and their PoE drop at once. While the UPSs last, the console server reaches the firewall over "
         "cellular (both internet boxes are off).",
         "Wi-Fi, desk phones and the shop go dark first. Close the DMS sessions cleanly before the UPSs run out."),
    ]
    for n, (icon, title, what, takes, notice) in enumerate(scenarios):
        y = 100 + n * 136
        p.cell(lb, "", CARD, 24, y, 2350, 124)
        icon_card(p, lb, 40, y + 14, 460, 96, icon, title, what, 34, 14)
        for k, (head, text, color) in enumerate([("WHAT TAKES OVER", takes, "#15803D"),
                                                 ("WHAT PEOPLE NOTICE", notice, "#B45309")]):
            x = 540 + k * 900
            p.cell(lb, f"<b>{head}</b>", SMALL.replace("#64748B", color), x, y + 18, 860, 20)
            p.cell(lb, esc(text), TEXT.replace("fontSize=10", "fontSize=12"), x, y + 42, 860, 70)
    p.title_block(p.layer("Border & title block"), CODE, "Failover scenarios", f"5 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 6 rooftops and cloud
def multisite() -> Page:
    p = Page("multisite", "6 · Rooftops and cloud", 2400, 1130, prefix="d")
    lb, lc, ll = p.layer("Sites"), p.layer("Cards"), p.layer("Tunnels")
    p.title(lb, "Kestrel Valley — Rooftops and cloud",
            esc("D01, the D02 pre-owned store, the hosted DMS, SaaS, the MSP and vendor support. Every site has its "
            "own internet line; the tunnels all end on the D01 firewall pair."))
    inet = icon_card(p, lc, 860, 100, 520, 80, "globe", "Internet", "Each site's own lines · SaaS reached directly "
                     "from every site", 30, 13)
    hq = p.cell(lc, "<b>D01 · Kestrel Valley Motors</b> · 10.30.0.0/16 · about 120 staff<br>"
                + sub("Firewall HA pair · core stack · main and service buildings · 12 APs · the deal-jacket NAS"),
                zone_style("#F5F5FE", "#C2C4F6", "#4F46E5", "top", 12), 760, 420, 720, 156)
    for n, (icon, title, text) in enumerate([("firewall", "D01-FW HA pair", "Ends every tunnel"),
                                             ("router", "Manufacturer's router", "Their own line"),
                                             ("backup", "Deal-jacket NAS", "Copies to the cloud vault nightly")]):
        icon_card(p, lc, 780 + n * 232, 476, 218, 80, icon, title, text, 24, 11)
    br = p.cell(lc, "<b>D02 · Kestrel Valley Pre-Owned</b> · 10.31.0.0/16 · about 12 staff<br>"
                + sub("One firewall with cellular backup · one switch · two APs · a card terminal"),
                zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), 100, 690, 560, 170)
    for n, (icon, title, text) in enumerate([("firewall", "D02-FW-01", "Broadband 300/30 + cellular"),
                                             ("access-switch", "D02-ACC-1", "24-port PoE")]):
        icon_card(p, lc, 120 + n * 264, 756, 250, 80, icon, title, text, 24, 11)
    cl = p.cell(lc, "<b>DMS (hosted)</b> · the DMS vendor's data center<br>"
                + sub("Deals, repair orders, parts and accounting for both rooftops, reached only over the tunnel"),
                zone_style("#F3FAF9", "#AADAD5", "#0D9488", "top", 12), 1580, 690, 560, 170)
    for n, (icon, title, text) in enumerate([("dms", "DMS", "Both rooftops' records"),
                                             ("backup", "Backup vault", "Immutable, 30 days")]):
        icon_card(p, lc, 1600 + n * 264, 756, 250, 80, icon, title, text, 24, 11)
    saas = icon_card(p, lc, 1580, 240, 560, 80, "cloud", "SaaS", "CRM, email, phones, lender portals", 30, 13)
    vend = icon_card(p, lc, 100, 240, 560, 80, "users", "Vendor support", "DMS vendor, manufacturer · per ticket · MFA",
                     30, 13)
    msp = icon_card(p, lc, 100, 420, 560, 80, "wrench", "MSP", "VPN · MFA · logged", 30, 13)
    tunnel = ("html=1;strokeColor=#2563EB;strokeWidth=2;dashed=1;dashPattern=8 4;endArrow=none;fontSize=10;"
              "fontColor=#1E3A8A;labelBackgroundColor=#FFFFFF;" + FONT)
    plain_line = "html=1;strokeColor=#94A3B8;strokeWidth=1.4;endArrow=none;fontSize=10;fontColor=#475569;" \
                 "labelBackgroundColor=#FFFFFF;" + FONT
    p.edge(ll, br, hq, tunnel, "IPsec · F22", exit=(1, 0.3), entry=(0.1, 1), points=[(832, 741)])
    p.edge(ll, cl, hq, tunnel, "IPsec · F01 F03", exit=(0, 0.3), entry=(0.9, 1), points=[(1408, 741)])
    p.edge(ll, vend, hq, tunnel.replace("#2563EB", "#7C3AED"), "VPN + MFA · F21", exit=(1, 0.5), entry=(0.3, 0),
           points=[(976, 280)])
    p.edge(ll, msp, hq, tunnel.replace("#2563EB", "#EA580C"), "VPN + MFA · F20", exit=(1, 0.5), entry=(0, 0.2564))
    p.edge(ll, inet, hq, plain_line, "ISP-A + ISP-B", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(ll, inet, saas, plain_line, "HTTPS", exit=(1, 0.5), entry=(0.5, 0), points=[(1860, 140)])
    lt = p.layer("Site table")
    p.cell(lt, "<b>Sites</b>", HEADING, 100, 900, 2040, 22)
    table(p, lt, 100, 926, [("CODE", 90), ("SITE", 240), ("PREFIX", 160), ("INTERNET", 420), ("BACKUP", 380),
          ("LINK TO D01", 750)], [
[("D01", f"{NETBOX}/dcim/sites/?slug=d01"), "Kestrel Valley Motors", "10.30.0.0/16",
"ISP-A DIA 1G fiber · ISP-B cable 500/50", "Second ISP, firewall HA pair", "—"],
[("D02", f"{NETBOX}/dcim/sites/?slug=d02"), "Kestrel Valley Pre-Owned", "10.31.0.0/16",
"Provider C broadband 300/30", "Cellular on D02-FW-01", "IPsec to the D01 firewall pair"],
["DMS", "DMS (hosted)", "vendor's ranges", "Vendor's network", "The vendor's own failover",
"IPsec to the D01 firewall pair"]], row_h=26)
    p.title_block(p.layer("Border & title block"), "All", "Rooftops and cloud", f"6 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 7 flow register
ZONE_ORDER = ["zone-internet", "zone-fi", "zone-sales", "zone-office", "zone-cde", "zone-service", "zone-shop",
              "zone-parts", "zone-oem", "zone-guest", "zone-voice", "zone-building", "zone-mgmt"]
MATRIX = {  # (from, to): (verdict, flows)
    ("zone-fi", "zone-internet"): ("cond", "F01 F02"), ("zone-sales", "zone-internet"): ("allow", "F03 F04"),
    ("zone-office", "zone-internet"): ("cond", "F03 F13 F14"), ("zone-service", "zone-internet"): ("allow", "F03"),
    ("zone-parts", "zone-internet"): ("allow", "F03"), ("zone-sales", "zone-fi"): ("deny", "F05"),
    ("zone-shop", "zone-fi"): ("deny", "F05 F09"), ("zone-guest", "zone-fi"): ("deny", "F05 F16"),
    ("zone-shop", "zone-oem"): ("allow", "F06"), ("zone-service", "zone-oem"): ("allow", "F07"),
    ("zone-parts", "zone-oem"): ("allow", "F07"), ("zone-oem", "zone-shop"): ("deny", "F08"),
    ("zone-oem", "zone-service"): ("deny", "F08"), ("zone-oem", "zone-parts"): ("deny", "F08"),
    ("zone-shop", "zone-sales"): ("deny", "F09"), ("zone-shop", "zone-office"): ("deny", "F09"),
    ("zone-cde", "zone-internet"): ("allow", "F10"), ("zone-service", "zone-cde"): ("deny", "F11"),
    ("zone-parts", "zone-cde"): ("deny", "F11"), ("zone-fi", "zone-office"): ("allow", "F12"),
    ("zone-guest", "zone-internet"): ("allow", "F15"), ("zone-guest", "zone-sales"): ("deny", "F16"),
    ("zone-voice", "zone-internet"): ("allow", "F17"), ("zone-building", "zone-internet"): ("cond", "F19 F29"),
    ("zone-internet", "zone-mgmt"): ("cond", "F20 F27"), ("zone-internet", "zone-fi"): ("cond", "F21"),
    ("zone-internet", "zone-office"): ("allow", "F22"), ("zone-mgmt", "zone-internet"): ("cond", "F23 F25"),
    ("zone-office", "zone-building"): ("cond", "F28"), ("zone-sales", "zone-building"): ("cond", "F28"),
    ("zone-guest", "zone-mgmt"): ("deny", "F26"), ("zone-shop", "zone-mgmt"): ("deny", "F26"),
}


def register() -> Page:
    # Grows with the register; the title block just clears the zone matrix.
    p = Page("register", "7 · Flow register & standards", 2400, 806 + 26 * len(S.FLOWS), prefix="d")
    lf, lm, ls = p.layer("Flow register"), p.layer("Zone matrix"), p.layer("Standards")
    p.title(lf, f"{CODE} · {S.SITE['name']} — Flow register and standards",
            esc("The segmentation in writing: every permitted conversation, its conditions and owner, then default "
            "deny. The zone matrix is the same rules as a grid. Naming and drawing standards at the right."))
    p.cell(lf, "", CARD, 24, 92, 1500, 22 + 26 * (len(S.FLOWS) + 2) + 30)
    p.cell(lf, "<b>Flow register</b>", HEADING, 40, 102, 1460, 22)
    look = {"Allow": "#15803D", "Conditional": "#B45309", "Deny": "#B91C1C"}
    rows = [[fid, src, dst, what, f'<font color="{look[v]}"><b>{v}</b></font>', cond, owner]
            for fid, src, dst, what, v, cond, owner in S.FLOWS]
    rows.append(["—", "Any", "Any", "Everything not listed above", '<font color="#B91C1C"><b>Deny</b></font>',
                 "Default deny, logged", "IT manager"])
    table(p, lf, 40, 128, [("ID", 44), ("FROM", 210), ("TO", 200), ("WHAT", 330), ("VERDICT", 90),
          ("CONDITIONS", 360), ("OWNER", 230)], rows, row_h=26)
    my = 128 + p.table_height + 30
    n = len(ZONE_ORDER)
    matrix_card = p.cell(lm, "", CARD, 24, my, 1500, 60 + 30 * (n + 1))
    p.cell(lm, "<b>Zone matrix</b> — rows start the conversation, columns answer; blank is "
           "default deny", HEADING, 40, my + 10, 1460, 22)
    cols = [("FROM \\ TO", 92)] + [(S.ZONE[z][1], 104) for z in ZONE_ORDER]
    cell = {"allow": '<font color="#15803D"><b>allow</b></font>', "cond": '<font color="#B45309"><b>cond.</b></font>',
            "deny": '<font color="#B91C1C"><b>deny</b></font>'}
    rows = []
    for a in ZONE_ORDER:
        row = [S.ZONE[a][1]]
        for b in ZONE_ORDER:
            if a == b:
                row.append('<font color="#94A3B8">inside zone</font>')
            elif (a, b) in MATRIX:
                v, f = MATRIX[(a, b)]
                row.append(f"{cell[v]} {f}")
            else:
                row.append("")
        rows.append(row)
    table(p, lm, 40, my + 40, cols, rows, row_h=30, key=KEY_CELL)
    resize(p, matrix_card, 40 + p.table_height + 16)
    sx = 1560
    p.cell(ls, "", CARD, sx, 92, 816, 410)
    p.cell(ls, "<b>Naming and drawing standards</b>", HEADING, sx + 16, 102, 780, 22)
    table(p, ls, sx + 16, 128, [("ITEM", 170), ("STANDARD", 610)], [
          ["Site code", "D + two digits: D01 Kestrel Valley Motors, D02 Pre-Owned"],
          ["Device", "SITE-ROLE-NN: D01-FW-01, D01-ACC-MAIN-1 (building, member)"],
          ["Stack", "SITE-ROLE-BUILDING: D01-ACC-MAIN; members -1, -2, -3"],
          ["Cable label", "SITE-CBL-nnnnn on both ends: D01-CBL-00011"],
          ["Zone tag", "zone-&lt;name&gt; on every device, VLAN and prefix"],
          ["VLAN", "10s sales and F&amp;I, 20s office, 30 card, 40s service, 50s shop and parts, 65 manufacturer, "
                   "70 guest, 75 voice, 80s building, 99 management"],
          ["Subnet", "10.&lt;30 + site&gt;.&lt;vlan&gt;.0/24 (card /26, guest from 172.16)"],
          ["Gateway", ".1 on the firewall pair, for every VLAN"],
          ["Link pill", "Po · speed · media; port tags at each end"],
          ["Hide before sharing", "Layers 3 (mgmt IPs) and 4 (circuit IDs)"],
          ["Change", "Edit NetBox, then rebuild; never fix the drawing alone"]], row_h=30)
    p.title_block(p.layer("Border & title block"), CODE, "Flow register and standards", f"7 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ main
def build() -> ET.Element:
    return mxfile((overview(), logical(), physical(), wireless(), flows(), failover(), multisite(), register()),
                  "netdiagrams dealership template")


def main() -> None:
    tree = build()
    ET.indent(tree, space=" ")
    OUT.write_text(ET.tostring(tree, encoding="unicode") + "\n", "utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
