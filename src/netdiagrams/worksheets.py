"""Files that close the gaps the "Plan to improve" cards list, through NetBox's own Import.

``netdiagrams gaps`` writes one CSV per NetBox list that has gaps: devices without
a serial, room, rack or zone; cables without a label or media type; trunks with no
tagged VLANs; subnets with no zone; VLANs with no subnet. Every row carries the
object's NetBox ``id`` and its current values, so importing the file back updates
those objects in place (NetBox's import updates an existing object when a row has
an ``id``) and a column left as it was changes nothing. The blank cells are the
gaps: fill them from the matching collection worksheet, delete the rows you cannot
answer yet, and import. NetDiagrams itself still writes nothing to NetBox.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from . import audit, gaps, hardware, intake, wireless
from .model import _get


# Rows left out of the last files() because a cell would run as a spreadsheet formula ("object: value").
SKIPPED: list[str] = []
FORMULA = re.compile(r"^[=+\-@\t\r]")


def _is_formula(value) -> bool:
    text = str(value)
    if not FORMULA.match(text):
        return False
    try:
        float(text)  # -5 or +1 is a number, not a formula
        return False
    except ValueError:
        return True


def _csv(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        bad = next((v for v in row if _is_formula(v)), None)
        if bad is None:
            writer.writerow(row)
        else:  # an apostrophe would defuse it in Excel, but NetBox would store the apostrophe on import
            SKIPPED.append(f"{row[1] if len(row) > 1 and row[1] else row[0]}: {str(bad)[:40]}")
    return out.getvalue()


def _field(export: dict, key: str, canonical: str, names) -> str:
    """The custom field this site keeps ``canonical`` in, for an import header NetBox recognises.

    intake copies the site's own field (settings *_field, audit.fields) to the canonical name, so a
    configured name present on the objects is the site's; the canonical name otherwise.
    """
    present = {k for o in export.get(key) or [] for k in (o.get("custom_fields") or {})}
    return next((n for n in names if n != canonical and n in present), canonical)


def _setting_field(export: dict, key: str, canonical: str) -> str:
    names = intake.intake(export).settings.get(intake.CANONICAL[canonical]) or []
    return _field(export, key, canonical, [names] if isinstance(names, str) else names)


def _site(d: dict, export: dict) -> str:
    return _name(d.get("site")) or _name(export.get("site"))


def _name(obj) -> str:
    return (obj or {}).get("name", "") if isinstance(obj, dict) else (obj or "")


def _tags(obj: dict) -> str:
    return ",".join(t.get("slug", "") for t in obj.get("tags") or [] if t.get("slug"))


def files(export: dict, found: dict[str, gaps.Gap]) -> dict[str, str]:
    """File name -> CSV text, for the gaps ``found`` (from :func:`gaps.find`)."""
    out: dict[str, str] = {}
    SKIPPED.clear()
    names = lambda *keys: {n for k in keys if k in found for n in found[k].names}
    first = lambda s: s.split(":")[0].split(" ×")[0]

    # Devices: serial, asset tag, room, rack, U and zone tag live on the device.
    flagged = names("no_serial", "no_location", "no_zone", "bad_name", "no_name", "no_criticality")
    for key in ("dup_serial", "dup_ip", "dup_asset_tag"):
        for entry in found.get(key, gaps.Gap(key, "", "", "", "")).names:
            flagged.update(n.strip() for n in entry.split(":", 1)[-1].split(","))
    rows = []
    for d in export.get("devices", []):
        if d.get("name") in flagged and d.get("id") is not None:
            rows.append([d["id"], d.get("name", ""), _site(d, export), d.get("serial") or "", d.get("asset_tag") or "",
                         _name(d.get("location")), _name(d.get("rack")),
                         "" if d.get("position") is None else f"{d['position']:g}", _tags(d),
                         _name((d.get("custom_fields") or {}).get("criticality"))])
    if rows:
        # NetBox finds the room and rack by name within the row's site, so the site is always given.
        out["1-devices.csv"] = _csv(["id", "name", "site", "serial", "asset_tag", "location", "rack", "position",
                                     "tags", "cf_" + _setting_field(export, "devices", "criticality")], rows)

    # Access points: their mode and controller (custom fields) beside the device fields.
    ap_names = names("wlan_no_manager", "ap_no_location")
    rows = []
    for d in export.get("devices", []):
        if d.get("name") in ap_names and d.get("id") is not None:
            cf = d.get("custom_fields") or {}
            controller = cf.get("wireless_controller")
            # An object custom field imports by the object's id, not its name.
            rows.append([d["id"], d["name"], _site(d, export), _name(d.get("location")), cf.get("ap_mode") or "",
                         controller.get("id", "") if isinstance(controller, dict) else (controller or "")])
    if rows:
        out["6-access-points.csv"] = _csv(["id", "name", "site", "location", "cf_ap_mode", "cf_wireless_controller"],
                                          rows)

    # Wireless LANs: the VLAN and the wlan_* fields the SSID table reads. Never the PSK.
    flagged_ssids = names("wlan_no_vlan", "wlan_no_fields", "wlan_guest_controls", "wlan_review_open",
                          "wlan_review_psk")
    rows = []
    for w in export.get("wireless_lans") or []:
        if w.get("ssid") in flagged_ssids and w.get("id") is not None:
            cf = w.get("custom_fields") or {}
            bands = cf.get("wlan_bands")
            rows.append([w["id"], w["ssid"], _get(w, "vlan", "name") or "",   # NetBox finds the VLAN by name
                         _get(w, "auth_type", "value") or "", wireless.cf(w, "wlan_security"),
                         wireless.cf(w, "wlan_switching"),
                         ",".join(str(b) for b in bands) if isinstance(bands, list) else wireless.cf(w, "wlan_bands"),
                         "" if cf.get("wlan_client_isolation") is None else str(cf["wlan_client_isolation"]).lower(),
                         wireless.cf(w, "wlan_portal")])
    if rows:
        out["7-wireless-lans.csv"] = _csv(["id", "ssid", "vlan", "auth_type", "cf_wlan_security", "cf_wlan_switching",
                                           "cf_wlan_bands", "cf_wlan_client_isolation", "cf_wlan_portal"], rows)

    # Wireless links: one row per radio or bridge with no link yet (these rows create).
    unlinked = names("no_wireless_links", "wgb_no_link")
    rows = []
    for d in export.get("devices", []):
        if d.get("name") in unlinked:
            radio = next((i.get("name") for i in export.get("interfaces", []) if _get(i, "device", "name") == d["name"]
                          and wireless.RADIO_TYPES.search(_get(i, "type", "value") or "")), "")
            rows.append([d["name"], radio, "", "", "", "connected", "", "m"])
    if rows:
        out["8-new-wireless-links.csv"] = _csv(["device_a", "interface_a", "device_b", "interface_b",
                                                "ssid", "status", "distance", "distance_unit"], rows)

    # Cables: label, media type, length.
    cable_names = {first(n) for n in names("cable_no_label", "cable_no_type")}
    labels_twice = {first(n) for n in names("cable_label_twice")}
    rows = []
    for c in export.get("cables", []):
        if c.get("id") is None:
            continue
        if gaps._cable_name(c) in cable_names or (c.get("label") or "") in labels_twice:
            rows.append([c["id"], c.get("label") or "", c.get("type") or "",
                         "" if c.get("length") is None else f"{c['length']:g}",
                         _get(c, "length_unit", "value"), (c.get("color") or "")])
    if rows:
        out["2-cables.csv"] = _csv(["id", "label", "type", "length", "length_unit", "color"], rows)

    # Trunk interfaces: the allowed-VLAN list, by VID.
    trunks = names("trunk_no_vlans")
    by_vid = {v["id"]: v for v in export.get("vlans", []) if v.get("id") is not None}
    rows = []
    for i in export.get("interfaces", []):
        if f"{_get(i, 'device', 'name')} {i.get('name')}" in trunks and i.get("id") is not None:
            vlans = [i.get("untagged_vlan")] + list(i.get("tagged_vlans") or [])
            group = next((_name(by_vid.get((v or {}).get("id"), {}).get("group")) for v in vlans
                          if _name(by_vid.get((v or {}).get("id"), {}).get("group"))), "")
            rows.append([i["id"], _get(i, "device", "name"), i.get("name", ""), _get(i, "mode", "value") or "tagged",
                         ",".join(str(v.get("vid")) for v in i.get("tagged_vlans") or []),
                         str(_get(i, "untagged_vlan", "vid", default="") or ""), group])
    if rows:
        # A VID repeats across sites on a shared NetBox: the VLAN group says which one.
        out["3-interfaces.csv"] = _csv(["id", "device", "name", "mode", "tagged_vlans", "untagged_vlan",
                                        "vlan_group"], rows)

    # Subnets without a zone: a VLAN (by VID), a VRF or a zone tag places them.
    unzoned = names("prefix_no_zone")
    rows = []
    for p in export.get("prefixes", []):
        if p.get("prefix") in unzoned and p.get("id") is not None:
            vlan = by_vid.get(_get(p, "vlan", "id"), {})
            rows.append([p["id"], p["prefix"], _name(p.get("vrf")), str(_get(p, "vlan", "vid", default="") or ""),
                         _name(vlan.get("site")), _name(vlan.get("group")), _tags(p)])
    if rows:
        out["4-prefixes.csv"] = _csv(["id", "prefix", "vrf", "vlan", "vlan_site", "vlan_group", "tags"], rows)

    # VLANs with no subnet: new prefixes, one row each (no id: these rows create).
    no_prefix = {n.split(" ", 1)[0] for n in names("vlan_no_prefix")}
    rows = []
    for v in export.get("vlans", []):
        if str(v.get("vid")) in no_prefix:
            rows.append(["", "active", str(v.get("vid")), _name(v.get("site")), _name(v.get("group")), "",
                         f"{v.get('name', '')} subnet"])
    if rows:
        out["5-new-prefixes.csv"] = _csv(["prefix", "status", "vlan", "vlan_site", "vlan_group", "vrf",
                                          "description"], rows)

    # Modules and inventory items without a serial; a new transceiver row for each fiber end with none.
    wanted = names("module_no_serial")
    rows = [[m["id"], _name(m.get("device")), _name(m.get("module_bay")), _get(m, "module_type", "model"),
             m.get("serial") or ""] for m in export.get("modules") or []
            if m.get("id") is not None and not m.get("serial")
            and f"{_name(m.get('device'))} {_name(m.get('module_bay'))} {hardware.module_model(m)}".strip() in wanted]
    if rows:
        out["9-modules.csv"] = _csv(["id", "device", "module_bay", "module_type", "serial"], rows)
    wanted = names("item_no_serial")
    rows = [[i["id"], _name(i.get("device")), i.get("name") or "", _name(i.get("role")), i.get("part_id") or "",
             i.get("serial") or ""] for i in export.get("inventory_items") or []
            if i.get("id") is not None and not i.get("serial")   # not a same-part sibling that has one
            and f"{_name(i.get('device'))} {hardware.part(i)}".strip() in wanted]
    if rows:
        out["10-inventory-items.csv"] = _csv(["id", "device", "name", "role", "part_id", "serial"], rows)
    rows = []
    for entry in sorted(names("fibre_no_optic")):
        parts = entry.split(" ", 2)   # "<cable label> <device> <interface>"
        if len(parts) == 3:
            rows.append([parts[1], "", "transceiver", "", "", "dcim.interface", parts[2]])
    if rows:
        out["11-new-optics.csv"] = _csv(["device", "name", "role.slug", "part_id", "serial", "component_type",
                                         "component_name"], rows)
    _audit_files(export, found, out)
    _model_files(export, found, out)
    return out


def _audit_files(export: dict, found: dict[str, gaps.Gap], out: dict[str, str]) -> None:
    """The audit evidence gaps: device dates and monitoring, room access and walk-downs, and owner contacts."""
    names = lambda *keys: {n for k in keys if k in found for n in found[k].names}
    ev = audit.Evidence(export, intake.intake(export).settings)
    cf = lambda obj, f: audit.label(v) if isinstance(v := ev.cf(obj, f), list) else str(v or "")
    device_keys = ("stale_backup", "stale_patch", "support_ended", "not_monitored", "no_log_forwarding")
    columns = ["last_config_backup", "last_patched", "support_contract", "support_contract_end", "install_date",
               "monitoring", "log_forwarding"]
    scored = {k for k, (_, total) in ev.checks("").items() if total}
    wanted = names(*[k for k in device_keys if k in scored])
    if wanted:
        rows = [[d["id"], d["name"]] + [cf(d, c) for c in columns] for d in export.get("devices", [])
                if d.get("name") in wanted and d.get("id") is not None]
        if rows:
            out["12-audit-evidence.csv"] = _csv(["id", "name"] + [f"cf_{_field(export, 'devices', c, ev.names.get(c, [c]))}"
                                                                  for c in columns], rows)
    # Rooms: physical access and the walk-down date are set once per room, for every device in it.
    rooms = {}
    for key in ("no_physical_access", "stale_verified"):
        if key not in found or key not in scored:
            continue
        for name in found[key].names:
            d = next((x for x in export.get("devices", []) if x.get("name") == name), None)
            chain = ev.chain((d or {}).get("location"))
            if chain and chain[0].get("id") is not None:
                rooms[chain[0]["id"]] = chain[0]
    rows = [[loc["id"], loc.get("name") or "", cf(loc, "physical_access"), cf(loc, "last_verified")]
            for loc in rooms.values()]
    if rows:
        out["13-locations.csv"] = _csv(["id", "name"] + [f"cf_{_field(export, 'locations', c, ev.names.get(c, [c]))}"
                                                         for c in ("physical_access", "last_verified")], rows)
    # Owners: one new contact assignment per room (or per device with no room); these rows create.
    if "no_owner" in found and "no_owner" in scored:
        rows, seen = [], set()
        for d in export.get("devices", []):
            if d.get("name") not in found["no_owner"].names:
                continue
            chain = ev.chain(d.get("location"))
            target = ("dcim.location", chain[0]["id"]) if chain and chain[0].get("id") is not None \
                else ("dcim.device", d.get("id"))
            if target[1] is not None and target not in seen:
                seen.add(target)
                rows.append([target[0], target[1], "", "asset-owner", "primary"])
        if rows:
            out["14-new-owner-contacts.csv"] = _csv(["object_type", "object_id", "contact", "role.slug", "priority"],
                                                    rows)


def _model_files(export: dict, found: dict[str, gaps.Gap], out: dict[str, str]) -> None:
    """One row per network model with no end-of-support date: set once, every device of the model has it."""
    if "model_no_eos" not in found or not found["model_no_eos"].names:
        return
    wanted, rows, seen = set(found["model_no_eos"].names), [], set()
    types = export.get("device_types") or []
    for d in export.get("devices", []):
        ref = d.get("device_type") or {}
        key = " ".join(x for x in (_get(d, "device_type", "manufacturer", "name"), ref.get("model")) if x)
        t = intake.type_of(d, types) or ref
        if key not in wanted or key in seen or t.get("id") is None:
            continue
        seen.add(key)
        cf = t.get("custom_fields") or {}
        rows.append([t["id"], _get(t, "manufacturer", "name") or "", t.get("model") or "",
                     cf.get("end_of_sale") or "", cf.get("end_of_support") or "", cf.get("eol_notice") or ""])
    if rows:
        out["15-device-models.csv"] = _csv(["id", "manufacturer", "model", "cf_end_of_sale",
                                            "cf_" + _setting_field(export, "device_types", "end_of_support"),
                                            "cf_eol_notice"], rows)


GUIDE = """These files close the gaps the drawing's "Plan to improve" cards list, through
NetBox's own Import button. Each row carries the object's NetBox id and its current
values, so importing a file updates those objects in place. The blank cells are the
gaps. Fill them in, delete the rows you cannot answer yet, and import. A value you
leave as it was changes nothing. NetDiagrams only reads NetBox, except the opt-in
`netbox-setup --apply`.

1-devices.csv        Devices > Devices > Import              WS-02 Network devices (serial, asset tag,
                                                             room, rack, U, cf_criticality: critical, high,
                                                             medium or low) and WS-01 zones (tags: zone-...);
                                                             keep the site column: NetBox finds rooms by site
2-cables.csv         Devices > Cables > Import               WS-04 Links, cables, optics (label, type, length)
3-interfaces.csv     Devices > Interfaces > Import           WS-03 VLANs (tagged_vlans: VIDs, comma-separated)
4-prefixes.csv       IPAM > Prefixes > Import                WS-03 VLANs (vlan: the VID, with its vlan_site or
                                                             vlan_group; vrf: its name; tags: zone-...)
5-new-prefixes.csv   IPAM > Prefixes > Import                WS-03 VLANs: one new prefix per VLAN with none; fill
                                                             the prefix column (these rows create, they have no id)
6-access-points.csv  Devices > Devices > Import              WS-06 Wireless: each AP's room, mode and controller
                                                             (cf_ap_mode; cf_wireless_controller: the
                                                             controller's NetBox id)
7-wireless-lans.csv  Wireless > Wireless LANs > Import       WS-06 Wireless: VLAN (by name), security, switching,
                                                             bands (comma-separated, no spaces), guest
                                                             controls (cf_wlan_*); the PSK stays out of this file
8-new-wireless-links.csv  Wireless > Wireless Links > Import WS-06 Wireless: the far radio and SSID of each link
                                                             (these rows create; both radio interfaces must exist)
9-modules.csv        Devices > Modules > Import              WS-02 Network devices: each module's serial
10-inventory-items.csv  Devices > Inventory Items > Import   WS-02 Network devices: PSU, fan and optic serials
11-new-optics.csv    Devices > Inventory Items > Import      WS-04 Links, cables, optics: the transceiver in each
                                                             fiber port (name = part number; these rows create)
12-audit-evidence.csv  Devices > Devices > Import            WS-12 Audit evidence: backup, patch and contract
                                                             dates (YYYY-MM-DD), monitoring and log forwarding
                                                             (values from the list)
13-locations.csv     Devices > Locations > Import            WS-12 Audit evidence: each room's physical access
                                                             and last walk-down date
14-new-owner-contacts.csv  Organization > Contact Assignments > Import   WS-12 Audit evidence: the asset owner
                                                             of each room (or device, by id); fill the contact
                                                             with a name NetBox already has (these rows create)
15-device-models.csv  Devices > Device Types > Import      WS-02 Network devices (models): end of sale and end
                                                             of support (YYYY-MM-DD) and the vendor's notice, once
                                                             per model; every device of the model takes them

Tags are comma-separated slugs; a device keeps the tags already listed and gains
the zone tag you add. Management IPs are not in these files: NetBox sets a device's
primary IP from an address on one of its interfaces (IPAM > IP Addresses > Import,
then the device page), so the drift report lists those devices instead.

Then run netdiagrams again and the drawing follows.
"""


def write(folder: Path, out: dict[str, str]) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in out.items():
        path = folder / name
        path.write_text(text, "utf-8")
        written.append(path)
    if written:
        (folder / "README.txt").write_text(GUIDE, "utf-8")
    return written
