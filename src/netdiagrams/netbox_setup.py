"""Import files that give NetBox the structure the template expects (zones, roles, custom fields).

``netdiagrams netbox-setup`` writes CSV files you import in NetBox (each list has an
Import button), in the numbered order:

1. custom field choice sets: the dropdown lists (Purdue level and IEC 62443 security level for a plant);
2. custom fields: ``purdue_level`` and ``security_level_target`` on devices and
   locations, plus the asset fields the template's cards show;
3. zone tags, one per zone the template draws (``zone-it-ent``, ``zone-cell01``...);
4. device roles, one per role the template draws;
5. inventory item roles (transceiver, power supply, fan);
6. contact roles for the asset owner and custodian.

The audit evidence fields (compliance scope, data classification, physical access, backup,
patch, verification and contract dates, monitoring and logging; see audit.py) come with
step 2, as dropdowns, dates and bounded numbers so manual entry stays clean.
Facts true of every device of a model (end of sale, end of support, the vendor's
notice) are fields on the device type, set once per model; a device's own value
overrides its model's.

It follows the site's settings: a role mapped to one NetBox already has, or a
Purdue or SL-T fact kept in a field of the site's own, adds nothing. The
``netdiagrams`` JSON field (settings on a site, site group or region) is added
so a whole estate can keep its mapping in NetBox.

When NetDiagrams can read your NetBox it leaves out what is already there.
``--check`` only compares; ``--apply`` creates the missing objects through the API.
Everything here is additive and survives NetBox upgrades: custom fields, choice
sets, tags and roles are NetBox's own extension points, none is required, and the
tool never updates or deletes what exists, so a field you renamed or a tag you
recoloured is left alone.
"""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from . import audit, profiles, wireless
from .netbox import NetBoxError
from .model import band_for_zone, bands

PURDUE = [("L5", "Level 5 · Enterprise / internet"), ("L4", "Level 4 · Site business (IT)"),
          ("L3.5", "Level 3.5 · Industrial DMZ"), ("L3", "Level 3 · Site operations"),
          ("L2", "Level 2 · Area supervisory control"), ("L1", "Level 1 · Basic control"),
          ("L0", "Level 0 · Process")]
SECURITY_LEVELS = [("SL1", "SL 1 · casual or coincidental violation"), ("SL2", "SL 2 · simple means"),
                   ("SL3", "SL 3 · sophisticated means"), ("SL4", "SL 4 · sophisticated means and extended resources")]
BAND_COLORS = {"L5": "9e9e9e", "L4": "2196f3", "L3.5": "ff9800", "L3": "4caf50", "L2–0": "9c27b0",
               "—": "607d8b", "?": "607d8b"}
ZONE_COLORS = {"zone-sis": "f44336"}  # safety is red in the book's legend, not its band's purple
ROLE_COLORS = {"firewall": "334155", "core-switch": "3f51b5", "access-switch": "2196f3",
               "industrial-switch": "009688", "sis-switch": "e91e63", "oob-switch": "607d8b",
               "wireless-controller": "00bcd4", "access-point": "00bcd4", "ptp-radio": "ff4081",
               "sdwan-edge": "673ab7", "hypervisor": "795548", "plc": "8bc34a", "hmi": "cddc39",
               "io": "ffc107", "sis-controller": "f44336", "workgroup-bridge": "00bcd4"}
ROLE_NAMES = {"hmi": "HMI", "plc": "PLC", "io": "Remote I/O", "sis-controller": "SIS controller",
              "sis-switch": "SIS switch", "ptp-radio": "PtP radio", "sdwan-edge": "SD-WAN edge",
              "oob-switch": "OOB switch"}
CRITICALITY_SET = "Asset criticality"
MODEL_FIELDS = [  # name, label, group, type, object types, choice set, description
    ("end_of_sale", "End of sale", "Lifecycle", "date", "dcim.devicetype,dcim.device", "",
     "Last day the vendor sells this model. Set it on the device type; a device's own date overrides it"),
    ("end_of_support", "End of support", "Lifecycle", "date", "dcim.devicetype,dcim.device", "",
     "Last day the vendor supports this model (fixes, advisories, RMA). Set it on the device type; "
     "a device's own date overrides it"),
    ("eol_notice", "End-of-life notice", "Lifecycle", "url", "dcim.devicetype", "",
     "Link to the vendor's end-of-sale and end-of-support announcement for this model"),
]
CRITICALITY = (("critical", "Critical"), ("high", "High"), ("medium", "Medium"), ("low", "Low"))
ASSET_FIELDS = {"sw_version": "Software version", "lifecycle": "Lifecycle", "support_contract": "Support contract",
                "policy_tag": "Policy tag", "rf_tag": "RF tag", "site_tag": "Site tag"}


def _template_facts(template: ET.Element) -> tuple[dict[str, str], set[str], set[str]]:
    """Zone tags (slug -> name), device roles and custom fields the template uses.

    A zone is known from a ``zone-...`` tag on any shape, or from a row of the zone tables
    (ZONE / PURDUE and VLANS / ZONE), so a zone with no device of its own, such as GUEST,
    still gets its tag.
    """
    from .graph import Graph
    from .sync import _is_device, _table_text

    zones, roles, fields = {}, set(), set()
    for el in template.iter("object"):
        # A zone tag may sit on a VLAN, prefix or zone shape as well as on a device (a guest
        # zone often has no device of its own).
        for tag in (el.get("tags") or "").split(","):
            tag = tag.strip()
            if tag.startswith("zone-"):
                zones.setdefault(tag, tag[5:].replace("-", " ").upper())
        if not _is_device(el):
            continue
        roles.add(el.get("role") or "")
        fields.update(k[3:] for k in el.attrib if k.startswith("cf_"))
    for diagram in template.findall("diagram"):
        if diagram.find("mxGraphModel") is None:
            continue
        g = Graph(diagram)
        for table in g.tables():
            header = g.header(table)
            column = 0 if header[:1] == ["ZONE"] else 1 if header[:2] == ["VLANS", "ZONE"] else None
            if column is None:
                continue
            for row in _table_text(g, table):
                for name in re.split(r"\s*(?:/|·|,)\s*", row[column] if len(row) > column else ""):
                    if re.fullmatch(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*", name.strip()):  # IT-ENT, GUEST; not "CELL0n"
                        zones.setdefault("zone-" + name.strip().lower(), name.strip())
    zones.update(profiles.current().zone_names)  # zones the profile names, with or without a shape
    roles |= set(profiles.current().endpoint_roles)  # drawn as counted groups, so maybe no shape of their own
    roles.discard("")
    return zones, roles, fields


def _csv(header: list[str], rows: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def setup_files(template: ET.Element, existing: dict[str, set[str]] | None = None,
                settings: dict | None = None) -> dict[str, str]:
    """File name -> CSV text. ``existing`` maps 'choice_sets', 'custom_fields',
    'tags' and 'roles' to names or slugs NetBox already has."""
    existing = existing or {}
    settings = settings or {}
    zones, roles, fields = _template_facts(template)
    roles -= {r for r, names in (settings.get("roles") or {}).items() if names}
    # A fact the site keeps in its own field (settings name it first) needs no new field.
    own = lambda key, default: (settings.get(key) or [default])[0] != default
    if own("sw_field", "sw_version"):
        fields.discard("sw_version")
    files = {}

    levels = profiles.current().levels  # Purdue levels and SL-T are the plant standard's; other industries skip them
    worded = profiles.current().level_labels  # the values stay; an industry may word the labels
    choice_sets = [] if not levels else [["Purdue level", ",".join(f"{v}:{worded.get(v, l)}" for v, l in PURDUE)],
                   ["IEC 62443 security level", ",".join(f"{v}:{worded.get(v, l)}" for v, l in SECURITY_LEVELS)]]
    # The wireless sets: WPA3/OWE security, switching, bands, portal, AP mode, how the site's APs are managed.
    choice_sets += [[name, ",".join(f"{v}:{l}" for v, l in choices)] for name, choices in wireless.CHOICE_SETS.items()]
    if not own("criticality_field", "criticality"):
        choice_sets.append([CRITICALITY_SET, ",".join(f"{v}:{l}" for v, l in CRITICALITY)])
    # The audit evidence fields' lists (scope, classification, physical access, monitoring, log forwarding),
    # unless the site keeps that fact in a field of its own (settings audit.fields).
    own_audit = set(((settings.get("audit") or {}).get("fields") or {}))
    choice_sets += [[name, ",".join(f"{v}:{l}" for v, l in audit.choices(name))] for name in audit.CHOICE_SETS
                    if not all(f in own_audit for f, n in audit.SELECTS.items() if n == name)]
    choice_sets = [r for r in choice_sets if r[0] not in existing.get("choice_sets", set())]
    if choice_sets:
        files["1-custom-field-choice-sets.csv"] = _csv(["name", "extra_choices"], choice_sets)

    custom = [
        ["purdue_level", "Purdue level", "OT", "select", "dcim.device,dcim.location,ipam.vlan,ipam.prefix",
         "Purdue level", "Purdue reference model level"],
        ["security_level_target", "Security level target", "OT", "select", "dcim.device,dcim.location",
         "IEC 62443 security level", "IEC 62443 target security level (SL-T) of the zone"],
        ["netdiagrams", "NetDiagrams settings", "NetDiagrams", "json", "dcim.site,dcim.sitegroup,dcim.region",
         "", "Role map, zone field and naming for NetDiagrams (see netdiagrams.com)"],
        ["criticality", "Asset criticality", "Asset", "select", "dcim.device", CRITICALITY_SET,
         "How much the site depends on this asset: critical, high, medium or low"],
        ["gateway", "Gateway", "IPAM", "text", "ipam.prefix", "",
         "The subnet's gateway address, when no IP address in NetBox is marked as the gateway"],
    ]
    if own("gateway_field", "gateway"):
        custom = [r for r in custom if r[0] != "gateway"]
    # A model's dates and notice: set once on the device type; a device's own value overrides it.
    custom += [list(r) for r in MODEL_FIELDS if not (r[0] == "end_of_support" and own("end_of_support_field", r[0]))]
    if own("criticality_field", "criticality"):
        custom = [r for r in custom if r[0] != "criticality"]
    fields.discard("criticality")   # the template's cf_criticality is the select above, not a text field
    if not levels:
        custom = [r for r in custom if r[0] not in ("purdue_level", "security_level_target")]
    if own("level_field", "purdue_level"):
        custom = [r for r in custom if r[0] != "purdue_level"]
    if own("sl_field", "security_level_target"):
        custom = [r for r in custom if r[0] != "security_level_target"]
    wireless_fields = {row[0] for row in wireless.CUSTOM_FIELDS}
    for name in sorted(fields):
        if name in wireless_fields:   # the template's cf_ap_mode / cf_wireless_controller: defined below, with their types
            continue
        custom.append([name, ASSET_FIELDS.get(name, name.replace("_", " ").capitalize()), "Asset", "text",
                       "dcim.device", "", ""])
    for name, label, group, kind, types, choice_set, description in wireless.CUSTOM_FIELDS:
        custom.append([name, label, group, kind, types, choice_set, description])
    for name, label, group, kind, types, choice_set, description in audit.CUSTOM_FIELDS:
        if name not in own_audit:
            custom = [r for r in custom if r[0] != name]   # the template's text support_contract: defined here
            custom.append([name, label, group, kind, types, choice_set, description])
    custom = [r for r in custom if r[0] not in existing.get("custom_fields", set())]
    if custom:
        # An object field names the model it points at (NetBox's related_object_type); the others leave it blank.
        bounds = lambda name: [str(b) for b in audit.VALIDATION.get(name, ("", ""))]
        rows = [r + [wireless.OBJECT_FIELD_TYPES.get(r[0], "") if r[3] == "object" else ""] + bounds(r[0])
                for r in custom]
        files["2-custom-fields.csv"] = _csv(
            ["name", "label", "group_name", "type", "object_types", "choice_set", "description",
             "related_object_type", "validation_minimum", "validation_maximum"], rows)

    tags = []
    for slug, name in sorted(zones.items(), key=lambda kv: (band_order(kv[0]), kv[0])):
        band = band_for_zone(slug)
        level = band[0]
        named = slug in profiles.current().zone_names
        tags.append([name if named else f"Zone {name}", slug, ZONE_COLORS.get(slug) or BAND_COLORS.get(profiles.palette(level), "607d8b"),
                     f"Security zone {name} (Purdue {level})" if levels else
                     f"Security zone, {profiles.current().band_word} {level}: {band[1]}",
                     "dcim.device,dcim.location,ipam.vlan,ipam.prefix,ipam.vrf"])
    tags = [r for r in tags if r[1] not in existing.get("tags", set())]
    if tags:
        files["3-zone-tags.csv"] = _csv(["name", "slug", "color", "description", "object_types"], tags)

    role_rows = [[profiles.role_name(r, ROLE_NAMES), r, profiles.role_color(r, ROLE_COLORS)]
                 for r in sorted(roles)]
    role_rows = [r for r in role_rows if r[1] not in existing.get("roles", set())]
    if role_rows:
        files["4-device-roles.csv"] = _csv(["name", "slug", "color"], role_rows)
    # Inventory item roles, so a transceiver, power supply or fan is told apart by role, not by part number.
    item_roles = [r for r in ITEM_ROLES if r[1] not in existing.get("item_roles", set())]
    if item_roles:
        files["5-inventory-item-roles.csv"] = _csv(["name", "slug", "color"], item_roles)
    # Contact roles for the asset owner and custodian, so ownership is picked from NetBox's contacts.
    contact_roles = [r for r in audit.CONTACT_ROLES if r[1] not in existing.get("contact_roles", set())]
    if contact_roles:
        files["6-contact-roles.csv"] = _csv(["name", "slug", "description"], contact_roles)
    return files


ITEM_ROLES = [["Transceiver", "transceiver", "00bcd4"], ["Power supply", "psu", "ff9800"], ["Fan", "fan", "607d8b"]]


def band_order(slug: str) -> int:
    order = [b[0] for b in bands()] + ["—", "?"]
    return order.index(band_for_zone(slug)[0])


FILE_MENUS = {  # CSV file -> where NetBox imports it
    "1-custom-field-choice-sets.csv": "Customization > Custom Field Choice Sets > Import",
    "2-custom-fields.csv": "Customization > Custom Fields > Import",
    "3-zone-tags.csv": "Customization > Tags > Import",
    "4-device-roles.csv": "Devices > Device Roles > Import",
    "5-inventory-item-roles.csv": "Devices > Inventory Item Roles > Import",
    "6-contact-roles.csv": "Organization > Contact Roles > Import",
}


def guide(files: dict[str, str]) -> str:
    """README.txt for the files written: only those files, in the profile's own words."""
    profile = profiles.current()
    words = profile.words
    if profile.levels:
        places, grouping = profiles.word("place_nouns"), profiles.word("location_grouping")
    else:  # an industry without Purdue levels that says nothing of its own
        places = words.get("place_nouns", "building, floor, room")
        grouping = words.get("location_grouping", "rooms under floors and buildings")
    listed = [f"{name:<31} {menu}" for name, menu in FILE_MENUS.items() if name in files]
    steps = [f"- tag each device, VLAN and prefix with its zone (zone-...), or tag the location\n"
             f"  ({places}) and every device in it inherits the zone;"]
    if profile.levels:
        steps.append("- set Purdue level and Security level target on devices or on their location;")
    steps.append(f"- group {grouping} with nested locations;")
    steps.append("- assign each room (or the site) a contact with the role Asset owner, and set Monitoring,\n"
                 "  Log forwarding and Log destination on the site: every device inherits them.")
    return (("Import these files into NetBox in order. Each list in NetBox has an Import button.\n\n"
             + "\n".join(listed) + "\n\n" if listed else
             "NetBox already has every field, tag and role the template uses; nothing to import.\n\n")
            + "Then, in NetBox:\n" + "\n".join(steps) + "\n\n"
            "Run netdiagrams again and the drawing follows. A file missing from this folder means\n"
            "NetBox already has everything it would add. \"netdiagrams netbox-setup --apply\" creates\n"
            "the same objects through the API with a token that can write; \"--check\" only compares.\n"
            "Nothing that exists is ever changed or removed.\n")




KINDS = {  # kind -> (endpoint, key the CSV identifies it by, CSV file)
    "choice_sets": ("extras/custom-field-choice-sets", "name", "1-custom-field-choice-sets.csv"),
    "custom_fields": ("extras/custom-fields", "name", "2-custom-fields.csv"),
    "tags": ("extras/tags", "slug", "3-zone-tags.csv"),
    "roles": ("dcim/device-roles", "slug", "4-device-roles.csv"),
    "item_roles": ("dcim/inventory-item-roles", "slug", "5-inventory-item-roles.csv"),
    "contact_roles": ("tenancy/contact-roles", "slug", "6-contact-roles.csv"),
}


def inventory(client) -> dict[str, dict[str, dict]]:
    """What NetBox already has, read with GET only: kind -> {name or slug: the object}."""
    out = {}
    for kind, (endpoint, key, _) in KINDS.items():
        try:
            out[kind] = {o.get(key): o for o in client.list(endpoint) if o.get(key)}
        except NetBoxError as err:
            if err.code != 404:  # a bad token or an unreachable NetBox is not an empty one
                raise
            out[kind] = {}  # an older NetBox without the endpoint
    return out


def _version_tuple(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", version or "")
    return tuple(int(p) for p in parts[:3]) or (99,)


def _types(value: str) -> list[str]:
    return [t for t in (value or "").split(",") if t]


def _rows(files: dict[str, str], name: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(files[name]))) if name in files else []


@dataclass
class Step:
    kind: str
    endpoint: str
    label: str
    payload: dict


def plan(files: dict[str, str], version: str = "") -> list[Step]:
    """The API calls that create what the import files would, for this NetBox version.

    NetBox 4.0 renamed a custom field's ``content_types`` to ``object_types``;
    choice sets arrived in 3.6 (before that a select field carries its choices).
    """
    v = _version_tuple(version)
    steps = []
    for row in _rows(files, KINDS["choice_sets"][2]):
        if v >= (3, 6):
            steps.append(Step("choice_sets", KINDS["choice_sets"][0], f"choice set {row['name']}", {
                "name": row["name"],
                "extra_choices": [c.split(":", 1) for c in row["extra_choices"].split(",")]}))
    sets = {row["name"]: row["extra_choices"] for row in _rows(files, KINDS["choice_sets"][2])}
    for row in _rows(files, KINDS["custom_fields"][2]):
        payload = {"name": row["name"], "label": row["label"], "type": row["type"],
                   "description": row["description"], "required": False,
                   ("object_types" if v >= (4,) else "content_types"): _types(row["object_types"])}
        if row["group_name"]:
            payload["group_name"] = row["group_name"]
        if row.get("related_object_type"):  # NetBox 4.0 renamed object_type to related_object_type
            payload["related_object_type" if v >= (4,) else "object_type"] = row["related_object_type"]
        for bound in ("validation_minimum", "validation_maximum"):
            if row.get(bound):
                payload[bound] = int(row[bound])
        if row["choice_set"]:
            if v >= (3, 6):
                payload["choice_set"] = {"name": row["choice_set"]}  # resolved to an id when applied
            else:
                payload["choices"] = [c.split(":", 1)[0] for c in sets.get(row["choice_set"], "").split(",") if c]
        steps.append(Step("custom_fields", KINDS["custom_fields"][0], f"custom field {row['name']}", payload))
    for row in _rows(files, KINDS["tags"][2]):
        payload = {"name": row["name"], "slug": row["slug"], "color": row["color"], "description": row["description"]}
        if v >= (3, 6) and row.get("object_types"):
            payload["object_types"] = _types(row["object_types"])
        steps.append(Step("tags", KINDS["tags"][0], f"tag {row['slug']}", payload))
    for row in _rows(files, KINDS["roles"][2]):
        steps.append(Step("roles", KINDS["roles"][0], f"device role {row['slug']}",
                          {"name": row["name"], "slug": row["slug"], "color": row["color"]}))
    for row in _rows(files, KINDS["item_roles"][2]):
        steps.append(Step("item_roles", KINDS["item_roles"][0], f"inventory item role {row['slug']}",
                          {"name": row["name"], "slug": row["slug"], "color": row["color"]}))
    for row in _rows(files, KINDS["contact_roles"][2]):
        steps.append(Step("contact_roles", KINDS["contact_roles"][0], f"contact role {row['slug']}",
                          {"name": row["name"], "slug": row["slug"], "description": row["description"]}))
    return steps


def apply(client, steps: list[Step], have: dict[str, dict[str, dict]] | None = None) -> list[tuple[str, str]]:
    """Create each step's object unless NetBox has it; never update or delete. Returns (label, outcome)."""
    have = have or inventory(client)
    out = []
    for step in steps:
        key = step.payload.get("slug") or step.payload["name"]
        if key in have.get(step.kind, {}):
            out.append((step.label, "already there, left as is"))
            continue
        payload = dict(step.payload)
        if isinstance(payload.get("choice_set"), dict):
            name = payload["choice_set"]["name"]
            found = have.get("choice_sets", {}).get(name)
            if found is None:
                try:
                    found = next(iter(client.list("extras/custom-field-choice-sets", name=name)), None)
                except Exception:
                    found = None
            if found is None or found.get("id") is None:
                out.append((step.label, f"skipped: choice set {name} is not in NetBox"))
                continue
            payload["choice_set"] = found["id"]
        try:
            created = client.post(step.endpoint, payload)
        except Exception as err:  # one refusal must not stop the rest
            out.append((step.label, f"failed: {err}"))
            continue
        have.setdefault(step.kind, {})[key] = created
        out.append((step.label, "created"))
    return out


def check(template: ET.Element, have: dict[str, dict[str, dict]], settings: dict | None = None,
          version: str = "") -> list[tuple[str, str, str]]:
    """(kind, name, state) for everything the template needs: present, missing, or present but short of a type."""
    files = setup_files(template, settings=settings)
    rows = []
    for kind, (endpoint, key, name) in KINDS.items():
        if kind == "choice_sets" and _version_tuple(version) < (3, 6):
            continue  # before 3.6 a select field carries its own choices; there is nothing to create
        for row in _rows(files, name):
            ident = row[key]
            found = have.get(kind, {}).get(ident)
            if found is None:
                rows.append((kind, ident, "missing"))
                continue
            wanted = set(_types(row.get("object_types", "")))
            has = found.get("object_types") or found.get("content_types") or []
            has = {t if isinstance(t, str) else (t.get("app_label", "") + "." + t.get("model", "")) for t in has}
            short = sorted(wanted - has) if wanted and has else []
            rows.append((kind, ident, "present" if not short else f"present, but not on {', '.join(short)}"))
    return rows


def check_lines(rows: list[tuple[str, str, str]]) -> list[str]:
    labels = {"choice_sets": "Choice set", "custom_fields": "Custom field", "tags": "Tag", "roles": "Device role",
              "item_roles": "Item role", "contact_roles": "Contact role"}
    missing = sum(1 for _, _, state in rows if state == "missing")
    partial = sum(1 for _, _, state in rows if state.startswith("present, but"))
    out = [f"{labels[kind]:<13} {ident:<28} {state}" for kind, ident, state in rows]
    if not rows:
        out.append("The template needs nothing this NetBox lacks.")
    out.append(f"{len(rows) - missing - partial} present, {partial} present but short of an object type, {missing} missing."
               + (" Run netdiagrams netbox-setup --apply, or import the CSV files." if missing else "")
               + (" A field short of a type is edited by hand in NetBox (the tool never changes what exists)."
                  if partial else ""))
    return out


def write(folder: Path, files: dict[str, str]) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    for name in FILE_MENUS:  # a file from an earlier run that NetBox no longer needs goes
        if name not in files:
            (folder / name).unlink(missing_ok=True)
    written = []
    for name, text in files.items():
        path = folder / name
        path.write_text(text, "utf-8")
        written.append(path)
    (folder / "README.txt").write_text(guide(files), "utf-8")
    return written
