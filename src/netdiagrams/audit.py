"""Audit evidence: who owns each asset, what it is in scope for, and whether it is backed up,
patched, verified, supported, monitored and logged.

Auditors ask the same questions of every asset (IEC 62443-2-1, NIST CSF 2.0 ID.AM and DE.CM,
ISO 27001:2022 A.5.9-A.5.13 and A.8.15-A.8.16, NERC CIP-002/007/010, PCI DSS 4.0 req. 1, 10 and 12.5).
NetBox answers the first with its own objects (a device's tenant, and Contacts assigned with the role
"Asset owner" or "Custodian"); the rest live in optional custom fields that ``netbox-setup`` adds:

=====================  =========================  ==========================================
field                  set on                     what it records
=====================  =========================  ==========================================
compliance_scope       device, room, subnet       PCI CDE, NERC CIP, safety, GxP, HIPAA...
data_classification    device, room, subnet       public, internal, confidential, restricted
physical_access        room, rack                 open, locked cabinet, locked room, badge...
last_config_backup     device                     date of the last good configuration backup
last_patched           device                     date the software was last brought current
last_verified          device, room, site         date someone last checked it against NetBox
support_contract       device                     the contract (text)
support_contract_end   device                     the date the contract ends
install_date           device                     the date it went into service
monitoring             device, room, site         alerting, polling only, passive (IDS or sensor), none
monitored_by           device, site               the monitoring system
log_forwarding         device, room, site         to a SIEM, to a syslog server, local only, none
log_destination        device, site               where the logs go
log_retention_days     device, site               how long the destination keeps them
=====================  =========================  ==========================================

A value set on a room (any NetBox location), a rack, a subnet or the site applies to every device
in it, so a walk-down of a room or a site-wide syslog target is one entry, not one per device; a
value on the device wins. Compliance scope adds up instead: a device is in every scope its room,
its subnet or itself is in. Each field is optional and nothing here is drawn or scored until the
site starts recording it; dates are aged from the day the export is true for.
"""

from __future__ import annotations

import datetime as dt
import html
import ipaddress
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from . import paper
from .model import _get, _label

PAGE_ID = "audit"
SHEET = "3f"
PAGE_NAME = "3f · Audit evidence — owners, scope, backups, patching, monitoring"

CHOICE_SETS = {
    "Compliance scope": [
        ("pci-cde", "PCI DSS cardholder data environment"), ("pci-connected", "PCI DSS connected-to system"),
        ("nerc-cip", "NERC CIP BES Cyber System"), ("safety", "Safety instrumented system (IEC 61511)"),
        ("gxp", "GxP / GDP (FDA 21 CFR Part 11)"), ("hipaa", "HIPAA ePHI"), ("sox", "SOX financial reporting"),
        ("cui", "CMMC / NIST SP 800-171 CUI"), ("ferpa", "FERPA student records"),
        ("glba", "GLBA customer information"), ("cjis", "CJIS criminal justice information")],
    "Data classification": [("public", "Public"), ("internal", "Internal"), ("confidential", "Confidential"),
                            ("restricted", "Restricted")],
    "Physical access": [("open", "Open area"), ("locked-cabinet", "Locked cabinet"), ("locked-room", "Locked room"),
                        ("badge", "Badge access"), ("badge-camera", "Badge and camera")],
    "Monitoring": [("alerting", "Monitored with alerts"), ("polling", "Monitored without alerts"),
                   ("passive", "Passive (IDS or sensor)"), ("none", "Not monitored")],
    "Log forwarding": [("siem", "To a SIEM"), ("syslog", "To a syslog server"), ("local", "Local only"),
                       ("none", "None")],
}
def choices(name: str) -> list[tuple[str, str]]:
    """A choice set as netbox-setup offers it: the industry's own compliance scopes first, then the rest.
    Every choice stays, so a NetBox that serves several industries holds one whole list."""
    from . import profiles
    offered = CHOICE_SETS[name]
    first = [v for v in (profiles.current().scopes if name == "Compliance scope" else ()) if v in dict(offered)]
    return [(v, dict(offered)[v]) for v in first] + [(v, w) for v, w in offered if v not in first]


SHORT = {  # the register's words for each choice
    "pci-cde": "PCI CDE", "pci-connected": "PCI connected", "nerc-cip": "NERC CIP", "safety": "Safety", "gxp": "GxP",
    "hipaa": "HIPAA", "sox": "SOX", "cui": "CUI", "ferpa": "FERPA", "glba": "GLBA", "cjis": "CJIS",
    "open": "Open area", "locked-cabinet": "Locked cabinet", "locked-room": "Locked room", "badge": "Badge",
    "badge-camera": "Badge + camera",
    "alerting": "Alerts on", "polling": "No alerts", "passive": "Passive (IDS or sensor)", "none": "None",
    "siem": "SIEM", "syslog": "Syslog server", "local": "Local only",
}
DEVICE, LOCATION, SITE, PREFIX, RACK = "dcim.device", "dcim.location", "dcim.site", "ipam.prefix", "dcim.rack"
CUSTOM_FIELDS = [  # name, label, group, type, object types, choice set, description
    ("compliance_scope", "Compliance scope", "Audit", "multiselect", f"{DEVICE},{LOCATION},{PREFIX}",
     "Compliance scope", "The regimes this asset is in scope for; a room or subnet in scope puts its devices in"),
    ("data_classification", "Data classification", "Audit", "select", f"{DEVICE},{LOCATION},{PREFIX}",
     "Data classification", "The most sensitive data the asset stores or carries"),
    ("physical_access", "Physical access", "Audit", "select", f"{LOCATION},{RACK}", "Physical access",
     "How the room or cabinet is secured"),
    ("last_config_backup", "Last config backup", "Audit", "date", DEVICE, "",
     "Date of the last good configuration backup"),
    ("last_patched", "Last patched", "Audit", "date", DEVICE, "",
     "Date the software or firmware was last brought current"),
    ("last_verified", "Last verified", "Audit", "date", f"{DEVICE},{LOCATION},{SITE}", "",
     "Date someone last checked the asset (or every asset in the room or site) against NetBox"),
    ("support_contract", "Support contract", "Asset", "text", DEVICE, "", "Vendor support contract and level"),
    ("support_contract_end", "Support contract end", "Audit", "date", DEVICE, "",
     "Date the support contract ends"),
    ("install_date", "Install date", "Audit", "date", DEVICE, "", "Date the asset went into service"),
    ("monitoring", "Monitoring", "Audit", "select", f"{DEVICE},{LOCATION},{SITE}", "Monitoring",
     "Is it monitored, and does a failure raise an alert"),
    ("monitored_by", "Monitored by", "Audit", "text", f"{DEVICE},{SITE}", "",
     "The system that monitors it, by name"),
    ("log_forwarding", "Log forwarding", "Audit", "select", f"{DEVICE},{LOCATION},{SITE}", "Log forwarding",
     "Where the device's logs go"),
    ("log_destination", "Log destination", "Audit", "text", f"{DEVICE},{SITE}", "",
     "The server the logs go to, and how they get there"),
    ("log_retention_days", "Log retention (days)", "Audit", "integer", f"{DEVICE},{SITE}", "",
     "How long the destination keeps the logs"),
]
FIELD_NAMES = tuple(f[0] for f in CUSTOM_FIELDS)
# NetBox rejects a value outside these bounds when it is typed or imported.
VALIDATION = {"log_retention_days": (1, 3650)}
SELECTS = {"compliance_scope": "Compliance scope", "data_classification": "Data classification",
           "physical_access": "Physical access", "monitoring": "Monitoring", "log_forwarding": "Log forwarding"}
DATES = ("last_config_backup", "last_patched", "last_verified", "support_contract_end", "install_date")
CONTACT_ROLES = [["Asset owner", "asset-owner", "Accountable for the asset: approves changes and access, accepts risk"],
                 ["Custodian", "custodian", "Runs the asset day to day on the owner's behalf"]]
OWNER_ROLES = {"asset-owner", "owner", "system-owner", "business-owner", "asset_owner"}
CUSTODIAN_ROLES = {"custodian", "technical-owner", "technical-contact", "administrator", "admin"}
DAYS = {"backup": 30, "patch": 90, "verify": 455, "contract_warn": 90}
# Attributes the drawing carries for the asset (Edit Data, the tooltip) without reporting them as drift:
# evidence dates move every night, and a drawing that never held them does not disagree with NetBox.
QUIET = {f"cf_{n}" for n in FIELD_NAMES} | {"owner", "custodian"}
CLASS_ORDER = ["public", "internal", "confidential", "restricted"]
# A big site's register lists the assets with a finding (and the critical ones) rather than thousands of rows.
MAX_ROWS = 250
# Access points take their configuration and software from their controller or cloud dashboard.
FOLLOWS_CONTROLLER = {"access-point"}


@dataclass
class Value:
    value: object
    where: str = "device"   # device, rack, room, subnet, site, tenant

    @property
    def inherited(self) -> bool:
        return self.where != "device"


@dataclass
class Facts:
    name: str
    id: object
    role: str
    criticality: str = ""
    owner: Value | None = None
    custodian: Value | None = None
    scope: list[str] = field(default_factory=list)       # choice values, every source added up
    scope_from: list[str] = field(default_factory=list)  # where each came from
    classification: Value | None = None
    access: Value | None = None
    backup: Value | None = None
    patched: Value | None = None
    verified: Value | None = None
    contract: str = ""
    contract_end: str = ""
    installed: str = ""
    monitoring: Value | None = None
    monitored_by: Value | None = None
    logs: Value | None = None
    log_destination: Value | None = None
    retention: Value | None = None
    has_location: bool = False


def _value(raw):
    """A custom field's value as NetBox's API gives it: a string, a list, a {value, label} or an object."""
    if isinstance(raw, dict):
        return raw.get("value") or raw.get("slug") or raw.get("name") or raw.get("label") or ""
    if isinstance(raw, list):
        return [v for v in (_value(x) for x in raw) if v]
    return raw


def _empty(value) -> bool:
    return value in (None, "", [], {})


def date_of(value) -> dt.date | None:
    try:
        return dt.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()  # the same on every Python
    except (TypeError, ValueError):
        return None


def label(value) -> str:
    """The register's word for a choice value (unknown values as NetBox holds them)."""
    if isinstance(value, list):
        return " · ".join(label(v) for v in value)
    text = str(value or "")
    if text == "passive":   # a plant's passive monitoring is an OT IDS; elsewhere an IDS or sensor
        from . import profiles
        return "Passive (OT IDS)" if profiles.current().levels else SHORT[text]
    if text in SHORT:
        return SHORT[text]
    for choices in CHOICE_SETS.values():
        for v, words in choices:
            if v == text:
                return words
    return text.replace("-", " ").capitalize() if text.islower() else text


def scope_title(value: str) -> str:
    return next((words for v, words in CHOICE_SETS["Compliance scope"] if v == value), label(value))


class Evidence:
    """Every device's audit facts, from the device, its rack, its room chain, its subnet and the site."""

    def __init__(self, export: dict, settings: dict | None = None, endpoint_roles: set[str] | None = None):
        cfg = (settings or {}).get("audit") or {}
        own = cfg.get("fields") or {}
        self.names = {n: ([own[n]] if isinstance(own.get(n), str) else list(own.get(n) or [])) + [n]
                      for n in FIELD_NAMES}
        days = cfg.get("days") or {}
        self.days = {k: int(days.get(k, v)) for k, v in DAYS.items()}
        self.endpoint_roles = set(endpoint_roles or ())
        self.site = export.get("site") or {}
        self.used: set[str] = set()
        locations = export.get("locations") or []
        self._loc = {}
        for loc in locations:
            for key in ("id", "slug", "name"):
                if loc.get(key) not in (None, ""):
                    self._loc.setdefault((key, loc[key]), loc)
        self._racks = {}
        for r in export.get("racks") or []:
            for key in ("id", "name"):
                if r.get(key) not in (None, ""):
                    self._racks.setdefault((key, r[key]), r)
        self._contacts = self._read_contacts(export.get("contact_assignments") or [])
        self._prefixes = []
        for p in export.get("prefixes") or []:
            if any(not _empty(self.cf(p, n)) for n in ("compliance_scope", "data_classification")):
                try:
                    self._prefixes.append((ipaddress.ip_network(p.get("prefix", ""), strict=False), p))
                except ValueError:
                    continue
        self._prefixes.sort(key=lambda np: -np[0].prefixlen)   # the most specific first
        for obj in [self.site, *locations, *(export.get("racks") or []), *(export.get("prefixes") or [])]:
            self.used.update(n for n in FIELD_NAMES if not _empty(self.cf(obj, n)))
        self._objects = [("site", self.site.get("name") or "site", self.site)] \
            + [("room", o.get("name") or "?", o) for o in locations] \
            + [("rack", o.get("name") or "?", o) for o in export.get("racks") or []] \
            + [("subnet", o.get("prefix") or "?", o) for o in export.get("prefixes") or []] \
            + [("device", o.get("name"), o) for o in export.get("devices") or [] if o.get("name")]
        self.devices: dict[str, Facts] = {}
        for d in export.get("devices") or []:
            if d.get("name"):
                self.devices[d["name"]] = self._facts(d)
        if self._contacts or any(f.owner for f in self.devices.values()):
            self.used.add("owner")

    # reading -------------------------------------------------------------
    def cf(self, obj: dict | None, name: str):
        fields = (obj or {}).get("custom_fields") or {}
        for n in self.names.get(name, [name]):
            value = _value(fields.get(n))
            if not _empty(value):
                return value
        return None

    @staticmethod
    def _read_contacts(assignments: list[dict]) -> dict[tuple[str, object], dict[str, list[str]]]:
        out: dict[tuple[str, object], dict[str, list[tuple[int, str]]]] = {}
        for a in assignments:
            kind = a.get("object_type") or a.get("content_type") or ""
            if isinstance(kind, dict):
                kind = f"{kind.get('app_label', '')}.{kind.get('model', '')}"
            role = (_get(a, "role", "slug") or _get(a, "role", "name")).lower()
            which = "owner" if role in OWNER_ROLES else "custodian" if role in CUSTODIAN_ROLES else ""
            name = _label(a.get("contact"))
            if not which or not name:
                continue
            order = {"primary": 0, "secondary": 1, "tertiary": 2, "inactive": 9}.get(
                _get(a, "priority", "value") or str(a.get("priority") or ""), 5)
            out.setdefault((kind, a.get("object_id")), {}).setdefault(which, []).append((order, name))
        return {k: {w: [n for _, n in sorted(v)] for w, v in roles.items()} for k, roles in out.items()}

    def _location(self, ref: dict | None) -> dict | None:
        if not ref:
            return None
        for key in ("id", "slug", "name"):
            if ref.get(key) not in (None, "") and (key, ref[key]) in self._loc:
                return self._loc[(key, ref[key])]
        return ref

    def chain(self, ref: dict | None) -> list[dict]:
        out, seen, loc = [], set(), self._location(ref)
        while loc and id(loc) not in seen and len(out) < 20:
            seen.add(id(loc))
            out.append(loc)
            loc = self._location(loc.get("parent")) if loc.get("parent") else None
        return out

    def _rack(self, ref: dict | None) -> dict | None:
        if not ref:
            return None
        for key in ("id", "name"):
            if ref.get(key) not in (None, "") and (key, ref[key]) in self._racks:
                return self._racks[(key, ref[key])]
        return None

    def _prefix(self, d: dict) -> dict | None:
        address = _get(d, "primary_ip4", "address")
        if not address or not self._prefixes:
            return None
        try:
            ip = ipaddress.ip_interface(address).ip
        except ValueError:
            return None
        return next((p for net, p in self._prefixes if ip in net), None)

    def _first(self, name: str, sources: list[tuple[str, dict | None]]) -> Value | None:
        for where, obj in sources:
            value = self.cf(obj, name)
            if not _empty(value):
                self.used.add(name)
                return Value(value, where)
        return None

    def _contact(self, which: str, places: list[tuple[str, str, object]]) -> Value | None:
        for where, kind, ident in places:
            names = (self._contacts.get((kind, ident)) or {}).get(which)
            if names:
                return Value(names[0], where)
        return None

    def _facts(self, d: dict) -> Facts:
        role = _get(d, "role", "slug")
        f = Facts(d["name"], d.get("id"), role, criticality=str(self.cf(d, "criticality") or
                                                              ((d.get("custom_fields") or {}).get("criticality")) or ""))
        rooms = self.chain(d.get("location"))
        rack = self._rack(d.get("rack"))
        prefix = self._prefix(d)
        f.has_location = bool(rooms or d.get("rack"))
        here = [("device", d)]
        room = [("room", loc) for loc in rooms]
        site = [("site", self.site)]
        places = [("device", DEVICE, d.get("id"))] + ([("rack", RACK, rack.get("id"))] if rack else []) \
            + [("room", LOCATION, loc.get("id")) for loc in rooms if loc.get("id") is not None] \
            + [("site", SITE, self.site.get("id") or _get(d, "site", "id", default=None))]
        f.owner = self._contact("owner", places)
        if f.owner is None and _label(d.get("tenant")):
            f.owner = Value(_label(d.get("tenant")), "tenant")
        f.custodian = self._contact("custodian", places)
        for where, obj in here + room + [("subnet", prefix)]:
            value = self.cf(obj, "compliance_scope")
            if _empty(value):
                continue
            self.used.add("compliance_scope")
            for v in (value if isinstance(value, list) else [value]):
                if v not in f.scope:
                    f.scope.append(v)
                    f.scope_from.append(where)
        found = [Value(v, w) for w, obj in here + room + [("subnet", prefix)]
                 for v in [self.cf(obj, "data_classification")] if not _empty(v)]
        if found:
            self.used.add("data_classification")
            own = next((x for x in found if x.where == "device"), None)
            rank = lambda x: CLASS_ORDER.index(x.value) if x.value in CLASS_ORDER else -1
            f.classification = own or max(found, key=rank)
        f.access = self._first("physical_access", ([("rack", rack)] if rack else []) + room)
        f.backup = self._first("last_config_backup", here)
        f.patched = self._first("last_patched", here)
        f.verified = self._first("last_verified", here + room + site)
        f.contract = str(self.cf(d, "support_contract") or "")
        f.contract_end = str(self.cf(d, "support_contract_end") or "")[:10]
        f.installed = str(self.cf(d, "install_date") or "")[:10]
        for name in ("support_contract_end", "install_date"):
            if not _empty(self.cf(d, name)):
                self.used.add(name)
        f.monitoring = self._first("monitoring", here + room + site)
        f.monitored_by = self._first("monitored_by", here + site)
        f.logs = self._first("log_forwarding", here + room + site)
        f.log_destination = self._first("log_destination", here + site)
        f.retention = self._first("log_retention_days", here + site)
        return f

    # questions -----------------------------------------------------------
    @property
    def any(self) -> bool:
        """The site records some audit evidence: the sheet is drawn and the checks are scored."""
        return bool(self.used - {"support_contract"})

    def network(self, f: Facts) -> bool:
        return f.role not in self.endpoint_roles

    def watched(self) -> list[Facts]:
        """Devices the monitoring and logging checks apply to: network gear, plus the end devices the
        profile names (a store's POS server); a PLC that keeps local logs is not a finding."""
        from . import profiles
        extra = set(profiles.current().watched_roles)
        return [f for f in self.devices.values() if self.network(f) or f.role in extra]

    @staticmethod
    def age(value: Value | None, as_of: str) -> int | None:
        when, today = date_of(value.value if value else None), date_of(as_of)
        if when is None or today is None:
            return None
        return (today - when).days

    def stale(self, value: Value | None, limit: int, as_of: str) -> bool:
        """Missing, unreadable, or older than ``limit`` days on ``as_of``."""
        if value is None or date_of(value.value) is None:
            return True
        age = self.age(value, as_of)
        # A date in the future is a typo (2062 for 2026), not fresh evidence; a day's slack covers time zones.
        return age is not None and (age > limit or age < -1)

    def contract_state(self, f: Facts, as_of: str) -> str:
        """'' (no end date), 'ended', 'ending' (inside the warning window) or 'current'."""
        end, today = date_of(f.contract_end), date_of(as_of)
        if end is None or today is None:
            return ""
        if end < today:
            return "ended"
        return "ending" if (end - today).days <= self.days["contract_warn"] else "current"

    def checks(self, as_of: str) -> dict[str, tuple[list[str], int]]:
        """check key -> (devices failing it, devices it applies to). A check on a field the site does not
        record yet applies to nothing (listed, not scored), so adopting the module never costs points
        until it is in use."""
        devs = list(self.devices.values())
        configured = [f for f in devs if f.role not in FOLLOWS_CONTROLLER]
        located = [f for f in devs if f.has_location]
        ended = [f for f in devs if f.contract_end]
        d = self.days
        rows = {
            "no_owner": (devs, "owner", lambda f: f.owner is None),
            "stale_backup": (configured, "last_config_backup", lambda f: self.stale(f.backup, d["backup"], as_of)),
            "stale_patch": (configured, "last_patched", lambda f: self.stale(f.patched, d["patch"], as_of)),
            "stale_verified": (devs, "last_verified", lambda f: self.stale(f.verified, d["verify"], as_of)),
            "support_ended": (ended, "support_contract_end", lambda f: self.contract_state(f, as_of) == "ended"),
            "not_monitored": (self.watched(), "monitoring", lambda f: f.monitoring is None or f.monitoring.value == "none"),
            "no_log_forwarding": (self.watched(), "log_forwarding",
                                  lambda f: f.logs is None or f.logs.value in ("none", "local")),
            "no_physical_access": (located, "physical_access", lambda f: f.access is None),
        }
        out = {}
        for key, (applies, name, failing) in rows.items():
            out[key] = ([f.name for f in applies if failing(f)], len(applies) if name in self.used else 0)
        out["audit_bad_values"] = self.values()
        return out

    def values(self) -> tuple[list[str], int]:
        """('<object> <field> = <value>' for every recorded audit value off its list, not a date or out of
        bounds; how many values were recorded). NetBox's own dropdowns and date fields keep these clean;
        they come from a field of the site's own (settings audit.fields), an old choice or an import."""
        allowed = {f: {v for v, _ in CHOICE_SETS[c]} for f, c in SELECTS.items()}
        bad, count = [], 0
        for kind, name, obj in self._objects:
            for f in [*SELECTS, *DATES, *VALIDATION]:
                value = self.cf(obj, f)
                if _empty(value):
                    continue
                count += 1
                if f in SELECTS:
                    wrong = [v for v in (value if isinstance(value, list) else [value]) if v not in allowed[f]]
                    ok = not wrong
                elif f in DATES:
                    ok, wrong = date_of(value) is not None and len(str(value)) >= 10, value
                else:
                    try:
                        low, high = VALIDATION[f]
                        ok, wrong = low <= int(value) <= high, value
                    except (TypeError, ValueError):
                        ok, wrong = False, value
                if not ok:
                    shown = ", ".join(map(str, wrong)) if isinstance(wrong, list) else str(wrong)
                    bad.append(f"{name} {f} = {shown}")
        return bad, count

    def site_value(self, name: str):
        return self.cf(self.site, name)


def gap_texts(days: dict[str, int]) -> dict[str, tuple[str, str, str]]:
    """check key -> (what, how to close it, where it goes in NetBox)."""
    months = round(days["verify"] / 30.4)
    return {
        "no_owner": ("Devices without an owner",
                     "Name who is accountable for it (asset owner) and who runs it day to day (custodian); "
                     "set once on the room or site for everything in it",
                     "Device, room or site ▸ Contacts (role Asset owner)"),
        "stale_backup": (f"Devices with no config backup in {days['backup']} days",
                         "Record the date of the last good backup from the backup tool's job log; "
                         "fix the job for any device it misses",
                         "Device ▸ Last config backup (custom field)"),
        "stale_patch": (f"Devices not patched in {days['patch']} days",
                        "Patch, or record the date the vendor's advisories were last checked and applied",
                        "Device ▸ Last patched (custom field)"),
        "stale_verified": (f"Devices not verified in {months} months",
                           "Walk the room against the drawing and record the date on the room: "
                           "it covers every device in it",
                           "Room or site ▸ Last verified (custom field)"),
        "support_ended": ("Support contracts that have ended", "Renew it, or record the replacement plan",
                          "Device ▸ Support contract end (custom field)"),
        "not_monitored": ("Devices not monitored",
                          "Add it to the monitoring system with alerting on, then record it "
                          "(a site-wide value covers every device)",
                          "Device or site ▸ Monitoring (custom field)"),
        "no_log_forwarding": ("Devices not sending their logs off the box",
                              "Point syslog at the SIEM or log server and record where",
                              "Device or site ▸ Log forwarding (custom field)"),
        "audit_bad_values": ("Audit fields holding a value off their list",
                             "Pick the value from the field's list, or write the date as YYYY-MM-DD; an old choice or "
                             "an import from a spreadsheet usually brings these",
                             "The object and field named on each line"),
        "no_physical_access": ("Devices in rooms with no physical access control recorded",
                               "Record how each room or cabinet is secured: open, locked cabinet, locked room, "
                               "badge, badge and camera",
                               "Room or rack ▸ Physical access (custom field)"),
    }


CHECK_KEYS = tuple(gap_texts(DAYS))


# ----------------------------------------------------------------------- sheet
GREEN, AMBER, RED, MUTED, PURPLE = "#059669", "#B45309", "#B91C1C", "#94A3B8", "#6D28D9"


def _span(text: str, color: str = "", bold: bool = False, italic: bool = False, size: int = 0) -> str:
    style = (f"color:{color};" if color else "") + ("font-weight:bold;" if bold else "") \
        + ("font-style:italic;" if italic else "") + (f"font-size:{size}px;" if size else "")
    return f'<span style="{style}">{html.escape(text)}</span>' if style else html.escape(text)


def _shown(v: Value | None, words=None) -> str:
    if v is None:
        return ""
    text = words(v.value) if words else label(v.value)
    return _span(text, italic=v.inherited)


def _date_cell(ev: Evidence, v: Value | None, limit: int, as_of: str, applies: bool, used: bool) -> str:
    if not applies:
        return _span("from controller", MUTED)
    if v is None:
        return _span("none", RED, bold=True) if used else _span("—", MUTED)
    age = ev.age(v, as_of)
    if age is None:
        return _span(str(v.value), AMBER)
    if age < -1:
        return _span(f"{str(v.value)[:10]} · in the future", AMBER, italic=v.inherited)
    text = f"{str(v.value)[:10]} · {age:,} d" if age >= 0 else str(v.value)[:10]
    color = AMBER if age > limit else ""
    return _span(text, color, italic=v.inherited)


def _owner_cell(f: Facts, used: bool) -> str:
    if f.owner is None:
        out = _span("none", RED, bold=True) if used else _span("—", MUTED)
    else:
        out = _span(str(f.owner.value) + (" (tenant)" if f.owner.where == "tenant" else ""), italic=f.owner.inherited)
    if f.custodian is not None:
        out += "<br>" + _span(f"custodian {f.custodian.value}", "#64748B", size=9)
    return out


def _support_cell(ev: Evidence, f: Facts, as_of: str) -> str:
    state = ev.contract_state(f, as_of)
    contract = html.escape(f.contract)
    if state == "ended":
        end = _span(f"ended {f.contract_end}", RED, bold=True)
    elif state == "ending":
        end = _span(f"ends {f.contract_end}", AMBER, bold=True)
    elif state == "current":
        end = _span(f"to {f.contract_end}", "#475569")
    else:
        end = ""
    return " · ".join(x for x in (contract, end) if x) or _span("—", MUTED)


def _monitor_cell(ev: Evidence, f: Facts) -> str:
    if not ev.network(f) and f.monitoring is None:
        return _span("—", MUTED)
    v = f.monitoring
    if v is None:
        return _span("none", RED, bold=True) if "monitoring" in ev.used else _span("—", MUTED)
    color = RED if v.value == "none" else AMBER if v.value == "polling" else ""
    out = _span(label(v.value), color, bold=v.value == "none", italic=v.inherited)
    site = ev.site_value("monitored_by")
    if f.monitored_by is not None and (f.monitored_by.where == "device" or not site) and v.value != "none":
        out += "<br>" + _span(str(f.monitored_by.value), "#64748B", size=9)
    return out


def _logs_cell(ev: Evidence, f: Facts) -> str:
    if not ev.network(f) and f.logs is None:
        return _span("—", MUTED)
    v = f.logs
    if v is None:
        return _span("none", RED, bold=True) if "log_forwarding" in ev.used else _span("—", MUTED)
    weak = v.value in ("none", "local")
    flagged = weak and ev.network(f)   # a PLC or drive keeping its own log is normal; a switch doing so is not
    out = _span(label(v.value), RED if flagged else "#64748B" if weak else "", bold=flagged, italic=v.inherited)
    site = ev.site_value("log_destination")
    if f.log_destination is not None and (f.log_destination.where == "device" or not site) and not weak:
        out += "<br>" + _span(str(f.log_destination.value), "#64748B", size=9)
    return out


def _access_cell(f: Facts, used: bool) -> str:
    if f.access is None:
        if not f.has_location:
            return _span("—", MUTED)
        return _span("none", RED, bold=True) if used else _span("—", MUTED)
    return _span(label(f.access.value), AMBER if f.access.value == "open" else "", italic=f.access.inherited)


def _crit_cell(level: str) -> str:
    if not level:
        return _span("—", MUTED)
    return _span(level.capitalize(), RED, bold=True) if level.lower() == "critical" else html.escape(level.capitalize())


def _tile(fraction: float | None) -> str:
    return MUTED if fraction is None else GREEN if fraction >= 0.95 else "#D97706" if fraction >= 0.7 else "#DC2626"


def page(ev: Evidence, export: dict, as_of: str, zone_of, link=None, revision: str = "") -> ET.Element:
    """Sheet 3f as a <diagram>; the caller adds the title block."""
    from . import drawio, graph as graph_mod, quality
    from .drawio import MARGIN, PAGE_W, TEXT, Page

    p = Page(PAGE_ID, PAGE_NAME)
    l_title, l_tiles, l_site, l_table = (p.layer("Titles"), p.layer("Readiness"), p.layer("Site evidence"),
                                         p.layer("Asset evidence register"))
    d = ev.days
    site_name = ev.site.get("name") or ev.site.get("slug") or "Site"
    when = f"NetBox as of {as_of}" if as_of else "NetBox"
    drawio._title(p, l_title, f"{site_name} — Audit evidence",
                  f"Who owns each asset, what it is in scope for, and whether it is backed up, patched, verified, "
                  f"supported, monitored and logged, from {when}" + (f". Rev {revision}." if revision else "."))
    checks = ev.checks(as_of)

    # Readiness tiles: one per check, the share of assets that pass.
    from . import profiles
    watched_unit = "devices" if profiles.current().watched_roles else "network devices"
    tiles = [("Owner recorded", "no_owner", "assets"), (f"Config backup ≤ {d['backup']} d", "stale_backup", "assets"),
             (f"Patched ≤ {d['patch']} d", "stale_patch", "assets"),
             (f"Verified ≤ {round(d['verify'] / 30.4)} months", "stale_verified", "assets"),
             ("Support in contract", "support_ended", "contracts"), ("Monitored", "not_monitored", watched_unit),
             ("Logs sent off the box", "no_log_forwarding", watched_unit),
             ("Room access recorded", "no_physical_access", "located assets")]
    tile_w = (PAGE_W - 2 * MARGIN - 16 * (len(tiles) - 1)) / len(tiles)
    y = 100
    for i, (title, key, unit) in enumerate(tiles):
        failing, total = checks[key]
        fraction = None if total <= 0 else max(0.0, 1 - len(failing) / total)
        big = "—" if fraction is None else f"{quality.pct(fraction)}"
        note = "not recorded at this site yet" if fraction is None else f"{total - len(failing):,} of {total:,} {unit}"
        p.box(l_tiles, MARGIN + i * (tile_w + 16), y, tile_w, 92,
              f'<span style="font-size:11px;color:#64748B">{html.escape(title)}</span><br>'
              f'<span style="font-size:30px;font-weight:bold;color:{_tile(fraction)}">{big}'
              f'<span style="font-size:14px;color:#94A3B8">{"" if fraction is None else "%"}</span></span><br>'
              f'<span style="font-size:9px;color:#64748B">{html.escape(note)}</span>', quality.TILE)
    y += 92 + 20

    # Site evidence: who owns what, what is in scope, how the site is monitored and where its logs go.
    devs = list(ev.devices.values())
    owners: dict[str, int] = {}
    for f in devs:
        if f.owner is not None:
            owners[str(f.owner.value)] = owners.get(str(f.owner.value), 0) + 1
    top = sorted(owners.items(), key=lambda kv: (-kv[1], kv[0]))
    owned = "<br>".join(f"{html.escape(n)} · {c:,} asset{'' if c == 1 else 's'}" for n, c in top[:4]) or \
        _span("No owner recorded yet: assign a contact with the role Asset owner to the site, a room or a device.",
              "#64748B")
    if len(top) > 4:
        owned += f"<br>{_span(f'and {len(top) - 4} more', '#64748B')}"
    scopes: dict[str, int] = {}
    for f in devs:
        for s in f.scope:
            scopes[s] = scopes.get(s, 0) + 1
    scoped = "<br>".join(f"{_span(scope_title(s), PURPLE, bold=True)} · {c:,} asset{'' if c == 1 else 's'}"
                         for s, c in sorted(scopes.items(), key=lambda kv: (-kv[1], kv[0]))) or \
        _span("No asset is recorded as in a compliance scope (PCI, NERC CIP, safety, GxP...).", "#64748B")
    watched = logged = ev.watched()
    monitored = [f for f in watched if f.monitoring is not None and f.monitoring.value != "none"]
    alerting = [f for f in watched if f.monitoring is not None and f.monitoring.value in ("alerting", "passive")]
    system = ev.site_value("monitored_by")
    watch = (f"{_span(str(system), bold=True)}<br>" if system else "") + (
        f"{len(monitored):,} of {len(watched):,} {watched_unit} monitored, {len(alerting):,} with alerts"
        + (" or passive monitoring" if any(f.monitoring.value == "passive" for f in alerting) else "")
        if "monitoring" in ev.used else _span("Not recorded yet: set Monitoring on the site, then the exceptions "
                                              "on the devices.", "#64748B"))
    forwarded = [f for f in logged if f.logs is not None and f.logs.value in ("siem", "syslog")]
    target, keep = ev.site_value("log_destination"), ev.site_value("log_retention_days")
    kept = ""
    if keep not in (None, ""):
        try:
            days_kept = int(keep)
            kept = _span(f"kept {days_kept:,} days", AMBER if days_kept < 365 else "")
        except (TypeError, ValueError):
            kept = html.escape(str(keep))
    logs = (f"{_span(str(target), bold=True)}" + (f" · {kept}" if kept else "") + "<br>" if target or kept else "") + (
        f"{len(forwarded):,} of {len(logged):,} {watched_unit} send their logs off the box"
        if "log_forwarding" in ev.used else _span("Not recorded yet: set Log forwarding and Log destination on the "
                                                  "site.", "#64748B"))
    cards = [("Ownership", owned), ("Compliance scope", scoped), ("Monitoring", watch), ("Logging", logs)]
    card_w = (PAGE_W - 2 * MARGIN - 16 * (len(cards) - 1)) / len(cards)
    card_h = 108
    for i, (title, body) in enumerate(cards):
        p.box(l_site, MARGIN + i * (card_w + 16), y, card_w, card_h,
              f'<span style="font-size:11px;color:#64748B">{html.escape(title)}</span><br>'
              f'<span style="font-size:11px;color:#0F172A">{body}</span>', quality.TILE)
    y += card_h + 24

    # The register: every asset, by zone, most critical first.
    columns = [("ASSET", 196), ("CRIT", 64), ("OWNER", 170), ("SCOPE", 118), ("DATA", 90), ("ROOM ACCESS", 112),
               ("CONFIG BACKUP", 122), ("PATCHED", 122), ("VERIFIED", 122), ("SUPPORT", 214), ("INSTALLED", 86),
               ("MONITORING", 140)]
    columns.append(("LOGS", PAGE_W - 2 * MARGIN - sum(w for _, w in columns)))
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    devices = {d["name"]: d for d in export.get("devices") or [] if d.get("name")}

    def register(listed: list[Facts]) -> list[list[str]]:
        by_zone: dict[str, list[Facts]] = {}
        for f in listed:
            zones = zone_of(devices[f.name]) if f.name in devices else []
            by_zone.setdefault(zones[0] if zones else "", []).append(f)
        rows = []
        for zone in sorted(by_zone, key=lambda z: (z == "", z)):
            members = sorted(by_zone[zone], key=lambda f: (rank.get(f.criticality.lower(), 4), f.name))
            title = (zone.upper().replace("ZONE-", "") or "NO ZONE") + f" · {len(members):,} asset{'' if len(members) == 1 else 's'}"
            rows.append([f'<b style="color:#4338CA">{html.escape(title)}</b>'] + [""] * (len(columns) - 1))
            for f in members:
                name = html.escape(f.name)
                url = link(f) if link else ""
                if url:
                    name = f'<a href="{html.escape(url)}">{name}</a>'
                configured = f.role not in FOLLOWS_CONTROLLER
                scope = " · ".join(_span(SHORT.get(s, label(s)), PURPLE, bold=True, italic=w != "device")
                                   for s, w in zip(f.scope, f.scope_from)) or _span("—", MUTED)
                rows.append([
                    name, _crit_cell(f.criticality), _owner_cell(f, "owner" in ev.used), scope,
                    _shown(f.classification) or _span("—", MUTED), _access_cell(f, "physical_access" in ev.used),
                    _date_cell(ev, f.backup, d["backup"], as_of, configured, "last_config_backup" in ev.used),
                    _date_cell(ev, f.patched, d["patch"], as_of, configured, "last_patched" in ev.used),
                    _date_cell(ev, f.verified, d["verify"], as_of, True, "last_verified" in ev.used),
                    _support_cell(ev, f, as_of), html.escape(f.installed) or _span("—", MUTED),
                    _monitor_cell(ev, f), _logs_cell(ev, f)])
        return rows

    def height(rows: list[list[str]]) -> float:
        return 20 + sum(graph_mod.row_height([(v, w - 4) for (_, w), v in zip(columns, row)], size=10, base=22)
                        for row in rows)

    # The sheet stays within the tallest paper: past it, the assets with a finding and the critical ones
    # come first, and the worksheets list every one.
    room = paper.SIZES[-1][2] - 40 - (y + 28) - 20 - 56 - 24 - 110  # the notes and the title block under the table
    listed = devs
    rows = register(listed)
    heading = "<b>Every asset</b>"
    if len(devs) > MAX_ROWS or height(rows) > room:
        flagged = {n for key, (names, _) in checks.items() if key != "audit_bad_values" for n in names}
        listed = [f for f in devs if f.name in flagged or f.criticality.lower() == "critical"]
        listed = sorted(listed, key=lambda f: (f.name not in flagged, f.criticality.lower() != "critical", f.name))
        shown, listed = len(listed), listed[:MAX_ROWS]
        rows = register(listed)
        while len(listed) > 1 and height(rows) > room:
            listed = listed[:max(1, int(len(listed) * 0.9))]
            rows = register(listed)
        rest = (f"the first {len(listed):,} of {shown:,} shown; the worksheets list every one" if shown > len(listed)
                else f"the other {len(devs) - shown:,} pass every check")
        heading = f"<b>Assets with a finding, and the critical ones</b> ({len(listed):,} of {len(devs):,} assets; {rest})"
    p.box(l_table, MARGIN, y, PAGE_W - 2 * MARGIN, 22,
          heading + " · by zone, most critical first · <i>italic</i> = set on the room, rack, subnet or "
          "site and inherited · amber = past its limit or weak · red = missing or failed",
          TEXT + "fontSize=11;fontColor=#0F172A;")
    y = quality._table(p, l_table, MARGIN, y + 28, columns, rows) + 20
    p.box(l_title, MARGIN, y, PAGE_W - 2 * MARGIN, 56,
          "<b>How to read this sheet.</b> Owners and custodians are NetBox contacts (roles Asset owner and Custodian) "
          "on the device, its rack, its room or the site, or else the device's tenant. Every other column is an "
          "optional custom field <i>netdiagrams netbox-setup</i> adds: compliance_scope and data_classification "
          "(device, room or subnet), physical_access (room or rack), last_config_backup, last_patched, "
          "support_contract_end and install_date (device), last_verified, monitoring and log_forwarding (device, "
          "room or site), monitored_by, log_destination and log_retention_days (device or site). "
          f"Ages count from {html.escape(as_of or 'the build date')}; limits are backup {d['backup']} days, patch "
          f"{d['patch']} days, verification {d['verify']} days and a contract warning {d['contract_warn']} days "
          "ahead (settings: audit.days). Access points take their configuration from their controller.",
          TEXT + "fontSize=10;fontColor=#475569;")
    p.height = y + 56 + 24
    return p.element()


def wanted(export: dict, settings: dict | None = None) -> bool:
    return Evidence(export, settings).any
