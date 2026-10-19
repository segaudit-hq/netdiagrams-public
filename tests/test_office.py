"""The office standard (O01 template, Alder & Finch sample) and the industry switch."""

import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from importlib import resources
from pathlib import Path

from netdiagrams import cli, drawio, gaps, model, ot, profiles, stencils, sync
from netdiagrams.model import build_site

FIXTURES = Path(__file__).parent / "fixtures"
SCRIPTS = Path(__file__).parent.parent / "scripts"


def office_export():
    return json.loads(resources.files("netdiagrams").joinpath("data", "sample-office.json").read_text("utf-8"))


def branch_export():
    return json.loads((FIXTURES / "office-o02.json").read_text("utf-8"))


def text_of(root: ET.Element) -> str:
    return ET.tostring(root, "unicode")


def devices_on(root: ET.Element) -> set[str]:
    return {el.get("name") for el in root.iter("object") if el.get("role") and el.get("name")}


class Profile(unittest.TestCase):
    def test_the_office_profile_is_registered(self):
        office = profiles.get("office")
        self.assertEqual((office.site_code, office.template), ("O01", "O01-Office-Template.drawio"))
        self.assertEqual([b[0] for b in office.bands], ["OUT", "EDGE", "STAFF", "SHARED", "MGMT"])
        self.assertFalse(office.levels)

    def test_the_sample_picks_the_office_profile_itself(self):
        report = sync.fill(sync.default_template("office"), branch_export(), today="2026-10-15")
        self.assertEqual(report.profile, "office")
        self.assertEqual(profiles.current().name, "manufacturing")  # and leaves the default in force after

    def test_every_office_zone_lands_in_its_band(self):
        with profiles.use("office"):
            for slug in profiles.current().zone_names:
                self.assertNotEqual(model.band_for_zone(slug)[0], "?", slug)


class OfficeSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template("office")
        cls.report = sync.fill(cls.template, office_export(), today="2026-10-15")
        cls.xml = text_of(cls.template)

    def test_every_sample_device_is_drawn_or_counted(self):
        drawn = devices_on(self.template)
        for name in ("O01-FW-01", "O01-FW-02", "O01-CORE-1", "O01-ACC-F3-2", "O01-NAS-01", "O01-UPS-02"):
            self.assertIn(name, drawn)
        self.assertIn("×8", self.xml)  # the access points on each floor, counted on one card
        self.assertFalse(self.report.missing_cables)
        self.assertFalse(self.report.netbox_only_cables)  # a counted card's own drops are on the drawing
        self.assertFalse(self.report.glance)  # counting by design is not "bigger than the template"

    def test_no_manufacturing_wording_reaches_an_office_drawing(self):
        for word in ("Plant A", "S01-", "Purdue level", "PLC ×"):
            self.assertNotIn(word, self.xml, word)
        self.assertIn("Draw Secure Small Office Network Diagrams", self.xml)

    def test_each_zone_table_lists_only_that_zones_vlans(self):
        from netdiagrams.graph import Graph
        zone_of = {v["vid"]: v["tags"][0]["slug"] for v in office_export()["vlans"]}
        g = Graph(next(d for d in self.template.findall("diagram") if d.get("id") == "logical"))
        checked = 0
        for table in g.tables():
            header = g.header(table)
            if header[:2] != ["VLAN", "NAME"]:
                continue
            zone = sync._zone_of_table(g, table)
            for row in g.rows(table)[1:]:
                vid = g.value(g.els[g.row_cells(row)[0]])
                if vid.isdigit():
                    self.assertEqual(zone_of[int(vid)], zone, f"VLAN {vid} in the {zone} table")
                    checked += 1
        self.assertEqual(checked, len(zone_of))

    def test_example_sheets_say_whose_example_they_are(self):
        self.assertIn("Alder &amp; Finch", self.xml)
        self.assertIn("EXAMPLE", self.xml)


class SmallBranch(unittest.TestCase):
    def test_branch_build_renames_and_drops_what_it_lacks(self):
        template = sync.default_template("office")
        with profiles.use("office"):
            sync.fill(template, branch_export(), today="2026-10-15")
        drawn = devices_on(template)
        self.assertIn("O02-FW-01", drawn)
        self.assertNotIn("O02-FW-02", drawn)
        self.assertFalse([n for n in drawn if n.startswith("O01-")])
        titles = [el.get("value") for el in template.iter("mxCell") if "fontSize=22" in (el.get("style") or "")]
        self.assertTrue(titles)
        self.assertFalse([t for t in titles if "Finch HQ" in t])  # 'Alder &amp; Finch HQ' is renamed too
        # HQ's promises (a firewall pair, two UPSs) are stamped EXAMPLE, and no HQ-only fact is stated as the branch's.
        xml = text_of(template)
        self.assertIn('id="overview-example-1"', xml)
        self.assertNotIn("a pair of firewalls", xml)
        self.assertNotIn("Two virtualization hosts", xml)

    def test_branch_draft_uses_office_shapes_and_zone_names(self):
        with profiles.use("office"):
            xml = text_of(drawio.render(build_site(branch_export()), segaudit_note=False))
            printer = stencils.shape_for_role("printer")
            library = stencils.library()
        self.assertIn("ZONE Printers", xml)
        self.assertIn("ZONE Guests", xml)  # a zone only VLANs carry is named from its tag too
        root = ET.fromstring(xml)
        names = {el.get("id"): el.get("name") for el in root.iter("object")}
        racked = {names.get(el.find("mxCell").get("parent")) for el in root.iter("object")
                  if "%rack%" in (el.get("label") or "")}
        self.assertEqual(racked, {"O02-FW-01", "O02-ACC-1"})  # the APs and printer have no rack, so no pill
        self.assertIn("by band", xml)
        self.assertNotIn("Purdue", xml)
        self.assertEqual(printer, "Printer / MFP (asset)")
        self.assertIn(printer, library)

    def test_branch_wifi_is_its_own(self):
        export = branch_export()
        vids = {v["vid"] for v in export["vlans"]}
        self.assertEqual({(w["ssid"], w["vlan"]["vid"]) for w in export["wireless_lans"]},
                         {("AF-STAFF", 10), ("AF-GUEST", 70)})
        for w in export["wireless_lans"]:
            self.assertEqual((w["scope_type"], w["scope_id"]), ("dcim.site", export["site"]["id"]))
        for i in export["interfaces"]:
            used = {v["vid"] for v in i["tagged_vlans"]} | {(i.get("untagged_vlan") or {}).get("vid")} - {None}
            self.assertLessEqual(used, vids, i["name"])  # an AP or its switch port trunks only O02's VLANs
        radios = [i for i in export["interfaces"] if i["name"].startswith("radio")]
        self.assertEqual(len(radios), 6)  # two tri-band APs
        for i in radios:  # each radio broadcasts only Riverside's SSIDs
            self.assertLessEqual({w["ssid"] for w in i["wireless_lans"]}, {"AF-STAFF", "AF-GUEST"})

    def test_wifi_is_fully_described(self):
        """Both sites say how their APs are run, and every SSID has the fields the wireless checks want."""
        for export in (office_export(), branch_export()):
            with profiles.use("office"):
                found = gaps.find(export, sync.endpoint_roles(),
                                  lambda d: ot.device_zones(d, ot.Locations(export.get("locations"))))
            for check in ("wlan_no_manager", "wlan_no_fields", "wlan_no_vlan", "wlan_guest_controls",
                          "wlan_review_open", "wlan_review_psk"):
                self.assertFalse(found.get(check) and found[check].names, (export["site"]["name"], check))
            self.assertNotIn("auth_psk", json.dumps(export))

    def test_every_fibre_end_has_its_optic(self):
        """HQ's floor 3 uplinks are the only fibre: each end carries an SR optic with a serial, and the core's
        PSUs and fan trays are recorded too, so none of the hardware checks fire on the sample."""
        export = office_export()
        with profiles.use("office"):
            found = gaps.find(export, sync.endpoint_roles(),
                              lambda d: ot.device_zones(d, ot.Locations(export.get("locations"))))
        for check in ("fibre_no_optic", "item_no_serial", "module_no_serial", "no_criticality"):
            self.assertFalse(found.get(check) and found[check].names, check)
        optics = [i for i in export["inventory_items"] if i["role"]["slug"] == "transceiver"]
        self.assertEqual(len(optics), 4)
        self.assertTrue(all(i["component_type"] == "dcim.interface" and i["serial"] for i in optics))


class AuditEvidence(unittest.TestCase):
    def test_hq_records_owners_and_evidence_with_a_few_findings(self):
        """Every HQ device has an owner and room access; the CUI file servers are in scope; the findings are
        the ones Chapter 14 names: the console server's backup, four unpatched boxes, and the NVR's logs."""
        from netdiagrams import audit
        export = office_export()
        with profiles.use("office"):
            ev = audit.Evidence(export, None, sync.endpoint_roles())
        checks = ev.checks("2026-10-15")
        self.assertTrue(ev.any)
        self.assertEqual(checks["no_owner"][0], [])
        self.assertEqual(checks["no_physical_access"][0], [])
        self.assertEqual(checks["stale_backup"][0], ["O01-OOB-01"])
        self.assertEqual(sorted(checks["stale_patch"][0]), ["O01-DOOR-01", "O01-OOB-01", "O01-UPS-01", "O01-UPS-02"])
        self.assertEqual(checks["no_log_forwarding"][0], ["O01-NVR-01"])
        self.assertEqual(sorted(f.name for f in ev.devices.values() if "cui" in f.scope),
                         ["O01-HV-01", "O01-HV-02", "O01-NAS-01"])

    def test_day_one_records_none(self):
        from netdiagrams import audit
        with profiles.use("office"):
            self.assertFalse(audit.Evidence(starter_export(), None, sync.endpoint_roles()).any)


class DayOne(unittest.TestCase):
    def test_starter_export_has_the_gaps_the_book_describes(self):
        export = starter_export()
        locations = ot.Locations(export.get("locations"))
        with profiles.use("office"):
            found = {k: len(g.names) for k, g in
                     gaps.find(export, sync.endpoint_roles(), lambda d: ot.device_zones(d, locations)).items()}
        self.assertEqual(found.get("no_zone"), 10)
        self.assertEqual(found.get("cable_no_label"), 2)
        self.assertGreater(found.get("no_serial", 0), 20)
        # Wireless LANs imported before the wireless fields existed: the checks name what to add.
        self.assertEqual(found.get("wlan_no_manager"), 16)
        self.assertEqual(found.get("wlan_no_fields"), 3)
        self.assertEqual(found.get("wlan_guest_controls"), 1)
        # The optics were never entered; the PSUs and fans in the core member with no serial have none.
        self.assertEqual(found.get("fibre_no_optic"), 4)
        self.assertEqual(found.get("item_no_serial"), 4)
        # Nobody has rated the assets yet: the criticality field comes with netbox-setup.
        self.assertEqual(found.get("no_criticality"), 53)


sys.path.insert(0, str(Path(__file__).parent))
import test_netdiagrams as base  # noqa: E402  (the render gate, run here over the office fixtures)


def starter_export():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import make_office_sample
    finally:
        sys.path.remove(str(SCRIPTS))
    return make_office_sample.starter()


class Generated(unittest.TestCase):
    """The bundled template, samples and stencils are exactly what their scripts write."""

    def test_bundled_files_match_their_generators(self):
        sys.path.insert(0, str(SCRIPTS))
        try:
            import make_office_sample
            import make_office_stencils
            import make_office_template
        finally:
            sys.path.remove(str(SCRIPTS))
        data = resources.files("netdiagrams").joinpath("data")
        tree = make_office_template.build()
        ET.indent(tree, space=" ")
        self.assertEqual(ET.tostring(tree, encoding="unicode") + "\n",
                         data.joinpath("O01-Office-Template.drawio").read_text("utf-8"))
        for made, bundled in ((make_office_sample.hq(), data.joinpath("sample-office.json")),
                              (make_office_sample.branch(), FIXTURES / "office-o02.json")):
            self.assertEqual(json.dumps(made, indent=1, ensure_ascii=False) + "\n", bundled.read_text("utf-8"))
        shapes = [make_office_stencils.entry(*shape) for shape in make_office_stencils.SHAPES]
        self.assertEqual("<mxlibrary>" + json.dumps(shapes, ensure_ascii=False, indent=0) + "</mxlibrary>\n",
                         data.joinpath("Office-Stencils.xml").read_text("utf-8"))
        self.assertEqual({title for title, *_ in make_office_stencils.SHAPES},
                         set(profiles.get("office").role_shapes.values()))


class OfficeRenderGate(base.RenderGate):
    """The definition of done over the office sample, its day-one starter and the small branch."""

    EXPORTS = {"office": office_export, "office-starter": starter_export, "office-o02": branch_export}

    @classmethod
    def setUpClass(cls):
        cls.built = {}
        for name, make in cls.EXPORTS.items():
            export = make()
            template = sync.default_template("office")
            report = sync.fill(template, export, today="2026-10-15")
            cls.built[name] = (export, template, report)

    def setUp(self):
        token = profiles._current.set(profiles.get("office"))
        self.addCleanup(profiles._current.reset, token)

    def test_two_builds_from_the_same_data_are_identical(self):
        a, b = sync.default_template("office"), sync.default_template("office")
        sync.fill(a, starter_export(), today="2026-10-15")
        sync.fill(b, starter_export(), today="2026-10-15")
        self.assertEqual(ET.tostring(a), ET.tostring(b))


class Commands(unittest.TestCase):
    def run_cli(self, *args) -> int:
        with redirect_stdout(io.StringIO()):
            return cli.main(list(args))

    def test_settings_choose_the_office_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "o02.json"
            src.write_text(json.dumps(branch_export()))
            (Path(tmp) / "netdiagrams.json").write_text(json.dumps({"profile": "office"}))
            out = Path(tmp) / "o02.drawio"
            branch = branch_export()
            del branch["site"]["custom_fields"]["netdiagrams"]  # the file chooses the profile, not NetBox
            src.write_text(json.dumps(branch))
            self.assertEqual(self.run_cli("build", "--input", str(src), "-o", str(out)), 0)
            self.assertIn("O02-FW-01", out.read_text("utf-8"))

    def test_netbox_setup_for_offices_has_no_ot_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_cli("netbox-setup", "--profile", "office", "--offline", "-o", tmp), 0)
            written = "".join(p.read_text("utf-8") for p in Path(tmp).rglob("*") if p.is_file())
        self.assertIn("zone-guest", written)
        self.assertNotIn("purdue", written.lower())

    def test_office_stencil_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "office.xml"
            self.assertEqual(self.run_cli("stencils", "--profile", "office", "-o", str(out)), 0)
            self.assertIn("Door controller (asset)", out.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
