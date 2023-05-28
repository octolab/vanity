# shellcheck source=modules.bash # modules

compile() (
  local build
  build=$(mktemp -d "${root}/.dist.XXXXXX") || return
  trap 'rm -rf "${build}"' EXIT
  modules >"${build}/modules.yml" || return

  maintainer go vanity build -f "${build}/modules.yml" "${build}" || return
  python3 "${root}/bin/verify.py" "${build}" || return
  rm -rf "${root}/dist"
  mv "${build}" "${root}/dist"
)

verify() {
  python3 "${root}/bin/verify.py" "${root}/dist"
}
