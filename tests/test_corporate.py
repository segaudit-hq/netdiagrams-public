"""The corporate standard (C01 template, Sable Ridge HQ campus sample, C11 branch draft)."""

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
from netdiagrams.graph import Graph, plain
from netdiagrams.model import build_site

SCRIPTS = Path(__file__).parent.parent / "scripts"
TODAY = "2026-10-18"


def scripts(*names):
    """The generator modules, imported from scripts/."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        return [__import__(n) for n in names]
    finally:
        sys.path.remove(str(SCRIPTS))


def corporate_export():
    return json.loads(resources.files("netdiagrams").joinpath("data", "sample-corporate.json").read_text("utf-8"))


def starter_export():
    return scripts("make_corporate_sample")[0].starter()


def branch_export():
    return scripts("make_corporate_sample")[0].branch()


def text_of(root: ET.Element) -> str:
    return ET.tostring(root, "unicode")


def devices_on(root: ET.Element) -> set[str]:
    return {el.get("name") for el in root.iter("object") if el.get("role") and el.get("name")}


def page(template: ET.Element, page_id: str) -> Graph:
    return Graph(next(d for d in template.findall("diagram") if d.get("id") == page_id))


def found_gaps(export: dict) -> dict:
    locations = ot.Locations(export.get("locations"))
    with profiles.use("corporate"):
        return {k: len(g.names) for k, g in
                gaps.find(export, sync.endpoint_roles(), lambda d: ot.device_zones(d, locations)).items() if g.names}


class Profile(unittest.TestCase):
    def test_the_corporate_profile_is_registered(self):
        corp = profiles.get("corporate")
        self.assertEqual((corp.site_code, corp.template), ("C01", "C01-Corporate-Template.drawio"))
        self.assertEqual([b[0] for b in corp.bands], ["OUT", "EDGE", "USERS", "DC", "SHARED", "MGMT"])
        self.assertEqual(len(corp.zone_names), 20)
        self.assertFalse(corp.levels)
        self.assertIn("sox", corp.scopes)
        self.assertEqual(corp.book_url, "https://netdiagrams.com/books/corporate-network-diagrams/")

    def test_every_corporate_zone_lands_in_its_band(self):
        with profiles.use("corporate"):
            for slug in profiles.current().zone_names:
                self.assertNotEqual(model.band_for_zone(slug)[0], "?", slug)

    def test_the_sample_picks_the_corporate_profile_itself(self):
        report = sync.fill(sync.default_template("corporate"), corporate_export(), today=TODAY)
        self.assertEqual(report.profile, "corporate")
        self.assertEqual(profiles.current().name, "manufacturing")

    def test_names_follow_the_standard(self):
        self.assertEqual(found_gaps(corporate_export()).get("bad_name"), None)


class CorporateSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template("corporate")
        cls.report = sync.fill(cls.template, corporate_export(), today=TODAY)
        cls.xml = text_of(cls.template)

    def test_every_sample_device_is_drawn_or_counted(self):
        drawn = devices_on(self.template)
        for name in ("C01-EFW-01", "C01-ISFW-02", "C01-SDW-01", "C01-CORE-02", "C01-DIST-S-02", "C01-DCSW-01",
                     "C01-WLC-02", "C01-HV-08", "C01-HV-L2", "C01-SAN-01", "C01-BKP-01", "C01-NVR-02", "C01-OOB-02",
                     "C01-UPS-A", "C01-UPS-C2", "C01-ACC-S4-3", "C01-BADGE-N", "C01-BMS-S"):
            self.assertIn(name, drawn)
        self.assertIn("×10", self.xml)  # each floor's access points, counted on one card
        self.assertFalse(self.report.missing_cables)
        self.assertFalse(self.report.netbox_only_cables)  # every cable is on a drawn line or a counted card
        self.assertNotIn("HSRP", self.xml)  # the core pair is one StackWise Virtual switch, like DIST-S
        self.assertFalse(self.report.netbox_only_devices)  # nothing waits in a tray
        self.assertFalse(self.report.glance)

    def test_the_registers_stay_on_the_physical_sheet(self):
        ids = [d.get("id") for d in self.template.findall("diagram")]
        self.assertNotIn("physical-registers", ids)
        self.assertIn("riser", ids)
        self.assertFalse(self.report.oversize)

    def test_no_other_industry_wording_reaches_a_corporate_drawing(self):
        for word in ("Plant A", "S01-", "Purdue level", "PLC ×", "Alder &amp; Finch", "O01-"):
            self.assertNotIn(word, self.xml, word)
        self.assertIn("Draw Secure Corporate Network Diagrams", self.xml)

    def test_each_zone_table_lists_its_vlans_with_their_vrf(self):
        export = corporate_export()
        zone_of = {v["vid"]: v["tags"][0]["slug"] for v in export["vlans"]}
        vrf_of = {p["vlan"]["vid"]: (p.get("vrf") or {}).get("name", "") for p in export["prefixes"] if p.get("vlan")}
        g = page(self.template, "logical")
        checked = 0
        for table in g.tables():
            header = g.header(table)
            if header[:2] != ["VLAN", "NAME"]:
                continue
            self.assertIn("VRF", header)
            zone = sync._zone_of_table(g, table)
            for row in g.rows(table)[1:]:
                cells = {h: plain(g.value(g.els[c])) for h, c in zip(header, g.row_cells(row))}
                if cells["VLAN"].isdigit():
                    vid = int(cells["VLAN"])
                    self.assertEqual(zone_of[vid], zone, f"VLAN {vid} in the {zone} table")
                    self.assertEqual(cells["VRF"], vrf_of[vid], vid)  # the VRF column, not appended to the gateway
                    if vrf_of[vid]:
                        self.assertNotIn(vrf_of[vid], cells["GATEWAY"].split(" · "), vid)
                    checked += 1
        self.assertEqual(checked, len(zone_of))

    def test_a_table_without_a_vrf_column_keeps_the_vrf_in_the_gateway(self):
        export = corporate_export()
        with profiles.use("corporate"):
            nb = sync.NetBoxIndex(export)
            g = page(sync.default_template("corporate"), "logical")
            table = next(t for t in g.tables() if g.header(t)[:2] == ["VLAN", "NAME"]
                         and sync._zone_of_table(g, t) == "zone-corp")
            rows = sync._vlan_rows(g, table, ["VLAN", "NAME", "SUBNET", "GATEWAY · VRF"], nb)
        self.assertEqual(rows[0][3][0], "Core pair .1 · CORP")

    def test_example_sheets_say_whose_example_they_are(self):
        self.assertIn("EXAMPLE", self.xml)
        self.assertIn("Sable Ridge", self.xml)
        for sheet in ("flows", "failover", "multisite"):
            self.assertIn(f"{sheet}-example", self.xml)

    def test_the_flow_sheet_has_every_flow_and_the_default_deny(self):
        g = page(self.template, "flows")
        texts = " ".join(plain(g.value(el)) for el in g.els.values())
        for n in range(1, 34):
            self.assertIn(f"F{n:02d}", texts)
        self.assertIn("Default deny", texts)


class SettledDetails(unittest.TestCase):
    """The details settled after the first draft of sample-site.md (2026-10-18)."""

    @classmethod
    def setUpClass(cls):
        cls.export = corporate_export()
        cls.ifaces = {(i["device"]["name"], i["name"]): i for i in cls.export["interfaces"]}

    def tagged(self, device: str, lag: str) -> set:
        return {v["vid"] for v in self.ifaces[(device, lag)]["tagged_vlans"]}

    def test_wireless_vlans_ride_only_the_controller_link(self):
        wireless = {115, 199, 215, 700}
        self.assertLessEqual(wireless, self.tagged("C01-CORE-01", "Po42"))
        for (dev, name), i in self.ifaces.items():
            if dev.startswith("C01-ACC-") or name.startswith(("Po1", "Po2", "Po3")):
                self.assertFalse(wireless & {v["vid"] for v in i["tagged_vlans"]}, (dev, name))

    def test_legal_wired_nc_and_the_floor_trunks(self):
        vlan = next(v for v in self.export["vlans"] if v["vid"] == 211)
        prefix = next(p for p in self.export["prefixes"] if (p.get("vlan") or {}).get("vid") == 211)
        self.assertEqual((vlan["name"], vlan["tags"][0]["slug"]), ("LEGAL-WIRED-NC", "zone-legal"))
        self.assertEqual((prefix["prefix"], prefix["vrf"]["name"]), ("10.1.52.0/22", "LEGAL"))
        self.assertEqual(self.tagged("C01-CORE-01", "Po11"), {110, 120, 130, 211, 800, 810, 820, 850, 990})
        self.assertEqual(self.tagged("C01-CORE-01", "Po31"), {112, 120, 130, 211, 800, 810, 820, 850, 990})
        self.assertEqual(self.tagged("C01-DIST-S-01", "Po21"), {111, 120, 130, 210, 800, 810, 820, 850, 990})

    def test_dmz_lag_and_hundred_gig_peer_links(self):
        self.assertEqual(self.tagged("C01-EFW-01", "Po44"), {600, 610})
        self.assertEqual(self.tagged("C01-DCSW-02", "Po44"), {600, 610})
        for dev, port in (("C01-CORE-01", "Hu1/0/50"), ("C01-DIST-S-01", "Hu1/0/27"), ("C01-DCSW-01", "Eth1/53")):
            self.assertEqual(self.ifaces[(dev, port)]["type"]["value"], "100gbase-x-qsfp28", dev)

    def test_layer2_paths_to_the_leafs_and_the_guest_interface(self):
        self.assertEqual(self.tagged("C01-CORE-01", "Po45"), {990})
        self.assertEqual(self.tagged("C01-DCSW-01", "Po45"), {990})
        self.assertEqual(self.tagged("C01-EFW-02", "Po46"), {199, 700})
        # Po40 and Po42 leave MDF-N for DC-N: fiber, not DAC.
        for c in self.export["cables"]:
            if c["description"] in ("Po40", "Po42", "Po45", "Po46"):
                self.assertEqual(c["type"], "mmf-om4", c["label"])

    def test_vpn_pool_and_core_gateways(self):
        prefixes = {p["prefix"]: p for p in self.export["prefixes"]}
        self.assertIn("10.250.0.0/21", prefixes)
        self.assertEqual(prefixes["10.1.16.0/21"]["custom_fields"]["gateway"], "Core pair .1")
        cores = {d["name"]: d["virtual_chassis"]["name"] for d in self.export["devices"]
                 if d["name"].startswith("C01-CORE-")}
        self.assertEqual(cores, {"C01-CORE-01": "C01-CORE", "C01-CORE-02": "C01-CORE"})


class Branch(unittest.TestCase):
    def test_branch_draft_uses_corporate_shapes_and_bands(self):
        with profiles.use("corporate"):
            xml = text_of(drawio.render(build_site(branch_export()), segaudit_note=False))
            printer = stencils.shape_for_role("printer")
            library = stencils.library()
        for text in ("ZONE Corporate users", "ZONE Legal users", "ZONE Guests", "C11-FW-01", "by band"):
            self.assertIn(text, xml)
        self.assertNotIn("Purdue", xml)
        self.assertEqual(printer, "Printer / MFP (asset)")
        self.assertIn(printer, library)

    def test_branch_wifi_switches_locally(self):
        export = branch_export()
        self.assertTrue(export["wireless_lans"])
        self.assertEqual({w["custom_fields"].get("wlan_switching") for w in export["wireless_lans"]}, {"local"})
        self.assertFalse(set(found_gaps(export)) - {"model_no_eos"})  # end of support sits on the device types


class DayOne(unittest.TestCase):
    def test_starter_export_has_the_gaps_the_book_describes(self):
        export = starter_export()
        found = found_gaps(export)
        self.assertEqual(found.get("no_zone"), 12)  # the ten Commons cameras and the two legal hosts
        self.assertEqual(found.get("cable_no_label"), 1)  # P2P-NS-W
        self.assertGreater(sum(1 for p in export["prefixes"] if not p.get("vrf")),
                           sum(1 for p in corporate_export()["prefixes"] if not p.get("vrf")))
        south = [d for d in export["devices"] if d["name"].startswith("C01-ACC-S")]
        self.assertTrue(south and all(d["position"] is None for d in south))
        today = export["exported_at"][:10]   # no backup or patch dated after the starter's own export
        self.assertEqual([d["name"] for d in export["devices"] for k in ("last_config_backup", "last_patched")
                          if (d.get("custom_fields") or {}).get(k, "") > today], [])


class Generated(unittest.TestCase):
    """The bundled template, sample and stencils are exactly what their scripts write."""

    def test_bundled_files_match_their_generators(self):
        sample, stencil_script, template = scripts("make_corporate_sample", "make_corporate_stencils",
                                                   "make_corporate_template")
        data = resources.files("netdiagrams").joinpath("data")
        tree = template.build()
        ET.indent(tree, space=" ")
        self.assertEqual(ET.tostring(tree, encoding="unicode") + "\n",
                         data.joinpath("C01-Corporate-Template.drawio").read_text("utf-8"))
        self.assertEqual(json.dumps(sample.hq(), indent=1, ensure_ascii=False) + "\n",
                         data.joinpath("sample-corporate.json").read_text("utf-8"))
        shapes = [stencil_script.entry(*shape) for shape in stencil_script.SHAPES]
        self.assertEqual("<mxlibrary>" + json.dumps(shapes, ensure_ascii=False, indent=0) + "</mxlibrary>\n",
                         data.joinpath("Corporate-Stencils.xml").read_text("utf-8"))
        self.assertEqual({title for title, *_ in stencil_script.SHAPES},
                         set(profiles.get("corporate").role_shapes.values()))


sys.path.insert(0, str(Path(__file__).parent))
import test_netdiagrams as base  # noqa: E402  (the render gate, run here over the corporate samples)


class CorporateRenderGate(base.RenderGate):
    """The definition of done over the HQ sample and its day-one starter."""

    EXPORTS = {"corporate": corporate_export, "corporate-starter": starter_export}

    @classmethod
    def setUpClass(cls):
        cls.built = {}
        for name, make in cls.EXPORTS.items():
            export = make()
            template = sync.default_template("corporate")
            report = sync.fill(template, export, today=TODAY)
            cls.built[name] = (export, template, report)

    def setUp(self):
        token = profiles._current.set(profiles.get("corporate"))
        self.addCleanup(profiles._current.reset, token)

    def test_rack_pills_read_the_device_they_sit_in(self):
        # The base test fills the manufacturing small site into this profile's template; here, the HQ and its
        # day one, whose South stacks have no rack positions yet.
        for name, (_, template, _) in self.built.items():
            pills = [o for o in template.iter("object") if "%rack%" in (o.get("label") or "")]
            self.assertTrue(pills, name)
            self.assertFalse([o.get("id") for o in pills if o.get("rack") == ""], name)

    def test_two_builds_from_the_same_data_are_identical(self):
        a, b = sync.default_template("corporate"), sync.default_template("corporate")
        sync.fill(a, starter_export(), today=TODAY)
        sync.fill(b, starter_export(), today=TODAY)
        self.assertEqual(ET.tostring(a), ET.tostring(b))


class Commands(unittest.TestCase):
    def run_cli(self, *args) -> int:
        with redirect_stdout(io.StringIO()):
            return cli.main(list(args))

    def test_netbox_setup_emits_the_corporate_zones_and_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_cli("netbox-setup", "--profile", "corporate", "--offline", "-o", tmp), 0)
            tags = (Path(tmp) / "3-zone-tags.csv").read_text("utf-8")
            roles = (Path(tmp) / "4-device-roles.csv").read_text("utf-8")
        for slug in profiles.get("corporate").zone_names:
            self.assertIn(f",{slug},", tags)
        used = {d["role"]["slug"] for d in corporate_export()["devices"]}
        for slug in used:
            self.assertIn(f",{slug},", roles)
        self.assertIn("SD-WAN hub,sdwan-hub", roles)
        self.assertNotIn("purdue", (tags + roles).lower())

    def test_corporate_stencil_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "corporate.xml"
            self.assertEqual(self.run_cli("stencils", "--profile", "corporate", "-o", str(out)), 0)
            self.assertIn("DC leaf switch (asset)", out.read_text("utf-8"))

    def test_draft_and_blank_lay_out_the_six_bands(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "c11.json"
            src.write_text(json.dumps(branch_export()))
            out = Path(tmp) / "c11.drawio"
            self.assertEqual(self.run_cli("draft", "--profile", "corporate", "--input", str(src), "-o", str(out)), 0)
            self.assertIn("C11-ACC-1", out.read_text("utf-8"))
            blank = Path(tmp) / "blank.drawio"
            self.assertEqual(self.run_cli("blank", "--profile", "corporate", "-o", str(blank)), 0)
            text = blank.read_text("utf-8")
            for zone in profiles.get("corporate").blank_zones:
                self.assertIn(f"ZONE {zone} (rename me)", text)


if __name__ == "__main__":
    unittest.main()
