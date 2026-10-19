"""Provenance: what a sheet was built from, written on the sheet itself.

An auditor reading a printed sheet needs to know which NetBox it came from,
when the data was true, which tool version drew it and under which settings.
The drift report has most of that; the sheet is what gets filed. So every
title block gets a revision and a one-line provenance note, and the drift
report starts with the same facts.

The revision is content-based: the same NetBox data and settings always give
the same revision, and any change to either gives a new one. Two prints a
month apart can be told apart, and a rebuild with nothing changed cannot.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field

from . import __version__

VOLATILE = {"exported_at", "netbox_url", "_intake"}


def _canonical(value):
    if dataclasses.is_dataclass(value):
        return _canonical(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items()) if k not in VOLATILE}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def digest(export: dict, settings: dict | None = None) -> str:
    """SHA-256 over the export's data (not its export time or URL) and the settings in force."""
    payload = json.dumps({"export": _canonical(export), "settings": _canonical(settings or {})},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class Provenance:
    built: str = ""              # build date, YYYY-MM-DD
    data_date: str = ""          # the day the NetBox data is true for
    tool: str = __version__
    netbox_url: str = ""
    netbox_version: str = ""
    source: str = ""             # the export file, or "live NetBox"
    digest: str = ""             # full SHA-256 of data + settings
    revision: str = ""           # what the title block shows
    settings: list[str] = field(default_factory=list)

    @classmethod
    def build(cls, export: dict, settings: dict, sources: list[str], data_date: str,
              source: str = "", today: str | None = None, revision: str = "") -> "Provenance":
        full = digest(export, settings)
        return cls(
            built=today or dt.date.today().isoformat(),
            data_date=data_date,
            netbox_url=(export.get("netbox_url") or "").rstrip("/"),
            netbox_version=str(export.get("netbox_version") or ""),
            source=source or ("live NetBox" if export.get("netbox_url") else "export file"),
            digest=full,
            revision=revision or full[:6],
            settings=list(sources),
        )

    @property
    def netbox(self) -> str:
        host = self.netbox_url.split("//", 1)[-1] if self.netbox_url else ""
        version = f"NetBox {self.netbox_version}" if self.netbox_version and self.netbox_version != "sample" else ""
        return " · ".join(x for x in (host, version) if x)

    def line(self, shared: bool = False) -> str:
        """The one-line note under the title block. ``shared`` leaves the NetBox host out."""
        parts = [f"Rev {self.revision}", f"built {self.built} with netdiagrams {self.tool}"]
        if self.data_date and self.data_date != self.built:
            parts.append(f"NetBox data as of {self.data_date}")
        netbox = (f"NetBox {self.netbox_version}" if shared and self.netbox_version
                  and self.netbox_version != "sample" else self.netbox)
        if netbox:
            parts.append(f"from {netbox}")
        parts.append(f"settings: {', '.join(self.settings) or 'defaults'}")
        parts.append(f"sha256 {self.digest[:12]}")
        return " · ".join(parts)

    def markdown(self) -> list[str]:
        lines = [f"- Revision: {self.revision} (SHA-256 of the NetBox data and settings: {self.digest})",
                 f"- Built: {self.built} with netdiagrams {self.tool}"]
        if self.data_date:
            lines.append(f"- NetBox data as of: {self.data_date}")
        if self.netbox:
            lines.append(f"- NetBox: {self.netbox_url or ''}" + (f" (version {self.netbox_version})"
                                                                 if self.netbox_version else ""))
        lines.append(f"- Source: {self.source}")
        lines.append(f"- Settings: {', '.join(self.settings) or 'defaults'}")
        return lines
