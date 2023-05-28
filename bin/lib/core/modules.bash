modules() {
  local modules module name path git url actual
  modules=$(@modules) || return
  for module in ${modules}; do
    name=$(git config --file .gitmodules --get "submodule.${module}.name") || return
    path=$(git config --file .gitmodules --get "submodule.${module}.path") || return
    git=$(git config --file .gitmodules --get "submodule.${module}.url") || return
    url=${git/#git@github.com:/https://github.com/}
    url=${url%.git}

    if [[ ! -f ${path}/go.mod ]]; then
      echo "Missing ${path}/go.mod; run git submodule update --init first" >&2
      return 1
    fi
    actual=$(cd "${path}" && GO111MODULE=on GOWORK=off GOPROXY=off go list -m) || return
    if [[ ${actual} != "${name}" ]]; then
      echo "Module mismatch in ${path}: expected ${name}, found ${actual}" >&2
      return 1
    fi

    local metadata branch tags packages
    metadata=$(
      gh repo view --json defaultBranchRef,repositoryTopics \
        --jq '[.defaultBranchRef.name, ((.repositoryTopics // []) | map(.name) | join(", "))] | @tsv' \
        "${git}"
    ) || return
    IFS=$'\t' read -r branch tags <<<"${metadata}"
    if [[ -z ${branch} ]]; then
      echo "Missing default branch for ${url}" >&2
      return 1
    fi
    # Module mode can load the dependency graph even with -find on older
    # modules. GOPATH mode only inspects local package directories.
    packages=$(
      cd "${path}" &&
        GO111MODULE=off GOWORK=off GOPROXY=off go list -find -f '{{.Dir}}' ./... |
        while IFS= read -r dir; do
          # Nested go.mod files describe separate modules, not subpackages.
          local parent=${dir}
          while [[ ${parent} != "${PWD}" && ! -f ${parent}/go.mod ]]; do
            parent=${parent%/*}
          done
          [[ ${parent} == "${PWD}" ]] || continue
          printf '%s%s\n' "${name}" "${dir#"${PWD}"}"
        done
    ) || return
    packages=$(printf '%s\n' "${name}" "${packages}" | LC_ALL=C sort -u | sed '/^$/d; s|^|    - |') || return

    cat <<EOF
- prefix: ${name}
  import:
    - url: ${url}
      vcs: git
      source:
        url:  ${url}
        dir:  ${url}/tree/${branch}{/dir}
        file: ${url}/blob/${branch}{/dir}/{file}#L{line}
  packages:
${packages}
  tags: [ ${tags} ]
EOF
  done
}

@modules() {
  git config --file .gitmodules --get-regexp '^submodule\..*\.path$' |
    sed -E 's/^submodule\.(.*)\.path .*/\1/' |
    sort
}
