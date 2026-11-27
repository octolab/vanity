#!/usr/bin/env python3
"""GitHub Pages of go.octolab.org: the settings, the deployed site, a doctor.

  settings            the Pages configuration on GitHub (source, custom domain,
                      Enforce HTTPS) against .github/settings.json; needs gh.
  smoke [SITE]        the deployed catalog page (default https://go.octolab.org/):
                      its assets, og:image and icon, a card per module at the
                      version of the catalog, the site's own 404, the shared
                      stylesheet of the package pages, http:// redirecting to
                      https:// permanently (the page and ?go-get=1 alike) and
                      the default domain redirecting to the custom one.
                      --retries N tries again every 15 s while Pages still
                      serves the previous deployment.
  doctor              settings, workflows and the live site, with what to do.

The go command's side of the site (go-import and go-source of every page) is
bin/verify.py --url. The standard library only; settings and doctor ask
GitHub with the gh command.
"""

import argparse
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import verify  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ".github/settings.json"
REPOSITORY = "octolab/vanity"


def settings(root=ROOT):
    data = json.loads(Path(root, SETTINGS).read_text(encoding="utf-8"))
    return data.get("pages") or {}, data.get("workflows") or {}


def gh(*args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or f"gh {' '.join(args)} failed")
    return result.stdout


def settings_errors(actual, want, slug=REPOSITORY):
    """The Pages configuration on GitHub against what settings.json declares."""
    where = f"https://github.com/{slug}/settings/pages"
    errors = []
    if actual.get("build_type") != want.get("build_type", "workflow"):
        errors.append(f"Pages builds from {actual.get('build_type')}; set Settings → Pages → Source: "
                      f"GitHub Actions ({where})")
    if (actual.get("cname") or None) != (want.get("cname") or None):
        errors.append(f"Pages domain is {actual.get('cname') or 'the default one'}, {SETTINGS} says "
                      f"{want.get('cname') or 'the default one'}; align them ({where})")
    if "https_enforced" in want and "https_enforced" not in actual:
        print(f"::warning::the Pages answer has no https_enforced; check Enforce HTTPS by hand ({where})",
              file=sys.stderr)
    elif "https_enforced" in want and bool(actual.get("https_enforced")) != want["https_enforced"]:
        errors.append(f"Enforce HTTPS is {'on' if actual.get('https_enforced') else 'off'}, {SETTINGS} wants "
                      f"{'on' if want['https_enforced'] else 'off'}; toggle it ({where}) or: gh api -X PUT "
                      f"repos/{slug}/pages -F https_enforced={str(want['https_enforced']).lower()}")
    certificate = (actual.get("https_certificate") or {}).get("state")
    if want.get("https_enforced") and certificate not in (None, "approved"):
        errors.append(f"the certificate of {actual.get('cname')} is {certificate}, not approved yet")
    return errors


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = build_opener(NoRedirect)


def probe(url, method="GET"):
    """(status, content type, location, text) without following redirects."""
    request = Request(url, method=method, headers={"User-Agent": "vanity-pages-check"})
    try:
        with OPENER.open(request, timeout=20) as response:
            body = response.read().decode("utf-8", "replace") if method == "GET" else ""
            return response.status, response.headers.get("Content-Type", ""), None, body
    except HTTPError as error:
        body = error.read().decode("utf-8", "replace") if method == "GET" else ""
        return error.code, error.headers.get("Content-Type", ""), error.headers.get("Location"), body
    except (URLError, OSError) as error:
        return 0, "", None, str(getattr(error, "reason", error))


def card_errors(page, items, site):
    """Every module has its card (data-module) on the page; a released one shows its version."""
    errors = []
    for item in items:
        marker = f'data-module="{html.escape(item["module"])}"'
        start = page.find(marker)
        if start < 0:
            errors.append(f"{site}: {item['module']} has no card on the page")
            continue
        end = min([i for i in (page.find("</article>", start), page.find("</li>", start)) if i >= 0] or [len(page)])
        card = page[start:end]
        # a private module is listed by its path only
        if item["visibility"] == "public" and item["version"] and f">{item['version']}<" not in card:
            errors.append(f"{site}: {item['module']} is not shown at {item['version']}; "
                          "the page is older than the catalog, rebuild it")
    return errors


def smoke_once(site, items, pages, missing="vanity-smoke-missing-page"):
    errors = []
    status, kind, _, page = probe(site)
    if status != 200 or "text/html" not in kind:
        return [f"{site}: HTTP {status}, want the catalog page"]
    assets = sorted(set(re.findall(r'(?:href|src)="(/_next/static/[^"]+\.(?:css|js))"', page)))
    if not assets:
        errors.append(f"{site}: no /_next/static assets referenced")
    for asset in [next((a for a in assets if a.endswith(ext)), None) for ext in (".css", ".js")]:
        if asset and probe(urljoin(site, asset), "HEAD")[0] != 200:
            errors.append(f"{urljoin(site, asset)}: missing; the page was built for another base path")
    # a local build is made for the custom domain: its links point there
    origin = f"https://{pages['cname']}/" if pages.get("cname") and site.startswith("http://") else site
    og = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', page)
    if not og:
        errors.append(f"{site}: no og:image")
    elif not og.group(1).startswith(origin):
        errors.append(f"og:image {og.group(1)} is outside {origin}; SITE_URL was wrong, rebuild the site")
    else:
        status, kind, _, _ = probe(urljoin(site, og.group(1)[len(origin):]), "HEAD")
        if status != 200 or not kind.startswith("image/"):
            errors.append(f"{og.group(1)}: HTTP {status} {kind}, want an image")
    for path in ("icon.svg", catalog.PAGE_CSS, "modules.yml"):
        if probe(urljoin(site, path), "HEAD")[0] != 200:
            errors.append(f"{urljoin(site, path)}: missing")
    errors += card_errors(page, items, site)
    status, _, _, text = probe(urljoin(site, f"{missing}/"))
    if status != 404 or "/_next/static/" not in text:
        errors.append(f"{site}{missing}/: HTTP {status}, want the site's own 404")
    # from outside only: the custom domain, Enforce HTTPS and the default domain
    if pages.get("cname") and pages.get("https_enforced") and site == f"https://{pages['cname']}/":
        for path in ("", "toolset/indexit?go-get=1"):
            plain, secure = f"http://{pages['cname']}/{path}", f"https://{pages['cname']}/{path}"
            status, _, location, _ = probe(plain)
            if status not in (301, 308) or location != secure:
                errors.append(f"{plain}: HTTP {status} to {location}, want a permanent redirect to {secure}; "
                              "turn on Enforce HTTPS")
        owner, name = REPOSITORY.split("/")
        fallback = f"https://{owner}.github.io/{name}/"
        status, _, location, _ = probe(fallback)
        if status not in (301, 302, 308) or not (location or "").startswith(site):
            errors.append(f"{fallback}: HTTP {status} to {location}, want a redirect to {site}")
    return errors


def smoke(site, retries=0, root=ROOT):
    site = site.rstrip("/") + "/"
    entries, problems = catalog.load(root)
    cards, more = catalog.read_cards(root)
    if problems or more:
        return problems + more
    items = catalog.all_items(catalog.site_data(root, entries, cards))
    pages, _ = settings(root)
    # a path no entry publishes, nor a parent of one
    missing = verify.probe({e["module"]: e for e in entries})[len(catalog.HOST) + 1:]
    errors = []
    for attempt in range(retries + 1):
        errors = smoke_once(site, items, pages, missing)
        if not errors or attempt == retries:
            break
        print(f"Attempt {attempt + 1}/{retries + 1}: {len(errors)} problems; retrying in 15s", file=sys.stderr)
        time.sleep(15)
    return errors


def doctor(root=ROOT):
    report = []
    want, declared = settings(root)
    try:
        workflows = json.loads(gh("api", f"repos/{REPOSITORY}/actions/workflows", "--paginate", "--slurp"))
        for workflow in (w for page in workflows for w in page["workflows"]):
            if not workflow["path"].startswith(".github/workflows/"):
                continue
            file = workflow["path"].rsplit("/", 1)[-1]
            state = (declared.get(file) or {}).get("state", "active")
            ok = workflow["state"] == state or (state == "disabled" and workflow["state"].startswith("disabled"))
            report.append(("ok" if ok else "fail",
                           f"{workflow['name']} is {workflow['state']}" if ok else
                           f"{workflow['name']} is {workflow['state']}, want {state}: "
                           f"gh workflow {'enable' if state == 'active' else 'disable'} {file} -R {REPOSITORY}"))
    except (RuntimeError, ValueError, KeyError) as error:
        report.append(("fail", f"workflows are not readable: {error}"))
    try:
        actual = json.loads(gh("api", f"repos/{REPOSITORY}/pages"))
        errors = settings_errors(actual, want)
        report += [("fail", e) for e in errors]
        if not errors:
            report.append(("ok", f"Pages publishes {actual.get('html_url')} from GitHub Actions, HTTPS enforced, "
                                 f"certificate {(actual.get('https_certificate') or {}).get('state')} until "
                                 f"{(actual.get('https_certificate') or {}).get('expires_at')}"))
    except (RuntimeError, ValueError) as error:
        report.append(("fail", f"Pages is not readable: {error}"))
    site = f"https://{want.get('cname')}/" if want.get("cname") else None
    if site:
        errors = smoke(site, root=root)
        report += [("fail", f"site: {e}") for e in errors]
        if not errors:
            report.append(("ok", f"{site} serves the catalog page, its assets, every card at its version, "
                                 "its 404 and redirects http:// to https://"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="catalog checkout")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("settings", help=f"the Pages configuration on GitHub against {SETTINGS}")
    s = sub.add_parser("smoke", help="the deployed site")
    s.add_argument("site", nargs="?")
    s.add_argument("--retries", type=int, default=0)
    sub.add_parser("doctor", help="settings, workflows and the live site")
    args = parser.parse_args()
    want, _ = settings(args.root)
    if args.command == "settings":
        try:
            errors = settings_errors(json.loads(gh("api", f"repos/{REPOSITORY}/pages")), want)
        except (RuntimeError, ValueError) as error:
            errors = [f"cannot read the Pages configuration: {error}"]
        catalog.report(errors)
        if errors:
            raise SystemExit(1)
        print(f"Pages of {REPOSITORY} match {SETTINGS}: {want}")
    elif args.command == "smoke":
        site = args.site or f"https://{want['cname']}/"
        if not site.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            parser.error("the site must be an https:// URL (or a local one)")
        errors = smoke(site, args.retries, args.root)
        catalog.report(errors)
        if errors:
            raise SystemExit(1)
        print(f"{site} serves the catalog page and its assets")
    else:
        report = doctor(args.root)
        for status, message in report:
            print(f"{status:<5} {message}")
        if any(status == "fail" for status, _ in report):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
