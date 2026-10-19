"""The warehouse standard: W01 · Riverside DC, a fictional distribution center.

The template is the S01 standard redrawn for a warehouse by
scripts/make_warehouse.py: the same sheets, layers and NetBox fields, with
inbound conveyor, sortation and AMRs, and dock and yard in the cell/area
zones, WES/WCS and handhelds in operations, and carriers and the cloud WMS
ending in the integration DMZ. Material handling automation is drawn on the
same Purdue levels a plant uses, so the bands and fields are the plant's.
"""

from __future__ import annotations

from .profiles import MANUFACTURING, Profile, register

BOOK = "Draw Secure Warehouse Network Diagrams"
BOOK_URL = "https://netdiagrams.com/books/warehouse-network-diagrams/"

WAREHOUSE = Profile(
    name="warehouse",
    industry="Warehousing and logistics",
    template="W01-Warehouse-Network-Template.drawio",
    site_code="W01",
    site_name="Riverside DC",
    sample="sample-warehouse-w01.json",
    sample_out="sample-warehouse-w01.drawio",
    sample_title="the fictional Riverside DC",
    blank_zones=("Internet, WAN & carriers", "Site business", "Integration DMZ", "Warehouse operations",
                 "Automation area"),
    bands=(
        ("L5", "INTERNET · WAN", ("internet", "wan", "carrier", "edge")),
        ("L4", "SITE BUSINESS (IT)", ("it", "corp", "ent", "guest", "office")),
        ("L3.5", "INTEGRATION DMZ", ("idmz", "dmz")),
        ("L3", "WAREHOUSE OPERATIONS (OT)", ("ot", "wh", "mobile")),
        ("L2–0", "AUTOMATION & SAFETY", ("cell", "sis", "safety", "area", "line", "mhe", "conveyor", "sorter",
                                         "amr", "dock")),
    ),
    words={
        "site": "warehouse",
        "outer_gate": "checks everything going onto or off the warehouse floor",
        "inner_gate": "between operations and every automation area",
        "missing_band": (("overview-c5", "L4", "No office zone"), ("overview-c8", "L3.5", "No warehouse DMZ zone"),
                         ("overview-c11", "L3", "No operations zone")),
        "areas_band": "L2–0",
        "areas_title": "Automation areas",
        "area": "automation area",
        "no_areas_card": "No conveyor, sorter or dock zone in NetBox yet (tag devices or locations zone-cell01…)",
        "no_areas": "No conveyor, sorter or dock zone in NetBox yet.",
        "zone_words": (("L4", "office"), ("L3.5", "DMZ"), ("L3", "operations"), ("L2–0", "automation and safety")),
        "boundary": "between office and floor",
        "zone_examples": "zone-it-ent, zone-ot-ops, zone-cell02",
        "no_zone_fix": "Agree each automation area's zone and Purdue level with the controls or MHE owner",
        "safety_title": "Safety",
        "safety": "in a separate safety zone.",
        "no_safety": "No separate safety zone in NetBox.",
        "place_nouns": "building, area, aisle or dock door",
        "location_grouping": "aisles and dock doors under areas and buildings",
    },
    book=BOOK,
    book_url=BOOK_URL,
    chapters={
        "overview": (2, "The page your general manager reads", BOOK_URL),
        "glance": (1, "One building, many audiences", BOOK_URL),
        "quality": (13, "Diagrams rot. Measure the rot.", BOOK_URL),
        "logical": (4, "Zones on paper: the logical page", BOOK_URL),
        "physical": (5, "Cables are data: long aisles and conveyor cabinets", BOOK_URL),
        "physical-registers": (5, "Cables are data: long aisles and conveyor cabinets", BOOK_URL),
        "hardware": (6, "Optics and the long building", BOOK_URL),
        "platforms": (7, "Pairs, rings and peak season at 3 a.m.", BOOK_URL),
        "wireless": (8, "Warehouse Wi-Fi without hand-waving (free to read)",
                     "https://netdiagrams.com/free/warehouse-wifi-design/"),
        "wireless-registers": (8, "Warehouse Wi-Fi without hand-waving (free to read)",
                               "https://netdiagrams.com/free/warehouse-wifi-design/"),
        "flows": (9, "Draw the conversations", BOOK_URL),
        "failover": (7, "Pairs, rings and peak season at 3 a.m.", BOOK_URL),
        "multisite": (11, "More than one site", BOOK_URL),
        "register": (10, "The flow register", BOOK_URL),
        "netbox": (12, "NetBox is the source, the drawing is the view", BOOK_URL),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Riverside DC's flows, not from this site's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Riverside DC's failover scenarios, not from this site's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "Riverside DC and its sister sites, not this estate",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
        "platforms": ("REFERENCE", "the template's platform catalogue, not this site's inventory", ""),
        "netbox": ("REFERENCE", "how the template maps to NetBox, not this site's data", ""),
    },
    # The warehouse template keeps the S01 element ids, so its example cards and guides are the same shapes.
    example_cards=MANUFACTURING.example_cards,
    example_table_headers=MANUFACTURING.example_table_headers,
    guide_ids=MANUFACTURING.guide_ids,
    # The safety system here is the conveyor and sorter safety PLC, not a process SIS.
    role_names={"sis-controller": "Safety PLC", "sis-switch": "Safety switch", "handheld": "Handheld scanner",
                "vehicle-mount-terminal": "Vehicle-mount terminal", "amr": "AMR / AGV",
                "print-and-apply": "Print-and-apply", "dock-door-controller": "Dock door controller"},
    # Floor devices a warehouse NetBox often holds; drawn as counted groups, not one card each.
    endpoint_roles=("handheld", "vehicle-mount-terminal", "amr", "print-and-apply", "dock-door-controller"),
    # The warehouse's own shapes (scripts/make_warehouse_stencils.py writes the library).
    stencil_library="warehouse-stencils.xml",
    # netbox-setup's choice sets in warehouse words (the values stay) and the scopes a warehouse meets first.
    level_labels={"L3.5": "Level 3.5 · Integration DMZ", "L3": "Level 3 · Warehouse operations (WCS)",
                  "L2": "Level 2 · Automation area supervisory", "L1": "Level 1 · Automation controls",
                  "L0": "Level 0 · Conveyor sensors and drives"},
    scopes=("safety", "sox", "gxp", "cui", "pci-connected", "pci-cde"),
    role_shapes={"handheld": "Handheld scanner (asset)", "vehicle-mount-terminal": "Vehicle-mount terminal (asset)",
                 "amr": "AMR / AGV (asset)", "print-and-apply": "Print-and-apply (asset)",
                 "camera": "Dock / yard camera (asset)", "dock-door-controller": "Dock door controller (asset)"},
)

register(WAREHOUSE)
