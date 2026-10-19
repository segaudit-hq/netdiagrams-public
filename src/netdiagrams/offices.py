"""The office profile: the O01 office standard (Alder & Finch HQ, a fictional consultancy).

A small or mid-size office is one firewall pair in the middle with every zone
hanging off it: staff, voice, printers, servers, meeting rooms, guests, building
systems and management, two internet lines, a branch or two, home workers on the
VPN and an MSP. Its zones band by who uses them, not by Purdue level: outside,
the edge, staff and services, shared spaces and guests, building and management.

The template, its sample and the shape library are drawn by
scripts/make_office_template.py, scripts/make_office_sample.py and
scripts/make_office_stencils.py.
"""

from __future__ import annotations

from .profiles import Profile, register

BOOK = "Draw Secure Small Office Network Diagrams"
BOOK_URL = "https://netdiagrams.com/books/small-office-network-diagrams/"

# Zone tag slug -> tag name, in band order. The sample's tags and netbox-setup use these.
ZONE_NAMES = {
    "zone-internet": "Internet and providers", "zone-edge": "Firewall and remote access", "zone-staff": "Staff",
    "zone-voice": "Voice", "zone-print": "Printers", "zone-servers": "Servers", "zone-meeting": "Meeting rooms",
    "zone-guest": "Guests", "zone-building": "Building systems", "zone-mgmt": "Network management",
}

register(Profile(
    name="office",
    industry="Office",
    template="O01-Office-Template.drawio",
    site_code="O01",
    site_name="Alder & Finch HQ",
    sample="sample-office.json",
    sample_out="sample-office.drawio",
    sample_title="the fictional Alder & Finch HQ",
    bands=(
        ("OUT", "OUTSIDE · INTERNET & CLOUD", ("internet", "isp", "wan", "cloud", "saas", "remote")),
        ("EDGE", "EDGE · FIREWALL & REMOTE ACCESS", ("edge", "dmz", "vpn", "perimeter")),
        ("STAFF", "STAFF & SERVICES", ("staff", "corp", "it", "voice", "print", "servers", "office", "ent")),
        ("SHARED", "SHARED SPACES & GUEST", ("meeting", "guest", "av", "iot")),
        ("MGMT", "BUILDING & MANAGEMENT", ("building", "cameras", "security", "mgmt", "oob")),
    ),
    band_layer="Bands",
    band_word="band",
    blank_zones=("Internet & cloud", "Firewall & remote access", "Staff", "Meeting rooms & guests",
                 "Building & management"),
    band_palette={"OUT": "L5", "EDGE": "—", "STAFF": "L4", "SHARED": "L2–0", "MGMT": "L3.5"},
    words={
        "site": "office",
        "zone_examples": "zone-staff, zone-guest, zone-building",
        "place_nouns": "floor, closet, meeting room",
        "location_grouping": "closets and rooms under floors",
        "group_example": "AP ×8",
    },
    levels=False,
    scopes=("cui", "hipaa", "sox", "pci-cde"),  # a client's controlled files, a practice's records, audit work, card data
    glance_on_groups=False,  # the template counts APs, printers and cameras by design; that is not "bigger"
    naming=r"^[A-Z]\d{2}-[A-Z0-9]+(-[A-Z0-9]+)*$",
    zone_names=ZONE_NAMES,
    endpoint_roles=("room-system", "door-controller"),
    role_names={"nvr": "NVR", "ups": "UPS", "room-system": "Meeting-room system"},
    role_colors={"printer": "4caf50", "camera": "e91e63", "nvr": "e91e63", "door-controller": "e91e63",
                 "room-system": "9c27b0", "storage": "009688", "ups": "607d8b", "console-server": "607d8b",
                 "phone": "03a9f4"},
    stencil_library="Office-Stencils.xml",
    role_shapes={"printer": "Printer / MFP (asset)", "camera": "Camera (asset)", "nvr": "Video recorder (asset)",
                 "door-controller": "Door controller (asset)", "room-system": "Meeting-room system (asset)",
                 "storage": "Storage / NAS (asset)", "ups": "UPS (asset)",
                 "console-server": "Console server (asset)", "phone": "Desk phone (asset)"},
    book=BOOK,
    book_url=BOOK_URL,
    chapters={
        "overview": (2, "The page the managing partner actually reads", BOOK_URL),
        "glance": (1, "One office, eight audiences", BOOK_URL),
        "quality": (13, "Diagrams rot. Measure the rot.", BOOK_URL),
        "logical": (4, "Office VLANs on paper: the logical page", BOOK_URL),
        "physical": (5, "Cables are data: the comms room, the patch panel and the floor drop", BOOK_URL),
        "physical-registers": (5, "Cables are data: the comms room, the patch panel and the floor drop", BOOK_URL),
        "wireless": (8, "Wireless: staff, guests and the meeting-room screen", BOOK_URL),
        "wireless-registers": (8, "Wireless: staff, guests and the meeting-room screen", BOOK_URL),
        "flows": (9, "Draw the conversations", BOOK_URL),
        "failover": (7, "Two internet lines, a firewall pair and what happens at 3 a.m.", BOOK_URL),
        "multisite": (11, "Branches, home offices and the cloud", BOOK_URL),
        "register": (10, "The flow register: your segmentation in writing", BOOK_URL),
        "netbox": (12, "NetBox is the source, the drawing is the view", BOOK_URL),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Alder & Finch's flows, not from this office's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Alder & Finch's failover scenarios, not from this office's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "Alder & Finch's branches and cloud, not this estate",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
    },
    # The overview's six promises are HQ's (a firewall pair, two lines, two UPSs); a branch must write its own.
    example_cards={"register": ("Flow register", "Zone matrix", "Standards"),
                   "overview": ("Business promises (Alder & Finch's; rewrite for your office)",)},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
    guide_ids={"physical": ["physical-oc120"]},  # HQ's console lines and UPS runtimes: a note, not every office's fact
))
