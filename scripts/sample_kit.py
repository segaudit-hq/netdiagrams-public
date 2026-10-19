"""What every sample-export generator shares: the slug rule and the device types' lifecycle dates."""

from __future__ import annotations

import re


def slug(value: str) -> str:
    """A name's slug as NetBox makes one: lower case, spaces as hyphens, only letters, digits, - and _."""
    return re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", value.lower(), flags=re.ASCII).strip())


def model_lifecycle(devices, lifecycle: dict) -> list[dict]:
    """The device types in use, with their end of sale and end of support; each device names its type's id.

    ``devices`` are NetBox-shaped device records; ``lifecycle`` maps a model to (end of sale, end of support).
    Types are numbered in order of first use; a device's device_type gets its type's "id".
    """
    types = {}
    for d in devices:
        ref = d["device_type"]
        key = ((ref.get("manufacturer") or {}).get("slug", ""), ref["model"])
        if key not in types:
            sale, support = lifecycle.get(ref["model"], (None, None))
            types[key] = {"id": len(types) + 1, "model": ref["model"], "manufacturer": ref.get("manufacturer"),
                          "slug": slug(ref["model"]),
                          "custom_fields": {"end_of_sale": sale, "end_of_support": support}}
        ref["id"] = types[key]["id"]
    return list(types.values())
