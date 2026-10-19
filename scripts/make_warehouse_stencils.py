"""Write src/netdiagrams/data/warehouse-stencils.xml: the warehouse's own device shapes.

Each shape is a copy of a common shape (the access point card for devices with
NetBox fields, the PLC tile for controllers) with its own icon, colors and
example values, so it sits on a page next to the common shapes without looking
borrowed. Rerun after changing a shape here:

    python3 scripts/make_warehouse_stencils.py
"""

from __future__ import annotations

import base64
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from netdiagrams import stencils  # noqa: E402

OUT = ROOT / "src" / "netdiagrams" / "data" / "warehouse-stencils.xml"


def svg(fill: str, stroke: str, body: str) -> str:
    """A 32x32 icon on a rounded tile, in the common shapes' style."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">'
            f'<rect x="0" y="0" width="32" height="32" rx="8" fill="{fill}"/>'
            + body.replace("S", stroke) + "</svg>")


def line(d: str, width: float = 1.7) -> str:
    return (f'<path d="{d}" fill="none" stroke="S" stroke-width="{width}" '
            'stroke-linecap="round" stroke-linejoin="round"/>')


# Zone colors from the template legend: OT ops green for floor devices, Cell purple for automation.
GREEN = ("#E6F4EF", "#059669")
PURPLE = ("#EFE9FB", "#7C3AED")
SLATE = ("#E7E9EC", "#475569")

ICONS = {
    "handheld": line("M11 6h10a1.5 1.5 0 0 1 1.5 1.5v17a1.5 1.5 0 0 1-1.5 1.5H11a1.5 1.5 0 0 1-1.5-1.5v-17A1.5 1.5 0 0 1 11 6z")
                + line("M12.5 9.5h7v6h-7z") + line("M13 19h1M16 19h1M19 19h1M13 22h1M16 22h1M19 22h1", 1.9),
    "vmt": line("M7 8h18v12H7z") + line("M10 11h12v6H10z", 1.3) + line("M16 20v4M11 25h10"),
    "amr": line("M7 13h18a1.5 1.5 0 0 1 1.5 1.5v5a1.5 1.5 0 0 1-1.5 1.5H7a1.5 1.5 0 0 1-1.5-1.5v-5A1.5 1.5 0 0 1 7 13z")
           + '<circle cx="11" cy="23.5" r="2" fill="none" stroke="S" stroke-width="1.6"/>'
           + '<circle cx="21" cy="23.5" r="2" fill="none" stroke="S" stroke-width="1.6"/>'
           + line("M12 9.5a6 6 0 0 1 8 0M14.2 11.3a3 3 0 0 1 3.6 0", 1.4),
    "conveyor": line("M5.5 13h21") + line("M5.5 21h21")
                + "".join(f'<circle cx="{x}" cy="17" r="2.4" fill="none" stroke="S" stroke-width="1.5"/>'
                          for x in (9, 16, 23))
                + line("M12 9.5l4-3 4 3", 1.4),
    "sorter": line("M5.5 16h9") + line("M14.5 16l6-6.5h5M14.5 16h11M14.5 16l6 6.5h5")
              + line("M23.5 7.5l2 2-2 2M23.5 14l2 2-2 2M23.5 20.5l2 2-2 2", 1.4),
    "print": line("M10 6.5h12v6H10zM7 12.5h18v9H7zM10 18h12v7.5H10z") + line("M12.5 21h7M12.5 23.5h5", 1.3),
    "camera": line("M6 11.5h14v9H6z") + line("M20 14l6-3v10l-6-3") + line("M10 20.5v4M7.5 24.5h5"),
    "dock": line("M6 25V9.5L16 6l10 3.5V25") + line("M9.5 25V13h13v12") + line("M9.5 16.5h13M9.5 20h13", 1.3),
}

# title, base shape, icon, colors, role slug, example name, example device type, location, description
SHAPES = [
    ("Handheld scanner (asset)", "Access point (asset)", "handheld", GREEN, "handheld",
     "W##-HH-001", "‹handheld model›", "‹area›", "Handheld or wearable scanner · RF-HANDHELD"),
    ("Vehicle-mount terminal (asset)", "Access point (asset)", "vmt", GREEN, "vehicle-mount-terminal",
     "W##-VMT-01", "‹VMT model›", "‹area›", "Forklift or reach-truck terminal · RF-HANDHELD"),
    ("AMR / AGV (asset)", "Access point (asset)", "amr", PURPLE, "amr",
     "W##-AMR-01", "‹robot model›", "‹automation area›", "Mobile robot · fleet manager in operations"),
    ("Print-and-apply (asset)", "Access point (asset)", "print", PURPLE, "print-and-apply",
     "W##-PA-01", "‹printer model›", "‹conveyor section›", "Label print-and-apply on the outbound conveyor"),
    ("Dock / yard camera (asset)", "Access point (asset)", "camera", SLATE, "camera",
     "W##-CAM-D01", "‹camera model›", "‹dock door›", "Dock or yard camera · building systems"),
    ("Dock door controller (asset)", "Access point (asset)", "dock", SLATE, "dock-door-controller",
     "W##-DD-01", "‹controller model›", "‹dock door›", "Door, leveler and restraint controller"),
    ("Conveyor PLC", "PLC", "conveyor", PURPLE, None, "Conveyor PLC · L1", None, None, None),
    ("Sorter PLC", "PLC", "sorter", PURPLE, None, "Sorter PLC · L1", None, None, None),
]


def make(title, base, icon, colors, role, name, device_type, location, description, common) -> dict:
    entry = common[base]
    model = stencils._decode(entry["xml"])
    root = model.find("root")
    for el in list(root):
        if el.get("id") not in ("0", "1", "lib-c1"):
            root.remove(el)   # the rack pill: robots, scanners and door controllers aren't racked
    card = root.find("*[@id='lib-c1']")
    cell = card if card.tag == "mxCell" else card.find("mxCell")
    image = base64.b64encode(svg(*colors, ICONS[icon]).encode()).decode()
    cell.set("style", re.sub(r"image=data:image/svg\+xml,[^;]+", "image=data:image/svg+xml," + image,
                             cell.get("style")))
    if card.tag == "mxCell":
        card.set("value", f"<b>{name}</b>")
    else:
        card.set("name", name)
        card.set("role", role)
        card.set("manufacturer", "")
        card.set("device_type", device_type)
        card.set("platform", "")
        card.set("site", "W##")
        card.set("location", location)
        card.set("rack", "")
        card.set("position", "")
        card.set("description", description)
        card.set("link", "https://netbox.example.com/dcim/devices/?name=" + name.replace("#", "%23"))
    return {"xml": ET.tostring(model, encoding="unicode"), "w": entry["w"], "h": entry["h"],
            "aspect": entry.get("aspect", "fixed"), "title": title}


def main() -> None:
    common = {e["title"]: e for e in stencils._entries(stencils.LIBRARY_FILE)}
    items = [make(*shape, common) for shape in SHAPES]
    OUT.write_text("<mxlibrary>" + json.dumps(items, ensure_ascii=False) + "</mxlibrary>\n", "utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(items)} shapes.")


if __name__ == "__main__":
    main()
