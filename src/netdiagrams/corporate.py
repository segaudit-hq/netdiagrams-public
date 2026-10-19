"""The corporate profile: the C01 standard (Sable Ridge HQ campus, a fictional professional services firm).

A company network past one firewall: a routed campus core with VRFs, an internal
segmentation firewall pair between them, a data center whose every tier is
gated by that pair, an edge pair for everything outside, two SD-WAN hubs, a
regional office, branches built to typicals, home workers and the cloud. Its
zones band by trust: outside, the edge, users, the data center, shared spaces
and building systems, management.

The template, its sample and the shape library are drawn by
scripts/make_corporate_template.py, scripts/make_corporate_sample.py and
scripts/make_corporate_stencils.py.
"""

from __future__ import annotations

from .profiles import Profile, register

BOOK = "Draw Secure Corporate Network Diagrams"
BOOK_URL = "https://netdiagrams.com/books/corporate-network-diagrams/"

# Zone tag slug -> tag name, in band order. The sample's tags and netbox-setup use these.
ZONE_NAMES = {
    "zone-internet": "Internet and SaaS", "zone-wan": "SD-WAN overlay", "zone-cloud": "Cloud",
    "zone-edge": "Firewalls and remote access", "zone-dmz": "DMZ", "zone-extranet": "Client extranet",
    "zone-corp": "Corporate users", "zone-voice": "Voice", "zone-print": "Printers", "zone-legal": "Legal users",
    "zone-dc-app": "DC applications", "zone-dc-data": "DC data", "zone-dc-infra": "DC infrastructure",
    "zone-dc-backup": "Backup", "zone-dms": "Legal systems",
    "zone-guest": "Guests", "zone-rooms": "Meeting rooms", "zone-building": "Building systems",
    "zone-mgmt": "Network management", "zone-oob": "Out-of-band",
}


def _chapter(n: int, title: str) -> tuple:
    return (n, title, BOOK_URL)


CABLES = "Cables are data: campus fiber, risers and the building-to-building run"
WIRELESS = "Wireless across a campus: identity, guests and the badge reader on the AP"

register(Profile(
    name="corporate",
    industry="Corporate",
    template="C01-Corporate-Template.drawio",
    site_code="C01",
    site_name="Sable Ridge HQ campus",
    sample="sample-corporate.json",
    sample_out="sample-corporate.drawio",
    sample_title="the fictional Sable Ridge HQ campus",
    bands=(
        ("OUT", "OUTSIDE · INTERNET, WAN & CLOUD", ("internet", "wan", "cloud", "saas", "isp", "remote")),
        ("EDGE", "EDGE · FIREWALLS, DMZ & REMOTE ACCESS", ("edge", "dmz", "extranet", "vpn", "perimeter")),
        ("USERS", "USERS · CORPORATE & LEGAL", ("corp", "voice", "print", "legal", "staff", "users")),
        ("DC", "DATA CENTER", ("dc", "dms", "servers", "server")),
        ("SHARED", "SHARED & BUILDING", ("guest", "rooms", "building", "meeting", "iot")),
        ("MGMT", "MANAGEMENT", ("mgmt", "oob")),
    ),
    band_layer="Bands",
    band_word="band",
    blank_zones=("Internet, WAN and cloud", "Firewalls, DMZ and remote access", "Corporate and legal users",
                 "Data center", "Guests and building systems", "Management"),
    band_palette={"OUT": "L5", "EDGE": "—", "USERS": "L4", "DC": "L3", "SHARED": "L3.5", "MGMT": "L2–0"},
    words={
        "site": "campus",
        "zone_examples": "zone-corp, zone-legal, zone-dc-app",
        "place_nouns": "building, floor, closet, data center room",
        "location_grouping": "closets and rooms under floors and buildings",
        "group_example": "AP ×10",
    },
    levels=False,
    scopes=("sox", "pci-cde", "hipaa", "cui"),  # the financial systems first; a client's card or health data next
    glance_on_groups=False,  # the template counts APs, printers, cameras and rooms by design
    naming=r"^C\d{2}-[A-Z0-9]+(-[A-Z0-9]+)*$",
    zone_names=ZONE_NAMES,
    endpoint_roles=("room-system", "door-controller", "bms-controller"),
    role_names={"sdwan-hub": "SD-WAN hub", "dc-leaf": "DC leaf switch", "nvr": "NVR", "ups": "UPS",
                "bms-controller": "BMS controller", "room-system": "Meeting-room system",
                "backup-appliance": "Backup appliance"},
    role_colors={"sdwan-hub": "673ab7", "distribution-switch": "3f51b5", "dc-leaf": "3949ab",
                 "storage": "009688", "backup-appliance": "4caf50", "ups": "607d8b", "console-server": "607d8b",
                 "printer": "4caf50", "nvr": "e91e63", "camera": "e91e63", "door-controller": "e91e63",
                 "bms-controller": "795548", "room-system": "9c27b0"},
    stencil_library="Corporate-Stencils.xml",
    role_shapes={"sdwan-hub": "SD-WAN hub (asset)", "distribution-switch": "Distribution switch (asset)",
                 "dc-leaf": "DC leaf switch (asset)", "storage": "Storage array (asset)",
                 "backup-appliance": "Backup appliance (asset)", "ups": "UPS (asset)",
                 "console-server": "Console server (asset)", "printer": "Printer / MFP (asset)",
                 "nvr": "Video recorder (asset)", "camera": "Camera (asset)",
                 "door-controller": "Badge controller (asset)", "bms-controller": "BMS controller (asset)",
                 "room-system": "Meeting-room system (asset)"},
    book=BOOK,
    book_url=BOOK_URL,
    chapters={
        "overview": _chapter(2, "The page the board actually reads"),
        "glance": _chapter(1, "One company, twelve audiences"),
        "quality": _chapter(14, "Diagrams rot across forty sites. Measure the rot."),
        "logical": _chapter(4, "The logical page at scale: VRFs, summaries and an IP plan you can read"),
        "physical": _chapter(5, CABLES),
        "physical-registers": _chapter(5, CABLES),
        "riser": _chapter(5, CABLES),
        "hardware": _chapter(6, "The data center, or the server room that became one"),
        "wireless": _chapter(8, WIRELESS),
        "wireless-registers": _chapter(8, WIRELESS),
        "flows": _chapter(9, "Draw the conversations: users to apps, and east-west"),
        "failover": _chapter(7, "Redundancy you can draw: core pairs, routing failover and the dark data center"),
        "multisite": _chapter(11, "The WAN: hubs, branches, home workers and the cloud"),
        "register": _chapter(10, "The flow register: your segmentation in writing, with owners"),
        "netbox": _chapter(13, "NetBox is the source: many sites, many authors, one standard"),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Sable Ridge's flows, not from this site's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Sable Ridge's failover scenarios, not from this site's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "Sable Ridge's hubs, branches and cloud, not this estate",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
    },
    example_cards={"register": ("Flow register", "Zone matrix", "Standards")},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
))
