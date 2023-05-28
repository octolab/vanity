#!/usr/bin/env python3
"""Check vanity discovery against .gitmodules, locally or over verified HTTPS."""

import argparse
import configparser
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen

HOST = "go.octolab.org"
ROOT = Path(__file__).resolve().parent.parent


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.imports = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "go-import":
            self.imports.append(attrs.get("content", "").split())


def repositories():
    config = configparser.ConfigParser(interpolation=None)
    config.read(ROOT / ".gitmodules")
    result = {}
    for section in config.values():
        if "name" not in section:
            continue
        prefix = section["name"]
        if prefix != HOST and not prefix.startswith(HOST + "/"):
            raise ValueError(f"Unexpected vanity prefix: {prefix}")
        if prefix in result:
            raise ValueError(f"Duplicate vanity prefix: {prefix}")
        result[prefix] = section["url"].replace(
            "git@github.com:", "https://github.com/", 1
        ).removesuffix(".git")
    if HOST not in result:
        raise ValueError("The root module is missing from .gitmodules")
    return result


def verify(html, package, repos):
    prefix = max(
        (p for p in repos if package == p or package.startswith(p + "/")),
        key=len,
    )
    expected = [[prefix, "git", repos[prefix]]]
    metadata = Metadata()
    metadata.feed(html)
    if metadata.imports != expected:
        raise ValueError(f"{package}: expected {expected}, got {metadata.imports}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=ROOT / "dist")
    parser.add_argument("--url", help="Check all module roots on this HTTPS site")
    parser.add_argument("--module", action="append", help="Limit HTTPS checks to this module (repeatable)")
    args = parser.parse_args()
    repos = repositories()
    if args.module and not args.url:
        parser.error("--module requires --url")
    if args.url:
        if not args.url.startswith("https://"):
            parser.error("--url must use HTTPS")
        prefixes = sorted(set(args.module or repos))
        for prefix in prefixes:
            if prefix not in repos:
                parser.error(f"Unknown module: {prefix}")
            url = args.url.rstrip("/") + "/" + prefix[len(HOST):].lstrip("/")
            with urlopen(url + "?go-get=1", timeout=30) as response:
                if not response.url.startswith("https://"):
                    raise ValueError(f"Redirected to insecure URL: {response.url}")
                verify(response.read().decode(), prefix, repos)
        print(f"Verified HTTPS discovery for {len(prefixes)} modules")
        return

    for prefix in repos:
        page = args.directory / prefix[len(HOST):].lstrip("/") / "index.html"
        verify(page.read_text(), prefix, repos)
    pages = sorted(args.directory.rglob("index.html"))
    for page in pages:
        relative = page.parent.relative_to(args.directory).as_posix()
        package = HOST if relative == "." else HOST + "/" + relative
        verify(page.read_text(), package, repos)
    print(f"Verified {len(repos)} module roots and {len(pages)} package pages")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
