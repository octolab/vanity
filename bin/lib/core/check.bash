# check is a smoke test of the live site, go.octolab.org, after a deploy.
#
# It covers the modules whose broken discovery stopped indexit's dependency
# jobs (octopot/indexit#102): the root module, toolkit/cli and toolkit/config.
# It answers "can a consumer resolve them right now", not "is the catalog
# complete": for every module root run
#   python3 bin/verify.py --url https://go.octolab.org
#
# Run it after the delivery workflow publishes a new build, with each Go
# version that the consumer's CI uses. Exit status 0 means both steps passed.
check() (
  # 1. Metadata: over verified HTTPS (the certificate must cover the domain),
  #    the go-import and go-source tags of each module must match .gitmodules.
  python3 "${root}/bin/verify.py" --url https://go.octolab.org \
    --module go.octolab.org \
    --module go.octolab.org/toolkit/cli \
    --module go.octolab.org/toolkit/config || return

  # 2. Download, as a consumer without any help would:
  #    - an empty module cache, so nothing warm hides a failure;
  #    - GOPROXY=direct, so Go asks go.octolab.org and then git itself,
  #      not proxy.golang.org, which may still hold an old copy;
  #    - the checksum database on and every bypass (GOINSECURE, GOPRIVATE,
  #      GONOPROXY, GONOSUMDB) empty, so TLS and checksums are enforced;
  #    - GOWORK, GOENV and GOFLAGS off, so a local go.work or `go env -w`
  #      settings do not change the result.
  local cache
  cache=$(mktemp -d) || return
  # Go makes extracted module directories read-only; use its cache cleanup.
  trap 'GOWORK=off GOENV=off GOFLAGS= GOTOOLCHAIN=local GOMODCACHE="${cache}" go clean -modcache' EXIT
  # The versions are the ones indexit requires after the upgrade that followed
  # #102 (the historical config v0.0.4 tag is missing from GitHub). Update them
  # when indexit moves on, or when another consumer becomes the one to watch.
  GOWORK=off GOENV=off GOFLAGS= GOMODCACHE="${cache}" \
    GOPROXY=direct GOINSECURE= GOPRIVATE= GONOPROXY= GONOSUMDB= \
    GOSUMDB=sum.golang.org go mod download -json \
    go.octolab.org@v0.12.0 \
    go.octolab.org@v0.12.2 \
    go.octolab.org/toolkit/cli@v0.6.4 \
    go.octolab.org/toolkit/config@v0.0.5
)
