"""City of Halvern: the fictional city the M01 municipal template is drawn for.

One source for the template's shapes and for the sample NetBox export, so the
two never disagree. The drawn site is CH1, the Halvern Civic Center: City Hall
and the Police Department in one building, sharing a basement data room where
police keep their own locked rack. The Main Library (LB1) is the second export.
The water treatment plant, county 911 dispatch and the state CJIS network are
boundaries: drawn as an edge with a label, never opened up.
Addresses are private or documentation ranges; serials and circuit IDs are placeholders.
"""

from __future__ import annotations

SITE = {"code": "CH1", "name": "Halvern Civic Center", "slug": "ch1"}
BRANCH = {"code": "LB1", "name": "Halvern Main Library", "slug": "lb1"}

# Zones: slug, short name, title, band code, what lives there, rule, (fill, stroke, font)
ZONES = [
    ("zone-internet", "INTERNET", "Internet and providers", "OUT", "ISP-A, ISP-B, SaaS, staff on the VPN, patrol cars on cellular",
     "Untrusted. Everything from here ends on the firewall.", ("#F8FAFC", "#CBD5E1", "#475569")),
    ("zone-partner", "PARTNER", "State, county and vendors", "OUT", "The state CJIS router, the county dispatch link, vendor support",
     "Not ours. We draw the edge and the one door through it; the owner draws the rest.", ("#F5F5F4", "#C8C2BC", "#57534E")),
    ("zone-water", "WATER", "Water plant (boundary)", "OUT", "The utility's treatment plant network",
     "Out of scope. No city zone has a path into it, and none is drawn.", ("#F0F7FA", "#B9D3DE", "#3F6F82")),
    ("zone-edge", "EDGE", "Firewall and remote access", "EDGE", "The firewall HA pair, the staff and patrol VPN pools",
     "The one place zones meet. Every inter-zone packet is inspected here.", ("#F1F5F9", "#94A3B8", "#334155")),
    ("zone-public", "PUBLIC", "Public Wi-Fi", "PUBLIC", "Lobby and council chamber Wi-Fi for residents and visitors",
     "Internet only, filtered. Clients can't see each other or anything the city owns.", ("#FDF8F3", "#F2CFA8", "#D97706")),
    ("zone-staff", "STAFF", "City staff", "CITY", "City Hall computers, wired and on HALVERN-STAFF",
     "Reaches the internet, city servers and printers. Never police systems.", ("#F4F7FE", "#B3C8F8", "#2563EB")),
    ("zone-voice", "VOICE", "Voice", "CITY", "Desk phones in both wings",
     "Talks to the hosted phone service only.", ("#F2F9FC", "#A6D4EB", "#0284C7")),
    ("zone-pay", "PAY", "Payment counters", "CITY", "Card terminals at the utility billing and permit counters",
     "Talks to the payment processor only.", ("#FEF6F6", "#F5C2C2", "#DC2626")),
    ("zone-servers", "SERVERS", "City servers", "CITY", "Virtualization hosts, the backup appliance",
     "Reached from staff and VPN users on named ports. Backs up offsite.", ("#F3FAF9", "#AADAD5", "#0D9488")),
    ("zone-cjis", "CJIS", "Police (CJIS)", "SAFETY", "Police workstations, records and evidence servers, PD-SECURE Wi-Fi",
     "Walled off. Reached from police devices, the state router and dispatch on named hosts only.", ("#F5F3FF", "#C4B5FD", "#6D28D9")),
    ("zone-building", "BLDG", "Building systems", "FAC", "Cameras, the NVR, door access, HVAC controls",
     "Each system talks to its own server only. No internet.", ("#FDF4F9", "#F3B8D6", "#DB2777")),
    ("zone-field", "FIELD", "Traffic signals and field", "FAC", "The traffic signal central system and signal cabinets on city fiber",
     "Signals talk to their central system only. Vendor support by booked session.", ("#FEFCE8", "#E9D97A", "#A16207")),
    ("zone-mgmt", "MGMT", "Network management", "FAC", "Firewall, switch, AP and UPS management; the console server",
     "Reached only by IT, through the VPN with MFA.", ("#F0FAFC", "#A5DCE8", "#0891B2")),
]
ZONE = {z[0]: z for z in ZONES}

BANDS = [
    ("OUT", "OUTSIDE · INTERNET, STATE & COUNTY", ("internet", "isp", "wan", "cloud", "saas", "remote-users", "partner", "state", "county", "water", "boundary")),
    ("EDGE", "EDGE · FIREWALL & REMOTE ACCESS", ("edge", "dmz", "vpn", "perimeter")),
    ("PUBLIC", "PUBLIC · RESIDENTS & VISITORS", ("public", "guest", "patron", "library")),
    ("CITY", "CITY HALL · STAFF & SERVICES", ("staff", "corp", "it", "voice", "pay", "servers", "office")),
    ("SAFETY", "PUBLIC SAFETY · POLICE (CJIS)", ("cjis", "police", "pd", "safety", "fire")),
    ("FAC", "FACILITIES, FIELD & MANAGEMENT", ("building", "cameras", "security", "field", "signals", "mgmt", "oob")),
]

# VLANs: vid, name, zone, subnet, gateway text
VLANS = [
    (10, "STAFF-WIRED", "zone-staff", "10.30.10.0/23", "FW HA .1"),
    (11, "STAFF-WIFI", "zone-staff", "10.30.12.0/22", "FW HA .1"),
    (20, "VOICE", "zone-voice", "10.30.20.0/24", "FW HA .1"),
    (25, "PAY-COUNTER", "zone-pay", "10.30.25.0/26", "FW HA .1"),
    (40, "SERVERS", "zone-servers", "10.30.40.0/24", "FW HA .1"),
    (45, "BACKUP", "zone-servers", "10.30.45.0/24", "FW HA .1"),
    (60, "PD-WORKSTATIONS", "zone-cjis", "10.31.60.0/24", "FW HA .1"),
    (61, "PD-SERVERS", "zone-cjis", "10.31.61.0/24", "FW HA .1"),
    (62, "PD-WIFI", "zone-cjis", "10.31.62.0/24", "FW HA .1"),
    (70, "PUBLIC-WIFI", "zone-public", "172.20.0.0/22", "FW HA .1"),
    (80, "CAMERAS", "zone-building", "10.30.80.0/24", "FW HA .1"),
    (81, "DOOR-ACCESS", "zone-building", "10.30.81.0/24", "FW HA .1"),
    (82, "HVAC", "zone-building", "10.30.82.0/24", "FW HA .1"),
    (90, "SIGNALS", "zone-field", "10.32.90.0/24", "FW HA .1"),
    (99, "NET-MGMT", "zone-mgmt", "10.30.99.0/24", "FW HA .1"),
]
# The library: patron Wi-Fi and public PCs on its own filtered internet line, staff back to City Hall on city fiber.
BRANCH_VLANS = [
    (10, "STAFF", "zone-staff", "10.40.10.0/24"), (20, "VOICE", "zone-voice", "10.40.20.0/24"),
    (70, "PATRON-WIFI", "zone-public", "172.21.0.0/22"), (71, "PUBLIC-PCS", "zone-public", "172.21.8.0/24"),
    (99, "NET-MGMT", "zone-mgmt", "10.40.99.0/24"),
]

CISCO, PALO, DELL, HPE, EATON, OPEN, MERAKI, HANWHA, KYOCERA, VERIFONE, GENETEC, TRANE, ECONOLITE = (
    "Cisco", "Palo Alto Networks", "Dell", "HPE", "Eaton", "Opengear", "Cisco Meraki", "Hanwha Vision",
    "Kyocera", "Verifone", "Genetec", "Trane", "Econolite")

# Asset criticality by role: what stops for the city when the box fails. The firewall pair, the core and the
# hosts stop City Hall and the police at once; an access stack, the backup, the UPSes, door access or the signal
# central system stop a wing, a safeguard or the intersections' coordination; the rest inconvenience a room.
CRITICALITY = {"firewall": "critical", "core-switch": "critical", "hypervisor": "critical",
               "access-switch": "high", "storage": "high", "ups": "high", "door-controller": "high",
               "signal-system": "high", "router": "high",
               "access-point": "medium", "console-server": "medium", "nvr": "medium", "hvac-controller": "medium",
               "payment-terminal": "medium",
               "printer": "low", "camera": "low", "phone": "low", "public-pc": "low"}


def _dev(name, role, mfr, model, platform, location, rack, pos, ip, zone, desc, serial, tag, vc="", vcpos="",
         sw="", contract="", modules="", power="", status="active"):
    return {"name": name, "role": role, "manufacturer": mfr, "device_type": model, "platform": platform,
            "location": location, "rack": rack, "position": pos, "primary_ip4": ip, "tags": zone,
            "description": desc, "serial": serial, "asset_tag": tag, "virtual_chassis": vc, "vc_position": vcpos,
            "status": status, "cf_sw_version": sw, "cf_support_contract": contract,
            "cf_lifecycle": "In support" if contract else "", "x_modules": modules, "x_power": power,
            "cf_ap_mode": "cloud" if role == "access-point" else "", "cf_criticality": CRITICALITY.get(role, "")}


# Rooms: DATA-B is the basement data room (racks R01, R02 city; R03 police, caged, own badge reader).
# IDF-C2 is City Hall's floor 2 closet; IDF-PD is the police wing closet (locked, police badge only).
DEVICES = [
    _dev("CH1-FW-01", "firewall", PALO, "PA-1410", "panos", "DATA-B", "R01", "40", "10.30.99.2/24",
         "zone-edge", "Internet edge and inter-zone firewall (HA active)", "PAxxxxxxxx01", "HV-0001",
         sw="PAN-OS 11.1.x", contract="Premium support", modules="2× 10G SFP+ (to core) · 2× 1G RJ45 WAN · HA1/HA2",
         power="2× AC PSU"),
    _dev("CH1-FW-02", "firewall", PALO, "PA-1410", "panos", "DATA-B", "R02", "40", "10.30.99.3/24",
         "zone-edge", "Internet edge and inter-zone firewall (HA passive)", "PAxxxxxxxx02", "HV-0002",
         sw="PAN-OS 11.1.x", contract="Premium support", modules="2× 10G SFP+ (to core) · 2× 1G RJ45 WAN · HA1/HA2",
         power="2× AC PSU"),
    _dev("CH1-OOB-01", "console-server", OPEN, "OM1204-4E-L", "opengear", "DATA-B", "R01", "41", "10.30.99.5/24",
         "zone-mgmt", "Out-of-band console with cellular", "OMxxxxxx01", "HV-0003", sw="Opengear 24.x",
         modules="4× serial (FW-01, FW-02, CORE-1, CORE-2) · LTE", power="2× DC"),
    _dev("CH1-CORE-1", "core-switch", CISCO, "C9500-24Y4C", "ios-xe", "DATA-B", "R01", "38", "10.30.99.10/24",
         "zone-mgmt", "Core pair member 1 (StackWise Virtual active)", "FCWxxxxx11", "HV-0010", "CH1-CORE", "1",
         sw="IOS XE 17.12.x", contract="Smart Net NBD", modules="24× 25G SFP28 · 4× 100G · SVL on 1/0/23–24",
         power="2× PWR-C4-950WAC-R"),
    _dev("CH1-CORE-2", "core-switch", CISCO, "C9500-24Y4C", "ios-xe", "DATA-B", "R02", "38", "",
         "zone-mgmt", "Core pair member 2 (StackWise Virtual standby)", "FCWxxxxx12", "HV-0011", "CH1-CORE", "2",
         sw="IOS XE 17.12.x", contract="Smart Net NBD", modules="24× 25G SFP28 · 4× 100G · SVL on 2/0/23–24",
         power="2× PWR-C4-950WAC-R"),
] + [
    _dev(f"CH1-ACC-C1-{n}", "access-switch", CISCO, "C9300-48P", "ios-xe", "DATA-B", "R02",
         str(36 - n), "10.30.99.21/24" if n == 1 else "", "zone-staff",
         f"City Hall floor 1 access stack member {n}" + (" (active)" if n == 1 else ""), f"FOCxxxxx1{n}",
         f"HV-002{n}", "CH1-ACC-C1", str(n), sw="IOS XE 17.12.x", contract="Smart Net NBD",
         modules="48× 1G PoE+ · 4× 10G SFP+ (C9300-NM-4G)", power="1× 715 W PSU")
    for n in (1, 2)
] + [
    _dev(f"CH1-ACC-C2-{n}", "access-switch", CISCO, "C9300-48P", "ios-xe", "IDF-C2", "R01",
         str(22 - n), "10.30.99.22/24" if n == 1 else "", "zone-staff",
         f"City Hall floor 2 access stack member {n}" + (" (active)" if n == 1 else ""), f"FOCxxxxx2{n}",
         f"HV-003{n}", "CH1-ACC-C2", str(n), sw="IOS XE 17.12.x", contract="Smart Net NBD",
         modules="48× 1G PoE+ · 4× 10G SFP+ · 10G-SR to core", power="1× 715 W PSU")
    for n in (1, 2)
] + [
    _dev(f"CH1-ACC-PD-{n}", "access-switch", CISCO, "C9300-48P", "ios-xe", "IDF-PD", "R01",
         str(22 - n), "10.30.99.23/24" if n == 1 else "", "zone-cjis",
         f"Police wing access stack member {n}" + (" (active)" if n == 1 else ""), f"FOCxxxxx3{n}",
         f"HV-004{n}", "CH1-ACC-PD", str(n), sw="IOS XE 17.12.x", contract="Smart Net NBD",
         modules="48× 1G PoE+ · 4× 10G SFP+ · 10G-SR to core", power="1× 715 W PSU")
    for n in (1, 2)
] + [
    _dev("CH1-HV-01", "hypervisor", DELL, "PowerEdge R660", "", "DATA-B", "R01", "30", "10.30.40.11/24",
         "zone-servers", "City virtualization host 1 (directory, files, finance, permits)", "SVCTAGxx01", "HV-0050",
         sw="Hypervisor 8.0", contract="ProSupport NBD", modules="2× 25G SFP28 (DAC) · iDRAC 10.30.99.31",
         power="2× 1100 W"),
    _dev("CH1-HV-02", "hypervisor", DELL, "PowerEdge R660", "", "DATA-B", "R01", "28", "10.30.40.12/24",
         "zone-servers", "City virtualization host 2", "SVCTAGxx02", "HV-0051", sw="Hypervisor 8.0",
         contract="ProSupport NBD", modules="2× 25G SFP28 (DAC) · iDRAC 10.30.99.32", power="2× 1100 W"),
    _dev("CH1-BKP-01", "storage", HPE, "StoreOnce 3720", "", "DATA-B", "R01", "24", "10.30.45.20/24",
         "zone-servers", "City backup appliance, copies to the offsite vault", "CZxxxxxx01", "HV-0052",
         sw="StoreOnce 4.3.x", contract="Foundation Care NBD", modules="2× 10G SFP+", power="2× redundant"),
    # Police rack R03: caged, police badge reader on the cage door, its own UPS. City IT has escorted access.
    _dev("CH1-PD-HV-01", "hypervisor", DELL, "PowerEdge R660", "", "DATA-B", "R03", "30", "10.31.61.11/24",
         "zone-cjis", "Police host (records management, evidence index, police directory)", "SVCTAGxx61", "HV-0061",
         sw="Hypervisor 8.0", contract="ProSupport NBD", modules="2× 25G SFP28 (DAC) · iDRAC 10.30.99.33",
         power="2× 1100 W"),
    _dev("CH1-PD-NAS-01", "storage", DELL, "PowerVault ME5012", "", "DATA-B", "R03", "26", "10.31.61.20/24",
         "zone-cjis", "Evidence storage (interview video, body-worn camera uploads)", "SVCTAGxx62", "HV-0062",
         sw="ME5 firmware 1.2.x", contract="ProSupport NBD", modules="12 bays · 2× 25G iSCSI", power="2× 580 W"),
    _dev("CH1-STATE-RTR", "router", CISCO, "ISR 1121", "", "DATA-B", "R03", "36", "",
         "zone-partner", "State CJIS network router (owned and managed by the state; drawn, not configured)",
         "FGLxxxxx71", "", sw="Managed by the state"),
    _dev("CH1-UPS-01", "ups", EATON, "9PX 3000", "", "DATA-B", "R01", "1", "10.30.99.41/24",
         "zone-mgmt", "Rack R01 UPS (network card)", "EAxxxxxx01", "HV-0070", modules="Network-M3 card",
         power="3 kVA · about 20 min at today's load · generator transfer"),
    _dev("CH1-UPS-02", "ups", EATON, "9PX 3000", "", "DATA-B", "R02", "1", "10.30.99.42/24",
         "zone-mgmt", "Rack R02 UPS (network card)", "EAxxxxxx02", "HV-0071", modules="Network-M3 card",
         power="3 kVA · about 24 min at today's load · generator transfer"),
    _dev("CH1-UPS-03", "ups", EATON, "9PX 2000", "", "DATA-B", "R03", "1", "10.30.99.43/24",
         "zone-mgmt", "Police rack R03 UPS (network card)", "EAxxxxxx03", "HV-0072", modules="Network-M3 card",
         power="2 kVA · about 30 min at today's load · generator transfer"),
    _dev("CH1-NVR-01", "nvr", GENETEC, "Streamvault SV-1000E", "", "DATA-B", "R02", "30", "10.30.80.10/24",
         "zone-building", "City building video recorder (lobby, counters, parking)", "GNxxxxxx01", "HV-0080",
         modules="24 TB"),
    _dev("CH1-DOOR-01", "door-controller", GENETEC, "Synergis Cloud Link", "", "DATA-B", "R02", "28", "10.30.81.10/24",
         "zone-building", "Door access controller (both wings; police doors on their own schedule)", "GNxxxxxx02", "HV-0081"),
    _dev("CH1-BAS-01", "hvac-controller", TRANE, "Tracer SC+", "", "DATA-B", "", "", "10.30.82.10/24",
         "zone-building", "Building automation controller (HVAC, both wings)", "TRxxxxxx01", "HV-0082"),
    _dev("CH1-TSC-01", "signal-system", ECONOLITE, "Centracs server", "", "DATA-B", "R02", "26", "10.32.90.10/24",
         "zone-field", "Traffic signal central system (42 intersections on city fiber)", "ECxxxxxx01", "HV-0090",
         sw="Centracs 3.x", contract="Vendor support annual"),
]
# Endpoints, by area: (area, prefix, AP count, printers, cameras, stack)
AREAS = [
    ("City Hall Floor 1", "C1", 4, 1, 4, "CH1-ACC-C1"),
    ("City Hall Floor 2", "C2", 4, 1, 2, "CH1-ACC-C2"),
    ("Police wing", "PD", 3, 1, 0, "CH1-ACC-PD"),
]
_ap_ip = iter(range(101, 200))
for area, pre, aps, prns, cams, _stack in AREAS:
    police = pre == "PD"
    for n in range(1, aps + 1):
        DEVICES.append(_dev(f"CH1-AP-{pre}-{n:02d}", "access-point", MERAKI, "MR46", "meraki", area, "", "",
                            f"10.30.99.{next(_ap_ip)}/24", "zone-cjis" if police else "zone-staff",
                            f"{area} ceiling AP {n}", f"Q2xx-xx{pre}-{n:02d}", ""))
    for n in range(1, prns + 1):
        DEVICES.append(_dev(f"CH1-PRN-{pre}-{n:02d}", "printer", KYOCERA, "TASKalfa 3554ci", "", area, "", "",
                            (f"10.31.60.{200 + n}/24" if police else f"10.30.11.{200 + (10 if pre == 'C2' else 0) + n}/23"),
                            "zone-cjis" if police else "zone-staff", f"{area} printer", f"KYxxxxx{pre}{n}", ""))
    for n in range(1, cams + 1):
        DEVICES.append(_dev(f"CH1-CAM-{pre}-{n:02d}", "camera", HANWHA, "XNV-8082R", "", area, "", "",
                            f"10.30.80.{20 + (0 if pre == 'C1' else 10) + n}/24", "zone-building",
                            "Lobby, counter and parking camera", f"HWxxxx{pre}{n:02d}", ""))
DEVICES.append(_dev("CH1-AP-CC-01", "access-point", MERAKI, "MR46", "meraki", "Council chamber", "", "",
                    f"10.30.99.{next(_ap_ip)}/24", "zone-public", "Council chamber AP (public and staff SSIDs)",
                    "Q2xx-xxCC-01", ""))
for n in (1, 2):
    DEVICES.append(_dev(f"CH1-PAY-{n:02d}", "payment-terminal", VERIFONE, "P400", "", "City Hall Floor 1", "", "",
                        f"10.30.25.{10 + n}/26", "zone-pay", ["Utility billing counter terminal", "Permit counter terminal"][n - 1],
                        f"VFxxxxxx0{n}", ""))

# LB1, the Main Library: its own E-rate funded, filtered internet line for patrons; staff back to City Hall on city fiber.
BRANCH_DEVICES = [
    _dev("LB1-FW-01", "firewall", PALO, "PA-445", "panos", "LB1-MDF", "CAB-1", "12", "10.40.99.2/24",
         "zone-edge", "Library firewall: patron internet breakout and filter; staff to City Hall", "PAxxxxxxxx21", "HV-0201",
         sw="PAN-OS 11.1.x"),
    _dev("LB1-ACC-1", "access-switch", CISCO, "C9300-48P", "ios-xe", "LB1-MDF", "CAB-1", "10", "10.40.99.10/24",
         "zone-staff", "Library access switch", "FOCxxxxx41", "HV-0202", sw="IOS XE 17.12.x"),
] + [
    _dev(f"LB1-AP-{n:02d}", "access-point", MERAKI, "MR46", "meraki", "Reading room", "", "", f"10.40.99.{100 + n}/24",
         "zone-public", f"Reading room ceiling AP {n}", f"Q2xx-xxLB-{n:02d}", "") for n in (1, 2, 3)
] + [
    _dev(f"LB1-PC-{n:02d}", "public-pc", DELL, "OptiPlex 7020", "", "Reading room", "", "", f"172.21.8.{10 + n}/24",
         "zone-public", f"Public computer {n} (reimaged at every logoff)", f"SVCTAGxx8{n}", "") for n in (1, 2, 3, 4)
] + [
    _dev("LB1-PRN-01", "printer", KYOCERA, "TASKalfa 3554ci", "", "Reading room", "", "", "172.21.8.50/24", "zone-public",
         "Patron print release printer", "KYxxxxxLB1", ""),
]


def _cable(labels, a, b, ctype, color, speed, media, vlans="", lag=""):
    return {"labels": labels, "a": a, "b": b, "type": ctype, "color": color, "speed": speed, "media": media,
            "vlans": vlans, "lag": lag}


CITY_TRUNK = "10, 11, 20, 25, 70, 80, 81, 82, 99"
PD_TRUNK = "20, 60, 62, 99"  # the police wing carries police VLANs, voice and management; no city or public VLAN
FW_TRUNK = "10, 11, 20, 25, 40, 45, 60, 61, 62, 70, 80, 81, 82, 90, 99"
CABLES = [
    _cable(["CH1-CBL-00001", "CH1-CBL-00002"], ["CH1-FW-01:ethernet1/1", "CH1-FW-01:ethernet1/2"],
           ["CH1-CORE-1:Twe1/0/1", "CH1-CORE-2:Twe1/0/1"], "dac-passive", "111111", "2×10G", "DAC", FW_TRUNK, "Po1"),
    _cable(["CH1-CBL-00003", "CH1-CBL-00004"], ["CH1-FW-02:ethernet1/1", "CH1-FW-02:ethernet1/2"],
           ["CH1-CORE-1:Twe1/0/2", "CH1-CORE-2:Twe1/0/2"], "dac-passive", "111111", "2×10G", "DAC", FW_TRUNK, "Po2"),
    _cable(["CH1-CBL-00005"], ["CH1-FW-01:ha1"], ["CH1-FW-02:ha1"], "cat6", "9e9e9e", "1G", "Cat6", "", "HA"),
    _cable(["CH1-CBL-00011", "CH1-CBL-00012"], ["CH1-CORE-1:Twe1/0/11", "CH1-CORE-2:Twe1/0/11"],
           ["CH1-ACC-C1-1:Te1/1/1", "CH1-ACC-C1-2:Te1/1/1"], "dac-passive", "111111", "2×10G", "DAC", CITY_TRUNK, "Po11"),
    _cable(["CH1-CBL-00013", "CH1-CBL-00014"], ["CH1-CORE-1:Twe1/0/12", "CH1-CORE-2:Twe1/0/12"],
           ["CH1-ACC-C2-1:Te1/1/1", "CH1-ACC-C2-2:Te1/1/1"], "mmf-om4", "00bcd4", "2×10G", "MMF OM4", CITY_TRUNK, "Po12"),
    _cable(["CH1-CBL-00015", "CH1-CBL-00016"], ["CH1-CORE-1:Twe1/0/13", "CH1-CORE-2:Twe1/0/13"],
           ["CH1-ACC-PD-1:Te1/1/1", "CH1-ACC-PD-2:Te1/1/1"], "mmf-om4", "7c4dff", "2×10G", "MMF OM4", PD_TRUNK, "Po13"),
    _cable(["CH1-CBL-00021", "CH1-CBL-00022"], ["CH1-CORE-1:Twe1/0/21", "CH1-CORE-2:Twe1/0/21"],
           ["CH1-HV-01:nic1", "CH1-HV-01:nic2"], "dac-passive", "111111", "2×25G", "DAC", "40, 45", "Po21"),
    _cable(["CH1-CBL-00023", "CH1-CBL-00024"], ["CH1-CORE-1:Twe1/0/22", "CH1-CORE-2:Twe1/0/22"],
           ["CH1-HV-02:nic1", "CH1-HV-02:nic2"], "dac-passive", "111111", "2×25G", "DAC", "40, 45", "Po22"),
    _cable(["CH1-CBL-00025"], ["CH1-CORE-1:Twe1/0/14"], ["CH1-BKP-01:port1"], "dac-passive", "111111", "10G", "DAC", "", ""),
    # Police rack R03: its own cage, its own violet patch cords, and only police VLANs on the trunk.
    _cable(["CH1-CBL-00031", "CH1-CBL-00032"], ["CH1-CORE-1:Twe1/0/15", "CH1-CORE-2:Twe1/0/15"],
           ["CH1-PD-HV-01:nic1", "CH1-PD-HV-01:nic2"], "dac-passive", "7c4dff", "2×25G", "DAC", "61", "Po15"),
    _cable(["CH1-CBL-00033"], ["CH1-CORE-1:Twe1/0/16"], ["CH1-PD-NAS-01:port1"], "dac-passive", "7c4dff", "25G", "DAC", "", ""),
    _cable(["CH1-CBL-00034"], ["CH1-FW-01:ethernet1/5"], ["CH1-STATE-RTR:Gi0/1/0"], "cat6", "7c4dff", "1G", "Cat6", "", ""),
    _cable(["CH1-CBL-00035"], ["CH1-FW-02:ethernet1/5"], ["CH1-STATE-RTR:Gi0/1/1"], "cat6", "7c4dff", "1G", "Cat6", "", ""),
    _cable(["CH1-CBL-00041"], ["CH1-ACC-C1-2:Gi2/0/45"], ["CH1-NVR-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["CH1-CBL-00042"], ["CH1-ACC-C1-2:Gi2/0/46"], ["CH1-DOOR-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["CH1-CBL-00043"], ["CH1-ACC-C1-2:Gi2/0/47"], ["CH1-BAS-01:eth0"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["CH1-CBL-00044"], ["CH1-CORE-1:Twe1/0/17"], ["CH1-TSC-01:nic1"], "cat6a", "a16207", "10G", "Cat6A", "", ""),
    # Management drops on the core: 1G copper SFPs, beside the gear they watch.
    _cable(["CH1-CBL-00051"], ["CH1-CORE-1:Twe1/0/20"], ["CH1-UPS-01:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["CH1-CBL-00052"], ["CH1-CORE-2:Twe1/0/20"], ["CH1-UPS-02:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["CH1-CBL-00053"], ["CH1-CORE-2:Twe1/0/19"], ["CH1-UPS-03:nmc"], "cat6", "2196f3", "1G", "Cat6", "", ""),
    _cable(["CH1-CBL-00054"], ["CH1-CORE-1:Twe1/0/19"], ["CH1-OOB-01:net1"], "cat6", "2196f3", "1G", "Cat6", "", ""),
]
# Endpoint drops: APs, printers, cameras and payment terminals on their area's stack.
_STACK_OF = {area: stack for area, _p, _a, _n, _c, stack in AREAS}
_STACK_OF["Council chamber"] = "CH1-ACC-C1"
_port = {}
_drop = iter(range(101, 1000))
for d in DEVICES:
    stack = _STACK_OF.get(d["location"])
    if not stack:
        continue
    n = _port.get(stack, 1)
    _port[stack] = n + 1
    member = (n - 1) % 2 + 1
    iface = f"Gi{member}/0/{(n - 1) // 2 + 1}"
    ap = d["role"] == "access-point"
    police = stack == "CH1-ACC-PD"
    CABLES.append(_cable([f"CH1-CBL-{next(_drop):05d}"], [f"{stack}-{member}:{iface}"], [f"{d['name']}:eth0"],
                         "cat6a" if ap else "cat6", "7c4dff" if police else "2196f3", "1G",
                         "Cat6A" if ap else "Cat6", ("62, 99" if police else "11, 70, 99") if ap else "", ""))

# A stack member's ports carry its member number: CH1-CORE-2's first port is Twe2/0/1.
_MEMBER = {d["name"]: int(d["vc_position"]) for d in DEVICES if d["vc_position"]}


def _member_port(end: str) -> str:
    dev, port = end.split(":", 1)
    m = _MEMBER.get(dev, 1)
    if m > 1:
        for pre in ("Twe1/", "Te1/", "Gi1/"):
            if port.startswith(pre):
                port = f"{pre[:-2]}{m}/{port[len(pre):]}"
    return f"{dev}:{port}"


for _c in CABLES:
    _c["a"], _c["b"] = [_member_port(e) for e in _c["a"]], [_member_port(e) for e in _c["b"]]

CIRCUITS = [
    {"cid": "CH1-ISP-A-01", "provider": "Provider A", "type": "Dedicated internet access", "speed": "1G",
     "handoff": "CH1-FW-01:ethernet1/3, CH1-FW-02:ethernet1/3", "media": "Cat6", "label": "DIA 1G · fiber"},
    {"cid": "CH1-ISP-B-01", "provider": "Provider B", "type": "Business cable", "speed": "500/50M",
     "handoff": "CH1-FW-01:ethernet1/4, CH1-FW-02:ethernet1/4", "media": "Cat6", "label": "Cable 500/50 · modem"},
    {"cid": "CH1-STATE-01", "provider": "State CJIS network", "type": "State-managed circuit", "speed": "100M",
     "handoff": "CH1-STATE-RTR:Gi0/0/0", "media": "Fiber", "label": "State network · state router"},
    {"cid": "CH1-COUNTY-01", "provider": "County IT", "type": "County fiber (dispatch)", "speed": "1G",
     "handoff": "CH1-FW-01:ethernet1/6, CH1-FW-02:ethernet1/6", "media": "SMF", "label": "County 911 dispatch link"},
]

SSIDS = [
    ("HALVERN-STAFF", "WPA3-Enterprise · 802.1X", 11, "zone-staff", "City staff laptops and phones; EAP-TLS with device certificates"),
    ("HALVERN-PUBLIC", "Open · splash page · client isolation", 70, "zone-public", "Residents and visitors; internet only, filtered, 10 Mb/s per client"),
    ("PD-SECURE", "WPA3-Enterprise · 802.1X (EAP-TLS)", 62, "zone-cjis", "Police laptops only; broadcast in the police wing only"),
]
# The library: patrons on their own SSID and line; staff join the same staff SSID as City Hall.
BRANCH_SSIDS = [
    ("HALVERN-STAFF", "WPA3-Enterprise · 802.1X", 10, "zone-staff", "Library staff; same SSID as City Hall"),
    ("HALVERN-LIBRARY", "Open · splash page · client isolation", 70, "zone-public", "Patrons; filtered, local internet line"),
]

# The access VLAN of each end device's switch port. APs trunk: native 99, tagged per area.
AP_VLANS = (11, 62, 70)
ACCESS_VLAN = {"printer": 10, "camera": 80, "nvr": 80, "door-controller": 81, "hvac-controller": 82, "ups": 99,
               "console-server": 99, "storage": 45, "payment-terminal": 25, "signal-system": 90, "public-pc": 71}

# Flows: id, from, to, what, verdict, conditions, owner
FLOWS = [
    ("F01", "City staff", "Internet and SaaS", "Web, email, files, meetings · HTTPS", "Allow", "Web filter", "IT"),
    ("F02", "City staff", "City servers", "Files (SMB) · finance and permits apps (HTTPS)", "Allow", "Named ports only", "IT"),
    ("F03", "Public Wi-Fi", "Internet", "Web", "Allow", "Content filter · 10 Mb/s per client", "IT"),
    ("F04", "Public Wi-Fi", "Any city zone", "Anything", "Deny", "Logged", "IT"),
    ("F05", "Payment counters", "Payment processor", "Card authorization · HTTPS", "Conditional", "One destination: the processor", "Finance"),
    ("F06", "Payment counters", "Any other zone", "Anything", "Deny", "Logged", "Finance"),
    ("F07", "Voice", "Hosted phone service", "SIP, RTP", "Allow", "Provider's published ranges", "IT"),
    ("F08", "Police workstations", "Police servers", "Records, evidence index, police directory", "Allow", "Inside zone-cjis", "Police"),
    ("F09", "Police servers", "State CJIS network", "State and national queries · via the state router", "Conditional", "State router only · encrypted · per the state agreement", "Police"),
    ("F10", "Patrol laptops (VPN)", "Police servers", "Records and queries from the car", "Conditional", "Patrol VPN pool · MFA · encrypted", "Police"),
    ("F11", "County dispatch (CAD)", "Police servers", "CAD-to-records interface", "Conditional", "One county host to one records host, one port", "Police"),
    ("F12", "City staff, public, building", "Police (CJIS)", "Anything", "Deny", "Logged", "Police"),
    ("F13", "Police workstations", "Internet", "Web, email", "Conditional", "Web filter · police directory sign-in", "Police"),
    ("F14", "Cameras", "NVR", "Video", "Allow", "Inside zone-building", "Facilities"),
    ("F15", "Building systems", "Internet", "Anything", "Deny", "No cloud services", "Facilities"),
    ("F16", "Signal central system", "Signal cabinets", "Signal timing and status (city fiber)", "Allow", "Inside zone-field", "Public Works"),
    ("F17", "Signal vendor (remote)", "Signal central system", "Support session", "Conditional", "Booked window · MFA · logged", "Public Works"),
    ("F18", "Traffic signals and field", "Any other zone", "Anything", "Deny", "Logged", "Public Works"),
    ("F19", "Library staff (LB1)", "City servers", "Files, finance, directory (city fiber)", "Allow", "Through the City Hall firewall", "IT"),
    ("F20", "Any city zone", "Water plant (boundary)", "Anything", "Deny", "No route; the plant's network is the utility's", "IT"),
    ("F21", "IT (VPN)", "Network management", "SSH, HTTPS to device management", "Conditional", "VPN + MFA · logged", "IT"),
    ("F22", "Every zone", "Firewall services", "DHCP, DNS, NTP", "Allow", "The firewall's own address on each VLAN", "IT"),
    ("F23", "Network management", "City SIEM service", "Syslog over TLS · monitoring", "Conditional", "One destination: the SIEM collectors", "IT"),
    ("F24", "APs (management, VLAN 99)", "Cloud Wi-Fi service", "AP management and config · HTTPS", "Conditional", "Provider's published ranges · APs only", "IT"),
]

# Remote access pools on the firewall pair (the patrol pool is police-only and lands in zone-cjis rules F10).
VPN_POOLS = [
    ("STAFF-VPN", "10.30.200.0/24", "City staff and IT, MFA (F21 for IT)"),
    ("PATROL-VPN", "10.31.200.0/24", "Patrol laptops over cellular, MFA (F10)"),
]

# The city's other buildings and its boundaries, for the buildings-and-links sheet:
# code, name, prefix, internet, link to the civic center.
CITY_SITES = [
    ("CH1", "Halvern Civic Center", "10.30.0.0/15", "ISP-A DIA 1G fiber · ISP-B cable 500/50", "— (the hub)"),
    ("LB1", "Halvern Main Library", "10.40.0.0/16", "Its own filtered line for patrons and public PCs",
     "City fiber; staff only, through the CH1 firewall pair (F19)"),
    ("PW1", "Public Works Yard", "10.42.0.0/16", "Through CH1", "City fiber; the signal cabinet ring starts here"),
    ("FS1", "Fire Station 1", "10.44.0.0/16", "Through CH1", "City fiber"),
    ("FS2", "Fire Station 2", "10.45.0.0/16", "Through CH1", "City fiber"),
    ("FS3", "Fire Station 3", "10.46.0.0/16", "Through CH1", "City fiber"),
    ("COUNTY", "County 911 dispatch", "the county's", "—",
     "County fiber 1G to the CH1 firewall pair; one CAD host to one records host (F11)"),
    ("STATE", "State CJIS network", "the state's", "—", "State circuit 100M to the state's router in R03 (F09)"),
    ("WATER", "Water treatment plant", "the utility's", "The utility's own", "None. A boundary, never a path (F20)"),
]

# Where a role's usual access VLAN differs by zone: police printers and evidence storage sit on police VLANs,
# the library's patron printer on its public PC VLAN.
ZONE_ACCESS_VLAN = {("printer", "zone-cjis"): 60, ("storage", "zone-cjis"): 61, ("printer", "zone-public"): 71}


def access_vlan(role: str, zone: str = ""):
    """The access VLAN of a device's switch port, by its role and zone tag."""
    return ZONE_ACCESS_VLAN.get((role, zone), ACCESS_VLAN.get(role))
