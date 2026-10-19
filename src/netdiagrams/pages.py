"""Which pages a site gets: leave out pages (or groups of pages) a site doesn't need.

A page is left out by default when NetBox has nothing for it at the site (no
access points, controllers or radios: no wireless pages). On top of that, a
page list can add or remove pages, first for every site (``--leave-out`` and
``--keep-in``) and then per site, from the NetBox site's ``netdiagrams_pages``
custom field.

A page list is names separated by commas or spaces; ``-name`` leaves a page
out and ``+name`` keeps it in even when NetBox has nothing for it. A name is
a group, a page id or a sheet number:

    -wireless              no wireless pages (3d and its register sheet)
    -reference, +3c        no reference pages, but keep the platform catalog
    -failover -multisite   only one site, no failover page
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .model import _get
from .wireless import WIRELESS_ROLES

SITE_FIELD = "netdiagrams_pages"

GROUPS = {
    "overview": ["overview"],
    "glance": ["glance"],
    "quality": ["quality"],
    "logical": ["logical"],
    "physical": ["physical", "physical-registers"],
    "riser": ["riser"],
    "audit": ["audit"],
    "hardware": ["hardware"],
    "platforms": ["platforms"],
    "wireless": ["wireless", "wireless-registers"],
    "flows": ["flows"],
    "failover": ["failover"],
    "multisite": ["multisite"],
    "register": ["register"],
    "netbox": ["netbox"],
    # Groups of pages
    "security": ["flows", "register"],
    "reference": ["platforms", "netbox"],
    "registers": ["physical-registers", "wireless-registers"],
    # Sheets added during the build, by number
    "1b": ["glance"],
    "1c": ["quality"],
    "3r": ["physical-registers"],
    "3e": ["riser"],
    "3f": ["audit"],
    "3dr": ["wireless-registers"],
}

class PageError(ValueError):
    """A page list names a page or group that doesn't exist."""




def _ids(name: str, diagrams: list[ET.Element]) -> list[str]:
    """The page ids a name stands for: a group, a page id or a sheet number such as 3d."""
    name = name.strip().lower()
    if name in GROUPS:
        return GROUPS[name]
    ids = [d.get("id") for d in diagrams]
    if name in ids:
        return [name]
    sheets = {(d.get("name") or "").split(" ", 1)[0].lower(): d.get("id") for d in diagrams}
    if name in sheets:
        return [sheets[name]]
    raise PageError(f"Unknown page '{name}'. Use a sheet number (3d), a page id or one of: "
                     + ", ".join(sorted(GROUPS)))


def parse(spec: str, diagrams: list[ET.Element]) -> list[tuple[bool, str, list[str]]]:
    """A page list as (keep, name, page ids) in the order given."""
    out = []
    for token in re.split(r"[,\s]+", spec or ""):
        if not token:
            continue
        keep = not token.startswith("-")
        name = token.lstrip("+-")
        out.append((keep, name, _ids(name, diagrams)))
    return out


def auto_skip(export: dict) -> dict[str, str]:
    """Pages NetBox has nothing for at this site, with the reason."""
    roles = {_get(d, "role", "slug") for d in export.get("devices", [])}
    if not roles & WIRELESS_ROLES and not export.get("wireless_links"):
        return {page: "no access points, wireless controllers or radios in NetBox"
                for page in GROUPS["wireless"]}
    return {}


def site_spec(export: dict) -> str:
    return str((export.get("site") or {}).get("custom_fields", {}).get(SITE_FIELD) or "")


def skipped(template: ET.Element, export: dict, spec: str = "") -> dict[str, str]:
    """Page ids to leave out, each with why: NetBox has nothing for it, --leave-out, or the site's own list."""
    diagrams = template.findall("diagram")
    skip = auto_skip(export)
    for source, text in (("--leave-out", spec), (f"the site's {SITE_FIELD} field", site_spec(export))):
        for keep, name, ids in parse(text, diagrams):
            for page in ids:
                if keep:
                    skip.pop(page, None)
                else:
                    skip[page] = f"left out by {source} ({name})"
    return skip


def remove(template: ET.Element, skip: dict[str, str]) -> list[tuple[str, str]]:
    """Take the skipped pages out of the file; return (page name, reason) for the drift report."""
    out = []
    for diagram in list(template.findall("diagram")):
        page = diagram.get("id") or ""
        page = page if page in skip else re.sub(r"(-registers)-\d+$", r"\1", page)  # a continued register sheet
        if page in skip:
            out.append((diagram.get("name") or diagram.get("id"), skip[page]))
            template.remove(diagram)
    return out
