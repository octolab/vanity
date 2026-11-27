#!/usr/bin/env python3
"""The catalog of go.octolab.org: entries under modules/, their rules, the site.

Commands:
  check     validate every entry and the catalog invariants, offline;
            with --untrusted / --transitions-from, also the rules for what a
            publisher wrote (see README, "Security model").
  manifest  print the manifest (modules.yml) built from the entries; the site
            publishes it next to the pages.
  build     render the site: a page per package and per directory up to its
            module root, for the go command and for people, and modules.yml;
            with --site, lay the catalog page (the static export of docs/)
            over /; check it with bin/verify.py and only then replace DIR.
  cards     check docs/catalog.json, the hand-written cards of the catalog
            page, against the entries; warn about public modules without one.
  site      print what the catalog page shows as JSON: entries, cards and
            the release history from the catalog tags; docs/ reads it.
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
import time
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
# files at the root of the site: no page of a module or package may take their
# place, or the build could not lay them side by side (the catalog page is a
# static export next to the import pages; a path segment never starts with "_")
MAX_SEGMENT, MAX_PATH = 100, 400
RESERVED = ("404", "404.html", "icon.svg", "index.html", "index.txt", "modules.yml", "og.png",
            "robots.txt", "sitemap.xml")
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


def reserved_problem(path):
    """A path whose page would take the place of a file of the site: a file at
    its root, or index.html anywhere, the file every page is written to."""
    # case-insensitive: a Mac builds on a file system that ignores case
    segments = path[len(HOST):].lstrip("/").split("/")
    lowered = [s.lower() for s in segments]
    if lowered[0] in RESERVED:
        return f"/{segments[0]} is a file of the site, not a module path (reserved: {', '.join(RESERVED)})"
    if "index.html" in lowered:
        return "index.html is the file of every page, not a path segment"
    # file systems cap a name at 255 bytes; leave room for what the build adds
    if any(len(s.encode()) > MAX_SEGMENT for s in segments) or len(path.encode()) > MAX_PATH:
        return f"a path segment is longer than {MAX_SEGMENT} bytes or the path longer than {MAX_PATH}"
    return None


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
        if reserved_problem(module):
            fail(reserved_problem(module))

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
        for p in packages[1:]:
            if full(MODULE, module) and reserved_problem(module + p):
                fail(f"package {p!r}: {reserved_problem(module + p)}")
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


# --- the cards: what a person reads, written by hand ---------------------------
#
# docs/catalog.json is the maintainer's: publishers can write modules/ only.
# Nothing a publisher writes can fail the site: a public module without a card
# is listed from its entry alone, and a card of a module that became private is
# set aside. Errors are the maintainer's own mistakes in docs/catalog.json.

CARDS = "docs/catalog.json"
GROUP_KEYS = ("id", "eyebrow", "title", "lead")
CARD_REQUIRED = ("module", "group", "kind", "emoji", "title", "tagline", "summary")
CARD_OPTIONAL = ("site", "releaseNotes", "install")
KINDS = ("tool", "library", "template", "service")
# anchors of the page's own sections; a module named like one is anchored at its path
SECTIONS = ("top", "how", "unlisted", "private", "notes")
# ids the page's own parts take: a heading of a section, the resolver of the hero
ID_SUFFIXES, ID_PREFIXES = ("-title",), ("resolver-",)
HTTPS_URL = re.compile(r"https://[a-z0-9-]+(\.[a-z0-9-]+)+/[^\s\"'<>]*")
DOCS_URL = "https://pkg.go.dev/"


def read_cards(root):
    """docs/catalog.json, and the problems of its form."""
    path = Path(root) / CARDS
    empty = {"groups": [], "items": []}
    if not path.is_file():
        return empty, [f"{CARDS} is missing"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        return empty, [f"{CARDS}: not JSON: {error}"]
    if not isinstance(data, dict) or set(data) != {"groups", "items"} or not all(
            isinstance(data[k], list) for k in ("groups", "items")):
        return empty, [f"{CARDS}: must be an object with the lists groups and items"]
    errors = []
    groups = []
    for group in data["groups"]:
        where = f"{CARDS}: group {group.get('id', '?') if isinstance(group, dict) else '?'}"
        if not isinstance(group, dict) or set(group) != set(GROUP_KEYS):
            errors.append(f"{where}: must have exactly {', '.join(GROUP_KEYS)}")
            continue
        if not all(isinstance(group[k], str) and group[k].strip() for k in GROUP_KEYS):
            errors.append(f"{where}: {', '.join(GROUP_KEYS)} must be non-empty strings")
            continue
        if not re.fullmatch(r"[a-z]+", group["id"]) or group["id"] in SECTIONS:
            errors.append(f"{where}: id must be lowercase letters and not one of {', '.join(SECTIONS)}")
            continue
        if any(g["id"] == group["id"] for g in groups):
            errors.append(f"{where}: listed twice")
            continue
        groups.append(group)
    items = []
    for card in data["items"]:
        where = f"{CARDS}: {card.get('module', '?') if isinstance(card, dict) else '?'}"
        if not isinstance(card, dict):
            errors.append(f"{where}: a card is an object")
            continue
        unknown = set(card) - set(CARD_REQUIRED) - set(CARD_OPTIONAL)
        missing = [k for k in CARD_REQUIRED if not (isinstance(card.get(k), str) and card[k].strip())]
        if unknown or missing:
            errors.append(f"{where}: " + "; ".join(
                ([f"unknown {', '.join(sorted(unknown))}"] if unknown else [])
                + ([f"{', '.join(missing)} required"] if missing else [])))
            continue
        problems = []
        if card["kind"] not in KINDS:
            problems.append(f"kind must be one of {', '.join(KINDS)}")
        if card["group"] not in {g["id"] for g in groups}:
            problems.append(f"group {card['group']} is not in groups")
        for key in ("site", "releaseNotes"):
            if key in card and not full(HTTPS_URL, card[key]):
                problems.append(f"{key} must be an https:// URL with a path, e.g. https://example.org/")
        if "releaseNotes" in card and "{version}" not in card["releaseNotes"]:
            problems.append("releaseNotes must hold {version}, the published version without v")
        if "install" in card and not (isinstance(card["install"], str) and card["install"].strip()
                                      and "\n" not in card["install"]):
            problems.append("install must be one command on one line")
        if any(c["module"] == card["module"] for c in items):
            problems.append("listed twice")
        if problems:
            errors.extend(f"{where}: {p}" for p in problems)
            continue
        items.append(card)
    return {"groups": groups, "items": items}, errors


def check_cards(entries, cards):
    """(errors, warnings) of the cards against the entries.

    Errors: a card of a module the catalog does not have (only a maintainer
    removes an entry). Warnings: what a publisher can cause and the page copes
    with: a public module without a card, a card of a private module.
    """
    errors, warnings = [], []
    by_module = {e["module"]: e for e in entries}
    for card in cards["items"]:
        e = by_module.get(card["module"])
        if e is None:
            errors.append(f"{CARDS}: {card['module']} has no entry in modules/; remove the card or fix its module")
        elif e["visibility"] != "public":
            warnings.append(f"{CARDS}: {card['module']} is {e['visibility']}; the page lists private modules "
                            "by their path only (#499), so this card is not shown")
    described = {c["module"] for c in cards["items"]}
    for e in entries:
        if e["visibility"] == "public" and e["module"] not in described:
            warnings.append(f"{e['module']}: no card in {CARDS}; the page lists it under \"Not described yet\" "
                            "until one is added (AGENTS.md, \"Add a module\")")
    return errors, warnings


def git_out(root, *args):
    # a ref name may hold any byte: undecodable ones come back as surrogates
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                            encoding="utf-8", errors="surrogateescape")
    return result.stdout if result.returncode == 0 else None


def history(root, entries=()):
    """{name: [(version, YYYY-MM-DD)]} from the catalog tags <name>--vX.Y.Z.

    A tag counts as the README says: on a commit of the checked-out branch whose
    entry of that name holds that version. Nothing without git or in a shallow
    clone, whose dates would be those of its boundary; no date in the future.
    """
    if (git_out(root, "rev-parse", "--is-shallow-repository") or "").strip() != "false":
        return {}
    modules = {e["name"]: e["module"] for e in entries}
    out = git_out(root, "for-each-ref", "--format=%(refname:strip=2) %(*objectname) %(objectname) "
                  "%(*committerdate:unix) %(committerdate:unix)", "refs/tags/") or ""
    now = time.time()
    found = {}
    # one record per LF; a tag is a publisher's too: skip what is not a catalog tag
    for line in out.split("\n"):
        fields = line.split(" ")
        if len(fields) < 3 or not fields[0].isascii() or not fields[0].isprintable():
            continue
        tag, *rest = fields
        name, sep, version = tag.rpartition("--")
        if not sep or not full(VERSION, version) or name not in modules:
            continue
        commit = next((r for r in rest if full(COMMIT, r)), None)
        stamp = next((int(r) for r in rest if r.isdigit()), None)
        if commit is None or subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", commit, "HEAD"],
                                            capture_output=True).returncode:
            continue
        path = entry_path(modules[name])
        recorded = git_show(root, commit, path)
        # an entry of history is a publisher's: anything but a valid one is no release
        try:
            value, problems = parse(recorded, path) if recorded is not None else (None, ["missing"])
        except (RecursionError, ValueError, TypeError):
            continue
        if problems or value["version"] != version:
            continue
        day = time.strftime("%Y-%m-%d", time.gmtime(stamp)) if stamp is not None and stamp <= now else None
        found.setdefault(name, []).append((version, day))
    for name in found:
        found[name].sort(key=lambda r: tuple(int(x) for x in r[0][1:].split(".")))
    return found


def page_url(package):
    """The path of a package's page on the site: / for the root module."""
    return "/" + "".join(f"{s}/" for s in package.removeprefix(HOST).split("/") if s)


def anchor(e, groups=()):
    """The id of a module's card: its name, or its path when the name is taken by
    a section or a group of the page, or looks like a heading's id."""
    name = e["name"]
    taken = (name in SECTIONS or name in groups or name.endswith(ID_SUFFIXES)
             or name.startswith(ID_PREFIXES))
    return e["module"] if taken else name


def command(e, card):
    if card and card.get("install"):
        return card["install"]
    if card and card["kind"] == "library":
        return f"go get {e['module']}@latest"
    return None


def describe(e, card, tags, groups=()):
    """One module as the site shows it: its entry, its card, its releases."""
    public = e["visibility"] == "public"
    card = card if public else None
    releases = tags.get(e["name"], [])
    published = next((d for v, d in releases if v == e["version"]), None)
    owner_name = e["repository"].removeprefix("https://github.com/")
    item = {
        "module": e["module"],
        "name": e["name"],
        "anchor": anchor(e, groups),
        "page": page_url(e["module"]),
        "repository": e["repository"],
        "repo": owner_name,
        "branch": e["branch"],
        "visibility": e["visibility"],
        "topics": e["topics"],
        "version": e["version"],
        "commit": e["commit"],
        "tag": f"{e['name']}--{e['version']}" if e["version"] else None,
        "published": published,
        "history": [{"version": v, "date": d} for v, d in releases],
        "packages": [{"path": p, "import": e["module"] + p, "page": page_url(e["module"] + p)}
                     for p in e["packages"]],
        "docs": DOCS_URL + e["module"] if public else None,
        "described": card is not None,
        "group": card["group"] if card else None,
        "kind": card["kind"] if card else None,
        "emoji": card["emoji"] if card else None,
        "title": card["title"] if card else e["name"],
        "tagline": card["tagline"] if card else None,
        "summary": card["summary"] if card else None,
        "site": card.get("site") if card else None,
        "releaseNotes": (card["releaseNotes"].replace("{version}", e["version"][1:])
                         if card and card.get("releaseNotes") and e["version"] else None),
        "command": command(e, card),
    }
    return item


def site_data(root, entries, cards):
    """What the catalog page shows, as one JSON-able object (catalog.py site)."""
    tags = history(root, entries)
    cards_by_module = {c["module"]: c for c in cards["items"]}
    group_ids = [g["id"] for g in cards["groups"]]
    items = {e["module"]: describe(e, cards_by_module.get(e["module"]), tags, group_ids) for e in entries}
    groups = []
    for group in cards["groups"]:
        members = [items[c["module"]] for c in cards["items"]
                   if c["group"] == group["id"] and c["module"] in items and items[c["module"]]["described"]]
        groups.append({**group, "items": members})
    # only a card lists the packages of its module: the rest of the page needs
    # none, and the data stays small whatever the entries hold
    for item in items.values():
        if not item["described"]:
            item["packages"] = item["packages"][:1]
    unlisted = [i for i in items.values() if i["visibility"] == "public" and not i["described"]]
    private = [i for i in items.values() if i["visibility"] != "public"]
    # the hero names the last release: a public module's only (#499)
    released = [i for i in items.values() if i["published"] and i["visibility"] == "public"]
    latest = max(released, key=lambda i: (i["published"], i["module"]), default=None)
    root_item = items.get(HOST)
    return {
        "host": HOST,
        "root": root_item,
        "groups": groups,
        "unlisted": unlisted,
        "private": private,
        "latest": latest and {k: latest[k] for k in ("module", "name", "title", "anchor", "version", "published",
                                                      "releaseNotes")},
        "updated": latest["published"] if latest else None,
        "counts": {
            "modules": len(entries),
            "packages": sum(len(e["packages"]) for e in entries),
            "public": sum(1 for e in entries if e["visibility"] == "public"),
            "private": len(private),
            "released": sum(1 for e in entries if e["version"]),
            "releases": sum(len(v) for v in tags.values()),
        },
    }


# --- the pages: one per package, for the go command and for people ----------
#
# The go command reads go-import (and godoc tools go-source) from the head of
# the page it gets for ?go-get=1: both come first, before anything else, and
# the rest of the page is for people. No redirect: the page itself says what
# the package is and links its documentation, source and project.

# one stylesheet for every page; a path segment of a module never starts with "_"
PAGE_CSS = "_vanity/page.css"
STYLE = """
:root{--paper:#f7f8fa;--ink:#14202e;--muted:#56626f;--line:#dbe1e8;--accent:#00677f;--wash:#ebf0f4;--card:#fff;--gold:#b3831a;
--mono:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,monospace;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--paper:#0e131a;--ink:#e5ecf2;--muted:#9eabb8;--line:#25303c;--accent:#6fd0e6;--wash:#17202a;--card:#121921;--gold:#e5bd5c}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline;text-underline-offset:3px}
a:focus-visible{outline:3px solid var(--accent);outline-offset:3px;border-radius:3px}
.bar,.wrap,footer{max-width:960px;margin:0 auto;padding:0 20px}
.bar{display:flex;justify-content:space-between;align-items:center;gap:16px;padding-top:18px;padding-bottom:18px;border-bottom:1px solid var(--line)}
.wordmark{color:var(--ink);font-weight:750;font-size:20px;letter-spacing:-.04em}.wordmark span{margin-right:8px}
.bar nav{display:flex;gap:18px;font-size:14px;font-weight:600}.bar nav a{color:var(--ink)}
.crumbs{margin:34px 0 0;font:13px/1.6 var(--mono);color:var(--muted);overflow-wrap:anywhere}.crumbs a{color:var(--muted)}.crumbs a:hover{color:var(--accent)}
.eyebrow{margin:26px 0 8px;font:600 11px/1.6 var(--mono);letter-spacing:.12em;color:var(--accent)}
h1{margin:0;font-size:clamp(30px,5vw,46px);line-height:1.12;letter-spacing:-.045em;font-weight:680;overflow-wrap:anywhere}
.tagline{margin:14px 0 0;font-size:20px;font-weight:600;letter-spacing:-.02em}
.lead{margin:10px 0 0;max-width:680px;color:var(--muted)}
.command{display:flex;align-items:center;gap:10px;margin:26px 0 0;padding:12px 16px;border-radius:10px;background:#101a26;color:#e8f0f6;font:14px/1.5 var(--mono);overflow-wrap:anywhere}
.command span{color:#7fd6ea;user-select:none}
.note{margin:10px 0 0;color:var(--muted);font-size:14px}.note code,.lead code{font:13px var(--mono);background:var(--wash);padding:.1em .35em;border-radius:5px}
.links{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0 0;padding:0;list-style:none}
.links a{display:inline-block;padding:8px 14px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font-size:14px;font-weight:600}
.links a:hover{border-color:var(--accent);text-decoration:none}.links li:first-child a{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.facts{display:grid;grid-template-columns:max-content 1fr;gap:8px 22px;margin:34px 0 0;padding:20px 22px;border:1px solid var(--line);border-radius:12px;background:var(--card);font-size:14px}
.facts dt{color:var(--muted)}.facts dd{margin:0;font-family:var(--mono);font-size:13px;overflow-wrap:anywhere}
h2{margin:40px 0 12px;font-size:20px;letter-spacing:-.02em}
.dirs{margin:0;padding:0;list-style:none;border-top:1px solid var(--line)}
.dirs li{display:flex;justify-content:space-between;gap:12px;padding:9px 4px;border-bottom:1px solid var(--line);font:14px/1.5 var(--mono)}
.dirs li a{min-width:0;overflow-wrap:anywhere}.dirs small{flex:none;color:var(--muted);font:11px/1.9 var(--mono);letter-spacing:.06em;text-transform:uppercase}
details{margin:40px 0 0;padding:16px 20px;border:1px dashed var(--line);border-radius:12px;color:var(--muted);font-size:14px}
summary{cursor:pointer;color:var(--ink);font-weight:600}
details pre{margin:12px 0 0;padding:12px;border-radius:8px;background:var(--wash);color:var(--ink);font:12px/1.6 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere}
footer{display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-top:56px;padding-top:20px;padding-bottom:36px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
@media (max-width:600px){.facts{grid-template-columns:1fr;gap:2px}.facts dd{margin-bottom:10px}}
"""


def discovery(e):
    """The two meta tags the go command and godoc tools read, escaped."""
    module, url, branch = (html.escape(e[k]) for k in ("module", "repository", "branch"))
    return (f'<meta name="go-import" content="{module} git {url}">\n'
            f'<meta name="go-source" content="{module} {url} {url}/tree/{branch}{{/dir}} '
            f'{url}/blob/{branch}{{/dir}}/{{file}}#L{{line}}">\n')


def human_date(day):
    if not day:
        return None
    y, m, d = (int(x) for x in day.split("-"))
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{d} {months[m - 1]} {y}"


def package_page(package, e, item, pages_of_entry):
    """The page of one package (or directory) of entry e, for go and for people."""
    esc = html.escape
    module = e["module"]
    rel = package[len(module):]
    is_root = rel == ""
    is_package = rel in e["packages"]
    internal = "internal" in rel.split("/")
    public = e["visibility"] == "public"
    # breadcrumbs: every prefix that has a page of its own links to it
    parts = package.split("/")
    crumbs = []
    for i in range(len(parts)):
        prefix = "/".join(parts[:i + 1])
        label = esc(parts[i])
        if i == len(parts) - 1:
            crumbs.append(f'<span aria-current="page">{label}</span>')
        elif prefix in pages_of_entry or i == 0:
            crumbs.append(f'<a href="{page_url(prefix)}">{label}</a>')
        else:
            crumbs.append(label)
    kind = "MODULE" if is_root else ("PACKAGE" if is_package else "DIRECTORY")
    eyebrow = f"{kind} · {'PRIVATE MODULE' if not public else (esc(item['kind'] or 'module').upper())}"
    if is_root and item["described"]:
        heading = f"{esc(item['emoji'])} {esc(item['title'])}"
    else:
        heading = esc(parts[-1])
    out = []
    if is_root and item["described"]:
        out.append(f'<p class="tagline">{esc(item["tagline"])}</p>')
        out.append(f'<p class="lead">{esc(item["summary"])}</p>')
    elif not is_root:
        out.append(f'<p class="lead">{"A package" if is_package else "A directory"} of the module '
                   f'<a href="{page_url(module)}"><code>{esc(module)}</code></a>'
                   f'{" (" + esc(item["title"]) + ")" if item["described"] else ""}.</p>')
    importable = item["kind"] in (None, "library") or not is_root
    if is_root and item["command"]:
        out.append(f'<div class="command"><span aria-hidden="true">$&nbsp;</span>{esc(item["command"])}</div>')
    elif is_package and importable and not internal and "cmd" not in rel.split("/"):
        out.append(f'<div class="command"><span aria-hidden="true">$&nbsp;</span>go get {esc(package)}</div>')
    if internal:
        out.append('<p class="note">An <code>internal</code> package: only the code of its own module may '
                   'import it.</p>')
    if not public:
        out.append('<p class="note">A private module: <code>go get</code> works for those with access to its '
                   f'repository, with <code>GOPRIVATE={esc(module)}</code> and git credentials for GitHub.</p>')
    links = []
    if public and is_package:
        links.append(f'<li><a href="{DOCS_URL}{esc(package)}">Documentation on pkg.go.dev</a></li>')
    tree = f"{e['repository']}/tree/{e['branch']}{rel}"
    links.append(f'<li><a href="{esc(tree)}">Source on GitHub</a></li>')
    if item["site"]:
        links.append(f'<li><a href="{esc(item["site"])}">Project site</a></li>')
    if item["releaseNotes"]:
        links.append(f'<li><a href="{esc(item["releaseNotes"])}">Release notes</a></li>')
    links.append(f'<li><a href="/#{esc(item["anchor"])}">In the catalog</a></li>')
    out.append(f'<ul class="links">{"".join(links)}</ul>')
    if e["version"]:
        version = esc(e["version"])
        if item["published"]:
            version += f" · published {esc(human_date(item['published']))}"
    else:
        version = "not released through the catalog yet: go get takes the latest tag or commit"
    facts = [("Module", f'<a href="{page_url(module)}">{esc(module)}</a>'),
             ("Version", version),
             ("Repository", f'<a href="{esc(e["repository"])}">{esc(item["repo"])}</a> · {esc(e["branch"])}'),
             ("Visibility", esc(e["visibility"]))]
    if not is_root:
        facts.insert(0, ("Import path", esc(package)))
    out.append('<dl class="facts">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts) + "</dl>")
    below = [p for p in e["packages"] if p.startswith(rel + "/") and p != rel]
    if below:
        title = "Packages" if is_root else "Packages below"
        rows = []
        for p in below:
            tag = '<small>internal</small>' if "internal" in p.split("/") else ""
            rows.append(f'<li><a href="{page_url(module + p)}">{esc(p[len(rel) + 1:])}</a>{tag}</li>')
        out.append(f'<h2>{title} <small>({len(below)})</small></h2><ul class="dirs">{"".join(rows)}</ul>')
    out.append('<details><summary>This page also answers the go command</summary>'
               '<p>The same address serves you and <code>go get</code>: the go command asks for '
               f'<code>{esc(package)}?go-get=1</code> and reads these tags from the head of this page.</p>'
               f'<pre>{esc(discovery(e))}</pre></details>')
    description = (f"{item['tagline']} {package} on go.octolab.org." if is_root and item["described"]
                   else f"{package}: a Go {'package' if is_package else 'directory'} of {module} on go.octolab.org.")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{discovery(e)}<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(package)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="https://{HOST}{page_url(package)}">
<link rel="icon" href="/icon.svg">
<link rel="stylesheet" href="/{PAGE_CSS}">
</head>
<body>
<header class="bar"><a class="wordmark" href="/"><span aria-hidden="true">🤴</span>go.octolab.org</a>
<nav aria-label="Site"><a href="/">Catalog</a><a href="https://github.com/octolab/vanity">GitHub</a></nav></header>
<main class="wrap">
<nav class="crumbs" aria-label="Breadcrumb">{" / ".join(crumbs)}</nav>
<p class="eyebrow">{eyebrow}</p>
<h1>{heading}</h1>
{chr(10).join(out)}
</main>
<footer><span>The Go modules of OctoLab at <a href="/">go.octolab.org</a> · <a href="/modules.yml">modules.yml</a></span>
<span>made with ❤️ for everyone by <a href="https://www.octolab.org/">OctoLab</a></span></footer>
</body>
</html>
"""


def pages(entries, items=None):
    """(package, html) for every page of the site, in the order they are written.

    A page per published package and per directory between a package and the
    root of its module, so that every prefix of an import path resolves. S5
    keeps the pages of two entries apart. items: the modules as site_data()
    describes them; without them, every module is shown from its entry alone.
    """
    items = items or {}
    for e in sorted(entries, key=lambda e: e["module"]):
        item = items.get(e["module"]) or describe(e, None, {})
        own = rendered(e)
        for package in sorted(own):
            yield package, package_page(package, e, item, own)


def page_file(directory, package):
    return Path(directory, *package.removeprefix(HOST).split("/"), "index.html")


def render(entries, directory, items=None):
    """Write the pages of the site and modules.yml into an empty directory; the page count."""
    count = 0
    for package, page in pages(entries, items):
        target = page_file(directory, package)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding="utf-8")
        count += 1
    Path(directory, "modules.yml").write_text(manifest(entries), encoding="utf-8")
    css = Path(directory, PAGE_CSS)
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text(STYLE.lstrip(), encoding="utf-8")
    return count


# Next.js writes these next to the page; Pages answers a missing path with
# 404.html, and 404/ would read as an import page of go.octolab.org/404
SITE_DROPPED = ("404", "index.html")


def compose(entries, work, site):
    """Lay the catalog page (a static export in site/) over the import pages in work.

    The root module's page becomes the catalog: its own discovery tags are put
    first in the head of the exported index.html. Every other file of the export
    is copied as it is, and none of them may take the place of an import page
    or of modules.yml.
    """
    site = Path(site)
    index = site / "index.html"
    if not index.is_file():
        raise ValueError(f"{site} has no index.html; build the catalog page first: ./Taskfile docs build")
    root = next((e for e in entries if e["module"] == HOST), None)
    page = index.read_text(encoding="utf-8")
    head = re.search(r"<head(\s[^>]*)?>", page)
    if root is None or head is None:
        raise ValueError(f"{index}: no <head> to put the discovery tags of {HOST} in")
    taken = {page_file(work, p).relative_to(work).as_posix() for e in entries for p in rendered(e)}
    taken.update(("modules.yml", PAGE_CSS))
    for item in sorted(site.rglob("*")):
        rel = item.relative_to(site).as_posix()
        if item.is_symlink():
            raise ValueError(f"{site}/{rel}: symbolic links are not allowed in the site")
        if rel.split("/")[0] in SITE_DROPPED or item.is_dir():
            continue
        if rel in taken:
            raise ValueError(f"{site}/{rel} would replace the import page or manifest at /{rel}")
        target = work / rel
        if target.is_dir() or any(parent.is_file() for parent in target.parents if parent != work):
            raise ValueError(f"{site}/{rel} collides with an import page at /{rel}; "
                             f"add {rel.split('/')[0]} to RESERVED in bin/catalog.py")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item, target)
    # no text between the tags: React hydrates the head and would see it
    page = page[:head.end()] + discovery(root).replace("\n", "") + page[head.end():]
    page_file(work, HOST).write_text(page, encoding="utf-8")


def build(entries, directory, root=None, site=None):
    """Render the site next to directory, verify it, then put it in its place.

    root: the catalog checkout with docs/catalog.json (cards); site: a static
    export of the catalog page that becomes the page of the root module.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import verify  # the independent check of the pages; it imports this file

    items = None
    if root is not None:
        cards, errors = read_cards(root)
        problems, warnings = check_cards(entries, cards)
        errors += problems
        if errors:
            raise ValueError("\n".join(errors))
        report(warnings, warning=True)
        items = {i["module"]: i for i in all_items(site_data(root, entries, cards))}
    target = Path(directory).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".dist.", dir=target.parent))
    try:
        print(f"Rendered {render(entries, work, items)} pages of {len(entries)} modules")
        if site is not None:
            compose(entries, work, site)
            print(f"Laid the catalog page of {site} over /")
        verify.local(work, {e["module"]: e for e in entries}, catalog_page=site is not None)
        shutil.rmtree(target, ignore_errors=True)
        work.rename(target)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def all_items(data):
    """Every module of site_data(), once."""
    seen = {}
    for group in data["groups"]:
        for i in group["items"]:
            seen[i["module"]] = i
    for i in data["unlisted"] + data["private"]:
        seen[i["module"]] = i
    if data["root"]:
        seen.setdefault(data["root"]["module"], data["root"])
    return list(seen.values())


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


def report(errors, warning=False):
    """Print errors (or warnings); on GitHub Actions as escaped ::error:: (::warning::) commands."""
    actions = os.environ.get("GITHUB_ACTIONS") == "true"
    for error in errors:
        if actions:
            error = error.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::{'warning' if warning else 'error'}::{error}", file=sys.stderr)
        else:
            print(f"warning: {error}" if warning else error, file=sys.stderr)


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
    b.add_argument("--site", type=Path, metavar="EXPORT",
                   help="the static export of the catalog page (docs/dist) to lay over /")
    sub.add_parser("cards", help=f"check {CARDS} against the entries; warn about modules without a card")
    sub.add_parser("site", help="print what the catalog page shows, as JSON (docs/catalog.mjs reads it)")
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

    if args.command in ("manifest", "build", "cards", "site"):
        entries, errors = load(args.root)
        errors += invariants(entries)
        if args.command in ("cards", "site"):
            cards, problems = read_cards(args.root)
            errors += problems
            problems, warnings = check_cards(entries, cards) if not errors else ([], [])
            errors += problems
        if errors:
            report(errors)
            raise SystemExit(1)
        if args.command == "build":
            try:
                build(entries, args.directory, args.root, args.site)
            except ValueError as error:
                report(str(error).splitlines())
                raise SystemExit(1)
        elif args.command == "cards":
            report(warnings, warning=True)
            described = sum(1 for c in cards["items"] if c["module"] in {e["module"] for e in entries})
            print(f"Checked {len(cards['items'])} cards in {len(cards['groups'])} groups: "
                  f"{described} of {len(entries)} modules described, {len(warnings)} warnings")
        elif args.command == "site":
            json.dump(site_data(args.root, entries, cards), sys.stdout, indent=1, ensure_ascii=False)
            sys.stdout.write("\n")
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
