"""The local government standard (M01 template, City of Halvern sample)."""

import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from importlib import resources
from pathlib import Path

from netdiagrams import audit, cli, drawio, gaps, model, ot, profiles, stencils, sync
from netdiagrams.model import build_site

FIXTURES = Path(__file__).parent / "fixtures"
SCRIPTS = Path(__file__).parent.parent / "scripts"


def city_export():
    return json.loads(resources.files("netdiagrams").joinpath("data", "sample-municipal.json").read_text("utf-8"))


def library_export():
    return json.loads((FIXTURES / "municipal-lb1.json").read_text("utf-8"))


def scripts(*names):
    sys.path.insert(0, str(SCRIPTS))
    try:
        return [__import__(n) for n in names]
    finally:
        sys.path.remove(str(SCRIPTS))


def starter_export():
    return scripts("make_city_sample")[0].starter()


def text_of(root: ET.Element) -> str:
    return ET.tostring(root, "unicode")


def devices_on(root: ET.Element) -> set[str]:
    return {el.get("name") for el in root.iter("object") if el.get("role") and el.get("name")}


def found_gaps(export) -> dict:
    with profiles.use("municipal"):
        return gaps.find(export, sync.endpoint_roles(),
                         lambda d: ot.device_zones(d, ot.Locations(export.get("locations"))))


class Profile(unittest.TestCase):
    def test_the_municipal_profile_is_registered(self):
        city = profiles.get("municipal")
        self.assertEqual((city.site_code, city.template), ("CH1", "M01-Municipal-Template.drawio"))
        self.assertEqual([b[0] for b in city.bands], ["OUT", "EDGE", "PUBLIC", "CITY", "SAFETY", "FAC"])
        self.assertFalse(city.levels)
        self.assertEqual(city.scopes[:2], ("cjis", "pci-cde"))

    def test_the_sample_picks_the_municipal_profile_itself(self):
        report = sync.fill(sync.default_template("municipal"), library_export(), today="2026-10-18")
        self.assertEqual(report.profile, "municipal")
        self.assertEqual(profiles.current().name, "manufacturing")

    def test_every_city_zone_lands_in_its_band(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            from city_template import site as S
        finally:
            sys.path.remove(str(SCRIPTS))
        with profiles.use("municipal"):
            self.assertEqual(set(profiles.current().zone_names), {z[0] for z in S.ZONES})
            for slug, _short, _title, band, *_ in S.ZONES:
                self.assertEqual(model.band_for_zone(slug)[0], band, slug)

    def test_the_naming_standard_takes_every_city_site(self):
        import re
        naming = re.compile(profiles.get("municipal").naming)
        for name in ("CH1-FW-01", "LB1-AP-02", "PW1-ACC-1", "FS3-FW-01", "CH1-ACC-PD-2"):
            self.assertTrue(naming.match(name), name)
        self.assertFalse(naming.match("O01-FW-01"))


class CitySample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template("municipal")
        cls.report = sync.fill(cls.template, city_export(), today="2026-10-18")
        cls.xml = text_of(cls.template)

    def test_every_sample_device_is_drawn_or_counted(self):
        drawn = devices_on(self.template)
        for name in ("CH1-FW-01", "CH1-FW-02", "CH1-CORE-2", "CH1-ACC-PD-2", "CH1-STATE-RTR", "CH1-PD-NAS-01",
                     "CH1-UPS-03", "CH1-TSC-01", "CH1-BAS-01"):
            self.assertIn(name, drawn)
        self.assertIn("×5", self.xml)  # floor 1's APs, the council chamber's included, on one card
        self.assertFalse(self.report.missing_cables)
        self.assertFalse(self.report.netbox_only_cables)
        self.assertFalse(self.report.glance)

    def test_no_other_industrys_wording_reaches_a_city_drawing(self):
        for word in ("Plant A", "S01-", "Purdue level", "PLC ×", "Alder", "O01-"):
            self.assertNotIn(word, self.xml, word)
        self.assertIn("Draw Secure Local Government Network Diagrams", self.xml)

    def test_each_zone_table_lists_only_that_zones_vlans(self):
        from netdiagrams.graph import Graph
        zone_of = {v["vid"]: v["tags"][0]["slug"] for v in city_export()["vlans"]}
        g = Graph(next(d for d in self.template.findall("diagram") if d.get("id") == "logical"))
        checked = 0
        for table in g.tables():
            if g.header(table)[:2] != ["VLAN", "NAME"]:
                continue
            zone = sync._zone_of_table(g, table)
            for row in g.rows(table)[1:]:
                vid = g.value(g.els[g.row_cells(row)[0]])
                if vid.isdigit():
                    self.assertEqual(zone_of[int(vid)], zone, f"VLAN {vid} in the {zone} table")
                    checked += 1
        self.assertEqual(checked, len(zone_of))

    def test_example_sheets_say_whose_example_they_are(self):
        self.assertIn("Halvern", self.xml)
        self.assertIn("EXAMPLE", self.xml)


class PoliceWall(unittest.TestCase):
    """The book's CJIS claims, held against the sample."""

    def test_the_police_trunk_carries_only_police_voice_and_management(self):
        export = city_export()
        pd_ports = [i for i in export["interfaces"] if i["device"]["name"].startswith("CH1-ACC-PD")
                    and i["lag"] and i["lag"]["name"] == "Po13"]
        self.assertEqual(len(pd_ports), 2)
        for i in pd_ports:
            self.assertEqual({v["vid"] for v in i["tagged_vlans"]}, {20, 60, 62, 99})

    def test_pd_secure_is_broadcast_in_the_police_wing_only(self):
        for i in city_export()["interfaces"]:
            if i["name"].startswith("radio"):
                police = i["device"]["name"].startswith("CH1-AP-PD")
                ssids = {w["ssid"] for w in i["wireless_lans"]}
                if police:
                    self.assertLessEqual(ssids, {"PD-SECURE"})
                else:
                    self.assertNotIn("PD-SECURE", ssids)

    def test_police_own_their_gear_and_the_subnets_carry_the_cjis_scope(self):
        export = city_export()
        with profiles.use("municipal"):
            ev = audit.Evidence(export, None, sync.endpoint_roles())
        checks = ev.checks("2026-10-18")
        self.assertEqual(checks["no_owner"][0], [])
        self.assertEqual(checks["no_physical_access"][0], [])
        self.assertEqual(sorted(f.name for f in ev.devices.values() if "pci-cde" in f.scope), ["CH1-PAY-01",
                                                                                               "CH1-PAY-02"])
        self.assertIn("CH1-PD-HV-01", [f.name for f in ev.devices.values() if "cjis" in f.scope])
        owners = {(c["object_type"], c["object_id"]): c["contact"]["name"] for c in export["contact_assignments"]
                  if c["role"]["slug"] == "asset-owner"}
        ids = {d["name"]: d["id"] for d in export["devices"]}
        self.assertEqual(owners[("dcim.device", ids["CH1-PD-NAS-01"])], "Police department")
        self.assertEqual(owners[("dcim.device", ids["CH1-PAY-01"])], "Finance director")
        self.assertEqual(owners[("dcim.device", ids["CH1-TSC-01"])], "Public works director")
        self.assertEqual(owners[("dcim.device", ids["CH1-STATE-RTR"])], "State CJIS agency")
        # Until core offers 'cjis' as a Compliance scope choice, it is the only value reported as unknown.
        self.assertTrue(all("= cjis" in v for v in checks.get("audit_bad_values", ([],))[0]))
        self.assertEqual(sorted(checks["stale_patch"][0]), ["CH1-DOOR-01", "CH1-OOB-01", "CH1-STATE-RTR",
                                                            "CH1-UPS-01", "CH1-UPS-02", "CH1-UPS-03"])

    def test_day_one_records_none(self):
        with profiles.use("municipal"):
            self.assertFalse(audit.Evidence(starter_export(), None, sync.endpoint_roles()).any)


class Library(unittest.TestCase):
    def test_library_build_renames_and_drops_what_it_lacks(self):
        template = sync.default_template("municipal")
        with profiles.use("municipal"):
            sync.fill(template, library_export(), today="2026-10-18")
        drawn = devices_on(template)
        self.assertIn("LB1-FW-01", drawn)
        self.assertFalse([n for n in drawn if n.startswith("CH1-")])
        self.assertIn('id="overview-example-1"', text_of(template))

    def test_library_draft_uses_city_shapes_and_zone_names(self):
        with profiles.use("municipal"):
            xml = text_of(drawio.render(build_site(library_export()), segaudit_note=False))
            pc = stencils.shape_for_role("public-pc")
            library = stencils.library()
        self.assertIn("ZONE Public Wi-Fi", xml)
        self.assertNotIn("Purdue", xml)
        self.assertEqual(pc, "Public PC (asset)")
        self.assertIn(pc, library)

    def test_wifi_and_hardware_are_fully_described(self):
        for export in (city_export(), library_export()):
            found = found_gaps(export)
            for check in ("wlan_no_manager", "wlan_no_fields", "wlan_no_vlan", "wlan_guest_controls",
                          "wlan_review_open", "wlan_review_psk", "fibre_no_optic", "item_no_serial",
                          "no_criticality", "no_zone", "bad_name"):
                self.assertFalse(found.get(check) and found[check].names, (export["site"]["name"], check))
            self.assertNotIn("auth_psk", json.dumps(export))
        optics = [i for i in city_export()["inventory_items"] if i["role"]["slug"] == "transceiver"]
        self.assertEqual(len(optics), 8)  # both ends of the floor 2 and police wing fibre uplinks


class DayOne(unittest.TestCase):
    def test_starter_export_has_the_gaps_the_book_describes(self):
        found = {k: len(g.names) for k, g in found_gaps(starter_export()).items()}
        self.assertEqual(found.get("no_zone"), 6)
        self.assertEqual(found.get("cable_no_label"), 2)
        self.assertEqual(found.get("vlan_no_prefix"), 1)
        self.assertGreater(found.get("no_serial", 0), 20)
        self.assertEqual(found.get("wlan_no_manager"), 12)
        self.assertEqual(found.get("wlan_no_fields"), 3)
        self.assertEqual(found.get("wlan_guest_controls"), 1)
        self.assertEqual(found.get("fibre_no_optic"), 8)
        self.assertEqual(found.get("no_criticality"), 47)


sys.path.insert(0, str(Path(__file__).parent))
import test_netdiagrams as base  # noqa: E402  (the render gate, run here over the city fixtures)


class Generated(unittest.TestCase):
    """The bundled template, samples and stencils are exactly what their scripts write."""

    def test_bundled_files_match_their_generators(self):
        sample, stencil_script, template_script = scripts("make_city_sample", "make_city_stencils",
                                                          "make_city_template")
        data = resources.files("netdiagrams").joinpath("data")
        tree = template_script.build()
        ET.indent(tree, space=" ")
        self.assertEqual(ET.tostring(tree, encoding="unicode") + "\n",
                         data.joinpath("M01-Municipal-Template.drawio").read_text("utf-8"))
        for made, bundled in ((sample.ch1(), data.joinpath("sample-municipal.json")),
                              (sample.lb1(), FIXTURES / "municipal-lb1.json")):
            self.assertEqual(json.dumps(made, indent=1, ensure_ascii=False) + "\n", bundled.read_text("utf-8"))
        shapes = [stencil_script.entry(*shape) for shape in stencil_script.SHAPES]
        self.assertEqual("<mxlibrary>" + json.dumps(shapes, ensure_ascii=False, indent=0) + "</mxlibrary>\n",
                         data.joinpath("Municipal-Stencils.xml").read_text("utf-8"))
        self.assertEqual({title for title, *_ in stencil_script.SHAPES},
                         set(profiles.get("municipal").role_shapes.values()))


class MunicipalRenderGate(base.RenderGate):
    """The definition of done over the city sample, its day-one starter and the library."""

    EXPORTS = {"municipal": city_export, "municipal-starter": starter_export, "municipal-lb1": library_export}

    @classmethod
    def setUpClass(cls):
        cls.built = {}
        for name, make in cls.EXPORTS.items():
            export = make()
            template = sync.default_template("municipal")
            report = sync.fill(template, export, today="2026-10-18")
            cls.built[name] = (export, template, report)

    def setUp(self):
        token = profiles._current.set(profiles.get("municipal"))
        self.addCleanup(profiles._current.reset, token)

    def test_two_builds_from_the_same_data_are_identical(self):
        a, b = sync.default_template("municipal"), sync.default_template("municipal")
        sync.fill(a, starter_export(), today="2026-10-18")
        sync.fill(b, starter_export(), today="2026-10-18")
        self.assertEqual(ET.tostring(a), ET.tostring(b))


class Commands(unittest.TestCase):
    def run_cli(self, *args) -> int:
        with redirect_stdout(io.StringIO()):
            return cli.main(list(args))

    def test_settings_choose_the_municipal_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = library_export()
            del library["site"]["custom_fields"]["netdiagrams"]  # the file chooses the profile, not NetBox
            src = Path(tmp) / "lb1.json"
            src.write_text(json.dumps(library))
            (Path(tmp) / "netdiagrams.json").write_text(json.dumps({"profile": "municipal"}))
            out = Path(tmp) / "lb1.drawio"
            self.assertEqual(self.run_cli("build", "--input", str(src), "-o", str(out)), 0)
            self.assertIn("LB1-FW-01", out.read_text("utf-8"))

    def test_netbox_setup_for_cities_has_the_city_zones_and_no_ot_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_cli("netbox-setup", "--profile", "municipal", "--offline", "-o", tmp), 0)
            written = "".join(p.read_text("utf-8") for p in Path(tmp).rglob("*") if p.is_file())
        for slug in ("zone-cjis", "zone-water", "zone-field", "payment-terminal", "signal-system"):
            self.assertIn(slug, written)
        self.assertNotIn("purdue", written.lower())

    def test_city_stencil_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "city.xml"
            self.assertEqual(self.run_cli("stencils", "--profile", "municipal", "-o", str(out)), 0)
            self.assertIn("Traffic signal system (asset)", out.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
