"""Sheet 3d from NetBox: what the wireless page keeps, drops and rewrites.

The template's wireless sheet is Plant A's: two controller pairs, CAPWAP captions, a
C9800 tag table and a hand-written SSID table. :mod:`sync` renames its site prefix,
and before this module every card and caption that NetBox had no record for kept
Plant A's words under the new site's name. Here the sheet follows NetBox:

- a controller, switch or radio card NetBox has no device for goes, like a device
  shape would; when the site runs without a controller the first emptied controller
  box becomes the management card (cloud dashboard, firewall, controllerless);
- a caption that still names a device, cable or SSID NetBox lacks shows an amber ``?``
  in its place, and the name is listed on the page's "Plan to improve" card;
- the SSID table, the AP register's mode/power/controller columns, the point-to-point
  register, the tag table and the flow rows come from NetBox's wireless LANs, links,
  interfaces and the ``wlan_*``/``ap_mode``/``wireless_*`` custom fields
  (:mod:`wireless`), never from the template's rows;
- the sheet is named after the vendors NetBox records, not after the template's.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

from . import gaps, profiles, truth, wireless
from .graph import Graph, cell_of, plain
from .model import _get, _label, _natural, _number

MGMT_MARK = "netdiagrams_wireless_mgmt"
LEFTOVER_MARK = "netdiagrams_leftovers"       # names a caption lost to '?', kept for the gaps card on a rebuild
RADIO_STYLE = ("edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=none;dashed=1;dashPattern=6 4;"
               "strokeColor=#7C3AED;strokeWidth=1.5;fontSize=9;fontColor=#5B21B6;labelBackgroundColor=#FFFFFF;"
               "html=1;fontFamily=Inter;")
AREA_LAYER = "APs by area (from NetBox)"
AREA_COLUMNS = [("AREA", 300), ("APS", 56), ("MODELS", 230), ("UPLINK CLOSETS", 250), ("SSIDS BROADCAST", 300)]
TEMPLATE_SHEET = "Wireless — Cisco WLAN · PtP"
TEMPLATE_TITLE_VENDOR = "(Cisco Catalyst WLAN)"
MODE_WORDS = re.compile(r"\s*·\s*(?:local|flexconnect|flex|bridge|monitor|sniffer)\s+mode\b", re.I)
CAPWAP = re.compile(r"CAPWAP(?:\s+over\s+[A-Za-z0-9-]+)?\s*(?:→|-&gt;|->)\s*" + truth.NAME.pattern)


# ------------------------------------------------------------------ what NetBox backs
def backed_names(nb) -> set[str]:
    """Every name a template caption may use that NetBox has an object for."""
    out = set(nb.devices) | set(nb.register_only)
    out |= {c.get("label") for c in nb.cables.values() if c.get("label")}
    out |= set(nb.circuits)
    out |= {w.get("ssid") for w in nb.wx.links if w.get("ssid")}
    out |= {w.get("ssid") for w in nb.wlans if w.get("ssid")}
    out |= {_label(d.get("virtual_chassis")) for d in nb.devices.values() if d.get("virtual_chassis")}
    return {n for n in out if n}


def is_backed(name: str, backed: set[str]) -> bool:
    """A name, or the pair/stack it stands for (S01-WLC for S01-WLC-01/-02)."""
    return name in backed or any(b.startswith(name + "-") for b in backed)


def _inside(a: tuple, b: tuple) -> bool:
    """Box a sits within box b."""
    return b[0] <= a[0] and b[1] <= a[1] and a[0] + a[2] <= b[0] + b[2] and a[1] + a[3] <= b[1] + b[3]


def _vertices(g: Graph, is_device):
    for i, el in list(g.els.items()):
        cell = cell_of(el)
        if cell is None or cell.get("vertex") != "1" or is_device(el) or g.hidden(i):
            continue
        yield i, el, cell


def leftovers(template: ET.Element) -> dict[str, set[str]]:
    """Page id -> the template names its captions lost to '?', for the captions still showing on it."""
    out: dict[str, set[str]] = {}
    for diagram in template.findall("diagram"):
        if diagram.find("mxGraphModel") is None:
            continue
        g = Graph(diagram)
        names = {n for i, el in g.els.items() if not g.hidden(i) for n in (el.get(LEFTOVER_MARK) or "").split(",") if n}
        if names:
            out[diagram.get("id") or ""] = names
    return out


def device_cards(g: Graph, is_device) -> dict[str, str]:
    """Plain cards whose label starts with a device name (the template's controllers, switches, radios)."""
    out = {}
    for i, el, cell in _vertices(g, is_device):
        if cell.get("parent") not in g.layers or (cell.get("style") or "").startswith("text"):
            continue
        text = plain(g.value(el))
        m = truth.NAME.match(text)
        if m and (len(text) == len(m.group(0)) or text[len(m.group(0))] in " \n·"):
            out[i] = m.group(0)
    return out


# ------------------------------------------------------------------ the page pass
def fill(g: Graph, nb, report, is_device, keep_unmatched: bool, prefix: str) -> None:
    """Drop, rewrite and rename what the template drew that NetBox doesn't back (W1, W4, W10, W11)."""
    wx = nb.wx
    backed = backed_names(nb)
    page = g.diagram.get("id") or ""
    devices_backed = lambda n: is_backed(n, set(nb.devices) | set(nb.register_only))

    # 1. Cards for devices NetBox doesn't have go, and the boxes they sat in are remembered.
    cards = device_cards(g, is_device)
    inner = [g.box(i) for i in cards] + [g.box(i) for i, el in g.els.items() if is_device(el) and not g.hidden(i)]
    holds = lambda i: any(b != g.box(i) and _inside(b, g.box(i)) for b in inner)
    groups = {i: n for i, n in cards.items() if holds(i)}          # a box titled with the pair's name
    cards = {i: n for i, n in cards.items() if i not in groups}
    gone = {i: n for i, n in cards.items() if not devices_backed(n)}
    containers = []
    for i in gone:
        box = truth.card_around(g, i)
        if box and box not in containers and box not in gone:
            containers.append(box)
    if gone and not keep_unmatched:
        boxes = [g.box(i) for i in gone]
        g.remove(list(gone))
        report.removed_cards += sorted(set(gone.values()))
        _remove_loose_edges(g, boxes)

    # 2. A site without an on-prem controller: the emptied controller box becomes the management card.
    if wx.aps and wx.no_controller:
        _management_card(g, nb, report, is_device, containers)

    # 3. Captions: CAPWAP phrases follow the management mode; names NetBox lacks become '?'.
    pattern = re.compile(r"(?<![A-Z0-9-])" + re.escape(prefix) + r"[A-Z0-9]+(?:-[A-Z0-9]+)*(?![A-Za-z0-9])") \
        if prefix else None
    guide = set(profiles.current().guide_ids.get(page, ()))   # template prose bound for the hidden guide layer
    for i, el, cell in _vertices(g, is_device):
        value = g.value(el)
        if not value or el.get(MGMT_MARK) or i in guide:
            continue
        new = value
        if wx.aps and wx.no_controller:
            new = CAPWAP.sub(lambda m: _mgmt_phrase(wx), new)
            new = MODE_WORDS.sub("", new)     # "local mode" is a controller's word; the AP register carries the real mode
        lost: set[str] = set()
        if pattern:
            def swap(m: re.Match) -> str:
                name = m.group(0)
                if is_backed(name, backed):
                    return name
                lost.add(name)
                return gaps.MISSING
            new = pattern.sub(swap, new)
        if new != value:
            g.set_value(el, new)
        if lost:  # kept on the caption (an <object>, so draw.io keeps it too) for the card, this build and the next
            had = {n for n in (el.get(LEFTOVER_MARK) or "").split(",") if n}
            g.wrap(i, **{LEFTOVER_MARK: ",".join(sorted(had | lost))})

    # 4. The sheet's own name and title name the vendors NetBox records (W10).
    _vendor_names(g, wx)
    # 5. The RF survey link (W11).
    _survey(g, wx)


def _remove_loose_edges(g: Graph, boxes: list[tuple]) -> None:
    """Lines drawn point to point between removed cards (the HA back-to-back link) go with them."""
    doomed = []
    for i, el in g.els.items():
        cell = cell_of(el)
        if cell is None or cell.get("edge") != "1" or cell.get("source") or cell.get("target"):
            continue
        points = [(float(pt.get("x", 0)), float(pt.get("y", 0))) for pt in cell.iter("mxPoint")
                  if pt.get("as") in ("sourcePoint", "targetPoint")]
        if points and all(any(bx <= x <= bx + bw and by <= y <= by + bh for bx, by, bw, bh in boxes)
                          for x, y in points):
            doomed.append(i)
    if doomed:
        g.remove(doomed)


def _mgmt_phrase(wx: wireless.Index) -> str:
    if wx.mode == "cloud":
        return f"mgmt → {html.escape(wx.manager or 'cloud dashboard')}"
    if wx.mode == "firewall":
        return f"managed by {html.escape(wx.manager or 'the firewall')}"
    if wx.mode == "controllerless":
        return "embedded controller (no WLC)"
    return "controller " + gaps.MISSING


def _management_card(g: Graph, nb, report, is_device, containers: list[str]) -> None:
    """One box says how the APs are managed; the other emptied controller boxes go."""
    marked = [i for i, el in g.els.items() if el.get(MGMT_MARK)]
    occupied = [g.box(i) for i, el in g.els.items() if is_device(el) and not g.hidden(i)]
    occupied += [g.box(i) for i in device_cards(g, is_device) if i not in containers]
    empty = []
    for i in containers:
        if i not in g.els:
            continue
        box = g.box(i)
        if any(b != box and _inside(b, box) for b in occupied):
            continue
        empty.append(i)
    empty.sort(key=lambda i: (g.box(i)[1], g.box(i)[0]))
    keep = marked[0] if marked else (empty[0] if empty else None)
    if keep is None:
        return
    title, text = nb.wx.management_card()
    el = g.els[keep]
    if el.tag != "object":
        el = g.wrap(keep)
    el.set(MGMT_MARK, "1")
    el.set("tooltip", f"{title}\n{text}")
    g.set_value(el, f"<b>{html.escape(title)}</b><br><span style=\"font-size:9px\">{html.escape(text)}</span>")
    cell = cell_of(el)
    style = cell.get("style") or ""
    if "verticalAlign=top" not in style:
        cell.set("style", style + "verticalAlign=top;spacing=8;whiteSpace=wrap;")
    doomed = [i for i in empty if i != keep]
    if doomed:
        g.remove(doomed)
    report.wireless_management = title


def _vendor_names(g: Graph, wx: wireless.Index) -> None:
    name = g.diagram.get("name") or ""
    makers_list = wx.manufacturers()
    # The template's own vendor word stays when NetBox agrees with it (a Cisco site keeps "Cisco WLAN").
    agrees = bool(makers_list) and makers_list[0].split()[0] in TEMPLATE_SHEET and wx.mode != "cloud"
    if TEMPLATE_SHEET in name and (makers_list or wx.mode == "cloud") and not agrees:
        g.diagram.set("name", name.replace(TEMPLATE_SHEET, wx.sheet_title()))
        g.name = g.diagram.get("name")
    if agrees:
        return
    makers = " · ".join(makers_list[:2])
    for el in g.els.values():
        value = g.value(el)
        if TEMPLATE_TITLE_VENDOR in value:
            if wx.mode == "cloud":
                who = wx.manager or makers
                g.set_value(el, value.replace(TEMPLATE_TITLE_VENDOR, f"({html.escape(who)}, cloud-managed)" if who
                                              else "(cloud-managed)"))
            elif makers:
                g.set_value(el, value.replace(TEMPLATE_TITLE_VENDOR, f"({html.escape(makers)})"))
            else:
                g.set_value(el, value.replace(" " + TEMPLATE_TITLE_VENDOR, "").replace(TEMPLATE_TITLE_VENDOR, ""))


def _survey(g: Graph, wx: wireless.Index) -> None:
    url = wx.survey()
    if not url:
        return
    for i, el in g.els.items():
        cell = cell_of(el)
        if cell is None or cell.get("vertex") != "1" or cell.get("parent") not in g.layers:
            continue      # a layer can be named "AP placement" too; its name is a button, not a caption
        value = g.value(el)
        if plain(value).startswith("AP placement") and "Survey:" not in value:
            shown = re.sub(r"^https?://", "", url)[:60]
            g.set_value(el, f'{value} · Survey: <a href="{html.escape(url)}">{html.escape(shown)}</a>')
            return


# ------------------------------------------------------------------ tables
def _pill(status: str) -> str:
    from .sync import STATUS_COLORS
    return f'<font color="{STATUS_COLORS.get(status, "#334155")}"><b>{html.escape(status)}</b></font>'


def _missing(text: str, link: str = "", tooltip: str = "") -> tuple:
    return (text, link, False, tooltip) if text else (gaps.MISSING, link, True, tooltip or "Not in NetBox yet")


def ssid_rows(g: Graph, table: str, header: list[str], nb) -> list[list]:
    """The SSID table from NetBox wireless LANs; an empty column shows '?' rather than the template's text."""
    wx = nb.wx
    if not nb.wlans:
        if not (wx.aps or wx.controllers):
            return []
        return [[("No wireless LANs in NetBox yet", nb.link("wireless/wireless-lans", site_id=nb.site.get("id"))
                  if nb.site.get("id") is not None else "", False, "Wireless ▸ Wireless LANs: one per SSID")
                 if n == 0 else (gaps.MISSING, "", True) if n in (1, 3) else ("", "")
                 for n in range(len(header))]]
    rows = []
    for s in wx.ssids():
        ssid = html.escape(s.ssid)
        if s.status not in ("", "active"):
            ssid = f"{ssid} {_pill(s.status)}"
        link = nb.link("wireless/wireless-lans", s.wlan) if s.wlan.get("id") else ""
        vlan_text = " · ".join(x for x in [str(s.vlan.get("vid") or "")] + [p.get("prefix", "") for p in s.prefixes]
                               if x)
        controller_link = ""
        if s.controller and s.controller in nb.devices:
            controller_link = nb.link("dcim/devices", nb.devices[s.controller])
        values = {
            "SSID": (ssid, link, True, s.notes),
            "SECURITY": _missing(s.security, "", "Wireless LAN ▸ Auth type, or the wlan_security field"),
            "CONTROLLER": _missing(s.controller, controller_link,
                                   "Site ▸ Wireless management, or the APs' Wireless controller field"),
            "VLAN": _missing(vlan_text, nb.link("ipam/vlans", s.vlan) if s.vlan.get("id") else "",
                             "Wireless LAN ▸ VLAN"),
            "ZONE": _missing(s.zone[len("zone-"):].upper() if s.zone.startswith("zone-") else s.zone.upper(),
                             "", "The VLAN's zone tag, or a zone- tag on the wireless LAN"),
            "SWITCHING": _missing(s.switching, "", "Wireless LAN ▸ Switching (wlan_switching)"),
            "BANDS": _missing(s.bands, "", "Wireless LAN ▸ Bands (wlan_bands)"),
            "BROADCAST ON": _missing(s.broadcast_on, "",
                                     "AP radio interfaces ▸ Wireless LANs, or the wireless LAN's scope"),
            "GUEST CONTROLS": (s.guest_controls, "", False,
                               "Wireless LAN ▸ Client isolation, Portal") if s.guest_controls or not s.zone
                              or not wireless.GUEST_ZONE.search(s.zone) else
                              (gaps.MISSING, "", True, "A guest SSID: record client isolation and the portal"),
            "NOTES": (s.notes, ""),
        }
        row = []
        for col in header:
            key = next((k for k in values if col.startswith(k)), None)
            row.append(values[key] if key else ("", ""))
        rows.append(row)
    return rows


def ap_columns(nb, d: dict, col: str) -> tuple | None:
    """MODE, CONTROLLER, POWER and a radio-fed SWITCH · PORT for an AP register row; None when not ours."""
    wx = nb.wx
    name = d.get("name", "")
    role = _get(d, "role", "slug")
    if role not in wireless.WIRELESS_ROLES:
        return None
    if col == "MODE":
        return _missing(wx.ap_mode(d), "", "Device ▸ AP mode (ap_mode)") if role in ("access-point", "workgroup-bridge") \
            else ("", "")
    if col == "CONTROLLER":
        if role not in ("access-point", "workgroup-bridge"):
            return ("", "")
        controller, how, path = wx.controller_of(d)
        if not controller:
            return _missing("", "", "Device ▸ Wireless controller, or Site ▸ Wireless management")
        link = nb.link(path, nb.devices[controller]) if path and controller in nb.devices else ""
        site = wx.controller_site(controller) if path else ""
        text = f"{controller} ({site})" if site else controller
        if controller in nb.devices and wx.ha_state(controller):
            how = f"{how}; {wx.ha_state(controller)}"
        return (text, link, False, f"From {how}")
    if col == "POWER":
        if role not in ("access-point",):
            return ("", "")
        return _missing(wx.ap_power(d), "", "Interface ▸ PoE mode / PoE type on the AP's uplink or the switch port")
    if col.startswith("SWITCH") and wx.is_radio_fed(name):
        text = wx.uplink_text(name)
        root = text.split(" via ", 1)[-1] if " via " in text else ""
        return (text, nb.link("dcim/devices", nb.devices[root]) if root in nb.devices else "", False,
                "Radio-fed: the uplink is a wireless link, not a switch port")
    if col == "CABLE" and wx.is_radio_fed(name):
        return ("—", "", False, "No cable: radio uplink")
    return None


def ptp_rows(g: Graph, table: str, header: list[str], nb) -> list[list]:
    """The point-to-point register: one row per NetBox wireless link between radios (W2, W6)."""
    wx = nb.wx
    meshed = {id(lw) for *_, lw in wx.mesh_links() if lw}
    links = [w for w in wx.links if id(w) not in meshed]
    if not links:
        # The template's example links (with their management addresses) would read as this site's.
        return [[("?", "", False, "Wireless ▸ Wireless links") if n == 0 else
                 ("No wireless links in NetBox yet", "") if n == 1 else ("", "") for n in range(len(header))]]
    rows = []
    for n, w in enumerate(sorted(links, key=lambda w: (w.get("ssid") or "", w.get("id") or 0))):
        (da, ia), (db, ib) = wx.link_ends[id(w)]
        link = nb.link("wireless/wireless-links", w) if w.get("id") else ""

        def radio(dev: str, iface: str) -> tuple:
            d = nb.devices.get(dev)
            if not d:
                return _missing(dev, "", "Device not in NetBox")
            place = _label(d.get("location"))
            return (f"{_short(dev, nb)} {iface}".strip() + (f" · {place}" if place else ""),
                    nb.link("dcim/devices", d))

        models = []
        for dev in (da, db):
            m = _label((nb.devices.get(dev) or {}).get("device_type"))
            if m:
                models.append(m)
        model = (f"{models[0]} ×2" if len(models) == 2 and models[0] == models[1] else " · ".join(models))
        band = " / ".join(x for x in (wx.radio_text(da, ia), wx.radio_text(db, ib)) if x)
        if wx.radio_text(da, ia) and wx.radio_text(da, ia) == wx.radio_text(db, ib):
            band = wx.radio_text(da, ia)
        distance = ""
        if w.get("distance") is not None:
            distance = f"{_number(w.get('distance'))} {_get(w, 'distance_unit', 'value') or 'm'}"
        auth = " · ".join(x for x in (_get(w, "auth_type", "label") or _get(w, "auth_type", "value"),
                                      _get(w, "auth_cipher", "label") or _get(w, "auth_cipher", "value")) if x)
        mgmt = " / ".join(x for x in ((_get(nb.devices.get(da) or {}, "primary_ip4", "address") or "").split("/")[0],
                                      (_get(nb.devices.get(db) or {}, "primary_ip4", "address") or "").split("/")[0])
                          if x)
        vlans = _bridged_vlans(nb, da, db)
        status = (_get(w, "status", "value") or "connected").lower()
        label = w.get("ssid") or f"Link {w.get('id') or n + 1}"
        if status != "connected":
            label = f"{html.escape(label)} {_pill(status)}"
            label_cell = (label, link, True)
        else:
            label_cell = (label, link)
        values = {
            "LINK": label_cell, "RADIO A": radio(da, ia), "RADIO B": radio(db, ib),
            "MODEL": _missing(model, "", "Device ▸ Device type"),
            "BAND": _missing(band, "", "Interface ▸ RF channel, width, Tx power on the radio interfaces"),
            "PATH": _missing(distance, "", "Wireless link ▸ Distance"),
            "CAPACITY": ("", ""),
            "SECURITY": _missing(auth, "", "Wireless link ▸ Auth type, cipher"),
            "MGMT": _missing(mgmt, "", "Device ▸ Primary IPv4 on each radio"),
            "VLANS": (vlans, "", False, "Tagged VLANs on the radios' wired ports"),
        }
        row = []
        for col in header:
            key = next((k for k in values if col.startswith(k)), None)
            row.append(values[key] if key else ("", ""))
        rows.append(row)
    return rows


def _short(dev: str, nb) -> str:
    from .sync import _short_dev
    return _short_dev(dev)


def _bridged_vlans(nb, da: str, db: str) -> str:
    vids = []
    for dev in (da, db):
        for i in nb.wx.device_interfaces.get(dev, []):
            for v in i.get("tagged_vlans") or []:
                vid = v.get("vid") if isinstance(v, dict) else v
                if vid is not None and vid not in vids:
                    vids.append(vid)
            u = _get(i, "untagged_vlan", "vid", default=None)
            if u is not None and u not in vids:
                vids.append(u)
    return ", ".join(str(v) for v in sorted(vids))


def tag_rows(g: Graph, table: str, header: list[str], nb) -> list[list]:
    """The controller tag table from the APs' policy_tag/site_tag/rf_tag fields, one row per area."""
    rows = []
    for r in nb.wx.tag_rows():
        values = {
            "AREA": (r["area"], ""),
            "POLICY TAG": (r["policy_tag"], ""), "SITE TAG": (r["site_tag"], ""), "RF TAG": (r["rf_tag"], ""),
            "CONTROLLER": (" · ".join(r["controllers"]), ""),
            "APS": (_ap_range(r["aps"], nb), ""),
        }
        row = []
        for col in header:
            key = next((k for k in values if col.startswith(k)), None)
            row.append(values[key] if key else ("", ""))
        rows.append(row)
    return rows


def _ap_range(names: list[str], nb) -> str:
    short = [_short(n, nb) for n in sorted(names, key=_natural)]
    if len(short) > 3:
        return f"{short[0]} … {short[-1]} ({len(short)})"
    return " · ".join(short)


def hide_tag_table(g: Graph, table: str) -> None:
    """No AP carries a tag model: the table and its caption go to the hidden Guides layer."""
    layer = truth._layer(g, truth.GUIDE_LAYER, hidden=True)
    g.els[layer].set("visible", "0")
    tx, ty, tw, th = g.box(table)
    for i, el in list(g.els.items()):
        cell = cell_of(el)
        if cell is None or cell.get("vertex") != "1" or cell.get("parent") not in g.layers:
            continue
        x, y, w, h = g.box(i)
        caption = (cell.get("style") or "").startswith("text") and abs(x - tx) < 4 and 0 < ty - y <= 40
        if i == table or caption:
            truth._move_to_layer(g, i, layer)
    g.reindex()


def flow_rows(g: Graph, table: str, header: list[str], nb, before: list[list[str]]) -> list[list]:
    """The wireless flow rows for a site without a controller: CAPWAP rows become the management flow (W4)."""
    wx = nb.wx
    replacement = wx.management_flow()
    if not (wx.aps and wx.no_controller) or replacement is None or not before:
        return []
    rows, done = [], False
    for cells in before:
        text = " ".join(cells)
        if "CAPWAP" in text:
            if done:
                continue      # one management flow stands for every CAPWAP row
            done = True
            cells = [cells[0]] + replacement
        elif "RADIUS" in text and len(cells) > 2:
            # The RADIUS client is the APs (or the cloud) when there is no controller to proxy it.
            cells = list(cells)
            cells[2] = "Access points" if wx.mode != "cloud" else f"APs / {wx.manager or 'cloud dashboard'}"
        rows.append([(c, "") for c in cells[:len(header)]] + [("", "")] * max(0, len(header) - len(cells)))
    return rows


def mark_example_regions(g: Graph, template: set[str], nb) -> list[str]:
    """Watermark the site plan schematic and the flow table while they still show the template's site.

    Both are drawn for the template's own plant. The schematic is an example while it labels
    an AP or radio ("OF-02") that NetBox has no device for; the flow table is one while a
    row speaks of gear the site doesn't have in NetBox.
    """
    real = set(nb.devices)
    ours = lambda label: any(t.endswith("-" + label) for t in template)
    backed = lambda label: any(n.endswith("-" + label) for n in real)
    regions = []
    for i, el in g.els.items():
        if plain(g.value(el)).startswith("AP placement & RF layout"):
            card = truth.card_around(g, i)
            if card:
                regions.append(("site plan schematic", card, False))
    for table in g.tables():
        if g.header(table)[:2] == ["ID", "FLOW"]:
            card = truth.card_around(g, table)
            if card:
                regions.append(("wireless flows", card, True))
    marked = []
    for what, card, lost in regions:
        if g.hidden(card):
            continue
        texts = [plain(g.value(el)) for el in g.els.values() if gaps._within(g, el, g.box(card))]
        example = any(t and ours(t) and not backed(t) for t in texts)
        if lost:   # a row whose endpoint NetBox lacks: a name lost to '?', or radios or a controller it hasn't
            example |= any(t == "?" or t.startswith("? ") for t in texts)
            example |= not nb.wx.radios and any(re.search(r"\bPtP", t) for t in texts)
            example |= nb.wx.no_controller and any("CAPWAP" in t for t in texts)
        if example:
            truth.watermark(g, "EXAMPLE", f"{truth.possessive(profiles.current().site_name)}, not from this site's NetBox",
                            g.box(card))
            marked.append(f"{g.name}: {what}")
    return marked


# ------------------------------------------------------------------ links and tray
def add_links(g: Graph, nb, report, is_device) -> int:
    """NetBox wireless links the sheet has no line for, dashed, between the cards that are drawn (W5, W6)."""
    wx = nb.wx
    cards = {el.get("name"): i for i, el in g.els.items() if is_device(el) and not g.hidden(i)}
    for i, name in device_cards(g, is_device).items():
        cards.setdefault(name, i)
    # An AP folded into a counted group ("AP-F3 ×8") is drawn by its group's card: a mesh hop starts there.
    for i, el in list(g.els.items()):
        if is_device(el) and not g.hidden(i):
            for member in (el.get("netdiagrams_group") or "").split(","):
                if member:
                    cards.setdefault(member, i)
    new = []
    for w in wx.links:
        if id(w) in report.matched_wireless:
            continue
        (da, ia), (db, ib) = wx.link_ends[id(w)]
        if da in cards and db in cards and da != db:
            new.append((w, (da, ia), (db, ib)))
    if not new:
        return 0
    layer = f"{g.diagram.get('id', 'p')}-nbradio"
    if layer not in g.els:
        from .sync import ADDED_LINKS_LAYER
        g.root.append(ET.Element("mxCell", {"id": layer, "value": ADDED_LINKS_LAYER, "style": "", "parent": "0"}))
    for n, (w, (da, ia), (db, ib)) in enumerate(new):
        kind = "mesh" if da in wx.mesh or db in wx.mesh else "WGB" if (
            da in {d["name"] for d in wx.wgbs} or db in {d["name"] for d in wx.wgbs}) else "radio link"
        text = " · ".join(x for x in (w.get("ssid") or kind, wx.radio_text(da, ia) or wx.radio_text(db, ib)) if x)
        attrs = {"object": "wireless.wirelesslink", "ssid": w.get("ssid") or "",
                 "status": _get(w, "status", "value") or "", "interface_a": f"{da}:{ia}", "interface_b": f"{db}:{ib}",
                 "auth_type": _get(w, "auth_type", "value") or "", "auth_cipher": _get(w, "auth_cipher", "value") or ""}
        obj = ET.Element("object", {"id": f"{layer}-{n}", "label": html.escape(text), **attrs})
        if nb.url and w.get("id") is not None:
            obj.set("link", nb.link("wireless/wireless-links", w))
            obj.set("linkTarget", "_blank")
        obj.set("tooltip", "\n".join(f"{k}: {v}" for k, v in attrs.items() if v and k != "object"))
        cell = ET.SubElement(obj, "mxCell", {"style": RADIO_STYLE, "edge": "1", "parent": layer,
                                              "source": cards[da], "target": cards[db]})
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        g.root.append(obj)
        report.added_wireless_links.append(w.get("ssid") or f"{da} ⇄ {db}")
    g.reindex()
    return len(new)


def wireless_only(nb, names: list[str]) -> list[str]:
    """The NetBox-only devices that belong on the wireless sheet's tray, not the physical page's."""
    return [n for n in names if _get(nb.devices[n], "role", "slug") in wireless.WIRELESS_ROLES]


# ------------------------------------------------------------------ APs by area
def add_area_register(g: Graph, nb) -> bool:
    """One row per NetBox location with APs: count, models, uplink closets, SSIDs (W11)."""
    from .typicals import table_card, table_styles

    rows_data = nb.wx.aps_by_area()
    if not rows_data:
        return False
    layer = f"{g.diagram.get('id')}-aps-by-area"
    if layer in g.els:
        return False
    like = next((t for t in g.tables() if "HOSTNAME" in g.header(t)), None) or next(iter(g.tables()), None)
    if like is None:
        return False
    styles = table_styles(g, like)
    g.root.append(ET.Element("mxCell", {"id": layer, "value": AREA_LAYER, "style": "", "parent": "0"}))
    g.reindex()
    rows = []
    for r in rows_data:
        link = nb.link("dcim/locations", r["location"]) if r["location"].get("id") is not None else ""
        rows.append([(r["area"], link), (str(len(r["aps"])), ""), (" · ".join(r["models"]), ""),
                     (" · ".join(r["closets"]) or "—", ""), (" · ".join(r["ssids"]) or "—", "")])
    width = sum(w for _, w in AREA_COLUMNS) + 28
    skip = ("Border", "Controls", "Guides")
    bottom = max((g.box(i)[1] + g.box(i)[3] for i, el in g.els.items() if cell_of(el) is not None
                  and cell_of(el).get("vertex") == "1" and cell_of(el).get("parent") in g.layers
                  and not g.layer_of(i).startswith(skip)), default=0)
    x, y = 24, bottom + 16
    table_card(g, layer, styles, x, y, "APs by area",
               "Where the coverage is, from NetBox locations: APs, models, the closets they uplink to and the "
               "SSIDs their radios carry. A room with no SSIDs listed has no radio interface assigned a wireless LAN.",
               AREA_COLUMNS, rows, f"{layer}-card")
    return True
