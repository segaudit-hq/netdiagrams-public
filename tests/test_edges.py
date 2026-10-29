"""Edge cases a reader meets on the way in: output folders, bad files, the first login, NetBox's refusals,
NetBox 3.5 data, devices that share a name, and a rebuild from the reader's own drawing."""

import contextlib
import copy
import http.server
import io
import json
import os
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from netdiagrams import cli, intake, netbox, profiles, sync, wireless_page
from netdiagrams.graph import Graph

FIXTURES = Path(__file__).parent / "fixtures"


def run(*argv) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        try:
            code = cli.main(list(argv))
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else 1
            out.write(str(stop.code))
    return code, out.getvalue()


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text("utf-8"))


def build(export: dict, profile: str, template: ET.Element | None = None) -> ET.Element:
    with profiles.use(profiles.get(profile)):
        template = template if template is not None else sync.default_template(profiles.get(profile))
        sync.fill(template, export, today="2026-10-29")
    return template


class Files(unittest.TestCase):
    def test_output_folders_are_made(self):
        with tempfile.TemporaryDirectory() as tmp:
            export = Path(tmp) / "o02.json"
            export.write_text((FIXTURES / "office-o02.json").read_text("utf-8"), "utf-8")
            for argv, made in ((["sample", "-o"], "a/plant.drawio"), (["blank", "-o"], "b/blank.drawio"),
                               (["stencils", "-o"], "c/shapes.xml"),
                               (["build", "--input", str(export), "-o"], "d/2026-10/o02.drawio"),
                               (["draft", "--input", str(export), "-o"], "e/o02-draft.drawio")):
                code, out = run(*argv, str(Path(tmp) / made))
                self.assertEqual(code, 0, out)
                self.assertTrue((Path(tmp) / made).is_file(), made)
            code, out = run("share", str(Path(tmp) / "a/plant.drawio"), "-o", str(Path(tmp) / "f/vendor.drawio"))
            self.assertEqual(code, 0, out)
            self.assertTrue((Path(tmp) / "d/2026-10/o02.drift.md").is_file())

    def test_bad_input_and_template_files_are_errors_not_tracebacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad, no_site, broken = Path(tmp) / "bad.json", Path(tmp) / "nosite.json", Path(tmp) / "broken.drawio"
            bad.write_text("not json", "utf-8")
            no_site.write_text('{"devices": {}}', "utf-8")
            broken.write_text("<mxfile", "utf-8")
            good = str(FIXTURES / "office-o02.json")
            for argv, says in ((["build", "--input", str(Path(tmp) / "missing.json")], "Can't read"),
                               (["build", "--input", str(bad)], "Can't read"),
                               (["gaps", "--input", str(no_site)], "not a NetDiagrams export"),
                               (["build", "--input", good, "--template", str(Path(tmp) / "nope.drawio")],
                                "cannot read the template"),
                               (["doctor", "--input", good, "--template", str(broken)], "cannot read the template")):
                code, out = run(*argv, "-o", tmp) if argv[0] != "doctor" else run(*argv)
                self.assertNotEqual(code, 0, argv)
                self.assertIn(says, out, argv)
                self.assertNotIn("Traceback", out)

    def test_a_mistyped_command_is_named(self):
        code, out = run("netbox_setup")
        self.assertEqual(code, 2)
        self.assertIn("unknown command 'netbox_setup'", out)

    def test_gaps_takes_the_profile_and_settings_like_build(self):
        args = cli.parser().parse_args(["gaps", "--profile", "retail", "--settings", "x.json", "--site", "st031"])
        self.assertEqual((args.profile, args.settings), ("retail", "x.json"))


class Login(unittest.TestCase):
    def test_urls_are_tidied(self):
        self.assertEqual(cli._url(" netbox.example.com/ "), "https://netbox.example.com")
        self.assertEqual(cli._url("http://10.0.0.5:8000/"), "http://10.0.0.5:8000")
        self.assertEqual(cli._url(""), "")

    def test_a_typed_in_login_is_checked_before_it_is_saved(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(cli, "CONFIG", Path(tmp) / "config.json"), \
                mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch("sys.stdin") as stdin, \
                mock.patch("builtins.input", return_value="netbox.example.com"), \
                mock.patch("getpass.getpass", return_value="mistyped"), \
                mock.patch.object(netbox.NetBoxClient, "check",
                                  side_effect=netbox.NetBoxError("NetBox returned 403: Invalid token", 403)):
            stdin.isatty.return_value = True
            args = cli.parser().parse_args(["build"])
            with self.assertRaises(netbox.NetBoxError):
                cli._client(args)
            self.assertFalse((Path(tmp) / "config.json").exists())

    def test_the_saved_token_follows_the_url_with_or_without_a_slash(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(cli, "CONFIG", Path(tmp) / "config.json"), \
                mock.patch.dict(os.environ, {"NETBOX_URL": "https://nb.example.com"}, clear=True), \
                mock.patch("sys.stdin") as stdin:
            stdin.isatty.return_value = False
            (Path(tmp) / "config.json").write_text('{"url": "https://nb.example.com/", "token": "t"}', "utf-8")
            client = cli._client(cli.parser().parse_args(["build"]))
            self.assertEqual((client.base, client.token), ("https://nb.example.com/api", "t"))


class NetBoxReplies(unittest.TestCase):
    """What NetBox (or whatever answers at its URL) says comes through, with the next step."""

    def serve(self, *replies: tuple):
        """A server giving each (code, body[, content type]) in turn, then the last one again."""
        replies = list(replies)

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                code, body, *ctype = replies.pop(0) if len(replies) > 1 else replies[0]
                self.send_response(code)
                self.send_header("Content-Type", ctype[0] if ctype else "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.dict(os.environ, {"no_proxy": "*", "NO_PROXY": "*"}))
        self.addCleanup(stack.close)
        return netbox.NetBoxClient(f"http://127.0.0.1:{server.server_port}", "t")

    def test_a_refused_token_says_why_and_what_to_do(self):
        client = self.serve((403, b'{"detail": "Invalid token"}'))
        with self.assertRaises(netbox.NetBoxError) as err:
            client.sites()
        self.assertIn("Invalid token. Check the API token", str(err.exception))
        self.assertEqual(err.exception.code, 403)

    def test_a_login_page_is_not_netbox(self):
        client = self.serve((200, b"<html>Sign in</html>", "text/html"))
        with self.assertRaises(netbox.NetBoxError) as err:
            client.check()
        self.assertIn("did not answer with JSON", str(err.exception))

    def test_a_busy_netbox_is_asked_once_more(self):
        client = self.serve((503, b'{"detail": "busy"}'), (200, b'{"results": [{"slug": "s01"}], "next": null}'))
        with mock.patch.object(netbox.time, "sleep") as pause:
            self.assertEqual(client.sites(), [{"slug": "s01"}])
        pause.assert_called_once()
        client = self.serve((503, b'{"detail": "busy"}'))
        with mock.patch.object(netbox.time, "sleep"), self.assertRaises(netbox.NetBoxError) as err:
            client.sites()
        self.assertEqual(err.exception.code, 503)


class OddData(unittest.TestCase):
    def test_netbox_35_device_role_counts_as_the_role(self):
        export = fixture("office-o02.json")
        for d in export["devices"]:
            d["device_role"] = d.pop("role")
        tidy = intake.prepare(export)
        self.assertTrue(all(d.get("role", {}).get("slug") for d in tidy["devices"]))
        self.assertEqual(intake.prepare(fixture("office-o02.json"))["devices"][0]["role"]["slug"],
                         tidy["devices"][0]["role"]["slug"])

    def test_devices_sharing_a_name_each_keep_their_own_data(self):
        export = fixture("office-o02.json")
        first = export["devices"][0]
        twin = copy.deepcopy(export["devices"][1])
        twin.update(id=9999, name=first["name"], serial="TWIN-SERIAL")
        export["devices"].append(twin)
        export.setdefault("interfaces", []).append({"id": 1, "name": "eth0", "device": {"id": 9999, "name": first["name"]}})
        tidy = intake.prepare(export)
        names = [d["name"] for d in tidy["devices"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn(f"{first['name']}-9999", names)
        self.assertEqual(tidy["interfaces"][-1]["device"]["name"], f"{first['name']}-9999")
        self.assertEqual(intake.intake(tidy).shared_names, [f"{first['name']}: {first['name']}, {first['name']}-9999"])
        built = build(export, "office")
        card = next(el for el in built.iter("object") if el.get("name") == first["name"] and el.get("role"))
        self.assertNotEqual(card.get("serial"), "TWIN-SERIAL")


class FirstBuildAndRebuild(unittest.TestCase):
    def test_a_critical_device_keeps_its_stripe_when_a_template_neighbour_is_removed(self):
        export = fixture("hotel-h02.json")
        built = build(export, "hotel")
        critical = {d["name"] for d in export["devices"] if (d.get("custom_fields") or {}).get("criticality") == "critical"}
        page = built.find("diagram[@id='physical']")
        drawn = {el.get("id"): el.get("name") for el in page.iter("object") if el.get("name") in critical and el.get("role")}
        self.assertTrue(drawn)
        striped = {el.get("netdiagrams_ref") for el in page.iter("object") if el.get("netdiagrams_field") == "cf_criticality"}
        self.assertEqual(set(drawn) - striped, set())

    def test_the_wireless_plan_card_says_the_same_on_a_rebuild(self):
        export = fixture("bank-b02.json")
        first = build(export, "bank")
        again = build(export, "bank", ET.fromstring(ET.tostring(first)))

        def leftovers(root):
            g = Graph(root.find("diagram[@id='wireless']"))
            return {n for el in g.els.values() for n in (el.get(wireless_page.LEFTOVER_MARK) or "").split(",") if n}

        def card(root):
            return " ".join(c.get("value") or c.get("label") or "" for c in root.iter()
                            if (c.get("id") or "").startswith("wireless-gaps-card"))

        self.assertTrue(leftovers(first))
        self.assertEqual(leftovers(again), leftovers(first))
        self.assertIn("Template examples still on this page", card(first))
        self.assertEqual(card(again), card(first))

    def test_example_cards_name_what_they_are(self):
        text = ET.tostring(build(fixture("office-o02.json"), "office"), "unicode")
        self.assertNotIn("'s, not from this site", text)
        self.assertIn("flow register, not from this site's NetBox", text)


if __name__ == "__main__":
    unittest.main()
