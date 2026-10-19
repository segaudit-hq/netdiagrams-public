"""Command line: netdiagrams build | draft | doctor | export | share | netbox-setup | sample | blank | stencils."""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
import sys
import time
from pathlib import Path

import xml.etree.ElementTree as ET

from . import __version__, doctor, drawio, gaps, intake, netbox_setup, ot, profiles, quality, settings as config, share, stencils, sync, worksheets
from .model import build_site
from .netbox import NetBoxClient, NetBoxError, load_export
from .pages import PageError

SAMPLE_FILE = profiles.MANUFACTURING.sample


CONFIG = Path(os.environ.get("NETDIAGRAMS_CONFIG", Path.home() / ".config" / "netdiagrams" / "config.json"))


def _saved() -> dict:
    try:
        return json.loads(CONFIG.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _save(url: str, token: str) -> None:
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # never readable by others, even briefly
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"url": url, "token": token}))
    CONFIG.chmod(0o600)  # a file saved by an older release keeps its old mode otherwise


def _client(args) -> NetBoxClient:
    """NetBox details come from flags, then the environment, then the saved login.

    If none is set and someone is at the keyboard, ask once and remember it.
    """
    saved = _saved()
    url = args.netbox_url or os.environ.get("NETBOX_URL") or saved.get("url")
    token = os.environ.get("NETBOX_TOKEN") or (saved.get("token") if url == saved.get("url") else None)
    if (not url or not token) and sys.stdin.isatty():
        url = url or input("NetBox URL: ").strip()
        token = token or getpass.getpass("NetBox API token (read-only is enough): ").strip()
        if url and token:
            _save(url, token)
            print(f"Saved to {CONFIG} for next time.")
    if not url or not token:
        raise NetBoxError("No NetBox to read from. Run netdiagrams in a terminal to log in once, set NETBOX_URL and "
                          "NETBOX_TOKEN, or pass --input with an export file.")
    return NetBoxClient(url, token, verify_tls=not args.insecure)


def cmd_login(args) -> None:
    url = args.netbox_url or input("NetBox URL: ").strip()
    token = getpass.getpass("NetBox API token (read-only is enough): ").strip()
    client = NetBoxClient(url, token, verify_tls=not args.insecure)
    sites = client.sites()
    _save(url, token)
    print(f"Logged in to {client.base[:-4]} ({len(sites)} sites). Saved to {CONFIG}.")


def _settings(args) -> tuple[dict, str]:
    """--settings FILE, else netdiagrams.json in the output folder or the current folder."""
    path = getattr(args, "settings", None)
    if not path:
        out = Path(args.output) if getattr(args, "output", None) else None
        folder = out if out is not None and out.is_dir() else (out.parent if out is not None else None)
        path = config.find_file(folder, os.getcwd())
    try:
        cfg = config.load_file(path) if path else {}
        if getattr(args, "profile", None):
            cfg = {**cfg, "profile": profiles.get(args.profile).name}
    except config.SettingsError as err:
        raise NetBoxError(str(err)) from err
    # A profile picked on the command line is a setting too; say where it came from, by name.
    flag = f"--profile {cfg['profile']}" if getattr(args, "profile", None) else ""
    return cfg, f"{path} + {flag}" if path and flag else str(path or flag)


def _profile(export: dict, cfg: tuple) -> profiles.Profile:
    """The industry profile one site is drawn to: --profile, then the settings file, then NetBox's field."""
    try:
        return profiles.from_settings(intake.intake(intake.prepare(export, *cfg)).settings)
    except config.SettingsError as err:
        raise SystemExit(f"netdiagrams: {err}")


def _template(args, profile: profiles.Profile) -> ET.Element:
    return stencils.inflate(ET.parse(args.template).getroot()) if args.template else sync.default_template(profile)


def _render(export: dict, out: Path, segaudit_note: bool, cfg: tuple = ({}, "")) -> None:
    with profiles.use(_profile(export, cfg)):
        site = build_site(intake.prepare(export, *cfg))
        drawio.write(drawio.render(site, segaudit_note=segaudit_note), out)
        examples = profiles.word("zone_examples")
    zoned = sum(1 for d in site.devices.values() if d.zone)
    print(f"Wrote {out}: {len(site.devices)} devices ({zoned} zoned), {len(site.links)} links, "
          f"{len([z for z in site.zones.values() if z.slug])} zones.")
    if zoned < len(site.devices):
        print(f"Tip: tag devices zone-<name> in NetBox (e.g. {examples}) to place them in their zone.")


def _exports(args):
    """Yield one export per site: the --input file, the --site given, or every site with devices."""
    if args.input:
        yield load_export(args.input)
        return
    client = _client(args)
    slugs = [args.site] if args.site else None
    if slugs is None:
        sites = client.sites()
        slugs = [s["slug"] for s in sites if (s.get("device_count") or 0) > 0 or "device_count" not in s]
        if not slugs:
            raise NetBoxError("NetBox has no sites with devices yet.")
        print(f"Reading {len(slugs)} site(s) from {client.base[:-4]}: {', '.join(slugs)}")
    for slug in slugs:
        yield client.export_site(slug)


def _out_path(args, slug: str, suffix: str, many: bool) -> Path:
    if args.output and not many and not Path(args.output).is_dir():
        return Path(args.output)
    folder = Path(args.output or ".")  # several sites, or -o names a folder
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{slug}{suffix}"


def _page_list(args) -> str:
    """--leave-out and --keep-in as one page list: -name leaves a page out, +name keeps it."""
    split = lambda text: [n for n in text.replace(",", " ").split() if n]
    return " ".join([f"-{n}" for n in split(args.leave_out)] + [f"+{n}" for n in split(args.keep_in)])


def _prefix_map(values: list[str]) -> dict[str, str]:
    out = {}
    for value in values or []:
        if "=" not in value:
            raise NetBoxError(f"--rename expects OLD=NEW, got '{value}'")
        old, new = value.split("=", 1)
        out[old] = new
    return out


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def cmd_build(args) -> None:
    cfg, cfg_name = _settings(args)
    started = time.perf_counter()
    exports = list(_exports(args))
    read_time = time.perf_counter() - started
    many = len(exports) > 1
    for export in exports:
        started = time.perf_counter()
        try:
            export = intake.prepare(export, cfg, cfg_name)  # once: _profile and fill take it as it is
        except config.SettingsError as e:
            raise SystemExit(f"netdiagrams: {e}")
        template = _template(args, _profile(export, (cfg, cfg_name)))
        slug = export["site"].get("slug") or "site"
        out = _out_path(args, slug, ".drawio", many)
        quality_file = out.with_suffix(".quality.json")
        state_file = out.with_suffix(".state.json")
        previous = _read_json(quality_file)
        try:
            report = sync.fill(template, export, prefix_map=_prefix_map(args.rename), tray=not args.no_tray,
                               keep_unmatched=args.keep_unmatched, glance=args.glance, riser=args.riser, audit=args.audit,
                               controls=not args.no_controls, data_gaps=not args.no_plan,
                               pages=_page_list(args), settings=cfg, settings_name=cfg_name,
                               book_note=not args.no_book_note, guide=not args.no_guide,
                               source_name=args.input or "",
                               revision=args.rev or "", quality_sheet=not args.no_quality,
                               previous_quality=previous,
                               previous_state=_read_json(state_file))
        except (PageError, config.SettingsError) as e:
            raise SystemExit(f"netdiagrams: {e}")
        sync.write(template, out)
        drift = out.with_suffix(".drift.md")
        drift.write_text(report.markdown(export["site"].get("name") or slug), "utf-8")
        quality_file.write_text(json.dumps(report.quality.to_json(), indent=1) + "\n", "utf-8")
        state_file.write_text(json.dumps(report.state, indent=1) + "\n", "utf-8")
        placed = len(report.matched_devices)
        took = time.perf_counter() - started
        timing = f"drawn in {took:.1f}s" + (f", NetBox read in {read_time / len(exports):.1f}s" if not args.input else "")
        print(f"Wrote {out}: {placed} devices placed ({len(report.slotted)} in a matching slot), "
              f"{len(report.tables)} tables and {report.tags} labels filled from NetBox ({timing}).")
        if report.netbox_only_devices:
            physical = len(report.netbox_only_devices) - len(report.wireless_tray)
            trays = [(n, where) for n, where in ((physical, "physical page"), (len(report.wireless_tray), "wireless sheet")) if n]
            print("  " + " and ".join(f"{n} device{'s' if n != 1 else ''} had no slot and wait{'s' if n == 1 else ''} in the tray "
                                      f"below the {where}" for n, where in trays) + ".")
        if report.grouped:
            n = sum(len(m) for m in report.grouped.values())
            print(f"  {n} more end devices are shown as counted groups on {len(report.grouped)} shapes.")
        if report.glance:
            print("  Added a 'Site at a glance' page with every zone and its device counts.")
        if report.riser:
            print("  Added a 'Riser' sheet: buildings, floors and closets from NetBox's locations.")
        if report.audit:
            print("  Added sheet 3f 'Audit evidence': owners, scope, backups, patching, monitoring and logging.")
        for page, why in report.skipped_pages:
            print(f"  Left out {page.split(' · ')[0]}: {why}.")
        for sheet in report.oversize:
            print(f"  Larger than A0, prints tiled: {sheet}.")
        print("  " + quality.lines(report.quality, previous)[0] + (" · sheet 1c has the detail"
                                                                   if not args.no_quality else ""))
        worst = report.quality.worst[:3]
        if worst:
            print("  Fix first: " + "; ".join(f"{n} ({', '.join(f)})" for n, f, _ in worst)
                  + ". 'netdiagrams gaps' writes the import files.")
        if report.changes_since is not None:
            since = report.changes_since
            print(f"  Since Rev {since.since_revision}: {since.summary()}"
                  + (f"; {report.marked_changes} shapes carry a NEW or CHANGED pill" if report.marked_changes else "")
                  + ".")
        print(f"  Drift report: {drift}")


def cmd_draft(args) -> None:
    cfg = _settings(args)
    exports = list(_exports(args))
    for export in exports:
        slug = export["site"].get("slug") or "site"
        _render(export, _out_path(args, slug, "-draft.drawio", len(exports) > 1), not args.no_note, cfg)


def cmd_doctor(args) -> None:
    cfg, cfg_name = _settings(args)
    proposed: dict = {}
    lowest = 100
    for export in _exports(args):
        profile = _profile(export, (cfg, cfg_name))
        try:
            with profiles.use(profile):
                text, suggestion = doctor.check(export, _template(args, profile), cfg, cfg_name)
                card = doctor.quality(export, cfg, cfg_name)
        except config.SettingsError as e:
            raise SystemExit(f"netdiagrams: {e}")
        print(text)
        lowest = min(lowest, card.score)
        print("\n".join(quality.lines(card)) + "\n")
        proposed = config.merge(proposed, suggestion) if suggestion else proposed
    if args.fail_under is not None and lowest < args.fail_under:
        print(f"netdiagrams: data quality {lowest} is under {args.fail_under}.", file=sys.stderr)
        raise SystemExit(1)
    if args.save_settings and proposed:
        path = Path(args.save_settings)
        merged = config.merge(cfg, proposed)
        path.write_text(json.dumps(merged, indent=2) + "\n", "utf-8")
        print(f"Saved the proposed settings to {path}. Check the role mapping, then build.")


def cmd_export(args) -> None:
    args.input = None
    exports = list(_exports(args))
    for export in exports:
        slug = export["site"].get("slug") or "site"
        out = _out_path(args, slug, "-netbox.json", len(exports) > 1)
        out.write_text(json.dumps(export, indent=1), "utf-8")
        print(f"Wrote {out}: {len(export['devices'])} devices, {len(export['cables'])} cables.")


def cmd_sample(args) -> None:
    try:
        profile = profiles.get(args.profile)
    except config.SettingsError as err:
        raise SystemExit(f"netdiagrams: {err}")
    out = Path(args.output or profile.sample_out)
    with profiles.use(profile):
        sync.write(sync.finish_sample(sync.default_template(profile)), out)
    print(f"Wrote {out}: {profile.sample_title}, fully drawn to the standard.")


def cmd_blank(args) -> None:
    out = Path(args.output or "blank.drawio")
    try:
        profile = profiles.get(args.profile)
    except config.SettingsError as err:
        raise SystemExit(f"netdiagrams: {err}")
    with profiles.use(profile):
        drawio.write(drawio.render(drawio.blank_site(), segaudit_note=not args.no_note), out)
    print(f"Wrote {out}.")


def cmd_stencils(args) -> None:
    cfg = config.merge(config.DEFAULTS, _settings(args)[0])
    try:
        profile = profiles.from_settings(cfg)
    except config.SettingsError as err:
        raise SystemExit(f"netdiagrams: {err}")
    out = Path(args.output or ("Network-Docs-Stencils.xml" if profile is profiles.MANUFACTURING
                               else f"{profile.name}-stencils.xml"))
    with profiles.use(profile):
        n = stencils.write_library(out)
    print(f"Wrote {out}: {n} shapes for the {profile.industry.lower()} standard. "
          "In draw.io: File ▸ Open Library from ▸ Device.")


def cmd_netbox_setup(args) -> None:
    cfg = config.merge(config.DEFAULTS, _settings(args)[0])
    try:
        profile = profiles.from_settings(cfg)
    except config.SettingsError as err:
        raise SystemExit(f"netdiagrams: {err}")
    with profiles.use(profile):
        _netbox_setup(args, _template(args, profile), cfg)


def _netbox_setup(args, template: ET.Element, cfg: dict) -> None:
    client, have, version = None, {}, ""
    if not args.offline:
        try:
            client = _client(args)
            have = netbox_setup.inventory(client)
            version = client.version()
        except NetBoxError as err:
            if args.check or args.apply:
                raise
            print("Not logged in to NetBox, so every file is written. Run 'netdiagrams login' to skip what exists.")
    if args.check:
        if client is None:
            raise NetBoxError("--check needs a NetBox to compare with (log in, or drop --offline).")
        for line in netbox_setup.check_lines(netbox_setup.check(template, have, cfg, version)):
            print(line)
        return
    existing = {kind: set(objects) for kind, objects in have.items()}
    files = netbox_setup.setup_files(template, existing, cfg)
    if args.apply:
        if client is None:
            raise NetBoxError("--apply needs a NetBox to write to (log in, or drop --offline).")
        steps = netbox_setup.plan(files, version)
        if not steps:
            print("NetBox already has every field, tag and role the template uses. Nothing to create.")
            return
        print(f"Creating {len(steps)} objects in {client.base[:-4]}" + (f" (NetBox {version})" if version else "")
              + ". Nothing that exists is changed or removed.")
        results = netbox_setup.apply(client, steps, have)
        for label, outcome in results:
            print(f"  {label}: {outcome}")
        created = sum(1 for _, o in results if o == "created")
        failed = [label for label, o in results if o.startswith(("failed", "skipped"))]
        print(f"{created} created." + (f" {len(failed)} not created: {', '.join(failed)}." if failed else ""))
        if failed:
            raise SystemExit(1)
        return
    out = Path(args.output or "netbox-setup")
    written = netbox_setup.write(out, files)
    if not written:
        print("NetBox already has every field, tag and role the template uses. Nothing to import.")
        return
    steps = netbox_setup.plan(files, version)
    print(f"Wrote {len(written)} import files to {out}/ ({len(steps)} objects). Import them in NetBox in order; "
          f"{out}/README.txt says where. Or run netdiagrams netbox-setup --apply to create them through the API.")


def cmd_gaps(args) -> None:
    cfg, cfg_name = _settings(args)
    exports = list(_exports(args))
    for export in exports:
        slug = export["site"].get("slug") or "site"
        profile = _profile(export, (cfg, cfg_name))
        with profiles.use(profile):   # the same tidied data, settings and industry the build and doctor use
            try:
                export = intake.prepare(export, cfg, cfg_name)
            except config.SettingsError as e:
                raise SystemExit(f"netdiagrams: {e}")
            locations = ot.Locations(export.get("locations"))
            checked = intake.intake(export).data_date or dt.date.today().isoformat()
            found = gaps.find(export, sync.endpoint_roles(), lambda d: ot.device_zones(d, locations), checked)
            files = worksheets.files(export, found)
            for line in worksheets.SKIPPED:
                print(f"{slug}: left out of the import files, a value starts like a spreadsheet formula "
                      f"(fix it in NetBox): {line}")
        folder = Path(args.output) if args.output and len(exports) == 1 else Path(args.output or ".") / f"{slug}-gaps"
        written = worksheets.write(folder, files)
        if not written:
            print(f"{slug}: nothing to close through import files; see the drift report for what remains.")
            continue
        rows = sum(text.count("\n") - 1 for text in files.values())
        files_word = "import file" if len(written) == 1 else "import files"
        objects = "object" if rows == 1 else "objects"
        print(f"Wrote {len(written)} {files_word} to {folder}/ ({rows} {objects} with gaps). Fill the blanks and "
              f"import them in NetBox; {folder}/README.txt says where each goes.")


def cmd_share(args) -> None:
    src = Path(args.drawing)
    try:
        mxfile = ET.parse(src).getroot()
    except (OSError, ET.ParseError) as err:
        raise SystemExit(f"netdiagrams: cannot read {src}: {err}")
    report = share.share(mxfile, audience=args.audience, keep_examples=args.keep_examples)
    out = Path(args.output or src.with_name(f"{src.stem}-{args.audience}{src.suffix}"))
    for line in report.lines():
        print(line)
    if report.leaks and not args.allow_leaks:
        raise SystemExit(f"netdiagrams: not written. {out} would still carry data from the original "
                         "(listed above). Fix the drawing, or pass --allow-leaks to write it anyway.")
    share.write(mxfile, out)
    print(f"Wrote {out}." + (" Leaks listed above were kept (--allow-leaks)." if report.leaks else ""))


COMMANDS = {"build", "draft", "doctor", "export", "login", "sample", "blank", "stencils", "netbox-setup", "share",
            "gaps"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="netdiagrams",
        description="Network diagrams from NetBox. Run 'netdiagrams' on its own to draw every site.")
    p.add_argument("--version", action="version", version=f"netdiagrams {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def netbox_args(sp):
        sp.add_argument("--netbox-url", help="NetBox URL. Default: NETBOX_URL, then your saved login.")
        sp.add_argument("--insecure", action="store_true", help="Skip TLS certificate checks.")

    b = sub.add_parser("build", help="Fill the drawing template from NetBox (the default command).")
    b.add_argument("--template", help="Your own .drawio template (default: the bundled S01 standard).")
    b.add_argument("--rename", action="append", metavar="OLD=NEW",
                   help="Override the automatic site-prefix rename, e.g. S01-=S07- (repeatable).")
    b.add_argument("--no-tray", action="store_true", help="Don't add unplaced NetBox devices below the drawing.")
    b.add_argument("--no-controls", action="store_true",
                   help="Leave out the show/hide buttons at the top of each page.")
    b.add_argument("--leave-out", metavar="PAGES", default="",
                   help="Pages to leave out, by group, page id or sheet number, e.g. 'failover,reference,3b'. "
                        "Wireless pages are left out by themselves when NetBox has no wireless gear.")
    b.add_argument("--keep-in", metavar="PAGES", default="",
                   help="Pages to keep even when NetBox has nothing for them, e.g. 'wireless'.")
    b.add_argument("--no-plan", action="store_true",
                   help="Leave out the 'Plan to improve this page' cards that list what NetBox is missing.")
    b.add_argument("--no-guide", action="store_true",
                   help="Remove the hidden 'Guides' layer (the template's how-to notes and design rules) "
                        "instead of keeping it hidden.")
    b.add_argument("--no-book-note", action="store_true",
                   help="Leave out the line under each sheet naming the book chapter that explains it.")
    b.add_argument("--no-quality", action="store_true", help="Leave out the 'Data quality' sheet (1c).")
    b.add_argument("--glance", action=argparse.BooleanOptionalAction, default=None,
                   help="Add the 'Site at a glance' zone page always (--glance) or never (--no-glance). "
                        "Default: when the site outgrows the template.")
    b.add_argument("--riser", action=argparse.BooleanOptionalAction, default=None,
                   help="Add the 'Riser' sheet (buildings, floors, closets and the cables between them, from "
                        "NetBox locations) always (--riser) or never (--no-riser). Default: when the site's "
                        "locations nest and more than one holds network gear.")
    b.add_argument("--audit", action=argparse.BooleanOptionalAction, default=None,
                   help="Add sheet 3f 'Audit evidence' (owner, compliance scope, backups, patching, verification, "
                        "support, monitoring and logging per asset) always (--audit) or never (--no-audit). "
                        "Default: when NetBox records any of that evidence for the site.")
    b.add_argument("--keep-unmatched", action="store_true",
                   help="Keep template devices that aren't in NetBox instead of removing them.")
    b.add_argument("--rev", metavar="REV",
                   help="Revision to print in every title block, e.g. C or 2026-10. Default: the first six "
                        "characters of the data fingerprint, so the same NetBox data gives the same revision.")
    b.set_defaults(func=cmd_build)

    f = sub.add_parser("draft", help="Lay out a first draft automatically, for a site with no drawing yet.")
    f.set_defaults(func=cmd_draft)
    e = sub.add_parser("export", help="Save sites' NetBox objects to JSON (read-only).")
    e.set_defaults(func=cmd_export)
    ga = sub.add_parser("gaps", help="Write NetBox import files that close the data gaps the drawing lists "
                                      "(fill the blanks, import, build again).")
    ga.set_defaults(func=cmd_gaps)

    d = sub.add_parser("doctor", help="Check what a build would infer from NetBox (roles, zones, prefix), "
                                      "and what to fix first. Draws nothing.")
    d.add_argument("--template", help="Your own .drawio template (default: the bundled S01 standard).")
    d.add_argument("--fail-under", type=int, metavar="SCORE",
                   help="Exit 1 when a site's data quality score is under SCORE (for a scheduled check).")
    d.add_argument("--save-settings", metavar="FILE",
                   help="Write the settings with the proposed role mapping to FILE, e.g. netdiagrams.json.")
    d.set_defaults(func=cmd_doctor)
    for sp in (b, f, e, d, ga):
        sp.add_argument("--site", help="NetBox site slug. Default: every site with devices.")
        netbox_args(sp)
    for sp in (b, f, d, ga):
        sp.add_argument("--input", help="A NetDiagrams export (from 'netdiagrams export') instead of live NetBox.")

    lg = sub.add_parser("login", help="Save your NetBox URL and token so you never type them again.")
    netbox_args(lg)
    lg.set_defaults(func=cmd_login)

    s = sub.add_parser("sample", help="Write an industry's fictional example drawing (Plant A by default).")
    s.set_defaults(func=cmd_sample)
    k = sub.add_parser("blank", help="Write an empty drawing with one zone per band (Purdue level for a plant).")
    k.set_defaults(func=cmd_blank)
    t = sub.add_parser("stencils", help="Save the draw.io shape library.")
    t.set_defaults(func=cmd_stencils)
    n = sub.add_parser("netbox-setup",
                       help="Write NetBox import files for the zones, roles and custom fields the template uses.")
    n.add_argument("--template", help="Your own .drawio template (default: the bundled S01 standard).")
    n.add_argument("--offline", action="store_true", help="Don't read NetBox; write every file.")
    n.add_argument("--check", action="store_true",
                   help="Only compare: list each field, tag and role the template needs as present or missing.")
    n.add_argument("--apply", action="store_true",
                   help="Create the missing fields, tags and roles through the API (needs a token that can write). "
                        "Nothing that exists is changed or removed.")
    netbox_args(n)
    n.set_defaults(func=cmd_netbox_setup)
    for sp in (b, f, d, s, k, n, t):
        sp.add_argument("--profile", metavar="NAME",
                        help=f"Industry standard to draw to: {', '.join(sorted(profiles.PROFILES))} "
                             f"(default: the 'profile' setting, else {profiles.DEFAULT}).")

    sh = sub.add_parser("share", help="Copy a built drawing with IPs, serials, circuit IDs, NetBox links and the "
                                      "template's examples stripped, for a vendor, an auditor or management.")
    sh.add_argument("drawing", help="A .drawio file netdiagrams built.")
    sh.add_argument("--audience", choices=share.AUDIENCES, default="vendor",
                    help="vendor (default): no IPs, serials, asset tags, circuit IDs or links. auditor: every "
                         "register and link stays; only guides and examples go. management: overview sheets only. "
                         "The audit evidence sheet (3f) goes to the auditor only.")
    sh.add_argument("--keep-examples", action="store_true",
                    help="Keep the template's example and reference sheets (flows, failover, multi-site, "
                         "platforms, NetBox).")
    sh.add_argument("--allow-leaks", action="store_true",
                    help="Write the copy even when data from the original is still found in it.")
    sh.add_argument("-o", "--output", help="Output file (default: <drawing>-<audience>.drawio).")
    sh.set_defaults(func=cmd_share)

    for sp in (b, f, d, n):
        sp.add_argument("--settings", metavar="FILE",
                        help=f"Settings file (role map, zone field, naming...). Default: {config.FILE_NAME} "
                             "in the output folder or the current folder.")
    for sp in (b, f, e, s, k, t, n, ga):
        sp.add_argument("-o", "--output", help="Output file (or folder, when drawing several sites).")
    for sp in (f, k):
        sp.add_argument("--no-note", action="store_true", help="Leave out the 'About this drawing' note.")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # 'netdiagrams' and 'netdiagrams --site s01' mean 'netdiagrams build ...'.
    if not argv or (argv[0] not in COMMANDS and argv[0] not in ("-h", "--help", "--version")):
        argv.insert(0, "build")
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except NetBoxError as err:
        print(f"netdiagrams: {err}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    return 0
