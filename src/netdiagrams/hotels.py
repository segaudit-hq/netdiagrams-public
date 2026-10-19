"""The hotel profile: the H01 hotel standard (Alder Bay Hotel and Conference Center, a fictional hotel).

A full-service hotel is one firewall pair with three owners around it: the owner,
the management company that runs IT, and the brand whose router and cloud PMS
sit in the rack. Card terminals, guests living on the network overnight, a
ballroom of events, the TVs, locks and thermostats in every room and a plant
room of building systems all meet there. Its zones band by who they serve:
outside (internet, brand and vendors), the edge, payments and operations,
guests and rooms, building and safety.

The template, its sample and the shape library are drawn by
scripts/make_hotel_template.py, scripts/make_hotel_sample.py and
scripts/make_hotel_stencils.py.
"""

from __future__ import annotations

from .profiles import Profile, register

BOOK = "Draw Secure Hotel Network Diagrams"
BOOK_URL = "https://netdiagrams.com/books/hotel-network-diagrams/"

# Zone tag slug -> tag name, in band order. The sample's tags and netbox-setup use these.
ZONE_NAMES = {
    "zone-internet": "Internet and providers", "zone-brand": "Brand and management company",
    "zone-edge": "Firewall pair", "zone-payments": "Payments", "zone-ops": "Hotel operations",
    "zone-servers": "Property servers and interfaces", "zone-voice": "Voice", "zone-guest": "Guests",
    "zone-events": "Meetings and events", "zone-roomtech": "Guest room technology",
    "zone-building": "Building systems", "zone-safety": "Safety and security", "zone-mgmt": "Network management",
}

register(Profile(
    name="hotel",
    industry="Hotel",
    template="H01-Hotel-Template.drawio",
    site_code="H01",
    site_name="Alder Bay Hotel and Conference Center",
    sample="sample-hotel.json",
    sample_out="sample-hotel.drawio",
    sample_title="the fictional Alder Bay Hotel and Conference Center",
    bands=(
        ("OUT", "OUTSIDE · INTERNET, BRAND & VENDORS", ("internet", "isp", "wan", "cloud", "brand", "vendor", "remote")),
        ("EDGE", "EDGE · FIREWALL PAIR", ("edge", "dmz", "vpn", "perimeter")),
        ("BUSINESS", "PAYMENTS & HOTEL OPERATIONS", ("payments", "pay", "pos", "cde", "ops", "staff", "office",
                                                     "servers", "interfaces", "voice", "corp")),
        ("GUEST", "GUESTS, EVENTS & ROOMS", ("guest", "hsia", "events", "event", "meeting", "roomtech", "room",
                                             "iptv")),
        ("BUILDING", "BUILDING, SAFETY & MANAGEMENT", ("building", "bms", "plant", "safety", "security", "cameras",
                                                       "mgmt", "oob")),
    ),
    band_layer="Bands",
    band_word="band",
    blank_zones=("Internet, brand & vendors", "Firewall pair", "Payments & operations", "Guests, events & rooms",
                 "Building, safety & management"),
    band_palette={"OUT": "L5", "EDGE": "—", "BUSINESS": "L4", "GUEST": "L2–0", "BUILDING": "L3.5"},
    words={
        "site": "hotel",
        "zone_examples": "zone-payments, zone-guest, zone-building",
        "place_nouns": "floor, closet, room",
        "location_grouping": "closets and rooms under floors",
        "group_example": "AP ×16",
    },
    levels=False,
    scopes=("pci-cde", "pci-connected"),   # the card terminals and POS, and the systems that reach them
    watched_roles=("pos-server",),          # the POS server is held to the monitoring and logging checks
    glance_on_groups=False,  # the template counts APs, terminals and cameras by design; that is not "bigger"
    naming=r"^[A-Z]\d{2}-[A-Z0-9]+(-[A-Z0-9]+)*$",
    zone_names=ZONE_NAMES,
    # Hotel end devices: drops, folded into a counted card when a property has more.
    endpoint_roles=("payment-terminal", "pos-terminal", "pos-server", "key-encoder", "lock-gateway", "room-controls",
                    "tv-headend", "call-server", "bms-server", "building-controller", "door-controller",
                    "safety-gateway", "elevator-monitor"),
    role_names={"nvr": "NVR", "ups": "UPS", "pos-server": "POS server", "pos-terminal": "POS workstation",
                "payment-terminal": "Card terminal", "guest-gateway": "Guest gateway", "call-server": "Call server",
                "tv-headend": "TV head-end", "lock-gateway": "Lock gateway", "key-encoder": "Key encoder",
                "room-controls": "Room-controls gateway", "bms-server": "BMS supervisor",
                "building-controller": "Building controller", "safety-gateway": "Safety-button gateway",
                "elevator-monitor": "Elevator monitor"},
    role_colors={"payment-terminal": "f44336", "pos-terminal": "f44336", "pos-server": "c62828",
                 "guest-gateway": "ff9800", "router": "673ab7", "call-server": "03a9f4", "tv-headend": "9c27b0",
                 "lock-gateway": "9c27b0", "key-encoder": "9c27b0", "room-controls": "9c27b0",
                 "bms-server": "4caf50", "building-controller": "4caf50", "elevator-monitor": "4caf50",
                 "camera": "e91e63", "nvr": "e91e63", "door-controller": "e91e63", "safety-gateway": "e91e63",
                 "printer": "2196f3", "ups": "607d8b", "console-server": "607d8b"},
    stencil_library="Hotel-Stencils.xml",
    role_shapes={"payment-terminal": "Card terminal (asset)", "pos-terminal": "POS workstation (asset)",
                 "pos-server": "POS server (asset)", "guest-gateway": "Guest gateway (asset)",
                 "router": "Brand router (asset)", "call-server": "Call server (asset)",
                 "tv-headend": "TV head-end (asset)", "lock-gateway": "Lock gateway (asset)",
                 "key-encoder": "Key encoder (asset)", "room-controls": "Room-controls gateway (asset)",
                 "bms-server": "BMS supervisor (asset)", "building-controller": "Building controller (asset)",
                 "elevator-monitor": "Elevator monitor (asset)", "safety-gateway": "Safety-button gateway (asset)",
                 "door-controller": "Door controller (asset)", "camera": "Camera (asset)",
                 "nvr": "Video recorder (asset)", "printer": "Printer (asset)", "ups": "UPS (asset)",
                 "console-server": "Console server (asset)"},
    book=BOOK,
    book_url=BOOK_URL,
    chapters={
        "overview": (2, "The page the general manager reads", BOOK_URL),
        "glance": (1, "One hotel, fourteen audiences", BOOK_URL),
        "quality": (13, "Diagrams rot: renovations, rebrands and the PIP", BOOK_URL),
        "logical": (4, "Zones on paper: the hotel logical page", BOOK_URL),
        "physical": (5, "Cables are data: a closet on every floor", BOOK_URL),
        "physical-registers": (5, "Cables are data: a closet on every floor", BOOK_URL),
        "riser": (5, "Cables are data: a closet on every floor", BOOK_URL),
        "audit": (6, "The plant room: building systems on the hotel network", BOOK_URL),
        "wireless": (8, "Wireless: guest rooms, ballrooms and the room TV", BOOK_URL),
        "wireless-registers": (8, "Wireless: guest rooms, ballrooms and the room TV", BOOK_URL),
        "flows": (9, "Draw the conversations: from swipe to folio", BOOK_URL),
        "failover": (7, "3 a.m. at the front desk: failover and the night audit", BOOK_URL),
        "multisite": (11, "One property or a portfolio: owners, brands and management companies", BOOK_URL),
        "register": (10, "The flow register: segmentation in writing", BOOK_URL),
        "netbox": (12, "NetBox is the source, the drawing is the view", BOOK_URL),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Alder Bay's flows, not from this property's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Alder Bay's failover scenarios, not from this property's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "Alder Bay's portfolio, brand and management company, not this estate",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
    },
    # The overview's promises are H01's (a firewall pair, two lines, two UPSs); a sister property writes its own.
    example_cards={"register": ("Flow register", "Zone matrix", "Standards"),
                   "overview": ("Business promises (Alder Bay's; rewrite for your hotel)",)},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
    guide_ids={},
))
