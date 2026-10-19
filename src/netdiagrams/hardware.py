"""Modules, module bays and inventory items from NetBox.

NetBox records what sits inside a device: line cards and uplink modules in module
bays (``dcim.module``), and the inventory items a ``show inventory`` lists: power
supplies, fans, transceivers, SD cards (``dcim.inventoryitem``). This module reads
them from an export and answers the questions the hardware sheet asks: which optic is
in a port, what powers a switch, which bays are empty, and what is missing a serial.

Only the data lives here; the sheet's registers are drawn by ``sync``.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .model import _get

# An inventory item's kind, from its role first and its part number or name second.
ROLE_KINDS = (("transceiver", "optic"), ("optic", "optic"), ("sfp", "optic"), ("psu", "power"),
              ("power", "power"), ("fan", "fan"))
PART_KINDS = ((re.compile(r"^(SFP|QSFP|GLC|SFP28|QSFP28|X2|XFP|CFP|OSFP|CWDM|DWDM)[-+]|^J\d{4}[A-Z]\b", re.I), "optic"),
              (re.compile(r"PWR|PSU|power", re.I), "power"),
              (re.compile(r"FAN", re.I), "fan"))
FIBRE = ("smf", "mmf")   # cable types that need a transceiver at each end
OPTIC_PREFIX = re.compile(r"^(?:SFP28|QSFP28|QSFP|SFP|GLC|X2|XFP)(?:\+|-\d+G)?-", re.I)


def kind_of(item: dict) -> str:
    """'optic', 'power', 'fan' or 'other' for an inventory item."""
    role = (_get(item, "role", "slug") + " " + _get(item, "role", "name")).lower()
    for word, kind in ROLE_KINDS:
        if word in role:
            return kind
    if item.get("component_type") == "dcim.interface" and item.get("component"):
        return "optic"
    text = f"{item.get('part_id') or ''} {item.get('name') or ''}"
    for pattern, kind in PART_KINDS:
        if pattern.search(text):
            return kind
    return "other"


def part(item: dict) -> str:
    """What to call an item: its part number, else its name."""
    return item.get("part_id") or item.get("name") or ""


def short_optic(part_number: str) -> str:
    """The code a port cell shows: 'SR' for SFP-10G-SR-S, 'TE' for GLC-TE, 'LR' for SFP-10G-LR-S."""
    code = OPTIC_PREFIX.sub("", part_number or "")
    return re.sub(r"-S$", "", code) or part_number


def module_model(module: dict) -> str:
    return _get(module, "module_type", "model") or _get(module, "module_type", "part_number") or "module"


def counted(parts: list[str]) -> str:
    """'2× PWR-C1-350WAC-P · FAN-T1' for a list of part numbers."""
    counts = Counter(p for p in parts if p)
    return " · ".join(f"{n}× {p}" if n > 1 else p for p, n in counts.items())


class Hardware:
    """Everything NetBox records inside the site's devices, by device name."""

    def __init__(self, export: dict):
        names = {d.get("id"): d.get("name") for d in export.get("devices", [])}

        def device(obj: dict) -> str:
            d = obj.get("device") or {}
            return d.get("name") or names.get(d.get("id")) or ""

        self.modules: dict[str, list[dict]] = defaultdict(list)
        self.bays: dict[str, list[dict]] = defaultdict(list)
        self.items: dict[str, list[dict]] = defaultdict(list)
        self.optics: dict[tuple[str, str], dict] = {}
        for m in export.get("modules") or []:
            self.modules[device(m)].append(m)
        for b in export.get("module_bays") or []:
            self.bays[device(b)].append(b)
        for item in export.get("inventory_items") or []:
            dev = device(item)
            self.items[dev].append(item)
            if kind_of(item) == "optic" and item.get("component_type") == "dcim.interface":
                port = (item.get("component") or {}).get("name")
                if port:
                    self.optics.setdefault((dev, port), item)
        self.recorded = bool(self.modules or self.bays or self.items)

    def of_kind(self, devices: list[str], kind: str) -> list[dict]:
        return [i for d in devices for i in self.items.get(d, []) if kind_of(i) == kind]

    def power(self, devices: list[str]) -> str:
        return counted([part(i) for i in self.of_kind(devices, "power")])

    def fans(self, devices: list[str]) -> str:
        return counted([part(i) for i in self.of_kind(devices, "fan")])

    def other(self, devices: list[str]) -> str:
        """Items that are not power, fans or optics: SD cards, stack cables, licences."""
        return counted([part(i) for i in self.of_kind(devices, "other")])

    def fitted(self, devices: list[str]) -> list[tuple[str, str]]:
        """(bay, model) for every module in these devices, in bay order."""
        out = []
        for d in devices:
            for m in sorted(self.modules.get(d, []), key=lambda m: _get(m, "module_bay", "name")):
                out.append((_get(m, "module_bay", "name") or "bay", module_model(m)))
        return out

    def empty_bays(self, devices: list[str]) -> list[str]:
        filled = {(d, _get(m, "module_bay", "name")) for d in devices for m in self.modules.get(d, [])}
        return [b.get("name") or "bay" for d in devices for b in self.bays.get(d, [])
                if not b.get("installed_module") and (d, b.get("name")) not in filled]

    # ------------------------------------------------------------------ gaps
    def modules_without_serial(self) -> list[str]:
        return [f"{d} {_get(m, 'module_bay', 'name')} {module_model(m)}".strip()
                for d, ms in sorted(self.modules.items()) for m in ms
                if not m.get("serial") and "blank" not in module_model(m).lower()]   # a blank cover has none

    def items_without_serial(self) -> list[str]:
        """Power supplies, fans and optics with no serial; a 'discovered' item NetBox read itself counts too."""
        return [f"{d} {part(i)}".strip() for d, items in sorted(self.items.items()) for i in items
                if not i.get("serial") and kind_of(i) in ("power", "fan", "optic")]

    def all_empty_bays(self) -> list[str]:
        return [f"{d} {bay}" for d in sorted(self.bays) for bay in self.empty_bays([d])]

    def fibre_without_optic(self, cables: list[dict], names: dict) -> list[str]:
        """Each end of a fiber cable with no transceiver recorded on its interface."""
        out = []
        for c in cables:
            if not str(c.get("type") or "").startswith(FIBRE):
                continue
            for side in ("a_terminations", "b_terminations"):
                for t in c.get(side) or []:
                    obj = t.get("object") or {}
                    dev = (obj.get("device") or {}).get("name") or names.get((obj.get("device") or {}).get("id"))
                    port = obj.get("name")
                    if dev and port and (dev, port) not in self.optics:
                        out.append(f"{c.get('label') or '#' + str(c.get('id'))} {dev} {port}")
        return out

    def counts(self) -> dict[str, int]:
        """Totals the quality sheet scores against."""
        return {"modules": sum(len(v) for v in self.modules.values()),
                "bays": sum(len(v) for v in self.bays.values()),
                "items": sum(1 for v in self.items.values() for i in v if kind_of(i) in ("power", "fan", "optic"))}


def fibre_ends(cables: list[dict]) -> int:
    """How many cable ends sit on fiber, for the optic check's total."""
    return sum(len(c.get("a_terminations") or []) + len(c.get("b_terminations") or [])
               for c in cables if str(c.get("type") or "").startswith(FIBRE))
