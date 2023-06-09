# seed writes modules/*.json once from the submodules of a past revision, the
# migration of issue 500: ./Taskfile seed --action <vanity-action checkout>
# --rev 0f56e6a. Needs gh with read access to the private repositories, Go and
# Node. Delete it and bin/seed.py once the entries are committed.
seed() {
  python3 "${root}/bin/seed.py" "${@}"
}
