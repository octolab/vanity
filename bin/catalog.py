#!/usr/bin/env python3
"""The catalog of go.octolab.org: entries under modules/, their rules, the site.

Commands:
  check     validate every entry and the catalog invariants, offline;
            with --untrusted / --transitions-from, also the rules for what a
            publisher wrote (see README, "Security model").
  manifest  print the manifest (modules.yml) built from the entries; the site
            publishes it next to the pages.
  build     render the site: an import page per package and per directory up
            to its module root, and modules.yml; check it with bin/verify.py
            and only then replace DIR.
  progress  how many modules publish themselves and which still sit on seeds
            (version null, dumped from the submodules); --summary FILE appends
            it as Markdown, e.g. to $GITHUB_STEP_SUMMARY.

The standard library only. The deploy gate runs this file as it is at the last
deployed revision, so keep it self-contained and keep --root explicit there.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOST = "go.octolab.org"
SCHEMA = 1
KEYS = (
    "schema",
    "name",
    "module",
    "repository",
    "branch",
    "visibility",
    "scope",
    "packages",
    "topics",
    "version",
    "commit",
)
MAX_PACKAGES = 5000
MAX_TOPICS = 20

MODULE = re.compile(r"go\.octolab\.org(/[a-z0-9]([a-z0-9._-]*[a-z0-9])?)*")
# kebab-case segments joined by "/", e.g. indexit or ecosystem/tablo; the tag
# <name>--vX.Y.Z is a valid git ref and no two names' tags conflict as ref
# files and directories: a segment never holds "--"
NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)*")
MAX_NAME = 64
REPOSITORY = re.compile(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+")
BRANCH = re.compile(r"[A-Za-z0-9._/-]+")
PACKAGE = re.compile(r"(/[A-Za-z0-9._~+-]+)+")
TOPIC = re.compile(r"[a-z0-9][a-z0-9-]{0,49}")
VERSION = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
COMMIT = re.compile(r"[0-9a-f]{40}")
ENTRY_PATH = re.compile(r"modules/(.+)\.json")
SUFFIX = re.compile(r"/v([0-9.]+)$")


def entry(**fields):
    """An entry with its keys in canonical order."""
    missing = set(KEYS[1:]) - set(fields)
    extra = set(fields) - set(KEYS)
    if missing or extra:
        raise ValueError(f"entry fields: missing {sorted(missing)}, unexpected {sorted(extra)}")
    return {"schema": SCHEMA, **{key: fields[key] for key in KEYS[1:]}}


def canonical(value):
    """Canonical bytes: two-space JSON, ASCII only, a trailing newline."""
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def entry_path(module):
    return f"modules/{module}.json"


def write_entry(root, value):
    path = Path(root) / entry_path(value["module"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def full(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def suffix_problem(module):
    """Go reads a last element v<digits or dots> as a major version suffix: only /vN, N >= 2."""
    match = SUFFIX.search(module)
    if match is None:
        return None
    digits = match.group(1)
    if re.fullmatch(r"[1-9][0-9]*", digits) and int(digits) >= 2:
        return None
    return f"{module}: a major version suffix must be /v2 or higher, digits only"


def major_problem(module, version):
    """Go's major version rule: no suffix takes v0/v1, /vN (N >= 2) takes vN only."""
    major = int(VERSION.fullmatch(version).group(1))
    match = SUFFIX.search(module)
    if match:
        if major != int(match.group(1)):
            return f"{version} does not match the major version suffix of {module}"
    elif major > 1:
        return f"{version} needs the module path {module}/v{major}"
    return None


def validate(value, path):
    """Errors of one entry read from path (relative to the root, POSIX)."""
    where = path
    if not isinstance(value, dict):
        return [f"{where}: not a JSON object"]
    if list(value) != list(KEYS):
        return [f"{where}: keys must be exactly {', '.join(KEYS)} in this order"]
    errors = []

    def fail(message):
        errors.append(f"{where}: {message}")

    if type(value["schema"]) is not int or value["schema"] != SCHEMA:
        fail(f"schema must be {SCHEMA}")

    module = value["module"]
    if not full(MODULE, module) or ".." in module:
        fail(f"module {module!r} is not a module path under {HOST}")
    else:
        if path != entry_path(module):
            fail(f"module {module} belongs in {entry_path(module)}")
        if suffix_problem(module):
            fail(suffix_problem(module))

    if not full(NAME, value["name"]) or len(value["name"]) > MAX_NAME:
        fail(f"name {value['name']!r} must match {NAME.pattern}, at most {MAX_NAME} characters")

    repository = value["repository"]
    if not full(REPOSITORY, repository) or repository.endswith(".git"):
        fail(f"repository {repository!r} must be https://github.com/<owner>/<name> without .git")

    branch = value["branch"]
    if not full(BRANCH, branch) or branch.startswith(("-", "/")) or ".." in branch:
        fail(f"branch {branch!r} is not a valid branch name")

    if value["visibility"] not in ("public", "private", "internal"):
        fail("visibility must be public, private or internal")

    scope = value["scope"]
    if scope not in ("all", "root"):
        fail("scope must be all or root")

    packages = value["packages"]
    if not isinstance(packages, list) or not all(isinstance(p, str) for p in packages):
        fail("packages must be a list of strings")
    else:
        if not packages or packages[0] != "":
            fail('packages must start with "" (the module root)')
        if len(packages) > MAX_PACKAGES:
            fail(f"packages: more than {MAX_PACKAGES}")
        if packages != sorted(set(packages)):
            fail("packages must be unique and sorted in byte order")
        for p in packages[1:]:
            segments = p.split("/")[1:]
            if not full(PACKAGE, p) or any(
                s in (".", "..", "testdata", "vendor") or s.startswith((".", "_"))
                for s in segments
            ):
                fail(f"package {p!r} is not a publishable package directory")
        if scope == "root" and packages != [""]:
            fail('scope root publishes the module root only: packages must be [""]')

    topics = value["topics"]
    if not isinstance(topics, list) or not all(full(TOPIC, t) for t in topics):
        fail(f"topics must be a list of GitHub topics ({TOPIC.pattern})")
    elif len(topics) > MAX_TOPICS or topics != sorted(set(topics)):
        fail(f"topics must be unique, sorted, at most {MAX_TOPICS}")

    version = value["version"]
    if version is not None and not full(VERSION, version):
        fail(f"version {version!r} must be null or a stable vX.Y.Z")
    elif version is not None and full(MODULE, module) and not suffix_problem(module):
        problem = major_problem(module, version)
        if problem:
            fail(problem)

    if not full(COMMIT, value["commit"]):
        fail("commit must be a full lowercase SHA-1")
    return errors


def parse(data, path):
    """The entry in data (bytes) read from path, and its errors."""
    try:
        text = data.decode("ascii")
        value = json.loads(text)
    except (UnicodeDecodeError, ValueError) as error:
        return None, [f"{path}: not ASCII JSON: {error}"]
    errors = validate(value, path)
    if not errors and canonical(value) != data:
        errors.append(f"{path}: not in canonical form (two-space JSON, ASCII, trailing newline)")
    return value, errors


def load(root):
    """All entries under root/modules, and the errors found (S1)."""
    root = Path(root)
    base = root / "modules"
    entries, errors = [], []
    if not base.is_dir() or base.is_symlink():
        return entries, ["modules/ is missing"]
    for item in sorted(base.rglob("*")):
        rel = item.relative_to(root).as_posix()
        if item.is_symlink():
            errors.append(f"{rel}: symbolic links are not allowed")
            continue
        if item.is_dir():
            continue
        if not item.is_file() or not rel.endswith(".json"):
            errors.append(f"{rel}: only entries (<module path>.json) belong under modules/")
            continue
        value, problems = parse(item.read_bytes(), rel)
        errors.extend(problems)
        if not problems:
            entries.append(value)
    entries.sort(key=lambda e: e["module"])
    return entries, errors


def rendered(e):
    """Pages of an entry: its packages and their parents inside the module."""
    pages = set()
    for p in e["packages"]:
        while True:
            pages.add(e["module"] + p)
            if not p:
                break
            p = p.rsplit("/", 1)[0]
    return pages


def invariants(entries):
    """S2 the root module exists; S3 full package paths are disjoint; S4 names are unique;
    S5 no entry renders a page (a parent of its packages) that another entry publishes."""
    errors = []
    if HOST not in {e["module"] for e in entries}:
        errors.append(f"S2: the root module {HOST} has no entry")
    owner = {}
    for e in entries:
        for p in e["packages"]:
            package = e["module"] + p
            if package in owner:
                errors.append(f"S3: {package} is published by both {owner[package]} and {e['module']}")
            else:
                owner[package] = e["module"]
    for e in entries:
        for page in sorted(rendered(e)):
            other = owner.get(page)
            if other and other != e["module"]:
                errors.append(f"S5: {e['module']} renders {page}, published by {other}")
    names = {}
    for e in entries:
        if e["name"] in names:
            errors.append(f"S4: name {e['name']} is used by both {names[e['name']]} and {e['module']}")
        else:
            names[e["name"]] = e["module"]
    return errors


def git_show(root, rev, path):
    """Bytes of path at rev, or None if it does not exist there."""
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "blob", f"{rev}:{path}"],
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def untrusted(root, paths=(), transitions=()):
    """Rules for what a publisher (any push not by the maintainer) wrote.

    paths: the paths whose last writer since the last deployment is a
    publisher; each must be an entry that exists now. transitions: (commit,
    path) for every path such a commit changed; the entry must survive the
    commit and keep the repository and name it had in the commit's parent.
    """
    root = Path(root)
    errors = []
    for path in paths:
        if not ENTRY_PATH.fullmatch(path):
            errors.append(f"{path}: a publisher may change modules/<module path>.json only")
            continue
        current = root / path
        if current.is_symlink() or not current.is_file():
            errors.append(f"{path}: a publisher may not delete an entry")
            continue
        errors.extend(parse(current.read_bytes(), path)[1])
    for commit, path in transitions:
        where = f"{path} in {commit[:12]}"
        if not COMMIT.fullmatch(commit):
            errors.append(f"{where}: not a commit")
            continue
        if not ENTRY_PATH.fullmatch(path):
            errors.append(f"{where}: a publisher may change modules/<module path>.json only")
            continue
        after = git_show(root, commit, path)
        if after is None:
            errors.append(f"{where}: a publisher may not delete an entry")
            continue
        value, problems = parse(after, path)
        if problems:
            errors.extend(f"{where}: {p}" for p in problems)
            continue
        before = git_show(root, f"{commit}^", path)
        if before is None:
            continue
        previous, problems = parse(before, path)
        if problems:
            errors.append(f"{where}: the entry before it is invalid; a maintainer must change it")
            continue
        for key in ("repository", "name"):
            if previous[key] != value[key]:
                errors.append(
                    f"{where}: a publisher may not change {key} "
                    f"({previous[key]} -> {value[key]}); a maintainer moves it"
                )
    return errors


def check(root, paths=(), transitions=()):
    entries, errors = load(root)
    errors += invariants(entries)
    if paths or transitions:
        errors += untrusted(root, paths, transitions)
    return errors


def manifest(entries):
    """modules.yml, the catalog as the site publishes it, block by block."""
    out = []
    for e in entries:
        url, branch, module = e["repository"], e["branch"], e["module"]
        out.append(f"- prefix: {module}\n")
        out.append("  import:\n")
        out.append(f"    - url: {url}\n")
        out.append("      vcs: git\n")
        out.append("      source:\n")
        out.append(f"        url:  {url}\n")
        out.append(f"        dir:  {url}/tree/{branch}{{/dir}}\n")
        out.append(f"        file: {url}/blob/{branch}{{/dir}}/{{file}}#L{{line}}\n")
        out.append("  packages:\n")
        for p in e["packages"]:
            out.append(f"    - {module}{p}\n")
        out.append(f"  tags: [ {', '.join(e['topics'])} ]\n")
    return "".join(out)


PAGE = """<!DOCTYPE html>
<html lang="en">
    <head>
        <meta name="go-import" content="{module} git {url}">
        <meta name="go-source" content="{module} {url} {url}/tree/{branch}{{/dir}} {url}/blob/{branch}{{/dir}}/{{file}}#L{{line}}">
        <meta http-equiv="content-type" content="text/html; charset=utf-8">
        <meta http-equiv="refresh" content="0; url=https://pkg.go.dev/{package}">
        <title>{package}</title>
    </head>
    <body>
        Nothing to see here. Please <a href="https://pkg.go.dev/{package}">move along</a>.
    </body>
</html>
"""


def pages(entries):
    """(package, html) for every page of the site, in the order they are written.

    A page per published package and per directory between a package and the
    root of its module, so that every prefix of an import path resolves. S5
    keeps the pages of two entries apart.
    """
    for e in sorted(entries, key=lambda e: e["module"]):
        values = {k: html.escape(e[k]) for k in ("module", "branch")}
        values["url"] = html.escape(e["repository"])
        for package in sorted(rendered(e)):
            yield package, PAGE.format(package=html.escape(package), **values)


def render(entries, directory):
    """Write the pages of the site and modules.yml into an empty directory; the page count."""
    count = 0
    for package, page in pages(entries):
        target = Path(directory, *package.removeprefix(HOST).split("/"), "index.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding="utf-8")
        count += 1
    Path(directory, "modules.yml").write_text(manifest(entries), encoding="utf-8")
    return count


def build(entries, directory):
    """Render the site next to directory, verify it, then put it in its place."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import verify  # the independent check of the pages; it imports this file

    target = Path(directory).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".dist.", dir=target.parent))
    try:
        print(f"Rendered {render(entries, work)} pages of {len(entries)} modules")
        verify.local(work, {e["module"]: e for e in entries})
        shutil.rmtree(target, ignore_errors=True)
        work.rename(target)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def progress(entries):
    """(published, total, seeds): a seed is an entry no release has written yet
    (version null, dumped from the submodules); a release displaces it."""
    seeds = sorted(e["name"] for e in entries if e["version"] is None)
    return len(entries) - len(seeds), len(entries), seeds


def progress_text(entries):
    published, total, seeds = progress(entries)
    line = f"Self-published: {published} of {total} modules; on seeds: {len(seeds)}"
    return line + (f" ({', '.join(seeds)})" if seeds else "")


def progress_summary(entries):
    """The same as Markdown for a job summary."""
    published, total, seeds = progress(entries)
    out = ["### Catalog: self-publishing", "",
           f"**{published} of {total}** modules publish themselves; **{len(seeds)}** still on seeds (`version: null`)."]
    if seeds:
        out += ["", ", ".join(f"`{name}`" for name in seeds)]
    return "\n".join(out) + "\n"


def report(errors):
    """Print errors; on GitHub Actions as escaped ::error:: commands."""
    actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for error in errors:
        if actions:
            error = error.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::error::{error}", file=sys.stderr)
        else:
            print(error, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="catalog checkout (default: the one holding this file)")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="validate the entries and the catalog invariants")
    c.add_argument("--untrusted", action="append", default=[], metavar="PATH",
                   help="a path whose last writer is a publisher (repeatable)")
    c.add_argument("--untrusted-from", type=Path, metavar="FILE",
                   help="read more such paths from FILE, one per line")
    c.add_argument("--transitions-from", type=Path, metavar="FILE",
                   help="read <commit> TAB <path> lines: what each publisher commit changed")
    sub.add_parser("manifest", help="print modules.yml built from the entries")
    b = sub.add_parser("build", help="render and verify the site, then replace DIR with it")
    b.add_argument("directory", type=Path, metavar="DIR")
    pr = sub.add_parser("progress", help="how many modules publish themselves, which are still seeds")
    pr.add_argument("--summary", type=Path, metavar="FILE",
                    help="also append it as Markdown to FILE, e.g. $GITHUB_STEP_SUMMARY")
    args = parser.parse_args()

    if args.command == "progress":
        entries, errors = load(args.root)
        errors += invariants(entries)
        if errors:
            report(errors)
            raise SystemExit(1)
        print(progress_text(entries))
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as f:
                f.write(progress_summary(entries))
        return

    if args.command in ("manifest", "build"):
        entries, errors = load(args.root)
        errors += invariants(entries)
        if errors:
            report(errors)
            raise SystemExit(1)
        if args.command == "build":
            build(entries, args.directory)
        else:
            sys.stdout.write(manifest(entries))
        return

    paths = list(args.untrusted)
    if args.untrusted_from:
        paths += [line for line in args.untrusted_from.read_text().splitlines() if line]
    transitions = []
    if args.transitions_from:
        for line in args.transitions_from.read_text().splitlines():
            if line:
                commit, _, path = line.partition("\t")
                transitions.append((commit, path))
    errors = check(args.root, paths, transitions)
    if errors:
        report(errors)
        raise SystemExit(1)
    entries, _ = load(args.root)
    count = sum(len(e["packages"]) for e in entries)
    print(f"Checked {len(entries)} entries, {count} packages"
          + (f"; {len(paths)} publisher-written paths, {len(transitions)} publisher changes"
             if paths or transitions else ""))


if __name__ == "__main__":
    main()
