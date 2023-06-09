#!/usr/bin/env python3
"""Check vanity discovery against the entries in modules/, locally or over HTTPS.

For every page: go-import names the module and its repository, go-source its
repository and default branch, and the refresh and the link lead to the
package on pkg.go.dev. Locally, every published package has a page and no page
is outside the declared packages of its module (Maintainer also writes the
parent directories of packages inside a module). With --url, the module roots
(or, with --packages, every published package and the served modules.yml, which
must equal the manifest of the entries) are fetched over verified HTTPS, and a
path outside the catalog must answer 404.
"""

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402

HOST = catalog.HOST
ROOT = Path(__file__).resolve().parent.parent


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("name") or attrs.get("http-equiv")
            if key in ("go-import", "go-source", "refresh"):
                self.meta.setdefault(key, []).append(attrs.get("content", ""))
        elif tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])


def owner(package, modules):
    """The module whose prefix is the longest one of package, or None."""
    candidates = [m for m in modules if package == m or package.startswith(m + "/")]
    return max(candidates, key=len) if candidates else None


def pages_of(modules):
    """Every page the catalog renders and the module it belongs to.

    A published package belongs to the entry that declares it; Maintainer also
    renders the parent directories of a package inside its module, which belong
    to that module unless another entry declares them.
    """
    pages = {e["module"] + p: m for m, e in modules.items() for p in e["packages"]}
    for package, module in list(pages.items()):
        parent = package
        while parent != module:
            parent = parent.rsplit("/", 1)[0]
            pages.setdefault(parent, module)
    return pages


def expected(package, e):
    url, branch, module = e["repository"], e["branch"], e["module"]
    docs = f"https://pkg.go.dev/{package}"
    return {
        "go-import": [f"{module} git {url}"],
        "go-source": [
            f"{module} {url} {url}/tree/{branch}{{/dir}} {url}/blob/{branch}{{/dir}}/{{file}}#L{{line}}"
        ],
        "refresh": [f"0; url={docs}"],
        "links": [docs],
    }


def verify(html, package, modules, pages=None):
    module = (pages or {}).get(package) or owner(package, modules)
    if module is None:
        raise ValueError(f"{package}: no module in the catalog serves it")
    want = expected(package, modules[module])
    page = Metadata()
    page.feed(html)
    got = {key: page.meta.get(key, []) for key in ("go-import", "go-source", "refresh")}
    got["links"] = page.links
    for key in want:
        if got[key] != want[key]:
            raise ValueError(f"{package}: {key}: expected {want[key]}, got {got[key]}")


def entries(root):
    found, errors = catalog.load(root)
    errors += catalog.invariants(found)
    if errors:
        raise ValueError("\n".join(errors))
    return {e["module"]: e for e in found}


def local(directory, modules):
    published = {e["module"] + p for e in modules.values() for p in e["packages"]}
    rendered = pages_of(modules)
    allowed = set(rendered)
    pages = {}
    for page in sorted(directory.rglob("index.html")):
        relative = page.parent.relative_to(directory).as_posix()
        pages[HOST if relative == "." else HOST + "/" + relative] = page
    missing = sorted(published - set(pages))
    if missing:
        raise ValueError(f"Packages without a page: {', '.join(missing[:10])}")
    extra = sorted(set(pages) - allowed)
    if extra:
        raise ValueError(f"Pages outside the catalog: {', '.join(extra[:10])}")
    for package, page in pages.items():
        verify(page.read_text(), package, modules, rendered)
    print(f"Verified {len(modules)} module roots, {len(published)} packages and {len(pages)} pages")


def fetch(url):
    with urlopen(url, timeout=30) as response:
        if not response.url.startswith("https://"):
            raise ValueError(f"Redirected to insecure URL: {response.url}")
        return response.read().decode()


def probe(modules):
    """A path under the root module that no entry publishes, nor a parent of one."""
    taken = {e["module"] + p for e in modules.values() for p in e["packages"]}
    n = 0
    while True:
        path = f"{HOST}/vanity-probe-of-a-missing-package-{n}"
        if not any(t == path or t.startswith(path + "/") for t in taken):
            return path
        n += 1


def previous_entries(root, rev):
    """The entries of the catalog at rev ({} before the catalog had entries)."""
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "-z", "--name-only", rev, "--", "modules/"],
        capture_output=True, check=True).stdout
    found = {}
    for path in (p.decode() for p in listing.split(b"\0") if p):
        value, problems = catalog.parse(catalog.git_show(root, rev, path) or b"", path)
        if problems:
            raise ValueError(f"{rev}: {'; '.join(problems)}")
        found[value["module"]] = value
    return found


def gone(url):
    """Raise unless url answers 404."""
    try:
        fetch(url)
    except HTTPError as error:
        if error.code != 404:
            raise ValueError(f"{url}: expected 404, got {error.code}") from error
    else:
        raise ValueError(f"{url}: expected 404, got a page")


def remote(base, targets, modules, manifest=False, removed=()):
    base = base.rstrip("/")
    pages = pages_of(modules)
    if manifest:
        # the deployed build is this one: its manifest is byte-equal
        served = fetch(f"{base}/modules.yml")
        if served != catalog.manifest(sorted(modules.values(), key=lambda e: e["module"])):
            raise ValueError(f"{base}/modules.yml differs from the manifest of the entries")

    def one(package):
        url = f"{base}/{package[len(HOST):].lstrip('/')}?go-get=1"
        try:
            html = fetch(url)
        except HTTPError as error:
            raise ValueError(f"{package}: {url} answered {error.code}") from error
        verify(html, package, modules, pages)

    def url(package):
        return f"{base}/{package[len(HOST):].lstrip('/')}?go-get=1"

    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(one, package) for package in targets]
        # pages of the previous deployment that this one no longer renders
        futures += [pool.submit(gone, url(package)) for package in removed]
        futures.append(pool.submit(gone, url(probe(modules))))
        for future in futures:
            future.result()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", nargs="?", type=Path, default=ROOT / "dist")
    parser.add_argument("--root", type=Path, default=ROOT, help="catalog checkout with modules/")
    parser.add_argument("--url", help="check the live site at this HTTPS URL instead of a directory")
    parser.add_argument("--module", action="append", help="limit --url checks to this module (repeatable)")
    parser.add_argument("--packages", action="store_true", help="with --url, check every published package")
    parser.add_argument("--previous", metavar="REV",
                        help="with --url --packages, require 404 for pages the catalog at REV rendered and this one does not")
    parser.add_argument("--attempts", type=int, default=1, help="with --url, tries before failing")
    parser.add_argument("--delay", type=int, default=30, help="with --url, seconds between tries")
    args = parser.parse_args()
    if (args.module or args.packages or args.attempts != 1) and not args.url:
        parser.error("--module, --packages and --attempts require --url")
    if args.previous and (not args.packages or args.module):
        parser.error("--previous requires --packages and no --module")
    if args.attempts < 1 or args.delay < 0:
        parser.error("--attempts must be at least 1 and --delay not negative")
    if not args.url:
        local(args.directory, entries(args.root))
        return
    if not args.url.startswith("https://"):
        parser.error("--url must use HTTPS")
    modules = entries(args.root)
    for module in args.module or []:
        if module not in modules:
            parser.error(f"Unknown module: {module}")
    selected = sorted(set(args.module or modules))
    if args.packages:
        targets = sorted(m + p for m in selected for p in modules[m]["packages"])
    else:
        targets = selected
    removed = []
    if args.previous:
        removed = sorted(set(pages_of(previous_entries(args.root, args.previous))) - set(pages_of(modules)))
        print(f"{len(removed)} pages of {args.previous[:12]} must be gone")
    for attempt in range(1, args.attempts + 1):
        try:
            remote(args.url, targets, modules, manifest=args.packages and not args.module, removed=removed)
            break
        except (OSError, ValueError) as error:
            if attempt == args.attempts:
                raise
            print(f"Attempt {attempt}/{args.attempts}: {error}; retrying in {args.delay}s", file=sys.stderr)
            time.sleep(args.delay)
    print(f"Verified HTTPS discovery for {len(targets)} {'packages' if args.packages else 'modules'}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
