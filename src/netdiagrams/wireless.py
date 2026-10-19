"""Wireless LANs as NetBox records them: SSIDs, access points, controllers and radio links.

The wireless sheet used to carry the template's own words where NetBox has no field
(the controller an SSID is served by, how it is switched, which bands, which APs
broadcast it, an AP's mode and power). This module is the one place that works
those facts out, from NetBox's core fields first and from a small set of additive
custom fields second (``netbox-setup`` creates them; see :data:`CUSTOM_FIELDS`).
What neither holds stays empty, and the sheet shows the gap rather than the
template's example.

Every site has one of four wireless designs, and the sheet follows the site's
``wireless_management`` field: on-prem controllers (drawn as today), cloud-managed
(a cloud management card and an outbound HTTPS flow instead of controllers and
CAPWAP), firewall-managed (the firewall is the controller) and controllerless.
A mesh AP or a workgroup bridge hangs off another AP's radio, not a switch port,
and is read as such.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from . import ot
from .model import _get, _label, _number

# ----------------------------------------------------------------- custom fields
# Choice set name -> (value, label). Values are what the API returns; labels what the sheet prints.
CHOICE_SETS = {
    "Wireless switching": [("tunnelled", "Tunnelled to controller"), ("local", "Local switching"),
                           ("bridged", "Bridged (WGB)"), ("cloud", "Cloud/local breakout")],
    "Wireless bands": [("2.4ghz", "2.4 GHz"), ("5ghz", "5 GHz"), ("6ghz", "6 GHz")],
    "Wireless portal": [("none", "None"), ("captive", "Captive portal"), ("sponsored", "Sponsored"),
                        ("self", "Self-registration")],
    "Wireless security": [("wpa2-enterprise", "WPA2-Enterprise"), ("wpa3-enterprise", "WPA3-Enterprise"),
                          ("wpa3-enterprise-192", "WPA3-Enterprise 192-bit"),
                          ("wpa2-wpa3", "WPA2/WPA3 transition"), ("wpa3-sae", "WPA3-Personal (SAE)"),
                          ("wpa2-psk", "WPA2-PSK"), ("mpsk", "MPSK / per-device PSK"), ("owe", "OWE"),
                          ("open-portal", "Open + portal")],
    "AP mode": [("local", "Local"), ("flexconnect", "Local switching (FlexConnect)"), ("mesh", "Mesh"),
                ("bridge", "Bridge/WGB"), ("monitor", "Monitor/sensor"), ("cloud", "Cloud-managed")],
    "Wireless management": [("controller", "On-prem controller"), ("cloud", "Cloud-managed"),
                            ("firewall", "Firewall-managed"), ("controllerless", "Controllerless/embedded")],
}
# (name, label, group, type, object types, choice set, description) as netbox-setup imports them.
CUSTOM_FIELDS = [
    ("wlan_security", "Security", "Wireless", "select", "wireless.wirelesslan", "Wireless security",
     "WPA3, OWE and transition modes NetBox's own auth type cannot say"),
    ("wlan_eap", "EAP method", "Wireless", "text", "wireless.wirelesslan", "", "EAP-TLS, PEAP-MSCHAPv2, EAP-TTLS..."),
    ("wlan_switching", "Switching", "Wireless", "select", "wireless.wirelesslan", "Wireless switching",
     "Where client traffic lands: tunnelled to the controller, switched locally, bridged, cloud"),
    ("wlan_bands", "Bands", "Wireless", "multiselect", "wireless.wirelesslan", "Wireless bands",
     "The radio bands the SSID is broadcast on"),
    ("wlan_client_isolation", "Client isolation", "Wireless", "boolean", "wireless.wirelesslan", "",
     "Clients on this SSID cannot reach each other"),
    ("wlan_portal", "Portal", "Wireless", "select", "wireless.wirelesslan", "Wireless portal",
     "Guest access control: captive portal, sponsored, self-registration"),
    ("ap_mode", "AP mode", "Wireless", "select", "dcim.device", "AP mode",
     "How the access point forwards client traffic"),
    ("wireless_controller", "Wireless controller", "Wireless", "object", "dcim.device", "",
     "The controller (or firewall) this access point joins; empty when the site has one controller"),
    ("wireless_management", "Wireless management", "Wireless", "select", "dcim.site,dcim.sitegroup,dcim.region",
     "Wireless management", "On-prem controller, cloud-managed, firewall-managed or controllerless"),
    ("wireless_manager", "Wireless manager", "Wireless", "text", "dcim.site,dcim.sitegroup,dcim.region", "",
     "The system or device that manages the APs, by name"),
    ("wireless_survey", "Wireless survey", "Wireless", "url", "dcim.site", "",
     "Link to the latest RF survey or heat map"),
]
OBJECT_FIELD_TYPES = {"wireless_controller": "dcim.device"}  # object fields name the model they point at
WIRELESS_ROLES = {"access-point", "wireless-controller", "ptp-radio", "workgroup-bridge"}
RADIO_TYPES = re.compile(r"ieee802\.11|wireless|radio|other-wireless", re.I)
POE_TYPES = {"type1-ieee802.3af": "802.3af (Type 1)", "type2-ieee802.3at": "802.3at (Type 2)",
             "type3-ieee802.3bt": "802.3bt (Type 3)", "type4-ieee802.3bt": "802.3bt (Type 4)",
             "passive-24v-2pair": "Passive 24 V", "passive-24v-4pair": "Passive 24 V (4-pair)",
             "passive-48v-2pair": "Passive 48 V", "passive-48v-4pair": "Passive 48 V (4-pair)"}
OPEN_AUTH = {"open", "owe", "open-portal", ""}
SHARED_AUTH = {"wpa-personal", "wep", "wpa2-psk", "wpa3-sae", "mpsk"}
GUEST_ZONE = re.compile(r"guest|visitor|public|byod", re.I)
# whole words only: "ent" is a zone slug word, not a match inside "events", "student" or "government"
STAFF_ZONE = re.compile(r"(?<![a-z0-9])(?:mgmt|management|ent|enterprise|corp|corporate|staff|ops|servers?|idmz)"
                        r"(?![a-z0-9])", re.I)


def cf(obj: dict | None, name: str) -> str:
    """A custom field's value as text: a choice's value, an object's name, a list joined."""
    value = ((obj or {}).get("custom_fields") or {}).get(name)
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, list):
        return ", ".join(_label(v) if isinstance(v, dict) else str(v) for v in value)
    if isinstance(value, dict):
        return _label(value)
    return str(value)


def choice_label(set_name: str, value: str) -> str:
    """The printed form of a choice: its label when the value is known, else the value as given."""
    if not value:
        return ""
    labels = dict(CHOICE_SETS.get(set_name, ()))
    by_label = {lab.lower(): lab for lab in labels.values()}
    out = []
    for part in [p.strip() for p in str(value).split(",") if p.strip()]:
        out.append(labels.get(part.lower()) or by_label.get(part.lower()) or part)
    return " · ".join(out)


def choice_value(set_name: str, value: str) -> str:
    """The stored value of a choice given as a value or a label ('Cloud-managed' -> 'cloud')."""
    if not value:
        return ""
    for v, lab in CHOICE_SETS.get(set_name, ()):
        if str(value).strip().lower() in (v, lab.lower()):
            return v
    return str(value).strip().lower()


def management(export: dict) -> tuple[str, str]:
    """(mode, manager) from the site's ``wireless_management`` / ``wireless_manager``, inherited
    from the site group and the region chain the way the other site settings are."""
    layers = [export.get("site") or {}]
    if export.get("site_group"):
        layers.append(export["site_group"])
    layers += list(export.get("regions") or [])   # innermost first, as the export lists them
    mode = next((choice_value("Wireless management", cf(o, "wireless_management")) for o in layers
                 if cf(o, "wireless_management")), "")
    manager = next((cf(o, "wireless_manager") for o in layers if cf(o, "wireless_manager")), "")
    return mode, manager


# ---------------------------------------------------------------------- index
@dataclass
class Ssid:
    wlan: dict
    ssid: str
    vlan: dict
    prefixes: list
    zone: str
    security: str
    controller: str
    switching: str
    bands: str
    broadcast_on: str
    guest_controls: str
    notes: str
    status: str
    aps: list = field(default_factory=list)   # the devices whose radios carry it


class Index:
    """Everything the wireless sheet says, worked out once per export."""

    def __init__(self, export: dict, endpoint_roles: set[str] | None = None):
        self.export = export
        devices = [d for d in export.get("devices", []) if d.get("name")]
        self.devices = {d["name"]: d for d in devices}
        self.by_id = {d.get("id"): d for d in devices if d.get("id") is not None}
        role = lambda d: _get(d, "role", "slug")
        self.aps = [d for d in devices if role(d) == "access-point"]
        self.controllers = [d for d in devices if role(d) == "wireless-controller"]
        self.radios = [d for d in devices if role(d) == "ptp-radio"]
        self.wgbs = [d for d in devices if role(d) == "workgroup-bridge"]
        self.locations = ot.Locations(export.get("locations"))
        self.mode, self.manager = management(export)
        self.interfaces: dict[tuple[str, str], dict] = {}
        self.device_interfaces: dict[str, list[dict]] = defaultdict(list)
        for i in export.get("interfaces", []):
            dev = _get(i, "device", "name") or (self.by_id.get(_get(i, "device", "id", default=None)) or {}).get("name")
            if dev:
                self.interfaces[(dev, i.get("name"))] = i
                self.device_interfaces[dev].append(i)
        self.cabled: dict[str, tuple[str, str, dict]] = {}   # device -> (peer device, peer port, cable)
        self.cable_port: dict[str, str] = {}                 # device -> its own cabled port
        for c in export.get("cables", []):
            ends = [self._end(t) for t in (c.get("a_terminations") or [])[:1] + (c.get("b_terminations") or [])[:1]]
            ends = [e for e in ends if e]
            if len(ends) == 2:
                for (a, ap), (b, bp) in ((ends[0], ends[1]), (ends[1], ends[0])):
                    self.cabled.setdefault(a, (b, bp, c))
                    self.cable_port.setdefault(a, ap)
        self.links = export.get("wireless_links") or []
        self.wlans = export.get("wireless_lans") or []
        self.wlan_by_id = {w.get("id"): w for w in self.wlans if w.get("id") is not None}
        self.vlans = {v.get("id"): v for v in export.get("vlans", [])}
        self.prefixes_by_vlan: dict = defaultdict(list)
        for p in export.get("prefixes", []):
            if _get(p, "vlan", "id", default=None) is not None:
                self.prefixes_by_vlan[p["vlan"]["id"]].append(p)
        # Radio links by the pair of interfaces, then by SSID.
        self.link_ends: dict[int, list[tuple[str, str]]] = {}
        for w in self.links:
            self.link_ends[id(w)] = [self._link_end(w, side) for side in ("interface_a", "interface_b")]
        self.mesh = self._mesh()
        self.endpoint_roles = endpoint_roles or set()

    def _end(self, term: dict) -> tuple[str, str] | None:
        obj = (term or {}).get("object") or {}
        dev = obj.get("device") or {}
        name = dev.get("name") or (self.by_id.get(dev.get("id")) or {}).get("name")
        return (name, obj.get("name", "")) if name else None

    def _link_end(self, w: dict, side: str) -> tuple[str, str]:
        iface = w.get(side) or {}
        dev = iface.get("device") or {}
        name = dev.get("name") or (self.by_id.get(dev.get("id")) or {}).get("name") or ""
        return name, iface.get("name") or ""

    # ------------------------------------------------------------ APs, mesh, WGB
    def links_of(self, device: str) -> list[dict]:
        return [w for w in self.links if device in (e[0] for e in self.link_ends[id(w)])]

    def peer(self, device: str, w: dict) -> str:
        ends = self.link_ends[id(w)]
        return next((e[0] for e in ends if e[0] != device), "")

    def _mesh(self) -> dict[str, str]:
        """Mesh AP -> the AP it hangs off: an AP with no cable whose radio links to another AP,
        or whose radio interface is a station."""
        out = {}
        ap_names = {d["name"] for d in self.aps}
        for d in self.aps:
            name = d["name"]
            if name in self.cabled:
                continue
            roots = [self.peer(name, w) for w in self.links_of(name)]
            roots = [r for r in roots if r in ap_names]
            if not roots:
                station = any(_get(i, "rf_role", "value") == "station" for i in self.device_interfaces[name])
                if station:
                    roots = [self.peer(name, w) for w in self.links_of(name) if self.peer(name, w)]
            if roots:
                roots.sort(key=lambda r: (r not in self.cabled, r))
                out[name] = roots[0]
        return out

    def wgb_association(self, device: str) -> str:
        """The AP a workgroup bridge is associated with, from its wireless link."""
        peers = [self.peer(device, w) for w in self.links_of(device)]
        return next((p for p in peers if p), "")

    def is_radio_fed(self, device: str) -> bool:
        """An AP or bridge whose uplink is a radio, not a cable: never 'without a switch port'."""
        d = self.devices.get(device) or {}
        return device in self.mesh or (_get(d, "role", "slug") == "workgroup-bridge")

    def uplink_text(self, device: str) -> str:
        """What the register's SWITCH · PORT column says for a radio-fed device."""
        if device in self.mesh:
            return f"Mesh via {self.mesh[device]}"
        if _get(self.devices.get(device) or {}, "role", "slug") == "workgroup-bridge":
            assoc = self.wgb_association(device)
            return f"WGB via {assoc}" if assoc else ""
        return ""

    # ---------------------------------------------------------------- management
    @property
    def no_controller(self) -> bool:
        """The site runs its APs without an on-prem controller: by its field, or NetBox has none."""
        return self.mode in ("cloud", "firewall", "controllerless") or (bool(self.aps) and not self.controllers)

    def management_card(self) -> tuple[str, str]:
        """(title, text) for the card that stands where the template's controllers were."""
        if self.mode == "cloud":
            who = self.manager or "cloud dashboard"
            return (f"Cloud management · {who}",
                    "APs reach it outbound over HTTPS/TLS through the edge firewall; it holds the SSIDs, RADIUS "
                    "settings and firmware. Clients keep working when it is unreachable; changes wait.")
        if self.mode == "firewall":
            who = self.manager or "the site firewall"
            return (f"Firewall-managed · {who}",
                    "The firewall is the AP controller: SSIDs, VLANs and RADIUS live in its wireless settings.")
        if self.mode == "controllerless":
            who = f" · {self.manager}" if self.manager else ""
            return (f"Controllerless{who}",
                    "The APs run embedded/virtual control between themselves; one of them holds the configuration.")
        return ("No wireless controller in NetBox",
                "Record how the APs are managed: the site's Wireless management field, or each AP's "
                "Wireless controller field.")

    def management_flow(self) -> list[str] | None:
        """The row that replaces a CAPWAP flow when the APs are not controller-joined."""
        if self.mode == "cloud":
            return ["AP → cloud management", "Access points", self.manager or "Cloud dashboard",
                    "TCP 443 (HTTPS/TLS), outbound", "Edge firewall · AP mgmt VLAN → internet", "Allow"]
        if self.mode == "firewall":
            return ["AP → firewall control", "Access points", self.manager or "Site firewall",
                    "Vendor control channel", "AP mgmt VLAN → firewall", "Allow"]
        if self.mode == "controllerless":
            return ["AP ⇄ AP control", "Access points", "Access points (embedded controller)",
                    "Vendor control channel", "AP mgmt VLAN, intra-zone", "Intra-zone"]
        return None

    def mesh_links(self) -> list[tuple[str, str, dict | None]]:
        """(mesh AP or WGB, its root AP, the NetBox link) for every radio-fed device."""
        out = []
        for name, root in self.mesh.items():
            w = next((w for w in self.links_of(name) if self.peer(name, w) == root), None)
            out.append((name, root, w))
        for d in self.wgbs:
            root = self.wgb_association(d["name"])
            if root:
                w = next((w for w in self.links_of(d["name"]) if self.peer(d["name"], w) == root), None)
                out.append((d["name"], root, w))
        return out

    # ---------------------------------------------------------------- controllers
    def controller_groups(self) -> dict[str, list[str]]:
        """Controllers grouped as HA pairs: by virtual chassis, else by name without its member number."""
        groups: dict[str, list[str]] = defaultdict(list)
        for d in self.controllers:
            key = _get(d, "virtual_chassis", "name") or re.sub(r"[-_ ]0?\d{1,2}$", "", d["name"])
            groups[key].append(d["name"])
        return dict(groups)

    def ha_state(self, controller: str) -> str:
        for key, members in self.controller_groups().items():
            if controller in members and len(members) > 1:
                return f"HA pair {key} ({len(members)})"
        return ""

    def controller_of(self, ap: dict) -> tuple[str, str, str]:
        """(name, how it was found, NetBox link path) for the controller or manager an AP joins."""
        named = cf(ap, "wireless_controller")
        if named:
            return named, "the AP's wireless_controller field", "dcim/devices"
        if self.mode == "cloud":
            return self.manager or "Cloud-managed", "the site's wireless_manager", ""
        if self.mode == "firewall":
            return self.manager or "Firewall-managed", "the site's wireless_manager", ""
        if self.mode == "controllerless":
            return self.manager or "Controllerless", "the site's wireless_management", ""
        groups = self.controller_groups()
        if len(groups) == 1:
            key, members = next(iter(groups.items()))
            how = "the site's only controller" if len(members) == 1 else f"the site's only controller pair ({', '.join(members)})"
            return (members[0] if len(members) == 1 else key), how, "dcim/devices"
        return "", "", ""

    def controller_site(self, name: str) -> str:
        """The site of a controller named by an AP when it is not at this site."""
        d = self.devices.get(name)
        if d is not None:
            return ""
        for ap in self.aps:
            value = ((ap.get("custom_fields") or {}).get("wireless_controller"))
            if isinstance(value, dict) and _label(value) == name:
                return _label(value.get("site")) or "another site"
        return "another site" if name else ""

    def ap_mode(self, ap: dict) -> str:
        value = cf(ap, "ap_mode")
        if value:
            return choice_label("AP mode", value)
        name = ap.get("name", "")
        if name in self.mesh:
            return "Mesh"
        if _get(ap, "role", "slug") == "workgroup-bridge":
            return "Bridge/WGB"
        if self.mode == "cloud":
            return "Cloud-managed"
        return ""

    def ap_power(self, ap: dict) -> str:
        """The PoE the AP draws: its uplink interface's poe fields, else the switch port's (PSE)."""
        name = ap.get("name", "")
        own = self.interfaces.get((name, self.cable_port.get(name, "")))
        peer = self.cabled.get(name)
        candidates = [own] + ([self.interfaces.get((peer[0], peer[1]))] if peer else [])
        for i in candidates:
            if not i:
                continue
            poe_type = _get(i, "poe_type", "value")
            if poe_type:
                return POE_TYPES.get(poe_type) or _get(i, "poe_type", "label") or poe_type
            if _get(i, "poe_mode", "value"):
                return _get(i, "poe_mode", "label") or _get(i, "poe_mode", "value")
        return ""

    # ---------------------------------------------------------------------- SSIDs
    def zone_of_wlan(self, w: dict) -> str:
        vlan = self.vlans.get(_get(w, "vlan", "id", default=None)) or w.get("vlan") or {}
        zone = ot.vlan_zone(vlan, self.prefixes_by_vlan.get(vlan.get("id"))) if vlan else ""
        if not zone:
            zone = next((t.get("slug") for t in w.get("tags") or [] if (t.get("slug") or "").startswith("zone-")), "")
        return zone or ""

    def aps_broadcasting(self, w: dict) -> list[str]:
        """Devices whose radio interfaces carry the wireless LAN (core: interface.wireless_lans)."""
        wid = w.get("id")
        out = []
        for (dev, _), i in self.interfaces.items():
            if any((x.get("id") if isinstance(x, dict) else x) == wid for x in i.get("wireless_lans") or []):
                if dev not in out and dev in self.devices:   # an export can keep interfaces of devices it left out
                    out.append(dev)
        return out

    def ssids(self) -> list[Ssid]:
        out = []
        for w in sorted(self.wlans, key=lambda w: w.get("ssid") or ""):
            vlan = self.vlans.get(_get(w, "vlan", "id", default=None)) or w.get("vlan") or {}
            prefixes = list(self.prefixes_by_vlan.get(vlan.get("id"), []))
            aps = self.aps_broadcasting(w)
            controllers = []
            for name in aps:
                d = self.devices.get(name)
                c = self.controller_of(d)[0] if d else ""
                if c and c not in controllers:
                    controllers.append(c)
            if not controllers and self.aps:
                c = self.controller_of(self.aps[0])[0]
                if c and (len(self.controller_groups()) <= 1 or self.mode in ("cloud", "firewall", "controllerless")):
                    controllers = [c]
            auth = " · ".join(x for x in (_get(w, "auth_type", "label") or _get(w, "auth_type", "value"),
                                          _get(w, "auth_cipher", "label") or _get(w, "auth_cipher", "value")) if x)
            security = choice_label("Wireless security", cf(w, "wlan_security")) or auth
            if cf(w, "wlan_security") and auth and auth.lower() not in security.lower():
                security = f"{security} · {auth}"
            if cf(w, "wlan_eap"):
                security = f"{security} · {cf(w, 'wlan_eap')}" if security else cf(w, "wlan_eap")
            if aps:
                places = []
                for name in aps:
                    place = self.locations.card_path(self.devices[name].get("location")) or _label(self.devices[name].get("location"))
                    if place and place not in places:
                        places.append(place)
                broadcast = " · ".join(places[:4]) + (f" +{len(places) - 4} more" if len(places) > 4 else "")
                broadcast += f" ({len(aps)} AP{'s' if len(aps) != 1 else ''})"
            else:
                scope = _label(w.get("scope")) if isinstance(w.get("scope"), dict) else ""
                broadcast = f"{scope} (scope)" if scope else ""
            controls = []
            isolation = ((w.get("custom_fields") or {}).get("wlan_client_isolation"))
            if isolation is True:
                controls.append("client isolation")
            portal = choice_label("Wireless portal", cf(w, "wlan_portal"))
            if portal and portal != "None":
                controls.append(portal.lower() if portal[0].isupper() and portal != "OWE" else portal)
            out.append(Ssid(
                wlan=w, ssid=w.get("ssid") or "", vlan=vlan, prefixes=prefixes, zone=self.zone_of_wlan(w),
                security=security, controller=" · ".join(controllers),
                switching=choice_label("Wireless switching", cf(w, "wlan_switching")),
                bands=choice_label("Wireless bands", cf(w, "wlan_bands")), broadcast_on=broadcast,
                guest_controls=" · ".join(controls), notes=w.get("description") or "",
                status=(_get(w, "status", "value") or "active").lower(), aps=aps))
        return out

    # ------------------------------------------------------------------- radios
    def radio_text(self, device: str, iface: str) -> str:
        """'ch 36 · 5180 MHz · 20 MHz · 20 dBm' from the radio interface's RF fields."""
        i = self.interfaces.get((device, iface)) or {}
        parts = []
        channel = _get(i, "rf_channel", "label") or _get(i, "rf_channel", "value")
        if channel:
            parts.append(channel if str(channel).lower().startswith("ch") else f"ch {channel}")
        # NetBox's channel label already says the frequency and width ("36 (5180/40 MHz)"): no repeat.
        said = bool(re.search(r"\d[\d.]*\s*/\s*\d+|\d+\s*[MG]Hz", str(channel or "")))   # 60 GHz labels say GHz
        if i.get("rf_channel_frequency") and not said:
            parts.append(f"{_number(i['rf_channel_frequency'])} MHz")
        if i.get("rf_channel_width") and not said:
            parts.append(f"{_number(i['rf_channel_width'])} MHz wide")
        if i.get("tx_power") is not None:
            parts.append(f"{_number(i['tx_power'])} dBm")
        return " · ".join(parts)

    def link_for(self, ends: set[str], ssid: str = "") -> dict | None:
        """The NetBox link between the radios named (device, or device:port), else the one with the SSID."""
        devices = {e.partition(":")[0] for e in ends if e}
        ports = {e for e in ends if ":" in e}
        for w in self.links:
            pair = self.link_ends[id(w)]
            if ports and {f"{d}:{p}" for d, p in pair} == ports:
                return w
        for w in self.links:
            pair = {d for d, _ in self.link_ends[id(w)]}
            if devices and pair == devices:
                return w
        if ssid:
            return next((w for w in self.links if w.get("ssid") == ssid), None)
        return None

    def unlinked_radios(self) -> list[str]:
        linked = {d for w in self.links for d, _ in self.link_ends[id(w)] if d}
        radios = {d["name"] for d in self.radios}
        for c in self.export.get("cables", []):
            ends = [self._end(t) for t in (c.get("a_terminations") or [])[:1] + (c.get("b_terminations") or [])[:1]]
            names = {e[0] for e in ends if e}
            if names and names <= radios:
                linked |= names
        return sorted(radios - linked)

    # ----------------------------------------------------------------- by area
    def aps_by_area(self) -> list[dict]:
        """One row per NetBox location with APs: path, count, models, uplink closets, SSIDs."""
        ssid_by_ap: dict[str, list[str]] = defaultdict(list)
        for s in self.ssids():
            for ap in s.aps:
                ssid_by_ap[ap].append(s.ssid)
        rows: dict[str, dict] = {}
        for d in self.aps:
            path = self.locations.card_path(d.get("location")) or _label(d.get("location")) or "No location in NetBox"
            row = rows.setdefault(path, {"area": path, "location": d.get("location") or {}, "aps": [], "models": [],
                                          "closets": [], "ssids": []})
            row["aps"].append(d["name"])
            model = _label(d.get("device_type"))
            if model and model not in row["models"]:
                row["models"].append(model)
            peer = self.cabled.get(d["name"])
            closet = ""
            if peer:
                closet = _label((self.devices.get(peer[0]) or {}).get("location")) or peer[0]
            elif d["name"] in self.mesh:
                closet = f"mesh via {self.mesh[d['name']]}"
            if closet and closet not in row["closets"]:
                row["closets"].append(closet)
            for ssid in ssid_by_ap.get(d["name"], []):
                if ssid not in row["ssids"]:
                    row["ssids"].append(ssid)
        return sorted(rows.values(), key=lambda r: (r["area"] == "No location in NetBox", r["area"]))

    # ---------------------------------------------------------------- tag model
    def tag_rows(self) -> list[dict]:
        """One row per AP area with the controller tag model recorded (policy_tag, site_tag, rf_tag)."""
        rows: dict[tuple, dict] = {}
        for d in self.aps:
            tags = tuple(cf(d, k) for k in ("policy_tag", "site_tag", "rf_tag"))
            if not any(tags):
                continue
            area = self.locations.card_path(d.get("location")) or _label(d.get("location")) or "No location in NetBox"
            row = rows.setdefault((area,) + tags, {"area": area, "policy_tag": tags[0], "site_tag": tags[1],
                                                   "rf_tag": tags[2], "controllers": [], "aps": []})
            row["aps"].append(d["name"])
            c = self.controller_of(d)[0]
            if c and c not in row["controllers"]:
                row["controllers"].append(c)
        return [rows[k] for k in sorted(rows)]

    def survey(self) -> str:
        return cf(self.export.get("site") or {}, "wireless_survey")

    # ------------------------------------------------------------------- naming
    def manufacturers(self) -> list[str]:
        out = []
        for d in self.aps + self.controllers:
            m = _label(_get(d, "device_type", "manufacturer", default=None))
            if m and m not in out:
                out.append(m)
        return out

    def sheet_title(self) -> str:
        """'Wireless — Aruba · PtP', 'Wireless — Meraki (cloud)': the vendors NetBox names, not the template's."""
        makers = self.manufacturers()
        if self.mode == "cloud":
            who = self.manager or (makers[0] if makers else "")
            return f"Wireless — {who} (cloud)" if who else "Wireless — cloud-managed"
        parts = [" · ".join(makers[:2])] if makers else []
        if self.radios:
            parts.append("PtP")
        return "Wireless — " + " · ".join(parts) if parts else "Wireless"


# --------------------------------------------------------------------- checks
def gaps_for(index: Index, endpoint_roles: set[str]) -> dict[str, list[str]]:
    """Names for the wireless data-quality checks (gaps.py words them)."""
    aps = index.aps
    ssids = index.ssids()
    zone_word = lambda s: (s.zone[len("zone-"):] if s.zone.startswith("zone-") else s.zone)
    out = {
        "no_wlans": ["No SSIDs in NetBox"] if aps and not index.wlans else [],
        "wlan_no_vlan": [s.ssid for s in ssids if not s.vlan],
        "wlan_no_fields": [s.ssid for s in ssids if not (s.switching and s.bands and s.broadcast_on)],
        "ap_no_location": [d["name"] for d in aps if not _get(d, "location", "name")],
        "wlan_no_manager": [d["name"] for d in aps if not index.controller_of(d)[0]] if not index.mode else [],
        "wlan_review_open": [s.ssid for s in ssids
                             if _get(s.wlan, "auth_type", "value") in OPEN_AUTH
                             and choice_value("Wireless security", cf(s.wlan, "wlan_security")) in OPEN_AUTH
                             and not GUEST_ZONE.search(zone_word(s))],
        "wlan_review_psk": [s.ssid for s in ssids
                            if (_get(s.wlan, "auth_type", "value") in SHARED_AUTH
                                or choice_value("Wireless security", cf(s.wlan, "wlan_security")) in SHARED_AUTH)
                            and STAFF_ZONE.search(zone_word(s))],
        "wlink_bad_ends": [], "wgb_no_link": [d["name"] for d in index.wgbs if not index.wgb_association(d["name"])],
        "wlan_guest_controls": [s.ssid for s in ssids if GUEST_ZONE.search(zone_word(s) or s.ssid)
                                and not s.guest_controls],
    }
    for w in index.links:
        for dev, iface in index.link_ends[id(w)]:
            if not dev or not iface or (dev, iface) not in index.interfaces and index.interfaces:
                label = w.get("ssid") or f"link {w.get('id')}"
                out["wlink_bad_ends"].append(f"{label}: {dev or '?'}:{iface or '?'}")
    return out
