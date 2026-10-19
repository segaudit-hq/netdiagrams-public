"""Make a copy of a built drawing that is safe to send outside the plant.

``netdiagrams share site.drawio -o site-vendor.drawio`` reads a drawing NetDiagrams
built and writes a copy for one audience:

- **vendor** (default): the drawings a contractor needs to quote or install. Management
  IPs, serial numbers, asset tags, circuit IDs, NetBox links and the data carried on
  every shape are gone; the example sheets, guide notes, plan cards and the on-screen
  controls are gone too. Any IP address left in visible text is blanked.
- **auditor**: the evidence set. Every register and tag stays, NetBox links and
  tooltips stay so a finding can be traced back; the guide notes and the template's
  example sheets go, and the hidden per-shape data is cut down to what the drawing shows.
- **management**: the overview and the glance sheet only, with the vendor rules.

Before writing, the copy is checked against what the original knew: every IP, serial,
asset tag, circuit ID and NetBox URL the original carried. If one survives in a vendor
or management copy, nothing is written and the leaks are listed; ``--allow-leaks``
writes it anyway. Each sheet's provenance line says the copy is shared and for whom.
"""

from __future__ import annotations

import html
import ipaddress
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from . import interactive, paper, stencils
from .graph import Graph, cell_of

AUDIENCES = ("vendor", "auditor", "management")
HIDDEN = "[hidden]"

# Layer names (prefix or fragment) that leave a shared copy, by audience.
STRIP_LAYERS = {
    "vendor": ("hide before sharing", "Guides", "Controls", "Copy of the typical", "Plan to improve",
               "How to draw this page", "3b · Serial numbers", "Links from NetBox", "Changed since"),
    "auditor": ("Guides", "How to draw this page"),
    "management": ("hide before sharing", "Guides", "Controls", "Copy of the typical", "Plan to improve",
                   "How to draw this page", "3b · Serial numbers", "Links from NetBox", "Schedules",
                   "Changed since"),
}
KEEP_PAGES = {"management": ("overview", "glance")}
# Sheets that never leave for an audience: the audit evidence register names owners and says what is unpatched.
DROP_PAGES = {"vendor": ("audit",)}
# Object attributes that survive the strip. Everything else NetBox put on a shape goes.
KEEP_ATTRS = {"vendor": {"id", "label", "placeholders"},
              "auditor": {"id", "label", "placeholders", "link", "linkTarget", "tooltip", "netdiagrams_provenance"},
              "management": {"id", "label", "placeholders"}}
REDACT = {"vendor": True, "auditor": False, "management": True}
# Attributes whose values are secrets to check the copy against.
SECRET_ATTRS = ("primary_ip4", "primary_ip6", "oob_ip", "serial", "asset_tag", "cid", "x_optic_serial", "link",
                "auth_psk")
PSK_ATTR = re.compile(r"(psk|secret|passphrase|password)", re.I)
# Register columns blanked for a vendor or management (the register itself stays useful: model, room, rack, U).
# CRIT goes too: which assets a site can least afford to lose is not for a vendor's copy.
SECRET_COLUMNS = {"SERIAL", "MGMT IP", "OOB IP", "ASSET TAG", "CIRCUIT ID", "CID", "IP", "SUBNET", "GATEWAY",
                  "OPTIC SERIAL", "CRIT", "CRITICALITY"}
SERIAL_SUFFIX = re.compile(r"(\s*(·|&middot;|&#183;)\s*)?SN\s+%serial%")

IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?(?![\d.])")
# A candidate only: ``_ips`` keeps the ones that parse, so '10:30:00' stays and '2001:db8::/64' goes.
IPV6 = re.compile(r"(?<![:\w.])[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}(?:/\d{1,3})?(?![:\w])")


def _is_ip(text: str) -> bool:
    if ":" in text and not re.search(r"[0-9A-Fa-f]", text):
        return False
    try:
        ipaddress.ip_interface(text)
        return True
    except ValueError:
        return False


def _ips(text: str) -> list[str]:
    """Every IPv4 and IPv6 address (or prefix) in the text."""
    return [m for m in IPV4.findall(text) + IPV6.findall(text) if _is_ip(m)]


def _bounded(secret: str) -> re.Pattern:
    """A secret as a whole word: asset tag '2026' must not blank '2026-10-17'."""
    return re.compile(rf"(?<![\w-]){re.escape(secret)}(?![\w-])")


ANCHOR = re.compile(r"<a\b[^>]*>(.*?)</a>", re.S)
PLACEHOLDER = re.compile(r"%(\w+)%")
# Sentences about the editable file's hidden data, untrue once that data is gone.
EDITOR_SENTENCE = re.compile(r"\s*[^.<>]*\b(Hover|Edit Data)\b[^.<>]*\.")
LINKED_TITLE = ", every row linked to NetBox"
WITHHELD = " (serials, addresses and NetBox links withheld in this copy)"
LAYERS_CARD = "<b>Layers on this sheet</b>"


@dataclass
class ShareReport:
    audience: str
    pages_kept: list[str] = field(default_factory=list)
    pages_removed: list[str] = field(default_factory=list)
    layers_removed: list[tuple[str, str]] = field(default_factory=list)
    attributes_stripped: int = 0
    redacted: int = 0
    links_removed: int = 0
    leaks: list[tuple[str, str, str]] = field(default_factory=list)  # (page, what, where)

    def lines(self) -> list[str]:
        n = len(self.pages_kept)
        out = [f"Shared copy for {_an(self.audience)}: {n} sheet{'' if n == 1 else 's'} kept"
               + (f", {len(self.pages_removed)} removed ({', '.join(self.pages_removed)})" if self.pages_removed
                  else "") + "."]
        if self.layers_removed:
            out.append(f"  {len(self.layers_removed)} layers removed: "
                       + "; ".join(sorted({name for _, name in self.layers_removed})) + ".")
        out.append(f"  {self.attributes_stripped} hidden data fields stripped from shapes"
                   + (f", {self.links_removed} NetBox links removed" if self.links_removed else "")
                   + (f", {self.redacted} addresses or identifiers blanked" if self.redacted else "") + ".")
        if self.leaks:
            out.append(f"  {len(self.leaks)} leaks found:")
            out += [f"    {page}: {what} in {where}" for page, what, where in self.leaks[:40]]
            if len(self.leaks) > 40:
                out.append(f"    … and {len(self.leaks) - 40} more")
        elif self.audience == "auditor":
            out.append("  Kept on purpose for the auditor: IPs, serials, circuit IDs, registers and NetBox links.")
        else:
            out.append("  Checked: no IP, serial, asset tag, circuit ID or NetBox URL from the original remains.")
        return out


def _an(word: str) -> str:
    if word == "management":
        return word
    return ("an " if word[:1] in "aeiou" else "a ") + word


def _layer_matches(name: str, patterns: tuple[str, ...]) -> bool:
    low = name.lower()
    return any(p.lower() in low for p in patterns)


def _texts(el: ET.Element):
    """(attribute name, text) pairs of everything a reader or a tooltip could show."""
    for key in ("label", "value", "tooltip"):
        if el.get(key):
            yield key, el.get(key)
    cell = cell_of(el) if el.tag != "mxCell" else el
    if cell is not None and cell is not el and cell.get("value"):
        yield "value", cell.get("value")


def secrets(mxfile: ET.Element) -> dict[str, str]:
    """Secret -> kind, harvested from the original before anything is stripped."""
    found: dict[str, str] = {}
    for el in (el for el in mxfile.iter() if el.tag in ("object", "UserObject")):
        for key in list(SECRET_ATTRS) + [k for k in el.attrib if PSK_ATTR.search(k) and k not in SECRET_ATTRS]:
            value = (el.get(key) or "").strip()
            if key == "link" and value:
                host = re.sub(r"^https?://", "", value).split("/")[0]
                if host and "." in host:
                    found.setdefault(host, "NetBox host")
                continue
            if len(value) >= 4 and value not in ("—", "n/a"):
                found.setdefault(value.split("/")[0] if key.endswith("ip4") or key.endswith("ip6")
                                 or key == "oob_ip" else value, key.replace("_", " ").replace("cid", "circuit ID"))
    for el in mxfile.iter():
        for _, text in _texts(el):
            plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
            for ip in _ips(plain):
                found.setdefault(ip.split("/")[0], "IP address")
    return found


def _resolve_placeholders(g: Graph, el: ET.Element, redact: bool) -> bool:
    """Write %name%-style placeholders into the label before their attributes are stripped.

    A key is read as draw.io reads it, from the shape or the shape it sits in (a rack pill
    inside its device card). One nothing resolves is dropped rather than printed literally.
    Returns False when the label is left with nothing to say, so the caller can remove it.
    """
    from .sync import _inherited

    label = el.get("label") or ""
    if el.get("placeholders") == "1" and "%" in label:
        if redact:
            label = SERIAL_SUFFIX.sub("", label)

        def value(m):
            key = m.group(1)
            found = _inherited(g, el, key)
            if found is None:
                return ""
            return HIDDEN if redact and key in SECRET_ATTRS else found

        label = PLACEHOLDER.sub(value, label)
        el.set("label", label)
    el.attrib.pop("placeholders", None)
    return bool(re.sub(r"<[^>]+>|&nbsp;|[\s·—-]", "", html.unescape(label)).strip()) or not label


def _fix_wording(g: Graph) -> None:
    """Make the copy's own words true: no 'Edit Data' advice, no 'linked to NetBox', a layer list that matches."""
    for el_id, el in list(g.els.items()):
        text = g.value(el)
        if not text:
            continue
        if text.startswith(LAYERS_CARD):
            names = [n for n in g.layers.values() if n and not n.startswith(("Border", "Example watermark"))]
            text = (LAYERS_CARD + " (View ▸ Layers)<br><br>" + "<br>".join(html.escape(n) for n in names)
                    + "<br><br>Shared copy: management IPs, serial numbers, circuit IDs, the hidden shape data and "
                      "the links to NetBox were removed before sending.")
        else:
            if LINKED_TITLE in text:
                text = text.replace(LINKED_TITLE, WITHHELD)
            if "Hover" in text or "Edit Data" in text:
                text = EDITOR_SENTENCE.sub("", text)
        g.set_value(el, text)


def _blank_columns(g: Graph, report: ShareReport) -> None:
    """Empty the secret columns of every register and schedule, keeping the rest of the row."""
    for table in g.tables():
        header = g.header(table)
        cols = [i for i, h in enumerate(header) if h.strip().upper() in SECRET_COLUMNS]
        if not cols:
            continue
        for row in g.rows(table)[1:]:
            cells = g.row_cells(row)
            for i in cols:
                if i < len(cells) and g.value(g.els[cells[i]]):
                    g.set_value(g.els[cells[i]], "")
                    report.redacted += 1


def _redact(text: str, known: dict[str, str]) -> tuple[str, int]:
    """Blank every IP address and every secret the original carried (serials, asset tags, circuit IDs, hosts)."""
    n = 0

    def sub(m):
        nonlocal n
        if not _is_ip(m.group()):
            return m.group()
        n += 1
        return HIDDEN

    text = IPV4.sub(sub, text)
    text = IPV6.sub(sub, text)
    for secret in known:
        if secret in text:
            text, hits = _bounded(secret).subn(HIDDEN, text)
            n += hits
    return text, n


def _provenance_note(label: str, audience: str) -> str:
    parts = [p for p in label.split(" · ") if not p.startswith("shared copy")]
    for i, part in enumerate(parts):
        if part.startswith("from ") and audience != "auditor":
            # Leave the NetBox host out; keep the version if the line carried one.
            nxt = parts[i + 1] if i + 1 < len(parts) else ""
            if nxt.startswith("NetBox "):
                parts[i] = f"from {nxt}"
                parts.pop(i + 1)
            else:
                parts.pop(i)
            break
    parts.append(f"shared copy for {_an(audience)}")
    return " · ".join(parts)


def share(mxfile: ET.Element, audience: str = "vendor", keep_examples: bool = False) -> ShareReport:
    """Strip ``mxfile`` in place for ``audience``; the report says what went and what leaked."""
    if audience not in AUDIENCES:
        raise ValueError(f"audience must be one of {', '.join(AUDIENCES)}, not {audience!r}")
    report = ShareReport(audience)
    stencils.inflate(mxfile)  # a page saved compressed would otherwise pass through unread
    known = secrets(mxfile)
    keep_attrs = KEEP_ATTRS[audience]
    redact = REDACT[audience]

    for diagram in list(mxfile.findall("diagram")):
        page_id = diagram.get("id") or ""
        name = diagram.get("name") or page_id
        kept = KEEP_PAGES.get(audience)
        # An example sheet is one the build stamped; a sheet the audience keeps stays, stamp and all.
        example = any(el.get("netdiagrams_example") == "page" for el in diagram.iter("object"))
        drop = (kept is not None and page_id not in kept) or page_id in DROP_PAGES.get(audience, ()) or \
               (not keep_examples and example and not (kept and page_id in kept))
        if drop:
            mxfile.remove(diagram)
            report.pages_removed.append(name.split(" · ")[0] if " · " in name else name)
            continue
        report.pages_kept.append(name)
        g = Graph(diagram)
        doomed = [i for i, lname in g.layers.items() if _layer_matches(lname, STRIP_LAYERS[audience])]
        for i in doomed:
            report.layers_removed.append((name, g.layers[i]))
        g.remove(doomed)
        if audience == "auditor":  # the controls bar names layers that are gone now; rebuild it
            g.remove([i for i, lname in g.layers.items() if lname.startswith("Controls")])
            interactive.add_controls(diagram)
            g = Graph(diagram)

        if redact:
            _blank_columns(g, report)
            _fix_wording(g)
        # Resolve every placeholder first: a pill reads its data from the shape around it, and that
        # shape's attributes are about to go.
        empty = [i for i, el in g.els.items() if el.tag in ("object", "UserObject")
                 and el.get("placeholders") == "1" and not _resolve_placeholders(g, el, redact)
                 and el.get("role") is None]
        if empty:
            g.remove(empty)
            report.attributes_stripped += len(empty)
        for el in list(g.root):
            if el.tag in ("object", "UserObject"):
                _resolve_placeholders(g, el, redact)
                if el.get("netdiagrams_provenance") == "1":
                    el.set("label", _provenance_note(el.get("label") or "", audience))
                    el.attrib.pop("tooltip", None)
                for key in list(el.attrib):
                    if key not in keep_attrs:
                        if key == "link":
                            report.links_removed += 1
                        report.attributes_stripped += 1
                        del el.attrib[key]
            if redact:
                for key in ("label", "value"):
                    if el.get(key):
                        text, n = _redact(el.get(key), known)
                        if ANCHOR.search(text):
                            text = ANCHOR.sub(r"\1", text)
                            report.links_removed += 1
                        if n:
                            report.redacted += n
                        el.set(key, text)
                cell = cell_of(el) if el.tag != "mxCell" else None
                if cell is not None and cell.get("value"):
                    text, n = _redact(cell.get("value"), known)
                    report.redacted += n
                    cell.set("value", text)

        if audience != "auditor":
            _scan(diagram, known, report)
    _renumber_sheets(mxfile)
    return report


SHEET_OF = re.compile(r"^(\S+) of (\d+)$")


def _renumber_sheets(mxfile: ET.Element) -> None:
    """The title block's 'SHEET 3 of 13' counts the sheets this copy has."""
    total = len(mxfile.findall("diagram"))
    for el in mxfile.iter():
        for key in ("value", "label"):
            m = SHEET_OF.match(el.get(key) or "")
            if m and m.group(2) != str(total):
                el.set(key, f"{m.group(1)} of {total}")


def _scan(diagram: ET.Element, known: dict[str, str], report: ShareReport) -> None:
    page = (diagram.get("name") or diagram.get("id") or "").split(" — ")[0]
    for el in diagram.iter():
        for where, text in list(_texts(el)) + [(k, v) for k, v in el.attrib.items()
                                                if k not in ("id", "label", "value", "tooltip", "style", "parent",
                                                             "source", "target", "as", "x", "y", "width",
                                                             "height", "vertex", "edge", "visible", "relative",
                                                             "connectable", "locked", "name")]:
            plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
            for secret, kind in known.items():
                if secret in plain and _bounded(secret).search(plain):
                    report.leaks.append((page, f"{kind} {secret}", f"{el.get('id') or el.tag} ({where})"))
            if _ips(plain):
                report.leaks.append((page, "an IP address", f"{el.get('id') or el.tag} ({where})"))
            if PSK_ATTR.search(where) and plain.strip():
                report.leaks.append((page, "a pre-shared key", f"{el.get('id') or el.tag} ({where})"))
    # one line per (secret, element), not per attribute
    seen, unique = set(), []
    for leak in report.leaks:
        key = (leak[0], leak[1], leak[2].split(" (")[0])
        if key not in seen:
            seen.add(key)
            unique.append(leak)
    report.leaks[:] = unique


def write(mxfile: ET.Element, path) -> None:
    paper.fit(mxfile)
    ET.ElementTree(mxfile).write(path, encoding="utf-8", xml_declaration=False)
