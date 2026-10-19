import contextlib
import copy
import csv
import io
import dataclasses
import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from contextlib import redirect_stdout
from importlib import resources
from pathlib import Path
from unittest import mock

from netdiagrams import audit, changes, cli, profiles, doctor, drawio, gaps, hardware, intake, model, netbox, netbox_setup, ot, paper, quality, riser, settings, share, stencils, sync, truth, wireless, worksheets
from netdiagrams.graph import Graph, cell_of, plain
from netdiagrams.graph import text_lines as graph_mod_text_lines
from netdiagrams.model import band_for_zone, build_site
from netdiagrams.netbox import NetBoxClient


def sample_export():
    return json.loads(resources.files("netdiagrams").joinpath("data", cli.SAMPLE_FILE).read_text("utf-8"))


class ZoneBands(unittest.TestCase):
    def test_readme_lists_only_the_files_written_in_the_profiles_words(self):
        full = netbox_setup.guide({"3-zone-tags.csv": "", "4-device-roles.csv": ""})
        self.assertIn("3-zone-tags.csv", full)
        self.assertNotIn("1-custom-field-choice-sets.csv", full)
        self.assertIn("Purdue level", full)
        school = dataclasses.replace(profiles.MANUFACTURING, name="test-school", levels=False,
                                     words={"place_nouns": "building, wing, closet"})
        with profiles.use(school):
            text = netbox_setup.guide({"3-zone-tags.csv": ""})
        self.assertNotIn("Purdue", text)
        self.assertNotIn("cell", text)
        self.assertIn("(building, wing, closet)", text)
        self.assertIn("rooms under floors and buildings", text)
        self.assertEqual(netbox_setup.guide({}).split("\n")[0],
                         "NetBox already has every field, tag and role the template uses; nothing to import.")

    def test_stencil_library_follows_the_profile(self):
        import tempfile
        base = {e["title"]: e for e in stencils._entries(stencils.LIBRARY_FILE)}
        with tempfile.TemporaryDirectory() as tmp:
            own = Path(tmp) / "school.xml"
            own.write_text("<mxlibrary>" + json.dumps([{**base["Server (asset)"], "title": "Camera (asset)"}])
                           + "</mxlibrary>", "utf-8")
            school = dataclasses.replace(
                profiles.MANUFACTURING, name="test-school", levels=False, band_word="Band",
                bands=(("B1", "DISTRICT · INTERNET", ("wan",)), ("B2", "STAFF (IT)", ("staff",)),
                       ("B3", "CLASSROOMS", ("class",))),
                band_palette={"B1": "L5", "B2": "L4", "B3": "L2–0"},
                role_shapes={"camera": "Camera (asset)"}, stencil_library=str(own))
            with profiles.use(school):
                lib = stencils.library()
                self.assertIn("Camera (asset)", lib)
                self.assertEqual(stencils.shape_for_role("camera"), "Camera (asset)")
                self.assertEqual(stencils.shape_for_role("plc"), "PLC")
                self.assertIn("Band B2 · STAFF (IT)", lib)
                self.assertIn("Band B3 · CLASSROOMS", lib)
                self.assertFalse([t for t in lib if t.startswith("Purdue band")])
                values = [el.get("value") for el in lib["Band B3 · CLASSROOMS"]["root"].iter("mxCell")]
                self.assertIn("<b>B3</b>", values)
                self.assertIn("CLASSROOMS", values)
                out = Path(tmp) / "lib.xml"
                n = stencils.write_library(out)
                self.assertEqual(n, len(lib))
                self.assertIn("Camera (asset)", out.read_text("utf-8"))
            self.assertEqual(stencils.shape_for_role("camera"), stencils.DEFAULT_SHAPE)
            self.assertIn("Purdue band L4", stencils.library())
            plant = Path(tmp) / "plant.xml"
            stencils.write_library(plant)
            self.assertEqual(plant.read_bytes(), (Path("src/netdiagrams/data") / stencils.LIBRARY_FILE).read_bytes())

    def test_zone_tags_come_from_the_zone_tables_too(self):
        slugs = [line.split(",")[1] for line in
                 netbox_setup.setup_files(sync.default_template())["3-zone-tags.csv"].splitlines()[1:]]
        self.assertIn("zone-guest", slugs)  # GUEST has no device of its own, only a zone-table row
        self.assertNotIn("zone-native", slugs)
        self.assertNotIn("zone-cell0n", slugs)

    def test_profile_hooks_feed_roles_names_zones_and_naming(self):
        test_profile = dataclasses.replace(
            profiles.MANUFACTURING, name="test-industry", endpoint_roles=("pos-terminal",),
            role_names={"pos-terminal": "POS terminal"}, role_colors={"pos-terminal": "9c27b0"},
            zone_names={"zone-cde": "Cardholder data"}, naming=r"^ST\d{3}-[A-Z0-9-]+$",
            words={**profiles.MFG_WORDS, "zone_examples": "zone-cde, zone-store-ops"})
        with profiles.use(test_profile):
            self.assertIn("pos-terminal", sync.endpoint_roles())
            self.assertEqual(profiles.role_name("pos-terminal", netbox_setup.ROLE_NAMES), "POS terminal")
            self.assertEqual(profiles.role_name("plc", netbox_setup.ROLE_NAMES), "PLC")
            self.assertEqual(profiles.role_color("pos-terminal", netbox_setup.ROLE_COLORS), "9c27b0")
            self.assertEqual(gaps.naming_pattern({}), r"^ST\d{3}-[A-Z0-9-]+$")
            self.assertEqual(gaps.naming_pattern({"pattern": "^X-"}), "^X-")
            files = netbox_setup.setup_files(sync.default_template())
            self.assertIn("Cardholder data,zone-cde,", files["3-zone-tags.csv"])
            self.assertEqual(profiles.word("zone_examples"), "zone-cde, zone-store-ops")
        self.assertNotIn("pos-terminal", sync.endpoint_roles())
        self.assertEqual(gaps.naming_pattern({}), gaps.NAME.pattern)

    def test_zone_tags_come_from_any_tagged_shape(self):
        template = sync.default_template()
        root = template.find("diagram").find("mxGraphModel/root")
        vlan = ET.SubElement(root, "object", {"id": "t-vlan-guest", "label": "VLAN 500 GUEST", "tags": "zone-guest"})
        ET.SubElement(vlan, "mxCell", {"vertex": "1", "parent": "1"})
        files = netbox_setup.setup_files(template)
        self.assertIn("zone-guest", files["3-zone-tags.csv"])

    def test_zone_tags_map_to_purdue_levels(self):
        cases = {
            "zone-wan": "L5", "zone-it-ent": "L4", "zone-guest": "L4", "zone-idmz": "L3.5",
            "zone-ot-ops": "L3", "zone-ot-mgmt": "L3", "zone-cell01": "L2–0", "zone-sis": "L2–0",
            "zone-lab": "—", None: "?",
        }
        for zone, level in cases.items():
            self.assertEqual(band_for_zone(zone)[0], level, zone)


def small_site_export():
    return json.loads((Path(__file__).parent / "fixtures" / "small-site.json").read_text("utf-8"))


class Draft(unittest.TestCase):
    def setUp(self):
        self.site = build_site(small_site_export())
        self.xml = drawio.render(self.site)

    def test_two_pages(self):
        self.assertEqual([d.get("id") for d in self.xml.findall("diagram")], ["logical", "physical"])

    def test_every_device_card_carries_netbox_fields(self):
        for diagram in self.xml.findall("diagram"):
            names = {o.get("name") for o in diagram.iter("object") if o.get("role")}
            self.assertEqual(names, {d.name for d in self.site.devices.values()})

    def test_stencil_example_values_do_not_leak(self):
        plc = next(o for o in self.xml.iter("object") if o.get("name") == "S01-C02-PLC01")
        self.assertEqual(plc.get("manufacturer"), "Siemens")
        self.assertNotIn("‹", ET.tostring(self.xml, encoding="unicode"))

    def test_links_attach_to_cards_on_the_page(self):
        physical = self.xml.find("diagram[@id='physical']")
        ids = {c.get("id") for c in physical.iter() if c.get("id")}
        edges = [c for c in physical.iter("mxCell") if c.get("edge") == "1"]
        self.assertEqual(len(edges), len(self.site.links))
        for edge in edges:
            self.assertIn(edge.get("source"), ids)
            self.assertIn(edge.get("target"), ids)

    def test_ids_unique_per_page(self):
        for diagram in self.xml.findall("diagram"):
            ids = [c.get("id") for c in diagram.iter() if c.tag in ("mxCell", "object") and c.get("id")]
            self.assertEqual(len(ids), len(set(ids)))

    def test_vlans_land_in_their_zone(self):
        self.assertEqual([v.vid for v in self.site.zones["zone-cell01"].vlans], [510])

    def test_unzoned_devices_get_their_own_band(self):
        export = small_site_export()
        export["devices"][0]["tags"] = []
        site = build_site(export)
        self.assertIn("", site.zones)
        self.assertEqual(site.bands()[-1][0][0], "?")


def page(template, prefix):
    from netdiagrams.graph import Graph
    return Graph(next(d for d in template.findall("diagram") if d.get("name").startswith(prefix)))


def table_rows(g, first_header):
    from netdiagrams.graph import plain
    table = next(t for t in g.tables() if g.header(t)[:1] == [first_header])
    return [[plain(g.value(g.els[c])) for c in g.row_cells(r)] for r in g.rows(table)[1:]]


class Shift(unittest.TestCase):
    def test_lines_move_with_the_shapes_below_a_growing_table(self):
        page = ET.fromstring(
            '<diagram name="p"><mxGraphModel pageHeight="500"><root><mxCell id="0"/>'
            '<mxCell id="1" parent="0"/>'
            '<mxCell id="box" vertex="1" parent="1"><mxGeometry x="10" y="200" width="50" height="20" as="geometry"/></mxCell>'
            '<mxCell id="sample" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
            '<mxPoint x="10" y="240" as="sourcePoint"/><mxPoint x="60" y="240" as="targetPoint"/></mxGeometry></mxCell>'
            '<mxCell id="above" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
            '<mxPoint x="10" y="40" as="sourcePoint"/><mxPoint x="60" y="40" as="targetPoint"/></mxGeometry></mxCell>'
            '</root></mxGraphModel></diagram>')
        g = Graph(page)
        g.shift_below(0, 100, 100, 30, set())
        self.assertEqual(g.geometry("box").get("y"), "230")
        self.assertEqual([p.get("y") for p in g.geometry("sample").iter("mxPoint")], ["270", "270"])
        self.assertEqual([p.get("y") for p in g.geometry("above").iter("mxPoint")], ["40", "40"])


class TemplateFill(unittest.TestCase):
    def test_sample_export_fills_the_template_without_drift(self):
        template = sync.default_template()
        before = {d.get("name"): sorted(o.get("name") for o in d.iter("object") if sync._is_device(o))
                  for d in template.findall("diagram")}
        report = sync.fill(template, sample_export(), today="2026-10-09")
        self.assertEqual(report.changes, [])
        self.assertFalse(report.netbox_only_devices or report.drawing_only_devices or report.removed_devices)
        self.assertEqual(len(report.matched_devices), 70)
        after = {d.get("name"): sorted(o.get("name") for o in d.iter("object") if sync._is_device(o))
                 for d in template.findall("diagram") if d.get("id") not in ("quality", "audit")}
        self.assertEqual(before, after)
        # Registers keep the template's scope: network gear on the physical page, radios on wireless.
        self.assertEqual(len(table_rows(page(template, "3 "), "HOSTNAME")), 44)
        self.assertEqual(len(table_rows(page(template, "3d"), "HOSTNAME")), 11)

    def test_a_named_port_cell_shows_its_own_interface_name(self):
        # A port cell's bold name is typed text: it must be the interface it stands for, not another one.
        wrong = []
        for o in sync.default_template().iter("object"):
            name = re.match(r"<b>([A-Za-z][^<]*)</b>", o.get("label") or "")
            if name and o.get("device") and o.get("name") and name.group(1) != o.get("name"):
                short = {"management": "MGT"}.get(o.get("name")) or re.sub(r"^StackPort\d+/", "SP", o.get("name"))
                if not o.get("name").endswith(name.group(1)) and name.group(1) != short:
                    wrong.append((o.get("device"), o.get("name"), name.group(1)))
        self.assertEqual(wrong, [])

    def test_link_register_groups_port_channels_and_chassis(self):
        template = sync.default_template()
        sync.fill(template, sample_export())
        rows = {r[0]: r for r in table_rows(page(template, "3 "), "LINK")}
        self.assertRegex(rows["Po1"][1], r"^#\d+, #\d+$")  # the NetBox cable ids beside the link
        self.assertEqual(rows["Po1"][2], "IT-CORE Twe1/0/1 · Twe2/0/1")
        self.assertEqual(rows["REP 11"][3], "C01-IE01 Gi1/1 · C01-IE03 Gi1/2")
        self.assertIn("RP", rows)
        self.assertFalse([r for r in rows.values() if "PLC" in r[2] + r[3]])

    def test_vlan_tables_follow_their_zone(self):
        export = sample_export()
        vlan = next(v for v in export["vlans"] if v["vid"] == 510)
        vlan["name"] = "CELL01-RENAMED"
        template = sync.default_template()
        sync.fill(template, export)
        logical = page(template, "2 ")
        rows = [r for t in logical.tables() if logical.header(t)[:2] == ["VLAN", "NAME"]
                for r in table_rows_by_id(logical, t)]
        self.assertIn(["510", "CELL01-RENAMED"], [r[:2] for r in rows])

    def test_netbox_changes_flow_into_the_drawing_and_the_report(self):
        export = sample_export()
        fw = next(d for d in export["devices"] if d["name"] == "S01-FW-ITOT-01")
        fw["serial"] = "NEW-SERIAL-1"
        export["devices"] = [d for d in export["devices"] if d["name"] != "S01-OOB-SW-01"]
        export["devices"].append({"id": 999, "name": "S01-OT-NEW-01", "role": {"slug": "server"},
                                  "device_type": {"model": "R660"}, "tags": []})
        template = sync.default_template()
        report = sync.fill(template, export)
        drawn = [o for o in template.iter("object") if o.get("name") == "S01-FW-ITOT-01"]
        self.assertTrue(drawn and all(o.get("serial") == "NEW-SERIAL-1" for o in drawn))
        self.assertIn("S01-OOB-SW-01", report.drawing_only_devices)
        self.assertNotIn("S01-OOB-SW-01", {o.get("name") for o in template.iter("object")})
        self.assertEqual(report.netbox_only_devices, ["S01-OT-NEW-01"])
        tray = [o for o in template.iter("object") if o.get("name") == "S01-OT-NEW-01"]
        self.assertEqual(len(tray), 1)
        self.assertIn("NEW-SERIAL-1", report.markdown("Plant A"))
        # The serial tag next to the card is rewritten too.
        self.assertTrue([e for e in template.iter() if "NEW-SERIAL-1" in (e.get("value") or e.get("label") or "")
                         and not e.get("name")])

    def test_a_new_device_takes_the_slot_of_its_role(self):
        export = sample_export()
        oob = next(d for d in export["devices"] if d["name"] == "S01-OOB-SW-01")
        oob["name"] = "S01-OOB-SW-09"
        template = sync.default_template()
        report = sync.fill(template, export)
        self.assertEqual(report.slotted, {"S01-OOB-SW-01": "S01-OOB-SW-09"})
        self.assertEqual(report.netbox_only_devices, [])
        names = {o.get("name") for o in template.iter("object")}
        self.assertIn("S01-OOB-SW-09", names)
        self.assertNotIn("S01-OOB-SW-01", names)

    def test_extra_end_devices_become_a_counted_group(self):
        export = sample_export()
        export["netbox_url"] = "https://netbox.test"
        plc = next(d for d in export["devices"] if d["name"] == "S01-C01-PLC01")
        switch = next(c for c in export["cables"] if "S01-C01-PLC01" in json.dumps(c))
        for n in (2, 3):
            extra = json.loads(json.dumps(plc))
            extra.update(id=900 + n, name=f"S01-C01-PLC0{n}")
            export["devices"].append(extra)
            cable = json.loads(json.dumps(switch).replace("S01-C01-PLC01", extra["name"]))
            cable.update(id=900 + n, label=f"S01-CBL-90{n}")
            cable["a_terminations"][0]["object"]["device"]["id"] = extra["id"]
            export["cables"].append(cable)
        template = sync.default_template()
        report = sync.fill(template, export)
        self.assertEqual(report.grouped, {"S01-C01-PLC01": ["S01-C01-PLC02", "S01-C01-PLC03"]})
        self.assertEqual(report.netbox_only_devices, [])
        shape = next(o for o in template.iter("object") if o.get("name") == "S01-C01-PLC01")
        self.assertEqual(shape.get("label"), "<b>PLC ×3 · L1</b>")
        self.assertEqual(shape.get("link"), "https://netbox.test/dcim/devices/?id=36&id=902&id=903")
        self.assertTrue(shape.get("tooltip").startswith("Group of 3 devices: S01-C01-PLC01, S01-C01-PLC02"))

    def test_glance_page_only_when_the_site_outgrows_the_template(self):
        template = sync.default_template()
        sync.fill(template, sample_export())
        self.assertNotIn(sync.GLANCE_NAME, [d.get("name") for d in template.findall("diagram")])

        export = sample_export()
        new = json.loads(json.dumps(next(d for d in export["devices"] if d["name"] == "S01-OT-CORE-1")))
        new.update(id=999, name="S01-OT-CORE-9")
        export["devices"].append(new)
        template = sync.default_template()
        sync.fill(template, export, slots=False)
        names = [d.get("name") for d in template.findall("diagram")]
        self.assertEqual(names[1], sync.GLANCE_NAME)
        glance = template.findall("diagram")[1]
        cards = {o.get("zone"): int(o.get("devices")) for o in glance.iter("object") if o.get("zone") is not None}
        self.assertEqual(sum(cards.values()), len(export["devices"]))
        self.assertIn("zone-ot-ops", cards)
        texts = " ".join(c.get("value") or "" for c in glance.iter("mxCell"))
        self.assertIn("Site at a glance", texts)
        self.assertIn("1b", texts)

    def test_end_devices_stay_with_a_switch_that_has_no_shape(self):
        export = sample_export()
        ie = next(d for d in export["devices"] if d["name"] == "S01-C01-IE02")
        ie["name"] = "S01-C09-IE02"
        ie["role"] = {"name": "Core switch", "slug": "core-switch"}
        report = sync.fill(sync.default_template(), export, slots=False)
        self.assertEqual(report.grouped, {})
        self.assertIn("S01-C01-PLC01", report.matched_devices)

    def test_another_site_is_renamed_without_flags(self):
        export = json.loads(json.dumps(sample_export()).replace("S01-", "S07-"))
        export["site"] = {"id": 7, "slug": "s07", "name": "Plant G"}
        export["netbox_url"] = "https://nb.plant-g.example"
        template = sync.default_template()
        report = sync.fill(template, export, today="2026-10-09")
        self.assertEqual(report.site_code, "S07")
        # The only differences are text that names the site, e.g. a chassis or a description.
        self.assertTrue(all("S01" in old for *_, old, _new in report.changes))
        names = {o.get("name") for o in template.iter("object") if sync._is_device(o)}
        self.assertTrue(names and all(n.startswith("S07-") for n in names))
        raw = ET.tostring(template, encoding="unicode")
        links = [e.get(k) for e in template.iter() for k in ("link", "tooltip") if e.get(k)]
        self.assertFalse([x for x in links if "netbox.example.com" in x])
        self.assertIn("https://nb.plant-g.example/dcim/devices/", raw)
        self.assertIn("Plant G", raw)

    def test_a_zone_with_no_device_is_owned_by_its_vlan_or_prefix_tenant(self):
        from netdiagrams import model, truth
        export = {"site": {"name": "Store", "slug": "store"}, "devices": [], "cables": [],
                  "vlans": [{"id": 1, "vid": 500, "name": "GUEST", "tags": [{"slug": "zone-guest"}],
                             "tenant": {"name": "Guest services"}},
                            {"id": 2, "vid": 510, "name": "CDE", "tags": [{"slug": "zone-cde"}]}],
                  "prefixes": [{"prefix": "10.5.10.0/24", "vlan": {"id": 2}, "tenant": {"name": "Payments"}}]}
        site = model.build_site(export)
        self.assertEqual(truth._owner(site.zones["zone-guest"], {}), "Guest services")
        self.assertEqual(truth._owner(site.zones["zone-cde"], {}), "Payments")  # from the prefix

    def test_renamed_site_leaves_no_template_prefix_outside_example_sheets(self):
        export = json.loads(json.dumps(sample_export()).replace("S01-", "W02-"))
        export["site"] = {"id": 2, "slug": "w02", "name": "Northgate"}
        for d in export["devices"]:
            if d["name"] == "W02-C01-IE01":
                d["primary_ip4"] = None
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-15")
        left = {}
        for d in template.findall("diagram"):
            for el in d.iter():
                for attr in ("label", "value", "name", "tooltip", "link", "x_cable", "ssid", "interface_a", "interface_b"):
                    v = el.get(attr) or ""
                    if re.search(r"(?<![A-Za-z0-9])S01-", v):
                        left.setdefault(d.get("id"), []).append(f"{attr}: {v[:60]}")
        # Group titles, stack names, zone notes, links and register text follow the site; example
        # sheets keep Plant A's.
        self.assertFalse({p: v for p, v in left.items() if p not in truth.example_sheets()})
        physical = next(sync.Graph(d) for d in template.findall("diagram") if d.get("id") == "physical")
        self.assertIn("W02-FW-EDGE", "".join(physical.value(el) for el in physical.els.values()))
        # A device NetBox has no IP for does not inherit the template's.
        checked = False
        for tbl in physical.tables():
            header = physical.header(tbl)
            if "MGMT IP" in header:
                rows = {r[0]: dict(zip(header, r)) for r in sync._table_text(physical, tbl) if r}
                self.assertEqual(rows["W02-C01-IE01"]["MGMT IP"], "")
                checked = True
        self.assertTrue(checked)

    def test_s01_template_text_is_consistent(self):
        template = sync.default_template()
        raw = ET.tostring(template, encoding="unicode")
        self.assertNotIn("takes over instantly", raw)  # the failover sheet says "Brief pause"
        matrix_cell = next(el for el in template.iter("mxCell") if el.get("id") == "register-c349")
        self.assertEqual(matrix_cell.get("value"), "F22")  # OT-MGMT -> OT-OPS, the RADIUS flow the register lists

    def test_rename_prefix_for_a_copied_site(self):
        template = sync.default_template()
        sync.fill(template, {"site": {}, "devices": [], "cables": []}, prefix_map={"S01-": "S07-"},
                  tray=False, keep_unmatched=True)
        names = {o.get("name") for o in template.iter("object") if o.get("role") is not None}
        self.assertTrue(names and all(n.startswith("S07-") for n in names))


def table_rows_by_id(g, table):
    from netdiagrams.graph import plain
    return [[plain(g.value(g.els[c])) for c in g.row_cells(r)] for r in g.rows(table)[1:]]


class BigSites(unittest.TestCase):
    @staticmethod
    def make_site_module():
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_site", Path(__file__).parent.parent / "scripts" / "make_site.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @classmethod
    def setUpClass(cls):
        cls.make_site = cls.make_site_module()

    def test_plant_a_keeps_the_template_pages(self):
        template = sync.default_template()
        pages = len(template.findall("diagram"))
        report = sync.fill(template, sample_export())
        self.assertEqual((report.scheduled, report.register_sheets), ([], []))
        self.assertEqual(len(template.findall("diagram")), pages + 2)  # + the data quality and audit evidence sheets

    def test_a_large_site_gets_typicals_schedules_and_register_sheets(self):
        export = self.make_site.grow("large")
        template = sync.default_template()
        pages = len(template.findall("diagram"))
        report = sync.fill(template, export)
        self.assertEqual(report.netbox_only_devices, [])
        self.assertGreater(len(report.scheduled), 2000)
        self.assertGreater(len(template.findall("diagram")), pages)
        for d in template.findall("diagram"):  # long registers continue on more sheets, none larger than A0
            w, h = paper.content_size(d.find("mxGraphModel"))
            self.assertTrue(w <= 4681 and h <= 3311, f"{d.get('name')}: {w} × {h}")
        self.assertEqual(report.oversize, [])
        physical = next(d for d in template.findall("diagram") if d.get("id") == "physical")
        text = " ".join((e.get("value") or e.get("label") or "") for e in physical.iter() if e.tag in ("mxCell", "object"))
        for words in ("Cell schedule", "IDF schedule", "TYPICAL ×38", "C40-IE01"):
            self.assertIn(words, text)
        sheets = [d for d in template.findall("diagram") if (d.get("id") or "").startswith("physical-registers")]
        names = {e.get("value") or e.get("label") for s in sheets for e in s.iter() if e.tag in ("mxCell", "object")}
        switches = {d["name"] for d in export["devices"] if d["role"]["slug"] == "industrial-switch"}
        self.assertLessEqual(switches, names)
        logical = next(d for d in template.findall("diagram") if d.get("id") == "logical")
        text = " ".join((e.get("value") or e.get("label") or "") for e in logical.iter() if e.tag in ("mxCell", "object"))
        for words in ("Cell VLAN schedule", "TYPICAL ×40", "1409 TR-C40", "CELL01–40", "Big sites"):
            self.assertIn(words, text)
        self.assertEqual(report.vlan_scheduled, 37)


class DrawKit(unittest.TestCase):
    def test_a_kit_page_is_valid_drawio_with_unique_ids(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("drawkit", Path(__file__).parent.parent / "scripts" / "drawkit.py")
        kit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kit)
        p = kit.Page("demo", "1 · Demo", 1200, 800)
        layer = p.layer("Devices")
        self.assertEqual(p.layer("Devices"), layer)  # a layer is made once per name
        a = p.cell(layer, "<b>FW-01</b>", kit.CARD, 40, 40, 200, 56, {"name": "FW-01", "role": "firewall"})
        b = p.cell(layer, "SW-01", kit.CARD, 40, 200, 200, 56)
        e = p.edge(layer, a, b, kit.LINK_EDGE, "1G", exit=(0.5, 1), entry=(0.5, 0))
        p.edge_label(e, "port1", -0.8)
        p.table(layer, 300, 40, [("NAME", 100), ("VLAN", 60)], [["FW-01", ("10", "https://netbox.example.com/vlan/10")]])
        root = ET.fromstring(ET.tostring(kit.mxfile([p], "test")))
        ids = [el.get("id") for el in root.iter() if el.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        known = set(ids)
        for el in root.iter("mxCell"):
            for ref in ("parent", "source", "target"):
                self.assertIn(el.get(ref, "0"), known)
        self.assertEqual(root.find(".//object[@label='10']").get("link"), "https://netbox.example.com/vlan/10")


class DayOne(unittest.TestCase):
    def page_text(self, template, page_id):
        page = next(d for d in template.findall("diagram") if d.get("id") == page_id)
        return " ".join((e.get("value") or e.get("label") or "") for e in page.iter() if e.tag in ("mxCell", "object"))

    def test_a_sparse_site_marks_gaps_and_gets_a_plan(self):
        export = BigSites.make_site_module().grow("starter")
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-12")
        physical = self.page_text(template, "physical")
        for words in ("Plan to improve this page", "Devices without a serial number", "Names off the naming standard",
                      "Cables without a label", "Nothing in NetBox here yet", "IP <font"):
            self.assertIn(words, physical)
        self.assertIn("Not in NetBox yet", self.page_text(template, "logical"))
        self.assertNotIn("Plan to improve", self.page_text(template, "overview"))

    def test_a_complete_page_says_nothing_is_missing(self):
        template = sync.default_template()
        export = sample_export()
        for t in export["device_types"]:   # the sample's ProCurves are past end of support
            t["custom_fields"]["end_of_support"] = "2033-10-31"
        sync.fill(template, export, today="2026-10-12")
        self.assertIn("nothing missing in NetBox for this page", self.page_text(template, "hardware"))

    def test_no_plan_leaves_the_cards_out(self):
        template = sync.default_template()
        sync.fill(template, sample_export(), data_gaps=False)
        self.assertNotIn("Plan to improve", self.page_text(template, "physical"))


class EdgeCases(unittest.TestCase):
    """NetBox data that used to put a wrong fact on a page (plan items E1-E10, E13, E16, E17)."""

    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("edges")
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, cls.export, today="2026-10-12")
        cls.pages = {d.get("id"): Graph(d) for d in cls.template.findall("diagram")}

    def rows(self, page_id, first):
        g = self.pages[page_id]
        return [r for t in g.tables() if g.header(t)[:1] == [first] for r in table_rows_by_id(g, t)]

    def all_rows(self, first):
        return [r for page_id in self.pages for r in self.rows(page_id, first)]

    def shape(self, name):
        return next(o for o in self.template.iter("object") if o.get("name") == name and sync._is_device(o))

    def test_spares_are_listed_not_drawn(self):
        drawn = {o.get("name") for o in self.template.iter("object") if sync._is_device(o)}
        self.assertFalse({"S01-OOB-SW-01", "S01-OT-CORE-SPARE"} & drawn)
        self.assertNotIn("S01-OT-CORE-SPARE", self.report.slotted.values())
        registered = {r[0]: r for r in self.all_rows("HOSTNAME")}
        self.assertEqual(registered["S01-OT-CORE-SPARE"][2], "inventory")  # its own STATUS column
        self.assertIn("S01-OOB-SW-01", registered)

    def test_planned_is_dashed_and_offline_is_marked(self):
        planned = self.shape("S01-IT-ACC-IDF1-2")
        self.assertIn("dashed=1", planned.find("mxCell").get("style"))
        pills = {c.get("value") for c in self.template.iter("mxCell") if (c.get("id") or "").endswith("-status")}
        self.assertEqual(pills, {"Planned", "Offline"})
        self.assertIn("strokeColor=#D97706", self.shape("S01-SIS-SW01").find("mxCell").get("style"))

    def test_links_through_a_patch_panel_join_the_two_switches(self):
        self.assertNotIn("S01-PP-MDF-01", {o.get("name") for o in self.template.iter("object")})
        po101 = next(r for r in self.rows("physical", "LINK") if r[0] == "Po101")
        self.assertEqual(po101[2:4], ["IT-CORE Twe1/0/13 · Twe2/0/13", "IT-ACC-IDF1 Te1/1/1 · Te3/1/1"])
        line = next(o for o in self.template.iter("object") if "S01-CBL-018" in (o.get("cable_label") or ""))
        self.assertEqual((line.get("x_patch_a"), line.get("x_patch_b")), ("S01-PP-MDF-01:1", "S01-PP-MDF-01:R1"))
        self.assertNotIn("S01-CBL-018", self.report.missing_cables)

    def test_gateways_subnets_and_group_vlans(self):
        vlans = {r[0]: r for r in self.rows("logical", "VLAN")}
        self.assertEqual(vlans["110"][2:], ["10.1.10.0/24 · 2001:db8:110::/64", "HSRP .254 / IT-CORE-1 ::1 · CORP"])
        self.assertEqual(vlans["360"][1], "OT-HISTORIAN")
        self.assertEqual(vlans["120"][1], "CORP-VOICE")
        self.assertEqual(self.report.intake.shadowed_vlans, ["120 VOICE-GLOBAL (Region IT)"])

    def test_cable_labels_used_twice_are_both_kept(self):
        self.assertEqual(sorted(self.report.added_cables), ["1 (#95)", "1 (S01-WLC-01)", "S01-CBL-BRK"])
        self.assertEqual(self.report.intake.duplicate_labels, {"1": 2})
        physical = " ".join(c.get("value") or c.get("label") or "" for c in self.pages["physical"].els.values())
        self.assertIn("Cable labels used on more than one cable", physical)

    def test_a_breakout_lists_every_leg(self):
        row = next(r for r in self.rows("physical", "LINK") if r[0] == "CBL-BRK")
        self.assertEqual(row[3], "FW-EDGE-01 eth1/21+eth1/22+eth1/23+eth1/24")

    def test_unnamed_devices_are_named_and_reported(self):
        self.assertEqual(self.report.intake.unnamed, ["plc-73"])
        self.assertIn("plc-73", self.report.grouped["S01-C01-PLC01"])
        self.assertIn("Devices with no name in NetBox", self.report.markdown("Plant A"))

    def test_oob_address_fills_the_ip_tag(self):
        self.assertEqual(self.shape("S01-C01-IE01").get("oob_ip"), "10.1.99.77/24")
        texts = [c.get("value") or c.get("label") or "" for c in self.pages["physical"].els.values()]
        self.assertIn("OOB 10.1.99.77", texts)  # an out-of-band address is marked as one

    def test_ssid_table_from_wireless_lans(self):
        self.assertEqual(self.rows("wireless", "SSID")[0][:5],
                         ["PLANT-OT", "WPA Enterprise · AES", "S01-WLC-01", "350 · 10.101.50.0/24", "OT-OPS"])
        # The APs whose radios carry the SSID name their controller (cf wireless_controller), so the cell does too.

    def test_sheets_are_numbered_out_of_the_pages_in_the_file(self):
        total = len(self.template.findall("diagram"))
        sheets = [c.get("value") for c in self.template.iter("mxCell") if (c.get("value") or "").endswith(f" of {total}")]
        self.assertIn(f"1b of {total}", sheets)
        self.assertIn(f"3 of {total}", sheets)
        self.assertFalse([c for c in self.template.iter("mxCell") if (c.get("value") or "").endswith(" of 8")])
        self.assertFalse([c for c in self.template.iter("mxCell") if c.get("value") == "<b>LOGO</b>"])

    def test_title_says_when_the_data_is_from(self):
        g = self.pages["physical"]
        line = g.value(g.els["physical-provenance"])
        self.assertIn("NetBox data as of 2026-04-01", line)
        self.assertIn("built 2026-10-12", line)
        self.assertIn(f"Rev {self.report.provenance.revision}", line)
        self.assertIn("NetBox data as of: 2026-04-01", self.report.markdown("Plant A"))
        table = next(t for t in g.tables() if {"SITE", "DATE", "REV"} <= set(g.header(t)))
        cells = dict(zip(g.header(table), g.row_cells(g.rows(table)[1])))
        self.assertEqual(g.value(g.els[cells["DATE"]]), "2026-10-12")
        self.assertEqual(g.value(g.els[cells["REV"]]), self.report.provenance.revision)
        self.assertEqual(g.value(g.els[cells["SITE"]]), self.report.site_code)

    def test_draft_uses_the_same_tidy_data(self):
        site = build_site(self.export)
        names = {d.name for d in site.devices.values()}
        self.assertIn("plc-73", names)
        self.assertFalse({"S01-PP-MDF-01", "S01-OT-CORE-SPARE"} & names)


def own_slugs_export():
    """Plant A as a NetBox that names its roles its own way and has a fire-zone 'zone' field."""
    export = sample_export()
    renames = {"core-switch": "switch-core", "access-point": "wap", "industrial-switch": "ie-switch"}
    names = []
    for d in export["devices"]:
        role = d["role"]["slug"]
        if role in renames:
            d["role"] = {"name": renames[role].replace("-", " ").title(), "slug": renames[role]}
            names.append(d["name"])
        d.setdefault("custom_fields", {})["zone"] = "Fire zone 3"
    text = json.dumps(export)
    for name in names:  # named off the template too, so only the role can place them
        text = text.replace(f'"{name}"', f'"{name}X"')
    return json.loads(text)


MAPPING = {"roles": {"core-switch": "switch-core", "access-point": ["wap"], "industrial-switch": ["IE Switch"]}}


class Settings(unittest.TestCase):
    def test_sources_name_the_profile_they_pick(self):
        export = {"site": {"name": "Plant A", "custom_fields": {"netdiagrams": {"profile": "manufacturing"}}}}
        _, sources = settings.resolve(export, {"profile": "manufacturing"}, "netdiagrams.json")
        self.assertEqual(sources, ["defaults", "netdiagrams.json (profile manufacturing)",
                                   "netdiagrams field on site Plant A (profile manufacturing)"])
        _, sources = settings.resolve({"site": {}}, {"profile": "manufacturing"}, "--profile manufacturing")
        self.assertEqual(sources, ["defaults", "--profile manufacturing"])

    def test_later_sources_win_and_lists_merge(self):
        export = {"site": {"slug": "s01", "custom_fields": {"netdiagrams": json.dumps(
            {"naming": {"prefix": "S09-"}, "pages": "+wireless"})}},
            "regions": [{"name": "Plant", "custom_fields": {"netdiagrams": {"naming": {"prefix": "S08-"},
                                                                             "sw_field": "firmware"}}},
                        {"name": "EMEA", "custom_fields": {"netdiagrams": {"pages": "-multisite"}}}]}
        cfg, sources = settings.resolve(export, {"zone_field": "ot_area", "naming": {"prefix": "S07-"}})
        self.assertEqual(cfg["naming"]["prefix"], "S09-")
        self.assertEqual(cfg["zone_field"], ["ot_area"])
        self.assertEqual(cfg["sw_field"], ["firmware"])
        self.assertEqual(cfg["pages"], "-multisite +wireless")
        self.assertTrue(cfg["naming"]["pattern"])
        self.assertEqual(sources[1:], ["netdiagrams.json", "netdiagrams field on region EMEA",
                                       "netdiagrams field on region Plant", "netdiagrams field on site s01"])

    def test_unknown_or_broken_settings_are_errors(self):
        with self.assertRaises(settings.SettingsError):
            settings.resolve({"site": {"custom_fields": {"netdiagrams": "{not json"}}})
        with self.assertRaises(settings.SettingsError):
            settings.resolve({}, {"role": {}})

    def test_a_generic_zone_field_is_not_a_security_zone(self):
        export = intake.prepare({"devices": [{"id": 1, "name": "A", "custom_fields": {"zone": "Fire zone 3"}}]})
        self.assertEqual(ot.device_zones(export["devices"][0]), [])
        export = intake.prepare({"devices": [{"id": 1, "name": "A", "custom_fields": {"zone": "OT Ops"}}]},
                                {"zone_field": "zone"})
        self.assertEqual(ot.device_zones(export["devices"][0]), ["zone-ot-ops"])

    def test_own_role_slugs_need_the_mapping(self):
        report = sync.fill(sync.default_template(), own_slugs_export())
        self.assertGreater(len(report.netbox_only_devices), 10)

        template = sync.default_template()
        report = sync.fill(template, own_slugs_export(), settings=MAPPING)
        self.assertEqual(report.netbox_only_devices, [])
        self.assertEqual(len(report.matched_devices), 70)
        self.assertEqual(report.intake.roles_mapped,
                         {"switch-core": "core-switch", "wap": "access-point", "ie-switch": "industrial-switch"})
        self.assertEqual(report.slotted["S01-OT-CORE-1"], "S01-OT-CORE-1X")
        core = next(o for o in template.iter("object") if o.get("name") == "S01-OT-CORE-1X")
        self.assertEqual((core.get("role"), core.get("netbox_role")), ("core-switch", "switch-core"))
        self.assertIn("wireless", [d.get("id") for d in template.findall("diagram")])
        self.assertIn("switch-core → core-switch", report.markdown("Plant A"))

    def test_mapping_in_the_site_field(self):
        export = own_slugs_export()
        export["site"]["custom_fields"] = {"netdiagrams": json.dumps(MAPPING)}
        report = sync.fill(sync.default_template(), export)
        self.assertEqual(report.netbox_only_devices, [])
        self.assertIn("netdiagrams field on site", report.markdown("Plant A"))

    def test_own_field_names_software_gateway_and_naming(self):
        export = sample_export()
        core = next(d for d in export["devices"] if d["name"] == "S01-IT-CORE-1")
        core["custom_fields"] = {"os_version": "IOS-XE 17.15.1"}
        prefix = next(p for p in export["prefixes"] if p["prefix"] == "10.1.10.0/24")
        prefix["custom_fields"] = {"gw": "10.1.10.254 (HSRP)"}
        export["devices"][0]["name"] = "plant-a-fw-edge"
        template = sync.default_template()
        sync.fill(template, export, settings={"sw_field": "os_version", "gateway_field": "gw",
                                              "naming": {"pattern": "^(S01-|plant-a-)"}}, today="2026-10-12")
        rows = {}
        for d in template.findall("diagram"):
            g = Graph(d)
            for t in g.tables():
                for r in table_rows_by_id(g, t):
                    rows.setdefault(r[0], r)
        self.assertEqual(rows["S01-IT-CORE-1"][-2:], ["IOS-XE 17.15.1", "2033-10-31"])  # SW, then EOS from the model
        self.assertEqual(rows["110"][3], "10.1.10.254 (HSRP) · CORP")
        physical = " ".join(e.get("value") or e.get("label") or "" for d in template.findall("diagram")
                            if d.get("id") == "physical" for e in d.iter())
        self.assertNotIn("Names off the naming standard", physical)

    def test_end_of_support_dates_are_a_gap(self):
        export = sample_export()
        export["devices"][0]["custom_fields"] = {"eos_date": "2025-01-31"}
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-12")
        hardware = next(d for d in template.findall("diagram") if d.get("id") == "hardware")
        self.assertIn("Devices past end of support",
                      " ".join(e.get("value") or e.get("label") or "" for e in hardware.iter()))

    def test_netbox_setup_follows_the_mapping(self):
        template = sync.default_template()
        cfg = settings.merge(settings.DEFAULTS, {**MAPPING, "level_field": "ot_level"})
        files = netbox_setup.setup_files(template, settings=cfg)
        self.assertNotIn("core-switch", files["4-device-roles.csv"])
        self.assertIn("firewall", files["4-device-roles.csv"])
        self.assertIn("netdiagrams,NetDiagrams settings", files["2-custom-fields.csv"])
        self.assertNotIn("purdue_level", files["2-custom-fields.csv"])


class Doctor(unittest.TestCase):
    def test_doctor_proposes_a_role_map_and_names_next_steps(self):
        text, proposed = doctor.check(own_slugs_export(), sync.default_template())
        self.assertEqual(proposed["roles"], {"core-switch": ["switch-core"], "access-point": ["wap"],
                                             "industrial-switch": ["ie-switch"]})
        for words in ("Site prefix: S01- (shared by 70 of 70", "not a template role: goes to the tray",
                      "Read from: field security_zone, iec62443_zone, ot_zone on 0 devices, zone-* tags on 70",
                      "Next three things to fix", "save this as netdiagrams.json"):
            self.assertIn(words, text)

    def test_doctor_with_the_mapping_has_nothing_to_propose(self):
        text, proposed = doctor.check(own_slugs_export(), sync.default_template(), MAPPING)
        self.assertEqual(proposed, {})
        self.assertIn("mapped from switch-core", text)

    def test_doctor_lists_data_that_needs_care(self):
        text, _ = doctor.check(BigSites.make_site_module().grow("edges"), sync.default_template())
        for words in ("Spares and devices being taken out (listed, not drawn): 2", "Patch panels",
                      "Cable labels used more than once: 1 · 1 ×2", "NetBox data as of 2026-04-01"):
            self.assertIn(words, text)

    def test_doctor_command_saves_the_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "site.json"
            src.write_text(json.dumps(own_slugs_export()))
            out = Path(tmp) / "netdiagrams.json"
            with mock.patch("os.getcwd", return_value=tmp), redirect_stdout(io.StringIO()) as printed:
                code = cli.main(["doctor", "--input", str(src), "--save-settings", str(out)])
            self.assertEqual(code, 0)
            self.assertIn("template role", printed.getvalue())
            saved = json.loads(out.read_text())
            self.assertEqual(saved["roles"]["core-switch"], ["switch-core"])
            # The saved file is picked up by the next build in that folder.
            with mock.patch("os.getcwd", return_value=tmp), redirect_stdout(io.StringIO()) as printed:
                code = cli.main(["build", "--input", str(src), "-o", str(Path(tmp) / "s01.drawio")])
            self.assertEqual(code, 0)
            self.assertNotIn("wait in the tray", printed.getvalue())


class DesignFixes(unittest.TestCase):
    """Design critique round 2: paper size, red only for denied, chapter notes, no LOGO box."""

    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, sample_export(), today="2026-10-12")

    def note(self, page_id):
        diagram = next(d for d in self.template.findall("diagram") if d.get("id") == page_id)
        return next(o for o in diagram.iter("object") if o.get("id") == f"{page_id}-book-note")

    def test_each_sheet_names_the_chapter_that_explains_it(self):
        physical = self.note("physical")
        self.assertIn("How to draw this page: <b>Chapter 5,", physical.get("label"))
        self.assertEqual(physical.get("link"), sync.BOOK_URL)
        self.assertIn("/free/", self.note("register").get("link"))
        template = sync.default_template()
        sync.fill(template, sample_export(), today="2026-10-12", book_note=False)
        self.assertFalse([o for o in template.iter("object") if (o.get("id") or "").endswith("-book-note")])

    def test_drift_report_ends_with_the_upkeep_chapter(self):
        last = self.report.markdown("Plant A").rstrip().splitlines()[-1]
        self.assertTrue(last.startswith("Fixing these for good? Chapter 13"))
        self.assertIn(sync.BOOK_URL, last)

    def test_logo_box_is_blank_or_the_logo_from_settings(self):
        logos = [c for c in self.template.iter("mxCell") if "fillColor=none;strokeColor=none;" in (c.get("style") or "")
                 and (c.get("value") or "") == ""]
        self.assertTrue(logos)
        with tempfile.TemporaryDirectory() as tmp:
            logo = Path(tmp) / "logo.png"
            logo.write_bytes(b"\x89PNG\r\n\x1a\n")
            template = sync.default_template()
            sync.fill(template, sample_export(), settings={"logo": str(logo)}, today="2026-10-12")
        self.assertTrue([c for c in template.iter("mxCell") if "image=data:image/png," in (c.get("style") or "")])
        sample = sync.finish_sample(sync.default_template())
        self.assertFalse([c for c in sample.iter("mxCell") if c.get("value") == "<b>LOGO</b>"])

    def test_firewalls_are_slate_and_red_means_denied(self):
        firewall = ET.tostring(stencils.library()["Firewall (asset)"]["root"], "unicode")
        self.assertNotIn("#DC2626", firewall.upper())
        text = resources.files("netdiagrams").joinpath("data", "S01-Network-Architecture-Template.drawio").read_text()
        reds = [m for m in re.finditer(r'<mxCell id="([^"]+)" value="([^"]*)" style="([^"]*Color=#DC2626[^"]*)"', text)]
        for m in reds:
            self.assertRegex(m.group(1) + " " + m.group(2) + " " + m.group(3),
                             r"✕|deny|denied|no route|D\d|SIS|End of support|endArrow|failover|Internet|hosts|CORE|PA-450",
                             m.group(1))

    def test_every_sheet_prints_on_iso_paper_at_full_size(self):
        self.assertEqual(paper.paper_for(2000, 1180)[0], "A2")
        self.assertEqual(paper.paper_for(2400, 1460)[0], "A1")
        self.assertEqual(paper.paper_for(2880, 2400)[0], "A0")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plant.drawio"
            sync.write(self.template, out)
            sizes = {(m.get("pageWidth"), m.get("pageHeight")) for m in ET.parse(out).getroot().iter("mxGraphModel")}
        self.assertTrue(sizes <= {(str(w), str(h)) for _, w, h in paper.SIZES}, sizes)


class PageSelection(unittest.TestCase):
    def ids(self, template):
        return [d.get("id") for d in template.findall("diagram")]

    def no_wireless(self):
        export = sample_export()
        export["devices"] = [d for d in export["devices"]
                             if d["role"]["slug"] not in ("access-point", "wireless-controller", "ptp-radio",
                                                          "workgroup-bridge")]
        return export

    def test_a_site_without_wireless_gear_gets_no_wireless_page(self):
        template = sync.default_template()
        report = sync.fill(template, self.no_wireless())
        self.assertNotIn("wireless", self.ids(template))
        self.assertIn("no access points", report.skipped_pages[0][1])
        self.assertIn("Pages left out", report.markdown("Plant A"))

    def test_groups_page_ids_and_sheet_numbers_leave_pages_out(self):
        template = sync.default_template()
        sync.fill(template, sample_export(), pages="-failover, -reference +3c -3b")
        ids = self.ids(template)
        for page in ("failover", "netbox", "hardware"):
            self.assertNotIn(page, ids)
        self.assertIn("platforms", ids)

    def test_the_site_field_wins_over_the_default(self):
        export = self.no_wireless()
        export["site"]["custom_fields"] = {"netdiagrams_pages": "+wireless, -multisite"}
        template = sync.default_template()
        sync.fill(template, export, pages="-wireless")
        self.assertIn("wireless", self.ids(template))
        self.assertNotIn("multisite", self.ids(template))

    def test_an_unknown_page_name_is_an_error(self):
        with self.assertRaises(ValueError):
            sync.fill(sync.default_template(), sample_export(), pages="-wifi")


class Interactive(unittest.TestCase):
    def actions(self, link):
        self.assertTrue(link.startswith("data:action/json,"))
        return json.loads(link[len("data:action/json,"):])["actions"]

    def test_every_button_switches_layers_that_exist(self):
        template = sync.default_template()
        sync.fill(template, sample_export())
        physical = next(d for d in template.findall("diagram") if d.get("id") == "physical")
        layers = {c.get("id") for c in physical.iter("mxCell") if c.get("parent") == "0"}
        buttons = {o.get("label"): o.get("link") for o in physical.iter("object")
                   if o.get("id", "").startswith("physical-controls-")}
        self.assertIn("Print view", buttons)
        self.assertIn("Mgmt IPs", buttons)
        for label, link in buttons.items():
            for action in self.actions(link):
                for ids in action.values():
                    self.assertLessEqual(set(ids["cells"]), layers, label)
        print_view = self.actions(buttons["Print view"])[0]["hide"]["cells"]
        self.assertIn("physical-controls", print_view)

    def test_schedule_rows_reveal_a_hidden_copy_of_the_typical(self):
        export = BigSites.make_site_module().grow("medium")
        template = sync.default_template()
        sync.fill(template, export)
        physical = next(d for d in template.findall("diagram") if d.get("id") == "physical")
        copies = {c.get("id"): c for c in physical.iter("mxCell")
                  if c.get("parent") == "0" and (c.get("value") or "").startswith("Copy of the typical")}
        self.assertIn("physical-copy-zone-cell05", copies)
        self.assertTrue(all(c.get("visible") == "0" for c in copies.values()))
        row = next(o for o in physical.iter("object") if o.get("label") == "CELL05 ›")
        show = [a["show"]["cells"] for a in self.actions(row.get("link")) if "show" in a]
        self.assertEqual(show, [["physical-copy-zone-cell05"]])
        names = {o.get("name") for o in physical.iter("object") if o.get("id", "").startswith("physical-copy-zone-cell05")}
        self.assertIn("S01-C05-IE01", names)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        with redirect_stdout(io.StringIO()) as out:
            code = cli.main(list(args))
        return code, out.getvalue()

    def test_sample_blank_and_stencils_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for cmd, name in (("sample", "s.drawio"), ("blank", "b.drawio"), ("stencils", "lib.xml"),
                              ("draft", "d.drawio")):
                if cmd == "draft":
                    src = Path(tmp) / "e.json"
                    src.write_text(json.dumps(sample_export()))
                    code, _ = self.run_cli(cmd, "--input", str(src), "-o", str(Path(tmp) / name))
                    self.assertEqual(code, 0)
                    continue
                code, _ = self.run_cli(cmd, "-o", str(Path(tmp) / name))
                self.assertEqual(code, 0)
                ET.parse(Path(tmp) / name)

    def test_blank_has_no_devices(self):
        xml = drawio.render(drawio.blank_site())
        self.assertFalse([o for o in xml.iter("object") if o.get("role")])

    def test_build_from_export_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "export.json"
            src.write_text(json.dumps(sample_export()))
            code, out = self.run_cli("build", "--input", str(src), "-o", str(Path(tmp) / "o.drawio"))
            self.assertEqual(code, 0)
            self.assertIn("70 devices placed", out)
            self.assertTrue((Path(tmp) / "o.drift.md").exists())
            self.assertEqual(len(ET.parse(Path(tmp) / "o.drawio").getroot().findall("diagram")), 13)

    def test_bare_command_builds_every_site_from_the_saved_login(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.json"
            config.write_text(json.dumps({"url": "https://nb.example.com", "token": "t"}))
            export = sample_export()
            with mock.patch.object(cli, "CONFIG", config), mock.patch.dict("os.environ", {}, clear=True), \
                    mock.patch.object(NetBoxClient, "sites", return_value=[{"slug": "s01", "device_count": 70}]), \
                    mock.patch.object(NetBoxClient, "export_site", return_value=export), \
                    mock.patch("os.getcwd", return_value=tmp):
                code, out = self.run_cli("-o", str(Path(tmp) / "s01.drawio"))
            self.assertEqual(code, 0, out)
            self.assertTrue((Path(tmp) / "s01.drawio").exists())

    def test_build_without_netbox_details_explains(self):
        with mock.patch.dict("os.environ", {}, clear=True), redirect_stdout(io.StringIO()), \
                mock.patch.object(cli, "CONFIG", Path("/nonexistent/netdiagrams.json")):
            with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                code = cli.main(["build", "--site", "s01"])
        self.assertEqual(code, 2)
        self.assertIn("NETBOX_TOKEN", err.getvalue())


class OtStructure(unittest.TestCase):
    LOCATIONS = [
        {"id": 1, "name": "Building 1", "slug": "b1", "parent": None},
        {"id": 2, "name": "Hall A", "slug": "hall-a", "parent": {"id": 1},
         "custom_fields": {"purdue_level": {"value": "L2", "label": "Level 2"}}},
        {"id": 3, "name": "Cell 04", "slug": "cell-04", "parent": {"id": 2}},
        {"id": 4, "name": "Safety", "slug": "safety", "parent": {"id": 1}, "tags": [{"slug": "zone-sis"}]},
    ]

    def test_zone_from_custom_field_tag_or_location(self):
        locs = ot.Locations(self.LOCATIONS)
        self.assertEqual(ot.device_zones({"custom_fields": {"security_zone": "OT Ops"}}), ["zone-ot-ops"])
        self.assertEqual(ot.device_zones({"tags": [{"slug": "zone-idmz"}]}), ["zone-idmz"])
        self.assertEqual(ot.device_zones({"location": {"id": 3}}, locs), ["zone-cell04"])
        self.assertEqual(ot.device_zones({"location": {"id": 4}}, locs), ["zone-sis"])
        self.assertEqual(locs.path({"id": 3}), "Building 1 › Hall A › Cell 04")

    def test_purdue_level_from_device_or_location(self):
        locs = ot.Locations(self.LOCATIONS)
        for raw, level in (("3", "L3"), ("Level 3.5", "L3.5"), ("L4", "L4"), ("L1", "L2–0"), ("level-3-5", "L3.5")):
            self.assertEqual(ot.normalize_level(raw), level, raw)
        self.assertEqual(ot.device_level({"location": {"id": 3}}, [], locs), "L2–0")
        self.assertEqual(ot.device_level({}, ["zone-it-ent"]), "L4")

    def test_vlan_zone_from_vrf_when_untagged(self):
        self.assertEqual(ot.vlan_zone({"vid": 10}, [{"vrf": {"name": "OT-OPS"}}]), "zone-ot-ops")
        self.assertEqual(ot.vlan_zone({"vid": 10, "group": {"slug": "zone-cell01"}}), "zone-cell01")
        self.assertEqual(ot.vlan_zone({"vid": 10}, [{"vrf": {"name": "Mgmt-Customer-X"}}]), "")

    def test_draft_places_location_zoned_devices_in_their_purdue_band(self):
        export = small_site_export()
        export["locations"] = self.LOCATIONS
        for d in export["devices"][:1]:
            d["tags"] = []
            d["location"] = {"id": 3, "name": "Cell 04"}
        site = build_site(export)
        self.assertIn("zone-cell04", site.zones)
        self.assertEqual(site.zones["zone-cell04"].band[0], "L2–0")

    def test_gateway_only_counts_addresses_in_the_prefix_vrf(self):
        nb = sync.NetBoxIndex({"ip_addresses": [
            {"address": "10.0.0.1/24", "vrf": {"id": 1}, "assigned_object": {"device": {"name": "S01-A"}}},
            {"address": "10.0.0.254/24", "vrf": {"id": 2}, "assigned_object": {"device": {"name": "S01-B"}}},
        ]})
        self.assertEqual(sync._gateway("10.0.0.0/24", nb, 2), "B .254")

    def test_netbox_setup_files_cover_the_template_and_skip_what_exists(self):
        template = sync.default_template()
        files = netbox_setup.setup_files(template)
        self.assertEqual(sorted(files), ["1-custom-field-choice-sets.csv", "2-custom-fields.csv",
                                         "3-zone-tags.csv", "4-device-roles.csv", "5-inventory-item-roles.csv",
                                         "6-contact-roles.csv"])
        self.assertIn("zone-cell01", files["3-zone-tags.csv"])
        self.assertIn("purdue_level", files["2-custom-fields.csv"])
        import csv
        for row in csv.DictReader(io.StringIO(files["1-custom-field-choice-sets.csv"])):
            self.assertTrue(all(":" in c for c in row["extra_choices"].split(",")))
        roles = {r["slug"] for r in csv.DictReader(io.StringIO(files["4-device-roles.csv"]))}
        less = netbox_setup.setup_files(template, {"roles": roles, "tags": set(), "custom_fields": set(), "item_roles": set(),
                                                   "choice_sets": {"Purdue level", "IEC 62443 security level",
                                                                   "Asset criticality", *wireless.CHOICE_SETS,
                                                                   *audit.CHOICE_SETS}})
        self.assertNotIn("4-device-roles.csv", less)
        self.assertNotIn("1-custom-field-choice-sets.csv", less)


class Client(unittest.TestCase):
    def test_token_schemes(self):
        self.assertTrue(NetBoxClient("https://nb", "abc")._headers()["Authorization"].startswith("Token "))
        self.assertTrue(NetBoxClient("https://nb", "nbt_x.y")._headers()["Authorization"].startswith("Bearer "))

    def test_export_follows_pagination_and_only_reads(self):
        client = NetBoxClient("https://nb.example.com/", "t")
        pages = {
            "https://nb.example.com/api/status/": {"netbox-version": "4.4.1"},
        }
        seen = []

        def fake_get(url):
            seen.append(url)
            if url in pages:
                return pages[url]
            if "dcim/sites" in url:
                return {"results": [{"slug": "s01", "name": "Plant A"}], "next": None}
            if "dcim/devices" in url and "offset" not in url:
                return {"results": [{"id": 1}], "next": url + "&offset=1"}
            if "dcim/devices" in url:
                return {"results": [{"id": 2}], "next": None}
            return {"results": [], "next": None}

        with mock.patch.object(client, "get", side_effect=fake_get):
            data = client.export_site("s01")
        self.assertEqual([d["id"] for d in data["devices"]], [1, 2])
        self.assertEqual(data["netbox_url"], "https://nb.example.com")
        self.assertTrue(all("site=s01" in u or "device_id=" in u or "object_id=" in u
                            for u in seen if "/status/" not in u and "dcim/sites" not in u))

    def test_export_reads_group_vlans_their_prefixes_and_fhrp_gateways(self):
        client = NetBoxClient("https://nb.example.com/", "t")
        seen = []

        def fake_get(url):
            seen.append(url)
            if "/status/" in url:
                return {"netbox-version": "4.4.1"}
            if "dcim/sites" in url:
                return {"results": [{"id": 3, "slug": "s01", "name": "Plant A"}], "next": None}
            if "ipam/vlans" in url and "available_at_site=3" in url:
                return {"results": [{"id": 70, "vid": 360, "group": {"slug": "region-ot"}}], "next": None}
            if "ipam/prefixes" in url and "vlan_id=70" in url:
                return {"results": [{"id": 5, "prefix": "10.101.60.0/24", "vlan": {"id": 70}}], "next": None}
            if "ipam/ip-addresses" in url and "parent=" in url:
                return {"results": [{"id": 9, "address": "10.101.60.254/24", "role": {"value": "vrrp"}}],
                        "next": None}
            return {"results": [], "next": None}

        with mock.patch.object(client, "get", side_effect=fake_get):
            data = client.export_site("s01")
        self.assertEqual([v["vid"] for v in data["vlans"]], [360])
        self.assertEqual([p["prefix"] for p in data["prefixes"]], ["10.101.60.0/24"])
        self.assertEqual([i["address"] for i in data["ip_addresses"]], ["10.101.60.254/24"])
        self.assertTrue(data["exported_at"])
        fhrp = next(u for u in seen if "parent=" in u)
        self.assertIn("role=hsrp", fhrp)


class Share(unittest.TestCase):
    """netdiagrams share: a copy for a vendor, an auditor or management, checked for leaks."""

    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("edges")
        cls.built = sync.default_template()
        sync.fill(cls.built, cls.export, today="2026-10-12")

    def copy(self, audience, **kw):
        import copy
        mxfile = copy.deepcopy(self.built)
        return mxfile, share.share(mxfile, audience=audience, **kw)

    @staticmethod
    def text(mxfile):
        return " ".join((e.get("value") or e.get("label") or "") + " " + (e.get("tooltip") or "")
                        for e in mxfile.iter())

    def test_built_file_has_no_unresolved_placeholders_or_empty_badges(self):
        for o in self.built.iter("object"):
            if o.get("placeholders") == "1":
                # draw.io reads a key from the shape, else from the shape it sits in (a rack pill
                # inside its device card), so every key must resolve on one or the other.
                g = next(sync.Graph(d) for d in self.built.findall("diagram") if o in d.iter("object"))
                for key in re.findall(r"%(\w+)%", o.get("label") or ""):
                    self.assertIsNotNone(sync._inherited(g, o, key), o.get("id"))
                self.assertNotIn("%rack% · U%position%", o.get("label")) \
                    if not sync._inherited(g, o, "rack") else None

    def test_every_shared_copy_prints_no_literal_placeholder(self):
        for audience in share.AUDIENCES:
            mxfile, _ = self.copy(audience)
            literal = [(e.get("id"), e.get("value") or e.get("label")) for e in mxfile.iter()
                       if re.search(r"%\w+%", e.get("value") or e.get("label") or "")]
            self.assertFalse(literal, audience)
            # rack pills inside device cards keep saying where the device is
            self.assertIn("R01 · U", self.text(mxfile), audience) if audience != "management" else None

    def test_vendor_copy_carries_no_secrets(self):
        known = share.secrets(self.built)
        self.assertTrue(any(kind == "serial" for kind in known.values()))
        self.assertTrue(any(kind == "IP address" for kind in known.values()))
        mxfile, report = self.copy("vendor")
        self.assertEqual(report.leaks, [])
        text = self.text(mxfile)
        for secret in known:
            self.assertNotIn(secret, text, secret)
        self.assertFalse(share.IPV4.search(re.sub(r"<[^>]+>", " ", text)))
        attrs = {k for o in mxfile.iter("object") for k in o.attrib}
        self.assertLessEqual(attrs, {"id", "label"})
        ids = {d.get("id") for d in mxfile.findall("diagram")}
        self.assertTrue({"overview", "glance", "logical", "physical", "register"} <= ids)
        self.assertFalse({"flows", "failover", "multisite", "platforms", "netbox"} & ids)
        physical = Graph(next(d for d in mxfile.findall("diagram") if d.get("id") == "physical"))
        self.assertFalse([n for n in physical.layers.values() if "hide before sharing" in n or "Controls" in n
                          or n.startswith(("Guides", "Plan to improve", "How to draw"))])
        self.assertIn("7 · Asset register", physical.layers.values())
        self.assertIn("shared copy for a vendor", text)
        self.assertNotIn("every row linked to NetBox", text)
        self.assertNotIn("Edit Data", text)
        self.assertNotIn("netbox.example.com", text)

    def test_vendor_register_keeps_rows_but_blanks_serial_and_ip_columns(self):
        mxfile, _ = self.copy("vendor")
        for d in mxfile.findall("diagram"):
            g = Graph(d)
            for t in g.tables():
                header = g.header(t)
                if "SERIAL" in header:
                    rows = g.rows(t)[1:]
                    self.assertGreater(len(rows), 10)
                    for row in rows:
                        cells = g.row_cells(row)
                        self.assertTrue(g.value(g.els[cells[0]]))
                        for col in ("SERIAL", "MGMT IP"):
                            if col in header:
                                self.assertEqual(g.value(g.els[cells[header.index(col)]]), "")

    def test_auditor_copy_keeps_evidence_and_links(self):
        mxfile, report = self.copy("auditor")
        text = self.text(mxfile)
        self.assertTrue(share.IPV4.search(text))
        self.assertTrue([o for o in mxfile.iter("object") if o.get("link", "").startswith("https://netbox.example.com")])
        physical = Graph(next(d for d in mxfile.findall("diagram") if d.get("id") == "physical"))
        self.assertIn("3 · Mgmt IPs (hide before sharing)", physical.layers.values())
        self.assertIn("Plan to improve (data gaps)", physical.layers.values())
        self.assertFalse([n for n in physical.layers.values() if n.startswith(("Guides", "How to draw"))])
        self.assertTrue([n for n in physical.layers.values() if n.startswith("Controls")])
        self.assertIn("shared copy for an auditor", text)
        self.assertNotIn("flows", {d.get("id") for d in mxfile.findall("diagram")})
        self.assertIn("Kept on purpose", "\n".join(report.lines()))

    def test_management_copy_is_the_two_overview_sheets(self):
        mxfile, report = self.copy("management")
        self.assertEqual([d.get("id") for d in mxfile.findall("diagram")], ["overview", "glance"])
        self.assertEqual(report.leaks, [])
        self.assertIn("1b of 2", self.text(mxfile))
        self.assertIn("shared copy for management", self.text(mxfile))

    def test_keep_examples_keeps_the_watermarked_sheets(self):
        mxfile, _ = self.copy("auditor", keep_examples=True)
        self.assertIn("flows", {d.get("id") for d in mxfile.findall("diagram")})

    def test_cli_refuses_a_leaking_copy_unless_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "site.drawio"
            import copy
            leaky = copy.deepcopy(self.built)
            glance = next(d for d in leaky.findall("diagram") if d.get("id") == "glance")
            root = glance.find("mxGraphModel/root")
            layer = next(c.get("id") for c in root if c.get("parent") == "0" and c.get("value") == "Zones")
            cell = ET.SubElement(root, "mxCell", {"id": "leak", "value": "mgmt 10.9.9.9 on <b>FOCxxxxx11</b>",
                                                  "vertex": "1", "parent": layer, "style": "text;"})
            ET.SubElement(cell, "mxGeometry", {"x": "10", "y": "10", "width": "100", "height": "20", "as": "geometry"})
            sync.write(leaky, src)
            out = Path(tmp) / "vendor.drawio"
            with redirect_stdout(io.StringIO()) as log:
                # redaction blanks both the IP and the serial, so this copy is clean
                self.assertEqual(cli.main(["share", str(src), "-o", str(out)]), 0)
            self.assertIn("Checked: no IP", log.getvalue())
            self.assertIn("[hidden]", out.read_text("utf-8"))
            # a secret redaction misses is refused
            with mock.patch.object(share, "_redact", side_effect=lambda text, known: (text, 0)):
                with redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        cli.main(["share", str(src), "-o", str(out)])
                    self.assertEqual(cli.main(["share", str(src), "-o", str(out), "--allow-leaks"]), 0)

    def test_report_counts_sheets_in_the_singular_too(self):
        one = share.ShareReport("management")
        one.pages_kept = ["1 · Overview"]
        self.assertTrue(one.lines()[0].startswith("Shared copy for management: 1 sheet kept"))
        self.assertIn("2 sheets kept", self.copy("management")[1].lines()[0])

    def test_default_output_name_and_bad_audience(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "plant.drawio"
            sync.write(sync.finish_sample(sync.default_template()), src)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["share", str(src), "--audience", "management"]), 0)
            self.assertTrue((Path(tmp) / "plant-management.drawio").exists())
        with self.assertRaises(ValueError):
            share.share(ET.Element("mxfile"), audience="press")


class FakeNetBox:
    """A NetBox that answers inventory reads and records creates."""
    base = "https://netbox.example.com/api"

    def __init__(self, have=None, version="4.2.5", refuse=()):
        self.have = have or {}
        self.created, self.refuse, self._version = [], set(refuse), version

    def version(self):
        return self._version

    def list(self, endpoint, **params):
        objects = list(self.have.get(endpoint, []))
        if "name" in params:
            objects = [o for o in objects if o.get("name") == params["name"]]
        return objects

    def post(self, endpoint, payload):
        if payload.get("name") in self.refuse:
            from netdiagrams.netbox import NetBoxError
            raise NetBoxError("NetBox returned 403 creating " + endpoint)
        created = {"id": 100 + len(self.created), **payload}
        self.created.append((endpoint, payload))
        self.have.setdefault(endpoint, []).append(created)
        return created


class NetBoxSetupApply(unittest.TestCase):
    def setUp(self):
        self.template = sync.default_template()
        self.files = netbox_setup.setup_files(self.template)

    def test_plan_follows_the_netbox_version(self):
        new = netbox_setup.plan(self.files, "4.2.5")
        kinds = [s.kind for s in new]
        self.assertEqual(kinds, sorted(kinds, key=["choice_sets", "custom_fields", "tags", "roles", "item_roles",
                                                         "contact_roles"].index))
        field = next(s for s in new if s.label == "custom field purdue_level")
        self.assertEqual(field.payload["choice_set"], {"name": "Purdue level"})
        self.assertIn("dcim.location", field.payload["object_types"])
        self.assertFalse(field.payload["required"])
        old = netbox_setup.plan(self.files, "3.5.2")
        self.assertFalse([s for s in old if s.kind == "choice_sets"])
        field = next(s for s in old if s.label == "custom field purdue_level")
        self.assertIn("content_types", field.payload)
        self.assertEqual(field.payload["choices"][:2], ["L5", "L4"])
        tag = next(s for s in old if s.kind == "tags")
        self.assertNotIn("object_types", tag.payload)

    def test_apply_creates_only_what_is_missing_and_never_updates(self):
        nb = FakeNetBox({"dcim/device-roles": [{"id": 1, "slug": "firewall", "name": "FW", "color": "000000"}]})
        steps = netbox_setup.plan(self.files, nb.version())
        results = netbox_setup.apply(nb, steps, netbox_setup.inventory(nb))
        outcomes = dict(results)
        self.assertEqual(outcomes["device role firewall"], "already there, left as is")
        self.assertEqual(outcomes["custom field purdue_level"], "created")
        self.assertEqual(len([e for e, _ in nb.created if e == "extras/custom-field-choice-sets"]),
                         3 + len(wireless.CHOICE_SETS) + len(audit.CHOICE_SETS))   # Purdue, SL, criticality, wireless, audit
        field = next(p for e, p in nb.created if p.get("name") == "purdue_level")
        self.assertIsInstance(field["choice_set"], int)  # resolved to the set created a moment earlier
        self.assertEqual(len(nb.created), len(steps) - 1)
        self.assertFalse([e for e, p in nb.created if e == "dcim/device-roles" and p.get("slug") == "firewall"])

    def test_apply_reports_a_refusal_and_carries_on(self):
        nb = FakeNetBox(refuse={"Purdue level"})
        results = netbox_setup.apply(nb, netbox_setup.plan(self.files, "4.2.5"), netbox_setup.inventory(nb))
        outcomes = dict(results)
        self.assertTrue(outcomes["choice set Purdue level"].startswith("failed"))
        self.assertTrue(outcomes["custom field purdue_level"].startswith("skipped"))
        self.assertEqual(outcomes["tag zone-cell01"], "created")

    def test_check_tells_present_missing_and_short_of_a_type(self):
        have = {"custom_fields": {"purdue_level": {"object_types": ["dcim.device"]}},
                "tags": {"zone-cell01": {"object_types": ["dcim.device", "dcim.location", "ipam.vlan",
                                                           "ipam.prefix", "ipam.vrf"]}},
                "roles": {}, "choice_sets": {}}
        rows = dict(((k, n), s) for k, n, s in netbox_setup.check(self.template, have))
        self.assertEqual(rows[("tags", "zone-cell01")], "present")
        self.assertEqual(rows[("custom_fields", "purdue_level")], "present, but not on dcim.location, ipam.prefix, ipam.vlan")
        self.assertEqual(rows[("roles", "firewall")], "missing")
        text = "\n".join(netbox_setup.check_lines(netbox_setup.check(self.template, have)))
        self.assertIn("1 present but short of an object type", text)
        self.assertIn("--apply", text)

    def test_cli_check_and_apply(self):
        nb = FakeNetBox()
        with mock.patch.object(cli, "_client", return_value=nb):
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(["netbox-setup", "--check"]), 0)
            self.assertIn("missing", out.getvalue())
            self.assertEqual(nb.created, [])
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(["netbox-setup", "--apply"]), 0)
            self.assertIn("created.", out.getvalue())
            self.assertTrue(nb.created)
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(["netbox-setup", "--apply"]), 0)
            self.assertIn("Nothing to create", out.getvalue())


class GapFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("edges")
        locations = ot.Locations(cls.export.get("locations"))
        cls.found = gaps.find(cls.export, sync.ENDPOINT_ROLES, lambda d: ot.device_zones(d, locations), "2026-10-12")
        cls.files = worksheets.files(cls.export, cls.found)

    def test_rows_carry_ids_and_current_values_for_flagged_objects_only(self):
        import csv
        devices = list(csv.DictReader(io.StringIO(self.files["1-devices.csv"])))
        self.assertTrue(devices)
        by_id = {str(d["id"]): d for d in self.export["devices"]}
        flagged = set(self.found["no_serial"].names) | set(self.found["no_location"].names)
        for row in devices:
            source = by_id[row["id"]]
            self.assertEqual(row["name"], source["name"])
            self.assertEqual(row["serial"], source.get("serial") or "")
            self.assertEqual(row["tags"], ",".join(t["slug"] for t in source.get("tags") or []))
        names = {row["name"] for row in devices}
        self.assertTrue(flagged <= names)
        self.assertLess(len(names), len(by_id))
        for name, text in self.files.items():
            header = text.splitlines()[0]
            self.assertTrue(header.startswith("id,") or "-new-" in name, name)

    def test_cli_writes_the_folder_with_a_guide(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "e.json"
            src.write_text(json.dumps(self.export))
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(["gaps", "--input", str(src), "-o", str(Path(tmp) / "g")]), 0)
            self.assertIn("import files", out.getvalue())
            written = sorted(p.name for p in (Path(tmp) / "g").iterdir())
            self.assertIn("README.txt", written)
            self.assertIn("1-devices.csv", written)


class RenderGate(unittest.TestCase):
    """The definition of done, run over every fixture: deterministic, complete, traceable, no residue, no overflow."""

    FIXTURES = ("starter", "edges", "medium")
    # Other industries' samples, built to their own standard: (fixture, profile, bundled export).
    PROFILE_FIXTURES = (("warehouse-w01", "warehouse", "sample-warehouse-w01.json"),
                        ("warehouse-w02", "warehouse", "sample-warehouse-w02.json"))

    @classmethod
    def setUpClass(cls):
        make = BigSites.make_site_module()
        cls.built = {}
        for name in cls.FIXTURES:
            export = make.grow(name)
            template = sync.default_template()
            report = sync.fill(template, export, today="2026-10-12")
            cls.built[name] = (export, template, report)
        for name, profile, data in cls.PROFILE_FIXTURES:
            export = json.loads(resources.files("netdiagrams").joinpath(f"data/{data}").read_text())
            template = sync.default_template(profile)
            report = sync.fill(template, export, settings={"profile": profile}, today="2026-10-12")
            cls.built[name] = (export, template, report)

    def pages(self, template):
        return {d.get("id"): Graph(d) for d in template.findall("diagram")}

    def test_two_builds_from_the_same_data_are_identical(self):
        make = BigSites.make_site_module()
        export = make.grow("starter")
        a, b = sync.default_template(), sync.default_template()
        sync.fill(a, export, today="2026-10-12")
        sync.fill(b, export, today="2026-10-12")
        self.assertEqual(ET.tostring(a), ET.tostring(b))

    def test_the_controls_bar_sits_inside_the_frame(self):
        for name, (_, template, _) in self.built.items():
            for page_id, g in self.pages(template).items():
                frame = [g.box(i) for i in g.els if g.layer_of(i).startswith("Border") and g.box(i)[2] > 1000
                        ]
                buttons = [g.box(i) for i in g.els if g.layer_of(i).startswith("Controls") and g.box(i)[2] > 0]
                if not frame or not buttons:
                    continue
                fx, fy, fw, fh = frame[0]
                right = max(x + w for x, _, w, _ in buttons)
                self.assertLessEqual(right, fx + fw, f"{name} {page_id}: controls bar outside the frame")
                self.assertGreaterEqual(min(x for x, *_ in buttons), fx, f"{name} {page_id}")

    def test_every_sheet_carries_provenance_and_the_same_revision(self):
        for name, (export, template, report) in self.built.items():
            rev = report.provenance.revision
            total = len(template.findall("diagram"))
            for page_id, g in self.pages(template).items():
                with self.subTest(fixture=name, page=page_id):
                    notes = [el for el in g.els.values() if el.get("netdiagrams_provenance") == "1"]
                    self.assertEqual(len(notes), 1)
                    line = g.value(notes[0])
                    self.assertIn(f"Rev {rev}", line)
                    self.assertIn("sha256", line)
                    table = next(t for t in g.tables() if {"SITE", "DATE", "REV", "SHEET"} <= set(g.header(t)))
                    cells = dict(zip(g.header(table), g.row_cells(g.rows(table)[1])))
                    self.assertEqual(g.value(g.els[cells["REV"]]), rev)
                    self.assertTrue(g.value(g.els[cells["SHEET"]]).endswith(f" of {total}"))

    def test_every_netbox_device_is_drawn_scheduled_grouped_or_reported(self):
        for name, (export, template, report) in self.built.items():
            with self.subTest(fixture=name):
                named = {d["name"] for d in export["devices"] if d.get("name")}
                drawn = {o.get("name") for d in template.findall("diagram") for o in d.iter("object")
                         if sync._is_device(o)}
                grouped = {m for members in report.grouped.values() for m in members}
                accounted = drawn | grouped | set(report.scheduled) | set(report.netbox_only_devices)
                tidy = intake.intake(export)
                left = named - accounted - set(tidy.unnamed)
                left = {n for n in left if not any(n in line for line in report.markdown("x").splitlines())}
                self.assertEqual(left, set())

    def test_no_orphan_pills_or_literal_placeholders_remain(self):
        from netdiagrams import truth
        for name, (export, template, report) in self.built.items():
            for page_id, g in self.pages(template).items():
                if page_id not in ("physical", "logical", "wireless"):
                    continue
                with self.subTest(fixture=name, page=page_id):
                    ends = truth.edge_endpoints(g, list(g.els))
                    for i, el in g.els.items():
                        cell = sync.cell_of(el)
                        if cell is None or cell.get("vertex") != "1" or g.hidden(i):
                            continue
                        style = cell.get("style") or ""
                        x, y, w, h = g.box(i)
                        if style.startswith("ellipse;fillColor=none") and not g.value(el).strip() \
                                and max(w, h) <= 40:  # a port-channel oval
                            self.assertTrue(truth._near(x + w / 2, y + h / 2, ends, max(w, h) + 24),
                                            f"orphan oval {i} at {x:g},{y:g}")
                        if el.tag == "object" and el.get("placeholders") == "1":
                            for key in re.findall(r"%(\w+)%", el.get("label") or ""):
                                self.assertIsNotNone(sync._inherited(g, el, key), f"{i}: %{key}%")

    def test_rack_pills_read_the_device_they_sit_in(self):
        template = sync.default_template()
        before = len([o for o in template.iter("object") if "%rack%" in (o.get("label") or "")])
        sync.fill(template, small_site_export(), today="2026-10-12")
        pills = [o for o in template.iter("object") if "%rack%" in (o.get("label") or "")]
        self.assertGreater(len(pills), before // 2)
        self.assertFalse([o.get("id") for o in pills if o.get("rack") == ""])

    def test_table_rows_are_tall_enough_for_their_text(self):
        from netdiagrams import graph as graph_mod
        for name, (export, template, report) in self.built.items():
            for page_id, g in self.pages(template).items():
                for table in g.tables():
                    header = g.header(table)
                    if not header or g.hidden(table):
                        continue
                    for row in g.rows(table)[1:]:
                        cells = g.row_cells(row)
                        geo = g.geometry(row)
                        if geo is None or not cells:
                            continue
                        size = graph_mod.font_size(sync.cell_of(g.els[cells[0]]).get("style") or "")
                        need = graph_mod.row_height([(g.value(g.els[c]), float(g.geometry(c).get("width", 60)))
                                                     for c in cells if g.geometry(c) is not None], size)
                        with self.subTest(fixture=name, page=page_id, row=row):
                            self.assertGreaterEqual(float(geo.get("height", 0)) + 0.01, need)

    def test_examples_are_marked_and_guides_hidden_on_every_fixture(self):
        from netdiagrams import truth
        for name, (export, template, report) in self.built.items():
            pages = self.pages(template)
            for page_id in truth.EXAMPLE_SHEETS:
                if page_id in pages:
                    with self.subTest(fixture=name, page=page_id):
                        g = pages[page_id]
                        self.assertIn("Example watermark", g.layers.values())
            for page_id, g in pages.items():
                for layer_id, layer in g.layers.items():
                    if layer.startswith("Guides"):
                        self.assertEqual(g.els[layer_id].get("visible"), "0", f"{name}/{page_id}")


class DataQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("starter")
        cls.card = doctor.quality(cls.export)

    def test_scorecard_counts_missing_of_total_and_weights_the_score(self):
        card = self.card
        serial = card.check("no_serial")
        self.assertEqual((serial.missing, serial.total), (4, 10))
        self.assertEqual(serial.group, "evidence")
        self.assertTrue(0 < card.score < 100)
        weight = sum(quality.WEIGHT[c.group] for c in card.checks if c.total > 0)
        expected = round(100 * sum(quality.WEIGHT[c.group] * c.complete for c in card.checks if c.total > 0) / weight)
        self.assertEqual(card.score, expected)
        self.assertTrue(card.worst and len(card.worst[0][1]) >= len(card.worst[-1][1]))
        self.assertTrue(all(z.complete <= z.devices for z in card.zones))
        perfect = doctor.quality({"site": {"name": "Empty", "slug": "e"}, "devices": [], "cables": [],
                                  "vlans": [{"id": 1, "vid": 1, "name": "x"}],
                                  "prefixes": [{"id": 1, "prefix": "10.0.0.0/24", "vlan": {"id": 1}}]})
        self.assertEqual(perfect.score, 100)

    def test_trend_compares_with_the_previous_json(self):
        card = self.card
        previous = json.loads(json.dumps(card.to_json()))
        previous["score"] -= 7
        previous["checks"]["no_serial"]["missing"] += 2
        self.assertEqual(quality.delta(card, previous), 7)
        self.assertEqual(quality.delta(card, previous, "no_serial"), -2)
        self.assertIsNone(quality.delta(card, {"format": "something-else"}))
        text = "\n".join(quality.lines(card, previous))
        self.assertIn("+7 since Rev", text)
        self.assertIn("(-2)", text)

    def test_sheet_1c_is_drawn_with_the_title_block_and_trend(self):
        template = sync.default_template()
        report = sync.fill(template, self.export, today="2026-10-12", previous_quality={**self.card.to_json(), "score": 10})
        ids = [d.get("id") for d in template.findall("diagram")]
        self.assertEqual(ids[:2], ["overview", "quality"])
        g = Graph(next(d for d in template.findall("diagram") if d.get("id") == "quality"))
        text = " ".join(g.value(el) for el in g.els.values())
        self.assertIn("Data quality", text)
        self.assertIn("Fix these first", text)
        self.assertIn(f"▲ {report.quality.score - 10}", text)
        self.assertIn("Rev " + report.provenance.revision, text)
        self.assertTrue([el for el in g.els.values() if el.get("netdiagrams_provenance") == "1"])
        self.assertNotIn("Plan to improve", g.layers.values())
        self.assertIn("Data quality:", report.markdown("x"))
        plain_template = sync.default_template()
        sync.fill(plain_template, self.export, today="2026-10-12", quality_sheet=False)
        self.assertNotIn("quality", [d.get("id") for d in plain_template.findall("diagram")])

    def test_cli_writes_quality_json_and_doctor_fails_under(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "e.json"
            src.write_text(json.dumps(self.export))
            out = Path(tmp) / "s.drawio"
            with redirect_stdout(io.StringIO()) as log:
                self.assertEqual(cli.main(["build", "--input", str(src), "-o", str(out)]), 0)
            self.assertIn("Data quality:", log.getvalue())
            saved = json.loads((Path(tmp) / "s.quality.json").read_text())
            self.assertEqual(saved["score"], self.card.score)
            with redirect_stdout(io.StringIO()) as log:
                self.assertEqual(cli.main(["build", "--input", str(src), "-o", str(out)]), 0)
            self.assertIn("since Rev", log.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["doctor", "--input", str(src), "--fail-under", str(self.card.score)]), 0)
                with self.assertRaises(SystemExit):
                    cli.main(["doctor", "--input", str(src), "--fail-under", str(self.card.score + 1)])


class ChangesSinceLastBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("starter")
        first = sync.default_template()
        cls.first = sync.fill(first, cls.export, today="2026-10-12")
        later = json.loads(json.dumps(cls.export))
        core = next(d for d in later["devices"] if d["name"] == "S01-IT-CORE-1")
        core["serial"] = "NEWSERIAL"
        new = json.loads(json.dumps(core))
        new.update(id=424242, name="S01-IT-CORE-9", serial="S9")
        later["devices"].append(new)
        later["devices"] = [d for d in later["devices"] if d["name"] != "S01-AP-OF-01"]
        later["cables"][0]["label"] = "RELABELLED"
        cls.later_export = later
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, later, today="2026-10-13", previous_state=cls.first.state)

    def test_first_build_has_nothing_to_compare_and_says_so(self):
        self.assertIsNone(self.first.changes_since)
        self.assertEqual(self.first.state["format"], changes.FORMAT)
        self.assertIn("First build here", self.first.markdown("x"))

    def test_second_build_lists_added_removed_and_changed(self):
        since = self.report.changes_since
        self.assertEqual(since.since_revision, self.first.provenance.revision)
        self.assertEqual(since.added, ["S01-IT-CORE-9"])
        self.assertEqual(since.removed, ["S01-AP-OF-01"])
        self.assertIn(("S01-IT-CORE-1", "serial", "FDOxxxxxx11", "NEWSERIAL"), since.changed)
        self.assertTrue(since.cables_changed and since.cables_changed[0][1] == "label")
        text = self.report.markdown("x")
        self.assertIn(f"## Changes since Rev {self.first.provenance.revision}", text)
        self.assertIn("| S01-IT-CORE-1 | serial |", text)
        self.assertIn("1 new device,", since.summary())

    def test_changed_and_new_devices_get_a_pill_on_their_own_layer(self):
        self.assertGreater(self.report.marked_changes, 0)
        physical = Graph(next(d for d in self.template.findall("diagram") if d.get("id") == "physical"))
        self.assertIn(changes.LAYER, physical.layers.values())
        pills = {el.get("netdiagrams_change"): el for el in physical.els.values() if el.get("netdiagrams_change")}
        self.assertEqual(pills["changed"].get("label"), "CHANGED")
        self.assertIn("serial: FDOxxxxxx11 → NEWSERIAL", pills["changed"].get("tooltip"))
        # the same comparison with no changes marks nothing
        same = sync.default_template()
        again = sync.fill(same, self.export, today="2026-10-12", previous_state=self.first.state)
        self.assertEqual(again.marked_changes, 0)
        self.assertFalse(again.changes_since.any)

    def test_vendor_share_drops_the_change_layer(self):
        import copy
        mxfile = copy.deepcopy(self.template)
        share.share(mxfile, "vendor")
        physical = Graph(next(d for d in mxfile.findall("diagram") if d.get("id") == "physical"))
        self.assertNotIn(changes.LAYER, physical.layers.values())

    def test_cli_keeps_state_between_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.json", Path(tmp) / "b.json"
            a.write_text(json.dumps(self.export))
            b.write_text(json.dumps(self.later_export))
            out = Path(tmp) / "s.drawio"
            with redirect_stdout(io.StringIO()) as log:
                self.assertEqual(cli.main(["build", "--input", str(a), "-o", str(out)]), 0)
            self.assertNotIn("Since Rev", log.getvalue())
            self.assertTrue((Path(tmp) / "s.state.json").exists())
            with redirect_stdout(io.StringIO()) as log:
                self.assertEqual(cli.main(["build", "--input", str(b), "-o", str(out)]), 0)
            self.assertIn("Since Rev", log.getvalue())
            self.assertIn("NEW or CHANGED pill", log.getvalue())


class Profiles(unittest.TestCase):
    """Industry profiles: manufacturing is the default; another profile bands zones its own way."""

    def test_default_is_manufacturing(self):
        self.assertIs(profiles.current(), profiles.MANUFACTURING)
        self.assertIs(profiles.get(""), profiles.MANUFACTURING)
        self.assertEqual(band_for_zone("zone-idmz")[0], "L3.5")

    def test_unknown_profile_is_a_settings_error(self):
        with self.assertRaises(settings.SettingsError):
            profiles.get("aquarium")
        with self.assertRaises(settings.SettingsError):
            settings._as_dict({"profile": 3}, "test")
        self.assertEqual(settings._as_dict({"profile": "manufacturing"}, "test"), {"profile": "manufacturing"})

    def test_use_bands_and_restore(self):
        shop = profiles.Profile(
            name="test-shop", industry="Shop", template=profiles.MANUFACTURING.template, site_code="S01",
            site_name="Plant A", sample=profiles.MANUFACTURING.sample, sample_out="shop.drawio",
            sample_title="a test shop", bands=(("T1", "OUTSIDE", ("internet",)), ("T2", "TILLS", ("pos",))),
            band_layer="Zone bands", levels=False, band_palette={"T1": "L5", "T2": "L3.5"},
            words={"site": "shop"})
        profiles.register(shop)
        try:
            with profiles.use("test-shop"):
                self.assertEqual(band_for_zone("zone-pos")[0], "T2")
                self.assertEqual(band_for_zone("zone-idmz")[0], "—")
                self.assertEqual(profiles.palette("T2"), "L3.5")
                self.assertEqual(profiles.word("site"), "shop")
                self.assertEqual(profiles.word("area"), "line")  # not overridden: manufacturing's
                files = netbox_setup.setup_files(sync.default_template(), {}, settings.DEFAULTS)
                self.assertNotIn("Purdue level", files["1-custom-field-choice-sets.csv"])  # wireless sets only
                self.assertNotIn("purdue_level", files["2-custom-fields.csv"])
            self.assertEqual(band_for_zone("zone-idmz")[0], "L3.5")
        finally:
            profiles.PROFILES.pop("test-shop")

    def test_settings_pick_the_profile_for_a_build(self):
        export = sample_export()
        report = sync.fill(sync.default_template(), export, settings={"profile": "manufacturing"}, today="2026-01-01")
        self.assertEqual(report.profile, "manufacturing")
        with self.assertRaises(settings.SettingsError):
            sync.fill(sync.default_template(), export, settings={"profile": "aquarium"}, today="2026-01-01")


class RebuildFromOwnDrawing(unittest.TestCase):
    """``--template last.drawio``: building again from the last drawing is the day-to-day path."""

    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("edges")
        first = sync.default_template()
        sync.fill(first, cls.export, today="2026-10-12")
        cls.builds = [first]
        for _ in range(2):  # a file round trip between builds, as on disk
            again = ET.fromstring(ET.tostring(cls.builds[-1]))
            sync.fill(again, cls.export, today="2026-10-12")
            cls.builds.append(again)

    @staticmethod
    def ids(template):
        return [(d.get("id"), [e.get("id") for e in d.iter() if e.get("id")]) for d in template.findall("diagram")]

    @staticmethod
    def geometry(template):
        out = set()
        for d in template.findall("diagram"):
            for e in d.iter():
                geo = e.find("mxGeometry")
                if e.get("id") and geo is not None:
                    out.add((d.get("id"), e.get("id"), geo.get("x"), geo.get("y"), geo.get("width"), geo.get("height")))
        return out

    def test_nothing_generated_is_doubled(self):
        for n, template in enumerate(self.builds):
            pages = [p for p, _ in self.ids(template)]
            self.assertEqual(len(pages), len(set(pages)), f"build {n + 1}: duplicate sheets")
            for page, ids in self.ids(template):
                dup = sorted(i for i, c in Counter(ids).items() if c > 1 and i != "0")
                self.assertEqual(dup, [], f"build {n + 1}, sheet {page}")
                layers = [c.get("value") for c in template.find(f"diagram[@id='{page}']").iter("mxCell")
                          if c.get("parent") == "0"]
                for name in (truth.WATERMARK_LAYER, sync.UNPLACED_LAYER, sync.ADDED_LINKS_LAYER, gaps.LAYER):
                    self.assertLessEqual(layers.count(name), 1, f"build {n + 1}, sheet {page}: {name}")

    def test_the_second_build_is_a_fixpoint(self):
        self.assertEqual(self.geometry(self.builds[1]), self.geometry(self.builds[2]))
        self.assertEqual([p for p, _ in self.ids(self.builds[0])], [p for p, _ in self.ids(self.builds[2])])

    def test_a_register_sheet_comes_back_with_its_table(self):
        for n, template in enumerate(self.builds):
            sheet = template.find("diagram[@id='physical-registers']")
            self.assertIsNotNone(sheet, f"build {n + 1}")
            g = Graph(sheet)
            rows = [len(g.rows(t)) for t in g.tables() if g.header(t)[:1] == ["HOSTNAME"]]
            self.assertEqual(rows, [rows[0]] if n == 0 else self.first_rows, f"build {n + 1}")
            if n == 0:
                self.first_rows = rows
            pointers = [o for o in template.find("diagram[@id='physical']").iter("object")
                        if (o.get("id") or "").startswith("physical-registers-ptr")]
            self.assertEqual(len(pointers), 1, f"build {n + 1}")

    def test_netbox_only_links_and_dashed_lines_are_not_restyled_twice(self):
        for template in self.builds[1:]:
            links = [o for o in template.find("diagram[@id='physical']").iter("object")
                     if (o.get("id") or "").startswith("physical-nblinks-")]
            self.assertEqual(len(links), 3)
            for cell in template.iter("mxCell"):
                self.assertLessEqual((cell.get("style") or "").count(sync.MISSING_LINK_STYLE), 1)


class TrayCards(unittest.TestCase):
    """A NetBox device the template has no slot for waits in the tray with its own tags."""

    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("starter")
        core = next(d for d in cls.export["devices"] if d["name"] == "S01-IT-CORE-1")
        new = json.loads(json.dumps(core))
        new.update(id=424243, name="S01-IT-CORE-9", serial="FOC999TRAY", rack=None, position=None,
                   primary_ip4={"address": "10.1.99.99/24"})
        cls.export["devices"].append(new)
        cls.template = sync.default_template()
        sync.fill(cls.template, cls.export, today="2026-10-12")
        cls.again = ET.fromstring(ET.tostring(cls.template))
        sync.fill(cls.again, cls.export, today="2026-10-12")

    def tray_card(self, template):
        return next(o for o in template.iter("object") if o.get("name") == "S01-IT-CORE-9" and sync._is_device(o))

    def test_tray_card_has_ip_and_serial_tags_and_no_empty_pill(self):
        for template in (self.template, self.again):
            card = self.tray_card(template)
            tags = {o.get("netdiagrams_field"): o.get("label") for o in template.iter("object")
                    if o.get("netdiagrams_ref") == card.get("id")}
            self.assertEqual(tags.get("primary_ip4"), "10.1.99.99")
            self.assertEqual(tags.get("serial"), "SN FOC999TRAY")
            page = next(d for d in template.findall("diagram") if card in list(d.iter()))
            g = Graph(page)
            texts = [plain(g.value(g.els[i])) for i in g.descendants(card.get("id"))]
            self.assertFalse([t for t in texts if "%" in t or t.strip(" ·") == "U"], texts)

    def test_rebuilding_keeps_one_tag_per_field(self):
        card = self.tray_card(self.again)
        refs = [o.get("netdiagrams_field") for o in self.again.iter("object") if o.get("netdiagrams_ref") == card.get("id")]
        self.assertEqual(len(refs), len(set(refs)))


class FirewallInterfaceTable(unittest.TestCase):
    def rows(self, export):
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-12")
        g = Graph(template.find("diagram[@id='logical']"))
        table = next(t for t in g.tables() if g.header(t)[:1] == ["INTERFACE"])
        return {r[0]: r for r in table_rows_by_id(g, table)}

    def test_sample_rows_come_from_netbox_ip_addresses(self):
        rows = self.rows(sample_export())
        self.assertEqual(rows["ae1.191"][1:], ["IT ENT", "191", "10.1.191.2/29"])
        self.assertEqual(rows["MGT"][3], "10.250.1.226/27 · 10.250.1.227/27")
        self.assertFalse([r for r in rows.values() if r[1].startswith("zone-")], "zone slugs shown")

    def test_an_address_outside_any_vlan_prefix_shows_no_template_zone(self):
        export = sample_export()
        export["vlans"] = [v for v in export["vlans"] if v.get("vid") != 191]
        export["prefixes"] = [p for p in export["prefixes"] if (p.get("vlan") or {}).get("vid") != 191]
        rows = self.rows(export)
        self.assertEqual(rows["ae1.191"][1:], ["?", "?", "10.1.191.2/29"])

    def test_a_site_with_no_firewall_addresses_says_so(self):
        export = BigSites.make_site_module().grow("starter")
        firewalls = {d["name"] for d in export["devices"] if (d.get("role") or {}).get("slug") == "firewall"}
        export["ip_addresses"] = [a for a in export["ip_addresses"]
                                  if ((a.get("assigned_object") or {}).get("device") or {}).get("name") not in firewalls]
        rows = self.rows(export)
        addressed = [r for r in rows.values() if re.search(r"\d+\.\d+\.\d+\.\d+", r[3])]
        self.assertEqual(addressed, [], "template addresses shown as this site's")
        self.assertEqual(rows["ae1.191"][1:], ["?", "?", "?"])  # zone and VLAN are the template's too
        self.assertEqual(rows["eth1/7 · 1/8"][3], "back-to-back")  # not an address: the template's note stays


class NoCablesInNetBox(unittest.TestCase):
    """Template cabling is never presented as this site's when NetBox records no cables."""

    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("starter")
        cls.export["cables"] = []
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, cls.export, today="2026-10-12")

    def test_drawn_links_go_dashed(self):
        lines = [o for o in self.template.iter("object") if o.get("cable_label") and o.find("mxCell") is not None
                 and o.find("mxCell").get("edge") == "1"]
        self.assertTrue(lines)
        for line in lines:
            self.assertIn(sync.MISSING_LINK_STYLE, line.find("mxCell").get("style"), line.get("cable_label"))
            self.assertTrue(line.get("tooltip", "").startswith("Not in NetBox"))
        self.assertTrue(self.report.missing_cables)

    def test_link_register_is_empty_with_a_note(self):
        for d in self.template.findall("diagram"):
            g = Graph(d)
            for t in g.tables():
                if g.header(t)[:1] == ["LINK"] and any("A-SIDE" in h for h in g.header(t)):
                    rows = table_rows_by_id(g, t)
                    self.assertEqual([r[:2] for r in rows], [["?", "No cables in NetBox yet"]], d.get("id"))

    def test_gap_card_asks_for_the_cables(self):
        g = Graph(self.template.find("diagram[@id='physical']"))
        rows = table_rows_by_id(g, "physical-gaps-card-t")
        self.assertIn("Network gear with no cable recorded", [r[0] for r in rows])


class VlanOnlyZoneName(unittest.TestCase):
    def test_a_zone_carried_only_by_vlans_takes_its_tags_name(self):
        export = small_site_export()
        export["vlans"].append({"id": 9001, "vid": 900, "name": "GUEST-WIFI", "status": {"value": "active"},
                                "tags": [{"name": "Guests", "slug": "zone-guest"}]})
        site = model.build_site(export)
        self.assertEqual(site.zones["zone-guest"].name, "Guests")


class SviOutsidePrefix(unittest.TestCase):
    def test_the_sample_is_clean_and_its_ot_transits_sit_on_the_ot_core(self):
        export = sample_export()
        self.assertEqual(gaps.svis_outside_prefix(export), [])
        svi = {(a["assigned_object"]["name"], a["assigned_object"]["device"]["name"]): a["address"]
               for a in export["ip_addresses"] if a["assigned_object"]["name"].startswith("Vlan")}
        self.assertEqual(svi[("Vlan399", "S01-OT-CORE-1")], "10.101.252.33/29")
        self.assertEqual(svi[("Vlan191", "S01-IT-CORE-1")], "10.1.191.1/29")
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-12")
        g = Graph(template.find("diagram[@id='logical']"))
        rows = {r[0]: r for t in g.tables() if g.header(t)[:2] == ["VLAN", "NAME"] for r in table_rows_by_id(g, t)}
        self.assertIn("OT-CORE-1 .33", rows["399"][3])

    def test_an_svi_outside_its_vlans_prefix_is_a_gap(self):
        export = sample_export()
        bad = next(a for a in export["ip_addresses"] if a["assigned_object"]["name"] == "Vlan399")
        bad["address"] = "10.101.252.65/29"
        found = gaps.svis_outside_prefix(export)
        self.assertEqual(found, ["S01-OT-CORE-1 Vlan399 10.101.252.65/29 (VLAN 399 is 10.101.252.32/29)"])
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-12")
        g = Graph(template.find("diagram[@id='logical']"))
        self.assertIn("SVI addresses outside their VLAN's prefix", [r[0] for r in table_rows_by_id(g, "logical-gaps-card-t")])


def campus_export():
    """Plant A with NetBox locations nested campus > building > floor > closet."""
    export = sample_export()
    tree = [  # id, name, parent id
        (1, "Plant A campus", None),
        (2, "Admin building", 1), (3, "Admin · floor 1", 2), (4, "Admin · floor 2", 2), (5, "Admin · roof", 2),
        (6, "MDF-01", 3), (7, "IDF-1", 4), (8, "Office", 4), (9, "Mast M1", 5), (10, "Admin · basement", 2),
        (11, "Production building", 1), (12, "Production · floor 1", 11), (13, "IDF-2", 12), (14, "Control room", 12),
        (15, "IDF-B", 10), (16, "Mast M2", 12),
    ]
    export["netbox_url"] = "https://netbox.example"
    export["wireless_links"] = [{"id": 1, "ssid": "PLANT-WH", "status": {"value": "connected"},
                                 "interface_a": {"device": {"name": "S01-PTP-WH-A"}, "name": "radio0"},
                                 "interface_b": {"device": {"name": "S01-PTP-WH-B"}, "name": "radio0"}}]
    export["locations"] = [{"id": i, "name": n, "slug": n.lower().replace(" ", "-"),
                            "parent": {"id": parent} if parent else None} for i, n, parent in tree]
    by_name = {n: i for i, n, _ in tree}
    for d in export["devices"]:
        name = (d.get("location") or {}).get("name")
        if name in by_name:
            d["location"] = {"id": by_name[name], "name": name, "slug": name.lower()}
    return export


class RiserSheet(unittest.TestCase):
    """Buildings, floors and closets from NetBox's location tree, on an optional sheet."""

    @classmethod
    def setUpClass(cls):
        cls.export = campus_export()
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, cls.export, today="2026-10-16")
        cls.sheet = cls.template.find(f"diagram[@id='{riser.PAGE_ID}']")

    def objects(self, attr):
        return [o for o in self.sheet.iter("object") if o.get(attr)]

    def test_a_nested_site_gets_the_sheet_after_the_physical_pages(self):
        self.assertTrue(self.report.riser)
        self.assertIsNotNone(self.sheet)
        ids = [d.get("id") for d in self.template.findall("diagram")]
        self.assertGreater(ids.index(riser.PAGE_ID), ids.index("physical"))
        self.assertLess(ids.index(riser.PAGE_ID), ids.index("flows"))
        self.assertIn("3e", self.sheet.get("name"))

    def test_the_campus_root_is_skipped_and_each_building_is_a_box(self):
        self.assertEqual(sorted(o.get("netdiagrams_building") for o in self.objects("netdiagrams_building")), ["11", "2"])

    def test_floors_read_top_to_bottom(self):
        labels = {}
        for cell in self.sheet.iter("mxCell"):
            geo = cell.find("mxGeometry")
            if cell.get("value", "").startswith("Admin · ") and geo is not None:
                labels[cell.get("value")] = float(geo.get("y"))
        order = sorted(labels, key=labels.get)
        self.assertEqual(order, ["Admin · roof", "Admin · floor 2", "Admin · floor 1", "Admin · basement"])

    def test_closets_and_cables_come_from_netbox(self):
        cards = {o.get("netdiagrams_location"): o for o in self.objects("netdiagrams_location")}
        self.assertEqual(sorted(cards, key=int), ["6", "7", "8", "9", "13", "14", "15", "16"])
        self.assertEqual(cards["15"].get("devices"), "0")
        self.assertIn("/dcim/locations/15/", cards["15"].get("link"))
        self.assertEqual(cards["6"].get("devices"), "18")
        self.assertIn("MDF-01", cards["6"].get("label"))
        self.assertIn("Plant A campus › Admin building › Admin · floor 1 › MDF-01", cards["6"].get("tooltip"))
        self.assertIn("/dcim/devices/?location_id=6", cards["6"].get("link"))
        cables = self.objects("netdiagrams_cables")
        self.assertTrue(cables)
        self.assertTrue(any(riser.BETWEEN_BUILDINGS in cell_style(c) for c in cables),
                        "the MDF to IDF-2 uplink runs between the two buildings")
        self.assertTrue(all(re.match(r"\d+ × ", c.get("label")) for c in cables))

    def test_a_wireless_link_is_a_dashed_radio_run(self):
        radios = self.objects("netdiagrams_radio")
        self.assertEqual(len(radios), 1)
        self.assertIn("1 × radio link · PLANT-WH", radios[0].get("label"))
        self.assertIn("dashed=1", cell_style(radios[0]))
        self.assertIn("/wireless/wireless-links/?id=1", radios[0].get("link"))
        self.assertIn("radio link", self.sheet.find(".//mxCell[@id='riser-c2']").get("value"))

    def test_no_run_crosses_a_card(self):
        boxes = []
        for o in self.objects("netdiagrams_location"):
            g = o.find("mxCell/mxGeometry")
            boxes.append((o.get("netdiagrams_location"), float(g.get("x")), float(g.get("y")),
                          float(g.get("width")), float(g.get("height"))))
        runs = self.objects("netdiagrams_cables") + self.objects("netdiagrams_radio")
        for run in runs:
            points = [(float(pt.get("x")), float(pt.get("y"))) for pt in run.iter("mxPoint")]
            self.assertGreaterEqual(len(points), 2, run.get("label"))
            for (x1, y1), (x2, y2) in zip(points, points[1:]):
                self.assertTrue(x1 == x2 or y1 == y2, f"{run.get('label')}: a slanted segment")
                for loc, bx, by, bw, bh in boxes:
                    crosses = (min(x1, x2) < bx + bw - 1 and max(x1, x2) > bx + 1
                               and min(y1, y2) < by + bh - 1 and max(y1, y2) > by + 1)
                    self.assertFalse(crosses, f"{run.get('label')} runs through card {loc}")

    def test_buildings_are_packed_into_columns(self):
        tops = {}
        for o in self.objects("netdiagrams_building"):
            g = o.find("mxCell/mxGeometry")
            tops[o.get("netdiagrams_building")] = (float(g.get("x")), float(g.get("y")), float(g.get("width")))
        (ax, ay, aw), (px, py, pw) = tops["2"], tops["11"]
        self.assertTrue(ax + aw <= px or px + pw <= ax or ay != py, "the two buildings do not overlap")

    def test_a_flat_site_gets_no_sheet_unless_asked(self):
        plain_template = sync.default_template()
        report = sync.fill(plain_template, sample_export(), today="2026-10-16")
        self.assertFalse(report.riser)
        self.assertIsNone(plain_template.find(f"diagram[@id='{riser.PAGE_ID}']"))
        asked = sync.default_template()
        flat = sample_export()
        flat.pop("locations")
        report = sync.fill(asked, flat, today="2026-10-16", riser=True)
        self.assertTrue(report.riser)
        sheet = asked.find(f"diagram[@id='{riser.PAGE_ID}']")
        self.assertIn("NetBox has no locations", ET.tostring(sheet, encoding="unicode"))
        refused = sync.default_template()
        self.assertFalse(sync.fill(refused, self.export, today="2026-10-16", riser=False).riser)
        self.assertIsNone(refused.find(f"diagram[@id='{riser.PAGE_ID}']"))

    def test_the_sheet_can_be_left_out_by_name(self):
        template = sync.default_template()
        sync.fill(template, self.export, today="2026-10-16", pages="-riser")
        self.assertIsNone(template.find(f"diagram[@id='{riser.PAGE_ID}']"))

    def test_rebuilding_from_the_drawing_keeps_one_sheet(self):
        again = ET.fromstring(ET.tostring(self.template))
        sync.fill(again, self.export, today="2026-10-16")
        self.assertEqual(len(again.findall(f"diagram[@id='{riser.PAGE_ID}']")), 1)
        first = {o.get("netdiagrams_location") for o in self.objects("netdiagrams_location")}
        second = {o.get("netdiagrams_location") for o in again.find(f"diagram[@id='{riser.PAGE_ID}']").iter("object")
                  if o.get("netdiagrams_location")}
        self.assertEqual(first, second)


def cell_style(obj):
    return obj.find("mxCell").get("style") or ""


class LocationPaths(unittest.TestCase):
    """Device cards and the physical page's closet boxes say where NetBox puts them."""

    @classmethod
    def setUpClass(cls):
        cls.export = campus_export()
        cls.template = sync.default_template()
        sync.fill(cls.template, cls.export, today="2026-10-16")
        cls.physical = Graph(cls.template.find("diagram[@id='physical']"))

    def notes(self, template=None):
        page = (self.template if template is None else template).find("diagram[@id='physical']")
        return [o for o in page.iter("object") if o.get("netdiagrams_closet")]

    def test_a_device_carries_its_location_path(self):
        core = next(el for el in self.physical.els.values() if el.get("name") == "S01-IT-CORE-1")
        self.assertEqual(core.get("location_path"), "Admin building › Admin · floor 1 › MDF-01")
        self.assertEqual(core.get("location"), "MDF-01")
        text = ET.tostring(self.template.find("diagram[@id='physical']"), encoding="unicode")
        self.assertIn("Admin building › Admin · floor 1 › MDF-01", text)
        self.assertNotIn("%location_path%", text)

    def test_closet_boxes_get_the_shared_path(self):
        notes = self.notes()
        self.assertTrue(notes)
        for note in notes:  # inside the box's top strip, or just above the box when its title fills that strip,
            # or along its bottom when a link pill or band subtitle sits just above it
            box = self.physical.box(note.get("id")[:-len("-closet")])
            x, y = (float(note.find("mxCell/mxGeometry").get(k)) for k in ("x", "y"))
            self.assertIn(y, (box[1] + 4, box[1] - 16, box[1] + box[3] - 18, box[1] + box[3] + 2), note.get("label"))
            spot = (x, y, float(note.find("mxCell/mxGeometry").get("width")), 14)
            for j, el in self.physical.els.items():  # never printed over another label
                if j != note.get("id") and cell_of(el) is not None and cell_of(el).get("vertex") == "1" \
                        and not self.physical.hidden(j) and plain(self.physical.value(el)).strip() \
                        and not el.get("netdiagrams_closet") and sync._overlaps(self.physical.box(j), spot):
                    self.assertTrue(sync._inside(spot, self.physical.box(j)), (note.get("label"), j))
            self.assertGreaterEqual(x, box[0])
        paths = sorted(o.get("label") for o in notes)
        self.assertTrue(all(" › " in p for p in paths), paths)
        mdf = next(o for o in notes if o.get("label").endswith("MDF-01"))
        self.assertIn("/dcim/locations/6/", mdf.get("link"))

    def test_a_flat_site_gets_no_closet_notes(self):
        template = sync.default_template()
        sync.fill(template, sample_export(), today="2026-10-16")
        self.assertEqual(self.notes(template), [])
        text = ET.tostring(template.find("diagram[@id='physical']"), encoding="unicode")
        self.assertNotIn("%location_path%", text)

    def test_rebuilding_keeps_one_note_per_box(self):
        again = ET.fromstring(ET.tostring(self.template))
        sync.fill(again, self.export, today="2026-10-16")
        self.assertEqual(sorted(o.get("id") for o in self.notes(again)), sorted(o.get("id") for o in self.notes()))


def school_export():
    from netdiagrams import profiles
    return json.loads(resources.files("netdiagrams").joinpath(
        "data", profiles.get("education").sample).read_text("utf-8"))


class SchoolRenderGate(RenderGate):
    """The same definition of done over the education template and its Harbor Pines sample."""

    FIXTURES = ("school",)

    @classmethod
    def setUpClass(cls):
        export = school_export()
        template = sync.default_template("education")
        cls.built = {"school": (export, template, sync.fill(template, export, today="2026-10-12"))}


class Education(unittest.TestCase):
    def test_bundled_files_match_the_generator(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "make_school", Path(__file__).parent.parent / "scripts" / "make_school.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        with tempfile.TemporaryDirectory() as tmp:
            for write, bundled in ((gen.write_template, gen.TEMPLATE), (gen.write_sample, gen.SAMPLE),
                                   (gen.write_stencils, gen.STENCILS)):
                with contextlib.redirect_stdout(io.StringIO()):
                    write(Path(tmp) / bundled.name)
                with self.subTest(file=bundled.name):
                    self.assertEqual((Path(tmp) / bundled.name).read_text("utf-8"), bundled.read_text("utf-8"))

    def test_the_manufacturing_template_stays_the_default(self):
        from netdiagrams import profiles
        self.assertEqual(profiles.DEFAULT, "manufacturing")
        self.assertIsNone(sync.default_template().get("industry"))
        self.assertEqual(sync.default_template("education").get("industry"), "education")

    def test_the_sample_builds_back_to_itself(self):
        export = school_export()
        template = sync.default_template("education")
        report = sync.fill(template, export, today="2026-10-12")
        self.assertEqual(report.profile, "education")
        # Two APs are in NetBox only: each folds into a drawn AP of its wing, which reads "AP ×2".
        self.assertEqual(report.grouped, {"HS1-AP-A120": ["HS1-AP-A110"], "HS1-AP-B230": ["HS1-AP-B202"]})
        folded = {m for members in report.grouped.values() for m in members}
        self.assertEqual(report.matched_devices | folded, {d["name"] for d in export["devices"]})
        self.assertEqual((report.removed_devices, report.netbox_only_devices, report.netbox_only_cables), ([], [], []))
        self.assertEqual(report.site_code, "HS1")
        text = ET.tostring(template, encoding="unicode")
        self.assertIn("Draw Secure School Network Diagrams", text)
        self.assertNotIn("Manufacturing Network Diagrams", text)
        self.assertNotIn("Plant A", text)

    def test_a_school_build_renames_the_example_site(self):
        export = json.loads(json.dumps(school_export()).replace("HS1-", "MS1-")
                            .replace("Harbor Pines High School", "Cedar Middle School"))
        export["site"]["facility"] = "MS1"
        template = sync.default_template("education")
        report = sync.fill(template, export, today="2026-10-12")
        self.assertEqual(report.site_code, "MS1")
        self.assertIn("MS1 · Cedar Middle School — Physical Architecture", ET.tostring(template, encoding="unicode"))
        drawn = {o.get("name") for o in template.iter("object") if sync._is_device(o)}
        self.assertIn("MS1-CORE-1", drawn)
        self.assertFalse({n for n in drawn if n.startswith("HS1-")})

    def test_sample_command_writes_the_school(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, built = Path(tmp) / "school.drawio", Path(tmp) / "hs1.drawio"
            src = Path(tmp) / "hs1.json"
            src.write_text(json.dumps(school_export()), "utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["sample", "--profile", "education", "-o", str(out)]), 0)
                # The export names its profile in the site's netdiagrams field: no flag needed.
                self.assertEqual(cli.main(["build", "--input", str(src), "-o", str(built)]), 0)
            self.assertEqual(ET.parse(out).getroot().get("industry"), "education")
            self.assertIn("Chapter 5, Cables are data", out.read_text("utf-8"))
            self.assertIn("Harbor Pines High School", built.read_text("utf-8"))
class Warehouse(unittest.TestCase):
    """The warehouse standard: W01 · Riverside DC and the W02 cross-dock, drawn with no plant words left."""

    PLANT = re.compile(r"\b(plant|production line|assembly|packaging|boiler|pump house|historian|MES|AGV|OEM)\b", re.I)

    def build(self, data):
        export = json.loads(resources.files("netdiagrams").joinpath(f"data/{data}").read_text())
        template = sync.default_template("warehouse")
        report = sync.fill(template, export, settings={"profile": "warehouse"}, today="2026-10-12")
        return export, template, report

    def words(self, template):
        out = []
        for d in template.findall("diagram"):
            for el in d.iter():
                cell = el if el.tag == "mxCell" else el.find("mxCell")
                if cell is not None and cell.get("parent") == "0":
                    continue
                for key in ("value", "label", "tooltip"):
                    if el.get(key):
                        out.append((d.get("id"), el.get(key)))
        return out

    def test_registered_with_its_own_template_and_sample(self):
        p = profiles.get("warehouse")
        self.assertEqual((p.site_code, p.site_name), ("W01", "Riverside DC"))
        for name in (p.template, p.sample, "sample-warehouse-w02.json"):
            self.assertTrue(resources.files("netdiagrams").joinpath(f"data/{name}").is_file(), name)

    def test_sample_and_builds_use_warehouse_words(self):
        with profiles.use("warehouse"):
            sample = sync.default_template("warehouse")
        for label, template in (("sample", sample), ("w01", self.build("sample-warehouse-w01.json")[1]),
                                ("w02", self.build("sample-warehouse-w02.json")[1])):
            left = [(page, text[:80]) for page, text in self.words(template) if self.PLANT.search(text)]
            self.assertEqual(left, [], label)

    def test_the_sample_rebuilds_without_drift(self):
        export, template, report = self.build("sample-warehouse-w01.json")
        self.assertEqual(report.netbox_only_devices, [])
        self.assertEqual(report.removed_devices, [])
        self.assertEqual(report.site_code, "W01")

    def test_the_cross_dock_is_renamed_and_shows_its_gaps(self):
        export, template, report = self.build("sample-warehouse-w02.json")
        names = {o.get("name") for d in template.findall("diagram") for o in d.iter("object") if sync._is_device(o)}
        self.assertIn("W02-OT-CORE-1", names)
        self.assertFalse({n for n in names if n and n.startswith("W01-")})
        plan = [t for _, t in self.words(template) if "Plan to improve" in t]
        self.assertTrue(plan)

    def test_wireless_flow_ids_do_not_collide_with_the_site_code(self):
        template = sync.default_template("warehouse")
        wireless = next(d for d in template.findall("diagram") if d.get("id") == "wireless")
        ids = {el.get("value") for el in wireless.iter() if re.fullmatch(r"W[F0-9]+\d", el.get("value") or "")}
        self.assertIn("WF01", ids)
        self.assertNotIn("W01", ids)

    def test_overview_says_warehouse(self):
        export, template, report = self.build("sample-warehouse-w01.json")
        overview = " ".join(t for page, t in self.words(template) if page == "overview")
        self.assertIn("warehouse", overview)
        self.assertNotIn("plant", overview.lower())

    def test_wifi_is_in_netbox_and_on_the_wireless_sheet(self):
        for data, ssids, links in (("sample-warehouse-w01.json", {"CORP", "GUEST", "WH-SCAN", "C02-AMR", "WH-IOT"}, 3),
                                   ("sample-warehouse-w02.json", {"CORP", "GUEST", "WH-SCAN"}, 0)):
            export, template, report = self.build(data)
            self.assertEqual({w["ssid"] for w in export["wireless_lans"]}, ssids, data)
            self.assertEqual(len(export["wireless_links"]), links, data)
            self.assertNotRegex(json.dumps(export), r'"[a-z_]*psk[a-z_]*":', data)  # no key is ever stored
            self.assertIn(("3d · Wireless — Cisco WLAN · PtP", "SSID table", len(ssids)), report.tables, data)
            found = gaps.find(export, sync.ENDPOINT_ROLES, lambda d: ot.device_zones(d, []), "2026-10-12")
            for check in ("no_wireless_links", "wlan_no_vlan", "wlan_no_manager", "ap_no_location", "wlink_bad_ends",
                          "wgb_no_link", "wlan_no_fields"):
                self.assertEqual(found[check].names if check in found else [], [], (data, check))
            # Every AP radio names the SSIDs it carries; 2.4 GHz only the SSIDs that use it.
            radios = [i for i in export["interfaces"] if i["name"] in ("radio0", "radio1")
                      and "-AP-" in i["device"]["name"]]
            self.assertTrue(radios and all(i["wireless_lans"] or i["name"] == "radio0" for i in radios), data)
            bands = {w["id"]: w["custom_fields"]["wlan_bands"] for w in export["wireless_lans"]}
            self.assertTrue(all("2.4ghz" in bands[w["id"]] for i in radios if i["name"] == "radio0"
                                for w in i["wireless_lans"]), data)
            text = " ".join(t for p, t in self.words(template) if p == "wireless")
            self.assertNotIn("‹n›", text)
            self.assertNotIn("‹link ssid›", text)
            # Every AP has a shape of its own: nothing is folded into a counted group.
            self.assertEqual(report.grouped, {}, data)

    def test_the_generator_reproduces_the_bundled_files(self):
        # Run in a child process: make_warehouse patches make_sample's module globals.
        import subprocess, sys
        root = Path(__file__).parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            code = ("import sys, pathlib; sys.path[:0] = ['scripts']; import make_warehouse as w; t = pathlib.Path(sys.argv[1]); "
                    "w.TEMPLATE, w.SAMPLE, w.SMALL = t / w.TEMPLATE.name, t / w.SAMPLE.name, t / w.SMALL.name; w.main()")
            subprocess.run([sys.executable, "-c", code, tmp], cwd=root, check=True, capture_output=True)
            for name in ("W01-Warehouse-Network-Template.drawio", "sample-warehouse-w01.json", "sample-warehouse-w02.json"):
                self.assertEqual((Path(tmp) / name).read_bytes(), (root / "src" / "netdiagrams" / "data" / name).read_bytes(), name)

    def test_handhelds_reach_the_wms_through_the_dmz(self):
        template = sync.default_template("warehouse")
        text = {d.get("id"): " ".join(t for p, t in self.words(template) if p == d.get("id"))
                for d in template.findall("diagram")}
        self.assertIn("Handhelds → WMS", text["flows"])
        self.assertIn("IDMZ WMS broker → cloud WMS", text["register"])
        self.assertNotIn("Central OT", text["flows"] + text["register"])
        self.assertNotIn("instantly", text["overview"])

    def test_warehouse_shapes_and_netbox_words(self):
        with profiles.use("warehouse"):
            lib = stencils.library()
            for role in ("handheld", "vehicle-mount-terminal", "amr", "print-and-apply", "camera",
                         "dock-door-controller"):
                self.assertIn(stencils.shape_for_role(role), lib)
            self.assertIn("Conveyor PLC", lib)
            self.assertIn("Sorter PLC", lib)
            self.assertEqual(stencils.shape_for_role("plc"), "PLC")
            self.assertNotIn("Purdue band L4", lib)
            self.assertIn("handheld", sync.endpoint_roles())
            readme = netbox_setup.guide({"3-zone-tags.csv": ""})
            self.assertIn("(building, area, aisle or dock door)", readme)
            self.assertIn("group aisles and dock doors under areas and buildings", readme)




def s07_export(mode: str = ""):
    """Plant A renamed S07 with no controllers, a mesh AP, a PtP link without an SSID and five SSIDs."""
    import copy
    text = json.dumps(sample_export()).replace("S01-", "S07-").replace('"s01"', '"s07"').replace("Plant A", "Plant G")
    e = json.loads(text)
    e["netbox_url"] = "https://netbox.example"
    e["devices"] = [d for d in e["devices"] if d["role"]["slug"] != "wireless-controller"]
    for d in e["devices"]:   # nothing recorded about how the APs are managed
        for key in ("ap_mode", "wireless_controller"):
            (d.get("custom_fields") or {}).pop(key, None)
    ids = {d["name"]: d["id"] for d in e["devices"]}
    nid = max(ids.values()) + 1
    mesh = copy.deepcopy(next(d for d in e["devices"] if d["name"] == "S07-AP-WH-02"))
    mesh.update(id=nid, name="S07-AP-YARD-01", location={"name": "Yard", "slug": "yard"}, serial="YARD0001",
                asset_tag=None)
    e["devices"].append(mesh)
    ids[mesh["name"]] = nid
    iid = max(i["id"] for i in e["interfaces"]) + 1

    def iface(dev, name, **kw):
        nonlocal iid
        i = {"id": iid, "device": {"id": ids[dev], "name": dev}, "name": name, "type": {"value": "ieee802.11ax"},
             "enabled": True, "lag": None, "mode": None, "untagged_vlan": None, "tagged_vlans": [], "description": "",
             "vrf": None, **kw}
        iid += 1
        e["interfaces"].append(i)

    iface("S07-AP-WH-02", "radio0", rf_role={"value": "ap"}, rf_channel={"value": "5g-36-20", "label": "36 (5180/20)"})
    iface("S07-AP-YARD-01", "radio0", rf_role={"value": "station"})
    iface("S07-PTP-WH-B", "ath0")
    iface("S07-PTP-PH-B", "wlan0")
    end = lambda dev, name: {"device": {"id": ids[dev], "name": dev}, "name": name}
    e["wireless_links"] = [
        {"id": 1, "ssid": "S07-MESH", "status": {"value": "connected"}, "interface_a": end("S07-AP-WH-02", "radio0"),
         "interface_b": end("S07-AP-YARD-01", "radio0"), "auth_type": {"value": "wpa-personal"},
         "auth_cipher": {"value": "aes"}},
        {"id": 2, "ssid": "", "status": {"value": "connected"}, "interface_a": end("S07-PTP-WH-A", "ath0"),
         "interface_b": end("S07-PTP-WH-B", "ath0"), "auth_type": {"value": "wpa-personal"},
         "auth_cipher": {"value": "aes"}, "distance": 350, "distance_unit": {"value": "m"}},
    ]
    vl = {v["vid"]: v for v in e["vlans"]}
    wlan = lambda i, ssid, vid, auth, cipher, **kw: {
        "id": i, "ssid": ssid, "vlan": {"id": vl[vid]["id"], "vid": vid} if vid else None,
        "auth_type": {"value": auth, "label": auth.replace("wpa-", "WPA ").title()},
        "auth_cipher": {"value": cipher, "label": cipher.upper()} if cipher else None,
        "status": {"value": "active"}, **kw}
    e["wireless_lans"] = [
        wlan(1, "STAFF", 130, "wpa-enterprise", "aes"),
        wlan(2, "VISITOR", 190, "open", ""),
        wlan(3, "SCANNERS", 350, "wpa-personal", "aes", auth_psk="hunter2-secret-key"),
        wlan(4, "LEGACY-IOT", 0, "wpa-personal", "tkip", auth_psk="iot-psk-0000", status={"value": "planned"}),
        wlan(5, "OPEN-LAB", 310, "open", ""),
    ]
    if mode:
        e["site"]["custom_fields"] = {"wireless_management": mode,
                                      "wireless_manager": {"cloud": "Meraki Dashboard"}.get(mode, "")}
    return e


def page_text(diagram):
    return " ".join((el.get("value") or el.get("label") or "") for el in diagram.iter())


def sparse_wireless_export():
    """A day-one site: a few devices, one AP, the controllers and a spare, no radios, two SSIDs."""
    import copy
    e = sample_export()
    keep = {"S01-FW-EDGE-01", "S01-IT-CORE-1", "S01-FW-ITOT-01", "S01-OT-CORE-1", "S01-AP-OF-01",
            "S01-WLC-01", "S01-WLC-02", "S01-OT-WLC-01", "S01-OT-WLC-02"}
    e["devices"] = [d for d in e["devices"] if d["name"] in keep]
    spare = copy.deepcopy(next(d for d in sample_export()["devices"] if d["name"] == "S01-OT-WLC-02"))
    spare.update(id=9001, name="S01-OT-WLC-03", serial="WLC0003", asset_tag=None)
    e["devices"].append(spare)
    e["vlans"] = [v for v in e["vlans"] if v["vid"] in (110, 310)]
    e["wireless_links"] = []
    corp = next(w for w in e["wireless_lans"] if w["ssid"] == "CORP")
    corp.update(scope_type="dcim.site", scope_id=e["site"]["id"])   # its VLAN sits in a VLAN group, not on the site
    e["wireless_lans"] = [corp, next(w for w in e["wireless_lans"] if w["ssid"] == "GUEST")]
    return e


class SparseWireless(unittest.TestCase):
    """The wireless sheet of a site NetBox barely knows: nothing of Plant A reads as this site's."""

    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, sparse_wireless_export(), today="2026-10-16")
        cls.g = page(cls.template, "3d")

    def test_an_ssid_scoped_to_the_site_stays_and_one_on_another_vlan_is_reported(self):
        self.assertEqual([r[0].split(" ")[0] for r in table_rows(self.g, "SSID")], ["CORP"])
        self.assertEqual(self.report.intake.left_out_wlans, ["GUEST (VLAN 190)"])
        self.assertIn("- GUEST (VLAN 190)", self.report.markdown("Plant A"))

    def test_the_ptp_register_keeps_no_example_link(self):
        rows = table_rows(self.g, "LINK")
        self.assertEqual(rows[0][:2], ["?", "No wireless links in NetBox yet"])
        self.assertNotIn("10.1.99.41", " ".join(" ".join(r) for r in rows))

    def test_the_site_plan_and_flows_are_marked_as_the_templates_example(self):
        self.assertIn("3d · Wireless — Cisco WLAN · PtP: site plan schematic", self.report.examples_marked)
        self.assertIn("3d · Wireless — Cisco WLAN · PtP: wireless flows", self.report.examples_marked)

    def test_the_drift_report_says_which_tray_a_device_waits_in(self):
        self.assertEqual(self.report.wireless_tray, ["S01-OT-WLC-03"])
        text = self.report.markdown("Plant A")
        physical = text.split("## In NetBox, no slot on the drawing (in the tray below the physical page)")[1]
        self.assertNotIn("S01-OT-WLC-03", physical.split("## ")[0])
        wireless = text.split("## In NetBox, no slot on the wireless sheet (in the tray below it)")[1]
        self.assertIn("- S01-OT-WLC-03", wireless.split("## ")[0])

    def test_the_full_sample_keeps_its_site_plan_and_flows_unmarked(self):
        template = sync.default_template()
        report = sync.fill(template, sample_export(), today="2026-10-16")
        self.assertFalse([m for m in report.examples_marked if m.startswith("3d")])


class WirelessCoverage(unittest.TestCase):
    """A site with APs but no controller in NetBox: nothing of the template's Cisco example survives."""

    @classmethod
    def setUpClass(cls):
        cls.export = s07_export()
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, cls.export, today="2026-10-16")
        cls.sheet = cls.template.find("diagram[@id='wireless']")
        cls.g = Graph(cls.sheet)

    def rows(self, first):
        g = self.g
        return [[plain(g.value(g.els[c])) if isinstance(c, str) and c in g.els else "" for c in g.row_cells(r)]
                for t in g.tables() if g.header(t)[:1] == [first] for r in g.rows(t)[1:]]

    def test_template_controllers_leave_the_page_with_no_trace(self):
        self.assertEqual(sorted(self.report.removed_cards), ["S07-OT-WLC-01", "S07-OT-WLC-02", "S07-WLC-01", "S07-WLC-02"])
        hidden = {c.get("id") for c in self.sheet.iter("mxCell") if c.get("parent") == "0" and c.get("visible") == "0"}
        shown = [el for el in self.sheet.iter() if (el.get("parent") or (el.find("mxCell").get("parent")
                 if el.tag == "object" and el.find("mxCell") is not None else "")) not in hidden]
        text = " ".join((el.get("value") or el.get("label") or "") for el in shown)
        # Only the design notes on the hidden Guides layer still speak of the template's controllers.
        self.assertFalse(re.findall(r"S07-(?:OT-)?WLC", text), "a template controller name survived")
        self.assertNotIn("CAPWAP →", text)
        self.assertNotIn("local mode", text.lower().replace("local switching", ""))
        self.assertEqual(self.report.template_leftovers, {"wireless": {"S07-WLC", "S07-OT-WLC"}})

    def test_a_management_card_stands_where_the_controllers_were(self):
        cards = [o for o in self.sheet.iter("object") if o.get(sync.wireless_page.MGMT_MARK) is not None]
        self.assertEqual(len(cards), 1)
        self.assertIn("No wireless controller in NetBox", cards[0].get("label"))
        self.assertEqual(self.report.wireless_management, "No wireless controller in NetBox")
        self.assertNotIn("Nothing in NetBox here yet", cards[0].get("label"))

    def test_ssid_rows_say_what_netbox_does_not_record(self):
        rows = {r[0].split(" ")[0]: r for r in self.rows("SSID")}
        self.assertEqual(set(rows), {"STAFF", "VISITOR", "SCANNERS", "LEGACY-IOT", "OPEN-LAB"})
        header = self.g.header(next(t for t in self.g.tables() if self.g.header(t)[:1] == ["SSID"]))
        col = {h.split(" ")[0]: i for i, h in enumerate(header)}
        self.assertEqual(rows["STAFF"][col["CONTROLLER"]], "?")
        self.assertEqual(rows["STAFF"][col["SWITCHING"]], "?")
        self.assertEqual(rows["STAFF"][col["BANDS"]], "?")
        self.assertEqual(rows["LEGACY-IOT"][col["VLAN"]], "?")
        self.assertIn("planned", rows["LEGACY-IOT"][0].lower())
        self.assertEqual(rows["VISITOR"][col["GUEST"]], "?")
        self.assertEqual(rows["SCANNERS"][col["GUEST"]], "")   # not a guest SSID: no guest controls asked for
        self.assertEqual(rows["STAFF"][col["VLAN"]], "130 · 10.1.30.0/23")
        self.assertIn("hunter2", json.dumps(self.export))   # the fixture carries a key...
        self.assertNotIn("hunter2", ET.tostring(self.template, encoding="unicode"))  # ...the drawing never does

    def test_a_mesh_ap_is_drawn_with_its_radio_link_and_not_flagged(self):
        self.assertTrue(any(o.get("name") == "S07-AP-YARD-01" for o in self.sheet.iter("object")))
        self.assertEqual(self.report.added_wireless_links, ["S07-MESH"])
        layer = self.sheet.find(".//mxCell[@id='wireless-nbradio']")
        self.assertIsNotNone(layer)
        edges = [c for c in self.sheet.iter("mxCell") if c.get("parent") == "wireless-nbradio" and c.get("edge") == "1"]
        self.assertEqual(len(edges), 1)
        checks = {c.key: c.names for c in self.report.quality.checks}
        for key in ("ap_no_cable", "no_wireless_links", "wlink_bad_ends", "ap_no_location", "no_location"):
            self.assertNotIn("S07-AP-YARD-01", checks[key], key)
        self.assertIn("S07-AP-YARD-01", checks["wlan_no_manager"])   # nothing says how it is managed, like the rest
        # It waits in the tray, but the AP register is the inventory: it has a row, uplink "Mesh via" its root.
        row = next(r for r in self.rows("HOSTNAME") if r[0] == "S07-AP-YARD-01")
        self.assertIn("Mesh via S07-AP-WH-", " ".join(row))
        self.assertIn("—", row)

    def test_a_mesh_hop_from_an_ap_in_a_counted_group_starts_at_the_group_card(self):
        # Office and school sheets fold APs into "AP ×8" cards; the root AP is then a group member.
        template = sync.default_template()
        export = s07_export()
        report = sync.fill(template, export, today="2026-10-16")
        sheet = template.find("diagram[@id='wireless']")
        g = Graph(sheet)
        g.remove([i for i, el in g.els.items() if (i or "").startswith("wireless-nbradio")])
        root = next(i for i, el in g.els.items() if el.get("name") == "S07-AP-WH-02")
        g.els[root].set("name", "S07-AP-WH-01")
        g.els[root].set("netdiagrams_group", "S07-AP-WH-02")
        report.added_wireless_links = []
        sync.wireless_page.add_links(g, sync.NetBoxIndex(export), report, sync._is_device)
        edges = [c for c in sheet.iter("mxCell") if c.get("parent") == "wireless-nbradio" and c.get("edge") == "1"]
        self.assertIn("S07-MESH", report.added_wireless_links)
        self.assertTrue(any(root in (e.get("source"), e.get("target")) for e in edges))

    def test_a_ptp_link_without_an_ssid_still_matches_the_drawn_line(self):
        self.assertEqual(len(self.report.matched_wireless), 1)
        rows = {r[0]: r for r in self.rows("LINK")}
        self.assertEqual(list(rows), ["Link 2"])
        self.assertEqual(rows["Link 2"][5], "350 m")
        self.assertIn("ath0", rows["Link 2"][1])

    def test_the_new_wireless_gaps_are_found_and_scored(self):
        checks = {c.key: c for c in self.report.quality.checks}
        self.assertEqual(checks["wlan_no_vlan"].names, ["LEGACY-IOT"])
        self.assertEqual(checks["wlan_review_open"].names, ["OPEN-LAB"])      # open on an OT VLAN
        self.assertEqual(checks["wlan_review_psk"].names, ["SCANNERS"])       # PSK on an OT VLAN
        self.assertEqual(checks["wlan_guest_controls"].names, ["VISITOR"])
        self.assertEqual(checks["wgb_no_link"].names, ["S07-WGB-AGV-01"])
        self.assertEqual(len(checks["wlan_no_fields"].names), 5)
        self.assertEqual(sorted(checks["wlan_no_manager"].names)[:2], ["S07-AP-C02-01", "S07-AP-OF-01"])
        self.assertEqual(checks["no_wireless_links"].names, ["S07-PTP-PH-A", "S07-PTP-PH-B"])
        # The template's example names are listed for the reader but never cost points.
        self.assertEqual(checks["template_examples"].total, 0)
        self.assertIn("S07-WLC", checks["template_examples"].names)
        self.assertEqual(len([c for c in self.sheet.iter("object") if (c.get("id") or "").startswith("wireless-gaps-card")]) > 0, True)
        self.assertIn("Template examples still on this page", page_text(self.sheet))

    def test_a_rebuild_from_the_built_drawing_is_stable(self):
        import copy
        first = copy.deepcopy(self.template)
        sync.fill(first, self.export, today="2026-10-16")
        second = copy.deepcopy(first)
        sync.fill(second, self.export, today="2026-10-16")
        self.assertEqual(ET.tostring(first, encoding="unicode"), ET.tostring(second, encoding="unicode"))

    def test_the_aps_by_area_register_reads_from_locations(self):
        rows = {r[0]: r for r in self.rows("AREA") if len(r) == len(sync.wireless_page.AREA_COLUMNS)}
        self.assertIn("Yard", rows)
        self.assertEqual(rows["Office"][1], "5")
        self.assertEqual(rows["Office"][4], "STAFF · VISITOR")


class WirelessCloud(unittest.TestCase):
    """Cloud-managed APs: the site's field names the dashboard, and the sheet stops saying Cisco WLAN."""

    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, s07_export("cloud"), today="2026-10-16")
        cls.sheet = cls.template.find("diagram[@id='wireless']")

    def test_the_card_the_flows_and_the_sheet_name_follow_the_dashboard(self):
        self.assertEqual(self.report.wireless_management, "Cloud management · Meraki Dashboard")
        text = page_text(self.sheet)
        self.assertIn("Meraki Dashboard", text)
        self.assertNotIn("(another site)", text)
        self.assertIn("Meraki Dashboard (cloud)", self.sheet.get("name"))
        self.assertNotIn("Cisco WLAN", self.sheet.get("name"))
        g = Graph(self.sheet)
        flows = next(t for t in g.tables() if g.header(t)[:2] == ["ID", "FLOW"])
        cells = [plain(g.value(g.els[c])) for r in g.rows(flows)[1:] for c in g.row_cells(r) if isinstance(c, str)]
        self.assertIn("AP → cloud management", cells)
        self.assertFalse([c for c in cells if c.startswith("CAPWAP")])

    def test_the_on_prem_sample_keeps_the_template_names(self):
        template = sync.default_template()
        report = sync.fill(template, sample_export(), today="2026-10-16")
        sheet = template.find("diagram[@id='wireless']")
        self.assertIn(sync.wireless_page.TEMPLATE_SHEET, sheet.get("name"))
        self.assertEqual(report.wireless_management, "")
        self.assertFalse([o for o in sheet.iter("object") if o.get(sync.wireless_page.MGMT_MARK) is not None])
        self.assertEqual(report.removed_cards, [])
        self.assertEqual(report.template_leftovers, {})
        g = Graph(sheet)
        ssid = next(t for t in g.tables() if g.header(t)[:1] == ["SSID"])
        rows = {plain(g.value(g.els[g.row_cells(r)[0]])): [plain(g.value(g.els[c])) for c in g.row_cells(r)]
                for r in g.rows(ssid)[1:]}
        self.assertEqual(rows["CORP"][2], "S01-WLC-01")
        self.assertEqual(rows["C02-AGV"][5], "Local switching")
        self.assertIn("client isolation", rows["GUEST"][8])
        aps = next(t for t in g.tables() if g.header(t)[:1] == ["HOSTNAME"])
        header = g.header(aps)
        row = next([plain(g.value(g.els[c])) for c in g.row_cells(r)] for r in g.rows(aps)[1:]
                   if plain(g.value(g.els[g.row_cells(r)[0]])) == "S01-AP-C02-01")
        self.assertEqual(row[header.index("MODE")], "Local switching (FlexConnect)")
        self.assertEqual(row[header.index("CONTROLLER")], "S01-OT-WLC-01")
        self.assertEqual(row[header.index("POWER")], "802.3at (Type 2)")
        self.assertNotIn("‹serial›", row[header.index("SERIAL")])
        # The WGB's association is a wireless link now, so it is no longer a gap.
        self.assertEqual([c.names for c in report.quality.checks if c.key == "wgb_no_link"], [[]])


class WirelessSafety(unittest.TestCase):
    """Keys never travel, setup creates the fields, the import files carry the gaps, odd exports don't break."""

    def test_exports_never_carry_a_pre_shared_key(self):
        client = NetBoxClient("https://nb.example.com/", "t")

        def fake_get(url):
            if "status" in url:
                return {"netbox-version": "4.4.1"}
            if "dcim/sites" in url:
                return {"results": [{"id": 7, "slug": "s01", "name": "Plant A"}], "next": None}
            if "wireless-lans" in url:
                return {"results": [{"id": 1, "ssid": "IOT", "auth_psk": "sekrit-1234", "vlan": None,
                                     "custom_fields": {"wlan_psk_hint": "nope"}}], "next": None}
            return {"results": [], "next": None}

        with mock.patch.object(client, "get", side_effect=fake_get):
            data = client.export_site("s01")
        text = json.dumps(data)
        self.assertNotIn("sekrit", text)
        self.assertNotIn("psk", text.lower())
        self.assertEqual(data["wireless_lans"][0]["ssid"], "IOT")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "e.json"
            path.write_text(json.dumps({"devices": [], "wireless_lans": [{"id": 1, "ssid": "X", "auth_psk": "sekrit"}]}))
            self.assertNotIn("sekrit", json.dumps(netbox.load_export(path)))

    def test_share_reports_a_key_left_on_a_shape(self):
        mxfile = sync.default_template()
        sync.fill(mxfile, s07_export(), today="2026-10-16")
        card = next(o for o in mxfile.find("diagram[@id='wireless']").iter("object") if o.get("name") == "S07-AP-OF-01")
        card.set("auth_psk", "hunter2-secret-key")
        caption = next(o for o in mxfile.find("diagram[@id='wireless']").iter() if o.get("id") == "wireless-c32")
        key = "label" if caption.tag == "object" else "value"
        caption.set(key, (caption.get(key) or "") + " · key hunter2-secret-key")
        self.assertEqual(share.secrets(mxfile).get("hunter2-secret-key"), "auth psk")
        report = share.share(mxfile, audience="vendor")
        self.assertIsNone(card.get("auth_psk"))                       # the attribute is stripped...
        self.assertNotIn("hunter2", ET.tostring(mxfile, encoding="unicode"))   # ...the caption is redacted...
        self.assertGreaterEqual(report.redacted, 1)
        self.assertEqual(report.leaks, [])                             # ...and the copy is clean

    def test_netbox_setup_writes_the_wireless_fields_and_choice_sets_once(self):
        files = netbox_setup.setup_files(sync.default_template())
        fields = list(__import__("csv").DictReader(io.StringIO(files["2-custom-fields.csv"])))
        names = [f["name"] for f in fields]
        for name in ("wlan_security", "wlan_switching", "wlan_bands", "ap_mode", "wireless_controller",
                     "wireless_management", "wireless_manager", "wireless_survey"):
            self.assertIn(name, names)
        self.assertEqual(len(names), len(set(names)))
        controller = next(f for f in fields if f["name"] == "wireless_controller")
        self.assertEqual((controller["type"], controller["related_object_type"]), ("object", "dcim.device"))
        bands = next(f for f in fields if f["name"] == "wlan_bands")
        self.assertEqual(bands["type"], "multiselect")
        self.assertIn("Wireless security", files["1-custom-field-choice-sets.csv"])
        self.assertIn("Wireless management", files["1-custom-field-choice-sets.csv"])
        plan = netbox_setup.plan(files, "4.2.5")
        step = next(s for s in plan if s.label == "custom field wireless_controller")
        self.assertEqual(step.payload["related_object_type"], "dcim.device")

    def test_gap_files_cover_wireless_lans_access_points_and_links_without_the_key(self):
        export = s07_export()
        locations = ot.Locations(export.get("locations"))
        found = gaps.find(export, sync.ENDPOINT_ROLES, lambda d: ot.device_zones(d, locations), "2026-10-16")
        files = worksheets.files(export, found)
        self.assertIn("7-wireless-lans.csv", files)
        self.assertIn("8-new-wireless-links.csv", files)
        self.assertIn("6-access-points.csv", files)
        self.assertNotIn("hunter2", files["7-wireless-lans.csv"])
        self.assertNotIn("psk", files["7-wireless-lans.csv"].splitlines()[0])
        self.assertIn("4,LEGACY-IOT,,wpa-personal", files["7-wireless-lans.csv"])
        self.assertIn("S07-WGB-AGV-01,radio0", files["8-new-wireless-links.csv"])
        self.assertIn("S07-AP-OF-01", files["6-access-points.csv"])
        self.assertIn("7-wireless-lans.csv", worksheets.GUIDE)

    def test_intake_keeps_only_links_with_an_end_at_the_site(self):
        export = s07_export()
        export["wireless_links"].append({"id": 9, "ssid": "ELSEWHERE", "status": {"value": "connected"},
                                         "interface_a": {"device": {"id": 9999, "name": "S99-PTP-A"}, "name": "ath0"},
                                         "interface_b": {"device": {"id": 9998, "name": "S99-PTP-B"}, "name": "ath0"}})
        intake._site_wireless_links(export)
        self.assertEqual([w["id"] for w in export["wireless_links"]], [1, 2])

    def test_a_ptp_radio_has_its_own_stencil(self):
        self.assertEqual(stencils.shape_for_role("ptp-radio"), "PtP radio (asset)")
        self.assertIn("PtP radio (asset)", stencils.library())

    def test_an_export_that_lost_its_aps_but_kept_their_radios_still_builds(self):
        export = s07_export()
        export["devices"] = [d for d in export["devices"] if d["role"]["slug"] != "access-point"]
        template = sync.default_template()
        report = sync.fill(template, export, today="2026-10-16")
        sheet = template.find("diagram[@id='wireless']")   # the radios and the bridge keep the sheet
        self.assertIsNotNone(sheet)
        self.assertEqual(len(report.matched_wireless), 1)
        self.assertFalse([o for o in sheet.iter("object") if o.get("name") == "S07-AP-OF-01"])

    def test_floors_straight_under_a_site_form_one_building(self):
        export = sample_export()
        export["site"]["name"] = "Head office"
        export["locations"] = [{"id": 1, "name": "Floor 2", "slug": "floor-2", "parent": None},
                               {"id": 2, "name": "COMMS-2", "slug": "comms-2", "parent": {"id": 1}},
                               {"id": 3, "name": "Floor 3", "slug": "floor-3", "parent": None},
                               {"id": 4, "name": "IDF-3", "slug": "idf-3", "parent": {"id": 3}}]
        for d in export["devices"]:
            if d["name"] in ("S01-IT-ACC-IDF1-1", "S01-IT-ACC-IDF1-2"):
                d["location"] = {"id": 2, "name": "COMMS-2", "slug": "comms-2"}
            elif d["name"] in ("S01-IT-ACC-IDF2-1", "S01-IT-CORE-1"):
                d["location"] = {"id": 4, "name": "IDF-3", "slug": "idf-3"}
        buildings = riser.tree(export)
        self.assertEqual([b.name for b in buildings], ["Head office"])
        self.assertEqual([c.name for c in buildings[0].children], ["Floor 2", "Floor 3"])
        self.assertTrue(riser.wanted(export, sync.ENDPOINT_ROLES))
        sheet = riser.page(export, sync.ENDPOINT_ROLES, "https://netbox.example", "S01")
        text = page_text(sheet)
        self.assertIn("1 building · 2 floors", text)
        self.assertNotIn("Floor 2 (building)", text)
        # A sole campus root over real buildings is still a campus.
        self.assertEqual(sorted(b.name for b in riser.tree(campus_export())), ["Admin building", "Production building"])


class BookThreadFixes(unittest.TestCase):
    """Small core defects the book threads found while rebasing on the wireless batch."""

    def test_a_table_with_no_card_does_not_grow_the_page_frame(self):
        page = ET.fromstring(
            '<diagram id="t" name="p"><mxGraphModel pageWidth="2000" pageHeight="800"><root><mxCell id="0"/>'
            '<mxCell id="1" value="Main" parent="0"/>'
            '<mxCell id="frame" vertex="1" parent="1" style="rounded=1;"><mxGeometry x="10" y="10" width="1980" height="780" as="geometry"/></mxCell>'
            '<mxCell id="tbl" vertex="1" parent="1" style="shape=table;"><mxGeometry x="40" y="40" width="200" height="40" as="geometry"/></mxCell>'
            '<mxCell id="h" vertex="1" parent="tbl" style="shape=tableRow;"><mxGeometry y="0" width="200" height="20" as="geometry"/></mxCell>'
            '<mxCell id="hc" value="NAME" vertex="1" parent="h" style="shape=partialRectangle;fontSize=9;"><mxGeometry width="200" height="20" as="geometry"/></mxCell>'
            '<mxCell id="r" vertex="1" parent="tbl" style="shape=tableRow;"><mxGeometry y="20" width="200" height="20" as="geometry"/></mxCell>'
            '<mxCell id="rc" value="x" vertex="1" parent="r" style="shape=partialRectangle;fontSize=9;"><mxGeometry width="200" height="20" as="geometry"/></mxCell>'
            '<mxCell id="under" vertex="1" parent="1"><mxGeometry x="40" y="100" width="50" height="20" as="geometry"/></mxCell>'
            '<mxCell id="room" vertex="1" parent="1"><mxGeometry x="900" y="100" width="50" height="20" as="geometry"/></mxCell>'
            '</root></mxGraphModel></diagram>')
        g = Graph(page)
        g.fill_table("tbl", [[("a", "")], [("b", "")], [("c", "")]])
        self.assertEqual(g.geometry("frame").get("height"), "780")   # the frame is not the table's card
        self.assertEqual(g.geometry("room").get("y"), "100")         # a room beside the table stays put
        self.assertEqual(g.geometry("under").get("y"), "140")        # what is under the table moves

    def test_the_link_register_leaves_out_the_profile_end_devices(self):
        export = sample_export()
        nb = sync.NetBoxIndex(export)
        self.assertTrue(sync._infrastructure(nb, "S01-IT-CORE-1"))
        self.assertFalse(sync._infrastructure(nb, "S01-C01-PLC01"))
        self.assertTrue(sync._infrastructure(nb, "S01-FW-EDGE-01"))
        shop = dataclasses.replace(profiles.MANUFACTURING, name="test-shop", endpoint_roles=("firewall",))
        with profiles.use(shop):
            self.assertFalse(sync._infrastructure(nb, "S01-FW-EDGE-01"))   # a profile's end device, not a link row

    def test_shift_below_leaves_a_full_width_band_in_place(self):
        page = ET.fromstring(
            '<diagram name="p"><mxGraphModel pageHeight="500"><root><mxCell id="0"/>'
            '<mxCell id="1" parent="0"/>'
            '<mxCell id="band" vertex="1" parent="1"><mxGeometry x="0" y="200" width="2000" height="20" as="geometry"/></mxCell>'
            '<mxCell id="caption" vertex="1" parent="1"><mxGeometry x="90" y="200" width="140" height="20" as="geometry"/></mxCell>'
            '<mxCell id="box" vertex="1" parent="1"><mxGeometry x="110" y="240" width="50" height="20" as="geometry"/></mxCell>'
            '</root></mxGraphModel></diagram>')
        g = Graph(page)
        g.shift_below(100, 200, 100, 30, set())
        self.assertEqual(g.geometry("band").get("y"), "200")      # spans the page: not this column's
        self.assertEqual(g.geometry("caption").get("y"), "230")   # a little wider than the column: moves
        self.assertEqual(g.geometry("box").get("y"), "270")

    def test_radio_text_does_not_repeat_what_the_channel_label_says(self):
        def radio(**rf):
            export = {"devices": [{"id": 1, "name": "AP", "role": {"slug": "access-point"}}],
                      "interfaces": [{"id": 1, "device": {"name": "AP"}, "name": "radio0",
                                      "type": {"value": "ieee802.11ax"}, **rf}]}
            return wireless.Index(export, set()).radio_text("AP", "radio0")
        self.assertEqual(radio(rf_channel={"value": "5g-36-40", "label": "36 (5180/40 MHz)"},
                               rf_channel_frequency=5180, rf_channel_width=40, tx_power=14),
                         "ch 36 (5180/40 MHz) · 14 dBm")
        self.assertEqual(radio(rf_channel={"value": "36", "label": "36"}, rf_channel_frequency=5180,
                               rf_channel_width=40), "ch 36 · 5180 MHz · 40 MHz wide")
        # A 60 GHz label gives the frequency in GHz with a decimal point: still said once.
        self.assertEqual(radio(rf_channel={"value": "60g-2-60480-2160", "label": "2 (60.48/2160 GHz)"},
                               rf_channel_frequency=60480, rf_channel_width=2160, tx_power=11),
                         "ch 2 (60.48/2160 GHz) · 11 dBm")

    def test_the_survey_link_goes_on_a_caption_not_a_layer_named_like_it(self):
        export = s07_export()
        export["site"]["custom_fields"] = {"wireless_survey": "https://docs.example/survey-2026.pdf"}
        template = sync.default_template()
        sheet = template.find("diagram[@id='wireless']")
        layer = next(c for c in sheet.iter("mxCell") if c.get("parent") == "0" and c.get("value") == "Zones & groups")
        layer.set("value", "AP placement")
        sync.fill(template, export, today="2026-10-16")
        sheet = template.find("diagram[@id='wireless']")
        layers = [c.get("value") for c in sheet.iter("mxCell") if c.get("parent") == "0"]
        self.assertIn("AP placement", layers)
        self.assertFalse([v for v in layers if v and "<a " in v])
        holders = [el for el in sheet.iter() if "survey-2026" in (el.get("value") or el.get("label") or "")]
        self.assertEqual(len(holders), 1)
        self.assertEqual(holders[0].find("mxCell").get("vertex") if holders[0].tag == "object" else holders[0].get("vertex"), "1")

    def test_a_riser_run_label_sits_on_its_first_stretch_not_the_shaft(self):
        export = sample_export()
        export["locations"] = [{"id": 1, "name": "Floor 2", "slug": "floor-2", "parent": None},
                               {"id": 2, "name": "COMMS-2", "slug": "comms-2", "parent": {"id": 1}},
                               {"id": 3, "name": "Floor 3", "slug": "floor-3", "parent": None},
                               {"id": 4, "name": "IDF-3", "slug": "idf-3", "parent": {"id": 3}}]
        for d in export["devices"]:
            if d["name"].startswith("S01-IT-ACC-IDF1"):
                d["location"] = {"id": 2, "name": "COMMS-2", "slug": "comms-2"}
            elif d["name"].startswith("S01-IT-CORE"):
                d["location"] = {"id": 4, "name": "IDF-3", "slug": "idf-3"}
        sheet = riser.page(export, sync.ENDPOINT_ROLES, "https://netbox.example", "S01")
        runs = [o for o in sheet.iter("object") if o.get("netdiagrams_cables")]
        self.assertTrue(runs)
        geometry = runs[0].find("mxCell/mxGeometry")
        points = [(float(p.get("x")), float(p.get("y"))) for p in geometry.iter("mxPoint")]
        self.assertEqual(len(points), 4)                       # lift, shaft down, lift at the other floor
        self.assertLess(float(geometry.get("x")), -0.3)        # well before the middle, on the first stretch
        self.assertLess(float(geometry.get("y")), -10)         # lifted clear of the card's stacked lines

    def test_runs_leaving_one_card_stack_their_labels_apart(self):
        export = campus_export()
        sheet = riser.page(export, sync.ENDPOINT_ROLES, "https://netbox.example", "S01")
        by_end: dict = {}
        for o in sheet.iter("object"):
            if not (o.get("netdiagrams_cables") or o.get("netdiagrams_radio")):
                continue
            cell = o.find("mxCell")
            geometry = cell.find("mxGeometry")
            key = (cell.get("source") if float(geometry.get("x", 0)) < 0 else cell.get("target"),
                   geometry.get("x"), geometry.get("y"))
            self.assertNotIn(key, by_end, "two labels at the same spot on one card")
            by_end[key] = o.get("label")
        offsets = {abs(float(y)) for _, _, y in by_end}
        self.assertGreater(len(offsets), 1)   # labels at a shared card sit at different heights

    def test_an_ap_on_its_own_switch_is_not_folded_by_zone_alone(self):
        export = sample_export()
        new = json.loads(json.dumps(next(d for d in export["devices"] if d["name"] == "S01-AP-OF-01")))
        new.update(id=9901, name="S01-AP-PORTABLE-01", location={"id": 9902, "name": "Portable P1", "slug": "p1"},
                   serial="PORT0001", asset_tag=None, primary_ip4=None)
        export["devices"].append(new)       # same zone as the office APs, no cable, another room
        template = sync.default_template()
        report = sync.fill(template, export, today="2026-10-16")
        self.assertFalse([h for h, members in report.grouped.items() if "S01-AP-PORTABLE-01" in members])
        self.assertIn("S01-AP-PORTABLE-01", report.netbox_only_devices)
        self.assertEqual(report.wireless_tray, ["S01-AP-PORTABLE-01"])
        sheet = template.find("diagram[@id='wireless']")
        heading = next(c for c in sheet.iter("mxCell") if (c.get("id") or "").endswith("-unplaced-title"))
        self.assertIn("1 device · drag it into place", heading.get("value"))
        # A PLC in the same zone still folds into a drawn PLC (the zone test stays for wired end devices).
        plc = json.loads(json.dumps(next(d for d in export["devices"] if d["name"] == "S01-C01-PLC01")))
        plc.update(id=9903, name="S01-C01-PLC09", serial="PLC0009", asset_tag=None, primary_ip4=None, location=None)
        export["devices"].append(plc)
        report = sync.fill(sync.default_template(), export, today="2026-10-16")
        self.assertTrue([h for h, members in report.grouped.items() if "S01-C01-PLC09" in members])


class FigureRoundTwoFixes(unittest.TestCase):
    """Non-wireless defects the Book 1 figure review found: stale link pills, inline member serials,
    and a card left behind when its zone card moved."""

    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, sample_export(), today="2026-10-16")
        cls.physical = page(cls.template, "3 ")

    def pill(self, cables, template=None):
        g = page(template, "3 ") if template is not None else self.physical
        return next(el.get("label") for el in g.els.values() if el.get("cable_label") == cables and el.get("label"))

    def test_link_pills_follow_netbox(self):
        self.assertEqual(self.pill("S01-CBL-007, S01-CBL-008"), "Po1 · 2×10G · 181,189 · MMF OM4")
        self.assertEqual(self.pill("S01-CBL-030, S01-CBL-031, S01-CBL-032, S01-CBL-033"), "Po31/32 · 210–249 · Cat6")
        self.assertEqual(self.pill("S01-CBL-048, S01-CBL-049"), "REP 11 · 1G · SMF OS2")  # two ring uplinks, no bundle
        self.assertFalse([c for c in self.report.changes if c[3] == "label"], "the sample is the template's truth")

    def test_a_pill_loses_vlans_netbox_does_not_have(self):
        export = sample_export()
        for i in export["interfaces"]:
            if i["name"] in ("Port-channel1", "Port-channel101") and i["device"]["name"].startswith("S01-IT-CORE-1"):
                i["mode"], i["tagged_vlans"] = None, []
            if i["device"]["name"] == "S01-FW-EDGE-01" and i["name"] == "ae1":
                i["mode"], i["tagged_vlans"] = None, []
        for c in export["cables"]:
            if c["label"] in ("S01-CBL-007", "S01-CBL-008"):
                c["type"] = "smf-os2"
        template = sync.default_template()
        report = sync.fill(template, export, today="2026-10-16")
        self.assertEqual(self.pill("S01-CBL-007, S01-CBL-008", template), "Po1 · 2×10G · SMF OS2")
        self.assertIn(("3 · Physical — Devices, Uplinks, Trunks", "cable", "S01-CBL-007, S01-CBL-008", "label",
                       "Po1 · 2×10G · 181,189 · MMF OM4", "Po1 · 2×10G · SMF OS2"), report.changes)
        rows = table_rows(page(template, "3 "), "LINK")
        self.assertEqual(next(r for r in rows if r[0] == "Po1")[-1], "—")

    def test_compact_vlan_lists(self):
        self.assertEqual(sync.compact_vids([189, 181]), "181,189")
        self.assertEqual(sync.compact_vids([10, 11, 20, 30, 99], ", "), "10, 11, 20, 30, 99")
        rows = table_rows(self.physical, "LINK")
        self.assertEqual(next(r for r in rows if r[0] == "Po21")[-1], "392, 399, 519, 529, 539, 590",
                         "the register's list has spaces so a long one wraps inside its cell")
        self.assertEqual(sync.compact_vids(range(210, 250)), "210–249")
        self.assertEqual(sync.compact_vids([10, 11, 20, 21, 22, 30]), "10,11,20–22,30")

    def test_stack_member_serials_sit_on_the_serial_layer(self):
        g = self.physical
        self.assertFalse([el for el in g.els.values() if "SN %serial%" in (el.get("label") or "")])
        member = g.els["physical-c72"]
        self.assertEqual(member.get("name"), "S01-IT-ACC-IDF1-1")
        self.assertNotIn("SN", plain(g.value(member)))
        tag = next(el for i, el in g.els.items() if el.get("netdiagrams_ref") == "physical-c72"
                   and el.get("netdiagrams_field") == "serial")
        self.assertEqual(g.layer_of(tag.get("id")), "3b · Serial numbers")
        self.assertEqual(plain(g.value(tag)), "SN " + member.get("serial"))
        x, y, w, h = g.box("physical-c72")
        tx, ty, tw, th = g.box(tag.get("id"))
        self.assertTrue(x < tx and tx + tw <= x + w and y <= ty and ty + th <= y + h, "the tag sits inside the row")

    def test_an_inline_serial_in_a_hand_made_template_is_lifted(self):
        diagram = ET.fromstring(
            '<diagram id="t" name="3 · Physical"><mxGraphModel pageWidth="1000" pageHeight="800"><root><mxCell id="0"/>'
            '<mxCell id="1" value="Devices" parent="0"/><mxCell id="L6" value="3b · Serial numbers" parent="0"/>'
            '<object id="sw" name="S01-IT-ACC-IDF1-1" role="access-switch" serial="FOCxxxxx11" position="42" placeholders="1"'
            ' label="&lt;b&gt;Sw1&lt;/b&gt; · active &lt;span&gt;&amp;nbsp;U%position% · SN %serial%&lt;/span&gt;">'
            '<mxCell vertex="1" parent="1" style="shape=label;"><mxGeometry x="100" y="100" width="230" height="22" as="geometry"/></mxCell></object>'
            '</root></mxGraphModel></diagram>')
        g = Graph(diagram)
        sync._lift_inline_serials(g)
        self.assertEqual(g.els["sw"].get("label"), "<b>Sw1</b> · active <span>&nbsp;U%position%</span>")
        tag = g.els["sw-tag-serial"]
        self.assertEqual((tag.get("label"), tag.get("netdiagrams_format"), g.layer_of("sw-tag-serial")),
                         ("SN FOCxxxxx11", "SN {}", "3b · Serial numbers"))
        self.assertEqual(g.box("sw-tag-serial"), (226.0, 104.0, 98.0, 14.0))

    def test_a_card_inside_a_moved_card_moves_with_it(self):
        page_xml = ET.fromstring(
            '<diagram name="p"><mxGraphModel pageHeight="900"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
            '<mxCell id="zone" vertex="1" parent="1"><mxGeometry x="600" y="300" width="500" height="300" as="geometry"/></mxCell>'
            '<mxCell id="l0" vertex="1" parent="1"><mxGeometry x="1000" y="400" width="80" height="40" as="geometry"/></mxCell>'
            '<mxCell id="beside" vertex="1" parent="1"><mxGeometry x="1000" y="700" width="80" height="40" as="geometry"/></mxCell>'
            '</root></mxGraphModel></diagram>')
        g = Graph(page_xml)
        g.shift_below(80, 980, 200, 31, set())
        self.assertEqual(g.geometry("zone").get("y"), "331")
        self.assertEqual(g.geometry("l0").get("y"), "431", "inside the zone card, so it moves with it")
        self.assertEqual(g.geometry("beside").get("y"), "700", "outside the column and outside any moved card")

    def test_text_is_measured_with_inter_widths(self):
        from netdiagrams import graph as graph_mod
        # Bold hostnames measure bold, and break after a hyphen as the browser does.
        self.assertGreater(graph_mod.text_width("W01-IT-ACC-IDF2-2", 9, bold=True),
                           graph_mod.text_width("W01-IT-ACC-IDF2-2", 9))
        self.assertEqual(graph_mod.text_lines("W01-IT-ACC-IDF2-2", 90, 9, bold=True), 2)
        self.assertEqual(graph_mod.row_height([("W01-IT-ACC-IDF2-2", 90, True)], 9, 22), 29)
        self.assertEqual(graph_mod.row_height([("W01-IT-ACC-IDF2-2", 100, True)], 9, 22), 22)
        # The class-average guess said this NAME fitted its 124 px cell; drawn in Inter it wraps,
        # and the row was clipped. Measured widths grow the row instead.
        self.assertGreater(graph_mod.text_width("WH-SCAN · SSID WH-SCAN", 10), 124 - 8)
        self.assertEqual(graph_mod.text_lines("WH-SCAN · SSID WH-SCAN", 124, 10), 2)
        logical = page(self.template, "2 ")
        row = next(logical.els[c].find("mxCell").get("parent") for c in logical.els
                   if plain(logical.value(logical.els[c])) == "WH-SCAN · SSID WH-SCAN")
        self.assertEqual(logical.box(row)[3], 31.0)
        self.assertEqual(len(self.template.findall("diagram")), 13, "Plant A's registers still fit their sheet")

    def test_the_l0_card_keeps_its_row_under_a_wrapped_vlan_name(self):
        logical = page(self.template, "2 ")
        cards = {plain(logical.value(logical.els[i]))[:2]: logical.box(i)[1] for i in ("logical-c279", "logical-c280", "logical-c281")}
        self.assertEqual(len(set(cards.values())), 1, cards)
        table_bottom = logical.box("logical-c258")[1] + logical.box("logical-c258")[3]
        self.assertGreater(cards["L0"], table_bottom)


class ModulesAndInventory(unittest.TestCase):
    """What sits inside a device comes from NetBox: modules in bays, PSUs, fans and the optic in each port."""

    @classmethod
    def setUpClass(cls):
        cls.export = sample_export()
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, cls.export, today="2026-10-17")
        cls.hardware = page(cls.template, "3b")

    def register(self, g, first):
        return next((t for t in g.tables() if g.header(t)[:1] == [first]), None)

    def rows(self, g, first):
        return {r[0]: r for r in table_rows_by_id(g, self.register(g, first))}

    def filled(self, export):
        template = sync.default_template()
        report = sync.fill(template, export, today="2026-10-17")
        return page(template, "3b"), report

    def found(self, export):
        locations = ot.Locations(export.get("locations"))
        return gaps.find(export, sync.ENDPOINT_ROLES, lambda d: ot.device_zones(d, locations), "2026-10-17")

    def test_export_reads_modules_bays_and_items_per_device(self):
        from netdiagrams import netbox
        self.assertEqual(set(netbox.PER_DEVICE) >= {"modules", "module_bays", "inventory_items"}, True)
        self.assertTrue(self.export["modules"] and self.export["module_bays"] and self.export["inventory_items"])

    def test_optics_register_names_the_transceiver_in_each_end(self):
        rows = self.rows(self.hardware, "CABLE ID")
        self.assertIn("S01-CBL-007", rows)
        header = self.hardware.header(self.register(self.hardware, "CABLE ID"))
        a_optic, b_optic = header.index("A OPTIC"), header.index("B OPTIC")
        self.assertEqual(rows["S01-CBL-007"][a_optic], "SFP-10G-SR-S")
        self.assertEqual(rows["S01-CBL-007"][b_optic], "SFP-10G-SR-S")
        self.assertNotIn("?", [r[a_optic] for r in rows.values()] + [r[b_optic] for r in rows.values()])

    def test_a_fibre_end_without_a_transceiver_shows_a_gap(self):
        export = copy.deepcopy(self.export)
        export["inventory_items"] = [i for i in export["inventory_items"]
                                     if not (i["device"]["name"] == "S01-FW-EDGE-01" and (i.get("component") or {}).get("name") == "ethernet1/19")]
        g, report = self.filled(export)
        rows = self.rows(g, "CABLE ID")
        self.assertEqual(rows["S01-CBL-007"][3], "?")
        found = self.found(export)
        self.assertIn("S01-CBL-007 S01-FW-EDGE-01 ethernet1/19", found["fibre_no_optic"].names)
        files = worksheets.files(export, found)
        self.assertIn("S01-FW-EDGE-01,,transceiver,,,dcim.interface,ethernet1/19", files["11-new-optics.csv"])

    def test_modules_register_lists_a_stack_as_one_row_with_its_bays(self):
        rows = self.rows(self.hardware, "DEVICE")
        self.assertIn("S01-IT-ACC-IDF1", rows)
        self.assertNotIn("S01-IT-ACC-IDF1-1", rows)
        self.assertIn("C9300-NM-8X", rows["S01-IT-ACC-IDF1"][3])
        self.assertIn("C9300-NM-BLANK", rows["S01-IT-ACC-IDF1"][3])
        self.assertEqual(rows["S01-IT-ACC-IDF1"][2], "2× PWR-C1-1100WAC-P per member")
        self.assertEqual(rows["S01-FW-EDGE-01/02"][2], "2× AC PSU")   # identical boxes share a row
        self.assertIn("S01-C01-IE01 … S01-C03-IE03 (9)", rows)
        self.assertTrue(any(r[1].startswith("Not recorded in NetBox") for r in rows.values()))

    def test_the_not_recorded_row_fits_its_cell_and_keeps_the_list_in_the_tooltip(self):
        export = copy.deepcopy(self.export)
        keep = {"S01-IT-CORE-1", "S01-IT-CORE-2"}
        for key in ("modules", "module_bays", "inventory_items"):
            export[key] = [o for o in export[key] if o["device"]["name"] in keep]
        g, _ = self.filled(export)
        table = self.register(g, "DEVICE")
        row = next(r for r in g.rows(table) if plain(g.value(g.els[g.row_cells(r)[0]])) == "?")
        cell = g.els[g.row_cells(row)[1]]
        text, width = g.value(cell), float(g.geometry(g.row_cells(row)[1]).get("width"))
        self.assertTrue(text.startswith("Not recorded in NetBox: "))
        self.assertIn("more", text)
        self.assertLessEqual(graph_mod_text_lines(text, width), 2)
        self.assertIn("S01-WLC-02", cell.get("tooltip") or "")

    def test_an_empty_bay_is_amber_and_a_site_without_records_says_so(self):
        export = copy.deepcopy(self.export)
        export["modules"] = [m for m in export["modules"] if m["device"]["name"] != "S01-IDMZ-SW-01"]
        for bay in export["module_bays"]:
            if bay["device"]["name"] == "S01-IDMZ-SW-01":
                bay["installed_module"] = None
        g, _ = self.filled(export)
        rows = self.rows(g, "DEVICE")
        self.assertEqual(rows["S01-IDMZ-SW-01"][3], "Network Module empty")
        table = self.register(g, "DEVICE")
        raw = " ".join(g.value(g.els[c]) for r in g.rows(table) for c in g.row_cells(r))
        self.assertIn('<font color="#B45309">Network Module empty</font>', raw)
        for key in ("modules", "module_bays", "inventory_items"):
            export[key] = []
        g, _ = self.filled(export)
        self.assertEqual(list(self.rows(g, "DEVICE").values())[0][1], "No modules or inventory items in NetBox yet")

    def test_port_cell_and_footer_follow_the_inventory_items(self):
        export = copy.deepcopy(self.export)
        for i in export["inventory_items"]:
            if i["device"]["name"] == "S01-IT-CORE-1" and (i.get("component") or {}).get("name") == "TwentyFiveGigE1/0/1":
                i["part_id"] = i["name"] = "SFP-10G-LR-S"
            if i["device"]["name"] == "S01-FW-ITOT-01" and i["role"]["slug"] == "psu":
                i["name"] = "PA-450 redundant PSU"
        g, report = self.filled(export)
        cell = next(el for el in g.els.values() if el.get("device") == "S01-IT-CORE-1" and el.get("name") == "TwentyFiveGigE1/0/1")
        self.assertEqual(cell.get("x_optic"), "SFP-10G-LR-S")
        self.assertTrue(cell.get("x_optic_serial", "").startswith("AV"))
        self.assertTrue(cell.get("label", "").rstrip().endswith("LR</span>"), cell.get("label"))
        footers = [plain(g.value(el)) for el in g.els.values() if g.value(el).startswith("<b>Power</b>")]
        self.assertTrue(any(f.startswith("Power PA-450 redundant PSU") for f in footers), footers)
        self.assertFalse([c for c in report.changes if c[3] == "x_optic_serial"])   # filling a ‹serial› blank is not drift

    def test_missing_serials_are_gaps_with_import_files(self):
        export = copy.deepcopy(self.export)
        module = next(m for m in export["modules"] if m["module_type"]["model"] == "C9300-NM-8X")
        module["serial"] = ""
        psu = next(i for i in export["inventory_items"] if i["role"]["slug"] == "psu" and i["part_id"])
        psu["serial"] = ""
        found = self.found(export)
        self.assertEqual(found["module_no_serial"].names, [f"{module['device']['name']} Network Module C9300-NM-8X"])
        self.assertEqual(found["item_no_serial"].names, [f"{psu['device']['name']} {psu['part_id']}"])
        self.assertFalse([m for m in found["module_no_serial"].names if "BLANK" in m])
        files = worksheets.files(export, found)
        self.assertIn(f"{module['id']},{module['device']['name']},Network Module,C9300-NM-8X,", files["9-modules.csv"])
        self.assertIn(f"{psu['id']},{psu['device']['name']},", files["10-inventory-items.csv"])
        sibling = next(i for i in export["inventory_items"] if i is not psu and i["device"]["name"] == psu["device"]["name"]
                       and i["part_id"] == psu["part_id"])
        self.assertNotIn(f"{sibling['id']},{sibling['device']['name']},", files["10-inventory-items.csv"])
        card = doctor.quality(export)
        totals = {c.key: (c.missing, c.total) for c in card.checks}
        self.assertEqual(totals["module_no_serial"], (1, len(export["modules"])))
        self.assertEqual(totals["fibre_no_optic"][0], 0)

    def test_netbox_setup_adds_the_inventory_item_roles(self):
        files = netbox_setup.setup_files(sync.default_template())
        self.assertIn("5-inventory-item-roles.csv", files)
        slugs = {r["slug"] for r in csv.DictReader(io.StringIO(files["5-inventory-item-roles.csv"]))}
        self.assertEqual(slugs, {"transceiver", "psu", "fan"})
        steps = netbox_setup.plan(files, "4.2.5")
        self.assertIn("dcim/inventory-item-roles", {s.endpoint for s in steps if s.kind == "item_roles"})
        self.assertNotIn("5-inventory-item-roles.csv", netbox_setup.setup_files(
            sync.default_template(), {"item_roles": slugs, "roles": set(), "tags": set(), "custom_fields": set(), "choice_sets": set()}))

    def optics_table(self, template):
        g = page(template, "3b")
        return g, self.register(g, "CABLE ID")

    def test_optics_register_can_hold_fibre_only(self):
        # The switch: netdiagrams_rows="fiber" on the table.
        template = sync.default_template()
        g, table = self.optics_table(template)
        g.wrap(table, netdiagrams_rows="fiber")
        sync.fill(template, self.export, today="2026-10-17")
        g, table = self.optics_table(template)
        media = g.header(table).index("MEDIA")
        rows = table_rows_by_id(g, table)
        self.assertTrue(rows and all(r[media].startswith(("SMF", "MMF")) for r in rows), rows[:3])
        self.assertLess(len(rows), len(self.export["cables"]))
        # The British spelling of the attribute works too.
        template = sync.default_template()
        g, table = self.optics_table(template)
        g.wrap(table, netdiagrams_rows="fibre")
        sync.fill(template, self.export, today="2026-10-17")
        g, table = self.optics_table(template)
        self.assertEqual(len(table_rows_by_id(g, table)), len(rows))
        # Inferred when every row the template drew is fiber, as a register of uplinks is.
        template = sync.default_template()
        g, table = self.optics_table(template)
        for row in g.rows(table)[1:]:
            g.set_value(g.els[g.row_cells(row)[media]], "SMF OS2")
        sync.fill(template, self.export, today="2026-10-17")
        g, table = self.optics_table(template)
        self.assertEqual(len(table_rows_by_id(g, table)), len(rows))
        # "all" forces the full list, placeholders in the template notwithstanding.
        template = sync.default_template()
        g, table = self.optics_table(template)
        g.wrap(table, netdiagrams_rows="all")
        sync.fill(template, self.export, today="2026-10-17")
        g, table = self.optics_table(template)
        self.assertGreater(len(table_rows_by_id(g, table)), len(rows))

    def test_patch_columns_come_from_the_traced_path_or_stay_as_drawn(self):
        template = sync.default_template()
        g, table = self.optics_table(template)
        patch = g.header(table).index("PATCH")
        for row in g.rows(table)[1:]:
            cells = g.row_cells(row)
            if plain(g.value(g.els[cells[0]])) == "CBL-018":
                g.set_value(g.els[cells[patch]], "MDF-FP1:1-2 / IDF1-FP1:1-2")
        export = copy.deepcopy(self.export)
        cable = next(c for c in export["cables"] if c["label"] == "S01-CBL-019")
        cable["x_patch_a"], cable["x_patch_b"] = "MDF-FP2:3-4", "IDF1-FP2:3-4"
        sync.fill(template, export, today="2026-10-17")
        g, table = self.optics_table(template)
        rows = {r[0]: r for r in table_rows_by_id(g, table)}
        self.assertEqual(rows["S01-CBL-018"][patch], "MDF-FP1:1-2 / IDF1-FP1:1-2")   # kept from the drawing
        self.assertEqual(rows["S01-CBL-019"][patch], "MDF-FP2:3-4 · IDF1-FP2:3-4")   # NetBox's path wins
        self.assertEqual(rows["S01-CBL-020"][patch], "—")                             # a ‹panel› placeholder is not kept
        # A register with PATCH A / PATCH B columns gets one side each: rebuild from this output keeps the text.
        rebuilt = copy.deepcopy(template)
        sync.fill(rebuilt, self.export, today="2026-10-17")
        g, table = self.optics_table(rebuilt)
        rows = {r[0]: r for r in table_rows_by_id(g, table)}
        self.assertEqual(rows["S01-CBL-019"][patch], "MDF-FP2:3-4 · IDF1-FP2:3-4")

    def test_register_rows_link_to_netbox(self):
        export = copy.deepcopy(self.export)
        export["netbox_url"] = "https://netbox.example.com"
        g, _ = self.filled(export)
        kinds = Counter(re.sub(r"\d+", "N", (el.get("link") or "").replace(export["netbox_url"], "").split("?")[0])
                        for el in g.els.values() if (el.get("link") or "").startswith(export["netbox_url"]))
        cable_rows = len(table_rows_by_id(g, self.register(g, "CABLE ID")))
        module_rows = len(table_rows_by_id(g, self.register(g, "DEVICE")))
        self.assertGreaterEqual(kinds["/dcim/cables/N/"], cable_rows)        # CABLE ID (and LINK) per cable row
        self.assertGreaterEqual(kinds["/dcim/interfaces/N/"], cable_rows)    # the ends that have an interface record
        self.assertGreater(kinds["/dcim/inventory-items/N/"], 0)              # the optics
        self.assertGreaterEqual(kinds["/dcim/devices/N/"] + kinds["/dcim/virtual-chassis/"], module_rows - 1)  # not the ? row
        row = next(r for r in g.rows(self.register(g, "CABLE ID"))[1:])
        self.assertTrue((g.els[g.row_cells(row)[0]].get("link") or "").startswith(export["netbox_url"] + "/dcim/cables/"))

    def test_item_kind_comes_from_role_then_part_number(self):
        self.assertEqual(hardware.kind_of({"role": {"slug": "psu"}, "name": "whatever"}), "power")
        self.assertEqual(hardware.kind_of({"role": None, "part_id": "SFP-10G-SR-S"}), "optic")
        self.assertEqual(hardware.kind_of({"role": None, "part_id": "J4858C", "name": "J4858C"}), "optic")
        self.assertEqual(hardware.kind_of({"role": None, "name": "FAN-T1"}), "fan")
        self.assertEqual(hardware.kind_of({"role": None, "name": "SD-IE-4GB"}), "other")
        self.assertEqual(hardware.short_optic("SFP-10G-SR-S"), "SR")
        self.assertEqual(hardware.short_optic("GLC-TE"), "TE")
        self.assertEqual(hardware.short_optic("QSFP-100G-AOC5M"), "AOC5M")


class AssetCriticality(unittest.TestCase):
    """Auditors ask which assets are critical: a criticality custom field, a pill on the card, a register column, a gap."""

    @classmethod
    def setUpClass(cls):
        cls.export = sample_export()
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, cls.export, today="2026-10-17")
        cls.physical = page(cls.template, "3 ")

    def test_netbox_setup_adds_the_field_and_its_choice_set(self):
        files = netbox_setup.setup_files(sync.default_template())
        fields = {r["name"]: r for r in csv.DictReader(io.StringIO(files["2-custom-fields.csv"]))}
        self.assertEqual(fields["criticality"]["type"], "select")
        self.assertEqual(fields["criticality"]["choice_set"], "Asset criticality")
        self.assertEqual(fields["criticality"]["object_types"], "dcim.device")
        sets = {r["name"]: r["extra_choices"] for r in csv.DictReader(io.StringIO(files["1-custom-field-choice-sets.csv"]))}
        self.assertEqual(sets["Asset criticality"], "critical:Critical,high:High,medium:Medium,low:Low")
        own = netbox_setup.setup_files(sync.default_template(), settings={"criticality_field": ["bia_criticality"]})
        self.assertNotIn("criticality", own.get("2-custom-fields.csv", ""))

    def test_the_register_gets_a_crit_column_and_critical_cards_a_pill(self):
        g = self.physical
        table = next(t for t in g.tables() if "HOSTNAME" in g.header(t) and "SW" in g.header(t))
        header = g.header(table)
        self.assertIn("CRIT", header)
        rows = {r[0]: r for r in table_rows_by_id(g, table)}
        self.assertEqual(rows["S01-IT-CORE-1"][header.index("CRIT")], "Critical")
        self.assertEqual(rows["S01-IT-ACC-IDF1-1"][header.index("CRIT")], "High")
        core = next(i for i, el in g.els.items() if el.get("name") == "S01-IT-CORE-1" and sync._is_device(el))
        self.assertIn(f"{core}-crit", g.els)
        self.assertTrue((g.els[f"{core}-crit"].get("tooltip") or "").startswith("Critical asset"))
        cx, cy, cw, ch = g.box(core)
        mx, my, mw, mh = g.box(f"{core}-crit")
        self.assertTrue(cx <= mx and mx + mw <= cx + cw and cy <= my and my + mh <= cy + ch)   # inside the card: covers nothing
        self.assertEqual(g.layer_of(f"{core}-crit"), sync.CRITICALITY_LAYER)   # a layer, so sharing can drop it
        crit = g.row_cells(g.rows(table)[1])[header.index("CRIT")]
        self.assertNotIn("fontColor", sync.cell_of(g.els[crit]).get("style") or "")
        self.assertIn('<font color="#B91C1C">', g.value(g.els[crit]))
        shared = copy.deepcopy(self.template)
        share.share(shared, audience="vendor")
        self.assertFalse([i for i in page(shared, "3 ").els if i.endswith("-crit")])
        sg = page(shared, "3 ")
        stable = next(t for t in sg.tables() if "HOSTNAME" in sg.header(t) and "SW" in sg.header(t))
        crit_col = sg.header(stable).index("CRIT")
        self.assertEqual({r[crit_col] for r in table_rows_by_id(sg, stable)}, {""})   # the column is blank for a vendor
        managed = copy.deepcopy(self.template)
        share.share(managed, audience="management")
        for d in managed.findall("diagram"):   # whatever pages a management copy keeps, no rating survives
            mg = Graph(d)
            self.assertFalse([i for i in mg.els if i.endswith("-crit")])
            for t in mg.tables():
                if "CRIT" in mg.header(t):
                    self.assertEqual({r[mg.header(t).index("CRIT")] for r in table_rows_by_id(mg, t)}, {""})
        kept = copy.deepcopy(self.template)
        share.share(kept, audience="auditor")
        self.assertTrue([i for i in page(kept, "3 ").els if i.endswith("-crit")])
        idf = next(i for i, el in g.els.items() if el.get("name") == "S01-IT-ACC-IDF1-1" and sync._is_device(el))
        self.assertNotIn(f"{idf}-crit", g.els)
        # The page's layer card names the new layer, in the list and in the "hide by hand" sentence, once.
        card = next(g.value(el) for el in g.els.values() if g.value(el).startswith(sync.LAYERS_CARD))
        self.assertEqual(card.count(sync.CRITICALITY_LEGEND), 1)
        self.assertIn("7 · Asset register<br>" + sync.CRITICALITY_LEGEND + "<br>", card)
        self.assertIn("hide layers 3, 3b, 4, 7, Asset criticality and Compliance scope by hand", card)

    def test_a_site_may_keep_criticality_in_its_own_field(self):
        export = copy.deepcopy(self.export)
        for d in export["devices"]:
            d["custom_fields"] = {"bia_criticality": "high", **{k: v for k, v in d["custom_fields"].items() if k != "criticality"}}
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-17", settings={"criticality_field": "bia_criticality"})
        g = page(template, "3 ")
        table = next(t for t in g.tables() if "HOSTNAME" in g.header(t) and "SW" in g.header(t))
        header = g.header(table)
        self.assertEqual({r[header.index("CRIT")] for r in table_rows_by_id(g, table)}, {"High"})

    def test_quality_sheet_rows_grow_for_long_check_names(self):
        from netdiagrams.drawio import Page
        p = Page("t", "t")
        layer = p.layer("x")
        columns = [("WHAT", 250), ("MISSING", 70)]
        long = "Power supplies, fans and optics without a serial number on every device of the site"
        y = quality._table(p, layer, 0, 0, columns, [["short", "1"], [long, "2"]])
        self.assertGreater(y, 20 + 22 * 2)
        heights = [float(c.find("mxGeometry").get("height")) for c in p.cells if c.get("value") in ("short", long)]
        self.assertEqual(heights[0], 22)
        self.assertGreaterEqual(heights[1], 31)


class ModelLifecycle(unittest.TestCase):
    """End of sale and end of support are kept once per model, on the NetBox device type."""

    def test_a_device_takes_its_models_dates_unless_it_has_its_own(self):
        export = sample_export()
        procurve = next(d for d in export["devices"] if d["device_type"]["model"] == "ProCurve 2610-24")
        core = next(d for d in export["devices"] if d["name"] == "S01-IT-CORE-1")
        core["custom_fields"]["end_of_support"] = "2030-01-31"   # an extended contract on this one unit
        for d in export["devices"]:   # an export without type ids still matches on manufacturer and model
            d["device_type"].pop("id", None)
        prepared = intake.prepare(export)
        by_name = {d["name"]: d["custom_fields"] for d in prepared["devices"]}
        self.assertEqual(by_name[procurve["name"]]["end_of_support"], "2018-10-31")
        self.assertEqual(by_name[procurve["name"]]["end_of_sale"], "2013-10-31")
        self.assertEqual(by_name["S01-IT-CORE-1"]["end_of_support"], "2030-01-31")
        self.assertNotIn("end_of_support", by_name["S01-C01-PLC01"])   # endpoint models carry none
        self.assertIn(procurve["name"], intake.intake(prepared).from_type["end_of_support"])
        self.assertNotIn("S01-IT-CORE-1", intake.intake(prepared).from_type["end_of_support"])

    def test_one_date_on_the_model_clears_every_device_of_it(self):
        export = sample_export()
        found = gaps.find(intake.prepare(export), sync.ENDPOINT_ROLES, lambda d: ["zone"], "2026-10-17")
        self.assertEqual(sorted(found["past_support"].names), ["S01-C03-PH-SW01", "S01-WH-ACC-01", "S01-WH-ACC-02"])
        self.assertEqual(found["model_no_eos"].names, [])
        catalyst = next(t for t in export["device_types"] if t["model"] == "Catalyst 9300-48UXM")
        catalyst["custom_fields"]["end_of_support"] = None
        export = intake.prepare(export)
        found = gaps.find(export, sync.ENDPOINT_ROLES, lambda d: ["zone"], "2026-10-17")
        self.assertEqual(found["model_no_eos"].names, ["Cisco Catalyst 9300-48UXM"])   # one row, seven devices
        self.assertIn("Device type", found["model_no_eos"].where)
        rows = list(csv.DictReader(io.StringIO(worksheets.files(export, found)["15-device-models.csv"])))
        self.assertEqual([(r["id"], r["model"]) for r in rows], [(str(catalyst["id"]), "Catalyst 9300-48UXM")])
        self.assertIn("15-device-models.csv  Devices > Device Types > Import", worksheets.GUIDE)

    def test_the_gaps_command_agrees_with_doctor_on_models(self):
        export = sample_export()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "e.json"
            src.write_text(json.dumps(export))
            with redirect_stdout(io.StringIO()):
                cli.main(["gaps", "--input", str(src), "-o", str(Path(tmp) / "g")])
            self.assertFalse((Path(tmp) / "g" / "15-device-models.csv").exists())   # every model is dated
            next(t for t in export["device_types"] if t["model"] == "PA-450")["custom_fields"]["end_of_support"] = ""
            src.write_text(json.dumps(export))
            with redirect_stdout(io.StringIO()):
                cli.main(["gaps", "--input", str(src), "-o", str(Path(tmp) / "h")])
            rows = list(csv.DictReader(io.StringIO((Path(tmp) / "h" / "15-device-models.csv").read_text())))
        self.assertEqual([r["model"] for r in rows], ["PA-450"])   # eol_notice left blank adds no row

    def test_the_register_shows_the_models_date_without_drift_or_wrapping(self):
        template = sync.default_template()
        report = sync.fill(template, sample_export(), today="2026-10-17")
        self.assertEqual(report.changes, [])
        g = page(template, "3 ")
        table = next(t for t in g.tables() if "HOSTNAME" in g.header(t) and "SW" in g.header(t))
        header = g.header(table)
        rows = {r[0]: r for r in table_rows_by_id(g, table)}
        self.assertEqual(rows["S01-C03-PH-SW01"][header.index("EOS")], "2022-07-31")
        widths = [float(g.geometry(c).get("width")) for c in g.row_cells(g.rows(table)[0])]
        self.assertEqual(sum(widths), g.box(table)[2])   # the EOS column took room where the text had some
        tx, ty, tw, th = g.box(table)
        card = min((g.box(i) for i, e in g.els.items() if "rounded=1" in (cell_of(e).get("style") or "")
                    and g.box(i)[0] < tx and g.box(i)[1] < ty and g.box(i)[1] + g.box(i)[3] > ty + th
                    and g.box(i)[2] < 1000), key=lambda b: b[2] * b[3])
        self.assertLessEqual(tx + tw, card[0] + card[2] - 14)   # inside its card, with the card's margin
        heads = [cell_of(g.els[c]).get("style") for c in g.row_cells(g.rows(table)[0])]
        self.assertEqual(heads[header.index("EOS")], heads[header.index("SW")])   # added headers look the same
        serial = header.index("SERIAL")
        self.assertTrue(all(graph_mod_text_lines(r[serial], widths[serial]) == 1 for r in rows.values()))

    def test_a_register_column_is_never_narrower_than_its_longest_word(self):
        export = sample_export()
        for d in export["devices"]:   # long unbroken serials, as on FortiGates, on the firewalls and switches
            if d["role"]["slug"] in ("firewall", "access-switch"):
                d["serial"] = d["serial"][:2] + "x" * 10 + d["serial"][-2:]
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-17")
        g = next(Graph(d) for d in template.iter("diagram")
                 if any("HOSTNAME" in Graph(d).header(t) and "SW" in Graph(d).header(t) for t in Graph(d).tables()))
        table = next(t for t in g.tables() if "HOSTNAME" in g.header(t) and "SW" in g.header(t))
        serial = g.header(table).index("SERIAL")
        width = float(g.geometry(g.row_cells(g.rows(table)[0])[serial]).get("width"))
        for r in table_rows_by_id(g, table):
            self.assertEqual(graph_mod_text_lines(r[serial], width), 1, r[serial])

    def test_setup_puts_the_dates_on_the_device_type(self):
        template = sync.default_template()
        rows = {r["name"]: r for r in csv.DictReader(io.StringIO(netbox_setup.setup_files(template)["2-custom-fields.csv"]))}
        self.assertEqual((rows["end_of_support"]["type"], rows["end_of_support"]["object_types"]),
                         ("date", "dcim.devicetype,dcim.device"))
        self.assertEqual(rows["end_of_sale"]["object_types"], "dcim.devicetype,dcim.device")
        self.assertEqual((rows["eol_notice"]["type"], rows["eol_notice"]["object_types"]), ("url", "dcim.devicetype"))
        self.assertEqual(rows["gateway"]["object_types"], "ipam.prefix")
        cfg = settings.merge(settings.DEFAULTS, {"end_of_support_field": "eos_date", "gateway_field": "gw"})
        rows = netbox_setup.setup_files(template, settings=cfg)["2-custom-fields.csv"]
        self.assertNotIn("end_of_support,", rows)
        self.assertNotIn("gateway,", rows)
        self.assertIn("end_of_sale,", rows)
        # A NetBox that has the field on devices only is told to add device types by hand; nothing is changed.
        have = {"custom_fields": {"end_of_support": {"object_types": ["dcim.device"]}}}
        state = dict(((k, n), s) for k, n, s in netbox_setup.check(template, have))
        self.assertEqual(state[("custom_fields", "end_of_support")], "present, but not on dcim.devicetype")

    def test_an_industry_orders_the_scopes_and_words_the_levels_but_keeps_every_choice(self):
        school = dataclasses.replace(profiles.MANUFACTURING, name="test-school", scopes=("ferpa", "pci-cde", "cui"),
                                     level_labels={"L3.5": "Level 3.5 · Automation DMZ"})
        with profiles.use(school):
            sets = dict(csv.reader(io.StringIO(netbox_setup.setup_files(sync.default_template())[
                "1-custom-field-choice-sets.csv"])))
        scopes = [c.split(":")[0] for c in sets["Compliance scope"].split(",")]
        self.assertEqual(scopes[:3], ["ferpa", "pci-cde", "cui"])
        self.assertEqual(sorted(scopes), sorted(v for v, _ in audit.CHOICE_SETS["Compliance scope"]))
        self.assertIn("L3.5:Level 3.5 · Automation DMZ", sets["Purdue level"])
        self.assertIn("gxp:GxP / GDP", sets["Compliance scope"])

    def test_field_descriptions_name_no_industry_standard_or_product(self):
        fields = list(audit.CUSTOM_FIELDS) + list(wireless.CUSTOM_FIELDS) + list(netbox_setup.MODEL_FIELDS)
        text = " ".join(f[-1] for f in fields)
        for word in ("IEC", "NERC", "PCI", "PLC", "ISO", "NIST", "Splunk", "Meraki", "LibreNMS", "FortiGate"):
            self.assertNotIn(word, text)
        setup_help = next(a for a in cli.parser()._subparsers._group_actions[0]._choices_actions
                          if a.dest == "netbox-setup").help
        self.assertNotIn("Purdue", setup_help)
        self.assertNotIn("OT", setup_help)


class AuditEvidence(unittest.TestCase):
    """Owner, compliance scope, backups, patching, verification, support, monitoring and logging per asset."""

    @classmethod
    def setUpClass(cls):
        cls.export = sample_export()
        cls.template = sync.default_template()
        cls.report = sync.fill(cls.template, cls.export, today="2026-10-17")
        cls.sheet = page(cls.template, "3f")
        cls.evidence = audit.Evidence(intake.prepare(copy.deepcopy(cls.export)), {}, sync.endpoint_roles())

    @staticmethod
    def bare(export):
        """The export with every piece of audit evidence taken out."""
        export = copy.deepcopy(export)
        export["contact_assignments"] = []
        for obj in [export["site"], *export.get("locations", []), *export["devices"], *export["prefixes"]]:
            cf = obj.get("custom_fields") or {}
            for name in audit.FIELD_NAMES:
                if name != "support_contract":
                    cf.pop(name, None)
        return export

    def register(self, g=None):
        g = g or self.sheet
        rows = {}
        for el_id, el in g.els.items():
            if g.layer_of(el_id) != "Asset evidence register":
                continue
            x, y, w, h = g.box(el_id)
            rows.setdefault(y, []).append((x, plain(g.value(el)), g.value(el)))
        out = [sorted(r) for _, r in sorted(rows.items())]
        header = next(i for i, r in enumerate(out) if r[0][1] == "ASSET")
        names = [c[1] for c in out[header]]
        return names, {r[0][1]: {names[k]: (r[k][1], r[k][2]) for k in range(min(len(names), len(r)))}
                       for r in out[header + 1:] if len(r) == len(names)}

    def test_netbox_setup_adds_dropdowns_dates_bounds_and_contact_roles(self):
        files = netbox_setup.setup_files(sync.default_template())
        sets = {r["name"]: r["extra_choices"] for r in csv.DictReader(io.StringIO(files["1-custom-field-choice-sets.csv"]))}
        for name in audit.CHOICE_SETS:
            self.assertIn(name, sets)
        self.assertIn("pci-cde:PCI DSS cardholder data environment", sets["Compliance scope"])
        fields = {r["name"]: r for r in csv.DictReader(io.StringIO(files["2-custom-fields.csv"]))}
        for name, _, _, kind, types, choice_set, _ in audit.CUSTOM_FIELDS:
            self.assertEqual((fields[name]["type"], fields[name]["object_types"], fields[name]["choice_set"]),
                             (kind, types, choice_set))
        self.assertEqual(sum(1 for r in csv.DictReader(io.StringIO(files["2-custom-fields.csv"]))
                             if r["name"] == "support_contract"), 1)   # the template's text field, defined once
        self.assertEqual((fields["log_retention_days"]["validation_minimum"],
                          fields["log_retention_days"]["validation_maximum"]), ("1", "3650"))
        self.assertEqual(fields["last_patched"]["type"], "date")
        roles = {r["slug"] for r in csv.DictReader(io.StringIO(files["6-contact-roles.csv"]))}
        self.assertEqual(roles, {"asset-owner", "custodian"})
        step = next(s for s in netbox_setup.plan(files, "4.2.5") if s.label == "custom field log_retention_days")
        self.assertEqual((step.payload["validation_minimum"], step.payload["validation_maximum"]), (1, 3650))
        role = next(s for s in netbox_setup.plan(files, "4.2.5") if s.kind == "contact_roles")
        self.assertEqual(role.endpoint, "tenancy/contact-roles")
        # A fact the site keeps in a field of its own needs no new field.
        own = netbox_setup.setup_files(sync.default_template(), settings={
            "audit": {"fields": {"last_config_backup": "backup_date", "monitoring": "nms"}}})
        names = {r["name"] for r in csv.DictReader(io.StringIO(own["2-custom-fields.csv"]))}
        self.assertNotIn("last_config_backup", names)
        self.assertNotIn("monitoring", names)
        self.assertNotIn("Monitoring", own["1-custom-field-choice-sets.csv"])
        have = {"contact_roles": {"asset-owner", "custodian"}}
        self.assertNotIn("6-contact-roles.csv", netbox_setup.setup_files(sync.default_template(), have))

    def test_values_come_from_the_device_its_rack_room_subnet_or_site(self):
        export = copy.deepcopy(self.export)
        export["racks"] = [{"id": 7, "name": "R01", "custom_fields": {"physical_access": "locked-cabinet"}}]
        export["prefixes"].append({"id": 900, "prefix": "10.1.99.0/24",
                                   "custom_fields": {"compliance_scope": ["pci-connected"],
                                                     "data_classification": "restricted"}})
        fw = next(d for d in export["devices"] if d["name"] == "S01-FW-EDGE-01")
        fw["rack"] = {"id": 7, "name": "R01"}
        fw["tenant"] = {"name": "Plant IT"}
        ev = audit.Evidence(export, {}, sync.endpoint_roles())
        f = ev.devices["S01-FW-EDGE-01"]
        self.assertEqual((f.owner.value, f.owner.where), ("Maya Chen", "room"))      # the room's contact
        self.assertEqual((f.custodian.value, f.custodian.where), ("Plant IT team", "site"))
        self.assertEqual((f.access.value, f.access.where), ("locked-cabinet", "rack"))   # the rack beats the room
        self.assertEqual(f.scope, ["pci-connected"])                                 # from its subnet
        self.assertEqual((f.classification.value, f.classification.where), ("restricted", "subnet"))   # the strictest
        self.assertEqual((f.verified.value, f.verified.where), ("2026-09-12", "room"))
        self.assertEqual((f.monitoring.value, f.monitoring.where), ("alerting", "site"))
        ot_core = ev.devices["S01-OT-CORE-1"]
        self.assertEqual((ot_core.owner.value, ot_core.owner.where), ("Ravi Okafor", "device"))   # a device's own wins
        sis = ev.devices["S01-SIS-LS01"]
        self.assertEqual((sis.scope, sis.scope_from), (["safety"], ["room"]))
        self.assertEqual(sis.monitoring.value, "passive")
        self.assertEqual(audit.label("passive"), "Passive (OT IDS)")   # a plant's words
        with profiles.use(dataclasses.replace(profiles.MANUFACTURING, name="test-office", levels=False)):
            self.assertEqual(audit.label("passive"), "Passive (IDS or sensor)")
        # No contact anywhere: the tenant stands in as the owner.
        export["contact_assignments"] = []
        f = audit.Evidence(export, {}, sync.endpoint_roles()).devices["S01-FW-EDGE-01"]
        self.assertEqual((f.owner.value, f.owner.where), ("Plant IT", "tenant"))

    def test_checks_count_the_sample_findings(self):
        checks = self.evidence.checks("2026-10-17")
        self.assertEqual(checks["no_owner"], ([], 70))
        self.assertEqual(checks["stale_backup"], (["S01-C02-HMI01"], 59))   # access points follow their controller
        self.assertEqual(sorted(checks["stale_patch"][0]),
                         ["S01-C03-IE03", "S01-C03-PH-SW01", "S01-WH-ACC-01", "S01-WH-ACC-02"])
        self.assertEqual(sorted(checks["support_ended"][0]), ["S01-C03-PH-SW01", "S01-WH-ACC-01", "S01-WH-ACC-02"])
        self.assertEqual(checks["no_physical_access"], (["S01-WH-ACC-02"], 70))
        self.assertEqual(checks["not_monitored"][0], [])
        self.assertEqual(checks["no_log_forwarding"][0], [])   # PLCs keep local logs: not network gear
        self.assertEqual(checks["audit_bad_values"][0], [])
        card = self.report.quality
        self.assertEqual(card.score, 99)
        self.assertEqual((card.check("stale_patch").missing, card.check("stale_patch").group), (4, "audit"))
        self.assertIn("audit", {c.group for c in card.checks})

    def test_the_sheet_draws_tiles_site_cards_and_a_register(self):
        names = [d.get("name") for d in self.template.findall("diagram")]
        self.assertEqual(names.index(self.sheet.diagram.get("name")), names.index(page(self.template, "3d").name) + 1)
        text = " ".join(plain(self.sheet.value(e)) for e in self.sheet.els.values())
        for words in ("S01 · Plant A — Audit evidence", "Owner recorded", "Config backup ≤ 30 d",
                      "100 %", "LibreNMS", "44 of 44 network devices monitored, 41 with alerts", "Splunk, syslog over TLS", "kept 400 days",
                      "Safety instrumented system (IEC 61511) · 4 assets", "Ravi Okafor · 39 assets"):
            self.assertIn(words, text)
        columns, rows = self.register()
        self.assertEqual(columns[:4], ["ASSET", "CRIT", "OWNER", "SCOPE"])
        self.assertEqual(len([n for n in rows if n.startswith("S01-")]), 70)
        self.assertIn("SIS · 4 assets", rows)   # one heading row per zone
        self.assertIn(audit.AMBER, rows["S01-C02-HMI01"]["CONFIG BACKUP"][1])
        self.assertTrue(rows["S01-C02-HMI01"]["CONFIG BACKUP"][0].startswith("2026-07-02 · 107 d"))
        self.assertIn("ended 2025-12-31", rows["S01-WH-ACC-01"]["SUPPORT"][0])
        self.assertIn(audit.RED, rows["S01-WH-ACC-01"]["SUPPORT"][1])
        self.assertEqual(rows["S01-AP-OF-01"]["PATCHED"][0], "from controller")
        self.assertEqual(rows["S01-WH-ACC-02"]["ROOM ACCESS"][0], "none")
        self.assertEqual(rows["S01-SIS-LS01"]["SCOPE"][0], "Safety")
        self.assertNotIn(audit.RED, rows["S01-C01-PLC01"]["LOGS"][1])   # a PLC's own log is not a finding
        self.assertIn("font-style:italic", rows["S01-C01-IE01"]["OWNER"][1])   # inherited from the room
        self.assertEqual(self.sheet.diagram.get("name").split(" ", 1)[0], "3f")
        self.assertIn("3f of 13", text)
        export = copy.deepcopy(self.export)
        next(d for d in export["devices"] if d["name"] == "S01-C01-IE01")["custom_fields"]["monitoring"] = "passive"
        ev = audit.Evidence(export, {}, sync.endpoint_roles())
        sheet = Graph(audit.page(ev, export, "2026-10-17", lambda d: ["zone-cell01"]))
        self.assertIn("41 with alerts or passive monitoring", " ".join(plain(sheet.value(e)) for e in sheet.els.values()))

    def test_a_site_without_evidence_gets_no_sheet_and_loses_no_points(self):
        bare = self.bare(self.export)
        template = sync.default_template()
        report = sync.fill(template, bare, today="2026-10-17")
        self.assertFalse(report.audit)
        self.assertIsNone(template.find("diagram[@id='audit']"))
        self.assertEqual(report.quality.score, self.report.quality.score)
        check = report.quality.check("no_owner")
        self.assertEqual((check.missing, check.total), (70, 0))   # listed, not scored
        self.assertFalse([i for i in page(template, "3 ").els if i.endswith("-scope")])
        forced = sync.default_template()
        self.assertTrue(sync.fill(forced, bare, today="2026-10-17", audit=True).audit)
        left_out = sync.default_template()
        sync.fill(left_out, self.export, today="2026-10-17", pages="-audit")
        self.assertIsNone(left_out.find("diagram[@id='audit']"))

    def test_scope_stripe_layer_card_and_sharing(self):
        g = page(self.template, "3 ")
        sis = next(i for i, el in g.els.items() if el.get("name") == "S01-SIS-SW01" and sync._is_device(el))
        self.assertIn(f"{sis}-scope", g.els)
        self.assertEqual(g.layer_of(f"{sis}-scope"), sync.SCOPE_LAYER)
        self.assertEqual(g.els[f"{sis}-scope"].get("tooltip"), "In compliance scope: Safety instrumented system (IEC 61511)")
        cx, cy, cw, ch = g.box(sis)
        mx, my, mw, mh = g.box(f"{sis}-scope")
        self.assertTrue(cx + cw / 2 < mx and mx + mw <= cx + cw and cy <= my and my + mh <= cy + ch)   # right edge, inside
        self.assertFalse([i for i in g.els if i.endswith("-scope") and "SIS" not in (g.els[g.els[i].get("netdiagrams_ref")].get("name") or "")])
        card = next(g.value(el) for el in g.els.values() if g.value(el).startswith(sync.LAYERS_CARD))
        self.assertIn("Compliance scope — <i>hide before sharing</i>", card)
        vendor = copy.deepcopy(self.template)
        share.share(vendor, audience="vendor")
        self.assertIsNone(vendor.find("diagram[@id='audit']"))
        self.assertFalse([i for i in page(vendor, "3 ").els if i.endswith("-scope")])
        auditor = copy.deepcopy(self.template)
        share.share(auditor, audience="auditor")
        self.assertIsNotNone(auditor.find("diagram[@id='audit']"))
        managed = copy.deepcopy(self.template)
        share.share(managed, audience="management")
        self.assertIsNone(managed.find("diagram[@id='audit']"))
        # Rebuilt from that drawing with no scope left in NetBox: the stripe, the layer and its card line go.
        export = copy.deepcopy(self.export)
        for loc in export["locations"]:
            loc["custom_fields"].pop("compliance_scope", None)
        again = ET.fromstring(ET.tostring(self.template))
        sync.fill(again, export, today="2026-10-17")
        g = page(again, "3 ")
        self.assertFalse([i for i in g.els if i.endswith("-scope")])
        card = next(g.value(el) for el in g.els.values() if g.value(el).startswith(sync.LAYERS_CARD))
        self.assertNotIn("Compliance scope", card)
        self.assertIn("hide layers 3, 3b, 4, 7 and Asset criticality by hand", card)

    def test_evidence_dates_never_show_as_drift(self):
        again = ET.fromstring(ET.tostring(self.template))
        export = copy.deepcopy(self.export)
        for d in export["devices"]:
            if d["custom_fields"].get("last_config_backup"):
                d["custom_fields"]["last_config_backup"] = "2026-10-17"
        export["exported_at"] = "2026-10-18T06:00:00+00:00"
        report = sync.fill(again, export, today="2026-10-18")
        self.assertEqual(report.changes, [])
        fw = next(el for el in page(again, "3 ").els.values() if el.get("name") == "S01-FW-EDGE-01" and sync._is_device(el))
        self.assertEqual((fw.get("cf_last_config_backup"), fw.get("owner"), fw.get("custodian")),
                         ("2026-10-17", "Maya Chen", "Plant IT team"))

    def test_a_flagged_gap_never_scores_100(self):
        export = copy.deepcopy(self.export)
        for d in export["devices"]:   # close the sample's audit findings: only one missing serial is left
            cf = d["custom_fields"]
            cf.update(last_config_backup="2026-10-16", last_patched="2026-10-01", support_contract_end="2027-06-30")
            cf.pop("monitoring", None) if cf.get("monitoring") == "polling" else None
        for loc in export["locations"]:
            loc["custom_fields"].setdefault("physical_access", "locked-room")
        for t in export["device_types"]:   # and the ProCurves' end of support
            t["custom_fields"]["end_of_support"] = "2033-10-31"
        next(d for d in export["devices"] if d["name"] == "S01-SIS-LS01")["serial"] = ""
        card = doctor.quality(export)
        self.assertEqual(card.check("no_serial").missing, 1)
        self.assertEqual(card.score, 99)
        weight = sum(quality.WEIGHT[c.group] for c in card.checks if c.total > 0)
        raw = 100 * sum(quality.WEIGHT[c.group] * c.complete for c in card.checks if c.total > 0) / weight
        self.assertGreaterEqual(raw, 99.5)   # the case: rounding alone would have said 100

    def test_a_single_firewall_reads_as_no_standby_not_no_backup(self):
        export = copy.deepcopy(self.export)
        firewalls = [d["name"] for d in export["devices"] if d["role"]["slug"] == "firewall"]
        export["devices"] = [d for d in export["devices"] if d["name"] not in firewalls[1:]]
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-17")
        text = " ".join(plain(g.value(e)) for g in [page(template, "1 ")] for e in g.els.values())
        self.assertIn("one firewall in NetBox (no standby firewall recorded)", text)
        self.assertIn("NetBox records no standby firewall for it.", text)
        self.assertNotIn("no backup", text.lower())

    def test_every_gap_card_holds_its_wrapped_rows_inside_the_page(self):
        template = sync.default_template()
        sync.fill(template, self.export, today="2026-10-17")
        seen = 0
        for diagram in template.iter("diagram"):
            g = Graph(diagram)
            pid = diagram.get("id")
            if f"{pid}-gaps-card-t" not in g.els:
                continue
            seen += 1
            cx, cy, cw, ch = g.box(f"{pid}-gaps-card-card")
            tx, ty, tw, th = g.box(f"{pid}-gaps-card-t")
            rows = [g.box(i)[3] for i in g.children[f"{pid}-gaps-card-t"]]
            self.assertAlmostEqual(sum(rows), th, msg=pid)
            self.assertAlmostEqual(cy + ch - (ty + th), 14, msg=pid)   # same margin under the table as at its sides
            self.assertLessEqual(cy + ch, float(g.model.get("pageHeight")), pid)
        self.assertGreaterEqual(seen, 3)

    def test_values_off_the_list_are_flagged(self):
        export = copy.deepcopy(self.export)
        hmi = next(d for d in export["devices"] if d["name"] == "S01-C01-HMI01")
        hmi["custom_fields"].update(monitoring="yes", last_patched="17/10/2026", log_retention_days=None)
        export["site"]["custom_fields"]["log_retention_days"] = 99999
        ev = audit.Evidence(export, {}, sync.endpoint_roles())
        bad, count = ev.values()
        self.assertEqual(sorted(bad), ["Plant A log_retention_days = 99999", "S01-C01-HMI01 last_patched = 17/10/2026",
                                       "S01-C01-HMI01 monitoring = yes"])
        self.assertGreater(count, 100)
        found = gaps.find(export, sync.ENDPOINT_ROLES, lambda d: ["zone"], "2026-10-17")
        self.assertEqual(len(found["audit_bad_values"].names), 3)
        self.assertIn("HMI01 last_patched", " ".join(found["audit_bad_values"].names))

    def test_settings_rename_fields_and_change_the_limits(self):
        with self.assertRaises(settings.SettingsError):
            settings.merge(settings.DEFAULTS, settings._as_dict({"audit": {"limits": {}}}, "x"))
        with self.assertRaises(settings.SettingsError):
            settings._as_dict({"audit": {"days": {"backup": 0}}}, "x")
        with self.assertRaises(settings.SettingsError):
            settings._as_dict({"audit": {"fields": {"nonsense": "x"}}}, "x")
        export = copy.deepcopy(self.export)
        for d in export["devices"]:
            cf = d["custom_fields"]
            if "last_config_backup" in cf:
                cf["backup_date"] = cf.pop("last_config_backup")
        cfg = {"audit": {"fields": {"last_config_backup": "backup_date"}, "days": {"backup": 10}}}
        ev = audit.Evidence(export, cfg, sync.endpoint_roles())
        failing, total = ev.checks("2026-10-17")["stale_backup"]
        self.assertEqual(total, 59)
        self.assertIn("S01-C01-PLC01", failing)   # 16 days old: past a 10-day limit
        self.assertEqual(audit.gap_texts(ev.days)["stale_backup"][0], "Devices with no config backup in 10 days")

    def test_worksheets_close_the_audit_gaps(self):
        export = copy.deepcopy(self.export)
        export["contact_assignments"] = [a for a in export["contact_assignments"] if a["role"]["slug"] != "asset-owner"
                                         or (a["object_type"], a["object_id"]) not in (("dcim.site", 1), ("dcim.location", 1))]
        export["site"]["custom_fields"]["monitoring"] = None
        prepared = intake.prepare(export)
        found = gaps.find(prepared, sync.ENDPOINT_ROLES, lambda d: ["zone"], "2026-10-17")
        files = worksheets.files(prepared, found)
        rows = list(csv.DictReader(io.StringIO(files["12-audit-evidence.csv"])))
        self.assertIn("S01-C02-HMI01", {r["name"] for r in rows})
        self.assertIn("cf_monitoring", rows[0])
        rooms = list(csv.DictReader(io.StringIO(files["13-locations.csv"])))
        self.assertEqual([r["name"] for r in rooms], ["WH-01 ship office"])
        self.assertIn("13-locations.csv", worksheets.GUIDE)
        self.assertEqual(worksheets.GUIDE.count("WS-12 Audit evidence"), 3)
        self.assertEqual({found[k].worksheet for k in audit.CHECK_KEYS}, {"WS-12 Audit evidence"})
        cell = next(loc for loc in export["locations"] if loc["id"] == 1)
        self.assertTrue(found["no_owner"].names)
        self.assertTrue(all(next(d for d in export["devices"] if d["name"] == n)["location"]["name"] == cell["name"]
                            for n in found["no_owner"].names))
        contacts = list(csv.DictReader(io.StringIO(files["14-new-owner-contacts.csv"])))
        self.assertEqual(contacts, [{"object_type": "dcim.location", "object_id": "1", "contact": "",
                                     "role.slug": "asset-owner", "priority": "primary"}])

    def test_export_reads_contacts_with_the_versions_filter(self):
        for version, key in (("4.2.5", "object_type=dcim.device"), ("3.7.8", "content_type=dcim.device")):
            client = NetBoxClient("https://nb.example.com/", "t")
            seen = []

            def fake_get(url, version=version):
                seen.append(url)
                if "/status/" in url:
                    return {"netbox-version": version}
                if "dcim/sites" in url:
                    return {"results": [{"id": 1, "slug": "s01", "name": "Plant A"}], "next": None}
                if "dcim/devices" in url:
                    return {"results": [{"id": 5, "name": "A"}], "next": None}
                if "tenancy/contact-assignments" in url and "dcim.device" in url:
                    return {"results": [{"id": 1, "object_id": 5, "contact": {"name": "M"}, "role": {"slug": "asset-owner"}}],
                            "next": None}
                return {"results": [], "next": None}

            with mock.patch.object(client, "get", side_effect=fake_get):
                data = client.export_site("s01")
            self.assertTrue(any(key in u and "object_id=5" in u for u in seen), version)
            self.assertEqual(len(data["contact_assignments"]), 1)
            self.assertIn("racks", data)

    def test_a_big_site_lists_the_findings_not_every_asset(self):
        export = BigSites.make_site_module().grow("large")
        template = sync.default_template()
        sync.fill(template, export, today="2026-10-17")
        g = page(template, "3f")
        text = " ".join(plain(g.value(e)) for e in g.els.values())
        self.assertIn("Assets with a finding, and the critical ones", text)
        rows = {g.box(i)[1] for i in g.els if g.layer_of(i) == "Asset evidence register" and g.box(i)[3] > 1}
        self.assertLess(len(rows), audit.MAX_ROWS + 60)


if __name__ == "__main__":
    unittest.main()


class ReviewFixes(unittest.TestCase):
    """Regression tests for the code review of the template engine (ponytail-review.md)."""

    def test_the_package_compiles_on_the_oldest_python_it_supports(self):
        import shutil
        import subprocess
        olds = [p for p in (shutil.which(f"python3.{n}") for n in (9, 10, 11)) if p]
        if not olds:
            self.skipTest("no Python 3.9 to 3.11 installed")
        src = Path(__file__).parent.parent / "src" / "netdiagrams"
        for python in olds:
            for path in sorted(src.glob("*.py")):
                run = subprocess.run([python, "-c", "import ast, sys; ast.parse(open(sys.argv[1]).read())", str(path)],
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, f"{python} {path.name}: {run.stderr[-300:]}")

    def test_share_blanks_compressed_ipv6_and_counts_it(self):
        built = sync.default_template()
        sync.fill(built, sample_export(), today="2026-10-12")
        g = Graph(built.find("diagram[@id='logical']"))
        el = next(e for e in g.els.values() if "VLAN" in g.value(e))
        g.set_value(el, g.value(el) + "<br>2001:db8:130::/64 · gw fd00:99::10")
        report = share.share(built, audience="vendor")
        text = " ".join(e.get("value") or e.get("label") or "" for e in built.iter())
        for ip in ("2001:db8:130::/64", "fd00:99::10"):
            self.assertNotIn(ip, text)
        self.assertEqual(report.leaks, [])
        self.assertEqual(share._ips("at 10:30 and 12:45:00, fe80::1"), ["fe80::1"])

    def test_site_names_are_written_once_and_escaped_in_titles(self):
        for name in ("Plant AB", "Plant <img src=x> & Co"):
            export = sample_export()
            export["site"]["name"] = name
            built = sync.default_template()
            sync.fill(built, export, today="2026-10-12")
            again = ET.fromstring(ET.tostring(built))
            sync.fill(again, export, today="2026-10-12")
            values = [e.get("value") or e.get("label") or "" for e in again.iter()]
            self.assertFalse([v for v in values if "Plant ABB" in v], name)
            self.assertFalse([v for v in values if "<img" in v], name)
            self.assertTrue([v for v in values if __import__("html").escape(name, quote=False) in v], name)

    def test_a_redirected_post_is_an_error_not_a_success(self):
        import http.server
        import os
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(301)
                self.send_header("Location", "/api/dcim/device-roles/?redirected=1")
                self.end_headers()

            def do_GET(self):  # what urllib would turn the redirected POST into
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"count": 0, "results": []}')

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with mock.patch.dict(os.environ, {"no_proxy": "*", "NO_PROXY": "*"}):
                client = NetBoxClient(f"http://127.0.0.1:{server.server_port}", "t\n")
                with self.assertRaises(netbox.NetBoxError) as err:
                    client.post("dcim/device-roles", {"name": "x", "slug": "x"})
            self.assertIn("redirected", str(err.exception))
            self.assertEqual(client._headers()["Authorization"], "Token t")
        finally:
            server.shutdown()

    def test_pagination_stays_on_the_netbox_host(self):
        client = NetBoxClient("https://nb.example.com/", "t")
        seen = []

        def fake_get(url):
            seen.append(url)
            if "offset" not in url:
                return {"results": [{"id": 1}], "next": "http://evil.example.net/api/dcim/sites/?offset=1"}
            return {"results": [{"id": 2}], "next": None}

        with mock.patch.object(client, "get", side_effect=fake_get):
            self.assertEqual([s["id"] for s in client.sites()], [1, 2])
        self.assertTrue(seen[1].startswith("https://nb.example.com/api/dcim/sites/"))

    def test_a_refused_read_is_not_an_empty_netbox(self):
        client = NetBoxClient("https://nb.example.com/", "t")
        with mock.patch.object(client, "get", side_effect=netbox.NetBoxError("NetBox returned 403", 403)):
            with self.assertRaises(netbox.NetBoxError):
                client._optional("dcim/modules", device_id=1)
            with self.assertRaises(netbox.NetBoxError):
                netbox_setup.inventory(client)

    def test_gap_files_import_into_netbox(self):
        export = BigSites.make_site_module().grow("edges")
        locations = ot.Locations(export.get("locations"))
        found = gaps.find(export, sync.ENDPOINT_ROLES, lambda d: ot.device_zones(d, locations), "2026-10-12")
        files = worksheets.files(export, found)
        devices = list(csv.DictReader(io.StringIO(files["1-devices.csv"])))
        self.assertTrue(devices and all(row["site"] == export["site"]["name"] for row in devices))
        optics = files["11-new-optics.csv"].splitlines()[0].split(",")
        self.assertIn("role.slug", optics)
        self.assertNotIn("role", optics)
        wlans = list(csv.DictReader(io.StringIO(files["7-wireless-lans.csv"])))
        self.assertTrue(all(", " not in (row.get("cf_wlan_bands") or "") for row in wlans))
        export["devices"][0]["asset_tag"] = None
        export["devices"][0]["serial"] = '=HYPERLINK("http://x","click")'
        found = gaps.find(export, sync.ENDPOINT_ROLES, lambda d: ot.device_zones(d, locations), "2026-10-12")
        text = "".join(worksheets.files(export, found).values())
        self.assertNotIn("=HYPERLINK", text)

    def test_a_compressed_template_builds_and_shares(self):
        import base64
        import urllib.parse
        import zlib
        template = sync.default_template()
        for d in template.findall("diagram"):
            model = d.find("mxGraphModel")
            raw = urllib.parse.quote(ET.tostring(model, encoding="unicode"), safe="")
            z = zlib.compressobj(9, zlib.DEFLATED, -15)
            d.remove(model)
            d.text = base64.b64encode(z.compress(raw.encode()) + z.flush()).decode()
        report = sync.fill(template, sample_export(), today="2026-10-12")
        self.assertIsNotNone(template.find("diagram[@id='physical']/mxGraphModel"))
        self.assertFalse(report.netbox_only_devices)
        share.share(template, audience="vendor")

    def test_renaming_a_sheet_keeps_its_devices(self):
        export = BigSites.make_site_module().grow("medium")
        template = sync.default_template()
        template.find("diagram[@id='physical']").set("name", "Our plant floor")
        report = sync.fill(template, export, today="2026-10-12")
        self.assertGreater(len(report.scheduled), 100)

    def test_a_relative_logo_is_read_beside_its_settings_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            (Path(tmp) / "netdiagrams.json").write_text(json.dumps({"logo": "logo.svg"}))
            cfg = settings.load_file(Path(tmp) / "netdiagrams.json")
            self.assertEqual(Path(cfg["logo"]), Path(tmp) / "logo.svg")

    def test_dates_in_the_future_are_flagged_and_bad_dates_are_not_dates(self):
        self.assertIsNone(audit.date_of("2026-1-5x"))
        ev = audit.Evidence(sample_export())
        self.assertTrue(ev.stale(audit.Value("2026-12-31"), 365, "2026-10-17"))
        self.assertFalse(ev.stale(audit.Value("2026-10-18"), 365, "2026-10-17"))   # a day's clock skew is fine

    def test_industry_modules_are_found_however_they_register(self):
        for line in ("register(WAREHOUSE)", "OFFICE = register(Profile(", "RETAIL=register(RETAIL_PROFILE)"):
            self.assertTrue(profiles.REGISTERS.search("x = 1\n" + line + "\n"), line)
        for line in ("    register(P)", "# register(P)", "from .profiles import register"):
            self.assertFalse(profiles.REGISTERS.search(line), line)

    def test_every_slug_core_ships_or_writes_is_one_netbox_accepts(self):
        valid = re.compile(r"^[-a-zA-Z0-9_]+$")

        def slugs(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "slug" and isinstance(v, str):
                        yield v
                    yield from slugs(v)
            elif isinstance(obj, list):
                for v in obj:
                    yield from slugs(v)

        self.assertEqual([s for s in slugs(sample_export()) if not valid.match(s)], [])
        for name in profiles.PROFILES:
            with profiles.use(name):
                for f, text in netbox_setup.setup_files(sync.default_template()).items():
                    for row in csv.DictReader(io.StringIO(text)):
                        self.assertTrue(valid.match(row.get("slug") or "x"), f"{name} {f}: {row.get('slug')}")
        import importlib.util  # scripts/ are not a package
        spec = importlib.util.spec_from_file_location("sample_kit", Path(__file__).parent.parent / "scripts" / "sample_kit.py")
        sample_kit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sample_kit)
        self.assertEqual([sample_kit.slug(n) for n in ("ProCurve 2910al-24G-PoE+", "Remote I/O", "PIN pad (P2PE)", "Café")],
                         ["procurve-2910al-24g-poe", "remote-io", "pin-pad-p2pe", "caf"])

    def test_safety_reads_red_and_only_ot_ops_reads_the_sis(self):
        files = netbox_setup.setup_files(sync.default_template())
        tags = {r["slug"]: r["color"] for r in csv.DictReader(io.StringIO(files["3-zone-tags.csv"]))}
        self.assertEqual(tags["zone-sis"], "f44336")
        self.assertNotEqual(tags["zone-sis"], tags.get("zone-cell01"))
        template = sync.default_template()
        for page, cell in (("flows", "flows-c207"), ("register", "register-c156")):
            g = Graph(template.find(f"diagram[@id='{page}']"))
            text = plain(g.value(g.els[cell]))
            self.assertIn("OT-OPS historian / SCADA HMI", text)
            self.assertNotIn("CELL", text)

    def test_a_profile_can_hold_servers_to_the_logging_check(self):
        export = sample_export()
        hmi = next(d for d in export["devices"] if d["role"]["slug"] == "hmi")
        before = audit.Evidence(export, endpoint_roles=sync.ENDPOINT_ROLES).checks("2026-10-17")
        with profiles.use(dataclasses.replace(profiles.MANUFACTURING, watched_roles=("hmi",))):
            after = audit.Evidence(export, endpoint_roles=sync.ENDPOINT_ROLES).checks("2026-10-17")
        self.assertNotIn(hmi["name"], before["no_log_forwarding"][0])
        self.assertIn(hmi["name"], after["no_log_forwarding"][0])   # it keeps local logs only
        self.assertGreater(after["no_log_forwarding"][1], before["no_log_forwarding"][1])
        self.assertGreater(after["not_monitored"][1], before["not_monitored"][1])

    def test_scores_never_round_up_to_complete(self):
        self.assertEqual(quality.pct(0.999), 99)
        self.assertEqual(quality.pct(1.0), 100)

    def test_a_folder_given_to_o_holds_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "e.json"
            src.write_text(json.dumps(sample_export()))
            out = Path(tmp) / "out"
            out.mkdir()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["build", "--input", str(src), "-o", str(out)]), 0)
            self.assertTrue(list(out.glob("*.drawio")))

    def test_overview_lines_skip_cards_between_and_gate_only_sites_get_a_card(self):
        from netdiagrams import overview
        export = sample_export()
        built = sync.default_template()
        sync.fill(built, export, today="2026-10-12")
        site = build_site(intake.prepare(export))
        page = overview.page(site)
        g = Graph(page)
        geo = {i: g.box(i) for i in g.els}
        for el in g.els.values():
            cell = cell_of(el)
            if cell.get("edge") != "1" or "exitY=0.5" not in (cell.get("style") or ""):
                continue
            a, b = geo[cell.get("source")], geo[cell.get("target")]
            between = [i for i, box in geo.items() if box and box[1] == a[1] and a[0] + a[2] < box[0] < b[0]
                       and box[3] == a[3]]
            self.assertEqual(between, [], cell.get("source"))
        fw = dict(export, devices=[d for d in export["devices"] if d["role"]["slug"] == "firewall"])
        gate_only = overview.page(build_site(intake.prepare(fw)))
        self.assertIn("Security gate", ET.tostring(gate_only, encoding="unicode"))


class RebuildKeepsSchedules(unittest.TestCase):
    """A rebuild from the last drawing of a site with typicals keeps every schedule and settles."""

    @classmethod
    def setUpClass(cls):
        cls.export = BigSites.make_site_module().grow("medium")
        cls.builds, cls.reports = [sync.default_template()], []
        cls.reports.append(sync.fill(cls.builds[0], cls.export, today="2026-10-12"))
        for _ in range(2):
            again = ET.fromstring(ET.tostring(cls.builds[-1]))
            cls.reports.append(sync.fill(again, cls.export, today="2026-10-12"))
            cls.builds.append(again)

    def test_the_schedules_survive(self):
        counts = [len(r.scheduled) for r in self.reports]
        self.assertGreater(counts[0], 100)
        self.assertEqual(counts, [counts[0]] * 3)
        for template in self.builds:
            text = ET.tostring(template, encoding="unicode")
            self.assertEqual(len(re.findall(r"TYPICAL ×\d+ ·[^<]*TYPICAL ×", text)), 0)

    def test_the_second_rebuild_changes_nothing(self):
        self.assertEqual(RebuildFromOwnDrawing.geometry(self.builds[1]), RebuildFromOwnDrawing.geometry(self.builds[2]))
        self.assertEqual(ET.tostring(self.builds[1]), ET.tostring(self.builds[2]))


class CoreTemplateFixes(unittest.TestCase):
    """Defects the industry books found in the core template (2026-10-18)."""

    def test_staff_zone_words_match_whole_words_only(self):
        for word in ("ent", "staff", "mgmt", "servers", "corp-it", "it-ops"):
            self.assertTrue(wireless.STAFF_ZONE.search(word), word)
        for word in ("events", "student", "government", "students-wifi", "shops"):
            self.assertFalse(wireless.STAFF_ZONE.search(word), word)

    def test_an_ampersand_in_a_blank_zone_name_reads_as_one(self):
        with profiles.use(profiles.get("office")):
            mxfile = drawio.render(drawio.blank_site())
        labels = [c.get("value") for c in mxfile.iter("mxCell") if (c.get("value") or "").startswith("ZONE ")]
        self.assertIn("ZONE Internet &amp; cloud (rename me)", labels)   # escaped once for the HTML label
        self.assertFalse([v for v in labels if "&amp;amp;" in v])

    def test_a_netbox_settings_field_may_carry_its_own_keys(self):
        export = {"site_group": {"name": "BR-S", "custom_fields": {"netdiagrams": {"typical": "BR-S",
                                                                                   "profile": "office"}}}}
        cfg, sources = settings.resolve(export)
        self.assertEqual(cfg["profile"], "office")
        self.assertNotIn("typical", cfg)
        self.assertIn("ignored unknown typical", sources[-1])
        with self.assertRaises(settings.SettingsError):   # a typo in the file you edit is still an error
            settings.resolve({}, {"typical": "BR-S"})

    def test_a_name_ending_in_s_takes_a_bare_apostrophe(self):
        self.assertEqual(truth.possessive("Kestrel Valley Motors"), "Kestrel Valley Motors'")
        self.assertEqual(truth.possessive("Plant A"), "Plant A's")

    def test_a_tilted_watermark_stays_inside_its_box(self):
        import math
        g = Graph(sync.default_template().find("diagram[@id='physical']"))
        box = (100, 100, 1400, 300)   # a wide, flat card
        mark = truth.watermark(g, "EXAMPLE", "why", box)
        geo = next(o for o in g.root.iter("object") if o.get("id") == mark).find("mxCell/mxGeometry")
        x, y, w, h = (float(geo.get(k)) for k in ("x", "y", "width", "height"))
        s, c = math.sin(math.radians(18)), math.cos(math.radians(18))
        self.assertLessEqual(w * s + h * c, box[3] + 0.5)
        self.assertAlmostEqual(y + h / 2, box[1] + box[3] / 2)

    def test_quality_colours_and_trend_on_a_first_build(self):
        self.assertNotEqual(quality._color(0.98, 3), quality.GREEN)   # 3 missing is not done
        self.assertEqual(quality._color(1.0, 0), quality.GREEN)
        self.assertIn("new", quality._trend_text(None))
        template = sync.default_template()
        sync.fill(template, sample_export(), today="2026-10-12")   # no previous quality.json
        text = page_text(template.find("diagram[@id='quality']"))
        self.assertIn("first build", text)
        self.assertNotIn("points since last build", text)

    def test_rooms_straight_under_a_building_are_not_floors(self):
        export = sample_export()
        export["locations"] = [{"id": 1, "name": "Main building", "slug": "main", "parent": None},
                               {"id": 2, "name": "MDF", "slug": "mdf", "parent": {"id": 1}},
                               {"id": 3, "name": "Shop", "slug": "shop", "parent": {"id": 1}}]
        for n, d in enumerate(export["devices"]):
            d["location"] = {"id": 2 + n % 2, "name": ("MDF", "Shop")[n % 2], "slug": ("mdf", "shop")[n % 2]}
        text = page_text(riser.page(export, sync.ENDPOINT_ROLES, "https://netbox.example", "S01"))
        self.assertIn("1 building · no floor locations", text)
        self.assertNotIn("0 floors", text)
        self.assertNotIn("1 floor ", text)

    def test_runs_between_side_by_side_buildings_skip_the_ground_line(self):
        template = sync.default_template()
        sync.fill(template, campus_export(), today="2026-10-16")
        text = page_text(template.find(f"diagram[@id='{riser.PAGE_ID}']"))
        self.assertIn("runs between buildings", text)
        self.assertNotIn("ground · runs between buildings", text)

    def test_a_template_stack_with_no_netbox_device_is_drawn_as_a_slot(self):
        g = Graph(sync.default_template().find("diagram[@id='physical']"))
        box = next(i for i, el in g.els.items() if el.get("placeholders") == "1" and el.get("name")
                   and not sync._is_device(el) and g.descendants(i))
        name = g.els[box].get("name")
        for d in g.descendants(box):
            g.els[d].set("name", "")
        gaps.mark_empty(g, sync._is_device, {name}, set(), name.split("-")[0] + "-")
        self.assertIn("dashed=1", cell_of(g.els[box]).get("style"))

    def test_the_segaudit_card_fits_its_text_and_keeps_off_the_edge(self):
        with profiles.use(profiles.get("office")):
            mxfile = drawio.render(drawio.blank_site())
        card = next(c for c in mxfile.iter("mxCell") if "SegAudit reads" in (c.get("value") or ""))
        geo = card.find("mxGeometry")
        self.assertLessEqual(float(geo.get("height")), 80)
        self.assertLessEqual(float(geo.get("x")) + float(geo.get("width")), drawio.PAGE_W - 2 * drawio.MARGIN)

    def test_a_stack_label_changes_only_when_its_count_is_wrong(self):
        one = [{"device_type": {"model": "Catalyst 9300-48UXM"}}]
        two = one * 2
        self.assertEqual(truth._model_count("<b>S01-IT-CORE</b> · SVL 2×100G", two), "<b>S01-IT-CORE</b> · SVL 2×100G")
        self.assertEqual(truth._model_count("<b>X</b><br>C9300-48UXM ×2 · mGig", two), "<b>X</b><br>C9300-48UXM ×2 · mGig")
        self.assertEqual(truth._model_count("<b>X</b><br>C9300-48UXM ×3 · mGig", one),
                         "<b>X</b><br>Catalyst 9300-48UXM · mGig")
