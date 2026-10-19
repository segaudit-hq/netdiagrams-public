"""The hotel standard (H01 template, Alder Bay sample)."""

import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from importlib import resources
from pathlib import Path

from netdiagrams import cli, gaps, model, ot, profiles, stencils, sync

FIXTURES = Path(__file__).parent / "fixtures"
SCRIPTS = Path(__file__).parent.parent / "scripts"


def hotel_export():
    return json.loads(resources.files("netdiagrams").joinpath("data", "sample-hotel.json").read_text("utf-8"))


def branch_export():
    return json.loads((FIXTURES / "hotel-h02.json").read_text("utf-8"))


def scripts(*names):
    sys.path.insert(0, str(SCRIPTS))
    try:
        return [__import__(n) for n in names]
    finally:
        sys.path.remove(str(SCRIPTS))


def starter_export():
    return scripts("make_hotel_sample")[0].starter()


def text_of(root: ET.Element) -> str:
    return ET.tostring(root, "unicode")


def devices_on(root: ET.Element) -> set[str]:
    return {el.get("name") for el in root.iter("object") if el.get("role") and el.get("name")}


def found_gaps(export) -> dict:
    with profiles.use("hotel"):
        found = gaps.find(export, sync.endpoint_roles(),
                          lambda d: ot.device_zones(d, ot.Locations(export.get("locations"))))
    return {k: g.names for k, g in found.items() if g.names}


class Profile(unittest.TestCase):
    def test_the_hotel_profile_is_registered(self):
        hotel = profiles.get("hotel")
        self.assertEqual((hotel.site_code, hotel.template), ("H01", "H01-Hotel-Template.drawio"))
        self.assertEqual([b[0] for b in hotel.bands], ["OUT", "EDGE", "BUSINESS", "GUEST", "BUILDING"])
        self.assertEqual(hotel.scopes, ("pci-cde", "pci-connected"))
        self.assertFalse(hotel.levels)

    def test_the_sample_picks_the_hotel_profile_itself(self):
        report = sync.fill(sync.default_template("hotel"), branch_export(), today="2026-10-15")
        self.assertEqual(report.profile, "hotel")
        self.assertEqual(profiles.current().name, "manufacturing")  # and leaves the default in force after

    def test_every_hotel_zone_lands_in_its_band(self):
        with profiles.use("hotel"):
            for slug in profiles.current().zone_names:
                self.assertNotEqual(model.band_for_zone(slug)[0], "?", slug)


class HotelSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = sync.default_template("hotel")
        cls.report = sync.fill(cls.template, hotel_export(), today="2026-10-15")
        cls.xml = text_of(cls.template)

    def test_every_sample_device_is_drawn_or_counted(self):
        drawn = devices_on(self.template)
        for name in ("H01-FW-01", "H01-FW-02", "H01-BRAND-RTR-01", "H01-GW-01", "H01-CORE-1", "H01-ACC-F6-2",
                     "H01-POS-SRV-01", "H01-BMS-01", "H01-ELEV-01"):
            self.assertIn(name, drawn)
        self.assertIn("×16", self.xml)  # a guest floor's in-room APs, counted on one card
        self.assertFalse(self.report.missing_cables)
        self.assertFalse(self.report.netbox_only_cables)
        self.assertFalse(self.report.netbox_only_devices)  # nothing falls to the tray
        self.assertFalse(self.report.glance)

    def test_no_manufacturing_wording_reaches_a_hotel_drawing(self):
        for word in ("Plant A", "S01-", "Purdue level", "PLC ×", "Alder &amp; Finch"):
            self.assertNotIn(word, self.xml, word)
        self.assertIn("Draw Secure Hotel Network Diagrams", self.xml)

    def test_each_zone_table_lists_only_that_zones_vlans(self):
        from netdiagrams.graph import Graph
        zone_of = {v["vid"]: v["tags"][0]["slug"] for v in hotel_export()["vlans"]}
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

    def test_the_firewall_ports_read_netbox_addresses(self):
        for address in ("203.0.113.2/29", "10.40.250.1/29", "10.40.251.1/29"):
            self.assertIn(address, self.xml)

    def test_example_sheets_say_whose_example_they_are(self):
        self.assertIn("Alder Bay", self.xml)
        self.assertIn("EXAMPLE", self.xml)

    def test_the_brand_router_and_guest_gateway_are_third_party(self):
        tenants = {d["name"]: (d.get("tenant") or {}).get("name") for d in hotel_export()["devices"]}
        self.assertEqual(tenants["H01-BRAND-RTR-01"], "Larkline Hotels")
        self.assertEqual(tenants["H01-GW-01"], "Guest Wi-Fi vendor")
        self.assertIsNone(tenants["H01-FW-01"])


class SisterProperty(unittest.TestCase):
    def test_h02_build_renames_and_drops_what_it_lacks(self):
        template = sync.default_template("hotel")
        with profiles.use("hotel"):
            sync.fill(template, branch_export(), today="2026-10-15")
        drawn = devices_on(template)
        self.assertIn("H02-FW-01", drawn)
        self.assertNotIn("H02-FW-02", drawn)
        self.assertFalse([n for n in drawn if n.startswith("H01-")])
        # H01's promises are stamped EXAMPLE; its line count and firewall pair are not stated as H02's.
        xml = text_of(template)
        self.assertIn('id="overview-example-1"', xml)
        self.assertNotIn("Two internet lines", xml)
        self.assertNotIn("the firewall pair:", xml)
        logical = next(d for d in template.findall("diagram") if d.get("id") == "logical")
        self.assertIn("ISP-B-01", text_of(logical.find(".//*[@id='logical-gaps-card-t-r1-c2']")))  # flagged, not stated

    def test_h02_draft_uses_hotel_shapes(self):
        with profiles.use("hotel"):
            terminal = stencils.shape_for_role("payment-terminal")
            library = stencils.library()
        self.assertEqual(terminal, "Card terminal (asset)")
        self.assertIn(terminal, library)

    def test_h02_wifi_is_its_own(self):
        export = branch_export()
        vids = {v["vid"] for v in export["vlans"]}
        for w in export["wireless_lans"]:
            self.assertEqual((w["scope_type"], w["scope_id"]), ("dcim.site", export["site"]["id"]))
            self.assertIn(w["vlan"]["vid"], vids)
        for i in export["interfaces"]:
            used = {v["vid"] for v in i["tagged_vlans"]} | {(i.get("untagged_vlan") or {}).get("vid")} - {None}
            self.assertLessEqual(used, vids, i["name"])


class Wireless(unittest.TestCase):
    def test_wifi_is_fully_described(self):
        for export in (hotel_export(), branch_export()):
            found = found_gaps(export)
            for check in ("wlan_no_manager", "wlan_no_fields", "wlan_no_vlan", "wlan_guest_controls",
                          "wlan_review_open"):
                self.assertNotIn(check, found, (export["site"]["name"], check))
            self.assertNotIn("auth_psk", json.dumps(export))

    def test_the_events_ssid_is_not_a_staff_zone(self):
        # The staff-zone pattern matches whole words, so "events" no longer reads as "ent".
        self.assertNotIn("wlan_review_psk", found_gaps(hotel_export()))

    def test_room_tech_is_vlan_61_and_only_floor_1_aps_carry_pay(self):
        export = hotel_export()
        ssids = {w["ssid"]: w["vlan"]["vid"] for w in export["wireless_lans"]}
        self.assertEqual(ssids["AB-ROOMTECH"], 61)
        for i in export["interfaces"]:
            if i["device"]["name"].startswith("H01-AP-") and i["name"] == "eth0":
                tagged = {v["vid"] for v in i["tagged_vlans"]}
                self.assertEqual((i["untagged_vlan"] or {}).get("vid"), 99)
                self.assertEqual(22 in tagged, "-F1-" in i["device"]["name"], i["device"]["name"])


class Hardware(unittest.TestCase):
    def test_every_fibre_end_has_its_optic(self):
        export = hotel_export()
        found = found_gaps(export)
        for check in ("fibre_no_optic", "item_no_serial", "module_no_serial", "no_criticality", "prefix_no_zone"):
            self.assertNotIn(check, found, check)
        optics = [i for i in export["inventory_items"] if i["role"]["slug"] == "transceiver"]
        self.assertEqual(len(optics), 24)  # six floor uplinks, two fibres each, an optic at both ends
        self.assertTrue(all(i["component_type"] == "dcim.interface" and i["serial"] for i in optics))


class AuditEvidence(unittest.TestCase):
    def test_h01_records_owners_and_evidence_with_a_few_findings(self):
        from netdiagrams import audit
        with profiles.use("hotel"):
            ev = audit.Evidence(hotel_export(), None, sync.endpoint_roles())
        checks = ev.checks("2026-10-15")
        self.assertTrue(ev.any)
        self.assertEqual(checks["no_owner"][0], [])
        self.assertEqual(checks["no_physical_access"][0], [])
        self.assertEqual(sorted(checks["stale_backup"][0]), ["H01-BRAND-RTR-01", "H01-ELEV-01", "H01-GW-01"])
        self.assertEqual(sorted(checks["stale_patch"][0]), ["H01-BMS-01", "H01-DOOR-01", "H01-ELEV-01", "H01-OOB-01"])
        self.assertEqual(checks["no_log_forwarding"][0], ["H01-NVR-01"])
        scope = {f.name: f.scope for f in ev.devices.values() if f.scope}
        self.assertEqual(scope["H01-PT-FD-01"], ["pci-cde"])
        self.assertEqual(scope["H01-POS-SRV-01"], ["pci-cde"])
        for name in ("H01-FW-01", "H01-CORE-1", "H01-HV-01"):
            self.assertEqual(scope[name], ["pci-connected"])

    def test_day_one_records_none(self):
        from netdiagrams import audit
        with profiles.use("hotel"):
            self.assertFalse(audit.Evidence(starter_export(), None, sync.endpoint_roles()).any)


class DayOne(unittest.TestCase):
    def test_starter_export_has_the_gaps_the_book_describes(self):
        found = {k: len(v) for k, v in found_gaps(starter_export()).items()}
        self.assertEqual(found.get("no_zone"), 16)  # the cameras
        self.assertEqual(found.get("cable_no_label"), 2)
        self.assertEqual(found.get("vlan_no_prefix"), 1)
        self.assertEqual(found.get("no_ip"), 2)
        self.assertGreater(found.get("no_serial", 0), 80)
        self.assertEqual(found.get("wlan_no_manager"), 94)
        self.assertEqual(found.get("wlan_no_fields"), 5)
        self.assertEqual(found.get("wlan_guest_controls"), 1)
        self.assertEqual(found.get("fibre_no_optic"), 24)
        self.assertEqual(found.get("item_no_serial"), 4)
        self.assertEqual(found.get("no_criticality"), 176)


class Generated(unittest.TestCase):
    """The bundled template, samples and stencils are exactly what their scripts write."""

    def test_bundled_files_match_their_generators(self):
        sample, shapes_mod, template_mod = scripts("make_hotel_sample", "make_hotel_stencils", "make_hotel_template")
        data = resources.files("netdiagrams").joinpath("data")
        tree = template_mod.build()
        ET.indent(tree, space=" ")
        self.assertEqual(ET.tostring(tree, encoding="unicode") + "\n",
                         data.joinpath("H01-Hotel-Template.drawio").read_text("utf-8"))
        for made, bundled in ((sample.hq(), data.joinpath("sample-hotel.json")),
                              (sample.branch(), FIXTURES / "hotel-h02.json")):
            self.assertEqual(json.dumps(made, indent=1, ensure_ascii=False) + "\n", bundled.read_text("utf-8"))
        shapes = [shapes_mod.entry(*shape) for shape in shapes_mod.SHAPES]
        self.assertEqual("<mxlibrary>" + json.dumps(shapes, ensure_ascii=False, indent=0) + "</mxlibrary>\n",
                         data.joinpath("Hotel-Stencils.xml").read_text("utf-8"))
        self.assertEqual({title for title, *_ in shapes_mod.SHAPES}, set(profiles.get("hotel").role_shapes.values()))


sys.path.insert(0, str(Path(__file__).parent))
import test_netdiagrams as base  # noqa: E402  (the render gate, run here over the hotel fixtures)


class HotelRenderGate(base.RenderGate):
    """The definition of done over the hotel sample, its day-one starter and the sister property."""

    EXPORTS = {"hotel": hotel_export, "hotel-starter": starter_export, "hotel-h02": branch_export}

    @classmethod
    def setUpClass(cls):
        cls.built = {}
        for name, make in cls.EXPORTS.items():
            export = make()
            template = sync.default_template("hotel")
            report = sync.fill(template, export, today="2026-10-15")
            cls.built[name] = (export, template, report)

    def setUp(self):
        token = profiles._current.set(profiles.get("hotel"))
        self.addCleanup(profiles._current.reset, token)

    def test_two_builds_from_the_same_data_are_identical(self):
        a, b = sync.default_template("hotel"), sync.default_template("hotel")
        sync.fill(a, starter_export(), today="2026-10-15")
        sync.fill(b, starter_export(), today="2026-10-15")
        self.assertEqual(ET.tostring(a), ET.tostring(b))


class Commands(unittest.TestCase):
    def run_cli(self, *args) -> int:
        with redirect_stdout(io.StringIO()):
            return cli.main(list(args))

    def test_settings_choose_the_hotel_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            branch = branch_export()
            del branch["site"]["custom_fields"]["netdiagrams"]  # the file chooses the profile, not NetBox
            src = Path(tmp) / "h02.json"
            src.write_text(json.dumps(branch))
            (Path(tmp) / "netdiagrams.json").write_text(json.dumps({"profile": "hotel"}))
            out = Path(tmp) / "h02.drawio"
            self.assertEqual(self.run_cli("build", "--input", str(src), "-o", str(out)), 0)
            self.assertIn("H02-FW-01", out.read_text("utf-8"))

    def test_netbox_setup_for_hotels_has_pci_scopes_and_no_ot_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.run_cli("netbox-setup", "--profile", "hotel", "--offline", "-o", tmp), 0)
            written = "".join(p.read_text("utf-8") for p in Path(tmp).rglob("*") if p.is_file())
        self.assertIn("zone-roomtech", written)
        self.assertIn("pci-cde", written)
        self.assertNotIn("purdue", written.lower())

    def test_hotel_stencil_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "hotel.xml"
            self.assertEqual(self.run_cli("stencils", "--profile", "hotel", "-o", str(out)), 0)
            self.assertIn("Card terminal (asset)", out.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
