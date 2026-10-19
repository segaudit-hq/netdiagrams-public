"""Paper size: print each sheet full size on the smallest ISO landscape sheet that holds it.

draw.io prints 100 units to the inch, so a 2400-unit page needs A1. Text of 9
units and up stays readable at that size; an A3 or A4 print is a reduced copy.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

# Landscape (width, height) in draw.io units, smallest first.
SIZES = (("A2", 2339, 1654), ("A1", 3311, 2339), ("A0", 4681, 3311))


def content_size(model: ET.Element) -> tuple[float, float]:
    """The page's declared size, grown to the farthest top-level shape."""
    w, h = float(model.get("pageWidth", 0)), float(model.get("pageHeight", 0))
    root = model.find("root")
    if root is None:
        return w, h
    layers = {c.get("id") for c in root if c.get("parent") == "0"}
    for el in root:
        cell = el if el.tag == "mxCell" else el.find("mxCell")
        if cell is None or cell.get("vertex") != "1" or cell.get("parent") not in layers:
            continue
        geo = cell.find("mxGeometry")
        if geo is None:
            continue
        w = max(w, float(geo.get("x", 0)) + float(geo.get("width", 0)))
        h = max(h, float(geo.get("y", 0)) + float(geo.get("height", 0)))
    return w, h


def paper_for(w: float, h: float) -> tuple[str, int, int]:
    for size in SIZES:
        if w <= size[1] and h <= size[2]:
            return size
    return SIZES[-1]


def fit(mxfile: ET.Element) -> dict[str, str]:
    """Set every sheet's page to its paper size; returns {sheet name: paper}."""
    out = {}
    for diagram in mxfile.findall("diagram"):
        model = diagram.find("mxGraphModel")
        if model is None:
            continue
        name, pw, ph = paper_for(*content_size(model))
        model.set("pageWidth", str(pw))
        model.set("pageHeight", str(ph))
        model.set("pageScale", "1")
        out[diagram.get("name") or diagram.get("id") or ""] = name
    return out
