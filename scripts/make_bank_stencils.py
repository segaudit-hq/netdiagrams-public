"""Regenerate src/netdiagrams/data/Bank-Stencils.xml, the bank device shapes.

The bank standard draws devices the manufacturing library has no shape for:
ATMs, teller cash recyclers, wire workstations, instant-issue card printers,
alarm panels and the core processor's own router, plus the office kit
(printers, cameras, UPSes, video recorders, door controllers, NAS boxes,
console servers, desk phones). Each shape is a NetBox device card in the same
form as the core library's "(asset)" shapes, with the same icons the B01
template uses, so `draft` and a hand-drawn page look alike. A fork of
make_office_stencils.py.

    python scripts/make_bank_stencils.py
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drawkit import RACK_PILL, sub  # noqa: E402
from make_bank_template import label_style  # noqa: E402  (the B01 template's own icons)

OUT = Path(__file__).resolve().parent.parent / "src" / "netdiagrams" / "data" / "Bank-Stencils.xml"

# title, icon, example manufacturer and model
SHAPES = [
    ("Printer / MFP (asset)", "printer", "Canon", "iR-ADV C3826"),
    ("Camera (asset)", "camera", "Axis", "P3265-LVE"),
    ("Video recorder (asset)", "nvr", "Axis", "S3008"),
    ("Door controller (asset)", "door-controller", "Axis", "A1610"),
    ("Storage / NAS (asset)", "storage", "Synology", "RS1221+"),
    ("UPS (asset)", "ups", "APC", "SMT1500RMI2UC"),
    ("Console server (asset)", "console-server", "Opengear", "OM1204"),
    ("Desk phone (asset)", "phone", "Yealink", "T54W"),
    ("ATM (asset)", "atm", "NCR Atleos", "SelfServ 84"),
    ("Teller cash recycler (asset)", "cash-recycler", "Glory", "RBG-200"),
    ("Wire workstation (asset)", "wire-workstation", "Dell", "OptiPlex 7020"),
    ("Card printer (asset)", "card-printer", "Entrust", "Sigma DS3"),
    ("Alarm panel (asset)", "alarm-panel", "Bosch", "B6512"),
    ("Provider-owned router (asset)", "provider-router", "Cisco", "ISR 1111-4P"),
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
        "id": "lib-f1", "label": "<b>%name%</b><br>" + sub("%device_type%", 8),
        "placeholders": "1", "tooltip": TOOLTIP, "name": "F##-ROLE-NN", "role": icon, "manufacturer": make,
        "device_type": model, "status": "planned", "site": "F##", "location": "‹room›", "face": "front",
        "primary_ip4": "‹a.b.c.d/nn›", "cf_lifecycle": "In support", **{k: "" for k in FIELDS}})
    cell = ET.SubElement(card, "mxCell", style=label_style(icon), vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x="0", y="0", width="200", height="50", **{"as": "geometry"})
    pill = ET.SubElement(root, "object", {"id": "lib-f2", "label": "%rack% · U%position%", "placeholders": "1"})
    cell = ET.SubElement(pill, "mxCell", style=RACK_PILL, vertex="1", parent="lib-f1")
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
