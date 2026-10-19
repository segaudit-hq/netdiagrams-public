"""Regenerate src/netdiagrams/data/Corporate-Stencils.xml, the corporate device shapes.

The corporate standard draws devices the core library has no shape for: SD-WAN
hubs, distribution and DC leaf switches, storage and backup, UPSes, console
servers, printers, video recorders, cameras, badge and BMS controllers and
meeting-room systems. Each shape is a NetBox device card in the same form as the
core library's "(asset)" shapes, with the same icons the C01 template uses, so
`draft` and a hand-drawn page look alike.

    python scripts/make_corporate_stencils.py
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawkit import RACK_PILL, sub  # noqa: E402
from make_corporate_template import ICON_FOR_ROLE, label_style  # noqa: E402  (the C01 template's own icons)

OUT = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data" / "Corporate-Stencils.xml"

# title, NetBox role, example manufacturer and model (the C01 sample's own)
SHAPES = [
    ("SD-WAN hub (asset)", "sdwan-hub", "Fortinet", "FortiGate 600F"),
    ("Distribution switch (asset)", "distribution-switch", "Cisco", "Catalyst 9500-24Y4C"),
    ("DC leaf switch (asset)", "dc-leaf", "Cisco", "Nexus 93180YC-FX3"),
    ("Storage array (asset)", "storage", "NetApp", "AFF A250"),
    ("Backup appliance (asset)", "backup-appliance", "Dell", "PowerProtect DD6400"),
    ("UPS (asset)", "ups", "APC", "Smart-UPS SRT 3000"),
    ("Console server (asset)", "console-server", "Opengear", "OM2248-L"),
    ("Printer / MFP (asset)", "printer", "Canon", "imageRUNNER ADVANCE DX C5870i"),
    ("Video recorder (asset)", "nvr", "Axis", "S1296"),
    ("Camera (asset)", "camera", "Axis", "P3268-LV"),
    ("Badge controller (asset)", "door-controller", "Mercury", "LP4502"),
    ("BMS controller (asset)", "bms-controller", "Tridium", "JACE 9000"),
    ("Meeting-room system (asset)", "room-system", "Cisco", "Room Bar"),
]
TOOLTIP = ("Edit Data (Ctrl+M) = NetBox device fields: name, role, device_type, rack, position, serial, "
           "primary_ip4, cf_*")
FIELDS = ("platform", "serial", "asset_tag", "rack", "position", "virtual_chassis", "vc_position", "description",
          "tags", "cf_sw_version", "cf_support_contract", "x_modules", "x_power")


def entry(title: str, role: str, make: str, model: str) -> dict:
    root = ET.Element("root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    card = ET.SubElement(root, "object", {
        "id": "lib-c1", "label": "<b>%name%</b><br>" + sub("%device_type%", 8),
        "placeholders": "1", "tooltip": TOOLTIP, "name": "C##-ROLE-NN", "role": role, "manufacturer": make,
        "device_type": model, "status": "planned", "site": "C##", "location": "‹closet or room›", "face": "front",
        "primary_ip4": "‹a.b.c.d/nn›", "cf_lifecycle": "In support", **{k: "" for k in FIELDS}})
    cell = ET.SubElement(card, "mxCell", style=label_style(ICON_FOR_ROLE[role]), vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x="0", y="0", width="200", height="50", **{"as": "geometry"})
    pill = ET.SubElement(root, "object", {"id": "lib-c2", "label": "%rack% · U%position%", "placeholders": "1"})
    cell = ET.SubElement(pill, "mxCell", style=RACK_PILL, vertex="1", parent="lib-c1")
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
