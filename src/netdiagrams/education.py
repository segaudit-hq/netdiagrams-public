"""The school standard: HS1 · Harbor Pines High School, a fictional district high school.

The template is drawn by scripts/make_school.py from one table of facts
(scripts/school/site.py), with the S01 standard's sheets, layers, NetBox
fields and table headers. Zones group into trust tiers instead of Purdue
levels: outside and the district WAN; staff and the front office; students
and guests; school services and building systems; management.
"""

from __future__ import annotations

from .profiles import Profile, register

BOOK = "Draw Secure School Network Diagrams"
BOOK_URL = "https://netdiagrams.com/books/school-network-diagrams/"

EDUCATION = Profile(
    name="education",
    industry="Education",
    template="School-Network-Template.drawio",
    site_code="HS1",
    site_name="Harbor Pines High School",
    sample="sample-harbor-pines-hs.json",
    sample_out="sample-harbor-pines-hs.drawio",
    sample_title="the fictional Harbor Pines High School",
    bands=(
        ("OUT", "INTERNET · DISTRICT WAN", ("internet", "wan", "edge", "district", "carrier")),
        ("T1", "STAFF · FRONT OFFICE", ("staff", "admin", "office", "it")),
        ("T2", "STUDENTS · GUESTS", ("student", "guest", "byod", "lab")),
        ("T3", "SERVICES · BUILDING", ("svc", "bldg", "building", "security", "iot", "server")),
        ("M", "MANAGEMENT", ("mgmt", "oob")),
    ),
    band_layer="Trust tiers",
    band_word="trust tier",
    blank_zones=("Internet & district WAN", "Staff & front office", "Students & guests", "Services & building",
                 "Management"),
    band_palette={"OUT": "L5", "T1": "L4", "T2": "L3.5", "T3": "L3", "M": "L2–0"},
    words={
        "site": "school",
        "zone_words": (("T1", "staff and office"), ("T2", "student and guest"), ("T3", "services and building"),
                       ("M", "management")),
        "zone_examples": "zone-staff, zone-student, zone-bldg",
        "no_zone_fix": "Agree each building's, wing's and closet's zone with whoever runs it",
        "safety_zones": r"(?!)",          # never matches: schools have no safety-instrumented zone
        "place_nouns": "building, wing, closet, room",
        "location_grouping": "closets and rooms under wings and buildings",
        "group_example": "AP ×4",          # the counted group the big-site legend shows
    },
    levels=False,
    scopes=("ferpa", "pci-cde", "pci-connected", "hipaa", "cui"),
    naming=r"^(DO|(HS|MS|ES|TY)\d)-[A-Z0-9]+(-[A-Z0-9]+)*$",
    endpoint_roles=("nvr", "pa-system", "bas-controller", "access-control", "hypervisor"),
    role_names={"nvr": "NVR", "pa-system": "PA system", "bas-controller": "BAS controller",
                "access-control": "Access control"},
    stencil_library="School-Stencils.xml",
    role_shapes={"camera": "Camera (asset)", "access-control": "Door controller (asset)",
                 "bas-controller": "BAS / HVAC controller (asset)", "pa-system": "PA, bells & clocks (asset)",
                 "nvr": "NVR / VMS server (asset)", "classroom-display": "Classroom display (asset)",
                 "printer": "Printer (asset)"},
    role_colors={"nvr": "9c27b0", "pa-system": "ff9800", "bas-controller": "795548", "access-control": "673ab7"},
    book=BOOK,
    book_url=BOOK_URL,
    chapters={
        "overview": (2, "The page your superintendent actually reads", BOOK_URL),
        "glance": (1, "One district, a dozen audiences", BOOK_URL),
        "quality": (13, "Diagrams rot over the summer", BOOK_URL),
        "logical": (4, "Zones on paper: the logical page", BOOK_URL),
        "physical": (5, "Cables are data: MDF, IDFs and the portables", BOOK_URL),
        "physical-registers": (5, "Cables are data: MDF, IDFs and the portables", BOOK_URL),
        "hardware": (6, "Closets, PoE and optics", BOOK_URL),
        "wireless": (8, "Wireless for two thousand Chromebooks", BOOK_URL),
        "wireless-registers": (8, "Wireless for two thousand Chromebooks", BOOK_URL),
        "flows": (9, "Draw the conversations", BOOK_URL),
        "failover": (7, "Pairs, stacks and state-testing day", BOOK_URL),
        "multisite": (11, "The district WAN", BOOK_URL),
        "register": (10, "The flow register", BOOK_URL),
        "netbox": (12, "NetBox is the source, the drawing is the view", BOOK_URL),
    },
    example_sheets={
        # The overview is written by hand for Harbor Pines; nothing fills it from NetBox yet.
        "overview": ("EXAMPLE", "Harbor Pines High School's overview, not from this site's NetBox",
                     "edit by hand for this school, or leave the sheet out"),
        "flows": ("EXAMPLE", "Harbor Pines High School's flows, not from this site's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Harbor Pines High School's failover scenarios, not from this site's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "the Harbor Pines district, not this district",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
        "netbox": ("REFERENCE", "how the template maps to NetBox, not this site's data", ""),
    },
    example_cards={"register": ("Flow register", "Zone matrix", "Drawing conventions")},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
    guide_ids={},  # the school template's own ids; its guide layer starts empty
)

register(EDUCATION)
