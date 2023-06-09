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


class Verify(unittest.TestCase):
    def setUp(self):
        self.modules = {e["module"]: e for e in (ROOT_ENTRY, TOOL_ENTRY)}

    def page(self, package, module="go.octolab.org/toolset/indexit", repo="https://github.com/octopot/indexit",
             branch="main", docs=None):
        docs = docs or f"https://pkg.go.dev/{package}"
        return (
            f'<meta name="go-import" content="{module} git {repo}">'
            f'<meta name="go-source" content="{module} {repo} {repo}/tree/{branch}{{/dir}} '
            f'{repo}/blob/{branch}{{/dir}}/{{file}}#L{{line}}">'
            f'<meta http-equiv="refresh" content="0; url={docs}"><a href="{docs}">move along</a>'
        )

    def test_good_page(self):
        verify.verify(self.page("go.octolab.org/toolset/indexit/internal"), "go.octolab.org/toolset/indexit/internal",
                      self.modules)

    def test_wrong_branch(self):
        with self.assertRaisesRegex(ValueError, "go-source"):
            verify.verify(self.page("go.octolab.org/toolset/indexit", branch="master"),
                          "go.octolab.org/toolset/indexit", self.modules)

    def test_wrong_redirect(self):
        with self.assertRaisesRegex(ValueError, "refresh"):
            verify.verify(self.page("go.octolab.org/toolset/indexit", docs="https://evil.example/x"),
                          "go.octolab.org/toolset/indexit", self.modules)

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


if __name__ == "__main__":
    unittest.main()
