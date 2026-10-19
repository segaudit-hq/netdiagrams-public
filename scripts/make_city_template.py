"""Generate src/netdiagrams/data/M01-Municipal-Template.drawio, the local government standard.

Eight sheets drawn for the fictional City of Halvern's civic center (site CH1):
overview, logical, physical, wireless, traffic flows, failover, the city's
buildings and links, and the flow register. Every fact comes from
scripts/city_template/site.py, the same source scripts/make_city_sample.py
turns into the sample NetBox export, so
`netdiagrams build --input sample-municipal.json` reproduces the template.

    python scripts/make_city_template.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from city_template import site as S  # noqa: E402
from drawkit import (  # noqa: E402
    BAND, EDGE, FONT, NETBOX, NOTE, POINTS, RACK_PILL, SUBTITLE, TITLE, Page, _svg, esc, mxfile, sub, zone_style)
from make_office_template import (  # noqa: E402  (the office look: same styles, same icon strokes)
    BUNDLE, CARD, CID_TAG, HEADING, ICONS as OFFICE_ICONS, IP_TAG, KEY_CELL, ORANGE, PINK, PORT_LABEL, SMALL,
    SN_TAG, TEXT, VIOLET, _circle, _line, _rect, group_style, table)

AMBER, RED, BROWN = "#A16207", "#DC2626", "#78716C"

# ------------------------------------------------------------------ icons: the office set plus the city's own
ICONS = dict(OFFICE_ICONS)
ICONS.update({
    "payment-terminal": _svg("#FDE8E8", _rect(10, 6, 12, 20, RED, rx=2.5) + _rect(12.5, 8.5, 7, 5, RED, rx=1)
                             + f'<circle cx="13.5" cy="17" r="0.9" fill="{RED}"/><circle cx="16" cy="17" r="0.9" fill="{RED}"/>'
                               f'<circle cx="18.5" cy="17" r="0.9" fill="{RED}"/><circle cx="13.5" cy="20.5" r="0.9" fill="{RED}"/>'
                               f'<circle cx="16" cy="20.5" r="0.9" fill="{RED}"/><circle cx="18.5" cy="20.5" r="0.9" fill="{RED}"/>'),
    "signal-system": _svg("#FBF3D5", _rect(11.5, 5.5, 9, 21, AMBER, rx=3) + _circle(16, 10, 2, AMBER, width=1.4)
                          + _circle(16, 16, 2, AMBER, width=1.4) + _circle(16, 22, 2, AMBER, width=1.4)),
    "hvac-controller": _svg("#FBE4EF", _rect(7, 8, 18, 16, PINK, rx=2.5) + _circle(16, 16, 4.5, PINK, width=1.4)
                            + _line("16,11.5 16,20.5", PINK, 1.4) + _line("11.5,16 20.5,16", PINK, 1.4)),
    "router": _svg("#EDEBE9", _circle(16, 16, 9, BROWN, width=1.6) + _line("11,13 21,13", BROWN, 1.4)
                   + _line("18.8,10.8 21,13 18.8,15.2", BROWN, 1.4) + _line("21,19 11,19", BROWN, 1.4)
                   + _line("13.2,16.8 11,19 13.2,21.2", BROWN, 1.4)),
    "public-pc": _svg("#FCEFE0", _rect(7, 8, 18, 12, ORANGE, rx=2) + _line("16,20 16,24", ORANGE)
                      + _line("12,24.5 20,24.5", ORANGE)),
    "badge": _svg("#EFE7FD", _line("16,6 18.4,11 24,11.6 19.8,15.4 21,21 16,18.2 11,21 12.2,15.4 8,11.6 13.6,11 16,6",
                                   VIOLET)),
    "drop": _svg("#E2F0F5", _line("16,6.5 20.6,13 22.5,17.5 21.4,21.6 18.6,24.2 16,25 13.4,24.2 10.6,21.6 9.5,17.5 "
                                  "11.4,13 16,6.5", "#3F6F82")),
    "book": _svg("#FCEFE0", _line("16,9.5 12,8 7,8 7,23 12,23 16,24.5 20,23 25,23 25,8 20,8 16,9.5", ORANGE)
                 + _line("16,9.5 16,24.5", ORANGE)),
    "capitol": _svg("#EDEBE9", _line("7,13 16,7 25,13", BROWN) + _line("8,13 24,13", BROWN) + _line("10,13 10,22", BROWN)
                    + _line("14,13 14,22", BROWN) + _line("18,13 18,22", BROWN) + _line("22,13 22,22", BROWN)
                    + _line("7,24.5 25,24.5", BROWN)),
    "truck": _svg("#FDE8E8", _rect(6, 11, 13, 10, RED, rx=1.5) + _line("19,14 23,14 26,18 26,21 19,21", RED)
                  + _circle(10.5, 22.5, 2, RED, fill="#FDE8E8") + _circle(21.5, 22.5, 2, RED, fill="#FDE8E8")),
    "headset": _svg("#EDEBE9", _line("8.5,18 8.5,15 10.7,10.2 16,8 21.3,10.2 23.5,15 23.5,18", BROWN)
                    + _rect(7, 17, 4, 6, BROWN, rx=1.5) + _rect(21, 17, 4, 6, BROWN, rx=1.5)
                    + _line("23,23 20,25.5 17,25.5", BROWN, 1.4)),
    "car": _svg("#EFE7FD", _line("7,19 8.5,13.5 11,11 21,11 23.5,13.5 25,19", VIOLET) + _rect(6, 18, 20, 5, VIOLET, rx=2)
                + _circle(11, 23.5, 1.6, VIOLET, fill="#EFE7FD") + _circle(21, 23.5, 1.6, VIOLET, fill="#EFE7FD")),
})
ICON_FOR_ROLE = {"firewall": "firewall", "core-switch": "core-switch", "access-switch": "access-switch",
                 "access-point": "access-point", "hypervisor": "hypervisor", "storage": "storage", "server": "server",
                 "ups": "ups", "console-server": "console-server", "printer": "printer", "nvr": "nvr", "camera": "camera",
                 "door-controller": "door-controller", "router": "router", "payment-terminal": "payment-terminal",
                 "signal-system": "signal-system", "hvac-controller": "hvac-controller", "public-pc": "public-pc",
                 "phone": "phone"}


def label_style(icon: str, size: int = 22, left: int = 28, font: int = 10, valign: str = "top", arc: int = 12) -> str:
    return (f"shape=label;rounded=1;absoluteArcSize=1;arcSize={arc};fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;"
            f"shadow=1;align=left;verticalAlign={valign};spacingTop=5;spacingLeft={left};fontSize={font};fontColor=#0F172A;"
            f"whiteSpace=wrap;html=1;{POINTS}{FONT}image=data:image/svg+xml,{ICONS[icon]};imageWidth={size};"
            f"imageHeight={size};imageAlign=left;imageVerticalAlign=middle;")


DEVICE_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 30, 38, 11)
SMALL_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 22, 28, 10)
MEMBER_ROW = lambda role: label_style(ICON_FOR_ROLE.get(role, "access-switch"), 16, 22, 9)

LEGEND_ITEMS = [("firewall", "Firewall (HA pair)"), ("core-switch", "Core pair (SVL)"),
                ("access-switch", "Access stack"), ("access-point", "Wireless AP (cloud managed)"),
                ("hypervisor", "Virtualization host"), ("storage", "Storage / backup"), ("ups", "UPS"),
                ("console-server", "Out-of-band console"), ("router", "Router (state-managed)"),
                ("payment-terminal", "Payment terminal"), ("printer", "Printer / MFP"), ("nvr", "Video recorder"),
                ("camera", "Camera"), ("door-controller", "Door controller"), ("hvac-controller", "HVAC controller"),
                ("signal-system", "Traffic signal system"), ("public-pc", "Public PC"), ("cloud", "Cloud / SaaS")]


def legend(p: Page, x: float, y: float, zones: list[tuple[str, str, str, str]], flows: bool = True) -> float:
    """The city legend: icons, line meanings and the zone colors. Returns its height."""
    layer = p.layer("Legend")
    rows = -(-len(LEGEND_ITEMS) // 2)
    lines = [("#64748B", 1.6, "", "Link · pill = Po · speed · media · tag = port"),
             ("#64748B", 2.5, "", "Weight = speed (thicker = 10G and up)"),
             ("#7C4DFF", 2.5, "", "Violet = police cords (R03 and IDF-PD)")]
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
OUT = DATA / "M01-Municipal-Template.drawio"
DATE = "2026-10-18"
PROJECT = "City network standard"
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
MEDIA_LOOK = {  # label background, label border
    "DAC": ("#E2E8F0", "#64748B"), "MMF OM4": ("#A5F3FC", "#0891B2"),
    "Cat6": ("#DBEAFE", "#2563EB"), "Cat6A": ("#DBEAFE", "#2563EB"),
}
ZONE_LOOK = {z[0]: z[6] for z in S.ZONES}
POLICE = "#7C4DFF"   # the police patch cords' color, as NetBox records it (7c4dff)
LINKS = "2 · Links (Po · speed · VLANs)"


# ------------------------------------------------------------------ objects
def resize(p, cid: str, height: float) -> None:
    """Set a drawn box's height once what it holds is measured."""
    p.find(cid).find(".//mxGeometry").set("height", f"{height:g}")


def dev_attrs(name: str) -> dict:
    d = DEV[name]
    a = {k: str(d.get(k, "") or "") for k in ATTR_ORDER}
    a["site"] = SITE
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
        role_word = "active" if n == 0 else ("standby" if n == 1 else "member")
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
         ports=None, bundle=None, weight=None, color=None, pos=None) -> str:
    labels = ", ".join(cable["labels"])
    attrs = {"object": "dcim.cable", "cable_label": labels, "type": cable["type"], "status": "connected",
             "color": cable["color"], "length": "", "length_unit": "", "a_terminations": ", ".join(cable["a"]),
             "b_terminations": ", ".join(cable["b"]), "x_speed": cable["speed"], "x_media": cable["media"],
             "x_patch_a": "", "x_patch_b": ""}
    attrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in attrs.items()), **attrs,
             "link": f"{NETBOX}/dcim/cables/?" + "&".join(f"label={l}" for l in cable["labels"]),
             "linkTarget": "_blank"}
    bg, border = MEDIA_LOOK.get(cable["media"], ("#FFFFFF", "#E2E8F0"))
    width = weight or (2.5 if "10G" in cable["speed"] or "25G" in cable["speed"] else 1.4)
    color = color or (POLICE if cable["color"] == "7c4dff" else "#64748B")
    style = (EDGE.replace("strokeColor=#64748B", f"strokeColor={color}").replace("strokeWidth=1.6", f"strokeWidth={width}")
             + f"labelBackgroundColor={bg};labelBorderColor={border};")
    if text is None:
        text = " · ".join(x for x in (cable["lag"] if cable["lag"].startswith("Po") else "", cable["speed"],
                                       cable["media"]) if x)
    eid = p.edge(p.layer(LINKS), src, dst, style, esc(text), attrs, points=points, exit=exit, entry=entry, pos=pos)
    if ports:
        a, b = ports[:2]
        if a:
            dx, dy = ports[2] if len(ports) > 2 else (0, 0)
            p.edge_label(eid, a, -1, dy, PORT_LABEL, dx)
        if b:
            dx, dy = ports[3] if len(ports) > 3 else (0, 0)
            p.edge_label(eid, b, 1, dy, PORT_LABEL, dx)
    if bundle:
        p.cell(p.layer(LINKS), "", BUNDLE, bundle[0] - 10, bundle[1] - 4.5, 20, 9)
    return eid


def label_at(path: list[tuple[float, float]], seg: int, frac: float = 0.5) -> float:
    """The edge-label position (-1 source .. 1 target) of a point ``frac`` along segment ``seg`` of an
    orthogonal path given as its absolute corners, source end first."""
    lens = [abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(path, path[1:])]
    return round(2 * (sum(lens[:seg]) + lens[seg] * frac) / sum(lens) - 1, 4)


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


def boundary_style(fill="#F0F7FA", stroke="#3F6F82") -> str:
    """A boundary we draw but never open up: hatched, dashed, its owner's to detail."""
    return (f"rounded=1;absoluteArcSize=1;arcSize=16;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;dashed=1;"
            "dashPattern=6 4;fillStyle=hatch;verticalAlign=top;align=left;spacingLeft=10;spacingTop=6;fontSize=11;"
            f"fontColor={stroke};html=1;whiteSpace=wrap;" + FONT)


def x_mark(p: Page, layer: str, x, y) -> str:
    return p.cell(layer, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
                  "fontSize=10;fontStyle=1;" + FONT, x, y, 20, 20)


DENIED = ("endArrow=none;html=1;strokeColor=#DC2626;strokeWidth=1.6;dashed=1;fontSize=9;fontColor=#991B1B;"
          "labelBackgroundColor=#FFFFFF;" + FONT)


# ------------------------------------------------------------------ 1 overview
def overview() -> Page:
    p = Page("overview", "1 · Overview — for the city manager", 2000, 1150, prefix="m")
    lay = p.layer("Overview")
    p.cell(lay, "How the city network is protected", TITLE, 24, 18, 1000, 32)
    p.cell(lay, "Management overview: no technical detail. City Hall, the police, the public and the buildings "
           "share one network, each behind its own door.", SUBTITLE, 24, 52, 1200, 22)
    x, w = 170, 1010
    rows = [  # y, side label, color
        (100, "Outside", "#64748B"), (280, "The public", "#D97706"), (466, "City Hall", "#2563EB"),
        (682, "Police", "#6D28D9"), (898, "Facilities &amp; field", "#DB2777")]
    for y, text, color in rows:
        p.cell(lay, f"<b>{text}</b>", "text;html=1;align=right;verticalAlign=middle;fontSize=10;"
               f"fontColor={color};whiteSpace=wrap;{FONT}", 40, y, 120, 60)
    icon_card(p, lay, x, 92, 380, 76, "cloud", "Internet and SaaS",
                        "Email, files and meetings · staff and patrol cars on the VPN", 26, 12)
    state = icon_card(p, lay, x + 392, 92, 360, 76, "capitol", "State and county",
                      "The state police network · county 911 dispatch", 26, 12)
    p.cell(lay, "<b>Water plant</b><br>" + sub("The utility's own network: not connected", 10, "#3F6F82"),
                   boundary_style() + "verticalAlign=middle;spacingTop=0;", x + 764, 92, 246, 76)
    gate_bar(p, lay, x, 196, w, "<b>Security gate</b> · the firewall pair: everything between the outside and the "
             "city passes through it")
    public = p.cell(lay, "<b>The public</b> · residents and visitors: trusted by no one",
                    zone_style("#FDF8F3", "#F2CFA8", "#D97706", "top", 12), x, 246, w, 128)
    icon_card(p, lay, x + 16, 282, 480, 76, "guest", "Public Wi-Fi",
              "Lobby and council chamber: the internet, filtered, and nothing else")
    icon_card(p, lay, x + 514, 282, 480, 76, "book", "Library patrons",
              "Their own Wi-Fi, public PCs and internet line at the library")
    gate_bar(p, lay, x, 392, w, "<b>Same security gate</b> · between every group inside: the public, City Hall, "
             "police, building systems and traffic signals")
    city = p.cell(lay, "<b>City Hall</b> · the staff and the systems they run the city with",
                  zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), x, 442, w, 128)
    for n, (icon, title, text) in enumerate([
            ("laptop", "Staff computers", "Wired desks and staff Wi-Fi"), ("phone", "Phones", "Both wings"),
            ("payment-terminal", "Payment counters", "Utility billing and permits"),
            ("server", "City servers", "Files, finance, permits, backup")]):
        icon_card(p, lay, x + 16 + n * 248, 478, 232, 76, icon, title, text, 24, 11)
    gate_bar(p, lay, x, 588, w, "<b>Same security gate</b> · police systems have a wall of their own: only police "
             "devices, the state and dispatch get through")
    police = p.cell(lay, "<b>Police (CJIS)</b> · criminal justice information: walled off from everything else",
                    zone_style("#F5F3FF", "#C4B5FD", "#6D28D9", "top", 12), x, 638, w, 150)
    icon_card(p, lay, x + 16, 674, 480, 92, "badge", "Police workstations and servers",
              "Records and evidence in a locked cage in the data room, on their own network")
    icon_card(p, lay, x + 514, 674, 480, 92, "car", "Patrol cars",
                       "Laptops reach police records over an encrypted link with strong sign-in")
    gate_bar(p, lay, x, 806, w, "<b>Same security gate</b> · building systems, traffic signals and network management "
             "have their own doors, opened only for the people who need them")
    p.cell(lay, "<b>Facilities and field</b> · the systems that keep the buildings and streets running",
                   zone_style("#FDF4F9", "#F3B8D6", "#DB2777", "top", 12), x, 856, w, 150)
    icon_card(p, lay, x + 16, 892, 316, 92, "building", "Cameras, doors, HVAC",
              "Talk to their own servers only; never the internet")
    icon_card(p, lay, x + 346, 892, 316, 92, "signal-system", "Traffic signals",
              "42 intersections on city fiber; the vendor gets in by booked session")
    icon_card(p, lay, x + 676, 892, 318, 92, "wrench", "Network management",
                     "Reached only by IT, through the VPN with MFA")
    arrows = p.layer("Arrows")
    # Patrol cars and the state: in through the gate, to police only.
    p.edge(arrows, state, police, "endArrow=block;endFill=1;html=1;strokeColor=#7C3AED;strokeWidth=1.6;dashed=1;"
           "fontSize=9;fontColor=#4C1D95;labelBackgroundColor=#FFFFFF;" + FONT, "", exit=(0.9, 1), entry=(1, 0.35),
           points=[(886, 182), (1206, 182), (1206, 690.5)])
    p.cell(arrows, "<b>State, dispatch &amp; patrol cars</b>: to police only, named hosts ↓",
           "text;html=1;align=right;verticalAlign=middle;fontSize=9;fontColor=#6D28D9;" + FONT, 880, 198, 290, 26)
    # The public: no path to anything the city owns.
    p.edge(arrows, public, city, DENIED, "", exit=(0.82, 1), entry=(0.82, 0))
    x_mark(p, arrows, 998.2, 397)
    p.cell(arrows, "<b>No path</b> from the public to the city", "text;html=1;align=left;verticalAlign=middle;"
           "fontSize=9;fontColor=#991B1B;" + FONT, 1024, 392, 150, 30)
    # What this means for the city: Halvern's promises, on their own layer so a build marks them EXAMPLE
    rx = 1240
    promises = p.layer("Promises to the city (Halvern's; rewrite for your city)")
    p.cell(promises, "", "rounded=1;arcSize=2;html=1;fillColor=none;strokeColor=none;", rx - 12, 120, 724, 892)
    p.cell(lay, "What this means for the city", HEADING.replace("fontSize=12", "fontSize=14"), rx, 92, 700, 24)
    cards = [
        ("badge", "Police data stays behind its own wall",
         "Police systems sit in a locked cage on their own network. Only police devices, the state's router and "
         "one dispatch link get in, as the state's CJIS audit asks."),
        ("guest", "The public gets the internet and nothing else",
         "Lobby, council chamber and library Wi-Fi can't see city systems or each other."),
        ("payment-terminal", "Card payments touch one destination",
         "The counter terminals talk to the card processor only, which keeps the card audit small."),
        ("isp", "One internet line can fail and the counters stay open",
         "Two providers on different technologies; the backup takes over on its own."),
        ("power", "A storm doesn't take City Hall down",
         "A firewall pair, a core pair and three UPSes bridge the gap until the generator takes the load."),
        ("drop", "The water plant is not on this network",
         "The utility runs its own. No city system has a path into it, and none is drawn."),
    ]
    for n, (icon, title, text) in enumerate(cards):
        icon_card(p, promises, rx, 128 + n * 146, 700, 128, icon, title, text, 26, 12)
    p.title_block(p.layer("Border & title block"), "All", "Overview — city manager", f"1 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 2 logical
def vlan_rows(zone: str) -> list[list]:
    return [[(str(vid), f"{NETBOX}/ipam/vlans/?vid={vid}&site={S.SITE['slug']}"), name, subnet, gw]
            for vid, name, z, subnet, gw in S.VLANS if z == zone]


VLAN_COLS = [("VLAN", 44), ("NAME", 130), ("SUBNET", 132), ("GATEWAY", 110)]


def logical() -> Page:
    p = Page("logical", "2 · Logical — Zones, VLANs, Subnets", 2400, 1440, prefix="m")
    lb, lz = p.layer("Bands"), p.layer("Zones")
    lt = p.layer("VLAN tables")
    p.title(lb, f"{SITE} · {S.SITE['name']} — Logical",
            esc("Zones · VLANs · subnets · gateways. Every VLAN lives in one zone and every gateway is on the firewall, "
            "so every packet between departments is inspected. One-line rule per zone."))
    W = 1880
    bands = {"OUT": (96, 170), "EDGE": (282, 250), "PUBLIC": (548, 150), "CITY": (714, 184), "SAFETY": (914, 184),
             "FAC": (1114, 200)}
    for code, label, _ in S.BANDS:
        y, h = bands[code]
        p.band(lb, y, h, code, label.split(" · ")[0], W)
    # OUTSIDE: providers, the state and county, and the water plant boundary. No VLANs.
    zone_box(p, lz, "zone-internet", 100, 108, 900, 146)
    p.cell(lz, esc(S.ZONE["zone-internet"][5]), SMALL, 112, 132, 870, 18)
    for n, (icon, title, text) in enumerate([
            ("isp", "ISP-A", "DIA 1G · fiber"), ("isp", "ISP-B", "Cable 500/50"),
            ("cloud", "SaaS", "Mail, files, phones, card processor"),
            ("car", "VPN users", "Staff and patrol laptops · MFA")]):
        icon_card(p, lz, 112 + n * 220, 160, 210, 80, icon, title, text, 24, 11)
    zone_box(p, lz, "zone-partner", 1010, 108, 610, 146)
    p.cell(lz, esc(S.ZONE["zone-partner"][5]), SMALL, 1022, 132, 590, 18)
    for n, (icon, title, text) in enumerate([
            ("capitol", "State CJIS network", "State router in R03"), ("headset", "County dispatch", "County fiber 1G"),
            ("wrench", "Vendors", "Signal and records vendors")]):
        icon_card(p, lz, 1022 + n * 198, 160, 190, 80, icon, title, text, 24, 11)
    p.cell(lz, "<b>WATER</b> · " + esc(S.ZONE["zone-water"][2]), boundary_style(), 1630, 108, 260, 146)
    p.cell(lz, esc(S.ZONE["zone-water"][5]), SMALL.replace("#64748B", "#3F6F82"), 1642, 136, 236, 60)
    # EDGE: the firewall pair and its interfaces.
    zone_box(p, lz, "zone-edge", 100, 294, 1790, 226)
    p.cell(lz, esc(S.ZONE["zone-edge"][5]), SMALL, 112, 318, 900, 18)
    p.cell(lz, f"<b>{SITE}-FW</b> · HA pair (active / passive)",
           zone_style("#FFFFFF", "#94A3B8", "#334155", "top", 10), 112, 346, 300, 150)
    for n, name in enumerate((f"{SITE}-FW-01", f"{SITE}-FW-02")):
        device(p, p.layer("Devices"), name, 124, 376 + n * 60, 276, 52, ip=False, serial=False, pill=False)
    p.cell(lz, "<b>Firewall interfaces</b>", HEADING.replace("fontSize=12", "fontSize=10"), 440, 346, 300, 20)
    table(p, lt, 440, 370, [("INTERFACE", 150), ("ZONE", 110), ("VLAN", 110), ("IP / PREFIX", 240)], [
          ["ethernet1/3", "INTERNET", "—", "ISP-A, static from the provider"], ["ethernet1/4", "INTERNET", "—",
                                                                                "DHCP (ISP-B)"],
          ["ethernet1/1–1/2 (Po1 / Po2)", "all inside zones", "10–99 tagged", ".1 on every VLAN"],
          ["ethernet1/5", "PARTNER", "—", "to the state router (state's addressing)"],
          ["ethernet1/6", "PARTNER", "—", "county dispatch link"]], row_h=22)
    p.cell(lz, "<b>Remote access</b>", HEADING.replace("fontSize=12", "fontSize=10"), 1080, 346, 300, 20)
    table(p, lt, 1080, 370, [("POOL", 130), ("SUBNET", 120), ("WHO", 340)],
          [[name, subnet, who] for name, subnet, who in S.VPN_POOLS], row_h=22)
    # Inside zones with VLAN tables.
    layout = {"PUBLIC": ["zone-public"], "CITY": ["zone-staff", "zone-voice", "zone-pay", "zone-servers"],
              "SAFETY": ["zone-cjis"], "FAC": ["zone-building", "zone-field", "zone-mgmt"]}
    for code, zones in layout.items():
        y, h = bands[code]
        bw = (1790 - 10 * (len(zones) - 1)) / len(zones)
        for n, zone in enumerate(zones):
            zx = 100 + n * (bw + 10)
            z = S.ZONE[zone]
            zone_box(p, lz, zone, zx, y + 12, bw, h - 24, f"<b>ZONE {zone[5:].upper()}</b> · {esc(z[2])}")  # the build reads the zone tag from it
            p.cell(lz, esc(z[5]), SMALL, zx + 12, y + 36, bw - 24, 20)
            table(p, lt, zx + 12, y + 62, VLAN_COLS, vlan_rows(zone), row_h=22)
            lives = sub("Lives here: " + esc(z[4]), 9, "#64748B")
            if len(zones) > 2:
                p.cell(lz, lives, SMALL, zx + 12, y + h - 38, bw - 24, 20)
            else:
                p.cell(lz, lives, SMALL, zx + 452, y + 62, bw - 470, 40)
    legend(p, 2000, 96, [(z[1], *z[6]) for z in S.ZONES], flows=False)
    p.title_block(p.layer("Border & title block"), SITE, "Logical — zones, VLANs", f"2 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 3 physical
def physical() -> Page:
    p = Page("physical", "3 · Physical — Devices, Uplinks, Trunks", 3200, 1900, prefix="m")
    lb = p.layer("Bands")
    lz = p.layer("Zones (groups · stacks)")
    p.layer(LINKS)
    ld = p.layer("1 · Devices")
    for name in ("3 · Mgmt IPs (hide before sharing)", "3b · Serial numbers", "4 · Circuit IDs (hide before sharing)"):
        p.layer(name)
    p.title(lb, f"{SITE} · {S.SITE['name']} — Physical",
            esc("Devices · uplinks · port-channels · trunked VLANs · rack and U on every device. Police gear and cords "
            "are violet. Hover a device or Edit Data (Ctrl+M) for its NetBox record."))
    W = 2200
    p.band(lb, 96, 130, "ISP", "PROVIDERS", W)
    p.band(lb, 242, 788, "DATA-B", "DATA-B · BASEMENT DATA ROOM", W)
    p.band(lb, 1046, 170, "IDF", "IDF-C2 · IDF-PD", W)
    p.band(lb, 1232, 234, "AREAS", "ON THE FLOORS", W)
    lc = p.layer(LINKS)
    cids = p.layer("4 · Circuit IDs (hide before sharing)")

    # The firewall pair
    zone_box(p, lz, "zone-edge", 420, 262, 940, 118, f"<b>{SITE}-FW</b> · HA pair · R01 / R02", valign="bottom")
    fw1 = device(p, ld, f"{SITE}-FW-01", 460, 290, 250, 58)
    fw2 = device(p, ld, f"{SITE}-FW-02", 1010, 290, 250, 58)
    link(p, fw1, fw2, cable_by_label(f"{SITE}-CBL-00005"), "HA · 1G · Cat6", exit=(1, 0.5), entry=(0, 0.5),
         ports=("ha1", "ha1"), weight=1.4)

    # Providers: ISP-A, ISP-B and the county link hand off to both firewalls; the state's circuit ends on its router.
    looks = {"CH1-ISP-A-01": ("isp", "ISP-A"), "CH1-ISP-B-01": ("isp", "ISP-B"),
             "CH1-COUNTY-01": ("headset", "County dispatch"), "CH1-STATE-01": ("capitol", "State CJIS network")}
    box_x = {"CH1-ISP-A-01": 300, "CH1-ISP-B-01": 740, "CH1-COUNTY-01": 1160}
    circ_box = {}
    for cid, cx in box_x.items():
        circ = next(c for c in S.CIRCUITS if c["cid"] == cid)
        icon, title = looks[cid]
        circ_box[cid] = p.cell(ld, f"<b>{title}</b><br>{sub(esc(circ['label']))}",
                               label_style(icon, 26, 36, 11, "middle", 12) + "spacingTop=0;", cx, 140, 230, 60)
        p.cell(cids, f"CID {circ['cid']}<br>{esc(circ['provider'])} · {esc(circ['speed'])}", CID_TAG, cx + 236, 154,
               160, 32)
    state_circ = next(c for c in S.CIRCUITS if c["cid"] == "CH1-STATE-01")
    circ_box["CH1-STATE-01"] = p.cell(
        ld, f"<b>State CJIS network</b><br>{sub(esc(state_circ['label']))}",
        label_style("capitol", 26, 36, 11, "middle", 12).replace("strokeColor=#E2E8F0", "strokeColor=#C8C2BC;dashed=1")
        + "spacingTop=0;", 1985, 140, 210, 60)
    p.cell(cids, f"CID {state_circ['cid']}<br>{esc(state_circ['provider'])} · {esc(state_circ['speed'])}",
           CID_TAG.replace("align=left", "align=right"), 1770, 154, 166, 32)
    # Three lines into two firewalls cannot all run straight down without crossing, so two go round:
    # ISP-A reaches FW-02 over the top of the row, and the county reaches FW-01 over ISP-B and down the
    # gap beside it. Each route is (exit side, exit x, entry x on the firewall, corners).
    routes = {
        ("CH1-ISP-A-01", 0): (1, 500, 500, []),
        ("CH1-ISP-B-01", 0): (1, 760, 680, [(760, 224), (680, 224)]),
        ("CH1-COUNTY-01", 0): (0, 1200, 600, [(1200, 126), (718, 126), (718, 210), (600, 210)]),
        ("CH1-ISP-B-01", 1): (1, 950, 1040, [(950, 224), (1040, 224)]),
        ("CH1-COUNTY-01", 1): (1, 1180, 1080, [(1180, 210), (1080, 210)]),
        ("CH1-ISP-A-01", 1): (0, 415, 1120, [(415, 116), (1580, 116), (1580, 238), (1120, 238)]),
    }
    ports = {"CH1-ISP-A-01": "e1/3", "CH1-ISP-B-01": "e1/4", "CH1-COUNTY-01": "e1/6"}
    for (cid, m), (side, sx, tx, corners) in routes.items():
        circ = next(c for c in S.CIRCUITS if c["cid"] == cid)
        fw = (fw1, fw2)[m]
        style = (EDGE.replace("strokeColor=#64748B", "strokeColor=#94A3B8").replace("strokeWidth=1.6", "strokeWidth=1.4")
                 + "labelBackgroundColor=#DBEAFE;labelBorderColor=#2563EB;")
        port = ports[cid].replace("e", "ethernet")
        attrs = {"object": "circuits.circuit", "cid": circ["cid"], "status": "active",
                 "x_handoff": f"{SITE}-FW-0{m + 1}:{port}", "x_speed": circ["speed"],
                 "x_media": circ["media"], "x_patch_a": "", "x_patch_b": ""}
        attrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in attrs.items()), **attrs,
                 "link": f"{NETBOX}/circuits/circuits/?cid={circ['cid']}", "linkTarget": "_blank"}
        eid = p.edge(lc, circ_box[cid], fw, style, "", attrs, exit=((sx - box_x[cid]) / 230, side),
                     entry=((tx - (460, 1010)[m]) / 250, 0), points=corners)
        p.edge_label(eid, ports[cid], 1, 0, PORT_LABEL)

    # Core pair
    core = stack(p, lz, f"{SITE}-CORE", 560, 462, 640, [f"{SITE}-CORE-1", f"{SITE}-CORE-2"], "zone-mgmt",
                 "C9500-24Y4C ×2 · StackWise Virtual · DATA-B R01 / R02")
    link(p, fw1, core, cable_by_label(f"{SITE}-CBL-00001"), exit=(0.5, 1), entry=(0.2, 0),
         points=[(585, 420), (688, 420)], ports=("e1/1–1/2", "Twe1/0/1 · 2/0/1"), bundle=(688, 448))
    link(p, fw2, core, cable_by_label(f"{SITE}-CBL-00003"), exit=(0.5, 1), entry=(0.8, 0),
         points=[(1135, 420), (1072, 420)], ports=("e1/1–1/2", "Twe1/0/2 · 2/0/2"), bundle=(1072, 448))

    # Police cage R03, right: the state's router, the police host and storage, and the cage's own UPS.
    # 238 wide, under the 240 the build labels with a location note, which would sit on the state's line.
    p.cell(lz, "<b>R03 · POLICE CAGE</b><br>" + sub("Police badge door · IT escorted", 9, "#6D28D9"),
           "rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#F5F3FF;strokeColor=#6D28D9;strokeWidth=2.5;dashed=1;"
           "dashPattern=2 3;verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontSize=10;fontColor=#6D28D9;"
           "html=1;whiteSpace=wrap;" + FONT, 1970, 252, 238, 412)
    rtr = device(p, ld, f"{SITE}-STATE-RTR", 1985, 296, 210, 70,
                 label="<b>%name%</b><br>" + sub("%device_type%") + "<br>"
                       + '<font style="font-size:9px" color="#B45309"><b>STATE-MANAGED</b> · drawn, not configured</font>')
    rtr_el = p.find(rtr).find("mxCell")
    rtr_el.set("style", rtr_el.get("style").replace("strokeColor=#E2E8F0", "strokeColor=#D97706;dashed=1"))
    pdhv = device(p, ld, f"{SITE}-PD-HV-01", 1985, 400, 210, 58)
    pdnas = device(p, ld, f"{SITE}-PD-NAS-01", 1985, 480, 210, 58)
    ups3 = device(p, ld, f"{SITE}-UPS-03", 1985, 584, 210, 58)
    p.edge(lc, circ_box["CH1-STATE-01"], rtr, EDGE.replace("strokeColor=#64748B", "strokeColor=#A8A29E").replace(
        "strokeWidth=1.6", "strokeWidth=1.4") + "dashed=1;labelBackgroundColor=#F5F5F4;labelBorderColor=#C8C2BC;",
           "100M · fiber", {"object": "circuits.circuit", "cid": state_circ["cid"], "status": "active",
                            "x_handoff": state_circ["handoff"], "x_speed": state_circ["speed"],
                            "x_media": state_circ["media"], "x_patch_a": "", "x_patch_b": "",
                            "link": f"{NETBOX}/circuits/circuits/?cid={state_circ['cid']}", "linkTarget": "_blank"},
           exit=(0.5, 1), entry=(0.5, 0))
    # FW-02 straight across; FW-01 round the outside of everything above it, so it crosses nothing.
    link(p, fw2, rtr, cable_by_label(f"{SITE}-CBL-00035"), "1G · Cat6", exit=(1, 0.5), entry=(0, 0.7),
         points=[(1700, 319), (1700, 345)], ports=("e1/5", "Gi0/1/1", (14, 0), (-22, 0)))
    fw1_rtr = [(460, 319), (270, 319), (270, 106), (1955, 106), (1955, 313.5), (1985, 313.5)]
    link(p, fw1, rtr, cable_by_label(f"{SITE}-CBL-00034"), "1G · Cat6", exit=(0, 0.5), entry=(0, 0.25),
         points=fw1_rtr[1:-1], ports=("e1/5", "Gi0/1/0", (-14, 0), (-22, 0)), pos=label_at(fw1_rtr, 2, 0.12))
    # The core's right side: five links 18 apart, each port name just outside the card.
    link(p, core, pdhv, cable_by_label(f"{SITE}-CBL-00031"), exit=(1, 0.1), entry=(0, 0.5),
         points=[(1950, 471), (1950, 429)], ports=("Twe1/0/15 · 2/0/15", "nic1–2", (58, 0), (-18, 0)),
         bundle=(1212, 471))
    link(p, core, pdnas, cable_by_label(f"{SITE}-CBL-00033"), "25G · DAC", exit=(1, 0.3), entry=(0, 0.5),
         points=[(1940, 489), (1940, 509)], ports=("Twe1/0/16", "port1", (24, 0), (-18, 0)))

    # Building systems under the core, fed from the floor 1 stack beside them.
    c1 = stack(p, lz, f"{SITE}-ACC-C1", 90, 650, 330, [f"{SITE}-ACC-C1-1", f"{SITE}-ACC-C1-2"], "zone-staff",
               "C9300-48P ×2 · City Hall floor 1 · DATA-B R02")
    link(p, core, c1, cable_by_label(f"{SITE}-CBL-00011"), exit=(0, 0.5), entry=(0.5, 0),
         points=[(255, 507)], ports=("Twe1/0/11 · 2/0/11", "Te1/1/1 · 2/1/1", (-42, 0)), bundle=(255, 610))
    zone_box(p, lz, "zone-building", 470, 630, 620, 120, "<b>BLDG</b> · cameras record here; nothing reaches the "
             "internet")
    nvr = device(p, ld, f"{SITE}-NVR-01", 486, 662, 190, 58)
    door = device(p, ld, f"{SITE}-DOOR-01", 686, 662, 190, 58)
    bas = device(p, ld, f"{SITE}-BAS-01", 886, 662, 190, 58)
    link(p, c1, nvr, cable_by_label(f"{SITE}-CBL-00041"), "1G", exit=(1, 0.456), entry=(0, 0.5),
         ports=("2/0/45", "eth0"))
    link(p, c1, door, cable_by_label(f"{SITE}-CBL-00042"), "DOOR · 1G", exit=(1, 0.84), entry=(0.5, 1),
         points=[(781, 725.6)], ports=("2/0/46", "eth0"))
    link(p, c1, bas, cable_by_label(f"{SITE}-CBL-00043"), "HVAC · 1G", exit=(1, 0.93), entry=(0.5, 1),
         points=[(981, 733.7)], ports=("2/0/47", "eth0"))

    # Traffic signals, below: the central system on the core, its cabinets out on city fiber.
    zone_box(p, lz, "zone-field", 470, 790, 620, 130, "<b>FIELD</b> · traffic signal central system")
    p.cell(lz, sub("42 signal cabinets on city fiber, drawn on sheet 6; the vendor gets in by booked session "
           "only (F17).", 9, "#A16207"), SMALL, 486, 822, 290, 60)
    tsc = device(p, ld, f"{SITE}-TSC-01", 790, 826, 200, 58)
    path = [(1100, 552), (1100, 855), (990, 855)]   # label on the short run in, clear of the corridor
    link(p, core, tsc, cable_by_label(f"{SITE}-CBL-00044"), "10G · Cat6A", exit=((1100 - 560) / 640, 1),
         entry=(1, 0.5), points=path[1:2], ports=("", "nic1"), pos=label_at(path, 1, 0.58))

    # City servers, right: nested elbows off the core's right side, so no two links cross.
    # Title at the bottom and the backup line in left of centre: the lines from above clear the title
    # and the NetBox location note the build adds at the top right.
    zone_box(p, lz, "zone-servers", 1250, 630, 706, 120, "<b>SERVERS</b> · two hosts and the backup appliance",
             valign="bottom")
    hv1 = device(p, ld, f"{SITE}-HV-01", 1266, 662, 210, 58)
    hv2 = device(p, ld, f"{SITE}-HV-02", 1488, 662, 210, 58)
    bkp = device(p, ld, f"{SITE}-BKP-01", 1710, 662, 200, 58)
    link(p, core, bkp, cable_by_label(f"{SITE}-CBL-00025"), "BKP · 10G · DAC", exit=(1, 0.5), entry=(0.15, 0),
         points=[(1740, 507)], ports=("Twe1/0/14", "port1", (24, 0)))
    link(p, core, hv2, cable_by_label(f"{SITE}-CBL-00023"), exit=(1, 0.7), entry=(0.5, 0),
         points=[(1593, 525)], ports=("Twe1/0/22 · 2/0/22", "nic1–2", (42, 0)), bundle=(1593, 648))
    link(p, core, hv1, cable_by_label(f"{SITE}-CBL-00021"), exit=(1, 0.9), entry=(0.5, 0),
         points=[(1371, 543)], ports=("Twe1/0/21 · 2/0/21", "nic1–2", (42, 0)), bundle=(1371, 648))

    # Management and power, below the servers: down the gap beside them, then up into each card.
    zone_box(p, lz, "zone-mgmt", 1250, 790, 706, 120, "<b>MGMT &amp; POWER</b> · on the core, in the racks")
    ups1 = device(p, ld, f"{SITE}-UPS-01", 1266, 826, 210, 58)
    ups2 = device(p, ld, f"{SITE}-UPS-02", 1488, 826, 210, 58)
    oob = device(p, ld, f"{SITE}-OOB-01", 1710, 826, 200, 58)
    for n, (dev, label, ports, name) in enumerate([(ups1, "00051", ("1/0/20", "nmc"), "UPS1"),
                                                   (ups2, "00052", ("2/0/20", "nmc"), "UPS2"),
                                                   (oob, "00054", ("1/0/19", "net1"), "OOB")]):
        x = 1190 - n * 10
        y = 940 + n * 12
        target = (1371, 1593, 1810)[n]
        path = [(x, 552), (x, y), (target, y), (target, 884)]
        # Labels on the runs across, staggered so neighbours 12 apart never touch.
        link(p, core, dev, cable_by_label(f"{SITE}-CBL-{label}"), f"{name} · {ports[0]} · 1G",
             exit=((x - 560) / 640, 1), entry=(0.5, 1), points=path[1:3], ports=("", ports[1]),
             pos=label_at(path, 1, ((1282, 1490, 1700)[n] - x) / (target - x)))
    path = [(1160, 552), (1160, 976), (2090, 976), (2090, 642)]
    link(p, core, ups3, cable_by_label(f"{SITE}-CBL-00053"), "UPS3 · 2/0/19 · 1G",
         exit=((1160 - 560) / 640, 1), entry=(0.5, 1), points=path[1:3], ports=("", "nmc"),
         pos=label_at(path, 1, (1950 - 1160) / (2090 - 1160)))
    note(p, 1250, 988, 690, 30, "Console lines (not cables in NetBox): OOB-01 serial 1–4 to FW-01, FW-02, "
         "CORE-1, CORE-2 · LTE to IT. UPS runtime: R01 about 20 min, R02 about 24, R03 about 30; the generator "
         "transfer switch takes the load within a minute.")

    # The two wing closets: floor 2 straight under the core's corridor, police along to the right.
    c2 = stack(p, lz, f"{SITE}-ACC-C2", 1100, 1074, 330, [f"{SITE}-ACC-C2-1", f"{SITE}-ACC-C2-2"], "zone-staff",
               "C9300-48P ×2 · IDF-C2 R01")
    # Its label sits below the corridor's last run across (Po13 at 1038), where no other line passes.
    link(p, core, c2, cable_by_label(f"{SITE}-CBL-00013"), "Po12 · 2×10G · MMF OM4", exit=((1120 - 560) / 640, 1),
         entry=(20 / 330, 0), ports=("", "Te1/1/1 · 2/1/1"), bundle=(1120, 1068),
         pos=label_at([(1120, 552), (1120, 1074)], 0, (1056 - 552) / (1074 - 552)))
    pd = stack(p, lz, f"{SITE}-ACC-PD", 1730, 1074, 330, [f"{SITE}-ACC-PD-1", f"{SITE}-ACC-PD-2"], "zone-cjis",
               "C9300-48P ×2 · IDF-PD R01 · police badge only")
    link(p, core, pd, cable_by_label(f"{SITE}-CBL-00015"), "Po13 · 2×10G · MMF OM4 · VLANs " + S.PD_TRUNK,
         exit=((1140 - 560) / 640, 1), entry=(0.5, 0), points=[(1140, 1038), (1895, 1038)],
         ports=("", "Te1/1/1 · 2/1/1"), bundle=(1895, 1062))

    # Areas: one card per kind of end device, the build counts the rest. Drops leave the stack
    # left to right and drop to nested levels, so none cross.
    ends = [("City Hall floor 1", 90, 800, 90, 330, c1,
             [f"{SITE}-AP-C1-01", f"{SITE}-PRN-C1-01", f"{SITE}-CAM-C1-01", f"{SITE}-PAY-01"]),
            ("City Hall floor 2", 1080, 630, 1100, 330, c2,
             [f"{SITE}-AP-C2-01", f"{SITE}-PRN-C2-01", f"{SITE}-CAM-C2-01"]),
            ("Police wing", 1722, 424, 1730, 330, pd, [f"{SITE}-AP-PD-01", f"{SITE}-PRN-PD-01"])]
    for area, fx, fw, sx, sw_w, sw, names in ends:
        police = area == "Police wing"
        p.cell(lz, f"<b>{area}</b> · one card per kind; the build shows how many",
               zone_style("#F5F3FF" if police else "#FFFFFF", "#C4B5FD" if police else "#E2E8F0",
                          "#6D28D9" if police else "#334155", "bottom", 10), fx, 1240, fw, 210)
        bottom = (650 if sw == c1 else 1074) + 90   # the stack's lower edge: two members, 90 tall
        for n, name in enumerate(names):
            d = DEV[name]
            x = fx + 14 + n * 192
            cid = device(p, ld, name, x, 1336, 180, 52, small=True, pill=False,
                         label='<b>%name%</b><br>' + sub("%device_type%"))
            c = CABLE_OF[name][0]
            sw_port = c["a"][0].split(":")[1]
            vlan = S.access_vlan(d["role"], d["tags"])
            text = f"{c['speed']} · {c['media']}" + (f" · {vlan}" if vlan else " · trunk")
            ex_x = sx + (14 if sw == c1 else 44 if sw == pd else 30) + n * 60
            level = 1316 - n * 12   # below the area's NetBox location note (top right, to 1258)
            path = [(ex_x, bottom), (ex_x, level), (x + 90, level), (x + 90, 1336)]
            # Floor 1's stack is up in the data room: its labels go on the runs across, by the cards.
            link(p, sw, cid, c, text, exit=((ex_x - sx) / sw_w, 1), entry=(0.5, 0), points=path[1:3],
                 ports=(sw_port.replace("Gi", ""), "eth0"), weight=1.2, color="#A78BFA" if police else "#94A3B8",
                 pos=label_at(path, 1) if sw == c1 else None)

    # Registers and legend, right
    rx = 2260
    lr = p.layer("6 · Link register")
    link_card = p.cell(lr, "", CARD, rx, 96, 900, 400)
    p.cell(lr, "<b>Link register</b> — port-channels, members, speed, trunked VLANs", HEADING, rx + 14, 106, 860, 22)
    rows = []
    short = {f"{SITE}-BKP-01": "BKP", f"{SITE}-NVR-01": "NVR", f"{SITE}-DOOR-01": "DOOR", f"{SITE}-BAS-01": "HVAC",
             f"{SITE}-TSC-01": "TSC", f"{SITE}-UPS-01": "UPS1", f"{SITE}-UPS-02": "UPS2", f"{SITE}-UPS-03": "UPS3",
             f"{SITE}-OOB-01": "OOB", f"{SITE}-PD-NAS-01": "PDNAS", f"{SITE}-STATE-RTR": "STATE"}
    infra_cables = [c for c in S.CABLES if not c["labels"][0] >= f"{SITE}-CBL-00101"]
    for c in infra_cables:
        a_dev = sorted({e.split(":")[0].replace(f"{SITE}-", "") for e in c["a"]})
        b_dev = sorted({e.split(":")[0].replace(f"{SITE}-", "") for e in c["b"]})
        a_ports = " · ".join(e.split(":")[1] for e in c["a"])
        b_ports = " · ".join(e.split(":")[1] for e in c["b"])
        name = c["lag"] or short.get(c["b"][0].split(":")[0], "")
        speed = c["speed"] + (" LACP" if c["lag"].startswith("Po") else "")
        ids = ", ".join(f"#{S.CABLES.index(c) * 2 + k + 1}" for k in range(len(c["labels"])))
        rows.append([name, ids, f"{'/'.join(a_dev)} {a_ports}", f"{'/'.join(b_dev)} {b_ports}", speed, c["media"],
                     "connected",
                     c["vlans"] or ("heartbeat" if c["lag"] == "HA" else "routed (state)" if "STATE" in name
                                    else f"access {S.access_vlan(DEV[c['b'][0].split(':')[0]]['role'], DEV[c['b'][0].split(':')[0]]['tags'])}")])
    table(p, lr, rx + 14, 134, [("LINK", 52), ("CABLE ID", 60), ("A-SIDE (MEMBERS)", 190), ("B-SIDE (MEMBERS)", 176),
          ("SPEED", 84), ("MEDIA", 66), ("STATUS", 70), ("TRUNKED VLANS", 172)], rows, row_h=22)
    note(p, rx + 14, 134 + p.table_height + 8, 860, 32, "All trunks: native VLAN 999 (unused) · explicit allowed list · "
         "LACP fast. The police trunk (Po13) carries 20, 60, 62 and 99 only. End-device drops are in NetBox, not here.")
    bottom = 134 + p.table_height + 8 + 32 + 14
    resize(p, link_card, bottom - 96)
    la = p.layer("7 · Asset register")
    ends_roles = ("access-point", "printer", "camera", "payment-terminal")
    reg = [d["name"] for d in S.DEVICES if d["role"] not in ends_roles]
    top = bottom + 14
    asset_card = p.cell(la, "", CARD, rx, top, 900, 400)
    p.cell(la, "<b>Asset register</b> — mirrors each device's NetBox record", HEADING, rx + 14, top + 10, 860, 22)
    rows = []
    role_word = {"ups": "UPS", "nvr": "NVR", "hvac-controller": "HVAC controller", "signal-system": "Signal system"}
    for name in reg:
        d = DEV[name]
        role = role_word.get(d["role"], d["role"].replace("-", " ").capitalize())
        rows.append([name, role, d["device_type"], d["serial"], d["primary_ip4"].split("/")[0], d["location"],
                     d["rack"], f"U{d['position']}" if d["position"] else "", d["cf_sw_version"]])
    table(p, la, rx + 14, top + 36, [("HOSTNAME", 120), ("ROLE", 110), ("MODEL", 160), ("SERIAL", 96), ("MGMT IP", 84),
          ("ROOM", 70), ("RACK/CAB", 58), ("U", 36), ("SW", 136)], rows, row_h=20)
    resize(p, asset_card, 36 + p.table_height + 16)
    ly = top + 36 + p.table_height + 16 + 14
    h = legend(p, rx, ly, [(z[1], *z[6]) for z in S.ZONES], flows=False)
    height = int(max(1560, ly + h + 120))
    p.height = height
    p.model.set("pageHeight", str(height))
    p.title_block(p.layer("Border & title block"), SITE, "Physical — devices, links", f"3 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 3d wireless
def wireless() -> Page:
    p = Page("wireless", "3d · Wireless — APs and SSIDs", 2400, 1120, prefix="m")
    lb, ld = p.layer("Floors"), p.layer("1 · Devices")
    p.layer("Zones")
    p.layer("3 · Mgmt IPs (hide before sharing)")
    p.layer("3b · Serial numbers")
    p.title(lb, f"{SITE} · {S.SITE['name']} — Wireless",
            esc("Access points per area · SSIDs and the zone each one lands in. Police Wi-Fi is broadcast in the "
            "police wing only."))
    # A build rewrites this card from the site's wireless_management / wireless_manager fields.
    cloud = icon_card(p, lb, 450, 96, 600, 70, "cloud", "Cloud Wi-Fi management",
                      "Configuration, firmware and the public splash page from the vendor's cloud · APs reach it over "
                      "HTTPS", attrs={"netdiagrams_wireless_mgmt": "1"})
    areas = [("City Hall floor 1", "C1-01", "CH1-ACC-C1", "11, 70",
              "HALVERN-STAFF and HALVERN-PUBLIC; the council chamber AP is one of them"),
             ("City Hall floor 2", "C2-01", "CH1-ACC-C2", "11, 70", "HALVERN-STAFF and HALVERN-PUBLIC"),
             ("Police wing", "PD-01", "CH1-ACC-PD", "62", "PD-SECURE only")]
    for n, (area, ap, sw, trunk, ssids) in enumerate(areas):
        fx, fy = 24 + n * 520, 210
        police = area == "Police wing"
        p.cell(lb, f"<b>{area}</b> · APs on {sw}: PoE, trunk {trunk} (native 99)",
               zone_style("#F5F3FF" if police else "#FFFFFF", "#C4B5FD" if police else "#E2E8F0",
                          "#6D28D9" if police else "#334155", "top", 11), fx, fy, 504, 190)
        device(p, ld, f"{SITE}-AP-{ap}", fx + 16, fy + 40, 300, 60, small=True, pill=False,
               label="<b>%name%</b><br>" + sub("%device_type% · one card per area; the build counts them"))
        p.cell(lb, sub(f"Broadcasts {esc(ssids)}. Each AP's switch port, cable and address are in the AP register "
               "below, rebuilt from NetBox on every run.", 10), SMALL, fx + 16, fy + 112, 472, 60)
    la = p.layer("AP register")
    aps = [d["name"] for d in S.DEVICES if d["role"] == "access-point"]
    ry = 430
    p.cell(la, "", CARD, 24, ry, 1520, 60 + 22 * (len(aps) + 1))
    p.cell(la, "<b>AP register</b> — every access point, its switch port and cable", HEADING, 40, ry + 10, 1480, 22)
    rows = []
    for name in aps:
        d = DEV[name]
        c = CABLE_OF[name][0]
        sw, port = c["a"][0].split(":")
        rows.append([name, d["device_type"], d["serial"], d["primary_ip4"].split("/")[0], d["location"],
                     f"{sw.replace(f'{SITE}-', '')} {port}", c["labels"][0]])
    table(p, la, 40, ry + 36, [("NAME", 200), ("MODEL", 140), ("SERIAL", 160), ("MGMT IP", 150), ("LOCATION", 150),
          ("SWITCH PORT", 380), ("CABLE", 300)], rows, row_h=22)
    p.edge(p.layer("2 · Management"), cloud, None, "endArrow=none;html=1;strokeColor=#94A3B8;strokeWidth=1.2;"
           "dashed=1;fontSize=9;fontColor=#475569;labelBackgroundColor=#FFFFFF;" + FONT, "AP management",
           exit=(0.5, 1), tgt_pt=(750, 210))
    lt = p.layer("SSID table")
    p.cell(lt, "", CARD, 1580, 210, 796, 330)
    p.cell(lt, "<b>SSIDs</b> — one per zone, never one for everything", HEADING, 1596, 220, 760, 22)
    rows = [[ssid, str(vlan), S.ZONE[zone][1], sec, notes] for ssid, sec, vlan, zone, notes in S.SSIDS]
    table(p, lt, 1596, 250, [("SSID", 120), ("VLAN", 120), ("ZONE", 70), ("SECURITY", 200), ("NOTES", 250)], rows,
          row_h=30)
    note(p, 1596, 250 + p.table_height + 12, 760, 120, "<b>Rules</b><br>· HALVERN-PUBLIC: client isolation, splash "
         "page, content filter, 10 Mb/s per client; lands in PUBLIC only.<br>· PD-SECURE: EAP-TLS with police "
         "device certificates; broadcast by the police wing APs only.<br>· No SSID for cameras, door controllers, "
         "HVAC or card terminals: they are wired.<br>· Rogue AP detection on; management VLAN 99 is never broadcast.")
    legend(p, 1580, 560, [(z[1], *z[6]) for z in S.ZONES], flows=False)
    p.title_block(p.layer("Border & title block"), SITE, "Wireless — APs, SSIDs", f"3d of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 4 flows
VERDICT = {"Allow": ("#16A34A", "endArrow=block;endFill=1;", "Permitted"),
           "Conditional": ("#EA580C", "dashed=1;endArrow=block;endFill=1;", "Conditional"),
           "Deny": ("#DC2626", "dashed=1;endArrow=none;", "Denied")}


def flows() -> Page:
    p = Page("flows", "4 · Traffic Flows — who talks to whom", 2400, 60 + 96 + 46 * len(S.FLOWS) + 150, prefix="m")
    lb, lf = p.layer("Lanes"), p.layer("Flows")
    p.title(lb, f"{SITE} · {S.SITE['name']} — Traffic flows",
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
            x_mark(p, lf, 760, y + 10)
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
    p.title_block(p.layer("Border & title block"), SITE, "Traffic flows", f"4 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 5 failover
def failover() -> Page:
    p = Page("failover", "5 · Failover scenarios", 2400, 1060, prefix="m")
    lb = p.layer("Scenarios")
    p.title(lb, f"{SITE} · {S.SITE['name']} — Failover",
            esc("What happens when one thing breaks, storm included: what fails, what takes over, and what people "
            "at the counters and in the patrol cars notice."))
    scenarios = [
        ("isp", "ISP-A goes down", "Fiber cut or provider outage on CH1-ISP-A-01.",
         "The firewall pair moves internet traffic to ISP-B (cable 500/50) within about 30 seconds; staff and patrol "
         "VPN sessions rebuild over ISP-B.",
         "Calls in progress drop and redial. Patrol laptops reconnect on their own. The state link and county "
         "dispatch are separate circuits and carry on."),
        ("firewall", "CH1-FW-01 fails", "Power supply, disk or a bad update on the active firewall.",
         "CH1-FW-02 takes over the gateway addresses (.1 on every VLAN), both internet lines, the state router "
         "link and the dispatch link; sessions carry on.",
         "A few seconds of pause. VPN users, in the building and in patrol cars, may need to reconnect."),
        ("core-switch", "A core member fails", "CH1-CORE-1 or CH1-CORE-2 dies or is rebooted (StackWise Virtual).",
         "Every port-channel (Po1, Po2, Po11, Po12, Po13, Po15, Po21, Po22) keeps its link on the other member at "
         "half speed.", "Nothing, apart from the single links on that member: the backup appliance, the evidence "
         "storage, the signal system and the management drops."),
        ("power", "The storm: utility power fails", "Wind takes the feed; the civic center's generator starts.",
         "The three UPSes carry the data room (about 20, 24 and 30 minutes at today's load) while the transfer "
         "switch moves the building to the generator, usually within a minute. The wing closets are on the "
         "generator circuit too.",
         "Lights flicker; the network stays up. If the generator fails to start, shut down city servers first "
         "and the police rack last."),
        ("console-server", "Nobody can reach the firewall", "A bad change or an outage cuts IT off from the network.",
         "IT dials CH1-OOB-01 over its own LTE link and reaches the firewall and core consoles on serial lines, "
         "with nothing in between.", "Nothing, if IT gets in before the counters open."),
        ("router", "The state circuit goes down", "The state's line or its router in R03 fails.",
         "Nothing on the city side takes over: the circuit and the router are the state's. Police call the state "
         "help desk; dispatch keeps running on the county link.",
         "Officers can't run state and national queries from the car or the station until the state restores it."),
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
    p.title_block(p.layer("Border & title block"), SITE, "Failover scenarios", f"5 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 6 the city's buildings and links
def multisite() -> Page:
    p = Page("multisite", "6 · City buildings and links", 2400, 1400, prefix="m")
    lb, lc, ll = p.layer("Sites"), p.layer("Cards"), p.layer("Links")
    p.title(lb, "City of Halvern — Buildings and links",
            esc("The civic center is the hub: the library, the public works yard and the fire stations reach it on "
            "city-owned fiber. The state and county links end there too. The water plant is the utility's own "
            "network and is never connected."))
    inet = icon_card(p, lc, 860, 100, 520, 80, "globe", "Internet", "ISP-A and ISP-B at the civic center · the "
                     "library's own filtered line", 30, 13)
    hub = p.cell(lc, "<b>CH1 · Halvern Civic Center</b> · 10.30.0.0/15 (city 10.30, police 10.31) · about 180 staff<br>"
                 + sub("City Hall and police in one building · firewall HA pair · core pair · police cage R03"),
                 zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), 760, 400, 720, 190)
    for n, (icon, title, text) in enumerate([("firewall", "CH1-FW HA pair", "Every link ends here"),
                                             ("badge", "Police cage R03", "State router · records"),
                                             ("signal-system", "Signal central", "42 intersections")]):
        icon_card(p, lc, 780 + n * 232, 466, 218, 92, icon, title, text, 24, 11)
    # Partners, left: the state network and county dispatch, drawn as an edge with one door each.
    state = p.cell(lc, "<b>State CJIS network</b><br>" + sub("The state's circuit and router; the state draws the "
                   "rest", 10), boundary_style("#F5F5F4", "#78716C") + "verticalAlign=middle;", 100, 240, 520, 80)
    county = p.cell(lc, "<b>County 911 dispatch</b><br>" + sub("County fiber 1G · one CAD host to one records "
                    "host (F11)", 10), boundary_style("#F5F5F4", "#78716C") + "verticalAlign=middle;", 100, 400, 520,
                    80)
    water = p.cell(lc, "<b>Water treatment plant</b> · boundary<br>" + sub("The utility's own network and its "
                   "SCADA. Out of scope: no city zone has a path into it (F20).", 10, "#3F6F82"),
                   boundary_style() + "verticalAlign=middle;", 1720, 240, 520, 96)
    saas = icon_card(p, lc, 1720, 420, 520, 80, "cloud", "SaaS and VPN users",
                     "Mail, files, card processor · staff and patrol laptops on the VPN", 30, 13)
    # City fiber sites, along the bottom.
    sites = [(lib, icon, title, text) for lib, icon, title, text in (
        ("LB1", "book", "LB1 · Main Library", "Patron Wi-Fi and public PCs on their own filtered line; staff to "
                                              "City Hall"),
        ("PW1", "truck", "PW1 · Public Works Yard", "Shops, fuel and the signal cabinet fiber ring"),
        ("FS1", "truck", "FS1 · Fire Station 1", "Station alerting, staff and crew Wi-Fi"),
        ("FS2", "truck", "FS2 · Fire Station 2", "Same build as FS1"),
        ("FS3", "truck", "FS3 · Fire Station 3", "Same build as FS1"))]
    boxes = {}
    for n, (code, icon, title, text) in enumerate(sites):
        boxes[code] = icon_card(p, lc, 56 + n * 432, 720, 400, 92, icon, title, text, 28, 12)
    fiber = ("html=1;strokeColor=#2563EB;strokeWidth=2.5;endArrow=none;fontSize=10;fontColor=#1E3A8A;"
             "labelBackgroundColor=#FFFFFF;" + FONT)
    partner = ("html=1;strokeColor=#78716C;strokeWidth=2;dashed=1;dashPattern=8 4;endArrow=none;fontSize=10;"
               "fontColor=#44403C;labelBackgroundColor=#FFFFFF;" + FONT)
    plain_line = ("html=1;strokeColor=#94A3B8;strokeWidth=1.4;endArrow=none;fontSize=10;fontColor=#475569;"
                  "labelBackgroundColor=#FFFFFF;" + FONT)
    for n, code in enumerate(boxes):
        cx = 256 + n * 432
        hx = 760 + 720 * (0.1 + 0.2 * n)
        p.edge(ll, boxes[code], hub, fiber, "City fiber",
               exit=(0.5, 0), entry=(0.1 + 0.2 * n, 1), points=[(cx, 660 - abs(n - 2) * 14), (hx, 660 - abs(n - 2) * 14)])
    p.edge(ll, state, hub, partner, "State circuit 100M · F09", exit=(1, 0.5), entry=(0, 0.2),
           points=[(690, 280), (690, 438)])
    p.edge(ll, county, hub, partner, "County fiber 1G · F11", exit=(1, 0.5), entry=(0, 0.6))
    p.edge(ll, inet, hub, plain_line, "ISP-A + ISP-B", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(ll, saas, hub, plain_line, "HTTPS · VPN + MFA", exit=(0, 0.5), entry=(1, 0.5), points=[(1600, 460),
                                                                                                    (1600, 495)])
    p.edge(ll, water, hub, DENIED, "No connection", exit=(0, 0.5), entry=(1, 0.15), points=[(1560, 288),
                                                                                               (1560, 428.5)])
    x_mark(p, ll, 1550, 330)
    lt = p.layer("Site table")
    p.cell(lt, "<b>Sites and links</b>", HEADING, 100, 880, 2040, 22)
    rows = [[(code, f"{NETBOX}/dcim/sites/?slug={code.lower()}") if code in ("CH1", "LB1") else code,
             name, prefix, internet, link_text] for code, name, prefix, internet, link_text in S.CITY_SITES]
    table(p, lt, 100, 906, [("CODE", 90), ("SITE", 240), ("PREFIX", 180), ("INTERNET", 560), ("LINK TO CH1", 970)],
          rows, row_h=26)
    p.title_block(p.layer("Border & title block"), "All", "City buildings and links", f"6 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 7 flow register
ZONE_ORDER = ["zone-internet", "zone-partner", "zone-water", "zone-public", "zone-staff", "zone-voice", "zone-pay",
              "zone-servers", "zone-cjis", "zone-building", "zone-field", "zone-mgmt"]
MATRIX = {  # (from, to): (verdict, flows)
    ("zone-staff", "zone-internet"): ("allow", "F01"), ("zone-staff", "zone-servers"): ("allow", "F02 F19"),
    ("zone-public", "zone-internet"): ("allow", "F03"), ("zone-pay", "zone-internet"): ("cond", "F05"),
    ("zone-voice", "zone-internet"): ("allow", "F07"), ("zone-cjis", "zone-partner"): ("cond", "F09"),
    ("zone-internet", "zone-cjis"): ("cond", "F10"), ("zone-partner", "zone-cjis"): ("cond", "F11"),
    ("zone-cjis", "zone-internet"): ("cond", "F13"), ("zone-building", "zone-internet"): ("deny", "F15"),
    ("zone-partner", "zone-field"): ("cond", "F17"), ("zone-field", "zone-internet"): ("deny", "F18"),
    ("zone-internet", "zone-mgmt"): ("cond", "F21"), ("zone-mgmt", "zone-internet"): ("cond", "F23 F24"),
}
for _z in ("zone-staff", "zone-voice", "zone-pay", "zone-servers", "zone-building", "zone-field", "zone-mgmt"):
    MATRIX[("zone-public", _z)] = ("deny", "F04")
MATRIX[("zone-public", "zone-cjis")] = ("deny", "F04 F12")
for _z in ("zone-staff", "zone-servers"):
    MATRIX[("zone-pay", _z)] = ("deny", "F06")
for _z in ("zone-staff", "zone-voice", "zone-building"):
    MATRIX[("zone-field", _z)] = ("deny", "F18")
for _z in ("zone-staff", "zone-building"):
    MATRIX[(_z, "zone-cjis")] = ("deny", "F12")
for _z in ZONE_ORDER:
    if _z != "zone-water":
        MATRIX[(_z, "zone-water")] = ("deny", "F20")


def register() -> Page:
    p = Page("register", "7 · Flow register & standards", 2400, 1600, prefix="m")  # height set once measured
    lf, lm, ls = p.layer("Flow register"), p.layer("Zone matrix"), p.layer("Standards")
    p.title(lf, f"{SITE} · {S.SITE['name']} — Flow register and standards",
            esc("The segmentation in writing: every permitted conversation, its conditions and owner, then default "
            "deny. The zone matrix is the same rules as a grid. Naming and drawing standards at the right."))
    flow_card = p.cell(lf, "", CARD, 24, 92, 1500, 400)
    p.cell(lf, "<b>Flow register</b>", HEADING, 40, 102, 1460, 22)
    look = {"Allow": "#15803D", "Conditional": "#B45309", "Deny": "#B91C1C"}
    rows = [[fid, src, dst, what, f'<font color="{look[v]}"><b>{v}</b></font>', cond, owner]
            for fid, src, dst, what, v, cond, owner in S.FLOWS]
    rows.append(["—", "Any", "Any", "Everything not listed above", '<font color="#B91C1C"><b>Deny</b></font>',
                 "Default deny, logged", "IT"])
    table(p, lf, 40, 128, [("ID", 44), ("FROM", 200), ("TO", 190), ("WHAT", 340), ("VERDICT", 90),
          ("CONDITIONS", 400), ("OWNER", 196)], rows, row_h=26)
    resize(p, flow_card, 36 + p.table_height + 16)
    my = 92 + 36 + p.table_height + 16 + 24
    n = len(ZONE_ORDER)
    matrix_card = p.cell(lm, "", CARD, 24, my, 1500, 400)
    p.cell(lm, "<b>Zone matrix</b> — rows start the conversation, columns answer; blank is "
           "default deny", HEADING, 40, my + 10, 1460, 22)
    cols = [("FROM \\ TO", 116)] + [(S.ZONE[z][1], 112) for z in ZONE_ORDER]
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
    height = int(my + 40 + p.table_height + 16 + 140)
    sx = 1560
    std_card = p.cell(ls, "", CARD, sx, 92, 816, 560)
    p.cell(ls, "<b>Naming and drawing standards</b>", HEADING, sx + 16, 102, 780, 22)
    table(p, ls, sx + 16, 128, [("ITEM", 170), ("STANDARD", 610)], [
          ["Site code", "Two letters and a digit: CH1 civic center, LB1 library, PW1 public works, FS1–FS3 fire "
                        "stations"],
          ["Device", "SITE-ROLE-NN: CH1-FW-01, CH1-PD-HV-01 (police gear carries PD)"],
          ["Stack", "SITE-ACC-AREA: CH1-ACC-C1, -C2, -PD; members -1, -2"],
          ["Cable label", "SITE-CBL-nnnnn on both ends: CH1-CBL-00015"],
          ["Zone tag", "zone-&lt;name&gt; on every device, VLAN and prefix"],
          ["VLAN", "Tens per department: 10s staff, 20 voice, 25 payments, 40s servers, 60s police, 70s public, "
                   "80s building, 90 signals, 99 management"],
          ["Subnet", "10.30 city, 10.31 police, 10.32 field, 10.40 library; public Wi-Fi from 172.20"],
          ["Gateway", ".1 on the firewall pair, for every VLAN"],
          ["Police", "Rack R03 and IDF-PD: police badge, city IT escorted; violet cords; the police trunk carries "
                     "20, 60, 62 and 99 only"],
          ["Boundary", "State, county and water: drawn as one box and one edge; never opened up"],
          ["Link pill", "Po · speed · media; port tags at each end"],
          ["Hide before sharing", "Layers 3 (mgmt IPs) and 4 (circuit IDs)"],
          ["Change", "Edit NetBox, then rebuild; never fix the drawing alone"]], row_h=30)
    resize(p, std_card, 36 + p.table_height + 16)
    p.height = height
    p.model.set("pageHeight", str(height))
    p.title_block(p.layer("Border & title block"), SITE, "Flow register and standards", f"7 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ main
def build() -> ET.Element:
    return mxfile((overview(), logical(), physical(), wireless(), flows(), failover(), multisite(), register()),
                  "netdiagrams municipal template")


def main() -> None:
    tree = build()
    ET.indent(tree, space=" ")
    OUT.write_text(ET.tostring(tree, encoding="unicode") + "\n", "utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
