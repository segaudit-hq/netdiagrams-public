"""Generate src/netdiagrams/data/O01-Office-Template.drawio, the office standard.

Eight sheets drawn for the fictional Alder & Finch HQ (site O01): overview,
logical, physical, wireless, traffic flows, failover, branches and cloud, and
the flow register. Every fact comes from scripts/office_template/site.py, the
same source scripts/make_office_sample.py turns into the sample NetBox export,
so `netdiagrams build --input sample-office.json` reproduces
the template.

    python scripts/make_office_template.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from office_template import site as S  # noqa: E402
from drawkit import (  # noqa: E402
    BAND, EDGE, FONT, MONO, NETBOX, NOTE, POINTS, PORT, RACK_PILL, SUBTITLE, TCELL, TITLE, Page, _svg, esc, mxfile, sub,
    zone_style)
from netdiagrams.graph import font_size, row_height  # noqa: E402  (the measure the build and the tests use)

# ------------------------------------------------------------------ the office look, on the S01 kit
HEADING = "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=12;fontColor=#334155;fontStyle=1;spacing=2;" + FONT
TEXT = "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=10;fontColor=#334155;spacing=2;" + FONT
SMALL = "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=9;fontColor=#64748B;spacing=2;" + FONT
CARD = "rounded=1;absoluteArcSize=1;arcSize=24;fillColor=#FFFFFF;strokeColor=#E2E8F0;shadow=1;html=1;whiteSpace=wrap;" + FONT
IP_TAG = ("text;html=1;fontSize=9;fontColor=#475569;fillColor=#FFFFFF;fillOpacity=70;strokeColor=none;align=left;"
          "verticalAlign=middle;spacingLeft=2;spacing=0;" + FONT)
SN_TAG = "text;html=1;fontSize=9;fontColor=#64748B;align=right;verticalAlign=middle;spacing=0;spacingLeft=2;" + MONO
CID_TAG = "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=9;fontColor=#64748B;spacing=2;" + FONT
PORT_LABEL = PORT.replace("fontSize=7;", "fontSize=8;")
BUNDLE = "ellipse;fillColor=none;strokeColor=#64748B;strokeWidth=1.2;html=1;" + FONT
BODY_CELL = TCELL + "fontSize=10;fontColor=#334155;"
KEY_CELL = TCELL + "fontSize=10;fontColor=#0F172A;fontStyle=1;"


def group_style(fill: str, stroke: str, font: str, stack: bool = False) -> str:
    style = (f"rounded=1;absoluteArcSize=1;arcSize=24;fillColor={fill};strokeColor={stroke};strokeWidth=1;"
             f"verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontSize=10;fontStyle=1;fontColor={font};"
             "html=1;whiteSpace=wrap;container=1;collapsible=0;")
    if stack:
        style += ("childLayout=stackLayout;horizontalStack=0;resizeParent=1;resizeParentMax=0;stackSpacing=4;"
                  "marginTop=34;marginLeft=10;marginRight=10;marginBottom=4;")
    return style + FONT


def table(p: Page, parent: str, x, y, cols: list[tuple[str, float]], rows: list[list], row_h: float = 22,
          head_h: float | None = None, key: str | None = None, **kw) -> str:
    """A kit table whose body rows grow when a cell's text wraps; ``p.table_height`` is the height drawn."""
    text = lambda v: v[0] if isinstance(v, tuple) else str(v)
    heights = [head_h or row_h] + [row_height([(text(v), w - 4) for (_, w), v in zip(cols, values)],
                                              font_size(BODY_CELL), row_h) for values in rows]
    return p.table(parent, x, y, cols, rows, heights=heights,
                   body=lambda c, link: key if key and c == 0 else BODY_CELL, **kw)


# ------------------------------------------------------------------ icons
def _line(points: str, color: str, width: float = 1.7) -> str:
    return (f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{width}" '
            'stroke-linecap="round" stroke-linejoin="round"/>')


def _rect(x, y, w, h, color, rx=2, width=1.7, fill="none") -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{color}" stroke-width="{width}"/>'


def _circle(cx, cy, r, color, fill="none", width=1.7) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{color}" stroke-width="{width}"/>'


SLATE, GREY, BLUE, TEAL, GREEN, VIOLET, PINK, CYAN, ORANGE, SKY = (
    "#334155", "#475569", "#2563EB", "#0D9488", "#16A34A", "#7C3AED", "#DB2777", "#0891B2", "#D97706", "#0284C7")

ICONS = {
    "firewall": _svg("#E2E8F0", _rect(7, 8, 18, 16, SLATE) + _line("7,13.3 25,13.3", SLATE) + _line("7,18.6 25,18.6", SLATE)
                     + _line("13,8 13,13.3", SLATE) + _line("19,8 19,13.3", SLATE) + _line("16,13.3 16,18.6", SLATE)
                     + _line("11,18.6 11,24", SLATE) + _line("21,18.6 21,24", SLATE)),
    "core-switch": _svg("#E3EBFC", _rect(6, 9, 20, 14, BLUE, rx=3) + _line("10,13.5 22,13.5", BLUE) + _line("19.5,11.5 22,13.5 19.5,15.5", BLUE)
                        + _line("22,18.5 10,18.5", BLUE) + _line("12.5,16.5 10,18.5 12.5,20.5", BLUE)),
    "access-switch": _svg("#E3EBFC", _line("8,11 24,11", BLUE) + _line("21.77,12.69 24,11 21.77,9.31", BLUE) + _line("24,16 8,16", BLUE)
                          + _line("10.23,14.31 8,16 10.23,17.69", BLUE) + _line("8,21 24,21", BLUE) + _line("21.77,22.69 24,21 21.77,19.31", BLUE)),
    "access-point": _svg("#E0F1F0", _rect(7, 19, 18, 6, TEAL, rx=3) + f'<circle cx="16" cy="22" r="1.1" fill="{TEAL}"/>'
                         + _line("19.45,14.11 18.25,13.1 16,12.5 13.75,13.1 12.55,14.11", TEAL)
                         + _line("22.51,11.54 20.25,9.64 16,8.5 11.75,9.64 9.49,11.54", TEAL)),
    "hypervisor": _svg("#E7E9EC", _rect(8, 8, 7, 7, GREY, rx=1.5) + _rect(17, 8, 7, 7, GREY, rx=1.5) + _rect(8, 17, 7, 7, GREY, rx=1.5)
                       + _rect(17, 17, 7, 7, GREY, rx=1.5)),
    "storage": _svg("#E7E9EC", _rect(8, 7, 16, 18, GREY, rx=2.5) + _line("8,13 24,13", GREY) + _line("8,19 24,19", GREY)
                    + f'<circle cx="20.5" cy="10" r="1" fill="{GREY}"/><circle cx="20.5" cy="16" r="1" fill="{GREY}"/>'
                      f'<circle cx="20.5" cy="22" r="1" fill="{GREY}"/>'),
    "server": _svg("#E7E9EC", _rect(9, 7, 14, 7.5, GREY) + _rect(9, 17.5, 14, 7.5, GREY)
                   + f'<circle cx="12.5" cy="10.75" r="1.1" fill="{GREY}"/><circle cx="12.5" cy="21.25" r="1.1" fill="{GREY}"/>'),
    "ups": _svg("#E0F2F6", _rect(9, 6, 14, 20, CYAN, rx=2.5) + _line("17.5,9.5 13.5,16 18.5,16 14.5,22.5", CYAN)),
    "console-server": _svg("#E0F2F6", _rect(6, 10, 20, 12, CYAN, rx=2.5) + _line("10,14 12.5,16 10,18", CYAN) + _line("14.5,18 18,18", CYAN)
                           + _line("21,10 21,6.5", CYAN, 1.4) + f'<circle cx="21" cy="6" r="1.2" fill="{CYAN}"/>'),
    "printer": _svg("#E3F4E8", _rect(10, 6.5, 12, 6, GREEN, rx=1) + _rect(6.5, 12.5, 19, 9, GREEN, rx=2.5) + _rect(10, 18.5, 12, 7, GREEN, rx=1, fill="#E3F4E8")
                    + f'<circle cx="22" cy="15.5" r="0.9" fill="{GREEN}"/>'),
    "nvr": _svg("#FBE4EF", _rect(6, 10, 20, 12, PINK, rx=2.5) + _circle(12, 16, 2.6, PINK) + _line("17,14 22,14", PINK) + _line("17,18 22,18", PINK)),
    "camera": _svg("#FBE4EF", _rect(7, 10, 13, 9, PINK, rx=2) + _line("20,12.5 25,10 25,19 20,16.5", PINK) + _line("12,19 10.5,24", PINK)
                   + _line("8,24 13,24", PINK)),
    "door-controller": _svg("#FBE4EF", _rect(9, 6, 14, 20, PINK, rx=2) + _circle(16, 13, 2.6, PINK) + _line("16,15.6 16,20", PINK)),
    "room-system": _svg("#EFE7FD", _rect(6, 8, 20, 13, VIOLET, rx=2) + _line("16,21 16,24.5", VIOLET) + _line("11,24.5 21,24.5", VIOLET)
                        + _circle(16, 14.5, 2.4, VIOLET)),
    "phone": _svg("#E0F0F9", _rect(7, 13, 18, 11, SKY, rx=2.5) + _line("10,13 10,9 22,9 22,13", SKY) + _line("12,17.5 20,17.5", SKY)
                  + _line("12,20.5 20,20.5", SKY)),
    "laptop": _svg("#EBEDF0", _rect(7, 8, 18, 12, "#64748B") + _line("16,20 16,24", "#64748B") + _line("12,24.5 20,24.5", "#64748B")),
    "cloud": _svg("#EBEDF0", _line("11.5,14 9.25,14.6 7.6,16.25 7,18.5 7.6,20.75 9.25,22.4 11.5,23", "#64748B")
                  + _line("21.42,13.54 20.21,10.96 18,9.4 16,9 14,9.4 11.79,10.96 10.58,13.54", "#64748B")
                  + _line("21,23 23.25,22.4 24.9,20.75 25.5,18.5 24.9,16.25 23.25,14.6 21,14", "#64748B") + _line("11.5,23 21,23", "#64748B")),
    "globe": _svg("#EBEDF0", _circle(16, 16, 9, "#64748B", width=1.5) + _line("7,16 25,16", "#64748B", 1.3)
                  + _line("16,7 19.2,9.6 20.5,16 19.2,22.4 16,25", "#64748B", 1.3) + _line("16,7 12.8,9.6 11.5,16 12.8,22.4 16,25", "#64748B", 1.3)),
    "user": _svg("#F1E4FC", _circle(16, 12, 4, "#9333EA") + _line("23.5,23.3 21.1,19.9 18.7,18.5 16,18 13.3,18.5 10.9,19.9 8.5,23.3", "#9333EA")),
    "users": _svg("#E3EBFC", _circle(13, 12, 3.5, BLUE) + _line("19.5,22.5 17.6,19.2 13,17.5 8.4,19.2 6.5,22.5", BLUE)
                  + _circle(21, 11, 2.8, BLUE, width=1.4) + _line("25.5,20 23.8,17.4 20.5,16.4", BLUE, 1.4)),
    "guest": _svg("#FCEFE0", _circle(16, 12, 4, ORANGE) + _line("23.5,23.3 21.1,19.9 18.7,18.5 16,18 13.3,18.5 10.9,19.9 8.5,23.3", ORANGE)
                  + _line("21.5,7.5 24.5,7.5", ORANGE, 1.4) + _line("23,6 23,9", ORANGE, 1.4)),
    "building": _svg("#FBE4EF", _rect(9, 7, 14, 18, PINK, rx=1.5) + _line("12.5,11 13.5,11", PINK) + _line("18.5,11 19.5,11", PINK)
                     + _line("12.5,15 13.5,15", PINK) + _line("18.5,15 19.5,15", PINK) + _line("14.5,25 14.5,20.5 17.5,20.5 17.5,25", PINK)),
    "wrench": _svg("#E0F2F6", _line("21.5,7.5 18.5,10.5 18.5,13.5 21.5,13.5 24.5,10.5", CYAN) + _line("18.5,13.5 9,23", CYAN, 2.2)),
    "lock": _svg("#E2E8F0", _rect(9, 14, 14, 11, SLATE, rx=2.5) + _line("12,14 12,11 13.2,8.6 16,7.5 18.8,8.6 20,11 20,14", SLATE)
                 + f'<circle cx="16" cy="19.5" r="1.4" fill="{SLATE}"/>'),
    "shield": _svg("#E2E8F0", _line("16,6.5 24,9.5 24,15 22.5,20 16,25.5 9.5,20 8,15 8,9.5 16,6.5", SLATE)
                   + _line("12.5,16 15,18.5 19.5,13", SLATE)),
    "backup": _svg("#E3F4E8", _line("22.5,12 20.6,9.4 17.6,8 14.4,8.1 11.6,9.6 9.7,12.2 9.1,15.3", GREEN) + _line("22.8,8.3 22.5,12 18.9,11.5", GREEN)
                   + _line("9.5,20 11.4,22.6 14.4,24 17.6,23.9 20.4,22.4 22.3,19.8 22.9,16.7", GREEN) + _line("9.2,23.7 9.5,20 13.1,20.5", GREEN)),
    "power": _svg("#E0F2F6", _line("17.5,6.5 11,17 16.5,17 14.5,25.5 21,15 15.5,15 17.5,6.5", CYAN)),
    "isp": _svg("#EBEDF0", _circle(16, 16, 9, "#64748B", width=1.5) + _line("7,16 25,16", "#64748B", 1.3)
                + _line("16,7 19.2,9.6 20.5,16 19.2,22.4 16,25", "#64748B", 1.3) + _line("16,7 12.8,9.6 11.5,16 12.8,22.4 16,25", "#64748B", 1.3)),
}
ICON_FOR_ROLE = {"firewall": "firewall", "core-switch": "core-switch", "access-switch": "access-switch",
                 "access-point": "access-point", "hypervisor": "hypervisor", "storage": "storage", "server": "server",
                 "ups": "ups", "console-server": "console-server", "printer": "printer", "nvr": "nvr", "camera": "camera",
                 "door-controller": "door-controller", "room-system": "room-system"}


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
                ("hypervisor", "Virtualization host"), ("storage", "Storage / NAS"), ("ups", "UPS"),
                ("console-server", "Out-of-band console"), ("printer", "Printer / MFP"), ("nvr", "Video recorder"),
                ("camera", "Camera"), ("door-controller", "Door controller"), ("room-system", "Meeting-room system"),
                ("cloud", "Cloud / SaaS")]


def legend(p: Page, x: float, y: float, zones: list[tuple[str, str, str, str]], flows: bool = True) -> float:
    """The office legend: icons, line meanings and the zone colors. Returns its height."""
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
OUT = DATA / "O01-Office-Template.drawio"
DATE = "2026-10-15"
PROJECT = "Office network standard"
SHEETS = 8

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
    p = Page("overview", "1 · Overview — for management", 2000, 990, prefix="o")
    lay = p.layer("Overview")
    p.cell(lay, "How the office network is protected", TITLE, 24, 18, 1000, 32)
    p.cell(lay, "Management overview: no technical detail. Each office and branch follows the same "
           "design.", SUBTITLE, 24, 52, 1000, 22)
    x, w = 170, 1010
    rows = [  # y, side label, color
        (100, "Outside", "#64748B"), (305, "Staff &amp; services", "#2563EB"), (531, "Shared spaces", "#7C3AED"),
        (767, "Building &amp; management", "#DB2777")]
    for y, text, color in rows:
        p.cell(lay, f"<b>{text}</b>", "text;html=1;align=right;verticalAlign=middle;fontSize=10;"
               f"fontColor={color};whiteSpace=wrap;{FONT}", 40, y, 120, 60)
    outside = icon_card(p, lay, x, 92, w, 76, "cloud", "Internet, SaaS and the cloud",
                        "Email, files and meetings in SaaS · the cloud server network · people working from home · "
                        "the managed service provider (MSP)")
    gate1 = gate_bar(p, lay, x, 214, w, "<b>Security gate</b> · the firewall: everything between the internet and the office "
                     "passes through it")
    staff = p.cell(lay, "<b>Staff and services</b> · the people and the systems they use every day",
                   zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), x, 270, w, 130)
    for n, (icon, title, text) in enumerate([
            ("laptop", "Staff laptops", "Wired desks and staff Wi-Fi"), ("phone", "Phones", "Desk and room phones"),
            ("printer", "Printers", "Print and scan"), ("server", "Servers &amp; backup", "Files, accounts, backup")]):
        icon_card(p, lay, x + 16 + n * 248, 306, 232, 76, icon, title.replace("&amp;", "&"), text, 24, 11)
    gate2 = gate_bar(p, lay, x, 430, w, "<b>Same security gate</b> · between every group inside the office: "
                     "staff, phones, printers, servers, meeting rooms, guests and building systems")
    shared = p.cell(lay, "<b>Shared spaces</b> · used by everyone, trusted by no one",
                    zone_style("#F8F5FE", "#D1BAF9", "#7C3AED", "top", 12), x, 486, w, 150)
    meet = icon_card(p, lay, x + 16, 522, 480, 92, "room-system", "Meeting rooms",
                     "Room screens and cameras join cloud meetings; staff can cast to them")
    guest = icon_card(p, lay, x + 514, 522, 480, 92, "guest", "Guest Wi-Fi",
                      "Visitors get the internet and nothing else; they can't see each other")
    gate3 = gate_bar(p, lay, x, 666, w, "<b>Same security gate</b> · building systems and network management have "
                     "their own doors, opened only for the people who need them")
    build = p.cell(lay, "<b>Building and management</b> · the systems that keep the office running",
                   zone_style("#FDF4F9", "#F3B8D6", "#DB2777", "top", 12), x, 722, w, 150)
    icon_card(p, lay, x + 16, 758, 480, 92, "camera", "Cameras and door access",
              "Record to a box in the comms room; never talk to the internet")
    mgmt = icon_card(p, lay, x + 514, 758, 480, 92, "wrench", "Network management",
                     "Firewalls, switches, Wi-Fi and power; reached only by IT and the MSP")
    arrows = p.layer("Arrows")
    # Home workers and the MSP: in through the gate, with MFA.
    p.edge(arrows, outside, mgmt, "endArrow=block;endFill=1;html=1;strokeColor=#7C3AED;strokeWidth=1.6;dashed=1;"
           "fontSize=9;fontColor=#4C1D95;labelBackgroundColor=#FFFFFF;" + FONT, "", exit=(1, 0.7), entry=(1, 0.5),
           points=[(1206, 145.2), (1206, 804)])
    p.cell(arrows, "<b>Home workers &amp; the MSP</b>: in through the gate, with MFA ↓",
           "text;html=1;align=right;verticalAlign=middle;fontSize=9;fontColor=#6D28D9;" + FONT, 900, 216, 270, 26)
    # Guests: no direct path to staff.
    p.edge(arrows, guest, staff, "endArrow=none;html=1;strokeColor=#DC2626;strokeWidth=1.6;dashed=1;fontSize=9;"
           "fontColor=#991B1B;labelBackgroundColor=#FFFFFF;" + FONT, "No direct path<br>from guests to staff",
           exit=(0.25, 0), entry=(0.6277, 1))
    p.cell(arrows, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
           "fontSize=10;fontStyle=1;" + FONT, 794, 405, 20, 20)
    # What this means for the business: Alder & Finch's promises, on their own layer so a build marks them EXAMPLE
    rx = 1240
    promises = p.layer("Business promises (Alder & Finch's; rewrite for your office)")
    p.cell(promises, "", "rounded=1;arcSize=2;html=1;fillColor=none;strokeColor=none;", rx - 12, 120, 724, 736)
    p.cell(lay, "What this means for the business", HEADING.replace("fontSize=12", "fontSize=14"), rx, 92, 700, 24)
    cards = [
        ("lock", "Guests can't reach staff or files", "Visitors are on their own network with the internet only."),
        ("shield", "The MSP only gets in through one logged door",
         "Remote support uses the VPN with MFA, in a booked window, and every session is recorded."),
        ("printer", "Printers, cameras and door controllers can't phone home",
         "Building and office devices reach only what they need; nothing they start reaches staff."),
        ("isp", "One internet line can fail and work carries on",
         "Two providers on different technologies; the backup takes over on its own."),
        ("power", "No single box takes the office down",
         "A firewall pair, stacked switches and two UPSs: one failure is a ticket, not an outage."),
        ("backup", "Backups leave the building every night",
         "The servers copy overnight to a cloud vault that can't be altered for 30 days and has its own admin "
         "login, so a fire or ransomware is not the end."),
    ]
    for n, (icon, title, text) in enumerate(cards):
        icon_card(p, promises, rx, 128 + n * 122, 700, 106, icon, title, text, 26, 12)
    p.title_block(p.layer("Border & title block"), "All", "Overview — management", f"1 of {SHEETS}", DATE,
                  "Office network standard")
    return p


# ------------------------------------------------------------------ 2 logical
def vlan_rows(zone: str) -> list[list]:
    return [[(str(vid), f"{NETBOX}/ipam/vlans/?vid={vid}&site=o01"), name, subnet, gw]
            for vid, name, z, subnet, gw in S.VLANS if z == zone]


VLAN_COLS = [("VLAN", 44), ("NAME", 130), ("SUBNET", 132), ("GATEWAY", 110)]


def logical() -> Page:
    p = Page("logical", "2 · Logical — Zones, VLANs, Subnets", 2400, 1190, prefix="o")
    lb, lz = p.layer("Bands"), p.layer("Zones")
    lt = p.layer("VLAN tables")
    p.title(lb, f"{S.SITE['code']} · {S.SITE['name']} — Logical",
            esc("Zones · VLANs · subnets · gateways. Every VLAN lives in one zone and every gateway is on the firewall, "
            "so every packet between zones is inspected. One-line rule per zone."))
    W = 1880
    bands = {"OUT": (96, 170), "EDGE": (282, 250), "STAFF": (548, 184), "SHARED": (748, 150), "MGMT": (914, 150)}
    for code, label, _ in S.BANDS:
        y, h = bands[code]
        p.band(lb, y, h, code, label.split(" · ")[0], W)
    # OUTSIDE: providers and cloud, no VLANs.
    zone_box(p, lz, "zone-internet", 100, 108, 1790, 146)
    p.cell(lz, esc(S.ZONE["zone-internet"][5]), SMALL, 112, 132, 900, 18)
    for n, (icon, title, text) in enumerate([
            ("isp", "ISP-A", "DIA 1G · fiber · static 203.0.113.0/29"), ("isp", "ISP-B", "Cable 500/50 · DHCP"),
            ("cloud", "SaaS", "Mail, files, meetings, phones"), ("cloud", "Cloud VNet", "10.50.0.0/16 · IPsec to HQ"),
            ("users", "Home workers", "Remote-access VPN · MFA"), ("wrench", "MSP", "VPN · MFA · booked window"),
            ("building", "O02 Riverside", "10.20.0.0/16 · IPsec to HQ")]):
        icon_card(p, lz, 112 + n * 252, 160, 240, 80, icon, title, text, 24, 11)
    # EDGE: the firewall pair and its interfaces.
    zone_box(p, lz, "zone-edge", 100, 294, 1790, 226)
    p.cell(lz, esc(S.ZONE["zone-edge"][5]), SMALL, 112, 318, 900, 18)
    fwg = p.cell(lz, "<b>O01-FW</b> · HA pair (active / passive)",
                 zone_style("#FFFFFF", "#94A3B8", "#334155", "top", 10), 112, 346, 300, 150)
    for n, name in enumerate(("O01-FW-01", "O01-FW-02")):
        device(p, p.layer("Devices"), name, 124, 376 + n * 60, 276, 52, ip=False, serial=False, pill=False)
    p.cell(lz, "<b>Firewall interfaces</b>", HEADING.replace("fontSize=12", "fontSize=10"), 440, 346, 300, 20)
    table(p, lt, 440, 370, [("INTERFACE", 150), ("ZONE", 120), ("VLAN", 120), ("IP / PREFIX", 200)], [
          ["wan1", "INTERNET", "—", "203.0.113.2/29 (ISP-A)"], ["wan2", "INTERNET", "—", "DHCP (ISP-B)"],
          ["x1–x2 (Po1 / Po2)", "all inside zones", "10–99 tagged", ".1 on every VLAN"],
          ["ssl-vpn", "EDGE", "—", "10.10.200.0/24 (VPN pool)"], ["ipsec-o02", "INTERNET", "—", "to 10.20.0.0/16"]],
          row_h=22)
    p.cell(lz, "<b>Remote access</b>", HEADING.replace("fontSize=12", "fontSize=10"), 1060, 346, 300, 20)
    table(p, lt, 1060, 370, [("POOL", 110), ("NAME", 120), ("SUBNET", 116), ("WHO", 150)], [
          ["—", "VPN-POOL", "10.10.200.0/24", "Staff and the MSP, MFA"],
          ["—", "IPSEC-O02", "10.20.0.0/16", "Riverside branch"],
          ["—", "IPSEC-CLOUD", "10.50.0.0/16", "Cloud VNet"]], row_h=22)
    # Inside zones with VLAN tables.
    layout = {"STAFF": ["zone-staff", "zone-voice", "zone-print", "zone-servers"],
              "SHARED": ["zone-meeting", "zone-guest"], "MGMT": ["zone-building", "zone-mgmt"]}
    for code, zones in layout.items():
        y, h = bands[code]
        bw = (1790 - 10 * (len(zones) - 1)) / len(zones)
        for n, zone in enumerate(zones):
            zx = 100 + n * (bw + 10)
            z = S.ZONE[zone]
            zone_box(p, lz, zone, zx, y + 12, bw, h - 24, f"<b>ZONE {z[1]}</b> · {esc(z[2])}")
            p.cell(lz, esc(z[5]), SMALL, zx + 12, y + 36, bw - 24, 20)
            table(p, lt, zx + 12, y + 62, VLAN_COLS, vlan_rows(zone), row_h=22)
            lives = sub("Lives here: " + esc(z[4]), 9, "#64748B")
            if len(zones) > 2:
                p.cell(lz, lives, SMALL, zx + 12, y + h - 38, bw - 24, 20)
            else:
                p.cell(lz, lives, SMALL, zx + 452, y + 62, bw - 470, 40)
    legend(p, 2000, 96, [(z[1], *z[6]) for z in S.ZONES], flows=False)
    p.title_block(p.layer("Border & title block"), "O01", "Logical — zones, VLANs", f"2 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 3 physical
def physical(p: Page | None = None) -> Page:
    p = Page("physical", "3 · Physical — Devices, Uplinks, Trunks", 2880, 1560, prefix="o")
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
    p.band(lb, 242, 760, "C-2", "COMMS-2 · FLOOR 2", W)
    p.band(lb, 1018, 170, "IDF-3", "IDF-3 · FLOOR 3", W)
    p.band(lb, 1204, 230, "FLRS", "ON THE FLOORS", W)

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
    zone_box(p, lz, "zone-edge", 520, 262, 760, 104, "<b>O01-FW</b> · HA pair (active / passive) · inspects "
             "every zone")
    fw1 = device(p, ld, "O01-FW-01", 560, 290, 250, 58)
    fw2 = device(p, ld, "O01-FW-02", 990, 290, 250, 58)
    ha = cable_by_label("O01-CBL-00005")
    link(p, fw1, fw2, ha, "HA · 1G · Cat6", exit=(1, 0.5), entry=(0, 0.5), ports=("ha", "ha"), weight=1.4)
    # Circuits: each provider hands off to both firewalls.
    lc = p.layer("2 · Links (Po · speed · VLANs)")
    for n, circ in enumerate(S.CIRCUITS):
        for m, fw in enumerate((fw1, fw2)):
            port = f"wan{n + 1}"
            style = (EDGE.replace("strokeColor=#64748B", "strokeColor=#94A3B8").replace("strokeWidth=1.6", "strokeWidth=1.4")
                     + "labelBackgroundColor=#DBEAFE;labelBorderColor=#2563EB;")
            attrs = {"object": "circuits.circuit", "cid": circ["cid"], "status": "active",
                     "x_handoff": f"{'O01-FW-01' if m == 0 else 'O01-FW-02'}:{port}", "x_speed": circ["speed"],
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
    core = stack(p, lz, "O01-CORE", 600, 462, 640, ["O01-CORE-1", "O01-CORE-2"], "zone-mgmt",
                 "CX 6300M ×2 · VSF stack · COMMS-2 R01 / R02")
    link(p, fw1, core, cable_by_label("O01-CBL-00001"), exit=(0.5, 1), entry=(0.2, 0),
         points=[(685, 420), (728, 420)], ports=("x1–x2", "1/1/1 · 2/1/1"), bundle=(728, 448))
    link(p, fw2, core, cable_by_label("O01-CBL-00003"), exit=(0.5, 1), entry=(0.8, 0),
         points=[(1115, 420), (1112, 420)], ports=("x1–x2", "1/1/2 · 2/1/2"), bundle=(1112, 448))

    # Floor 2 access stack, left
    f2 = stack(p, lz, "O01-ACC-F2", 90, 640, 330, ["O01-ACC-F2-1", "O01-ACC-F2-2", "O01-ACC-F2-3"], "zone-staff",
               "CX 6200F 48G PoE ×3 · COMMS-2 R02")
    link(p, core, f2, cable_by_label("O01-CBL-00011"), exit=(0, 0.5), entry=(0.5, 0),
         points=[(255, 508)], ports=("1/1/11 · 2/1/11", "1/1/49 · 3/1/49"), bundle=(255, 600))
    # Building systems beside it
    zone_box(p, lz, "zone-building", 530, 630, 460, 120, "<b>BUILDING</b> · cameras record here; no internet")
    nvr = device(p, ld, "O01-NVR-01", 546, 666, 208, 58)
    door = device(p, ld, "O01-DOOR-01", 766, 666, 208, 58)
    link(p, f2, nvr, cable_by_label("O01-CBL-00031"), "NVR · 1G · Cat6", exit=(1, 0.48), entry=(0, 0.5),
         ports=("2/1/45", "eth0"))
    link(p, f2, door, cable_by_label("O01-CBL-00032"), "DOOR · 1G · Cat6", exit=(1, 0.85), entry=(0.5, 1),
         points=[(870, 739)], ports=("2/1/46", "eth0"))

    # Servers, right: nested elbows off the core's right side, so no two links cross.
    zone_box(p, lz, "zone-servers", 1250, 630, 690, 120, "<b>SERVERS</b> · two hosts and the backup NAS")
    hv1 = device(p, ld, "O01-HV-01", 1266, 666, 216, 58)
    hv2 = device(p, ld, "O01-HV-02", 1494, 666, 216, 58)
    nas = device(p, ld, "O01-NAS-01", 1722, 666, 206, 58)
    link(p, core, nas, cable_by_label("O01-CBL-00025"), "NAS · 10G · Cat6A", exit=(1, 0.15), entry=(0.5, 0),
         points=[(1825, 475.5)], ports=("1/1/23", "lan1"))
    link(p, core, hv2, cable_by_label("O01-CBL-00023"), exit=(1, 0.45), entry=(0.5, 0),
         points=[(1602, 502.5)], ports=("1/1/22 · 2/1/22", "nic1–2"), bundle=(1602, 640))
    link(p, core, hv1, cable_by_label("O01-CBL-00021"), exit=(1, 0.75), entry=(0.5, 0),
         points=[(1374, 529.5)], ports=("1/1/21 · 2/1/21", "nic1–2"), bundle=(1374, 640))

    # Management and power, below the servers: down the gap beside them, then up into each card.
    zone_box(p, lz, "zone-mgmt", 1250, 790, 690, 120, "<b>MGMT &amp; POWER</b> · on the core, in the racks")
    ups1 = device(p, ld, "O01-UPS-01", 1266, 826, 216, 58)
    ups2 = device(p, ld, "O01-UPS-02", 1494, 826, 216, 58)
    oob = device(p, ld, "O01-OOB-01", 1722, 826, 206, 58)
    for n, (dev, label, ports, name) in enumerate([(ups1, "O01-CBL-00033", ("1/1/24", "nmc"), "UPS1"),
                                                   (ups2, "O01-CBL-00034", ("2/1/24", "nmc"), "UPS2"),
                                                   (oob, "O01-CBL-00035", ("1/1/20", "net1"), "OOB")]):
        x = 1225 - n * 10
        y = 940 + n * 12
        target = (1374, 1602, 1825)[n]
        link(p, core, dev, cable_by_label(label), f"{name} · 1G · Cat6", exit=((x - 600) / 640, 1), entry=(0.5, 1),
             points=[(x, y), (target, y)], ports=ports)
    note(p, 1250, 984, 690, 30, "Console lines (not cables in NetBox): OOB-01 serial 1–4 to FW-01, FW-02, "
         "CORE-1, CORE-2 · cellular to the MSP. UPS runtime: R01 about 18 min, R02 about 22 min.")

    # Floor 3 access stack, straight under the core
    f3 = stack(p, lz, "O01-ACC-F3", 1000, 1046, 330, ["O01-ACC-F3-1", "O01-ACC-F3-2"], "zone-staff",
               "CX 6200F 48G PoE ×2 · IDF-3 R01")
    link(p, core, f3, cable_by_label("O01-CBL-00013"), exit=(0.78125, 1), entry=(0.3, 0),
         ports=("1/1/12 · 2/1/12", "1/1/49 · 2/1/49"), bundle=(1100, 1034))

    # Floors: one card per kind of end device, the build counts the rest. Drops leave the stack
    # left to right and drop to nested levels, so none cross.
    ends = [("Floor 2", 90, 90, 330, f2, ["O01-AP-F2-01", "O01-PRN-F2-01", "O01-MR-2A", "O01-CAM-01"]),
            ("Floor 3", 1000, 1000, 330, f3, ["O01-AP-F3-01", "O01-PRN-F3-01", "O01-MR-3A"])]
    for floor, fx, sx, sw_w, sw, names in ends:
        p.cell(lz, f"<b>{floor}</b> · one card per kind of end device; the build shows how many",
               zone_style("#FFFFFF", "#E2E8F0", "#334155", "bottom", 10), fx, 1222,
               880 if floor == "Floor 2" else 680, 210)
        for n, name in enumerate(names):
            d = DEV[name]
            x = fx + 14 + n * 212
            cid = device(p, ld, name, x, 1316, 200, 52, small=True, pill=False,
                         label='<b>%name%</b><br>' + sub("%device_type%"))
            c = CABLE_OF[name][0]
            sw_port = c["a"][0].split(":")[1]
            member = int(c["a"][0].split(":")[0].rsplit("-", 1)[1])
            iface = f"{member}/1/{sw_port.split('/')[-1]}"
            vlan = S.ACCESS_VLAN.get(d["role"])
            text = f"{c['speed']} · {c['media']}" + (f" · {vlan}" if vlan else " · trunk")
            ex_x = sx + 30 + n * 70
            level = 1290 - n * 14
            pts = [(ex_x, level), (x + 100, level)]
            link(p, sw, cid, c, text, exit=((ex_x - sx) / sw_w, 1), entry=(0.5, 0), points=pts,
                 ports=(iface, "eth0"), weight=1.2, color="#94A3B8")
    note(p, 1720, 1222, 220, 210, "<b>End devices</b><br>APs trunk VLANs 11, 50, 70 (native 99). Printers on "
         "VLAN 30, meeting rooms on 50, cameras on 80. Desk phones and PCs are not drawn: the switch port "
         "carries the zone.", guide=False)

    # Registers and legend, right
    lr = p.layer("6 · Link register")
    link_card = p.cell(lr, "", CARD, 1976, 96, 880, 400)
    p.cell(lr, "<b>Link register</b> — port-channels, members, speed, trunked VLANs", HEADING, 1990, 106, 840, 22)
    rows = []
    for c in S.CABLES[:13]:
        a_dev = sorted({e.split(":")[0].replace("O01-", "") for e in c["a"]})
        b_dev = sorted({e.split(":")[0].replace("O01-", "") for e in c["b"]})
        a_ports = " · ".join(e.split(":")[1] for e in c["a"])
        b_ports = " · ".join(e.split(":")[1] for e in c["b"])
        name = c["lag"] or {"O01-NAS-01": "NAS", "O01-NVR-01": "NVR", "O01-DOOR-01": "DOOR", "O01-UPS-01": "UPS1",
                        "O01-UPS-02": "UPS2", "O01-OOB-01": "OOB"}.get(c["b"][0].split(":")[0], "")
        speed = c["speed"] + (" LACP" if c["lag"].startswith("Po") else "")
        ids = ", ".join(f"#{S.CABLES.index(c) * 2 + k + 1}" for k in range(len(c["labels"])))
        rows.append([name, ids, f"{'/'.join(a_dev)} {a_ports}", f"{'/'.join(b_dev)} {b_ports}", speed, c["media"],
                     "connected",
                     c["vlans"] or ("access " + str(S.ACCESS_VLAN.get(DEV[c["b"][0].split(':')[0]]['role'], ''))
                                    if c["lag"] != "HA" else "heartbeat")])
    # CABLE ID and STATUS are drawn here, wide enough for "connected", so the build doesn't squeeze them in.
    table(p, lr, 1990, 134, [("LINK", 46), ("CABLE ID", 60), ("A-SIDE (MEMBERS)", 176), ("B-SIDE (MEMBERS)", 176),
          ("SPEED", 84), ("MEDIA", 66), ("STATUS", 70), ("TRUNKED VLANS", 162)], rows, row_h=22)
    note(p, 1990, 134 + p.table_height + 8, 840, 32, "All trunks: native VLAN 999 (unused) · explicit allowed list · LACP "
         "fast. End-device drops are in NetBox, not in this register.")
    bottom = 134 + p.table_height + 8 + 32 + 14   # the card fits its table, two-line trunk rows included
    resize(p, link_card, bottom - 96)
    la = p.layer("7 · Asset register")
    infra = [d["name"] for d in S.DEVICES if d["role"] not in ("access-point", "printer", "room-system", "camera")]
    reg = infra  # end devices are counted on their cards; APs have their own register on sheet 3d
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
    # Wide enough that the STATUS and CRIT columns a build adds (from HOSTNAME/ROLE and MODEL/ROOM/SW) leave
    # every cell on one line.
    table(p, la, 1990, top + 36, [("HOSTNAME", 112), ("ROLE", 104), ("MODEL", 166), ("SERIAL", 96), ("MGMT IP", 78),
          ("ROOM", 76), ("RACK/CAB", 58), ("U", 36), ("SW", 114)], rows, row_h=20)
    resize(p, asset_card, 36 + p.table_height + 16)
    legend(p, 1976, top + 36 + p.table_height + 16 + 14, [(z[1], *z[6]) for z in S.ZONES], flows=False)
    p.title_block(p.layer("Border & title block"), "O01", "Physical — devices, links", f"3 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ 3d wireless
def wireless() -> Page:
    p = Page("wireless", "3d · Wireless — APs and SSIDs", 2400, 1000, prefix="o")
    lb, lz, ld = p.layer("Floors"), p.layer("Zones"), p.layer("1 · Devices")
    p.layer("3 · Mgmt IPs (hide before sharing)")
    p.layer("3b · Serial numbers")
    p.title(lb, f"{S.SITE['code']} · {S.SITE['name']} — Wireless",
            esc("Access points per floor · SSIDs and the zone each one lands in."))
    # A build rewrites this card from the site's wireless_management / wireless_manager fields.
    cloud = icon_card(p, lb, 600, 96, 600, 70, "cloud", "Cloud Wi-Fi management",
                      "Configuration, firmware and guest portal from the vendor's cloud · APs reach it over HTTPS",
                      attrs={"netdiagrams_wireless_mgmt": "1"})
    for n, floor in enumerate((2, 3)):
        fx = 24 + n * 760
        p.cell(lb, f"<b>Floor {floor}</b> · ceiling APs on O01-ACC-F{floor}: PoE, trunk 11, 50, 70 "
               "(native 99)", zone_style("#FFFFFF", "#E2E8F0", "#334155", "top", 11), fx, 210, 740, 130)
        device(p, ld, f"O01-AP-F{floor}-01", fx + 20, 250, 360, 60, small=True, pill=False,
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
                     f"{sw.replace('O01-', '')} {port}", c["labels"][0]])
    table(p, la, 40, 400, [("NAME", 200), ("MODEL", 140), ("SERIAL", 160), ("MGMT IP", 150), ("LOCATION", 150),
          ("SWITCH PORT", 380), ("CABLE", 300)], rows, row_h=22)
    p.edge(p.layer("2 · Management"), cloud, None, "endArrow=none;html=1;strokeColor=#94A3B8;strokeWidth=1.2;"
           "dashed=1;fontSize=9;fontColor=#475569;labelBackgroundColor=#FFFFFF;" + FONT, "AP management",
           exit=(0.5, 1), tgt_pt=(900, 210))
    lt = p.layer("SSID table")
    p.cell(lt, "", CARD, 1580, 210, 796, 290)
    p.cell(lt, "<b>SSIDs</b> — one per zone, never one for everything", HEADING, 1596, 220, 760, 22)
    rows = [[ssid, str(vlan), S.ZONE[zone][1], sec, notes] for ssid, sec, vlan, zone, notes in S.SSIDS]
    table(p, lt, 1596, 250, [("SSID", 110), ("VLAN", 120), ("ZONE", 80), ("SECURITY", 200), ("NOTES", 250)], rows,
          row_h=30)
    note(p, 1596, 360, 760, 120, "<b>Rules</b><br>· AF-GUEST: client isolation, captive portal, rate limit, DNS "
         "filter; lands in GUEST only.<br>· AF-DEVICES: meeting-room systems only; key rotated quarterly and whenever someone who knew it leaves.<br>"
         "· No SSID for cameras, printers or building systems: they are wired.<br>· Rogue AP detection on; "
         "management VLAN 99 is never broadcast.")
    legend(p, 1580, 520, [(z[1], *z[6]) for z in S.ZONES], flows=False)
    p.title_block(p.layer("Border & title block"), "O01", "Wireless — APs, SSIDs", f"3d of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 4 flows
VERDICT = {"Allow": ("#16A34A", "endArrow=block;endFill=1;", "Permitted"),
           "Conditional": ("#EA580C", "dashed=1;endArrow=block;endFill=1;", "Conditional"),
           "Deny": ("#DC2626", "dashed=1;endArrow=none;", "Denied")}


def flows() -> Page:
    p = Page("flows", "4 · Traffic Flows — who talks to whom", 2400, 60 + 96 + 46 * len(S.FLOWS) + 150, prefix="o")
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
    p.title_block(p.layer("Border & title block"), "O01", "Traffic flows", f"4 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 5 failover
def failover() -> Page:
    p = Page("failover", "5 · Failover scenarios", 2400, 900, prefix="o")
    lb = p.layer("Scenarios")
    p.title(lb, f"{S.SITE['code']} · {S.SITE['name']} — Failover",
            esc("What happens at 3 a.m. when one thing breaks: what fails, what takes over, and what people notice."))
    scenarios = [
        ("isp", "ISP-A goes down", "Fiber cut or provider outage on O01-ISP-A-01.",
         "The firewall pair moves internet traffic to ISP-B (cable 500/50) within about 30 seconds; the IPsec "
         "tunnels to O02 and the cloud rebuild over ISP-B.",
         "Calls in progress drop and redial. Big uploads are slower until ISP-A is back."),
        ("firewall", "O01-FW-01 fails", "Power supply, disk or a bad update on the active firewall.",
         "O01-FW-02 takes over the gateway addresses (.1 on every VLAN) and both WAN lines; sessions carry on.",
         "A few seconds of pause. VPN users may need to reconnect."),
        ("core-switch", "A core stack member fails", "O01-CORE-1 or O01-CORE-2 dies or is rebooted.",
         "Every port-channel (Po1, Po2, Po11, Po12, Po21, Po22) keeps its link on the other member at half "
         "speed.", "Nothing, apart from the NAS link and the management drops on that member."),
        ("access-switch", "The floor 3 uplink cable is cut", "One of the two Po12 fibers to IDF-3 is damaged.",
         "The other Po12 member carries all of floor 3 at 10G.", "Nothing. The alert goes to the MSP."),
        ("power", "Power cut", "The building loses power; the generator does not cover the tenant floors.",
         "Both UPSs carry COMMS-2 (about 18 and 22 minutes at today's load). Floor PoE goes dark with the "
         "access switches' power. While the UPSs last, the console server reaches the firewall over cellular "
         "(both internet boxes are off). Then everything in COMMS-2 goes dark.",
         "Wi-Fi and desk phones stop; laptops on battery lose the network. Shut down cleanly before the UPSs "
         "run out."),
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
    p.title_block(p.layer("Border & title block"), "O01", "Failover scenarios", f"5 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 6 branches and cloud
def multisite() -> Page:
    p = Page("multisite", "6 · Branches and cloud", 2400, 1130, prefix="o")
    lb, lc, ll = p.layer("Sites"), p.layer("Cards"), p.layer("Tunnels")
    p.title(lb, "Alder & Finch — Branches and cloud",
            esc("HQ, the Riverside branch, the cloud server network, SaaS, home workers and the MSP. Every site has "
            "its own internet line; the tunnels all end on the HQ firewall pair."))
    inet = icon_card(p, lc, 860, 100, 520, 80, "globe", "Internet", "Each site's own lines · SaaS reached directly "
                     "from every site", 30, 13)
    hq = p.cell(lc, "<b>O01 · Alder &amp; Finch HQ</b> · 10.10.0.0/16 · about 140 staff<br>"
                + sub("Firewall HA pair · core stack · 2 floors · 16 APs · servers and backup"),
                zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), 760, 420, 720, 180)
    for n, (icon, title, text) in enumerate([("firewall", "O01-FW HA pair", "Ends every tunnel"),
                                             ("server", "Servers", "Files and the accounting app"),
                                             ("backup", "Backup NAS", "Copies to the cloud vault nightly")]):
        icon_card(p, lc, 780 + n * 232, 476, 218, 80, icon, title, text, 24, 11)
    br = p.cell(lc, "<b>O02 · Riverside branch</b> · 10.20.0.0/16 · about 15 staff<br>"
                + sub("One firewall with cellular backup · one switch · two APs · a printer"),
                zone_style("#F4FAF5", "#B4DDBF", "#16A34A", "top", 12), 100, 690, 560, 170)
    for n, (icon, title, text) in enumerate([("firewall", "O02-FW-01", "Broadband 300/30 + cellular"),
                                             ("access-switch", "O02-ACC-1", "24-port PoE")]):
        icon_card(p, lc, 120 + n * 264, 756, 250, 80, icon, title, text, 24, 11)
    cl = p.cell(lc, "<b>Cloud VNet</b> · 10.50.0.0/16<br>"
                + sub("Line-of-business VMs and the backup vault, reached only from HQ and the branch"),
                zone_style("#F3FAF9", "#AADAD5", "#0D9488", "top", 12), 1580, 690, 560, 170)
    for n, (icon, title, text) in enumerate([("server", "App VMs", "Accounting back end"),
                                             ("backup", "Backup vault", "Immutable, 30 days")]):
        icon_card(p, lc, 1600 + n * 264, 756, 250, 80, icon, title, text, 24, 11)
    saas = icon_card(p, lc, 1580, 240, 560, 80, "cloud", "SaaS", "Mail, files, meetings, the phone service", 30, 13)
    home = icon_card(p, lc, 100, 240, 560, 80, "users", "Home workers", "About 30 a day · remote-access VPN · MFA",
                     30, 13)
    msp = icon_card(p, lc, 100, 420, 560, 80, "wrench", "MSP", "VPN · MFA · booked window · logged", 30, 13)
    tunnel = ("html=1;strokeColor=#2563EB;strokeWidth=2;dashed=1;dashPattern=8 4;endArrow=none;fontSize=10;"
              "fontColor=#1E3A8A;labelBackgroundColor=#FFFFFF;" + FONT)
    plain_line = "html=1;strokeColor=#94A3B8;strokeWidth=1.4;endArrow=none;fontSize=10;fontColor=#475569;" \
                 "labelBackgroundColor=#FFFFFF;" + FONT
    p.edge(ll, br, hq, tunnel, "IPsec · F16", exit=(1, 0.3), entry=(0.1, 1), points=[(832, 741)])
    p.edge(ll, cl, hq, tunnel, "IPsec · F15", exit=(0, 0.3), entry=(0.9, 1), points=[(1408, 741)])
    p.edge(ll, home, hq, tunnel.replace("#2563EB", "#7C3AED"), "VPN + MFA · F14", exit=(1, 0.5), entry=(0.3, 0),
           points=[(976, 280)])
    p.edge(ll, msp, hq, tunnel.replace("#2563EB", "#EA580C"), "VPN + MFA · F13", exit=(1, 0.5), entry=(0, 0.2222))
    p.edge(ll, inet, hq, plain_line, "ISP-A + ISP-B", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(ll, saas, hq, plain_line, "HTTPS", exit=(0, 0.5), entry=(1, 0.2), points=[(1520, 280), (1520, 456)])
    lt = p.layer("Site table")
    p.cell(lt, "<b>Sites</b>", HEADING, 100, 900, 2040, 22)
    table(p, lt, 100, 926, [("CODE", 90), ("SITE", 240), ("PREFIX", 160), ("INTERNET", 420), ("BACKUP", 380),
          ("LINK TO HQ", 750)], [
[("O01", f"{NETBOX}/dcim/sites/?slug=o01"), "Alder & Finch HQ", "10.10.0.0/16",
"ISP-A DIA 1G fiber · ISP-B cable 500/50", "Second ISP, firewall HA pair", "—"],
[("O02", f"{NETBOX}/dcim/sites/?slug=o02"), "Riverside branch", "10.20.0.0/16",
"Provider C broadband 300/30", "Cellular on O02-FW-01", "IPsec to the HQ firewall pair"],
["CLOUD", "Cloud VNet", "10.50.0.0/16", "Provider network", "Second region for the vault",
"IPsec to the HQ firewall pair"]], row_h=26)
    p.title_block(p.layer("Border & title block"), "All", "Branches and cloud", f"6 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 7 flow register
ZONE_ORDER = ["zone-internet", "zone-staff", "zone-voice", "zone-print", "zone-servers", "zone-meeting",
              "zone-guest", "zone-building", "zone-mgmt"]
MATRIX = {  # (from, to): (verdict, flows)
    ("zone-staff", "zone-internet"): ("allow", "F01"), ("zone-staff", "zone-servers"): ("allow", "F02"),
    ("zone-staff", "zone-print"): ("allow", "F03"), ("zone-print", "zone-staff"): ("deny", "F04"),
    ("zone-print", "zone-internet"): ("cond", "F05"), ("zone-voice", "zone-internet"): ("allow", "F06"),
    ("zone-guest", "zone-internet"): ("allow", "F07"), ("zone-meeting", "zone-internet"): ("allow", "F09"),
    ("zone-staff", "zone-meeting"): ("cond", "F10"), ("zone-building", "zone-internet"): ("deny", "F12"),
    ("zone-internet", "zone-mgmt"): ("cond", "F13"), ("zone-internet", "zone-servers"): ("allow", "F14 F16"),
    ("zone-servers", "zone-internet"): ("allow", "F15"), ("zone-mgmt", "zone-internet"): ("cond", "F18 F19 F21"),
}


def register() -> Page:
    p = Page("register", "7 · Flow register & standards", 2400, 718 + 26 * len(S.FLOWS), prefix="o")  # 1160 at 17 flows; grows with the register
    lf, lm, ls = p.layer("Flow register"), p.layer("Zone matrix"), p.layer("Standards")
    p.title(lf, f"{S.SITE['code']} · {S.SITE['name']} — Flow register and standards",
            esc("The segmentation in writing: every permitted conversation, its conditions and owner, then default "
            "deny. The zone matrix is the same rules as a grid. Naming and drawing standards at the right."))
    p.cell(lf, "", CARD, 24, 92, 1500, 22 + 26 * (len(S.FLOWS) + 2) + 30)
    p.cell(lf, "<b>Flow register</b>", HEADING, 40, 102, 1460, 22)
    look = {"Allow": "#15803D", "Conditional": "#B45309", "Deny": "#B91C1C"}
    rows = [[fid, src, dst, what, f'<font color="{look[v]}"><b>{v}</b></font>', cond, owner]
            for fid, src, dst, what, v, cond, owner in S.FLOWS]
    rows.append(["—", "Any", "Any", "Everything not listed above", '<font color="#B91C1C"><b>Deny</b></font>',
                 "Default deny, logged", "IT"])
    table(p, lf, 40, 128, [("ID", 44), ("FROM", 210), ("TO", 200), ("WHAT", 330), ("VERDICT", 90),
          ("CONDITIONS", 360), ("OWNER", 230)], rows, row_h=26)
    my = 128 + 26 * (len(S.FLOWS) + 2) + 50
    n = len(ZONE_ORDER)
    p.cell(lm, "", CARD, 24, my, 1500, 60 + 30 * (n + 1))
    p.cell(lm, "<b>Zone matrix</b> — rows start the conversation, columns answer; blank is "
           "default deny", HEADING, 40, my + 10, 1460, 22)
    cols = [("FROM \\ TO", 140)] + [(S.ZONE[z][1], 140) for z in ZONE_ORDER]
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
    sx = 1560
    p.cell(ls, "", CARD, sx, 92, 816, 410)
    p.cell(ls, "<b>Naming and drawing standards</b>", HEADING, sx + 16, 102, 780, 22)
    table(p, ls, sx + 16, 128, [("ITEM", 170), ("STANDARD", 610)], [
          ["Site code", "O + two digits: O01 HQ, O02 Riverside"],
          ["Device", "SITE-ROLE-NN: O01-FW-01, O01-ACC-F2-1 (floor, member)"],
          ["Stack", "SITE-ROLE-FLOOR: O01-ACC-F2; members -1, -2, -3"],
          ["Cable label", "SITE-CBL-nnnnn on both ends: O01-CBL-00011"],
          ["Zone tag", "zone-&lt;name&gt; on every device, VLAN and prefix"],
          ["VLAN", "Tens per zone: 10s staff, 20 voice, 30 print, 40s servers, 50 meeting, 70 guest, "
                   "80s building, 99 management"],
          ["Subnet", "10.&lt;site&gt;.&lt;vlan&gt;.0/24 (staff /23 and /22, guest from 172.16)"],
          ["Gateway", ".1 on the firewall pair, for every VLAN"],
          ["Link pill", "Po · speed · media; port tags at each end"],
          ["Hide before sharing", "Layers 3 (mgmt IPs) and 4 (circuit IDs)"],
          ["Change", "Edit NetBox, then rebuild; never fix the drawing alone"]], row_h=30)
    p.title_block(p.layer("Border & title block"), "O01", "Flow register and standards", f"7 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ main
def build() -> ET.Element:
    return mxfile((overview(), logical(), physical(), wireless(), flows(), failover(), multisite(), register()),
                  "netdiagrams office template")


def main() -> None:
    tree = build()
    ET.indent(tree, space=" ")
    OUT.write_text(ET.tostring(tree, encoding="unicode") + "\n", "utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
