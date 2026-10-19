"""Industry profiles: one drawing standard per kind of organization.

A profile says which bundled template a build fills, the example site that
template is drawn for, how zones group into bands (Purdue levels for a plant,
trust tiers for a store), which sheets are the template's example and which of
its notes are guides, and which book chapter explains each sheet.

``manufacturing`` (the S01 standard, Plant A) is the default. A site picks
another with the ``profile`` setting (``netdiagrams.json`` or the NetBox
``netdiagrams`` field) or ``--profile``; ``netdiagrams sample --profile NAME``
writes that profile's example.

To add an industry: draw its template, export its example site, and add a
module to this package that ends with ``register(PROFILE)``. It is found and
loaded on start; nothing else in the engine changes.
"""

from __future__ import annotations

import contextlib
import contextvars
from dataclasses import dataclass, field

from .settings import SettingsError


@dataclass(frozen=True)
class Profile:
    name: str                   # settings value: "manufacturing", "retail"
    industry: str               # "Manufacturing", for messages
    template: str               # bundled template file (in netdiagrams/data)
    site_code: str              # the template's own site code: "S01"
    site_name: str              # the template's own site name: "Plant A"
    sample: str                 # the example site's NetBox export (in netdiagrams/data)
    sample_out: str             # default file name for ``netdiagrams sample``
    sample_title: str           # "the fictional Plant A"
    # Bands, top to bottom: (code, label, zone slug prefixes). A zone lands in the first match.
    bands: tuple = ()
    band_layer: str = "Purdue levels"       # the template layer that holds the band strips
    band_word: str = "Purdue level"         # what one band is called in generated text
    blank_zones: tuple = ()                 # example zone names for ``netdiagrams blank``, one per band
    band_palette: dict = field(default_factory=dict)    # band code -> the Purdue band whose colors it wears
    words: dict = field(default_factory=dict)           # the overview sheet's wording (see MFG_WORDS)
    levels: bool = True                     # Purdue level and IEC 62443 SL-T fields apply
    level_labels: dict = field(default_factory=dict)    # Purdue or SL value -> this industry's label for it
    scopes: tuple = ()                      # compliance scopes this industry uses: listed first, the rest kept
    glance_on_groups: bool = True           # counted groups alone add the "Site at a glance" page
    book: str = ""
    book_url: str = ""
    chapters: dict = field(default_factory=dict)        # page id -> (chapter, title, link)
    example_sheets: dict = field(default_factory=dict)  # page id -> (word, why, what fills it)
    example_cards: dict = field(default_factory=dict)   # page id -> card layer names kept as example
    example_table_headers: dict = field(default_factory=dict)
    guide_ids: dict = field(default_factory=dict)       # page id -> element ids moved to the guide layer
    naming: str = ""                        # the naming standard when the site sets none (S01's when empty)
    zone_names: dict = field(default_factory=dict)      # zone tag slug -> tag name, for netbox-setup
    endpoint_roles: tuple = ()              # this industry's end-device roles, on top of the common ones
    watched_roles: tuple = ()               # end devices held to the monitoring and logging checks (a POS server)
    role_names: dict = field(default_factory=dict)      # role slug -> name, on top of the common ones
    role_colors: dict = field(default_factory=dict)     # role slug -> NetBox color, on top of the common ones
    role_shapes: dict = field(default_factory=dict)     # role slug -> stencil title, on top of the common ones
    stencil_library: str = ""               # this industry's own shapes: an mxlibrary file in data/ (or a path)


MFG_BOOK_URL = "https://netdiagrams.com/books/manufacturing-network-diagrams/"

# What the management overview calls things. A profile overrides any key; the rest
# fall back to these (see word()).
MFG_WORDS = {
    "site": "plant",                       # "What NetBox says about this plant"
    "outer_gate": "checks everything going into or out of the plant",
    "inner_gate": "between operations and every production line",
    # band code -> what the overview says when NetBox has no zone in that band
    "missing_band": (("overview-c5", "L4", "No office zone"), ("overview-c8", "L3.5", "No plant DMZ zone"),
                     ("overview-c11", "L3", "No operations zone")),
    "areas_band": "L2–0",                  # the band whose zones get one card each
    "areas_title": "Production lines",
    "area": "line",                        # "3 lines, each its own zone"
    "no_areas_card": "No production-line zone in NetBox yet (tag devices or locations zone-cell01…)",
    "no_areas": "No production-line zone in NetBox yet.",
    "zone_words": (("L4", "office"), ("L3.5", "DMZ"), ("L3", "operations"), ("L2–0", "production and safety")),
    "boundary": "between office and plant",
    "zone_examples": "zone-it-ent, zone-ot-ops, zone-cell01",   # tag examples in tips
    "place_nouns": "building, area, cell",                       # NetBox locations, outer to inner
    "location_grouping": "cells under areas and buildings",      # how nested locations are read
    "no_zone_fix": "Agree each area's zone and Purdue level with the OT owner",   # the data gap's fix
    "safety_band": "L2–0",                 # the band whose safety zones get a card of their own
    "safety_zones": r"zone-(sis|safety)",  # which zones in it count as the safety zones
    "safety_title": "Safety",
    "safety": "in a separate safety zone.",
    "no_safety": "No separate safety zone in NetBox.",
    "group_example": "PLC ×20",            # the counted group the big-site legend shows
}

MANUFACTURING = Profile(
    name="manufacturing",
    industry="Manufacturing",
    template="S01-Network-Architecture-Template.drawio",
    site_code="S01",
    site_name="Plant A",
    sample="sample-plant-a.json",
    sample_out="sample-plant-a.drawio",
    sample_title="the fictional Plant A",
    blank_zones=("Internet & WAN", "IT enterprise", "Industrial DMZ", "Site operations", "Cell / area"),
    bands=(
        ("L5", "INTERNET · WAN", ("internet", "wan", "carrier", "edge")),
        ("L4", "SITE BUSINESS (IT)", ("it", "corp", "ent", "guest", "office")),
        ("L3.5", "INDUSTRIAL DMZ", ("idmz", "dmz")),
        ("L3", "SITE OPERATIONS (OT)", ("ot",)),
        ("L2–0", "CELL/AREA & SAFETY", ("cell", "sis", "safety", "area", "line")),
    ),
    book="Draw Secure Manufacturing Network Diagrams",
    book_url=MFG_BOOK_URL,
    chapters={
        "overview": (2, "The page your plant manager actually reads", MFG_BOOK_URL),
        "glance": (1, "One plant, eleven audiences", MFG_BOOK_URL),
        "quality": (13, "Diagrams rot. Measure the rot.", MFG_BOOK_URL),
        "logical": (4, "Zones on paper: the logical page", MFG_BOOK_URL),
        "physical": (5, "Cables are data, not decoration", MFG_BOOK_URL),
        "physical-registers": (5, "Cables are data, not decoration", MFG_BOOK_URL),
        "riser": (5, "Cables are data, not decoration", MFG_BOOK_URL),
        "hardware": (6, "Optics, faceplates and the SFP drawer", MFG_BOOK_URL),
        "platforms": (7, "Rings, pairs and what happens at 3 a.m.", MFG_BOOK_URL),
        "wireless": (8, "Wireless without hand-waving", MFG_BOOK_URL),
        "wireless-registers": (8, "Wireless without hand-waving", MFG_BOOK_URL),
        "flows": (9, "Draw the conversations", MFG_BOOK_URL),
        "failover": (7, "Rings, pairs and what happens at 3 a.m.", MFG_BOOK_URL),
        "multisite": (11, "More than one site", MFG_BOOK_URL),
        "register": (10, "The flow register (free to read)",
                     "https://netdiagrams.com/free/zones-and-conduits-flow-register/"),
        "netbox": (12, "NetBox is the source, the drawing is the view", MFG_BOOK_URL),
    },
    example_sheets={
        "flows": ("EXAMPLE", "Plant A's flows, not from this site's NetBox",
                  "the flow worksheet (WS-08) once it is read; until then edit by hand or leave the sheet out"),
        "failover": ("EXAMPLE", "Plant A's failover scenarios, not from this site's NetBox",
                     "nothing yet; edit by hand or leave the sheet out (--leave-out failover)"),
        "multisite": ("EXAMPLE", "Plant A, B and C, not this estate",
                      "a multi-site build (planned); until then edit by hand or leave the sheet out"),
        "platforms": ("REFERENCE", "the template's platform catalogue, not this site's inventory", ""),
        "netbox": ("REFERENCE", "how the template maps to NetBox, not this site's data", ""),
    },
    example_cards={"register": ("Flow register", "Zone matrix", "Drawing conventions")},
    example_table_headers={"register": [["ITEM", "STANDARD"]]},
    guide_ids={
        "logical": ["logical-c98", "logical-c206", "logical-c229", "logical-c230", "logical-c256", "logical-c282",
                    "logical-c308", "logical-c324", "logical-c410", "logical-c335", "logical-c336"],
        "physical": ["physical-c81", "physical-c645"],
        "wireless": ["wireless-c63", "wireless-c85", "wireless-c108", "wireless-c109", "wireless-c112",
                     "wireless-c227", "wireless-c389", "wireless-c426", "wireless-c502"],
        "register": ["register-c261", "register-c526"],
        "flows": ["flows-c230"],
    },
)

PROFILES: dict[str, Profile] = {MANUFACTURING.name: MANUFACTURING}
DEFAULT = MANUFACTURING.name

_current: contextvars.ContextVar[Profile] = contextvars.ContextVar("netdiagrams_profile", default=MANUFACTURING)


class ProfileError(SettingsError):
    pass


def register(profile: Profile) -> Profile:
    PROFILES[profile.name] = profile
    return profile


def get(name: str | None) -> Profile:
    """The profile called ``name`` (case and spaces ignored); the default when empty."""
    key = (name or "").strip().lower() or DEFAULT
    if key not in PROFILES:
        raise ProfileError(f"unknown profile '{name}'; known: {', '.join(sorted(PROFILES))}")
    return PROFILES[key]


def current() -> Profile:
    return _current.get()


def word(key: str):
    """The overview wording of the profile in force (manufacturing's where it says nothing)."""
    return current().words.get(key, MFG_WORDS[key])


def endpoint_roles(common: set) -> set:
    """The end-device roles in force: the common ones plus the profile's."""
    return common | set(current().endpoint_roles)


def role_name(slug: str, common: dict) -> str:
    """A device role's display name: the profile's, else the common one, else from the slug."""
    return current().role_names.get(slug) or common.get(slug) or (slug or "other").replace("-", " ").capitalize()


def role_color(slug: str, common: dict) -> str:
    return current().role_colors.get(slug) or common.get(slug) or "9e9e9e"


def palette(code: str) -> str:
    """The color slot of a band: a profile's own band codes wear the Purdue bands' colors."""
    return current().band_palette.get(code, code)


def from_settings(cfg: dict | None) -> Profile:
    return get((cfg or {}).get("profile"))


@contextlib.contextmanager
def use(profile: Profile | str | None):
    """Build with ``profile`` in force, then put the previous one back."""
    token = _current.set(profile if isinstance(profile, Profile) else get(profile))
    try:
        yield _current.get()
    finally:
        _current.reset(token)


# Other industries live in their own modules and register themselves on import: any module in this
# package with a top-level ``register(...)`` or ``NAME = register(...)`` line is loaded, so a new industry needs no edit here.
import importlib as _importlib  # noqa: E402
import pathlib as _pathlib  # noqa: E402
import re as _re  # noqa: E402

REGISTERS = _re.compile(r"^(?:\w+\s*=\s*)?register\(", _re.M)  # register(P) or OFFICE = register(Profile(...))

for _source in sorted(_pathlib.Path(__file__).parent.glob("*.py")):
    if _source.stem != "profiles" and REGISTERS.search(_source.read_text(encoding="utf-8")):
        _importlib.import_module(f".{_source.stem}", __package__)
