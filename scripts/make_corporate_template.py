"""Generate src/netdiagrams/data/C01-Corporate-Template.drawio, the corporate standard.

Eight sheets drawn for the fictional Sable Ridge HQ campus (site C01): overview,
logical, physical, wireless, traffic flows, failover, the multi-site WAN and the
flow register. Every fact comes from scripts/corporate_template/site.py, the same
source scripts/make_corporate_sample.py turns into the sample NetBox export, so
`netdiagrams build --input sample-corporate.json` reproduces the template. The
riser sheet (3e) is not drawn here: a build makes it from NetBox's location tree.

    python scripts/make_corporate_template.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from corporate_template import site as S  # noqa: E402
from drawkit import (  # noqa: E402
    BAND, FONT, MONO, NETBOX, NOTE, POINTS, Page, _svg, esc, mxfile, sub, zone_style)
from make_office_template import (  # noqa: E402  (the office kit: styles, icons, tables, links)
    BODY_CELL, CARD, CID_TAG, HEADING, ICONS as OFFICE_ICONS, IP_TAG, KEY_CELL, SMALL, SN_TAG, TEXT, _circle,
    _line, _rect, gate_bar, group_style, link, note, resize, table)
from netdiagrams.graph import font_size, row_height  # noqa: E402

# ------------------------------------------------------------------ icons: the office set plus the company's own
VIOLET, INDIGO, NAVY, CYAN, BROWN, GREEN, RED = "#6D28D9", "#4338CA", "#3949AB", "#0891B2", "#92400E", "#16A34A", \
    "#B91C1C"
ICONS = dict(OFFICE_ICONS)
ICONS.update({
    "sdwan-hub": _svg("#EDE7FD", _rect(6, 9, 20, 14, VIOLET, rx=3) + _line("10,13 22,19", VIOLET) + _line("10,19 22,13", VIOLET)
                      + _circle(10, 13, 1.3, VIOLET, VIOLET) + _circle(10, 19, 1.3, VIOLET, VIOLET)
                      + _circle(22, 13, 1.3, VIOLET, VIOLET) + _circle(22, 19, 1.3, VIOLET, VIOLET)),
    "distribution-switch": _svg("#E4E6FB", _rect(6, 9, 20, 14, INDIGO, rx=3) + _line("16,12 16,20", INDIGO)
                                + _line("10,16 22,16", INDIGO) + _line("13.5,13.5 16,11.5 18.5,13.5", INDIGO)
                                + _line("13.5,18.5 16,20.5 18.5,18.5", INDIGO)),
    "dc-leaf": _svg("#E4E7F7", _rect(6, 8, 20, 7, NAVY, rx=2) + _rect(6, 17, 20, 7, NAVY, rx=2)
                    + _line("9.5,11.5 14,11.5", NAVY) + _line("9.5,20.5 14,20.5", NAVY)
                    + _circle(21, 11.5, 1.1, NAVY, NAVY) + _circle(21, 20.5, 1.1, NAVY, NAVY)),
    "wireless-controller": _svg("#E0F2F6", _rect(6, 16, 20, 9, CYAN, rx=2.5) + _circle(11, 20.5, 1.1, CYAN, CYAN)
                                + _line("19.5,11.6 18.3,10.6 16,10 13.7,10.6 12.5,11.6", CYAN)
                                + _line("22.5,9 20.3,7.1 16,6 11.7,7.1 9.5,9", CYAN)),
    "bms-controller": _svg("#F6EEE6", _rect(8, 6, 16, 20, BROWN, rx=2) + _circle(16, 19.5, 3, BROWN)
                           + _line("16,9.5 16,16.5", BROWN) + _line("12,10 13.5,10", BROWN)
                           + _line("12,13 13.5,13", BROWN)),
    "badge": _svg("#FBE4EF", _rect(9, 6, 14, 20, "#DB2777", rx=2) + _rect(12, 10, 8, 5, "#DB2777", rx=1)
                  + _line("12,19 20,19", "#DB2777") + _line("12,22 17,22", "#DB2777")),
    "scale": _svg("#FEE2E2", _line("16,7 16,25", RED) + _line("8,11 24,11", RED) + _line("8,11 5.5,17 10.5,17 8,11", RED)
                  + _line("24,11 21.5,17 26.5,17 24,11", RED) + _line("12,25 20,25", RED)),
    "datacenter": _svg("#E2F3EF", _rect(7, 6, 8, 20, "#047857", rx=1.5) + _rect(17, 6, 8, 20, "#047857", rx=1.5)
                       + _line("9.5,10 12.5,10", "#047857") + _line("9.5,14 12.5,14", "#047857")
                       + _line("19.5,10 22.5,10", "#047857") + _line("19.5,14 22.5,14", "#047857")),
})
ICON_FOR_ROLE = {"firewall": "firewall", "sdwan-hub": "sdwan-hub", "core-switch": "core-switch",
                 "distribution-switch": "distribution-switch", "access-switch": "access-switch", "dc-leaf": "dc-leaf",
                 "wireless-controller": "wireless-controller", "access-point": "access-point",
                 "hypervisor": "hypervisor", "storage": "storage", "backup-appliance": "backup", "ups": "ups",
                 "console-server": "console-server", "printer": "printer", "nvr": "nvr", "camera": "camera",
                 "door-controller": "badge", "bms-controller": "bms-controller", "room-system": "room-system"}


def label_style(icon: str, size: int = 22, left: int = 28, font: int = 10, valign: str = "top", arc: int = 12) -> str:
    return (f"shape=label;rounded=1;absoluteArcSize=1;arcSize={arc};fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;"
            f"shadow=1;align=left;verticalAlign={valign};spacingTop=5;spacingLeft={left};fontSize={font};fontColor=#0F172A;"
            f"whiteSpace=wrap;html=1;{POINTS}{FONT}image=data:image/svg+xml,{ICONS[icon]};imageWidth={size};"
            f"imageHeight={size};imageAlign=left;imageVerticalAlign=middle;")


DEVICE_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 30, 38, 11)  # noqa: E731
SMALL_CARD = lambda role: label_style(ICON_FOR_ROLE.get(role, "server"), 22, 28, 10)  # noqa: E731
MEMBER_ROW = lambda role: label_style(ICON_FOR_ROLE.get(role, "access-switch"), 16, 22, 9)  # noqa: E731


def icon_card(p: Page, layer: str, x, y, w, h, icon: str, title: str, text: str, size=28, title_size=12,
              attrs: dict | None = None) -> str:
    style = label_style(icon, size, size + 18, title_size, "middle", 16) + "spacingTop=0;"
    return p.cell(layer, f"<b>{esc(title)}</b><br>{sub(esc(text), 10)}", style, x, y, w, h, attrs=attrs)


LEGEND_ITEMS = [("firewall", "Firewall pair"), ("sdwan-hub", "SD-WAN hub"), ("core-switch", "Core switch"),
                ("distribution-switch", "Distribution (SVL)"), ("access-switch", "Access stack"),
                ("dc-leaf", "DC leaf (vPC)"), ("wireless-controller", "Wireless controller"),
                ("access-point", "AP (local mode)"), ("hypervisor", "Virtualization host"), ("storage", "Storage"),
                ("backup", "Backup appliance"), ("ups", "UPS"), ("console-server", "Out-of-band console"),
                ("printer", "Printer / MFP"), ("nvr", "Video recorder"), ("camera", "Camera"),
                ("badge", "Badge controller"), ("bms-controller", "BMS controller"),
                ("room-system", "Meeting-room system"), ("cloud", "Cloud / SaaS")]


def legend(p: Page, x: float, y: float, flows: bool = True) -> float:
    """Icons, line meanings and the 20 zone colors. Returns its height."""
    layer = p.layer("Legend")
    rows = -(-len(LEGEND_ITEMS) // 2)
    lines = [("#64748B", 1.6, "", "Link · pill = Po · speed · media · port tags at the ends"),
             ("#64748B", 2.5, "", "Weight = speed (thicker = 10G and up)")]
    if flows:
        lines += [("#16A34A", 1.6, "endArrow=block;endFill=1;", "Permitted flow (initiator → responder)"),
                  ("#EA580C", 1.6, "dashed=1;endArrow=block;endFill=1;", "Conditional (MFA · one destination)"),
                  ("#DC2626", 1.6, "dashed=1;", "Denied path")]
    zone_rows = -(-len(S.ZONES) // 5)
    h = 40 + rows * 24 + 6 + len(lines) * 22 + 10 + zone_rows * 26 + 14
    p.cell(layer, "", CARD, x, y, 420, h)
    p.cell(layer, "Legend", HEADING, x + 16, y + 10, 200, 22)
    for n, (icon, text) in enumerate(LEGEND_ITEMS):
        col, row = n % 2, n // 2
        p.cell(layer, esc(text),
               f"shape=label;html=1;fillColor=none;strokeColor=none;align=left;verticalAlign=middle;spacingLeft=24;"
               f"fontSize=10;fontColor=#334155;{FONT}image=data:image/svg+xml,{ICONS[icon]};imageWidth=18;imageHeight=18;"
               "imageAlign=left;imageVerticalAlign=middle;", x + 14 + col * 200, y + 36 + row * 24, 194, 24)
    ly = y + 36 + rows * 24 + 6
    for color, width, extra, text in lines:
        p.edge(layer, None, None, f"endArrow=none;html=1;strokeColor={color};strokeWidth={width};{extra}",
               src_pt=(x + 18, ly + 10), tgt_pt=(x + 58, ly + 10))
        if "Denied" in text:
            p.cell(layer, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
                   "fontSize=10;fontStyle=1;" + FONT, x + 64, ly, 20, 20)
        p.cell(layer, esc(text), "text;html=1;fontSize=10;fontColor=#334155;align=left;"
               "verticalAlign=middle;" + FONT, x + 88, ly, 320, 20)
        ly += 22
    ly += 10
    for n, z in enumerate(S.ZONES):
        fill, stroke, font = z[6]
        col, row = n % 5, n // 5
        p.cell(layer, esc(z[1]),
               f"rounded=1;absoluteArcSize=1;arcSize=12;fillColor={fill};strokeColor={stroke};fontColor={font};"
               "fontSize=8;fontStyle=1;html=1;whiteSpace=wrap;" + FONT, x + 14 + col * 79, ly + row * 26, 75, 22)
    return h


DATA = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data"
OUT = DATA / "C01-Corporate-Template.drawio"
DATE = "2026-10-18"
PROJECT = "Corporate network standard"
SHEETS = 8
SITE = f"{S.SITE['code']} · {S.SITE['name']}"

DEV = S.DEV
CABLE_OF = defaultdict(list)
for _c in S.CABLES:
    for _end in _c["a"] + _c["b"]:
        CABLE_OF[_end.split(":")[0]].append(_c)
ATTR_ORDER = ["name", "role", "manufacturer", "device_type", "platform", "serial", "asset_tag", "status", "site",
              "location", "rack", "position", "face", "primary_ip4", "virtual_chassis", "vc_position", "description",
              "tags", "cf_sw_version", "cf_support_contract", "cf_lifecycle", "x_modules", "x_power"]
ZONE_LOOK = {z[0]: z[6] for z in S.ZONES}
TAGS = ("3 · Mgmt IPs (hide before sharing)", "3b · Serial numbers")
LINKS = "2 · Links (Po · speed · VLANs)"


# ------------------------------------------------------------------ objects
def dev_attrs(name: str) -> dict:
    d = DEV[name]
    a = {k: str(d.get(k, "") or "") for k in ATTR_ORDER}
    a["site"] = S.SITE["code"]
    a["face"] = "front" if d.get("position") else ""
    for key in ("cf_ap_mode", "cf_criticality"):
        if d.get(key):
            a[key] = d[key]
    tooltip = "\n".join(f"{k}: {v}" for k, v in a.items())
    return {"placeholders": "1", "tooltip": tooltip, **a, "link": f"{NETBOX}/dcim/devices/?name={name}",
            "linkTarget": "_blank"}


def device(p: Page, layer: str, name: str, x, y, w=300, h=58, small=False, label=None, ip=True, serial=True,
           pill=True) -> str:
    d = DEV[name]
    style = (SMALL_CARD if small else DEVICE_CARD)(d["role"])
    cid = p.cell(layer, label or ('<b>%name%</b><br>' + sub("%device_type%")), style, x, y, w, h, dev_attrs(name))
    if pill and d.get("rack"):
        p.cell(cid, "%rack% · U%position%", "rounded=1;absoluteArcSize=1;arcSize=8;fillColor=#EEF2F7;strokeColor=none;"
               "fontSize=7.5;fontColor=#475569;html=1;" + FONT, w - 64, 6, 58, 13, {"placeholders": "1"})
    if ip and d.get("primary_ip4"):
        p.cell(p.layer(TAGS[0]), d["primary_ip4"].split("/")[0], IP_TAG, x + (30 if small else 40), y + h - 18, 110, 14)
    if serial and d.get("serial"):
        p.cell(p.layer(TAGS[1]), f"SN {d['serial']}", SN_TAG, x + w - 116, y + h - 18, 110, 14)
    return cid


def member_rows(p: Page, parent: str, x0, y0, w, names: list[str], cols: int = 1, words=None,
                ip_head: float | None = None) -> list[str]:
    """Device rows inside a group: name, rack and U, the serial (lifted to its layer by a build) and the IP tag.

    A stack's rows are too full for the IP tag: ``ip_head`` (the group's width) puts it in the group's header."""
    ids = []
    for n, m in enumerate(names):
        d = DEV[m]
        col, row = n % cols, n // cols
        rx, ry = x0 + col * (w + 8), y0 + 26 * row
        word = f" · {words[n]}" if words else ""
        text = (f"<b>%name%</b>{word} <span style=\"color:#94A3B8;font-family:JetBrains Mono;font-size:9px\">"
                f"&nbsp;{'%rack% ' if d['rack'] else ''}U%position% · SN %serial%</span>")
        rid = p.cell(parent, text, MEMBER_ROW(d["role"]), rx, ry, w, 22, dev_attrs(m))
        ids.append(rid)
        if d.get("primary_ip4"):
            gx, gy = absolute(p, rid)
            tx, ty = (gx - x0 + ip_head - 94, gy - ry + 19) if ip_head else (gx + w - 194, gy + 4)
            p.cell(p.layer(TAGS[0]), d["primary_ip4"].split("/")[0], IP_TAG.replace("align=left", "align=right"),
                   tx, ty, 84, 14)
    return ids


def absolute(p: Page, cid: str) -> tuple[float, float]:
    """A cell's page position, through its containers."""
    x = y = 0.0
    while cid and cid not in p.layers.values():
        el = p.find(cid)
        cell = el if el.tag == "mxCell" else el.find("mxCell")
        geo = cell.find("mxGeometry")
        x, y = x + float(geo.get("x", 0)), y + float(geo.get("y", 0))
        cid = cell.get("parent")
    return x, y


def group_box(p: Page, layer: str, zone: str, x, y, w, h, title: str, attrs: dict | None = None) -> str:
    fill, stroke, font = ZONE_LOOK[zone]
    return p.cell(layer, title, group_style(fill, stroke, font), x, y, w, h, attrs)


def stack(p: Page, layer: str, vc: str, x, y, w, members: list[str], zone: str, note_text: str) -> str:
    fill, stroke, font = ZONE_LOOK[zone]
    first = DEV[members[0]]
    h = 34 + 26 * len(members) + 4
    sid = p.cell(layer, f"%name%<br>{sub(esc(note_text), 9, '#64748B')}", group_style(fill, stroke, font), x, y, w, h,
                 {"placeholders": "1", "tooltip": f"NetBox virtual chassis {vc} · {first['location']} {first['rack']}",
                  "object": "dcim.virtualchassis", "name": vc, "location": first["location"], "rack": first["rack"],
                  "link": f"{NETBOX}/dcim/virtual-chassis/?name={vc}", "linkTarget": "_blank"})
    words = ["active", "standby"] + ["member"] * (len(members) - 2)
    member_rows(p, sid, 10, 34, w - 20, members, words=words, ip_head=w)
    return sid


def cable(name: str, a_dev: str = "") -> dict:
    """The link of that name (Po11, P2P-NS-E); a port-channel on several boxes picks the one on ``a_dev``."""
    found = [c for c in S.CABLES if c["name"] == name and (not a_dev or any(e.startswith(a_dev + ":")
                                                                            for e in c["a"] + c["b"]))]
    if len(found) == 1:
        return found[0]
    merged = dict(found[0])
    merged["labels"] = [lb for c in found for lb in c["labels"]]
    merged["a"] = [e for c in found for e in c["a"]]
    merged["b"] = [e for c in found for e in c["b"]]
    return merged


def cables(*names: str) -> dict:
    """Several links drawn as one edge (a cluster's port-channels to the leaf pair)."""
    found = [cable(n) for n in names]
    return {**found[0], "labels": [lb for c in found for lb in c["labels"]], "a": [e for c in found for e in c["a"]],
            "b": [e for c in found for e in c["b"]]}


def zone_box(p: Page, layer: str, zone: str, x, y, w, h, title=None) -> str:
    fill, stroke, font = ZONE_LOOK[zone]
    z = S.ZONE[zone]
    return p.cell(layer, title if title is not None else f"<b>ZONE {z[1]}</b> · {esc(z[2])}",
                  zone_style(fill, stroke, font, "top", 10), x, y, w, h)


VERTICAL = "horizontal=0;"   # a link pill set on its edge's vertical run, reading upward


def pill_at(p: Page, eid: str, pos: float) -> str:
    """Move a link's pill along it (-1 source .. 1 target), off a crossing."""
    cell = p.find(eid)
    (cell if cell.tag == "mxCell" else cell.find("mxCell")).find("mxGeometry").set("x", f"{pos:g}")
    return eid


def vlink(p, src, dst, c, text=None, pos: float | None = None, **kw) -> str:
    """A link whose pill reads up its vertical run (lanes and channels too narrow for a flat pill); ``pos`` moves
    the pill along the line (-1 source .. 1 target)."""
    eid = link(p, src, dst, c, text, **kw)
    cell = p.find(eid)
    cell = cell if cell.tag == "mxCell" else cell.find("mxCell")
    cell.set("style", cell.get("style") + VERTICAL)
    return pill_at(p, eid, pos) if pos is not None else eid


# ------------------------------------------------------------------ 1 overview
def overview() -> Page:
    p = Page("overview", "1 · Overview — for the board", 2160, 1180, prefix="c")
    lay = p.layer("Overview")
    p.cell(lay, "How the company network is protected", "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;"
           "fontSize=22;fontColor=#0F172A;fontStyle=1;spacing=2;" + FONT, 24, 18, 1200, 32)
    p.cell(lay, "For the board, the auditors and our clients: no technical detail. The HQ campus, the DR site, "
           "Lakeview and every branch follow this design.", "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;"
           "fontSize=12;fontColor=#64748B;spacing=2;" + FONT, 24, 52, 1250, 22)
    x, w = 170, 1110
    slot = lambda n: x + 16 + n * 272  # noqa: E731  (four card slots across a band box)
    rows = [(92, "Outside", "#64748B"), (262, "Users", "#2563EB"), (482, "Data center", "#047857"),
            (702, "Shared &amp; building", "#D97706"), (922, "Management", "#0891B2")]
    for y, text, color in rows:
        p.cell(lay, f"<b>{text}</b>", "text;html=1;align=right;verticalAlign=middle;fontSize=10;"
               f"fontColor={color};whiteSpace=wrap;{FONT}", 40, y, 120, 76)
    outside = icon_card(p, lay, x, 92, w, 76, "cloud", "Internet, the cloud and our other sites",
                        "SaaS for email, files and meetings · the client portal and analytics in the cloud · the DR "
                        "site, Lakeview and 14 branches · about 600 people a day working remotely · the security "
                        "monitoring service, which reads our logs in the cloud and has no way in")
    gate_bar(p, lay, x, 186, w, "<b>Edge gate</b> · the edge firewall pair: everything between the internet and the "
             "company passes through it, including the client portal, the extranet and remote access")
    users = p.cell(lay, "<b>Users</b> · who you are decides where you land, not which desk you sit at",
                   zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), x, 232, w, 136)
    icon_card(p, lay, slot(0), 268, 800, 80, "users", "Corporate staff",
              "Consulting, accounting and audit, and the business teams: laptops, phones and printers on every floor",
              26, 12)
    legal_users = icon_card(p, lay, slot(3), 268, 256, 80, "scale", "Legal practice",
                            "Sable Ridge Legal: its own network by identity, on any floor", 26, 12)
    gate_bar(p, lay, x, 406, w, "<b>Internal gate</b> · the internal firewall pair: between staff, the data center, "
             "the legal systems, building systems and management. Every crossing is checked and logged")
    dc = p.cell(lay, "<b>Data center</b> · every system tier sits behind the internal gate",
                zone_style("#F2FAF8", "#A8DACA", "#047857", "top", 12), x, 452, w, 136)
    icon_card(p, lay, slot(0), 488, 256, 80, "datacenter", "Business applications",
              "Practice management and billing: the financial systems", 26, 12)
    icon_card(p, lay, slot(1), 488, 256, 80, "storage", "Files and databases",
              "Reached only by the applications and backup", 26, 12)
    icon_card(p, lay, slot(2), 488, 256, 80, "backup", "Backups",
              "Can't be altered; copied to the DR site", 26, 12)
    legal_sys = icon_card(p, lay, slot(3), 488, 256, 80, "lock", "Legal systems",
                          "Documents and matters, on their own servers", 26, 12)
    same = p.find(gate_bar(p, lay, x, 626, w, "<b>Same internal gate</b> · guests, meeting rooms and building systems "
                           "each sit behind it, with their own doors"))
    same.set("style", same.get("style").replace("align=left", "align=right;spacingRight=16"))  # clear of the guests' ✕
    p.cell(lay, "<b>Shared spaces and building systems</b> · used by everyone, trusted by no one",
           zone_style("#FDF8F3", "#F2CFA8", "#D97706", "top", 12), x, 672, w, 136)
    icon_card(p, lay, slot(0), 708, 256, 80, "guest", "Guest Wi-Fi",
                      "The internet and nothing else", 26, 12)
    icon_card(p, lay, slot(1), 708, 256, 80, "room-system", "Meeting rooms",
              "Cloud meetings; staff can cast to them", 26, 12)
    icon_card(p, lay, slot(2), 708, 528, 80, "building", "Building systems",
              "Cameras, badge doors and the building controls: facilities and their contractor only, in through "
              "the edge gate with MFA", 26, 12)
    gate_bar(p, lay, x, 846, w, "<b>Management door</b> · only from the privileged jump hosts, with MFA, and "
             "every session recorded")
    p.cell(lay, "<b>Management</b> · the controls of the network itself",
           zone_style("#F0FAFC", "#A5DCE8", "#0891B2", "top", 12), x, 892, w, 136)
    icon_card(p, lay, slot(0), 928, 528, 80, "wrench", "Network management",
              "Firewalls, switches, Wi-Fi, power and server consoles; named admins only", 26, 12)
    icon_card(p, lay, slot(2), 928, 528, 80, "console-server", "Out-of-band access",
              "A cellular back door to the consoles that works when the network doesn't; every login logged", 26, 12)
    arrows = p.layer("Arrows")
    # The ethical wall: a line between corporate staff and everything legal, through the internal gate.
    wall_x = slot(3) - 9
    p.edge(arrows, None, None, "endArrow=none;html=1;strokeColor=#DC2626;strokeWidth=2.5;dashed=1;dashPattern=6 4;",
           src_pt=(wall_x, 252), tgt_pt=(wall_x, 584))
    p.cell(arrows, "<b>Ethical wall</b><br>staff can't reach legal systems",
           "rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#FEF2F2;strokeColor=#FCA5A5;fontColor=#991B1B;"
           "fontSize=9;html=1;whiteSpace=wrap;" + FONT, wall_x - 80, 370, 160, 34)
    p.edge(arrows, legal_users, legal_sys, "endArrow=block;endFill=1;html=1;strokeColor=#16A34A;strokeWidth=1.6;",
           exit=(0.5, 1), entry=(0.5, 0))
    # Guests: no path to anything inside.
    # From the shared spaces' edge (clear of its title) up to the data center: crossed out at the gate.
    p.edge(arrows, None, None, "endArrow=none;html=1;strokeColor=#DC2626;strokeWidth=1.6;dashed=1;",
           src_pt=(slot(0) + 128, 672), tgt_pt=(slot(0) + 128, 588))
    p.cell(arrows, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
           "fontSize=10;fontStyle=1;" + FONT, slot(0) + 118, 636, 20, 20)
    p.cell(arrows, "No path from guests to anything inside", "text;html=1;align=left;verticalAlign=middle;"
           "fontSize=9;fontColor=#991B1B;fontStyle=1;labelBackgroundColor=#F1F5F9;" + FONT,
           slot(0) + 144, 600, 230, 20)
    # Remote staff: in through the edge gate with MFA, then the same rules as at their desk.
    p.edge(arrows, outside, users, "endArrow=block;endFill=1;html=1;strokeColor=#7C3AED;strokeWidth=1.6;dashed=1;",
           exit=(1, 0.7), entry=(1, 0.5), points=[(1306, 145.2), (1306, 300)])
    p.cell(arrows, "<b>Remote staff</b>: in through the edge gate with MFA ↓",
           "text;html=1;align=right;verticalAlign=middle;fontSize=9;fontColor=#6D28D9;" + FONT, 990, 176, 280, 14)
    rx = 1340
    promises = p.layer("Business promises (Sable Ridge's; rewrite for your company)")
    p.cell(promises, "", "rounded=1;arcSize=2;html=1;fillColor=none;strokeColor=none;", rx - 12, 120, 784, 916)
    p.cell(lay, "What this means for the business", HEADING.replace("fontSize=12", "fontSize=14"), rx, 92, 760, 24)
    cards = [
        ("scale", "Legal files are walled off from the rest of the firm",
         "Only legal staff reach the legal systems; inside them, each matter's team sees only its own files."),
        ("datacenter", "The financial systems sit behind their own gate",
         "Practice management and billing are reached on named ports only, and every change is logged."),
        ("guest", "Guests and visitors never reach anything inside",
         "Guest Wi-Fi goes to the internet and nowhere else, on every site."),
        ("shield", "No one gets in through an unrecorded door",
         "Admins work from recorded jump hosts with MFA; the monitoring service has no way in; the building "
         "contractor comes through the edge with MFA."),
        ("power", "One broken box or cut cable is a ticket, not an outage",
         "Firewalls, core switches and controllers come in pairs; the buildings are joined by two fiber routes."),
        ("backup", "If the data center goes dark, the company restarts from the DR site",
         "The DR site holds copies of the systems and the backups, and has its own internet line."),
        ("isp", "Branches keep working if a line fails",
         "Every branch has two or three internet lines and tunnels to both hubs."),
    ]
    for n, (icon, title, text) in enumerate(cards):
        icon_card(p, promises, rx, 128 + n * 128, 760, 112, icon, title, text, 26, 12)
    p.title_block(p.layer("Border & title block"), "All", "Overview — the board", f"1 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 2 logical
VLAN_COLS = [("VLAN", 42), ("NAME", 112), ("VRF", 62), ("SUBNET", 108), ("GATEWAY", 140)]


def vlan_rows(zone: str) -> list[list]:
    ssid = {vid: s for s, _, vid, *_ in S.SSIDS}
    return [[(str(vid), f"{NETBOX}/ipam/vlans/?vid={vid}&site=c01"),
             name + (f" · SSID {ssid[vid]}" if vid in ssid else ""), vrf or "—", subnet, gw]
            for vid, name, vrf, z, subnet, gw in S.VLANS if z == zone]


def table_h(cols, rows, row_h=22) -> float:
    text = lambda v: v[0] if isinstance(v, tuple) else str(v)  # noqa: E731
    return 22 + sum(row_height([(text(v), w - 4) for (_, w), v in zip(cols, r)], font_size(BODY_CELL), row_h)
                    for r in rows)


def zone_card(p: Page, lz, lt, zone: str, x, y, w, h, cols=None, rows=None) -> None:
    z = S.ZONE[zone]
    zone_box(p, lz, zone, x, y, w, h)
    p.cell(lz, esc(z[5]), SMALL, x + 12, y + 26, w - 24, 20)
    rows = vlan_rows(zone) if rows is None else rows
    if rows:
        table(p, lt, x + 12, y + 50, cols or VLAN_COLS, rows, row_h=22)
    p.cell(lz, sub("Lives here: " + esc(z[4]), 9, "#64748B"), SMALL, x + 12, y + h - 34, w - 24, 28)


def logical() -> Page:
    W, X0 = 2600, 100
    p = Page("logical", "2 · Logical — Zones, VRFs, VLANs, Subnets", 3340, 1800, prefix="c")
    lb, lz, lt = p.layer("Bands"), p.layer("Zones"), p.layer("VLAN tables")
    p.title(lb, f"{SITE} — Logical",
            esc("Zones · VRFs · VLANs · subnets · gateways. The big zones are VRFs on the routed core; VRFs meet "
                "only at a firewall: the internal pair inside, the edge pair outside. Every data center VLAN's "
                "gateway is on the internal pair, so every tier-to-tier packet is inspected."))
    widths = lambda n: (W - 10 * (n - 1)) / n  # noqa: E731
    y = 96
    # OUTSIDE: providers, the SD-WAN overlay and the cloud; prefixes, no VLANs.
    out_cols = {"zone-internet": [("PREFIX", 120), ("NAME", 120), ("GATEWAY", 140)],
                "zone-wan": [("SEGMENT", 80), ("VRF", 62), ("HUBS", 230), ("UNDERLAYS", 170)],
                "zone-cloud": [("NETWORK", 140), ("PREFIX", 110), ("WHAT", 280)]}
    out_rows = {"zone-internet": [[pfx, name, gw] for pfx, name, _, z, gw in S.PREFIXES if z == "zone-internet"],
                "zone-wan": [["CORP", "CORP", "C01-SDW (primary) · C02-SDW (secondary)", "DIA, broadband, 5G"],
                             ["LEGAL", "LEGAL", "C01-SDW (primary) · C02-SDW (secondary)", "DIA, broadband, 5G"]],
                "zone-cloud": [list(c[:2]) + [c[2]] for c in S.CLOUD]}
    h = 50 + max(table_h(out_cols[z], out_rows[z]) for z in out_cols) + 50
    p.band(lb, y, h + 24, "OUT", "OUTSIDE", W + 76)
    for n, zone in enumerate(out_cols):
        zone_card(p, lz, lt, zone, X0 + n * (widths(3) + 10), y + 12, widths(3), h, out_cols[zone], out_rows[zone])
    y += h + 24 + 16
    # EDGE: the two firewall pairs and their interfaces, the DMZ and the extranet.
    # ADDRESSING, not IP: the build would read an IP column from NetBox's interface addresses, and the sample records
    # the edge pair's plan as prefixes, not as addresses on these interfaces.
    efw_cols = [("INTERFACE", 150), ("ZONE", 110), ("VLAN / VRF", 110), ("ADDRESSING", 230)]
    efw_rows = [["ethernet1/1", "INTERNET", "—", "198.51.100.0/28 (ISP-1)"],
                ["ethernet1/2", "INTERNET", "—", "203.0.113.0/28 (ISP-2)"],
                ["ethernet1/3–4 (Po43)", "EDGE", "ISFW transit", "10.1.255.32/29"],
                ["ethernet1/5–6 (Po44)", "DMZ, EXTRANET", "600, 610", ".1 of 10.1.200.0/24, 10.1.204.0/27"],
                ["guest interface", "GUEST", "700, 199", "172.20.0.0/18, 172.20.64.0/22"],
                ["ethernet1/7", "WAN", "—", "C01-SDW underlay"],
                ["VPN portal", "EDGE", "CORP or LEGAL", "10.250.0.0/21 (VPN pool)"],
                ["tunnel TUN-PHX", "INTERNET", "—", "to 192.0.2.44 (no owner)"]]
    isfw_cols = [("INTERFACE", 150), ("VRF", 80), ("TRANSIT", 130), ("CARRIES", 240)]
    isfw_rows = [["Po40 · VRF sub-interfaces", "CORP", "10.1.255.0/29", "Corporate users, voice, printers"],
                 ["", "LEGAL", "10.1.255.8/29", "Legal users"],
                 ["", "BUILDING", "10.1.255.16/29", "Cameras, badges, BMS, rooms"],
                 ["", "MGMT", "10.1.255.24/29", "Network management"],
                 ["Po41 (DC leafs)", "DC, LEGAL", "gateways", "VLANs 400–440, the DC tiers"],
                 ["Po43 (to edge)", "—", "10.1.255.32/29", "Internal to edge"],
                 ["ethernet1/7", "CORP, LEGAL", "SD-WAN overlay", "Branch and regional users"]]
    eh = 58 + max(table_h(efw_cols, efw_rows), table_h(isfw_cols, isfw_rows), 160) + 44
    ew = 2 * 300 + 600 + 600 + 70
    p.band(lb, y, eh + 24, "EDGE", "EDGE", W + 76)
    zone_box(p, lz, "zone-edge", X0, y + 12, ew, eh)
    p.cell(lz, esc(S.ZONE["zone-edge"][5]), SMALL, X0 + 12, y + 38, 900, 18)
    for k, (pair, title, cols, rows) in enumerate((
            ("C01-EFW", "<b>C01-EFW</b> · edge HA pair (active / passive)", efw_cols, efw_rows),
            ("C01-ISFW", "<b>C01-ISFW</b> · internal segmentation HA pair", isfw_cols, isfw_rows))):
        gx = X0 + 12 + k * (300 + 600 + 30)
        # Below the zone's rule line: a build pins each pair's location pill above its top edge.
        p.cell(lz, title, zone_style("#FFFFFF", "#94A3B8", "#334155", "top", 10), gx, y + 70, 290, 150)
        for n in (1, 2):
            device(p, p.layer("Devices"), f"{pair}-0{n}", gx + 12, y + 100 + (n - 1) * 60, 266, 52, ip=False,
                   serial=False, pill=False)
        table(p, lt, gx + 300, y + 70, cols, rows, row_h=22)
    # The DMZ and the extranet, one above the other beside the edge zone.
    dh = (eh - 10) / 2
    for n, zone in enumerate(("zone-dmz", "zone-extranet")):
        zone_card(p, lz, lt, zone, X0 + ew + 10, y + 12 + n * (dh + 10), W - ew - 10, dh)
    y += eh + 24 + 16
    for code, zones in (("USERS", ["zone-corp", "zone-voice", "zone-print", "zone-legal"]),
                        ("DC", ["zone-dc-app", "zone-dc-data", "zone-dc-infra", "zone-dc-backup", "zone-dms"]),
                        ("SHARED", ["zone-guest", "zone-rooms", "zone-building"]),
                        ("MGMT", ["zone-mgmt", "zone-oob"])):
        h = 50 + max(table_h(VLAN_COLS, vlan_rows(z)) for z in zones) + 44
        p.band(lb, y, h + 24, code, dict(S.BANDS)[code].split(" · ")[0], W + 76)
        bw = widths(len(zones))
        for n, zone in enumerate(zones):
            zone_card(p, lz, lt, zone, X0 + n * (bw + 10), y + 12, bw, h)
        y += h + 24 + 16
    # The VRFs, at the right.
    lv = p.layer("VRF table")
    vx = 2730
    vcols = [("VRF", 76), ("RD", 82), ("HOLDS", 200), ("TRANSIT TO ISFW", 214)]
    vrows = [[v, f"{S.RD_ASN}:{rd}", holds, transit] for v, rd, holds, transit in S.VRFS]
    vh = table_h(vcols, vrows)
    p.cell(lv, "", CARD, vx, 96, 600, 36 + vh + 132)
    p.cell(lv, "<b>VRFs</b> — the big zones, routed apart on the core", HEADING, vx + 14, 106, 560, 22)
    table(p, lv, vx + 14, 132, vcols, vrows, row_h=22)
    p.cell(lv, "OSPF per VRF on the core pair and DIST-S. Each VRF has one transit to the ISFW pair and a default "
           "route to it; no route leaks on the switches, so a packet that changes VRF goes through the ISFW. GUEST "
           "has no route to the ISFW at all. Identity (802.1X, EAP-TLS) puts a user in CORP or LEGAL; unknown "
           "devices land in VLAN 199.", TEXT, vx + 14, 140 + vh, 572, 112)
    legend(p, vx - 10 + 0, 96 + 36 + vh + 132 + 16, flows=False)
    p.model.set("pageHeight", str(int(y + 110)))
    p.height = int(y + 110)
    p.title_block(p.layer("Border & title block"), "C01", "Logical — zones, VRFs, VLANs", f"2 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ 3 physical
A, B, C = 110, 850, 1640      # DC-N columns: A and B; the campus core column C
PAIR_W, CARD_W = 640, 296
SX, SW = 2000, 320            # the floor stacks' column
LANE0, LANE = 2338, 18        # the core's lanes down the right of the stacks
DROPS = ("access-point", "printer", "camera", "room-system", "door-controller", "bms-controller")


def pair_box(p: Page, lz, ld, zone, names, x, y, title, attrs: dict | None = None) -> tuple[str, list[str]]:
    box = group_box(p, lz, zone, x, y, PAIR_W, 104, title, attrs)
    cards = [device(p, ld, n, x + 12 + k * (CARD_W + 24), y + 34, CARD_W, 58) for k, n in enumerate(names)]
    return box, cards


def engine_rows(p: Page, header: list[str], names: list[str] | None = None) -> list[list]:
    """A register exactly as a build of the sample writes it (the engine's own rows), so that build neither grows
    nor shrinks the table: the link register, or with ``names`` the asset register for those devices."""
    from make_corporate_sample import hq
    from netdiagrams import intake, profiles, sync
    from netdiagrams.graph import Graph, plain
    with profiles.use("corporate"):
        nb, g = sync.NetBoxIndex(intake.prepare(hq())), Graph(p.diagram)
        if names is None:
            order = list(dict.fromkeys(c["lag"] or c["name"] for c in S.CABLES if c["lag"] or c["name"]))
            rows = sync._link_rows(g, header, nb, order)
        else:
            rows = sync._asset_rows(g, None, header, nb, [(n, None) for n in names], DATE)
    return [[plain(v[0]) if isinstance(v, tuple) else v for v in row] for row in rows]


def physical() -> Page:
    p = Page("physical", "3 · Physical — Devices, Uplinks, Campus Fiber", 4640, 2860, prefix="c")
    lb = p.layer("Bands")
    lz = p.layer("Zones (groups · stacks)")
    p.layer(LINKS)
    ld = p.layer("1 · Devices")
    for name in TAGS + ("4 · Circuit IDs (hide before sharing)",):
        p.layer(name)
    p.title(lb, f"{SITE} — Physical",
            esc("Devices · uplinks · port-channels · campus fiber · rack and U on every device. The data center and "
                "the campus core share North's first floor; each floor's access stack and its end devices follow, "
                "building by building. Hover a device or Edit Data (Ctrl+M) for its NetBox record."))
    BW = 2476
    lc = p.layer("4 · Circuit IDs (hide before sharing)")
    # ---- providers
    p.band(lb, 96, 120, "ISP", "PROVIDERS", BW)
    isp = []
    for n, circ in enumerate(S.CIRCUITS[:2]):
        cx = A + 10 + n * 320
        isp.append(p.cell(ld, f"<b>ISP-{n + 1}</b><br>{sub(esc(circ['provider'] + ' · ' + circ['type']))}",
                          label_style("isp", 26, 36, 11, "middle", 12) + "spacingTop=0;", cx, 118, 290, 60))
        p.cell(lc, f"CID {circ['cid']}<br>{esc(circ['speed'])} · BGP", CID_TAG, cx + 40, 180, 200, 30)
    p.cell(ld, "<b>C02 · DR colocation</b>, 40 km<br>" + sub("DCI-1 and DCI-2 to the DC leafs (below) · the private "
           "cloud circuit lands there"), label_style("building", 26, 36, 11, "middle", 12) + "spacingTop=0;",
           B, 118, 420, 60)
    # ---- DC-N and MDF-N
    y0 = 232
    p.band(lb, y0, 868, "N-L1", "DC-N · MDF-N", BW)
    p.cell(lb, "<b>DC-N</b> · data center room, racks A01–A08", SMALL, A, y0 + 2, 500, 18)
    p.cell(lb, "<b>MDF-N</b> · campus core, racks M01–M02 (the WLCs sit in DC-N A03/A04)", SMALL, C, y0 + 2, 680, 18)
    r1, r2, r3, r4, r5, r6 = y0 + 20, y0 + 172, y0 + 324, y0 + 476, y0 + 640, y0 + 748
    efw, efw_c = pair_box(p, lz, ld, "zone-edge", ["C01-EFW-01", "C01-EFW-02"], A, r1,
                          "<b>C01-EFW</b> · edge HA pair (active / passive)")
    sdw, sdw_c = pair_box(p, lz, ld, "zone-wan", ["C01-SDW-01", "C01-SDW-02"], B, r1,
                          "<b>C01-SDW</b> · SD-WAN hub 1 (HA pair)")
    isfw, isfw_c = pair_box(p, lz, ld, "zone-edge", ["C01-ISFW-01", "C01-ISFW-02"], A, r2,
                            "<b>C01-ISFW</b> · internal segmentation HA pair: VRF transits, DC gateways")
    dcsw, dcsw_c = pair_box(p, lz, ld, "zone-mgmt", ["C01-DCSW-01", "C01-DCSW-02"], A, r3,
                            "<b>C01-DCSW</b> · DC leaf vPC pair: layer 2 for the DC VLANs")
    core, core_c = pair_box(p, lz, ld, "zone-mgmt", ["C01-CORE-01", "C01-CORE-02"], C, r2,
                            "<b>C01-CORE</b> · StackWise Virtual core: one logical switch, OSPF per VRF, .1 gateways",
                            {"tooltip": "NetBox virtual chassis C01-CORE · MDF-N",
                             "object": "dcim.virtualchassis", "name": "C01-CORE", "location": "MDF-N",
                             "link": f"{NETBOX}/dcim/virtual-chassis/?name=C01-CORE", "linkTarget": "_blank"})
    wlc, wlc_c = pair_box(p, lz, ld, "zone-mgmt", ["C01-WLC-01", "C01-WLC-02"], C, r3,
                          "<b>C01-WLC</b> · wireless controller SSO pair")
    for (a_card, b_card), name in ((efw_c, "HA-E"), (isfw_c, "HA-I"), (dcsw_c, "Po1"), (core_c, "Po1"),
                                   (wlc_c, "RP")):
        c = cable(name, DEV[p.find(a_card).get("name")]["name"]) if name == "Po1" else cable(name)
        link(p, a_card, b_card, c, "", exit=(1, 0.5), entry=(0, 0.5))
    link(p, core_c[0], core_c[1], cable("DAD-CORE"), "", exit=(1, 0.8), entry=(0, 0.8))   # SVL dual-active detection
    # Circuits: each ISP into the edge pair.
    for n, circ in enumerate(S.CIRCUITS[:2]):
        attrs = {"object": "circuits.circuit", "cid": circ["cid"], "status": "active", "x_handoff": circ["handoff"],
                 "x_speed": circ["speed"], "x_media": circ["media"], "x_patch_a": "", "x_patch_b": ""}
        attrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in attrs.items()), **attrs,
                 "link": f"{NETBOX}/circuits/circuits/?cid={circ['cid']}", "linkTarget": "_blank"}
        p.edge(p.layer(LINKS), isp[n], efw, "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=none;"
               "strokeColor=#94A3B8;strokeWidth=1.6;fontSize=9;fontColor=#334155;labelBackgroundColor=#DBEAFE;"
               "labelBorderColor=#2563EB;" + FONT, esc(f"{circ['speed']} · {circ['media']}"), attrs,
               exit=(0.5, 1), entry=(0.25 + 0.5 * n, 0))
    # Edge to internal, internal to DC leafs: one LAG per firewall.
    for k in range(2):
        link(p, efw_c[k], isfw_c[k], cable("Po43", f"C01-EFW-0{k + 1}"), exit=(0.5, 1), entry=(0.5, 0))
        link(p, isfw_c[k], dcsw, cable("Po41", f"C01-ISFW-0{k + 1}"), exit=(0.5, 1),
             entry=((12 + k * 320 + 148) / PAIR_W, 0))
    link(p, efw, sdw, cable("SDW-U"), "SDW-U · 10G · DAC", exit=(1, 0.4), entry=(0, 0.4))
    link(p, sdw, isfw, cable("SDW-O"), "SDW-O · 10G · DAC", exit=(0.25, 1), entry=(1, 0.3),
         points=[(B + 160, r2 + 31)])
    link(p, isfw, core, cable("Po40"), "Po40 · 2×25G per firewall · MMF OM4", exit=(1, 0.55), entry=(0, 0.55))
    vlink(p, efw, dcsw, cable("Po44"), "Po44 · 600,610 · DAC", exit=(0, 0.75), entry=(0, 0.5),
          points=[(A - 16, r1 + 78), (A - 16, r3 + 52)])
    link(p, core, wlc, cable("Po42"), "Po42 · 115,199,215,700,990 · MMF OM4", exit=(0.5, 1), entry=(0.5, 0))
    # Guest and quarantine VLANs, layer 2 only, to the edge pair's guest interface; NET-MGMT to the DC leafs.
    link(p, core, efw, cable("Po46"), "Po46 · 199,700 · 2×10G per firewall · MMF OM4", exit=(0.5, 0),
         entry=(0.97, 1), points=[(C + PAIR_W / 2, r1 + 128), (A + 0.97 * PAIR_W, r1 + 128)])
    link(p, core, dcsw, cable("Po45"), "Po45 · 990 · 2×25G · MMF OM4", exit=(0.15, 1), entry=(1, 0.12),
         points=[(C + 0.15 * PAIR_W, r3 - 24), (A + PAIR_W + 40, r3 - 24), (A + PAIR_W + 40, r3 + 12.5)])
    # DCI to C02, beside the leafs.
    dci = p.cell(ld, "<b>DCI-1 · DCI-2</b> to C02<br>" + sub("Carrier D and Carrier E · 10 Gb/s each · diverse paths"),
                 label_style("isp", 24, 34, 11, "middle", 12) + "spacingTop=0;", B, r3 + 20, 330, 60)
    for n, circ in enumerate(S.CIRCUITS[2:]):
        attrs = {"object": "circuits.circuit", "cid": circ["cid"], "status": "active", "x_handoff": circ["handoff"],
                 "x_speed": circ["speed"], "x_media": circ["media"]}
        attrs = {"tooltip": "\n".join(f"{k}: {v}" for k, v in attrs.items()), **attrs,
                 "link": f"{NETBOX}/circuits/circuits/?cid={circ['cid']}", "linkTarget": "_blank"}
        p.edge(p.layer(LINKS), dci, dcsw, "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=none;"
               "strokeColor=#94A3B8;strokeWidth=2;" + FONT, "", attrs, exit=(0, 0.3 + 0.4 * n),
               entry=(1, 0.3 + 0.2 * n))
        p.cell(lc, f"CID {circ['cid']}", CID_TAG, B + 340, r3 + 22 + 26 * n, 160, 18)
    # Hosts: the production cluster under the leafs, the legal cluster beside it.
    prod = group_box(p, lz, "zone-dc-infra", A, r4, PAIR_W, 144,
                     "<b>CL-PROD</b> · production cluster, 8 hosts · DMZ and extranet VMs on their own port group")
    member_rows(p, prod, 10, 34, (PAIR_W - 28) / 2, [f"C01-HV-0{n}" for n in (1, 5, 2, 6, 3, 7, 4, 8)], cols=2)
    legal = group_box(p, lz, "zone-dms", B, r4, 400, 92,
                      "<b>CL-LEGAL</b> · legal cluster: DMS and matters only, own local storage")
    member_rows(p, legal, 10, 34, 380, ["C01-HV-L1", "C01-HV-L2"])
    link(p, dcsw, prod, cables(*(f"Po{101 + k}" for k in range(8))), "Po101–108 · 2×25G each · DAC", exit=(0.3, 1), entry=(0.3, 0))
    # The pill on the run right of the SAN and backup lines.
    pill_at(p, link(p, dcsw, legal, cables("Po109", "Po110"), "Po109–110 · DAC", exit=(0.85, 1), entry=(0.4, 0),
                    points=[(A + 0.85 * PAIR_W, r4 - 18), (B + 160, r4 - 18)]), 0.42)
    san = device(p, ld, "C01-SAN-01", B, r5, 330, 58)
    bkp = device(p, ld, "C01-BKP-01", B + 370, r5, 330, 58)
    link(p, dcsw, san, cable("Po111"), "Po111 · DAC", exit=(1, 0.62), entry=(0, 0.5),
         points=[(A + PAIR_W + 46, r3 + 64), (A + PAIR_W + 46, r5 + 29)])
    link(p, dcsw, bkp, cable("Po112"), "Po112 · DAC", exit=(1, 0.86), entry=(0.5, 1),
         points=[(A + PAIR_W + 30, r3 + 89), (A + PAIR_W + 30, r5 + 76), (B + 535, r5 + 76)])
    note(p, A, r5, 640, 58, "DC-N and MDF-N: two PDUs per rack, one per UPS (C01-UPS-A, -B, beside the core). Each "
         "IDF has a rack UPS, on its floor's row below.", guide=False)
    note(p, A, r6, 640, 58, "Console lines: OOB-02 to the firewalls, hubs, DC leafs and WLCs · OOB-01 to the core "
         "and DIST-S. Both reach out on cellular when the network is down.", guide=False)
    nvr = group_box(p, lz, "zone-building", B, r6, 700, 104, "<b>Recorders</b> · 60 cameras record here")
    for n in (1, 2):
        device(p, ld, f"C01-NVR-0{n}", B + 12 + (n - 1) * 344, r6 + 34, 332, 58)
    # Down the core's left side, outermost first: the recorders, then the UPS cards and console servers.
    vlink(p, core, nvr, cable("NVR"), "NVR · 10G · MMF OM4", exit=(0, 0.66), entry=(1, 0.5),
          points=[(C - 64, r2 + 69), (C - 64, r6 + 52)], pos=0.62)   # the pill below the UPS cards' lines
    mgmt = [("C01-UPS-A", C, r5, 0.74, C - 52, None), ("C01-UPS-B", C + 350, r5, 0.81, C - 40, r5 - 22),
            ("C01-OOB-01", C, r4, 0.88, C - 28, None), ("C01-OOB-02", C + 350, r4, 0.95, C - 16, r4 - 22)]
    for name, x, ry, ey, lx, over in mgmt:
        did = device(p, ld, name, x, ry, 330, 58)
        c = cable(f"MGMT-{name[4:]}")
        if over is None:   # straight in from the left
            link(p, core, did, c, "", exit=(0, ey), entry=(0, 0.5), points=[(lx, r2 + ey * 104), (lx, ry + 29)],
                 weight=1.2, color="#94A3B8")
        else:              # over the card beside it, in from the top
            link(p, core, did, c, "", exit=(0, ey), entry=(0.5, 0),
                 points=[(lx, r2 + ey * 104), (lx, over), (x + 165, over)], weight=1.2, color="#94A3B8")
    # ---- the floors: a band per building, a row per floor, top floor first
    lanes = {}   # stack -> (lane x, exit y on the core)
    order = ["N5", "N4", "N3", "N2", "N1", "C2", "C1", "DIST-E", "DIST-W"]
    for k, key in enumerate(order):
        lanes[key] = (LANE0 + k * LANE, r2 + 100 - 10 * k)
    y = y0 + 868 + 16
    stacks = {}

    def floor_row(code: str, ry: float) -> None:
        _, floor, closet, *_ = S.FLOOR[code]
        stack_code, closet_name, rack, members, _, zone = S.STACK[code]
        p.cell(lb, f"<b>{floor}</b><br>{closet}", SMALL.replace("fontSize=9", "fontSize=10"), A, ry + 4, 120, 40)
        ups = f"C01-UPS-{code}"
        names = [f"C01-ACC-{code}-{m}" for m in range(1, members + 1)]
        model = "9300-48UXM"
        sid = stack(p, lz, f"C01-ACC-{code}", SX, ry, SW, names, zone, f"Catalyst {model} ×{members} · {closet} {rack}")
        stacks[code] = sid
        heads = [n for n in (f"C01-AP-{code}-01", f"C01-PRN-{code}-01") if n in DEV]
        heads += [next(d["name"] for d in S.DEVICES if d["location"] == floor and d["role"] == role)
                  for role in ("camera", "room-system", "door-controller", "bms-controller")
                  if any(d["location"] == floor and d["role"] == role for d in S.DEVICES)]
        h = 34 + 26 * members + 4
        for n, name in enumerate(heads):
            d = DEV[name]
            x = SX - 200 * (n + 1)
            cid = device(p, ld, name, x, ry + 70, 186, 56, small=True, pill=False, ip=False, serial=False,
                         label="<b>%name%</b><br>" + sub(f"%device_type% · VLAN {S.ACCESS_VLAN[d['role']]}"))
            c = CABLE_OF[name][0]
            level = ry + 56 - 8 * n
            link(p, sid, cid, c, "", exit=(0, (level - ry) / h), entry=(0.5, 0), points=[(x + 93, level)], weight=1.2,
                 color="#94A3B8")
        if ups in DEV:   # the closet's rack UPS, its network card on the stack, above the end devices' drops
            uid = device(p, ld, ups, A + 140, ry + 64, 300, 56)
            level = ry + 56 - 8 * len(heads)
            link(p, sid, uid, CABLE_OF[ups][0], "", exit=(0, (level - ry) / h), entry=(0.5, 0),
                 points=[(A + 290, level)], weight=1.2, color="#94A3B8")

    def lane(key: str, src: str, dst: str, c: dict, text: str, entry_y: float, dst_y: float, dst_h: float) -> None:
        lx, ey = lanes[key]
        vlink(p, src, dst, c, text, exit=(1, (ey - r2) / 104), entry=(1, (entry_y - dst_y) / dst_h),
              points=[(lx, ey), (lx, entry_y)])

    for building, codes, label in (("North", ["N5", "N4", "N3", "N2", "N1"], "NORTH"),
                                   ("Commons", ["C2", "C1"], "COMMONS")):
        bh = 16 + 136 * len(codes)
        p.band(lb, y, bh, building[0], label, BW)
        for n, code in enumerate(codes):
            ry = y + 12 + 136 * n
            floor_row(code, ry)
            members = S.STACK[code][3]
            po = cable(next(c["name"] for c in S.CABLES if c["b"][0].startswith(f"C01-ACC-{code}-1:")))
            lane(code, core, stacks[code], po, f"{po['name']} · {po['speed']} · {po['media']}",
                 ry + 17 + 13 * members, ry, 34 + 26 * members + 4)
        y += bh + 16
    # South: DIST-S first, then its four floors.
    p.band(lb, y, 16 + 150 + 136 * 4, "S", "SOUTH", BW)
    dy = y + 12
    dist = group_box(p, lz, "zone-mgmt", SX, dy, SW, 128, "%name%<br>" + sub("SVL pair · MDF-S M01 / M02", 9),
                     {"placeholders": "1", "tooltip": "NetBox virtual chassis C01-DIST-S · MDF-S",
                      "object": "dcim.virtualchassis", "name": "C01-DIST-S", "location": "MDF-S",
                      "link": f"{NETBOX}/dcim/virtual-chassis/?name=C01-DIST-S", "linkTarget": "_blank"})
    svl = member_rows(p, dist, 10, 34, SW - 20, ["C01-DIST-S-01", "C01-DIST-S-02"], words=["SVL 1", "SVL 2"],
                      ip_head=SW)
    p.cell(lb, "<b>S-L1</b><br>MDF-S · South distribution", SMALL.replace("fontSize=9", "fontSize=10"), A, dy + 4,
           220, 40)
    p.cell(lb, sub("SVL: 2×100G DAC · DAD: a 10G dual-active detection link (both in the link register).", 9),
           SMALL, SX - 560, dy + 40, 420, 30)
    for name, lx, at in (("SVL", SX - 80, 0.3), ("DAD", SX - 30, 0.7)):
        link(p, svl[0], svl[1], cable(name), name, exit=(0, at), entry=(0, at),
             points=[(lx, dy + 34 + 22 * at), (lx, dy + 60 + 22 * at)])
    for key, name, ey in (("DIST-E", "P2P-NS-E", 20), ("DIST-W", "P2P-NS-W", 38)):
        c = cable(name)
        lane(key, core, dist, c, f"{name} · 100G · {c['media']} · {'east' if key[-1] == 'E' else 'west'} duct", dy + ey, dy,
             128)
    sy = dy + 150
    for n, code in enumerate(["S4", "S3", "S2", "S1"]):
        floor_row(code, sy + 136 * n)
    # DIST-S to its floors: S4 straight down, the rest down a lane each beside the stacks.
    po = cable("Po24")
    link(p, dist, stacks["S4"], po, f"Po24 · {po['speed']} · {po['media']}", exit=(0.35, 1), entry=(0.35, 0))
    for k, code in enumerate(["S3", "S2", "S1"]):
        po = cable(f"Po{21 + 2 - k}")
        lx = LANE0 + k * LANE
        ey = dy + 80 + 16 * k
        ry = sy + 136 * (1 + k)
        vlink(p, dist, stacks[code], po, f"{po['name']} · {po['speed']} · {po['media']}", exit=(1, (ey - dy) / 128),
              entry=(1, 56 / 116), points=[(lx, ey), (lx, ry + 56)])
    bottom = sy + 136 * 4 + 16
    p.cell(lb, sub("Campus fiber: two 24-strand SMF trunks North to South and two North to Commons, one in each of "
                   "the east and west ducts (trunk labels: sheet 7) · access uplinks inside a building are OM4 riser "
                   "fiber",
                   9), SMALL, A, bottom - 4, 1600, 18)
    # ---- registers and legend, right
    RX = 2540
    lr = p.layer("6 · Link register")
    cols = [("LINK", 92), ("CABLE ID", 92), ("A-SIDE (MEMBERS)", 196), ("B-SIDE (MEMBERS)", 196), ("SPEED", 84),
            ("MEDIA", 66), ("STATUS", 70), ("TRUNKED VLANS", 236)]   # wide enough for a floor trunk on one line
    rows = engine_rows(p, [c[0] for c in cols])
    card = p.cell(lr, "", CARD, RX, 96, 1060, 400)
    p.cell(lr, "<b>Link register</b> — port-channels, members, speed, trunked VLANs", HEADING, RX + 14, 106, 1000, 22)
    table(p, lr, RX + 14, 134, cols, rows, row_h=22)
    p.cell(lr, "All trunks: explicit allowed list · LACP fast. End-device drops are in NetBox and counted on the floor "
           "cards, not listed here.", NOTE, RX + 14, 134 + p.table_height + 8, 1020, 32)   # on the card, not under it
    lbottom = 134 + p.table_height + 8 + 32 + 14
    resize(p, card, lbottom - 96)
    la = p.layer("7 · Asset register")
    infra = [d["name"] for d in S.DEVICES if d["role"] not in DROPS]
    ax = RX + 1080
    acard = p.cell(la, "", CARD, ax, 96, 1000, 400)
    p.cell(la, "<b>Asset register</b> — mirrors each device's NetBox record", HEADING, ax + 14, 106, 960, 22)
    cols = [("HOSTNAME", 100), ("ROLE", 108), ("STATUS", 46), ("CRIT", 50), ("MODEL", 150), ("SERIAL", 94),
            ("MGMT IP", 76), ("ROOM", 48), ("RACK/CAB", 56), ("U", 32), ("SW", 102), ("EOS", 74)]
    rows = engine_rows(p, [c[0] for c in cols], infra)
    # Row heights as the build draws them: it balances the columns so no row wraps.
    p.table(la, ax + 14, 134, cols, rows, heights=[20] * (len(rows) + 1), body=lambda c, link: BODY_CELL)
    resize(p, acard, 38 + p.table_height + 16)
    legend(p, ax, 96 + 38 + p.table_height + 16 + 14, flows=False)
    p.title_block(p.layer("Border & title block"), "C01", "Physical — devices, links", f"3 of {SHEETS}", DATE, PROJECT)
    return p



# ------------------------------------------------------------------ 3d wireless
def wireless() -> Page:
    p = Page("wireless", "3d · Wireless — APs, controllers and SSIDs", 3240, 1060, prefix="c")
    lb, lc, ld = p.layer("Floors"), p.layer("Controllers"), p.layer("1 · Devices")   # the pair's box under its cards
    for name in TAGS:
        p.layer(name)
    p.title(lb, f"{SITE} — Wireless",
            esc("Access points per floor and building · the controller pair · SSIDs and the zone each one lands in. "
                "Campus APs run in local mode: client traffic tunnels to the WLC pair, so the wireless VLANs ride "
                "Po42 to the core, never the access trunks (guest and quarantine go on to the edge on Po46)."))
    wlc = group_box(p, lc, "zone-mgmt", 640, 96, 680, 104,
                    "<b>C01-WLC</b> · SSO pair in DC-N · 114 campus APs (local mode) · branch APs (FlexConnect)")
    cards = [device(p, ld, f"C01-WLC-0{n}", 652 + (n - 1) * 332, 130, 320, 58) for n in (1, 2)]
    link(p, cards[0], cards[1], cable("RP"), "", exit=(1, 0.5), entry=(0, 0.5))
    buildings = (("North", ["N5", "N4", "N3", "N2", "N1"]), ("South", ["S4", "S3", "S2", "S1"]),
                 ("Commons", ["C2", "C1"]))
    for b, (name, codes) in enumerate(buildings):
        bx = 40 + b * 640
        total = sum(S.FLOOR[c][3] for c in codes)
        box = p.cell(lb, f"<b>{name}</b> · {total} APs on {len(codes)} floors",
                     zone_style("#FFFFFF", "#E2E8F0", "#334155", "top", 11), bx, 260, 620, 40 + 76 * len(codes))
        for n, code in enumerate(codes):
            _, floor, closet, aps, *_ = S.FLOOR[code]
            fy = 296 + 76 * n
            p.cell(lb, f"<b>{floor}</b><br>{sub(closet, 9)}", SMALL.replace("fontSize=9", "fontSize=10"), bx + 14,
                   fy + 10, 90, 40)
            device(p, ld, f"C01-AP-{code}-01", bx + 110, fy, 300, 60, small=True, pill=False, ip=False, serial=False,
                   label="<b>%name%</b><br>" + sub("%device_type% · local mode, tunnels to C01-WLC"))
            p.cell(lb, sub(f"PoE from C01-ACC-{code} · access VLAN 990" + (" · legal floor" if code in S.LEGAL_FLOORS
                                                                          else ""), 9), SMALL, bx + 420, fy + 12,
                   190, 40)
        p.edge(p.layer("2 · CAPWAP"), box, wlc, "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=none;"
               "strokeColor=#0891B2;strokeWidth=1.4;dashed=1;fontSize=9;fontColor=#0E7490;labelBackgroundColor=#FFFFFF;"
               + FONT, "CAPWAP → C01-WLC", exit=(0.5, 0), entry=(0.2 + 0.3 * b, 1))
    lt = p.layer("SSID table")
    tx = 1980
    p.cell(lt, "", CARD, tx, 96, 1236, 300)
    p.cell(lt, "<b>SSIDs</b> — one per zone; identity, not the SSID, picks CORP or LEGAL", HEADING, tx + 16, 106,
           1200, 22)
    rows = [[ssid, sec, str(vlan), S.ZONE[zone][1], "Tunnelled to controller", notes]
            for ssid, sec, vlan, zone, notes in S.SSIDS]
    table(p, lt, tx + 16, 136, [("SSID", 100), ("SECURITY", 230), ("VLAN", 110), ("ZONE", 80), ("SWITCHING", 150),
          ("NOTES", 420)], rows, row_h=30)
    note(p, tx + 16, 270, 1204, 112, "<b>Rules</b><br>· SR-CORP: EAP-TLS certificates; the NAC returns VLAN 115 or "
         "215 by identity group; 802.11r fast roaming; every campus AP joins the same pair, so a client keeps its "
         "address across buildings.<br>· SR-GUEST: captive portal, client isolation, anchored on the WLC pair, never "
         "routed internally. SR-IOT: room systems only, one key per device from the NAC.<br>· Branch APs run "
         "FlexConnect: SR-CORP and SR-GUEST switch locally to the branch's VLANs 110/210 and 700. No SSID for "
         "cameras, badges or building controls: they are wired.", guide=False)
    legend(p, tx, 412, flows=False)
    p.title_block(p.layer("Border & title block"), "C01", "Wireless — APs, SSIDs", f"3d of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 4 flows
VERDICT = {"Permitted": ("#16A34A", "endArrow=block;endFill=1;"),
           "Conditional": ("#EA580C", "dashed=1;endArrow=block;endFill=1;"),
           "Denied": ("#DC2626", "dashed=1;endArrow=none;")}


def flows() -> Page:
    p = Page("flows", "4 · Traffic Flows — who talks to whom", 2600, 60 + 96 + 46 * len(S.FLOWS) + 150, prefix="c")
    lb, lf = p.layer("Lanes"), p.layer("Flows")
    p.title(lb, f"{SITE} — Traffic flows",
            esc("Each lane is one conversation: who starts it, who answers, and what the firewalls do. Solid green "
                "is permitted, orange dashed is conditional, red ✕ is denied. Everything else is denied by default."))
    xa, xb, top = 120, 1000, 110
    for x, text in ((xa, "INITIATOR"), (xb, "RESPONDER"), (1400, "WHAT · CONDITIONS · OWNER")):
        p.cell(lb, f"<b>{text}</b>", SMALL, x, top - 6, 600, 20)
    box = ("rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#FFFFFF;strokeColor=#CBD5E1;fontSize=10;"
           "fontColor=#0F172A;fontStyle=1;html=1;whiteSpace=wrap;" + FONT)
    for n, (fid, src, dst, what, verdict, cond, owner) in enumerate(S.FLOWS):
        y = top + 20 + n * 46
        color, extra = VERDICT[verdict]
        p.cell(lb, "", BAND.replace("fillColor=#FFFFFF", "fillColor=#FFFFFF" if n % 2 else "fillColor=#FBFCFE"),
               24, y, 2550, 40)
        p.cell(lb, f"<b>{fid}</b>", "rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#E9ECEF;"
               "strokeColor=none;fontColor=#475569;fontSize=10;html=1;" + FONT, 36, y + 9, 60, 22)
        a = p.cell(lf, esc(src), box, xa, y + 6, 340, 28)
        b = p.cell(lf, esc(dst), box, xb, y + 6, 360, 28)
        p.edge(lf, a, b, f"html=1;strokeColor={color};strokeWidth=1.8;{extra}fontSize=9;fontColor={color};"
               "labelBackgroundColor=#FFFFFF;fontStyle=1;" + FONT, verdict, exit=(1, 0.5), entry=(0, 0.5))
        if verdict == "Denied":
            p.cell(lf, "✕", "ellipse;html=1;fillColor=#DC2626;strokeColor=none;fontColor=#FFFFFF;"
                   "fontSize=10;fontStyle=1;" + FONT, 790, y + 10, 20, 20)
        p.cell(lf, f"<b>{esc(what)}</b>" + (f" · {sub(esc(cond), 10)}" if cond else "")
               + f" · {sub('owner: ' + esc(owner), 10, '#94A3B8')}",
               TEXT.replace("verticalAlign=top", "verticalAlign=middle"), 1400, y + 4, 1160, 32)
    y = top + 20 + len(S.FLOWS) * 46
    p.cell(lb, "", BAND.replace("fillColor=#FFFFFF", "fillColor=#FEF2F2"), 24, y, 2550, 40)
    p.cell(lb, "<b>—</b>", "rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#FEE2E2;"
           "strokeColor=none;fontColor=#991B1B;fontSize=10;html=1;" + FONT, 36, y + 9, 60, 22)
    p.cell(lf, "<b>Default deny</b> · anything not listed above, between any two zones, is blocked and logged · "
           "owner: Security", TEXT.replace("verticalAlign=top", "verticalAlign=middle").replace("#334155", "#991B1B"),
           xa, y + 6, 1240, 28)
    p.title_block(p.layer("Border & title block"), "C01", "Traffic flows", f"4 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 5 failover
SCENARIOS = [
    ("core-switch", "A core switch fails", "C01-CORE-01 dies or is reloaded.",
     "C01-CORE-02 carries on as the whole StackWise Virtual core, every .1 gateway with it; each port-channel to the "
     "floors, the ISFW and the WLCs keeps its member on CORE-02 at half speed; OSPF moves South onto P2P-NS-W.",
     "Nothing. The alert goes to the network team."),
    ("isp", "The east duct is cut", "A dig severs C01-FIB-NS-E and C01-FIB-NC-E.",
     "South's routes move to P2P-NS-W; Commons runs on the west-duct members of Po31 and Po32 at 10G.",
     "Nothing, unless the west duct goes too. Then South and Commons are cut off from the core."),
    ("isp", "ISP-1 goes down", "Fiber cut or provider outage on the 10 Gb/s line.",
     "BGP withdraws ISP-1; the edge pair sends and receives everything over ISP-2 (1 Gb/s). The cloud IPsec backup "
     "and the remote-access portal follow.",
     "Big uploads and video are slower. Remote users on C01's portal reconnect, some to C02's."),
    ("firewall", "An edge firewall fails", "C01-EFW-01, the active member, loses power or a bad update.",
     "C01-EFW-02 takes over the internet, DMZ, extranet, VPN and guest interfaces; sessions are synced over HA-E.",
     "A few seconds' pause. Some VPN users reconnect."),
    ("firewall", "An internal firewall fails", "C01-ISFW-01, the active member, fails.",
     "C01-ISFW-02 takes over every VRF transit and every DC gateway (VLANs 400–440); sessions are synced over HA-I.",
     "A pause in open application sessions; most carry on."),
    ("datacenter", "DC-N goes dark", "Fire, flood or a power failure takes out the whole room.",
     "The branches and C10 already have tunnels to the C02 hub. Systems restart from replicas on CL-DR and backups "
     "on C02-BKP-01 when DR is declared (practice management in 4 hours, the rest in 24). Remote users connect to C02.",
     "HQ loses its firewalls and the WLC pair with the room: no internet, no applications, no campus Wi-Fi until DR "
     "is declared. Branches pause, then work against C02."),
    ("sdwan-hub", "A branch's broadband goes down", "A BR-S branch loses its business broadband.",
     "The branch FortiGate moves its tunnels to both hubs, and local internet breakout, onto 5G.",
     "Slower uploads and video calls until broadband is back."),
    ("wireless-controller", "A WLC fails", "C01-WLC-01, the active controller, fails.",
     "C01-WLC-02 takes over in SSO: APs stay joined and clients keep their sessions. Branch APs (FlexConnect) keep "
     "switching locally either way.", "Nothing."),
]


def failover() -> Page:
    p = Page("failover", "5 · Failover scenarios", 2600, 110 + 136 * len(SCENARIOS) + 110, prefix="c")
    lb = p.layer("Scenarios")
    p.title(lb, f"{SITE} — Failover",
            esc("What happens when one thing breaks: what fails, what takes over, and what people notice. Pairs "
                "everywhere, two fiber ducts, two hubs, and a DR site for the day the data center goes dark."))
    for n, (icon, title, what, takes, notice) in enumerate(SCENARIOS):
        y = 100 + n * 136
        p.cell(lb, "", CARD, 24, y, 2550, 124)
        icon_card(p, lb, 40, y + 14, 520, 96, icon, title, what, 34, 14)
        for k, (head, text, color) in enumerate([("WHAT TAKES OVER", takes, "#15803D"),
                                                 ("WHAT PEOPLE NOTICE", notice, "#B45309")]):
            x = 600 + k * 990
            p.cell(lb, f"<b>{head}</b>", SMALL.replace("#64748B", color), x, y + 14, 950, 20)
            p.cell(lb, esc(text), TEXT.replace("fontSize=10", "fontSize=12"), x, y + 36, 950, 80)
    p.title_block(p.layer("Border & title block"), "C01", "Failover scenarios", f"5 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 6 multi-site WAN
def multisite() -> Page:
    p = Page("multisite", "6 · Multi-site WAN — hubs, branches, cloud", 2800, 1720, prefix="c")
    lb, lc, ll = p.layer("Sites"), p.layer("Cards"), p.layer("Tunnels")
    p.title(lb, "Sable Ridge — the WAN: hubs, branches, home workers and the cloud",
            esc("Two hubs (C01 primary, C02 secondary), the Lakeview regional office and 14 branches built to two "
                "typicals. Every spoke has tunnels to both hubs over two or three underlays; a branch is drawn once as "
                "its typical plus a row in the site table."))
    home = icon_card(p, lc, 60, 100, 560, 84, "users", "Home and travel",
                     "About 600 a day · always-on VPN with MFA · C01's portal first, then C02's", 30, 13)
    inet = icon_card(p, lc, 1000, 100, 640, 84, "globe", "Internet and SaaS",
                     "Email, files, meetings and phones in SaaS · every branch breaks out locally", 30, 13)
    mssp = icon_card(p, lc, 2040, 100, 680, 84, "shield", "MSSP",
                     "Watches the logs around the clock in the cloud SIEM · no inbound access to the network", 30, 13)
    c01 = p.cell(lc, "<b>C01 · Sable Ridge HQ campus</b> · 10.1.0.0/16 · about 1,400 staff<br>"
                 + sub("Hub 1 (primary) · three buildings · the primary data center (DC-N)"),
                 zone_style("#F4F7FE", "#B3C8F8", "#2563EB", "top", 12), 60, 300, 1060, 200)
    for n, (icon, title, text) in enumerate([
            ("firewall", "C01-EFW pair", "Edge: ISP-1 10 Gb/s · ISP-2 1 Gb/s"),
            ("firewall", "C01-ISFW pair", "Every VRF and DC tier"),
            ("sdwan-hub", "C01-SDW pair", "SD-WAN hub 1"),
            ("datacenter", "DC-N", "CL-PROD · CL-LEGAL · SAN · backup")]):
        icon_card(p, lc, 76 + n * 260, 370, 248, 100, icon, title, text, 24, 11)
    c02 = p.cell(lc, "<b>C02 · DR colocation</b> · 10.2.0.0/16 · cage 4-17, 40 km away<br>"
                 + sub("Hub 2 (secondary) · second internet edge · disaster recovery copies"),
                 zone_style("#F2FAF8", "#A8DACA", "#047857", "top", 12), 1560, 300, 1160, 200)
    for n, (icon, title, text) in enumerate([
            ("firewall", "C02-FW pair", "Edge and internal in one pair · ISP-3 1 Gb/s"),
            ("sdwan-hub", "C02-SDW pair", "SD-WAN hub 2"),
            ("hypervisor", "CL-DR", "C02-HV-01…04: replicas of production"),
            ("backup", "C02-BKP-01", "Replica of the backup store")]):
        icon_card(p, lc, 1576 + n * 284, 370, 272, 100, icon, title, text, 24, 11)
    cloud = p.cell(lc, "<b>Cloud</b> · 10.200.0.0/14<br>" + sub("A transit hub and two spokes"),
                   zone_style("#F0F9FF", "#A5D8F3", "#0369A1", "top", 12), 1560, 640, 1160, 180)
    for n, (name, prefix, what) in enumerate(S.CLOUD):
        icon_card(p, lc, 1576 + n * 380, 700, 368, 96, "cloud", f"{name} · {prefix}", what, 24, 11)
    overlay = p.cell(lc, "<b>SD-WAN overlay</b> · CORP and LEGAL ride as separate segments · every spoke builds "
                     "tunnels to both hubs over each underlay · branch rules are enforced at the hub's ISFW",
                     zone_style("#F5F3FF", "#C4B5FD", "#6D28D9", "middle", 11), 60, 640, 1380, 56)
    spokes = [
        ("building", "C10 · Lakeview regional office", "10.10.0.0/16 · about 280 staff · built like a Book 5 office: "
         "C10-FW pair (FortiGate 120G, SD-WAN spoke), C10-CORE stack, three floor stacks, 18 APs, a local host"),
        ("building", "BR-M typical · 25–70 staff", "2× FortiGate 120G (HA) · 2× Catalyst 9300-48P (stack) · 4–6 "
         "C9136I (FlexConnect) · DIA + broadband + 5G · C11, C14, C17, C21"),
        ("building", "BR-S typical · 8–25 staff", "1× FortiGate 70G · 1× Catalyst 9200L-24P-4G · 2–3 C9120AXI "
         "(FlexConnect) · broadband + 5G · ten sites, C12 to C24"),
    ]
    tunnel = ("html=1;strokeColor=#6D28D9;strokeWidth=2;dashed=1;dashPattern=8 4;endArrow=none;fontSize=10;"
              "fontColor=#4C1D95;labelBackgroundColor=#FFFFFF;" + FONT)
    plain = "html=1;strokeColor=#94A3B8;strokeWidth=1.4;endArrow=none;fontSize=10;fontColor=#475569;" \
            "labelBackgroundColor=#FFFFFF;" + FONT
    for n, (icon, title, text) in enumerate(spokes):
        s = icon_card(p, lc, 60 + n * 470, 790, 440, 130, icon, title, text, 30, 12)
        p.edge(ll, s, overlay, tunnel, "", exit=(0.5, 0), entry=((220 + n * 470) / 1380, 1))
    p.edge(ll, overlay, c01, tunnel, "primary", exit=(0.3, 0), entry=(0.39, 1))
    p.edge(ll, overlay, c02, tunnel, "secondary", exit=(0.95, 0), entry=(0.03, 1),
           points=[(60 + 0.95 * 1380, 560), (1594.8, 560)])
    p.edge(ll, c01, c02, "html=1;strokeColor=#047857;strokeWidth=3;endArrow=none;fontSize=10;fontColor=#065F46;"
           "labelBackgroundColor=#FFFFFF;" + FONT, "DCI-1 + DCI-2 · 2× 10 Gb/s carrier Ethernet · diverse paths",
           exit=(1, 0.3), entry=(0, 0.3))
    p.edge(ll, c02, cloud, "html=1;strokeColor=#0369A1;strokeWidth=2.5;endArrow=none;fontSize=10;fontColor=#075985;"
           "labelBackgroundColor=#FFFFFF;" + FONT, "CLOUD-PVT · 2 Gb/s private circuit", exit=(0.8, 1), entry=(0.8, 0))
    p.edge(ll, c01, cloud, tunnel.replace("#6D28D9", "#0369A1"), "IPsec backup from C01's edge",
           exit=(0.92, 1), entry=(0, 0.75), points=[(60 + 0.92 * 1060, 775)])
    p.edge(ll, home, c01, tunnel.replace("#6D28D9", "#7C3AED"), "VPN + MFA", exit=(0.5, 1), entry=(0.32, 0))
    p.edge(ll, inet, c01, plain, "ISP-1 + ISP-2", exit=(0.2, 1), entry=(0.95, 0), points=[(1128, 250), (1067, 250)])
    p.edge(ll, inet, c02, plain, "ISP-3", exit=(0.8, 1), entry=(0.05, 0), points=[(1512, 250), (1618, 250)])
    p.edge(ll, mssp, cloud, plain.replace("endArrow=none", "endArrow=block;endFill=1"), "",
           exit=(1, 0.5), entry=(1, 0.2), points=[(2760, 142), (2760, 676)])
    p.cell(lb, sub("Logs over TLS to the SIEM (F24)", 9), SMALL, 2560, 600, 190, 20)
    lt = p.layer("Site table")
    p.cell(lt, "<b>Branches</b> — one row per site; the typical says how it is built", HEADING, 60, 960, 1400, 22)
    rows = [[(code, f"{NETBOX}/dcim/sites/?slug={code.lower()}"), name, typ, str(staff), f"10.{code[1:]}.0.0/16",
             under, legal] for code, name, typ, staff, under, legal in S.BRANCHES]
    table(p, lt, 60, 988, [("CODE", 80), ("SITE", 200), ("TYPICAL", 100), ("STAFF", 80), ("PREFIX", 160),
          ("UNDERLAYS", 320), ("LEGAL STAFF ON SITE", 180)], rows, row_h=26)
    note(p, 1240, 988, 600, 160, "<b>Reading a branch</b><br>A BR-M site is the BR-M card with the row's prefix: "
         "VLANs 110, 120, 130, 210 (legal staff only), 700 and 990 at 10.nn, guest at 172.21.nn.0/24 with local "
         "breakout. A branch with its own NetBox site is drafted, not drawn here: netdiagrams draft --profile "
         "corporate.", guide=False)
    p.title_block(p.layer("Border & title block"), "All", "Multi-site WAN", f"6 of {SHEETS}", DATE, PROJECT)
    return p


# ------------------------------------------------------------------ 7 flow register
ZONE_ORDER = [z[0] for z in S.ZONES]
INSIDE = [z for z in ZONE_ORDER if z not in ("zone-internet", "zone-wan", "zone-cloud", "zone-guest")]
MATRIX = {  # (from, to): (verdict, flows)
    ("zone-corp", "zone-internet"): ("allow", "F01 F26"), ("zone-corp", "zone-dc-app"): ("allow", "F02"),
    ("zone-corp", "zone-dc-infra"): ("allow", "F03"), ("zone-legal", "zone-dc-infra"): ("allow", "F03"),
    ("zone-corp", "zone-dc-data"): ("deny", "F04"), ("zone-dc-app", "zone-dc-data"): ("allow", "F05"),
    ("zone-legal", "zone-dms"): ("allow", "F06"), ("zone-corp", "zone-dms"): ("deny", "F07"),
    ("zone-legal", "zone-internet"): ("allow", "F08"), ("zone-legal", "zone-dc-app"): ("allow", "F08"),
    ("zone-dms", "zone-internet"): ("deny", "F09"), ("zone-edge", "zone-dc-app"): ("cond", "F10"),
    ("zone-edge", "zone-dms"): ("cond", "F10"), ("zone-voice", "zone-internet"): ("allow", "F11"),
    ("zone-dc-infra", "zone-print"): ("allow", "F12"), ("zone-print", "zone-internet"): ("cond", "F13"),
    ("zone-guest", "zone-internet"): ("allow", "F14"), ("zone-rooms", "zone-internet"): ("allow", "F16"),
    ("zone-corp", "zone-rooms"): ("cond", "F17"), ("zone-building", "zone-internet"): ("deny", "F19"),
    ("zone-internet", "zone-building"): ("cond", "F20"), ("zone-dc-infra", "zone-mgmt"): ("cond", "F21 F33"),
    ("zone-mgmt", "zone-dc-infra"): ("allow", "F23"), ("zone-dc-infra", "zone-internet"): ("cond", "F24"),
    ("zone-wan", "zone-dc-app"): ("allow", "F25"), ("zone-wan", "zone-dc-infra"): ("allow", "F25"),
    ("zone-dc-app", "zone-cloud"): ("allow", "F27"), ("zone-dc-backup", "zone-cloud"): ("allow", "F28"),
    ("zone-internet", "zone-dmz"): ("allow", "F29"), ("zone-dmz", "zone-dc-app"): ("cond", "F30"),
    ("zone-internet", "zone-extranet"): ("cond", "F31"), ("zone-dc-app", "zone-internet"): ("cond", "F32"),
}
MATRIX.update({("zone-guest", z): ("deny", "F15") for z in INSIDE})
MATRIX.update({(z, "zone-mgmt"): ("deny", "F22") for z in ("zone-corp", "zone-voice", "zone-print", "zone-legal",
                                                            "zone-rooms", "zone-building")})


def register() -> Page:
    p = Page("register", "7 · Flow register & standards", 3560, 1000, prefix="c")
    lf, lm, ls = p.layer("Flow register"), p.layer("Zone matrix"), p.layer("Standards")
    p.title(lf, f"{SITE} — Flow register and standards",
            esc("The segmentation in writing: every permitted conversation, its conditions and owner, then default "
                "deny. The zone matrix is the same rules as a grid. Naming standards at the right."))
    look = {"Permitted": "#15803D", "Conditional": "#B45309", "Denied": "#B91C1C"}
    rows = [[fid, src, dst, what, f'<font color="{look[v]}"><b>{v}</b></font>', cond, owner]
            for fid, src, dst, what, v, cond, owner in S.FLOWS]
    rows.append(["—", "Any", "Any", "Everything not listed above", '<font color="#B91C1C"><b>Denied</b></font>',
                 "Default deny, logged", "Security"])
    cols = [("ID", 44), ("FROM", 220), ("TO", 250), ("WHAT", 430), ("VERDICT", 96), ("CONDITIONS", 280),
            ("OWNER", 200)]
    card = p.cell(lf, "", CARD, 24, 92, 1560, 400)
    p.cell(lf, "<b>Flow register</b>", HEADING, 40, 102, 1500, 22)
    table(p, lf, 40, 128, cols, rows, row_h=26)
    resize(p, card, 36 + p.table_height + 16)
    my = 128 + p.table_height + 40
    n = len(ZONE_ORDER)
    cell = {"allow": '<font color="#15803D"><b>allow</b></font>', "cond": '<font color="#B45309"><b>cond.</b></font>',
            "deny": '<font color="#B91C1C"><b>deny</b></font>'}
    mrows = []
    for a in ZONE_ORDER:
        row = [S.ZONE[a][1]]
        for b in ZONE_ORDER:
            if a == b:
                row.append('<font color="#94A3B8">inside</font>' + (" F18" if a == "zone-building" else ""))
            elif (a, b) in MATRIX:
                v, f = MATRIX[(a, b)]
                row.append(f"{cell[v]} {f}")
            else:
                row.append("")
        mrows.append(row)
    mcols = [("FROM \\ TO", 96)] + [(S.ZONE[z][1], 82) for z in ZONE_ORDER]
    mcard = p.cell(lm, "", CARD, 24, my, 1800, 400)
    p.cell(lm, "<b>Zone matrix</b> — rows start the conversation, columns answer; blank is default deny",
           HEADING, 40, my + 10, 1700, 22)
    table(p, lm, 40, my + 40, mcols, mrows, row_h=30, key=KEY_CELL)
    resize(p, mcard, 40 + p.table_height + 16)
    bottom = my + 40 + p.table_height + 16
    sx = 1880
    std = [["Site code", "C + two digits: C01 HQ campus, C02 DR colocation, C10 Lakeview, C11–C24 branches"],
           ["Device", "SITE-ROLE-NN: C01-CORE-01, C01-ISFW-02; a building letter where it helps: C01-DIST-S-01"],
           ["Access stack", "SITE-ACC-<building><floor>: C01-ACC-N1; members -1, -2, -3"],
           ["End device", "SITE-ROLE-<floor>-NN: C01-AP-N2-01, C01-PRN-S3-02; cameras C01-CAM-001"],
           ["Branch", "Cnn-FW-01, Cnn-ACC-1, Cnn-AP-nn, Cnn-PRN-nn"],
           ["Cable label", "C01-CBL-nnnnn on both ends; campus fiber trunks C01-FIB-NS-E/W, C01-FIB-NC-E/W"],
           ["Zone tag", "zone-<name> on every device, VLAN and prefix: the 20 zones in the matrix"],
           ["VRF", "CORP, LEGAL, DC, GUEST, BUILDING, MGMT · RD 65010:<id> (10, 20, 40, 70, 80, 99)"],
           ["VLAN", "1xx corporate (199 quarantine), 2xx legal, 4xx data center, 6xx DMZ and extranet, 700 guest, "
                    "8xx building and rooms, 99x management; the same numbers at every branch"],
           ["Address plan", "10.<site>.0.0/16 per site; cloud 10.200.0.0/14; VPN 10.250.0.0/20 (C01 /21, C02 /21); "
                            "guest 172.20.0.0/16 on campus, 172.21.<site>.0/24 at branches"],
           ["Gateway", ".1 on the core pair or DIST-S inside a VRF; the ISFW for DC VLANs; the edge pair for "
                       "guest, DMZ and extranet"],
           ["Hide before sharing", "Layers 3 (mgmt IPs) and 4 (circuit IDs)"],
           ["Change", "Edit NetBox, then rebuild; never fix the drawing alone"]]
    scard = p.cell(ls, "", CARD, sx, 92, 1656, 400)
    p.cell(ls, "<b>Naming and addressing standards</b>", HEADING, sx + 16, 102, 1600, 22)
    table(p, ls, sx + 16, 128, [("ITEM", 180), ("STANDARD", 1440)], std, row_h=28)
    resize(p, scard, 36 + p.table_height + 16)
    height = max(bottom, 92 + 36 + p.table_height + 16) + 120
    p.model.set("pageHeight", str(int(height)))
    p.height = int(height)
    p.title_block(p.layer("Border & title block"), "C01", "Flow register and standards", f"7 of {SHEETS}", DATE,
                  PROJECT)
    return p


# ------------------------------------------------------------------ main
def build() -> ET.Element:
    return mxfile((overview(), logical(), physical(), wireless(), flows(), failover(), multisite(), register()),
                  "netdiagrams corporate template")


def main() -> None:
    tree = build()
    ET.indent(tree, space=" ")
    OUT.write_text(ET.tostring(tree, encoding="unicode") + "\n", "utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
