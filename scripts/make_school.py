"""Write the bundled school template and its sample from one table of facts.

    python scripts/make_school.py            # both files below
    python scripts/make_school.py template   # src/netdiagrams/data/School-Network-Template.drawio
    python scripts/make_school.py sample     # src/netdiagrams/data/sample-harbor-pines-hs.json
    python scripts/make_school.py stencils   # src/netdiagrams/data/School-Stencils.xml

The school, Harbor Pines High School in the fictional Harbor Pines School
District, is described once in scripts/school/site.py; the drawing and the
NetBox export are both made from it, so a build from the export reproduces
the template.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))  # the wireless rows come from the package itself
from school import pages, site  # noqa: E402
from drawkit import Page, mxfile  # noqa: E402

DATA = HERE.parent / "src" / "netdiagrams" / "data"
TEMPLATE = DATA / "School-Network-Template.drawio"
SAMPLE = DATA / "sample-harbor-pines-hs.json"
STENCILS = DATA / "School-Stencils.xml"

# The school's own device shapes for 'netdiagrams stencils --profile education':
# title -> (role slug, placeholder name, model, rack, position, location)
SCHOOL_SHAPES = {
    "Camera (asset)": ("camera", "HS1-CAM-NN", "‹camera model›", "", "", "‹location›"),
    "Door controller (asset)": ("access-control", "HS1-ACS-NN", "‹door panel model›", "", "", "‹location›"),
    "BAS / HVAC controller (asset)": ("bas-controller", "HS1-BAS-NN", "‹controller model›", "", "", "‹location›"),
    "PA, bells & clocks (asset)": ("pa-system", "HS1-PA-NN", "‹PA server model›", "R‹nn›", "‹U›", "‹location›"),
    "NVR / VMS server (asset)": ("nvr", "HS1-NVR-NN", "‹recorder model›", "R‹nn›", "‹U›", "‹location›"),
    "Classroom display (asset)": ("classroom-display", "HS1-DSP-NN", "‹display model›", "", "", "‹room›"),
    "Printer (asset)": ("printer", "HS1-PRN-NN", "‹printer model›", "", "", "‹room›"),
}


def write_template(path: Path = TEMPLATE) -> None:
    root = mxfile(pages.all_pages(), "netdiagrams make_school.py", industry="education", site_code=site.SITE_CODE, site_name=site.SITE_NAME)
    ET.indent(root, space="")
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", "utf-8")
    print(f"wrote {path}: {len(root)} pages")


def write_stencils(path: Path = STENCILS) -> None:
    entries = []
    for title, (role, name, model, rack, position, location) in SCHOOL_SHAPES.items():
        p = Page("lib", title, 300, 100, prefix="s")
        pages.device(p, "1", 0, 0, {"name": name, "role": role, "device_type": model, "status": "planned", "site": "HS1",
                             "rack": rack, "position": position, "location": location}, w=220, h=56)
        model_el = ET.Element("mxGraphModel")
        root = ET.SubElement(model_el, "root")
        root.append(ET.Element("mxCell", {"id": "0"}))
        root.append(ET.Element("mxCell", {"id": "1", "parent": "0"}))
        for el in list(p.root)[1:]:
            root.append(el)
        entries.append({"xml": ET.tostring(model_el, encoding="unicode"), "w": 220, "h": 56, "title": title,
                        "aspect": "fixed"})
    path.write_text("<mxlibrary>" + json.dumps(entries, ensure_ascii=False) + "</mxlibrary>\n", "utf-8")
    print(f"wrote {path}: {len(entries)} shapes")


def write_sample(path: Path = SAMPLE) -> None:
    data = site.export()
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {path}: {len(data['devices'])} devices, {len(data['cables'])} cables, {len(data['vlans'])} VLANs")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "template"):
        write_template()
    if what in ("all", "sample"):
        write_sample()
    if what in ("all", "stencils"):
        write_stencils()
