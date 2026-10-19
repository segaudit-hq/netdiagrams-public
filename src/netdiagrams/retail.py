"""The retail profile: the R01 store standard (Store 014 of a fictional estate).

A store estate is many small sites built to one design: a firewall that is also
the SD-WAN edge, a 4G backup line, a cabinet switch, a counter switch for the
checkout, and a handful of access points. Its zones band by trust, not by
Purdue level: outside, head office, store operations, the cardholder data
environment, and guest Wi-Fi with the store's devices.
"""

from __future__ import annotations

from . import profiles
from .profiles import register

BOOK_URL = "https://netdiagrams.com/books/retail-network-diagrams/"

WORDS = {
    "site": "store",
    "outer_gate": "checks everything going into or out of the store",
    "inner_gate": "between the back office, the checkout and the shop floor",
    "missing_band": (("overview-c5", "R3", "No back office zone"), ("overview-c8", "R5", "No WAN edge zone"),
                     ("overview-c11", "R3", "No store operations zone")),
    "areas_band": "R1",
    "areas_title": "Shop floor",
    "area": "shop-floor zone",
    "no_areas_card": "No guest or device zone in NetBox yet (tag VLANs or devices zone-guest, zone-iot)",
    "no_areas": "No guest Wi-Fi or device zone in NetBox yet.",
    "zone_words": (("R5", "edge"), ("R4", "head office"), ("R3", "store"), ("R2", "card data"),
                   ("R1", "guest and device")),
    "boundary": "between the zones",
    "zone_examples": "zone-cde, zone-store, zone-guest",
    "place_nouns": "room: back office, checkout, sales floor, stockroom",
    "location_grouping": "rooms under each store's site",
    "no_zone_fix": "Agree each device's zone (card data, store, guest, devices) with the store systems owner",
    "safety_band": "R2",
    "safety_zones": r"zone-(cde|pos|checkout|pci)",
    "safety_title": "Card data",
    "safety": "in the separate card data zone.",
    "no_safety": "No card data zone in NetBox: the checkout is not separated on paper.",
}

RETAIL = profiles.Profile(
    name="retail",
    industry="Retail",
    template="R01-Retail-Store-Template.drawio",
    site_code="ST014",
    site_name="Store 014",
    sample="sample-retail-st014.json",
    sample_out="sample-retail-st014.drawio",
    sample_title="the fictional Store 014",
    bands=(
        ("R5", "OUTSIDE · WAN", ("internet", "wan", "carrier", "edge", "outside")),
        ("R4", "HEAD OFFICE", ("hq", "head-office", "dc", "corp")),
        ("R3", "STORE OPERATIONS", ("store", "mgmt", "staff", "office", "bo")),
        ("R2", "CARDHOLDER DATA (CDE)", ("cde", "pos", "checkout", "pci")),
        ("R1", "GUEST & DEVICES", ("guest", "iot", "device", "cctv", "bldg")),
    ),
    band_layer="Zone bands",
    band_word="zone band",
    blank_zones=("Internet & WAN", "Head office", "Store business", "Cardholder data", "Guest Wi-Fi"),
    band_palette={"R5": "L5", "R4": "L4", "R3": "L3", "R2": "L2–0", "R1": "L3.5"},
    words=WORDS,
    zone_names={"zone-edge": "EDGE · Store WAN edge", "zone-store": "STORE · Store business",
                "zone-mgmt": "MGMT · Network management", "zone-cde": "CDE · Cardholder data environment",
                "zone-guest": "GUEST · Customer Wi-Fi", "zone-iot": "IOT · Store devices"},
    levels=False,
    scopes=("pci-cde", "pci-connected"),   # listed first in netbox-setup's Compliance scope choices
    watched_roles=("pos-server",),          # the POS server is held to the monitoring and logging checks
    naming=r"^[A-Z]{2}\d{3}-[A-Z0-9]+(-[A-Z0-9]+)*$",
    # The checkout and the store's devices are end devices: drops, grouped when a store has more.
    endpoint_roles=("pos-terminal", "pin-pad", "pos-server", "nvr", "signage", "building-controller"),
    role_names={"lte-router": "LTE router", "nvr": "NVR", "pin-pad": "PIN pad", "pos-server": "POS server",
                "pos-terminal": "POS terminal"},
    # Shapes for `netdiagrams stencils --profile retail` and drafts (scripts/make_retail.py writes the library).
    stencil_library="R01-Retail-Stencils.xml",
    role_shapes={"firewall": "Store firewall · SD-WAN edge (asset)", "lte-router": "LTE / 4G router (asset)",
                 "access-switch": "Store switch (asset)", "access-point": "Store access point (asset)",
                 "pos-terminal": "POS register (asset)", "pin-pad": "PIN pad (asset)",
                 "pos-server": "Store POS server (asset)", "workstation": "Back office PC (asset)",
                 "printer": "Printer (asset)", "nvr": "NVR (asset)", "camera": "IP camera (asset)",
                 "signage": "Signage player (asset)",
                 "building-controller": "Refrigeration / building controller (asset)",
                 "sensor": "Sensor / door counter (asset)"},
    role_colors={"lte-router": "607d8b", "pos-terminal": "9c27b0", "pin-pad": "9c27b0", "pos-server": "673ab7",
                 "nvr": "ff9800", "camera": "ff9800", "signage": "ff9800", "building-controller": "ff9800",
                 "sensor": "ff9800", "workstation": "4caf50", "printer": "4caf50"},
    book="Draw Secure Retail Network Diagrams",
    book_url=BOOK_URL,
    chapters={
        "overview": (2, "The page your operations director reads", BOOK_URL),
        "glance": (1, "One estate, many audiences", BOOK_URL),
        "quality": (13, "Diagrams rot: remodels, refreshes and the pop-up store", BOOK_URL),
        "logical": (4, "Zones on paper: the store logical page", BOOK_URL),
        "physical": (5, "The POS network: registers, PIN pads and the back office",
                     "https://netdiagrams.com/free/pos-network-diagram/"),
        "physical-registers": (5, "The POS network: registers, PIN pads and the back office", BOOK_URL),
        "hardware": (6, "The closet under the stairs: small cabinets, PoE and optics", BOOK_URL),
        "wireless": (8, "Guest Wi-Fi without hand-waving", BOOK_URL),
        "wireless-registers": (8, "Guest Wi-Fi without hand-waving", BOOK_URL),
        "flows": (9, "Draw the card's journey", BOOK_URL),
        "failover": (7, "When the line goes down: LTE, pairs and offline mode", BOOK_URL),
        "multisite": (11, "Three stores or three hundred: one standard", BOOK_URL),
        "register": (10, "The flow register: PCI segmentation in writing", BOOK_URL),
        "netbox": (12, "NetBox is the source, the drawing is the view", BOOK_URL),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Store 014's flows, the estate standard, not from this store's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Store 014's failover scenarios, not from this store's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "the sample estate (HQ1, ST014, ST027, ST031), not this estate",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
        "netbox": ("REFERENCE", "how the template maps to NetBox, not this store's data", ""),
    },
    example_cards={"register": ("Flow register", "Zone matrix", "Drawing conventions")},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
    guide_ids={},
)
register(RETAIL)
