"""Settings: how one NetBox's names map onto the template's.

Real NetBox installs rarely use the template's exact role slugs and field
names. A small JSON object says how they map. It is read in this order, later
wins:

1. the built-in defaults below;
2. ``netdiagrams.json`` next to the drawings (or ``--settings FILE``);
3. a JSON custom field ``netdiagrams`` on the site's region (outermost region
   first), then on its site group;
4. the same field on the NetBox site itself;
5. the command line (``--leave-out``, ``--keep-in``, ``--rename``).

Example::

    {
      "roles": {"core-switch": ["switch-core", "l3-core"], "access-point": ["ap", "wap"]},
      "zone_field": "security_zone",
      "level_field": "purdue_level",
      "sl_field": "sl_target",
      "sw_field": "os_version",
      "gateway_field": "gateway",
      "end_of_support_field": "eos_date",
      "criticality_field": "asset_criticality",
      "status": {"draw": ["active", "staged"], "dashed": ["planned"],
                 "flagged": ["offline", "failed"], "register_only": ["inventory", "decommissioning"]},
      "naming": {"prefix": "S07-", "pattern": "^S\\\\d{2}-[A-Z0-9-]+$"},
      "pages": "-multisite +wireless",
      "logo": "company-logo.png",
      "profile": "manufacturing",
      "audit": {"fields": {"last_config_backup": "backup_date"},
                "days": {"backup": 7, "patch": 30, "verify": 365, "contract_warn": 120}}
    }

``roles`` maps a template role to the NetBox role slugs or names that mean it.
Each ``*_field`` names the NetBox custom field (or a list, first one set wins)
that holds that fact. ``logo`` is an image file (PNG, JPEG, SVG) or URL for
the title blocks' logo box; without one the box is left blank. ``profile`` picks
the industry standard the site is drawn to (``manufacturing`` by default; see
profiles.py). The generic field ``zone`` is not read unless named
here, because it often means a fire, HVAC or building zone. ``audit`` tunes the audit
evidence sheet (see audit.py): ``fields`` names the site's own custom field for any of its
facts (``netbox-setup`` then leaves that field out), ``days`` sets how old a config backup,
patch or verification may get and how far ahead a contract end is flagged.

An unknown key in a settings file is an error (usually a typo in the file you just edited). In a
NetBox ``netdiagrams`` field it is skipped instead, so a region, site group or site can carry its own
keys (e.g. ``{"typical": "BR-S"}``) without breaking the build; doctor's "Settings from" line names them.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

FILE_NAME = "netdiagrams.json"
FIELD = "netdiagrams"

DEFAULTS = {
    "roles": {},
    "zone_field": ["security_zone", "iec62443_zone", "ot_zone"],
    "level_field": ["purdue_level", "purdue"],
    "sl_field": ["security_level_target", "sl_t", "slt"],
    "sw_field": ["sw_version", "os_version", "software_version", "firmware", "firmware_version"],
    "gateway_field": ["gateway"],
    "end_of_support_field": ["end_of_support", "eos_date", "end_of_support_date", "support_expiry"],
    "criticality_field": ["criticality", "asset_criticality", "bia_criticality", "business_criticality"],
    "status": {"draw": ["active", "staged"], "dashed": ["planned"], "flagged": ["offline", "failed"],
               "register_only": ["inventory", "decommissioning"]},
    "naming": {"prefix": "", "pattern": r"^[A-Z]\d{2}-[A-Z0-9]+(-[A-Z0-9]+)*$"},
    "pages": "",
    "logo": "",
    "project": "",
}
# Known but not defaulted, so a site without them is built (and fingerprinted) exactly as before.
OPTIONAL_KEYS = ("profile", "audit")
AUDIT_KEYS = {"fields", "days"}
FIELD_KEYS = ("zone_field", "level_field", "sl_field", "sw_field", "gateway_field", "end_of_support_field",
              "criticality_field")
MERGED_KEYS = ("roles", "status", "naming")  # merged key by key; every other key is replaced


class SettingsError(ValueError):
    pass


def _as_dict(value, source: str, strict: bool = True) -> dict:
    if value in (None, "", {}):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as err:
            raise SettingsError(f"{source} is not valid JSON: {err}") from err
    if not isinstance(value, dict):
        raise SettingsError(f"{source} must be a JSON object")
    unknown = sorted(set(value) - set(DEFAULTS) - set(OPTIONAL_KEYS))
    if unknown and not strict:
        # NetBox fields may carry the site's own keys (e.g. {"typical": ...} on a site group): skip them,
        # and resolve() names them in the sources so doctor shows what was ignored
        value = {k: v for k, v in value.items() if k not in unknown}
        value["_ignored"] = unknown
    elif unknown:
        raise SettingsError(f"{source}: unknown setting(s) {', '.join(unknown)}; "
                            f"known: {', '.join(sorted(set(DEFAULTS) | set(OPTIONAL_KEYS)))}")
    if "profile" in value and not isinstance(value["profile"], str):
        raise SettingsError(f"{source}: profile must be a name, e.g. \"retail\"")
    if "audit" in value:
        _check_audit(value["audit"], source)
    return value


def _check_audit(audit, source: str) -> None:
    from .audit import DAYS, FIELD_NAMES

    if not isinstance(audit, dict) or set(audit) - AUDIT_KEYS:
        raise SettingsError(f"{source}: audit takes \"fields\" and \"days\", e.g. "
                            "{\"days\": {\"backup\": 7}}")
    fields = audit.get("fields") or {}
    if not isinstance(fields, dict) or set(fields) - set(FIELD_NAMES) or \
            any(not isinstance(v, (str, list)) for v in fields.values()):
        raise SettingsError(f"{source}: audit.fields maps one of {', '.join(FIELD_NAMES)} to your field's name")
    days = audit.get("days") or {}
    if not isinstance(days, dict) or set(days) - set(DAYS) or \
            any(not isinstance(v, int) or isinstance(v, bool) or v < 1 for v in days.values()):
        raise SettingsError(f"{source}: audit.days takes whole days (1 or more) for {', '.join(DAYS)}")


def load_file(path: str | Path | None) -> dict:
    if not path:
        return {}
    path = Path(path)
    try:
        cfg = _as_dict(path.read_text("utf-8"), str(path))
    except OSError as err:
        raise SettingsError(f"Can't read {path}: {err}") from err
    logo = cfg.get("logo")
    if isinstance(logo, str) and logo and not logo.startswith(("http://", "https://")) and not Path(logo).is_absolute():
        cfg["logo"] = str(path.parent / logo)  # beside the settings file, wherever the build runs from
    return cfg


def find_file(*folders) -> Path | None:
    for folder in folders:
        if folder is None:
            continue
        candidate = Path(folder) / FILE_NAME
        if candidate.is_file():
            return candidate
    return None


def merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if key in FIELD_KEYS and isinstance(value, str):
            value = [value]
        if key == "roles":
            value = {k: [v] if isinstance(v, str) else list(v) for k, v in (value or {}).items()}
        if key in MERGED_KEYS and isinstance(value, dict):
            out[key] = {**out.get(key, {}), **value}
        elif key == "pages" and out.get("pages") and value:
            out[key] = f"{out['pages']} {value}"
        else:
            out[key] = value
    return out


def resolve(export: dict, file_settings: dict | None = None, file_name: str = "") -> tuple[dict, list[str]]:
    """The settings for one site, and where they came from (for the drift report and doctor)."""
    cfg, sources = copy.deepcopy(DEFAULTS), ["defaults"]

    def named(label: str, found: dict) -> str:  # a source that picks the profile says which
        profile = found.get("profile")
        return f"{label} (profile {profile})" if profile and str(profile) not in label else label

    if file_settings:
        found = _as_dict(file_settings, file_name or FILE_NAME)
        cfg = merge(cfg, found)
        sources.append(named(file_name or FILE_NAME, found))
    layers = [(f"region {r.get('name') or r.get('slug')}", r) for r in reversed(export.get("regions") or [])]
    if export.get("site_group"):
        group = export["site_group"]
        layers.append((f"site group {group.get('name') or group.get('slug')}", group))
    site = export.get("site") or {}
    layers.append((f"site {site.get('name') or site.get('slug') or ''}".strip(), site))
    for label, obj in layers:
        value = (obj.get("custom_fields") or {}).get(FIELD)
        found = _as_dict(value, f"the {FIELD} field on {label}", strict=False)
        ignored = found.pop("_ignored", [])
        if found or ignored:
            cfg = merge(cfg, found)
            note = f"; ignored unknown {', '.join(ignored)}" if ignored else ""
            sources.append(named(f"{FIELD} field on {label}", found) + note)
    return cfg, sources


def role_lookup(cfg: dict) -> dict[str, str]:
    """NetBox role slug or name (lower case) -> template role."""
    out = {}
    for template_role, names in (cfg.get("roles") or {}).items():
        for name in names:
            out[str(name).strip().lower()] = template_role
    return out
