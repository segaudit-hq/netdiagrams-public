"""Regenerate src/netdiagrams/data/Municipal-Stencils.xml, the city device shapes.

The local government standard draws devices the manufacturing library has no
shape for: card terminals, the traffic signal system, HVAC controllers, public
PCs, printers, cameras, video recorders, door controllers, UPSes, storage,
console servers and desk phones. Each shape is a NetBox device card in the
same form as the core library's "(asset)" shapes, with the same icons the M01
template uses, so `draft` and a hand-drawn page look alike.

    python scripts/make_city_stencils.py
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawkit import RACK_PILL, sub  # noqa: E402
from make_city_template import label_style  # noqa: E402  (the M01 template's own icons)

OUT = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data" / "Municipal-Stencils.xml"

# title, icon, example manufacturer and model
SHAPES = [
    ("Payment terminal (asset)", "payment-terminal", "Verifone", "P400"),
    ("Traffic signal system (asset)", "signal-system", "Econolite", "Centracs server"),
    ("HVAC controller (asset)", "hvac-controller", "Trane", "Tracer SC+"),
    ("Public PC (asset)", "public-pc", "Dell", "OptiPlex 7020"),
    ("Printer / MFP (asset)", "printer", "Kyocera", "TASKalfa 3554ci"),
    ("Camera (asset)", "camera", "Hanwha Vision", "XNV-8082R"),
    ("Video recorder (asset)", "nvr", "Genetec", "Streamvault SV-1000E"),
    ("Door controller (asset)", "door-controller", "Genetec", "Synergis Cloud Link"),
    ("Storage / NAS (asset)", "storage", "Dell", "PowerVault ME5012"),
    ("UPS (asset)", "ups", "Eaton", "9PX 3000"),
    ("Console server (asset)", "console-server", "Opengear", "OM1204"),
    ("Desk phone (asset)", "phone", "Cisco", "8851"),
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
        "id": "lib-m1", "label": "<b>%name%</b><br>" + sub("%device_type%", 8),
        "placeholders": "1", "tooltip": TOOLTIP, "name": "CH#-ROLE-NN", "role": icon, "manufacturer": make,
        "device_type": model, "status": "planned", "site": "CH#", "location": "‹room›", "face": "front",
        "primary_ip4": "‹a.b.c.d/nn›", "cf_lifecycle": "In support", **{k: "" for k in FIELDS}})
    cell = ET.SubElement(card, "mxCell", style=label_style(icon), vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x="0", y="0", width="200", height="50", **{"as": "geometry"})
    pill = ET.SubElement(root, "object", {"id": "lib-m2", "label": "%rack% · U%position%", "placeholders": "1"})
    cell = ET.SubElement(pill, "mxCell", style=RACK_PILL, vertex="1", parent="lib-m1")
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
