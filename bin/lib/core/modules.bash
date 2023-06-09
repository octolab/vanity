# modules prints the Maintainer manifest built from the entries in modules/.
modules() {
  python3 "${root}/bin/catalog.py" --root "${root}" manifest
}

# validate checks every entry and the catalog invariants, offline.
validate() {
  python3 "${root}/bin/catalog.py" --root "${root}" check
}

# tests runs the tests of the catalog tools.
tests() {
  python3 -m unittest discover -s "${root}/bin/tests" "${@}"
}
