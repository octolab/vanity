#!/usr/bin/env python3
"""Serve a build of go.octolab.org locally, the way GitHub Pages serves it.

  bin/serve.py [DIR] [--port N]          serve DIR (default dist/) at http://127.0.0.1:N/
  bin/serve.py [DIR] --go -- ARGS...     run `go ARGS...` against DIR instead of the live site

As Pages does, a directory without its trailing slash answers a 301 to the
path with it (the query kept), a directory answers its index.html, and a
missing path answers 404 with the site's 404.html.

The same server is also the go command's proxy. With --go, go runs in a fresh
GOPATH with GOPROXY=direct and GOINSECURE for go.octolab.org, and this server
as its HTTP and HTTPS proxy: it refuses HTTPS to go.octolab.org, so go falls
back to plain HTTP, asks this server and reads this build's go-import and
go-source tags. Every other host is tunnelled untouched (TLS end to end), and
GitHub and sum.golang.org are reached directly: go clones the repository
itself and checks the checksum database. So:

  bin/serve.py dist --go -- mod download -json go.octolab.org@v0.12.2

proves that this build, not the deployed one, still serves `go get`.

The standard library only.
"""

import argparse
import os
import select
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HOST = "go.octolab.org"
ROOT = Path(__file__).resolve().parent.parent
# reached directly by the go command and git, never through this server
DIRECT = "github.com,.github.com,.githubusercontent.com,sum.golang.org,proxy.golang.org,pkg.go.dev"


def tunnel(client, upstream):
    """Relay bytes both ways until either side closes."""
    sockets = [client, upstream]
    try:
        while True:
            ready, _, broken = select.select(sockets, [], sockets, 60)
            if broken or not ready:
                return
            for source in ready:
                data = source.recv(65536)
                if not data:
                    return
                (upstream if source is client else client).sendall(data)
    except OSError:
        return
    finally:
        upstream.close()


def handler(directory, quiet):
    class Pages(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format, *args):
            if not quiet:
                super().log_message(format, *args)

        def do_CONNECT(self):
            # HTTPS to go.octolab.org is refused, so go falls back to plain HTTP
            # and asks this server; any other host is tunnelled untouched, TLS
            # end to end, so dependencies resolve as they would without it
            host, _, port = self.path.rpartition(":")
            if host.lower() == HOST:
                self.send_error(405, "go.octolab.org is served over plain HTTP by this server")
                return
            try:
                upstream = socket.create_connection((host, int(port or 443)), timeout=30)
            except (OSError, ValueError) as error:
                self.send_error(502, f"cannot reach {self.path}: {error}")
                return
            self.send_response(200, "Connection Established")
            self.end_headers()
            tunnel(self.connection, upstream)
            self.close_connection = True

        def target(self):
            """The path asked for, or None for a proxy request to another host."""
            if self.path.startswith(("http://", "https://")):
                parts = urlsplit(self.path)
                if parts.hostname != HOST:
                    return None
                return parts.path or "/", parts.query
            parts = urlsplit(self.path)
            return parts.path or "/", parts.query

        def not_found(self):
            body = b"404 page not found\n"
            page = Path(self.directory, "404.html")
            if page.is_file():
                body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def route(self):
            found = self.target()
            if found is None:
                self.send_error(502, "this server proxies go.octolab.org only")
                return False
            path, query = found
            local = Path(self.directory, *[p for p in path.split("/") if p])
            if ".." in path.split("/"):
                self.not_found()
                return False
            if local.is_dir() and not path.endswith("/"):
                if not (local / "index.html").is_file():
                    self.not_found()
                    return False
                self.send_response(301)
                self.send_header("Location", path + "/" + (f"?{query}" if query else ""))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return False
            if local.is_dir():
                local = local / "index.html"
            if not local.is_file():
                self.not_found()
                return False
            # SimpleHTTPRequestHandler reads self.path: give it the plain path
            self.path = path
            return True

        def do_GET(self):
            if self.route():
                super().do_GET()

        def do_HEAD(self):
            if self.route():
                super().do_HEAD()

    return Pages


def serve(directory, port, quiet=False):
    server = ThreadingHTTPServer(("127.0.0.1", port), handler(directory, quiet))
    return server


def run_go(server, args, sumdb=True):
    """Run the go command with this server as the only way to go.octolab.org.

    sumdb=False skips the checksum database for go.octolab.org: it resolves a
    module through the live site, which does not know a module this build is
    the first to publish."""
    go = shutil.which("go")
    if not go:
        raise SystemExit("--go needs the go command on PATH")
    proxy = f"http://127.0.0.1:{server.server_address[1]}"
    with tempfile.TemporaryDirectory(prefix="vanity-go.") as home:
        env = {k: v for k, v in os.environ.items() if not k.startswith("GO") and k.lower() not in (
            "http_proxy", "https_proxy", "no_proxy", "all_proxy")}
        env.update({
            "GOPATH": str(Path(home, "gopath")),
            "GOMODCACHE": str(Path(home, "gopath", "pkg", "mod")),
            "GOCACHE": str(Path(home, "cache")),
            "GOFLAGS": "-modcacherw",
            "GOENV": "off",  # nothing saved with go env -w applies
            "GOWORK": "off",
            "GOPROXY": "direct",
            "GOSUMDB": "sum.golang.org",
            "GONOPROXY": "",
            "GOINSECURE": HOST,
            "GOPRIVATE": "",
            "GONOSUMDB": "" if sumdb else HOST,
            "GOTOOLCHAIN": "local",
            "GIT_TERMINAL_PROMPT": "0",
            "HTTP_PROXY": proxy, "http_proxy": proxy,
            "HTTPS_PROXY": proxy, "https_proxy": proxy,
            "NO_PROXY": DIRECT, "no_proxy": DIRECT,
        })
        # an empty module, so that go get has a go.mod to add to
        work = Path(home, "work")
        work.mkdir()
        Path(work, "go.mod").write_text("module example.com/resolve\n\ngo 1.21\n", encoding="utf-8")
        return subprocess.run([go, *args], cwd=work, env=env).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", nargs="?", type=Path, default=ROOT / "dist")
    parser.add_argument("--port", type=int, default=8040, help="port on 127.0.0.1 (default 8040; 0 picks one with --go)")
    parser.add_argument("--go", action="store_true", help="run the go command given after -- against DIR, then exit")
    parser.add_argument("--no-sumdb", action="store_true",
                        help="with --go, do not ask sum.golang.org about go.octolab.org modules")
    argv = sys.argv[1:]
    go_args = argv[argv.index("--") + 1:] if "--" in argv else []
    args = parser.parse_args(argv[:argv.index("--")] if "--" in argv else argv)
    if not (args.directory / "index.html").is_file():
        parser.error(f"{args.directory} has no index.html; build it first: make")
    if args.go and not go_args:
        parser.error("--go needs the arguments of the go command after --")
    if go_args and not args.go:
        parser.error("arguments after -- need --go")

    server = serve(args.directory, 0 if args.go and args.port == 8040 else args.port, quiet=args.go)
    if args.go:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            code = run_go(server, go_args, sumdb=not args.no_sumdb)
        finally:
            server.shutdown()
        raise SystemExit(code)
    host, port = server.server_address[:2]
    print(f"Serving {args.directory} at http://{host}:{port}/ (Ctrl+C to stop)")
    print(f"  people:  http://{host}:{port}/   http://{host}:{port}/toolset/indexit/")
    print(f"  go:      curl -s 'http://{host}:{port}/toolset/indexit?go-get=1' -L | grep go-import")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
