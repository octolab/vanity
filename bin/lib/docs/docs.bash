# shellcheck source=../git/core.bash # @root

# docs runs a command in docs/, the catalog page (Nextra on Next.js).
#
# Example: ./Taskfile docs npm ci
# Example: ./Taskfile docs dev          # http://localhost:3000, no go-import tags
# Example: ./Taskfile docs npm i nextra@latest
docs() (
  cd "$(@root)/docs" || return
  case "${1:-}" in
  dev) npx --no-install next dev ;;
  build) rm -rf dist && TARGET=static SITE_URL="${SITE_URL:-https://go.octolab.org/}" npx --no-install next build ;;
  '') echo 'usage: ./Taskfile docs dev|build|<command>' >&2 && return 2 ;;
  *) "${@}" ;;
  esac
)

# demo builds the whole site and serves it at http://127.0.0.1:8040/, as
# GitHub Pages would: the catalog at /, a page per package, 404.html.
demo() (
  cd "$(@root)" || return
  [ -d docs/node_modules ] || (cd docs && npm ci --no-audit --no-fund) || return
  make compile && python3 bin/serve.py dist "${@}"
)

# resolve runs the go command against the build in dist/, not the live site
# (bin/serve.py --go), with an empty module cache, GOPROXY=direct and the
# checksum database on. It proves that go get keeps working with this build
# before it is deployed.
#
# By default it resolves the modules below, which the maintainer chose and
# sum.golang.org already knows: the root module, the toolkits that indexit
# depends on, and a package path, for which go asks for every prefix. The
# delivery blocks on them. With --all it resolves every released public module
# of the catalog at its version, without the checksum database for
# go.octolab.org (a first release is not on the live site yet, which
# sum.golang.org would ask); the delivery only warns about those, since what a
# publisher writes must never stop the deploy.
#
# Example: ./Taskfile resolve
# Example: ./Taskfile resolve --all
resolve() (
  cd "$(@root)" || return
  if [ "${1:-}" != --all ]; then
    python3 bin/serve.py dist --go -- mod download -json \
      go.octolab.org@v0.12.2 \
      go.octolab.org/toolkit/cli@v0.6.4 \
      go.octolab.org/toolkit/config@v0.0.5 >/dev/null || return
    echo 'resolved through this build: go.octolab.org@v0.12.2, toolkit/cli@v0.6.4, toolkit/config@v0.0.5'
    python3 bin/serve.py dist --go -- get go.octolab.org/toolkit/config/http@v0.0.5 || return
    echo 'resolved a package path: go.octolab.org/toolkit/config/http@v0.0.5'
    return
  fi
  local targets
  targets=$(python3 bin/catalog.py site | python3 -c '
import json, sys
data = json.load(sys.stdin)
items = [i for g in data["groups"] for i in g["items"]] + data["unlisted"]
print(" ".join(i["module"] + "@" + i["version"] for i in items if i["version"]))
') || return
  [ -n "${targets}" ] || { echo 'no released public module to resolve' && return; }
  # shellcheck disable=SC2086 # one argument per module@version
  python3 bin/serve.py dist --go --no-sumdb -- mod download -json ${targets} >/dev/null || return
  echo "resolved through this build: ${targets}"
)
