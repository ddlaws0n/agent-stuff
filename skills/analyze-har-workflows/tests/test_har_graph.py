"""Linking and privacy regressions for the workflow sequence graph builder."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "har_graph.py"
CREATED_ID = "rec_7f3a91c2"
CSRF = "csrf-9d8e7f6a5b4c"
SECRET_COOKIE = "sid=cookie-secret-4242"


def entry(t, method, url, status=200, req_headers=(), body=None, res_body=None, res_mime="application/json", res_headers=(), redirect=""):
    req = {"method": method, "url": url, "headers": [{"name": k, "value": v} for k, v in req_headers]}
    if body is not None:
        req["postData"] = {"mimeType": "application/json", "text": json.dumps(body)}
    return {
        "startedDateTime": f"2026-01-01T10:00:{t:02d}.000Z",
        "_resourceType": "fetch",
        "request": req,
        "response": {
            "status": status,
            "headers": [{"name": k, "value": v} for k, v in res_headers],
            "redirectURL": redirect,
            "content": {"mimeType": res_mime, "text": json.dumps(res_body) if res_body is not None else ""},
        },
    }


def run_graph(entries, *extra):
    with tempfile.TemporaryDirectory() as tmp:
        har = Path(tmp) / "session.har"
        har.write_text(json.dumps({"log": {"version": "1.2", "entries": entries}}))
        out = Path(tmp) / "out"
        result = subprocess.run([sys.executable, str(SCRIPT), str(har), "--out", str(out), *extra], capture_output=True, text=True, check=True)
        graph = json.loads((out / "graph.json").read_text())
        markdown = (out / "workflow.md").read_text()
    return json.loads(result.stdout), graph, markdown


def edge_set(graph):
    return {(e["from"], e["to"], e["kind"]) for e in graph["edges"]}


class HarGraphTests(unittest.TestCase):
    def test_links_created_ids_tokens_and_referer(self):
        page = "https://app.example.com/records/new"
        entries = [
            entry(0, "GET", page, res_mime="text/html", res_body=None),
            entry(1, "GET", "https://app.example.com/api/session", req_headers=[("Referer", page)], res_body={"csrfToken": CSRF}),
            entry(2, "POST", "https://app.example.com/api/records", req_headers=[("X-CSRF-Token", CSRF), ("Cookie", SECRET_COOKIE), ("Referer", page)],
                  body={"title": "Quarterly report"}, res_body={"data": {"id": CREATED_ID}}),
            entry(30, "GET", f"https://app.example.com/api/records/{CREATED_ID}", req_headers=[("Referer", page)], res_body={"ok": True}),
        ]
        entries[0]["response"]["content"]["text"] = "<html><body>form</body></html>"
        stdout, graph, markdown = run_graph(entries, "--gap-ms", "1500")
        edges = edge_set(graph)
        self.assertIn((1, 2, "token"), edges)
        self.assertIn((2, 3, "created-id"), edges)
        self.assertIn((0, 2, "referer"), edges)
        wf = graph["workflows"][0]
        self.assertEqual(wf["evidence"], "linked")
        self.assertEqual(wf["primary_index"], 2)
        self.assertEqual([s["index"] for s in wf["steps"]], [0, 1, 2, 3])
        self.assertEqual({s["index"]: s["role"] for s in wf["steps"]}[3], "follow-up")
        self.assertEqual({s["index"]: s["t_rel_ms"] for s in wf["steps"]}, {0: -2000, 1: -1000, 2: 0, 3: 28000})
        self.assertIn("| 3 | +28.0 |", markdown)
        self.assertIn("wf1", stdout["linked_workflows"])
        serialized = json.dumps(graph) + markdown
        for secret in (CREATED_ID, CSRF, "cookie-secret-4242", "Quarterly report"):
            self.assertNotIn(secret, serialized)

    def test_upload_chain_and_signed_url(self):
        signed = "https://storage.example.com/bucket/obj-1?X-Amz-Signature=abc123def456"
        entries = [
            entry(0, "POST", "https://app.example.com/api/uploads", body={"name": "a.pdf"}, res_body={"uploadId": "upl_5551234", "url": signed}),
            entry(1, "PUT", signed, res_mime="text/plain"),
            entry(2, "POST", "https://app.example.com/api/uploads/upl_5551234/complete", body={}, res_body={"fileId": "file_99887"}),
            entry(3, "GET", "https://app.example.com/api/files/file_99887/status", res_body={"state": "processing"}),
            entry(4, "GET", "https://app.example.com/api/files/file_99887/status", res_body={"state": "processing"}),
            entry(5, "GET", "https://app.example.com/api/files/file_99887/status", res_body={"state": "done"}),
        ]
        entries[1]["request"]["headers"] = [{"name": "Content-Type", "value": "application/pdf"}]
        _, graph, markdown = run_graph(entries)
        edges = edge_set(graph)
        self.assertIn((0, 1, "signed-url"), edges)
        self.assertIn((0, 2, "upload-id"), edges)
        self.assertIn((2, 3, "upload-id"), edges)
        roles = {s["index"]: s["role"] for s in graph["workflows"][0]["steps"]}
        self.assertEqual(roles[1], "storage-upload")
        self.assertEqual(roles[4], "poll")
        self.assertIn("repeated", markdown)
        self.assertNotIn("abc123def456", json.dumps(graph) + markdown)

    def test_redirect_shared_id_fanout_and_unlinked_requests(self):
        entries = [
            entry(0, "POST", "https://app.example.com/orders/ord_31337/confirm", status=302, body={"client": "cli_00001"},
                  redirect="/orders/ord_31337/done", res_mime="text/html"),
            entry(1, "GET", "https://app.example.com/orders/ord_31337/done", res_mime="text/html"),
        ]
        entries += [entry(5 + i, "POST", f"https://app.example.com/api/ping/{i}", body={"client": "cli_00001"}) for i in range(10)]
        entries.append(entry(59, "POST", "https://other.example.com/api/save", body={"x": 1}))
        _, graph, _ = run_graph(entries, "--gap-ms", "500")
        edges = edge_set(graph)
        self.assertIn((0, 1, "redirect"), edges)
        self.assertNotIn((0, 5, "shared-id"), edges, "high-fanout value must not link requests")
        lone = [w for w in graph["workflows"] if any(s["index"] == 12 for s in w["steps"])][0]
        self.assertEqual(lone["evidence"], "temporal-only")
        self.assertEqual(lone["nodes"], 1)

    def test_shared_resource_id_and_seeded_indices(self):
        entries = [
            entry(0, "GET", "https://app.example.com/api/projects/prj_424242/members"),
            entry(20, "POST", "https://app.example.com/api/projects/prj_424242/invite", body={"role": "viewer"}),
            entry(40, "POST", "https://app.example.com/api/other", body={"y": 2}),
        ]
        _, graph, _ = run_graph(entries, "--indices", "0-1", "--gap-ms", "0")
        self.assertIn((0, 1, "shared-id"), edge_set(graph))
        self.assertNotIn(2, {s["index"] for w in graph["workflows"] for s in w["steps"]})

    def test_short_keys_link_but_constant_headers_do_not(self):
        app = [("X-Appl", "a1b2c3d4e5f6")]
        entries = [
            entry(0, "GET", "https://app.example.com/api/areas", req_headers=app, res_body=[{"key": "L219", "label": "Town"}]),
            entry(9, "POST", "https://app.example.com/api/requests", req_headers=app, body={"chiaveArea": "L219"}),
            entry(30, "GET", "https://app.example.com/api/requests", req_headers=app),
        ]
        _, graph, _ = run_graph(entries, "--gap-ms", "0")
        edges = edge_set(graph)
        self.assertIn((0, 1, "response-id"), edges)
        self.assertFalse(any(kind == "shared-id" for _, _, kind in edges))

    def test_response_keys_keep_their_names(self):
        entries = [
            entry(0, "POST", "https://app.example.com/api/jobs", body={"q": 1}, res_body={"requestId": "job_8675309"}),
            entry(1, "GET", "https://app.example.com/api/jobs/job_8675309"),
        ]
        _, graph, _ = run_graph(entries)
        edge = next(e for e in graph["edges"] if (e["from"], e["to"]) == (0, 1) and e["kind"] == "created-id")
        self.assertEqual(edge["evidence"][0]["from"], "response.json:$.requestId")

    def test_cache_busters_do_not_link(self):
        entries = [
            entry(0, "GET", "https://app.example.com/api/a?cache=55555"),
            entry(30, "GET", "https://app.example.com/api/b?cache=55555"),
        ]
        _, graph, _ = run_graph(entries, "--indices", "0-1", "--gap-ms", "0")
        self.assertEqual(graph["edges"], [])

    def test_fixtures_build(self):
        for fixture in (ROOT / "evals" / "files").glob("*.har"):
            with self.subTest(fixture=fixture.name), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run([sys.executable, str(SCRIPT), str(fixture), "--out", tmp], capture_output=True, text=True, check=True)
                self.assertTrue(json.loads(result.stdout)["ok"])
                self.assertTrue((Path(tmp) / "workflow.md").read_text().startswith("# Workflow sequence graph"))


if __name__ == "__main__":
    unittest.main()
