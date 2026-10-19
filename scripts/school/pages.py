"""The school template's pages, drawn from the facts in ``site.py``.

Sheets and their ids follow the S01 standard so page selection (--leave-out),
the book notes and the example watermarks work the same way:

    1 overview · 2 logical · 3 physical · 3b hardware (closets, PoE, optics)
    3d wireless · 4 flows · 5 failover · 6 multisite (district WAN)
    7 register (flow register and zone matrix) · 8 netbox
"""

from __future__ import annotations

import html
import re
from collections import defaultdict

from . import site as S

from netdiagrams import wireless as nb_wireless
from netdiagrams.education import EDUCATION
from netdiagrams import profiles, sync
from drawkit import FONT, MONO, NOTE, POINTS, RACK_PILL, ROW, TABLE, Page, _svg, zone_style

# ------------------------------------------------------------------ the school look, on the S01 kit
# Zone colors: (fill, stroke, text). Red stays for denied paths and faults; slate is enforcement.
ZONE_COLORS = {
    "staff": ("#F4F7FE", "#B3C8F8", "#2563EB"),
    "admin": ("#F0FBFA", "#99E2D8", "#0F766E"),
    "student": ("#F1FAF4", "#A7E3BF", "#15803D"),
    "guest": ("#F0F8FD", "#A5D3F0", "#0369A1"),
    "svc": ("#FFF8F1", "#F6C792", "#C2410C"),
    "bldg": ("#F8F5FE", "#D1BAF9", "#7C3AED"),
    "mgmt": ("#F5F7FA", "#CBD5E1", "#475569"),
    "out": ("#FFFFFF", "#E2E8F0", "#64748B"),
}

# Cable media pills (label background, border), the S01 legend's colors.
MEDIA_PILL = {
    "SMF OS2": ("#FEF08A", "#CA8A04"), "MMF OM4": ("#A5F3FC", "#0891B2"), "MMF OM3": ("#A5F3FC", "#0891B2"),
    "Cat6A": ("#E2E8F0", "#64748B"), "Cat6": ("#E2E8F0", "#64748B"), "DAC": ("#F1F5F9", "#334155"),
    "AOC": ("#F1F5F9", "#334155"), "PtP RF": ("#FCE7F3", "#DB2777"),
}


def text_style(size=10, color="#334155", bold=False, align="left", valign="top", extra="") -> str:
    return (f"text;html=1;whiteSpace=wrap;align={align};verticalAlign={valign};fontSize={size};"
            f"fontColor={color};{'fontStyle=1;' if bold else ''}spacing=2;{extra}{FONT}")


def card_style(fill="#FFFFFF", stroke="#E2E8F0", arc=24, shadow=False, extra="") -> str:
    return (f"rounded=1;absoluteArcSize=1;arcSize={arc};fillColor={fill};strokeColor={stroke};strokeWidth=1;"
            f"{'shadow=1;' if shadow else ''}html=1;whiteSpace=wrap;{extra}{FONT}")


def pill_style(fill, color, size=9, stroke="none", arc=22) -> str:
    return (f"rounded=1;absoluteArcSize=1;arcSize={arc};fillColor={fill};strokeColor={stroke};"
            f"fontColor={color};fontSize={size};html=1;whiteSpace=wrap;{FONT}")


def edge_style(color="#64748B", width=1.6, dashed=False, arrow=False, pill=None, extra="") -> str:
    """A link: orthogonal, its label a pill in the cable media's colors when ``pill`` is (fill, border)."""
    style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;arcSize=16;orthogonalLoop=1;jumpStyle=arc;jumpSize=8;"
             f"endArrow={'block' if arrow else 'none'};startArrow=none;strokeColor={color};strokeWidth={width};"
             f"{'dashed=1;dashPattern=6 4;' if dashed else ''}fontSize=9;fontColor=#334155;")
    style += f"labelBackgroundColor={pill[0]};labelBorderColor={pill[1]};" if pill else \
        "labelBackgroundColor=#FFFFFF;labelBorderColor=#E2E8F0;"
    return style + f"spacing=3;{'endSize=6;' if arrow else ''}html=1;{FONT}{extra}"


def line_style(color="#64748B", width=1.6, dashed=False, arrow=False, extra="") -> str:
    """A straight line between two points, as legends and markers draw them."""
    return (f"endArrow={'block' if arrow else 'none'};startArrow=none;strokeColor={color};strokeWidth={width};"
            f"{'dashed=1;dashPattern=6 4;' if dashed else ''}fontSize=10;fontColor={color};"
            f"labelBackgroundColor=#FFFFFF;edgeStyle=none;rounded=0;endSize=5;html=1;{FONT}{extra}")


# ------------------------------------------------------------------ icons
def _s(c: str) -> str:
    return f'fill="none" stroke="{c}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"'


ICON_COLORS = {  # family: (tile, stroke)
    "slate": ("#E7EAEF", "#334155"), "blue": ("#E3EBFC", "#2563EB"), "violet": ("#EEE8FD", "#7C3AED"),
    "teal": ("#E0F1F0", "#0D9488"), "green": ("#E3F4EA", "#15803D"), "amber": ("#FCEEDC", "#C2410C"),
    "sky": ("#E0F0FA", "#0369A1"), "grey": ("#ECEEF1", "#475569"), "pink": ("#FCE7F3", "#DB2777"),
    "indigo": ("#E6E8FB", "#4338CA"),
}


def icon(kind: str, family: str) -> str:
    bg, c = ICON_COLORS[family]
    s = _s(c)
    bodies = {
        "firewall": f'<rect x="7" y="8" width="18" height="16" rx="2" {s}/><path d="M7 13.3H25M7 18.6H25M13 8V13.3M19 8V13.3M16 13.3V18.6M10.5 18.6V24M21.5 18.6V24" {s}/>',
        "core": f'<path d="M13 13 7 7M9.8 7.4 7 7 7.4 9.8M19 13 25 7M24.6 9.8 25 7 22.2 7.4M13 19 7 25M7.4 22.2 7 25 9.8 24.6M19 19 25 25M22.2 24.6 25 25 24.6 22.2" {s}/><circle cx="16" cy="16" r="2" fill="{c}"/>',
        "switch": f'<path d="M8 11.5H24M21 8.5 24 11.5 21 14.5M24 20.5H8M11 17.5 8 20.5 11 23.5" {s}/>',
        "router": f'<circle cx="16" cy="16" r="8.5" {s}/><path d="M16 9.5V14M14 11.5 16 9.5 18 11.5M16 22.5V18M14 20.5 16 22.5 18 20.5M9.5 16H14M22.5 16H18" {s}/>',
        "server": f'<rect x="9" y="7" width="14" height="7.5" rx="2" {s}/><rect x="9" y="17.5" width="14" height="7.5" rx="2" {s}/><circle cx="12.5" cy="10.75" r="1.1" fill="{c}"/><circle cx="12.5" cy="21.25" r="1.1" fill="{c}"/>',
        "hypervisor": f'<rect x="8" y="8" width="7" height="7" rx="1.5" {s}/><rect x="17" y="8" width="7" height="7" rx="1.5" {s}/><rect x="8" y="17" width="7" height="7" rx="1.5" {s}/><rect x="17" y="17" width="7" height="7" rx="1.5" {s}/>',
        "wlc": f'<rect x="7" y="17" width="18" height="8" rx="2" {s}/><path d="M11.5 12.5A6.5 6.5 0 0 1 20.5 12.5M9 10A10 10 0 0 1 23 10" {s}/><circle cx="11" cy="21" r="1.1" fill="{c}"/>',
        "ap": f'<rect x="7" y="19" width="18" height="6" rx="3" {s}/><circle cx="16" cy="22" r="1.1" fill="{c}"/><path d="M12.5 14.1A5 5 0 0 1 19.5 14.1M9.5 11.5A9 9 0 0 1 22.5 11.5" {s}/>',
        "ptp": f'<path d="M9 24V12M6.5 12H11.5M23 24V12M20.5 12H25.5" {s}/><path d="M13 10.5Q16 8 19 10.5M14.5 13Q16 11.8 17.5 13" {s}/>',
        "camera": f'<rect x="6.5" y="11" width="13" height="9" rx="2" {s}/><path d="M19.5 14 25.5 11V20L19.5 17M10 20V24H16" {s}/><circle cx="11" cy="15.5" r="1.2" fill="{c}"/>',
        "door": f'<rect x="10" y="6.5" width="12" height="19" rx="1.5" {s}/><circle cx="18.5" cy="16" r="1.1" fill="{c}"/><rect x="13" y="10" width="6" height="4" rx="1" {s}/>',
        "hvac": f'<circle cx="16" cy="16" r="2" {s}/><path d="M16 14C16 9 21 8.5 21 11.5M18 16C23 16 23.5 21 20.5 21M16 18C16 23 11 23.5 11 20.5M14 16C9 16 8.5 11 11.5 11" {s}/>',
        "speaker": f'<path d="M8 13H12L17.5 8.5V23.5L12 19H8Z" {s}/><path d="M20.5 12.5A5 5 0 0 1 20.5 19.5M23 10A8.5 8.5 0 0 1 23 22" {s}/>',
        "phone": f'<rect x="8" y="9" width="16" height="15" rx="2" {s}/><path d="M11 9V7.5H21V9M12 14H20" {s}/><circle cx="12.5" cy="18" r=".9" fill="{c}"/><circle cx="16" cy="18" r=".9" fill="{c}"/><circle cx="19.5" cy="18" r=".9" fill="{c}"/><circle cx="12.5" cy="21" r=".9" fill="{c}"/><circle cx="16" cy="21" r=".9" fill="{c}"/><circle cx="19.5" cy="21" r=".9" fill="{c}"/>',
        "laptop": f'<rect x="9" y="9" width="14" height="10" rx="1.5" {s}/><path d="M6.5 22.5H25.5L23.5 19H8.5Z" {s}/>',
        "display": f'<rect x="6.5" y="8" width="19" height="12.5" rx="1.5" {s}/><path d="M16 20.5V24M12 24H20" {s}/>',
        "printer": f'<rect x="7" y="13" width="18" height="8" rx="2" {s}/><path d="M11 13V7.5H21V13M11 18.5H21V24.5H11Z" {s}/>',
        "cloud": f'<path d="M11 22.5H22A4 4 0 0 0 22.3 14.5 6 6 0 0 0 10.8 13.8 4.4 4.4 0 0 0 11 22.5Z" {s}/>',
        "building": f'<path d="M7 25V12L16 7 25 12V25M7 25H25M11 25V17H14V25M18 17H21V20H18Z" {s}/>',
        "people": f'<circle cx="13" cy="12" r="3.2" {s}/><path d="M7 23.5C7 19.5 9.5 17.5 13 17.5S19 19.5 19 23.5" {s}/><circle cx="21" cy="12.5" r="2.5" {s}/><path d="M20.5 17.5C23.5 17.5 25.5 19.2 25.5 23" {s}/>',
        "shield": f'<path d="M16 6.5 24 9.5V15.5C24 20.5 20.5 23.8 16 25.5 11.5 23.8 8 20.5 8 15.5V9.5Z" {s}/><path d="M12.5 16 15 18.5 19.5 13.5" {s}/>',
        "filter": f'<path d="M7.5 8.5H24.5L18 16.5V23.5L14 21.5V16.5Z" {s}/>',
        "book": f'<path d="M16 10C13.5 8 10 8 7.5 9V23C10 22 13.5 22 16 24 18.5 22 22 22 24.5 23V9C22 8 18.5 8 16 10ZM16 10V24" {s}/>',
        "wan": f'<circle cx="16" cy="16" r="9" {s}/><path d="M7 16H25M16 7C13 10 13 22 16 25M16 7C19 10 19 22 16 25" {s}/>',
        "bus": f'<rect x="7" y="8" width="18" height="14" rx="3" {s}/><path d="M7 15H25M10.5 22V24.5M21.5 22V24.5" {s}/><circle cx="11" cy="18.5" r="1" fill="{c}"/><circle cx="21" cy="18.5" r="1" fill="{c}"/>',
        "chart": f'<path d="M8 24H24M10 24V16M14.5 24V11M19 24V14M23 24V9" {s}/>',
        "key": f'<circle cx="12" cy="16" r="4.5" {s}/><path d="M16.5 16H25M22 16V19.5M25 16V19" {s}/>',
        "alert": f'<path d="M16 7 25.5 24H6.5Z" {s}/><path d="M16 13V18" {s}/><circle cx="16" cy="21" r="1" fill="{c}"/>',
        "tray": f'<rect x="7" y="9" width="18" height="14" rx="2" {s}/><path d="M7 17H12L13.5 19.5H18.5L20 17H25" {s}/>',
    }
    return "data:image/svg+xml," + _svg(bg, bodies[kind])


ROLE_ICONS = {  # NetBox role slug -> (icon, family)
    "firewall": ("firewall", "slate"), "core-switch": ("core", "blue"), "access-switch": ("switch", "blue"),
    "oob-switch": ("switch", "grey"), "router": ("router", "violet"), "sdwan-edge": ("router", "violet"),
    "server": ("server", "grey"), "hypervisor": ("hypervisor", "grey"), "wireless-controller": ("wlc", "teal"),
    "access-point": ("ap", "teal"), "ptp-radio": ("ptp", "pink"), "camera": ("camera", "violet"),
    "nvr": ("server", "amber"), "access-control": ("door", "violet"), "bas-controller": ("hvac", "violet"),
    "pa-system": ("speaker", "violet"), "ip-phone": ("phone", "blue"), "printer": ("printer", "blue"),
    "classroom-display": ("display", "blue"), "content-filter": ("filter", "slate"),
}


def labelled(p: Page, parent, x, y, w, h, title, sub="", ico=None, size=11, sub_size=9, arc=16,
             stroke="#E2E8F0", stroke_w=1, valign="middle", data=None, fill="#FFFFFF", spacing=None) -> str:
    """A white card with an icon tile on the left: the S01 host and device card."""
    img = ""
    if ico:
        kind, family = ico
        isz = 30 if h >= 50 else 22
        img = (f"image={icon(kind, family)};imageWidth={isz};imageHeight={isz};imageAlign=left;"
               f"imageVerticalAlign=middle;")
    left = spacing if spacing is not None else (38 if h >= 50 else 30)
    style = (f"shape=label;rounded=1;absoluteArcSize=1;arcSize={arc};fillColor={fill};strokeColor={stroke};"
             f"strokeWidth={stroke_w};shadow=1;align=left;verticalAlign={valign};spacingTop=5;"
             f"spacingLeft={left};fontSize={size};fontColor=#0F172A;whiteSpace=wrap;html=1;{POINTS}{FONT}{img}")
    value = f"<b>{title}</b>" + (f'<br><span style="font-size:{sub_size}px;color:#64748B">{sub}</span>'
                                 if sub else "")
    return p.cell(parent, value, style, x, y, w, h, data)


def device(p: Page, parent, x, y, dev: dict, w=240, h=56, ip_layer=None, sn_layer=None, label=None) -> str:
    """A NetBox device card: name and model as placeholders, rack pill, IP and serial tags."""
    kind, family = ROLE_ICONS.get(dev["role"], ("server", "grey"))
    title = label or "%name%"
    value = (f"<b>{title}</b><br><span style=\"font-size:9px;color:#64748B\">%device_type%</span>")
    style = ("shape=label;rounded=1;absoluteArcSize=1;arcSize=16;fillColor=#FFFFFF;"
             f"strokeColor={'#334155' if dev['role'] == 'firewall' else '#E2E8F0'};"
             f"strokeWidth={'1.5' if dev['role'] == 'firewall' else '1'};shadow=1;align=left;verticalAlign=top;"
             "spacingTop=5;spacingLeft=38;fontSize=11;fontColor=#0F172A;whiteSpace=wrap;html=1;"
             f"{POINTS}{FONT}image={icon(kind, family)};imageWidth=30;imageHeight=30;imageAlign=left;"
             "imageVerticalAlign=middle;")
    cid = p.cell(parent, value, style, x, y, w, h, {"placeholders": "1", **device_data(dev)})
    if dev.get("rack") or dev.get("location"):
        pill = "%rack% · U%position%" if dev.get("position") else ("%location%" if not dev.get("rack") else "%rack%")
        p.cell(cid, pill, RACK_PILL, w - 62, 6, 56, 13,
               {"placeholders": "1", "tooltip": "Opens the rack (or location) in NetBox"})
    tag = (f"fontSize=8;fontColor=#475569;align=left;verticalAlign=middle;html=1;spacing=0;{MONO}"
           "text;whiteSpace=nowrap;")
    if ip_layer and dev.get("primary_ip4"):
        p.cell(ip_layer, dev["primary_ip4"].split("/")[0], tag, x + 38, y + h - 17, 110, 12)
    if sn_layer and dev.get("serial"):
        p.cell(sn_layer, f"SN {dev['serial']}", tag + "align=right;", x + w - 100, y + h - 17, 96, 12)
    return cid


def table(p: Page, parent, x, y, headers: list[tuple[str, float]], rows: list[list], row_h=20, head_h=22,
          stroke="#E2E8F0", fill="#FFFFFF", size=10, head_fill="#F8FAFC", first_bold=True, mono_cols=(),
          link_cols=(), header_color="#64748B", values_style: dict | None = None) -> str:
    """A kit table in the school's type: first column bold blue, chosen columns monospaced. Cells may be
    (text, link) pairs; plain text is escaped."""
    base = ("shape=partialRectangle;html=1;whiteSpace=wrap;connectable=0;strokeColor=inherit;overflow=hidden;"
            "top=0;left=0;bottom=0;right=0;pointerEvents=1;align=left;spacingLeft=6;")

    def body(c, link):
        color = "#1D4ED8" if c in link_cols or (c == 0 and first_bold) else "#334155"
        return (base + f"fillColor=none;fontSize={size};fontColor={color};"
                f"{'fontStyle=1;' if c == 0 and first_bold else ''}{MONO if c in mono_cols else FONT}"
                + (values_style or {}).get(c, ""))

    def text(v):
        return html.escape(str(v)) if "<" not in str(v) else str(v)

    rows = [[(text(v[0]), v[1]) if isinstance(v, tuple) else text(v) for v in row] for row in rows]
    return p.table(parent, x, y, headers, rows, row_h, head_h,
                   style=TABLE.replace("fontSize=10;", f"fontSize={size};")
                   .replace("strokeColor=#E2E8F0", f"strokeColor={stroke}").replace("fillColor=#FFFFFF", f"fillColor={fill}"),
                   row=ROW.replace("fontSize=10;", f"fontSize={size};"),
                   head=base + f"fillColor={head_fill};fontSize=9;fontColor={header_color};fontStyle=1;{FONT}", body=body)


def device_data(dev: dict) -> dict:
    """Shape data in NetBox field names, plus drawing-only x_* fields."""
    keys = ("name", "role", "manufacturer", "device_type", "platform", "serial", "asset_tag", "status", "site",
            "location", "rack", "position", "face", "primary_ip4", "virtual_chassis", "vc_position",
            "description", "tags")
    data = {k: dev.get(k, "") for k in keys}
    data["status"] = dev.get("status", "active")
    data["tags"] = ",".join(dev.get("tags", []))
    for k, v in dev.get("cf", {}).items():
        data[f"cf_{k}"] = v
    for k, v in dev.get("x", {}).items():
        data[f"x_{k}"] = v
    data["tooltip"] = "\n".join(f"{k}: {v}" for k, v in data.items() if v)
    data["link"] = f"https://netbox.example.com/dcim/devices/?name={dev['name']}"
    data["linkTarget"] = "_blank"
    return data

TOTAL = 10
BLUE, SLATE, GREEN, ORANGE, RED, PINK, VIOLET = "#2563EB", "#334155", "#059669", "#EA580C", "#DC2626", "#DB2777", \
    "#7C3AED"


# ------------------------------------------------------------------ shared furniture
def frame(p: Page, title: str, subtitle: str, drawing: str, sheet: str) -> str:
    """Border, title, subtitle, logo box and the title block. Returns the title layer id."""
    border = p.layer("Border & title block")
    p.cell(border, "", card_style(fill="none", arc=36), 10, 10, p.width - 20, p.height - 20)
    p.cell(border, title, text_style(size=22, color="#0F172A", bold=True), 24, 18, 1600, 32)
    p.cell(border, subtitle, text_style(size=12, color="#64748B"), 24, 52, p.width - 600, 22)
    tx, ty = p.width - 772, p.height - 80
    # The title block sits on its own card: builds add the provenance line inside it and copy it to new sheets.
    p.cell(border, "", card_style(fill="#FFFFFF", stroke="#E2E8F0", arc=16), tx - 134, ty - 8, 134 + 744 + 12, 68)
    p.cell(border, "<b>LOGO</b>", pill_style("#E8EBF3", "#1E3A8A", size=11, arc=16), tx - 122, ty + 4, 108, 44)
    table(p, border, tx, ty, [("PROJECT", 250), ("DRAWING", 200), ("SITE", 60), ("REV", 54), ("DATE", 84),
          ("SHEET", 76)],
          [[f"{S.DISTRICT} · network standard", drawing, S.SITE_CODE, "A", "2026-10-14", f"{sheet} of {TOTAL}"]],
          row_h=26, head_h=26, stroke="none", head_fill="none", first_bold=False, header_color="#94A3B8")
    return border


def band(p: Page, layer: str, y: float, h: float, pill: str, label: str, w: float | None = None) -> None:
    p.cell(layer, "", card_style(arc=28), 24, y, w or (p.width - 48), h)
    p.cell(layer, f"<b>{pill}</b>", pill_style("#E9ECEF", "#64748B", size=10), 34, y + 10, 36, 22)
    p.cell(layer, label,
           text_style(size=10, color="#94A3B8", bold=True, align="right", valign="middle", extra="horizontal=0;"), 32,
           y + 38, 40, h - 48)


def zone_box(p: Page, layer: str, key: str, x, y, w, h, title: str, sub: str) -> str:
    fill, stroke, color = ZONE_COLORS[key]
    value = (f"ZONE {key.upper()} · {title}<br><span style=\"font-size:10px;font-weight:normal;color:#64748B\">"
             f"{sub}</span>")
    style = zone_style(fill, stroke, color)
    # The zone's tag on its box: netbox-setup offers one zone tag per zone the template draws.
    return p.cell(layer, value, style, x, y, w, h, {"tags": f"zone-{key}"})


LEGEND_ITEMS = [
    ("firewall", "slate", "Firewall (enforcement)"), ("core", "blue", "Core switch"),
    ("switch", "blue", "Access switch / stack"), ("wlc", "teal", "Wireless gateway"),
    ("ap", "teal", "Access point"), ("ptp", "pink", "Point-to-point radio"),
    ("server", "grey", "Server / host"), ("server", "amber", "Camera recorder (NVR)"),
    ("camera", "violet", "Camera"), ("door", "violet", "Door controller"),
    ("hvac", "violet", "HVAC controller"), ("speaker", "violet", "PA, bells, clocks"),
]


def legend(p: Page, x: float, y: float, w: float = 380, lines: bool = True, zones: bool = True,
           icons: bool = True) -> None:
    layer = p.layer("Legend")
    rows = (len(LEGEND_ITEMS) + 1) // 2 if icons else 0
    h = 44 + rows * 26 + (128 if lines else 0) + (64 if zones else 0)
    p.cell(layer, "", card_style(arc=24, shadow=True), x, y, w, h)
    p.cell(layer, "Legend", text_style(size=13, color="#0F172A", bold=True), x + 16, y + 10, 200, 22)
    for i, (kind, family, label) in enumerate(LEGEND_ITEMS if icons else []):
        cx, cy = x + 14 + (i % 2) * (w / 2 - 4), y + 36 + (i // 2) * 26
        p.cell(layer, label,
               "text;html=1;fontSize=10;fontColor=#334155;align=left;verticalAlign=middle;spacingLeft=30;"
               f"fontFamily=Inter;image={icon(kind, family)};imageWidth=22;imageHeight=22;imageAlign=left;"
               "imageVerticalAlign=middle;", cx, cy, w / 2 - 20, 24)
    cy = y + 44 + rows * 26
    if lines:
        for n, (color, width, dashed, arrow, text) in enumerate([
                ("#64748B", 2.5, False, False, "Link · pill = LAG · speed · media"),
                (BLUE, 3.5, False, False, "Uplink to the core (weight = speed)"),
                (GREEN, 2, False, True, "Permitted flow (initiator → responder)"),
                (ORANGE, 2, True, True, "Conditional (named group, approval or window)"),
                (RED, 2, True, False, "Denied path")]):
            p.edge(layer, None, None, line_style(color, width, dashed, arrow), "", src_pt=(x + 18, cy + 10 + n * 24),
                   tgt_pt=(x + 70, cy + 10 + n * 24))
            p.cell(layer, text, text_style(size=10, valign="middle"), x + 80, cy + n * 24, w - 90, 20)
        p.cell(layer, "✕", "ellipse;fillColor=#DC2626;strokeColor=#FFFFFF;strokeWidth=2;"
               "fontColor=#FFFFFF;fontSize=11;fontStyle=1;html=1;fontFamily=Inter;", x + 34, cy + 96, 20, 20)
        cy += 128
    if zones:
        for i, key in enumerate(["staff", "admin", "student", "guest", "svc", "bldg", "mgmt"]):
            fill, stroke, color = ZONE_COLORS[key]
            p.cell(layer, f"<b>{key.upper()}</b>", pill_style(fill, color, stroke=stroke),
                   x + 14 + (i % 4) * ((w - 28) / 4), cy + (i // 4) * 28, (w - 28) / 4 - 6, 22)


# ------------------------------------------------------------------ 1 overview
def overview() -> Page:
    p = Page("overview", "1 · Overview — for the principal and the board", 2000, 1180, prefix="s")
    L = p.layer("Overview")
    frame(p, "How every school network is protected",
          "Overview for the principal, the superintendent and the board — no technical detail. "
          "The same design is used at every school in the district.", "Overview — principal", "1")

    def tier(y, label, color, title, sub, kind, family, h=90):
        p.cell(L, label, text_style(size=11, color=color, bold=True, align="right", valign="middle"), 60, y, 100, h)
        return labelled(p, L, 170, y, 1060, h, f'<span style="font-size:16px">{title}</span>', sub, (kind, family),
                        size=12, sub_size=12, arc=24, spacing=64)

    def gate(y, text):
        return p.cell(L, text,
                      "shape=label;rounded=1;absoluteArcSize=1;arcSize=44;fillColor=#F1F5F9;strokeColor=#CBD5E1;strokeWidth=1;"
                      "align=left;verticalAlign=middle;spacingLeft=34;fontSize=12;fontColor=#334155;html=1;whiteSpace=wrap;"
                      f"fontFamily=Inter;image={icon('firewall', 'slate')};imageWidth=18;imageHeight=18;imageAlign=left;",
                      170, y, 1060, 40)

    out = tier(100, "Outside", "#64748B", "Internet, cloud apps and the district office",
               "Gradebook and student records, learning platform, email and testing, reached over the district fiber",
               "cloud", "grey", 80)
    f1 = gate(200, "<b>Web filter</b> — every student and guest web request is filtered at the district office "
                   "(see the internet safety policy)")
    staff = tier(260, "Staff", "#2563EB", "Staff & classrooms",
                 "Teachers' laptops, phones, printers and classroom displays", "people", "blue", 80)
    admin = tier(356, "Office", "#0F766E", "Front office & student services",
                 "Office, nurse and counseling: student records and health information", "book", "teal", 80)
    g1 = gate(456, "<b>Security gate</b> — a pair of firewalls checks traffic between every group on this page "
                   "(one takes over if the other fails)")
    stu = tier(516, "Students", "#15803D", "Students", "1,850 Chromebooks, computer labs and state testing rooms",
               "laptop", "green", 80)
    guest = tier(612, "Guests", "#0369A1", "Guests & personal phones",
                 "Internet only, filtered. Never reaches school systems", "people", "sky", 80)
    g2 = gate(712, "<b>Same security gate</b> — staff reach cameras, doors and heating only through their servers")
    svc = tier(772, "Buffer", "#C2410C", "School services — the only meeting point",
               "Camera recorder, door access, PA and heating servers. Nothing passes straight through",
               "server", "amber", 80)
    p.cell(L, "", card_style(fill="#F8F5FE", stroke="#D1BAF9"), 170, 870, 1060, 200)
    p.cell(L, "Building", text_style(size=11, color="#7C3AED", bold=True, align="right", valign="middle"), 60, 870,
           100, 200)
    p.cell(L, '<b><span style="font-size:16px">Building systems</span></b> — each kind is its '
           "own sealed group, with no internet access", text_style(size=12, color="#0F172A"), 190, 880, 700, 24)
    for i, (t, sub, k) in enumerate([("Cameras", "Every entrance · 90 days of video", "camera"),
                                     ("Door access", "8 controlled doors · lockdown", "door"),
                                     ("Heating & cooling", "Boilers and air handlers", "hvac"),
                                     ("PA, bells & clocks", "Announcements · intercom", "speaker")]):
        labelled(p, L, 190 + i * 258, 920, 240, 100, t, sub, (k, "violet"), size=12, sub_size=11)
    # The student path that must never exist.
    p.edge(L, stu, admin, edge_style(RED, 2, dashed=True), "", exit=(0.93, 0), entry=(0.93, 1))
    p.cell(L, "no student path<br>to the office", text_style(size=9, color=RED, align="right", valign="middle"), 1000,
           462, 150, 28)
    p.cell(L, "✕", "ellipse;fillColor=#DC2626;strokeColor=#FFFFFF;strokeWidth=2;fontColor=#FFFFFF;"
           "fontSize=11;fontStyle=1;html=1;fontFamily=Inter;", 1166, 466, 20, 20)
    p.edge(L, out, svc, edge_style(VIOLET, 1.6, dashed=True, arrow=True),
           "Vendors: approved,<br>recorded sessions only", exit=(0.75, 1), entry=(0.75, 0), pos=0.62)

    p.cell(L, "What this means for the school", text_style(size=17, color="#0F172A", bold=True), 1300, 100, 640, 30)
    for i, (t, body, k, fam) in enumerate([
            ("Students can't reach office computers", "No student or guest device has a network path to the "
             "front office or the nurse's computers. Grades and the SIS need a staff sign-in.", "shield", "teal"),
            ("Filtered for every student", "Every student and guest web request goes through the district web "
             "filter, on any device, in any building.", "filter", "slate"),
            ("Cameras and doors stay up", "Cameras keep recording and doors keep working if the internet or the "
             "district link goes down.", "camera", "violet"),
            ("Vendors are supervised", "Outside companies, such as the heating vendor, connect only through an "
             "approved, recorded session.", "key", "violet"),
            ("One failure won't close the school", "Firewalls, core switches and wireless gateways come in pairs: "
             "if one fails, the other takes over.", "core", "blue"),
            ("Testing day is protected", "State testing rooms have their own network, kept apart and given "
             "priority on the district link.", "chart", "green")]):
        labelled(p, L, 1300, 140 + i * 152, 640, 136, f'<span style="font-size:15px">{t}</span>', body, (k, fam),
                 size=12, sub_size=13, spacing=60)
    return p


# ------------------------------------------------------------------ 2 logical
def logical() -> Page:
    p = Page("logical", "2 · Logical — Zones, VLANs, Subnets", 2400, 1640, prefix="s")
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    bands = p.layer("Trust tiers")
    zl = p.layer("Zones")
    tl = p.layer("VLAN & subnet tables (hide before sharing)")
    ll = p.layer("Logical links (L3 adjacencies)")
    dl = p.layer("Routing devices & hosts")
    nl = p.layer("Notes & breakouts")
    frame(p, f"{S.SITE_CODE} · {S.SITE_NAME} — Logical Architecture",
          "Zones · VLANs · subnets · VRFs. The firewall pair is the only path between zones: every VRF on the core "
          "routes to it, and every routed VLAN, subnet and gateway is listed in the zone that owns it.",
          f"Logical — {S.SITE_CODE}", "2")
    for x in (80, 980, 1050, 1350, 1420):
        p.edge(guides, None, None, line_style("#F4A6A6", 1, dashed=True), "", src_pt=(x, 0), tgt_pt=(x, p.height))

    band(p, bands, 82, 170, "OUT", "INTERNET · WAN")
    band(p, bands, 272, 300, "T1", "STAFF · OFFICE")
    band(p, bands, 592, 220, "T2", "STUDENTS · GUESTS")
    band(p, bands, 832, 260, "T3", "SERVICES · BUILDING")
    band(p, bands, 1112, 410, "M", "MANAGEMENT")

    # Outside
    cloud = labelled(p, dl, 100, 105, 420, 120, "Cloud apps", "Gradebook and student records (SIS) · learning "
                     "platform · email · state testing platform", ("cloud", "grey"), size=12, sub_size=10)
    dc = labelled(p, dl, 560, 105, 420, 120, "District data center (DO)", "Directory · DNS · DHCP · RADIUS · phone "
                  "system · VMS archive · web filter", ("building", "grey"), size=12, sub_size=10)
    wan = labelled(p, dl, 1050, 100, 300, 132, "DISTRICT WAN", "HPSD fiber ring · 2× 10G<br>backup: broadband + IPsec",
                   ("wan", "grey"), size=12, sub_size=10, arc=60, spacing=48)
    inet = labelled(p, dl, 1420, 105, 420, 120, "Internet (district edge)", "Firewall pair and web filter at the "
                    "district office · ISP-A · ISP-B · no internet breakout at schools", ("filter", "slate"), size=12,
                    sub_size=10)
    vend = labelled(p, dl, 1880, 105, 460, 120, "Vendors (remote)", "HVAC, door access and camera integrators: "
                    "district remote access only, approved and recorded", ("key", "violet"), size=12, sub_size=10)
    for a in (cloud, dc):
        p.edge(ll, a, wan, edge_style(), "", exit=(1, 0.5), entry=(0, 0.5))
    p.edge(ll, inet, wan, edge_style(), "", exit=(0, 0.5), entry=(1, 0.5))
    p.edge(ll, vend, inet, edge_style(VIOLET, dashed=True, arrow=True), "", exit=(0, 0.5), entry=(1, 0.5))

    # Spine
    fw = labelled(p, dl, 1050, 290, 300, 116, "HS1-FW · HA pair", "FortiGate 200F · A/P<br>Zones: STAFF ⇄ ADMIN ⇄ "
                  "STUDENT ⇄ GUEST ⇄ SVC ⇄ BLDG ⇄ MGMT ⇄ WAN<br>Gateway for GUEST and BYOD", ("firewall", "slate"),
                  size=12, sub_size=9, stroke="#334155", stroke_w=1.5, valign="top")
    core = labelled(p, dl, 1050, 446, 300, 106, "HS1-CORE · VSX pair",
                    "CX 8360 ×2 · collapsed core<br>VRFs: STAFF · "
                    "ADMIN · STUDENT · SVC · BLDG · MGMT · WAN<br>SVI gateways, no routing between VRFs",
                    ("core", "blue"), size=12, sub_size=9, valign="top")
    p.edge(ll, wan, core, edge_style(SLATE), "VRF WAN<br>to district", points=[(1385, 206), (1385, 467)],
           exit=(1, 0.8), entry=(1, 0.2))
    p.edge(ll, core, fw, edge_style(SLATE, 2.5), "lag1 · one /29 transit per VRF", exit=(0.5, 0), entry=(0.5, 1))

    def vlan_table(x, y, zone):
        rows = [[str(v), n, s, g] for v, n, s, g, z in S.VLANS if z == zone]
        return table(p, tl, x, y, [("VLAN", 46), ("NAME", 124), ("SUBNET", 124), ("GATEWAY · VRF", 160)], rows,
                     link_cols=(2,))

    def hosts(x, y, cards, cols=2, w=160):
        for i, (t, sub, k, fam) in enumerate(cards):
            labelled(p, dl, x + (i % cols) * (w + 16), y + (i // cols) * 54, w, 44, t, sub, (k, fam), size=10,
                     sub_size=8)

    zones = {z[0]: z for z in S.ZONES}
    layout = {  # zone: (x, y, w, h)
        "staff": (80, 290, 900, 264), "admin": (1420, 290, 940, 264),
        "student": (80, 610, 900, 186), "guest": (1420, 610, 940, 186),
        "svc": (80, 850, 900, 226), "bldg": (1420, 850, 940, 226),
        "mgmt": (80, 1130, 900, 250),
    }
    boxes = {}
    for key, (x, y, w, h) in layout.items():
        _, title, sub, color, vrf = zones[key]
        boxes[key] = zone_box(p, zl, key, x, y, w, h, title, f"VRF {vrf} · {sub}")
        vlan_table(x + 20, y + 48, key)
    hosts(620, 338, [("Teacher laptops", "802.1X wired + Wi-Fi", "laptop", "blue"),
                     ("IP phones", "VOICE · PoE", "phone", "blue"),
                     ("Printers / copiers", "PRINTERS", "printer", "blue"),
                     ("Classroom displays", "CLASS-AV · casting", "display", "blue")])
    hosts(1960, 338, [("Front office PCs", "OFFICE", "people", "teal"), ("Nurse's office", "HEALTH", "book", "teal"),
                      ("Counseling", "OFFICE", "people", "teal"), ("Badge printers", "OFFICE · visitor desk",
                                                                   "printer", "teal")])
    hosts(620, 658, [("Chromebooks (1:1)", "STUDENT-WIFI", "laptop", "green"),
                     ("Computer labs", "STUDENT-LABS", "display", "green"),
                     ("Testing rooms", "TESTING · allow-list", "chart", "green")])
    hosts(1960, 658, [("Visitors", "GUEST-WIFI · portal", "people", "sky"),
                      ("Personal phones", "BYOD · rotating key", "phone", "sky"),
                      ("Event Wi-Fi", "gym · auditorium", "people", "sky")])
    hosts(620, 898, [("Camera recorder", "HS1-NVR-01 · VMS", "server", "amber"),
                      ("Door access server", "VM on HS1-SRV-01", "door", "amber"),
                      ("PA & bell server", "HS1-PA-01 schedule", "speaker", "amber"),
                      ("HVAC front end", "VM · vendor access", "hvac", "amber"),
                      ("Local cache & print", "HS1-SRV-01", "server", "amber")])
    hosts(1960, 898, [("Cameras", "CAMERAS · PoE", "camera", "violet"),
                       ("Door controllers ×8", "DOOR-ACCESS", "door", "violet"),
                       ("HVAC controllers", "HVAC-BAS · BACnet/IP", "hvac", "violet"),
                       ("PA, bells, clocks", "PA-CLOCKS", "speaker", "violet")])
    hosts(620, 1178, [("Switch & AP mgmt", "NET-MGMT · AP-MGMT", "switch", "grey"),
                      ("OOB console", "HS1-OOB-SW01", "key", "grey")])

    # Zone links to the core (one VRF each); the firewall routes between them.
    def side(key, right, xs):
        x, y, w, h = layout[key]
        return ((xs, 1), (0 if right else 1, 36 / h), [(1050 + 300 * xs, y + 36)])

    entries = {"staff": ((0, 0.5), (1, 0.2), None), "admin": ((1, 0.5), (0, 0.2), None),
               "student": side("student", False, 0.12), "guest": side("guest", True, 0.88),
               "svc": side("svc", False, 0.28), "bldg": side("bldg", True, 0.72), "mgmt": side("mgmt", False, 0.5)}
    for key, (exit_, entry, pts) in entries.items():
        label = f"VRF {S.ZONE_VRF[key]}"
        if key == "guest":
            label = "GUEST on the firewall · internet only"
        p.edge(ll, core, boxes[key], edge_style(SLATE if key != "guest" else "#0369A1"), label, points=pts,
               exit=exit_, entry=entry)

    # Firewall interfaces and notes.
    p.cell(dl, "HS1-FW logical interfaces", text_style(size=12, color="#334155", bold=True), 1420, 1124, 520, 22)
    table(p, dl, 1420, 1150, [("INTERFACE", 110), ("ZONE", 90), ("VLAN", 56), ("IP / PREFIX", 160), ("NOTE", 130)], [
          ["lag1.199", "STAFF", "199", "10.20.255.2/29", "transit"],
          ["lag1.169", "ADMIN", "169", "10.20.255.10/29", "transit"],
          ["lag1.299", "STUDENT", "299", "10.20.255.18/29", "transit"],
          ["lag1.310", "GUEST", "310", "172.20.0.1/22", "gateway · portal"],
          ["lag1.320", "GUEST", "320", "172.20.8.1/21", "gateway"],
          ["lag1.599", "SVC", "599", "10.20.255.42/29", "transit"],
          ["lag1.499", "BLDG", "499", "10.20.255.34/29", "transit"],
          ["lag1.999", "MGMT", "999", "10.20.255.50/29", "transit"],
          ["lag1.990", "WAN", "990", "10.255.20.6/29", "to district"]], row_h=19, mono_cols=(0, 3))
    p.cell(nl, "<b>Address plan</b> · 10.(site×10).0.0/16 per school: DO 10.10 · HS1 10.20 · "
           "MS1 10.30 · ES1 10.40 · ES2 10.50.<br>Same VLAN IDs at every school: 1xx staff and office, 2xx students, "
           "3xx guests, 4xx building, 5xx services, 9xx management; x99 is the zone's transit to the firewall.", NOTE,
           100, 1270, 840, 90)
    p.cell(guides, "<b>Zone rules</b><br>• No student VLAN is trunked to the front office.<br>"
           "• Building systems reach nothing but their own server.<br>• Guests leave by the firewall to the internet, "
           "filtered at the district office.", NOTE, 100, 450, 474, 96)
    legend(p, 1960, 1124, 380, lines=True, zones=True)
    return p


# ------------------------------------------------------------------ 3 physical
def _media_pill(media):
    return MEDIA_PILL.get(media, ("#FFFFFF", "#E2E8F0"))


def _uplink_routes() -> dict:
    """Closet uplinks as cable-tray routes: up from the stack to a tray level, across, up a lane to the core.

    Each of the eight lines gets its own tray level; the order with the fewest crossings is chosen.
    """
    import itertools
    lines = []
    for n in range(1, 5):
        members = S.IDFS[n - 1][3]
        x0 = 110 + (n - 1) * 370
        for to2 in (False, True):
            fx = 0.3 if not to2 else 0.7
            sx = x0 + 45 + 240 * fx
            core_x = 1040 if to2 else 710
            ex = 0.2 + 0.18 * (n - 1)
            lines.append(((n, to2), sx, core_x + 240 * ex, fx, ex))
    best = None
    levels = [880 + 12 * i for i in range(8)]
    for order in itertools.permutations(range(8)):
        tray = {lines[i][0]: levels[order[i]] for i in range(8)}
        cross = 0
        for (k, sx, lx, *_), (k2, sx2, lx2, *_) in itertools.permutations(lines, 2):
            y = tray[k]
            lo, hi = min(sx, lx), max(sx, lx)
            if lo < sx2 < hi and y > tray[k2]:
                cross += 1  # through the other line's rise from its stack
            if lo < lx2 < hi and y < tray[k2]:
                cross += 1  # through the other line's lane up to the core
        if best is None or cross < best[0]:
            best = (cross, tray)
    out = {}
    for k, sx, lx, fx, ex in lines:
        y = best[1][k]
        out[k] = ((fx, 0), (ex, 1), [(sx, y), (lx, y)])
    return out


UPLINK_ROUTES = _uplink_routes()


def physical() -> Page:
    p = Page("physical", "3 · Physical — Devices, Uplinks, Trunks", 2880, 1720, prefix="s")
    p.layer("Guides (hidden)", visible=False, locked=True)
    bl = p.layer("Zones (buildings · closets)")
    links = p.layer("2 · Links (LAG · speed · VLANs)")
    dv = p.layer("1 · Devices")
    ipl = p.layer("3 · Mgmt IPs (hide before sharing)")
    snl = p.layer("3b · Serial numbers")
    cl = p.layer("4 · Circuit IDs (hide before sharing)")
    nl = p.layer("5 · Breakouts (closet notes)")
    lr = p.layer("6 · Link register")
    ar = p.layer("7 · Asset register")
    frame(p, f"{S.SITE_CODE} · {S.SITE_NAME} — Physical Architecture",
          "Devices · uplinks · LAGs · trunked VLANs · room and rack on every device. Hover a device or Edit Data "
          "(Ctrl+M) for its full asset record.", f"Physical — {S.SITE_CODE}", "3")
    band(p, bl, 82, 132, "WAN", "CIRCUITS", w=1940)
    band(p, bl, 232, 760, "MDF", "MDF-101 · MAIN CLOSET", w=1940)
    band(p, bl, 1010, 600, "IDF", "CLOSETS · WINGS · STADIUM", w=1940)

    ids: dict[str, str] = {}

    def dev(name, x, y, w=240, h=56):
        ids[name] = device(p, dv, x, y, S.BY_NAME[name], w, h, ip_layer=ipl, sn_layer=snl)
        return ids[name]

    def group(x, y, w, h, title, sub, color="#2563EB", fill="#F8FAFF", stroke="#C7D7FB"):
        p.cell(bl, f"<b>{title}</b> <span style=\"font-weight:normal;color:#64748B\">{sub}</span>",
               f"rounded=1;absoluteArcSize=1;arcSize=18;fillColor={fill};strokeColor={stroke};strokeWidth=1;"
               f"dashed=1;dashPattern=4 3;verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontSize=10;"
               f"fontColor={color};html=1;whiteSpace=wrap;fontFamily=Inter;", x, y, w, h)

    # Circuits
    circuit_ids = {}
    # Each circuit drops to its own core on its own line: the DO leg left of the firewalls, the rest right.
    card_x = dict(zip([c[0] for c in S.CIRCUITS], (400, 1630, 1330)))
    wan_route = {"HPSD-DF-020": ([(530, 395), (734, 395)], (0.1, 0)),
                 "HPSD-DF-021": ([(1760, 392), (1256, 392)], (0.9, 0)),
                 "ISP-B-77310": ([(1460, 372), (1232, 372)], (0.8, 0))}
    for cid, title, sub, speed, lands in S.CIRCUITS:
        circuit_ids[cid] = labelled(p, dv, card_x[cid], 104, 260, 64, title, sub, ("wan", "grey"), size=11,
                                    sub_size=9, data={"cid": cid, "object": "circuits.circuit", "status": "active",
                                                      "link": f"https://netbox.example.com/circuits/circuits/?cid={cid}",
                                                      "linkTarget": "_blank"})
        p.cell(cl, f"CID ‹{cid}›", text_style(size=8, color="#475569", extra="fontFamily=JetBrains Mono;"),
               card_x[cid] + 38, 170, 220, 14)

    # MDF
    group(700, 250, 580, 100, "HS1-FW · HA pair (A/P)", "FortiGate 200F")
    dev("HS1-FW-01", 720, 278)
    dev("HS1-FW-02", 1020, 278)
    group(680, 420, 620, 100, "HS1-CORE · VSX pair", "CX 8360 · ISL 2×100G")
    dev("HS1-CORE-1", 710, 448)
    dev("HS1-CORE-2", 1040, 448)
    group(100, 410, 300, 168, "HS1-GW · gateway cluster", "9240 ×2")
    dev("HS1-GW-01", 130, 440)
    dev("HS1-GW-02", 130, 506)
    dev("HS1-OOB-SW01", 130, 268)
    dev("HS1-SRV-01", 1380, 410)
    dev("HS1-NVR-01", 1380, 480)
    group(1350, 580, 300, 168, "HS1-ACC-MDF · VSF stack (2)", "front office wing")
    dev("HS1-ACC-MDF-1", 1380, 610)
    dev("HS1-ACC-MDF-2", 1380, 676)
    for i, n in enumerate(["HS1-AP-ADM1", "HS1-PA-01", "HS1-ACS-01", "HS1-CAM-MDF01"]):
        dev(n, 1720, 560 + i * 72, 210, 56)
    p.cell(nl, "<b>MDF-101</b> · racks R01 and R02 on separate circuits, each with its own UPS. "
           "Firewall, core and gateway pairs are split across the two racks, so one rack's power can fail.<br>"
           "<b>Fiber</b> · 12-strand OS2 to IDF-A, B and D; 12-strand OM4 to IDF-C (under 300 m). Four strands (two "
           "pairs) in use per closet, the rest spare.", NOTE, 1350, 860, 560, 112)

    # Closets
    stacks = {}
    for k, (key, room, rack, members, base, desc, media) in enumerate(S.IDFS):
        x0 = 110 + k * 370
        h = 46 + members * 64
        group(x0, 1040, 330, h, f"HS1-ACC-IDF{key} · VSF stack ({members})", f"{room} · {desc.split(' (')[0]}")
        for m in range(1, members + 1):
            dev(f"HS1-ACC-IDF{key}-{m}", x0 + 45, 1070 + (m - 1) * 64)
        stacks[key] = (x0, 1040 + h)
    x0 = 110 + 4 * 370
    group(x0, 1040, 330, 360, "Stadium · press box", "60 GHz link from the B wing roof", PINK, "#FFF7FB", "#F5C2DA")
    dev("HS1-PTP-A", x0 + 45, 1070)
    dev("HS1-PTP-B", x0 + 45, 1200)
    dev("HS1-ACC-STAD-1", x0 + 45, 1300)
    p.edge(links, ids["HS1-PTP-A"], ids["HS1-PTP-B"], edge_style(PINK, 2, dashed=True, pill=MEDIA_PILL["PtP RF"]),
           "PtP · 60 GHz · 1G · 180 m",
           attrs={"object": "wireless.wirelesslink", "ssid": "HS1-STADIUM", "status": "connected"}, exit=(0.5, 1),
           entry=(0.5, 0))
    ends = defaultdict(list)
    for name, sw, *_ in S.APS + S.CAMERAS:
        ends[sw].append(name)
    ends["HS1-ACC-IDFD-2"].append("HS1-BAS-01")
    for k, (key, *_r) in enumerate(S.IDFS):
        x0, bottom = stacks[key]
        names = [n for m in range(1, 4) for n in ends.get(f"HS1-ACC-IDF{key}-{m}", [])]
        for i, n in enumerate(names):
            dev(n, x0 + 65, bottom + 40 + i * 76, 220, 56)
    for i, n in enumerate(ends["HS1-ACC-STAD-1"]):
        dev(n, 110 + 4 * 370 + 65, 1430 + i * 76, 220, 56)

    # Cables
    cores = {"HS1-CORE-1": 0, "HS1-CORE-2": 0}
    lag_seen = set()
    for label, a, ap, b, bp, kind, speed, media, lag in S.CABLES:
        if a not in ids or b not in ids:
            continue
        data = {"object": "dcim.cable", "cable_label": label, "type": kind, "status": "connected",
                "a_terminations": f"{a}:{ap}", "b_terminations": f"{b}:{bp}", "x_speed": speed, "x_media": media,
                "link": f"https://netbox.example.com/dcim/cables/?label={label}", "linkTarget": "_blank"}
        trunk = S.TRUNKS.get(lag, "")
        name = lag if lag.startswith("lag") else lag
        if lag.startswith("lag"):
            value = f"{lag} · {speed} · {media}" if lag not in lag_seen else f"{speed}"
            lag_seen.add(lag)
        elif lag:
            value = f"{lag} · {speed}"
        else:
            value = ""
        uplink = b in cores and lag.startswith("lag4")
        color, width = (BLUE, 3) if uplink else ("#64748B", 2.2 if lag else 1.2)
        exit_ = entry = None
        pts = None
        if uplink:
            n = int(lag[-1])
            to2 = b.endswith("2")
            if n == 0:  # the MDF stack, from the right
                if not to2:
                    exit_, entry, pts = (0, 0.3), (0.9, 1), [(1336, 627), (1336, 552), (926, 552)]
                else:
                    exit_, entry, pts = (0, 0.7), (0.9, 1), [(1320, 715), (1320, 566), (1256, 566)]
            else:
                exit_, entry, pts = UPLINK_ROUTES[(n, to2)]
        elif a in ("HS1-FW-01", "HS1-FW-02") and b in cores:
            exit_, entry = (0.3 if b.endswith("1") else 0.7, 1), (0.3 if a.endswith("1") else 0.7, 0)
        elif b.startswith("HS1-ACC-MDF"):
            exit_, entry = (0, 0.5), (1, 0.5)
            pts = [(1690, 560 + ["HS1-AP-ADM1", "HS1-PA-01", "HS1-ACS-01", "HS1-CAM-MDF01"].index(a) * 72 + 28)]
        elif b.startswith("HS1-ACC-") and a not in ("HS1-PTP-B",):
            exit_, entry = (0, 0.5), (0, 0.5 if a != "HS1-PTP-A" else 0.7)
        p.edge(links, ids[a], ids[b],
               edge_style(color, width, pill=_media_pill(media) if value and lag.startswith("lag") else None), value,
               attrs=data, points=pts, exit=exit_, entry=entry)
    for cid, title, sub, speed, lands in S.CIRCUITS:
        pts, entry = wan_route[cid]
        p.edge(links, circuit_ids[cid], ids[lands], edge_style("#64748B", 1.6), f"{speed} · VRF WAN",
               attrs={"object": "circuits.circuittermination", "cid": cid}, points=pts, exit=(0.5, 1), entry=entry)

    # Registers
    p.cell(lr, "Link register — LAGs, members, speed, trunked VLANs", text_style(size=13, color="#0F172A", bold=True),
           1990, 86, 860, 22)
    rows = []
    groups = defaultdict(list)
    for c in S.CABLES:
        label, a, ap, b, bp, kind, speed, media, lag = c
        if lag:
            groups[(lag, a.rsplit("-", 1)[0] if lag.startswith("lag4") else a)].append(c)
    ends = set(EDUCATION.endpoint_roles)
    role = {d["name"]: d["role"] for d in S.DEVICES}
    for (lag, _), members in groups.items():
        if role.get(members[0][1]) in ends or role.get(members[0][3]) in ends:
            continue  # links between network gear only, as a build writes it; a server or NVR bundle stays a line
        a = members[0][1]
        b = members[0][3]
        aside = ", ".join(f"{m[1].replace('HS1-', '')} {m[2]}" for m in members)
        bside = ", ".join(f"{m[3].replace('HS1-', '')} {m[4]}" for m in members)
        rows.append([lag if lag.startswith("lag") else lag, aside, bside, f"{len(members)}×{members[0][6]}",
                     members[0][7], S.TRUNKS.get(lag, "—")])
    table(p, lr, 1990, 112, [("LINK", 56), ("A-SIDE (MEMBERS)", 200), ("B-SIDE (MEMBERS)", 200), ("SPEED", 60),
          ("MEDIA", 70), ("TRUNKED VLANS", 274)], rows, row_h=20, size=9)
    y = 112 + 22 + 20 * len(rows) + 30
    p.cell(ar, "Asset register — mirrors each device's shape data (sync with NetBox)",
           text_style(size=13, color="#0F172A", bold=True), 1990, y, 860, 22)
    infra = [d for d in S.DEVICES if d["role"] not in ("access-point", "camera")]
    # ROLE and CRIT read as a build writes them: the role's name and the NetBox rating. A build adds
    # STATUS after ROLE, paid for by HOSTNAME and ROLE, so the other columns keep their width.
    from netdiagrams.netbox_setup import ROLE_NAMES
    profiles.use("education")
    table(p, ar, 1990, y + 26, [("HOSTNAME", 120), ("ROLE", 124), ("CRIT", 50), ("MODEL", 126), ("SERIAL", 84),
          ("MGMT IP", 82), ("ROOM", 84), ("RACK/CAB", 58), ("U", 30), ("SW", 96)],
          [[d["name"], profiles.role_name(d["role"], ROLE_NAMES), S.CRITICALITY[d["role"]].capitalize(),
d["device_type"], d["serial"], d["primary_ip4"].split("/")[0], d["location"], d["rack"],
f"U{d['position']}" if d["position"] else "", d["cf"].get("sw_version", "")]
for d in infra], row_h=19, size=8.5, mono_cols=(4, 5))
    ly = 112 + 22 + 20 * len(rows) + 30 + 26 + 22 + 19 * len(infra) + 30
    # The registers sit on their own card: when a build adds rows, only this column moves down.
    p.cell(lr, "", card_style(fill="none", stroke="#EEF2F7", arc=20), 1976, 66, 892, ly - 66 - 14)
    legend(p, 1990, ly, 420, lines=True, zones=False)
    p.cell(nl, "<b>Layers on this sheet</b> (View ▸ Layers)<br>1 · Devices<br>2 · Links<br>"
           "3 · Mgmt IPs — <i>hide before sharing</i><br>3b · Serial numbers<br>"
           "4 · Circuit IDs — <i>hide before sharing</i><br>5 · Closet notes<br>6 · Link register<br>"
           "7 · Asset register<br><br>To send a copy without <i>netdiagrams share</i>, hide layers 3, 3b, 4 and 7 "
           "by hand.<br><br>APs and cameras are listed on the wireless sheet and in NetBox; this sheet draws one "
           "of each per closet.", NOTE, 2430, ly, 420, 240)
    return p


# ------------------------------------------------------------------ 3b hardware
def hardware() -> Page:
    p = Page("hardware", "3b · Closets, PoE & optics — power budgets · uplink optics · fiber", 2480, 1240, prefix="s")
    p.layer("Guides (hidden)", visible=False, locked=True)
    cl = p.layer("Closets")
    dv = p.layer("Switches")
    ol = p.layer("Optics & strands register")
    frame(p, f"{S.SITE_CODE} · {S.SITE_NAME} — Closets, PoE & Optics",
          "Every closet's switches, PoE budget against what is drawn, uplink optics and fiber strands. "
          "PoE runs the APs, phones, cameras and door hardware: a closet that runs out of power fails quietly.",
          f"Closets — {S.SITE_CODE}", "3b")
    closets = [("MDF-101", "Main closet · front office wing", ["HS1-ACC-MDF-1", "HS1-ACC-MDF-2"],
                [740, 740], [312, 268], "10G DAC to core", "2× UPS 3 kVA, 35 min")]
    poe = {"A": ([740] * 3, [455, 402, 377]), "B": ([740] * 3, [512, 430, 498]), "C": ([740] * 2, [365, 410]),
           "D": ([740] * 2, [298, 342])}
    for key, room, rack, members, base, desc, media in S.IDFS:
        optic = "SFP+ 10G-LR (OS2)" if media == "SMF OS2" else "SFP+ 10G-SR (OM4)"
        closets.append((room, desc, [f"HS1-ACC-IDF{key}-{m}" for m in range(1, members + 1)],
                        poe[key][0], poe[key][1], optic, "UPS 1.5 kVA, 20 min"))
    for i, (room, desc, names, budget, used, optic, ups) in enumerate(closets):
        x, y = 40 + (i % 3) * 800, 96 + (i // 3) * 290
        h = 270
        p.cell(cl, f"<b>{room}</b> <span style=\"font-weight:normal;color:#64748B\">· {desc}</span>",
               card_style(fill="#FFFFFF", extra="verticalAlign=top;align=left;spacingLeft=14;spacingTop=8;fontSize=13;"
                                     "fontColor=#0F172A;"), x, y, 770, h)
        for m, n in enumerate(names):
            device(p, dv, x + 16, y + 40 + m * 64, S.BY_NAME[n], 230, 56)
        rows = []
        for n, b, u in zip(names, budget, used):
            pct = round(100 * u / b)
            color = "#B45309" if pct >= 65 else "#15803D"
            rows.append([n, "48× 1G/2.5G PoE", f"{b} W", f'<font color="{color}"><b>{u} W · {pct}%</b></font>',
                         optic])
        # The stack's name heads its table, so a build restates the Power and Fans segments below it
        # from NetBox's inventory items; the UPS and the rule are the drawing's.
        stack = S.BY_NAME[names[0]]["virtual_chassis"]
        p.cell(cl, f"<b>{stack}</b> <span style=\"color:#64748B\">· VSF stack of "
               f"{len(names)}</span>", text_style(size=10, color="#0F172A"), x + 262, y + 34, 490, 18)
        table(p, cl, x + 262, y + 56, [("MEMBER", 128), ("PORTS", 100), ("POE BUDGET", 72), ("POE DRAWN", 96),
              ("UPLINK OPTIC", 102)], rows, row_h=26, size=9)
        power = next(f"{c}× {n}" if c > 1 else n for k, n, c in S.HARDWARE["CX 6300M 48P"] if k == "power")
        fans = next(f"{c}× {n}" if c > 1 else n for k, n, c in S.HARDWARE["CX 6300M 48P"] if k == "fan")
        p.cell(cl, f"<b>Power</b> {power} per member · <b>Fans</b> {fans} per member · <b>UPS</b> {ups}<br>"
               "<b>Rule</b> · keep each switch under 65% of its PoE budget, so a failed member's ports can move "
               "to its neighbor.", text_style(size=9.5, color="#475569"), x + 262, y + 56 + 22 + 26 * len(rows) + 8,
               490, 44)
    y = 96 + 2 * 290 + 10
    p.cell(ol, "Optics & strands register — what is in each port and which strands it uses",
           text_style(size=13, color="#0F172A", bold=True), 40, y, 900, 22)
    rows = []
    for label, a, ap, b, bp, kind, speed, media, lag in S.CABLES:
        if media in ("SMF OS2", "MMF OM4"):
            optic = "SFP+ 10G-LR" if media == "SMF OS2" else "SFP+ 10G-SR"
            closet = S.BY_NAME[a]["location"]
            rows.append([label, f"{a.replace('HS1-', '')} {ap}", optic, f"{b.replace('HS1-', '')} {bp}", optic, media,
                         f"MDF-FP{1 + len(rows) // 2}:{1 + 2 * (len(rows) % 2)}-{2 + 2 * (len(rows) % 2)}",
                         f"{closet}-FP1:{1 + 2 * (len(rows) % 2)}-{2 + 2 * (len(rows) % 2)}"])
    table(p, ol, 40, y + 28, [("CABLE ID", 100), ("A END", 170), ("A OPTIC", 100), ("B END", 150), ("B OPTIC", 100),
          ("MEDIA", 80), ("PATCH A (STRANDS)", 150), ("PATCH B (STRANDS)", 170)], rows, row_h=20, size=9,
          mono_cols=(6, 7))
    # Modules & power: what NetBox records inside each box, one row per stack or set of identical boxes.
    p.cell(ol, "Modules & power register — PSUs, fans and modules from NetBox",
           text_style(size=13, color="#0F172A", bold=True), 1100, y, 860, 22)
    header = [("DEVICE", 150), ("CHASSIS", 150), ("POWER", 230), ("MODULES", 90), ("OTHER", 240)]
    profiles.use("education")
    nb = sync.NetBoxIndex(S.export())
    mrows = [[re.sub(r"<[^>]+>", "", cell[0]) for cell in row]
             for row in sync._module_rows(None, None, [h for h, _ in header], nb)]
    table(p, ol, 1100, y + 28, header, mrows, row_h=20, size=9)
    p.cell(ol, "<b>Why this sheet exists</b><br>Every new AP, camera and door strike draws "
           "PoE. Before summer installs, check the closet here first: the budget is the switch's, the drawn power "
           "is the rated draw of what is plugged in, kept by hand. Amber means the closet can't lose a member.", NOTE,
           1990, y + 28, 450, 130)
    return p


# ------------------------------------------------------------------ 3d wireless
def wireless() -> Page:
    p = Page("wireless", "3d · Wireless — SSIDs · APs · stadium link", 2600, 1340, prefix="s")
    guides = p.layer("Guides (hidden)", visible=False, locked=True)
    zl = p.layer("Zones & groups")
    links = p.layer("Links")
    dv = p.layer("Gateways · switches · APs")
    plan = p.layer("Site plan (replace with floor plan image)")
    cov = p.layer("Coverage cells (−67 dBm design)")
    place = p.layer("AP positions")
    ptp = p.layer("PtP paths")
    reg = p.layer("Registers (SSID · AP · PtP)")
    frame(p, f"{S.SITE_CODE} · {S.SITE_NAME} — Wireless",
          "SSIDs and the zone each one lands in · APs by wing · the gateway cluster · the stadium link. "
          "Every SSID maps to one VLAN in one zone; no SSID spans two zones.", f"Wireless — {S.SITE_CODE}", "3d")
    ids = {}
    ids["core"] = labelled(p, dv, 640, 110, 300, 64, "Core · VSX pair (sheet 3)",
                           "AP-MGMT 910 · client VLANs on the core", ("core", "blue"), size=11, sub_size=9)
    p.cell(zl, "<b>HS1-GW · gateway cluster</b> <span style=\"font-weight:normal;color:#64748B\">"
           "client traffic tunneled from every AP; the gateways put each SSID on its VLAN</span>",
           "rounded=1;absoluteArcSize=1;arcSize=18;fillColor=#F2FAF9;strokeColor=#99E2D8;strokeWidth=1;dashed=1;"
               "dashPattern=4 3;verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontSize=10;"
               "fontColor=#0F766E;html=1;whiteSpace=wrap;fontFamily=Inter;", 80, 200, 1300, 150)
    ids["gw1"] = device(p, dv, 400, 250, S.BY_NAME["HS1-GW-01"])
    ids["gw2"] = device(p, dv, 940, 250, S.BY_NAME["HS1-GW-02"])
    for g in ("gw1", "gw2"):
        p.edge(links, ids[g], ids["core"], edge_style("#64748B", 2.2), "2×10G", exit=(0.5, 0),
               entry=(0.3 if g == "gw1" else 0.7, 1))
    wings = [("Front office", ["HS1-AP-ADM1"], "6 APs · office, nurse, counseling"),
             ("A wing", ["HS1-AP-A101", "HS1-AP-A120"], "32 APs · one per classroom"),
             ("B wing & library", ["HS1-AP-B201", "HS1-AP-B230"], "36 APs · two in the library"),
             ("Gym & auditorium", ["HS1-AP-C-GYM1", "HS1-AP-C-AUD1"], "12 APs · high density for assemblies"),
             ("CTE & science", ["HS1-AP-D301", "HS1-AP-BUS1"], "18 APs · shops need ceiling mounts · outdoor AP on the bus loop"),
             ("Stadium", ["HS1-AP-STAD1"], "4 outdoor APs · over the PtP link")]
    for i, (title, aps, sub) in enumerate(wings):
        x, y = 80 + (i % 3) * 440, 390 + (i // 3) * 250
        p.cell(zl, f"<b>{title}</b><br><span style=\"font-weight:normal;color:#64748B\">{sub}</span>",
               "rounded=1;absoluteArcSize=1;arcSize=18;fillColor=#FFFFFF;strokeColor=#E2E8F0;strokeWidth=1;"
               "verticalAlign=top;align=left;spacingLeft=12;spacingTop=6;fontSize=11;fontColor=#0F766E;html=1;"
               "whiteSpace=wrap;fontFamily=Inter;", x, y, 420, 230)
        for j, ap in enumerate(aps):
            ids[ap] = device(p, dv, x + 20 + j * 200, y + 70, S.BY_NAME[ap], 190, 56)
        p.cell(zl, "Counted group: the build reads every AP NetBox has in this wing and "
               "writes “AP ×n” on the drawn one.", text_style(size=9, color="#94A3B8"), x + 20, y + 150, 380, 60)
    # Stadium link
    p.cell(zl, "<b>Stadium link</b> · B wing roof to the press box", text_style(size=11, color="#DB2777"), 540, 900,
           700, 22)
    ids["ptpa"] = device(p, dv, 540, 930, S.BY_NAME["HS1-PTP-A"])
    ids["ptpb"] = device(p, dv, 1140, 930, S.BY_NAME["HS1-PTP-B"])
    p.edge(ptp, ids["ptpa"], ids["ptpb"], edge_style(PINK, 2.5, dashed=True, pill=MEDIA_PILL["PtP RF"]),
           "60 GHz · 180 m · 1 Gb/s · clear line of sight",
           attrs={"object": "wireless.wirelesslink", "ssid": "HS1-STADIUM",
                                            "status": "connected"})
    # Registers
    p.cell(reg, "SSID register — one SSID, one VLAN, one zone", text_style(size=13, color="#0F172A", bold=True), 1440,
           100, 1100, 22)
    vl = {v[0]: v for v in S.VLANS}
    # The rows a build writes from the sample's NetBox data, so the template and a build read alike.
    wx = nb_wireless.Index(S.export())
    table(p, reg, 1440, 128, [("SSID", 110), ("SECURITY", 270), ("VLAN · SUBNET", 150), ("ZONE", 70),
          ("CONTROLLER", 80), ("BANDS", 90), ("GUEST CONTROLS", 140), ("NOTES", 200)],
          [[w.ssid, w.security, f"{w.vlan['vid']} · {vl[w.vlan['vid']][2]}", w.zone[len("zone-"):].upper(),
w.controller, w.bands, w.guest_controls, w.notes] for w in wx.ssids()], row_h=24, size=9)
    p.cell(reg, "AP register — the drawn APs; NetBox holds them all", text_style(size=13, color="#0F172A", bold=True),
           1440, 306, 1100, 22)
    table(p, reg, 1440, 334, [("NAME", 150), ("MODEL", 80), ("SERIAL", 110), ("MGMT IP", 100), ("LOCATION", 150),
          ("SWITCH PORT", 160), ("POWER", 90)],
          [[n, S.BY_NAME[n]["device_type"], S.BY_NAME[n]["serial"], S.BY_NAME[n]["primary_ip4"].split("/")[0], loc,
f"{sw.replace('HS1-', '')}", "PoE 802.3bt" if m == "AP-655" else "PoE 802.3at"] for n, sw, loc, m in S.APS + S.NETBOX_ONLY_APS],
          row_h=20, size=9, mono_cols=(2, 3))
    p.cell(reg, "PtP register", text_style(size=13, color="#0F172A", bold=True), 1440, 612, 1100, 22)
    table(p, reg, 1440, 640, [("LINK", 110), ("RADIO A", 175), ("RADIO B", 175), ("BAND", 300), ("PATH", 60),
          ("SECURITY", 150), ("VLANS", 130)],
          [["HS1-STADIUM", "PTP-A radio0 · ROOF-B", "PTP-B radio0 · STADIUM-PB", wx.radio_text("HS1-PTP-A", "radio0"), "180 m",
"WPA Personal (PSK) · AES", S.STADIUM_VLANS]], row_h=22, size=9)
    # Site plan sketch
    px, py = 1440, 730
    p.cell(plan, "", card_style(fill="#FBFCFE", stroke="#CBD5E1", arc=12, extra="dashed=1;dashPattern=6 4;"), px, py,
           1100, 400)
    p.cell(plan, "Site plan — replace with the floor plan image (View ▸ Layers)",
           text_style(size=10, color="#94A3B8", bold=True), px + 12, py + 8, 600, 20)
    blocks = [("A wing", 30, 60, 300, 90), ("B wing", 30, 170, 300, 90), ("Office", 350, 60, 110, 90),
              ("Gym", 350, 170, 170, 110), ("Aud.", 540, 170, 110, 110), ("CTE", 480, 60, 170, 90)]
    for title, bx, by, bw, bh in blocks:
        p.cell(plan, f"<b>{title}</b>",
               card_style(fill="#F1F5F9", stroke="#CBD5E1", arc=6, extra="fontSize=10;fontColor=#64748B;verticalAlign=top;"),
               px + bx, py + by, bw, bh)
    import random
    rng = random.Random(7)
    for title, bx, by, bw, bh in blocks:
        n = max(2, int(bw * bh / 9000))
        for k in range(n):
            cx = px + bx + 20 + (k * (bw - 40) / max(1, n - 1) if n > 1 else bw / 2)
            cy = py + by + bh / 2 + rng.choice((-14, 14))
            p.cell(cov, "", "ellipse;fillColor=#14B8A6;opacity=12;strokeColor=#14B8A6;"
                   "strokeOpacity=35;html=1;", cx - 34, cy - 34, 68, 68)
            p.cell(place, "", "ellipse;fillColor=#0D9488;strokeColor=#FFFFFF;strokeWidth=1.5;"
                   "html=1;", cx - 5, cy - 5, 10, 10)
    p.cell(plan, "<b>Stadium</b>",
           card_style(fill="#F1F5F9", stroke="#CBD5E1", arc=60, extra="fontSize=10;fontColor=#64748B;"), px + 860,
           py + 90, 200, 200)
    p.edge(ptp, None, None, line_style(PINK, 2, dashed=True), "", src_pt=(px + 330, py + 215),
           tgt_pt=(px + 900, py + 160))
    p.cell(plan, "AP placement · coverage cells sized for −67 dBm at the desk. Gym "
           "and auditorium use two directional APs each for assemblies (900 seats).",
           text_style(size=9, color="#64748B"), px + 700, py + 300, 380, 80)
    p.cell(guides, "<b>Design rules</b> · one AP per classroom; 5 and 6 GHz for staff and "
           "students, 2.4 GHz only on GUEST, DEVICES and BLDG; no SSID broadcasts in more than one zone.", NOTE, 540,
           1010, 840, 100)
    legend(p, 80, 900, 420, lines=False, zones=True)
    return p


# ------------------------------------------------------------------ 4 flows
ZONE_LANES = [("STUDENT", "student"), ("GUEST", "guest"), ("STAFF", "staff"), ("ADMIN", "admin"),
              ("SVC", "svc"), ("BLDG", "bldg"), ("MGMT", "mgmt"), ("DISTRICT DC", "out"), ("INTERNET · CLOUD", "out")]
FLOWS = [  # id, from, to, what, kind (permit/cond/deny), ports
    ("F01", "STUDENT", "INTERNET · CLOUD", "Web, via the district web filter", "permit", "TCP 443, 80"),
    ("F02", "STUDENT", "INTERNET · CLOUD", "Learning platform, email, testing", "permit", "TCP 443"),
    ("F03", "STUDENT", "STAFF", "Anything else (F05 sits above this deny)", "deny", "any"),
    ("F04", "STUDENT", "ADMIN", "Anything (records stay in the office)", "deny", "any"),
    ("F05", "STUDENT", "STAFF", "Cast to the classroom display (same room only)", "cond",
     "mDNS gateway · TCP 8008-8009 · UDP 32768-61000"),
    ("F06", "GUEST", "INTERNET · CLOUD", "Web, filtered, 10 Mb/s per device", "permit", "TCP 443, 80 · UDP 443"),
    ("F07", "GUEST", "STAFF", "Any school zone", "deny", "any"),
    ("F08", "STAFF", "INTERNET · CLOUD", "SIS, email, learning platform", "permit", "TCP 443"),
    ("F09", "STAFF", "DISTRICT DC", "Directory logon and file shares", "permit",
     "TCP/UDP 88, 389 · TCP 135 + RPC, 445, 636, 3268"),
    ("F10", "ADMIN", "DISTRICT DC", "Student records sync, health records", "permit", "TCP 443"),
    ("F11", "STAFF", "SVC", "Camera viewing (admins and SRO group)", "cond", "TCP 443, 554"),
    ("F12", "STAFF", "BLDG", "Straight to a camera or controller", "deny", "any"),
    ("F13", "SVC", "BLDG", "NVR pulls camera video", "permit", "TCP 554 · RTSP"),
    ("F14", "SVC", "BLDG", "Door server ⇄ door controllers", "permit", "TCP 3001 (vendor)"),
    ("F15", "BLDG", "INTERNET · CLOUD", "Cameras and controllers phoning home", "deny", "any"),
    ("F16", "INTERNET · CLOUD", "SVC", "HVAC vendor via district remote access, approved window", "cond",
     "TCP 443 (broker)"),
    ("F17", "DISTRICT DC", "MGMT", "District NOC manages switches, APs and firewalls", "permit",
     "TCP 22, 443 · UDP 161 (SNMPv3)"),
    ("F18", "STUDENT", "INTERNET · CLOUD", "Testing rooms: state testing platform only (allow-list)", "cond",
     "TCP 443 · named hosts"),
    ("F19", "MGMT", "DISTRICT DC", "Wireless gateways ask the district RADIUS servers (802.1X)", "permit",
     "UDP 1812, 1813"),
    ("F20", "MGMT", "INTERNET · CLOUD", "APs and gateways reach their cloud management", "permit",
     "TCP 443 · vendor hosts"),
    # The plumbing every zone needs; under default deny, leaving these out takes the school offline.
    ("F21", "STAFF", "DISTRICT DC", "Phone system: SIP-TLS and voice", "permit", "TCP 5061 · UDP 16384-32767 (RTP)"),
    ("F22", "ALL ZONES", "DISTRICT DC", "DHCP (relayed by the core), DNS and time", "permit",
     "UDP 67 · TCP/UDP 53 · UDP 123"),
    ("F23", "MGMT", "DISTRICT DC", "Logs and alerts to the district SIEM and NOC", "permit",
     "TCP 6514 (syslog over TLS) · UDP 162 (SNMPv3 traps)"),
    ("F24", "MGMT", "DISTRICT DC", "Config backups to the district", "permit", "TCP 22 (SFTP)"),
]
SCHOOL_ZONES = ["STUDENT", "GUEST", "STAFF", "ADMIN", "SVC", "BLDG", "MGMT"]   # what "ALL ZONES" stands for


def flows() -> Page:
    p = Page("flows", "4 · Traffic Flows — Zone paths · Internet · Vendors", 2500, 1760, prefix="s")
    p.layer("Guides (hidden)", visible=False, locked=True)
    hl = p.layer("Lane headers")
    lanes = {"permit": p.layer("Lanes – Permitted"), "cond": p.layer("Lanes – Conditional"),
             "deny": p.layer("Denied paths")}
    frame(p, f"{S.SITE_CODE} · {S.SITE_NAME} — Traffic Flows",
          "Who starts each conversation, who answers, and where the firewall decides. Green is permitted, "
          "orange needs a named group, an approval or a window, red is denied. IDs match the flow register.",
          f"Flows — {S.SITE_CODE}", "4")
    x0, step, top = 300, 238, 110
    ROW = 54  # row pitch: twenty-four flows fit above the legend
    lane_x = {}
    for i, (title, key) in enumerate(ZONE_LANES):
        fill, stroke, color = ZONE_COLORS[key]
        x = x0 + i * step
        lane_x[title] = x + 90
        p.cell(hl, f"<b>{title}</b>",
               pill_style(fill if key != "out" else "#F1F5F9", color, size=11, stroke=stroke, arc=14), x, top, 180,
               40)
        p.edge(hl, None, None, line_style("#CBD5E1", 1.2, dashed=True), "", src_pt=(x + 90, top + 40),
               tgt_pt=(x + 90, top + 60 + len(FLOWS) * ROW))
    marker = "ellipse;fillColor=#DC2626;strokeColor=#FFFFFF;strokeWidth=2;fontColor=#FFFFFF;fontSize=10;fontStyle=1;html=1;"
    for n, (fid, a, b, what, kind, ports) in enumerate(FLOWS):
        y = top + 80 + n * ROW
        color = {"permit": GREEN, "cond": ORANGE, "deny": RED}[kind]
        p.cell(lanes[kind], f"<b>{fid}</b> · {what}<br><span style=\"color:#94A3B8\">{ports}"
               "</span>", text_style(size=9.5, color="#334155", valign="middle"), 40, y - 18, 250, 36)
        starts = SCHOOL_ZONES if a == "ALL ZONES" else [a]   # one dot on every lane that starts it
        xa, xb = lane_x[starts[0]], lane_x[b]
        for z in starts:
            p.cell(lanes[kind], "", f"ellipse;fillColor={color};strokeColor=#FFFFFF;html=1;", lane_x[z] - 6, y - 6,
                   12, 12)
        if kind == "deny":
            mid = (xa + xb) / 2
            p.edge(lanes[kind], None, None, line_style(color, 2, dashed=True), "", src_pt=(xa, y), tgt_pt=(xb, y))
            p.cell(lanes[kind], "✕", marker + "fontFamily=Inter;", mid - 10, y - 10, 20, 20)
        else:
            p.edge(lanes[kind], None, None, line_style(color, 2, dashed=kind == "cond", arrow=True), "",
                   src_pt=(xa, y), tgt_pt=(xb, y))
        p.cell(lanes[kind], fid, pill_style("#FFFFFF", color, size=8.5, stroke=color), (xa + xb) / 2 - 22, y - 26, 44,
               16)
    legend(p, 40, top + 80 + len(FLOWS) * ROW + 10, 560, lines=True, zones=False, icons=False)
    p.cell(lanes["permit"],
           "<b>Read a lane like this</b> · the dot is the side that starts the conversation, the arrow the side "
           "that answers. A reply needs no lane of its own. Anything not drawn here is denied by the firewall's "
           "last rule, and every flow drawn is a row in the flow register (sheet 7).", NOTE, 640,
           top + 90 + len(FLOWS) * ROW, 900, 90)
    return p


# ------------------------------------------------------------------ 5 failover
SCENARIOS = [
    ("S1 · HS1-FW-01 fails", "none", "HA moves to HS1-FW-02 in about a second; sessions are synced.",
     "Nobody. One alert to the district NOC.", "Replace or reboot FW-01; it rejoins as passive.", "firewall"),
    ("S2 · HS1-CORE-1 fails", "low", "VSX keeps CORE-2 forwarding; every LAG loses one member. The ring leg "
     "to the district office lands on CORE-1, so traffic goes the other way round the ring, through Cedar MS.",
     "Nothing in the classrooms. The district NOC sees one ring leg down.",
     "Replace CORE-1; VSX resyncs; check every LAG shows both members and both ring legs are up.", "core"),
    ("S3 · District fiber lost (both ring legs)", "high", "WAN-B broadband takes over over IPsec to the "
     "district office at 1 Gb/s. "
     "QoS keeps testing, phones and SIS ahead of video.", "Video and updates slow. Phones and testing work. "
     "Cameras keep recording locally.", "Call the fiber contractor; the district owns the strands (HPSD-DF-020, HPSD-DF-021).",
     "wan"),
    ("S4 · An IDF-B stack member fails", "medium", "VSF keeps the other two members up; the uplink LAG keeps one "
     "member. APs and phones on the failed member go dark.", "Library and rooms B210-B219 lose wired phones; "
     "neighboring APs cover most of the Wi-Fi.", "Swap the member from the spares shelf; VSF renumbers it.",
     "switch"),
    ("S5 · Power out in IDF-C", "medium", "UPS carries the gym closet for about 20 minutes, then the gym, "
     "auditorium and cafeteria APs and cameras go dark.", "Assembly Wi-Fi and cafeteria cameras. The PA still "
     "works (its server is in the MDF).", "Restore power; check the UPS self-test; log the run time.", "alert"),
    ("S6 · Stadium radio fails", "low", "The 60 GHz link drops (heavy rain or misalignment). The press box "
     "switch, outdoor AP and gate camera are cut off.", "Scoreboard and gate camera at night games.",
     "Re-aim or replace; the spare radio is in MDF-101. Camera keeps 48 h on its SD card.", "ptp"),
]


def failover() -> Page:
    p = Page("failover", "5 · Failover scenarios", 2400, 1000, prefix="s")
    p.layer("Guides (hidden)", visible=False, locked=True)
    sl = p.layer("Scenarios")
    frame(p, f"{S.SITE_CODE} · {S.SITE_NAME} — Failover Scenarios",
          "What happens when one thing breaks, what people notice, and how to put it back. "
          "Practice S1 to S3 in the summer, not during state testing.", f"Failover — {S.SITE_CODE}", "5")
    impact = {"none": ("#DCFCE7", "#15803D"), "low": ("#E0F2FE", "#0369A1"), "medium": ("#FEF3C7", "#B45309"),
              "high": ("#FEE2E2", "#B91C1C")}
    for i, (title, level, what, notice, fix, kind) in enumerate(SCENARIOS):
        x, y = 40 + (i % 3) * 780, 96 + (i // 3) * 410
        fam = {"firewall": "slate", "core": "blue", "wan": "grey", "switch": "blue", "alert": "amber",
               "ptp": "pink"}[kind]
        p.cell(sl, "", card_style(shadow=True), x, y, 750, 390)
        labelled(p, sl, x + 20, y + 18, 560, 56, f'<span style="font-size:15px">{title}</span>', "", (kind, fam),
                 size=13)
        fill, color = impact[level]
        p.cell(sl, f"<b>Impact: {level}</b>", pill_style(fill, color, size=10, arc=14), x + 600, y + 30, 130, 28)
        for j, (head, body) in enumerate((("What happens", what), ("What people notice", notice),
                                          ("Put it back", fix))):
            p.cell(sl, head.upper(), text_style(size=10, color="#94A3B8", bold=True), x + 24, y + 92 + j * 96, 700,
                   22)
            p.cell(sl, body, text_style(size=13, color="#0F172A"), x + 24, y + 114 + j * 96, 700, 66)
    return p


# ------------------------------------------------------------------ 6 multisite
SITES = [  # code, name, grades, students, wan, backup, prefix
    ("DO", "District office & data center", "—", "—", "fiber ring hub · 2× ISP", "dual ISP", "10.10.0.0/16"),
    ("HS1", "Harbor Pines High School", "9-12", "1,850", "fiber ring 10G", "broadband + IPsec", "10.20.0.0/16"),
    ("MS1", "Cedar Middle School", "6-8", "1,020", "fiber ring 10G", "broadband + IPsec", "10.30.0.0/16"),
    ("ES1", "Willow Elementary", "K-5", "540", "metro Ethernet 1G", "LTE + IPsec", "10.40.0.0/16"),
    ("ES2", "Lakeside Elementary", "K-5", "610", "metro Ethernet 1G", "LTE + IPsec", "10.50.0.0/16"),
    ("TY1", "Transportation yard", "—", "—", "broadband 500M + IPsec", "LTE", "10.60.0.0/16"),
]


def multisite() -> Page:
    p = Page("multisite", "6 · District WAN — schools, district office, standards", 2400, 1060, prefix="s")
    p.layer("Guides (hidden)", visible=False, locked=True)
    wl = p.layer("WAN overview")
    rl = p.layer("Site register & rules")
    frame(p, f"{S.DISTRICT} — District WAN",
          "Every school reaches the internet, the cloud apps and the data center through the district office. "
          "Same VLAN IDs and zones at every school; each school gets its own /16.", "District WAN", "6")
    hub = labelled(p, wl, 660, 420, 360, 110, "DO · District office", "Data center · firewall pair · web filter<br>"
                   "ISP-A 2G · ISP-B 1G · district NOC", ("building", "grey"), size=14, sub_size=10)
    inet = labelled(p, wl, 690, 130, 300, 80, "Internet", "content filtered for every school", ("cloud", "grey"),
                    size=13, sub_size=10, arc=60, spacing=48)
    p.edge(wl, hub, inet, edge_style(SLATE, 2.5), "ISP-A · ISP-B", exit=(0.5, 0), entry=(0.5, 1))
    pos = {"HS1": (120, 300), "MS1": (120, 640), "ES1": (1220, 300), "ES2": (1220, 640), "TY1": (660, 700)}
    cards = {}
    for code, name, grades, students, wan, backup, prefix in SITES[1:]:
        x, y = pos[code]
        fam = "blue" if code.startswith(("HS", "MS")) else ("green" if code.startswith("ES") else "grey")
        kind = "bus" if code == "TY1" else "building"
        card = cards[code] = labelled(p, wl, x, y, 360, 100, f"{code} · {name}", f"Grades {grades} · {students} students<br>"
                        f"{prefix}" if students != "—" else f"Buses, fuel and dispatch<br>{prefix}", (kind, fam),
                        size=13, sub_size=10)
        dashed = "broadband" in wan
        color = BLUE if "fiber" in wan else ("#0369A1" if "metro" in wan else "#64748B")
        p.edge(wl, card, hub, edge_style(color, 3.5 if "fiber" in wan else 2, dashed=dashed), wan,
               exit=(1, 0.5) if x < 600 else ((0, 0.5) if x > 1000 else (0.5, 0)),
               entry=(0, 0.3 if y < 500 else 0.7) if x < 600 else ((1, 0.3 if y < 500 else 0.7) if x > 1000
                                                                  else (0.5, 1)))
    # The third leg closes the ring: drawn as three spokes it would read as three single points of failure.
    p.edge(wl, cards["HS1"], cards["MS1"], edge_style(BLUE, 3.5), "fiber ring 10G", exit=(0.5, 1),
           entry=(0.5, 0))
    p.cell(wl, "<b>Fiber ring</b> · DO, HS1 and MS1 share a district-owned 12-strand ring, so "
           "one cut leaves every site connected the other way round; broadband takes over only when both paths "
           "are lost (sheet 5, S3). Elementary schools have leased 1 Gb/s metro "
           "Ethernet with LTE backup.", NOTE, 120, 860, 900, 96)
    p.cell(rl, "Site register", text_style(size=13, color="#0F172A", bold=True), 1640, 100, 700, 22)
    table(p, rl, 1640, 128, [("SITE", 40), ("NAME", 156), ("GRADES", 50), ("STUDENTS", 62), ("WAN", 140),
          ("BACKUP", 112), ("PREFIX", 92)], [[c, n, g, s, w, b, pre] for c, n, g, s, w, b, pre in SITES], row_h=22,
          size=9.5, mono_cols=(6,))
    p.cell(rl, "District standards", text_style(size=13, color="#0F172A", bold=True), 1640, 330, 700, 22)
    table(p, rl, 1640, 358, [("ITEM", 150), ("STANDARD", 442)], [
          ["Site code", "DO, HS1, MS1, ES1, ES2, TY1 · first part of every device name"],
          ["Device names", "‹site›-‹role›-‹closet›-‹n› · HS1-ACC-IDFB-2"],
          ["Address plan", "10.(site×10).0.0/16 · guest 172.(18+site).0.0/16 · HS1 172.20"],
          ["VLAN IDs", "Same at every school: 1xx staff/office · 2xx student · 3xx guest · 4xx building · "
                       "5xx services · 9xx management · x99 transit"],
          ["SSIDs", "HPSD-STAFF · HPSD-STUDENT · HPSD-BYOD · HPSD-GUEST · HPSD-DEVICES · HPSD-BLDG, same everywhere"],
          ["Internet", "Only at the district office, through the web filter. No breakout at schools"],
          ["Cable labels", "‹site›-CBL-nnn on both ends; patch panels ‹closet›-FPn:port"],
          ["Rooms", "Closet = IDF-‹wing›‹room› · AP named for its room (HS1-AP-B201)"],
      ], row_h=34, size=9.5)
    return p


# ------------------------------------------------------------------ 7 register
def register() -> Page:
    p = Page("register", "7 · Flow register & standards", 2400, 1300, prefix="s")
    p.layer("Guides (hidden)", visible=False, locked=True)
    fl = p.layer("Flow register")
    zm = p.layer("Zone matrix")
    st = p.layer("Standards")
    dc = p.layer("Drawing conventions")
    frame(p, f"{S.SITE_CODE} · {S.SITE_NAME} — Flow Register & Zone Matrix",
          "The segmentation in writing: every permitted conversation, who owns it and when it was last reviewed. "
          "Default deny: anything not in this register is blocked.", f"Flow register — {S.SITE_CODE}", "7")
    p.cell(fl, "", card_style(shadow=True), 24, 90, 1500, 740)
    p.cell(fl, "Flow register — conduits between zones", text_style(size=14, color="#0F172A", bold=True), 40, 100,
           900, 24)
    owners = {"STUDENT": "Curriculum tech", "GUEST": "Network", "STAFF": "Network", "ADMIN": "Student services",
              "SVC": "Facilities + network", "BLDG": "Facilities", "DISTRICT DC": "District IT", "MGMT": "District NOC",
              "INTERNET · CLOUD": "Facilities (vendor)",
              "ALL ZONES": "District IT"}
    rows = []
    for fid, a, b, what, kind, ports in FLOWS:
        decision = {"permit": "permit", "cond": "conditional", "deny": "deny (logged)"}[kind]
        rows.append([fid, a, b, what, ports, decision, "HS1-FW" if "DISTRICT" not in a else "HS1-FW",
                     owners.get(a, "Network"), "2026-08"])
    table(p, fl, 40, 132, [("ID", 46), ("FROM", 110), ("TO", 120), ("SERVICE", 300), ("PORTS", 280),
          ("DECISION", 100), ("ENFORCED", 80), ("OWNER", 150), ("REVIEWED", 70)], rows, row_h=24, size=9.5,
          values_style={5: "fontStyle=1;"})
    p.cell(fl, "Last rule on HS1-FW: deny any any, logged. Reviewed each August before school starts, and after any "
           "change to a building system vendor.", text_style(size=10, color="#64748B"), 40,
           132 + 22 + 24 * len(rows) + 14, 1400, 40)
    # Zone matrix
    p.cell(zm, "", card_style(shadow=True), 1550, 90, 820, 740)
    p.cell(zm, "Zone matrix — from (row) to (column)", text_style(size=14, color="#0F172A", bold=True), 1566, 100,
           600, 24)
    names = ["STUDENT", "GUEST", "STAFF", "ADMIN", "SVC", "BLDG", "MGMT", "DISTRICT DC", "INTERNET · CLOUD"]
    short = ["STU", "GST", "STF", "ADM", "SVC", "BLD", "MGT", "DC", "NET"]
    grid = []
    for a in names:
        row = [short[names.index(a)]]
        for b in names:
            if a == b:
                row.append("·")
                continue
            mine = [(f, k) for f, x, y, w, k, pts in FLOWS
                    if (x == a or x == "ALL ZONES" and a in SCHOOL_ZONES) and y == b]
            ids, kinds = [f for f, _ in mine], [k for _, k in mine]
            if not ids:
                row.append('<font color="#CBD5E1">✕</font>')
            elif all(k == "deny" for k in kinds):
                row.append('<font color="#DC2626"><b>✕</b></font>')
            else:
                color = GREEN if "permit" in kinds else ORANGE
                row.append(f'<font color="{color}"><b>{" ".join(i for i, k in zip(ids, kinds) if k != "deny")}</b></font>')
        grid.append(row)
    table(p, zm, 1566, 132, [("", 54)] + [(s, 82) for s in short], grid, row_h=40, size=9)
    p.cell(zm, "Green: permitted flow IDs. Orange: conditional. Red ✕: "
           "denied and drawn on sheet 4. Grey ✕: denied by default, no flow requested.",
           text_style(size=10, color="#64748B"), 1566, 132 + 22 + 40 * 9 + 10, 790, 60)
    # Standards
    p.cell(st, "", card_style(shadow=True), 24, 850, 1100, 330)
    p.cell(st, "Standards", text_style(size=14, color="#0F172A", bold=True), 40, 860, 600, 24)
    table(p, st, 40, 892, [("ITEM", 170), ("STANDARD", 898)], [
          ["Default", "Deny between zones; every exception is a flow with an owner and sits above the denies"],
          ["Student traffic", "Filtered at the district office; SSL inspection on district Chromebooks"],
          ["Building systems", "No internet; reached only from their SVC server"],
          ["Vendors", "District remote access broker, named account, approved window, recorded"],
          ["Testing", "TESTING VLAN allow-list from the state's published host list each spring"],
          ["Management", "From the district NOC subnet only; OOB for firewall and core"],
          ["Review", "Every August, and when a vendor or building system changes"],
      ], row_h=36, size=10)
    p.cell(dc, "", card_style(shadow=True), 1150, 850, 1220, 330)
    p.cell(dc, "Drawing conventions", text_style(size=14, color="#0F172A", bold=True), 1166, 860, 600, 24)
    for i, (t, body) in enumerate([
            ("Colors mean one thing", "Slate is a firewall or an enforcement point. Red is only a denied path or a "
             "fault. Amber is missing or offline. Dashed is planned or conditional."),
            ("One zone, one color", "Staff blue, office teal, students green, guests sky, services orange, "
             "building violet, management grey, on every sheet."),
            ("Names come from NetBox", "Device, VLAN and cable names on the drawing are NetBox's. Fix a name in "
             "NetBox, not on the sheet."),
            ("Hide before sharing", "Mgmt IPs, circuit IDs and VLAN tables sit on layers marked “hide before "
             "sharing”. Use netdiagrams share for outside readers."),
    ]):
        labelled(p, dc, 1166 + (i % 2) * 596, 896 + (i // 2) * 136, 580, 122, t, body, None, size=13, sub_size=12,
                 valign="top", spacing=16)
    return p


# ------------------------------------------------------------------ 8 netbox
def netbox() -> Page:
    p = Page("netbox", "8 · NetBox — data model · import · sync", 2400, 960, prefix="s")
    p.layer("Guides (hidden)", visible=False, locked=True)
    ml = p.layer("NetBox mapping")
    il = p.layer("Import & sync")
    frame(p, "NetBox for schools — data model, import order and sync",
          "Where every fact on these sheets lives in NetBox. Zones are tags on devices; buildings, floors, closets "
          "and rooms are nested locations; nothing here needs a NetBox plugin.", "NetBox — district", "8")
    p.cell(ml, "What fills each part of the drawing", text_style(size=14, color="#0F172A", bold=True), 40, 96, 900,
           24)
    table(p, ml, 40, 126, [("DRAWING ELEMENT", 200), ("NETBOX OBJECT", 190), ("FIELDS", 420), ("SCHOOL NOTE", 340)],
          [
          ["Site code and name", "Site", "name, facility (HS1), description", "One site per school building"],
          ["Closet · room", "Location", "Main building → Floor 2 → IDF-B214", "Feeds are cables, not nesting"],
          ["Device card", "Device", "name, role, device_type, serial, asset_tag, primary_ip4, rack, position",
           "Asset tag = district inventory tag"],
          ["Zone", "Tag zone-* (or custom field)", "zone-staff, zone-student, zone-bldg …", "Tag each device; a tag on "
           "its location is the fallback"],
          ["VLAN table", "VLAN + Prefix", "vid, name, tags; prefix, vrf, vlan", "Same VLAN IDs in a district VLAN group"],
          ["Link and LAG", "Cable + Interface", "label, type, terminations; lag, tagged_vlans", "Label both ends: "
           "HS1-CBL-031"],
          ["Circuit", "Circuit + termination", "cid, provider, commit_rate", "E-Rate funded? note it in comments"],
          ["SSID table", "Wireless LAN", "ssid, vlan, auth_type, auth_cipher", "One SSID, one VLAN"],
          ["Stadium link", "Wireless link", "interface_a, interface_b, ssid", "PtP radios as devices"],
          ["Building systems", "Device (role)", "camera, access-control, bas-controller, pa-system, nvr", "Record the "
           "controllers; cameras optional"],
      ], row_h=34, size=9.5)
    p.cell(il, "Device roles for schools", text_style(size=14, color="#0F172A", bold=True), 40, 530, 900, 24)
    roles = [("firewall", "Firewall"), ("core-switch", "Core switch"), ("access-switch", "Access switch"),
             ("wireless-controller", "Wireless gateway"), ("access-point", "Access point"),
             ("ptp-radio", "PtP radio"), ("hypervisor", "Hypervisor"), ("nvr", "NVR / VMS server"),
             ("camera", "Camera"), ("access-control", "Door controller"), ("bas-controller", "HVAC controller"),
             ("pa-system", "PA / bells / clocks"), ("oob-switch", "OOB switch")]
    for i, (slug, name) in enumerate(roles):
        k, fam = ROLE_ICONS[slug]
        labelled(p, il, 40 + (i % 4) * 290, 566 + (i // 4) * 60, 270, 48, name, slug, (k, fam), size=11, sub_size=9)
    p.cell(il, "Import order (Appendix F)", text_style(size=14, color="#0F172A", bold=True), 1200, 96, 900, 24)
    for i, (t, body) in enumerate([
            ("1 · Sites and locations", "One site per school; buildings, floors, closets and rooms as nested locations"),
            ("2 · Roles, types, tags", "netdiagrams netbox-setup writes the import files for roles and zone tags"),
            ("3 · Devices", "Network gear first, then building controllers; serials from the asset sheet"),
            ("4 · VLANs and prefixes", "One district VLAN group; prefixes per school from the address plan"),
            ("5 · Cables", "Uplinks first (they make the physical sheet), then AP and camera drops"),
            ("6 · Wireless LANs and circuits", "Six SSIDs; the two fiber ring legs and the backup line"),
    ]):
        labelled(p, il, 1200, 130 + i * 70, 1150, 58, t, body, None, size=12, sub_size=10, spacing=16)
    p.cell(il, "<b>Sync</b> · run <font face=\"JetBrains Mono\">netdiagrams</font> after each "
           "change window; the drift report lists what NetBox has that the drawing doesn't, and the reverse. "
           "NetDiagrams reads NetBox; its one write is the opt-in netbox-setup --apply.<br><b>Summer</b> · the district's busy season is June to August: export "
           "a copy before the work starts (<font face=\"JetBrains Mono\">netdiagrams export</font>) and compare in "
           "August.", NOTE, 1200, 566, 1150, 170)
    return p


def all_pages() -> list[Page]:
    return [overview(), logical(), physical(), hardware(), wireless(), flows(), failover(), multisite(), register(),
            netbox()]
