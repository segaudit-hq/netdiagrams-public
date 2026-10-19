"""Read a site's objects from NetBox, or from an export file.

Drawing uses HTTP GET only: NetDiagrams never writes to NetBox and never connects
to network devices. The one exception is ``netdiagrams netbox-setup --apply``,
which creates (never updates or deletes) the custom fields, tags and roles the
template needs, through :meth:`NetBoxClient.post`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import ssl
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Export key -> NetBox REST endpoint (filtered by ?site=<slug>).
ENDPOINTS = {
    "devices": "dcim/devices",
    "virtual_chassis": "dcim/virtual-chassis",
    "cables": "dcim/cables",
    "vlans": "ipam/vlans",
    "prefixes": "ipam/prefixes",
    "circuits": "circuits/circuits",
    "interfaces": "dcim/interfaces",
    "wireless_links": "wireless/wireless-links",
    "wireless_lans": "wireless/wireless-lans",
    "locations": "dcim/locations",
    "racks": "dcim/racks",
}
# Fetched per device (these endpoints have no site filter, or not on every release): export key -> endpoint.
# Modules in their bays, the bays themselves (so an empty one shows) and inventory items (PSUs, fans, optics).
PER_DEVICE = {"ip_addresses": "ipam/ip-addresses", "modules": "dcim/modules", "module_bays": "dcim/module-bays",
              "inventory_items": "dcim/inventory-items"}
# Gateway addresses that belong to an FHRP group (HSRP, VRRP...) rather than a device.
FHRP_ROLES = ("vip", "vrrp", "hsrp", "glbp", "carp", "anycast")
BATCH = 50
WORKERS = 6  # parallel requests to NetBox; its API is read-only here and paginates per request


def _parallel(fn, items: list) -> list:
    """fn over items, several at a time, results in order. Small lists stay sequential."""
    if len(items) < 2:
        return [fn(i) for i in items]
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(items))) as pool:
        return list(pool.map(fn, items))

EXPORT_FORMAT = "netdiagrams-export/1"
# Keys never written to an export: a wireless LAN's or link's pre-shared key (auth_psk), and any key whose
# name says it holds a key, a secret or a password, custom fields included.
SECRET_KEYS = re.compile(r"(psk|secret|passphrase|password)", re.I)


def scrub(obj):
    """``obj`` without its secret keys, at any depth. Exports get sent around; keys must not travel with them."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if not SECRET_KEYS.search(str(k))}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


class NetBoxError(RuntimeError):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code  # the HTTP status, when NetBox answered


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an error here: urllib would turn a POST into a GET and carry the token to the new host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class NetBoxClient:
    def __init__(self, url: str, token: str, verify_tls: bool = True, timeout: float = 30):
        self.base = url.rstrip("/")
        if not self.base.endswith("/api"):
            self.base += "/api"
        self.token = token.strip()  # a trailing newline from a CI secret would land in an error message
        self.timeout = timeout
        self.context = None if verify_tls else ssl._create_unverified_context()
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.context), _NoRedirect)

    def _headers(self) -> dict[str, str]:
        # NetBox 4.5+ v2 tokens ("nbt_...") use Bearer; older tokens use "Token".
        scheme = "Bearer" if self.token.startswith("nbt_") else "Token"
        return {"Authorization": f"{scheme} {self.token}", "Accept": "application/json"}

    def _open(self, request: urllib.request.Request, what: str) -> dict:
        try:
            with self.opener.open(request, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if 300 <= err.code < 400:
                raise NetBoxError(f"NetBox redirected {request.full_url} to {err.headers.get('Location')}; "
                                  "use that address as the NetBox URL", err.code) from err
            detail = ""
            if request.get_method() == "POST":
                try:
                    detail = ": " + err.read().decode("utf-8", "replace")[:300]
                except Exception:
                    pass
            raise NetBoxError(f"NetBox returned {err.code} {what}{detail}", err.code) from err
        except urllib.error.URLError as err:
            raise NetBoxError(f"Could not reach NetBox at {self.base}: {err.reason}") from err
        except (OSError, ValueError) as err:  # a timeout mid-reply, or an HTML login page instead of JSON
            raise NetBoxError(f"Bad reply from NetBox at {self.base}: {err}") from err

    def get(self, url: str) -> dict:
        return self._open(urllib.request.Request(url, headers=self._headers(), method="GET"), f"for {url}")

    def post(self, endpoint: str, payload: dict) -> dict:
        """Create one object. Used by netbox-setup --apply only; nothing else writes."""
        body = json.dumps(payload).encode("utf-8")
        headers = {**self._headers(), "Content-Type": "application/json"}
        made = self._open(urllib.request.Request(f"{self.base}/{endpoint}/", data=body, headers=headers,
                                                 method="POST"), f"creating {endpoint}")
        if not isinstance(made, dict) or made.get("id") is None:
            raise NetBoxError(f"NetBox did not create {endpoint}: its reply has no id")
        return made

    def _pages(self, url: str):
        """Every result of a list, page by page. The next page is always asked of the same scheme and host,
        so a NetBox behind a proxy that writes http:// links never gets the token sent in clear."""
        base = urllib.parse.urlsplit(self.base)
        while url:
            page = self.get(url)
            yield from page.get("results", [])
            nxt = page.get("next")
            url = urllib.parse.urlsplit(nxt)._replace(scheme=base.scheme, netloc=base.netloc).geturl() if nxt else ""

    def version(self) -> str:
        """'4.2.5' from /api/status/, or '' when the endpoint is not readable."""
        try:
            return str(self.get(f"{self.base}/status/").get("netbox-version") or "")
        except NetBoxError:
            return ""

    def list(self, endpoint: str, **params: str) -> list[dict]:
        query = urllib.parse.urlencode({"limit": 1000, **params})
        return list(self._pages(f"{self.base}/{endpoint}/?{query}"))

    def sites(self) -> list[dict]:
        return self.list("dcim/sites")

    def _optional(self, endpoint: str, **params) -> list[dict]:
        """Older NetBox releases lack some filters; skip those objects rather than fail."""
        try:
            return self.list(endpoint, **params)
        except NetBoxError as err:
            if err.code in (400, 404):
                return []
            raise

    def export_site(self, site_slug: str) -> dict:
        sites = self.list("dcim/sites", slug=site_slug)
        if not sites:
            raise NetBoxError(f"No NetBox site with slug '{site_slug}'")
        status = self.get(f"{self.base}/status/")
        data = {
            "format": EXPORT_FORMAT,
            "netbox_version": status.get("netbox-version", ""),
            "netbox_url": self.base[: -len("/api")],
            "site": sites[0],
        }
        data["exported_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")  # the site's own day
        # The site's region chain and site group, for settings kept in their custom fields.
        data["regions"], region = [], (sites[0].get("region") or {}).get("id")
        while region is not None and len(data["regions"]) < 10:
            found = self._optional("dcim/regions", id=region)
            if not found:
                break
            data["regions"].append(found[0])
            region = (found[0].get("parent") or {}).get("id")
        group = (sites[0].get("group") or {}).get("id")
        if group is not None:
            data["site_group"] = next(iter(self._optional("dcim/site-groups", id=group)), None)
        keys = list(ENDPOINTS)
        for key, result in zip(keys, _parallel(lambda k: self._optional(ENDPOINTS[k], site=site_slug), keys)):
            data[key] = result
        site_id = sites[0].get("id")
        if site_id is not None:
            # VLANs in a group scoped to the site, its region or location, and global VLANs.
            data["vlans"] = _merge(data["vlans"], self._optional("ipam/vlans", available_at_site=site_id))
        ids = [d["id"] for d in data["devices"] if d.get("id") is not None]
        for key, endpoint in PER_DEVICE.items():
            data[key] = self._batched(endpoint, "device_id", ids)
        # The models in use: facts true of every device of a model (end of sale, end of support) live there.
        type_ids = sorted({d["device_type"]["id"] for d in data["devices"]
                           if isinstance(d.get("device_type"), dict) and d["device_type"].get("id") is not None})
        data["device_types"] = self._batched("dcim/device-types", "id", type_ids)
        # Who owns and runs each asset: contacts assigned to the devices, their racks and rooms, and the site.
        data["contact_assignments"] = self._contacts(status.get("netbox-version", ""), site_id, data)
        # Wireless LANs reach a site through its VLANs or a scope (site, location, region, site group;
        # NetBox 4.2+), not only through ?site=; intake keeps the ones that are this site's.
        vlan_ids = [v["id"] for v in data["vlans"] if v.get("id") is not None]
        data["wireless_lans"] = _merge(data["wireless_lans"], self._batched("wireless/wireless-lans", "vlan_id", vlan_ids))
        scopes = {"dcim.site": [site_id], "dcim.location": [loc.get("id") for loc in data["locations"]],
                  "dcim.region": [r.get("id") for r in data["regions"]],
                  "dcim.sitegroup": [(data.get("site_group") or {}).get("id")]}
        for scope_type, scope_ids in scopes.items():
            data["wireless_lans"] = _merge(data["wireless_lans"], self._batched(
                "wireless/wireless-lans", "scope_id", [i for i in scope_ids if i is not None],
                [("scope_type", scope_type)]))
        # Prefixes of VLANs that aren't the site's own (a group or global VLAN) have no site either.
        site_prefix_vlans = {(p.get("vlan") or {}).get("id") for p in data["prefixes"]}
        other = [v["id"] for v in data["vlans"] if v.get("id") is not None and v["id"] not in site_prefix_vlans]
        data["prefixes"] = _merge(data["prefixes"], self._batched("ipam/prefixes", "vlan_id", other))
        # HSRP/VRRP gateway addresses sit on an FHRP group, not a device: fetch them by prefix.
        nets = [p["prefix"] for p in data["prefixes"] if p.get("prefix")]
        data["ip_addresses"] = _merge(data["ip_addresses"], self._batched(
            "ipam/ip-addresses", "parent", nets, [("role", r) for r in FHRP_ROLES]))
        return scrub(data)

    def _contacts(self, version: str, site_id, data: dict) -> list[dict]:
        """Contact assignments on the site's devices, racks, locations and the site (NetBox 4.0 renamed the
        filter content_type to object_type)."""
        major = int((re.findall(r"\d+", version or "") or ["4"])[0])
        key = "object_type" if major >= 4 else "content_type"
        out = []
        for kind, objs in (("dcim.device", data.get("devices")), ("dcim.rack", data.get("racks")),
                           ("dcim.location", data.get("locations")), ("dcim.site", [{"id": site_id}])):
            ids = [o["id"] for o in objs or [] if o.get("id") is not None]
            if ids:
                out = _merge(out, self._batched("tenancy/contact-assignments", "object_id", ids, [(key, kind)]))
        return out

    def _batched(self, endpoint: str, key: str, values: list, extra: list | None = None) -> list[dict]:
        def fetch(start: int) -> list[dict]:
            batch = [(key, v) for v in values[start:start + BATCH]] + list(extra or []) + [("limit", 1000)]
            url = f"{self.base}/{endpoint}/?{urllib.parse.urlencode(batch)}"
            found = []
            try:
                found.extend(self._pages(url))
            except NetBoxError as err:
                if err.code not in (400, 404):
                    raise
            return found

        out = []
        for found in _parallel(fetch, list(range(0, len(values), BATCH))):
            out.extend(found)
        return out


def _merge(first: list[dict], more: list[dict]) -> list[dict]:
    """Add objects not already in the list (by id)."""
    out = list(first)
    seen = {o.get("id") for o in first if o.get("id") is not None}
    for o in more:
        if o.get("id") is None or o["id"] not in seen:
            out.append(o)
            seen.add(o.get("id"))
    return out


def load_export(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text("utf-8"))
    if not isinstance(data, dict) or "devices" not in data:
        raise NetBoxError(f"{path} is not a NetDiagrams export (expected a 'devices' list)")
    for key in list(ENDPOINTS) + list(PER_DEVICE) + ["contact_assignments", "device_types"]:
        data.setdefault(key, [])
    return scrub(data)   # an export written by an older release, or by hand, may still carry a PSK
