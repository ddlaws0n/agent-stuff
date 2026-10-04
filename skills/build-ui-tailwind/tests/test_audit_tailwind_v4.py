from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "audit-tailwind-v4.py"
SPEC = importlib.util.spec_from_file_location("audit_tailwind_v4", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AuditTailwindTests(unittest.TestCase):
    def make_project(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "package.json").write_text(json.dumps({"devDependencies": {"tailwindcss": "^4.3.0"}}))
        return temp, root

    def test_excludes_docs_locks_and_generated_directories_by_default(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        (root / "src").mkdir()
        (root / "src" / "app.css").write_text('@import "tailwindcss";')
        (root / "src" / "app.tsx").write_text('const cls = `bg-${color}-500`;')
        (root / "docs").mkdir()
        (root / "docs" / "guide.mdx").write_text('Example: `start-4`')
        (root / "node_modules").mkdir()
        (root / "node_modules" / "dependency.css").write_text('@tailwind utilities;')
        (root / "package-lock.json").write_text('{"content": ["start-4"], "safelist": []}')

        findings = MODULE.run(root, 512_000)["findings"]
        paths = {finding["path"] for finding in findings}
        codes = {finding["code"] for finding in findings}
        self.assertIn("dynamic-template-class", codes)
        self.assertFalse(any(path.startswith("docs/") for path in paths))
        self.assertFalse(any(path.startswith("node_modules/") for path in paths))
        self.assertNotIn("package-lock.json", paths)
        self.assertNotIn("css-import-not-found", codes)

    def test_css_discovery_prunes_dependencies_before_scanning(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        (root / "node_modules").mkdir()
        for index in range(550):
            (root / "node_modules" / f"{index}.css").write_text(".x {}")
        (root / "src").mkdir()
        (root / "src" / "tailwind.css").write_text('@import "tailwindcss";')
        codes = {finding["code"] for finding in MODULE.run(root, 512_000)["findings"]}
        self.assertNotIn("css-import-not-found", codes)

    def test_config_patterns_do_not_scan_ordinary_source_text(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        (root / "src").mkdir()
        (root / "src" / "app.css").write_text('@import "tailwindcss";')
        (root / "src" / "note.ts").write_text('const documentation = "safelist: content: [x]";')
        codes = {finding["code"] for finding in MODULE.run(root, 512_000)["findings"]}
        self.assertNotIn("legacy-safelist", codes)
        self.assertNotIn("legacy-content-config", codes)

    def test_major_version_parsing_does_not_treat_v4_minor_3_as_v3(self):
        for spec in ("^4.3.0", "~4.3.3", "4.3.1", "^4.1.3", "workspace:^4.3.0", ">=4.3"):
            self.assertEqual(MODULE.major_version(spec), 4, spec)
        for spec in ("^3.4.17", "~3.4", "3.x", "v3.4.0", "npm:tailwindcss@3.4.1", ">=3.0.0 <4"):
            self.assertEqual(MODULE.major_version(spec), 3, spec)
        self.assertIsNone(MODULE.major_version("latest"))

    def test_tailwind_4_3_is_not_reported_as_v3(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        (root / "app.css").write_text('@import "tailwindcss";')
        codes = {finding["code"] for finding in MODULE.run(root, 512_000)["findings"]}
        self.assertNotIn("tailwind-v3-installed", codes)

    def test_split_tailwind_imports_count_as_css_first_entry(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        (root / "app.css").write_text(
            '@layer theme, base, components, utilities;\n'
            '@import "tailwindcss/theme.css" layer(theme);\n'
            "@import 'tailwindcss/utilities.css' layer(utilities);\n"
        )
        codes = {finding["code"] for finding in MODULE.run(root, 512_000)["findings"]}
        self.assertNotIn("css-import-not-found", codes)

    def test_nested_workspace_package_json_is_inspected_but_node_modules_is_not(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "package.json").write_text(json.dumps({"private": True, "workspaces": ["apps/*"]}))
        web = root / "apps" / "web"
        web.mkdir(parents=True)
        (web / "package.json").write_text(json.dumps({"devDependencies": {"tailwindcss": "^3.4.17"}}))
        (web / "vite.config.ts").write_text("export default {};")
        dep = root / "node_modules" / "some-lib"
        dep.mkdir(parents=True)
        (dep / "package.json").write_text(json.dumps({"dependencies": {"tailwindcss": "3.0.0"}}))

        findings = MODULE.run(root, 512_000)["findings"]
        v3 = [f["path"] for f in findings if f["code"] == "tailwind-v3-installed"]
        self.assertEqual(v3, ["apps/web/package.json"])
        vite = [f["path"] for f in findings if f["code"] == "vite-plugin-missing"]
        self.assertEqual(vite, ["apps/web/package.json"])
        self.assertNotIn("tailwind-missing", {f["code"] for f in findings})

    def test_tree_is_walked_once(self):
        temp, root = self.make_project()
        self.addCleanup(temp.cleanup)
        (root / "src").mkdir()
        (root / "src" / "app.css").write_text('@import "tailwindcss";')
        with mock.patch.object(
            MODULE, "iter_files", wraps=getattr(MODULE, "iter_files")
        ) as iter_files:
            MODULE.run(root, 512_000)
        self.assertEqual(iter_files.call_count, 1)


if __name__ == "__main__":
    unittest.main()
