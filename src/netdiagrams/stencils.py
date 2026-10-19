"""Load the draw.io stencil library and turn its shapes into templates."""

from __future__ import annotations

import base64
import copy
import json
import re
import urllib.parse
import zlib
from functools import lru_cache
from importlib import resources
from pathlib import Path
import xml.etree.ElementTree as ET

from . import profiles

LIBRARY_FILE = "Network-Docs-Stencils.xml"

# NetBox device role slug -> stencil title. Unknown roles fall back to DEFAULT_SHAPE.
ROLE_SHAPES = {
    "firewall": "Firewall (asset)",
    "core-switch": "Core / L3 switch (asset)",
    "access-switch": "Access switch (asset)",
    "oob-switch": "Access switch (asset)",
    "industrial-switch": "IE switch (asset)",
    "sis-switch": "SIS switch (asset)",
    "router": "Router / SD-WAN (asset)",
    "sdwan-edge": "Router / SD-WAN (asset)",
    "server": "Server (asset)",
    "hypervisor": "Hypervisor / HCI (asset)",
    "wireless-controller": "Wireless controller (asset)",
    "access-point": "Access point (asset)",
    "workgroup-bridge": "Industrial AP / WGB (asset)",
    "ptp-radio": "PtP radio (asset)",
    "hmi": "HMI",
    "plc": "PLC",
    "sis-controller": "PLC",
    "io": "I/O · drives",
}
DEFAULT_SHAPE = "Server (asset)"
# A role's stencil title drawn with another entry's shape when a profile's own library lacks it.
ALIASES = {"PtP radio (asset)": "Industrial AP / WGB (asset)"}

# Label used when a stencil has no NetBox placeholders of its own (HMI, PLC, I/O).
PLACEHOLDER_LABEL = (
    '<b>%name%</b><br><span style="font-size:9px;color:#64748B">%device_type%</span>'
)


def _decode(xml: str) -> ET.Element:
    if not xml.lstrip().startswith("<"):
        raw = zlib.decompress(base64.b64decode(xml), -15).decode("utf-8")
        xml = urllib.parse.unquote(raw)
    return ET.fromstring(xml)


def inflate(mxfile: ET.Element) -> ET.Element:
    """Unpack the pages draw.io saved compressed (File ▸ Properties ▸ Compressed), in place."""
    for d in mxfile.findall("diagram"):
        if d.find("mxGraphModel") is None and (d.text or "").strip():
            d.append(_decode(d.text.strip()))
            d.text = None
    return mxfile


# Red is kept for denied flows and faults; firewalls are drawn in slate (design critique, round 2).
SLATE_SHAPES = {"Firewall (asset)"}
SLATE = {"#DC2626": "#334155", "#EF4444": "#475569", "#B91C1C": "#1E293B", "#7F1D1D": "#1E293B",
         "#FEF2F2": "#F1F5F9", "#FEE2E2": "#E2E8F0", "#FECACA": "#CBD5E1", "#FCA5A5": "#CBD5E1",
         "#F3B3B3": "#CBD5E1", "#FAE1E1": "#E2E8F0"}


def _to_slate(text: str) -> str:
    for red, slate in SLATE.items():
        text = re.sub(re.escape(red), slate, text, flags=re.I)
    return text


def _slate(root: ET.Element) -> None:
    """Recolor a shape, including the SVG icons embedded in its style, from red to slate."""
    def icon(m):
        try:
            svg = base64.b64decode(m.group(2)).decode()
        except ValueError:
            return m.group(0)
        return m.group(1) + base64.b64encode(_to_slate(svg).encode()).decode()

    for el in root.iter():
        for key in ("style", "value", "label"):
            text = el.get(key)
            if text:
                el.set(key, re.sub(r"(image=data:image/svg\+xml,)([A-Za-z0-9+/=]+)", icon, _to_slate(text)))


BAND_SHAPE = "Purdue band "   # the plant's band shapes; other industries get theirs generated
PURDUE_SHAPE_CODES = {"L2–0": "L2–L0"}   # band code -> the code in the plant shape's title


@lru_cache(maxsize=8)
def _entries(name: str) -> tuple:
    """The raw entries of an mxlibrary file: bundled in data/ by name, or any path."""
    path = Path(name)
    text = path.read_text("utf-8") if path.is_absolute() or path.exists() else \
        resources.files("netdiagrams").joinpath("data", name).read_text("utf-8")
    start, end = text.index("["), text.rindex("]") + 1
    return tuple(json.loads(text[start:end]))


def _band_entries(profile: profiles.Profile) -> list[dict]:
    """One band shape per profile band, cut from the plant band that lends it its colors."""
    plant = {e["title"]: e for e in _entries(LIBRARY_FILE) if e["title"].startswith(BAND_SHAPE)}
    out = []
    for code, name, _ in profile.bands:
        slot = profiles.palette(code)
        base = plant.get(BAND_SHAPE + PURDUE_SHAPE_CODES.get(slot, slot)) or plant.get(BAND_SHAPE + "L4")
        if base is None:
            continue
        model = _decode(base["xml"])
        for el in model.iter("mxCell"):
            value = el.get("value") or ""
            if re.fullmatch(r"<b>[^<]+</b>", value):
                el.set("value", f"<b>{code}</b>")
            elif value and "text;" in (el.get("style") or ""):
                el.set("value", name)
        out.append({**base, "title": f"{profile.band_word} {code} · {name}",
                    "xml": ET.tostring(model, encoding="unicode")})
    return out


def entries() -> list[dict]:
    """The library for the profile in force: the common shapes, the profile's own, and its bands."""
    profile = profiles.current()
    own = profile is profiles.MANUFACTURING or profile.bands == profiles.MANUFACTURING.bands
    out = [e for e in _entries(LIBRARY_FILE) if own or not e["title"].startswith(BAND_SHAPE)]
    if not own:
        out += _band_entries(profile)
    if profile.stencil_library:
        extra = {e["title"]: e for e in _entries(profile.stencil_library)}
        out = [e for e in out if e["title"] not in extra] + list(extra.values())
    return out


@lru_cache(maxsize=8)
def _library(profile_name: str) -> dict[str, dict]:
    shapes = {}
    for entry in entries():
        root = _decode(entry["xml"]).find("root")
        if entry["title"] in SLATE_SHAPES:
            _slate(root)
        shapes[entry["title"]] = {"root": root, "w": entry.get("w", 120), "h": entry.get("h", 40)}
    for alias, source in ALIASES.items():   # titles the roles use that the library file spells differently
        if alias not in shapes and source in shapes:
            shapes[alias] = shapes[source]
    return shapes


def library() -> dict[str, dict]:
    """Return {title: {"root": <mxGraphModel root>, "w": int, "h": int}} for the profile in force."""
    return _library(profiles.current().name)


def write_library(out: Path) -> int:
    """Save the profile's library as a draw.io mxlibrary file; returns how many shapes."""
    items = entries()
    if items == list(_entries(LIBRARY_FILE)):  # the plant's own library, byte for byte
        out.write_text(resources.files("netdiagrams").joinpath("data", LIBRARY_FILE).read_text("utf-8"), "utf-8")
    else:
        out.write_text("<mxlibrary>" + json.dumps(items, ensure_ascii=False) + "</mxlibrary>", "utf-8")
    return len(items)


def shape_for_role(role_slug: str | None) -> str:
    return profiles.current().role_shapes.get(role_slug or "") or ROLE_SHAPES.get(role_slug or "", DEFAULT_SHAPE)


def device_cells(title: str, cell_id: str, parent: str, x: float, y: float,
                 attrs: dict[str, str]) -> tuple[list[ET.Element], float, float]:
    """Copy a device stencil, fill its NetBox fields, and place it at (x, y).

    Returns the new elements plus the card's width and height. The card gets
    ``cell_id`` so links can attach to it; child cells (the rack pill) get
    ``cell_id`` plus a suffix.
    """
    shape = library()[title]
    items = [el for el in shape["root"] if el.get("id") not in ("0", "1")]
    ids = {el.get("id"): f"{cell_id}-{i}" for i, el in enumerate(items)}
    ids[items[0].get("id")] = cell_id
    out = []
    for index, el in enumerate(items):
        el = copy.deepcopy(el)
        cell = el if el.tag == "mxCell" else el.find("mxCell")
        keys = re.findall(r"%(\w+)%", el.get("label") or "") if index and el.get("placeholders") == "1" else []
        if keys and not any(attrs.get(k) for k in keys):
            continue  # a rack pill on a device with no rack would print " · U": leave it out
        new_id = ids[el.get("id")]
        cell.set("parent", ids.get(cell.get("parent"), parent))
        if index == 0:
            if el.tag == "mxCell":
                # Plain-cell stencil: wrap the card in an <object> so it carries NetBox data.
                cell.attrib.pop("value", None)
                cell.attrib.pop("id", None)
                el = ET.Element("object", {"label": PLACEHOLDER_LABEL, "placeholders": "1"})
                el.append(cell)
            # Drop the stencil's example field values so only NetBox facts remain.
            for key in [k for k in el.attrib if k not in ("label", "placeholders", "tooltip")]:
                del el.attrib[key]
            for key, value in attrs.items():
                el.set(key, value)
            if attrs.get("link"):
                el.set("linkTarget", "_blank")
            geo = cell.find("mxGeometry")
            geo.set("x", f"{x:g}")
            geo.set("y", f"{y:g}")
        el.set("id", new_id)
        out.append(el)
    return out, shape["w"], shape["h"]


def copy_shape(title: str, prefix: str, parent: str, x: float, y: float,
               replace: dict[str, str] | None = None) -> list[ET.Element]:
    """Copy any stencil as-is at (x, y), swapping cell values listed in ``replace``."""
    replace = replace or {}
    items = [el for el in library()[title]["root"] if el.get("id") not in ("0", "1")]
    ids = {el.get("id"): f"{prefix}-{i}" for i, el in enumerate(items)}
    out = []
    for el in items:
        el = copy.deepcopy(el)
        cell = el if el.tag == "mxCell" else el.find("mxCell")
        old_parent = cell.get("parent")
        cell.set("parent", ids.get(old_parent, parent))
        el.set("id", ids[el.get("id")])
        key = "value" if el.tag == "mxCell" else "label"
        if el.get(key) in replace:
            el.set(key, replace[el.get(key)])
        if old_parent == "1":
            geo = cell.find("mxGeometry")
            if geo is not None:
                geo.set("x", f"{float(geo.get('x', 0)) + x:g}")
                geo.set("y", f"{float(geo.get('y', 0)) + y:g}")
        out.append(el)
    return out
