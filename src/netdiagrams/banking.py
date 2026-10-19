"""The bank profile: the B01 bank standard (Ninebark Community Bank, a fictional community bank).

A community bank or credit union is one firewall pair in the middle with the
teller line, the platform and back office, the wire room and the card room each
in a zone of its own, ATMs and lobby guests apart, and the core processor's own
router in the rack behind the firewall. Its zones band by trust: outside, the
edge and the processor links, banking, services, customer-facing, security and
management.

The template, its sample and the shape library are drawn by
scripts/make_bank_template.py, scripts/make_bank_sample.py and
scripts/make_bank_stencils.py; the facts are in scripts/bank_template/site.py.
"""

from __future__ import annotations

from .profiles import Profile, register

BOOK = "Draw Secure Bank and Credit Union Network Diagrams"
BOOK_URL = "https://netdiagrams.com/books/bank-network-diagrams/"

# Zone tag slug -> tag name, in band order (the titles of scripts/bank_template/site.py's ZONES).
ZONE_NAMES = {
    "zone-internet": "Internet and outside parties", "zone-partner": "Core and card processor links",
    "zone-edge": "Firewall and remote access", "zone-teller": "Teller line", "zone-staff": "Platform and back office",
    "zone-wire": "Wire room", "zone-card": "Card issuing", "zone-servers": "Servers", "zone-voice": "Voice",
    "zone-atm": "ATMs", "zone-guest": "Lobby guests", "zone-security": "Physical security",
    "zone-mgmt": "Network management",
}

register(Profile(
    name="bank",
    industry="Bank",
    template="B01-Bank-Template.drawio",
    site_code="B01",
    site_name="Ninebark main office",
    sample="sample-bank.json",
    sample_out="sample-bank.drawio",
    sample_title="the fictional Ninebark Community Bank",
    bands=(  # as scripts/bank_template/site.py's BANDS
        ("OUT", "OUTSIDE · INTERNET & PARTIES", ("internet", "isp", "wan", "cloud", "saas", "remote")),
        ("EDGE", "EDGE · FIREWALL & PROCESSOR LINKS", ("edge", "partner", "core-link", "dmz", "vpn", "perimeter")),
        ("BANK", "BANKING · TELLER, STAFF, WIRE & CARD", ("teller", "staff", "platform", "wire", "card", "corp")),
        ("SERV", "SERVICES · SERVERS & VOICE", ("servers", "voice", "print")),
        ("CUST", "CUSTOMER-FACING · ATM & GUEST", ("atm", "itm", "guest", "lobby")),
        ("MGMT", "SECURITY & MANAGEMENT", ("security", "alarm", "cameras", "building", "mgmt", "oob")),
    ),
    band_layer="Bands",
    band_word="band",
    blank_zones=("Internet & parties", "Firewall & processors", "Teller, wire & card", "Servers & voice",
                 "ATMs & guests", "Security & mgmt"),
    band_palette={"OUT": "L5", "EDGE": "—", "BANK": "L4", "SERV": "L3.5", "CUST": "L2–0",
                  "MGMT": "L3.5"},
    words={
        "site": "bank",
        "zone_examples": "zone-teller, zone-wire, zone-atm",
        "place_nouns": "floor, closet, room",
        "location_grouping": "closets and rooms under floors",
        "group_example": "ATM ×2",
    },
    levels=False,
    scopes=("glba", "pci-cde", "sox"),  # customer information, card data, a holding company's financial reporting
    glance_on_groups=False,  # the template counts APs, cameras and ATMs by design; that is not "bigger"
    naming=r"^[A-Z]\d{2}-[A-Z0-9]+(-[A-Z0-9]+)*$",
    zone_names=ZONE_NAMES,
    endpoint_roles=("atm", "cash-recycler", "wire-workstation", "card-printer", "alarm-panel", "door-controller"),
    role_names={"nvr": "NVR", "ups": "UPS", "atm": "ATM", "provider-router": "Provider router",
                "cash-recycler": "Cash recycler", "wire-workstation": "Wire workstation",
                "card-printer": "Card printer", "alarm-panel": "Alarm panel"},
    role_colors={"printer": "4caf50", "camera": "e91e63", "nvr": "e91e63", "door-controller": "e91e63",
                 "alarm-panel": "e91e63", "storage": "009688", "ups": "607d8b", "console-server": "607d8b",
                 "phone": "03a9f4", "atm": "a21caf", "cash-recycler": "2563eb", "wire-workstation": "b91c1c",
                 "card-printer": "c2410c", "provider-router": "7c3aed"},
    stencil_library="Bank-Stencils.xml",
    role_shapes={"printer": "Printer / MFP (asset)", "camera": "Camera (asset)", "nvr": "Video recorder (asset)",
                 "door-controller": "Door controller (asset)", "storage": "Storage / NAS (asset)",
                 "ups": "UPS (asset)", "console-server": "Console server (asset)", "phone": "Desk phone (asset)",
                 "atm": "ATM (asset)", "cash-recycler": "Teller cash recycler (asset)",
                 "wire-workstation": "Wire workstation (asset)", "card-printer": "Card printer (asset)",
                 "alarm-panel": "Alarm panel (asset)", "provider-router": "Provider-owned router (asset)"},
    book=BOOK,
    book_url=BOOK_URL,
    chapters={
        "overview": (2, "The page the board actually reads", BOOK_URL),
        "glance": (1, "One institution, nine audiences", BOOK_URL),
        "quality": (13, "Diagrams rot. Measure the rot.", BOOK_URL),
        "logical": (4, "Branch VLANs on paper: the logical page", BOOK_URL),
        "physical": (5, "Cables are data: the branch closet and the teller line", BOOK_URL),
        "physical-registers": (5, "Cables are data: the branch closet and the teller line", BOOK_URL),
        "hardware": (6, "ATMs, vaults and the boxes the alarm company owns", BOOK_URL),
        "wireless": (8, "Wireless: staff, guests and the lobby", BOOK_URL),
        "wireless-registers": (8, "Wireless: staff, guests and the lobby", BOOK_URL),
        "flows": (9, "Draw the conversations", BOOK_URL),
        "failover": (7, "Two carriers, a core circuit and what happens at 3 a.m.", BOOK_URL),
        "multisite": (11, "Branches, the core processor and the cloud", BOOK_URL),
        "register": (10, "The flow register: your segmentation in writing", BOOK_URL),
        "netbox": (12, "NetBox is the source, the drawing is the view", BOOK_URL),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Ninebark's flows, not from this bank's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Ninebark's failover scenarios, not from this bank's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "Ninebark's branches, processors and cloud, not this estate",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
    },
    # The overview's six promises are the main office's (a firewall pair, two lines, two UPSs); a branch writes its own.
    example_cards={"register": ("Flow register", "Zone matrix", "Standards"),
                   "overview": ("Business promises (Ninebark's; rewrite for your bank)",)},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
    guide_ids={"physical": ["physical-fc133"]},  # the main office's console lines and UPS runtimes: a note
))
