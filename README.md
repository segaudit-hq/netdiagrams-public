# NetDiagrams

**Network diagrams from your NetBox data, drawn to one consistent standard in draw.io.**

You already keep your devices, cables, VLANs and sites in NetBox. NetDiagrams turns that data into a full set of drawings that look like an engineer drew them by hand: overview, logical, physical, hardware, wireless, flows, failover and multi-site sheets, each with registers and title blocks. Run it again whenever NetBox changes, and the drawings follow.

- **Works with free, self-hosted NetBox.** It needs only a read-only API token.
- **Read-only.** It sends GET requests to NetBox, never changes it unless you opt in with `netbox-setup --apply`, and never connects to your network devices.
- **No dependencies.** Pure Python 3.9+, standard library only.
- **Opens anywhere draw.io does:** the desktop app, diagrams.net, Confluence, or exported HTML.

## Quick start

```bash
pip install git+https://github.com/segaudit-hq/netdiagrams-public
netdiagrams
```

The first run asks for your NetBox URL and an API token and remembers them. It then writes one drawing per NetBox site, `<site>.drawio`, plus a `<site>.drift.md` report of anything the template and NetBox disagree on. Open the drawing in draw.io.

No NetBox handy? See what a finished drawing looks like with a fictional site:

```bash
netdiagrams sample -o plant-a.drawio
```

The sample is only a demo. NetDiagrams never uses it unless you ask for it.

## What you get

- **A drawing standard, not a random layout.** NetDiagrams fills a bundled template, so every site comes out with the same sheets, shapes and colors. Your site's names replace the template's, and NetBox devices take the template slot of the same role.
- **Everything typed comes from NetBox.** Device fields, management IPs, serials, modules and optics, circuits, VLAN tables per zone, asset and link registers, and title blocks. Every shape links back to its NetBox object.
- **Security zones you can see.** Zones come from NetBox tags or custom fields, with a flow register of what is allowed between them.
- **Any size fits.** Repeated cells and closets are drawn once as a TYPICAL with a schedule row per copy, so a 3,000-device site still prints on the same set of sheets.
- **Data quality, day to day.** A quality sheet scores the site and lists what NetBox is missing. `netdiagrams gaps` writes the NetBox import files that fill those gaps.
- **Audit evidence.** An optional sheet shows owners, compliance scope, backups, patching, support contracts and monitoring for every asset.
- **Safe to share.** `netdiagrams share` makes a copy without IPs, serials, circuit IDs or NetBox links, ready to send to a vendor.

## Industry profiles

Every kind of site groups its zones differently, so each industry has its own template, stencils and example site:

| Profile | For |
|---|---|
| `manufacturing` (default) | Plants, with Purdue levels, an industrial DMZ and production cells |
| `warehouse` | Distribution centers, cross-docks and 3PL sites |
| `education` | School districts and campuses |
| `retail` | Stores, with the payment zone kept apart |
| `office` | Offices and branches |

```bash
netdiagrams --profile retail
netdiagrams sample --profile retail
```

## Common commands

| Command | What it does |
|---|---|
| `netdiagrams` | Build drawings for every NetBox site (same as `build`) |
| `netdiagrams doctor` | Check how your NetBox maps onto the template before drawing anything |
| `netdiagrams netbox-setup` | Write NetBox import files for the zones, roles and custom fields the template uses (`--apply` creates them; nothing existing is changed) |
| `netdiagrams gaps` | Write NetBox import files that close the data gaps the drawing lists |
| `netdiagrams share` | Copy a drawing with sensitive details removed |
| `netdiagrams draft` | Lay out a first draft automatically for a site with no drawing yet |
| `netdiagrams blank` / `stencils` | Start by hand without NetBox, using the draw.io shape library |
| `netdiagrams export` / `build --input` | Save NetBox data to JSON and build from it offline |

If your NetBox uses its own role names or custom field names, map them in a small `netdiagrams.json` file. `netdiagrams doctor --save-settings netdiagrams.json` proposes one for you.

The full guide to every option, setting and sheet is in [docs/reference.md](docs/reference.md).

## Learn the method

The drawings follow a method for documenting segmented networks: what to draw on each sheet, how to name zones, and how to keep drawings current. It is written up as a series of industry guides at [netdiagrams.com](https://netdiagrams.com), with free chapters and worksheets.

Once your zones are drawn, [SegAudit](https://segaudit.com) checks that your firewall configuration actually enforces them.

## Contributing

Bug reports and pull requests are welcome. Run the tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). NetDiagrams is a product of SegAudit LLC.
