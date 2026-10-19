"""The dealership profile: the D01 dealership standard (Kestrel Valley Motors, a fictional franchised dealer).

A dealership is one rooftop with one firewall pair in the middle and its zones
following where customer financial information goes: F&I, sales and the back
office; the card terminals; the service drive, the shop and parts; the
manufacturer's own router; customer Wi-Fi, phones, the building and the lot.
The DMS is hosted by its vendor and reached over a tunnel, so it is drawn
outside. Zones band by department, not by Purdue level.

The template, its sample and the shape library are drawn by
scripts/make_dealer_template.py, scripts/make_dealer_sample.py and
scripts/make_dealer_stencils.py.
"""

from __future__ import annotations

from .profiles import Profile, register

BOOK = "Draw Secure Car Dealership Network Diagrams"
BOOK_URL = "https://netdiagrams.com/books/car-dealership-network-diagrams/"

# Zone tag slug -> tag name, in band order. The sample's tags and netbox-setup use these.
ZONE_NAMES = {
    "zone-internet": "Internet, DMS and lenders", "zone-edge": "Firewall and remote access",
    "zone-fi": "Finance and insurance", "zone-sales": "Sales floor", "zone-office": "Back office",
    "zone-cde": "Card terminals", "zone-service": "Service drive", "zone-shop": "Shop and technicians",
    "zone-parts": "Parts", "zone-oem": "Manufacturer link", "zone-guest": "Customer Wi-Fi", "zone-voice": "Phones",
    "zone-building": "Building and lot", "zone-mgmt": "Network management",
}

register(Profile(
    name="dealership",
    industry="Dealership",
    template="D01-Dealership-Template.drawio",
    site_code="D01",
    site_name="Kestrel Valley Motors",
    sample="sample-dealership.json",
    sample_out="sample-dealership.drawio",
    sample_title="the fictional Kestrel Valley Motors",
    bands=(
        ("OUT", "OUTSIDE · INTERNET & DMS", ("internet", "isp", "wan", "cloud", "saas", "dms", "lender", "remote")),
        ("EDGE", "EDGE · FIREWALL & REMOTE ACCESS", ("edge", "dmz", "vpn", "perimeter")),
        ("DEALS", "SALES, F&I & OFFICE", ("fi", "sales", "office", "cde", "card", "staff")),
        ("FIXED", "SERVICE, SHOP & PARTS", ("service", "shop", "parts", "oem", "body")),
        ("SHARED", "GUESTS, BUILDING & MGMT", ("guest", "voice", "building", "lot", "cameras", "mgmt", "oob")),
    ),
    band_layer="Bands",
    band_word="band",
    blank_zones=("Internet, DMS & lenders", "Firewall & remote access", "Sales, F&I & office",
                 "Service, shop & parts", "Guests, building & management"),
    band_palette={"OUT": "L5", "EDGE": "—", "DEALS": "L4", "FIXED": "L3", "SHARED": "L2–0"},
    words={
        "site": "dealership",
        "zone_examples": "zone-fi, zone-shop, zone-guest",
        "place_nouns": "building, room, bay",
        "location_grouping": "rooms under buildings",
        "group_example": "AP ×8",
    },
    levels=False,
    scopes=("glba", "pci-cde"),  # customer financial information (the Safeguards Rule), card data
    glance_on_groups=False,  # the template counts APs, cameras and terminals by design; that is not "bigger"
    naming=r"^[A-Z]\d{2}-[A-Z0-9]+(-[A-Z0-9]+)*$",
    zone_names=ZONE_NAMES,
    endpoint_roles=("card-terminal", "diag-tool", "key-cabinet"),
    watched_roles=("card-terminal",),
    role_names={"nvr": "NVR", "ups": "UPS", "card-terminal": "Card terminal", "diag-tool": "Diagnostic PC",
                "key-cabinet": "Key cabinet"},
    role_colors={"printer": "4caf50", "camera": "e91e63", "nvr": "e91e63", "key-cabinet": "e91e63",
                 "card-terminal": "ff5722", "diag-tool": "cddc39", "storage": "009688", "ups": "607d8b",
                 "console-server": "607d8b", "router": "673ab7", "phone": "03a9f4"},
    stencil_library="Dealership-Stencils.xml",
    role_shapes={"printer": "Printer (asset)", "camera": "Camera (asset)", "nvr": "Video recorder (asset)",
                 "key-cabinet": "Key cabinet (asset)", "card-terminal": "Card terminal (asset)",
                 "diag-tool": "Diagnostic PC (asset)", "storage": "Storage / NAS (asset)", "ups": "UPS (asset)",
                 "console-server": "Console server (asset)", "router": "Manufacturer router (asset)"},
    book=BOOK,
    book_url=BOOK_URL,
    chapters={
        "overview": (2, "The page the dealer principal actually reads", BOOK_URL),
        "glance": (1, "One rooftop, nine audiences", BOOK_URL),
        "quality": (13, "Diagrams rot. Measure the rot.", BOOK_URL),
        "logical": (4, "Dealership VLANs on paper: the logical page", BOOK_URL),
        "physical": (5, "Cables are data: showroom, service drive and the long run to bay 14", BOOK_URL),
        "physical-registers": (5, "Cables are data: showroom, service drive and the long run to bay 14", BOOK_URL),
        "wireless": (8, "Wireless: the lounge, the service lane and the lot", BOOK_URL),
        "wireless-registers": (8, "Wireless: the lounge, the service lane and the lot", BOOK_URL),
        "flows": (9, "Draw the conversations", BOOK_URL),
        "failover": (7, "The morning the DMS goes dark", BOOK_URL),
        "multisite": (11, "More rooftops: the group office, the body shop and the cloud", BOOK_URL),
        "register": (10, "The flow register: your Safeguards evidence in writing", BOOK_URL),
        "netbox": (12, "NetBox is the source, the drawing is the view", BOOK_URL),
        "riser": (5, "Cables are data: showroom, service drive and the long run to bay 14", BOOK_URL),
        "audit": (14, "Share it without leaking it", BOOK_URL),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Kestrel Valley's flows, not from this dealership's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Kestrel Valley's failover scenarios, not from this dealership's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "Kestrel Valley's rooftops and cloud, not this group",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
    },
    # The overview's promises are D01's (a firewall pair, two lines, the DMS tunnel); a smaller store writes its own.
    # The standards card is marked once, by its ITEM / STANDARD table below; listing its layer too stamped it twice.
    example_cards={"register": ("Flow register", "Zone matrix"),
                   "overview": ("Business promises (Kestrel Valley's; rewrite for your dealership)",)},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
    guide_ids={"physical": ["physical-dc113"]},  # D01's console lines and UPS runtimes: a note, not every store's fact
))
