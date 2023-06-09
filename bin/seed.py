#!/usr/bin/env python3
"""Seed modules/*.json once from the submodules of a past revision.

One-off migration from git submodules to entries (issue 500). For every
section of .gitmodules at REV it takes the gitlink commit pinned at REV, reads
the tree of that commit through git (never an archive: export-ignore would drop
files such as *_test.go), reads the repository's default branch, topics and
visibility with gh, and writes the entry printed by octomation/vanity-action's
own `entry` command for that tree (version null), so a seeded entry is byte for
byte what a release of the same commit would write. Nothing is pushed or
committed.

Objects come from the local submodule store .git/modules/<path> when it has
the commit, otherwise from a temporary bare repository that fetches only that
commit from the submodule URL.

Usage: python3 bin/seed.py --action DIR [--rev REV] [--only MODULE ...] [--names FILE]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GO_ENV = {
    "GOWORK": "off",
    "GOENV": "off",
    "GOFLAGS": "",
    "GOTOOLCHAIN": "local",
    "GOPROXY": "off",
    "GOPRIVATE": "",
    "GONOSUMDB": "",
    "GOINSECURE": "",
    "CGO_ENABLED": "0",
}

# Catalog tag names (<name>--vX.Y.Z), as the integrations pass them to the
# action. The default is the repository name (octolab/pkg is pkg); these
# modules get an explicit one because their repository name collides with
# another module's (service, tablo) or the project is renamed (octomation/tablo
# becomes pulse; its module path stays).
NAMES = {
    "go.octolab.org/ecosystem/sparkle": "sparkle",
    "go.octolab.org/ecosystem/tablo": "ecosystem/tablo",
    "go.octolab.org/ecosystem/tact": "tact",
    "go.octolab.org/toolset/tablo": "pulse",
}


def run(*args, cwd=None, env=None, input=None):
    result = subprocess.run(
        args, cwd=cwd, env=env, input=input, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise SystemExit(
            f"{' '.join(args)}: exit {result.returncode}\n{result.stderr.strip()}"
        )
    return result.stdout


def submodules(rev):
    blob = f"{rev}:.gitmodules"
    lines = run("git", "-C", str(ROOT), "config", "--blob", blob, "--get-regexp", r"^submodule\.")
    sections = {}
    for line in lines.splitlines():
        key, _, value = line.partition(" ")
        section, _, field = key[len("submodule."):].rpartition(".")
        sections.setdefault(section, {})[field] = value
    result = []
    for section, fields in sorted(sections.items()):
        path, url, name = fields["path"], fields["url"], fields["name"]
        tree = run("git", "-C", str(ROOT), "ls-tree", rev, "--", path).split()
        if len(tree) != 4 or tree[0] != "160000" or tree[1] != "commit":
            raise SystemExit(f"{path}: no gitlink at {rev}")
        result.append({"module": name, "path": path, "url": url, "commit": tree[2]})
    return result


def slug(url):
    for prefix in ("git@github.com:", "https://github.com/"):
        if url.startswith(prefix):
            return url[len(prefix):].removesuffix(".git")
    raise SystemExit(f"Not a GitHub URL: {url}")


def materialize(sub, workdir):
    """Check the tracked files of the pinned commit out into workdir/tree."""
    commit = sub["commit"]
    gitdir = ROOT / ".git" / "modules" / sub["path"]
    has = gitdir.is_dir() and subprocess.run(
        ["git", "--git-dir", str(gitdir), "cat-file", "-e", f"{commit}^{{commit}}"],
        capture_output=True,
    ).returncode == 0
    if not has:
        gitdir = workdir / "repo.git"
        run("git", "init", "--quiet", "--bare", str(gitdir))
        run("git", "--git-dir", str(gitdir), "fetch", "--quiet", "--depth=1", "--no-tags", sub["url"], commit)
    tree = workdir / "tree"
    env = dict(os.environ, GIT_INDEX_FILE=str(workdir / "index"))
    run("git", "--git-dir", str(gitdir), "read-tree", commit, env=env)
    run("git", "--git-dir", str(gitdir), "checkout-index", "--all", f"--prefix={tree}/", env=env)
    return tree


def topics_flag(topics):
    # an empty value would read as a missing flag; "," lists no topic
    return ",".join(topics) or ","


def metadata(repository):
    raw = run(
        "gh", "repo", "view", repository, "--json",
        "defaultBranchRef,repositoryTopics,visibility",
    )
    data = json.loads(raw)
    topics = [t["name"] for t in (data.get("repositoryTopics") or [])]
    return {
        "branch": data["defaultBranchRef"]["name"],
        "visibility": data["visibility"].lower(),
        "topics": sorted(set(topics)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--action", type=Path, required=True,
                        help="checkout of octomation/vanity-action whose entry command writes the entries")
    parser.add_argument("--rev", default="HEAD", help="revision that still has .gitmodules and the gitlinks")
    parser.add_argument("--only", action="append", help="seed only this module (repeatable)")
    parser.add_argument("--names", type=Path, help="also write the chosen catalog names as TSV here")
    args = parser.parse_args()

    rev = run("git", "-C", str(ROOT), "rev-parse", "--verify", f"{args.rev}^{{commit}}").strip()
    subs = submodules(rev)
    if args.only:
        unknown = set(args.only) - {s["module"] for s in subs}
        if unknown:
            parser.error(f"not in .gitmodules at {rev}: {', '.join(sorted(unknown))}")
        subs = [s for s in subs if s["module"] in args.only]

    with tempfile.TemporaryDirectory(prefix="vanity-seed.") as tmp:
        tmp = Path(tmp)
        cli = args.action.resolve() / "bin" / "vanity-action.mjs"
        if not cli.is_file():
            parser.error(f"{cli}: not a vanity-action checkout")
        names = []
        for sub in subs:
            work = tmp / "work"
            work.mkdir()
            repository = slug(sub["url"])
            meta = metadata(repository)
            flags = ["--packages", "all", "--repository", repository, "--branch", meta["branch"],
                     "--visibility", meta["visibility"], "--topics", topics_flag(meta["topics"]),
                     "--commit", sub["commit"]]
            if sub["module"] in NAMES:
                flags += ["--name", NAMES[sub["module"]]]
            try:
                tree = materialize(sub, work)
                printed = run("node", str(cli), "entry", "--path", str(tree), *flags,
                              env=dict(os.environ, **GO_ENV))
            finally:
                shutil.rmtree(work)
            value, problems = catalog.parse(printed.encode("ascii"), catalog.entry_path(sub["module"]))
            if problems:
                raise SystemExit("\n".join(problems))
            catalog.write_entry(ROOT, value)
            name = value["name"]
            names.append((sub["module"], name, repository, "explicit" if sub["module"] in NAMES else "repository name"))
            print(f"{sub['module']}: {len(value['packages'])} packages, name {name}", file=sys.stderr)

    if args.names:
        with args.names.open("w") as out:
            out.write("module\tname\trepository\tsource\n")
            for row in sorted(names):
                out.write("\t".join(row) + "\n")
    errors = catalog.check(ROOT)
    if errors:
        raise SystemExit("\n".join(errors))


if __name__ == "__main__":
    main()
