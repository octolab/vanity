#!/usr/bin/env bash
# Read-only check of go.octolab.org and the catalog after a deploy.
#
#   bin/verify-live.sh                     # module roots + delivery + catalog tags
#   bin/verify-live.sh --packages          # + every package page and the served modules.yml
#   bin/verify-live.sh --packages --module go.octolab.org/template/module
#
# Runs bin/verify.py of this checkout against the entries of main (a temporary
# export, read as data: main's own code never runs), requires the delivery run
# of main to be green and the live deployment to be main, and checks the
# catalog tags <name>--vX.Y.Z: authored by the Releaser App, verified, on main,
# the entry at the tag holds that name and version; every published version
# has its tag. Needs gh signed in with read access, jq, git, python3.
# Exit 1 on any failure.
set -euo pipefail
if ((BASH_VERSINFO[0] < 4)); then
  echo 'bash 4 or newer is needed (brew install bash)' >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO=octolab/vanity
RELEASER_BOT='octolab-releaser[bot]'

section() { printf '\n== %s\n' "$*"; }
note() { printf '  · %s\n' "$*"; }
ok() { printf '  OK    %s\n' "$*"; }
warn() { printf '  WARN  %s\n' "$*"; }
bad() { printf '  BLOCK %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
# gh_quiet: a read-only gh api call; on failure (e.g. 404) it prints nothing
gh_quiet() {
  local out
  out=$(gh api "$@" 2>/dev/null) || return 1
  [[ -z ${out} ]] || printf '%s\n' "${out}"
}

PACKAGES=()
MODS=()
while (($#)); do
  case $1 in
    --packages) PACKAGES=(--packages) ;;
    --module) MODS+=(--module "${2:?}"); shift ;;
    -h | --help) sed -n '2,14p' "$0"; exit 0 ;;
    *) die "unknown argument $1" ;;
  esac
  shift
done
for tool in gh jq git python3; do command -v "${tool}" >/dev/null || die "${tool} is not on PATH"; done
fail=0

section 'delivery'
main=$(gh api "repos/${REPO}/git/ref/heads/main" --jq .object.sha)
tmp=$(mktemp -d)
trap 'rm -rf "${tmp}"' EXIT
# main's entries as DATA only, from the API tarball; the verifier that runs is
# this checkout's, never main's own code
gh api "repos/${REPO}/tarball/${main}" >"${tmp}/main.tgz" || die 'cannot download main'
mkdir "${tmp}/main"
tar -xzf "${tmp}/main.tgz" -C "${tmp}/main" --strip-components 1
migrated=false
[[ -d ${tmp}/main/modules ]] && migrated=true
base=''
while read -r did sha; do
  st=$(gh api "repos/${REPO}/deployments/${did}/statuses?per_page=1" --jq '.[0].state // ""')
  if [[ ${st} == success ]]; then base=${sha}; break; fi
done < <(gh api "repos/${REPO}/deployments?environment=github-pages&per_page=30" --jq '.[] | "\(.id) \(.sha)"' || die 'cannot list deployments')
if [[ ${migrated} == false ]]; then
  note "main ${main:0:7} has no entries yet (submodules); live deployment ${base:0:7}"
else
  # the newest delivery run of main's commit must be green in every job
  run=$(gh run list -R "${REPO}" --workflow cd.urls.yml --commit "${main}" -L 1 --json databaseId,status,conclusion \
    --jq '.[0] | "\(.databaseId) \(.status) \(.conclusion)"') || die 'cannot list delivery runs'
  read -r run_id run_status run_conclusion <<<"${run:-none none none}"
  if [[ ${run_status} == completed && ${run_conclusion} == success ]]; then
    ok "delivery run ${run_id} on main ${main:0:7}: success"
    gh run view "${run_id}" -R "${REPO}" --json jobs --jq '.jobs[] | "  · \(.name): \(.conclusion)"'
  else
    bad "delivery of main ${main:0:7}: run ${run_id} ${run_status}/${run_conclusion} (paths outside the CD filter: dispatch it)"
    fail=1
  fi
  if [[ ${base} == "${main}" ]]; then ok "live deployment = main ${main:0:7}"; else bad "live deployment ${base:0:7} is not main ${main:0:7}"; fail=1; fi
fi

section "pages (bin/verify.py of ${ROOT}, entries of main)"
[[ -f ${ROOT}/bin/verify.py && -f ${ROOT}/bin/catalog.py ]] || die "no verifier in ${ROOT}/bin"
if [[ ${migrated} == true ]]; then
  root=${tmp}/main
else
  warn 'checking the module roots against the local entries'
  root=${ROOT}
  PACKAGES=()
fi
if python3 -B "${ROOT}/bin/verify.py" --root "${root}" --url https://go.octolab.org "${PACKAGES[@]}" "${MODS[@]}" --attempts 3 --delay 20; then
  ok "verify.py --url https://go.octolab.org ${PACKAGES[*]} ${MODS[*]}"
else
  bad 'verify.py failed'
  fail=1
fi
if [[ ${migrated} == true ]]; then
  python3 -B "${ROOT}/bin/catalog.py" --root "${root}" progress | sed 's/^/  · /' || true
fi

section 'catalog tags'
refs=$(gh api --paginate "repos/${REPO}/git/matching-refs/tags/" --jq '.[] | select(.ref | test("--v")) | "\(.ref) \(.object.sha)"') ||
  die 'cannot list the tags of the catalog'
declare -A module_of
if [[ -d ${root}/modules ]]; then
  while IFS=$'\t' read -r ename emodule; do module_of[${ename}]=${emodule}; done < <(
    find "${root}/modules" -name '*.json' -exec jq -r '[.name, .module] | @tsv' {} +)
fi
n=0
tags=()
while read -r ref sha; do
  [[ -n ${ref} ]] || continue
  tag=${ref#refs/tags/}
  [[ ${tag} =~ ^([a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)*)--(v[0-9]+\.[0-9]+\.[0-9]+)$ ]] || continue
  tname=${BASH_REMATCH[1]}
  tver=${BASH_REMATCH[5]}
  n=$((n + 1))
  tags+=("${tag}")
  info=$(gh api "repos/${REPO}/commits/${sha}" --jq '"\(.author.login // "-") \(.commit.verification.verified)"')
  on_main=$(gh api "repos/${REPO}/compare/${sha}...${main}" --jq .status)
  tmod=${module_of[${tname}]:-}
  at=''
  [[ -z ${tmod} ]] || at=$(gh_quiet "repos/${REPO}/contents/modules/${tmod}.json?ref=${sha}" --jq .content | base64 --decode | jq -r '"\(.name) \(.version)"' || true)
  if [[ ${info} == "${RELEASER_BOT} true" && (${on_main} == ahead || ${on_main} == identical) && ${at} == "${tname} ${tver}" ]]; then
    ok "${tag} -> ${sha:0:7} (${info}, ${on_main}, entry holds ${tver})"
  else
    bad "${tag} -> ${sha:0:7} (${info}, ${on_main}, entry at tag: ${at:-none for ${tmod:-unknown name}})"
    fail=1
  fi
done <<<"${refs}"
note "${n} catalog tags"
if [[ -d ${root}/modules ]]; then
  published=$(find "${root}/modules" -name '*.json' -exec jq -r 'select(.version != null) | "\(.name)--\(.version)"' {} + | sort)
  note "$(grep -c . <<<"${published}" || true) entries with a version on main (the rest are seeds)"
  missing=$(comm -23 <(grep . <<<"${published}" || true) <(printf '%s\n' "${tags[@]}" | sort) | tr '\n' ' ')
  if [[ -n ${missing// /} ]]; then
    bad "published versions without a catalog tag: ${missing}(a re-run of the publication repairs it)"
    fail=1
  fi
fi
exit "${fail}"
