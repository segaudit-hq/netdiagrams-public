# NetDiagrams reference

Network diagrams from NetBox, drawn to one consistent standard in draw.io.

NetDiagrams fills a drawing template with your NetBox data. The bundled template is an 11-page network standard: a management overview, logical, physical, hardware and optics, platform catalog, wireless, traffic flows, failover, multi-site WAN, a flow register and a NetBox mapping page. Every device and cable shape in it already carries NetBox field names.

When you run `netdiagrams`:

- **The layout stays exactly as drawn.** Every page of the template comes out with the same shapes in the same places.
- **Your site's names replace the template's.** NetDiagrams works out your site prefix (S07- for S07-IT-CORE-1) and renames the template to match. A NetBox device the template doesn't name takes the template slot of the same role, preferring one in the same zone.
- **Everything typed comes from NetBox.** Device fields, management IP, serial and circuit labels, the asset and link registers, the VLAN tables per zone (with subnet and gateway), the title blocks (site code, site name, today's date) and interface details are all rewritten from NetBox. Drawing-only details (`x_*` fields such as patch ports) are left alone.
- **What is inside each device comes from NetBox too.** Modules in their bays (`dcim.module`) and inventory items (power supplies, fans, transceivers, SD cards) fill the hardware sheet: the cable & optics register names the transceiver in each end's port, the modules & power register lists each switch's chassis, PSUs, modules and empty bays, the line under each port map restates power and fans, and a port cell shows the optic NetBox binds to it. The quality sheet counts modules and items without a serial and fiber ends with no transceiver; `netdiagrams gaps` writes the import files that close them.
- **Every item links to NetBox.** Click a device, cable, VLAN, subnet, circuit, table row, label or the site code to open it in your NetBox.
- **What the site doesn't have is removed; what the template lacks is added.** Template devices with no NetBox match are taken off (with their labels and links). Drawn links missing from NetBox turn dashed. NetBox cables the template doesn't draw are added on their own layer, and devices with no slot wait in a tray below the physical page.
- **Any size fits the same set of pages.** A cell or IDF stack that repeats is drawn once as the TYPICAL, as on electrical drawings, and a schedule under the drawing gives every copy its own row: switches, management IPs, cabinet, uplinks to the core and how many PLCs, HMIs, I/O and APs hang off it. Registers too long for their page continue on a register sheet right after it, laid out in columns. Plant A, which fits the template, comes out unchanged.
- **Click to reveal, print when you need paper.** Each page has a bar of buttons at its top right that switch its layers on and off (mgmt IPs, serials, registers, schedules), plus **Print view** (hides the bar and anything on-screen-only), **Share view** (also hides the layers marked "hide before sharing") and **Everything**. Every copy of a typical is drawn on its own hidden layer over the typical: click its row in the schedule and that cell or IDF appears in place, filled from NetBox. The buttons work in draw.io's viewer, Confluence and exported HTML, and from the link pop-up in the editor; View ▸ Layers does the same by hand.
- **Bigger sites stay readable.** Extra PLCs, HMIs, I/O and APs with no shape of their own join a drawn shape of the same role on the same switch, which then reads as "PLC ×20" and opens the whole group in NetBox; the registers still list every device. When a site outgrows the template, a "Site at a glance" page follows the overview: one card per zone with its device counts, and the cables between zones. A site shaped like the template gets no extra page.
- **Buildings and floors come from NetBox's locations.** A device card and a closet box on the physical page show the device's location path ("Main building › floor 1 › MDF-101") when NetBox nests its locations, and a site with more than one building or floor gets a "Riser" sheet after the physical pages: each building as a box, its floors stacked top to bottom, the closets and rooms on each floor with their device counts, and the cables between closets and between buildings, all from NetBox. Floors straight under the site ("Floor 2 › COMMS-2", "Floor 3 › IDF-3") are one building's floors, named after the site. A site whose locations are flat gets no riser sheet.
- **Wireless in every shape.** The wireless page follows NetBox's wireless LANs, wireless links and access points whatever runs them: controller pairs, a cloud dashboard, a firewall, or embedded control (the site's `wireless_management` field, or each AP's `wireless_controller`). A site with no controller loses the template's controller cards, CAPWAP captions and mode words, and a management card stands in their place. The SSID table reads security, VLAN, zone, switching, bands, where each SSID is broadcast (from the radios' Wireless LANs) and guest controls; the AP register adds mode, PoE and controller; point-to-point links, mesh links and workgroup-bridge associations are drawn and registered, with an SSID or without; an "APs by area" card sums the coverage per room. What NetBox does not record is a `?` with a tooltip, never a template value, and the quality sheet lists it (SSIDs without a VLAN, APs with no manager, open or shared-key SSIDs where they should not be, guest SSIDs without isolation or a portal). Pre-shared keys never leave NetBox: exports drop every `*psk*`, secret or password key, and `share` reports one typed into a caption.
- **Audit evidence for every asset.** Sheet 3f lists who owns each asset, what compliance scope it is in, its data classification and room access, when its configuration was last backed up, when it was last patched and verified, its support contract, and whether it is monitored and sends its logs off the box, with tiles for the share of assets that pass each check. Owners are NetBox contacts; the rest are optional custom fields `netbox-setup` adds as dropdowns, dates and bounded numbers, and a value set on a room, rack, subnet or the site covers every device in it. Assets in a compliance scope wear a purple stripe on their card. See [Audit evidence](#audit-evidence).
- **Differences are reported** in a drift report next to the drawing.

It only reads. NetDiagrams sends GET requests to NetBox and never changes it, and it never connects to your network devices.

## Install

```bash
pip install .
```

You need Python 3.9 or newer. There are no other dependencies.

## Run it

```bash
netdiagrams
```

The first time, NetDiagrams asks for your NetBox URL and an API token (read-only is enough) and remembers them in `~/.config/netdiagrams/config.json`. It then writes one drawing per NetBox site that has devices, `<site>.drawio`, plus `<site>.drift.md`. Open the drawing in draw.io (desktop or diagrams.net).

That is the whole workflow. Run `netdiagrams` again whenever NetBox changes.

To pick one site or a file name: `netdiagrams --site s07 -o s07.drawio`. In scripts and CI, set `NETBOX_URL` and `NETBOX_TOKEN` instead of logging in. `netdiagrams login` changes the saved login.

Or save the NetBox data once and build from the file (offline, or to share without NetBox access):

```bash
netdiagrams export --site s07 -o s07-netbox.json
netdiagrams build --input s07-netbox.json
```

### Check first: `netdiagrams doctor`

```bash
netdiagrams doctor --site s07
```

`doctor` draws nothing. For each site it prints the site prefix it would use,
how your device roles fill the template's slots (and which would land in the
tray), where it reads zones from, the data that needs care (spares, patch
panels, repeated cable labels, unnamed devices) and the next three things to
fix, each with its worksheet. Roles the template doesn't know get a proposed
mapping; `--save-settings netdiagrams.json` saves it for the next build.

### Your NetBox's own names: `netdiagrams.json`

NetDiagrams works without settings when NetBox uses the template's role slugs
(`core-switch`, `access-point`, `plc`...) and field names. When yours differ,
say how they map in a small JSON file, `netdiagrams.json`, next to your
drawings (or pass `--settings FILE`):

```json
{
  "roles": {"core-switch": ["switch-core", "l3-core"], "access-point": ["wap"]},
  "zone_field": "security_zone",
  "level_field": "purdue_level",
  "sl_field": "sl_target",
  "sw_field": "os_version",
  "gateway_field": "gateway",
  "end_of_support_field": "eos_date",
  "criticality_field": "asset_criticality",
  "audit": {"fields": {"last_config_backup": "backup_date"}, "days": {"backup": 7, "patch": 30}},
  "status": {"dashed": ["planned"], "register_only": ["inventory", "decommissioning"]},
  "naming": {"prefix": "S07-", "pattern": "^S\\d{2}-[A-Z0-9-]+$"},
  "pages": "-multisite",
  "logo": "company-logo.png"
}
```

Every key is optional. `roles` maps a template role to your NetBox role slugs
or names. Each `*_field` names the custom field that holds that fact (a list
works too; the first one set wins). Mapped devices keep their own role as
`netbox_role` in the shape data. The generic custom field `zone` is only read
when you name it in `zone_field`, because it often means a fire or HVAC zone.
`logo` is a PNG, JPEG or SVG file (or an image URL) for the logo box in every
title block; without it the box is left blank. `audit` tunes the audit evidence
sheet: `fields` names your own custom field for any of its facts, and `days` sets
how old a config backup (`backup`, 30 by default), patch (`patch`, 90) or
verification (`verify`, 455) may get, and how far ahead a contract end is flagged
(`contract_warn`, 90).

To keep the settings in NetBox instead, put the same JSON in a JSON custom
field named `netdiagrams` on a region, site group or site (`netbox-setup`
creates it). They apply in this order, later wins: built-in defaults, the
file, the site's regions (outermost first), its site group, the site, then the
command line. The drift report lists which settings were used.

### Printing

Each sheet is set to the smallest ISO landscape paper that holds it at full
size: A2 for the overview, A1 for most sheets, A0 for the physical and
hardware sheets. That is the size plant drawings are usually printed at, and
the smallest text is 9 units (about 6.5 pt) there. An A3 or A4 print is a
reduced copy for reading at a desk; use Print view first to drop the on-screen
buttons.

Colors mean one thing each: slate is a firewall or an enforcement point, red
is only a denied path, a fault or the safety zone, amber is an offline or
missing item, dashed is planned, indigo is a typical and its copies.

Each sheet ends with a small grey line naming the chapter of *Draw Secure
Manufacturing Network Diagrams* that explains how to draw it, and the drift
report ends with a pointer to the chapter on keeping drawings current.
`--no-book-note` leaves the sheet lines out.

### Evidence: what every sheet says about itself

Every title block carries a real revision (the first six characters of the
SHA-256 of the NetBox data and settings, or `--rev`) and a grey provenance line
under it: revision, build date, tool version, the date of the NetBox data, the
NetBox host and version, the settings file and the digest. Two builds from the
same data give the same revision; a changed NetBox gives a new one. The drift
report repeats it in full.

Nothing on a sheet pretends to be this site's data when it is not. The flows,
failover, multi-site, platform and NetBox sheets are watermarked EXAMPLE or
REFERENCE until a build can fill them; the template's guide notes move to a
hidden "Guides" layer (`--no-guide` removes them); group labels, subtitles and
the management overview are written from NetBox counts, not left from Plant A.
The asset register adds STATUS, OOB IP and, when NetBox has end-of-support
dates, EOS (red once past); the link register adds CABLE ID, STATUS and the
VLANs each trunk carries; rows grow with their text instead of clipping. The
label on each drawn link (`Po1 · 2×10G · 181,189 · MMF OM4`) is restated from
the cable and its interfaces, and a VLAN list NetBox does not have comes off the
line rather than staying as a claim nobody verified. Every serial, a stack
member's included, is a tag on layer 3b, so hiding that layer hides them all. The
"Plan to improve" cards list duplicate serials, IPs and asset tags, and trunks
with no VLANs, with the NetBox field and worksheet that close each gap.

### Data quality, day to day

Sheet 1c, **Data quality**, is the view an operations team works from: one score for
the site, every check with how many of how many objects are missing something, the
same per zone, the ten devices with the most gaps (linked to NetBox), and the trend
since the last build. The score weights the checks: needed to draw ×3 (names, zones,
cables, VLANs), needed as evidence ×2 (serials, IPs, rooms, duplicates, cable labels,
trunk VLANs, end of support), needed for an audit ×2 (owner, backup, patch, verification,
support contract, monitoring, logging, room access; each counts once the site records
its field, and until then it is listed but not scored), good to have ×1. Each build saves
`<site>.quality.json` next to the drawing and reads the previous one for the trend
column; the build summary prints the score and the three devices to fix first.
`--no-quality` leaves the sheet out.

```bash
netdiagrams doctor --fail-under 80      # exit 1 when a site scores under 80: for a weekly check
```

### What changed since the last build

Each build leaves `<site>.state.json` next to the drawing: the fields the drawing
shows for every device and cable. The next build compares against it: devices new in
NetBox get a green **NEW** pill on their shape and devices whose role, type, serial,
IP, room, rack, status, platform or zone changed get an amber **CHANGED** pill (hover
it for the old and new values), on a layer of their own that the controls bar toggles
and `share` leaves out. The drift report gets a "Changes since Rev …" section with
removed devices and every changed field, and the build summary says how much moved.

### Sharing a drawing

```bash
netdiagrams share s01.drawio                       # s01-vendor.drawio
netdiagrams share s01.drawio --audience auditor    # s01-auditor.drawio
netdiagrams share s01.drawio --audience management # s01-management.drawio
```

A built file carries more than it shows: every shape holds its NetBox record
(serial, management IP, asset tag, custom fields, a link back to NetBox), and
hiding a layer does not remove it. A pre-shared key is never in it: an export
drops `auth_psk` and any key named like a secret before it is written, and a
PSK someone typed into a caption is redacted and reported like an IP address.
`share` writes a copy for one audience:

- **vendor** (default): no management IPs, serial numbers, asset tags, circuit
  IDs, NetBox links or shape data; the registers stay with those columns blank,
  and the guide notes, plan cards, example sheets and on-screen controls go.
- **auditor**: every register, tag and NetBox link stays, so a finding can be
  traced back; only the guide notes and the template's example sheets go.
- **management**: the overview and the glance sheet, with the vendor rules.

The audit evidence sheet (3f) names owners and says what is unpatched, so only
the auditor's copy keeps it; the compliance scope and criticality stripes leave
vendor and management copies with their layers.

Before writing, the copy is checked against every IP, serial, asset tag,
circuit ID and NetBox host the original carried. If one survives a vendor or
management copy, nothing is written and the leaks are listed (`--allow-leaks`
writes it anyway). Each sheet's provenance line says the copy is shared and for
whom, and `--keep-examples` keeps the example sheets.

### Your own template

Pass `--template my-site.drawio` to fill your own drawing. Give its shapes NetBox field names (Edit Data, Ctrl+M) as the bundled template does; its NetBox page lists the fields. Tables are recognized by their header row (HOSTNAME for an asset register, LINK and A-SIDE for a link register, VLAN, NAME and SUBNET under a "ZONE ..." title for a VLAN table).

### What NetBox fills

| Drawing element | Matched on | Filled from NetBox |
| --- | --- | --- |
| Device card | name, else a free slot of the same role | role, manufacturer, device type, platform, serial, asset tag, status, site, location, rack, position, face, primary IPv4, virtual chassis, description, tags, custom fields, link |
| Wired link | cable label (several labels for a port-channel) | type, status, color, length, A and B terminations, link; dashed when missing |
| Port tag | device and interface name | interface fields |
| Mgmt IP, serial, circuit labels | the card or line they sit next to | primary IPv4, serial, circuit ID, link |
| Asset register | devices drawn on the page, for the roles the register lists | name, role, status, criticality, model, serial, mgmt IP, room, rack, U, software, end of support, links |
| Link register | NetBox cables between network devices | port-channel or link name, members on each side, speed, media, trunked VLANs, link |
| Cable & optics register (sheet 3b) | every NetBox cable, or only the fiber ones when the template's own rows are all fiber (or the table carries `netdiagrams_rows="fiber"`; `"all"` forces the full list) | cable, link, both ends, the transceiver inventory item in each port, media, speed, length, patch panel ports from the traced path (a cable with no path keeps the template's or the previous build's PATCH text), links |
| Modules & power register (sheet 3b) | network devices, a stack as one row | chassis model, power supplies, modules in their bays (empty bays amber), fans and other items, links |
| Port cell, port-map footer (sheet 3b) | device and interface name | the transceiver in the port (`x_optic`, its serial), power supplies and fans |
| VLAN table | VLANs tagged with the zone (`zone-*` tag or VLAN role) | VLAN, name, subnet, gateway and VRF, links |
| Title blocks | | site code and link, site name, date |

### When NetBox is still incomplete

Most sites don't have every serial, address, rack and cable label in NetBox on
day one, and that's fine: NetDiagrams draws what is there and says what isn't.

- A field NetBox doesn't have yet shows as an amber **?** on the shape
  (`IP ?`, `SN ?`), never as the template's example value.
- A zone table with no VLANs in NetBox says *Not in NetBox yet*, and a zone or
  group box with nothing in it says *Nothing in NetBox here yet*.
- Each data page gets a **Plan to improve this page** card beside the title
  block: what is missing for that page, how many, how to collect it, where it
  goes in NetBox and which free data collection worksheet (netdiagrams.com/worksheets)
  to use (WS-01 to WS-10, with WS-11 as the gaps register). When nothing is
  missing, the card says so in one line, with the date it was checked.
- Template examples the site doesn't have are listed on the card by name, so
  you can replace or delete them.

`python scripts/make_site.py starter -o starter.json` makes a day-one sample
site with gaps in it, to see all of this. `--no-plan` leaves the cards out.

### Spares, patch panels and other real-world data

NetBox holds more than the running network. NetDiagrams draws only what is
true and lists the rest in the drift report:

- **Device status.** `active` and `staged` devices are drawn as usual.
  `planned` devices are drawn dashed with a *Planned* pill, `offline` and
  `failed` ones with an amber outline and pill. Spares (`inventory`) and
  devices being taken out (`decommissioning`) are not drawn and never take a
  slot; they are listed in the asset register with their status.
- **Patch panels.** A cable that ends on a patch panel is drawn as the link it
  makes, switch port to far port, from the cable path NetBox traces
  (`connected_endpoints`). The panel ports go in the link's `x_patch_a` and
  `x_patch_b`. Patch panels (role `patch-panel`, or a device cabled only on
  front and rear ports) are not drawn as devices.
- **Gateways.** HSRP, VRRP and other FHRP addresses are read with the site's
  prefixes, so the VLAN tables show the virtual gateway (`HSRP .254`) rather
  than one member's address.
- **VLANs outside the site.** VLANs in a group scoped to the site, its region
  or location, and global VLANs, are read with their prefixes. A group VLAN
  with the same number as one assigned to the site itself is left out.
- **Every subnet.** A VLAN with secondary or IPv6 prefixes lists them all,
  IPv4 first; IPv6 gateways read `::1`.
- **Cable labels used twice.** Cabinet-local labels (`1`, `2`) no longer hide
  each other: each cable is kept, the drawn line is matched by its ends, and
  the plan card counts the repeats.
- **Breakouts.** A breakout or MPO trunk lists every leg in the link register.
- **Unnamed devices** are named `‹role›-‹id›` and listed on the plan card.
- **Out-of-band addresses.** With no primary IPv4, the IP tag and asset
  register show the device's OOB IP (NetBox 4.1+).
- **Wireless LANs** fill the SSID table on the wireless page: security and
  cipher, controller, VLAN and subnet, zone, switching, bands, the rooms whose
  APs broadcast it (interface ▸ Wireless LANs) and guest controls. Switching,
  bands, client isolation and portal are optional custom fields
  (`netbox-setup` adds them); a cell NetBox cannot fill shows `?`.
- **No controller, or a cloud one.** Set the site's (or site group's, or
  region's) `wireless_management` field to `cloud`, `firewall`,
  `controllerless` or `controller`, and `wireless_manager` to the dashboard or
  device name; or point each AP's `wireless_controller` field at its
  controller device. The sheet is named after what it finds ("Wireless —
  Meraki Dashboard (cloud)") and the CAPWAP flows become the management flow.
- **Point-to-point, mesh and bridges.** A NetBox wireless link between two
  radios matches the drawn line by its ends, SSID or not; links the template
  does not draw are added on their own layer; a workgroup bridge's
  association is a wireless link from its radio to the AP's.
- **Modules and inventory items.** `netdiagrams export` reads each device's modules, module bays and
  inventory items. An item's role (`transceiver`, `psu`, `fan`; `netbox-setup` adds the three) says what it
  is; without a role the part number decides. A transceiver whose component is an interface shows in that
  port cell and in the cable & optics register; a fiber end with none shows `?`.
- **Data date.** An export records when it was made. A drawing built from an
  older export shows both dates in the title block (`NetBox data 2026-04-01`).

To try these on the sample: `python scripts/make_site.py edges -o edges.json`,
then `netdiagrams build --input edges.json`.

### Pages a site doesn't need

Not every site has every page's subject. A site with no access points,
wireless controllers or radios in NetBox gets no wireless pages, and the drift
report says so. You can leave pages out yourself, or keep one in. A page is
named by its sheet number
(`3d`), a page id or a group: `overview`, `glance`, `logical`, `physical`,
`riser`, `audit` (3f), `hardware`, `platforms`, `wireless`, `flows`, `failover`, `multisite`,
`register`, `netbox`, and the groups `security` (flows and flow register),
`reference` (platform catalog and NetBox mapping) and `registers`.

- For every site: `netdiagrams build --leave-out failover,reference` and
  `--keep-in wireless`.
- For one site: a text custom field `netdiagrams_pages` on the NetBox site,
  where `-name` leaves a page out and `+name` keeps it, e.g. `-multisite` or
  `+wireless`. It is applied after the command line, so the site's own list
  wins.

## OT structure in NetBox

NetBox has no built-in security zone or Purdue level, so OT teams record them in a few ways. NetDiagrams reads all of them, first match wins:

| What | Where NetDiagrams looks |
| --- | --- |
| Security zone | `security_zone` custom field (or the one your settings name), then a `zone-*` tag, then the nearest location (cell, area, building) with a zone field or tag, or a slug like `cell-04` |
| Purdue level | `purdue_level` custom field on the device, then on its location, then the zone's usual level |
| VLAN zone | zone field or tag, VLAN role, VLAN group `zone-*`, then the zone or VRF of its prefix |
| Gateway | a `gateway` custom field on the prefix, then an HSRP/VRRP address in it, then the device address inside the prefix, in the prefix's own VRF |
| End of sale, end of support | `end_of_sale` and `end_of_support` date fields (and an `eol_notice` link) on the **device type**, set once per model; a device's own date overrides its model's. The asset register's EOS column, the "past end of support" gap and the "network models with no end-of-support date" gap use the result, and `netdiagrams gaps` writes `15-device-models.csv`, one row per undated model |
| Asset criticality | `criticality` custom field on the device (or the one your settings name): critical, high, medium, low. Critical assets wear a red stripe down the left edge of their card (on the "Asset criticality (hide before sharing)" layer, which `share` strips for vendor and management copies along with the CRIT column), the asset register gets a CRIT column, and devices with none are a data quality gap, because auditors (IEC 62443 consequence, NIST CSF ID.AM-05, ISO 27001 classification, NERC CIP impact) ask for it |

Tagging a location is usually enough: every device in a cell inherits its zone. A device in a cell takes the template slot of its role in that cell's zone.

To add the fields, tags and roles the template uses, run:

```bash
netdiagrams netbox-setup
```

It writes numbered CSV files to `netbox-setup/` for NetBox's Import buttons: Purdue level and IEC 62443 security level choice sets and the `purdue_level` and `security_level_target` fields (for an industry profile with levels; a profile may word their labels), the `criticality` (with its choice set) and `netdiagrams` (settings) custom fields, the wireless fields (`wlan_security`, `wlan_switching`, `wlan_bands`, `wlan_client_isolation`, `wlan_portal` on wireless LANs; `ap_mode` and `wireless_controller` on devices; `wireless_management`, `wireless_manager` and `wireless_survey` on sites, site groups and regions) with their choice sets, the audit evidence fields with their choice sets (see [Audit evidence](#audit-evidence)), the lifecycle fields on device types (`end_of_sale`, `end_of_support`, `eol_notice`), an optional `gateway` text field on prefixes, one `zone-*` tag per zone in the template, one device role per role, inventory item roles (transceiver, power supply, fan) and the contact roles Asset owner and Custodian. When NetDiagrams can read your NetBox, it leaves out what is already there, and it follows your settings: a role you mapped, or a level kept in a field of your own, adds nothing.

```bash
netdiagrams netbox-setup --check   # present / missing / present but not on locations, for each
netdiagrams netbox-setup --apply   # create what is missing through the API
```

`--check` compares and changes nothing. `--apply` creates the missing objects with a token that can write, one API call each, and reports each outcome; it is the only thing in NetDiagrams that writes to NetBox. Everything it adds is NetBox's own extension points, so an upgrade keeps it: custom fields in groups "OT" and "NetDiagrams", none required; choice sets; tags; device roles. It never updates or deletes: a field you renamed, a tag you recoloured or a role you already had is left alone and reported as present, and a field present but missing an object type is listed for you to extend by hand. It follows the NetBox version it finds (choice sets from 3.6, `object_types` from 4.0).

### Audit evidence

Auditors ask the same questions of every asset (IEC 62443-2-1, NIST CSF 2.0 ID.AM and
DE.CM, ISO 27001:2022 A.5.9 to A.5.13 and A.8.15 to A.8.16, NERC CIP-002/007/010, PCI DSS 4.0).
NetDiagrams answers them on sheet 3f from NetBox:

| Column | Where it comes from | Set on |
| --- | --- | --- |
| Owner, custodian | NetBox contacts with the role Asset owner or Custodian, else the device's tenant | device, rack, room, site |
| Scope | `compliance_scope` (PCI CDE, PCI connected, NERC CIP, safety, GxP / GDP, HIPAA, SOX, CUI, FERPA; an industry profile offers its own list, in its own order); every source adds up | device, room, subnet |
| Data | `data_classification` (public, internal, confidential, restricted); the strictest source wins | device, room, subnet |
| Room access | `physical_access` (open area, locked cabinet, locked room, badge, badge and camera) | rack, room |
| Config backup, Patched | `last_config_backup`, `last_patched` (dates; access points follow their controller) | device |
| Verified | `last_verified` (date of the last walk-down) | device, room, site |
| Support, Installed | `support_contract`, `support_contract_end`, `install_date` | device |
| Monitoring | `monitoring` (with alerts, without alerts, passive IDS or sensor, none) and `monitored_by` | device, room, site |
| Logs | `log_forwarding` (SIEM, syslog server, local only, none), `log_destination`, `log_retention_days` | device, room, site |

A value on the device wins; otherwise the rack, then the room and the rooms around it,
then the site. So a walk-down of a room, or a site-wide syslog target, is one entry.
Ages count from the day the export is true for: amber past its limit, red when missing.
The sheet comes when NetBox records any of this; a site that records none loses no points.

Manual entry stays clean because NetBox enforces the field types: choices are dropdowns
that only an admin can extend, dates use a date picker and must be real dates, owners
are picked from NetBox's contacts, and log retention must be between 1 and 3,650 days.
None of the fields is required, so imports and older devices keep working. The quality
sheet lists any value off its list (an old choice, a date typed as 17/10/2026 into a
field of your own), and `netdiagrams gaps` writes `12-audit-evidence.csv` (device dates,
monitoring and logging), `13-locations.csv` (room access and walk-down dates) and
`14-new-owner-contacts.csv` (one owner assignment per room) for NetBox's Import; the free worksheet WS-12 Audit evidence collects the same facts on paper.

### Closing the data gaps

Every "Plan to improve this page" card names what NetBox is missing for that page, how to collect it and the worksheet to use. To close those gaps through NetBox's own Import:

```bash
netdiagrams gaps --site s01 -o s01-gaps     # or --input s01-netbox.json
```

It writes one CSV per NetBox list with gaps (devices, cables, trunk interfaces, prefixes, new prefixes for VLANs that have none, access points, wireless LANs, and new wireless links for radios and bridges with none), each row with the object's `id` and its current values. The wireless LAN file never carries the pre-shared key. Fill the blank cells from the worksheet, delete rows you cannot answer yet, and import: NetBox updates the objects by `id`, and a value left as it was changes nothing. Build again and the drawing follows.

## No drawing yet? Start from a draft

```bash
netdiagrams draft --site s01 -o s01-draft.drawio
```

`draft` lays out a site automatically: Purdue levels, zones from `zone-*` device tags, VLAN tables and cables. It's a starting point to rearrange by hand, not a finished drawing in the standard.

## Start without NetBox

```bash
netdiagrams blank -o new-site.drawio      # empty zones, one per Purdue level
netdiagrams stencils -o Network-Docs-Stencils.xml        # add --profile NAME for another industry's shapes and bands
```

In draw.io, use File ▸ Open Library from ▸ Device to load the stencil library. It has one shape per device role, Purdue bands, zone and VLAN tables, a legend and a title block.

## Try the sample

```bash
netdiagrams sample -o plant-a.drawio
```

This writes the template as drawn for "Plant A", a fictional plant with IT, an industrial DMZ, OT operations, production cells and a safety system. It is only there to show what a finished drawing looks like. NetDiagrams never uses it unless you ask for it.

## Industry profiles

The bundled standard is drawn for a plant: Purdue levels, an industrial DMZ,
cells. Other kinds of organization band their zones differently, so each
industry is a profile with its own template and example site. Manufacturing is
the default. Pick another for a site with the `profile` setting (in
`netdiagrams.json`, or in the NetBox `netdiagrams` field on a region, site
group or site), or for one run with `--profile`:

```bash
netdiagrams build --profile retail
netdiagrams sample --profile retail
```

`netdiagrams sample --profile NAME` writes that industry's fictional example.
`netbox-setup` follows the profile too: Purdue level and security level fields
are only offered for manufacturing and warehouse.

The book that goes with the manufacturing standard is *Draw Secure
Manufacturing Network Diagrams* (netdiagrams.com/books/manufacturing-network-diagrams/).

### Warehouse (`--profile warehouse`)

For distribution centers, cross-docks and 3PL sites. The template is the same
eleven-sheet standard, drawn for "W01 · Riverside DC", a fictional
distribution center: the cell/area zones hold the inbound conveyor, the
cross-belt sorter and its AMRs, and the dock doors and yard gate; site
operations holds the WES/WCS servers and the handheld Wi-Fi; carriers, client
APIs and the cloud WMS end in the integration DMZ; and the conveyor and sorter
safety PLC has its own zone. Material handling automation sits on the same
Purdue levels as a plant, so the zone tags (`zone-cell01`, `zone-ot-ops`,
`zone-safety` ...) and fields are the same ones.

```bash
netdiagrams sample --profile warehouse -o riverside-dc.drawio
netdiagrams build --profile warehouse --input src/netdiagrams/data/sample-warehouse-w02.json
```

The second command builds "W02 · Northgate Cross-Dock", a small site on day
one with some serials, addresses and cable labels still to collect, to show
the plan cards. The warehouse template and both samples are generated from
the S01 template (see Development), so a fix to S01 is carried over by
regenerating them.

The book that goes with this standard is *Draw Secure Warehouse Network
Diagrams* (netdiagrams.com/books/warehouse-network-diagrams/).

### Offices: `--profile office`

The office standard (O01) is eight sheets drawn for a small or mid-size office
and its branches, around one firewall pair. Zones band by who uses them:
outside, the edge, staff and services, shared spaces and guests, building and
management.

```bash
netdiagrams sample --profile office -o alder-finch.drawio   # the finished set, for "Alder & Finch HQ"
netdiagrams build --profile office                         # your own office, from NetBox
```

| Sheet | What it shows |
|---|---|
| 1 Overview | How the office is protected, in business terms, for the partners and the insurer |
| 2 Logical | The five bands, a zone per box with its VLAN table, the firewall's interfaces |
| 3 Physical | Providers, the firewall pair, the core and floor stacks with their port-channels, servers, UPSes, the console server, one card per kind of end device per floor (AP ×8, Camera ×10), link and asset registers |
| 3d Wireless | Access points per floor with their switch port and cable, and the SSID table |
| 4 Traffic flows | Who may talk to whom, lane by lane, ending in default deny (example until you write yours) |
| 5 Failover | What fails, what takes over, what users notice (example) |
| 6 Branches and cloud | Sites, cloud networks and remote access, with a site table (example) |
| 7 Flow register | The flows as a register, a zone matrix and the naming standards |

A branch of a handful of devices is better drafted than fitted to the HQ
sheets: `netdiagrams draft --profile office` lays it out in the same bands with
the office shapes. `netdiagrams stencils --profile office` saves those shapes
(printers, cameras, UPSes, video recorders, door controllers, meeting-room
systems, NAS boxes, console servers, desk phones) as NetBox device cards, and
`netdiagrams netbox-setup --profile office` writes the office zone tags
(`zone-staff`, `zone-voice`, `zone-guest`, `zone-building`...) and roles.

A day-one office with the gaps a first import has (missing serials, an
unlabeled uplink, cameras with no zone, a VLAN with no prefix):

```bash
python3 scripts/make_office_sample.py --site starter -o office-starter.json
netdiagrams build --input office-starter.json
```

The book that goes with this standard is *Draw Secure Small Office Network
Diagrams* (netdiagrams.com/books/small-office-network-diagrams/).

### Banks and credit unions: `--profile bank`

The bank standard (B01) is eight sheets drawn for a community bank or credit
union and its branches, around one firewall pair with the core processor's own
router behind it. Zones band by trust: outside and the outside parties, the
edge and the processor links, banking (teller line, platform and back office,
wire room, card issuing), services, customer-facing (ATMs and lobby guests),
security and management.

```bash
netdiagrams sample --profile bank -o ninebark.drawio   # the finished set, for "Ninebark Community Bank"
netdiagrams build --profile bank                       # your own bank, from NetBox
```

| Sheet | What it shows |
|---|---|
| 1 Overview | How the bank is protected, in business terms, for the board and the examiners |
| 2 Logical | The six bands, a zone per box with its VLAN table, the firewall's interfaces, the core processor's link |
| 3 Physical | Providers and the core processor's circuit, the firewall pair, the provider-owned router on port5, the core and floor stacks, servers, UPSes, the console server, one card per kind of end device per floor (ATM ×2, Camera ×9), link and asset registers |
| 3d Wireless | Access points per floor with their switch port and cable, and the SSID table (staff and guests only) |
| 4 Traffic flows | Who may talk to whom, lane by lane, ending in default deny (example until you write yours) |
| 5 Failover | What fails, what takes over, what people notice, including the single core circuit (example) |
| 6 Branches, processors and cloud | Branches, the core and card processors, the Federal Reserve, the cloud and the providers, with a site table (example) |
| 7 Flow register | The flows as a register, a zone matrix and the naming standards |

A branch is better drafted than fitted to the main office's sheets:
`netdiagrams draft --profile bank` lays it out in the same bands with the bank
shapes. `netdiagrams stencils --profile bank` saves those shapes (ATMs, teller
cash recyclers, wire workstations, card printers, alarm panels, the
provider-owned router, plus the office kit) as NetBox device cards, and
`netdiagrams netbox-setup --profile bank` writes the bank zone tags
(`zone-teller`, `zone-wire`, `zone-card`, `zone-atm`...), roles and the
compliance scopes with GLBA first.

A day-one bank with the gaps a first import has (missing serials, an
unlabeled uplink, cameras with no zone, a VLAN with no prefix):

```bash
python3 scripts/make_bank_sample.py --site starter -o bank-starter.json
netdiagrams build --input bank-starter.json
```

The book that goes with this standard is *Draw Secure Bank and Credit Union
Network Diagrams* (netdiagrams.com/books/bank-network-diagrams/).

### Schools (`education`)

```bash
netdiagrams sample --profile education
```

The education standard is drawn for Harbor Pines High School (HS1), a fictional
district high school. Zones group into trust tiers instead of Purdue levels:
outside and the district WAN; staff and front office; students and guests;
services and building systems; management. Its ten sheets cover an MDF with four
IDFs and the stadium press box, closet PoE budgets and optics, a wireless
gateway cluster for 108 APs and a 60 GHz stadium link, flows, failover, the
district WAN, the flow register and the NetBox mapping. Its NetBox export,
`src/netdiagrams/data/sample-harbor-pines-hs.json`, carries
`{"profile": "education"}` and the district's naming standard in the site's
`netdiagrams` field, so `netdiagrams build --input sample-harbor-pines-hs.json`
picks the school standard by itself. `netdiagrams stencils --profile education`
adds school device shapes (camera, door controller, BAS controller, PA, NVR,
classroom display, printer) and trust-tier bands to the shape library.

The book that goes with this standard is *Draw Secure School Network
Diagrams* (netdiagrams.com/books/school-network-diagrams/).

### Retail (`--profile retail`)

| Profile | Template | Example | Bands |
|---|---|---|---|
| `manufacturing` (default) | S01, 11 sheets | Plant A | Purdue levels L5 to L0 |
| `bank` | B01, 8 sheets | Ninebark Community Bank | outside, edge and processor links, banking, services, customer-facing, security and management |
| `retail` | R01, 10 sheets | Store 014 | outside, head office, store, cardholder data (CDE), guest and devices |

The retail standard draws one store: firewall and SD-WAN edge, 4G backup line,
cabinet switch, counter switch for the checkout, access points, registers, PIN
pads and the store's devices. Its sheets are the overview, logical, physical,
cabinet and PoE (3b), wireless floor plan (3d), the card's journey (4),
failover (5), the estate (6), the flow register (7) and the NetBox mapping (8).
Zones come from `zone-…` tags (`zone-cde`, `zone-store`, `zone-mgmt`,
`zone-guest`, `zone-iot`, `zone-edge`); cables are labeled by their A-side port
(`ST014-SW01-P05`) so every store's cables match the template's. Set the
profile once on the estate's NetBox region and every store builds to it:

```json
{"profile": "retail"}
```

`netdiagrams stencils --profile retail` saves the retail shape library: a card
per store role (store firewall, 4G router, store and counter switch, POS
register, PIN pad, store POS server, NVR, camera, signage, refrigeration
controller, sensor) and the five zone bands; `draft` draws with the same shapes.

`scripts/make_retail.py` is the single source of the R01 template, its shape
library and the sample estate (Store 014, plus Store 027 and Store 031 with
`--estate DIR`).

The book that goes with this standard is *Draw Secure Retail Network
Diagrams* (netdiagrams.com/books/retail-network-diagrams/).

### Car dealerships: `--profile dealership`

The dealership standard (D01) is eight sheets drawn for one franchised rooftop,
Kestrel Valley Motors, around one firewall pair. Zones follow where customer
financial information goes and band by department: outside (the hosted DMS,
lenders and credit bureaus); the edge; sales, F&I and the back office with the
card terminals; service, the shop, parts and the manufacturer's router; and
customer Wi-Fi, phones, the building and lot, and management.

```bash
netdiagrams sample --profile dealership -o kestrel-valley.drawio   # the finished set, for "Kestrel Valley Motors"
netdiagrams build --profile dealership                            # your own dealership, from NetBox
```

| Sheet | What it shows |
|---|---|
| 1 Overview | How the dealership is protected, in business terms, for the dealer principal and the Qualified Individual |
| 2 Logical | The five bands, a zone per box with its VLAN table, the firewall's interfaces and tunnels |
| 3 Physical | Providers, the firewall pair, the core, the main-building and service-building stacks, the deal-jacket NAS, the manufacturer's router on its own VLAN, UPSes, the console server, one card per kind of end device per building, link and asset registers |
| 3d Wireless | Access points per building with their switch port and cable, and the SSID table (staff, service lane, shop, guest) |
| 4 Traffic flows | Who may talk to whom, lane by lane, ending in default deny (example until you write yours) |
| 5 Failover | What fails, what takes over, what people notice, including the morning the DMS goes dark (example) |
| 6 Rooftops and cloud | The pre-owned store, the hosted DMS, SaaS, the MSP and vendor support, with a site table (example) |
| 7 Flow register | The flows as a register, a zone matrix and the naming standards |

`netdiagrams stencils --profile dealership` saves the dealership shapes (card
terminal, diagnostic PC, key cabinet, manufacturer router, printer, camera,
video recorder, NAS, UPS, console server), and `netdiagrams netbox-setup
--profile dealership` writes the zone tags (`zone-fi`, `zone-shop`, `zone-oem`,
`zone-guest`...) and roles. The sample puts the F&I, office and file subnets in
the `glba` compliance scope (the FTC Safeguards Rule) and the card terminals in
`pci-cde`. A day-one dealership with the gaps a first import has:

```bash
python3 scripts/make_dealer_sample.py --site starter -o dealership-starter.json
netdiagrams build --input dealership-starter.json
```

The book that goes with this standard is *Draw Secure Car Dealership Network
Diagrams* (netdiagrams.com/books/car-dealership-network-diagrams/).

### Cities, towns and counties: `--profile municipal`

The local government standard (M01) is eight sheets drawn for a civic center
where City Hall and the police share one building and one network, around one
firewall pair. Zones band by who they serve: outside (internet, state, county
and the water plant as a boundary), the edge, the public, City Hall, public
safety (police, CJIS) and facilities, field and management.

```bash
netdiagrams sample --profile municipal -o halvern.drawio   # the finished set, for "Halvern Civic Center"
netdiagrams build --profile municipal                      # your own city, from NetBox
```

| Sheet | What it shows |
|---|---|
| 1 Overview | How the city is protected, for the city manager, the council and the insurer |
| 2 Logical | The six bands, a zone per box with its VLAN table, the firewall's interfaces and VPN pools |
| 3 Physical | Providers and the state and county circuits, the firewall pair, the core pair, the police cage (R03) with the state-managed router, the wing stacks, servers, building systems, the signal system, UPSes, link and asset registers |
| 3d Wireless | Access points per area, the SSID table (PD-SECURE in the police wing only) |
| 4 Traffic flows | Who may talk to whom, lane by lane, ending in default deny (example) |
| 5 Failover | ISP, firewall, core, the storm and the generator, the console server, the state circuit (example) |
| 6 City buildings and links | The civic center hub, the library, public works and fire stations on city fiber, state and county edges, the water plant boundary (example) |
| 7 Flow register | The flows as a register, a zone matrix and the naming standards |

`netdiagrams stencils --profile municipal` saves the city shapes (payment
terminal, traffic signal system, HVAC controller, public PC and the office
ones) and `netdiagrams netbox-setup --profile municipal` writes the city zone
tags (`zone-cjis`, `zone-public`, `zone-pay`, `zone-field`, `zone-water`...)
and roles. The library (LB1) is a second export; a day-one civic center shows
the gaps a first import has:

```bash
python3 scripts/make_city_sample.py --site starter -o city-starter.json
netdiagrams build --input city-starter.json
```

The book that goes with this standard is *Draw Secure Local Government Network
Diagrams* (netdiagrams.com/books/local-government-network-diagrams/).

### Hotels: `--profile hotel`

The hotel standard (H01) is eight sheets drawn for a full-service hotel, the
fictional Alder Bay Hotel and Conference Center, around one firewall pair with
three owners around it: the owner, the management company that runs IT, and the
brand whose router and cloud PMS sit in the rack. Zones band by who they serve:
outside (internet, brand and vendors), the edge, payments and operations, guests
and rooms, building and safety.

```bash
netdiagrams sample --profile hotel -o alder-bay.drawio   # the finished set
netdiagrams build --profile hotel                        # your own hotel, from NetBox
```

Sheets: 1 Overview, 2 Logical, 3 Physical, 3d Wireless, 4 Traffic flows,
5 Failover, 6 Portfolio (brand, management company, sister property) and
7 Flow register. `netdiagrams stencils --profile hotel` saves the hotel shapes
and `netdiagrams netbox-setup --profile hotel` writes the zone tags
(`zone-payments`, `zone-guest`, `zone-roomtech`, `zone-building`...) and roles.
A day-one hotel with the gaps a first import has:

```bash
python3 scripts/make_hotel_sample.py --site starter -o hotel-starter.json
netdiagrams build --input hotel-starter.json
```

The book that goes with this standard is *Draw Secure Hotel Network Diagrams*
(netdiagrams.com/books/hotel-network-diagrams/).

### Corporate HQ and multi-site: `--profile corporate`

The corporate standard (C01) is drawn for a company past one firewall: a routed
campus core with VRFs, an internal segmentation firewall pair that gates every
VRF and every data center tier, an edge pair for everything outside, SD-WAN
hubs, a DR site, branches built to typicals, home workers and the cloud. Zones
band by trust: outside (internet, WAN, cloud); the edge (firewalls, DMZ,
extranet); users (corporate, voice, printers, legal); the data center
(applications, data, infrastructure, backup, legal systems); shared spaces and
building systems; management.

```bash
netdiagrams sample --profile corporate -o sable-ridge.drawio   # the finished set, for "Sable Ridge HQ campus"
netdiagrams build --profile corporate                          # your own campus, from NetBox
```

| Sheet | What it shows |
|---|---|
| 1 Overview | How the company network is protected, in business terms, for the board, the auditors and clients |
| 2 Logical | The six bands, a zone per box with its VLAN table (VLAN, name, VRF, subnet, gateway), the two firewall pairs' interfaces and the VRF table |
| 3 Physical | Providers, the data center and campus core, then every floor of every building: its access stack, rack UPS and one counted card per kind of end device (AP ×10, Camera ×6); link and asset registers |
| 3d Wireless | Access points per floor and building, the controller pair and the SSID table |
| 3e Riser | Buildings, floors and closets from NetBox's location tree, with the cables between them (drawn by the build) |
| 4 Traffic flows | F01 to F33, lane by lane, ending in default deny (example until you write yours) |
| 5 Failover | Eight scenarios: what fails, what takes over, what people notice (example) |
| 6 Multi-site WAN | Hubs, the regional office, branch typicals, home workers and the cloud, with a site table (example) |
| 7 Flow register | The flows with an owner each, the zone matrix and the naming and addressing standards |

The VLAN tables have their own VRF column: a table whose header has `VRF`
gets the VRF there, and the gateway column keeps only the gateway.

A branch is drafted, not fitted to the HQ sheets: `netdiagrams draft --profile
corporate` lays it out in the same six bands with the corporate shapes.
`netdiagrams stencils --profile corporate` saves those shapes (SD-WAN hubs,
distribution and DC leaf switches, storage and backup, UPSes, console servers,
printers, video recorders, cameras, badge and BMS controllers, meeting-room
systems) as NetBox device cards, and `netdiagrams netbox-setup --profile
corporate` writes the twenty zone tags (`zone-corp`, `zone-legal`,
`zone-dc-app`, `zone-dms`...) and the roles.

```bash
python3 scripts/make_corporate_sample.py --site c11 -o c11.json   # C11 Ashcombe, a BR-M branch
netdiagrams draft --profile corporate --input c11.json -o c11.drawio
```

A day-one campus with the gaps a first import has (half the prefixes with no
VRF, South's stacks with no rack positions, the Commons cameras with no zone,
an unlabeled campus fiber link, the legal hosts untagged):

```bash
python3 scripts/make_corporate_sample.py --site starter -o corporate-starter.json
netdiagrams build --input corporate-starter.json
```

The book that goes with this standard is *Draw Secure Corporate Network
Diagrams* (netdiagrams.com/books/corporate-network-diagrams/).

## Options

- `--no-tray` leaves NetBox-only devices off the drawing; they are still listed in the drift report.
- `--no-controls` leaves out the show/hide buttons.
- `--leave-out failover,3b` and `--keep-in wireless` choose the pages (see above).
- `--no-plan` leaves out the "Plan to improve this page" cards.
- `--glance` / `--no-glance` always add, or never add, the "Site at a glance" page.
- `--riser` / `--no-riser` always add, or never add, the "Riser" sheet of buildings, floors and closets.
- `--audit` / `--no-audit` always add, or never add, the "Audit evidence" sheet (3f); by default it comes when NetBox records any audit evidence for the site.
- `--keep-unmatched` keeps template devices that NetBox doesn't have instead of removing them.
- `--rename S01-=S07-` sets the prefix swap yourself when NetDiagrams can't work it out.
- `--settings FILE` (build, draft, doctor, netbox-setup) reads settings from FILE instead of `netdiagrams.json`.
- `--profile NAME` (build, draft, doctor, netbox-setup, sample, blank) draws to that industry's standard (see Industry profiles).
- `--no-book-note` (build) leaves out the "How to draw this page" line under each sheet.
- `--no-quality` (build) leaves out the "Data quality" sheet (1c); the score is still printed and saved.
- `--fail-under SCORE` (doctor) exits 1 when a site's data quality is under SCORE.
- `--no-guide` (build) removes the template's guide notes instead of parking them on a hidden "Guides" layer.
- `--rev R1` (build) sets the revision in the title blocks; the default is the first six characters of the SHA-256 of the NetBox data and settings, printed in full in the drift report.
- `--no-note` (draft, blank) leaves out the small "About this drawing" note.
- `--insecure` skips TLS certificate checks (for a lab NetBox with a self-signed certificate).

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 scripts/make_sample.py   # regenerate the sample export from the template
python3 scripts/make_school.py   # regenerate the education template, sample export and shape library
python3 scripts/make_warehouse.py   # regenerate the warehouse template and both warehouse samples from S01
python3 scripts/make_site.py large -o large.json   # a 3,000-device test site (also small, medium)
python3 scripts/make_office_template.py  # redraw the O01 office template
python3 scripts/make_office_sample.py    # and its sample export (--site o02 / starter for the fixtures)
python3 scripts/make_office_stencils.py  # and the office shape library
python3 scripts/make_bank_sample.py --site starter -o bank-starter.json
python3 scripts/make_bank_template.py  # redraw the B01 bank template
python3 scripts/make_bank_sample.py    # and its sample export (--site b02 / starter for the fixtures)
python3 scripts/make_bank_stencils.py  # and the bank shape library
python3 scripts/make_retail.py  # regenerate the R01 retail template and the Store 014 export
python3 scripts/make_dealer_template.py  # redraw the D01 dealership template
python3 scripts/make_dealer_sample.py    # and its sample export (--site d02 / starter for the fixtures)
python3 scripts/make_dealer_stencils.py  # and the dealership shape library
python3 scripts/make_city_template.py    # redraw the M01 municipal template
python3 scripts/make_city_sample.py      # and its sample export (--site lb1 / starter for the fixtures)
python3 scripts/make_city_stencils.py    # and the municipal shape library
python3 scripts/make_hotel_template.py  # redraw the H01 hotel template
python3 scripts/make_hotel_sample.py    # and its sample export (--site h02 / starter for the fixtures)
python3 scripts/make_hotel_stencils.py  # and the hotel shape library
python3 scripts/make_corporate_template.py  # redraw the C01 corporate template (its registers come from the sample)
python3 scripts/make_corporate_sample.py    # and its sample export (--site starter / c11 for the day one and the branch)
python3 scripts/make_corporate_stencils.py  # and the corporate shape library
```
