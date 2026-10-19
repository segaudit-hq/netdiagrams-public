"""Regenerate src/netdiagrams/data/Dealership-Stencils.xml, the dealership device shapes.

The dealership standard draws devices the manufacturing library has no shape
for: card terminals, diagnostic PCs, the key cabinet, the manufacturer's
router, printers, cameras, UPSes, video recorders, NAS boxes and console
servers. Each shape is a NetBox device card in the same form as the core
library's "(asset)" shapes, with the same icons the D01 template uses, so
`draft` and a hand-drawn page look alike.

    python scripts/make_dealer_stencils.py
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawkit import RACK_PILL, sub  # noqa: E402
from make_dealer_template import label_style  # noqa: E402  (the D01 template's own icons)

OUT = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data" / "Dealership-Stencils.xml"

# title, icon, example manufacturer and model
SHAPES = [
    ("Card terminal (asset)", "card-terminal", "Generic", "Card terminal (P2PE)"),
    ("Diagnostic PC (asset)", "diag-tool", "Generic", "Diagnostic PC (manufacturer spec)"),
    ("Key cabinet (asset)", "key-cabinet", "Generic", "Key cabinet controller"),
    ("Manufacturer router (asset)", "router", "Cisco", "ISR1111-4P"),
    ("Printer (asset)", "printer", "HP", "LaserJet M610"),
    ("Camera (asset)", "camera", "Axis", "P3268-LVE"),
    ("Video recorder (asset)", "nvr", "Axis", "S3016"),
    ("Storage / NAS (asset)", "storage", "Synology", "RS2423RP+"),
    ("UPS (asset)", "ups", "APC", "Smart-UPS SRT 3000"),
    ("Console server (asset)", "console-server", "Opengear", "OM1204-4E-L"),
]
TOOLTIP = ("Edit Data (Ctrl+M) = NetBox device fields: name, role, device_type, rack, position, serial, "
           "primary_ip4, cf_*")
FIELDS = ("platform", "serial", "asset_tag", "rack", "position", "virtual_chassis", "vc_position", "description",
          "tags", "cf_sw_version", "cf_support_contract", "x_modules", "x_power")


def entry(title: str, icon: str, make: str, model: str) -> dict:
    root = ET.Element("root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    card = ET.SubElement(root, "object", {
        "id": "lib-d1", "label": "<b>%name%</b><br>" + sub("%device_type%", 8),
        "placeholders": "1", "tooltip": TOOLTIP, "name": "D##-ROLE-NN", "role": icon, "manufacturer": make,
        "device_type": model, "status": "planned", "site": "D##", "location": "‹room›", "face": "front",
        "primary_ip4": "‹a.b.c.d/nn›", "cf_lifecycle": "In support", **{k: "" for k in FIELDS}})
    cell = ET.SubElement(card, "mxCell", style=label_style(icon), vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x="0", y="0", width="200", height="50", **{"as": "geometry"})
    pill = ET.SubElement(root, "object", {"id": "lib-d2", "label": "%rack% · U%position%", "placeholders": "1"})
    cell = ET.SubElement(pill, "mxCell", style=RACK_PILL, vertex="1", parent="lib-d1")
    ET.SubElement(cell, "mxGeometry", x="124", y="19", width="70", height="13", **{"as": "geometry"})
    model_xml = ET.Element("mxGraphModel")
    model_xml.append(root)
    return {"xml": ET.tostring(model_xml, "unicode"), "w": 200, "h": 50, "aspect": "fixed", "title": title}


def main() -> None:
    data = [entry(*shape) for shape in SHAPES]
    OUT.write_text("<mxlibrary>" + json.dumps(data, ensure_ascii=False, indent=0) + "</mxlibrary>\n", "utf-8")
    print(f"wrote {OUT}: {len(data)} shapes")


if __name__ == "__main__":
    main()
