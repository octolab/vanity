# shellcheck source=modules.bash # modules validate

compile() (
  local build
  build=$(mktemp -d "${root}/.dist.XXXXXX") || return
  trap 'rm -rf "${build}"' EXIT
  validate || return
  modules >"${build}/modules.yml" || return

  maintainer go vanity build -f "${build}/modules.yml" "${build}" || return
  python3 "${root}/bin/verify.py" --root "${root}" "${build}" || return
  rm -rf "${root}/dist"
  mv "${build}" "${root}/dist"
)

verify() {
  python3 "${root}/bin/verify.py" --root "${root}" "${root}/dist"
}
