#!/usr/bin/env bash
# OCTOLAB_RELEASER_CLIENT_ID and OCTOLAB_RELEASER_KEY, the credentials of the
# OctoLab Releaser App, for every repository that publishes with it (the
# catalog entry, the Homebrew tap, the skills catalog). Run by the holder of
# the App's private key.
#
#   bin/releaser-secrets.sh --pem ~/path/octolab-releaser.pem            # dry run: key check, targets, presence
#   bin/releaser-secrets.sh --pem ~/path/octolab-releaser.pem --apply    # sets what is missing, each after a confirmation
#   bin/releaser-secrets.sh --pem ... --apply --force                    # sets everything again: key rotation
#   ... --yes                                                            # no confirmations
#
# Targets (on the Free plan an organization secret never reaches a private
# repository):
#   octomation, octopot   organization secrets, visibility all
#   octolab               organization secret, visibility selected: its public publishers
#   repository secrets    octolab/genome, withsparkle/service, tact-app/{service,inbox,github,trello},
#                         octomation/{dotapps,optflow,secret,tablo}
# The key goes to gh through stdin only: never printed, never on a command
# line. The dry run proves the key belongs to the App: it signs a short-lived
# JWT locally and calls GET /app (read-only). Rotation: generate a new key in
# the App settings, run with --apply --force, then delete the old key there.
set -euo pipefail
if ((BASH_VERSINFO[0] < 4)); then
  echo 'bash 4 or newer is needed (brew install bash)' >&2
  exit 2
fi

APP_SLUG=octolab-releaser
ORGS_ALL=(octomation octopot)
ORG_REPOS=(pkg propaganda cli config protocol breakit parallel testit try)
REPO_TARGETS=(octolab/genome withsparkle/service tact-app/service tact-app/inbox tact-app/github tact-app/trello
  octomation/dotapps octomation/optflow octomation/secret octomation/tablo)
NAMES=(OCTOLAB_RELEASER_CLIENT_ID OCTOLAB_RELEASER_KEY)

say() { printf '%s\n' "$*"; }
section() { printf '\n== %s\n' "$*"; }
note() { printf '  · %s\n' "$*"; }
ok() { printf '  OK    %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
gh_quiet() {
  local out
  out=$(gh api "$@" 2>/dev/null) || return 1
  [[ -z ${out} ]] || printf '%s\n' "${out}"
}

APPLY=false
YES=false
FORCE=false
PEM=''
while (($#)); do
  case $1 in
    --pem) PEM=${2:?--pem needs a path}; shift ;;
    --apply) APPLY=true ;;
    --yes) YES=true ;;
    --force) FORCE=true ;;
    -h | --help) sed -n '2,21p' "$0"; exit 0 ;;
    *) die "unknown argument $1" ;;
  esac
  shift
done
if [[ ${APPLY} == true ]]; then say 'mode: APPLY'; else say 'mode: dry run (add --apply to change anything)'; fi

# confirm asks before a step of --apply; --yes answers yes
confirm() {
  [[ ${APPLY} == true ]] || return 1
  [[ ${YES} == true ]] && return 0
  local answer
  read -r -p "  $* [y/N] " answer </dev/tty
  [[ ${answer} == y || ${answer} == Y ]]
}

# put sets one secret ($1 name, then the gh flags of the target); the key only
# through stdin
put() {
  local name=$1
  shift
  if [[ ${APPLY} != true ]]; then
    say "  [dry-run] gh secret set ${name} $* $([[ ${name} == OCTOLAB_RELEASER_KEY ]] && echo '< <pem>' || echo "--body ${client_id}")"
  elif ! confirm "set ${name} ($*)?"; then
    note 'skipped'
  elif [[ ${name} == OCTOLAB_RELEASER_KEY ]]; then
    gh secret set "${name}" "$@" <"${PEM}"
  else
    gh secret set "${name}" "$@" --body "${client_id}"
  fi
}

for tool in gh jq openssl curl; do command -v "${tool}" >/dev/null || die "${tool} is not on PATH"; done
[[ -n ${PEM} ]] || die 'give the App private key: --pem <path> (it stays on this machine)'
[[ -r ${PEM} ]] || die "cannot read ${PEM}"
openssl pkey -in "${PEM}" -noout 2>/dev/null || die "${PEM} is not a private key"

section 'the key belongs to the App'
client_id=$(gh api "apps/${APP_SLUG}" --jq .client_id)
b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }
now=$(date +%s)
header=$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)
payload=$(printf '{"iat":%d,"exp":%d,"iss":"%s"}' $((now - 60)) $((now + 300)) "${client_id}" | b64url)
signature=$(printf '%s.%s' "${header}" "${payload}" | openssl dgst -sha256 -sign "${PEM}" -binary | b64url)
hfile=$(mktemp)
chmod 600 "${hfile}"
trap 'rm -f "${hfile}"' EXIT
printf 'Authorization: Bearer %s.%s.%s\n' "${header}" "${payload}" "${signature}" >"${hfile}"
slug=$(curl -fsS -H @"${hfile}" -H 'Accept: application/vnd.github+json' https://api.github.com/app | jq -r .slug) || die 'GitHub refused a JWT signed with this key'
rm -f "${hfile}"
[[ ${slug} == "${APP_SLUG}" ]] || die "the key belongs to ${slug}, not ${APP_SLUG}"
ok "key signs for ${slug}; client id ${client_id}"

section 'organization secrets, visibility all'
for org in "${ORGS_ALL[@]}"; do
  for name in "${NAMES[@]}"; do
    vis=$(gh_quiet "orgs/${org}/actions/secrets/${name}" --jq .visibility || true)
    if [[ ${FORCE} == false && ${vis} == all ]]; then ok "${org} ${name}: present"; continue; fi
    note "${org} ${name}: ${vis:-absent}"
    put "${name}" --org "${org}" --visibility all
  done
done

section 'octolab organization secret, visibility selected'
want_ids=$(for r in "${ORG_REPOS[@]}"; do gh api "repos/octolab/${r}" --jq .id; done | sort -n | tr '\n' ' ')
list=$(IFS=,; echo "${ORG_REPOS[*]}")
for name in "${NAMES[@]}"; do
  vis=$(gh_quiet "orgs/octolab/actions/secrets/${name}" --jq .visibility || true)
  have_ids=''
  [[ ${vis} != selected ]] || have_ids=$(gh api --paginate "orgs/octolab/actions/secrets/${name}/repositories" --jq '.repositories[].id' | sort -n | tr '\n' ' ')
  if [[ ${FORCE} == false && ${vis} == selected && ${have_ids} == "${want_ids}" ]]; then
    ok "${name}: present for the ${#ORG_REPOS[@]} repositories"
    continue
  fi
  note "${name}: ${vis:-absent}${have_ids:+ (${have_ids})}"
  put "${name}" --org octolab --visibility selected --repos "${list}"
done

section 'repository secrets'
for repo in "${REPO_TARGETS[@]}"; do
  have=$(gh api "repos/${repo}/actions/secrets" --jq '[.secrets[].name] | join(",")')
  for name in "${NAMES[@]}"; do
    if [[ ${FORCE} == false && ,${have}, == *,${name},* ]]; then ok "${repo} ${name}: present"; continue; fi
    put "${name}" -R "${repo}"
  done
done
say ''
say '  rollback: gh secret delete <NAME> -R <repo> | --org <org>'
