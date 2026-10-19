"""Generate src/netdiagrams/data/B01-Bank-Template.drawio, the bank standard.

Eight sheets drawn for the fictional Ninebark Community Bank (site B01, the main
office): overview, logical, physical, wireless, traffic flows, failover,
branches, processors and cloud, and the flow register. Every fact comes from
scripts/bank_template/site.py, the same source scripts/make_bank_sample.py turns
into the sample NetBox export, so `netdiagrams build --input sample-bank.json`
reproduces the template. A fork of make_office_template.py: the shared styles
come from there, the bank's own icons and sheets are here.

    python scripts/make_bank_template.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bank_template import site as S  # noqa: E402
from drawkit import (  # noqa: E402
    BAND, EDGE, FONT, NETBOX, NOTE, POINTS, RACK_PILL, SUBTITLE, TITLE, Page, _svg, esc, mxfile, sub, zone_style)
from make_office_template import (  # noqa: E402  (the office kit: styles, tables and the common icons)
    BLUE, BUNDLE, CARD, CID_TAG, CYAN, GREY, HEADING, ICONS as OFFICE_ICONS, IP_TAG, KEY_CELL, PINK, PORT_LABEL,
    SLATE, SMALL, SN_TAG, TEXT, VERDICT, VIOLET, _circle, _line, _rect, group_style, table)

# ------------------------------------------------------------------ the bank's icons, on the office set
FUCHSIA, RED, ORANGE2 = "#A21CAF", "#B91C1C", "#C2410C"
ICONS = {
    **OFFICE_ICONS,
    "atm": _svg("#F8E3FB", _rect(8, 6, 16, 20, FUCHSIA, rx=2) + _rect(11, 9, 10, 6, FUCHSIA, rx=1)
                + _line("12,19 20,19", FUCHSIA) + _line("12,22.5 17,22.5", FUCHSIA)),
    "cash-recycler": _svg("#E3EBFC", _rect(5.5, 10, 21, 12, BLUE, rx=2) + _circle(16, 16, 3, BLUE)
                          + _line("9,13.5 9,18.5", BLUE) + _line("23,13.5 23,18.5", BLUE)),
    "wire-workstation": _svg("#FDE4E4", _rect(6, 7, 20, 13, RED) + _line("16,20 16,24", RED) + _line("12,24.5 20,24.5", RED)
                             + _line("10,13.5 21,13.5", RED) + _line("18.5,11 21,13.5 18.5,16", RED)),
    "card-printer": _svg("#FCEBDF", _rect(10, 5.5, 12, 9, ORANGE2, rx=1.2) + _line("10,8.5 22,8.5", ORANGE2)
                         + _rect(6.5, 13, 19, 10, ORANGE2, rx=2.5, fill="#FCEBDF") + _line("10,19.5 15,19.5", ORANGE2)),
    "alarm-panel": _svg("#FBE4EF", _line("10,21 10,15 11.2,11.4 13.5,9.3 16,8.6 18.5,9.3 20.8,11.4 22,15 22,21", PINK)
                        + _line("8,21 24,21", PINK) + _line("14,24.5 18,24.5", PINK) + _line("16,6 16,8.6", PINK)),
    "provider-router": _svg("#EFE7FD", _circle(16, 16, 9.5, VIOLET, width=1.5) + _line("10.5,13 21.5,13", VIOLET)
                            + _line("19.2,10.8 21.5,13 19.2,15.2", VIOLET) + _line("21.5,19 10.5,19", VIOLET)
                            + _line("12.8,16.8 10.5,19 12.8,21.2", VIOLET)),
    "bank": _svg("#E2E8F0", _line("6,12 16,6.5 26,12 6,12", SLATE) + _line("9.5,14.5 9.5,21.5", SLATE)
                 + _line("14,14.5 14,21.5", SLATE) + _line("18,14.5 18,21.5", SLATE) + _line("22.5,14.5 22.5,21.5", SLATE)
                 + _line("6,24.5 26,24.5", SLATE)),
}
ICON_FOR_ROLE = {"firewall": "firewall", "core-switch": "core-switch", "access-switch": "access-switch",
                 "access-point": "access-point", "hypervisor": "hypervisor", "storage": "storage", "server": "server",
                 "ups": "ups", "console-server": "console-server", "printer": "printer", "nvr": "nvr", "camera": "camera",
                 "door-controller": "door-controller", "atm": "atm", "cash-recycler": "cash-recycler",
                 "wire-workstation": "wire-workstation", "card-printer": "card-printer", "alarm-panel": "alarm-panel",
                 "provider-router": "provider-router", "router": "firewall"}


def label_style(icon: str, size: int = 22, left: int = 28, font: int = 10, valign: str = "top", arc: int = 12) -> str:
    return (f"shape=label;rounded=1;absoluteArcSize=1;arcSize={arc};fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;"
            f"shadow=1;align=left;verticalAlign={valign};spacingTop=5;spacingLeft={left};fontSize={font};fontColor=#0F172A;"
            f"whiteSpace=wrap;html=1;{POINTS}{FONT}image=data:image/svg+xml,{ICONS[icon]};imageWidth={size};"
            f"imageHeight={size};imageAlign=left;imageVerticalAlign=middle;")


DEVICE_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 30, 38, 11)
SMALL_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 22, 28, 10)
MEMBER_ROW = lambda role: label_style(ICON_FOR_ROLE.get(role, "access-switch"), 16, 22, 9)


LEGEND_ITEMS = [("firewall", "Firewall (HA pair)"), ("provider-router", "Provider-owned router"),
                ("core-switch", "Core switch / stack"), ("access-switch", "Access switch / stack"),
                ("access-point", "Wireless AP (cloud managed)"), ("hypervisor", "Virtualization host"),
                ("storage", "Storage / NAS"), ("ups", "UPS"), ("console-server", "Out-of-band console"),
                ("printer", "Printer / MFP"), ("atm", "ATM"), ("cash-recycler", "Teller cash recycler"),
                ("wire-workstation", "Wire workstation"), ("card-printer", "Instant-issue card printer"),
                ("alarm-panel", "Alarm panel"), ("nvr", "Video recorder"), ("camera", "Camera"),
                ("door-controller", "Door controller"), ("cloud", "Cloud / SaaS"), ("bank", "Branch / site")]


def legend(p: Page, x: float, y: float, zones: list[tuple[str, str, str, str]], flows: bool = True) -> float:
    """The bank legend: icons, line meanings and the zone colors. Returns its height."""
    layer = p.layer("Legend")
    rows = -(-len(LEGEND_ITEMS) // 2)
    lines = [("#64748B", 1.6, "", "Link · pill = Po · speed · media · tag = port"),
             ("#64748B", 2.5, "", "Weight = speed (thicker = 10G and up)"),
             ("#7C3AED", 1.4, "", "The core processor's link (their router)")]
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
OUT = DATA / "B01-Bank-Template.drawio"
DATE = "2026-10-15"
PROJECT = "Bank network standard"
SHEETS = 8
CORE_LINK = "#7C3AED"   # the core processor's circuit and its router's cables

DEV = {d["name"]: d for d in S.DEVICES}
CABLE_OF = {}
for _c in S.CABLES:
    for _end in _c["a"] + _c["b"]:
        CABLE_OF.setdefault(_end.split(":")[0], []).append(_c)
ATTR_ORDER = ["name", "role", "manufacturer", "device_type", "platform", "serial", "asset_tag", "status", "site",
              "location", "rack", "position", "face", "primary_ip4", "virtual_chassis", "vc_position", "description",
              "tags", "cf_sw_version", "cf_support_contract", "cf_lifecycle", "x_modules", "x_power"]
MEDIA_LOOK = {  # label background, label border
    "DAC": ("#E2E8F0", "#64748B"), "MMF OM4": ("#A5F3FC", "#0891B2"),
    "Cat6": ("#DBEAFE", "#2563EB"), "Cat6A": ("#DBEAFE", "#2563EB"),
}
ZONE_LOOK = {z[0]: z[6] for z in S.ZONES}
ZONE_CHIPS = [(z[1], *z[6]) for z in S.ZONES]


# ------------------------------------------------------------------ objects
def resize(p, cid: str, height: float) -> None:
    """Set a drawn box's height once what it holds is measured."""
    p.find(cid).find(".//mxGeometry").set("height", f"{height:g}")


def dev_attrs(name: str) -> dict:
    d = DEV[name]
    a = {k: str(d.get(k, "") or "") for k in ATTR_ORDER}
    a["site"] = S.SITE["code"]
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
        p.cell(p.layer("3b · Serial numbers"), f"SN {d['serial']}", SN_TAG, x + w - 116, y + h - 18, 110, 14)
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
         ports=None, bundle=None, weight=None, color="#64748B") -> str:
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
                 exit=exit, entry=entry)
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
    text = title if title is not None else f"<b>{z[1]}</b> · {esc(z[2])}"
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


def pill_label(p: Page, layer: str, x, y, w, text: str, fill="#F1F5F9", font="#475569") -> str:
    return p.cell(layer, esc(text), f"rounded=1;absoluteArcSize=1;arcSize=14;fillColor={fill};"
                  f"strokeColor=none;fontColor={font};fontSize=9;fontStyle=1;html=1;whiteSpace=wrap;{FONT}", x, y, w,
                  20)


# ------------------------------------------------------------------ 1 overview
def overview() -> Page:
    p = Page("overview", "1 · Overview — for the board", 2000, 990, prefix="f")
    lay = p.layer("Overview")
    p.cell(lay, "How the bank's network is protected", TITLE, 24, 18, 1000, 32)
    p.cell(lay, "Board overview: no technical detail. The main office and every branch follow the same "
           "design.", SUBTITLE, 24, 52, 1000, 22)
    x, w = 170, 1010
    rows = [  # y, side label, color
        (100, "Outside", "#64748B"), (305, "Banking &amp; services", "#2563EB"), (531, "Customer-facing", "#A21CAF"),
        (767, "Security &amp; management", "#DB2777")]
    for y, text, color in rows:
        p.cell(lay, f"<b>{text}</b>", "text;html=1;align=right;verticalAlign=middle;fontSize=10;"
               f"fontColor={color};whiteSpace=wrap;{FONT}", 40, y, 120, 60)
    outside = icon_card(p, lay, x, 92, w, 76, "cloud", "The internet, the core processor and outside parties",
                        "The core processor and card network over their own private line · the Federal Reserve for "
                        "wires · email and files in SaaS · the alarm company · the IT and security providers")
    gate_bar(p, lay, x, 214, w, "<b>Security gate</b> · the firewall: everything between the bank and the outside, "
             "the core processor included, passes through it")
    staff = p.cell(lay, "<b>Banking and services</b> · the people who serve customers and the systems behind them",
                   zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), x, 270, w, 130)
    for n, (icon, title, text) in enumerate([
            ("cash-recycler", "Teller line", "Teller PCs and cash recyclers"),
            ("users", "Platform & back office", "Desks, operations, staff Wi-Fi"),
            ("wire-workstation", "Wire room", "Two PCs, Federal Reserve only"),
            ("card-printer", "Card issuing", "Prints debit cards"),
            ("server", "Servers & backup", "Files, imaging, backup")]):
        icon_card(p, lay, x + 16 + n * 198, 306, 186, 76, icon, title, text, 24, 11)
    gate_bar(p, lay, x, 430, w, "<b>Same security gate</b> · between every group inside the bank, ATMs and "
             "guests included")
    p.cell(lay, "<b>Customer-facing</b> · in front of customers, trusted by no one",
           zone_style("#FDF4FF", "#F0ABFC", "#A21CAF", "top", 12), x, 486, w, 150)
    icon_card(p, lay, x + 16, 522, 480, 92, "atm", "ATMs",
              "The drive-up and lobby ATMs talk to the card and ATM processor and nothing else")
    guest = icon_card(p, lay, x + 514, 522, 480, 92, "guest", "Lobby guest Wi-Fi",
                      "Customers get the internet and nothing else; they can't see each other")
    gate_bar(p, lay, x, 666, w, "<b>Same security gate</b> · physical security and network management have "
             "their own doors, opened only for the people who need them")
    p.cell(lay, "<b>Security and management</b> · the systems that guard the bank and keep it running",
           zone_style("#FDF4F9", "#F3B8D6", "#DB2777", "top", 12), x, 722, w, 150)
    icon_card(p, lay, x + 16, 758, 480, 92, "alarm-panel", "Alarm, cameras and doors",
              "The alarm reports to its monitoring center; cameras record in the comms room")
    mgmt = icon_card(p, lay, x + 514, 758, 480, 92, "wrench", "Network management",
                     "Firewalls, switches, Wi-Fi and power; reached only by IT and the MSP")
    arrows = p.layer("Arrows")
    # The MSP and remote staff: in through the gate, with MFA.
    p.edge(arrows, outside, mgmt, "endArrow=block;endFill=1;html=1;strokeColor=#7C3AED;strokeWidth=1.6;dashed=1;"
           "fontSize=9;fontColor=#4C1D95;labelBackgroundColor=#FFFFFF;" + FONT, "", exit=(1, 0.7), entry=(1, 0.5),
           points=[(1206, 145.2), (1206, 804)])
    p.cell(arrows, "<b>The MSP &amp; remote staff</b>: in through the gate, with MFA ↓",
           "text;html=1;align=right;verticalAlign=middle;fontSize=9;fontColor=#6D28D9;" + FONT, 900, 244, 270, 22)
    # Guests: no direct path to the bank.
    p.edge(arrows, guest, staff, "endArrow=none;html=1;strokeColor=#DC2626;strokeWidth=1.6;dashed=1;fontSize=9;"
           "fontColor=#991B1B;labelBackgroundColor=#FFFFFF;" + FONT, "No direct path<br>from guests to the bank",
           exit=(0.25, 0), entry=(0.6277, 1))
    p.cell(arrows, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
           "fontSize=10;fontStyle=1;" + FONT, 794, 405, 20, 20)
    # What this means for the bank: Ninebark's promises, on their own layer so a build marks them EXAMPLE
    rx = 1240
    promises = p.layer("Business promises (Ninebark's; rewrite for your bank)")
    p.cell(promises, "", "rounded=1;arcSize=2;html=1;fillColor=none;strokeColor=none;", rx - 12, 120, 724, 736)
    p.cell(lay, "What this means for the bank", HEADING.replace("fontSize=12", "fontSize=14"), rx, 92, 700, 24)
    cards = [
        ("cash-recycler", "Tellers keep working",
         "Teller traffic goes to the core processor over its own private line, not the internet. If that line "
         "drops, tellers switch to the core system's offline mode (sheet 5)."),
        ("wire-workstation", "The wire room is isolated",
         "Two workstations reach the Federal Reserve and the core processor and nothing else; any attempt to "
         "reach them raises an alert."),
        ("card-printer", "Card data is fenced",
         "The instant-issue card printer has a network of its own that talks only to the card processor."),
        ("atm", "ATMs reach only their processor",
         "The ATMs talk to the card and ATM processor and nothing else; the servicer gets in only in a booked, "
         "logged window."),
        ("guest", "Lobby guests get the internet only",
         "Customers' phones are on their own network; they can't see each other, the staff or the tellers."),
        ("power", "No single box takes the bank down",
         "A firewall pair, stacked switches, two internet lines and two UPSs: one failure is a ticket, not an "
         "outage. The core processor's single line is the known exception."),
    ]
    for n, (icon, title, text) in enumerate(cards):
        icon_card(p, promises, rx, 128 + n * 122, 700, 106, icon, title, text, 26, 12)
    p.title_block(p.layer("Border & title block"), "All", "Overview — the board", f"1 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ 2 logical
def vlan_rows(zone: str) -> list[list]:
    return [[(str(vid), f"{NETBOX}/ipam/vlans/?vid={vid}&site=b01"), name, subnet, gw]
            for vid, name, z, subnet, gw in S.VLANS if z == zone]


VLAN_COLS = [("VLAN", 44), ("NAME", 130), ("SUBNET", 132), ("GATEWAY", 110)]


def logical() -> Page:
    p = Page("logical", "2 · Logical — Zones, VLANs, Subnets", 2400, 1370, prefix="f")
    lb, lz = p.layer("Bands"), p.layer("Zones")
    lt = p.layer("VLAN tables")
    p.title(lb, f"{S.SITE['code']} · {S.SITE['name']} — Logical",
            esc("Zones · VLANs · subnets · gateways. Every VLAN lives in one zone and every gateway is on the firewall, "
            "so every packet between zones is inspected; the core processor's router sits behind it too."))
    W = 1880
    bands = {"OUT": (96, 170), "EDGE": (282, 270), "BANK": (568, 184), "SERV": (768, 150),
             "CUST": (934, 150), "MGMT": (1100, 150)}
    for code, label, _ in S.BANDS:
        y, h = bands[code]
        p.band(lb, y, h, code, label.split(" · ")[0], W)
    # OUTSIDE: providers and outside parties, no VLANs.
    zone_box(p, lz, "zone-internet", 100, 108, 1790, 146)
    p.cell(lz, esc(S.ZONE["zone-internet"][5]), SMALL, 112, 132, 900, 18)
    for n, (icon, title, text) in enumerate([
            ("isp", "ISP-A", "DIA 1G · fiber · static 203.0.113.0/29"), ("isp", "ISP-B", "Cable 500/50 · DHCP"),
            ("cloud", "SaaS", "Mail, files, meetings, phones"), ("bank", "FedLine", "Federal Reserve · wires, ACH"),
            ("alarm-panel", "Alarm center", "Monitoring · IP + cellular"),
            ("wrench", "MSP, MSSP, remote staff", "VPN · MFA · logged"),
            ("bank", "B02 Elm Street", "10.32.0.0/16 · IPsec to B01")]):
        icon_card(p, lz, 112 + n * 252, 160, 240, 80, icon, title, text, 24, 11)
    # EDGE: the firewall pair and its interfaces; the core processor's link beside it.
    zone_box(p, lz, "zone-edge", 100, 294, 1340, 246)
    p.cell(lz, esc(S.ZONE["zone-edge"][5]), SMALL, 112, 318, 900, 18)
    p.cell(lz, "<b>B01-FW</b> · HA pair (active / passive)",
           zone_style("#FFFFFF", "#94A3B8", "#334155", "top", 10), 112, 346, 300, 150)
    for n, name in enumerate(("B01-FW-01", "B01-FW-02")):
        device(p, p.layer("Devices"), name, 124, 376 + n * 60, 276, 52, ip=False, serial=False, pill=False)
    p.cell(lz, "<b>Firewall interfaces</b>", HEADING.replace("fontSize=12", "fontSize=10"), 440, 346, 300, 20)
    table(p, lt, 440, 370, [("INTERFACE", 130), ("ZONE", 120), ("VLAN", 110), ("IP / PREFIX", 220)], [
          ["wan1", "INTERNET", "—", "203.0.113.2/29 (ISP-A)"], ["wan2", "INTERNET", "—", "DHCP (ISP-B)"],
          ["x1–x2 (Po1 / Po2)", "all inside zones", "10–99 tagged", ".1 on every VLAN"],
          ["port5", "PARTNER", "100 untagged", "10.30.100.1/29 (to B01-CPR-01)"],
          ["ssl-vpn", "EDGE", "—", "10.30.200.0/24 (VPN pool)"], ["ipsec-b02", "INTERNET", "—", "to 10.32.0.0/16"]],
          row_h=22)
    p.cell(lz, "<b>Remote access</b>", HEADING.replace("fontSize=12", "fontSize=10"), 1046, 346, 300, 20)
    table(p, lt, 1046, 370, [("POOL", 50), ("NAME", 100), ("SUBNET", 110), ("WHO", 120)], [
          ["—", "VPN-POOL", "10.30.200.0/24", "Staff, MSP, ATM servicer; MFA"],
          ["—", "IPSEC-B02", "10.32.0.0/16", "Elm Street branch"]], row_h=22)
    zone_box(p, lz, "zone-partner", 1450, 294, 440, 246, "<b>ZONE PARTNER</b> · Core and card processor links")
    p.cell(lz, esc(S.ZONE["zone-partner"][5]), SMALL, 1462, 318, 416, 32)
    device(p, p.layer("Devices"), "B01-CPR-01", 1462, 356, 416, 52, ip=False, serial=False, pill=False,
           label="<b>%name%</b><br>" + sub("%device_type% · the core processor's, we hold no login"))
    table(p, lt, 1462, 420, VLAN_COLS, vlan_rows("zone-partner"), row_h=22)
    # Inside zones with VLAN tables.
    layout = {"BANK": ["zone-teller", "zone-staff", "zone-wire", "zone-card"],
              "SERV": ["zone-servers", "zone-voice"], "CUST": ["zone-atm", "zone-guest"],
              "MGMT": ["zone-security", "zone-mgmt"]}
    for code, zones in layout.items():
        y, h = bands[code]
        bw = (1790 - 10 * (len(zones) - 1)) / len(zones)
        for n, zone in enumerate(zones):
            zx = 100 + n * (bw + 10)
            z = S.ZONE[zone]
            zone_box(p, lz, zone, zx, y + 12, bw, h - 24, f"<b>ZONE {z[1]}</b> · {esc(z[2])}")
            lives = sub("Lives here: " + esc(z[4]), 9, "#64748B")
            if len(zones) > 2:
                p.cell(lz, esc(z[5]), SMALL, zx + 12, y + 36, bw - 24, 26)
                table(p, lt, zx + 12, y + 66, VLAN_COLS, vlan_rows(zone), row_h=22)
                p.cell(lz, lives, SMALL, zx + 12, y + h - 40, bw - 24, 26)
            else:
                p.cell(lz, esc(z[5]), SMALL, zx + 12, y + 36, bw - 24, 20)
                table(p, lt, zx + 12, y + 62, VLAN_COLS, vlan_rows(zone), row_h=22)
                p.cell(lz, lives, SMALL, zx + 452, y + 62, bw - 470, 40)
    legend(p, 2000, 96, ZONE_CHIPS, flows=False)
    p.title_block(p.layer("Border & title block"), "B01", "Logical — zones, VLANs", f"2 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 3 physical
FLOOR_CARDS = {  # floor -> one drawn device per kind of end device on that floor's stack; the build counts the rest
    1: ["B01-AP-F1-01", "B01-PRN-F1-01", "B01-CAM-01", "B01-TCR-01", "B01-ATM-01", "B01-ALARM-01"],
    2: ["B01-AP-F2-01", "B01-PRN-F2-01", "B01-CAM-10", "B01-WIRE-01", "B01-CARD-01"],
}
LINK_NAME = {"B01-NAS-01": "NAS", "B01-NVR-01": "NVR", "B01-DOOR-01": "DOOR", "B01-UPS-01": "UPS1",
             "B01-UPS-02": "UPS2", "B01-OOB-01": "OOB", "B01-CPR-01": "CPR"}
BACKBONE = [c for c in S.CABLES if not c["labels"][0] >= "B01-CBL-00101"]   # drops are 00101 upward


def physical() -> Page:
    p = Page("physical", "3 · Physical — Devices, Uplinks, Trunks", 2880, 1600, prefix="f")
    lb = p.layer("Bands")
    lz = p.layer("Zones (groups · stacks)")
    p.layer("2 · Links (Po · speed · VLANs)")
    ld = p.layer("1 · Devices")
    for name in ("3 · Mgmt IPs (hide before sharing)", "3b · Serial numbers", "4 · Circuit IDs (hide before sharing)"):
        p.layer(name)
    p.title(lb, f"{S.SITE['code']} · {S.SITE['name']} — Physical",
            esc("Devices · uplinks · port-channels · trunked VLANs · rack and U on every device. Hover a device or Edit "
            "Data (Ctrl+M) for its NetBox record."))
    W = 1920
    p.band(lb, 96, 130, "ISP", "PROVIDERS", W)
    p.band(lb, 242, 760, "C-1", "COMMS-1 · FLOOR 1", W)
    p.band(lb, 1018, 170, "IDF-2", "IDF-2 · FLOOR 2", W)
    p.band(lb, 1204, 250, "FLRS", "ON THE FLOORS", W)

    # Providers and circuits: two internet lines and the core processor's private circuit.
    isp = {}
    lcid = p.layer("4 · Circuit IDs (hide before sharing)")
    for n, circ in enumerate(S.CIRCUITS):
        cx = 560 + n * 470 if n < 2 else 1512.5
        title = f"ISP-{'AB'[n]}" if n < 2 else "Core processor"
        isp[circ["cid"]] = p.cell(ld, f"<b>{title}</b><br>{sub(esc(circ['label']))}",
                                  label_style("provider-router" if n == 2 else "isp", 26, 36, 11, "middle", 12)
                                  + "spacingTop=0;", cx, 118, 230 if n < 2 else 250, 60)
        p.cell(lcid, f"CID {circ['cid']}<br>{esc(circ['provider'])} · {esc(circ['speed'])}", CID_TAG,
               cx + (236 if n < 2 else 256), 132, 170, 32)

    # Firewall pair
    zone_box(p, lz, "zone-edge", 520, 262, 760, 104, "<b>B01-FW</b> · HA pair (active / passive) · inspects "
             "every zone")
    fw1 = device(p, ld, "B01-FW-01", 560, 290, 250, 58)
    fw2 = device(p, ld, "B01-FW-02", 990, 290, 250, 58)
    link(p, fw1, fw2, cable_by_label("B01-CBL-00005"), "HA · 1G · Cat6", exit=(1, 0.5), entry=(0, 0.5),
         ports=("ha", "ha"), weight=1.4)
    # Internet circuits: each provider hands off to both firewalls.
    lc = p.layer("2 · Links (Po · speed · VLANs)")

    def circuit_edge(circ, src, dst, handoff, label, ex, en, pts, color="#94A3B8"):
        style = (EDGE.replace("strokeColor=#64748B", f"strokeColor={color}").replace("strokeWidth=1.6", "strokeWidth=1.4")
                 + "labelBackgroundColor=#DBEAFE;labelBorderColor=#2563EB;")
        attrs = {"object": "circuits.circuit", "cid": circ["cid"], "status": "active", "x_handoff": handoff,
                 "x_speed": circ["speed"], "x_media": circ["media"], "x_patch_a": "", "x_patch_b": ""}
        attrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in attrs.items()), **attrs,
                 "link": f"{NETBOX}/circuits/circuits/?cid={circ['cid']}", "linkTarget": "_blank"}
        return p.edge(lc, src, dst, style, label, attrs, exit=ex, entry=en, points=pts)

    for n, circ in enumerate(S.CIRCUITS[:2]):
        for m, fw in enumerate((fw1, fw2)):
            port = f"wan{n + 1}"
            same = n == m
            ex = (0.3 if m == 0 else 0.7, 1)
            en = (0.2 + 0.6 * n, 0)
            pts = [] if same else [((560 + n * 470) + 230 * ex[0], 238), (560 + m * 430 + 250 * en[0], 238)]
            eid = circuit_edge(circ, isp[circ["cid"]], fw, f"{'B01-FW-01' if m == 0 else 'B01-FW-02'}:{port}",
                               esc(f"{circ['speed']} · {circ['media']}") if same else "", ex, en, pts)
            p.edge_label(eid, port, 1, 0, PORT_LABEL)

    # The core processor's router: their box in our rack, behind both firewalls on port5.
    zone_box(p, lz, "zone-partner", 1370, 262, 420, 104, "<b>PARTNER</b> · their router, our rack · no login")
    cpr = device(p, ld, "B01-CPR-01", 1400, 290, 250, 58)
    core_circ = S.CIRCUITS[2]
    circuit_edge(core_circ, isp[core_circ["cid"]], cpr, core_circ["handoff"],
                 esc(f"{core_circ['speed']} · {core_circ['media']}"), (0.5, 1), (0.95, 0), [],   # right of the zone title
                 color=CORE_LINK)
    link(p, fw2, cpr, cable_by_label("B01-CBL-00007"), "1G · Cat6", exit=(1, 0.5), entry=(0, 0.5),
         ports=("port5", "ge0/1/1"), weight=1.4, color=CORE_LINK)
    # Under fw2's Po2 drop and back up into the router; the pill sits right of the crossing.
    link(p, fw1, cpr, cable_by_label("B01-CBL-00006"), "1G · Cat6", exit=(0.95, 1), entry=(0.8, 1),
         points=[(797.5, 378), (1600, 378)], ports=("port5", "ge0/1/0"), weight=1.4, color=CORE_LINK)

    # Core stack
    core = stack(p, lz, "B01-CORE", 600, 462, 640, ["B01-CORE-1", "B01-CORE-2"], "zone-mgmt",
                 "CX 6300M ×2 · VSF stack · COMMS-1 R01 / R02")
    link(p, fw1, core, cable_by_label("B01-CBL-00001"), exit=(0.5, 1), entry=(0.2, 0),
         points=[(685, 420), (728, 420)], ports=("x1–x2", "1/1/1 · 2/1/1"), bundle=(728, 448))
    link(p, fw2, core, cable_by_label("B01-CBL-00003"), exit=(0.5, 1), entry=(0.8, 0),
         points=[(1115, 420), (1112, 420)], ports=("x1–x2", "1/1/2 · 2/1/2"), bundle=(1112, 448))

    # Floor 1 (banking hall) access stack, left: it sits in COMMS-1.
    f1 = stack(p, lz, "B01-ACC-F1", 90, 640, 330, ["B01-ACC-F1-1", "B01-ACC-F1-2"], "zone-staff",
               "CX 6200F 48G PoE ×2 · COMMS-1 R02 · banking hall")
    link(p, core, f1, cable_by_label("B01-CBL-00011"), exit=(0, 0.5), entry=(0.5, 0),
         points=[(255, 508)], ports=("1/1/11 · 2/1/11", "1/1/49 · 2/1/49"), bundle=(255, 600))
    # Physical security beside it
    zone_box(p, lz, "zone-security", 530, 630, 460, 120, "<b>SECURITY</b> · cameras record here; no internet")
    nvr = device(p, ld, "B01-NVR-01", 546, 666, 208, 58)
    door = device(p, ld, "B01-DOOR-01", 766, 666, 208, 58)
    link(p, f1, nvr, cable_by_label("B01-CBL-00031"), "NVR · 1G · Cat6", exit=(1, 0.48), entry=(0, 0.5),
         ports=("2/1/45", "eth0"))
    link(p, f1, door, cable_by_label("B01-CBL-00032"), "DOOR · 1G · Cat6", exit=(1, 0.85), entry=(0.5, 1),
         points=[(870, 739)], ports=("2/1/46", "eth0"))

    # Servers, right: nested elbows off the core's right side, so no two links cross.
    zone_box(p, lz, "zone-servers", 1250, 630, 690, 120, "<b>SERVERS</b> · two hosts and the backup NAS")
    hv1 = device(p, ld, "B01-HV-01", 1266, 666, 216, 58)
    hv2 = device(p, ld, "B01-HV-02", 1494, 666, 216, 58)
    nas = device(p, ld, "B01-NAS-01", 1722, 666, 206, 58)
    link(p, core, nas, cable_by_label("B01-CBL-00025"), "NAS · 10G · Cat6A", exit=(1, 0.15), entry=(0.5, 0),
         points=[(1825, 475.5)], ports=("1/1/23", "lan1"))
    link(p, core, hv2, cable_by_label("B01-CBL-00023"), exit=(1, 0.45), entry=(0.5, 0),
         points=[(1602, 502.5)], ports=("1/1/22 · 2/1/22", "nic1–2"), bundle=(1602, 640))
    link(p, core, hv1, cable_by_label("B01-CBL-00021"), exit=(1, 0.75), entry=(0.5, 0),
         points=[(1374, 529.5)], ports=("1/1/21 · 2/1/21", "nic1–2"), bundle=(1374, 640))

    # Management and power, below the servers: down the gap beside them, then up into each card.
    zone_box(p, lz, "zone-mgmt", 1250, 790, 690, 120, "<b>MGMT &amp; POWER</b> · on the core, in the racks")
    ups1 = device(p, ld, "B01-UPS-01", 1266, 826, 216, 58)
    ups2 = device(p, ld, "B01-UPS-02", 1494, 826, 216, 58)
    oob = device(p, ld, "B01-OOB-01", 1722, 826, 206, 58)
    for n, (dev, label, ports, name) in enumerate([(ups1, "B01-CBL-00033", ("1/1/24", "nmc"), "UPS1"),
                                                   (ups2, "B01-CBL-00034", ("2/1/24", "nmc"), "UPS2"),
                                                   (oob, "B01-CBL-00035", ("1/1/20", "net1"), "OOB")]):
        x = 1225 - n * 10
        y = 940 + n * 12
        target = (1374, 1602, 1825)[n]
        link(p, core, dev, cable_by_label(label), f"{name} · 1G · Cat6", exit=((x - 600) / 640, 1), entry=(0.5, 1),
             points=[(x, y), (target, y)], ports=ports)
    note(p, 1250, 984, 690, 30, "Console lines (not cables in NetBox): OOB-01 serial 1–4 to FW-01, FW-02, "
         "CORE-1, CORE-2 · cellular to the MSP. UPS runtime: R01 about 20 min, R02 about 24 min; the generator "
         "transfers at 30 s.")

    # Floor 2 (operations) access stack, straight under the core
    f2 = stack(p, lz, "B01-ACC-F2", 1000, 1046, 330, ["B01-ACC-F2-1", "B01-ACC-F2-2"], "zone-staff",
               "CX 6200F 48G PoE ×2 · IDF-2 R01 · operations")
    link(p, core, f2, cable_by_label("B01-CBL-00013"), exit=(0.78125, 1), entry=(0.3, 0),
         ports=("1/1/12 · 2/1/12", "1/1/49 · 2/1/49"), bundle=(1100, 1034))
    note(p, 440, 1040, 520, 132, "<b>End devices</b><br>APs trunk VLANs 21 and 70 (native 99). Teller recyclers on "
         "VLAN 10, ATMs on 60, the wire PCs on 25, the card printer on 26, cameras on 80, the alarm panel on 81. "
         "Teller and desk PCs and phones are not drawn: the switch port carries the zone. Wire and card VLANs "
         "reach only floor 2's stack; teller and ATM VLANs only floor 1's.", guide=False)

    # Floors: one card per kind of end device, the build counts the rest. Drops leave the stack
    # left to right and drop to nested levels, so none cross.
    for floor, fx, sw, sx, sw_w in ((1, 90, f1, 90, 330), (2, 1090, f2, 1000, 330)):
        names = FLOOR_CARDS[floor]
        p.cell(lz, f"<b>Floor {floor}</b> · {'banking hall' if floor == 1 else 'operations'}: one card per kind "
               "of end device; the build shows how many",
               zone_style("#FFFFFF", "#E2E8F0", "#334155", "bottom", 10), fx, 1222, 18 + 160 * len(names), 220)
        for n, name in enumerate(names):
            d = DEV[name]
            x = fx + 14 + n * 160
            cid = device(p, ld, name, x, 1326, 150, 52, small=True, pill=False, serial=False,
                         label='<b>%name%</b><br>' + sub("%device_type%"))
            c = CABLE_OF[name][0]
            sw_port = c["a"][0].split(":")[1]
            iface = sw_port
            vlan = S.ACCESS_VLAN.get(d["role"])
            text = f"{c['speed']} · {c['media']}" + (f" · {vlan}" if vlan else " · trunk")
            ex_x = sx + 30 + n * 50
            level = 1300 - n * 12
            pts = [(ex_x, level), (x + 75, level)]
            link(p, sw, cid, c, text, exit=((ex_x - sx) / sw_w, 1), entry=(0.5, 0), points=pts,
                 ports=(iface, "eth0"), weight=1.2, color="#94A3B8")

    # Registers and legend, right
    lr = p.layer("6 · Link register")
    link_card = p.cell(lr, "", CARD, 1976, 96, 880, 400)
    p.cell(lr, "<b>Link register</b> — port-channels, members, speed, trunked VLANs", HEADING, 1990, 106, 840, 22)
    rows = []
    for c in BACKBONE:
        a_dev = sorted({e.split(":")[0].replace("B01-", "") for e in c["a"]})
        b_dev = sorted({e.split(":")[0].replace("B01-", "") for e in c["b"]})
        a_ports = " · ".join(e.split(":")[1] for e in c["a"])
        b_ports = " · ".join(e.split(":")[1] for e in c["b"])
        b_name = c["b"][0].split(":")[0]
        name = c["lag"] or LINK_NAME.get(b_name, "")
        speed = c["speed"] + (" LACP" if c["lag"].startswith("Po") else "")
        ids = ", ".join(f"#{S.CABLES.index(c) * 2 + k + 1}" for k in range(len(c["labels"])))
        role = DEV[b_name]["role"]
        carries = (c["vlans"] or ("heartbeat" if c["lag"] == "HA" else
                                  "100 untagged" if role == "provider-router" else
                                  "access " + str(S.ACCESS_VLAN.get(role, ""))))
        rows.append([name, ids, f"{'/'.join(a_dev)} {a_ports}", f"{'/'.join(b_dev)} {b_ports}", speed, c["media"],
                     "connected", carries])
    # CABLE ID and STATUS are drawn here, wide enough for "connected", so the build doesn't squeeze them in.
    table(p, lr, 1990, 134, [("LINK", 46), ("CABLE ID", 60), ("A-SIDE (MEMBERS)", 176), ("B-SIDE (MEMBERS)", 176),
          ("SPEED", 84), ("MEDIA", 66), ("STATUS", 70), ("TRUNKED VLANS", 162)], rows, row_h=22)
    note(p, 1990, 134 + p.table_height + 8, 840, 32, "All trunks: native VLAN 999 (unused) · explicit allowed list · LACP "
         "fast. CPR links are the provider's handoff: no VLANs, no switch. End-device drops are in NetBox.")
    bottom = 134 + p.table_height + 8 + 32 + 14   # the card fits its table, two-line trunk rows included
    resize(p, link_card, bottom - 96)
    la = p.layer("7 · Asset register")
    on_cards = {d["role"] for names in FLOOR_CARDS.values() for d in (DEV[n] for n in names)}
    reg = [d["name"] for d in S.DEVICES if d["role"] not in on_cards]  # end devices are counted on their cards
    top = bottom + 14
    asset_card = p.cell(la, "", CARD, 1976, top, 880, 400)
    p.cell(la, "<b>Asset register</b> — mirrors each device's NetBox record", HEADING, 1990, top + 10, 840, 22)
    rows = []
    for name in reg:
        d = DEV[name]
        role = {"ups": "UPS", "nvr": "NVR"}.get(d["role"], d["role"].replace("-", " ").capitalize())
        rows.append([name, role, d["device_type"], d["serial"],
                     d["primary_ip4"].split("/")[0], d["location"], d["rack"],
                     f"U{d['position']}" if d["position"] else "", d["cf_sw_version"] or "—"])
    # Wide enough that the STATUS and CRIT columns a build adds (from HOSTNAME/ROLE and MODEL/ROOM/SW) leave
    # every cell on one line.
    table(p, la, 1990, top + 36, [("HOSTNAME", 112), ("ROLE", 104), ("MODEL", 166), ("SERIAL", 96), ("MGMT IP", 78),
          ("ROOM", 76), ("RACK/CAB", 58), ("U", 36), ("SW", 114)], rows, row_h=20)
    resize(p, asset_card, 36 + p.table_height + 16)
    legend(p, 1976, top + 36 + p.table_height + 16 + 14, ZONE_CHIPS, flows=False)
    p.title_block(p.layer("Border & title block"), "B01", "Physical — devices, links", f"3 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ 3d wireless
def wireless() -> Page:
    p = Page("wireless", "3d · Wireless — APs and SSIDs", 2400, 960, prefix="f")
    lb, ld = p.layer("Floors"), p.layer("1 · Devices")
    p.layer("Zones")
    p.layer("3 · Mgmt IPs (hide before sharing)")
    p.layer("3b · Serial numbers")
    p.title(lb, f"{S.SITE['code']} · {S.SITE['name']} — Wireless",
            esc("Access points per floor · SSIDs and the zone each one lands in. Staff and guests only: teller, wire, "
                "card and ATM are wired."))
    # A build rewrites this card from the site's wireless_management / wireless_manager fields.
    cloud = icon_card(p, lb, 600, 96, 600, 70, "cloud", "Cloud Wi-Fi management",
                      "Configuration, firmware and guest portal from the vendor's cloud · APs reach it over HTTPS",
                      attrs={"netdiagrams_wireless_mgmt": "1"})
    trunk = ", ".join(str(v) for v in S.AP_VLANS)
    for n, floor in enumerate((1, 2)):
        fx = 24 + n * 760
        p.cell(lb, f"<b>Floor {floor}</b> · ceiling APs on B01-ACC-F{floor}: PoE, trunk {trunk} "
               "(native 99)", zone_style("#FFFFFF", "#E2E8F0", "#334155", "top", 11), fx, 210, 740, 130)
        device(p, ld, f"B01-AP-F{floor}-01", fx + 20, 250, 360, 60, small=True, pill=False,
               label="<b>%name%</b><br>" + sub("%device_type% · one card per floor; the build counts them"))
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
                     f"{sw.replace('B01-', '')} {port}", c["labels"][0]])
    table(p, la, 40, 400, [("NAME", 200), ("MODEL", 140), ("SERIAL", 160), ("MGMT IP", 150), ("LOCATION", 150),
          ("SWITCH PORT", 380), ("CABLE", 300)], rows, row_h=22)
    p.edge(p.layer("2 · Management"), cloud, None, "endArrow=none;html=1;strokeColor=#94A3B8;strokeWidth=1.2;"
           "dashed=1;fontSize=9;fontColor=#475569;labelBackgroundColor=#FFFFFF;" + FONT, "AP management",
           exit=(0.5, 1), tgt_pt=(900, 210))
    lt = p.layer("SSID table")
    ssid_card = p.cell(lt, "", CARD, 1580, 210, 796, 290)
    p.cell(lt, "<b>SSIDs</b> — one per zone, never one for everything", HEADING, 1596, 220, 760, 22)
    rows = [[ssid, str(vlan), S.ZONE[zone][1], sec, notes] for ssid, sec, vlan, zone, notes in S.SSIDS]
    table(p, lt, 1596, 250, [("SSID", 110), ("VLAN", 120), ("ZONE", 80), ("SECURITY", 200), ("NOTES", 250)], rows,
          row_h=30)
    resize(p, ssid_card, 40 + p.table_height + 16)
    # The SSID rules are design prose (a guide): under the AP register, where the page has room.
    note(p, 24, 600, 760, 110, "<b>Rules</b><br>· NB-GUEST: client isolation, captive portal, 10 Mb/s per client, "
         "DNS filter; lands in GUEST only.<br>· No SSID for teller, wire, card or ATM: they are wired, on their own "
         "VLANs.<br>· Rogue AP detection on; management VLAN 99 is never broadcast.")
    legend(p, 1580, 384, ZONE_CHIPS, flows=False)
    p.title_block(p.layer("Border & title block"), "B01", "Wireless — APs, SSIDs", f"3d of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 4 flows
def flows() -> Page:
    p = Page("flows", "4 · Traffic Flows — who talks to whom", 2400, 60 + 96 + 46 * len(S.FLOWS) + 150, prefix="f")
    lb, lf = p.layer("Lanes"), p.layer("Flows")
    p.title(lb, f"{S.SITE['code']} · {S.SITE['name']} — Traffic flows",
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
    p.cell(lf, "<b>Default deny</b> · anything not listed above, between any two zones, is "
           "blocked and logged",
           TEXT.replace("verticalAlign=top", "verticalAlign=middle").replace("#334155", "#991B1B"), xa, y + 6, 1220,
           28)
    p.title_block(p.layer("Border & title block"), "B01", "Traffic flows", f"4 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 5 failover
def failover() -> Page:
    p = Page("failover", "5 · Failover scenarios", 2400, 1040, prefix="f")
    lb = p.layer("Scenarios")
    p.title(lb, f"{S.SITE['code']} · {S.SITE['name']} — Failover",
            esc("What happens at 3 a.m. when one thing breaks: what fails, what takes over, and what people notice."))
    scenarios = [
        ("isp", "ISP-A goes down", "Fiber cut or provider outage on B01-ISP-A-01.",
         "The firewall pair moves internet traffic to ISP-B (cable 500/50) within about 30 seconds: FedLine, SaaS, "
         "the VPN and the B02 tunnel rebuild over ISP-B. Teller traffic never used the internet.",
         "Calls in progress drop and redial. Wires carry on once the FedLine client reconnects."),
        ("firewall", "B01-FW-01 fails", "Power supply, disk or a bad update on the active firewall.",
         "B01-FW-02 takes over the gateway addresses (.1 on every VLAN), both internet lines and its own port5 "
         "to the core processor's router; sessions carry on.",
         "A few seconds of pause at the teller line. VPN users may need to reconnect."),
        ("core-switch", "A core stack member fails", "B01-CORE-1 or B01-CORE-2 dies or is rebooted.",
         "Every port-channel (Po1, Po2, Po11, Po12, Po21, Po22) keeps its link on the other member at half "
         "speed.", "Nothing, apart from the NAS link and the management drops on that member."),
        ("provider-router", "The core processor's circuit drops (finding)",
         "Fiber cut, provider outage or a fault in B01-CPR-01 on B01-CORE-01, the only path to the core.",
         "Nothing takes over: there is no second path. Tellers at B01 and every branch switch to the core "
         "system's offline mode (store-and-forward) and operations calls the core processor. ATMs and card "
         "issuing stop until the circuit is back.",
         "Deliberate finding, accepted until a second path is bought: offline limits at the teller line, ATMs out "
         "of service, no instant-issue cards. Wires carry on over FedLine."),
        ("firewall", "The B02 branch's broadband drops", "Provider outage on the Elm Street branch's line.",
         "B02-FW-01 moves its tunnel to B01 onto the LTE backup (B02-LTE-01) within about a minute.",
         "Nothing at the teller line; the lobby guest Wi-Fi is slower until broadband is back."),
        ("power", "Power cut", "The main office loses mains power.",
         "Both UPSs carry COMMS-1 (about 20 and 24 minutes at today's load) until the generator takes the "
         "building at 30 seconds. The alarm panel has its own battery and cellular path.",
         "Nothing, if the generator starts. If it doesn't, shut down cleanly before the UPSs run out."),
    ]
    for n, (icon, title, what, takes, notice) in enumerate(scenarios):
        y = 100 + n * 136
        finding = "(finding)" in title
        p.cell(lb, "", CARD.replace("strokeColor=#E2E8F0", "strokeColor=#FCA5A5") if finding else CARD, 24, y, 2350,
               124)
        icon_card(p, lb, 40, y + 14, 460, 96, icon, title, what, 34, 14)
        for k, (head, text, color) in enumerate([("WHAT TAKES OVER", takes, "#15803D"),
                                                 ("WHAT PEOPLE NOTICE", notice, "#B45309")]):
            x = 540 + k * 900
            p.cell(lb, f"<b>{head}</b>", SMALL.replace("#64748B", color), x, y + 18, 860, 20)
            p.cell(lb, esc(text), TEXT.replace("fontSize=10", "fontSize=12"), x, y + 42, 860, 70)
    p.title_block(p.layer("Border & title block"), "B01", "Failover scenarios", f"5 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 6 branches, processors and cloud
def multisite() -> Page:
    p = Page("multisite", "6 · Branches, processors and cloud", 2400, 1230, prefix="f")
    lb, lc, ll = p.layer("Sites"), p.layer("Cards"), p.layer("Tunnels")
    p.title(lb, "Ninebark Community Bank — Branches, processors and cloud",
            esc("The main office, the branches, the core processor, the card and ATM processor, the Federal Reserve, "
            "the cloud and the providers. Every branch tunnel and the core processor's circuit end on the B01 "
            "firewall pair."))
    inet = icon_card(p, lc, 860, 100, 520, 80, "globe", "Internet", "Each site's own lines · SaaS reached directly "
                     "from every site", 30, 13)
    hq = p.cell(lc, "<b>B01 · Ninebark main office</b> · 10.30.0.0/16<br>"
                + sub("Firewall HA pair · core stack · 2 floors · 10 APs · servers and backup · the core processor's "
                      "router"),
                zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), 760, 420, 720, 180)
    for n, (icon, title, text) in enumerate([("firewall", "B01-FW HA pair", "Ends every tunnel"),
                                             ("provider-router", "B01-CPR-01", "The core processor's router"),
                                             ("backup", "Backup NAS", "Copies to the vault nightly")]):
        icon_card(p, lc, 780 + n * 232, 490, 218, 80, icon, title, text, 24, 11)
    br = p.cell(lc, "<b>B02 · Elm Street branch</b> · 10.32.0.0/16<br>"
                + sub("One firewall with LTE backup · one switch · two APs · an ATM"),
                zone_style("#F4FAF5", "#B4DDBF", "#16A34A", "top", 12), 100, 690, 560, 160)
    for n, (icon, title, text) in enumerate([("firewall", "B02-FW-01", "Broadband + LTE (B02-LTE-01)"),
                                             ("access-switch", "B02-ACC-1", "24-port PoE")]):
        icon_card(p, lc, 120 + n * 264, 750, 250, 80, icon, title, text, 24, 11)
    more = icon_card(p, lc, 100, 880, 560, 80, "bank", "4 more branches like B02",
                     "B03–B06 · same VLANs, same design · IPsec to B01", 30, 13)
    proc = p.cell(lc, "<b>The core processor's network</b> · private circuit B01-CORE-01 · 100M<br>"
                  + sub("Hosted by the providers, reached only through B01-CPR-01"),
                  zone_style("#F5F3FF", "#C4B5FD", "#6D28D9", "top", 12), 1100, 690, 600, 160)
    for n, (icon, title, text) in enumerate([("server", "Core processor", "Core banking, internet banking"),
                                             ("atm", "Card and ATM processor", "ATMs and card issuing")]):
        icon_card(p, lc, 1116 + n * 292, 750, 276, 80, icon, title, text, 24, 11)
    vault = icon_card(p, lc, 1760, 690, 380, 80, "backup", "Cloud backup vault", "Immutable copies · own admin "
                      "login", 30, 13)
    saas = icon_card(p, lc, 1580, 240, 560, 80, "cloud", "SaaS", "Mail, files, meetings, the phone service", 30, 13)
    fed = icon_card(p, lc, 1580, 420, 560, 80, "bank", "Federal Reserve (FedLine)",
                    "Wires and ACH · from the two wire workstations only", 30, 13)
    msp = icon_card(p, lc, 100, 240, 560, 80, "wrench", "MSP and MSSP",
                    "VPN · MFA · booked window · logs out over TLS", 30, 13)
    alarm = icon_card(p, lc, 100, 420, 560, 80, "alarm-panel", "Alarm monitoring center",
                      "IP from each alarm panel, cellular backup", 30, 13)
    tunnel = ("html=1;strokeColor=#2563EB;strokeWidth=2;dashed=1;dashPattern=8 4;endArrow=none;fontSize=10;"
              "fontColor=#1E3A8A;labelBackgroundColor=#FFFFFF;" + FONT)
    plain_line = "html=1;strokeColor=#94A3B8;strokeWidth=1.4;endArrow=none;fontSize=10;fontColor=#475569;" \
                 "labelBackgroundColor=#FFFFFF;" + FONT
    private = plain_line.replace("#94A3B8", CORE_LINK).replace("strokeWidth=1.4", "strokeWidth=2.5")
    p.edge(ll, br, hq, tunnel, "IPsec · F23", exit=(1, 0.3), entry=(0.08, 1), points=[(817.6, 738)])
    p.edge(ll, more, hq, tunnel, "IPsec · F23", exit=(1, 0.5), entry=(0.25, 1), points=[(940, 920)])
    p.edge(ll, proc, hq, private, "B01-CORE-01 · 100M", exit=((1264 - 1100) / 600, 0), entry=(0.7, 1))
    p.edge(ll, vault, hq, plain_line, "HTTPS · F14", exit=(0.5, 0), entry=(1, 0.78), points=[(1950, 560.4)])
    p.edge(ll, msp, hq, tunnel.replace("#2563EB", "#EA580C"), "VPN + MFA · F21", exit=(1, 0.5), entry=(0.3, 0),
           points=[(976, 280)])
    p.edge(ll, alarm, hq, plain_line.replace("#94A3B8", "#DB2777"), "Alarm signals · F19", exit=(1, 0.5),
           entry=(0, 0.2222))
    p.edge(ll, inet, hq, plain_line, "ISP-A + ISP-B", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(ll, saas, hq, plain_line, "HTTPS", exit=(0, 0.5), entry=(1, 0.12), points=[(1520, 280), (1520, 441.6)])
    p.edge(ll, fed, hq, plain_line.replace("#94A3B8", "#B91C1C"), "FedLine VPN · F06", exit=(0, 0.7875),
           entry=(1, 0.35))
    lt = p.layer("Site table")
    p.cell(lt, "<b>Sites</b>", HEADING, 100, 990, 2040, 22)
    table(p, lt, 100, 1016, [("CODE", 90), ("SITE", 240), ("PREFIX", 160), ("INTERNET", 420), ("BACKUP", 380),
          ("LINK TO B01", 750)], [
        [("B01", f"{NETBOX}/dcim/sites/?slug=b01"), "Ninebark main office", "10.30.0.0/16",
         "ISP-A DIA 1G fiber · ISP-B cable 500/50", "Second ISP, firewall HA pair",
         "— (the core processor's circuit lands here)"],
        [("B02", f"{NETBOX}/dcim/sites/?slug=b02"), "Elm Street branch", "10.32.0.0/16",
         "Provider C broadband", "LTE on B02-LTE-01", "IPsec to the B01 firewall pair"],
        ["B03–B06", "4 more branches", "one /16 each, as B02", "Local broadband", "LTE",
         "IPsec to the B01 firewall pair"]], row_h=26)
    p.title_block(p.layer("Border & title block"), "All", "Branches, processors, cloud", f"6 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ 7 flow register
ZONE_ORDER = ["zone-internet", "zone-partner", "zone-teller", "zone-staff", "zone-wire", "zone-card",
              "zone-servers", "zone-voice", "zone-atm", "zone-guest", "zone-security", "zone-mgmt"]
MATRIX = {  # (from, to): [(verdict, flows)]
    ("zone-teller", "zone-partner"): [("allow", "F01")], ("zone-staff", "zone-partner"): [("allow", "F02")],
    ("zone-teller", "zone-internet"): [("deny", "F03")], ("zone-staff", "zone-internet"): [("allow", "F04")],
    ("zone-teller", "zone-servers"): [("allow", "F05")], ("zone-staff", "zone-servers"): [("allow", "F05")],
    ("zone-wire", "zone-internet"): [("cond", "F06 F28")], ("zone-wire", "zone-servers"): [("cond", "F28")], ("zone-wire", "zone-partner"): [("allow", "F07")],
    ("zone-staff", "zone-wire"): [("deny", "F08")], ("zone-teller", "zone-wire"): [("deny", "F08")],
    ("zone-card", "zone-partner"): [("cond", "F09")], ("zone-card", "zone-servers"): [("cond", "F28")],
    ("zone-card", "zone-internet"): [("cond", "F28")], ("zone-staff", "zone-card"): [("deny", "F10")],
    ("zone-atm", "zone-partner"): [("allow", "F11")], ("zone-internet", "zone-atm"): [("cond", "F12")],
    ("zone-servers", "zone-partner"): [("cond", "F13")],
    ("zone-servers", "zone-internet"): [("allow", "F14"), ("cond", "F27")],
    ("zone-voice", "zone-internet"): [("allow", "F15")], ("zone-guest", "zone-internet"): [("allow", "F16")],
    ("zone-guest", "zone-staff"): [("deny", "F17")], ("zone-guest", "zone-teller"): [("deny", "F17")],
    ("zone-security", "zone-internet"): [("cond", "F19"), ("deny", "F20")],
    ("zone-internet", "zone-mgmt"): [("cond", "F21")], ("zone-internet", "zone-servers"): [("cond", "F22")],
    ("zone-staff", "zone-mgmt"): [("deny", "F24")], ("zone-teller", "zone-mgmt"): [("deny", "F24")],
    ("zone-mgmt", "zone-internet"): [("cond", "F25 F27")],
}


def register() -> Page:
    p = Page("register", "7 · Flow register & standards", 2400, 1500, prefix="f")
    lf, lm, ls = p.layer("Flow register"), p.layer("Zone matrix"), p.layer("Standards")
    p.title(lf, f"{S.SITE['code']} · {S.SITE['name']} — Flow register and standards",
            esc("The segmentation in writing: every permitted conversation, its conditions and owner, then default "
            "deny. The zone matrix is the same rules as a grid. Naming and drawing standards at the right."))
    flows_card = p.cell(lf, "", CARD, 24, 92, 1500, 22 + 26 * (len(S.FLOWS) + 2) + 30)
    p.cell(lf, "<b>Flow register</b>", HEADING, 40, 102, 1460, 22)
    look = {"Allow": "#15803D", "Conditional": "#B45309", "Deny": "#B91C1C"}
    rows = [[fid, src, dst, what, f'<font color="{look[v]}"><b>{v}</b></font>', cond, owner]
            for fid, src, dst, what, v, cond, owner in S.FLOWS]
    rows.append(["—", "Any", "Any", "Everything not listed above", '<font color="#B91C1C"><b>Deny</b></font>',
                 "Default deny, logged", "IT"])
    table(p, lf, 40, 128, [("ID", 44), ("FROM", 210), ("TO", 200), ("WHAT", 330), ("VERDICT", 90),
          ("CONDITIONS", 360), ("OWNER", 230)], rows, row_h=26)
    flows_card_h = 36 + p.table_height + 16
    resize(p, flows_card, flows_card_h)
    my = 92 + flows_card_h + 20
    n = len(ZONE_ORDER)
    matrix_card = p.cell(lm, "", CARD, 24, my, 1500, 60 + 30 * (n + 1))
    p.cell(lm, "<b>Zone matrix</b> — rows start the conversation, columns answer; blank is "
           "default deny", HEADING, 40, my + 10, 1460, 22)
    cols = [("FROM \\ TO", 128)] + [(S.ZONE[z][1], 110) for z in ZONE_ORDER]
    cell = {"allow": '<font color="#15803D"><b>allow</b></font>', "cond": '<font color="#B45309"><b>cond.</b></font>',
            "deny": '<font color="#B91C1C"><b>deny</b></font>'}
    rows = []
    for a in ZONE_ORDER:
        row = [S.ZONE[a][1]]
        for b in ZONE_ORDER:
            if a == b:
                row.append('<font color="#94A3B8">inside zone</font>')
            elif (a, b) in MATRIX:
                row.append(" · ".join(f"{cell[v]} {f}" for v, f in MATRIX[(a, b)]))
            else:
                row.append("")
        rows.append(row)
    table(p, lm, 40, my + 40, cols, rows, row_h=30, key=KEY_CELL)
    resize(p, matrix_card, 40 + p.table_height + 16)
    p.height = int(my + 40 + p.table_height + 16 + 110)   # the page ends under the matrix, title block below it
    p.model.set("pageHeight", str(p.height))
    sx = 1560
    std_card = p.cell(ls, "", CARD, sx, 92, 816, 500)
    p.cell(ls, "<b>Naming and drawing standards</b>", HEADING, sx + 16, 102, 780, 22)
    table(p, ls, sx + 16, 128, [("ITEM", 170), ("STANDARD", 610)], [
          ["Site code", "B + two digits: B01 main office, B02 Elm Street, B03–B06 the other branches"],
          ["Device", "SITE-ROLE-NN: B01-FW-01, B01-ACC-F1-1 (floor, member)"],
          ["Stack", "SITE-ROLE-FLOOR: B01-ACC-F1; members -1, -2"],
          ["Cable label", "SITE-CBL-nnnnn on both ends: B01-CBL-00011; drops from 00101"],
          ["Zone tag", "zone-&lt;name&gt; on every device, VLAN and prefix"],
          ["VLAN", "Same number for the same zone at every site: 10 teller, 20s staff, 25 wire, 26 card, 30 voice, "
                   "40s servers, 60 ATM, 70 guest, 80s security, 99 management, 100 core link"],
          ["Subnet", "10.&lt;site&gt;.&lt;vlan&gt;.0/24: 10.30 main office, 10.32 Elm Street (wire, card, ATM "
                     "smaller; guest from 172.16)"],
          ["Gateway", ".1 on the firewall pair, for every VLAN"],
          ["Provider-owned", "Recorded, labeled and drawn, never logged into: B01-CPR-01"],
          ["Link pill", "Po · speed · media; port tags at each end"],
          ["Hide before sharing", "Layers 3 (mgmt IPs) and 4 (circuit IDs)"],
          ["Change", "Edit NetBox, then rebuild; never fix the drawing alone"]], row_h=30)
    resize(p, std_card, 36 + p.table_height + 16)
    p.title_block(p.layer("Border & title block"), "B01", "Flow register and standards", f"7 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ main
def build() -> ET.Element:
    return mxfile((overview(), logical(), physical(), wireless(), flows(), failover(), multisite(), register()),
                  "netdiagrams bank template")


def main() -> None:
    tree = build()
    ET.indent(tree, space=" ")
    OUT.write_text(ET.tostring(tree, encoding="unicode") + "\n", "utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
