"""Sable Ridge Group: the fictional company the C01 corporate template is drawn for.

One source for the template's shapes and for the sample NetBox exports (C01 HQ
campus, its day-one starter, and the C11 Ashcombe branch), so the two never
disagree. Every fact is from Book 9's sample-site.md; where the drawing needs one
the facts leave open (a host's switch port, how many cameras on a floor) it is
marked "(drawing's choice)" below. Addresses are private or documentation
ranges; serials and circuit IDs are placeholders.
"""

from __future__ import annotations

SITE = {"code": "C01", "name": "Sable Ridge HQ campus", "slug": "c01"}
BRANCH = {"code": "C11", "name": "Ashcombe", "slug": "c11"}
REGION = {"id": 1, "name": "Sable Ridge", "slug": "sable-ridge"}
# Site groups: id, name, slug, parent id
GROUPS = {"hubs": (1, "Hubs", "hubs", None), "regional": (2, "Regional offices", "regional-offices", None),
          "branches": (3, "Branches", "branches", None), "br-m": (4, "BR-M", "br-m", 3), "br-s": (5, "BR-S", "br-s", 3)}

# Zones: slug, short name, title, band code, what lives there, rule, (fill, stroke, font)
ZONES = [
    ("zone-internet", "INTERNET", "Internet and SaaS", "OUT", "ISP-1, ISP-2, SaaS, home workers before they connect",
     "Untrusted. Everything from here ends on an edge firewall.", ("#F8FAFC", "#CBD5E1", "#475569")),
    ("zone-wan", "WAN", "SD-WAN overlay", "OUT", "The SD-WAN hubs and spokes, the carrier underlays",
     "Carries CORP and LEGAL as separate segments. Ends on a hub.", ("#F5F3FF", "#C4B5FD", "#6D28D9")),
    ("zone-cloud", "CLOUD", "Cloud", "OUT", "Transit hub, client-portal spoke, analytics spoke",
     "Reached over the private circuit, IPsec as backup.", ("#F0F9FF", "#A5D8F3", "#0369A1")),
    ("zone-edge", "EDGE", "Firewalls and remote access", "EDGE", "Edge firewall pairs, ISFW pair, VPN pool",
     "Where zones meet. Every crossing is inspected and logged.", ("#F1F5F9", "#94A3B8", "#334155")),
    ("zone-dmz", "DMZ", "DMZ", "EDGE", "Reverse proxy for the client portal, secure file transfer",
     "Reached from the internet on named ports; reaches in only to named APIs.", ("#FFF7ED", "#FDBA74", "#C2410C")),
    ("zone-extranet", "EXTRANET", "Client extranet", "EDGE", "One client's dedicated IPsec tunnel and its landing server",
     "One client, one peer, one service.", ("#FEFCE8", "#FDE68A", "#A16207")),
    ("zone-corp", "CORP", "Corporate users", "USERS", "Staff laptops and desktops, wired and on SR-CORP",
     "Reaches SaaS, the DC apps and infrastructure. Not the legal systems.", ("#F4F7FE", "#B3C8F8", "#2563EB")),
    ("zone-voice", "VOICE", "Voice", "USERS", "Desk and meeting-room phones",
     "Cloud phone service only.", ("#F2F9FC", "#A6D4EB", "#0284C7")),
    ("zone-print", "PRINT", "Printers", "USERS", "Multifunction printers",
     "Answers the print servers. Starts nothing except scan-to-email.", ("#F4FAF5", "#B4DDBF", "#16A34A")),
    ("zone-legal", "LEGAL", "Legal users", "USERS",
     "Legal practice staff (wired on S-L3/S-L4, any floor on Wi-Fi by identity)",
     "Reaches the legal systems. Everyone else can't.", ("#FEF2F2", "#FCA5A5", "#B91C1C")),
    ("zone-dc-app", "DC-APP", "DC applications", "DC", "Application servers",
     "Reached by users on named ports; reaches data.", ("#F2FAF8", "#A8DACA", "#047857")),
    ("zone-dc-data", "DC-DATA", "DC data", "DC", "Database servers, file services",
     "Reached only by the app tier and backup.", ("#F0FDF4", "#9DD9B4", "#15803D")),
    ("zone-dc-infra", "DC-INFRA", "DC infrastructure", "DC",
     "Directory, DNS, DHCP, NAC, PKI, print servers, PAM jump hosts",
     "Everyone uses it; only PAM reaches management.", ("#F3FAF9", "#AADAD5", "#0D9488")),
    ("zone-dc-backup", "DC-BACKUP", "Backup", "DC", "Backup servers and the immutable backup store",
     "Pulls from every tier; nothing pulls from it.", ("#F7FAF2", "#C5DFA6", "#4D7C0F")),
    ("zone-dms", "DMS", "Legal systems", "DC", "Document management and matter databases, on their own hosts",
     "Legal users only. The ethical wall in the network.", ("#FDF2F8", "#F5B5D5", "#9D174D")),
    ("zone-guest", "GUEST", "Guests", "SHARED", "Visitors on SR-GUEST",
     "Internet only. Never routed internally.", ("#FDF8F3", "#F2CFA8", "#D97706")),
    ("zone-rooms", "ROOMS", "Meeting rooms", "SHARED", "Room systems and displays",
     "Cloud meeting service; staff may cast.", ("#F8F5FE", "#D1BAF9", "#7C3AED")),
    ("zone-building", "BUILDING", "Building systems", "SHARED", "Cameras and recorders, badge controllers, the BMS",
     "Facilities and its contractor only, through the edge with MFA.", ("#FDF4F9", "#F3B8D6", "#DB2777")),
    ("zone-mgmt", "MGMT", "Network management", "MGMT", "Switch, firewall, WLC, AP, UPS and server management",
     "Reached only from the PAM jump hosts.", ("#F0FAFC", "#A5DCE8", "#0891B2")),
    ("zone-oob", "OOB", "Out-of-band", "MGMT", "Console servers with cellular",
     "Works when the network doesn't. Every login logged.", ("#F1F5F9", "#B8C4D4", "#475569")),
]
ZONE = {z[0]: z for z in ZONES}

BANDS = [
    ("OUT", "OUTSIDE · INTERNET, WAN & CLOUD"), ("EDGE", "EDGE · FIREWALLS, DMZ & REMOTE ACCESS"),
    ("USERS", "USERS · CORPORATE & LEGAL"), ("DC", "DATA CENTER"), ("SHARED", "SHARED & BUILDING"),
    ("MGMT", "MANAGEMENT"),
]

# VRFs: name, id (the RD's last half), what it holds, its transit to the ISFW pair
VRFS = [("CORP", 10, "Corporate users, voice, printers", "10.1.255.0/29"),
        ("LEGAL", 20, "Legal users and the legal systems", "10.1.255.8/29"),
        ("DC", 40, "Every data center tier; gateways on the ISFW", "none: gateways on the ISFW (10.1.255.32/29 is ISFW to edge, Po43)"),
        ("GUEST", 70, "Guests and quarantine; no route to the ISFW", "none: default to the edge's guest interface"),
        ("BUILDING", 80, "Cameras, badges, BMS, meeting rooms", "10.1.255.16/29"),
        ("MGMT", 99, "Network and server management", "10.1.255.24/29")]
RD_ASN = 65010

# VLANs: vid, name, VRF, zone, subnet, gateway
VLANS = [
    (110, "CORP-N", "CORP", "zone-corp", "10.1.16.0/21", "Core pair .1"),
    (111, "CORP-S", "CORP", "zone-corp", "10.1.24.0/21", "DIST-S"),
    (112, "CORP-C", "CORP", "zone-corp", "10.1.32.0/22", "Core pair .1"),
    (115, "CORP-WIFI", "CORP", "zone-corp", "10.1.64.0/19", "Core pair .1"),
    (120, "VOICE", "CORP", "zone-voice", "10.1.40.0/22", "Core pair .1, DIST-S"),
    (130, "PRINT", "CORP", "zone-print", "10.1.44.0/23", "Core pair .1, DIST-S"),
    (199, "QUARANTINE", "GUEST", "zone-guest", "172.20.64.0/22", "Edge FW guest interface"),
    (210, "LEGAL-WIRED", "LEGAL", "zone-legal", "10.1.48.0/22", "DIST-S"),
    (211, "LEGAL-WIRED-NC", "LEGAL", "zone-legal", "10.1.52.0/22", "Core pair .1"),
    (215, "LEGAL-WIFI", "LEGAL", "zone-legal", "10.1.96.0/22", "Core pair .1"),
    (400, "DC-APP", "DC", "zone-dc-app", "10.1.160.0/22", "ISFW"),
    (410, "DC-DATA", "DC", "zone-dc-data", "10.1.164.0/23", "ISFW"),
    (420, "DC-INFRA", "DC", "zone-dc-infra", "10.1.168.0/24", "ISFW"),
    (430, "DC-BACKUP", "DC", "zone-dc-backup", "10.1.170.0/24", "ISFW"),
    (440, "DC-DMS", "LEGAL", "zone-dms", "10.1.172.0/24", "ISFW"),
    (600, "DMZ", "", "zone-dmz", "10.1.200.0/24", "Edge FW"),
    (610, "EXTRANET", "", "zone-extranet", "10.1.204.0/27", "Edge FW"),
    (700, "GUEST", "GUEST", "zone-guest", "172.20.0.0/18", "Edge FW guest interface"),
    (800, "CAMERAS", "BUILDING", "zone-building", "10.1.128.0/22", "Core pair .1"),
    (810, "BADGE", "BUILDING", "zone-building", "10.1.132.0/24", "Core pair .1"),
    (820, "BMS", "BUILDING", "zone-building", "10.1.133.0/24", "Core pair .1"),
    (850, "ROOMS", "BUILDING", "zone-rooms", "10.1.136.0/23", "Core pair .1"),
    (990, "NET-MGMT", "MGMT", "zone-mgmt", "10.1.240.0/22", "Core pair .1"),
    (991, "OOB", "", "zone-oob", "10.1.250.0/24", "OOB console servers (cellular)"),
]
# Prefixes with no VLAN: prefix, name, VRF, zone, gateway
PREFIXES = [
    ("10.250.0.0/21", "VPN-POOL", "", "zone-edge", "Edge FW (identity-based: CORP or LEGAL policy)"),
    ("198.51.100.0/28", "ISP-1 outside", "", "zone-internet", "ISP-1 router .1"),
    ("203.0.113.0/28", "ISP-2 outside", "", "zone-internet", "ISP-2 router .1"),
    ("10.1.242.0/23", "AP management", "MGMT", "zone-mgmt", "Core pair .1"),
]
CLOUD = [("Transit hub", "10.200.0.0/22", "Cloud firewall, private circuit and VPN gateways"),
         ("Client-portal spoke", "10.201.0.0/16", "Client portal application back end"),
         ("Analytics spoke", "10.202.0.0/16", "Analytics platform, read replicas")]

# Branch VLANs (the same numbers at every branch): vid, name, VRF, zone, subnet pattern ({n} = site number)
BRANCH_VLANS = [
    (110, "CORP", "CORP", "zone-corp", "10.{n}.16.0/22"), (120, "VOICE", "CORP", "zone-voice", "10.{n}.40.0/24"),
    (130, "PRINT", "CORP", "zone-print", "10.{n}.44.0/24"), (210, "LEGAL", "LEGAL", "zone-legal", "10.{n}.48.0/24"),
    (700, "GUEST", "GUEST", "zone-guest", "172.21.{n}.0/24"), (990, "NET-MGMT", "MGMT", "zone-mgmt", "10.{n}.240.0/24"),
]

# ------------------------------------------------------------------ locations
# name, parent. Each building's floors are listed top floor first: the riser sheet keeps NetBox's order
# for floor names it can't read a number from ("N-L5"), and a riser reads from the roof down.
LOCATIONS = [("North", None)]
for _f in (5, 4, 3, 2):
    LOCATIONS += [(f"N-L{_f}", "North"), (f"IDF-N{_f}", f"N-L{_f}")]
LOCATIONS += [("N-L1", "North"), ("MDF-N", "N-L1"), ("DC-N", "N-L1"), ("South", None)]
for _f in (4, 3, 2):
    LOCATIONS += [(f"S-L{_f}", "South"), (f"IDF-S{_f}", f"S-L{_f}")]
LOCATIONS += [("S-L1", "South"), ("MDF-S", "S-L1"), ("Commons", None)]
for _f in (2, 1):
    LOCATIONS += [(f"C-L{_f}", "Commons"), (f"IDF-C{_f}", f"C-L{_f}")]
# Each floor: (code, floor location, closet, APs, cameras, meeting rooms). AP totals are the facts' (114);
# how the 60 cameras and 40 rooms spread over the floors is the drawing's choice.
FLOORS = [("N5", "N-L5", "IDF-N5", 10, 6, 4), ("N4", "N-L4", "IDF-N4", 10, 6, 4), ("N3", "N-L3", "IDF-N3", 10, 6, 4),
          ("N2", "N-L2", "IDF-N2", 10, 6, 4), ("N1", "N-L1", "MDF-N", 10, 6, 4),
          ("C2", "C-L2", "IDF-C2", 12, 5, 4), ("C1", "C-L1", "IDF-C1", 12, 5, 4),
          ("S4", "S-L4", "IDF-S4", 10, 5, 3), ("S3", "S-L3", "IDF-S3", 10, 5, 3), ("S2", "S-L2", "IDF-S2", 10, 5, 3),
          ("S1", "S-L1", "MDF-S", 10, 5, 3)]
FLOOR = {f[0]: f for f in FLOORS}
LEGAL_FLOORS = ("S3", "S4")

PAN, FORTI, CISCO, DELL, NETAPP, AXIS, OPEN, EATON, APC, CANON, MERCURY, TRIDIUM = (
    "Palo Alto Networks", "Fortinet", "Cisco", "Dell", "NetApp", "Axis", "Opengear", "Eaton", "APC", "Canon",
    "Mercury", "Tridium")

# Asset criticality by role: what stops when the box fails. The firewall pairs, the hubs, the core, the
# DC switching and the hosts and storage stop the company; a floor stack, the WLCs, the backup store,
# the UPSs and the badge controllers stop a floor or a safeguard; the rest inconvenience a room or a desk.
CRITICALITY = {"firewall": "critical", "sdwan-hub": "critical", "core-switch": "critical",
               "distribution-switch": "critical", "dc-leaf": "critical", "hypervisor": "critical",
               "storage": "critical", "access-switch": "high", "wireless-controller": "high",
               "backup-appliance": "high", "ups": "high", "door-controller": "high",
               "access-point": "medium", "console-server": "medium", "nvr": "medium", "bms-controller": "medium",
               "printer": "low", "camera": "low", "room-system": "low"}
SW = {"firewall": "PAN-OS 11.1.x", "sdwan-hub": "FortiOS 7.4.x", "core-switch": "IOS XE 17.12.x",
      "distribution-switch": "IOS XE 17.12.x", "access-switch": "IOS XE 17.12.x", "dc-leaf": "NX-OS 10.4.x",
      "wireless-controller": "IOS XE 17.12.x", "console-server": "Opengear 24.x", "hypervisor": "Hypervisor 8.0",
      "storage": "ONTAP 9.15", "backup-appliance": "DD OS 8.1", "nvr": "AXIS OS 11", "ups": "NMC 3"}
CONTRACT = {"firewall": "Premium support", "sdwan-hub": "FortiCare Premium", "core-switch": "Smart Net 8x5xNBD",
            "distribution-switch": "Smart Net 8x5xNBD", "access-switch": "Smart Net 8x5xNBD",
            "dc-leaf": "Smart Net 24x7x4", "wireless-controller": "Smart Net 8x5xNBD",
            "hypervisor": "ProSupport Plus 4h", "storage": "SupportEdge 4h", "backup-appliance": "ProSupport 4h"}


def _dev(name, role, mfr, model, platform, location, rack, pos, ip, zone, desc, serial, tag="", vc="", vcpos="",
         modules="", power="", status="active"):
    return {"name": name, "role": role, "manufacturer": mfr, "device_type": model, "platform": platform,
            "location": location, "rack": rack, "position": pos, "primary_ip4": ip, "tags": zone,
            "description": desc, "serial": serial, "asset_tag": tag, "virtual_chassis": vc, "vc_position": vcpos,
            "status": status, "cf_sw_version": SW.get(role, ""), "cf_support_contract": CONTRACT.get(role, ""),
            "cf_lifecycle": "In support" if role in CONTRACT else "", "x_modules": modules, "x_power": power,
            "cf_ap_mode": "local" if role == "access-point" else "", "cf_criticality": CRITICALITY.get(role, "")}


def _pair(base, role, mfr, model, platform, places, ips, zone, desc, serial, tag, **kw):
    """Two devices -01 and -02: places are (location, rack, U) each."""
    return [_dev(f"{base}-0{n + 1}", role, mfr, model, platform, *places[n], ips[n], zone, desc.format(n=n + 1),
                 f"{serial}{n + 1:02d}", f"{tag}{n + 1}", **kw) for n in range(2)]


DEVICES = (
    _pair("C01-EFW", "firewall", PAN, "PA-3420", "panos", [("DC-N", "A01", "38"), ("DC-N", "A01", "36")],
          ["10.1.240.11/22", "10.1.240.12/22"], "zone-edge",
          "Edge HA pair member {n}: internet, DMZ, extranet, VPN, guest", "PA34xxxxx", "SR-01",
          modules="eth1/1 SFP+ ISP-1 · eth1/2 RJ45 ISP-2 · eth1/3–4 to ISFW · eth1/5–6 DMZ to DC leafs · eth1/7 hub · ha1",
          power="2× AC PSU")
    + _pair("C01-ISFW", "firewall", PAN, "PA-5420", "panos", [("DC-N", "A02", "36"), ("DC-N", "A02", "31")],
            ["10.1.240.13/22", "10.1.240.14/22"], "zone-edge",
            "Internal segmentation HA pair member {n}: VRF transits, DC gateways", "PA54xxxxx", "SR-02",
            modules="eth1/1–2 SFP28 to core · eth1/3–4 to edge · eth1/5–6 to DC leafs · eth1/7 hub · ha1",
            power="2× AC PSU")
    + _pair("C01-SDW", "sdwan-hub", FORTI, "FortiGate 600F", "fortios", [("DC-N", "A01", "32"), ("DC-N", "A01", "31")],
            ["10.1.240.15/22", "10.1.240.16/22"], "zone-wan", "SD-WAN hub 1, HA member {n}", "FG6Hxxxxxx", "SR-03",
            modules="port1 underlay to edge · port2 overlay to ISFW", power="2× AC PSU")
    + [_dev("C01-CORE-01", "core-switch", CISCO, "Catalyst 9500-48Y4C", "ios-xe", "MDF-N", "M01", "40",
            "10.1.240.1/22", "zone-mgmt", "Routed core, StackWise Virtual member 1: OSPF per VRF; North floors' "
            "distribution too", "FDOxxxxx001", "SR-0101", "C01-CORE", "1", modules="48× SFP28 · 4× QSFP28", power="2× 950 W AC"),
       _dev("C01-CORE-02", "core-switch", CISCO, "Catalyst 9500-48Y4C", "ios-xe", "MDF-N", "M02", "40",
            "", "zone-mgmt", "Routed core, StackWise Virtual member 2: OSPF per VRF; North floors' "
            "distribution too", "FDOxxxxx002", "SR-0102", "C01-CORE", "2", modules="48× SFP28 · 4× QSFP28", power="2× 950 W AC"),
       _dev("C01-DIST-S-01", "distribution-switch", CISCO, "Catalyst 9500-24Y4C", "ios-xe", "MDF-S", "M01", "40",
            "10.1.240.3/22", "zone-mgmt", "South distribution, StackWise Virtual member 1", "FDOxxxxx011",
            "SR-0111", "C01-DIST-S", "1", modules="24× SFP28 · 4× QSFP28", power="2× 950 W AC"),
       _dev("C01-DIST-S-02", "distribution-switch", CISCO, "Catalyst 9500-24Y4C", "ios-xe", "MDF-S", "M02", "40",
            "", "zone-mgmt", "South distribution, StackWise Virtual member 2", "FDOxxxxx012", "SR-0112",
            "C01-DIST-S", "2", modules="24× SFP28 · 4× QSFP28", power="2× 950 W AC")]
    + _pair("C01-DCSW", "dc-leaf", CISCO, "Nexus 93180YC-FX3", "nx-os", [("DC-N", "A03", "40"), ("DC-N", "A04", "40")],
            ["10.1.240.51/22", "10.1.240.52/22"], "zone-mgmt", "DC leaf {n}, vPC pair: layer 2 for the DC VLANs",
            "FDOxxxxx05", "SR-05", modules="48× SFP28 · 6× QSFP28", power="2× 650 W AC")
    + _pair("C01-WLC", "wireless-controller", CISCO, "Catalyst 9800-40", "ios-xe",
            [("DC-N", "A03", "36"), ("DC-N", "A04", "36")], ["10.1.240.61/22", "10.1.240.62/22"], "zone-mgmt",
            "Wireless controller {n}, SSO pair: campus APs local mode, branch APs FlexConnect", "TTMxxxxxx",
            "SR-06", modules="4× SFP+", power="2× AC PSU")
    + [_dev(f"C01-HV-0{n}", "hypervisor", DELL, "PowerEdge R760", "", "DC-N", "A05" if n <= 4 else "A06",
            str(30 + 2 * ((n - 1) % 4)), f"10.1.241.{10 + n}/22", "zone-dc-infra",
            f"Production cluster CL-PROD host {n} (iDRAC address)", f"SVCTAG76{n:02d}", f"SR-07{n:02d}",
            modules="2× 25G SFP28 (DAC to the DC leafs)", power="2× 1400 W") for n in range(1, 9)]
    + [_dev(f"C01-HV-L{n}", "hypervisor", DELL, "PowerEdge R660", "", "DC-N", "A07", ("30", "28")[n - 1],
            f"10.1.241.{20 + n}/22", "zone-dms", f"Legal cluster CL-LEGAL host {n}: DMS and matter databases only",
            f"SVCTAG66{n:02d}", f"SR-08{n:02d}", modules="2× 25G SFP28 (DAC to the DC leafs)", power="2× 1100 W")
       for n in (1, 2)]
    + [_dev("C01-SAN-01", "storage", NETAPP, "AFF A250", "ontap", "DC-N", "A06", "20", "10.1.241.31/22",
            "zone-dc-data", "Primary storage for CL-PROD", "NAxxxxxx01", "SR-0901",
            modules="2 controllers · 4× 25G", power="2× AC PSU"),
       _dev("C01-BKP-01", "backup-appliance", DELL, "PowerProtect DD6400", "", "DC-N", "A07", "20",
            "10.1.241.41/22", "zone-dc-backup", "Immutable backup store; replicates to C02", "DDxxxxxx01", "SR-0902",
            modules="2× 25G", power="2× AC PSU"),
       _dev("C01-NVR-01", "nvr", AXIS, "S1296", "", "DC-N", "A08", "30", "10.1.128.10/22", "zone-building",
            "Video recorder 1 of 2 (60 cameras)", "AXNVRxx01", "SR-0911", modules="96 TB"),
       _dev("C01-NVR-02", "nvr", AXIS, "S1296", "", "DC-N", "A08", "28", "10.1.128.11/22", "zone-building",
            "Video recorder 2 of 2 (60 cameras)", "AXNVRxx02", "SR-0912", modules="96 TB"),
       _dev("C01-OOB-01", "console-server", OPEN, "OM2248-L", "opengear", "MDF-N", "M01", "42", "10.1.250.5/24",
            "zone-oob", "Console server with cellular: core and distribution consoles", "OMxxxxxx01", "SR-0921",
            modules="48× serial · LTE", power="2× AC"),
       _dev("C01-OOB-02", "console-server", OPEN, "OM2248-L", "opengear", "DC-N", "A01", "42", "10.1.250.6/24",
            "zone-oob", "Console server with cellular: firewalls, hubs, DC leafs, WLCs", "OMxxxxxx02", "SR-0922",
            modules="48× serial · LTE", power="2× AC"),
       _dev("C01-UPS-A", "ups", EATON, "93PM 100 kW", "", "DC-N", "", "", "10.1.240.81/22", "zone-mgmt",
            "DC-N UPS, power feed A", "EAxxxxxx0A", "SR-0931", modules="Network card", power="100 kW"),
       _dev("C01-UPS-B", "ups", EATON, "93PM 100 kW", "", "DC-N", "", "", "10.1.240.82/22", "zone-mgmt",
            "DC-N UPS, power feed B", "EAxxxxxx0B", "SR-0932", modules="Network card", power="100 kW")]
)

# Access stacks: code, closet, rack, stack members, mgmt IP, zone
STACKS = [("N1", "MDF-N", "M01", 3, "10.1.240.21", "zone-corp"), ("N2", "IDF-N2", "R01", 3, "10.1.240.22", "zone-corp"),
          ("N3", "IDF-N3", "R01", 3, "10.1.240.23", "zone-corp"), ("N4", "IDF-N4", "R01", 3, "10.1.240.24", "zone-corp"),
          ("N5", "IDF-N5", "R01", 3, "10.1.240.25", "zone-corp"), ("S1", "MDF-S", "M01", 3, "10.1.240.31", "zone-corp"),
          ("S2", "IDF-S2", "R01", 3, "10.1.240.32", "zone-corp"), ("S3", "IDF-S3", "R01", 3, "10.1.240.33", "zone-legal"),
          ("S4", "IDF-S4", "R01", 3, "10.1.240.34", "zone-legal"), ("C1", "IDF-C1", "R01", 2, "10.1.240.41", "zone-corp"),
          ("C2", "IDF-C2", "R01", 2, "10.1.240.42", "zone-corp")]
STACK = {s[0]: s for s in STACKS}
for _code, _closet, _rack, _members, _ip, _zone in STACKS:
    for _m in range(1, _members + 1):
        DEVICES.append(_dev(
            f"C01-ACC-{_code}-{_m}", "access-switch", CISCO, "Catalyst 9300-48UXM", "ios-xe", _closet, _rack,
            str({"M01": 36}.get(_rack, 40) - _m + 1), f"{_ip}/22" if _m == 1 else "", _zone,
            f"Floor {_code} access stack member {_m}" + (" (active)" if _m == 1 else " (standby)" if _m == 2 else ""),
            f"FOCxxxx{_code}{_m}", f"SR-1{_code}{_m}", f"C01-ACC-{_code}", str(_m),
            modules="48× mGig UPOE+ · 8× 25G network module", power="2× 1100 W AC"))
# A rack UPS in every IDF and in MDF-S (the facts' C01-UPS-N2 … C2, .83–.92)
for _n, _code in enumerate(("N2", "N3", "N4", "N5", "S1", "S2", "S3", "S4", "C1", "C2")):
    DEVICES.append(_dev(f"C01-UPS-{_code}", "ups", APC, "Smart-UPS SRT 3000", "", STACK[_code][1], STACK[_code][2], "1",
                        f"10.1.240.{83 + _n}/22", "zone-mgmt", f"{STACK[_code][1]} rack UPS (network card)",
                        f"ASxxxxxx{_code}", f"SR-15{_n:02d}", modules="Network card", power="3 kVA"))

# End devices, counted per floor on the physical page
_cam, _ap_ip, _prn_ip, _rm_ip = iter(range(1, 61)), iter(range(10, 200)), iter(range(10, 200)), iter(range(10, 200))
for _code, _floor, _closet, _aps, _cams, _rooms in FLOORS:
    for _n in range(1, _aps + 1):
        DEVICES.append(_dev(f"C01-AP-{_code}-{_n:02d}", "access-point", CISCO, "C9136I", "", _floor, "", "",
                            f"10.1.242.{next(_ap_ip)}/23", "zone-mgmt", f"{_floor} ceiling AP {_n}",
                            f"FJCxx{_code}{_n:02d}"))
    for _n in (1, 2):
        DEVICES.append(_dev(f"C01-PRN-{_code}-{_n:02d}", "printer", CANON, "imageRUNNER ADVANCE DX C5870i", "", _floor,
                            "", "", f"10.1.44.{next(_prn_ip)}/23", "zone-print", f"{_floor} print corner {_n}",
                            f"CNxxx{_code}{_n}"))
    for _n in range(_cams):
        _c = next(_cam)
        DEVICES.append(_dev(f"C01-CAM-{_c:03d}", "camera", AXIS, "P3268-LV", "", _floor, "", "",
                            f"10.1.128.{20 + _c}/22", "zone-building", f"{_floor} corridor and entrance camera",
                            f"AXCAMx{_c:03d}"))
    for _n in range(1, _rooms + 1):
        _room = f"{_code[0]}{_code[1]}{_n:02d}"
        DEVICES.append(_dev(f"C01-RM-{_room}", "room-system", CISCO, "Room Bar", "", _floor, "", "",
                            f"10.1.136.{next(_rm_ip)}/23", "zone-rooms", f"Meeting room {_room}",
                            f"FOCRMx{_room}"))
for _n, (_b, _floor) in enumerate((("N", "N-L1"), ("S", "S-L1"), ("C", "C-L1"))):
    DEVICES.append(_dev(f"C01-BADGE-{_b}", "door-controller", MERCURY, "LP4502", "", _floor, "", "",
                        f"10.1.132.{10 + _n}/24", "zone-building", f"Badge controller, {_floor[0]} building",
                        f"MRxxxx0{_n + 1}"))
    DEVICES.append(_dev(f"C01-BMS-{_b}", "bms-controller", TRIDIUM, "JACE 9000", "", _floor, "", "",
                        f"10.1.133.{10 + _n}/24", "zone-building",
                        f"Building management controller, {_floor[0]} building (contractor managed)",
                        f"TRxxxx0{_n + 1}"))

DEV = {d["name"]: d for d in DEVICES}


# ------------------------------------------------------------------ cables
def _cable(labels, a, b, ctype, color, speed, media, vlans="", lag="", name=""):
    return {"labels": labels, "a": a, "b": b, "type": ctype, "color": color, "speed": speed, "media": media,
            "vlans": vlans, "lag": lag, "name": name or lag}


# Campus APs tunnel to the WLC pair, so the wireless VLANs (115, 215, 199, 700) ride Po42, never the access trunks.
FLOOR_N = "110, 120, 130, 211, 800, 810, 820, 850, 990"
FLOOR_S = "111, 120, 130, 210, 800, 810, 820, 850, 990"
FLOOR_C = "112, 120, 130, 211, 800, 810, 820, 850, 990"
DC_VLANS = "400, 410, 420, 430, 440"
DAC, SMF, MMF, CAT = ("dac-passive", "111111", "DAC"), ("smf-os2", "ffeb3b", "SMF OS2"), ("mmf-om4", "00bcd4", "MMF OM4"), \
    ("cat6a", "2196f3", "Cat6A")
_num = iter(range(1, 100))
_lbl = lambda: f"C01-CBL-{next(_num):05d}"  # noqa: E731


def _c(n, a, b, kind, speed, vlans="", lag="", name=""):
    return _cable([_lbl() for _ in range(n)], a, b, kind[0], kind[1], speed, kind[2], vlans, lag, name)


CABLES = [
    _c(1, ["C01-EFW-01:ha1"], ["C01-EFW-02:ha1"], DAC, "10G", "", "HA-E"),
    _c(1, ["C01-ISFW-01:ha1"], ["C01-ISFW-02:ha1"], DAC, "10G", "", "HA-I"),
    _c(2, ["C01-ISFW-01:ethernet1/3", "C01-ISFW-01:ethernet1/4"], ["C01-EFW-01:ethernet1/3", "C01-EFW-01:ethernet1/4"],
       DAC, "2×10G", "", "Po43"),
    _c(2, ["C01-ISFW-02:ethernet1/3", "C01-ISFW-02:ethernet1/4"], ["C01-EFW-02:ethernet1/3", "C01-EFW-02:ethernet1/4"],
       DAC, "2×10G", "", "Po43"),
    _c(2, ["C01-CORE-01:Twe1/0/1", "C01-CORE-02:Twe1/0/1"], ["C01-ISFW-01:ethernet1/1", "C01-ISFW-01:ethernet1/2"],
       MMF, "2×25G", "", "Po40"),
    _c(2, ["C01-CORE-01:Twe1/0/2", "C01-CORE-02:Twe1/0/2"], ["C01-ISFW-02:ethernet1/1", "C01-ISFW-02:ethernet1/2"],
       MMF, "2×25G", "", "Po40"),
    _c(2, ["C01-ISFW-01:ethernet1/5", "C01-ISFW-01:ethernet1/6"], ["C01-DCSW-01:Eth1/47", "C01-DCSW-02:Eth1/47"],
       DAC, "2×25G", DC_VLANS, "Po41"),
    _c(2, ["C01-ISFW-02:ethernet1/5", "C01-ISFW-02:ethernet1/6"], ["C01-DCSW-01:Eth1/48", "C01-DCSW-02:Eth1/48"],
       DAC, "2×25G", DC_VLANS, "Po41"),
    _c(2, ["C01-CORE-01:Twe1/0/5", "C01-CORE-02:Twe1/0/5"], ["C01-WLC-01:Te0/0/0", "C01-WLC-01:Te0/0/1"],
       MMF, "2×10G", "115, 199, 215, 700, 990", "Po42"),
    _c(2, ["C01-CORE-01:Twe1/0/6", "C01-CORE-02:Twe1/0/6"], ["C01-WLC-02:Te0/0/0", "C01-WLC-02:Te0/0/1"],
       MMF, "2×10G", "115, 199, 215, 700, 990", "Po42"),
    _c(2, ["C01-EFW-01:ethernet1/5", "C01-EFW-01:ethernet1/6"], ["C01-DCSW-01:Eth1/45", "C01-DCSW-02:Eth1/45"],
       DAC, "2×10G", "600, 610", "Po44"),
    _c(2, ["C01-EFW-02:ethernet1/5", "C01-EFW-02:ethernet1/6"], ["C01-DCSW-01:Eth1/46", "C01-DCSW-02:Eth1/46"],
       DAC, "2×10G", "600, 610", "Po44"),
    _c(2, ["C01-CORE-01:Hu1/0/50", "C01-CORE-01:Hu1/0/51"], ["C01-CORE-02:Hu1/0/50", "C01-CORE-02:Hu1/0/51"], DAC,
       "2×100G", "", "Po1"),
    _c(2, ["C01-DIST-S-01:Hu1/0/27", "C01-DIST-S-01:Hu1/0/28"], ["C01-DIST-S-02:Hu1/0/27", "C01-DIST-S-02:Hu1/0/28"],
       DAC, "2×100G", "", "", "SVL"),
    _c(1, ["C01-DIST-S-01:Twe1/0/24"], ["C01-DIST-S-02:Twe1/0/24"], MMF, "10G", "", "", "DAD"),
    _c(2, ["C01-DCSW-01:Eth1/53", "C01-DCSW-01:Eth1/54"], ["C01-DCSW-02:Eth1/53", "C01-DCSW-02:Eth1/54"], DAC,
       "2×100G", "", "Po1"),
    _c(1, ["C01-WLC-01:RP"], ["C01-WLC-02:RP"], ("cat6", "9e9e9e", "Cat6"), "1G", "", "", "RP"),
    _c(1, ["C01-CORE-01:Hu1/0/49"], ["C01-DIST-S-01:Hu1/0/25"], SMF, "100G", "", "", "P2P-NS-E"),
    _c(1, ["C01-CORE-02:Hu1/0/49"], ["C01-DIST-S-02:Hu1/0/25"], SMF, "100G", "", "", "P2P-NS-W"),
    _c(2, ["C01-CORE-01:Te1/0/31", "C01-CORE-02:Te1/0/31"], ["C01-ACC-C1-1:Te1/1/1", "C01-ACC-C1-2:Te2/1/1"],
       SMF, "2×10G", FLOOR_C, "Po31"),
    _c(2, ["C01-CORE-01:Te1/0/32", "C01-CORE-02:Te1/0/32"], ["C01-ACC-C2-1:Te1/1/1", "C01-ACC-C2-2:Te2/1/1"],
       SMF, "2×10G", FLOOR_C, "Po32"),
]
for _k, _code in enumerate(("N1", "N2", "N3", "N4", "N5")):
    CABLES.append(_c(2, [f"C01-CORE-01:Twe1/0/{11 + _k}", f"C01-CORE-02:Twe1/0/{11 + _k}"],
                     [f"C01-ACC-{_code}-1:Twe1/1/1", f"C01-ACC-{_code}-3:Twe3/1/1"], MMF, "2×25G", FLOOR_N,
                     f"Po{11 + _k}"))
for _k, _code in enumerate(("S1", "S2", "S3", "S4")):
    CABLES.append(_c(2, [f"C01-DIST-S-01:Twe1/0/{1 + _k}", f"C01-DIST-S-02:Twe1/0/{1 + _k}"],
                     [f"C01-ACC-{_code}-1:Twe1/1/1", f"C01-ACC-{_code}-3:Twe3/1/1"], MMF, "2×25G", FLOOR_S,
                     f"Po{21 + _k}"))
# Links the facts don't list, chosen so the hubs, hosts, storage and recorders are connected (drawing's choice):
# each hub's underlay port to its edge firewall and overlay port to its ISFW; every host, the SAN and the backup
# store on both DC leafs (vPC); the two recorders on the core pair.
CABLES += [
    _c(2, ["C01-EFW-01:ethernet1/7", "C01-EFW-02:ethernet1/7"], ["C01-SDW-01:port1", "C01-SDW-02:port1"], DAC, "10G",
       "", "", "SDW-U"),
    _c(2, ["C01-ISFW-01:ethernet1/7", "C01-ISFW-02:ethernet1/7"], ["C01-SDW-01:port2", "C01-SDW-02:port2"], DAC,
       "10G", "", "", "SDW-O"),
]
HOSTS = [f"C01-HV-0{n}" for n in range(1, 9)] + ["C01-HV-L1", "C01-HV-L2", "C01-SAN-01", "C01-BKP-01"]
for _k, _host in enumerate(HOSTS):
    _vl = {"C01-HV-L1": "440", "C01-HV-L2": "440", "C01-SAN-01": "410", "C01-BKP-01": "430"}.get(
        _host, "400, 410, 420, 430, 600, 610")
    CABLES.append(_c(2, [f"C01-DCSW-01:Eth1/{1 + _k}", f"C01-DCSW-02:Eth1/{1 + _k}"], [f"{_host}:nic1", f"{_host}:nic2"],
                     DAC, "2×25G", _vl, f"Po{101 + _k}"))
CABLES.append(_c(2, ["C01-CORE-01:Twe1/0/40", "C01-CORE-02:Twe1/0/40"], ["C01-NVR-01:eth0", "C01-NVR-02:eth0"], MMF,
                 "10G", "", "", "NVR"))
# The DC-N UPS network cards and the console servers' network ports on the core pair (the office standard's
# pattern; drawing's choice): UPS cards in NET-MGMT, console servers in OOB.
CABLES += [_c(1, [f"C01-CORE-0{k}:Twe1/0/{port}"], [f"{dev}:{nic}"], ("cat6a", "2196f3", "Cat6A"), "1G", "", "",
              f"MGMT-{dev[4:]}")
           for k, port, dev, nic in ((1, 41, "C01-UPS-A", "nmc"), (2, 41, "C01-UPS-B", "nmc"),
                                     (1, 42, "C01-OOB-01", "net1"), (2, 42, "C01-OOB-02", "net1"))]
# The core pair's StackWise Virtual dual-active detection link (Po1 is the SVL); last, so earlier labels keep their numbers.
CABLES.append(_c(1, ["C01-CORE-01:Twe1/0/48"], ["C01-CORE-02:Twe1/0/48"], MMF, "10G", "", "", "DAD-CORE"))
# Layer 2 paths settled 2026-10-18 (appended, so earlier labels keep their numbers): NET-MGMT to the DC leafs for
# DC-N's management ports, and the guest and quarantine VLANs from the core to the edge pair's guest interface.
CABLES += [
    _c(2, ["C01-CORE-01:Twe1/0/3", "C01-CORE-02:Twe1/0/3"], ["C01-DCSW-01:Eth1/44", "C01-DCSW-02:Eth1/44"],
       MMF, "2×25G", "990", "Po45"),
    _c(2, ["C01-CORE-01:Twe1/0/7", "C01-CORE-02:Twe1/0/7"], ["C01-EFW-01:ethernet1/8", "C01-EFW-01:ethernet1/9"],
       MMF, "2×10G", "199, 700", "Po46"),
    _c(2, ["C01-CORE-01:Twe1/0/8", "C01-CORE-02:Twe1/0/8"], ["C01-EFW-02:ethernet1/8", "C01-EFW-02:ethernet1/9"],
       MMF, "2×10G", "199, 700", "Po46"),
]

# The access VLAN of each end device's switch port.
ACCESS_VLAN = {"printer": 130, "camera": 800, "door-controller": 810, "bms-controller": 820, "room-system": 850,
               "access-point": 990, "nvr": 800, "ups": 990, "console-server": 991}
_drop = iter(range(10001, 20000))
_port: dict[str, int] = {}
for d in DEVICES:
    # End devices sit on a floor; a rack UPS sits in its floor's closet.
    code = next((f[0] for f in FLOORS if d["location"] == f[1] or (d["role"] == "ups" and d["location"] == f[2])), "")
    if not code or d["role"] not in ACCESS_VLAN:
        continue
    stack, members = f"C01-ACC-{code}", STACK[code][3]
    n = _port.get(code, 0)
    _port[code] = n + 1
    member = n % members + 1
    CABLES.append(_cable([f"C01-CBL-{next(_drop)}"], [f"{stack}-{member}:Tw{member}/0/{n // members + 1}"],
                         [f"{d['name']}:eth0"], "cat6a", "2196f3", "2.5G" if d["role"] == "access-point" else "1G",
                         "Cat6A", "", "", f"MGMT-{d['name'][4:]}" if d["role"] == "ups" else ""))

CIRCUITS = [
    {"cid": "C01-ISP1-0001", "provider": "Provider A", "type": "Dedicated internet, fiber", "speed": "10G",
     "rate": 10_000_000, "label": "ISP-1 · 10 Gb/s DIA · BGP", "handoff": "C01-EFW-01/02 ethernet1/1",
     "media": "SMF"},
    {"cid": "C01-ISP2-0001", "provider": "Provider B", "type": "Dedicated internet, fiber", "speed": "1G",
     "rate": 1_000_000, "label": "ISP-2 · 1 Gb/s DIA · BGP", "handoff": "C01-EFW-01/02 ethernet1/2", "media": "Cat6"},
    {"cid": "C01-DCI1-0001", "provider": "Carrier D", "type": "Carrier Ethernet", "speed": "10G", "rate": 10_000_000,
     "label": "DCI-1 · 10 Gb/s to C02", "handoff": "C01-DCSW-01", "media": "SMF"},
    {"cid": "C01-DCI2-0001", "provider": "Carrier E", "type": "Carrier Ethernet", "speed": "10G", "rate": 10_000_000,
     "label": "DCI-2 · 10 Gb/s to C02 (diverse path)", "handoff": "C01-DCSW-02", "media": "SMF"},
]

# SSIDs: ssid, security, VLAN, zone, notes
SSIDS = [
    ("SR-CORP", "WPA3-Enterprise · EAP-TLS", 115, "zone-corp",
     "Staff; NAC returns VLAN 115 or 215 by identity group"),
    ("SR-GUEST", "Open · captive portal · client isolation", 700, "zone-guest",
     "Visitors; anchored on the WLC pair, never routed internally"),
    ("SR-IOT", "WPA3-Personal · per-device key from the NAC", 850, "zone-rooms", "Meeting-room systems"),
]
BRANCH_SSIDS = [
    ("SR-CORP", "WPA3-Enterprise · EAP-TLS", 110, "zone-corp", "Staff; FlexConnect, switched locally to 110 or 210"),
    ("SR-GUEST", "Open · captive portal · client isolation", 700, "zone-guest",
     "Visitors; FlexConnect, local internet breakout"),
]

# ------------------------------------------------------------------ flows
# id, from, to, what, verdict, conditions, owner
FLOWS = [
    ("F01", "Corporate users", "Internet and SaaS", "Web, email, files, meetings (HTTPS) through the edge's URL filtering",
     "Permitted", "", "Security"),
    ("F02", "Corporate users", "DC applications", "Practice management and billing (HTTPS)", "Permitted", "",
     "App owner: Finance systems"),
    ("F03", "Corporate and legal users", "DC infrastructure", "Directory, DNS, DHCP relay, NTP, print servers",
     "Permitted", "", "Infrastructure"),
    ("F04", "Corporate users", "DC data", "Anything direct to databases or file servers' admin ports", "Denied", "",
     "Infrastructure"),
    ("F05", "DC applications", "DC data", "Database ports from the app servers only", "Permitted", "",
     "App owner: Finance systems"),
    ("F06", "Legal users", "Legal systems", "Document management and matter database (HTTPS)", "Permitted", "",
     "Legal IT"),
    ("F07", "Corporate users", "Legal systems", "Anything", "Denied", "The ethical wall", "General Counsel"),
    ("F08", "Legal users", "Internet, SaaS, DC applications, DC infrastructure", "As F01–F03", "Permitted", "",
     "Security"),
    ("F09", "Legal systems", "Internet", "Anything", "Denied", "", "Legal IT"),
    ("F10", "Remote users (VPN)", "As their identity group", "CORP or LEGAL rules apply by group", "Conditional",
     "MFA, device posture", "Security"),
    ("F11", "Voice", "Cloud phone service", "SIP and media", "Permitted", "", "Infrastructure"),
    ("F12", "Print servers", "Printers", "Print jobs, printer management", "Permitted", "", "Infrastructure"),
    ("F13", "Printers", "Internet (mail relay)", "Scan-to-email through the SaaS mail relay", "Conditional",
     "One destination", "Infrastructure"),
    ("F14", "Guests", "Internet", "Web", "Permitted", "Rate-limited", "Security"),
    ("F15", "Guests", "Any internal zone", "Anything", "Denied", "", "Security"),
    ("F16", "Meeting rooms", "Cloud meeting service", "Meeting traffic", "Permitted", "", "Facilities IT"),
    ("F17", "Corporate users", "Meeting rooms", "Casting to room displays", "Conditional", "Casting ports only",
     "Facilities IT"),
    ("F18", "Cameras", "Recorders (NVR)", "Video", "Permitted", "", "Facilities"),
    ("F19", "Building systems", "Internet", "Anything", "Denied", "", "Facilities"),
    ("F20", "Facilities contractor", "BMS", "Remote support through the edge", "Conditional",
     "Vendor VPN + MFA, ticket, logged", "Facilities"),
    ("F21", "PAM jump hosts", "Network management", "SSH, HTTPS to device management", "Conditional",
     "Named admins, MFA, sessions recorded", "Network team"),
    ("F22", "Any other zone", "Network management", "Anything", "Denied", "", "Network team"),
    ("F23", "Network management", "DC infrastructure", "Syslog, NTP, TACACS+, RADIUS", "Permitted", "",
     "Network team"),
    ("F24", "DC infrastructure (log collectors)", "MSSP SIEM (cloud)", "Logs over TLS", "Conditional",
     "One destination", "Security"),
    ("F25", "Branch and regional users", "DC applications and infrastructure",
     "Over SD-WAN, same rules as campus, enforced at the hub's ISFW", "Permitted", "", "Network team"),
    ("F26", "Branch users", "Internet and SaaS", "Local breakout, branch firewall security profile", "Permitted", "",
     "Security"),
    ("F27", "DC applications", "Cloud client-portal spoke", "Application APIs over the private circuit", "Permitted",
     "", "App owner: Client portal"),
    ("F28", "Backup", "C02 replica and cloud vault", "Backup replication", "Permitted", "", "Infrastructure"),
    ("F29", "Internet", "DMZ reverse proxy", "Client portal (HTTPS)", "Permitted", "", "App owner: Client portal"),
    ("F30", "DMZ reverse proxy", "DC applications", "One named API", "Conditional", "One API, from the proxies only",
     "App owner: Client portal"),
    ("F31", "Extranet client", "Extranet landing server",
     "Secure file transfer (SFTP) over the client's dedicated tunnel", "Conditional", "One client, one peer",
     "Client service lead"),
    ("F32", "C01-APP-LEG-03", "192.0.2.44 over TUN-PHX", "Unknown at first (the Phoenix tunnel)", "Conditional",
     "Under review, no owner, decision due", "none yet"),
    ("F33", "DC infrastructure (NAC nodes, monitoring)", "Network management",
     "RADIUS change of authorization; SNMP and telemetry polling; config backup", "Conditional",
     "Named sources only", "Network team"),
]

# The branch site table (sheet 6): code, site, typical, staff, prefix, underlays, legal staff on site
BRANCHES = [
    ("C11", "Ashcombe", "BR-M", 64, "DIA 500M + broadband + 5G", "Yes"),
    ("C12", "Bellhaven", "BR-S", 18, "Broadband + 5G", "No"),
    ("C13", "Corran", "BR-S", 12, "Broadband + 5G", "No"),
    ("C14", "Dunmere", "BR-M", 41, "DIA 500M + broadband + 5G", "Yes"),
    ("C15", "Elmstead", "BR-S", 9, "Broadband + 5G", "No"),
    ("C16", "Farrow", "BR-S", 22, "Broadband + 5G", "No"),
    ("C17", "Glenwick", "BR-M", 55, "DIA 500M + broadband + 5G", "No"),
    ("C18", "Harlow Point", "BR-S", 14, "Broadband + 5G", "No"),
    ("C19", "Ivel", "BR-S", 8, "Broadband + 5G", "No"),
    ("C20", "Juniper Bay", "BR-S", 19, "Broadband + 5G", "No"),
    ("C21", "Kestrel Quay", "BR-M", 70, "DIA 500M + broadband + 5G", "Yes"),
    ("C22", "Larch Hill", "BR-S", 11, "Broadband + 5G", "No"),
    ("C23", "Millbrook", "BR-S", 16, "Broadband + 5G", "No"),
    ("C24", "Northwood", "BR-S", 25, "Broadband + 5G", "No"),
]
