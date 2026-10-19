"""The retail profile (R01): its generator, its stores, and the core's definition of done run over them."""
import io
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from importlib import resources
from pathlib import Path
from unittest import mock

import test_netdiagrams as base
from netdiagrams import cli, gaps, ot, profiles, quality, stencils, sync, truth
from netdiagrams.graph import Graph


class Retail(unittest.TestCase):
    """The retail profile: the R01 store standard drawn for Store 014 and built for the other stores."""

    @staticmethod
    def make_retail_module():
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_retail",
                                                      Path(__file__).parent.parent / "scripts" / "make_retail.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @classmethod
    def store(cls, code: str) -> dict:
        make = cls.make_retail_module()
        return make.export({"ST014": make.STORE, "ST027": make.ST027, "ST031": make.ST031}[code])

    @classmethod
    def setUpClass(cls):
        cls.builds = {}
        for code in ("ST014", "ST027", "ST031"):
            template = sync.default_template("retail")
            cls.builds[code] = (template, sync.fill(template, cls.store(code), today="2026-10-15"))

    def test_bundled_sample_and_template_match_the_generator(self):
        make = self.make_retail_module()
        data = resources.files("netdiagrams").joinpath("data")
        self.assertEqual(json.loads(data.joinpath("sample-retail-st014.json").read_text("utf-8")),
                         json.loads(json.dumps(make.export(make.STORE))))
        tree = make.build_template()
        ET.indent(tree, space="  ")
        self.assertEqual(data.joinpath("R01-Retail-Store-Template.drawio").read_text("utf-8"),
                         ET.tostring(tree, encoding="unicode"))
        self.assertEqual(data.joinpath("R01-Retail-Stencils.xml").read_text("utf-8"), make.build_stencils())
        self.assertEqual(profiles.get("retail").role_shapes, make.ROLE_SHAPES)

    def test_stencils_carry_a_shape_for_every_store_role(self):
        with profiles.use("retail"):
            lib = stencils.library()
            for role in ("firewall", "lte-router", "pos-terminal", "pin-pad", "pos-server", "camera", "nvr"):
                with self.subTest(role=role):
                    self.assertIn(stencils.shape_for_role(role), lib)
            self.assertIn("zone band R2 · CARDHOLDER DATA (CDE)", lib)
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "r.xml"
                self.assertGreater(stencils.write_library(out), 14)
                self.assertIn("PIN pad (asset)", out.read_text("utf-8"))

    def test_region_field_picks_the_retail_profile(self):
        for code, (template, report) in self.builds.items():
            with self.subTest(store=code):
                self.assertEqual(report.profile, "retail")
                self.assertEqual(report.site_code, code)
                self.assertIn("netdiagrams field on region Retail estate", report.markdown(code))

    def test_store_014_is_drawn_page_for_page(self):
        template, report = self.builds["ST014"]
        self.assertEqual(report.netbox_only_devices, [])
        self.assertEqual(report.removed_devices, [])
        self.assertEqual(report.quality.score, 100)
        self.assertNotIn("glance", [d.get("id") for d in template.findall("diagram")])

    def test_other_stores_fit_the_template(self):
        _, st027 = self.builds["ST027"]
        self.assertEqual(sorted(st027.grouped), ["ST027-PED-03", "ST027-POS-03"])
        self.assertEqual(st027.netbox_only_devices, [])
        template, st031 = self.builds["ST031"]
        self.assertIn("ST014-NVR-01", st031.removed_devices)
        self.assertEqual(st031.netbox_only_devices, [])
        names = {o.get("name") for o in template.iter("object") if sync._is_device(o)}
        self.assertFalse({n for n in names if n.startswith("ST014-")})
        self.assertLess(st031.quality.score, 100)  # the fit-out's missing serial and zone
        failing = {c.key: c.names for c in st031.quality.checks if c.names}
        self.assertIn("ST031-SIGN-01", [n for names in failing.values() for n in names])
        self.assertIn("ST031-CNT-01", [n for names in failing.values() for n in names])

    def test_cables_match_by_label_in_every_store(self):
        # Labels follow the A-side port, so the template's cables are every store's cables. The drops of
        # ST027's fourth lane are folded into lane 3's shapes and counted there, so they are not off-drawing.
        for code, (template, report) in self.builds.items():
            with self.subTest(store=code):
                self.assertEqual(report.netbox_only_cables, [])
                self.assertIn("drawn but not in NetBox (shown dashed): 0", report.markdown(code))

    def test_overview_speaks_retail(self):
        template, _ = self.builds["ST027"]
        g = Graph(next(d for d in template.findall("diagram") if d.get("id") == "overview"))
        text = " ".join(g.value(el) for el in g.els.values())
        self.assertIn("What NetBox says about this store", text)
        self.assertIn("Card data", text)
        self.assertIn("separate card data zone", text)
        self.assertNotIn("plant", text.lower())
        self.assertNotIn("Purdue", text)

    def test_zone_tables_fill_without_purdue_levels(self):
        template, report = self.builds["ST014"]
        titles = [t for page, t, n in report.tables]
        self.assertIn("ZONE / BAND / OWNER", titles)
        self.assertIn("VLANS / ZONE / BAND", titles)
        g = Graph(next(d for d in template.findall("diagram") if d.get("id") == "register"))
        table = next(t for t in g.tables() if g.header(t)[:3] == ["ZONE", "BAND", "OWNER"])
        rows = [[g.value(g.els[c]) for c in g.row_cells(r)] for r in g.rows(table)[1:]]
        self.assertIn("POS team", [r[2] for r in rows if r[0].startswith("CDE")][0])

    def test_naming_standard_and_zone_gap_follow_the_profile(self):
        export = self.store("ST031")
        with profiles.use("retail"):
            self.assertLessEqual({"pos-terminal", "pin-pad", "pos-server"}, sync.endpoint_roles())
            found = gaps.find(export, sync.endpoint_roles(), lambda d: ot.device_zones(d), "2026-10-15")
        self.assertEqual(found["bad_name"].names, [])
        self.assertEqual(found["no_zone"].names, ["ST031-CNT-01"])
        self.assertIn("store systems owner", found["no_zone"].how)
        self.assertNotIn("pin-pad", sync.endpoint_roles())
        found = gaps.find(export, sync.endpoint_roles(), lambda d: ot.device_zones(d), "2026-10-15")
        self.assertEqual(len(found["bad_name"].names), len(export["devices"]))  # S01's standard is S01-…

    def test_sample_command_writes_the_retail_store(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(["sample", "--profile", "retail", "-o", str(Path(tmp) / "s.drawio")]), 0)
            self.assertIn("Store 014", out.getvalue())
            self.assertIn("Store 014 — Logical Architecture".replace("Store 014", "ST014 · Store 014"),
                          (Path(tmp) / "s.drawio").read_text("utf-8"))


class RetailRenderGate(base.RenderGate):
    """The core render gate over the retail estate: the template's own store, a bigger one, a fit-out."""

    @classmethod
    def setUpClass(cls):
        cls.built = {}
        for code in ("ST014", "ST027", "ST031"):
            export = Retail.store(code)
            template = sync.default_template("retail")
            cls.built[f"retail-{code}"] = (export, template, sync.fill(template, export, today="2026-10-12"))

    def test_two_builds_from_the_same_data_are_identical(self):
        export = Retail.store("ST027")
        a, b = sync.default_template("retail"), sync.default_template("retail")
        sync.fill(a, export, today="2026-10-12")
        sync.fill(b, export, today="2026-10-12")
        self.assertEqual(ET.tostring(a), ET.tostring(b))

    def test_examples_are_marked_and_guides_hidden_on_every_fixture(self):
        with mock.patch.object(truth, "EXAMPLE_SHEETS", profiles.get("retail").example_sheets):
            super().test_examples_are_marked_and_guides_hidden_on_every_fixture()
