"""The municipal profile: the M01 local government standard (City of Halvern, a fictional city).

A city, town or county runs police, the public and city hall on the same
fiber: one firewall pair in the middle of a civic center, police in their own
walled-off zone with a state-owned router in a caged rack, public Wi-Fi in the
lobby and council chamber, payment counters, building systems, traffic signals
on city fiber, and the water plant, county dispatch and the state network as
boundaries. Its zones band by who they serve: outside, the edge, the public,
city hall, public safety, and facilities, field and management.

The template, its sample and the shape library are drawn by
scripts/make_city_template.py, scripts/make_city_sample.py and
scripts/make_city_stencils.py, from scripts/city_template/site.py.
"""

from __future__ import annotations

from .profiles import Profile, register

BOOK = "Draw Secure Local Government Network Diagrams"
BOOK_URL = "https://netdiagrams.com/books/local-government-network-diagrams/"

# Zone tag slug -> tag name, in band order. The sample's tags and netbox-setup use these.
ZONE_NAMES = {
    "zone-internet": "Internet and providers", "zone-partner": "State, county and vendors",
    "zone-water": "Water plant (boundary)", "zone-edge": "Firewall and remote access", "zone-public": "Public Wi-Fi",
    "zone-staff": "City staff", "zone-voice": "Voice", "zone-pay": "Payment counters", "zone-servers": "City servers",
    "zone-cjis": "Police (CJIS)", "zone-building": "Building systems", "zone-field": "Traffic signals and field",
    "zone-mgmt": "Network management",
}

register(Profile(
    name="municipal",
    industry="Local government",
    template="M01-Municipal-Template.drawio",
    site_code="CH1",
    site_name="Halvern Civic Center",
    sample="sample-municipal.json",
    sample_out="sample-municipal.drawio",
    sample_title="the fictional Halvern Civic Center",
    bands=(
        ("OUT", "OUTSIDE · INTERNET, STATE & COUNTY", ("internet", "isp", "wan", "cloud", "saas", "remote-users",
                                                       "partner", "state", "county", "water", "boundary")),
        ("EDGE", "EDGE · FIREWALL & REMOTE ACCESS", ("edge", "dmz", "vpn", "perimeter")),
        ("PUBLIC", "PUBLIC · RESIDENTS & VISITORS", ("public", "guest", "patron", "library")),
        ("CITY", "CITY HALL · STAFF & SERVICES", ("staff", "corp", "it", "voice", "pay", "servers", "office")),
        ("SAFETY", "PUBLIC SAFETY · POLICE (CJIS)", ("cjis", "police", "pd", "safety", "fire")),
        ("FAC", "FACILITIES, FIELD & MANAGEMENT", ("building", "cameras", "security", "field", "signals", "mgmt",
                                                   "oob")),
    ),
    band_layer="Bands",
    band_word="band",
    blank_zones=("Internet, state & county", "Firewall & remote access", "Public Wi-Fi", "City Hall staff & services",
                 "Police (CJIS)", "Facilities, field & management"),
    band_palette={"OUT": "L5", "EDGE": "—", "PUBLIC": "L3.5", "CITY": "L4", "SAFETY": "L2–0", "FAC": "L3"},
    words={
        "site": "city",
        "zone_examples": "zone-staff, zone-cjis, zone-public",
        "place_nouns": "building, floor, closet, room",
        "location_grouping": "closets and rooms under floors and buildings",
        "no_zone_fix": "Agree each building's, wing's and closet's zone with the department that runs it",
        "safety_zones": r"(?!)",          # never matches: police are their own band, not a safety-instrumented zone
        "group_example": "AP ×4",
    },
    levels=False,
    scopes=("cjis", "pci-cde"),  # criminal justice information, card data at the counters
    glance_on_groups=False,  # the template counts APs, printers and cameras by design; that is not "bigger"
    naming=r"^(CH|LB|PW|FS|PD)\d-[A-Z0-9]+(-[A-Z0-9]+)*$",
    zone_names=ZONE_NAMES,
    endpoint_roles=("door-controller", "payment-terminal", "hvac-controller", "public-pc"),
    role_names={"nvr": "NVR", "ups": "UPS", "payment-terminal": "Payment terminal", "signal-system": "Signal system",
                "hvac-controller": "HVAC controller", "public-pc": "Public PC"},
    role_colors={"printer": "4caf50", "camera": "e91e63", "nvr": "e91e63", "door-controller": "e91e63",
                 "hvac-controller": "e91e63", "payment-terminal": "f44336", "signal-system": "ffc107",
                 "public-pc": "ff9800", "storage": "009688", "ups": "607d8b", "console-server": "607d8b",
                 "router": "795548", "phone": "03a9f4"},
    stencil_library="Municipal-Stencils.xml",
    role_shapes={"printer": "Printer / MFP (asset)", "camera": "Camera (asset)", "nvr": "Video recorder (asset)",
                 "door-controller": "Door controller (asset)", "hvac-controller": "HVAC controller (asset)",
                 "payment-terminal": "Payment terminal (asset)", "signal-system": "Traffic signal system (asset)",
                 "public-pc": "Public PC (asset)", "storage": "Storage / NAS (asset)", "ups": "UPS (asset)",
                 "console-server": "Console server (asset)", "phone": "Desk phone (asset)"},
    book=BOOK,
    book_url=BOOK_URL,
    chapters={
        "overview": (2, "The page the city manager reads", BOOK_URL),
        "glance": (1, "One city, nine audiences", BOOK_URL),
        "quality": (13, "Diagrams rot. Measure the rot.", BOOK_URL),
        "logical": (4, "Department VLANs on paper", BOOK_URL),
        "physical": (5, "Cables are data: City Hall, the station and the fiber between them", BOOK_URL),
        "physical-registers": (5, "Cables are data: City Hall, the station and the fiber between them", BOOK_URL),
        "wireless": (8, "Wireless: staff, patrons, parks and the patrol car", BOOK_URL),
        "wireless-registers": (8, "Wireless: staff, patrons, parks and the patrol car", BOOK_URL),
        "flows": (9, "Draw the conversations", BOOK_URL),
        "failover": (7, "Two internet lines, a firewall pair and the storm", BOOK_URL),
        "multisite": (11, "Many buildings, one city", BOOK_URL),
        "register": (10, "The flow register: your segmentation in writing", BOOK_URL),
        "netbox": (12, "NetBox is the source, the drawing is the view", BOOK_URL),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Halvern's flows, not from this site's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Halvern's failover scenarios, not from this site's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "the City of Halvern's buildings and links, not this city",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
    },
    # The overview's promises are the civic center's (a firewall pair, a caged police rack, a generator).
    example_cards={"register": ("Flow register", "Zone matrix", "Standards"),
                   "overview": ("Promises to the city (Halvern's; rewrite for your city)",)},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
    guide_ids={"physical": ["physical-m120"]},  # the civic center's console lines and UPS runtimes: a note
))
