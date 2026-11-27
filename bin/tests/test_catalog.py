"""Tests of bin/catalog.py and bin/verify.py: python3 -m unittest discover -s bin/tests."""

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import catalog  # noqa: E402
import verify  # noqa: E402

ROOT_ENTRY = catalog.entry(
    module="go.octolab.org",
    name="pkg",
    repository="https://github.com/octolab/pkg",
    branch="main",
    visibility="public",
    scope="all",
    packages=["", "/errors", "/sync"],
    topics=["go", "octolab"],
    version="v0.12.2",
    commit="48e3b73f67d1e6d3f87b8e8862e03cb6e91c4d2a",
)
TOOL_ENTRY = catalog.entry(
    module="go.octolab.org/toolset/indexit",
    name="indexit",
    repository="https://github.com/octopot/indexit",
    branch="main",
    visibility="public",
    scope="all",
    packages=["", "/cmd/indexit", "/internal"],
    topics=[],
    version=None,
    commit="cbc7add36a6b87e57f0ee412626d91dd2d51d262",
)


def git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


class Catalog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for e in (ROOT_ENTRY, TOOL_ENTRY):
            catalog.write_entry(self.root, e)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            target.write_bytes(value)
        else:
            target.write_bytes(catalog.canonical(value))

    def errors(self, **kw):
        return catalog.check(self.root, **kw)

    def mutated(self, **changes):
        e = copy.deepcopy(TOOL_ENTRY)
        e.update(changes)
        return e

    def assertRejected(self, needle, **kw):
        errors = self.errors(**kw)
        self.assertTrue(any(needle in e for e in errors), f"{needle!r} not in {errors}")

    def test_valid(self):
        self.assertEqual(self.errors(), [])

    def test_canonical_bytes(self):
        data = catalog.canonical(TOOL_ENTRY)
        self.assertTrue(data.startswith(b'{\n  "schema": 1,\n  "name": "indexit",\n  "module": "go.octolab.org/toolset/indexit",\n'))
        self.assertTrue(data.endswith(b'"commit": "cbc7add36a6b87e57f0ee412626d91dd2d51d262"\n}\n'))
        self.assertIn(b'"topics": [],', data)

    def test_rejects_non_canonical_bytes(self):
        path = "modules/go.octolab.org/toolset/indexit.json"
        self.put(path, json.dumps(TOOL_ENTRY).encode())
        self.assertRejected("canonical form")

    def test_rejects_non_ascii(self):
        path = "modules/go.octolab.org/toolset/indexit.json"
        self.put(path, catalog.canonical(TOOL_ENTRY).replace(b"indexit", "indexét".encode(), 1))
        self.assertRejected("not ASCII JSON")

    def test_rejects_wrong_path(self):
        self.put("modules/go.octolab.org/toolset/other.json", self.mutated(name="other"))
        self.assertRejected("belongs in modules/go.octolab.org/toolset/indexit.json")

    def test_rejects_foreign_files(self):
        self.put("modules/README.md", b"hi\n")
        self.assertRejected("only entries")

    def test_rejects_symlink(self):
        (self.root / "modules/link.json").symlink_to(self.root / "modules/go.octolab.org.json")
        self.assertRejected("symbolic links")

    def test_rejects_key_order_and_extra_keys(self):
        e = self.mutated()
        e["extra"] = 1
        self.put("modules/go.octolab.org/toolset/indexit.json", e)
        self.assertRejected("keys must be exactly")
        e = {k: TOOL_ENTRY[k] for k in reversed(catalog.KEYS)}
        self.put("modules/go.octolab.org/toolset/indexit.json", e)
        self.assertRejected("keys must be exactly")

    def test_rejects_bad_fields(self):
        cases = {
            "schema must be": dict(schema=2),
            "schema must be ": dict(schema=1.0),
            "is not a module path": dict(module="go.octolab.org/Toolset/x"),
            "name": dict(name="Index_It"),
            "name 'a//b'": dict(name="a//b"),
            "name '/a'": dict(name="/a"),
            "name 'a/'": dict(name="a/"),
            "name 'a--b'": dict(name="a--b"),
            "name 'toolset/Tablo'": dict(name="toolset/Tablo"),
            "repository": dict(repository="https://github.com/octopot/indexit.git"),
            "branch": dict(branch="-x"),
            "visibility": dict(visibility="secret"),
            "scope must be": dict(scope="some"),
            'start with ""': dict(packages=["/cmd"]),
            "unique and sorted": dict(packages=["", "/b", "/a"]),
            "publishable": dict(packages=["", "/internal/testdata"]),
            "scope root": dict(scope="root"),
            "topics must be unique": dict(topics=["b", "a"]),
            "GitHub topics": dict(topics=["Go"]),
            "stable vX.Y.Z": dict(version="v1.0.0-rc1"),
            "needs the module path": dict(version="v2.0.0"),
            "full lowercase SHA-1": dict(commit="ABC"),
        }
        path = "modules/go.octolab.org/toolset/indexit.json"
        for needle, change in cases.items():
            with self.subTest(needle):
                e = self.mutated(**change)
                self.put(path, e if "module" not in change else e)
                self.assertRejected(needle)
        self.put(path, TOOL_ENTRY)
        self.assertEqual(self.errors(), [])

    def test_rejects_hidden_and_underscore_segments(self):
        path = "modules/go.octolab.org/toolset/indexit.json"
        for p in ("/.git", "/_x", "/a/..", "/vendor/x", "/a b"):
            with self.subTest(p):
                self.put(path, self.mutated(packages=sorted({"", p})))
                self.assertRejected("publishable")

    def test_rejects_paths_reserved_for_files_of_the_site(self):
        self.put("modules/go.octolab.org/og.png.json", self.mutated(module="go.octolab.org/og.png", name="og"))
        self.assertRejected("/og.png is a file of the site")
        (self.root / "modules/go.octolab.org/og.png.json").unlink()
        self.put("modules/go.octolab.org.json", {**ROOT_ENTRY, "packages": ["", "/errors", "/modules.yml"]})
        self.assertRejected("package '/modules.yml': /modules.yml is a file of the site")
        self.put("modules/go.octolab.org.json", {**ROOT_ENTRY, "packages": ["", "/Index.html", "/errors"]})
        self.assertRejected("package '/Index.html': /Index.html is a file of the site")
        self.put("modules/go.octolab.org.json", ROOT_ENTRY)
        self.put("modules/go.octolab.org/toolset/indexit.json", self.mutated(packages=["", "/index.html"]))
        self.assertRejected("package '/index.html': index.html is the file of every page")
        self.put("modules/go.octolab.org/toolset/indexit.json", TOOL_ENTRY)
        self.put("modules/go.octolab.org/toolset/indexit/index.html.json",
                 self.mutated(module="go.octolab.org/toolset/indexit/index.html", name="index"))
        self.assertRejected("index.html is the file of every page")
        (self.root / "modules/go.octolab.org/toolset/indexit/index.html.json").unlink()
        self.put("modules/go.octolab.org/toolset/indexit.json", self.mutated(packages=["", "/" + "a" * 300]))
        self.assertRejected("longer than 100 bytes")

    def test_major_version_suffix(self):
        path = "modules/go.octolab.org/toolset/indexit/v2.json"
        e = self.mutated(module="go.octolab.org/toolset/indexit/v2", name="indexit-v2",
                         packages=[""], version="v2.1.0")
        self.put(path, e)
        self.assertEqual(self.errors(), [])
        self.put(path, {**e, "version": "v3.0.0"})
        self.assertRejected("does not match the major version suffix")
        (self.root / path).unlink()
        self.put("modules/go.octolab.org/toolset/indexit/v1.json",
                 self.mutated(module="go.octolab.org/toolset/indexit/v1", name="indexit-v1", packages=[""]))
        self.assertRejected("/v2 or higher")

    def test_s2_root_required(self):
        (self.root / "modules/go.octolab.org.json").unlink()
        self.assertRejected("S2")

    def test_s3_disjoint_packages(self):
        self.put("modules/go.octolab.org/toolset/indexit/internal.json", catalog.entry(
            **{**{k: TOOL_ENTRY[k] for k in catalog.KEYS[1:]},
               "module": "go.octolab.org/toolset/indexit/internal", "name": "internal", "packages": [""]}))
        self.assertRejected("S3: go.octolab.org/toolset/indexit/internal")

    def test_s5_parent_page_of_another_package(self):
        self.put("modules/go.octolab.org/toolset/indexit/cmd.json", catalog.entry(
            **{**{k: TOOL_ENTRY[k] for k in catalog.KEYS[1:]},
               "module": "go.octolab.org/toolset/indexit/cmd", "name": "cmd",
               "repository": "https://github.com/octopot/cmd", "packages": ["", "/indexit/new"]}))
        self.assertRejected("S5: go.octolab.org/toolset/indexit/cmd renders go.octolab.org/toolset/indexit/cmd/indexit")

    def test_names_with_segments(self):
        for name in ("toolset/indexit", "a/b-c/d1"):
            self.put("modules/go.octolab.org/toolset/indexit.json", self.mutated(name=name))
            self.assertEqual(self.errors(), [], name)
        self.put("modules/go.octolab.org/toolset/indexit.json", self.mutated(name="a/" + "b" * 63))
        self.assertRejected("at most 64 characters")

    def test_s4_unique_names(self):
        self.put("modules/go.octolab.org/toolset/indexit.json", self.mutated(name="pkg"))
        self.assertRejected("S4: name pkg")

    def test_progress_counts_seeds(self):
        entries, errors = catalog.load(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(catalog.progress(entries), (1, 2, ["indexit"]))
        self.assertEqual(catalog.progress_text(entries), "Self-published: 1 of 2 modules; on seeds: 1 (indexit)")
        self.put(catalog.entry_path(TOOL_ENTRY["module"]), self.mutated(version="v0.4.1"))
        entries, _ = catalog.load(self.root)
        self.assertEqual(catalog.progress_text(entries), "Self-published: 2 of 2 modules; on seeds: 0")
        self.assertEqual(catalog.progress_summary(entries),
                         "### Catalog: self-publishing\n\n**2 of 2** modules publish themselves; **0** still on seeds (`version: null`).\n")

    def test_cli_progress_appends_the_summary(self):
        summary = self.root / "summary.md"
        summary.write_text("before\n")
        result = subprocess.run(
            ["python3", "-I", str(Path(catalog.__file__)), "--root", str(self.root), "progress", "--summary", str(summary)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Self-published: 1 of 2 modules; on seeds: 1 (indexit)\n")
        text = summary.read_text()
        self.assertTrue(text.startswith("before\n### Catalog: self-publishing\n"))
        self.assertIn("**1 of 2** modules publish themselves; **1** still on seeds", text)
        self.assertIn("`indexit`", text)

    def test_cli_progress_refuses_an_invalid_catalog(self):
        self.put("modules/stray.txt", b"x")
        result = subprocess.run(
            ["python3", "-I", str(Path(catalog.__file__)), "--root", str(self.root), "progress"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")

    def test_manifest_format(self):
        entries, _ = catalog.load(self.root)
        text = catalog.manifest(entries)
        self.assertIn(
            "- prefix: go.octolab.org/toolset/indexit\n"
            "  import:\n"
            "    - url: https://github.com/octopot/indexit\n"
            "      vcs: git\n"
            "      source:\n"
            "        url:  https://github.com/octopot/indexit\n"
            "        dir:  https://github.com/octopot/indexit/tree/main{/dir}\n"
            "        file: https://github.com/octopot/indexit/blob/main{/dir}/{file}#L{line}\n"
            "  packages:\n"
            "    - go.octolab.org/toolset/indexit\n"
            "    - go.octolab.org/toolset/indexit/cmd/indexit\n"
            "    - go.octolab.org/toolset/indexit/internal\n"
            "  tags: [  ]\n", text)
        self.assertTrue(text.startswith("- prefix: go.octolab.org\n"))
        self.assertIn("  tags: [ go, octolab ]\n", text)


class Untrusted(Catalog):
    """What a publisher wrote: final paths, and every publisher commit."""

    def setUp(self):
        super().setUp()
        git(self.root, "init", "-q", "-b", "main")
        self.commit("base")
        self.path = "modules/go.octolab.org/toolset/indexit.json"

    def commit(self, message):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def publish(self, value, path=None):
        path = path or self.path
        self.put(path, value)
        return (self.commit("publish"), path)

    def test_version_update_passes(self):
        t = self.publish(self.mutated(version="v0.4.2", packages=["", "/cmd/indexit"]))
        self.assertEqual(self.errors(paths=[self.path], transitions=[t]), [])

    def test_new_entry_passes(self):
        path = "modules/go.octolab.org/toolset/new.json"
        t = self.publish(self.mutated(module="go.octolab.org/toolset/new", name="new", packages=[""]), path)
        self.assertEqual(self.errors(paths=[path], transitions=[t]), [])

    def test_rejects_repository_change(self):
        t = self.publish(self.mutated(repository="https://github.com/evil/indexit"))
        self.assertRejected("may not change repository", paths=[self.path], transitions=[t])

    def test_rejects_name_change(self):
        t = self.publish(self.mutated(name="other"))
        self.assertRejected("may not change name", paths=[self.path], transitions=[t])

    def test_rejects_deletion(self):
        (self.root / self.path).unlink()
        t = (self.commit("delete"), self.path)
        self.assertRejected("may not delete", paths=[self.path])
        self.assertRejected("may not delete", transitions=[t])

    def test_rejects_takeover_of_an_undeployed_entry(self):
        path = "modules/go.octolab.org/toolset/new.json"
        first = self.publish(self.mutated(module="go.octolab.org/toolset/new", name="new", packages=[""]), path)
        second = self.publish(self.mutated(module="go.octolab.org/toolset/new", name="new", packages=[""],
                                           repository="https://github.com/evil/new"), path)
        self.assertRejected("may not change repository", paths=[path], transitions=[first, second])

    def test_maintainer_transfer_then_publisher_update_passes(self):
        self.put(self.path, self.mutated(repository="https://github.com/octolab/indexit"))
        self.commit("maintainer moves indexit")
        t = self.publish(self.mutated(repository="https://github.com/octolab/indexit", version="v0.5.0"))
        self.assertEqual(self.errors(paths=[self.path], transitions=[t]), [])

    def test_rejects_paths_outside_modules(self):
        for path in ("bin/catalog.py", "Makefile", "modules/x.txt", ".github/workflows/cd.urls.yml"):
            with self.subTest(path):
                self.assertRejected("modules/<module path>.json only", paths=[path])
                self.assertRejected("modules/<module path>.json only", transitions=[("a" * 40, path)])

    def test_cli_check_from_another_location(self):
        # the gate runs the validator copied from the last deployed revision
        commit, path = self.publish(self.mutated(repository="https://github.com/evil/indexit"))
        transitions = self.root / "transitions"
        transitions.write_text(f"{commit}\t{path}\n")
        result = subprocess.run(
            ["python3", "-I", str(Path(catalog.__file__)), "--root", str(self.root), "check",
             "--untrusted", path, "--transitions-from", str(transitions)],
            capture_output=True, text=True, env=dict(os.environ, GITHUB_ACTIONS="true"))
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"::error::{path} in {commit[:12]}: a publisher may not change repository", result.stderr)

    def test_error_commands_are_escaped(self):
        weird = "modules/x\n::warning::y.json"
        result = subprocess.run(
            ["python3", "-I", str(Path(catalog.__file__)), "--root", str(self.root), "check",
             "--untrusted", weird],
            capture_output=True, text=True, env=dict(os.environ, GITHUB_ACTIONS="true"))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("\n::warning::", result.stderr)
        self.assertIn("%0A::warning::", result.stderr)


HOST_MODULE = "go.octolab.org"


class Verify(unittest.TestCase):
    def setUp(self):
        self.modules = {e["module"]: e for e in (ROOT_ENTRY, TOOL_ENTRY)}

    def page(self, package, module="go.octolab.org/toolset/indexit", repo="https://github.com/octopot/indexit",
             branch="main", docs=None, head="", body=""):
        docs = docs or f"https://pkg.go.dev/{package}"
        return (
            f'<!DOCTYPE html><html><head>{head}'
            f'<meta name="go-import" content="{module} git {repo}">'
            f'<meta name="go-source" content="{module} {repo} {repo}/tree/{branch}{{/dir}} '
            f'{repo}/blob/{branch}{{/dir}}/{{file}}#L{{line}}">'
            f'<meta charset="utf-8"><script src="/x.js"></script></head>'
            f'<body><a href="{docs}">Documentation</a>{body}</body></html>'
        )

    def test_good_page(self):
        verify.verify(self.page("go.octolab.org/toolset/indexit/internal"), "go.octolab.org/toolset/indexit/internal",
                      self.modules)

    def test_wrong_branch(self):
        with self.assertRaisesRegex(ValueError, "go-source"):
            verify.verify(self.page("go.octolab.org/toolset/indexit", branch="master"),
                          "go.octolab.org/toolset/indexit", self.modules)

    def test_rejects_a_redirect(self):
        page = self.page("go.octolab.org/toolset/indexit",
                         head='<meta http-equiv="refresh" content="0; url=https://pkg.go.dev/go.octolab.org/toolset/indexit">')
        with self.assertRaisesRegex(ValueError, "refresh"):
            verify.verify(page, "go.octolab.org/toolset/indexit", self.modules)

    def test_requires_the_documentation_of_a_public_package(self):
        with self.assertRaisesRegex(ValueError, "no link to its documentation"):
            verify.verify(self.page("go.octolab.org/toolset/indexit", docs="https://evil.example/x"),
                          "go.octolab.org/toolset/indexit", self.modules)

    def test_a_directory_needs_no_documentation(self):
        tool = {**TOOL_ENTRY, "packages": ["", "/cmd/indexit"]}
        modules = {**self.modules, tool["module"]: tool}
        verify.verify(self.page("go.octolab.org/toolset/indexit/cmd", docs="https://example.org/"),
                      "go.octolab.org/toolset/indexit/cmd", modules)

    def test_private_pages_do_not_link_pkg_go_dev(self):
        private = {**TOOL_ENTRY, "visibility": "private"}
        modules = {**self.modules, private["module"]: private}
        with self.assertRaisesRegex(ValueError, "private module"):
            verify.verify(self.page("go.octolab.org/toolset/indexit"), "go.octolab.org/toolset/indexit", modules)
        verify.verify(self.page("go.octolab.org/toolset/indexit", docs="https://github.com/octopot/indexit"),
                      "go.octolab.org/toolset/indexit", modules)

    def test_discovery_tags_come_first_in_the_head(self):
        late = self.page("go.octolab.org/toolset/indexit", head='<script>var a = 1 < 2</script>')
        with self.assertRaisesRegex(ValueError, "first in the head"):
            verify.verify(late, "go.octolab.org/toolset/indexit", self.modules)
        styled = self.page("go.octolab.org/toolset/indexit", head='<link rel="stylesheet" href="/a.css">')
        with self.assertRaisesRegex(ValueError, "first in the head"):
            verify.verify(styled, "go.octolab.org/toolset/indexit", self.modules)
        twice = self.page("go.octolab.org/toolset/indexit",
                          body='<meta name="go-import" content="go.octolab.org/toolset/indexit git https://github.com/octopot/indexit">')
        with self.assertRaisesRegex(ValueError, "go-import"):
            verify.verify(twice, "go.octolab.org/toolset/indexit", self.modules)

    def test_a_private_root_page_may_link_other_modules(self):
        private_root = {**ROOT_ENTRY, "visibility": "private"}
        modules = {**self.modules, HOST_MODULE: private_root}
        catalog_page = self.page("go.octolab.org", "go.octolab.org", "https://github.com/octolab/pkg",
                                 docs="https://pkg.go.dev/go.octolab.org/toolset/indexit")
        verify.verify(catalog_page, "go.octolab.org", modules)
        with self.assertRaisesRegex(ValueError, "private module"):
            verify.verify(self.page("go.octolab.org", "go.octolab.org", "https://github.com/octolab/pkg",
                                    docs="https://pkg.go.dev/go.octolab.org/errors"), "go.octolab.org", modules)

    def test_wrong_repository(self):
        with self.assertRaisesRegex(ValueError, "go-import"):
            verify.verify(self.page("go.octolab.org/toolset/indexit", repo="https://github.com/evil/indexit"),
                          "go.octolab.org/toolset/indexit", self.modules)

    def test_explicit_owner_wins_over_longest_prefix(self):
        nested = catalog.entry(**{**{k: TOOL_ENTRY[k] for k in catalog.KEYS[1:]},
                                  "module": "go.octolab.org/toolset/indexit/cmd", "name": "cmd",
                                  "repository": "https://github.com/octopot/cmd", "packages": [""]})
        modules = {**self.modules, nested["module"]: nested}
        pages = verify.pages_of(modules)
        self.assertEqual(pages["go.octolab.org/toolset/indexit/cmd/indexit"], "go.octolab.org/toolset/indexit")
        self.assertEqual(pages["go.octolab.org/toolset/indexit/cmd"], "go.octolab.org/toolset/indexit/cmd")
        verify.verify(self.page("go.octolab.org/toolset/indexit/cmd/indexit"),
                      "go.octolab.org/toolset/indexit/cmd/indexit", modules, pages)

    def test_removed_pages_from_previous_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q", "-b", "main")
            for e in self.modules.values():
                catalog.write_entry(root, e)
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "before")
            previous = verify.previous_entries(root, "HEAD")
            now = {**previous, ROOT_ENTRY["module"]: {**ROOT_ENTRY, "scope": "root", "packages": [""]}}
            removed = set(verify.pages_of(previous)) - set(verify.pages_of(now))
            self.assertEqual(removed, {"go.octolab.org/errors", "go.octolab.org/sync"})

    def test_local_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for e in self.modules.values():
                for p in e["packages"]:
                    package = e["module"] + p
                    rel = package[len("go.octolab.org"):].lstrip("/")
                    (d / rel).mkdir(parents=True, exist_ok=True)
                    (d / rel / "index.html").write_text(
                        self.page(package, e["module"], e["repository"], e["branch"]))
            (d / "toolset/indexit/cmd").mkdir(exist_ok=True)
            (d / "toolset/indexit/cmd/index.html").write_text(self.page("go.octolab.org/toolset/indexit/cmd"))
            verify.local(d, self.modules)
            (d / "toolset/indexit/stray").mkdir()
            (d / "toolset/indexit/stray/index.html").write_text(self.page("go.octolab.org/toolset/indexit/stray"))
            with self.assertRaisesRegex(ValueError, "outside the catalog"):
                verify.local(d, self.modules)
            (d / "toolset/indexit/stray/index.html").unlink()
            (d / "toolset/indexit/internal/index.html").unlink()
            with self.assertRaisesRegex(ValueError, "without a page"):
                verify.local(d, self.modules)

    def test_local_tree_with_the_catalog_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            catalog.render(list(self.modules.values()), d)
            (d / "_not-found").mkdir()
            (d / "_not-found/index.html").write_text("<p>not found</p>")
            with self.assertRaisesRegex(ValueError, "outside the catalog"):
                verify.local(d, self.modules)
            with self.assertRaisesRegex(ValueError, "404.html"):
                verify.local(d, self.modules, catalog_page=True)
            (d / "404.html").write_text("<p>not found</p>")
            verify.local(d, self.modules, catalog_page=True)


CARDS = {
    "groups": [{"id": "tools", "eyebrow": "01 / TOOLS", "title": "Tools.", "lead": "Tools."},
               {"id": "libraries", "eyebrow": "02 / LIBRARIES", "title": "Libraries.", "lead": "Libraries."}],
    "items": [
        {"module": "go.octolab.org/toolset/indexit", "group": "tools", "kind": "tool", "emoji": "🗃️",
         "title": "indexit", "tagline": "Your Telegram. Your data.", "summary": "Export Telegram.",
         "site": "https://indexit.octolab.org/", "releaseNotes": "https://indexit.octolab.org/changelog/v{version}/",
         "install": "brew install --formula octolab/tap/indexit"},
        {"module": "go.octolab.org", "group": "libraries", "kind": "library", "emoji": "🧰",
         "title": "pkg", "tagline": "Go packages.", "summary": "The root module."},
    ],
}


def put_cards(root, cards=CARDS):
    path = Path(root, catalog.CARDS)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")


class Pages(unittest.TestCase):
    """bin/pages.py: the smoke test of the live catalog page, offline parts."""

    def test_private_cards_need_no_version(self):
        sys.path.insert(0, str(Path(catalog.__file__).parent))
        import pages
        items = [{"module": "go.octolab.org/a", "visibility": "public", "version": "v1.0.0"},
                 {"module": "go.octolab.org/b", "visibility": "private", "version": "v0.1.0"}]
        page = ('<article data-module="go.octolab.org/a"><a>v1.0.0</a></article>'
                '<li data-module="go.octolab.org/b"><code>b</code></li>')
        self.assertEqual(pages.card_errors(page, items, "https://go.octolab.org/"), [])
        stale = page.replace("v1.0.0", "v0.9.0")
        self.assertEqual(len(pages.card_errors(stale, items, "https://go.octolab.org/")), 1)
        self.assertEqual(len(pages.card_errors("", items, "https://go.octolab.org/")), 2)

    def test_smoke_probes_a_path_no_module_takes(self):
        sys.path.insert(0, str(Path(catalog.__file__).parent))
        import pages
        seen = []

        def fake(url, method="GET"):
            seen.append(url)
            if url == "https://example.org/":
                return 200, "text/html", None, "<html></html>"
            return 404, "text/html", None, "/_next/static/"

        original = pages.probe
        pages.probe = fake
        try:
            pages.smoke_once("https://example.org/", [], {}, "vanity-probe-of-a-missing-package-1")
        finally:
            pages.probe = original
        self.assertIn("https://example.org/vanity-probe-of-a-missing-package-1/", seen)
        self.assertNotIn("https://example.org/vanity-smoke-missing-page/", seen)

    def test_settings(self):
        sys.path.insert(0, str(Path(catalog.__file__).parent))
        import pages
        want = {"cname": "go.octolab.org", "https_enforced": True, "build_type": "workflow"}
        good = {"cname": "go.octolab.org", "https_enforced": True, "build_type": "workflow",
                "https_certificate": {"state": "approved"}}
        self.assertEqual(pages.settings_errors(good, want), [])
        self.assertEqual(len(pages.settings_errors({**good, "https_enforced": False}, want)), 1)
        self.assertEqual(len(pages.settings_errors({**good, "cname": None, "build_type": "legacy"}, want)), 2)
        unknown = {k: v for k, v in good.items() if k != "https_enforced"}
        self.assertEqual(pages.settings_errors(unknown, want), [])


class Cards(unittest.TestCase):
    """docs/catalog.json: the hand-written cards, and what the page shows."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        put_cards(self.root)
        self.entries = [ROOT_ENTRY, {**TOOL_ENTRY, "version": "v0.4.2"}]

    def tearDown(self):
        self.tmp.cleanup()

    def cards(self, **change):
        put_cards(self.root, {**CARDS, **change})
        return catalog.read_cards(self.root)

    def test_valid(self):
        cards, errors = catalog.read_cards(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(catalog.check_cards(self.entries, cards), ([], []))

    def test_form_errors(self):
        bad = dict(CARDS["items"][1])
        for change, needle in [({"kind": "app"}, "kind must be"), ({"group": "x"}, "group x is not in groups"),
                               ({"site": "http://example.org/"}, "site must be an https"),
                               ({"releaseNotes": "https://example.org/notes/"}, "must hold {version}"),
                               ({"install": "a\nb"}, "one command"), ({"extra": 1}, "unknown extra"),
                               ({"summary": " "}, "summary required")]:
            _, errors = self.cards(items=[{**bad, **change}])
            self.assertTrue(any(needle in e for e in errors), f"{needle!r} not in {errors}")
        _, errors = self.cards(items=[bad, bad])
        self.assertTrue(any("listed twice" in e for e in errors), errors)
        _, errors = self.cards(groups=[{**CARDS["groups"][0], "id": "private"}])
        self.assertTrue(any("not one of" in e for e in errors), errors)

    def test_a_card_without_an_entry_is_an_error(self):
        cards, _ = self.cards(items=[*CARDS["items"], {**CARDS["items"][1], "module": "go.octolab.org/gone"}])
        errors, _ = catalog.check_cards(self.entries, cards)
        self.assertEqual(errors, [f"{catalog.CARDS}: go.octolab.org/gone has no entry in modules/; "
                                  "remove the card or fix its module"])

    def test_what_a_publisher_causes_is_a_warning(self):
        cards, _ = catalog.read_cards(self.root)
        new = catalog.entry(**{**{k: TOOL_ENTRY[k] for k in catalog.KEYS[1:]},
                               "module": "go.octolab.org/toolset/new", "name": "new"})
        private = {**self.entries[1], "visibility": "private"}
        errors, warnings = catalog.check_cards([ROOT_ENTRY, private, new], cards)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 2)
        data = catalog.site_data(self.root, [ROOT_ENTRY, private, new], cards)
        self.assertEqual([i["module"] for i in data["unlisted"]], ["go.octolab.org/toolset/new"])
        self.assertEqual([i["module"] for i in data["private"]], ["go.octolab.org/toolset/indexit"])
        self.assertIsNone(data["private"][0]["summary"])
        self.assertIsNone(data["private"][0]["docs"])
        self.assertEqual([i["module"] for g in data["groups"] for i in g["items"]], ["go.octolab.org"])

    def test_site_data(self):
        cards, _ = catalog.read_cards(self.root)
        data = catalog.site_data(self.root, self.entries, cards)
        tool = data["groups"][0]["items"][0]
        self.assertEqual(tool["releaseNotes"], "https://indexit.octolab.org/changelog/v0.4.2/")
        self.assertEqual(tool["command"], "brew install --formula octolab/tap/indexit")
        self.assertEqual(tool["page"], "/toolset/indexit/")
        self.assertEqual(tool["docs"], "https://pkg.go.dev/go.octolab.org/toolset/indexit")
        self.assertEqual(tool["tag"], "indexit--v0.4.2")
        self.assertEqual(data["root"]["command"], "go get go.octolab.org@latest")
        self.assertEqual(data["root"]["page"], "/")
        self.assertEqual(data["counts"]["modules"], 2)
        self.assertEqual(data["counts"]["released"], 2)

    def test_release_history_from_catalog_tags(self):
        git(self.root, "init", "-q", "-b", "main")
        catalog.write_entry(self.root, ROOT_ENTRY)
        catalog.write_entry(self.root, {**TOOL_ENTRY, "version": "v0.4.1"})
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "publish v0.4.1")
        git(self.root, "tag", "indexit--v0.4.1")
        git(self.root, "tag", "indexit--v0.4.0")  # the entry of this commit holds another version
        catalog.write_entry(self.root, self.entries[1])
        git(self.root, "commit", "-q", "-am", "publish v0.4.2")
        git(self.root, "tag", "-a", "-m", "x", "indexit--v0.4.2")
        git(self.root, "tag", "not-a-catalog-tag")
        git(self.root, "tag", "\u2028odd\u0085tag")
        # a ref name git accepts but UTF-8 cannot decode (not creatable as a file on macOS)
        head = git(self.root, "rev-parse", "HEAD")
        with open(self.root / ".git/packed-refs", "ab") as refs:
            refs.write(head.encode() + b" refs/tags/odd\xfftag\n")
        git(self.root, "checkout", "-q", "-b", "side")
        catalog.write_entry(self.root, {**TOOL_ENTRY, "version": "v0.9.0"})
        git(self.root, "commit", "-q", "-am", "off main")
        git(self.root, "tag", "indexit--v0.9.0")
        git(self.root, "checkout", "-q", "main")
        # a broken entry, tagged on main and repaired later, is no release and no crash
        (self.root / "modules/go.octolab.org.json").write_bytes(b"[]")
        git(self.root, "commit", "-q", "-am", "broken")
        git(self.root, "tag", "pkg--v0.12.2")
        catalog.write_entry(self.root, ROOT_ENTRY)
        git(self.root, "commit", "-q", "-am", "repaired")
        found = catalog.history(self.root, self.entries)
        self.assertNotIn("pkg", found)
        self.assertEqual([v for v, _ in found["indexit"]], ["v0.4.1", "v0.4.2"])
        self.assertTrue(all(d for _, d in found["indexit"]))
        self.assertEqual(catalog.history(self.root), {})
        cards, _ = catalog.read_cards(self.root)
        tool = catalog.site_data(self.root, self.entries, cards)["groups"][0]["items"][0]
        self.assertEqual(tool["published"], found["indexit"][-1][1])

    def test_a_name_like_a_section_is_anchored_at_its_path(self):
        named = {**TOOL_ENTRY, "name": "private"}
        self.assertEqual(catalog.anchor(named), "go.octolab.org/toolset/indexit")
        self.assertEqual(catalog.anchor(TOOL_ENTRY), "indexit")
        self.assertEqual(catalog.anchor({**TOOL_ENTRY, "name": "tools"}, ["tools"]), "go.octolab.org/toolset/indexit")
        self.assertEqual(catalog.anchor({**TOOL_ENTRY, "name": "how-title"}), "go.octolab.org/toolset/indexit")
        self.assertEqual(catalog.anchor({**TOOL_ENTRY, "name": "resolver-panel"}), "go.octolab.org/toolset/indexit")

    def test_the_last_release_is_a_public_one(self):
        cards, _ = catalog.read_cards(self.root)
        private = {**self.entries[1], "visibility": "private"}
        git(self.root, "init", "-q", "-b", "main")
        for e in (ROOT_ENTRY, private):
            catalog.write_entry(self.root, e)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "publish")
        git(self.root, "tag", "pkg--v0.12.2")
        git(self.root, "tag", "indexit--v0.4.2")
        data = catalog.site_data(self.root, [ROOT_ENTRY, private], cards)
        self.assertEqual(data["latest"]["module"], "go.octolab.org")


class Build(unittest.TestCase):
    """bin/catalog.py build: the pages and modules.yml of the site."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def html(self, package):
        return (self.out / package.removeprefix("go.octolab.org").lstrip("/") / "index.html").read_text()

    def test_page_head(self):
        catalog.render([TOOL_ENTRY], self.out)
        page = self.html("go.octolab.org/toolset/indexit/internal")
        self.assertTrue(page.startswith("""<!DOCTYPE html>
<html lang="en">
<head>
<meta name="go-import" content="go.octolab.org/toolset/indexit git https://github.com/octopot/indexit">
<meta name="go-source" content="go.octolab.org/toolset/indexit https://github.com/octopot/indexit \
https://github.com/octopot/indexit/tree/main{/dir} https://github.com/octopot/indexit/blob/main{/dir}/{file}#L{line}">
<meta charset="utf-8">
"""), page[:600])
        self.assertNotIn("refresh", page)
        self.assertIn('<a href="https://pkg.go.dev/go.octolab.org/toolset/indexit/internal">', page)
        self.assertIn('<a href="https://github.com/octopot/indexit/tree/main/internal">', page)
        self.assertIn("An <code>internal</code> package", page)
        self.assertTrue((self.out / catalog.PAGE_CSS).is_file())

    def test_escapes_what_a_publisher_writes(self):
        sneaky = {**TOOL_ENTRY, "branch": "a<b>"}
        catalog.render([sneaky], self.out)
        page = self.html("go.octolab.org/toolset/indexit")
        self.assertNotIn("a<b>", page)
        self.assertIn("a&lt;b&gt;", page)

    def test_private_module_page(self):
        catalog.render([{**TOOL_ENTRY, "visibility": "private"}], self.out)
        page = self.html("go.octolab.org/toolset/indexit")
        self.assertNotIn("pkg.go.dev", page)
        self.assertIn("GOPRIVATE=go.octolab.org/toolset/indexit", page)

    def test_directory_pages_and_a_root_without_go_files(self):
        tool = {**TOOL_ENTRY, "packages": ["/cmd/indexit"]}
        modules = {e["module"]: e for e in (ROOT_ENTRY, tool)}
        count = catalog.render(list(modules.values()), self.out)
        built = sorted(p.parent.relative_to(self.out).as_posix() for p in self.out.rglob("index.html"))
        self.assertEqual(built, [".", "errors", "sync", "toolset/indexit",
                                 "toolset/indexit/cmd", "toolset/indexit/cmd/indexit"])
        self.assertEqual(count, len(built))
        self.assertIn("DIRECTORY", self.html("go.octolab.org/toolset/indexit/cmd"))
        self.assertNotIn("pkg.go.dev", self.html("go.octolab.org/toolset/indexit/cmd"))
        self.assertEqual((self.out / "modules.yml").read_text(), catalog.manifest(list(modules.values())))
        verify.local(self.out, modules)

    def site(self):
        site = self.out / "export"
        (site / "_next/static").mkdir(parents=True)
        (site / "_next/static/a.js").write_text("x")
        (site / "404").mkdir()
        (site / "404/index.html").write_text("<p>404</p>")
        (site / "404.html").write_text("<p>404</p>")
        (site / "index.html").write_text('<!DOCTYPE html><html><head><meta charSet="utf-8"/>'
                                         '<script src="/_next/static/a.js"></script></head><body>'
                                         '<a href="https://pkg.go.dev/go.octolab.org">Documentation</a></body></html>')
        return site

    def test_compose_puts_the_discovery_tags_first(self):
        modules = {e["module"]: e for e in (ROOT_ENTRY, TOOL_ENTRY)}
        work = self.out / "work"
        work.mkdir()
        catalog.render(list(modules.values()), work)
        catalog.compose(list(modules.values()), work, self.site())
        page = (work / "index.html").read_text()
        self.assertTrue(page.startswith('<!DOCTYPE html><html><head><meta name="go-import" '
                                        'content="go.octolab.org git https://github.com/octolab/pkg">'
                                        '<meta name="go-source"'), page)
        self.assertNotIn("\n", page)
        self.assertTrue((work / "_next/static/a.js").is_file())
        self.assertTrue((work / "404.html").is_file())
        self.assertFalse((work / "404").exists())
        verify.local(work, modules, catalog_page=True)

    def test_compose_never_replaces_an_import_page(self):
        modules = [ROOT_ENTRY, TOOL_ENTRY]
        work = self.out / "work"
        work.mkdir()
        catalog.render(modules, work)
        site = self.site()
        (site / "errors").mkdir()
        (site / "errors/index.html").write_text("x")
        with self.assertRaisesRegex(ValueError, "would replace the import page"):
            catalog.compose(modules, work, site)
        (site / "errors/index.html").unlink()
        (site / "modules.yml").write_text("x")
        with self.assertRaisesRegex(ValueError, "would replace the import page or manifest"):
            catalog.compose(modules, work, site)

    def test_compose_refuses_a_file_where_an_import_page_lives(self):
        modules = [ROOT_ENTRY, TOOL_ENTRY]
        work = self.out / "work"
        work.mkdir()
        catalog.render(modules, work)
        site = self.site()
        (site / "errors").write_text("a file where /errors/ is a directory of pages")
        with self.assertRaisesRegex(ValueError, "collides with an import page"):
            catalog.compose(modules, work, site)

    def test_cli_verify_detects_the_catalog_page(self):
        modules = {e["module"]: e for e in (ROOT_ENTRY, TOOL_ENTRY)}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for e in modules.values():
                catalog.write_entry(root, e)
            work = self.out / "work"
            work.mkdir()
            catalog.render(list(modules.values()), work)
            catalog.compose(list(modules.values()), work, self.site())
            (work / "_not-found").mkdir()
            (work / "_not-found/index.html").write_text("<p>404</p>")
            result = subprocess.run(["python3", "-I", str(Path(verify.__file__)), "--root", str(root), str(work)],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for e in (ROOT_ENTRY, TOOL_ENTRY):
                catalog.write_entry(root, e)
            put_cards(root)
            result = subprocess.run(
                ["python3", "-I", str(Path(catalog.__file__)), "--root", str(root), "build", str(self.out / "site"),
                 "--site", str(self.site())],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Rendered 7 pages of 2 modules\n"
                                        f"Laid the catalog page of {self.out / 'export'} over /\n"
                                        "Verified 2 module roots, 6 packages and 7 pages\n")
        self.assertTrue((self.out / "site/toolset/indexit/cmd/indexit/index.html").is_file())
        self.assertIn("Your Telegram. Your data.", (self.out / "site/toolset/indexit/index.html").read_text())
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["export", "site"])

    def test_cli_build_stops_on_a_broken_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for e in (ROOT_ENTRY, TOOL_ENTRY):
                catalog.write_entry(root, e)
            put_cards(root, {**CARDS, "items": [{**CARDS["items"][1], "module": "go.octolab.org/gone"}]})
            result = subprocess.run(
                ["python3", "-I", str(Path(catalog.__file__)), "--root", str(root), "build", str(self.out / "site")],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("go.octolab.org/gone has no entry", result.stderr)
        self.assertFalse((self.out / "site").exists())


if __name__ == "__main__":
    unittest.main()
