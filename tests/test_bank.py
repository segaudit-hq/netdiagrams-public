"""The bank standard (B01 template, Ninebark Community Bank sample)."""

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


def scripts(*names):
    sys.path.insert(0, str(SCRIPTS))
    try:
        return [__import__(n) for n in names]
    finally:
        sys.path.remove(str(SCRIPTS))


def bank_export():
    return json.loads(resources.files("netdiagrams").joinpath("data", "sample-bank.json").read_text("utf-8"))


def branch_export():
    return json.loads((FIXTURES / "bank-b02.json").read_text("utf-8"))


def starter_export():
    return scripts("make_bank_sample")[0].starter()


def text_of(root: ET.Element) -> str:
    return ET.tostring(root, "unicode")


def devices_on(root: ET.Element) -> set[str]:
    return {el.get("name") for el in root.iter("object") if el.get("role") and el.get("name")}


def found_gaps(export) -> dict:
    with profiles.use("bank"):
        return {k: g.names for k, g in gaps.find(export, sync.endpoint_roles(), lambda d: ot.device_zones(
            d, ot.Locations(export.get("locations")))).items()}


class Profile(unittest.TestCase):
    def test_the_bank_profile_is_registered(self):
        bank = profiles.get("bank")
        self.assertEqual((bank.site_code, bank.template), ("B01", "B01-Bank-Template.drawio"))
        self.assertEqual([b[0] for b in bank.bands], ["OUT", "EDGE", "BANK", "SERV", "CUST", "MGMT"])
        self.assertFalse(bank.levels)
        self.assertEqual(bank.scopes, ("glba", "pci-cde", "sox"))

    def test_the_profile_matches_the_site_facts(self):
        site = scripts("bank_template.site")[0].site
        bank = profiles.get("bank")
        self.assertEqual(list(bank.bands), [tuple(b) for b in site.BANDS])
        self.assertEqual(bank.zone_names, {z[0]: z[2] for z in site.ZONES})

    def test_every_bank_zone_lands_in_its_band(self):
        site = scripts("bank_template.site")[0].site
        with profiles.use("bank"):
            for slug, _, _, band, *_ in site.ZONES:
                self.assertEqual(model.band_for_zone(slug)[0], band, slug)

    def test_the_sample_picks_the_bank_profile_itself(self):
        report = sync.fill(sync.default_template("bank"), branch_export(), today="2026-10-15")
        self.assertEqual(report.profile, "bank")
        self.assertEqual(profiles.current().name, "manufacturing")


class BankSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template("bank")
        cls.report = sync.fill(cls.template, bank_export(), today="2026-10-15")
        cls.xml = text_of(cls.template)

    def test_every_sample_device_is_drawn_or_counted(self):
        drawn = devices_on(self.template)
        for name in ("B01-FW-01", "B01-FW-02", "B01-CPR-01", "B01-CORE-1", "B01-ACC-F2-2", "B01-NAS-01",
                     "B01-UPS-02", "B01-WIRE-01", "B01-CARD-01", "B01-ALARM-01"):
            self.assertIn(name, drawn)
        for count in ("×6", "×9", "×2"):  # floor 2's APs, floor 1's cameras, the ATMs, recyclers, wire PCs
            self.assertIn(count, self.xml)
        self.assertFalse(self.report.missing_cables)
        self.assertFalse(self.report.netbox_only_cables)
        self.assertFalse(self.report.glance)

    def test_no_other_industry_wording_reaches_a_bank_drawing(self):
        for word in ("Plant A", "S01-", "Purdue level", "PLC ×", "Alder", "O01-"):
            self.assertNotIn(word, self.xml, word)
        self.assertIn("Draw Secure Bank and Credit Union Network Diagrams", self.xml)

    def test_each_zone_table_lists_only_that_zones_vlans(self):
        from netdiagrams.graph import Graph
        zone_of = {v["vid"]: v["tags"][0]["slug"] for v in bank_export()["vlans"]}
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
        self.assertIn("Ninebark", self.xml)
        self.assertIn("EXAMPLE", self.xml)

    def test_the_sample_is_complete_and_wifi_is_described(self):
        found = found_gaps(bank_export())
        for check in ("no_zone", "no_serial", "no_criticality", "cable_no_label", "vlan_no_prefix", "fibre_no_optic",
                      "item_no_serial", "wlan_no_manager", "wlan_no_fields", "wlan_guest_controls", "no_owner"):
            self.assertFalse(found.get(check), check)
        self.assertNotIn("auth_psk", json.dumps(bank_export()))


class Branch(unittest.TestCase):
    def test_branch_build_renames_and_drops_what_it_lacks(self):
        template = sync.default_template("bank")
        with profiles.use("bank"):
            sync.fill(template, branch_export(), today="2026-10-15")
        drawn = devices_on(template)
        self.assertIn("B02-FW-01", drawn)
        self.assertNotIn("B02-FW-02", drawn)
        self.assertFalse([n for n in drawn if n.startswith("B01-")])
        self.assertIn('id="overview-example-1"', text_of(template))  # the main office's promises are an example

    def test_branch_draft_uses_bank_shapes_and_zone_names(self):
        with profiles.use("bank"):
            xml = text_of(drawio.render(build_site(branch_export()), segaudit_note=False))
            atm = stencils.shape_for_role("atm")
            library = stencils.library()
        self.assertIn("ZONE Teller line", xml)
        self.assertIn("ZONE Lobby guests", xml)
        self.assertNotIn("Purdue", xml)
        self.assertEqual(atm, "ATM (asset)")
        self.assertIn(atm, library)

    def test_branch_wifi_and_vlans_are_its_own(self):
        export = branch_export()
        vids = {v["vid"] for v in export["vlans"]}
        self.assertEqual({(w["ssid"], w["vlan"]["vid"]) for w in export["wireless_lans"]},
                         {("NB-STAFF", 20), ("NB-GUEST", 70)})
        for i in export["interfaces"]:
            used = {v["vid"] for v in i["tagged_vlans"]} | {(i.get("untagged_vlan") or {}).get("vid")} - {None}
            self.assertLessEqual(used, vids, i["name"])
        found = found_gaps(export)
        for check in ("no_zone", "no_criticality", "wlan_no_manager", "wlan_no_fields", "no_owner"):
            self.assertFalse(found.get(check), check)


class AuditEvidence(unittest.TestCase):
    def test_main_office_records_owners_and_evidence_with_a_few_findings(self):
        with profiles.use("bank"):
            ev = audit.Evidence(bank_export(), None, sync.endpoint_roles())
        checks = ev.checks("2026-10-15")
        self.assertEqual(checks["no_owner"][0], [])
        self.assertEqual(checks["no_physical_access"][0], [])
        # The provider's router has no backup or patch date: we hold no login. The alarm panel and NVR lag.
        self.assertEqual(sorted(checks["stale_backup"][0]), ["B01-CPR-01", "B01-OOB-01"])
        self.assertEqual(sorted(checks["stale_patch"][0]), ["B01-ALARM-01", "B01-CPR-01", "B01-NVR-01"])
        self.assertEqual(checks["no_log_forwarding"][0], ["B01-NVR-01"])
        self.assertEqual(sorted(f.name for f in ev.devices.values() if "pci-cde" in f.scope),
                         ["B01-ATM-01", "B01-ATM-02", "B01-CARD-01"])
        glba = {f.name for f in ev.devices.values() if "glba" in f.scope}
        self.assertLessEqual({"B01-TCR-01", "B01-WIRE-01", "B01-HV-01", "B01-NAS-01"}, glba)
        self.assertNotIn("B01-ATM-01", glba)

    def test_day_one_records_none(self):
        with profiles.use("bank"):
            self.assertFalse(audit.Evidence(starter_export(), None, sync.endpoint_roles()).any)


class DayOne(unittest.TestCase):
    def test_starter_export_has_the_gaps_the_book_describes(self):
        found = {k: len(v) for k, v in found_gaps(starter_export()).items()}
        self.assertEqual(found.get("no_zone"), 12)        # the cameras
        self.assertEqual(found.get("cable_no_label"), 2)  # the floor 2 uplink
        self.assertEqual(found.get("vlan_no_prefix"), 1)  # VLAN 81
        self.assertGreater(found.get("no_serial", 0), 20)
        self.assertEqual(found.get("wlan_no_manager"), 10)
        self.assertEqual(found.get("wlan_no_fields"), 2)
        self.assertEqual(found.get("fibre_no_optic"), 4)
        self.assertEqual(found.get("no_criticality"), 49)

    def test_the_starter_scores_lower_and_says_what_to_fix(self):
        scores = {}
        for name, export in (("b01", bank_export()), ("starter", starter_export())):
            template = sync.default_template("bank")
            report = sync.fill(template, export, today="2026-10-15")
            scores[name] = report.quality.score
            if name == "starter":
                xml = text_of(template)
        self.assertLess(scores["starter"], scores["b01"])
        self.assertIn("Plan to improve this page", xml)


sys.path.insert(0, str(Path(__file__).parent))
import test_netdiagrams as base  # noqa: E402  (the render gate, run here over the bank fixtures)


class Generated(unittest.TestCase):
    """The bundled template, samples and stencils are exactly what their scripts write."""

    def test_bundled_files_match_their_generators(self):
        sample, stencil_script, template_script = scripts("make_bank_sample", "make_bank_stencils",
                                                          "make_bank_template")
        data = resources.files("netdiagrams").joinpath("data")
        tree = template_script.build()
        ET.indent(tree, space=" ")
        self.assertEqual(ET.tostring(tree, encoding="unicode") + "\n",
                         data.joinpath("B01-Bank-Template.drawio").read_text("utf-8"))
        for made, bundled in ((sample.hq(), data.joinpath("sample-bank.json")),
                              (sample.branch(), FIXTURES / "bank-b02.json")):
            self.assertEqual(json.dumps(made, indent=1, ensure_ascii=False) + "\n", bundled.read_text("utf-8"))
        shapes = [stencil_script.entry(*shape) for shape in stencil_script.SHAPES]
        self.assertEqual("<mxlibrary>" + json.dumps(shapes, ensure_ascii=False, indent=0) + "</mxlibrary>\n",
                         data.joinpath("Bank-Stencils.xml").read_text("utf-8"))
        self.assertEqual({title for title, *_ in stencil_script.SHAPES},
                         set(profiles.get("bank").role_shapes.values()))

    def test_the_template_draws_the_site_facts(self):
        site = scripts("bank_template.site")[0].site
        xml = (resources.files("netdiagrams").joinpath("data", "B01-Bank-Template.drawio").read_text("utf-8"))
        root = ET.fromstring(xml)
        drawn = devices_on(root)
        for d in site.DEVICES:
            if d["role"] not in ("access-point", "camera", "printer", "atm", "cash-recycler", "wire-workstation"):
                self.assertIn(d["name"], drawn)
        for vid, name, *_ in site.VLANS:
            self.assertIn(f">{name}<", xml.replace('value="', ">").replace('"', "<"), name)
        for fid, *_ in site.FLOWS:
            self.assertIn(fid, xml)
        for c in site.CABLES[:15]:  # the backbone, in the link register and on the page
            for label in c["labels"]:
                self.assertIn(label, xml)


class BankRenderGate(base.RenderGate):
    """The definition of done over the bank sample, its day-one starter and the B02 branch."""

    EXPORTS = {"bank": bank_export, "bank-starter": starter_export, "bank-b02": branch_export}

    @classmethod
    def setUpClass(cls):
        cls.built = {}
        for name, make in cls.EXPORTS.items():
            export = make()
            template = sync.default_template("bank")
            report = sync.fill(template, export, today="2026-10-15")
            cls.built[name] = (export, template, report)

    def setUp(self):
        token = profiles._current.set(profiles.get("bank"))
        self.addCleanup(profiles._current.reset, token)

    def test_two_builds_from_the_same_data_are_identical(self):
        a, b = sync.default_template("bank"), sync.default_template("bank")
        sync.fill(a, starter_export(), today="2026-10-15")
        sync.fill(b, starter_export(), today="2026-10-15")
        self.assertEqual(ET.tostring(a), ET.tostring(b))


class Commands(unittest.TestCase):
    def run_cli(self, *args) -> int:
        with redirect_stdout(io.StringIO()):
            return cli.main(list(args))

    def test_sample_and_blank_for_banks(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bank.drawio"
            self.assertEqual(self.run_cli("sample", "--profile", "bank", "-o", str(out)), 0)
            self.assertIn("Ninebark", out.read_text("utf-8"))
            blank = Path(tmp) / "blank.drawio"
            self.assertEqual(self.run_cli("blank", "--profile", "bank", "-o", str(blank)), 0)

    def test_netbox_setup_for_banks_offers_glba_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_cli("netbox-setup", "--profile", "bank", "--offline", "-o", tmp), 0)
            written = "".join(p.read_text("utf-8") for p in Path(tmp).rglob("*") if p.is_file())
        self.assertIn("zone-wire", written)
        self.assertIn("glba", written)
        self.assertNotIn("purdue", written.lower())

    def test_bank_stencil_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bank.xml"
            self.assertEqual(self.run_cli("stencils", "--profile", "bank", "-o", str(out)), 0)
            self.assertIn("Teller cash recycler (asset)", out.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
